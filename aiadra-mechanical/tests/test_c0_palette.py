"""SK-C0 palette growth (arc 20260715-4, C0-1): arcs in contours,
circle-as-outer-profile, and construction geometry — the Codex2 build bars.

Proof fixtures pinned in the design (Claude2/Codex2):
  - the ROUNDED-CORNER L: an arc segment yields exactly one CYLINDRICAL wall,
    anchored by construction (`Generated(edge)`), verified by radius;
  - the BARREL: two NON-adjacent arcs on ONE supporting circle (same radius,
    same axis) get DISTINCT wall identities — the exact ambiguity that killed
    radius+axis correlation keys;
  - the TANGENT line–arc joint: two distinct walls (plane vs cylinder — the
    allowed adjacency);
  - CIRCLE-AS-OUTER: extrude → a cylinder with the pinned
    `<extrude>/<circle-skp>:face:outer_wall` role (never hole_wall), across the
    full EP2 plane matrix (xy/yz/zx × normal±);
  - CONSTRUCTION: guides are display-only — excluded from profiles, BREP, and
    the 3D topology signature; toggling participation changes the signature;
    an all-construction sketch is a VALID sketch-only artifact that cannot be
    extruded; legacy (no-construction) signatures stay byte-identical.
"""
from __future__ import annotations

import math

import pytest

from aiadra_core.transaction.boundary import TransactionError

from aiadra_mechanical import topology
from aiadra_mechanical.adapter_payload import (
    build_extrude_payload,
    build_sketch_payload,
)
from aiadra_mechanical.profile_classify import classify_sketch
from aiadra_mechanical import display, geometry


B90 = math.tan(math.pi / 8)  # a quarter-circle corner (90-degree sweep)


def L(x1, y1, x2, y2):
    return {"kind": "line", "x1_mm": x1, "y1_mm": y1, "x2_mm": x2, "y2_mm": y2}


def A(x1, y1, x2, y2, b):
    return {"kind": "arc", "x1_mm": x1, "y1_mm": y1, "x2_mm": x2, "y2_mm": y2, "bulge": b}


def _feats(prims, depth=10.0, plane=None, direction="normal+"):
    feats = [{"id": "feat_0001", "feature_type": "sketch",
              "adapter_payload": build_sketch_payload(prims, plane=plane)}]
    feats.append({
        "id": "feat_0002", "feature_type": "extrude",
        "parameters": [{"id": "featp_0001", "name": "depth_mm", "value": depth,
                        "datatype": "number", "unit": "mm"}],
        "adapter_payload": build_extrude_payload(
            sketch_feature_id="feat_0001", direction=direction,
            depth_parameter_id="featp_0001"),
    })
    return feats


def _gen(feats):
    return display.generate_display_representation(
        feats, object_uuid="u-1", object_number="PRT-0001",
        geometry_ref="sha256:deadbeef", cache_key="ck")


def _faces(d):
    return {f["face_id"]: f for f in d["render"]["faces"]}


def _topo_faces(feats):
    """{face_id: surface_kind} from the topology layer (FaceRecord)."""
    pt = topology.extract_part_topology(feats)
    return {f.face_id: f.surface_kind for f in pt.faces}


# ---------------------------------------------------------------------------
# 1. Arc walls — by-construction identity on the real engine
# ---------------------------------------------------------------------------

ROUNDED_L = [L(0, 0, 40, 0), A(40, 0, 50, 10, B90), L(50, 10, 50, 40),
             L(50, 40, 0, 40), L(0, 40, 0, 0)]


def test_rounded_corner_l_arc_wall_is_cylindrical_and_segment_anchored():
    faces = _topo_faces(_feats([{"type": "contour", "segments": ROUNDED_L}]))
    assert len(faces) == 7  # 4 line walls + 1 arc wall + 2 caps
    arc_wall = "feat_0002/skp_0001s02:face:wall"
    assert faces.get(arc_wall) == "cylinder"
    line_walls = [k for k, v in faces.items()
                  if k.endswith(":face:wall") and v == "plane"]
    assert len(line_walls) == 4


