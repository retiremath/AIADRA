"""Chamfer — the fillet's edge-reference twin (ADR/0037 D8; ADR/0038; arc
20260622-3).

Mirrors the fillet acceptance bar, plus the chamfer-specific emphasis Codex
flagged: the bevel face is a PLANE, so this exercises ADR/0038 A3's mandatory
produced-face claim on a *planar* produced face — the happy path yields exactly
one planar `…:face:chamfer`, and a missed/neutered claim fails loud rather than
letting the bevel be assigned a base wall/cap role.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from aiadra_core.native_engine.exceptions import NativeEngineKernelError
from aiadra_core.protocol import propose
from aiadra_core.transaction.boundary import TransactionError
from aiadra_core.validation.fold import FoldInconsistencyError

from aiadra_mechanical import geometry, topology
from aiadra_mechanical.adapter_payload import (
    build_chamfer_payload,
    build_extrude_payload,
    build_sketch_payload,
)

from conftest import part_sidecar  # type: ignore


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


def _vertical_wall_edge_id(ws: Path) -> str:
    feats = part_sidecar(ws)["feature"]
    topo = topology.extract_part_topology(feats)
    return next(e.edge_id for e in topo.edges if e.kind == "sharp" and e.edge_id.count("wall_") == 2)


def _box_with_chamfer_recipe(distance: float = 2.0) -> list[dict]:
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
    target = next(e for e in topo.edges if e.kind == "sharp" and e.edge_id.count("wall_") == 2)
    chamfer = {
        "id": "feat_0003", "feature_type": "chamfer",
        "depends_on_feature_ids": ["feat_0002"],
        "parameters": [{"id": "featp_0002", "name": "distance_mm", "value": distance,
                        "datatype": "number", "unit": "mm"}],
        "adapter_payload": build_chamfer_payload(
            adjacent_face_roles=list(target.adjacent_face_ids),
            edge_kind=target.kind,
            resolved_against_topology_signature=topo.topology_signature),
    }
    return feats + [chamfer]


# ----------------------------------------------------------------------------
# Acceptance bar — API-level
# ----------------------------------------------------------------------------


def test_add_chamfer_happy_path(workspace_with_part: Path):
    ws = workspace_with_part
    _make_box(ws)
    eid = _vertical_wall_edge_id(ws)
    before = part_sidecar(ws)["geometry_ref"][0]["vault_ref"]

    propose(ws, kind="mechanical.add_chamfer_feature", params={
        "part_number": "P-000001", "target_edge_id": eid, "distance_mm": 2.0}).commit()

    sc = part_sidecar(ws)
    cham = [f for f in sc["feature"] if f["feature_type"] == "chamfer"][0]
    assert cham["depends_on_feature_ids"] == ["feat_0002"]
    p = cham["parameters"][0]
    assert p["name"] == "distance_mm" and p["value"] == 2.0 and p["unit"] == "mm"
    tgt = cham["adapter_payload"]["target_edge"]
    assert len(tgt["adjacent_face_roles"]) == 2 and tgt["edge_kind"] == "sharp"
    assert tgt["resolved_against_topology_signature"].startswith("topo_")
    assert before != part_sidecar(ws)["geometry_ref"][0]["vault_ref"]


def test_target_edge_is_structured_not_the_display_string(workspace_with_part: Path):
    ws = workspace_with_part
    _make_box(ws)
    eid = _vertical_wall_edge_id(ws)
    propose(ws, kind="mechanical.add_chamfer_feature", params={
        "part_number": "P-000001", "target_edge_id": eid, "distance_mm": 2.0}).commit()
    tgt = [f for f in part_sidecar(ws)["feature"]
           if f["feature_type"] == "chamfer"][0]["adapter_payload"]["target_edge"]
    assert set(tgt) == {"adjacent_face_roles", "edge_kind", "resolved_against_topology_signature"}
    assert eid not in tgt["adjacent_face_roles"]
    assert not any(r.startswith("edge:") for r in tgt["adjacent_face_roles"])


def test_chamfer_bevel_role_is_planar_by_construction(workspace_with_part: Path):
    """Codex R1 build bar: the bevel is a PLANE, claimed by construction as
    exactly one `feat_N:face:chamfer` (ADR/0038 A3 on a planar produced face).
    The rounded-away sharp edge is gone from the id set."""
    ws = workspace_with_part
    _make_box(ws)
    eid = _vertical_wall_edge_id(ws)
    propose(ws, kind="mechanical.add_chamfer_feature", params={
        "part_number": "P-000001", "target_edge_id": eid, "distance_mm": 2.0}).commit()

    feats = part_sidecar(ws)["feature"]
    cham_id = [f["id"] for f in feats if f["feature_type"] == "chamfer"][0]
    topo = topology.extract_part_topology(feats)
    bevels = [f for f in topo.faces if f.face_id == f"{cham_id}:face:chamfer"]
    assert len(bevels) == 1
    assert bevels[0].surface_kind == "plane"       # a flat bevel, NOT a cylinder
    assert eid not in {e.edge_id for e in topo.edges}


def test_missed_chamfer_claim_fails_loud_not_base_role(monkeypatch):
    """Codex R1 build bar + ADR/0038 A3: a neutered produced-role claim must FAIL
    LOUD — the planar bevel must not silently take a base wall/cap role."""
    feats = _box_with_chamfer_recipe()
    monkeypatch.setattr(topology, "_claimed_produced_roles", lambda face_map, produced_hints: {})
    with pytest.raises(TransactionError):  # the unclaimed bevel collides → fail loud
        topology.extract_part_topology(feats)


def test_chamfer_survives_parent_dimension_edit(workspace_with_part: Path):
    ws = workspace_with_part
    _make_box(ws)
    eid = _vertical_wall_edge_id(ws)
    propose(ws, kind="mechanical.add_chamfer_feature", params={
        "part_number": "P-000001", "target_edge_id": eid, "distance_mm": 2.0}).commit()
    tgt_before = [f for f in part_sidecar(ws)["feature"]
                  if f["feature_type"] == "chamfer"][0]["adapter_payload"]["target_edge"]

    propose(ws, kind="mechanical.adjust_feature_parameter", params={
        "part_number": "P-000001", "feature_id": "feat_0002",
        "parameter_name": "depth_mm", "new_value": 10.0}).commit()

    sc = part_sidecar(ws)
    cham = [f for f in sc["feature"] if f["feature_type"] == "chamfer"][0]
    assert cham["adapter_payload"]["target_edge"] == tgt_before
    topo = topology.extract_part_topology(sc["feature"])
    assert any(f.face_id.endswith(":face:chamfer") for f in topo.faces)


def test_chamfer_distance_edit_recomputes(workspace_with_part: Path):
    ws = workspace_with_part
    _make_box(ws)
    eid = _vertical_wall_edge_id(ws)
    propose(ws, kind="mechanical.add_chamfer_feature", params={
        "part_number": "P-000001", "target_edge_id": eid, "distance_mm": 2.0}).commit()
    cham_id = [f["id"] for f in part_sidecar(ws)["feature"] if f["feature_type"] == "chamfer"][0]
    before = part_sidecar(ws)["geometry_ref"][0]["vault_ref"]

    propose(ws, kind="mechanical.adjust_feature_parameter", params={
        "part_number": "P-000001", "feature_id": cham_id,
        "parameter_name": "distance_mm", "new_value": 3.0}).commit()

    assert before != part_sidecar(ws)["geometry_ref"][0]["vault_ref"]


def test_remove_parent_with_dependent_chamfer_fails_loud(workspace_with_part: Path):
    ws = workspace_with_part
    _make_box(ws)
    eid = _vertical_wall_edge_id(ws)
    propose(ws, kind="mechanical.add_chamfer_feature", params={
        "part_number": "P-000001", "target_edge_id": eid, "distance_mm": 2.0}).commit()
    draft = propose(ws, kind="mechanical.remove_feature", params={
        "part_number": "P-000001", "feature_ids": ["feat_0002"]})
    with pytest.raises(FoldInconsistencyError, match="depends_on_feature_ids"):
        draft.validate()


def test_non_sharp_edge_rejected(workspace_with_part: Path):
    ws = workspace_with_part
    _make_box_with_sketch_hole(ws)
    non_sharp = next(
        (e for e in topology.extract_part_topology(part_sidecar(ws)["feature"]).edges
         if e.kind != "sharp"), None)
    assert non_sharp is not None
    with pytest.raises(TransactionError, match="SHARP"):
        propose(ws, kind="mechanical.add_chamfer_feature", params={
            "part_number": "P-000001", "target_edge_id": non_sharp.edge_id, "distance_mm": 1.0})


def test_oversize_distance_is_class2_kernel_rejection(workspace_with_part: Path):
    ws = workspace_with_part
    _make_box(ws)
    eid = _vertical_wall_edge_id(ws)
    with pytest.raises(NativeEngineKernelError):
        propose(ws, kind="mechanical.add_chamfer_feature", params={
            "part_number": "P-000001", "target_edge_id": eid, "distance_mm": 50.0}).commit()


def test_unknown_target_edge_id_fails_loud(workspace_with_part: Path):
    ws = workspace_with_part
    _make_box(ws)
    with pytest.raises(TransactionError, match="not found"):
        propose(ws, kind="mechanical.add_chamfer_feature", params={
            "part_number": "P-000001", "target_edge_id": "edge:does:not:exist", "distance_mm": 2.0})


# ----------------------------------------------------------------------------
# Reference / amendment invariants — engine-level
# ----------------------------------------------------------------------------


def test_distance_not_in_topology_signature():
    """ADR/0038 A2: distance is a VALUE, not skeleton — two chamfers differing
    only in distance share a signature; the chamfer IS a topology change vs box."""
    a = _box_with_chamfer_recipe(distance=2.0)
    b = _box_with_chamfer_recipe(distance=3.0)
    assert topology.compute_topology_signature(a) == topology.compute_topology_signature(b)
    assert topology.compute_topology_signature(a) != topology.compute_topology_signature(a[:2])


def test_stale_reference_fails_loud_on_topology_change():
    feats = _box_with_chamfer_recipe()
    feats[0]["adapter_payload"]["primitives"].append(
        {"id": "skp_0002", "type": "circle", "cx_mm": 6.0, "cy_mm": 4.0, "radius_mm": 1.0})
    with pytest.raises(TransactionError, match="STALE"):
        geometry.evaluate_part(feats)
