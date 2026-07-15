"""Engine-side **view-dependent HLR generation** for `aiadra-mechanical`
(arc 20260609-2; populates the Display Representation contract's reserved
`view_dependent` slot → contract v1.1; ADR/0033 D6 realized).

OCCT `HLRBRep` (exact) + `HLRBRep_PolyAlgo` (poly) computed per fixed view,
cached on the D8 freshness key — NEVER per-frame (ADR/0033 D6). Output edges
live in the **projector view plane** (probe-confirmed: all output z == 0), so
the payload ships 2D polylines (`coordinate_space: "view_plane_2d"`) plus a
contract-complete projector basis (arc 20260609-2 Codex1 B2).

View frame (the B2 pin; probe-confirmed mechanics):
  - `direction` = unit LOOK direction (eye → scene; camera convention).
  - `right` = normalize(direction × up_request); `up` = right × direction
    (orthonormalized; echoed in the payload so consumers never re-derive).
  - OCCT's projector frame has its main axis pointing scene → eye, and its
    auto-derived X/Y basis is NOT a drafting frame (probe: front view derived
    u along -z!) — so we construct `gp_Ax2(origin, -direction, right)`
    explicitly; then frame Y == `up` and the output (x, y) ARE our (u, v):
        u = (p - origin) · right,   v = (p - origin) · up      [mm]
  - Handedness: (right, up, -direction) is right-handed; u grows to screen
    right, v grows to screen up.

Identity discipline (Codex1 B1 + B5; ADR/0035 D2 inherited, not cloned):
  - Model-edge segments correlate against the SAME `topology.EdgeRecord`s the
    base display payload is built from — recipe-first, geometry-second.
  - Coincident-projection disambiguation is pinned (probe-surfaced: a hole rim
    seen edge-on is colinear with the box's top edges): (1) extent affinity
    (full-edge match), (2) uniquely most-specific candidate (fragments), (3)
    depth rule (visible → nearest, hidden → farthest), (4) fail loud.
  - Outline (silhouette) segments carry `{kind: "outline", face_id, index}` —
    face-anchored, per-view ephemeral, never a display id, never pickable.
  - Sliver policy (Codex1 B4): an UNCORRELATABLE non-outline segment shorter
    than `correlation_min_length_mm` is dropped and counted in
    `counters.discarded_tolerance_segments`; at or above the threshold it
    fails loud. Correlatable slivers are kept.
"""
from __future__ import annotations

import json
import math
import time
from typing import Any

from aiadra_core.transaction.boundary import TransactionError

from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.HLRBRep import (
    HLRBRep_Algo,
    HLRBRep_HLRToShape,
    HLRBRep_PolyAlgo,
    HLRBRep_PolyHLRToShape,
)
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopoDS import TopoDS
from OCP.TopLoc import TopLoc_Location
from OCP.BRep import BRep_Tool

from . import topology
from .display import load_display_material

DISPLAY_REPRESENTATION_VERSION = "1.1"
DEFAULT_CORRELATION_MIN_LENGTH_MM = 0.01  # probe: exact slivers 0; poly >= 0.145
_UNIT_TOL = 1e-6
_DEPTH_TIE_TOL_MM = 1e-6

# (payload edge_class, HLRBRep_HLRToShape / PolyHLRToShape method, visibility)
_COMPOUNDS = (
    ("sharp", "VCompound", "visible"),
    ("smooth", "Rg1LineVCompound", "visible"),
    ("sewn", "RgNLineVCompound", "visible"),
    ("outline", "OutLineVCompound", "visible"),
    ("sharp", "HCompound", "hidden"),
    ("smooth", "Rg1LineHCompound", "hidden"),
    ("sewn", "RgNLineHCompound", "hidden"),
    ("outline", "OutLineHCompound", "hidden"),
)