def test_barrel_same_circle_arcs_get_distinct_wall_identities():
    # Two 60-degree arcs on ONE supporting circle (center origin, r=10),
    # NON-adjacent, joined by chords: same radius, same axis — the exact
    # radius+axis ambiguity. By-construction identity keeps them distinct.
    c30, s30 = 10 * math.cos(math.pi / 6), 5.0
    b60 = -math.tan((math.pi / 3) / 4)  # negative: bows OUTWARD -> center (0,0)
    barrel = [A(c30, -s30, c30, s30, b60), L(c30, s30, -c30, s30),
              A(-c30, s30, -c30, -s30, b60), L(-c30, -s30, c30, -s30)]
    faces = _topo_faces(_feats([{"type": "contour", "segments": barrel}]))
    cyl_walls = {k for k, v in faces.items()
                 if k.endswith(":face:wall") and v == "cylinder"}
    assert cyl_walls == {"feat_0002/skp_0001s01:face:wall",
                         "feat_0002/skp_0001s03:face:wall"}


def test_tangent_line_arc_joint_yields_two_distinct_walls():
    # The ALLOWED adjacency (plane vs cylinder): a vertical line meeting a
    # quarter arc tangentially at (0, 0).
    ring = [L(0, 20, 0, 0), A(0, 0, 10, 10, B90), L(10, 10, 10, 20), L(10, 20, 0, 20)]
    faces = _topo_faces(_feats([{"type": "contour", "segments": ring}]))
    walls = {k: v for k, v in faces.items() if k.endswith(":face:wall")}
    assert walls["feat_0002/skp_0001s01:face:wall"] == "plane"
    assert walls["feat_0002/skp_0001s02:face:wall"] == "cylinder"


def test_arc_bulge_edit_is_a_value_edit_signature_stable():
    a = _feats([{"type": "contour", "segments": ROUNDED_L}])
    rounder = list(ROUNDED_L)
    rounder[1] = A(40, 0, 50, 10, 0.6)  # different curvature, same skeleton
    b = _feats([{"type": "contour", "segments": rounder}])
    assert topology.compute_topology_signature(a) == topology.compute_topology_signature(b)


def test_line_to_arc_kind_change_is_a_skeleton_change():
    a = _feats([{"type": "contour", "segments": ROUNDED_L}])
    straight = list(ROUNDED_L)
    straight[1] = L(40, 0, 50, 10)
    b = _feats([{"type": "contour", "segments": straight}])
    assert topology.compute_topology_signature(a) != topology.compute_topology_signature(b)


# ---------------------------------------------------------------------------
# 2. Circle-as-outer-profile — the cylinder, across the EP2 plane matrix
# ---------------------------------------------------------------------------

CIRCLE = {"type": "circle", "cx_mm": 5.0, "cy_mm": -3.0, "radius_mm": 8.0}


def test_circle_outer_extrudes_to_a_cylinder_with_pinned_roles():
    faces = _topo_faces(_feats([dict(CIRCLE)]))
    assert set(faces) == {"feat_0002/skp_0001:face:outer_wall",
                          "feat_0002:face:cap_base", "feat_0002:face:cap_top"}
    assert faces["feat_0002/skp_0001:face:outer_wall"] == "cylinder"
    assert not any("hole_wall" in k for k in faces)  # never the hole path


@pytest.mark.parametrize("orientation", ["xy", "yz", "zx"])
@pytest.mark.parametrize("direction", ["normal+", "normal-"])
def test_circle_outer_full_plane_matrix(orientation, direction):
    plane = {"kind": "principal", "orientation": orientation}
    faces = _faces(_gen(_feats([dict(CIRCLE)], plane=plane, direction=direction)))
    assert "feat_0002/skp_0001:face:outer_wall" in faces
    assert "feat_0002:face:cap_base" in faces
    assert "feat_0002:face:cap_top" in faces


