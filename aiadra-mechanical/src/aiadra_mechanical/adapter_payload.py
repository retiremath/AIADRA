"""Engine-opaque `adapter_payload` shapes for mechanical features.

Per ADR/0029 D7 sketch primitives + extrude op-data stay OPAQUE to
aiadra-core (the bundle schema only checks `adapter_payload` IS an object).
This module pins the payload format (adapter_schema_version 0.1.10 since SK-C1.0 S2: the face-plane binding; 0.1.9 since SK-C0: arc segments + circle-as-outer + construction; 0.1.1 since arc
20260609-1 added engine-minted `skp_` primitive ids — see `build_sketch_payload`)
and performs **domain/payload validation** — Class-1 failures per ADR/0031
D6/B2: malformed or out-of-domain inputs raise `TransactionError` (a
passthrough exception) BEFORE the kernel is touched, so they are never
laundered as kernel instability.

Per ADR/0031 D6 + Wedge-003 Codex1 B1: extrude `depth_mm` is NOT in the
payload — it lives in `feature.parameters[]` as a first-class
canonical-unit-bearing Product-Truth record. The payload references the
parameter id so the kernel can correlate it during evaluation.
"""
from __future__ import annotations

import math
from typing import Any

from aiadra_core.transaction.boundary import TransactionError

from .arc_geometry import (arc_geometry, bulge_domain_error,
                           circular_segment_area, point_on_arc_span)
from .recipe import EXTRUDE_DIRECTIONS, validate_plane_record

# Sketch primitive shapes carried in feature.adapter_payload["primitives"]:
#   {"type": "rectangle", "x_mm": float, "y_mm": float, "width_mm": float, "height_mm": float}
#   {"type": "circle", "cx_mm": float, "cy_mm": float, "radius_mm": float}
#   {"type": "line", "x1_mm": float, "y1_mm": float, "x2_mm": float, "y2_mm": float}
#   {"type": "contour", "segments": [ {"kind": "line"|"arc", "x1_mm", "y1_mm", "x2_mm", "y2_mm"[, "bulge"]}, … ]}
#     arc 20260711-11 slice E + SK-C0 (0.1.9): an arbitrary CLOSED-RING outer
#     profile of typed segments. kind="arc" carries bulge=tan(sweep/4)
#     (minor arcs only; see arc_geometry.py). Each segment is an explicit,
#     engine-anchored wall producer; there is NO implicit auto-closing edge
#     (Codex4 B1). Every primitive MAY carry construction: true (SK-C0 D-C3) —
#     top-level/atomic; guides are display-only, excluded from profiles,
#     BREP, and the 3D topology signature.

_SKETCH_PRIMITIVE_REQUIRED_KEYS = {
    "rectangle": {"type", "x_mm", "y_mm", "width_mm", "height_mm"},
    "circle": {"type", "cx_mm", "cy_mm", "radius_mm"},
    "line": {"type", "x1_mm", "y1_mm", "x2_mm", "y2_mm"},
    "contour": {"type", "segments"},
}

# The outer profiles (exactly one per sketch); a circle may be a hole (with a
# rectangle) or — since 0.1.9 (SK-C0 D-C2) — stand alone as the outer profile.
_OUTER_PROFILE_TYPES = {"rectangle", "contour"}
# Segment kinds a v1 contour may carry. SK-C0 D-C1 activates "arc" (bulge
# convention, minor arcs only — see arc_geometry.py); spline stays reserved.
_SUPPORTED_SEGMENT_KINDS = {"line", "arc"}
_SEGMENT_REQUIRED_KEYS = {
    "line": {"kind", "x1_mm", "y1_mm", "x2_mm", "y2_mm"},
    "arc": {"kind", "x1_mm", "y1_mm", "x2_mm", "y2_mm", "bulge"},
}
# Tolerance (mm) for contour ring continuity/closure — generous vs the kernel.
_CONTOUR_TOL = 1e-6


