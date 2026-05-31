"""Phase 1 Codex4 B8-B12 absorption tests.

Covers the missing acceptance coverage Codex4 flagged:
- B6 mutation prohibition through execution-instance links
- W2 attach-file emitting <type>_changed with attachment_delta
- W1 two-stage release with prior_stage_manifest_ref chaining
- N3 reservation_integrity violation caught by aiadra validate
- B9 dirty-worktree guard rejects state-changing Transactions
- B10 init pin is tracked in initial commit
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from aiadra_core.cli.validate import run_validate
from aiadra_core.transaction.operations import (
    attach_file,
    change_parameter,
    create_object,
    init_workspace,
    link_relationship,
    release,
)
from aiadra_core.truth_model.reservation import (
    find_reservation_entry_by_number,
    load_reservation,
    reservation_path,
)
from aiadra_core.validation.binding import RevisionBindingError
from aiadra_core.validation.bundle_registry import BundleRegistry
from aiadra_core.validation.profile import dump_yaml


def _init_basic(tmp_path: Path):
    workspace = tmp_path / "ws"
    bundle = BundleRegistry().latest()
    draft = init_workspace(workspace, bundle)
    draft.validate()
    draft.commit()
    return workspace, bundle


# ---------- B10 ----------


def test_b10_init_pin_is_tracked_in_initial_commit(tmp_path: Path):
    """B10: .aiadra/schemas.yaml MUST be tracked in the init commit (not
    written outside the Transaction)."""
    workspace, _ = _init_basic(tmp_path)
    result = subprocess.run(
        ["git", "-c", f"safe.directory={workspace.resolve().as_posix()}",
         "-C", str(workspace), "ls-files", ".aiadra/schemas.yaml"],
        capture_output=True, text=True, check=True,
    )
    assert ".aiadra/schemas.yaml" in result.stdout.strip()
    # Working tree must be clean (no untracked AIADRA-managed paths)
    status = subprocess.run(
        ["git", "-c", f"safe.directory={workspace.resolve().as_posix()}",
         "-C", str(workspace), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    )
    assert status.stdout.strip() == "", f"git status not clean after init: {status.stdout!r}"


# ---------- B9 dirty-worktree guard ----------


def test_b9_dirty_aiadra_path_rejects_state_changing_transaction(tmp_path: Path):
    """B9: an unrelated dirty AIADRA-managed file rejects a new Transaction."""
    workspace, bundle = _init_basic(tmp_path)
    # Manually dirty an AIADRA-managed file
    (workspace / "Reservations" / "P.yaml").write_text(
        '"artifact_kind": "reservation"\n"discriminator": "P"\n"name": "DIRTY"\n'
        '"reservations": {}\n"schema_version": "0.20.0"\n"status": "active"\n',
        encoding="utf-8",
    )
    # Attempt create-part; should be blocked by dirty-worktree guard via _run_draft
    from aiadra_core.cli.commands import _run_draft
    draft = create_object(workspace, bundle, "Part", "P-000001", "Test")
    rc = _run_draft(draft)
    assert rc == 5, f"expected exit 5 (dirty worktree); got {rc}"


# ---------- B9 fold check ----------


def test_b9_proposed_state_fold_catches_drift(tmp_path: Path):
    """B9: TransactionDraft.validate() must catch sidecar/event drift in proposed state.

    Scenario: create a Part normally, then build a follow-up Transaction that
    stages a DIVERGENT sidecar update against the on-disk Object without
    emitting a corresponding event. The proposed-state fold MUST catch the
    drift.
    """
    from copy import deepcopy
    workspace, bundle = _init_basic(tmp_path)
    draft = create_object(workspace, bundle, "Part", "P-000001", "Original")
    draft.validate(); draft.commit()

    # Build a follow-up draft that mutates the sidecar WITHOUT a corresponding event
    from aiadra_core.transaction.boundary import TransactionDraft, TransactionKind
    from aiadra_core.truth_model.reservation import find_reservation_entry_by_number
    from aiadra_core.truth_model.sidecar import load_sidecar

    _, entry = find_reservation_entry_by_number(workspace, "P-000001")
    uuid = entry["object_uuid"]
    sidecar = load_sidecar(workspace, uuid)
    mutated = deepcopy(sidecar)
    mutated["object"]["name"] = "DIVERGED"

    bad_draft = TransactionDraft(
        workspace=workspace, bundle=bundle,
        kind=TransactionKind.CHANGE_PARAMETER,  # any non-INIT kind triggers fold check
        transaction_id="tx_0099",
    )
    bad_draft.stage_sidecar(uuid, mutated)  # stage mutation WITHOUT event

    from aiadra_core.validation.fold import FoldInconsistencyError
    with pytest.raises(FoldInconsistencyError):
        bad_draft.validate()


# ---------- B6 mutation prohibition ----------


def _create_test_procedure(workspace, bundle, number, name):
    """Create a TestProcedure with the minimum required namespaces."""
    return create_object(
        workspace, bundle, "TestProcedure", number, name,
        extra_namespaces={
            "test_procedure": {
                "title": name,
                "verification_method": "test",
            },
            "attachment": [{
                "id": "att_seed",
                "role": "source_authoring",
                "content_hash": "sha256:" + "0" * 64,
                "vault_path": "vault/" + "0" * 64,
                "media_type": "application/pdf",
            }],
        },
    )


def _create_test_execution(workspace, bundle, number, name):
    return create_object(
        workspace, bundle, "TestExecution", number, name,
        extra_namespaces={
            "test_execution": {
                "executed_on_date": "2026-05-31",
                "execution_status": "completed",
            },
            "attachment": [{
                "id": "att_seed",
                "role": "source_authoring",
                "content_hash": "sha256:" + "1" * 64,
                "vault_path": "vault/" + "1" * 64,
                "media_type": "text/csv",
            }],
            "parameter": [{
                "id": "param_measured",
                "name": "measured_thickness_mm",
                "datatype": "number",
                "unit": "mm",
                "value": 7.1,
                "fact_provenance": {
                    "category": "measured",
                    "derived_from": ["attachment:att_seed"],
                },
            }],
        },
    )


def test_b6_link_executes_then_change_parameter_on_TST_rejected(tmp_path: Path):
    """B6 Option C: once TST has executes-binding from TEX, mutating TST
    (change_parameter or attach_file) must hard-fail until TST is released."""
    workspace, bundle = _init_basic(tmp_path)

    # Create TST with a parameter we'll later try to change
    d_tst = create_object(
        workspace, bundle, "TestProcedure", "TST-000001", "Procedure",
        extra_namespaces={
            "test_procedure": {"title": "Procedure", "verification_method": "test"},
            "attachment": [{
                "id": "att_seed", "role": "source_authoring",
                "content_hash": "sha256:" + "0" * 64,
                "vault_path": "vault/" + "0" * 64,
                "media_type": "application/pdf",
            }],
            "parameter": [{
                "id": "param_dur", "name": "duration_s", "datatype": "number",
                "unit": "s", "value": 60,
                "fact_provenance": {"category": "human_input"},
            }],
        },
    )
    d_tst.validate(); d_tst.commit()

    d_tex = _create_test_execution(workspace, bundle, "TEX-000001", "Execution")
    d_tex.validate(); d_tex.commit()

    # link-executes: binds TEX → TST current_revision_id
    d_link = link_relationship(workspace, bundle, "executes", "TEX-000001", "TST-000001")
    d_link.validate(); d_link.commit()

    # Now mutating TST.param_dur MUST be rejected per B6
    d_change = change_parameter(workspace, bundle, "TST-000001", "param_dur", 90, "tighten")
    with pytest.raises(RevisionBindingError):
        d_change.validate()


# ---------- W2 attach-file flow ----------


def test_w2_attach_file_emits_changed_event_with_attachment_delta(tmp_path: Path):
    """W2: attach-file MUST emit a <type>_changed event with attachment_delta
    payload (operation=add). Fold-replay must include the added attachment."""
    workspace, bundle = _init_basic(tmp_path)

    d_tst = _create_test_procedure(workspace, bundle, "TST-000001", "Procedure")
    d_tst.validate(); d_tst.commit()

    # Make a small fixture file to attach
    f = tmp_path / "extra.csv"
    f.write_text("col1,col2\n1,2\n", encoding="utf-8")

    d_att = attach_file(
        workspace, bundle, "TST-000001", f, "derived_secondary",
        attachment_id="att_extra",
        derived_from_attachment_id="att_seed",
    )
    d_att.validate(); d_att.commit()

    # Verify the event was emitted with attachment_delta
    assert any(e["event_type"] == "test_procedure_changed" for e in d_att.events)
    changed = [e for e in d_att.events if e["event_type"] == "test_procedure_changed"][0]
    delta = changed["payload"]["attachment_delta"]
    assert delta["operation"] == "add"
    assert delta["attachment_id"] == "att_extra"
    assert delta["attachment_record"]["role"] == "derived_secondary"
    assert delta["attachment_record"]["derived_from_attachment_id"] == "att_seed"

    # Run aiadra validate; it should pass (fold reconstructs working sidecar from events)
    rc = run_validate(workspace)
    assert rc == 0, f"validate should pass after W2 attach-file; got rc={rc}"


# ---------- W1 multi-stage release ----------


def test_w1_two_stage_release_chains_via_prior_stage_manifest_ref(tmp_path: Path):
    """W1 multi-stage: stage 1 releases a subset; stage 2 references prior
    via manifest_hash; both manifests on disk; final-stage validation passes."""
    workspace, bundle = _init_basic(tmp_path)

    d_p = create_object(workspace, bundle, "Part", "P-000001", "Bracket")
    d_p.validate(); d_p.commit()
    d_r = create_object(
        workspace, bundle, "Requirement", "REQ-000001", "Bracket req",
        extra_namespaces={
            "requirement": {
                "statement": {"text": "Bracket shall be sturdy", "language": "en", "format": "freeform"},
                "category": "functional",
            },
        },
    )
    d_r.validate(); d_r.commit()

    # Stage 1: release Part only (no final cardinality check needed)
    d_s1 = release(workspace, bundle, ["P-000001"],
                    release_label="rev-A-stage1", stage_number=1, final_stage=False)
    s1_outcomes = d_s1.validate()
    s1_result = d_s1.commit()
    assert s1_result.commit_hash
    s1_manifest_path = workspace / "Releases" / "rev-A-stage1" / "manifest.json"
    s1_hash = "sha256:" + __import__("hashlib").sha256(s1_manifest_path.read_bytes()).hexdigest()

    # Stage 2: release Requirement, chain to stage 1
    d_s2 = release(
        workspace, bundle, ["REQ-000001"],
        release_label="rev-A-stage2", stage_number=2, final_stage=True,
        prior_stage_manifest_ref={"manifest_hash": s1_hash, "stage_number": 1},
    )
    d_s2.validate()
    s2_result = d_s2.commit()
    assert s2_result.commit_hash
    assert (workspace / "Releases" / "rev-A-stage2" / "manifest.json").exists()

    # Validate workspace: both manifests + replay consistency must pass
    rc = run_validate(workspace)
    assert rc == 0, f"two-stage workspace validate failed; rc={rc}"


# ---------- N3 corruption ----------


def test_n3_aiadra_validate_catches_current_rev_id_reuse(tmp_path: Path):
    """N3 invariant 3: current_revision_id appearing in released_revision_ids[]
    is hard-failed by aiadra validate."""
    workspace, bundle = _init_basic(tmp_path)

    d_p = create_object(workspace, bundle, "Part", "P-000001", "Bracket")
    d_p.validate(); d_p.commit()
    d_rel = release(workspace, bundle, ["P-000001"], release_label="rev-X",
                     stage_number=1, final_stage=True)
    d_rel.validate(); d_rel.commit()

    # Corrupt the Reservation: set current_revision_id back to the released one
    p_res = load_reservation(workspace, "P")
    entry = p_res["reservations"]["P-000001"]
    released = entry["released_revision_ids"][0]
    entry["current_revision_id"] = released
    reservation_path(workspace, "P").write_bytes(dump_yaml(p_res).encode("utf-8"))

    rc = run_validate(workspace)
    assert rc == 1, f"N3 invariant 3 violation should fail validate; got rc={rc}"