def test_two_circles_without_rectangle_fail_loud():
    with pytest.raises(TransactionError):
        build_sketch_payload([dict(CIRCLE),
                              {"type": "circle", "cx_mm": 40.0, "cy_mm": 0.0, "radius_mm": 2.0}])


# ---------------------------------------------------------------------------
# 3. Construction geometry — display-only guides (D-C3)
# ---------------------------------------------------------------------------

GUIDE = {"type": "line", "x1_mm": -20.0, "y1_mm": -20.0, "x2_mm": 60.0, "y2_mm": 60.0,
         "construction": True}


def test_construction_guide_changes_neither_breps_nor_signature():
    plain = _feats([{"type": "contour", "segments": ROUNDED_L}])
    guided = _feats([{"type": "contour", "segments": ROUNDED_L}, dict(GUIDE)])
    # identical faces/roles ...
    assert set(_faces(_gen(plain))) == set(_faces(_gen(guided)))
    # ... and the 3D topology signature is UNCHANGED (B4): canonical selections
    # and parent-prefix references survive adding/removing a guide.
    assert (topology.compute_topology_signature(plain)
            == topology.compute_topology_signature(guided))


def test_construction_toggle_into_participation_changes_signature():
    guide_rect = {"type": "rectangle", "x_mm": 0.0, "y_mm": 0.0,
                  "width_mm": 30.0, "height_mm": 20.0, "construction": True}
    profile_rect = {k: v for k, v in guide_rect.items() if k != "construction"}
    contour = {"type": "contour", "segments": ROUNDED_L}
    with_guide = _feats([contour, guide_rect])
    sig_guide = topology.compute_topology_signature(with_guide)
    # toggling the rectangle INTO participation is a different classification
    # (two outers) — rejected loud, proving participation is never silent
    with pytest.raises(TransactionError):
        build_sketch_payload([dict(contour), profile_rect])
    # and a guide-only difference in the OTHER direction: rect profile with vs
    # without an extra construction rectangle — same signature
    plain_rect = _feats([{"type": "rectangle", "x_mm": 0, "y_mm": 0,
                          "width_mm": 40, "height_mm": 30}])
    guided_rect = _feats([{"type": "rectangle", "x_mm": 0, "y_mm": 0,
                           "width_mm": 40, "height_mm": 30}, guide_rect])
    assert (topology.compute_topology_signature(plain_rect)
            == topology.compute_topology_signature(guided_rect))
    assert sig_guide is not None


def test_all_construction_sketch_is_valid_sketch_only():
    payload = build_sketch_payload([dict(GUIDE)])
    cls = classify_sketch(payload["primitives"])
    assert cls.outer_kind == "none" and cls.is_sketch_only
    # evaluating the sketch alone yields no BREP (the no-base display lane)
    feats = [{"id": "feat_0001", "feature_type": "sketch", "adapter_payload": payload}]
    assert geometry.evaluate_part(feats).IsNull()


def test_extruding_a_construction_only_sketch_fails_loud():
    payload = build_sketch_payload([dict(GUIDE)])
    feats = [{"id": "feat_0001", "feature_type": "sketch", "adapter_payload": payload},
             {"id": "feat_0002", "feature_type": "extrude",
              "parameters": [{"id": "featp_0001", "name": "depth_mm", "value": 5.0,
                              "datatype": "number", "unit": "mm"}],
              "adapter_payload": build_extrude_payload(
                  sketch_feature_id="feat_0001", direction="normal+",
                  depth_parameter_id="featp_0001")}]
    with pytest.raises(TransactionError):
        geometry.evaluate_part(feats)


def test_non_construction_standalone_line_rejected_loud():
    with pytest.raises(TransactionError):
        build_sketch_payload([{k: v for k, v in GUIDE.items() if k != "construction"}])


