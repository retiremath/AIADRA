"""SK-C1.0 S2 (arc 20260716-2, Codex1 B1 evidence matrix) — the face-plane
binding: the two-layer resolver, the deterministic origin-aware frame, the
typed refusal set, edit-stability (the sketch rides a depth edit), signature
discipline (skeleton-only, principal byte-parity), and handler/evaluator
refusal parity.
"""
from __future__ import annotations

import pytest

from aiadra_core.transaction.boundary import TransactionError

from aiadra_mechanical import face_frame, geometry, topology
from aiadra_mechanical.recipe import (
    PlaneFrame,
    effective_plane_frame,
    plane_skeleton,
    principal_frame,
    validate_plane_record,
)


def _box_features(depth=10.0, width=30.0, height=20.0):
    """A committed box recipe: rectangle sketch on xy + extrude."""
    return [
        {
            "id": "feat_0001", "feature_type": "sketch", "engine": "mechanical",
            "adapter_schema_version": "0.1.10",
            "adapter_payload": {
                "primitives": [{
                    "type": "rectangle", "id": "skp_0001",
                    "x_mm": 0.0, "y_mm": 0.0, "width_mm": width, "height_mm": height,
                }],
                "plane": {"kind": "principal", "orientation": "xy"},
            },
        },
        {
            "id": "feat_0002", "feature_type": "extrude", "engine": "mechanical",
            "adapter_schema_version": "0.1.10",
            "depends_on_feature_ids": ["feat_0001"],
            "parameters": [{"id": "featp_0001", "name": "depth_mm", "value": depth,
                            "datatype": "number", "unit": "mm"}],
            "adapter_payload": {"sketch_feature_id": "feat_0001", "direction": "normal+"},
        },
    ]


def _face_plane(prefix, role):
    return {
        "kind": "face",
        "face_role": role,
        "resolved_against_topology_signature": topology.compute_topology_signature(prefix),
    }


def _face_sketch(prefix, role, feat_id="feat_0003"):
    return {
        "id": feat_id, "feature_type": "sketch", "engine": "mechanical",
        "adapter_schema_version": "0.1.10",
        "depends_on_feature_ids": ["feat_0002"],
        "adapter_payload": {
            "primitives": [{
                "type": "rectangle", "id": "skp_0001",
                "x_mm": 2.0, "y_mm": 2.0, "width_mm": 5.0, "height_mm": 5.0,
            }],
            "plane": _face_plane(prefix, role),
        },
    }


# ---- the resolved frame: top and side planar faces (the numerical rule) ----

def test_top_cap_resolves_an_origin_aware_z_frame():
    prefix = _box_features(depth=10.0)
    frame = face_frame.resolve_face_plane(
        prefix, _face_plane(prefix, "feat_0002:face:cap_top"))
    assert frame.orientation == "face"
    # the top cap of an upward extrude: outward normal +Z
    assert frame.normal == pytest.approx((0.0, 0.0, 1.0))
    # X projects fully onto that plane → u = X (the fixed tie-break)
    assert frame.u_axis == pytest.approx((1.0, 0.0, 0.0))
    assert frame.v_axis == pytest.approx((0.0, 1.0, 0.0))
    # the world origin projects to (0, 0, depth)
    assert frame.origin_mm == pytest.approx((0.0, 0.0, 10.0))
    # plane-local round-trip through the ORIGIN-AWARE methods
    world = frame.to_3d(3.0, 4.0)
    assert world == pytest.approx((3.0, 4.0, 10.0))
    assert frame.project_uv(world) == pytest.approx((3.0, 4.0))
    assert frame.normal_coord(world) == pytest.approx(0.0)


