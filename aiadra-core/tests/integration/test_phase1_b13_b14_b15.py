"""Codex5 B13-B15 absorption tests.

B13: V&V chain integrity at final-stage release (Wedge-002 shape; CHAIN CLOSED).
B14: W1 validators use authoritative staged graph — prior_stage_manifest_ref chain
     (NOT unrelated workspace releases) + released Revision contents (NOT working
     sidecars after mutation).
B15: final-stage validation outcomes (cardinality + V&V) appear in
     manifest.validation_outcomes (not discarded).
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from aiadra_core.cli.validate import run_validate
from aiadra_core.transaction.operations import (
    attach_file,
    create_object,
    init_workspace,
    link_relationship,
    release,
)
from aiadra_core.truth_model.manifest import load_manifest
from aiadra_core.truth_model.reservation import (
    find_reservation_entry_by_number,
    load_reservation,
    reservation_path,
)
from aiadra_core.validation.bundle_registry import BundleRegistry
from aiadra_core.validation.profile import dump_yaml
from aiadra_core.validation.release import ReleaseConsistencyError


def _init(tmp_path: Path):
    workspace = tmp_path / "ws"
    bundle = BundleRegistry().latest()
    d = init_workspace(workspace, bundle)
    d.validate(); d.commit()
    return workspace, bundle


def _make_minimal_part(workspace, bundle, number, name):
    return create_object(workspace, bundle, "Part", number, name)


def _make_minimal_req(workspace, bundle, number, name):
    return create_object(
        workspace, bundle, "Requirement", number, name,
        extra_namespaces={
            "requirement": {
                "statement": {"text": "Bracket shall hold load", "language": "en", "format": "freeform"},
                "category": "functional",
            },
        },
    )


def _make_minimal_tst(workspace, bundle, number, name):
    # No inline attachment; attach via real attach_file Transaction after create.
    return create_object(
        workspace, bundle, "TestProcedure", number, name,
        extra_namespaces={
            "test_procedure": {"title": name, "verification_method": "test"},
            "attachment": [],
        },
    )


def _make_minimal_tex(workspace, bundle, number, name):
    return create_object(
        workspace, bundle, "TestExecution", number, name,
        extra_namespaces={
            "test_execution": {
                "executed_on_date": "2026-05-31",
                "execution_status": "completed",
            },
            "attachment": [],
            "parameter": [{
                "id": "param_measured", "name": "measured_thickness_mm",
                "datatype": "number", "unit": "mm", "value": 7.1,
                "fact_provenance": {
                    "category": "measured",
                    "derived_from": ["attachment:att_tex_log"],
                },
            }],
        },
    )


def _make_minimal_evd(workspace, bundle, number, name):
    return create_object(
        workspace, bundle, "EvidenceArtifact", number, name,
        extra_namespaces={
            "evidence": {"summary": "Bracket thickness measurement", "evidence_kind": "measurement"},
            "attachment": [],
            "parameter": [{
                "id": "param_reported", "name": "reported_thickness_mm",
                "datatype": "number", "unit": "mm", "value": 7.1,
                "fact_provenance": {
                    "category": "measured",
                    "derived_from": ["attachment:att_evd_data"],
                },
            }],
        },
    )


def _run(d):
    d.validate(); d.commit()


def _attach_real(workspace, bundle, tmp_path, obj_number, att_id, role, content):
    """Create a real temp file + attach_file Transaction → real Vault bytes."""
    f = tmp_path / f"{att_id}.bin"
    f.write_bytes(content)
    d = attach_file(workspace, bundle, obj_number, f, role, attachment_id=att_id)
    d.validate(); d.commit()
    return d


def _make_attachment_record(content: bytes, att_id: str, role: str, media_type: str,
                              workspace: Path) -> dict:
    """Pre-stage Vault bytes + return an attachment record dict with the real hash.

    Bypasses the attach_file Transaction (which requires an existing Object)
    so the FIRST attachment of an Attachment-bearing Object can be seeded at
    create-time with real Vault bytes + matching content_hash.
    """
    from aiadra_core.vault.local_fs import LocalFSVaultAdapter
    vault = LocalFSVaultAdapter(workspace)
    content_hash, vault_path = vault.store(content)
    return {
        "id": att_id,
        "role": role,
        "content_hash": content_hash,
        "vault_path": vault_path,
        "media_type": media_type,
    }


def _make_tst_with_attachment(workspace, bundle, number, name, tmp_path: Path):
    rec = _make_attachment_record(
        b"TEST PROCEDURE for " + number.encode(),
        f"att_{number.lower().replace('-', '_')}_proc", "source_authoring",
        "application/pdf", workspace,
    )
    return create_object(
        workspace, bundle, "TestProcedure", number, name,
        extra_namespaces={
            "test_procedure": {"title": name, "verification_method": "test"},
            "attachment": [rec],
        },
    )


def _make_tex_with_attachment(workspace, bundle, number, name, tmp_path: Path):
    att_id = f"att_{number.lower().replace('-', '_')}_log"
    rec = _make_attachment_record(
        b"INSTRON LOG for " + number.encode(),
        att_id, "source_authoring",
        "text/csv", workspace,
    )
    return create_object(
        workspace, bundle, "TestExecution", number, name,
        extra_namespaces={
            "test_execution": {
                "executed_on_date": "2026-05-31",
                "execution_status": "completed",
            },
            "attachment": [rec],
            "parameter": [{
                "id": "param_measured", "name": "measured_thickness_mm",
                "datatype": "number", "unit": "mm", "value": 7.1,
                "fact_provenance": {"category": "measured", "derived_from": [f"attachment:{att_id}"]},
            }],
        },
    )


def _make_evd_with_attachment(workspace, bundle, number, name, tmp_path: Path):
    att_id = f"att_{number.lower().replace('-', '_')}_data"
    rec = _make_attachment_record(
        b"MEASUREMENT DATA for " + number.encode(),
        att_id, "source_authoring",
        "text/csv", workspace,
    )
    return create_object(
        workspace, bundle, "EvidenceArtifact", number, name,
        extra_namespaces={
            "evidence": {"summary": "Measurement", "evidence_kind": "measurement"},
            "attachment": [rec],
            "parameter": [{
                "id": "param_reported", "name": "reported_thickness_mm",
                "datatype": "number", "unit": "mm", "value": 7.1,
                "fact_provenance": {"category": "measured", "derived_from": [f"attachment:{att_id}"]},
            }],
        },
    )


# ---------- B13: V&V chain integrity at final-stage release ----------


def test_b13_b16_vv_chain_and_attachment_integrity_at_final_release(tmp_path: Path):
    """B13 + B16: a full Wedge-002 V&V chain (Part + REQ + TST + TEX + EVD +
    6 V&V relationships + 3 real attachments with Vault bytes) must pass V&V
    chain integrity AND attachment integrity AND attachment lineage at
    final-stage release. All outcomes must appear in
    manifest.validation_outcomes per B15."""
    workspace, bundle = _init(tmp_path)
    _run(_make_minimal_part(workspace, bundle, "P-000001", "Bracket"))
    _run(_make_minimal_req(workspace, bundle, "REQ-000001", "Bracket req"))
    _run(_make_tst_with_attachment(workspace, bundle, "TST-000001", "Procedure", tmp_path))
    _run(_make_tex_with_attachment(workspace, bundle, "TEX-000001", "Execution", tmp_path))
    _run(_make_evd_with_attachment(workspace, bundle, "EVD-000001", "Evidence", tmp_path))
    # 6 V&V relationships
    _run(link_relationship(workspace, bundle, "satisfies", "P-000001", "REQ-000001"))
    _run(link_relationship(workspace, bundle, "tested_against", "P-000001", "TST-000001"))
    _run(link_relationship(workspace, bundle, "verifies", "TST-000001", "REQ-000001"))
    _run(link_relationship(workspace, bundle, "cites", "REQ-000001", "EVD-000001"))
    _run(link_relationship(workspace, bundle, "executes", "TEX-000001", "TST-000001"))
    _run(link_relationship(workspace, bundle, "executed_on", "TEX-000001", "P-000001"))
    _run(link_relationship(workspace, bundle, "produces", "TEX-000001", "EVD-000001"))
    # Release all 5 final-stage single-stage
    d_rel = release(
        workspace, bundle,
        ["P-000001", "REQ-000001", "TST-000001", "TEX-000001", "EVD-000001"],
        release_label="rev-A", stage_number=1, final_stage=True,
    )
    d_rel.validate(); d_rel.commit()
    # B15 + B16: manifest.validation_outcomes contains all expected outcomes
    manifest = load_manifest(workspace, "rev-A")
    check_names = {o["check_name"] for o in manifest["validation_outcomes"]}
    assert "vv_chain_integrity" in check_names
    assert "execution_cardinality(TEX-000001)" in check_names
    assert "attachment_integrity(att_tst_000001_proc)" in check_names
    assert "attachment_integrity(att_tex_000001_log)" in check_names
    assert "attachment_integrity(att_evd_000001_data)" in check_names
    assert "attachment_lineage(TST-000001)" in check_names
    assert "attachment_lineage(TEX-000001)" in check_names
    assert "attachment_lineage(EVD-000001)" in check_names
    # validate workspace still passes
    rc = run_validate(workspace)
    assert rc == 0, f"validate failed; rc={rc}"


def test_b16_attachment_integrity_rejects_when_vault_bytes_missing(tmp_path: Path):
    """B16 negative: an Attachment-bearing Object with embedded content_hash
    but no matching Vault bytes must hard-fail release."""
    from aiadra_core.vault.interface import AttachmentIntegrityError as AIE
    workspace, bundle = _init(tmp_path)
    # Create TST with synthetic attachment (no Vault bytes for this hash)
    _run(create_object(
        workspace, bundle, "TestProcedure", "TST-000001", "Procedure",
        extra_namespaces={
            "test_procedure": {"title": "Procedure", "verification_method": "test"},
            "attachment": [{
                "id": "att_synthetic", "role": "source_authoring",
                "content_hash": "sha256:" + "f" * 64,
                "vault_path": "vault/" + "f" * 64,
                "media_type": "application/pdf",
            }],
        },
    ))
    # Release MUST raise AttachmentIntegrityError (B16: Vault bytes missing)
    with pytest.raises(AIE, match="Vault missing bytes"):
        release(workspace, bundle, ["TST-000001"], release_label="rev-bad",
                 stage_number=1, final_stage=False)


def test_b16_attachment_lineage_rejects_missing_source_authoring(tmp_path: Path):
    """B16 negative: an Attachment-bearing Object whose released attachments
    lack a source_authoring role MUST hard-fail per ADR/0017 §2 D7-escape."""
    from aiadra_core.vault.interface import AttachmentIntegrityError as AIE
    workspace, bundle = _init(tmp_path)
    # Pre-stage real Vault bytes for a derived attachment ONLY (no source_authoring)
    rec = _make_attachment_record(
        b"RENDERED PRIMARY ONLY\n",
        "att_derived_only", "rendered_primary",
        "image/png", workspace,
    )
    rec["derived_from_attachment_id"] = "att_missing_source"
    _run(create_object(
        workspace, bundle, "TestProcedure", "TST-000001", "Procedure",
        extra_namespaces={
            "test_procedure": {"title": "Procedure", "verification_method": "test"},
            "attachment": [rec],
        },
    ))
    # Release MUST raise — no source_authoring + derived chain doesn't terminate
    with pytest.raises(AIE):
        release(workspace, bundle, ["TST-000001"], release_label="rev-bad",
                 stage_number=1, final_stage=False)


def test_b13_broken_vv_chain_rejected_at_final_release(tmp_path: Path):
    """B13: a Part with tested_against but no executes/produces chain closure
    must hard-fail at final-stage release."""
    workspace, bundle = _init(tmp_path)
    _run(_make_minimal_part(workspace, bundle, "P-000001", "Bracket"))
    _run(_make_tst_with_attachment(workspace, bundle, "TST-000001", "Procedure", tmp_path))
    # tested_against but NO TestExecution / EvidenceArtifact / cites / verifies
    _run(link_relationship(workspace, bundle, "tested_against", "P-000001", "TST-000001"))
    # Validators run inline during release() construction (so outcomes can be
    # baked into the manifest before hash sealing per B15); the raise surfaces
    # at release() call, not at d_rel.validate().
    with pytest.raises(ReleaseConsistencyError, match="V&V chain"):
        release(
            workspace, bundle, ["P-000001", "TST-000001"],
            release_label="rev-broken", stage_number=1, final_stage=True,
        )


# ---------- B14: W1 graph authority ----------


def test_b14_unrelated_release_does_not_satisfy_prior_stage_closure(tmp_path: Path):
    """B14: a Fixed endpoint must resolve to the NAMED prior_stage_manifest_ref
    chain, not any unrelated release elsewhere in the workspace.

    Setup: two independent release chains.
    - Chain A: release P-000001 (rev-A1) — TST is here
    - Chain B: TEX wants to link-executes against TST's released rev, but
      Chain B's prior_stage_manifest_ref points at Chain C (which doesn't
      contain TST). Closure must fail.

    Simpler version: create 2 unrelated releases, then attempt a stage 2
    release that names ONE prior stage but contains relationships only
    satisfied by the OTHER unrelated release.
    """
    workspace, bundle = _init(tmp_path)
    # Two unrelated stage-1 releases:
    #  Release A contains TST
    _run(_make_tst_with_attachment(workspace, bundle, "TST-000001", "Procedure", tmp_path))
    d_relA = release(workspace, bundle, ["TST-000001"],
                      release_label="rev-A", stage_number=1, final_stage=False)
    d_relA.validate(); d_relA.commit()
    relA_hash = "sha256:" + hashlib.sha256(
        (workspace / "Releases" / "rev-A" / "manifest.json").read_bytes()
    ).hexdigest()

    #  Release B contains an unrelated Part
    _run(_make_minimal_part(workspace, bundle, "P-000099", "Unrelated"))
    d_relB = release(workspace, bundle, ["P-000099"],
                      release_label="rev-B", stage_number=1, final_stage=False)
    d_relB.validate(); d_relB.commit()
    relB_hash = "sha256:" + hashlib.sha256(
        (workspace / "Releases" / "rev-B" / "manifest.json").read_bytes()
    ).hexdigest()

    # Now create TEX that link-executes TST (which is in rel-A) but try to release
    # claiming rel-B as the prior stage. Closure must fail because rel-B's chain
    # doesn't contain TST.
    _run(_make_tex_with_attachment(workspace, bundle, "TEX-000001", "Execution", tmp_path))
    _run(_make_minimal_part(workspace, bundle, "P-000002", "Tested Part"))
    _run(link_relationship(workspace, bundle, "executes", "TEX-000001", "TST-000001"))
    _run(link_relationship(workspace, bundle, "executed_on", "TEX-000001", "P-000002"))

    # Release TEX with prior chain pointing at rel-B (which does NOT contain TST).
    # Closure validator runs inline during release() construction.
    with pytest.raises(ReleaseConsistencyError, match="Stage dependency closure"):
        release(
            workspace, bundle, ["TEX-000001", "P-000002"],
            release_label="rev-C", stage_number=2, final_stage=False,
            prior_stage_manifest_ref={"manifest_hash": relB_hash, "stage_number": 1},
        )


def test_b14_final_validation_uses_released_revision_not_working_sidecar(tmp_path: Path):
    """B14: after a Part is released, its working sidecar's `current_revision_id`
    is fresh; mutating the working sidecar must not perturb a subsequent
    final-stage validation that should consult the RELEASED Revision content.

    Simplest variant: this is exercised implicitly by the chain-following code
    paths. Here we assert that a final-stage release computing cardinality on
    a prior-stage TestExecution does NOT pick up post-release sidecar mutations
    on the test execution. This requires the cardinality validator to read the
    released Revision content (not the working sidecar).

    Since Phase 1 doesn't yet expose object-changed mutations outside of
    parameter_changed (which would be blocked by B6 anyway for execution-instance
    objects), this test verifies the structural invariant via the
    `_cumulative_released_revisions` helper directly.
    """
    from aiadra_core.validation.release import _cumulative_released_revisions, ReleaseDraft

    workspace, bundle = _init(tmp_path)
    _run(_make_minimal_part(workspace, bundle, "P-000001", "Bracket"))
    d_relA = release(workspace, bundle, ["P-000001"],
                      release_label="rev-A1", stage_number=1, final_stage=False)
    d_relA.validate(); d_relA.commit()
    relA_hash = "sha256:" + hashlib.sha256(
        (workspace / "Releases" / "rev-A1" / "manifest.json").read_bytes()
    ).hexdigest()

    # Mutate the working sidecar's name AFTER release (simulating drift).
    # Since change-parameter for Part with no parameters can't run easily,
    # we directly edit the file.
    from aiadra_core.truth_model.sidecar import working_sidecar_path, load_sidecar
    from aiadra_core.truth_model.atomic import atomic_write_bytes
    _, entry = find_reservation_entry_by_number(workspace, "P-000001")
    obj_uuid = entry["object_uuid"]
    sidecar = load_sidecar(workspace, obj_uuid)
    mutated = deepcopy(sidecar)
    mutated["object"]["name"] = "DRIFTED-AFTER-RELEASE"
    atomic_write_bytes(working_sidecar_path(workspace, obj_uuid),
                       dump_yaml(mutated).encode("utf-8"))

    # Build a fake stage-2 ReleaseDraft chaining to rel-A1; the cumulative
    # graph for prior-stage P-000001 should reflect the RELEASED Revision content
    # (object.name = "Bracket"), not the drifted working sidecar.
    proto = ReleaseDraft(
        release_label="rev-A2",
        manifest={"prior_stage_manifest_ref": {"manifest_hash": relA_hash, "stage_number": 1},
                  "revisions": []},
        manifest_hash="",
        release_staged_event={"payload": {"released_object_uuids": [], "stage_number": 2, "final_stage": True}},
    )
    cumulative = _cumulative_released_revisions(workspace, bundle.bundle_dir, proto)
    assert obj_uuid in cumulative
    assert cumulative[obj_uuid]["object"]["name"] == "Bracket", \
        f"B14: cumulative graph picked up drifted working sidecar instead of released Revision content"