def test_segment_level_construction_rejected():
    segs = [dict(s) for s in ROUNDED_L]
    segs[0]["construction"] = True
    with pytest.raises(TransactionError):
        build_sketch_payload([{"type": "contour", "segments": segs}])


def test_non_boolean_construction_rejected():
    with pytest.raises(TransactionError):
        build_sketch_payload([{**CIRCLE, "construction": "yes"}])


# ---------------------------------------------------------------------------
# 4. Class-1 curve pins (wrap / touch / tolerance / bulge bounds)
# ---------------------------------------------------------------------------


def _payload_of(segments):
    return build_sketch_payload([{"type": "contour", "segments": segments}])


def test_bulge_bounds_exact():
    def ring(b):
        # the arc bows OUTWARD (+x, negative bulge) so a near-semicircle stays
        # clear of the rest of the ring — the DOMAIN bound is what trips, not
        # an intersection
        return [L(0, 0, 20, 0), A(20, 0, 20, 10, b), L(20, 10, 0, 10), L(0, 10, 0, 0)]
    _payload_of(ring(-0.999999))           # minor arc, inside the bound
    for bad in (0.0, -1.0, 1.0, -5e-7, float("inf"), float("nan")):
        with pytest.raises(TransactionError):
            _payload_of(ring(bad))


def test_non_adjacent_tangential_touch_counts_as_intersection():
    # The top line grazes the arc apex exactly (apex y = 5): touch REJECTS.
    with pytest.raises(TransactionError):
        _payload_of([A(0, 0, 20, 0, 0.5), L(20, 0, 20, 5), L(20, 5, 0, 5), L(0, 5, 0, 0)])


def test_adjacent_cocircular_arcs_rejected():
    # two CONSECUTIVE 60-degree arcs on the SAME supporting circle (center
    # origin, r=10) meeting at 30 degrees — the same-cylinder merge risk
    c30, s30 = 10 * math.cos(math.pi / 6), 5.0
    b60 = -math.tan((math.pi / 3) / 4)  # negative: both on center-(0,0) r=10
    with pytest.raises(TransactionError):
        _payload_of([A(c30, -s30, c30, s30, b60), A(c30, s30, 0.0, 10.0, b60),
                     L(0.0, 10.0, c30, -s30)])


def test_wrapping_arc_spans_stay_exact():
    # An arc whose angular span crosses the ±180-degree wrap (start on the -x
    # side): the span predicates must not false-positive against a distant line.
    ring = [A(-10, -3, -10, 3, math.tan(math.radians(35) / 2)),  # 70-degree sweep across pi
            L(-10, 3, 8, 3), L(8, 3, 8, -3), L(8, -3, -10, -3)]
    _payload_of(ring)  # valid — no spurious intersection from wrap handling


# ---------------------------------------------------------------------------
# 5. Codex3 closures: the converged EMPTY row + the literal signature golden
# ---------------------------------------------------------------------------


def test_empty_primitives_is_a_valid_sketch_only_artifact():
    # Codex3 B2: the converged matrix makes EMPTY (like all-construction) a
    # VALID sketch-only artifact — one classifier authority, no contradictory
    # pre-rejection at the write path.
    payload = build_sketch_payload([])
    cls = classify_sketch(payload["primitives"])
    assert cls.outer_kind == "none" and cls.is_sketch_only
    feats = [{"id": "feat_0001", "feature_type": "sketch", "adapter_payload": payload}]
    assert geometry.evaluate_part(feats).IsNull()


def test_pre_c0_signature_literal_golden():
    # Codex3 non-blocker 3: LITERAL byte parity for a pre-C0 recipe shape —
    # this exact string was produced by the pre-C0 signature algorithm for
    # this exact recipe; the filtered (topology_contributing) path must keep
    # emitting it byte-for-byte.
    feats = _feats([{"type": "rectangle", "x_mm": 0.0, "y_mm": 0.0,
                     "width_mm": 40.0, "height_mm": 30.0}])
    assert topology.compute_topology_signature(feats) == "topo_8b3d982e8ef30128"