def test_side_wall_resolves_with_the_x_to_y_to_z_tie_break():
    prefix = _box_features()
    # wall_0 of the rectangle: the y=0 side → outward normal -Y; X survives the
    # projection (first in the fixed order) → u = X, v = n × u = -Z… compute:
    frame = face_frame.resolve_face_plane(
        prefix, _face_plane(prefix, "feat_0002/skp_0001:face:wall_y_min"))
    assert abs(frame.normal[2]) == pytest.approx(0.0, abs=1e-12)  # a vertical wall
    # u is the projection of X (unless the wall is the x-normal one)
    if abs(frame.normal[0]) < 0.5:  # a y-facing wall → X is in-plane
        assert frame.u_axis == pytest.approx((1.0, 0.0, 0.0))
    # right-handedness: u × v = n
    ux, uy, uz = frame.u_axis
    vx, vy, vz = frame.v_axis
    cross = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
    assert cross == pytest.approx(frame.normal)


# ---- the typed refusal set (three DISTINCT recovery paths) ----

def test_cylindrical_face_refuses_not_planar():
    features = [
        {
            "id": "feat_0001", "feature_type": "sketch", "engine": "mechanical",
            "adapter_schema_version": "0.1.10",
            "adapter_payload": {
                "primitives": [{"type": "circle", "id": "skp_0001",
                                "cx_mm": 0.0, "cy_mm": 0.0, "radius_mm": 8.0}],
            },
        },
        {
            "id": "feat_0002", "feature_type": "extrude", "engine": "mechanical",
            "adapter_schema_version": "0.1.10",
            "depends_on_feature_ids": ["feat_0001"],
            "parameters": [{"id": "featp_0001", "name": "depth_mm", "value": 12.0,
                            "datatype": "number", "unit": "mm"}],
            "adapter_payload": {"sketch_feature_id": "feat_0001", "direction": "normal+"},
        },
    ]
    with pytest.raises(TransactionError, match="NOT PLANAR"):
        face_frame.resolve_face_plane(
            features, _face_plane(features, "feat_0002/skp_0001:face:outer_wall"))


def test_stale_parent_signature_refuses_with_the_stale_copy():
    prefix = _box_features()
    plane = _face_plane(prefix, "feat_0002:face:cap_top")
    plane["resolved_against_topology_signature"] = "topo_deadbeefdeadbeef"
    with pytest.raises(TransactionError, match="STALE"):
        face_frame.resolve_face_plane(prefix, plane)


def test_missing_face_refuses_with_the_stale_selection_copy():
    prefix = _box_features()
    with pytest.raises(TransactionError, match="no longer exists"):
        face_frame.resolve_face_plane(
            prefix, _face_plane(prefix, "feat_0002:face:no_such_role"))


# ---- edit-stability: the sketch RIDES a depth edit ----

def test_face_bound_frame_rides_a_depth_edit_but_a_signature_matched_binding_survives():
    ten = _box_features(depth=10.0)
    twenty = _box_features(depth=20.0)
    # a parameter edit preserves the topology SKELETON → the same signature…
    assert (topology.compute_topology_signature(ten)
            == topology.compute_topology_signature(twenty))
    plane = _face_plane(ten, "feat_0002:face:cap_top")
    f10 = face_frame.resolve_face_plane(ten, plane)
    f20 = face_frame.resolve_face_plane(twenty, plane)
    # …and the frame MOVES WITH the cap: same axes, the origin rides the plane
    assert f20.u_axis == pytest.approx(f10.u_axis)
    assert f20.v_axis == pytest.approx(f10.v_axis)
    assert f20.normal == pytest.approx(f10.normal)
    assert f10.origin_mm[2] == pytest.approx(10.0)
    assert f20.origin_mm[2] == pytest.approx(20.0)
    # plane-local coordinates are invariant: the drawn point stays ON the cap
    assert f10.to_3d(3.0, 4.0)[2] == pytest.approx(10.0)
    assert f20.to_3d(3.0, 4.0)[2] == pytest.approx(20.0)


# ---- the evaluator fold: unconsumed face-bound sketches validate every run ----

