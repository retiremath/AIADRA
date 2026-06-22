"""Hole-as-feature — the first FACE reference (ADR/0037 D8; ADR/0038 A1–A3;
arc 20260622-2).

Covers the acceptance bar (the authoring op + canonical-unit params; the
engine-owned `target_face` reference NOT a display id; parent parameter-edit
survival incl. the width edit Codex1 N2; topology-change / missing / removed-
parent / non-cap / holed-cap / fit-breach fail-loud; by-construction hole-wall
role) plus the amendment invariants: A2 (values not skeleton — Codex1 B1) and A3
(mandatory produced-face claim — Codex1 B2).
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from aiadra_core.native_engine.exceptions import NativeEngineKernelError
from aiadra_core.protocol import propose
from aiadra_core.transaction.boundary import TransactionError
from aiadra_core.validation.fold import FoldInconsistencyError

from aiadra_mechanical import geometry, topology
from aiadra_mechanical.adapter_payload import (
    build_extrude_payload,
    build_hole_payload,
    build_sketch_payload,
)
from aiadra_mechanical.geometry import ProducedFaceHint

from conftest import part_sidecar  # type: ignore

from OCP.TopExp import TopExp
from OCP.TopAbs import TopAbs_FACE
from OCP.TopTools import TopTools_IndexedMapOfShape


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _make_box(ws: Path, *, w: float = 23.0, h: float = 11.0, depth: float = 6.0) -> None:
    propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001",
        "primitives": [{"type": "rectangle", "x_mm": 0.0, "y_mm": 0.0, "width_mm": w, "height_mm": h}],
    }).commit()
    propose(ws, kind="mechanical.add_extrude_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001",
        "depth_mm": depth, "direction": "z+"}).commit()


def _make_box_with_sketch_hole(ws: Path) -> None:
    propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001",
        "primitives": [
            {"type": "rectangle", "x_mm": 0.0, "y_mm": 0.0, "width_mm": 23.0, "height_mm": 11.0},
            {"type": "circle", "cx_mm": 6.0, "cy_mm": 4.5, "radius_mm": 2.0}],
    }).commit()
    propose(ws, kind="mechanical.add_extrude_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001",
        "depth_mm": 6.0, "direction": "z+"}).commit()


def _face_id(ws: Path, suffix: str) -> str:
    faces = topology.extract_part_topology(part_sidecar(ws)["feature"]).faces
    return next(f.face_id for f in faces if f.face_id.endswith(suffix))


def _box_with_hole_recipe(diameter: float = 4.0, cx: float = 11.5, cy: float = 5.5) -> list[dict]:
    feats = [
        {"id": "feat_0001", "feature_type": "sketch",
         "adapter_payload": build_sketch_payload(
             [{"type": "rectangle", "x_mm": 0.0, "y_mm": 0.0, "width_mm": 23.0, "height_mm": 11.0}])},
        {"id": "feat_0002", "feature_type": "extrude",
         "parameters": [{"id": "featp_0001", "name": "depth_mm", "value": 6.0,
                         "datatype": "number", "unit": "mm"}],
         "adapter_payload": build_extrude_payload(
             sketch_feature_id="feat_0001", direction="z+", depth_parameter_id="featp_0001")},
    ]
    topo = topology.extract_part_topology(feats)
    cap = next(f for f in topo.faces if f.face_id.endswith(":face:cap_top"))
    hole = {
        "id": "feat_0003", "feature_type": "hole",
        "depends_on_feature_ids": ["feat_0002"],
        "parameters": [
            {"id": "featp_0002", "name": "diameter_mm", "value": diameter, "datatype": "number", "unit": "mm"},
            {"id": "featp_0003", "name": "center_x_mm", "value": cx, "datatype": "number", "unit": "mm"},
            {"id": "featp_0004", "name": "center_y_mm", "value": cy, "datatype": "number", "unit": "mm"},
        ],
        "adapter_payload": build_hole_payload(
            face_role=cap.face_id, resolved_against_topology_signature=topo.topology_signature),
    }
    return feats + [hole]


# ----------------------------------------------------------------------------
# Acceptance bar — API-level
# ----------------------------------------------------------------------------


def test_add_hole_happy_path(workspace_with_part: Path):
    ws = workspace_with_part
    _make_box(ws)
    cap = _face_id(ws, ":face:cap_top")
    before = part_sidecar(ws)["geometry_ref"][0]["vault_ref"]

    propose(ws, kind="mechanical.add_hole_feature", params={
        "part_number": "P-000001", "target_face_id": cap,
        "diameter_mm": 4.0, "center_x_mm": 11.5, "center_y_mm": 5.5}).commit()

    sc = part_sidecar(ws)
    hole = [f for f in sc["feature"] if f["feature_type"] == "hole"][0]
    assert hole["depends_on_feature_ids"] == ["feat_0002"]
    names = {p["name"]: p for p in hole["parameters"]}
    assert set(names) == {"diameter_mm", "center_x_mm", "center_y_mm"}
    assert all(p["unit"] == "mm" and p["datatype"] == "number" for p in hole["parameters"])
    assert names["diameter_mm"]["value"] == 4.0
    tf = hole["adapter_payload"]["target_face"]
    assert tf["face_role"] == cap
    assert tf["resolved_against_topology_signature"].startswith("topo_")
    assert before != part_sidecar(ws)["geometry_ref"][0]["vault_ref"]


def test_add_hole_on_cap_base(workspace_with_part: Path):
    """Codex1 N3: cap_base is supported too (the through-cut spans the solid's
    full Z-extent, direction-agnostic) — the stored reference is the cap_base
    role."""
    ws = workspace_with_part
    _make_box(ws)
    cap_base = _face_id(ws, ":face:cap_base")
    propose(ws, kind="mechanical.add_hole_feature", params={
        "part_number": "P-000001", "target_face_id": cap_base,
        "diameter_mm": 4.0, "center_x_mm": 11.5, "center_y_mm": 5.5}).commit()
    hole = [f for f in part_sidecar(ws)["feature"] if f["feature_type"] == "hole"][0]
    assert hole["adapter_payload"]["target_face"]["face_role"].endswith(":face:cap_base")
    topo = topology.extract_part_topology(part_sidecar(ws)["feature"])
    assert any(f.face_id.endswith(":face:hole_wall") for f in topo.faces)


def test_target_face_is_structured_with_signature(workspace_with_part: Path):
    """ADR/0038 D1/A1: the reference is the structured `{face_role, signature}`
    resolved against a fresh extraction — not a bare display id, and the values
    (diameter/centre) are NOT in the reference shape (A2)."""
    ws = workspace_with_part
    _make_box(ws)
    cap = _face_id(ws, ":face:cap_top")
    propose(ws, kind="mechanical.add_hole_feature", params={
        "part_number": "P-000001", "target_face_id": cap,
        "diameter_mm": 4.0, "center_x_mm": 11.5, "center_y_mm": 5.5}).commit()
    payload = [f for f in part_sidecar(ws)["feature"] if f["feature_type"] == "hole"][0]["adapter_payload"]
    assert set(payload["target_face"]) == {"face_role", "resolved_against_topology_signature"}
    assert "diameter_mm" not in payload["target_face"]  # values are parameters, not the reference


def test_hole_wall_role_by_construction(workspace_with_part: Path):
    """A3: the hole wall gets a feature-owned `…:face:hole_wall` role by
    construction (a cylinder), never re-guessed from geometry."""
    ws = workspace_with_part
    _make_box(ws)
    cap = _face_id(ws, ":face:cap_top")
    propose(ws, kind="mechanical.add_hole_feature", params={
        "part_number": "P-000001", "target_face_id": cap,
        "diameter_mm": 4.0, "center_x_mm": 11.5, "center_y_mm": 5.5}).commit()

    feats = part_sidecar(ws)["feature"]
    hole_id = [f["id"] for f in feats if f["feature_type"] == "hole"][0]
    topo = topology.extract_part_topology(feats)
    walls = [f for f in topo.faces if f.face_id.startswith(f"{hole_id}:face:hole_wall")]
    assert walls and all(f.surface_kind == "cylinder" for f in walls)


def test_hole_survives_parent_depth_edit(workspace_with_part: Path):
    """ADR/0038 D4 survival: a parent parameter edit preserves the face role."""
    ws = workspace_with_part
    _make_box(ws)
    cap = _face_id(ws, ":face:cap_top")
    propose(ws, kind="mechanical.add_hole_feature", params={
        "part_number": "P-000001", "target_face_id": cap,
        "diameter_mm": 4.0, "center_x_mm": 11.5, "center_y_mm": 5.5}).commit()
    tf_before = [f for f in part_sidecar(ws)["feature"]
                 if f["feature_type"] == "hole"][0]["adapter_payload"]["target_face"]

    propose(ws, kind="mechanical.adjust_feature_parameter", params={
        "part_number": "P-000001", "feature_id": "feat_0002",
        "parameter_name": "depth_mm", "new_value": 10.0}).commit()

    sc = part_sidecar(ws)
    hole = [f for f in sc["feature"] if f["feature_type"] == "hole"][0]
    assert hole["adapter_payload"]["target_face"] == tf_before
    topo = topology.extract_part_topology(sc["feature"])
    assert any(f.face_id.endswith(":face:hole_wall") for f in topo.faces)


def test_hole_diameter_edit_recomputes(workspace_with_part: Path):
    ws = workspace_with_part
    _make_box(ws)
    cap = _face_id(ws, ":face:cap_top")
    propose(ws, kind="mechanical.add_hole_feature", params={
        "part_number": "P-000001", "target_face_id": cap,
        "diameter_mm": 4.0, "center_x_mm": 11.5, "center_y_mm": 5.5}).commit()
    hole_id = [f["id"] for f in part_sidecar(ws)["feature"] if f["feature_type"] == "hole"][0]
    before = part_sidecar(ws)["geometry_ref"][0]["vault_ref"]

    propose(ws, kind="mechanical.adjust_feature_parameter", params={
        "part_number": "P-000001", "feature_id": hole_id,
        "parameter_name": "diameter_mm", "new_value": 5.0}).commit()

    assert before != part_sidecar(ws)["geometry_ref"][0]["vault_ref"]


def test_edit_center_breaching_cap_fails_loud(workspace_with_part: Path):
    """Codex2 B1: editing the centre so the footprint breaches the cap fails
    Class-1 on the REGENERATION path (the gate re-runs the domain check), not as
    a side-breaching cut or a Class-2 surprise — and does not commit."""
    ws = workspace_with_part
    _make_box(ws)
    cap = _face_id(ws, ":face:cap_top")
    propose(ws, kind="mechanical.add_hole_feature", params={
        "part_number": "P-000001", "target_face_id": cap,
        "diameter_mm": 4.0, "center_x_mm": 11.5, "center_y_mm": 5.5}).commit()
    hole_id = [f["id"] for f in part_sidecar(ws)["feature"] if f["feature_type"] == "hole"][0]

    with pytest.raises(TransactionError, match="fit entirely inside"):
        propose(ws, kind="mechanical.adjust_feature_parameter", params={
            "part_number": "P-000001", "feature_id": hole_id,
            "parameter_name": "center_x_mm", "new_value": 22.0})  # 22 + 2 > 23
    # unchanged on disk
    hole = [f for f in part_sidecar(ws)["feature"] if f["feature_type"] == "hole"][0]
    cx = {p["name"]: p["value"] for p in hole["parameters"]}["center_x_mm"]
    assert cx == 11.5


def test_edit_diameter_too_large_fails_loud(workspace_with_part: Path):
    """Codex2 B1: an oversized diameter edit fails Class-1 on the gate path."""
    ws = workspace_with_part
    _make_box(ws)
    cap = _face_id(ws, ":face:cap_top")
    propose(ws, kind="mechanical.add_hole_feature", params={
        "part_number": "P-000001", "target_face_id": cap,
        "diameter_mm": 4.0, "center_x_mm": 11.5, "center_y_mm": 5.5}).commit()
    hole_id = [f["id"] for f in part_sidecar(ws)["feature"] if f["feature_type"] == "hole"][0]

    with pytest.raises(TransactionError, match="fit entirely inside"):
        propose(ws, kind="mechanical.adjust_feature_parameter", params={
            "part_number": "P-000001", "feature_id": hole_id,
            "parameter_name": "diameter_mm", "new_value": 24.0})  # radius 12 >> box


def test_evaluator_enforces_fit_independent_of_handler():
    """Codex2 B1: the v1 fit contract lives in the evaluator fold, so a stored
    recipe whose hole breaches the cap fails Class-1 before the kernel — even
    though no handler ran."""
    feats = _box_with_hole_recipe(diameter=4.0, cx=22.0, cy=5.5)  # 22 + 2 > 23
    with pytest.raises(TransactionError, match="fit entirely inside"):
        geometry.evaluate_part(feats)


def test_remove_parent_with_dependent_hole_fails_loud(workspace_with_part: Path):
    """ADR/0038 D5: removing the parent solid while the hole depends on it fails
    loud via the core cascade (ADR/0029 D12)."""
    ws = workspace_with_part
    _make_box(ws)
    cap = _face_id(ws, ":face:cap_top")
    propose(ws, kind="mechanical.add_hole_feature", params={
        "part_number": "P-000001", "target_face_id": cap,
        "diameter_mm": 4.0, "center_x_mm": 11.5, "center_y_mm": 5.5}).commit()

    draft = propose(ws, kind="mechanical.remove_feature", params={
        "part_number": "P-000001", "feature_ids": ["feat_0002"]})
    with pytest.raises(FoldInconsistencyError, match="depends_on_feature_ids"):
        draft.validate()


def test_non_cap_face_rejected(workspace_with_part: Path):
    """Cap-only operation guard: a wall face is planar but not a cap → Class-1."""
    ws = workspace_with_part
    _make_box(ws)
    wall = _face_id(ws, ":face:wall_x_max")
    before = len(part_sidecar(ws)["feature"])
    with pytest.raises(TransactionError, match="cap face only"):
        propose(ws, kind="mechanical.add_hole_feature", params={
            "part_number": "P-000001", "target_face_id": wall,
            "diameter_mm": 2.0, "center_x_mm": 11.5, "center_y_mm": 5.5})
    assert len(part_sidecar(ws)["feature"]) == before


def test_holed_cap_rejected_simple_cap_only(workspace_with_part: Path):
    """Codex1 B3: v1 supports a simple cap only — a cap with an existing sketch
    hole is an unsupported target face."""
    ws = workspace_with_part
    _make_box_with_sketch_hole(ws)
    cap = _face_id(ws, ":face:cap_top")
    with pytest.raises(TransactionError, match="simple cap only"):
        propose(ws, kind="mechanical.add_hole_feature", params={
            "part_number": "P-000001", "target_face_id": cap,
            "diameter_mm": 3.0, "center_x_mm": 15.0, "center_y_mm": 5.5})


def test_hole_outside_face_rejected(workspace_with_part: Path):
    """Codex1 B3: a hole whose footprint exceeds the cap boundary fails Class-1."""
    ws = workspace_with_part
    _make_box(ws)
    cap = _face_id(ws, ":face:cap_top")
    with pytest.raises(TransactionError, match="fit entirely inside"):
        propose(ws, kind="mechanical.add_hole_feature", params={
            "part_number": "P-000001", "target_face_id": cap,
            "diameter_mm": 4.0, "center_x_mm": 22.0, "center_y_mm": 5.5})  # 22+2 > 23


def test_unknown_target_face_id_fails_loud(workspace_with_part: Path):
    ws = workspace_with_part
    _make_box(ws)
    with pytest.raises(TransactionError, match="not found"):
        propose(ws, kind="mechanical.add_hole_feature", params={
            "part_number": "P-000001", "target_face_id": "feat_0002:face:nope",
            "diameter_mm": 2.0, "center_x_mm": 11.5, "center_y_mm": 5.5})


# ----------------------------------------------------------------------------
# Width-edit survival (Codex1 N2) + reference / amendment invariants — engine
# ----------------------------------------------------------------------------


def test_hole_survives_parent_width_edit():
    """Codex1 N2: sketch-XY placement survives a width edit (the plane-origin
    drift the spike found does NOT affect absolute sketch-coordinate placement).
    No API op edits a sketch dimension, so this is engine-level."""
    feats = _box_with_hole_recipe(diameter=4.0, cx=11.5, cy=5.5)
    wider = copy.deepcopy(feats)
    wider[0]["adapter_payload"]["primitives"][0]["width_mm"] = 30.0  # 23 -> 30
    # the skeleton signature is dimension-independent, so the hole still resolves
    topo = topology.extract_part_topology(wider)
    assert any(f.face_id.endswith(":face:hole_wall") for f in topo.faces)  # valid + present


def test_values_not_in_topology_signature():
    """ADR/0038 A2 (Codex1 B1): diameter/centre are NOT skeleton; retargeting IS.
    Two holes differing only in value parameters share a signature."""
    a = _box_with_hole_recipe(diameter=4.0, cx=11.5, cy=5.5)
    b = _box_with_hole_recipe(diameter=6.0, cx=8.0, cy=4.0)  # different values, same face
    assert topology.compute_topology_signature(a) == topology.compute_topology_signature(b)
    # ... but the hole IS a topology change vs the bare box, and the prefix is not
    assert topology.compute_topology_signature(a) != topology.compute_topology_signature(a[:2])


def test_stale_face_reference_fails_loud_on_topology_change():
    """ADR/0038 D4: a parent topology-skeleton change makes the stored signature
    stale → fail loud."""
    feats = _box_with_hole_recipe()
    feats[0]["adapter_payload"]["primitives"].append(
        {"id": "skp_0002", "type": "circle", "cx_mm": 18.0, "cy_mm": 8.0, "radius_mm": 1.0})
    with pytest.raises(TransactionError, match="STALE"):
        geometry.evaluate_part(feats)


def test_missing_face_role_fails_loud():
    """ADR/0038 D4: a reference whose face role is absent resolves to no face."""
    feats = _box_with_hole_recipe()
    feats[-1]["adapter_payload"]["target_face"]["face_role"] = "feat_0002:face:bogus"
    with pytest.raises(TransactionError, match="NO face"):
        geometry.evaluate_part(feats)


def test_produced_claim_is_mandatory():
    """ADR/0038 A3 (Codex1 B2): the produced-face claim is mandatory — a role
    with zero faces, or a hinted face absent from the final map, fails loud
    (never silently skipped)."""
    feats = _box_with_hole_recipe()
    shape = geometry.evaluate_part(feats[:2])  # the bare box
    fmap = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, TopAbs_FACE, fmap)

    with pytest.raises(TransactionError, match="zero faces"):
        topology._claimed_produced_roles(fmap, [ProducedFaceHint("feat_9", "hole_wall", ())])

    other = geometry.evaluate_part(_box_with_hole_recipe())  # a DIFFERENT shape
    other_map = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(other, TopAbs_FACE, other_map)
    from OCP.TopoDS import TopoDS
    foreign_face = TopoDS.Face_s(other_map.FindKey(1))  # not in `fmap`
    with pytest.raises(TransactionError, match="not present in the final shape"):
        topology._claimed_produced_roles(fmap, [ProducedFaceHint("feat_9", "hole_wall", (foreign_face,))])
