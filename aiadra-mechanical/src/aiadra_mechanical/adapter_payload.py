"""Engine-opaque `adapter_payload` shapes for mechanical features.

Per ADR/0029 D7 sketch primitives + extrude op-data stay OPAQUE to
aiadra-core (the bundle schema only checks `adapter_payload` IS an object).
This module pins the payload format (`adapter_schema_version = 0.1.1` since arc
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

# Sketch primitive shapes carried in feature.adapter_payload["primitives"]:
#   {"type": "rectangle", "x_mm": float, "y_mm": float, "width_mm": float, "height_mm": float}
#   {"type": "circle", "cx_mm": float, "cy_mm": float, "radius_mm": float}
#   {"type": "line", "x1_mm": float, "y1_mm": float, "x2_mm": float, "y2_mm": float}
#   {"type": "contour", "segments": [ {"kind": "line", "x1_mm", "y1_mm", "x2_mm", "y2_mm"}, … ]}
#     arc 20260711-11 slice E (Codex4): an arbitrary CLOSED-RING outer profile —
#     an ordered ring of typed segments (v1 implements kind="line" only). Each
#     segment is an explicit, engine-anchored wall producer; there is NO implicit
#     auto-closing edge (Codex4 B1) — the ring must close on authored segments.

_SKETCH_PRIMITIVE_REQUIRED_KEYS = {
    "rectangle": {"type", "x_mm", "y_mm", "width_mm", "height_mm"},
    "circle": {"type", "cx_mm", "cy_mm", "radius_mm"},
    "line": {"type", "x1_mm", "y1_mm", "x2_mm", "y2_mm"},
    "contour": {"type", "segments"},
}

# The outer profiles (exactly one per sketch); a circle is a hole, not an outer.
_OUTER_PROFILE_TYPES = {"rectangle", "contour"}
# Segment kinds a v1 contour may carry. arc/spline are reserved (fail loud) so
# the schema is future-proof without implementing the curve build yet (Codex4 D-E1).
_SUPPORTED_SEGMENT_KINDS = {"line"}
_SEGMENT_REQUIRED_KEYS = {"line": {"kind", "x1_mm", "y1_mm", "x2_mm", "y2_mm"}}
# Tolerance (mm) for contour ring continuity/closure — generous vs the kernel.
_CONTOUR_TOL = 1e-6


def build_sketch_payload(primitives: list[dict[str, Any]]) -> dict[str, Any]:
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
    return {"primitives": out}


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
    *, sketch_feature_id: str, direction: str, depth_parameter_id: str
) -> dict[str, Any]:
    """Build (and domain-validate) the adapter_payload for an extrude feature.

    `depth_mm` lives in `feature.parameters[]`; this payload references the
    parameter id so the kernel can correlate it.
    """
    if direction not in ("z+", "z-"):
        raise TransactionError(
            f"mechanical.add_extrude_feature: direction must be 'z+' or 'z-', got {direction!r}"
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
    return {
        "sketch_feature_id": sketch_feature_id,
        "direction": direction,
        "depth_parameter_id": depth_parameter_id,
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
    prims = (sketch.get("adapter_payload", {}) if sketch else {}).get("primitives", [])
    if any(p.get("type") == "circle" for p in prims) or any(
        f.get("feature_type") == "hole" for f in features
    ):
        raise TransactionError(
            "mechanical.add_hole_feature: v1 supports a simple cap only — the cap "
            "already has a cutout (a sketch hole or a prior hole feature). "
            "Unsupported target face for v1."
        )
    rectangle = next((p for p in prims if p.get("type") == "rectangle"), None)
    if rectangle is None:
        raise TransactionError(
            "mechanical.add_hole_feature: the sketch has no rectangle profile"
        )
    require_hole_inside_rectangle(rectangle, center_x_mm, center_y_mm, radius_mm)


def _validate_sketch_primitives(primitives: list[dict[str, Any]]) -> None:
    if not primitives:
        raise TransactionError(
            "mechanical.add_sketch_feature: primitives list cannot be empty"
        )
    outer_count = 0
    has_contour = False
    has_circle = False
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
        if kind in _OUTER_PROFILE_TYPES:
            outer_count += 1
        if kind == "rectangle":
            if prim["width_mm"] <= 0 or prim["height_mm"] <= 0:
                raise TransactionError(
                    f"mechanical.add_sketch_feature: primitive[{i}] rectangle "
                    f"width_mm/height_mm must be positive, got "
                    f"width={prim['width_mm']!r} height={prim['height_mm']!r}"
                )
        elif kind == "circle":
            has_circle = True
            if prim["radius_mm"] <= 0:
                raise TransactionError(
                    f"mechanical.add_sketch_feature: primitive[{i}] circle "
                    f"radius_mm must be positive, got {prim['radius_mm']!r}"
                )
        elif kind == "contour":
            has_contour = True
            require_valid_contour(prim, index=i)
    # A sketch builds a planar face from exactly ONE outer profile.
    if outer_count != 1:
        raise TransactionError(
            "mechanical.add_sketch_feature: a sketch needs exactly one outer "
            f"profile (a rectangle or a contour); got {outer_count} "
            "(circles are interpreted as holes, not outer profiles)"
        )
    # D-E4 (Codex4): a contour outer profile is an outer boundary only in v1 —
    # circle holes stay on the rectangle path until inner-loop containment +
    # face-role identity are designed.
    if has_contour and has_circle:
        raise TransactionError(
            "mechanical.add_sketch_feature: v1 does not support a circle hole with "
            "a contour outer profile (contour = outer boundary only); use a "
            "rectangle profile for a circular through-hole"
        )


def require_valid_contour(contour: dict[str, Any], *, index: int | str = "?") -> None:
    """Class-1 domain contract for a `contour` outer profile (arc 20260711-11
    slice E; Codex4 B1/D-E3). An ordered CLOSED RING of typed segments — v1
    implements `kind:"line"` only. Rejected BEFORE the kernel (ADR/0031 D6):
    unsupported kinds, malformed segments, gaps (not a closed ring), fewer than
    three segments, zero-length segments, zero enclosed area, self-intersection.
    There is NO implicit closing edge — the ring must close on an authored
    segment (Codex4 B1). Called at write time AND inside the evaluator fold so a
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
    verts = [_seg_points(s)[0] for s in segments]
    if abs(_signed_area(verts)) <= _CONTOUR_TOL:
        raise TransactionError(f"{where} encloses zero area (degenerate ring)")
    if _self_intersects(verts):
        raise TransactionError(
            f"{where} is self-intersecting; a valid profile is a simple (non-crossing) ring"
        )
    # Codex5 B1: each segment must turn at its vertices so it produces its OWN
    # wall face. Two collinear adjacent segments (a redundant vertex, or a
    # fold-back) can be closed + non-zero-area yet break the one-wall-per-segment
    # identity — reject them so a segment id always anchors exactly one wall.
    bad_vertex = _collinear_vertex(verts)
    if bad_vertex is not None:
        raise TransactionError(
            f"{where} has collinear adjacent segments at vertex {bad_vertex} (a redundant "
            f"vertex or a fold-back); each segment must turn to produce its own wall face "
            f"(one wall per segment). Remove the redundant vertex."
        )


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