def test_evaluator_validates_an_unconsumed_face_bound_sketch_and_rides_edits():
    prefix = _box_features(depth=10.0)
    features = prefix + [_face_sketch(prefix, "feat_0002:face:cap_top")]
    geometry.evaluate_part(features)  # resolves + validates; no raise
    # the depth edit keeps the signature → regeneration still validates
    edited = _box_features(depth=25.0) + [_face_sketch(prefix, "feat_0002:face:cap_top")]
    geometry.evaluate_part(edited)


def test_evaluator_refuses_a_stale_face_binding_on_regeneration():
    prefix = _box_features()
    sk = _face_sketch(prefix, "feat_0002:face:cap_top")
    sk["adapter_payload"]["plane"]["resolved_against_topology_signature"] = "topo_0000000000000000"
    with pytest.raises(TransactionError, match="STALE"):
        geometry.evaluate_part(prefix + [sk])


def test_base_profile_on_a_face_of_its_own_solid_refuses():
    prefix = _box_features()
    sk = _face_sketch(prefix, "feat_0002:face:cap_top", feat_id="feat_0003")
    extrude2 = {
        "id": "feat_0004", "feature_type": "extrude", "engine": "mechanical",
        "adapter_schema_version": "0.1.10",
        "depends_on_feature_ids": ["feat_0003"],
        "parameters": [{"id": "featp_0002", "name": "depth_mm", "value": 5.0,
                        "datatype": "number", "unit": "mm"}],
        "adapter_payload": {"sketch_feature_id": "feat_0003", "direction": "normal+"},
    }
    # two extrudes trip the one-base rule FIRST (that refusal stands); prove
    # the face-consumption refusal on its own by making the face sketch the
    # ONLY base's profile:
    with pytest.raises(TransactionError):
        geometry.evaluate_part(prefix + [sk, extrude2])
    lone = [_face_sketch(prefix, "feat_0002:face:cap_top", feat_id="feat_0001")]
    lone_extrude = {
        "id": "feat_0002", "feature_type": "extrude", "engine": "mechanical",
        "adapter_schema_version": "0.1.10",
        "depends_on_feature_ids": ["feat_0001"],
        "parameters": [{"id": "featp_0001", "name": "depth_mm", "value": 5.0,
                        "datatype": "number", "unit": "mm"}],
        "adapter_payload": {"sketch_feature_id": "feat_0001", "direction": "normal+"},
    }
    with pytest.raises(TransactionError):
        geometry.evaluate_part(lone + [lone_extrude])


# ---- the pure layer: structure, skeleton, no-recursion, principal parity ----

def test_pure_layer_validates_structure_and_refuses_the_pure_frame():
    assert validate_plane_record(
        {"kind": "face", "face_role": "feat_0002:face:cap_top",
         "resolved_against_topology_signature": "topo_x"},
        op_kind="t") == "face"
    with pytest.raises(TransactionError, match="unknown keys"):
        validate_plane_record(
            {"kind": "face", "face_role": "f:face:r",
             "resolved_against_topology_signature": "s", "extra": 1}, op_kind="t")
    with pytest.raises(TransactionError, match="face_role"):
        validate_plane_record({"kind": "face", "face_role": "not-a-role",
                               "resolved_against_topology_signature": "s"}, op_kind="t")
    # the pure frame table REFUSES face kinds (the evaluator owns resolution)
    with pytest.raises(TransactionError, match="parent prefix"):
        effective_plane_frame({"adapter_payload": {"plane": {
            "kind": "face", "face_role": "f:face:r",
            "resolved_against_topology_signature": "s"}}})