# Per-process HLR cache (ADR/0028 D6 advisory + per-process). Key includes the
# D8 cache_key (recipe | last_event_id | adapter version | OCP version) plus
# everything view-dependent that affects output.
_HLR_CACHE: dict[str, str] = {}  # key -> canonical JSON payload


def clear_cache() -> None:
    """Test hook: drop all cached HLR payloads."""
    _HLR_CACHE.clear()


def cache_size() -> int:
    return len(_HLR_CACHE)


# ---------------------------------------------------------------------------
# Read handler (registered as the `mechanical.display_hlr` READ op).
# ---------------------------------------------------------------------------


def handle_display_hlr(context, params: dict[str, Any]) -> dict[str, Any]:
    """Generate the standalone view-dependent HLR payload from committed state.

    `params` is supplied by `aiadra_core.protocol.display_hlr`: `object_uuid`
    (required), `object_number` (optional), `views` (required, non-empty),
    `algorithm` (optional, "exact"), `tolerance` (optional),
    `correlation_min_length_mm` (optional)."""
    material = load_display_material(context, params)
    views = params.get("views")
    algorithm = params.get("algorithm", "exact")
    min_len = params.get(
        "correlation_min_length_mm", DEFAULT_CORRELATION_MIN_LENGTH_MM)

    # S2 stepwise: a recipe with NO base creation feature has no solid to
    # project — every requested view answers with ZERO segments under the
    # Part's real identity echo (mirrors the base display's no-solid branch
    # and core's EP0 empty-HLR shape).
    features = material["features"]
    if features and not any(
        f.get("feature_type") in ("extrude", "revolve") for f in features
    ):
        return _no_solid_hlr(material, views, algorithm, min_len)

    topo = topology.extract_part_topology(
        material["features"],
        object_uuid=material["object_uuid"],
        object_number=material["object_number"],
        geometry_ref=material["geometry_ref"],
        cache_key=material["cache_key"],
        linear_deflection_mm=material["linear_deflection_mm"],
        angular_deflection_rad=material["angular_deflection_rad"],
        cache_material=material["cache_material"],
    )
    return generate_hlr(
        topo, views=views, algorithm=algorithm,
        correlation_min_length_mm=min_len,
    )


def _no_solid_hlr(
    material: dict[str, Any], views: Any, algorithm: str, min_len: Any,
) -> dict[str, Any]:
    """Zero-segment HLR for a no-base recipe (S2 stepwise) — the requested
    views echo back with empty segment lists; inputs validate as loudly as the
    solid path (same spec/algorithm checks, no silent acceptance)."""
    if not isinstance(views, list) or not views:
        raise TransactionError(
            "mechanical.display_hlr: 'views' must be a non-empty list of view specs"
        )
    if algorithm not in ("exact", "poly"):
        raise TransactionError(
            f"mechanical.display_hlr: unknown algorithm {algorithm!r} "
            f"(expected 'exact' or 'poly')"
        )
    min_len = float(min_len)
    if min_len < 0:
        raise TransactionError(
            "mechanical.display_hlr: correlation_min_length_mm must be >= 0"
        )
    frames = [_validate_view_spec(v) for v in views]
    return {
        "identity_echo": {
            "object_uuid": material["object_uuid"],
            "object_number": material["object_number"],
            "geometry_ref": material["geometry_ref"],
            "display_representation_version": DISPLAY_REPRESENTATION_VERSION,
            "cache_key": material["cache_key"],
            "topology_signature": topology.compute_topology_signature(
                material["features"]),
        },
        "views": [
            {
                "view_id": f["view_id"],
                "projector": {
                    "projection": f["projection"],
                    "origin": list(f["origin"]),
                    "direction": list(f["direction"]),
                    "up": list(f["up"]),
                    "right": list(f["right"]),
                    "units": "mm",
                },
                "algorithm": algorithm,
                "coordinate_space": "view_plane_2d",
                "correlation_min_length_mm": min_len,
                "segments": [],
                "counters": {
                    "visible_segments": 0,
                    "hidden_segments": 0,
                    "outline_segments": 0,
                    "discarded_tolerance_segments": 0,
                    "generation_ms": 0.0,
                },
            }
            for f in frames
        ],
    }