def _self_intersects(verts: list[tuple[float, float]]) -> bool:
    """True if any two NON-ADJACENT ring edges touch/cross (a bowtie / vertex-on-
    edge). Adjacent edges legitimately share their common vertex and are skipped;
    adjacent degeneracy (spikes) is caught by the zero-length + zero-area checks."""
    n = len(verts)
    edges = [(verts[i], verts[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue  # adjacent — share a vertex
            if _seg_intersect(edges[i][0], edges[i][1], edges[j][0], edges[j][1]):
                return True
    return False


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


def _collinear_vertex(verts: list[tuple[float, float]]):
    """Return the first ring vertex where the incoming and outgoing segments are
    collinear (parallel OR anti-parallel — |sin(turn)| ≈ 0), else None. A real
    turn at every vertex guarantees each segment produces its own wall face
    (Codex5 B1). Zero-length segments are rejected earlier."""
    n = len(verts)
    for i in range(n):
        ax, ay = verts[i - 1]
        bx, by = verts[i]
        cx, cy = verts[(i + 1) % n]
        d1x, d1y = bx - ax, by - ay
        d2x, d2y = cx - bx, cy - by
        n1 = math.hypot(d1x, d1y)
        n2 = math.hypot(d2x, d2y)
        if n1 <= _CONTOUR_TOL or n2 <= _CONTOUR_TOL:
            continue
        sin_turn = abs(d1x * d2y - d1y * d2x) / (n1 * n2)
        if sin_turn <= _CONTOUR_TOL:
            return (bx, by)
    return None


def _cross(o, a, b) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _on_segment(p, a, b) -> bool:
    """p is within the bounding box of a-b (used after a collinearity test)."""
    return (
        min(a[0], b[0]) - _CONTOUR_TOL <= p[0] <= max(a[0], b[0]) + _CONTOUR_TOL
        and min(a[1], b[1]) - _CONTOUR_TOL <= p[1] <= max(a[1], b[1]) + _CONTOUR_TOL
    )
