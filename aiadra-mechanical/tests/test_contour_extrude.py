"""Contour (arbitrary closed-ring) extrude — arc 20260711-11 slice E (Codex4).

Proves the engine extrudes an arbitrary closed contour into a real solid with
SEGMENT-ANCHORED wall roles, and holds the ADR/0035 identity line: a vertex MOVE
(a value edit) preserves every wall role id + the `topology_signature`, while a
segment insert/delete (a skeleton change) changes the signature. Plus the
Class-1 gate (Codex4 D-E3/B1): open ring, self-intersection, <3 segments, zero
area, unsupported kind, and a contour+circle combo — all fail loud BEFORE OCCT.
"""
from __future__ import annotations

import pytest

from aiadra_core.transaction.boundary import TransactionError

from aiadra_mechanical.adapter_payload import (
    build_sketch_payload,
    build_extrude_payload,
    _signed_area,
)
from aiadra_mechanical import display, topology


# A concave hexagon "L" — the canonical shape a rectangle-only engine can't do.
L_SHAPE = [(0.0, 0.0), (60.0, 0.0), (60.0, 20.0), (20.0, 20.0), (20.0, 50.0), (0.0, 50.0)]


def _segments(verts):
    """An explicit CLOSED ring of line segments (incl. the closing edge, B1)."""
    n = len(verts)
    return [
        {
            "kind": "line",
            "x1_mm": verts[i][0], "y1_mm": verts[i][1],
            "x2_mm": verts[(i + 1) % n][0], "y2_mm": verts[(i + 1) % n][1],
        }
        for i in range(n)
    ]


def _contour_recipe(verts, depth=12.0):
    prims = [{"type": "contour", "segments": _segments(verts)}]
    feats = [{"id": "feat_0001", "feature_type": "sketch",
              "adapter_payload": build_sketch_payload(prims)}]
    feats.append({
        "id": "feat_0002", "feature_type": "extrude",
        "parameters": [{"id": "featp_0001", "name": "depth_mm", "value": depth,
                        "datatype": "number", "unit": "mm"}],
        "adapter_payload": build_extrude_payload(
            sketch_feature_id="feat_0001", direction="z+",
            depth_parameter_id="featp_0001"),
    })
    return feats


def _gen(feats):
    return display.generate_display_representation(
        feats, object_uuid="u-1", object_number="PRT-0001",
        geometry_ref="sha256:deadbeef", cache_key="ck")


def _faces(d):
    return {f["face_id"] for f in d["render"]["faces"]}


# ---------------------------------------------------------------------------
# 1. A real solid with segment-anchored walls
# ---------------------------------------------------------------------------


def test_l_shape_extrudes_to_a_real_solid_with_segment_walls():
    faces = _faces(_gen(_contour_recipe(L_SHAPE)))
    assert len(faces) == 8  # 6 walls + 2 caps
    assert "feat_0002:face:cap_base" in faces
    assert "feat_0002:face:cap_top" in faces
    walls = {f for f in faces if f.endswith(":face:wall")}
    assert len(walls) == 6
    # Every wall is anchored to a DISTINCT contour segment id (skp_0001s01..s06).
    seg_ids = {f.split("/")[1].split(":")[0] for f in walls}
    assert seg_ids == {f"skp_0001s{k:02d}" for k in range(1, 7)}


# ---------------------------------------------------------------------------
# 2. The ADR/0035 identity line: value edit vs skeleton change
# ---------------------------------------------------------------------------


def test_vertex_move_preserves_wall_roles_and_signature():
    base = _contour_recipe(L_SHAPE)
    moved = list(L_SHAPE)
    moved[1] = (65.0, 0.0)   # extend the bottom-right corner — a VALUE edit
    moved[2] = (65.0, 20.0)  # (keep the ring closed + simple)
    moved_recipe = _contour_recipe(moved)
    # Wall roles identical (segment ids unchanged) ...
    assert _faces(_gen(base)) == _faces(_gen(moved_recipe))
    # ... and the topology signature is unchanged (coordinates are values).
    assert topology.compute_topology_signature(base) == topology.compute_topology_signature(moved_recipe)