# ---------------------------------------------------------------------------
# Public entry: extracted topology + view specs → ViewDependentPayload dict
# ---------------------------------------------------------------------------


def generate_hlr(
    topo: "topology.PartTopology",
    *,
    views: Any,
    algorithm: str = "exact",
    correlation_min_length_mm: float = DEFAULT_CORRELATION_MIN_LENGTH_MM,
) -> dict[str, Any]:
    """Compute classified HLR for each requested view over the SAME topology
    records the base display payload uses (B1). Returns the standalone
    `ViewDependentPayload` dict (`identity_echo` + `views`)."""
    if not isinstance(views, list) or not views:
        raise TransactionError(
            "mechanical.display_hlr: 'views' must be a non-empty list of view specs"
        )
    if algorithm not in ("exact", "poly"):
        raise TransactionError(
            f"mechanical.display_hlr: unknown algorithm {algorithm!r} "
            f"(expected 'exact' or 'poly')"
        )
    min_len = float(correlation_min_length_mm)
    if min_len < 0:
        raise TransactionError(
            "mechanical.display_hlr: correlation_min_length_mm must be >= 0"
        )

    frames = [_validate_view_spec(v) for v in views]

    cache_key = _hlr_cache_key(topo, frames, algorithm, min_len)
    if cache_key is not None and cache_key in _HLR_CACHE:
        return json.loads(_HLR_CACHE[cache_key])

    payload_views = [
        _generate_view(topo, frame, algorithm, min_len) for frame in frames
    ]
    payload = {
        "identity_echo": {
            "object_uuid": topo.object_uuid,
            "object_number": topo.object_number,
            "geometry_ref": topo.geometry_ref,
            "display_representation_version": DISPLAY_REPRESENTATION_VERSION,
            "cache_key": topo.cache_key,
            "topology_signature": topo.topology_signature,
        },
        "views": payload_views,
    }
    if cache_key is not None:
        _HLR_CACHE[cache_key] = json.dumps(payload)
        return json.loads(_HLR_CACHE[cache_key])
    return payload


def _hlr_cache_key(topo, frames, algorithm, min_len) -> str | None:
    """Cache key = the FULL B3 identity material + all view-affecting material.
    `None` (no caching) when the topology has no D8 cache key (engine-level
    direct calls).

    Codex2 B1 (arc 20260609-2): the D8 `cache_key` alone is geometry/freshness
    material (recipe hash | last_event_id | adapter version | OCP version) —
    two DISTINCT objects with identical recipes share it, and the cached value
    embeds `identity_echo`, so keying on geometry alone would return the first
    object's echo for the second object (which Studio's B3 attach check then
    correctly refuses). The key therefore carries the same six identity fields
    the echo does."""
    if not topo.cache_key:
        return None
    view_material = [
        {"view_id": f["view_id"], "origin": f["origin"],
         "direction": f["direction"], "up": f["up"], "right": f["right"]}
        for f in frames
    ]
    return json.dumps({
        # B3 identity material — everything identity_echo echoes (Codex2 B1).
        "object_uuid": topo.object_uuid,
        "object_number": topo.object_number,
        "geometry_ref": topo.geometry_ref,
        "display_representation_version": DISPLAY_REPRESENTATION_VERSION,
        "cache_key": topo.cache_key,
        "topology_signature": topo.topology_signature,
        # View-affecting material.
        "views": view_material,
        "algorithm": algorithm,
        "min_len": min_len,
        "lin": topo.linear_deflection_mm,
        "ang": topo.angular_deflection_rad,
    }, sort_keys=True)


# ---------------------------------------------------------------------------
# View frame construction + validation (B2)
# ---------------------------------------------------------------------------