def build_sketch_payload(
    primitives: list[dict[str, Any]], plane: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build (and domain-validate) the adapter_payload for a sketch feature.

    Per arc 20260609-1 Codex1 B2: each primitive is assigned a **stable,
    engine-minted `skp_NNNN` id** at authoring time. This is the
    primitive-level role anchor the Display Representation topology-identity
    scheme (ADR/0035) needs — face/edge display IDs derive from a primitive's
    `skp_` id, NOT from its position in the list (which is not stable once a
    sketch carries multiple same-type primitives). The id is engine-opaque to
    `aiadra-core` (the bundle schema only checks `adapter_payload` IS an
    object). It IS part of the canonical recipe → it participates in
    `vault_ref` identity (intentional: the primitive anchor is geometry
    identity, not incidental metadata). Bumps `adapter_schema_version` 0.1.0
    → 0.1.1.
    """
    _validate_sketch_primitives(primitives)
    out: list[dict[str, Any]] = []
    for i, p in enumerate(primitives, start=1):
        prim = dict(p)
        # Engine-minted stable id; a caller-supplied id is rejected so the
        # engine remains the sole minter (no spoofed anchors).
        if "id" in prim:
            raise TransactionError(
                f"mechanical.add_sketch_feature: primitive[{i - 1}] must not "
                f"carry a caller-supplied 'id'; the engine mints skp_ ids"
            )
        prim["id"] = f"skp_{i:04d}"
        if prim.get("type") == "contour":
            # arc 20260711-11 slice E (Codex4 B1): every wall-producing segment —
            # including the closing one — gets its own engine-minted stable id,
            # nested under the contour. This is the anchor for the wall role +
            # the signature skeleton (D-E2); there is no unanchored implicit edge.
            prim["segments"] = _mint_segment_ids(prim["id"], prim["segments"])
        out.append(prim)
    payload: dict[str, Any] = {"primitives": out}
    # The sketch-plane binding (arc 20260714-2 EP2; Codex1 B3): a discriminated
    # record, validated EXACTLY at write time; stored faithfully as passed.
    # Absent ≡ principal xy (legacy semantics preserved byte-for-byte).
    if plane is not None:
        kind = validate_plane_record(plane, op_kind="mechanical.add_sketch_feature")
        if kind == "face":
            # SK-C1.0 S2 (Codex7 B1): the STORED face reference persists
            # VERBATIM (kind + face_role + resolved_against — the validated
            # exact shape); normalization is a principal-plane concern.
            payload["plane"] = {
                "kind": "face",
                "face_role": plane["face_role"],
                "resolved_against_topology_signature": plane["resolved_against_topology_signature"],
            }
        else:
            payload["plane"] = {"kind": "principal", "orientation": kind}
    return payload


def _mint_segment_ids(contour_id: str, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    minted: list[dict[str, Any]] = []
    for k, seg in enumerate(segments, start=1):
        s = dict(seg)
        if "id" in s:
            raise TransactionError(
                f"mechanical.add_sketch_feature: contour segment[{k - 1}] must not "
                f"carry a caller-supplied 'id'; the engine mints segment ids"
            )
        s["id"] = f"{contour_id}s{k:02d}"
        minted.append(s)
    return minted


def build_extrude_payload(
    *, sketch_feature_id: str, direction: str, depth_parameter_id: str,
    operation: str = "add",
) -> dict[str, Any]:
    """Build (and domain-validate) the adapter_payload for an extrude feature.

    `depth_mm` lives in `feature.parameters[]`; this payload references the
    parameter id so the kernel can correlate it.
    """
    # EP2 (Codex1 B3): `normal±` is the canonical vocabulary; legacy `z±`
    # remains accepted here structurally — the HANDLER gates z± to principal-xy
    # sketches (it holds the resolved sketch) and stores canonical `normal±`
    # for new writes; the evaluator re-gates on every regeneration.
    if direction not in EXTRUDE_DIRECTIONS:
        raise TransactionError(
            f"mechanical.add_extrude_feature: direction must be one of "
            f"{list(EXTRUDE_DIRECTIONS)}, got {direction!r}"
        )
    if not depth_parameter_id.startswith("featp_"):
        raise TransactionError(
            f"mechanical.add_extrude_feature: depth_parameter_id must match featp_NNNN, "
            f"got {depth_parameter_id!r}"
        )
    if not sketch_feature_id.startswith("feat_"):
        raise TransactionError(
            f"mechanical.add_extrude_feature: sketch_feature_id must match feat_NNNN, "
            f"got {sketch_feature_id!r}"
        )
    # ADR/0038 A4 (arc 20260717-2): the STRUCTURAL operation — add fuses,
    # cut removes material. Skeleton-bearing (add vs cut cannot share a
    # topology signature); independent of `direction` (never inferred).
    # Absent in legacy 0.1.10 payloads ≡ "add"; NEW writes always emit it.
    if operation not in ("add", "cut"):
        raise TransactionError(
            f"mechanical.add_extrude_feature: operation must be 'add' or 'cut', "
            f"got {operation!r}"
        )
    return {
        "sketch_feature_id": sketch_feature_id,
        "direction": direction,
        "depth_parameter_id": depth_parameter_id,
        "operation": operation,
    }


def build_revolve_payload(*, sketch_feature_id: str, axis: str) -> dict[str, Any]:
    """Build (and domain-validate) the adapter_payload for a revolve feature
    (arc 20260622-4). The `axis` (`"x"`/`"y"` — an in-plane global axis) is
    STRUCTURAL (it is part of the topology skeleton, ADR/0038 A2 spirit), so it
    lives in the payload, not in `parameters[]`. v1 is a full 360° revolve, so
    there is no angle parameter."""
    if axis not in ("x", "y"):
        raise TransactionError(
            f"mechanical.add_revolve_feature: axis must be 'x' or 'y', got {axis!r}"
        )
    if not sketch_feature_id.startswith("feat_"):
        raise TransactionError(
            f"mechanical.add_revolve_feature: sketch_feature_id must match feat_NNNN, "
            f"got {sketch_feature_id!r}"
        )
    return {"sketch_feature_id": sketch_feature_id, "axis": axis}


_EDGE_KINDS = {"sharp", "tangent", "seam", "boundary", "free"}


def build_edge_reference_payload(
    *,
    operation_kind: str,
    adjacent_face_roles: list[str],
    edge_kind: str,
    resolved_against_topology_signature: str,
) -> dict[str, Any]:
    """Build (and domain-validate) a `target_edge` `adapter_payload` — the
    engine-owned, recipe-anchored edge reference (ADR/0038 D2) shared by every
    edge-referencing feature (fillet, chamfer; arc 20260622-3 Codex1 Q1). The
    persisted reference is structured recipe roles + edge kind + the parent-prefix
    topology signature it resolved against — NEVER the read-side Display
    Representation `edge_id` string (ADR/0038 D1). The feature's value parameter
    (`radius_mm` / `distance_mm`) is NOT here — it lives in `feature.parameters[]`
    as a first-class canonical-unit record (ADR/0038 A2). `operation_kind` keeps
    diagnostics operation-specific."""
    if not isinstance(adjacent_face_roles, list) or len(adjacent_face_roles) != 2:
        raise TransactionError(
            f"{operation_kind}: target_edge needs exactly two adjacent "
            f"face roles (v1 single sharp edge), got {adjacent_face_roles!r}"
        )
    if not all(isinstance(r, str) and r for r in adjacent_face_roles):
        raise TransactionError(
            f"{operation_kind}: adjacent_face_roles must be non-empty strings"
        )
    if edge_kind not in _EDGE_KINDS:
        raise TransactionError(
            f"{operation_kind}: edge_kind must be one of "
            f"{sorted(_EDGE_KINDS)}, got {edge_kind!r}"
        )
    if (
        not isinstance(resolved_against_topology_signature, str)
        or not resolved_against_topology_signature.startswith("topo_")
    ):
        raise TransactionError(
            f"{operation_kind}: resolved_against_topology_signature must be a "
            f"'topo_' signature, got {resolved_against_topology_signature!r}"
        )
    return {
        "target_edge": {
            # Codex1 N2 (arc 20260621-2): sort at write time so the stored order
            # is deterministic + the reference compares stably across regenerate.
            "adjacent_face_roles": sorted(adjacent_face_roles),
            "edge_kind": edge_kind,
            "resolved_against_topology_signature": resolved_against_topology_signature,
        }
    }


def build_fillet_payload(
    *, adjacent_face_roles: list[str], edge_kind: str, resolved_against_topology_signature: str
) -> dict[str, Any]:
    """Fillet's `target_edge` payload (operation-specific diagnostics)."""
    return build_edge_reference_payload(
        operation_kind="mechanical.add_fillet_feature",
        adjacent_face_roles=adjacent_face_roles,
        edge_kind=edge_kind,
        resolved_against_topology_signature=resolved_against_topology_signature,
    )


def build_chamfer_payload(
    *, adjacent_face_roles: list[str], edge_kind: str, resolved_against_topology_signature: str
) -> dict[str, Any]:
    """Chamfer's `target_edge` payload — same shape as the fillet's (the edge
    reference is shared, ADR/0038 D2); operation-specific diagnostics."""
    return build_edge_reference_payload(
        operation_kind="mechanical.add_chamfer_feature",
        adjacent_face_roles=adjacent_face_roles,
        edge_kind=edge_kind,
        resolved_against_topology_signature=resolved_against_topology_signature,
    )


def build_hole_payload(
    *, face_role: str, resolved_against_topology_signature: str
) -> dict[str, Any]:
    """Build (and domain-validate) the hole `adapter_payload` — the engine-owned,
    recipe-anchored **`target_face` reference** (ADR/0038 A1). Stores ONLY the
    face role + the parent-prefix signature; surface-kind/cap-only is an
    operation-scope guard at the handler, not part of the reference shape
    (Codex1 N1). `diameter_mm`/`center_x_mm`/`center_y_mm` are NOT here — they are
    first-class `feature.parameters[]` records (canonical units), and are VALUE
    parameters excluded from the topology skeleton (ADR/0038 A2)."""
    if not isinstance(face_role, str) or not face_role:
        raise TransactionError(
            f"mechanical.add_hole_feature: face_role must be a non-empty string, got {face_role!r}"
        )
    if (
        not isinstance(resolved_against_topology_signature, str)
        or not resolved_against_topology_signature.startswith("topo_")
    ):
        raise TransactionError(
            f"mechanical.add_hole_feature: resolved_against_topology_signature must be a "
            f"'topo_' signature, got {resolved_against_topology_signature!r}"
        )
    return {
        "target_face": {
            "face_role": face_role,
            "resolved_against_topology_signature": resolved_against_topology_signature,
        }
    }


def require_hole_inside_rectangle(
    rectangle: dict[str, Any], center_x_mm: float, center_y_mm: float, radius_mm: float
) -> None:
    """Class-1 fit-within-face check (ADR/0038 A2 / Codex1 B3, arc 20260622-2):
    the circular footprint must lie entirely inside the cap's outer boundary (the
    rectangle). A simple cap only (no inner cutouts) is guaranteed by
    `require_simple_cap_fit`, so the rectangle IS the usable face boundary."""
    x = float(rectangle["x_mm"]); y = float(rectangle["y_mm"])
    w = float(rectangle["width_mm"]); h = float(rectangle["height_mm"])
    if (
        (center_x_mm - radius_mm) < x
        or (center_x_mm + radius_mm) > (x + w)
        or (center_y_mm - radius_mm) < y
        or (center_y_mm + radius_mm) > (y + h)
    ):
        raise TransactionError(
            f"mechanical.add_hole_feature: hole (centre=({center_x_mm}, {center_y_mm}), "
            f"radius={radius_mm}) must fit entirely inside the cap rectangle "
            f"[{x}..{x + w}] x [{y}..{y + h}]"
        )


def require_simple_cap_fit(
    features: list[dict[str, Any]],
    center_x_mm: float,
    center_y_mm: float,
    radius_mm: float,
) -> None:
    """The full v1 hole domain contract (Codex2 B1, arc 20260622-2): a SIMPLE cap
    (no existing cutout) + the circular footprint fitting inside the rectangle.
    Called BOTH at the handler (early errors) AND inside the evaluator fold, so
    EVERY regeneration / parameter-edit path enforces it — a later `diameter_mm`
    / `center_*_mm` edit that would breach the cap fails Class-1 before the
    kernel, never as a side-breaching cut or a Class-2 surprise. `features` is the
    parent prefix (the hole excluded), so a sketch circle or a prior hole feature
    there means a non-simple cap."""
    sketch = next((f for f in features if f.get("feature_type") == "sketch"), None)
    all_prims = (sketch.get("adapter_payload", {}) if sketch else {}).get("primitives", [])
    # SK-C0 Codex3 B2: THE classifier is the one whole-list authority here too.
    from .profile_classify import classify_sketch

    cls = classify_sketch(all_prims)
    if cls.hole_index is not None or any(
        f.get("feature_type") == "hole" for f in features
    ):
        raise TransactionError(
            "mechanical.add_hole_feature: v1 supports a simple cap only — the cap "
            "already has a cutout (a sketch hole or a prior hole feature). "
            "Unsupported target face for v1."
        )
    if cls.outer_kind != "rectangle":
        raise TransactionError(
            "mechanical.add_hole_feature: the sketch has no rectangle profile"
        )
    rectangle = all_prims[cls.outer_index]
    require_hole_inside_rectangle(rectangle, center_x_mm, center_y_mm, radius_mm)


def _validate_sketch_primitives(primitives: list[dict[str, Any]]) -> None:
    """Per-primitive SHAPE/domain validation, then the whole-list semantics via
    THE classifier (SK-C0 B3: `classify_sketch` is the single interpretation
    authority — outer/hole/construction/topology-contributing; every
    unsupported combination fails loud there). Shape checks run for ALL
    primitives including construction guides (a construction circle with a
    negative radius is still Class-1 invalid)."""
    # SK-C0 Codex3 B2: the converged matrix makes EMPTY (like all-construction)
    # a VALID sketch-only artifact — the classifier below is the one authority
    # (outer_kind 'none'); no pre-classification rejection contradicts it.
    for i, prim in enumerate(primitives):
        kind = prim.get("type")
        if kind not in _SKETCH_PRIMITIVE_REQUIRED_KEYS:
            raise TransactionError(
                f"mechanical.add_sketch_feature: primitive[{i}] unknown type {kind!r}; "
                f"expected one of {sorted(_SKETCH_PRIMITIVE_REQUIRED_KEYS)}"
            )
        missing = _SKETCH_PRIMITIVE_REQUIRED_KEYS[kind] - set(prim)
        if missing:
            raise TransactionError(
                f"mechanical.add_sketch_feature: primitive[{i}] type={kind!r} "
                f"missing keys: {sorted(missing)}"
            )
        if kind == "rectangle":
            if prim["width_mm"] <= 0 or prim["height_mm"] <= 0:
                raise TransactionError(
                    f"mechanical.add_sketch_feature: primitive[{i}] rectangle "
                    f"width_mm/height_mm must be positive, got "
                    f"width={prim['width_mm']!r} height={prim['height_mm']!r}"
                )
        elif kind == "circle":
            if prim["radius_mm"] <= 0:
                raise TransactionError(
                    f"mechanical.add_sketch_feature: primitive[{i}] circle "
                    f"radius_mm must be positive, got {prim['radius_mm']!r}"
                )
        elif kind == "line":
            (x1, y1), (x2, y2) = (
                (float(prim["x1_mm"]), float(prim["y1_mm"])),
                (float(prim["x2_mm"]), float(prim["y2_mm"])),
            )
            if math.hypot(x2 - x1, y2 - y1) <= _CONTOUR_TOL:
                raise TransactionError(
                    f"mechanical.add_sketch_feature: primitive[{i}] line is zero-length"
                )
        elif kind == "contour":
            require_valid_contour(prim, index=i)
    # The whole-list semantics — ONE authority (SK-C0 B3).
    from .profile_classify import classify_sketch

    classify_sketch(primitives)


def require_valid_contour(contour: dict[str, Any], *, index: int | str = "?") -> None:
    """Class-1 domain contract for a `contour` outer profile (arc 20260711-11
    slice E; SK-C0 D-C1). An ordered CLOSED RING of typed segments —
    `kind:"line"` and `kind:"arc"` (bulge, minor arcs only; see
    arc_geometry.py); spline stays reserved. Rejected BEFORE the kernel
    (ADR/0031 D6): unsupported kinds, malformed segments, out-of-domain bulge,
    gaps, fewer than three segments, zero-length chords, zero curve-corrected
    area, and any curve-aware pair conflict (touch counts; adjacent pairs
    exempt only their shared authored endpoint; adjacent co-circular arcs
    reject; tangent line-arc joints are allowed). There is NO implicit closing
    edge (Codex4 B1). Called at write time AND inside the evaluator fold so a
    stored/edited/corrupt recipe fails Class-1 on every regeneration."""
    where = f"mechanical.add_sketch_feature: contour primitive[{index}]"
    segments = contour.get("segments")
    if not isinstance(segments, list) or not segments:
        raise TransactionError(f"{where} must carry a non-empty 'segments' list")
    if len(segments) < 3:
        raise TransactionError(
            f"{where} needs at least 3 segments to bound an area, got {len(segments)}"
        )
    for k, seg in enumerate(segments):
        if not isinstance(seg, dict):
            raise TransactionError(f"{where} segment[{k}] must be an object")
        skind = seg.get("kind")
        if skind not in _SUPPORTED_SEGMENT_KINDS:
            raise TransactionError(
                f"{where} segment[{k}] kind {skind!r} is not supported in v1 "
                f"(supported: {sorted(_SUPPORTED_SEGMENT_KINDS)}; arc/spline reserved)"
            )
        missing = _SEGMENT_REQUIRED_KEYS[skind] - set(seg)
        if missing:
            raise TransactionError(
                f"{where} segment[{k}] kind={skind!r} missing keys: {sorted(missing)}"
            )
        (sx, sy), (ex, ey) = _seg_points(seg)
        if math.hypot(ex - sx, ey - sy) <= _CONTOUR_TOL:
            raise TransactionError(f"{where} segment[{k}] is zero-length")
        if skind == "arc":
            reason = bulge_domain_error(seg.get("bulge"))
            if reason is not None:
                raise TransactionError(f"{where} segment[{k}]: {reason}")

    # Closed ring (Codex4 B1): seg[k].end == seg[k+1].start, wrapping — no gaps,
    # no hidden auto-closing edge. Vertices are the ordered segment start points.
    n = len(segments)
    for k in range(n):
        _, end = _seg_points(segments[k])
        nxt_start, _ = _seg_points(segments[(k + 1) % n])
        if math.hypot(end[0] - nxt_start[0], end[1] - nxt_start[1]) > _CONTOUR_TOL:
            raise TransactionError(
                f"{where} is not a closed ring: segment[{k}] end {end} does not meet "
                f"segment[{(k + 1) % n}] start {nxt_start} (a gap; contours must close "
                f"on an authored segment — no implicit closing edge)"
            )
    # Curve-aware signed area (SK-C0 D-C1): the chord-polygon shoelace PLUS the
    # signed circular-segment correction of every arc (left-bow positive).
    verts = [_seg_points(s)[0] for s in segments]
    geoms = [_seg_geometry(s) for s in segments]
    area = _signed_area(verts)
    for _kind, _pts, garc in geoms:
        if garc is not None:
            area += circular_segment_area(garc)
    if abs(area) <= _CONTOUR_TOL:
        raise TransactionError(f"{where} encloses zero area (degenerate ring)")

    # Curve-aware simple-wire contract (SK-C0 B1): exact primitive-pair
    # predicates over every pair. TOUCH COUNTS as intersection; the ONLY
    # exemption is the one shared authored endpoint of adjacent segments.
    # Adjacency also carries the one-wall-per-segment preconditions:
    #   line+line   collinear at the joint      -> REJECT (redundant vertex/fold-back)
    #   arc+arc     co-circular at the joint    -> REJECT (same-cylinder merge risk)
    #   line+arc    tangent or not              -> ALLOWED (plane vs cylinder)
    n = len(segments)
    for i in range(n):
        for j in range(i + 1, n):
            adjacent = (j == i + 1) or (i == 0 and j == n - 1)
            shared = None
            if adjacent:
                shared = _seg_points(segments[j])[0] if j == i + 1 else _seg_points(segments[i])[0]
            reason = _segment_pair_conflict(geoms[i], geoms[j], adjacent, shared)
            if reason is not None:
                raise TransactionError(f"{where}: segment[{i}] vs segment[{j}]: {reason}")


def _seg_points(seg: dict[str, Any]) -> tuple[tuple[float, float], tuple[float, float]]:
    return (
        (float(seg["x1_mm"]), float(seg["y1_mm"])),
        (float(seg["x2_mm"]), float(seg["y2_mm"])),
    )


def _signed_area(verts: list[tuple[float, float]]) -> float:
    """Shoelace signed area of the vertex ring (mm²)."""
    n = len(verts)
    s = 0.0
    for i in range(n):
        x0, y0 = verts[i]
        x1, y1 = verts[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return 0.5 * s


def _seg_geometry(seg: dict[str, Any]):
    """('line'|'arc', ((x1,y1),(x2,y2)), ArcGeometry|None) for one segment."""
    pts = _seg_points(seg)
    if seg.get("kind") == "arc":
        (x1, y1), (x2, y2) = pts
        return "arc", pts, arc_geometry(x1, y1, x2, y2, float(seg["bulge"]))
    return "line", pts, None


def _near(p, q, tol=_CONTOUR_TOL) -> bool:
    return math.hypot(p[0] - q[0], p[1] - q[1]) <= tol


def _line_circle_hits(a, b, center, radius) -> list[tuple[float, float]]:
    """Contact points of closed segment a-b with the FULL circle (center, r)."""
    ax, ay = a
    dx, dy = b[0] - a[0], b[1] - a[1]
    fx, fy = ax - center[0], ay - center[1]
    A = dx * dx + dy * dy
    B = 2.0 * (fx * dx + fy * dy)
    C = fx * fx + fy * fy - radius * radius
    disc = B * B - 4.0 * A * C
    # tangential touch counts: accept discriminant within tolerance of zero
    if disc < -_CONTOUR_TOL * A:
        return []
    disc = max(disc, 0.0)
    hits = []
    for t in ((-B - math.sqrt(disc)) / (2 * A), (-B + math.sqrt(disc)) / (2 * A)):
        if -_CONTOUR_TOL <= t <= 1.0 + _CONTOUR_TOL:
            p = (ax + t * dx, ay + t * dy)
            if not any(_near(p, q) for q in hits):
                hits.append(p)
    return hits


def _circle_circle_hits(c1, r1, c2, r2):
    """Contact points of two DISTINCT circles ('cocircular' if same circle)."""
    d = math.hypot(c2[0] - c1[0], c2[1] - c1[1])
    if d <= _CONTOUR_TOL and abs(r1 - r2) <= _CONTOUR_TOL:
        return "cocircular"
    if d > r1 + r2 + _CONTOUR_TOL or d < abs(r1 - r2) - _CONTOUR_TOL:
        return []
    d = max(d, 1e-12)
    a = (r1 * r1 - r2 * r2 + d * d) / (2.0 * d)
    h2 = r1 * r1 - a * a
    h = math.sqrt(max(h2, 0.0))
    ux, uy = (c2[0] - c1[0]) / d, (c2[1] - c1[1]) / d
    mx, my = c1[0] + a * ux, c1[1] + a * uy
    p1 = (mx - h * uy, my + h * ux)
    p2 = (mx + h * uy, my - h * ux)
    return [p1] if _near(p1, p2) else [p1, p2]


def _segment_pair_conflict(gi, gj, adjacent: bool, shared) -> str | None:
    """The exact pair predicate (SK-C0 B1). Returns a reason or None.
    Touch counts as intersection; adjacent pairs exempt ONLY their one shared
    authored endpoint and carry the one-wall-per-segment adjacency rules."""
    ki, pi, ai = gi
    kj, pj, aj = gj

    def beyond_shared(points):
        return [p for p in points if shared is None or not _near(p, shared)]

    if ki == "line" and kj == "line":
        if adjacent:
            # one-wall rule: collinear at the joint = redundant vertex/fold-back
            (a1, b1), (a2, b2) = pi, pj
            d1x, d1y = b1[0] - a1[0], b1[1] - a1[1]
            d2x, d2y = b2[0] - a2[0], b2[1] - a2[1]
            n1, n2 = math.hypot(d1x, d1y), math.hypot(d2x, d2y)
            if abs(d1x * d2y - d1y * d2x) / (n1 * n2) <= _CONTOUR_TOL:
                return ("adjacent collinear line segments (redundant vertex or "
                        "fold-back); each segment must produce its own wall")
            return None  # non-collinear adjacent lines meet only at the joint
        if _seg_intersect(pi[0], pi[1], pj[0], pj[1]):
            return "line segments touch/cross (a simple ring cannot self-contact)"
        return None

    if ki == "arc" and kj == "arc":
        hits = _circle_circle_hits(ai.center, ai.radius, aj.center, aj.radius)
        if hits == "cocircular":
            if adjacent:
                return ("adjacent co-circular arcs (same supporting circle) merge "
                        "into one cylindrical wall; author a single arc")
            # non-adjacent same-circle arcs: any angular-span OVERLAP rejects —
            # sample each arc's endpoints (+midpoint) against the other's span
            for g_a, g_b in ((ai, aj), (aj, ai)):
                mid_ang = g_a.start_angle + g_a.sweep / 2.0
                probes = [g_a.start, g_a.end,
                          (g_a.center[0] + g_a.radius * math.cos(mid_ang),
                           g_a.center[1] + g_a.radius * math.sin(mid_ang))]
                for p in probes:
                    if shared is not None and _near(p, shared):
                        continue
                    if point_on_arc_span(g_b, p[0], p[1], _CONTOUR_TOL):
                        return "co-circular arcs overlap in angular span"
            return None
        contacts = [p for p in hits
                    if point_on_arc_span(ai, p[0], p[1], _CONTOUR_TOL)
                    and point_on_arc_span(aj, p[0], p[1], _CONTOUR_TOL)]
        extra = beyond_shared(contacts) if adjacent else contacts
        if extra:
            return "arcs touch/cross beyond the shared endpoint" if adjacent \
                else "arcs touch/cross (a simple ring cannot self-contact)"
        return None

    # mixed line + arc (tangent line-arc adjacency is ALLOWED: plane vs cylinder)
    line_pts = pi if ki == "line" else pj
    garc = ai if ki == "arc" else aj
    hits = _line_circle_hits(line_pts[0], line_pts[1], garc.center, garc.radius)
    contacts = [p for p in hits if point_on_arc_span(garc, p[0], p[1], _CONTOUR_TOL)]
    extra = beyond_shared(contacts) if adjacent else contacts
    if extra:
        return "line and arc touch/cross beyond the shared endpoint" if adjacent \
            else "line and arc touch/cross (a simple ring cannot self-contact)"
    return None


def _seg_intersect(a, b, c, d) -> bool:
    """Do closed segments ab and cd share any point (proper crossing or touch)?"""
    d1 = _cross(c, d, a); d2 = _cross(c, d, b)
    d3 = _cross(a, b, c); d4 = _cross(a, b, d)
    if (
        ((d1 > _CONTOUR_TOL) != (d2 > _CONTOUR_TOL))
        and ((d3 > _CONTOUR_TOL) != (d4 > _CONTOUR_TOL))
        and abs(d1) > _CONTOUR_TOL and abs(d2) > _CONTOUR_TOL
        and abs(d3) > _CONTOUR_TOL and abs(d4) > _CONTOUR_TOL
    ):
        return True  # proper crossing
    if abs(d1) <= _CONTOUR_TOL and _on_segment(a, c, d):
        return True
    if abs(d2) <= _CONTOUR_TOL and _on_segment(b, c, d):
        return True
    if abs(d3) <= _CONTOUR_TOL and _on_segment(c, a, b):
        return True
    if abs(d4) <= _CONTOUR_TOL and _on_segment(d, a, b):
        return True
    return False


def _cross(o, a, b) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _on_segment(p, a, b) -> bool:
    """p is within the bounding box of a-b (used after a collinearity test)."""
    return (
        min(a[0], b[0]) - _CONTOUR_TOL <= p[0] <= max(a[0], b[0]) + _CONTOUR_TOL
        and min(a[1], b[1]) - _CONTOUR_TOL <= p[1] <= max(a[1], b[1]) + _CONTOUR_TOL
    )
