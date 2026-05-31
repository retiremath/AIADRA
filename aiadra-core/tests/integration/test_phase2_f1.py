"""Phase 2 F1 SCN tests — extend `parameter_changed` event with optional
`new_fact_provenance`; bundle v0.20.0 → v0.21.0.

Per ADR/0025 §4 + arc 20260531-3 Claude1+Codex1 absorptions.
"""
from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from aiadra_core.cli.validate import run_validate
from aiadra_core.transaction.operations import (
    change_parameter,
    create_object,
    init_workspace,
)
from aiadra_core.truth_model.reservation import find_reservation_entry_by_number
from aiadra_core.truth_model.sidecar import load_sidecar
from aiadra_core.validation.bundle_registry import BundleRegistry
from aiadra_core.validation.fold import (
    FoldInconsistencyError,
    _apply_attachment_delta,  # noqa: F401 (re-exported for clarity)
    fold_events_to_state,
)
from aiadra_core.validation.migration import (
    MigrationError,
    apply_migration_v0_20_0_to_v0_21_0,
    plan_migration_v0_20_0_to_v0_21_0,
)


def _bundle_v0_21_0():
    return BundleRegistry().bundle("0.21.0")


# ---------- 1. Schema acceptance/rejection ----------


def test_phase2_f1_schema_accepts_event_with_new_fact_provenance():
    """v0.21.0 parameter_changed accepts events with optional new_fact_provenance."""
    b = _bundle_v0_21_0()
    event = {
        "schema_version": "0.21.0",
        "event_id": "evt_0001",
        "event_type": "parameter_changed",
        "timestamp": "2026-05-31T12:00:00Z",
        "transaction_id": "tx_0001",
        "payload": {
            "object_uuid": "0193abcd-1234-7890-abcd-111111111111",
            "parameter_id": "param_x",
            "old_value": 5.0,
            "new_value": 7.0,
            "rationale": "AI proposed update",
            "new_fact_provenance": {
                "category": "ai_proposal",
                "ai_agent_ref": "claude-opus-4-7",
                "derived_from": ["evt_external_ref"],
            },
        },
    }
    b.validate(event, "event", "parameter_changed")  # no raise


def test_phase2_f1_schema_accepts_event_without_new_fact_provenance():
    """v0.21.0 parameter_changed accepts events that omit new_fact_provenance
    (backward-compat with v0.20.0-shaped events)."""
    b = _bundle_v0_21_0()
    event = {
        "schema_version": "0.21.0",
        "event_id": "evt_0001",
        "event_type": "parameter_changed",
        "timestamp": "2026-05-31T12:00:00Z",
        "transaction_id": "tx_0001",
        "payload": {
            "object_uuid": "0193abcd-1234-7890-abcd-111111111111",
            "parameter_id": "param_x",
            "old_value": 5.0,
            "new_value": 7.0,
            "rationale": "human update",
        },
    }
    b.validate(event, "event", "parameter_changed")  # no raise


def test_phase2_f1_schema_rejects_new_fact_provenance_without_category():
    """new_fact_provenance dict MUST carry `category`; agent + derived_from
    optional. Per Codex Q5 — add category-required negative test."""
    from aiadra_core.validation.bundle_registry import SchemaValidationError
    b = _bundle_v0_21_0()
    event = {
        "schema_version": "0.21.0",
        "event_id": "evt_0001",
        "event_type": "parameter_changed",
        "timestamp": "2026-05-31T12:00:00Z",
        "transaction_id": "tx_0001",
        "payload": {
            "object_uuid": "0193abcd-1234-7890-abcd-111111111111",
            "parameter_id": "param_x",
            "old_value": 5.0,
            "new_value": 7.0,
            "rationale": "missing category",
            "new_fact_provenance": {"ai_agent_ref": "claude-opus-4-7"},  # NO category
        },
    }
    with pytest.raises(SchemaValidationError, match="category"):
        b.validate(event, "event", "parameter_changed")


# ---------- 2. End-to-end Transaction with provenance ----------


def test_phase2_f1_change_parameter_with_provenance_applies_wholesale(tmp_path: Path):
    """End-to-end: change-parameter with new_fact_provenance updates BOTH
    event payload AND working sidecar's fact_provenance wholesale; fold replay
    reconstructs same state; aiadra validate exits 0."""
    workspace = tmp_path / "ws"
    bundle = _bundle_v0_21_0()
    init_workspace(workspace, bundle).validate()
    init_workspace(workspace, bundle).commit()
    # Re-init with v0.21.0 pin (init_workspace already does this with latest)
    # Create Part with a parameter carrying human_input provenance
    d_p = create_object(
        workspace, bundle, "Part", "P-000001", "Bracket",
        extra_namespaces={
            "parameter": [{
                "id": "param_thickness", "name": "plate_thickness_mm",
                "datatype": "number", "unit": "mm", "value": 5,
                "fact_provenance": {"category": "human_input"},
            }],
        },
    )
    d_p.validate(); d_p.commit()
    # Change parameter with AI provenance
    d_cp = change_parameter(
        workspace, bundle, "P-000001", "param_thickness", 7.0,
        "AI-proposed thicker bracket for higher load",
        new_fact_provenance={
            "category": "ai_proposal",
            "ai_agent_ref": "claude-opus-4-7",
        },
    )
    d_cp.validate(); d_cp.commit()
    # Sidecar fact_provenance must be wholesale-replaced
    _, entry = find_reservation_entry_by_number(workspace, "P-000001")
    sidecar = load_sidecar(workspace, entry["object_uuid"])
    fp = [p for p in sidecar["parameter"] if p["id"] == "param_thickness"][0]["fact_provenance"]
    assert fp["category"] == "ai_proposal"
    assert fp["ai_agent_ref"] == "claude-opus-4-7"
    # Event payload must carry new_fact_provenance
    assert any(
        e["event_type"] == "parameter_changed"
        and e["payload"].get("new_fact_provenance", {}).get("category") == "ai_proposal"
        for e in d_cp.events
    )
    # Validate passes
    rc = run_validate(workspace)
    assert rc == 0