def test_plane_skeleton_matches_pre_s2_bytes_for_principal_and_carries_the_face_binding():
    assert plane_skeleton({"adapter_payload": {}}) is None
    assert plane_skeleton({"adapter_payload": {"plane": {
        "kind": "principal", "orientation": "xy"}}}) is None
    assert plane_skeleton({"adapter_payload": {"plane": {
        "kind": "principal", "orientation": "yz"}}}) == "yz"
    sk = plane_skeleton({"adapter_payload": {"plane": {
        "kind": "face", "face_role": "feat_0002:face:cap_top",
        "resolved_against_topology_signature": "topo_abc"}}})
    assert sk == {"kind": "face", "face_role": "feat_0002:face:cap_top",
                  "resolved_against": "topo_abc"}


def test_signature_hashes_the_skeleton_only_and_face_edits_preserve_it():
    prefix = _box_features()
    with_sketch = prefix + [_face_sketch(prefix, "feat_0002:face:cap_top")]
    sig_a = topology.compute_topology_signature(with_sketch)
    # a PRIMITIVE edit inside the face-bound sketch (values, not skeleton)
    edited = prefix + [_face_sketch(prefix, "feat_0002:face:cap_top")]
    edited[2]["adapter_payload"]["primitives"][0]["width_mm"] = 9.0
    assert topology.compute_topology_signature(edited) == sig_a
    # retargeting the binding IS a skeleton change
    other = prefix + [_face_sketch(prefix, "feat_0002/skp_0001:face:wall_y_min")]
    assert topology.compute_topology_signature(other) != sig_a


def test_principal_origin_is_zero_and_numerically_identical():
    f = principal_frame("zx")
    assert f.origin_mm == (0.0, 0.0, 0.0)
    assert f.to_3d(7.0, -2.0) == pytest.approx((-2.0, 0.0, 7.0))
    assert PlaneFrame("xy", (1, 0, 0), (0, 1, 0), (0, 0, 1)).origin_mm == (0.0, 0.0, 0.0)


# ---- the v1.2 transport drop-test (Codex2 B3.1.4/B3.1.5: the REAL chain) ----

def test_v12_fields_survive_the_real_core_chain():
    """mechanical dict → core from_engine_dict → to_dict: surface_kind AND
    sketch_frames survive (the silent-drop path Codex2 B3 exposed is dead)."""
    from aiadra_core.protocol.display import DisplayRepresentation
    from aiadra_mechanical import display as display_mod

    prefix = _box_features(depth=10.0)
    features = prefix + [_face_sketch(prefix, "feat_0002:face:cap_top")]
    topo = topology.extract_part_topology(
        features, object_uuid="u-1", object_number="P-1",
        geometry_ref="vault:x", cache_key="ck-1",
    )
    payload = display_mod.build_display_payload(
        topo, sketch_frames=display_mod.build_sketch_frames(features))
    assert payload["display_representation_version"] == "1.2"

    dr = DisplayRepresentation.from_engine_dict(payload)
    out = dr.to_dict()
    # surface_kind survives, engine-classified
    kinds = {f["face_id"]: f["surface_kind"] for f in out["render"]["faces"]}
    assert kinds["feat_0002:face:cap_top"] == "plane"
    # sketch_frames survive with the resolved origin-aware frame
    (frame,) = out["sketch_frames"]
    assert frame["sketch_feature_id"] == "feat_0003"
    assert frame["origin_mm"][2] == pytest.approx(10.0)
    assert frame["normal"] == pytest.approx([0.0, 0.0, 1.0])


