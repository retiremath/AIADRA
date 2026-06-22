"""5-step authoring loop (Mode A + Mode B) + schema-conformance, against a real
OCCT kernel. Adapts the proven Wedge-003 surface (ADR/0031 D12) to the
production `mechanical` engine.
"""
from __future__ import annotations

from pathlib import Path

from aiadra_core.protocol import modify, modify_kinds, native_engine_status, propose, propose_kinds

from conftest import part_sidecar, two_primitives

_OPS = {
    "mechanical.add_sketch_feature",
    "mechanical.add_extrude_feature",
    "mechanical.add_fillet_feature",
    "mechanical.add_hole_feature",
    "mechanical.adjust_feature_parameter",
    "mechanical.remove_feature",
}


def test_discovered_via_entry_point():
    status = native_engine_status()
    assert status["mechanical"]["status"] == "loaded"
    assert status["mechanical"]["error"] is None
    assert set(status["mechanical"]["operations"]) == _OPS


def test_propose_and_modify_kinds_include_mechanical_ops():
    pk = set(propose_kinds())
    assert "create_part" in pk and _OPS <= pk
    mk = set(modify_kinds())
    assert "init" not in mk and "release" not in mk
    assert _OPS <= mk


def test_5_step_loop_mode_a(workspace_with_part: Path):
    ws = workspace_with_part
    propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001", "primitives": two_primitives()}).commit()
    propose(ws, kind="mechanical.add_extrude_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001",
        "depth_mm": 5.0, "direction": "z+"}).commit()
    propose(ws, kind="mechanical.adjust_feature_parameter", params={
        "part_number": "P-000001", "feature_id": "feat_0002",
        "parameter_name": "depth_mm", "new_value": 8.0}).commit()
    result = propose(ws, kind="release", params={
        "object_numbers": ["P-000001"], "final_stage": True}).commit()
    assert result is not None

    sc = part_sidecar(ws)
    assert sorted(f["feature_type"] for f in sc["feature"]) == ["extrude", "sketch"]
    assert len(sc["geometry_ref"]) == 1
    extrude = [f for f in sc["feature"] if f["feature_type"] == "extrude"][0]
    assert extrude["parameters"][0]["value"] == 8.0


def test_5_step_loop_mode_b_composed_via_modify(workspace_with_part: Path):
    ws = workspace_with_part
    draft = propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001", "primitives": two_primitives()})
    modify(draft, kind="mechanical.add_extrude_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001",
        "depth_mm": 5.0, "direction": "z+"})
    modify(draft, kind="mechanical.adjust_feature_parameter", params={
        "part_number": "P-000001", "feature_id": "feat_0002",
        "parameter_name": "depth_mm", "new_value": 8.0})
    draft.commit()

    sc = part_sidecar(ws)
    assert len(sc["feature"]) == 2
    assert len(sc["geometry_ref"]) == 1


def test_mode_b_event_ids_distinct(workspace_with_part: Path):
    ws = workspace_with_part
    draft = propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001", "primitives": two_primitives()})
    modify(draft, kind="mechanical.add_extrude_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001",
        "depth_mm": 5.0, "direction": "z+"})
    modify(draft, kind="mechanical.adjust_feature_parameter", params={
        "part_number": "P-000001", "feature_id": "feat_0002",
        "parameter_name": "depth_mm", "new_value": 8.0})
    ids = [e["event_id"] for e in draft.events if e.get("event_type") == "part_changed"]
    assert len(ids) == 3 and len(set(ids)) == 3


def test_part_changed_envelope_and_namespaces(workspace_with_part: Path):
    ws = workspace_with_part
    draft = propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001", "primitives": two_primitives()})
    ev = [e for e in draft.events if e.get("event_type") == "part_changed"][0]
    assert ev["actor"] == "agent"
    assert "timestamp" in ev and "transaction_id" in ev and "payload" in ev
    assert ev["payload"]["object_uuid"]
    draft.commit()
    sc = part_sidecar(ws)
    assert "feature" in sc and "geometry_ref" in sc
    assert "feature:" not in sc and "geometry_ref:" not in sc


def test_feature_dag_and_provenance_set_equality(workspace_with_extrude: Path):
    sc = part_sidecar(workspace_with_extrude)
    extrude = [f for f in sc["feature"] if f["feature_type"] == "extrude"][0]
    assert extrude["depends_on_feature_ids"] == ["feat_0001"]
    geom = sc["geometry_ref"][0]
    assert geom["role"] == "authoring_geometry"
    declared = set(geom["derived_from_feature_ids"])
    attested = {s.split(":", 1)[1] for s in geom["fact_provenance"]["derived_from"] if s.startswith("feature:")}
    assert declared == attested


def test_extrude_depth_is_canonical_unit_parameter(workspace_with_extrude: Path):
    sc = part_sidecar(workspace_with_extrude)
    extrude = [f for f in sc["feature"] if f["feature_type"] == "extrude"][0]
    p = extrude["parameters"][0]
    assert p["name"] == "depth_mm" and p["value"] == 5.0
    assert p["datatype"] == "number" and p["unit"] == "mm"
    assert p["id"].startswith("featp_")


def test_adjust_changes_parameter_value_and_geometry_hash(workspace_with_extrude: Path):
    ws = workspace_with_extrude
    before = part_sidecar(ws)["geometry_ref"][0]["vault_ref"]
    propose(ws, kind="mechanical.adjust_feature_parameter", params={
        "part_number": "P-000001", "feature_id": "feat_0002",
        "parameter_name": "depth_mm", "new_value": 8.0}).commit()
    after = part_sidecar(ws)["geometry_ref"][0]["vault_ref"]
    assert before != after


def test_geometry_ref_omits_kind_and_addresses_recipe_bytes(workspace_with_extrude: Path):
    """ADR/0031 D6/B1: vault_ref addresses canonical RECIPE bytes; `kind` omitted."""
    sc = part_sidecar(workspace_with_extrude)
    geom = sc["geometry_ref"][0]
    assert "kind" not in geom
    assert geom["vault_ref"].startswith("sha256:")


def test_release_with_features_and_geometry_refs(workspace_with_extrude: Path):
    ws = workspace_with_extrude
    from aiadra_core.truth_model.reservation import find_reservation_entry_by_number
    propose(ws, kind="release", params={"object_numbers": ["P-000001"], "final_stage": True}).commit()
    _, entry = find_reservation_entry_by_number(ws, "P-000001")
    assert len(entry.get("released_revision_ids", [])) >= 1
