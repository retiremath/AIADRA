"""Phase C tests — `propose` / `modify` as first-class Ring 2 entities
per ADR/0026 §"Sequencing" Phase C (arc 20260531-9).

Covers Codex1 absorptions:
- B1 (draft-aware reads + composability): create + mutate in one Transaction.
- B2 (init/release composition): init never composes; release never composes.
- B3 (lifecycle terminal-state): modify after commit/rollback raises.
- B4 (provenance discipline): agent cannot self-attest as human_input.
- B2 (bundle resolution): propose(init) uses BundleRegistry.latest(),
  all other kinds use bundle_for_pin (raises ProjectPinError if missing).

Plus per-kind smoke tests, CLI delegation unchanged-behavior, and migrator
v0.25.0 → v0.26.0 chain.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from aiadra_core import protocol
from aiadra_core.protocol import (
    ObjectNotFoundError,
    ProjectPinError,
    TransactionDraft,
    TransactionError,
    commit,
    modify,
    modify_kinds,
    propose,
    propose_kinds,
    rollback,
)
from aiadra_core.transaction.boundary import TransactionKind
from aiadra_core.truth_model.reservation import find_reservation_entry_by_number
from aiadra_core.truth_model.sidecar import load_sidecar
from aiadra_core.validation.bundle_registry import BundleRegistry
from aiadra_core.validation.migration import (
    REGISTERED_STEPS,
    apply_migration,
    plan_migration,
)


def _bundle_latest():
    return BundleRegistry().latest()


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_phase_c_module_exports():
    """All Phase C symbols importable from `aiadra_core.protocol`."""
    assert callable(propose)
    assert callable(modify)
    assert callable(propose_kinds)
    assert callable(modify_kinds)
    assert TransactionError is not None


def test_phase_c_propose_kinds_catalogue():
    """propose_kinds is a sorted tuple covering the 17 state-changing kinds:
    init + 5 create_* + change_parameter + add_acceptance_criterion + 7 link_* + attach_file + release.
    """
    kinds = propose_kinds()
    assert isinstance(kinds, tuple)
    assert kinds == tuple(sorted(kinds))
    assert "init" in kinds
    assert "release" in kinds
    assert "delete_object" in kinds  # ADR/0004 SCN arc 20260728-3
    assert "change_parameter" in kinds
    assert "add_acceptance_criterion" in kinds
    assert "attach_file" in kinds
    for t in ("part", "requirement", "test_procedure", "test_execution", "evidence_artifact"):
        assert f"create_{t}" in kinds
    for r in ("satisfies", "tested_against", "verifies", "cites", "executes", "executed_on", "produces"):
        assert f"link_{r}" in kinds
    # Friction surfaced by Wedge-003 install (arc 20260601-3): propose_kinds()
    # now returns COMBINED built-in + LOADED engine kinds per ADR/0028 D5. If
    # mechanical_spike (or any other engine) is installed, the count exceeds
    # 17. Fix: count only built-in kinds (those without a dot prefix).
    builtin_kinds = [k for k in kinds if "." not in k]
    # 18 since delete_object joined (ADR/0004 SCN arc 20260728-3).
    assert len(builtin_kinds) == 18


def test_phase_c_modify_kinds_excludes_init_and_release():
    """Codex1 B2 absorption: modify rejects init and release (they don't compose
    with in-flight mutations); modify_kinds() reflects this."""
    mkinds = modify_kinds()
    assert "init" not in mkinds
    assert "release" not in mkinds
    # delete_object joined the rejected set (Codex2 N1 arc 20260728-3:
    # the destructive kind is standalone).
    assert "delete_object" not in mkinds
    assert len(mkinds) == len(propose_kinds()) - 3
    for k in mkinds:
        assert k in propose_kinds()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_workspace(tmp_path: Path, name: str = "ws") -> Path:
    workspace = tmp_path / name
    propose(workspace, kind="init", params={}).commit()
    return workspace


def _create_part_with_thickness(
    workspace: Path, number: str = "P-000001", name: str = "Bracket", value: float = 7,
) -> str:
    """Create a Part with a parameter; return its UUID."""
    draft = propose(workspace, kind="create_part", params={
        "number": number, "name": name,
        "extra_namespaces": {
            "parameter": [{
                "id": "param_thickness", "name": "plate_thickness_mm",
                "datatype": "number", "unit": "mm", "value": value,
                "fact_provenance": {"category": "human_input"},
            }],
        },
    })
    draft.commit()
    _, entry = find_reservation_entry_by_number(workspace, number)
    return entry["object_uuid"]


def _seed_attachment(workspace: Path, payload: bytes, att_id: str,
                     role: str = "source_authoring",
                     media_type: str = "application/octet-stream") -> dict:
    """Pre-stage Vault bytes + return an attachment record. Bypasses the
    attach_file Transaction so the FIRST attachment of an Attachment-bearing
    Object can be seeded at create-time (same pattern as
    test_phase1_b13_b14_b15._make_attachment_record)."""
    from aiadra_core.vault.local_fs import LocalFSVaultAdapter
    vault = LocalFSVaultAdapter(workspace)
    content_hash, vault_path = vault.store(payload)
    return {
        "id": att_id, "role": role,
        "content_hash": content_hash, "vault_path": vault_path,
        "media_type": media_type,
    }


def _minimal_extra_for(obj_kind: str, workspace: Path | None = None) -> dict:
    """Minimum valid sidecar extras per Object Type schema requirements.

    Attachment-bearing kinds (TestProcedure / TestExecution / EvidenceArtifact)
    require a non-empty `attachment` array; `workspace` MUST be provided so
    real Vault bytes are pre-staged for the seed attachment.
    """
    if obj_kind == "create_part":
        return {}
    if obj_kind == "create_requirement":
        return {
            "requirement": {
                "statement": {"text": "shall do something",
                              "language": "en", "format": "freeform"},
                "category": "functional",
            },
        }
    if obj_kind == "create_test_procedure":
        assert workspace is not None, "test_procedure needs workspace for vault seed"
        return {
            "test_procedure": {
                "title": "fixture", "verification_method": "test",
            },
            "attachment": [_seed_attachment(
                workspace, b"TEST PROCEDURE seed", "att_tst_seed",
                media_type="application/pdf",
            )],
        }
    if obj_kind == "create_test_execution":
        assert workspace is not None, "test_execution needs workspace for vault seed"
        return {
            "test_execution": {
                "executed_on_date": "2026-05-31",
                "execution_status": "completed",
            },
            "attachment": [_seed_attachment(
                workspace, b"INSTRON LOG seed", "att_tex_seed",
                media_type="text/csv",
            )],
            "parameter": [{
                "id": "param_measured", "name": "measured_value",
                "datatype": "number", "unit": "mm", "value": 7.0,
                "fact_provenance": {
                    "category": "measured",
                    "derived_from": ["attachment:att_tex_seed"],
                },
            }],
        }
    if obj_kind == "create_evidence_artifact":
        assert workspace is not None, "evidence_artifact needs workspace for vault seed"
        return {
            "evidence": {"summary": "evidence", "evidence_kind": "measurement"},
            "attachment": [_seed_attachment(
                workspace, b"EVIDENCE DATA seed", "att_evd_seed",
                media_type="text/csv",
            )],
            "parameter": [{
                "id": "param_reported", "name": "reported_value",
                "datatype": "number", "unit": "mm", "value": 7.0,
                "fact_provenance": {
                    "category": "measured",
                    "derived_from": ["attachment:att_evd_seed"],
                },
            }],
        }
    raise KeyError(obj_kind)


# ---------------------------------------------------------------------------
# B2: bundle resolution — propose(init) uses latest; others use pin
# ---------------------------------------------------------------------------


def test_phase_c_propose_init_uses_latest_bundle_without_pin(tmp_path: Path):
    """B2: propose(kind='init') uses BundleRegistry.latest() because there is
    no project pin yet on an empty workspace."""
    workspace = tmp_path / "ws_init"
    draft = propose(workspace, kind="init", params={})
    assert draft.kind == TransactionKind.INIT
    assert draft.bundle.bundle_version == _bundle_latest().bundle_version
    draft.commit()
    assert (workspace / ".aiadra" / "schemas.yaml").exists()


def test_phase_c_propose_non_init_without_pin_raises_project_pin_error(tmp_path: Path):
    """B2: propose(kind=<not init>) requires a project pin; missing pin
    raises ProjectPinError with the underlying FileNotFoundError as __cause__."""
    workspace = tmp_path / "ws_no_pin"
    workspace.mkdir()
    with pytest.raises(ProjectPinError) as exc_info:
        propose(workspace, kind="create_part", params={"number": "P-000001", "name": "X"})
    assert exc_info.value.__cause__ is not None


def test_phase_c_propose_non_init_uses_bundle_for_pin(tmp_path: Path):
    """B2: non-init kinds resolve bundle from the project pin (which on a
    fresh init equals BundleRegistry.latest())."""
    workspace = _init_workspace(tmp_path)
    draft = propose(workspace, kind="create_part", params={
        "number": "P-000001", "name": "Bracket",
    })
    assert draft.bundle.bundle_version == _bundle_latest().bundle_version
    draft.commit()


# ---------------------------------------------------------------------------
# B1: composability (draft-aware reads)
# ---------------------------------------------------------------------------


def test_phase_c_compose_create_then_change_parameter_single_transaction(tmp_path: Path):
    """B1: create_part + change_parameter in ONE Transaction. The
    change_parameter must see the freshly-staged reservation + sidecar
    (NOT stale disk) so it can resolve P-000001 to its UUID."""
    workspace = _init_workspace(tmp_path)
    draft = propose(workspace, kind="create_part", params={
        "number": "P-000001", "name": "Bracket",
        "extra_namespaces": {
            "parameter": [{
                "id": "param_thickness", "name": "plate_thickness_mm",
                "datatype": "number", "unit": "mm", "value": 7,
                "fact_provenance": {"category": "human_input"},
            }],
        },
    })
    original_tx_id = draft.transaction_id
    modify(draft, kind="change_parameter", params={
        "obj_number": "P-000001",
        "parameter_id": "param_thickness",
        "new_value": 8.5,
        "rationale": "tightening tolerance",
        "new_fact_provenance": {"category": "ai_proposal"},
    })
    # Single transaction_id preserved across both ops
    assert draft.transaction_id == original_tx_id
    # Two events staged in the single draft
    assert len(draft.events) == 2
    result = draft.commit()
    assert result.transaction_id == original_tx_id
    assert len(result.event_ids) == 2
    # On-disk sidecar carries the mutated value
    _, entry = find_reservation_entry_by_number(workspace, "P-000001")
    sidecar = load_sidecar(workspace, entry["object_uuid"])
    assert sidecar["parameter"][0]["value"] == 8.5


def test_phase_c_compose_create_then_add_acceptance_criterion(tmp_path: Path):
    """B1: create_requirement + add_acceptance_criterion in one Transaction."""
    workspace = _init_workspace(tmp_path)
    draft = propose(workspace, kind="create_requirement", params={
        "number": "REQ-000001", "name": "Bracket strength",
        "extra_namespaces": _minimal_extra_for("create_requirement"),
    })
    modify(draft, kind="add_acceptance_criterion", params={
        "req_number": "REQ-000001",
        "criterion_id": "ac_strength_1",
        "criterion_text": "Bracket withstands 1000 N without yielding",
    })
    assert len(draft.events) == 2
    result = draft.commit()
    assert len(result.event_ids) == 2
    _, entry = find_reservation_entry_by_number(workspace, "REQ-000001")
    sidecar = load_sidecar(workspace, entry["object_uuid"])
    assert any(c["id"] == "ac_strength_1" for c in sidecar.get("acceptance_criterion", []))


def test_phase_c_compose_two_creates_plus_link(tmp_path: Path):
    """B1: create_part + create_requirement + link_satisfies in one Transaction.
    The link must resolve both numbers from STAGED reservations."""
    workspace = _init_workspace(tmp_path)
    draft = propose(workspace, kind="create_part", params={
        "number": "P-000001", "name": "Bracket",
    })
    modify(draft, kind="create_requirement", params={
        "number": "REQ-000001", "name": "Strength req",
        "extra_namespaces": _minimal_extra_for("create_requirement"),
    })
    modify(draft, kind="link_satisfies", params={
        "source_number": "P-000001", "target_number": "REQ-000001",
    })
    assert len(draft.events) == 3
    result = draft.commit()
    assert len(result.event_ids) == 3
    _, p_entry = find_reservation_entry_by_number(workspace, "P-000001")
    p_sidecar = load_sidecar(workspace, p_entry["object_uuid"])
    rels = p_sidecar.get("relationship", [])
    assert any(r["type"] == "satisfies" for r in rels)


def test_phase_c_compose_create_plus_attach_file(tmp_path: Path):
    """B1: create_evidence_artifact + attach_file in one Transaction.

    EvidenceArtifact requires `attachment` to be non-empty at creation; we
    pre-stage one attachment via the Vault adapter and seed it into the
    create's extra_namespaces, then compose `attach_file` which adds a
    SECOND attachment via the official Transaction path. The compose test
    here proves attach_file's draft-aware read sees the staged sidecar
    from the prior create (per B1)."""
    from aiadra_core.vault.local_fs import LocalFSVaultAdapter

    workspace = _init_workspace(tmp_path)
    vault = LocalFSVaultAdapter(workspace)
    seed_hash, seed_path = vault.store(b"SEED MEASUREMENT DATA")
    seed_extras = {
        "evidence": {"summary": "evidence", "evidence_kind": "measurement"},
        "attachment": [{
            "id": "att_seed",
            "role": "source_authoring",
            "content_hash": seed_hash,
            "vault_path": seed_path,
            "media_type": "text/csv",
        }],
        "parameter": [{
            "id": "param_reported", "name": "reported_value",
            "datatype": "number", "unit": "mm", "value": 7.0,
            "fact_provenance": {
                "category": "measured",
                "derived_from": ["attachment:att_seed"],
            },
        }],
    }
    second = tmp_path / "report.txt"
    second.write_bytes(b"second attachment payload")
    draft = propose(workspace, kind="create_evidence_artifact", params={
        "number": "EVD-000001", "name": "Test report",
        "extra_namespaces": seed_extras,
    })
    modify(draft, kind="attach_file", params={
        "obj_number": "EVD-000001",
        "file_path": second,
        "role": "derived_secondary",
    })
    result = draft.commit()
    assert len(result.event_ids) == 2
    _, e_entry = find_reservation_entry_by_number(workspace, "EVD-000001")
    e_sidecar = load_sidecar(workspace, e_entry["object_uuid"])
    assert len(e_sidecar.get("attachment", [])) == 2


def test_phase_c_compose_event_ids_are_unique_and_sequential(tmp_path: Path):
    """B1: composed events use _next_event_id_in_draft — sequential evt_NNNN
    counter advances per staged event (no collisions)."""
    workspace = _init_workspace(tmp_path)
    draft = propose(workspace, kind="create_part", params={
        "number": "P-000001", "name": "A",
    })
    modify(draft, kind="create_part", params={
        "number": "P-000002", "name": "B",
    })
    modify(draft, kind="create_part", params={
        "number": "P-000003", "name": "C",
    })
    event_ids = [e["event_id"] for e in draft.events]
    assert len(set(event_ids)) == 3
    nums = [int(eid[len("evt_"):]) for eid in event_ids]
    assert nums == [nums[0], nums[0] + 1, nums[0] + 2]


def test_phase_c_compose_extends_commit_message_lines(tmp_path: Path):
    """B1: composed ops EXTEND commit_message_lines (not replace) so the git
    commit captures the multi-op history."""
    workspace = _init_workspace(tmp_path)
    draft = propose(workspace, kind="create_part", params={
        "number": "P-000001", "name": "Bracket",
    })
    first_lines_len = len(draft.commit_message_lines)
    modify(draft, kind="create_part", params={
        "number": "P-000002", "name": "Plate",
    })
    assert len(draft.commit_message_lines) > first_lines_len
    # Both summaries present in joined message
    joined = "\n".join(draft.commit_message_lines)
    assert "P-000001" in joined
    assert "P-000002" in joined


# ---------------------------------------------------------------------------
# B2: init / release composition rejections
# ---------------------------------------------------------------------------


def test_phase_c_modify_init_rejected(tmp_path: Path):
    """B2: modify(kind='init') always raises TransactionError."""
    workspace = _init_workspace(tmp_path)
    draft = propose(workspace, kind="create_part", params={
        "number": "P-000001", "name": "X",
    })
    with pytest.raises(TransactionError, match="modify.kind='init'"):
        modify(draft, kind="init", params={})


def test_phase_c_modify_release_rejected(tmp_path: Path):
    """B2: modify(kind='release') always raises TransactionError."""
    workspace = _init_workspace(tmp_path)
    draft = propose(workspace, kind="create_part", params={
        "number": "P-000001", "name": "X",
    })
    with pytest.raises(TransactionError, match="modify.kind='release'"):
        modify(draft, kind="release", params={"object_numbers": ["P-000001"]})


# ---------------------------------------------------------------------------
# B3: lifecycle terminal-state guards
# ---------------------------------------------------------------------------


def test_phase_c_modify_after_commit_raises(tmp_path: Path):
    """B3: modify on a committed draft raises TransactionError per
    _assert_open('modify')."""
    workspace = _init_workspace(tmp_path)
    draft = propose(workspace, kind="create_part", params={
        "number": "P-000001", "name": "X",
    })
    draft.commit()
    with pytest.raises(TransactionError, match="committed"):
        modify(draft, kind="create_part", params={
            "number": "P-000002", "name": "Y",
        })


def test_phase_c_modify_after_rollback_raises(tmp_path: Path):
    """B3: modify on a rolled-back draft raises TransactionError."""
    workspace = _init_workspace(tmp_path)
    draft = propose(workspace, kind="create_part", params={
        "number": "P-000001", "name": "X",
    })
    rollback(draft)
    with pytest.raises(TransactionError, match="rolled_back|rolled back"):
        modify(draft, kind="create_part", params={
            "number": "P-000002", "name": "Y",
        })


# ---------------------------------------------------------------------------
# B4: provenance discipline (agent cannot self-attest as human)
# ---------------------------------------------------------------------------


def test_phase_c_agent_change_parameter_with_human_input_rejected(tmp_path: Path):
    """B4: propose(change_parameter, actor='agent') with human_input → TransactionError."""
    workspace = _init_workspace(tmp_path)
    _create_part_with_thickness(workspace)
    with pytest.raises(TransactionError, match="human_input|self-attest"):
        propose(workspace, kind="change_parameter", actor="agent", params={
            "obj_number": "P-000001",
            "parameter_id": "param_thickness",
            "new_value": 8.0,
            "rationale": "agent suggestion",
            "new_fact_provenance": {"category": "human_input"},
        })


def test_phase_c_human_change_parameter_with_human_input_allowed(tmp_path: Path):
    """B4: propose(change_parameter, actor='human') with human_input → OK."""
    workspace = _init_workspace(tmp_path)
    _create_part_with_thickness(workspace)
    draft = propose(workspace, kind="change_parameter", actor="human", params={
        "obj_number": "P-000001",
        "parameter_id": "param_thickness",
        "new_value": 8.0,
        "rationale": "operator-measured",
        "new_fact_provenance": {"category": "human_input"},
    })
    draft.commit()
    _, entry = find_reservation_entry_by_number(workspace, "P-000001")
    sidecar = load_sidecar(workspace, entry["object_uuid"])
    assert sidecar["parameter"][0]["fact_provenance"]["category"] == "human_input"


def test_phase_c_agent_change_parameter_with_ai_proposal_allowed(tmp_path: Path):
    """B4: propose(change_parameter, actor='agent') with ai_proposal → OK."""
    workspace = _init_workspace(tmp_path)
    _create_part_with_thickness(workspace)
    draft = propose(workspace, kind="change_parameter", actor="agent", params={
        "obj_number": "P-000001",
        "parameter_id": "param_thickness",
        "new_value": 8.0,
        "rationale": "ai analysis suggests tighter tolerance",
        "new_fact_provenance": {"category": "ai_proposal"},
    })
    draft.commit()
    _, entry = find_reservation_entry_by_number(workspace, "P-000001")
    sidecar = load_sidecar(workspace, entry["object_uuid"])
    assert sidecar["parameter"][0]["fact_provenance"]["category"] == "ai_proposal"


def test_phase_c_modify_change_parameter_inherits_actor_check(tmp_path: Path):
    """B4: modify also enforces B4 — agent cannot promote human_input via the
    modify path either."""
    workspace = _init_workspace(tmp_path)
    _create_part_with_thickness(workspace, number="P-000002", name="Other")
    draft = propose(workspace, kind="create_part", params={
        "number": "P-000001", "name": "Bracket",
        "extra_namespaces": {
            "parameter": [{
                "id": "param_thickness", "name": "t", "datatype": "number",
                "unit": "mm", "value": 5,
                "fact_provenance": {"category": "human_input"},
            }],
        },
    })
    with pytest.raises(TransactionError, match="human_input|self-attest"):
        modify(draft, kind="change_parameter", actor="agent", params={
            "obj_number": "P-000001",
            "parameter_id": "param_thickness",
            "new_value": 6.0,
            "rationale": "no",
            "new_fact_provenance": {"category": "human_input"},
        })


def test_phase_c_invalid_actor_rejected_at_propose(tmp_path: Path):
    """Invalid actor → ValueError at propose entry point."""
    workspace = _init_workspace(tmp_path)
    with pytest.raises(ValueError, match="actor"):
        propose(workspace, kind="create_part", actor="bot", params={
            "number": "P-000001", "name": "X",
        })


def test_phase_c_invalid_actor_rejected_at_modify(tmp_path: Path):
    """Invalid actor → ValueError at modify entry point."""
    workspace = _init_workspace(tmp_path)
    draft = propose(workspace, kind="create_part", params={
        "number": "P-000001", "name": "X",
    })
    with pytest.raises(ValueError, match="actor"):
        modify(draft, kind="create_part", actor="agentic", params={
            "number": "P-000002", "name": "Y",
        })


# ---------------------------------------------------------------------------
# Unknown kind handling
# ---------------------------------------------------------------------------


def test_phase_c_propose_unknown_kind_raises_value_error(tmp_path: Path):
    workspace = _init_workspace(tmp_path)
    # arc 20260601-1: dispatch unified to _resolve_propose_handler;
    # message changed from "Unknown propose kind" to "Unknown kind".
    with pytest.raises(ValueError, match="Unknown kind"):
        propose(workspace, kind="totally_made_up", params={})


def test_phase_c_modify_unknown_kind_raises_value_error(tmp_path: Path):
    workspace = _init_workspace(tmp_path)
    draft = propose(workspace, kind="create_part", params={
        "number": "P-000001", "name": "X",
    })
    # arc 20260601-1: dispatch unified to _resolve_propose_handler;
    # message changed from "Unknown modify kind" to "Unknown kind".
    with pytest.raises(ValueError, match="Unknown kind"):
        modify(draft, kind="totally_made_up", params={})


# ---------------------------------------------------------------------------
# Per-kind smoke tests
# ---------------------------------------------------------------------------


def test_phase_c_propose_each_create_kind(tmp_path: Path):
    """Smoke: each of the 5 create_* kinds produces a committed Object."""
    workspace = _init_workspace(tmp_path)
    cases = [
        ("create_part", "P-000001"),
        ("create_requirement", "REQ-000001"),
        ("create_test_procedure", "TST-000001"),
        ("create_test_execution", "TEX-000001"),
        ("create_evidence_artifact", "EVD-000001"),
    ]
    for kind, number in cases:
        draft = propose(workspace, kind=kind, params={
            "number": number, "name": f"obj-{number}",
            "extra_namespaces": _minimal_extra_for(kind, workspace),
        })
        draft.commit()
        assert find_reservation_entry_by_number(workspace, number) is not None


def test_phase_c_propose_link_satisfies(tmp_path: Path):
    workspace = _init_workspace(tmp_path)
    propose(workspace, kind="create_part", params={
        "number": "P-000001", "name": "B",
    }).commit()
    propose(workspace, kind="create_requirement", params={
        "number": "REQ-000001", "name": "R",
        "extra_namespaces": _minimal_extra_for("create_requirement"),
    }).commit()
    draft = propose(workspace, kind="link_satisfies", params={
        "source_number": "P-000001", "target_number": "REQ-000001",
    })
    draft.commit()


def test_phase_c_propose_release_standalone(tmp_path: Path):
    """Smoke: propose(kind='release') works as a standalone Transaction.

    Uses a non-final stage so the V&V chain validation (which requires the
    full TestExecution→produces→Evidence→cites→Req chain) does not fire —
    the focus here is the propose dispatch path, not stage validation.
    """
    workspace = _init_workspace(tmp_path)
    propose(workspace, kind="create_part", params={
        "number": "P-000001", "name": "B",
    }).commit()
    propose(workspace, kind="create_requirement", params={
        "number": "REQ-000001", "name": "R",
        "extra_namespaces": _minimal_extra_for("create_requirement"),
    }).commit()
    draft = propose(workspace, kind="release", params={
        "object_numbers": ["P-000001", "REQ-000001"],
        "release_label": "rev-A-non-final",
        "stage_number": 1,
        "final_stage": False,
    })
    draft.commit()


# ---------------------------------------------------------------------------
# CLI delegation unchanged behavior
# ---------------------------------------------------------------------------


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "aiadra_core.cli", *args],
        capture_output=True, text=True,
    )


def test_phase_c_cli_init_unchanged_behavior(tmp_path: Path):
    """CLI init still works after Phase C delegation through protocol.propose."""
    workspace = tmp_path / "ws_cli_init"
    result = _cli("init", str(workspace))
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert (workspace / ".aiadra" / "schemas.yaml").exists()


def test_phase_c_cli_create_part_unchanged_behavior(tmp_path: Path):
    workspace = tmp_path / "ws"
    assert _cli("init", str(workspace)).returncode == 0
    result = _cli("create-part", str(workspace), "P-000001", "Bracket")
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert find_reservation_entry_by_number(workspace, "P-000001") is not None


def test_phase_c_cli_change_parameter_human_input_allowed(tmp_path: Path):
    """B4 + CLI delegation: the CLI passes actor='human' so a human operator
    MAY attest fact_provenance.category=human_input via the CLI path. The
    same propose call with actor='agent' from Python would be rejected."""
    workspace = tmp_path / "ws"
    assert _cli("init", str(workspace)).returncode == 0
    # Create a Part with a parameter via Python helper (no CLI for parameters)
    _create_part_with_thickness(workspace)
    result = _cli(
        "change-parameter", str(workspace),
        "P-000001", "param_thickness", "8.5", "operator-measured",
        "--provenance-category", "human_input",
    )
    assert result.returncode == 0, f"stderr={result.stderr}"
    _, entry = find_reservation_entry_by_number(workspace, "P-000001")
    sidecar = load_sidecar(workspace, entry["object_uuid"])
    assert sidecar["parameter"][0]["fact_provenance"]["category"] == "human_input"


def test_phase_c_cli_no_pin_exits_3(tmp_path: Path):
    """CLI propose-delegation path still exits 3 on missing pin (no init)."""
    workspace = tmp_path / "ws_no_pin"
    workspace.mkdir()
    result = _cli("create-part", str(workspace), "P-000001", "X")
    assert result.returncode == 3
    assert "project pin" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Migrator v0.25.0 → v0.26.0 chain
# ---------------------------------------------------------------------------


def test_phase_c_bundle_v0_26_0_registered():
    """The v0.26.0 bundle ships in the registry with a non-empty digest."""
    bundle = BundleRegistry().bundle("0.26.0")
    assert bundle.bundle_version == "0.26.0"
    assert bundle.bundle_digest.startswith("sha256:")
    assert len(bundle.bundle_digest) > len("sha256:")


def test_phase_c_migration_step_25_to_26_registered():
    """A MigrationStep advancing 0.25.0 → 0.26.0 is in REGISTERED_STEPS."""
    pairs = [(s.from_version, s.to_version) for s in REGISTERED_STEPS]
    assert ("0.25.0", "0.26.0") in pairs


def test_phase_c_chain_migration_to_v0_26_0(tmp_path: Path):
    """Walking the chain from v0.19.0 → v0.26.0 succeeds via apply_migration.

    Per Phase 3 W3: chain-aware migrator; pin-only steps are byte-identical
    except for the project pin.
    """
    workspace = tmp_path / "ws_mig"
    workspace.mkdir()
    aiadra_dir = workspace / ".aiadra"
    aiadra_dir.mkdir()
    v019 = BundleRegistry().bundle("0.19.0")
    (aiadra_dir / "schemas.yaml").write_text(
        f'"bundle_version": "{v019.bundle_version}"\n'
        f'"bundle_digest": "{v019.bundle_digest}"\n',
        encoding="utf-8",
    )
    plan = apply_migration(workspace, "0.26.0")
    assert plan.from_bundle_version == "0.19.0"
    assert plan.to_bundle_version == "0.26.0"
    # Pin file now reflects v0.26.0
    pin_text = (aiadra_dir / "schemas.yaml").read_text(encoding="utf-8")
    assert '"bundle_version": "0.26.0"' in pin_text


def test_phase_c_cli_migrate_includes_v0_26_0_choice(tmp_path: Path):
    """CLI --to-bundle choices include 0.26.0 (help text + actual choice)."""
    result = _cli("migrate", str(tmp_path / "nope"), "--to-bundle", "0.26.0", "--dry-run")
    # Exit nonzero because workspace has no pin, but the ARG was accepted
    # (vs. exit 2 with "invalid choice" if 0.26.0 weren't in choices)
    assert "invalid choice" not in (result.stderr or "")


# ---------------------------------------------------------------------------
# Codex2 B1 absorption (arc 20260531-9): proposed-state B6 scan
# ---------------------------------------------------------------------------
#
# Composable `modify()` can stage a Fixed execution binding AND a mutation of
# the bound target in the same draft. The per-op `_mutation_prohibition_hook`
# only walked committed disk state, so it could not catch this. The new
# proposed-state scan in `TransactionDraft.validate()` runs over committed +
# staged events and rejects the violation BEFORE writes hit disk.


def _setup_tst_and_tex(workspace: Path) -> None:
    """Create a TestProcedure with a parameter + a TestExecution. Both must
    exist on disk so the composability test can link them."""
    propose(workspace, kind="create_test_procedure", params={
        "number": "TST-000001", "name": "T",
        "extra_namespaces": {
            "test_procedure": {"title": "T", "verification_method": "test"},
            "attachment": [_seed_attachment(
                workspace, b"TST seed", "att_tst_seed",
                media_type="application/pdf",
            )],
            "parameter": [{
                "id": "param_dur", "name": "duration",
                "datatype": "number", "unit": "s", "value": 60,
            }],
        },
    }).commit()
    propose(workspace, kind="create_test_execution", params={
        "number": "TEX-000001", "name": "TX",
        "extra_namespaces": _minimal_extra_for("create_test_execution", workspace),
    }).commit()


def test_codex2_b1_link_then_mutate_in_same_draft_rejected(tmp_path: Path):
    """Codex2 B1: link_executes (Fixed) + change_parameter on the bound target
    in ONE draft must raise RevisionBindingError at draft.validate(), BEFORE
    any writes hit disk. The proposed-state scan walks committed + staged
    events; the staged binding precedes the staged mutation, so the rule
    fires."""
    from aiadra_core.validation.binding import RevisionBindingError

    workspace = _init_workspace(tmp_path)
    _setup_tst_and_tex(workspace)

    draft = propose(workspace, kind="link_executes", params={
        "source_number": "TEX-000001", "target_number": "TST-000001",
    })
    modify(draft, kind="change_parameter", params={
        "obj_number": "TST-000001",
        "parameter_id": "param_dur",
        "new_value": 70.0,
        "rationale": "tweak after binding (should be rejected)",
    })
    with pytest.raises(RevisionBindingError, match="proposed-state|Codex2 B1"):
        draft.validate()


def test_codex2_b1_mutate_then_link_in_same_draft_allowed(tmp_path: Path):
    """Codex2 B1 contrapositive: mutation BEFORE binding in the same draft
    remains allowed — the binding pins the post-mutation revision."""
    workspace = _init_workspace(tmp_path)
    _setup_tst_and_tex(workspace)

    draft = propose(workspace, kind="change_parameter", params={
        "obj_number": "TST-000001",
        "parameter_id": "param_dur",
        "new_value": 70.0,
        "rationale": "tweak before binding (allowed)",
    })
    modify(draft, kind="link_executes", params={
        "source_number": "TEX-000001", "target_number": "TST-000001",
    })
    draft.validate()  # should NOT raise
    draft.commit()


def test_codex2_b1_disk_binding_then_staged_mutation_still_caught(tmp_path: Path):
    """Codex2 B1 covers the disk-binding case too: scan walks committed +
    staged so an on-disk Fixed binding still triggers when a staged mutation
    targets it. The per-op `_mutation_prohibition_hook` already catches this
    case before the new draft-level scan runs, but both raise the same
    RevisionBindingError — belt-and-suspenders."""
    from aiadra_core.validation.binding import RevisionBindingError

    workspace = _init_workspace(tmp_path)
    _setup_tst_and_tex(workspace)
    # Commit the binding to disk in a prior Transaction
    propose(workspace, kind="link_executes", params={
        "source_number": "TEX-000001", "target_number": "TST-000001",
    }).commit()
    # Now stage a mutation on the bound target in a fresh draft
    with pytest.raises(RevisionBindingError):
        d = propose(workspace, kind="change_parameter", params={
            "obj_number": "TST-000001",
            "parameter_id": "param_dur",
            "new_value": 80.0,
            "rationale": "post-binding tweak (rejected)",
        })
        d.validate()


# ---------------------------------------------------------------------------
# Codex2 non-blocking: lifecycle regressions
# ---------------------------------------------------------------------------


def test_phase_c_second_commit_raises(tmp_path: Path):
    """Codex2 non-blocking: a second commit() on the same draft raises
    TransactionError via _assert_open('commit')."""
    workspace = _init_workspace(tmp_path)
    draft = propose(workspace, kind="create_part", params={
        "number": "P-000001", "name": "X",
    })
    draft.commit()
    with pytest.raises(TransactionError, match="committed"):
        draft.commit()


def test_phase_c_commit_after_rollback_raises(tmp_path: Path):
    """Codex2 non-blocking: commit() after rollback() raises."""
    workspace = _init_workspace(tmp_path)
    draft = propose(workspace, kind="create_part", params={
        "number": "P-000001", "name": "X",
    })
    rollback(draft)
    with pytest.raises(TransactionError, match="rolled_back|rolled back"):
        draft.commit()


def test_phase_c_rollback_after_commit_raises(tmp_path: Path):
    """Codex2 non-blocking: rollback() after commit() raises."""
    workspace = _init_workspace(tmp_path)
    draft = propose(workspace, kind="create_part", params={
        "number": "P-000001", "name": "X",
    })
    draft.commit()
    with pytest.raises(TransactionError, match="committed"):
        rollback(draft)


def test_phase_c_rollback_after_rollback_raises(tmp_path: Path):
    """Codex2 non-blocking: rollback() is idempotent in the sense of state
    but a second call still raises (the lifecycle guard is symmetrical)."""
    workspace = _init_workspace(tmp_path)
    draft = propose(workspace, kind="create_part", params={
        "number": "P-000001", "name": "X",
    })
    rollback(draft)
    with pytest.raises(TransactionError, match="rolled_back|rolled back"):
        rollback(draft)
