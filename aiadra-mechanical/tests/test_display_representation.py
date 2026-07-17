"""Display Representation + topology-identity tests (arc 20260609-1; ADR/0035).

The crux of the rendering & topology foundation: prove the engine produces a
correct, versioned Display Representation AND that engine-minted, feature-
anchored topology identity SURVIVES an edit (the D5 selection trap) — plus the
B2 close conditions: deterministic `topology_signature`, role-to-shape
correspondence, the symmetric-face trap, and the tangent-edge classifier on a
real OCCT fillet.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from aiadra_core.protocol import display_representation, propose
from aiadra_core.protocol.display import DisplayRepresentation, DisplayContractError
from aiadra_core.transaction.boundary import TransactionError

from aiadra_mechanical.adapter_payload import build_sketch_payload, build_extrude_payload
from aiadra_mechanical import display, topology

from conftest import two_primitives  # type: ignore


# ----------------------------------------------------------------------------
# Recipe helpers (engine-level, no workspace)
# ----------------------------------------------------------------------------


def _recipe(depth=10.0, with_hole=True, with_extrude=True, w=40.0, h=30.0):
    prims = [{"type": "rectangle", "x_mm": 0, "y_mm": 0, "width_mm": w, "height_mm": h}]
    if with_hole:
        prims.append({"type": "circle", "cx_mm": w / 2, "cy_mm": h / 2, "radius_mm": 5})
    feats = [{"id": "feat_0001", "feature_type": "sketch",
              "adapter_payload": build_sketch_payload(prims)}]
    if with_extrude:
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


def _ids(d):
    return (
        {f["face_id"] for f in d["render"]["faces"]},
        {e["edge_id"] for e in d["render"]["edges"]},
        {v["vertex_id"] for v in d["render"]["vertices"]},
    )


# ----------------------------------------------------------------------------
# 1. Role grammar + contract shape (engine-level)
# ----------------------------------------------------------------------------


def test_box_with_hole_role_grammar():
    d = _gen(_recipe())
    faces, _, _ = _ids(d)
    assert faces == {
        "feat_0002:face:cap_base",
        "feat_0002:face:cap_top",
        "feat_0002/skp_0001:face:wall_x_min",
        "feat_0002/skp_0001:face:wall_x_max",
        "feat_0002/skp_0001:face:wall_y_min",
        "feat_0002/skp_0001:face:wall_y_max",
        "feat_0002/skp_0002:face:hole_wall",
    }


def test_box_with_hole_edge_kinds():
    d = _gen(_recipe())
    kinds = d["counters"]["edge_count_by_kind"]
    # 12 box edges + 2 rims = 14 sharp; 1 cylinder seam; ZERO tangent
    # (the box-with-hole has no smooth edge — tangent needs a fillet).
    assert kinds == {"sharp": 14, "seam": 1}
    assert "tangent" not in kinds


def test_contract_round_trips_through_dto():
    d = _gen(_recipe())
    dr = DisplayRepresentation.from_engine_dict(d)
    assert dr.display_representation_version == "1.2"
    assert dr.view_dependent is None  # base display never inlines HLR
    assert dr.selection.id_space == "canonical"
    assert dr.counters.face_count == 7
    # every face buffer is internally consistent (3 floats/node, 3 idx/triangle)
    for fb in dr.render.faces:
        assert len(fb.positions) % 3 == 0
        assert len(fb.normals) == len(fb.positions)
        assert len(fb.triangles) % 3 == 0
        max_idx = max(fb.triangles) if fb.triangles else -1
        assert max_idx < len(fb.positions) // 3


def test_dto_rejects_malformed_view_dependent():
    """Contract v1.1 (arc 20260609-2): the slot may be populated, but only by
    a VALID ViewDependentPayload — junk is still rejected loudly."""
    d = _gen(_recipe())
    d["view_dependent"] = {"hlr": "nope"}
    with pytest.raises(DisplayContractError):
        DisplayRepresentation.from_engine_dict(d)


def test_dto_v1_0_still_rejects_any_populated_view_dependent():
    """The v1.0 rule survives verbatim (arc 20260609-2 Codex1 Q7): a producer
    claiming contract 1.0 must ship a null slot, even a well-formed payload."""
    d = _gen(_recipe())
    d["display_representation_version"] = "1.0"
    # an honest 1.0 producer ships NEITHER v1.2 field (S2: their presence
    # under a legacy identity is its own rejection, tested separately)
    d.pop("sketch_frames", None)
    d["render"]["faces"] = [
        {k: v for k, v in f.items() if k != "surface_kind"}
        for f in d["render"]["faces"]
    ]
    d["view_dependent"] = {"identity_echo": {}, "views": []}
    with pytest.raises(DisplayContractError, match="view_dependent must be null"):
        DisplayRepresentation.from_engine_dict(d)


def test_true_surface_normals_present():
    d = _gen(_recipe())
    cap = next(f for f in d["render"]["faces"] if f["face_id"].endswith("cap_top"))
    # cap_top outward normal is +z everywhere
    n = cap["normals"]
    for k in range(0, len(n), 3):
        assert n[k + 2] == pytest.approx(1.0, abs=1e-6)


# ----------------------------------------------------------------------------
# 2. Topology signature (B2) — deterministic, value-independent
# ----------------------------------------------------------------------------


def test_topology_signature_stable_across_parameter_edit():
    a = display.compute_topology_signature(_recipe(depth=5.0))
    b = display.compute_topology_signature(_recipe(depth=99.0))
    assert a == b  # depth is a value, not topology


def test_topology_signature_changes_when_hole_added():
    no_hole = display.compute_topology_signature(_recipe(with_hole=False))
    with_hole = display.compute_topology_signature(_recipe(with_hole=True))
    assert no_hole != with_hole


def test_missing_primitive_id_fails_loud_no_placeholder(monkeypatch):
    """B1 (Codex2): a corrupt/legacy sketch primitive WITHOUT an engine-minted
    `skp_` id must fail loud — never mint a placeholder display id. Built via
    the real payload builder, then the id is stripped to simulate corruption."""
    feats = _recipe(with_hole=True)
    # Strip the rectangle primitive's engine-minted id (simulate a pre-0.1.1 /
    # corrupt payload that the opaque adapter_payload schema cannot catch).
    for p in feats[0]["adapter_payload"]["primitives"]:
        if p["type"] == "rectangle":
            del p["id"]
    with pytest.raises(TransactionError, match=r"skp_"):
        _gen(feats)


def test_malformed_primitive_id_fails_loud(monkeypatch):
    feats = _recipe(with_hole=False)
    feats[0]["adapter_payload"]["primitives"][0]["id"] = "rect"  # not ^skp_NNNN$
    with pytest.raises(TransactionError, match=r"skp_"):
        _gen(feats)


def test_add_hole_keeps_box_faces_adds_hole_faces():
    box = _gen(_recipe(with_hole=False))
    holed = _gen(_recipe(with_hole=True))
    box_faces, _, _ = _ids(box)
    holed_faces, _, _ = _ids(holed)
    assert box_faces.issubset(holed_faces)            # box roles survive
    new = holed_faces - box_faces
    assert new == {"feat_0002/skp_0002:face:hole_wall"}  # only the hole is new


# ----------------------------------------------------------------------------
# 3. Symmetric-face trap (B2) — equal areas, distinct sketch-edge anchors
# ----------------------------------------------------------------------------


def test_square_prism_walls_not_collapsed_by_equal_area():
    d = _gen(_recipe(with_hole=False, w=30.0, h=30.0))  # square: 4 congruent walls
    faces, _, _ = _ids(d)
    walls = sorted(r for r in faces if ":face:wall_" in r)
    assert walls == [
        "feat_0002/skp_0001:face:wall_x_max",
        "feat_0002/skp_0001:face:wall_x_min",
        "feat_0002/skp_0001:face:wall_y_max",
        "feat_0002/skp_0001:face:wall_y_min",
    ]  # 4 distinct roles — centroid-magnitude/area alone could not separate them


# ----------------------------------------------------------------------------
# 4. Tangent-edge classifier on a real OCCT fillet fixture (N1)
# ----------------------------------------------------------------------------


def _filleted_box():
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopoDS import TopoDS

    box = BRepPrimAPI_MakeBox(20.0, 20.0, 20.0).Shape()
    mk = BRepFilletAPI_MakeFillet(box)
    exp = TopExp_Explorer(box, TopAbs_EDGE)
    mk.Add(3.0, TopoDS.Edge_s(exp.Current()))
    return mk.Shape()


def test_tangent_classifier_detects_fillet_smooth_edges():
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopExp import TopExp
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopoDS import TopoDS
    from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape

    shape = _filleted_box()
    BRepMesh_IncrementalMesh(shape, 0.1, False, 0.5, True)
    edge_faces = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, edge_faces)
    kinds: dict[str, int] = {}
    for i in range(1, edge_faces.Extent() + 1):
        edge = TopoDS.Edge_s(edge_faces.FindKey(i))
        adj = [TopoDS.Face_s(f) for f in edge_faces.FindFromIndex(i)]
        k = topology._edge_kind(edge, adj)  # B1: classification lives in the shared layer
        kinds[k] = kinds.get(k, 0) + 1
    # The fillet meets its two neighbour faces along smooth (G1) tangent edges.
    assert kinds.get("tangent", 0) >= 2, f"expected ≥2 tangent edges, got {kinds}"


# ----------------------------------------------------------------------------
# 5. End-to-end through the Ring-2 read primitive + across-edit identity (D5)
# ----------------------------------------------------------------------------


def test_display_representation_end_to_end(workspace_with_extrude: Path):
    dr = display_representation(workspace_with_extrude, "P-000001")
    assert isinstance(dr, DisplayRepresentation)
    assert dr.counters.face_count == 7
    assert dr.identity.object_number == "P-000001"
    assert dr.identity.geometry_ref.startswith("sha256:")
    assert dr.selection.id_space == "canonical"
    # human names are present + Creo-styled
    assert any(name == "CAP_TOP" for name in dr.selection.names.values())


def test_identity_survives_parameter_edit(workspace_with_extrude: Path):
    ws = workspace_with_extrude
    before = display_representation(ws, "P-000001")

    propose(ws, kind="mechanical.adjust_feature_parameter", params={
        "part_number": "P-000001", "feature_id": "feat_0002",
        "parameter_name": "depth_mm", "new_value": 12.0,
    }).commit()

    after = display_representation(ws, "P-000001")

    # The CRUX: every display id is identical across the edit/recompute...
    assert {f.face_id for f in before.render.faces} == {f.face_id for f in after.render.faces}
    assert {e.edge_id for e in before.render.edges} == {e.edge_id for e in after.render.edges}
    assert {v.vertex_id for v in before.render.vertices} == {v.vertex_id for v in after.render.vertices}
    # ...and the topology signature is unchanged (a parameter edit, not topology)...
    assert before.identity.topology_signature == after.identity.topology_signature
    # ...while the geometry actually moved (depth 5 → 12) — so this is a real recompute.
    assert before.render.bbox_max[2] == pytest.approx(5.0, abs=1e-6)
    assert after.render.bbox_max[2] == pytest.approx(12.0, abs=1e-6)
    assert before.identity.geometry_ref != after.identity.geometry_ref


def test_role_to_shape_correspondence_after_edit(workspace_with_extrude: Path):
    """Not just set-equality: the cap_top role must still map to the geometric
    top face after the edit (role → shape correspondence, per B2)."""
    ws = workspace_with_extrude
    propose(ws, kind="mechanical.adjust_feature_parameter", params={
        "part_number": "P-000001", "feature_id": "feat_0002",
        "parameter_name": "depth_mm", "new_value": 12.0,
    }).commit()
    dr = display_representation(ws, "P-000001")
    cap_top = next(f for f in dr.render.faces if f.face_id.endswith("cap_top"))
    zs = [cap_top.positions[k + 2] for k in range(0, len(cap_top.positions), 3)]
    assert all(z == pytest.approx(12.0, abs=1e-6) for z in zs)  # top is at new depth


def test_display_representation_is_read_only(workspace_with_extrude: Path):
    """A display read must not write any workspace file (no draft, no events)."""
    ws = workspace_with_extrude

    def snap():
        return {str(p.relative_to(ws)) for p in ws.rglob("*")
                if p.is_file() and ".git" not in p.parts}

    before = snap()
    display_representation(ws, "P-000001")
    display_representation(ws, "P-000001")  # twice — deterministic, still no writes
    assert snap() == before
