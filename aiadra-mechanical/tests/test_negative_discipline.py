"""Negative-discipline tests — force the engine-boundary discipline to fire on
REAL `mechanical` handler emissions (ADR/0031 D12; adapted from Wedge-003).

Covers cascade rejection (ADR/0029 D12), provenance cross-Object-address
rejection (ADR/0029 D6), canonical-unit enforcement (ADR/0029 D10), and the B6
binding-scan integration test (ADR/0030 D9) against the UNRELEASED current
revision.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from aiadra_core.protocol import propose
from aiadra_core.transaction.boundary import TransactionDraft
from aiadra_core.truth_model.reservation import find_reservation_entry_by_number
from aiadra_core.truth_model.sidecar import load_sidecar
from aiadra_core.validation.binding import RevisionBindingError
from aiadra_core.validation.bundle_registry import BundleRegistry, SchemaValidationError
from aiadra_core.validation.fold import FoldInconsistencyError
from aiadra_core.vault.local_fs import LocalFSVaultAdapter

from conftest import part_sidecar


# ---- cascade ----

def test_cascade_rejects_remove_with_dependent_feature(workspace_with_extrude: Path):
    draft = propose(workspace_with_extrude, kind="mechanical.remove_feature", params={
        "part_number": "P-000001", "feature_ids": ["feat_0001"]})
    with pytest.raises(FoldInconsistencyError, match="depends_on_feature_ids"):
        draft.validate()


def test_cascade_accepts_batched_dependent_remove(workspace_with_extrude: Path):
    sc = part_sidecar(workspace_with_extrude)
    geom_ids = [g["id"] for g in sc["geometry_ref"]]
    propose(workspace_with_extrude, kind="mechanical.remove_feature", params={
        "part_number": "P-000001", "feature_ids": ["feat_0001", "feat_0002"],
        "geometry_ref_ids": geom_ids}).commit()
    sc_after = part_sidecar(workspace_with_extrude)
    assert sc_after.get("feature", []) == []
    assert sc_after.get("geometry_ref", []) == []


# ---- provenance + units (synthetic events through the low-level draft API) ----

def _bundle_and_part(ws: Path):
    bundle = BundleRegistry().bundle_for_pin(ws)
    _, entry = find_reservation_entry_by_number(ws, "P-000001")
    return bundle, entry["object_uuid"], load_sidecar(ws, entry["object_uuid"])


def test_provenance_blocks_cross_object_address_form(workspace_with_extrude: Path):
    ws = workspace_with_extrude
    bundle, part_uuid, sc = _bundle_and_part(ws)
    bad_geom = {
        "id": "geom_9999", "role": "authoring_geometry",
        "vault_ref": "sha256:" + "a" * 64,
        "derived_from_feature_ids": ["feat_0001"],
        "fact_provenance": {"category": "computed_result",
                            "derived_from": [f"{part_uuid}:feature:feat_0001"]},
    }
    draft = TransactionDraft(workspace=ws, bundle=bundle,
                             kind="mechanical.synthetic", transaction_id="tx_9999")
    bad_sc = copy.deepcopy(sc)
    bad_sc.setdefault("geometry_ref", []).append(copy.deepcopy(bad_geom))
    draft.stage_sidecar(part_uuid, bad_sc)
    draft.stage_event({
        "schema_version": bundle.bundle_version, "event_id": "evt_9999",
        "event_type": "part_changed", "timestamp": "2026-06-02T19:00:00Z",
        "transaction_id": "tx_9999", "actor": "agent",
        "payload": {"object_uuid": part_uuid, "geometry_ref_delta": {"added": [bad_geom]}}})
    with pytest.raises(FoldInconsistencyError, match="canonical"):
        draft.validate()


def test_canonical_unit_enforced_on_feature_parameters(workspace_with_extrude: Path):
    ws = workspace_with_extrude
    bundle, part_uuid, sc = _bundle_and_part(ws)
    bad_feature = {
        "id": "feat_9999", "name": "bad_unit", "feature_type": "extrude",
        "engine": "mechanical", "adapter_schema_version": "0.1.0",
        "adapter_payload": {"sketch_feature_id": "feat_0001", "direction": "z+",
                            "depth_parameter_id": "featp_9999"},
        "parameters": [{"id": "featp_9999", "name": "depth_inches", "value": 1.0,
                        "datatype": "number", "unit": "inches"}],
        "fact_provenance": {"category": "ai_proposal"},
    }
    draft = TransactionDraft(workspace=ws, bundle=bundle,
                             kind="mechanical.synthetic", transaction_id="tx_9999")
    bad_sc = copy.deepcopy(sc)
    bad_sc.setdefault("feature", []).append(copy.deepcopy(bad_feature))
    draft.stage_sidecar(part_uuid, bad_sc)
    draft.stage_event({
        "schema_version": bundle.bundle_version, "event_id": "evt_9999",
        "event_type": "part_changed", "timestamp": "2026-06-02T19:00:00Z",
        "transaction_id": "tx_9999", "actor": "agent",
        "payload": {"object_uuid": part_uuid, "feature_delta": {"added": [bad_feature]}}})
    with pytest.raises(SchemaValidationError):
        draft.validate()


# ---- B6 binding scan against UNRELEASED current revision ----

def _seed_attachment(ws: Path, payload: bytes, att_id: str, *,
                     role: str = "source_authoring", media_type: str = "application/octet-stream") -> dict:
    vault = LocalFSVaultAdapter(ws)
    content_hash, vault_path = vault.store(payload)
    return {"id": att_id, "role": role, "content_hash": content_hash,
            "vault_path": vault_path, "media_type": media_type}


def _setup_procedure_and_execution(ws: Path) -> None:
    propose(ws, kind="create_test_procedure", params={
        "number": "TST-000001", "name": "ExtrudeDimensionCheck",
        "extra_namespaces": {
            "test_procedure": {"title": "Extrude dim check", "verification_method": "test"},
            "attachment": [_seed_attachment(ws, b"PROCEDURE seed", "att_tst_seed", media_type="application/pdf")],
        }}).commit()
    propose(ws, kind="create_test_execution", params={
        "number": "TEX-000001", "name": "ExtrudeDimensionRun",
        "extra_namespaces": {
            "test_execution": {"executed_on_date": "2026-06-02", "execution_status": "completed"},
            "attachment": [_seed_attachment(ws, b"INSTRON LOG seed", "att_tex_seed", media_type="text/csv")],
            "parameter": [{"id": "param_measured", "name": "measured_depth_mm", "datatype": "number",
                           "unit": "mm", "value": 5.0,
                           "fact_provenance": {"category": "measured", "derived_from": ["attachment:att_tex_seed"]}}],
        }}).commit()


def test_b6_binding_scan_catches_mechanical_mutation_against_unreleased_bound_revision(
    workspace_with_extrude: Path,
):
    ws = workspace_with_extrude
    _setup_procedure_and_execution(ws)
    propose(ws, kind="link_executed_on", params={
        "source_number": "TEX-000001", "target_number": "P-000001"}).commit()
    draft = propose(ws, kind="mechanical.adjust_feature_parameter", params={
        "part_number": "P-000001", "feature_id": "feat_0002",
        "parameter_name": "depth_mm", "new_value": 9.0})
    with pytest.raises(RevisionBindingError):
        draft.validate()