def test_phase2_f1_change_parameter_without_provenance_unchanged(tmp_path: Path):
    """End-to-end: change-parameter WITHOUT new_fact_provenance leaves the
    parameter's fact_provenance dict UNCHANGED (Phase 1 backward-compat)."""
    workspace = tmp_path / "ws"
    bundle = _bundle_v0_21_0()
    init_workspace(workspace, bundle).commit()
    d_p = create_object(
        workspace, bundle, "Part", "P-000001", "Bracket",
        extra_namespaces={
            "parameter": [{
                "id": "param_thickness", "name": "plate_thickness_mm",
                "datatype": "number", "unit": "mm", "value": 5,
                "fact_provenance": {"category": "human_input"},
            }],
        },
    )
    d_p.validate(); d_p.commit()
    # No provenance flag
    d_cp = change_parameter(
        workspace, bundle, "P-000001", "param_thickness", 7.0,
        "thicken bracket",
    )
    d_cp.validate(); d_cp.commit()
    _, entry = find_reservation_entry_by_number(workspace, "P-000001")
    sidecar = load_sidecar(workspace, entry["object_uuid"])
    fp = [p for p in sidecar["parameter"] if p["id"] == "param_thickness"][0]["fact_provenance"]
    # fact_provenance unchanged
    assert fp == {"category": "human_input"}
    # Event payload must NOT carry new_fact_provenance
    assert all(
        "new_fact_provenance" not in e["payload"]
        for e in d_cp.events if e["event_type"] == "parameter_changed"
    )
    # Validate passes
    rc = run_validate(workspace)
    assert rc == 0


# ---------- 3. CLI category-required negative ----------


def test_phase2_f1_cli_category_required_when_other_provenance_flag_present(tmp_path: Path):
    """Per Codex Q5: if any --provenance-* flag is present,
    --provenance-category is REQUIRED. Without it, exit 2 with clear error."""
    workspace = tmp_path / "ws"
    bundle = _bundle_v0_21_0()
    init_workspace(workspace, bundle).commit()
    d_p = create_object(
        workspace, bundle, "Part", "P-000001", "Bracket",
        extra_namespaces={
            "parameter": [{
                "id": "param_thickness", "name": "plate_thickness_mm",
                "datatype": "number", "unit": "mm", "value": 5,
                "fact_provenance": {"category": "human_input"},
            }],
        },
    )
    d_p.validate(); d_p.commit()

    # Invoke CLI without --provenance-category but WITH --provenance-agent
    result = subprocess.run(
        [sys.executable, "-m", "aiadra_core.cli",
         "change-parameter", str(workspace), "P-000001", "param_thickness", "7.0",
         "test rationale",
         "--provenance-agent", "claude-opus-4-7"],
        capture_output=True, text=True,
    )
    assert result.returncode == 2, f"expected exit 2; got {result.returncode}; stderr={result.stderr}"
    assert "provenance-category" in result.stderr.lower()


# ---------- 4. Migrator v0.20.0 → v0.21.0 ----------


def test_phase2_f1_migrator_v0_20_0_to_v0_21_0_idempotent_and_dry_run(tmp_path: Path):
    """Migrator updates project pin from v0.20.0 → v0.21.0; idempotent;
    dry-run plan matches applied plan."""
    # Set up a v0.20.0-pinned workspace manually
    workspace = tmp_path / "ws"
    (workspace / ".aiadra").mkdir(parents=True)
    reg = BundleRegistry()
    v20 = reg.bundle("0.20.0")
    pin_text = f'"bundle_version": "0.20.0"\n"bundle_digest": "{v20.bundle_digest}"\n'
    (workspace / ".aiadra" / "schemas.yaml").write_bytes(pin_text.encode("utf-8"))

    # Dry-run plan
    plan = plan_migration_v0_20_0_to_v0_21_0(workspace, reg)
    assert plan.from_bundle_version == "0.20.0"
    assert plan.to_bundle_version == "0.21.0"
    assert plan.pin_will_change is True
    # Plan didn't change anything yet
    pin_after_plan = (workspace / ".aiadra" / "schemas.yaml").read_bytes()
    assert b"0.20.0" in pin_after_plan and b"0.21.0" not in pin_after_plan

    # Apply
    applied = apply_migration_v0_20_0_to_v0_21_0(workspace, reg)
    assert applied.to_bundle_version == "0.21.0"
    pin_after_apply = (workspace / ".aiadra" / "schemas.yaml").read_text(encoding="utf-8")
    assert '"bundle_version": "0.21.0"' in pin_after_apply
    v21 = reg.bundle("0.21.0")
    assert v21.bundle_digest in pin_after_apply

    # Idempotent: re-apply on v0.21.0 → no-op plan
    reapply = apply_migration_v0_20_0_to_v0_21_0(workspace, reg)
    assert reapply.from_bundle_version == "0.21.0"
    assert reapply.to_bundle_version == "0.21.0"
    assert reapply.pin_will_change is False

    # Rejects non-v0.20.0 pin
    other = tmp_path / "ws2"
    (other / ".aiadra").mkdir(parents=True)
    (other / ".aiadra" / "schemas.yaml").write_bytes(
        b'"bundle_version": "0.19.0"\n"bundle_digest": "sha256:00"\n'
    )
    with pytest.raises(MigrationError):
        plan_migration_v0_20_0_to_v0_21_0(other, reg)
