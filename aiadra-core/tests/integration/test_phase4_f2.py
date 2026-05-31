"""Phase 4 F2 SCN tests — `threshold_expression` canonical primitive on
Requirement `acceptance_criterion`; bundle v0.22.0 → v0.23.0.

Per ADR/0025 §5 + arc 20260531-5 Claude1+Codex1 absorptions:
- B1 absorption: requirement_changed event is added-only (no updated/removed
  in v0.23.0). Both fold paths reject duplicate criterion ids.
- N1 absorption: claim walk evaluates by `endpoints[0].object_uuid` against
  the current released Revision per object UUID; Fixed-binding stale-pin
  semantics carry an explicit TODO/comment for a future SCN.
- N2 absorption: event `added` records reference the FULL canonical
  `_shared/acceptance_criterion_item.schema.json` schema.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from aiadra_core.cli.validate import run_validate
from aiadra_core.transaction.operations import (
    add_acceptance_criterion,
    create_object,
    init_workspace,
    link_relationship,
    release,
)
from aiadra_core.truth_model.reservation import find_reservation_entry_by_number
from aiadra_core.truth_model.sidecar import load_sidecar
from aiadra_core.validation.bundle_registry import (
    BundleRegistry,
    SchemaValidationError,
)
from aiadra_core.validation.fold import (
    FoldInconsistencyError,
    fold_events_to_state,
)
from aiadra_core.validation.migration import (
    REGISTERED_STEPS,
    apply_migration,
    plan_migration,
)
from aiadra_core.validation.release import ReleaseConsistencyError


def _bundle_v0_23_0():
    return BundleRegistry().bundle("0.23.0")


# ---------- 1. Schema accept / reject ----------


def test_phase4_f2_schema_accepts_criterion_with_threshold_expression():
    """v0.23.0 Requirement accepts a criterion carrying full threshold_expression."""
    b = _bundle_v0_23_0()
    sidecar = _minimal_requirement_sidecar(extra_criteria=[{
        "id": "ac_min_thickness",
        "criterion": {
            "text": "plate_thickness_mm >= 5",
            "language": "en",
            "format": "freeform",
        },
        "threshold_expression": {
            "parameter_ref": "01934567-89ab-7def-8123-456789abcdef:parameter:param_thickness",
            "comparison_op": ">=",
            "value": 5.0,
            "unit": "mm",
        },
    }])
    b.validate(sidecar, "sidecar", "Requirement")


def test_phase4_f2_schema_accepts_criterion_without_threshold_expression():
    """Backward-compat: v0.22.0-shaped criteria validate against v0.23.0."""
    b = _bundle_v0_23_0()
    sidecar = _minimal_requirement_sidecar()  # default criterion has no threshold
    b.validate(sidecar, "sidecar", "Requirement")


def test_phase4_f2_schema_rejects_threshold_expression_missing_unit():
    """`unit` is required INSIDE the threshold_expression dict when present."""
    b = _bundle_v0_23_0()
    sidecar = _minimal_requirement_sidecar(extra_criteria=[{
        "id": "ac_x",
        "criterion": {"text": "x", "language": "en", "format": "freeform"},
        "threshold_expression": {
            "parameter_ref": "01934567-89ab-7def-8123-456789abcdef:parameter:param_x",
            "comparison_op": ">=",
            "value": 5.0,
            # NO unit
        },
    }])
    with pytest.raises(SchemaValidationError, match="unit"):
        b.validate(sidecar, "sidecar", "Requirement")


def test_phase4_f2_schema_rejects_threshold_expression_unknown_comparison_op():
    b = _bundle_v0_23_0()
    sidecar = _minimal_requirement_sidecar(extra_criteria=[{
        "id": "ac_x",
        "criterion": {"text": "x", "language": "en", "format": "freeform"},
        "threshold_expression": {
            "parameter_ref": "01934567-89ab-7def-8123-456789abcdef:parameter:param_x",
            "comparison_op": "approx",  # not in enum
            "value": 5.0,
            "unit": "mm",
        },
    }])
    with pytest.raises(SchemaValidationError, match="comparison_op"):
        b.validate(sidecar, "sidecar", "Requirement")


def test_phase4_f2_schema_rejects_threshold_expression_non_numeric_value():
    b = _bundle_v0_23_0()
    sidecar = _minimal_requirement_sidecar(extra_criteria=[{
        "id": "ac_x",
        "criterion": {"text": "x", "language": "en", "format": "freeform"},
        "threshold_expression": {
            "parameter_ref": "01934567-89ab-7def-8123-456789abcdef:parameter:param_x",
            "comparison_op": ">=",
            "value": "five",  # not a number
            "unit": "mm",
        },
    }])
    with pytest.raises(SchemaValidationError, match="value"):
        b.validate(sidecar, "sidecar", "Requirement")


def test_phase4_f2_schema_rejects_threshold_expression_malformed_parameter_ref():
    b = _bundle_v0_23_0()
    sidecar = _minimal_requirement_sidecar(extra_criteria=[{
        "id": "ac_x",
        "criterion": {"text": "x", "language": "en", "format": "freeform"},
        "threshold_expression": {
            "parameter_ref": "not-a-uuid:wrong:format",
            "comparison_op": ">=",
            "value": 5.0,
            "unit": "mm",
        },
    }])
    with pytest.raises(SchemaValidationError, match="parameter_ref"):
        b.validate(sidecar, "sidecar", "Requirement")


def test_phase4_f2_event_requirement_changed_rejects_updated_or_removed():
    """Per Codex1 B1 absorption: v0.23.0 requirement_changed is added-only.
    Both 'updated' and 'removed' delta keys are schema-rejected."""
    b = _bundle_v0_23_0()
    event_with_updated = {
        "schema_version": "0.23.0",
        "event_id": "evt_0001",
        "event_type": "requirement_changed",
        "timestamp": "2026-05-31T14:00:00Z",
        "transaction_id": "tx_0001",
        "payload": {
            "object_uuid": "01934567-89ab-7def-8123-456789abcdef",
            "acceptance_criterion_delta": {
                "added": [],  # required even if also passing updated
                "updated": [{"id": "ac_x"}],
            },
        },
    }
    with pytest.raises(SchemaValidationError):
        b.validate(event_with_updated, "event", "requirement_changed")


# ---------- 2. End-to-end Transaction ----------


def test_phase4_f2_add_acceptance_criterion_without_threshold_applies(tmp_path: Path):
    """Append criterion without threshold; sidecar carries new criterion; event
    payload carries acceptance_criterion_delta.added; fold reconstructs."""
    workspace = tmp_path / "ws"
    bundle = _bundle_v0_23_0()
    init_workspace(workspace, bundle).commit()
    # Seed a Requirement with one existing criterion
    _make_requirement(workspace, bundle, "REQ-000001")

    draft = add_acceptance_criterion(
        workspace, bundle, "REQ-000001", "ac_extra",
        "extra criterion",
    )
    draft.validate(); draft.commit()

    _, entry = find_reservation_entry_by_number(workspace, "REQ-000001")
    sidecar = load_sidecar(workspace, entry["object_uuid"])
    ids = [c["id"] for c in sidecar["acceptance_criterion"]]
    assert "ac_extra" in ids

    # Event payload carries the delta
    assert any(
        e["event_type"] == "requirement_changed"
        and any(c["id"] == "ac_extra"
                for c in e["payload"]["acceptance_criterion_delta"]["added"])
        for e in draft.events
    )

    # Validate workspace end-to-end (fold + schema)
    rc = run_validate(workspace)
    assert rc == 0, f"validate rc={rc}"


def test_phase4_f2_add_acceptance_criterion_with_threshold_applies(tmp_path: Path):
    """End-to-end with threshold_expression; sidecar + event carry the dict."""
    workspace = tmp_path / "ws"
    bundle = _bundle_v0_23_0()
    init_workspace(workspace, bundle).commit()
    part_uuid = _make_part(workspace, bundle, "P-000001", thickness=7.0)
    _make_requirement(workspace, bundle, "REQ-000001")

    draft = add_acceptance_criterion(
        workspace, bundle, "REQ-000001", "ac_min_thickness",
        "plate thickness >= 5",
        threshold_expression={
            "parameter_ref": f"{part_uuid}:parameter:param_thickness",
            "comparison_op": ">=",
            "value": 5.0,
            "unit": "mm",
        },
    )
    draft.validate(); draft.commit()

    _, entry = find_reservation_entry_by_number(workspace, "REQ-000001")
    sidecar = load_sidecar(workspace, entry["object_uuid"])
    ac = [c for c in sidecar["acceptance_criterion"] if c["id"] == "ac_min_thickness"][0]
    assert ac["threshold_expression"]["unit"] == "mm"
    assert ac["threshold_expression"]["value"] == 5.0

    rc = run_validate(workspace)
    assert rc == 0


def test_phase4_f2_add_acceptance_criterion_duplicate_id_rejected(tmp_path: Path):
    """Duplicate criterion id fails at Transaction-build time (cheap check)."""
    workspace = tmp_path / "ws"
    bundle = _bundle_v0_23_0()
    init_workspace(workspace, bundle).commit()
    _make_requirement(workspace, bundle, "REQ-000001")  # seeds ac_seed

    from aiadra_core.transaction.operations import TransactionError as _TxErr
    with pytest.raises(_TxErr, match="already exists"):
        add_acceptance_criterion(
            workspace, bundle, "REQ-000001", "ac_seed", "duplicate",
        )


# ---------- 3. Release threshold semantics ----------


def test_phase4_f2_release_threshold_pass_emits_pass_outcome(tmp_path: Path):
    """Release with PASS threshold → manifest carries threshold_check(...) PASS."""
    workspace, draft_rel = _setup_release_scenario(
        tmp_path, thickness=7.0, claim_kind=None,
    )
    outcomes = draft_rel.validate()
    result = draft_rel.commit()
    assert result.commit_hash

    # Manifest carries the PASS outcome
    manifest = _load_release_manifest(workspace, "rev-A")
    threshold_outcomes = [
        o for o in manifest["validation_outcomes"]
        if o["check_name"].startswith("threshold_check(")
    ]
    assert len(threshold_outcomes) == 1
    assert threshold_outcomes[0]["result"] == "PASS"


def test_phase4_f2_release_threshold_fail_no_claim_emits_fail_outcome(tmp_path: Path):
    """FAIL threshold, no satisfies/verifies claim → manifest FAIL diagnostic;
    release succeeds (not hard-fail)."""
    workspace, draft_rel = _setup_release_scenario(
        tmp_path, thickness=3.0, claim_kind=None,
    )
    draft_rel.validate()
    result = draft_rel.commit()
    assert result.commit_hash

    manifest = _load_release_manifest(workspace, "rev-A")
    threshold_outcomes = [
        o for o in manifest["validation_outcomes"]
        if o["check_name"].startswith("threshold_check(")
    ]
    assert len(threshold_outcomes) == 1
    assert threshold_outcomes[0]["result"] == "FAIL"


def test_phase4_f2_release_threshold_fail_with_satisfies_claim_hard_fails(tmp_path: Path):
    """FAIL threshold AND satisfies claiming the Requirement → hard-fail.

    NOTE: validate_final_stage_threshold_checks runs INSIDE the release()
    constructor (to populate validation_outcomes before manifest hash sealing),
    so the ReleaseConsistencyError raises at release() build-time, not at
    draft.validate().
    """
    with pytest.raises(ReleaseConsistencyError, match="threshold_check FAIL"):
        _setup_release_scenario(tmp_path, thickness=3.0, claim_kind="satisfies")


def test_phase4_f2_release_threshold_fail_with_verifies_criterion_claim_hard_fails(tmp_path: Path):
    """FAIL threshold AND verifies with `fact_ref: acceptance_criterion:<ac_id>` → hard-fail."""
    with pytest.raises(ReleaseConsistencyError, match="threshold_check FAIL"):
        _setup_release_scenario(tmp_path, thickness=3.0, claim_kind="verifies_criterion")


def test_phase4_f2_release_threshold_fail_with_verifies_whole_req_claim_hard_fails(tmp_path: Path):
    """FAIL threshold AND verifies WITHOUT fact_ref (whole-Requirement) → hard-fail."""
    with pytest.raises(ReleaseConsistencyError, match="threshold_check FAIL"):
        _setup_release_scenario(tmp_path, thickness=3.0, claim_kind="verifies_whole")


def test_phase4_f2_release_threshold_unit_mismatch_hard_fails(tmp_path: Path):
    """Layer-2 unit-mismatch hard-fail regardless of claim."""
    with pytest.raises(ReleaseConsistencyError, match="unit mismatch"):
        _setup_release_scenario(
            tmp_path, thickness=7.0, claim_kind=None, threshold_unit="inch",
        )


def test_phase4_f2_release_threshold_parameter_ref_outside_graph_fail_outcome(tmp_path: Path):
    """parameter_ref outside cumulative release graph → FAIL outcome (not hard-fail)."""
    workspace, draft_rel = _setup_release_scenario(
        tmp_path, thickness=7.0, claim_kind=None,
        threshold_parameter_ref="00000000-0000-0000-0000-000000000000:parameter:param_missing",
    )
    draft_rel.validate()  # should NOT raise
    result = draft_rel.commit()
    assert result.commit_hash
    manifest = _load_release_manifest(workspace, "rev-A")
    threshold_outcomes = [
        o for o in manifest["validation_outcomes"]
        if o["check_name"].startswith("threshold_check(")
    ]
    assert len(threshold_outcomes) == 1
    assert threshold_outcomes[0]["result"] == "FAIL"
    assert "not in cumulative release graph" in threshold_outcomes[0]["details"]


# ---------- 4. CLI threshold quartet gate ----------


def test_phase4_f2_cli_threshold_quartet_required_when_any_present(tmp_path: Path):
    """If any --threshold-* flag is present, the FULL quartet is REQUIRED;
    exit 2 with clear error."""
    workspace = tmp_path / "ws"
    bundle = _bundle_v0_23_0()
    init_workspace(workspace, bundle).commit()
    _make_requirement(workspace, bundle, "REQ-000001")

    # Pass --threshold-op without other three
    result = subprocess.run(
        [sys.executable, "-m", "aiadra_core.cli",
         "add-acceptance-criterion", str(workspace), "REQ-000001",
         "ac_part", "the criterion",
         "--threshold-op", ">="],
        capture_output=True, text=True,
    )
    assert result.returncode == 2, f"expected exit 2; got {result.returncode}; stderr={result.stderr}"
    msg = result.stderr.lower()
    assert "threshold" in msg and "quartet" in msg


# ---------- 5. Migrator ----------


def test_phase4_f2_migrator_v0_22_0_to_v0_23_0_via_chain(tmp_path: Path):
    """Chain-aware apply_migration(workspace, '0.23.0') updates pin from v0.22.0;
    idempotent."""
    workspace = tmp_path / "ws"
    (workspace / ".aiadra").mkdir(parents=True)
    reg = BundleRegistry()
    v22 = reg.bundle("0.22.0")
    pin_text = f'"bundle_version": "0.22.0"\n"bundle_digest": "{v22.bundle_digest}"\n'
    (workspace / ".aiadra" / "schemas.yaml").write_bytes(pin_text.encode("utf-8"))

    plan = plan_migration(workspace, "0.23.0", reg)
    assert plan.from_bundle_version == "0.22.0"
    assert plan.to_bundle_version == "0.23.0"
    assert plan.pin_will_change is True
    assert b"0.22.0" in (workspace / ".aiadra" / "schemas.yaml").read_bytes()

    applied = apply_migration(workspace, "0.23.0", reg)
    assert applied.to_bundle_version == "0.23.0"
    pin_after = (workspace / ".aiadra" / "schemas.yaml").read_text(encoding="utf-8")
    assert '"bundle_version": "0.23.0"' in pin_after

    # Idempotent
    reapply = apply_migration(workspace, "0.23.0", reg)
    assert reapply.pin_will_change is False


def test_phase4_f2_registered_steps_includes_v0_23_0():
    to_versions = [s.to_version for s in REGISTERED_STEPS]
    assert "0.23.0" in to_versions
    # Chain remains contiguous.
    for i in range(len(REGISTERED_STEPS) - 1):
        assert REGISTERED_STEPS[i + 1].from_version == REGISTERED_STEPS[i].to_version


# =============================================================================
# Fixtures
# =============================================================================


def _minimal_requirement_sidecar(*, extra_criteria: list[dict] | None = None) -> dict:
    return {
        "object": {
            "uuid": "01934567-89ab-7def-8123-456789abcdef",
            "number": "REQ-000099",
            "type": "Requirement",
            "name": "fixture requirement",
            "lifecycle": "in_work",
            "schema_version": "0.23.0",
        },
        "requirement": {
            "statement": {
                "text": "Test requirement.",
                "language": "en",
                "format": "freeform",
            },
            "category": "functional",
        },
        "acceptance_criterion": (extra_criteria or [{
            "id": "ac_seed",
            "criterion": {
                "text": "seed criterion text",
                "language": "en",
                "format": "freeform",
            },
        }]),
    }


def _make_part(workspace: Path, bundle, number: str, *, thickness: float) -> str:
    """Create a Part with `param_thickness` in mm; returns its UUID."""
    draft = create_object(
        workspace, bundle, "Part", number, "fixture part",
        extra_namespaces={
            "parameter": [{
                "id": "param_thickness",
                "name": "plate_thickness_mm",
                "datatype": "number",
                "unit": "mm",
                "value": thickness,
                "fact_provenance": {"category": "human_input"},
            }],
        },
    )
    draft.validate(); draft.commit()
    _, entry = find_reservation_entry_by_number(workspace, number)
    return entry["object_uuid"]


def _make_requirement(workspace: Path, bundle, number: str) -> str:
    """Create a Requirement with one seed criterion; returns its UUID."""
    draft = create_object(
        workspace, bundle, "Requirement", number, "fixture requirement",
        extra_namespaces={
            "requirement": {
                "statement": {
                    "text": "Fixture requirement statement.",
                    "language": "en",
                    "format": "freeform",
                },
                "category": "functional",
            },
            "acceptance_criterion": [{
                "id": "ac_seed",
                "criterion": {
                    "text": "seed criterion",
                    "language": "en",
                    "format": "freeform",
                },
            }],
        },
    )
    draft.validate(); draft.commit()
    _, entry = find_reservation_entry_by_number(workspace, number)
    return entry["object_uuid"]


def _setup_release_scenario(
    tmp_path: Path,
    *,
    thickness: float,
    claim_kind: str | None,
    threshold_unit: str = "mm",
    threshold_parameter_ref: str | None = None,
):
    """Build the standard release scenario: Part + Requirement + threshold
    criterion + optional satisfies/verifies claim. Returns (workspace, release_draft).

    claim_kind:
      None                  → no claim
      "satisfies"           → Part satisfies Requirement (whole-Requirement)
      "verifies_whole"      → TestProcedure verifies Requirement (whole)
      "verifies_criterion"  → TestProcedure verifies Requirement with fact_ref
    """
    workspace = tmp_path / "ws"
    bundle = _bundle_v0_23_0()
    init_workspace(workspace, bundle).commit()

    part_uuid = _make_part(workspace, bundle, "P-000001", thickness=thickness)
    _make_requirement(workspace, bundle, "REQ-000001")

    pref = (threshold_parameter_ref
            or f"{part_uuid}:parameter:param_thickness")

    # Add the threshold criterion to the Requirement
    draft_ac = add_acceptance_criterion(
        workspace, bundle, "REQ-000001", "ac_min_thickness",
        "plate thickness >= 5",
        threshold_expression={
            "parameter_ref": pref,
            "comparison_op": ">=",
            "value": 5.0,
            "unit": threshold_unit,
        },
    )
    draft_ac.validate(); draft_ac.commit()

    object_numbers = ["P-000001", "REQ-000001"]

    if claim_kind == "satisfies":
        d = link_relationship(workspace, bundle, "satisfies", "P-000001", "REQ-000001")
        d.validate(); d.commit()
    elif claim_kind in ("verifies_whole", "verifies_criterion"):
        # Need a TestProcedure for verifies — pre-stage Vault bytes so the
        # attachment_integrity release-time validator passes.
        from aiadra_core.vault.local_fs import LocalFSVaultAdapter
        vault = LocalFSVaultAdapter(workspace)
        content_hash, vault_path = vault.store(b"FIXTURE TEST PROCEDURE")
        tp_draft = create_object(
            workspace, bundle, "TestProcedure", "TST-000001", "fixture test proc",
            extra_namespaces={
                "test_procedure": {
                    "title": "fixture",
                    "verification_method": "test",
                },
                "attachment": [{
                    "id": "att_tst_000001_proc",
                    "role": "source_authoring",
                    "media_type": "application/pdf",
                    "vault_path": vault_path,
                    "content_hash": content_hash,
                }],
            },
        )
        tp_draft.validate(); tp_draft.commit()
        d = link_relationship(workspace, bundle, "verifies", "TST-000001", "REQ-000001")
        if claim_kind == "verifies_criterion":
            # Mutate the staged relationship record to add fact_ref before validate.
            # (link_relationship doesn't expose fact_ref directly; reach in.)
            for ev in d.events:
                if ev["event_type"] == "relationship_created":
                    rec = ev["payload"]["relationship_record"]
                    rec["endpoints"][0]["fact_ref"] = "acceptance_criterion:ac_min_thickness"
            # Also patch the staged sidecar for the source TestProcedure
            for uuid, sc in d.sidecar_writes.items():
                for r in sc.get("relationship", []):
                    if r.get("type") == "verifies":
                        r["endpoints"][0]["fact_ref"] = "acceptance_criterion:ac_min_thickness"
        d.validate(); d.commit()
        object_numbers.append("TST-000001")

    draft_rel = release(
        workspace, bundle, object_numbers,
        release_label="rev-A", stage_number=1, final_stage=True,
    )
    return workspace, draft_rel


def _load_release_manifest(workspace: Path, label: str) -> dict:
    from aiadra_core.truth_model.manifest import load_manifest
    return load_manifest(workspace, label)