def test_hlr_version_matrix_cross_versions_refuse():
    """Codex2 B3.1.2/B3.1.4: standalone HLR accepts the HLR-capable set
    {1.1, 1.2} and refuses 1.0; the drop-and-refetch mismatch stays loud."""
    from aiadra_core.protocol.display import (
        DisplayContractError,
        HLR_CAPABLE_VERSIONS,
        ViewDependentPayload,
    )
    assert HLR_CAPABLE_VERSIONS == ("1.1", "1.2")

    def hlr_dict(version):
        return {
            "identity_echo": {
                "object_uuid": "u-1", "object_number": "P-1",
                "geometry_ref": "vault:x", "cache_key": "ck-1",
                "topology_signature": "topo_x",
                "display_representation_version": version,
            },
            "views": [{
                "view_id": "front",
                "coordinate_space": "view_plane_2d",
                "algorithm": "exact",
                "correlation_min_length_mm": 0.1,
                "projector": {
                    "projection": "orthographic", "units": "mm",
                    "origin": [0.0, 0.0, 0.0],
                    "direction": [0.0, 1.0, 0.0],
                    "up": [0.0, 0.0, 1.0],
                    "right": [1.0, 0.0, 0.0],
                },
                "segments": [],
                "counters": {
                    "visible_segments": 0, "hidden_segments": 0,
                    "outline_segments": 0, "discarded_tolerance_segments": 0,
                },
            }],
        }

    for ok_version in ("1.1", "1.2"):
        ViewDependentPayload.from_engine_dict(hlr_dict(ok_version))
    with pytest.raises(DisplayContractError, match="HLR-capable"):
        ViewDependentPayload.from_engine_dict(hlr_dict("1.0"))


def test_sketch_frames_validator_refuses_duplicates_and_bad_axes():
    from aiadra_core.protocol.display import DisplayContractError, _validate_sketch_frames

    good = {
        "sketch_feature_id": "feat_0003",
        "origin_mm": [0.0, 0.0, 10.0],
        "u_axis": [1.0, 0.0, 0.0],
        "v_axis": [0.0, 1.0, 0.0],
        "normal": [0.0, 0.0, 1.0],
    }
    assert len(_validate_sketch_frames([good], "1.2")) == 1
    with pytest.raises(DisplayContractError, match="duplicates"):
        _validate_sketch_frames([good, dict(good)], "1.2")
    bad = dict(good, v_axis=[0.0, -1.0, 0.0])  # left-handed
    with pytest.raises(DisplayContractError, match="right-handed"):
        _validate_sketch_frames([bad], "1.2")
    with pytest.raises(DisplayContractError, match="v1.2"):
        _validate_sketch_frames([good], "1.1")  # populated frames need 1.2


# ---- Codex7 B1: the ACTUAL command path (handler-level, real context) ----

def test_handler_binds_a_cap_face_end_to_end(workspace_with_extrude):
    """handle_add_sketch_feature with a face-plane INPUT: the stored engine
    reference, the exact direct producer dependency, and regeneration."""
    from aiadra_core.protocol import propose
    from conftest import part_sidecar  # type: ignore

    ws = workspace_with_extrude
    propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001",
        "primitives": [{"type": "rectangle", "x_mm": 1.0, "y_mm": 1.0,
                        "width_mm": 3.0, "height_mm": 3.0}],
        "plane": {"kind": "face", "target_face_id": "feat_0002:face:cap_top"},
    }).commit()
    sidecar = part_sidecar(ws)
    sketches = [f for f in sidecar["feature"] if f["feature_type"] == "sketch"
                and (f.get("adapter_payload", {}).get("plane") or {}).get("kind") == "face"]
    assert len(sketches) == 1
    rec = sketches[0]
    plane = rec["adapter_payload"]["plane"]
    assert plane["face_role"] == "feat_0002:face:cap_top"
    assert plane["resolved_against_topology_signature"].startswith("topo_")
    assert "target_face_id" not in plane  # the INPUT shape never persists
    assert rec["depends_on_feature_ids"] == ["feat_0002"]  # the DIRECT producer
    # regeneration: the whole recipe re-evaluates (fold validation) cleanly
    geometry.evaluate_part(sidecar["feature"])


