"""delete_object tests — ADR/0004 SCN terminal `deleted` lifecycle
(arc 20260728-3; Codex2 SIGNOFF build contract; bundle v0.30.0; core 0.18.0).

Floors:
- B1: terminal Reservation tombstone (status=deleted; three tombstone fields
  REQUIRED; current_revision_id FORBIDDEN; Number/UUID never reused);
  `object_deleted` event; typed `ObjectDeletedError` lookup (deleted ≠ unknown).
- B2: two-graph referential-integrity scan (candidate as source AND endpoint,
  all relationship types, working sidecars + cumulative released Revision
  graph); refusal-only v1 with the structured, deterministically-sorted
  blocker list; honest copy (no invented remediation).
- B3: ONE Transaction / ONE Git commit staging the event + tombstone +
  sidecar REMOVAL; dual-fold agreement; deliberate sidecar absence; rollback
  restores nothing (nothing was written); vault bytes preserved.
- N1: standalone kind — modify(kind='delete_object') rejected AND a
  delete-rooted draft cannot be extended.
- N2: mechanical identity agreement — event payload, tombstone, and absent
  sidecar agree on uuid / number / transaction id / reason / deletion time.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from aiadra_core.protocol import (
    DeletionBlockedError,
    ObjectDeletedError,
    ObjectNotFoundError,
    TransactionError,
    commit,
    inspect,
    modify,
    modify_kinds,
    propose,
    propose_kinds,
    query,
)
from aiadra_core.transaction.boundary import TransactionKind
from aiadra_core.transaction.operations import _scan_deletion_blockers
from aiadra_core.truth_model.reservation import (
    find_reservation_entry_by_number,
    load_reservation,
)
from aiadra_core.truth_model.sidecar import (
    list_working_sidecar_uuids,
    working_sidecar_path,
)
from aiadra_core.validation.bundle_registry import BundleRegistry
from aiadra_core.validation.fold import validate_fold


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_REQ_EXTRAS = {
    "requirement": {
        "statement": {"text": "shall hold", "language": "en", "format": "freeform"},
        "category": "functional",
    },
}


def _tex_extras(workspace: Path) -> dict:
    """Minimal valid TestExecution extras (attachment-bearing: needs a seeded
    vault attachment + a measured parameter; same pattern as
    test_phase_c_propose_modify._minimal_extra_for)."""
    from aiadra_core.vault.local_fs import LocalFSVaultAdapter
    vault = LocalFSVaultAdapter(workspace)
    content_hash, vault_path = vault.store(b"INSTRON LOG seed")
    return {
        "test_execution": {
            "executed_on_date": "2026-07-28",
            "execution_status": "completed",
        },
        "attachment": [{
            "id": "att_tex_seed", "role": "source_authoring",
            "content_hash": content_hash, "vault_path": vault_path,
            "media_type": "text/csv",
        }],
        "parameter": [{
            "id": "param_measured", "name": "measured_value",
            "datatype": "number", "unit": "mm", "value": 7.0,
            "fact_provenance": {
                "category": "measured",
                "derived_from": ["attachment:att_tex_seed"],
            },
        }],
    }


def _init_workspace(tmp_path: Path, name: str = "ws") -> Path:
    workspace = tmp_path / name
    propose(workspace, kind="init", params={}).commit()
    return workspace


def _create_part(workspace: Path, number: str = "P-000001", name: str = "Bracket") -> str:
    propose(workspace, kind="create_part", params={
        "number": number, "name": name,
    }).commit()
    _, entry = find_reservation_entry_by_number(workspace, number)
    return entry["object_uuid"]


def _read_events(workspace: Path) -> list[dict]:
    lines = (workspace / "events.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _bundle_dir(workspace: Path) -> Path:
    return BundleRegistry().bundle_for_pin(workspace).bundle_dir


# ---------------------------------------------------------------------------
# B1 + B3 + N2: happy path — one atomic Transaction, mechanical identity
# ---------------------------------------------------------------------------


def test_delete_happy_path_tombstone_event_removal_agree(tmp_path: Path):
    ws = _init_workspace(tmp_path)
    uuid = _create_part(ws)

    draft = propose(ws, kind="delete_object", params={
        "obj_number": "P-000001", "reason": "authoring mistake",
    })
    result = commit(draft)
    assert result.event_ids  # the object_deleted event committed

    # Tombstone (B1).
    reservation = load_reservation(ws, "P")
    tomb = reservation["reservations"]["P-000001"]
    assert tomb["status"] == "deleted"
    assert "current_revision_id" not in tomb
    assert tomb["object_uuid"] == uuid
    assert tomb["deletion_reason"] == "authoring mistake"
    assert tomb["deleted_by_transaction"] == result.transaction_id

    # Event (B1) — last event is object_deleted with full identity.
    event = _read_events(ws)[-1]
    assert event["event_type"] == "object_deleted"
    payload = event["payload"]
    assert payload["object_type"] == "Part"
    assert payload["detached_attachments"] == []
    assert payload["detached_vault_refs"] == []

    # N2 mechanical identity agreement: event ↔ tombstone on uuid / number /
    # transaction / reason / time, with the sidecar ABSENT.
    assert payload["uuid"] == tomb["object_uuid"] == uuid
    assert payload["number"] == "P-000001"
    assert event["transaction_id"] == tomb["deleted_by_transaction"]
    assert payload["deletion_reason"] == tomb["deletion_reason"]
    assert event["timestamp"] == tomb["deleted_at"]
    assert not working_sidecar_path(ws, uuid).exists()
    assert uuid not in list_working_sidecar_uuids(ws)

    # Read-side fold + absence invariant hold post-deletion (B3).
    validate_fold(ws, _bundle_dir(ws))

    # ONE Git commit carrying tombstone + event + sidecar REMOVAL (B3).
    show = subprocess.run(
        ["git", "-C", str(ws), "show", "--name-status", "--format=%s", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "delete-object P-000001" in show
    assert "M\tReservations/P.yaml" in show
    assert "M\tevents.jsonl" in show
    assert f"D\trevisions/{uuid}/working.yaml" in show


def test_deleted_lookup_is_typed_and_distinct_from_unknown(tmp_path: Path):
    ws = _init_workspace(tmp_path)
    uuid = _create_part(ws)
    commit(propose(ws, kind="delete_object", params={
        "obj_number": "P-000001", "reason": "cleanup",
    }))

    # Number lookup → ObjectDeletedError carrying the tombstone metadata.
    with pytest.raises(ObjectDeletedError) as exc_info:
        inspect(ws, "P-000001")
    err = exc_info.value
    assert err.number == "P-000001"
    assert err.uuid == uuid
    assert err.deletion_reason == "cleanup"
    assert err.deleted_by_transaction.startswith("tx_")

    # UUID lookup → same typed error (deleted ≠ unknown).
    with pytest.raises(ObjectDeletedError):
        inspect(ws, uuid)

    # Genuinely unknown refs stay ObjectNotFoundError.
    with pytest.raises(ObjectNotFoundError):
        inspect(ws, "P-000999")

    # query excludes deleted Objects naturally (no sidecar exists).
    assert [v for v in query(ws) if v.object_number == "P-000001"] == []


def test_number_and_uuid_never_reused_after_deletion(tmp_path: Path):
    ws = _init_workspace(tmp_path)
    _create_part(ws)
    commit(propose(ws, kind="delete_object", params={
        "obj_number": "P-000001", "reason": "cleanup",
    }))
    # The Number remains permanently reserved — re-allocation refused.
    with pytest.raises(TransactionError):
        propose(ws, kind="create_part", params={
            "number": "P-000001", "name": "Impostor",
        })
    # Deleting again refuses with the already-deleted message.
    with pytest.raises(TransactionError, match="already deleted"):
        propose(ws, kind="delete_object", params={
            "obj_number": "P-000001", "reason": "again",
        })


# ---------------------------------------------------------------------------
# B2: referential-integrity scan
# ---------------------------------------------------------------------------


def test_scan_blocks_candidate_as_source(tmp_path: Path):
    ws = _init_workspace(tmp_path)
    _create_part(ws)
    propose(ws, kind="create_requirement", params={
        "number": "REQ-000001", "name": "Load",
        "extra_namespaces": _REQ_EXTRAS,
    }).commit()
    propose(ws, kind="link_satisfies", params={
        "source_number": "P-000001", "target_number": "REQ-000001",
    }).commit()

    with pytest.raises(DeletionBlockedError) as exc_info:
        propose(ws, kind="delete_object", params={
            "obj_number": "P-000001", "reason": "x",
        })
    blockers = exc_info.value.blockers
    assert len(blockers) == 1
    b = blockers[0]
    assert b["relationship_type"] == "satisfies"
    assert b["candidate_role"] == "source"
    assert b["state"] == "working"
    assert b["source_object"]["number"] == "P-000001"
    assert "revision_id" not in b
    # Honest copy: names the future design, promises nothing (B2).
    assert "relationship_retired" in str(exc_info.value)
    assert "future" in str(exc_info.value)


def test_scan_blocks_candidate_as_endpoint(tmp_path: Path):
    """executed_on (TestExecution → Part, Fixed) puts the Part in the
    ENDPOINT role — the scan must catch incoming references too."""
    ws = _init_workspace(tmp_path)
    _create_part(ws)
    propose(ws, kind="create_test_execution", params={
        "number": "TEX-000001", "name": "Run 1",
        "extra_namespaces": _tex_extras(ws),
    }).commit()
    propose(ws, kind="link_executed_on", params={
        "source_number": "TEX-000001", "target_number": "P-000001",
    }).commit()

    with pytest.raises(DeletionBlockedError) as exc_info:
        propose(ws, kind="delete_object", params={
            "obj_number": "P-000001", "reason": "x",
        })
    blockers = exc_info.value.blockers
    assert len(blockers) == 1
    b = blockers[0]
    assert b["relationship_type"] == "executed_on"
    assert b["candidate_role"] == "endpoint"
    assert b["state"] == "working"
    assert b["source_object"]["number"] == "TEX-000001"


def test_scan_covers_cumulative_released_revision_graph(tmp_path: Path):
    """Released references are permanently blocking. The released branch is
    exercised directly on `_scan_deletion_blockers` (defense-in-depth: with
    current v1 types + release dependency closure, a candidate passing the v1
    gates cannot yet appear in a released Revision — future types/ops can)."""
    ws = _init_workspace(tmp_path)
    _create_part(ws)
    propose(ws, kind="create_requirement", params={
        "number": "REQ-000001", "name": "Load",
        "extra_namespaces": _REQ_EXTRAS,
    }).commit()
    propose(ws, kind="link_satisfies", params={
        "source_number": "P-000001", "target_number": "REQ-000001",
    }).commit()
    propose(ws, kind="release", params={
        "object_numbers": ["P-000001", "REQ-000001"],
        "release_label": "rev-A",
        "stage_number": 1,
        "final_stage": False,
    }).commit()

    _, req_entry = find_reservation_entry_by_number(ws, "REQ-000001")
    req_uuid = req_entry["object_uuid"]
    blockers = _scan_deletion_blockers(ws, req_uuid)
    states = {(b["state"], b["candidate_role"]) for b in blockers}
    # REQ is endpoint of the satisfies record BOTH in the working sidecar and
    # in P-000001's released Revision content.
    assert ("working", "endpoint") in states
    assert ("released", "endpoint") in states
    released = [b for b in blockers if b["state"] == "released"]
    assert all(b["revision_id"] for b in released)
    # Deterministic order per Codex2 N2: (type, source number, id, state, rev).
    keys = [(b["relationship_type"], b["source_object"]["number"],
             b["relationship_id"], b["state"], b.get("revision_id", ""))
            for b in blockers]
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# v1 gates
# ---------------------------------------------------------------------------


def test_v1_gate_part_only(tmp_path: Path):
    ws = _init_workspace(tmp_path)
    propose(ws, kind="create_requirement", params={
        "number": "REQ-000001", "name": "Load",
        "extra_namespaces": _REQ_EXTRAS,
    }).commit()
    with pytest.raises(TransactionError, match="only Parts"):
        propose(ws, kind="delete_object", params={
            "obj_number": "REQ-000001", "reason": "x",
        })


def test_v1_gate_released_part_refused(tmp_path: Path):
    ws = _init_workspace(tmp_path)
    _create_part(ws)
    propose(ws, kind="release", params={
        "object_numbers": ["P-000001"],
        "release_label": "rev-A",
        "stage_number": 1,
        "final_stage": False,
    }).commit()
    with pytest.raises(TransactionError, match="released"):
        propose(ws, kind="delete_object", params={
            "obj_number": "P-000001", "reason": "x",
        })


def test_gate_unknown_and_empty_reason(tmp_path: Path):
    ws = _init_workspace(tmp_path)
    _create_part(ws)
    with pytest.raises(TransactionError, match="not found"):
        propose(ws, kind="delete_object", params={
            "obj_number": "P-000999", "reason": "x",
        })
    with pytest.raises(TransactionError, match="reason"):
        propose(ws, kind="delete_object", params={
            "obj_number": "P-000001", "reason": "   ",
        })


# ---------------------------------------------------------------------------
# N1: standalone kind
# ---------------------------------------------------------------------------


def test_delete_object_rejected_from_modify(tmp_path: Path):
    ws = _init_workspace(tmp_path)
    _create_part(ws)
    draft = propose(ws, kind="create_part", params={
        "number": "P-000002", "name": "Plate",
    })
    with pytest.raises(TransactionError, match="STANDALONE"):
        modify(draft, kind="delete_object", params={
            "obj_number": "P-000001", "reason": "x",
        })
    draft.rollback(reason="test cleanup")


def test_delete_rooted_draft_cannot_be_extended(tmp_path: Path):
    ws = _init_workspace(tmp_path)
    _create_part(ws)
    draft = propose(ws, kind="delete_object", params={
        "obj_number": "P-000001", "reason": "cleanup",
    })
    assert draft.kind == TransactionKind.DELETE_OBJECT.value
    with pytest.raises(TransactionError, match="Cannot extend a delete_object"):
        modify(draft, kind="create_part", params={
            "number": "P-000002", "name": "Plate",
        })
    draft.rollback(reason="test cleanup")


def test_kind_catalogues(tmp_path: Path):
    assert "delete_object" in propose_kinds()
    assert "delete_object" not in modify_kinds()


# ---------------------------------------------------------------------------
# B3: atomicity — rollback leaves the workspace untouched; staging exclusion
# ---------------------------------------------------------------------------


def test_rollback_of_delete_draft_leaves_object_intact(tmp_path: Path):
    ws = _init_workspace(tmp_path)
    uuid = _create_part(ws)
    draft = propose(ws, kind="delete_object", params={
        "obj_number": "P-000001", "reason": "changed my mind",
    })
    draft.rollback(reason="operator abort")
    # Nothing was written: sidecar present, reservation still current.
    assert working_sidecar_path(ws, uuid).exists()
    _, entry = find_reservation_entry_by_number(ws, "P-000001")
    assert entry["status"] == "current"
    inspect(ws, "P-000001")  # resolves normally


def test_stage_sidecar_delete_mutual_exclusion(tmp_path: Path):
    ws = _init_workspace(tmp_path)
    uuid = _create_part(ws)
    draft = propose(ws, kind="delete_object", params={
        "obj_number": "P-000001", "reason": "cleanup",
    })
    # Deletion already staged → a write for the same uuid must refuse.
    with pytest.raises(TransactionError, match="mutual"):
        draft.stage_sidecar(uuid, {"object": {}})
    # And the reverse direction on a manually-assembled draft.
    draft.rollback(reason="test cleanup")
    from aiadra_core.transaction.boundary import TransactionDraft
    bundle = BundleRegistry().bundle_for_pin(ws)
    manual = TransactionDraft(workspace=ws, bundle=bundle,
                              kind="delete_object", transaction_id="tx_0099")
    manual.stage_sidecar(uuid, {"object": {}})
    with pytest.raises(TransactionError, match="mutual"):
        manual.stage_sidecar_delete(uuid)


def test_vault_bytes_preserved_and_detached_refs_recorded(tmp_path: Path):
    """Vault is content-addressed and shared-by-hash — deletion never GCs."""
    ws = _init_workspace(tmp_path)
    _create_part(ws)
    vault_dir = ws / "vault"
    before = sorted(p.name for p in vault_dir.iterdir()) if vault_dir.exists() else []
    commit(propose(ws, kind="delete_object", params={
        "obj_number": "P-000001", "reason": "cleanup",
    }))
    after = sorted(p.name for p in vault_dir.iterdir()) if vault_dir.exists() else []
    assert after == before  # no vault entry created or removed


# ---------------------------------------------------------------------------
# Schema floors — bundle v0.30.0
# ---------------------------------------------------------------------------


def test_bundle_0_30_0_tombstone_schema_floors(tmp_path: Path):
    from aiadra_core.validation.bundle_registry import SchemaValidationError
    bundle = BundleRegistry().bundle("0.30.0")

    base_entry = {
        "object_uuid": "0193ffff-0000-4000-8000-000000000001",
        "allocated_at": "2026-07-28T00:00:00Z",
        "allocated_by_transaction": "tx_0001",
    }

    def _reservation(entry: dict) -> dict:
        return {
            "schema_version": "0.30.0",
            "artifact_kind": "reservation",
            "discriminator": "P",
            "name": "aiadra-reservation-P",
            "status": "active",
            "reservations": {"P-000001": entry},
        }

    bundle.validate(_reservation({
        **base_entry, "status": "deleted",
        "deleted_at": "2026-07-28T00:00:01Z",
        "deleted_by_transaction": "tx_0002",
        "deletion_reason": "cleanup",
    }), "reservation", "P")  # tombstone validates

    # Missing tombstone fields → schema refusal.
    with pytest.raises(SchemaValidationError):
        bundle.validate(_reservation({**base_entry, "status": "deleted"}),
                        "reservation", "P")

    # current_revision_id FORBIDDEN on a tombstone.
    with pytest.raises(SchemaValidationError):
        bundle.validate(_reservation({
            **base_entry, "status": "deleted",
            "deleted_at": "2026-07-28T00:00:01Z",
            "deleted_by_transaction": "tx_0002",
            "deletion_reason": "cleanup",
            "current_revision_id": "0193ffff-0000-4000-8000-00000000000f",
        }), "reservation", "P")


def test_delete_refused_under_pre_0_30_0_pin(tmp_path: Path):
    """The AIADRAWork poisoning regression (2026-07-28): a workspace pinned to
    a bundle that predates object_deleted must refuse at PROPOSE with the
    migrate remedy — never stamp artifacts its own bundle cannot validate
    (which poisons every subsequent event-log read)."""
    ws = _init_workspace(tmp_path)
    _create_part(ws)
    digest = json.loads(
        (BundleRegistry().bundle("0.29.0").bundle_dir / "_digest.json").read_text(encoding="utf-8")
    )["bundle_digest"]
    pin = ws / ".aiadra" / "schemas.yaml"
    pin.write_text(
        f'"bundle_version": "0.29.0"\n"bundle_digest": "{digest}"\n', encoding="utf-8",
    )
    with pytest.raises(TransactionError, match="0.30.0"):
        propose(ws, kind="delete_object", params={
            "obj_number": "P-000001", "reason": "x",
        })
    # Nothing was stamped: the log still reads clean end-to-end.
    validate_fold(ws, BundleRegistry().bundle("0.29.0").bundle_dir)


def test_migration_chain_reaches_0_30_0(tmp_path: Path):
    from aiadra_core.validation.migration import REGISTERED_STEPS
    versions = [(s.from_version, s.to_version) for s in REGISTERED_STEPS]
    assert ("0.29.0", "0.30.0") in versions