def test_segment_count_change_changes_signature():
    hexagon = _contour_recipe(L_SHAPE)  # 6 segments
    triangle = _contour_recipe([(0.0, 0.0), (50.0, 0.0), (25.0, 40.0)])  # 3 segments
    assert topology.compute_topology_signature(hexagon) != topology.compute_topology_signature(triangle)


# (Rectangle-signature backward-compat is covered exhaustively by the existing
# display/fillet/hole suites, which assert exact rectangle roles + signatures;
# slice E adds `contour_segments` only when a contour is present.)


# ---------------------------------------------------------------------------
# 3. Class-1 domain gate — rejected BEFORE the kernel (Codex4 D-E3)
# ---------------------------------------------------------------------------


def test_too_few_segments_fail_class1():
    with pytest.raises(TransactionError):
        build_sketch_payload([{"type": "contour", "segments": _segments([(0.0, 0.0), (50.0, 0.0)])}])


def test_open_ring_fails_class1():
    segs = _segments(L_SHAPE)[:-1]  # drop the closing segment → a gap, not a ring
    with pytest.raises(TransactionError):
        build_sketch_payload([{"type": "contour", "segments": segs}])


def test_self_intersecting_contour_rejected():
    # A crossing profile with NON-zero area (exercises the pair predicates, not area).
    crossing = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0), (2.0, -2.0)]
    assert abs(_signed_area(crossing)) > 1.0
    with pytest.raises(TransactionError):
        build_sketch_payload([{"type": "contour", "segments": _segments(crossing)}])


def test_simple_polygon_is_not_flagged_self_intersecting():
    # SK-C0: behavior-level — a clean convex pentagon builds fine.
    pent = [(0.0, 0.0), (4.0, 0.0), (5.0, 3.0), (2.0, 5.0), (-1.0, 3.0)]
    build_sketch_payload([{"type": "contour", "segments": _segments(pent)}])


def test_collinear_adjacent_segments_rejected():
    # A rectangle with a REDUNDANT midpoint on the bottom edge — segments 0 & 1 are
    # collinear. Closed, non-zero-area, non-self-intersecting, but it would not give
    # one clean wall per segment → rejected (Codex5 B1).
    redundant = [(0.0, 0.0), (30.0, 0.0), (60.0, 0.0), (60.0, 40.0), (0.0, 40.0)]
    with pytest.raises(TransactionError):
        build_sketch_payload([{"type": "contour", "segments": _segments(redundant)}])


def test_fold_back_vertex_rejected():
    # SK-C0: behavior-level — a fold-back (anti-parallel adjacent lines) rejects.
    foldback = [(0.0, 0.0), (60.0, 0.0), (30.0, 0.0), (30.0, 40.0), (0.0, 40.0)]
    with pytest.raises(TransactionError):
        build_sketch_payload([{"type": "contour", "segments": _segments(foldback)}])


def test_unsupported_segment_kind_fails_loud():
    segs = _segments(L_SHAPE)
    segs[0] = {"kind": "arc", "x1_mm": 0, "y1_mm": 0, "x2_mm": 60, "y2_mm": 0}
    with pytest.raises(TransactionError):
        build_sketch_payload([{"type": "contour", "segments": segs}])


def test_zero_length_segment_fails_loud():
    segs = _segments(L_SHAPE)
    segs.insert(0, {"kind": "line", "x1_mm": 0, "y1_mm": 0, "x2_mm": 0, "y2_mm": 0})
    with pytest.raises(TransactionError):
        build_sketch_payload([{"type": "contour", "segments": segs}])


def test_contour_with_circle_hole_rejected_v1():
    prims = [
        {"type": "contour", "segments": _segments(L_SHAPE)},
        {"type": "circle", "cx_mm": 10, "cy_mm": 10, "radius_mm": 3},
    ]
    with pytest.raises(TransactionError):
        build_sketch_payload(prims)


def test_two_outer_profiles_rejected():
    prims = [
        {"type": "rectangle", "x_mm": 0, "y_mm": 0, "width_mm": 40, "height_mm": 30},
        {"type": "contour", "segments": _segments(L_SHAPE)},
    ]
    with pytest.raises(TransactionError):
        build_sketch_payload(prims)