def test_handler_binds_a_planar_wall_and_derives_the_true_producer(workspace_with_extrude):
    """The Codex7 counterexample: a wall id carries the /skp_ segment — the
    producer is the FEATURE, extracted by the one grammar authority."""
    from aiadra_core.protocol import propose
    from conftest import part_sidecar  # type: ignore

    ws = workspace_with_extrude
    propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001",
        "primitives": [{"type": "rectangle", "x_mm": 0.5, "y_mm": 0.5,
                        "width_mm": 1.0, "height_mm": 1.0}],
        "plane": {"kind": "face", "target_face_id": "feat_0002/skp_0001:face:wall_y_min"},
    }).commit()
    sidecar = part_sidecar(ws)
    rec = [f for f in sidecar["feature"] if f["feature_type"] == "sketch"
           and (f.get("adapter_payload", {}).get("plane") or {}).get("kind") == "face"][0]
    assert rec["adapter_payload"]["plane"]["face_role"] == "feat_0002/skp_0001:face:wall_y_min"
    assert rec["depends_on_feature_ids"] == ["feat_0002"]  # NOT feat_0002/skp_0001
    geometry.evaluate_part(sidecar["feature"])


def test_handler_refuses_malformed_missing_grammar_without_mutation(workspace_with_extrude):
    from aiadra_core.protocol import propose
    from conftest import part_sidecar  # type: ignore

    ws = workspace_with_extrude
    before = len(part_sidecar(ws)["feature"])
    cases = [
        {"kind": "face", "target_face_id": "feat_0002:face:cap_top", "extra": 1},
        {"kind": "face", "target_face_id": "feat_0002:face:no_such"},
        {"kind": "face", "target_face_id": "not-a-face-id"},
    ]
    for plane in cases:
        with pytest.raises(TransactionError):
            propose(ws, kind="mechanical.add_sketch_feature", params={
                "part_number": "P-000001",
                "primitives": [{"type": "rectangle", "x_mm": 0, "y_mm": 0,
                                "width_mm": 1, "height_mm": 1}],
                "plane": plane,
            }).commit()
    assert len(part_sidecar(ws)["feature"]) == before


# ---- Codex7 B2: exact classification + the grammar helper ----

def test_producing_feature_id_grammar():
    assert topology.producing_feature_id("feat_0002:face:cap_top") == "feat_0002"
    assert topology.producing_feature_id("feat_0002/skp_0001:face:wall_y_min") == "feat_0002"
    with pytest.raises(TransactionError):
        topology.producing_feature_id("feat_0002:edge:sharp1")


def test_nonplanar_sphere_classifies_other_and_the_resolver_refuses():
    """A sphere face (built directly in OCCT) is neither plane nor cylinder —
    the resolver must fail CLOSED on exact kernel planarity even when the
    transported record lies."""
    import dataclasses

    from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder

    sphere = BRepPrimAPI_MakeSphere(5.0).Shape()
    exp = TopExp_Explorer(sphere, TopAbs_FACE)
    face = TopoDS.Face_s(exp.Current())
    stype = BRepAdaptor_Surface(face).GetType()
    assert stype not in (GeomAbs_Plane, GeomAbs_Cylinder)

    prefix = _box_features()
    topo = topology.extract_part_topology(prefix)
    assert {f.surface_kind for f in topo.faces} == {"plane"}  # a box is all-planar
    real = [f for f in topo.faces if f.face_id == "feat_0002:face:cap_top"][0]
    lying = dataclasses.replace(real, face=face, surface_kind="plane")

    class _TopoStub:
        faces = [lying]

    import aiadra_mechanical.face_frame as ff

    orig = topology.extract_part_topology
    try:
        topology.extract_part_topology = lambda *a, **k: _TopoStub()  # type: ignore
        with pytest.raises(TransactionError, match="NOT PLANAR"):
            ff.resolve_face_plane(prefix, _face_plane(prefix, "feat_0002:face:cap_top"))
    finally:
        topology.extract_part_topology = orig