def _validate_view_spec(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise TransactionError(
            f"mechanical.display_hlr: view spec must be a dict, got "
            f"{type(spec).__name__}"
        )
    view_id = spec.get("view_id")
    if not isinstance(view_id, str) or not view_id:
        raise TransactionError(
            "mechanical.display_hlr: view spec requires a non-empty 'view_id'"
        )
    projection = spec.get("projection", "orthographic")
    if projection != "orthographic":
        raise TransactionError(
            f"mechanical.display_hlr: view {view_id!r}: projection "
            f"{projection!r} unsupported (contract v1.1 = 'orthographic' only)"
        )
    origin = _vec3(spec.get("origin", [0.0, 0.0, 0.0]), view_id, "origin")
    direction = _vec3(spec.get("direction"), view_id, "direction")
    up_req = _vec3(spec.get("up"), view_id, "up")

    if abs(_norm(direction) - 1.0) > _UNIT_TOL:
        raise TransactionError(
            f"mechanical.display_hlr: view {view_id!r}: 'direction' must be a "
            f"unit vector (|d|={_norm(direction):.9f})"
        )
    if abs(_norm(up_req) - 1.0) > _UNIT_TOL:
        raise TransactionError(
            f"mechanical.display_hlr: view {view_id!r}: 'up' must be a unit "
            f"vector (|u|={_norm(up_req):.9f})"
        )
    right_raw = _cross(direction, up_req)
    if _norm(right_raw) <= _UNIT_TOL:
        raise TransactionError(
            f"mechanical.display_hlr: view {view_id!r}: 'up' is parallel to "
            f"'direction' — the view frame is degenerate"
        )
    right = _scaled(right_raw, 1.0 / _norm(right_raw))
    up = _cross(right, direction)  # orthonormalized true up
    return {
        "view_id": view_id,
        "projection": projection,
        "origin": origin,
        "direction": direction,
        "up": up,
        "right": right,
    }


# ---------------------------------------------------------------------------
# Per-view generation
# ---------------------------------------------------------------------------


def _generate_view(
    topo, frame: dict[str, Any], algorithm: str, min_len: float
) -> dict[str, Any]:
    t0 = time.perf_counter()
    origin, direction = frame["origin"], frame["direction"]
    right, up = frame["right"], frame["up"]

    # OCCT projector: main axis = scene → eye = -direction; explicit Vx = right
    # (the probe proved the auto-derived basis is unusable). Frame Y = up.
    ax2 = gp_Ax2(
        gp_Pnt(*origin),
        gp_Dir(-direction[0], -direction[1], -direction[2]),
        gp_Dir(*right),
    )
    projector = HLRAlgo_Projector(ax2)

    if algorithm == "exact":
        algo = HLRBRep_Algo()
        algo.Add(topo.shape)
        algo.Projector(projector)
        algo.Update()
        algo.Hide()
        extractor = HLRBRep_HLRToShape(algo)
    else:
        palgo = HLRBRep_PolyAlgo()
        palgo.Load(topo.shape)
        palgo.Projector(projector)
        palgo.Update()
        extractor = HLRBRep_PolyHLRToShape()
        extractor.Update(palgo)

    # Correlation reference data: the SAME EdgeRecords the display payload uses
    # (B1), projected with the SAME frame.
    edge_refs = [_project_edge_record(e, origin, direction, right, up)
                 for e in topo.edges]
    face_refs = [_project_face_nodes(f, origin, right, up)
                 for f in topo.faces if f.surface_kind != "plane"]

    segments: list[dict[str, Any]] = []
    discarded = 0
    outline_seen: dict[str, int] = {}
    for edge_class, method, visibility in _COMPOUNDS:
        compound = getattr(extractor, method)()
        if compound is None or compound.IsNull():
            continue
        exp = TopExp_Explorer(compound, TopAbs_EDGE)
        while exp.More():
            result_edge = TopoDS.Edge_s(exp.Current())
            exp.Next()
            pts2d = _result_polyline_2d(
                result_edge, topo.linear_deflection_mm,
                topo.angular_deflection_rad)
            if len(pts2d) < 2:
                continue
            seg_len = _polyline_length(pts2d)
            if edge_class == "outline":
                source = _correlate_outline(
                    pts2d, face_refs, topo.linear_deflection_mm)
                if source is None:
                    if seg_len < min_len:
                        discarded += 1
                        continue
                    raise TransactionError(
                        f"mechanical.display_hlr: view {frame['view_id']!r}: "
                        f"an outline segment (len {seg_len:.4f} mm) does not "
                        f"correlate to any curved face — correlation bug, "
                        f"not rendering guesswork"
                    )
            else:
                source = _correlate_model_edge(
                    pts2d, visibility, edge_refs, topo.linear_deflection_mm,
                    frame["view_id"], seg_len, min_len)
                if source is None:
                    discarded += 1
                    continue
            segments.append({
                "polyline_2d": [c for uv in pts2d for c in uv],
                "visibility": visibility,
                "edge_class": edge_class,
                "source": source,
            })

    # Deterministic ordering + outline ordinal assignment (B5): sort first,
    # then index outlines per face in sorted order.
    segments.sort(key=_segment_sort_key)
    for seg in segments:
        if seg["source"]["kind"] == "outline":
            fid = seg["source"]["face_id"]
            seg["source"]["index"] = outline_seen.get(fid, 0)
            outline_seen[fid] = seg["source"]["index"] + 1

    counters = {
        "visible_segments": sum(
            1 for s in segments if s["visibility"] == "visible"),
        "hidden_segments": sum(
            1 for s in segments if s["visibility"] == "hidden"),
        "outline_segments": sum(
            1 for s in segments if s["edge_class"] == "outline"),
        "discarded_tolerance_segments": discarded,
        "generation_ms": (time.perf_counter() - t0) * 1000.0,
    }
    return {
        "view_id": frame["view_id"],
        "projector": {
            "projection": frame["projection"],
            "origin": list(frame["origin"]),
            "direction": list(frame["direction"]),
            "up": list(frame["up"]),
            "right": list(frame["right"]),
            "units": "mm",
        },
        "algorithm": algorithm,
        "coordinate_space": "view_plane_2d",
        "correlation_min_length_mm": min_len,
        "segments": segments,
        "counters": counters,
    }


def _segment_sort_key(seg: dict[str, Any]):
    src = seg["source"]
    source_key = src.get("edge_id") or src.get("face_id") or ""
    p = seg["polyline_2d"]
    return (seg["visibility"], seg["edge_class"], src["kind"], source_key,
            round(p[0], 9), round(p[1], 9), round(p[-2], 9), round(p[-1], 9))


# ---------------------------------------------------------------------------
# Result-edge sampling (output is already in the projector frame; z == 0)
# ---------------------------------------------------------------------------


def _result_polyline_2d(edge, lin, ang) -> list[tuple[float, float]]:
    pts = topology.discretize_edge(edge, lin, ang)
    out: list[tuple[float, float]] = []
    for j in range(0, len(pts), 3):
        # probe-confirmed: result coordinates are (u, v, ~0) in the frame we
        # constructed; flattened depth is structurally zero for exact HLR.
        out.append((pts[j], pts[j + 1]))
    return out


def _polyline_length(pts2d: list[tuple[float, float]]) -> float:
    return sum(
        math.hypot(b[0] - a[0], b[1] - a[1])
        for a, b in zip(pts2d, pts2d[1:])
    )


# ---------------------------------------------------------------------------
# Model-edge correlation (recipe-first records; geometry-second mapping)
# ---------------------------------------------------------------------------


def _project_edge_record(rec, origin, direction, right, up) -> dict[str, Any]:
    pts3 = rec.polyline_mm
    pts2d: list[tuple[float, float]] = []
    depth_sum = 0.0
    n = 0
    for j in range(0, len(pts3), 3):
        p = (pts3[j] - origin[0], pts3[j + 1] - origin[1], pts3[j + 2] - origin[2])
        pts2d.append((_dot(p, right), _dot(p, up)))
        depth_sum += _dot(p, direction)
        n += 1
    return {
        "record": rec,
        "pts2d": pts2d,
        "mean_depth": depth_sum / n if n else 0.0,
    }


def _correlate_model_edge(
    pts2d, visibility, edge_refs, lin_deflection, view_id, seg_len, min_len,
):
    """Match a result segment to exactly one model EdgeRecord. Returns the
    source dict, or None when an UNCORRELATABLE segment is below the B4
    threshold (caller counts the discard). Raises on material failures."""
    # Both the result edge and the reference polylines are deflection-grade
    # discretizations of true curves; their mutual deviation is bounded by
    # ~2x the linear deflection.
    tol = 2.0 * lin_deflection + 1e-6
    samples = _sample_points(pts2d, 5)

    candidates = []
    for ref in edge_refs:
        if len(ref["pts2d"]) < 2:
            continue  # degenerate projection (an edge seen end-on)
        worst = max(_dist_to_polyline(s, ref["pts2d"]) for s in samples)
        if worst <= tol:
            candidates.append(ref)

    if not candidates:
        if seg_len < min_len:
            return None  # B4: numerical dust, dropped + counted
        raise TransactionError(
            f"mechanical.display_hlr: view {view_id!r}: a {visibility} "
            f"non-outline segment (len {seg_len:.4f} mm, start "
            f"({pts2d[0][0]:.3f}, {pts2d[0][1]:.3f})) does not correlate to "
            f"any model edge within {tol:.4f} mm — correlation bug, not "
            f"rendering guesswork"
        )
    if len(candidates) == 1:
        return {"kind": "model_edge", "edge_id": candidates[0]["record"].edge_id}

    # Coincident projections (probe-surfaced: a rim circle seen edge-on is
    # colinear with the box top edges — same v line, overlapping u range).
    # Pinned disambiguation:
    # (1) extent affinity — the candidate whose projected EXTENT (2D bbox
    #     diagonal) matches the segment's extent (a rim collapsing to exactly
    #     this segment beats a longer colinear box edge). Robust for closed
    #     curves, where endpoint matching degenerates (start == end).
    seg_extent = _bbox_diagonal(pts2d)
    with_affinity = [
        ref for ref in candidates
        if abs(_bbox_diagonal(ref["pts2d"]) - seg_extent) <= 2.0 * tol
    ]
    pool = with_affinity if with_affinity else candidates
    if len(pool) == 1:
        return {"kind": "model_edge", "edge_id": pool[0]["record"].edge_id}

    # (2) most-specific candidate — for FRAGMENTS (poly mode chops edges into
    #     short pieces) the smallest-extent candidate that still contains the
    #     segment is the right parent (a rim chip belongs to the 10 mm rim,
    #     not the colinear 40 mm box edge), provided it is UNIQUELY minimal;
    if not with_affinity:
        by_extent = sorted(pool, key=lambda r: _bbox_diagonal(r["pts2d"]))
        if (_bbox_diagonal(by_extent[1]["pts2d"])
                - _bbox_diagonal(by_extent[0]["pts2d"]) > 2.0 * tol):
            return {"kind": "model_edge",
                    "edge_id": by_extent[0]["record"].edge_id}

    # (3) depth rule — visible attributes to the candidate nearest the eye,
    #     hidden to the farthest;
    pool.sort(key=lambda r: r["mean_depth"])
    chosen = pool[0] if visibility == "visible" else pool[-1]
    runner = pool[1] if visibility == "visible" else pool[-2]
    if abs(chosen["mean_depth"] - runner["mean_depth"]) <= _DEPTH_TIE_TOL_MM:
        # (4) still ambiguous → fail loud.
        raise TransactionError(
            f"mechanical.display_hlr: view {view_id!r}: a {visibility} segment "
            f"matches multiple model edges at indistinguishable depth "
            f"({chosen['record'].edge_id!r} vs {runner['record'].edge_id!r}) — "
            f"refusing to guess"
        )
    return {"kind": "model_edge", "edge_id": chosen["record"].edge_id}


def _bbox_diagonal(pts2d) -> float:
    us = [p[0] for p in pts2d]
    vs = [p[1] for p in pts2d]
    return math.hypot(max(us) - min(us), max(vs) - min(vs))


# ---------------------------------------------------------------------------
# Outline (silhouette) correlation — face-anchored ephemeral identity (B5)
# ---------------------------------------------------------------------------


def _project_face_nodes(face_rec, origin, right, up) -> dict[str, Any]:
    loc = TopLoc_Location()
    tri = BRep_Tool.Triangulation_s(face_rec.face, loc)
    pts2d: list[tuple[float, float]] = []
    if tri is not None:
        trsf = loc.Transformation()
        for k in range(1, tri.NbNodes() + 1):
            p = tri.Node(k).Transformed(trsf)
            q = (p.X() - origin[0], p.Y() - origin[1], p.Z() - origin[2])
            pts2d.append((_dot(q, right), _dot(q, up)))
    return {"record": face_rec, "pts2d": pts2d}


def _correlate_outline(pts2d, face_refs, lin_deflection):
    """Attribute a silhouette segment to its generating curved face. The
    silhouette lies ON the face surface, so its projection lies within the
    face's projected node cloud (deflection-grade spacing). Returns the source
    dict (index assigned later, deterministically) or None when no curved face
    matches."""
    if not face_refs:
        return None
    # Triangulation nodes are spaced by the meshing deflections — on the
    # v0.0.1 cylinder ~sqrt(8 * r * lin) chord spacing. Half a chord + slack.
    samples = _sample_points(pts2d, 3)
    best = None
    best_d = None
    for ref in face_refs:
        if not ref["pts2d"]:
            continue
        worst = max(
            min(math.hypot(s[0] - q[0], s[1] - q[1]) for q in ref["pts2d"])
            for s in samples
        )
        if best_d is None or worst < best_d:
            best_d = worst
            best = ref
    if best is None:
        return None
    r_hint = 5.0  # tolerance scale; refined per-face when richer surfaces land
    node_tol = math.sqrt(8.0 * r_hint * lin_deflection) / 2.0 + lin_deflection
    if best_d > node_tol:
        return None
    return {"kind": "outline", "face_id": best["record"].face_id, "index": -1}


# ---------------------------------------------------------------------------
# Small vector helpers (tuples in, tuples out)
# ---------------------------------------------------------------------------


def _vec3(v, view_id, label) -> tuple[float, float, float]:
    if (not isinstance(v, (list, tuple)) or len(v) != 3
            or not all(isinstance(c, (int, float)) for c in v)):
        raise TransactionError(
            f"mechanical.display_hlr: view {view_id!r}: {label!r} must be a "
            f"3-component number list"
        )
    return (float(v[0]), float(v[1]), float(v[2]))


def _dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b) -> tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(a) -> float:
    return math.sqrt(_dot(a, a))


def _scaled(a, s) -> tuple[float, float, float]:
    return (a[0] * s, a[1] * s, a[2] * s)


def _sample_points(pts2d, n) -> list[tuple[float, float]]:
    if len(pts2d) <= n:
        return list(pts2d)
    step = (len(pts2d) - 1) / (n - 1)
    return [pts2d[round(i * step)] for i in range(n)]


def _dist_to_polyline(p, poly) -> float:
    best = math.inf
    for a, b in zip(poly, poly[1:]):
        best = min(best, _dist_to_segment(p, a, b))
    return best


def _dist_to_segment(p, a, b) -> float:
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 <= 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))