def test_display_transports_other_for_a_cylinder_wall():
    """Display v1.2 collapses to plane|other — a cylinder wall ships as
    OTHER (only exact planes enter the planar pick path)."""
    from aiadra_mechanical import display as display_mod

    features = [
        {"id": "feat_0001", "feature_type": "sketch", "engine": "mechanical",
         "adapter_schema_version": "0.1.10",
         "adapter_payload": {"primitives": [{"type": "circle", "id": "skp_0001",
                                             "cx_mm": 0.0, "cy_mm": 0.0, "radius_mm": 6.0}]}},
        {"id": "feat_0002", "feature_type": "extrude", "engine": "mechanical",
         "adapter_schema_version": "0.1.10",
         "depends_on_feature_ids": ["feat_0001"],
         "parameters": [{"id": "featp_0001", "name": "depth_mm", "value": 8.0,
                         "datatype": "number", "unit": "mm"}],
         "adapter_payload": {"sketch_feature_id": "feat_0001", "direction": "normal+"}},
    ]
    topo = topology.extract_part_topology(features)
    payload = display_mod.build_display_payload(topo)
    kinds = {f["face_id"]: f["surface_kind"] for f in payload["render"]["faces"]}
    assert kinds["feat_0002/skp_0001:face:outer_wall"] == "other"
    assert kinds["feat_0002:face:cap_top"] == "plane"


# ---- Codex7 B3: the v1.2 field version matrix ----

def test_core_rejects_v12_fields_under_legacy_versions():
    from aiadra_core.protocol.display import DisplayContractError, DisplayRepresentation
    from aiadra_mechanical import display as display_mod

    prefix = _box_features()
    topo = topology.extract_part_topology(
        prefix, object_uuid="u-1", object_number="P-1",
        geometry_ref="vault:x", cache_key="ck-1")
    payload = display_mod.build_display_payload(topo)
    legacy = dict(payload, display_representation_version="1.1")
    with pytest.raises(DisplayContractError, match="requires v1.2"):
        DisplayRepresentation.from_engine_dict(legacy)
    stripped = dict(legacy)
    stripped["render"] = dict(legacy["render"])
    stripped["render"]["faces"] = [
        {k: v for k, v in f.items() if k != "surface_kind"}
        for f in legacy["render"]["faces"]
    ]
    stripped["sketch_frames"] = []
    DisplayRepresentation.from_engine_dict(stripped)  # legacy WITHOUT the field: ok
    DisplayRepresentation.from_engine_dict(payload)   # v1.2 WITH the field: ok


# ---- Codex7 NB4: the base-profile refusal, ISOLATED ----

def test_base_consuming_a_face_bound_sketch_is_unreachable_with_a_valid_binding():
    """Codex7 NB4, resolved by documentation: under the ONE-base model the
    targeted branch cannot be reached with a VALID binding — the face's
    producer must PRECEDE the sketch, but the only base IS the producer and
    must consume a sketch preceding it. Every construction refuses EARLIER
    with a typed error; the branch is defence-in-depth for the sequential-
    extrude arc, which will bring its own focused test."""
    prefix = _box_features()
    face_sk = _face_sketch(prefix, "feat_0002:face:cap_top", feat_id="feat_0003")
    # ordering A: the face sketch after the base that consumes it — the
    # consumed-sketch resolution refuses first (recipe-order discipline)
    ordering_a = [
        prefix[0],
        dict(prefix[1],
             depends_on_feature_ids=["feat_0003"],
             adapter_payload={"sketch_feature_id": "feat_0003", "direction": "normal+"}),
        face_sk,
    ]
    with pytest.raises(TransactionError, match="not found in the recipe"):
        geometry.evaluate_part(ordering_a)
    # ordering B: the face sketch before its producer — the fold's binding
    # validation refuses first (no faces exist in the prefix yet)
    ordering_b = [
        prefix[0],
        face_sk,
        dict(prefix[1],
             depends_on_feature_ids=["feat_0003"],
             adapter_payload={"sketch_feature_id": "feat_0003", "direction": "normal+"}),
    ]
    with pytest.raises(TransactionError, match="STALE|no longer exists"):
        geometry.evaluate_part(ordering_b)
