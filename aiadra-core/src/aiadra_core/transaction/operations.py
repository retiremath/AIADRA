"""Transaction operations per ADR/0025 §1 Phase 1 implementation.

One module per family was Claude2's design proposal; Phase 1 lands a single
consolidated module to keep cross-operation invariants (B6 mutation prohibition,
N3 reservation integrity, rev_id allocation) in one place. Future refactor
can split by responsibility once the Phase 1 surface stabilizes.

Operations:
- init_workspace(workspace, bundle) — INIT
- create_object(workspace, bundle, type, number, ...) — CREATE_OBJECT
- change_parameter(workspace, bundle, obj_number, param_id, new_value, rationale) — CHANGE_PARAMETER
- link_relationship(workspace, bundle, rel_type, source_number, target_number) — LINK_RELATIONSHIP
- attach_file(workspace, bundle, obj_number, path, role, att_id) — ATTACH_FILE
- release(workspace, bundle, object_numbers, stage_number, final_stage, prior_stage_ref, release_label) — RELEASE
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import mimetypes
import uuid as _uuid
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import UUID

from ..truth_model.event_log import (
    event_log_path,
    last_event_id_and_hash,
    next_event_id,
    next_transaction_id,
)
from ..truth_model.reservation import (
    find_reservation_entry_by_number,
    find_reservation_entry_by_uuid,
    list_reservation_prefixes,
    load_reservation,
)
from ..truth_model.revision import revision_path
from ..truth_model.sidecar import (
    list_working_sidecar_uuids,
    load_sidecar,
    working_sidecar_path,
)
from ..validation.binding import (
    EXECUTION_INSTANCE_TYPES,
    RevisionBindingError,
    is_revision_bound,
    find_mutation_after_binding_violations,
)
from ..validation.bundle_registry import BundleHandle, BundleRegistry
from ..validation.release import (
    ReleaseConsistencyError,
    ReleaseDraft,
    validate_attachment_integrity,
    validate_attachment_lineage,
    validate_final_stage_cardinality,
    validate_final_stage_threshold_checks,
    validate_final_stage_vv_chain_integrity,
    validate_release_draft,
    validate_stage_dependency_closure,
)
from ..validation.reservation_integrity import (
    ReservationIntegrityError,
    validate_reservation_rev_id_history,
)
from ..validation.schema import (
    load_reservation_validated,
    load_sidecar_validated,
)
from .boundary import (
    CommitError,
    CommitResult,
    DeletionBlockedError,
    TransactionDraft,
    TransactionError,
    TransactionKind,
)


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _next_uuid() -> str:
    return str(_uuid.uuid4())


def _prefix_for_type(obj_type: str) -> str:
    return {
        "Part": "P",
        "Requirement": "REQ",
        "TestProcedure": "TST",
        "TestExecution": "TEX",
        "EvidenceArtifact": "EVD",
    }[obj_type]


def _next_event_id_in_draft(workspace: Path, draft: TransactionDraft, bundle_dir: Path) -> str:
    """Allocate next evt_NNNN considering both on-disk events AND staged events."""
    base = next_event_id(workspace, bundle_dir)
    n = int(base[len("evt_"):])
    n += len([e for e in draft.events if "event_id" in e])
    return f"evt_{n:04d}"


# -----------------------------------------------------------------------------
# Phase C (arc 20260531-9) Codex1 B1 absorption: draft-aware read helpers.
# Operations that participate in `modify` MUST resolve state from the draft's
# staged writes FIRST (creating an Object then mutating it within the same
# Transaction must see the staged reservation + sidecar, not stale disk).
# -----------------------------------------------------------------------------


def _find_reservation_entry_by_number_with_draft(
    workspace: Path, draft: TransactionDraft | None, number: str,
) -> tuple[str, dict[str, Any]] | None:
    """Like `find_reservation_entry_by_number` but checks `draft.reservation_writes`
    first. Returns (prefix, entry) for the latest known state.
    """
    if draft is not None:
        for prefix, reservation in draft.reservation_writes.items():
            entries = reservation.get("reservations", {}) or {}
            if number in entries:
                return prefix, entries[number]
    return find_reservation_entry_by_number(workspace, number)


def _load_sidecar_with_draft(
    workspace: Path, draft: TransactionDraft | None, obj_uuid: str,
) -> dict[str, Any]:
    """Like `load_sidecar` but returns the staged sidecar from `draft.sidecar_writes`
    if present, allowing intra-Transaction mutations to read prior staged state.
    """
    if draft is not None and obj_uuid in draft.sidecar_writes:
        return deepcopy(draft.sidecar_writes[obj_uuid])
    return load_sidecar(workspace, obj_uuid)


def _load_reservation_with_draft(
    workspace: Path, draft: TransactionDraft | None, prefix: str,
) -> dict[str, Any]:
    """Like `load_reservation` but returns the staged reservation from
    `draft.reservation_writes` if present.
    """
    if draft is not None and prefix in draft.reservation_writes:
        return deepcopy(draft.reservation_writes[prefix])
    return load_reservation(workspace, prefix)


def _begin_or_extend_draft(
    workspace: Path,
    bundle: BundleHandle,
    kind: TransactionKind,
    existing_draft: TransactionDraft | None,
) -> TransactionDraft:
    """Helper to either return the existing draft (modify path) or create
    a fresh one (propose / standalone path). When extending, the caller
    inherits transaction_id from the existing draft; when standalone, a
    fresh transaction_id is allocated. Per Codex1 B1+B3 absorption: in the
    extending case, asserts the draft is still open (terminal-state guard)."""
    if existing_draft is not None:
        existing_draft._assert_open("modify")
        return existing_draft
    transaction_id = next_transaction_id(workspace, bundle.bundle_dir)
    return TransactionDraft(
        workspace=workspace, bundle=bundle, kind=kind,
        transaction_id=transaction_id,
    )


# -----------------------------------------------------------------------------
# B6 mutation prohibition hook (added to draft.pre_validate_hooks for mutating ops)
# -----------------------------------------------------------------------------


def _mutation_prohibition_hook(workspace: Path, bundle_dir: Path, target_uuids: list[str]):
    def hook(draft: TransactionDraft) -> None:
        for uuid in target_uuids:
            entry = find_reservation_entry_by_uuid(workspace, uuid)
            if entry is None:
                continue
            _, _, res_entry = entry
            current_rev_id = res_entry.get("current_revision_id")
            if not current_rev_id:
                continue
            if is_revision_bound(workspace, bundle_dir, uuid, current_rev_id):
                raise RevisionBindingError(
                    f"B6 mutation prohibition: Object {uuid} has unreleased "
                    f"current_revision_id {current_rev_id!r} bound by Fixed "
                    f"execution-instance relationship; mutation Transaction rejected. "
                    f"Release the Object first, then mutate (a fresh "
                    f"current_revision_id will be allocated)."
                )
    return hook


# -----------------------------------------------------------------------------
# INIT
# -----------------------------------------------------------------------------


def init_workspace(workspace: Path, bundle: BundleHandle) -> TransactionDraft:
    """Initialize a new workspace: create directory structure + initialize git +
    stage project pin + empty Reservations for the 5 Object Type prefixes in
    the Transaction draft.

    Per B10 absorption arc 20260531-2 round-5: project pin is STAGED in the
    draft (not written outside the Transaction) so commit captures it in
    the init commit AND the no-writes-before-validate contract is preserved.

    `git init` runs BEFORE the draft is built (needed so subsequent
    `git add`/`git commit` work); it is a non-AIADRA-managed filesystem
    setup, not an AIADRA Transaction write.
    """
    import subprocess

    workspace.mkdir(parents=True, exist_ok=True)

    if not (workspace / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=workspace, check=False)
        # Local git config so subsequent commits work even when global config is absent.
        subprocess.run(
            ["git", "-c", f"safe.directory={workspace.resolve().as_posix()}",
             "-C", str(workspace), "config", "user.email", "aiadra@workspace.local"],
            check=False,
        )
        subprocess.run(
            ["git", "-c", f"safe.directory={workspace.resolve().as_posix()}",
             "-C", str(workspace), "config", "user.name", "AIADRA Core"],
            check=False,
        )

    draft = TransactionDraft(
        workspace=workspace,
        bundle=bundle,
        kind=TransactionKind.INIT,
        transaction_id="tx_0001",
    )
    # Stage project pin per B10 absorption (not a plain filesystem write).
    pin_text = (
        f'"bundle_version": "{bundle.bundle_version}"\n'
        f'"bundle_digest": "{bundle.bundle_digest}"\n'
    )
    draft.stage_project_pin(pin_text)
    # Empty Reservations for the 5 prefixes
    for prefix in ("P", "REQ", "TST", "TEX", "EVD"):
        empty_res = {
            "artifact_kind": "reservation",
            "discriminator": prefix,
            "name": f"aiadra-reservation-{prefix}",
            "reservations": {},
            "schema_version": bundle.bundle_version,
            "status": "active",
        }
        draft.stage_reservation(prefix, empty_res)
    draft.commit_message_lines = [f"aiadra: init workspace (bundle v{bundle.bundle_version})"]
    return draft


# -----------------------------------------------------------------------------
# CREATE OBJECT
# -----------------------------------------------------------------------------


def create_object(
    workspace: Path,
    bundle: BundleHandle,
    obj_type: str,
    number: str,
    name: str,
    *,
    uuid: str | None = None,
    revision_id: str | None = None,
    extra_namespaces: dict[str, Any] | None = None,
    existing_draft: TransactionDraft | None = None,
) -> TransactionDraft:
    """Create an Object: allocate Number + UUID + current_revision_id; emit
    `<type>_created` event with initial_sidecar.

    Phase C (arc 20260531-9) Codex1 B1 absorption: accepts optional
    `existing_draft` for composable propose+modify. When provided: inherits
    transaction_id; allocates event_id via `_next_event_id_in_draft`;
    checks for Number collisions via `_load_reservation_with_draft`
    (staged-aware); appends to `commit_message_lines` instead of replacing.
    """
    prefix = _prefix_for_type(obj_type)
    obj_uuid = uuid or _next_uuid()
    rev_id = revision_id or _next_uuid()
    draft = _begin_or_extend_draft(workspace, bundle, TransactionKind.CREATE_OBJECT, existing_draft)
    transaction_id = draft.transaction_id
    event_id = _next_event_id_in_draft(workspace, draft, bundle.bundle_dir)

    # Initial sidecar
    sidecar = {
        "object": {
            "uuid": obj_uuid,
            "number": number,
            "type": obj_type,
            "name": name,
            "lifecycle": "in_work",
            "schema_version": bundle.bundle_version,
        },
    }
    if extra_namespaces:
        sidecar.update(deepcopy(extra_namespaces))

    # Validate sidecar shape early
    bundle.validate(sidecar, "sidecar", obj_type)

    # Reservation update (allocate Number + UUID + current_revision_id) — B1 draft-aware
    res = _load_reservation_with_draft(workspace, draft, prefix)
    if number in res.get("reservations", {}):
        raise TransactionError(f"Number {number} already reserved in {prefix}.yaml")
    res.setdefault("reservations", {})[number] = {
        "allocated_at": _now_iso(),
        "allocated_by_transaction": transaction_id,
        "object_uuid": obj_uuid,
        "status": "current",
        "current_revision_id": rev_id,
    }

    # <type>_created event
    event_type = f"{obj_type.lower()}_created"
    event_type = {
        "part_created":             "part_created",
        "requirement_created":      "requirement_created",
        "testprocedure_created":    "test_procedure_created",
        "testexecution_created":    "test_execution_created",
        "evidenceartifact_created": "evidence_artifact_created",
    }[obj_type.lower() + "_created"]
    event = {
        "schema_version": bundle.bundle_version,
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": _now_iso(),
        "transaction_id": transaction_id,
        "payload": {
            "uuid": obj_uuid,
            "number": number,
            "initial_sidecar": sidecar,
        },
    }

    draft.stage_sidecar(obj_uuid, sidecar)
    draft.stage_event(event)
    draft.stage_reservation(prefix, res)
    _msg_lines = [
        f"aiadra: create-{obj_type.lower().replace('execution','-execution').replace('procedure','-procedure').replace('artifact','-artifact')} {number}",
        "",
        f"Transaction {transaction_id} created {obj_type} {number} (uuid {obj_uuid}).",
        f"Allocated current_revision_id {rev_id} per B3 absorption.",
    ]
    if existing_draft is None:
        draft.commit_message_lines = _msg_lines
    else:
        if draft.commit_message_lines:
            draft.commit_message_lines.append("")  # separator
        draft.commit_message_lines.extend(_msg_lines)
    return draft


# -----------------------------------------------------------------------------
# CHANGE PARAMETER
# -----------------------------------------------------------------------------


def change_parameter(
    workspace: Path,
    bundle: BundleHandle,
    obj_number: str,
    parameter_id: str,
    new_value: float,
    rationale: str,
    *,
    new_fact_provenance: dict[str, Any] | None = None,
    actor: str = "agent",
    existing_draft: TransactionDraft | None = None,
) -> TransactionDraft:
    """Mutate a parameter value. B6 mutation prohibition runs in validate-phase.

    Per F1 absorption Phase 2 (arc 20260531-3): if `new_fact_provenance` is
    provided, the proposed sidecar's parameter has its `fact_provenance` dict
    replaced wholesale AND the `parameter_changed` event payload carries the
    new dict. If `None`, both the sidecar's fact_provenance and the event
    payload omit the field (Phase 1 backward-compat).

    Phase C (arc 20260531-9) Codex1 B1+B4 absorption:
      - `existing_draft`: optional composable extension (B1 draft-aware).
      - `actor`: discipline boundary per ADR/0026 §5 (B4). When `actor="agent"`
        (default) and `new_fact_provenance.category == "human_input"`, raises
        ValueError — AI agents MUST NOT self-attest as human_input. The CLI
        binding layer that knows the operator is a human passes `actor="human"`.
    """
    # B4 provenance discipline at the propose/operation boundary
    if (actor == "agent"
            and new_fact_provenance is not None
            and new_fact_provenance.get("category") == "human_input"):
        raise TransactionError(
            "AI proposals cannot self-attest as new_fact_provenance.category="
            "'human_input' per ADR/0026 §5 (Codex1 B4 absorption arc 20260531-9). "
            "Use 'ai_proposal' or 'computed_result' or 'measured'. "
            "CLI bindings that know the operator is a human pass actor='human'."
        )
    if actor not in ("agent", "human"):
        raise ValueError(
            f"Invalid actor {actor!r}; expected 'agent' or 'human'."
        )

    found = _find_reservation_entry_by_number_with_draft(workspace, existing_draft, obj_number)
    if found is None:
        raise TransactionError(f"Object not found: {obj_number}")
    _, entry = found
    obj_uuid = entry["object_uuid"]
    sidecar = _load_sidecar_with_draft(workspace, existing_draft, obj_uuid)
    # Apply mutation to draft sidecar
    new_sidecar = deepcopy(sidecar)
    old_value = None
    for p in new_sidecar.get("parameter", []):
        if p.get("id") == parameter_id:
            old_value = p.get("value")
            p["value"] = new_value
            if new_fact_provenance is not None:
                p["fact_provenance"] = deepcopy(new_fact_provenance)
            break
    else:
        raise TransactionError(f"Parameter {parameter_id} not found on {obj_number}")

    draft = _begin_or_extend_draft(workspace, bundle, TransactionKind.CHANGE_PARAMETER, existing_draft)
    transaction_id = draft.transaction_id
    event_id = _next_event_id_in_draft(workspace, draft, bundle.bundle_dir)
    event_payload: dict[str, Any] = {
        "object_uuid": obj_uuid,
        "parameter_id": parameter_id,
        "old_value": old_value,
        "new_value": new_value,
        "rationale": rationale,
    }
    if new_fact_provenance is not None:
        event_payload["new_fact_provenance"] = deepcopy(new_fact_provenance)
    event = {
        "schema_version": bundle.bundle_version,
        "event_id": event_id,
        "event_type": "parameter_changed",
        "timestamp": _now_iso(),
        "transaction_id": transaction_id,
        "payload": event_payload,
    }

    draft.stage_sidecar(obj_uuid, new_sidecar)
    draft.stage_event(event)
    draft.pre_validate_hooks.append(
        _mutation_prohibition_hook(workspace, bundle.bundle_dir, [obj_uuid])
    )
    _msg_lines = [
        f"aiadra: change-parameter {obj_number} {parameter_id}={new_value}",
        "",
        f"Transaction {transaction_id} parameter {parameter_id} on {obj_number} "
        f"{old_value} → {new_value}. Rationale: {rationale}",
    ]
    if existing_draft is None:
        draft.commit_message_lines = _msg_lines
    else:
        if draft.commit_message_lines:
            draft.commit_message_lines.append("")
        draft.commit_message_lines.extend(_msg_lines)
    return draft


# -----------------------------------------------------------------------------
# ADD ACCEPTANCE CRITERION (Phase 4 F2 SCN arc 20260531-5)
# -----------------------------------------------------------------------------


def add_acceptance_criterion(
    workspace: Path,
    bundle: BundleHandle,
    req_number: str,
    criterion_id: str,
    criterion_text: str,
    *,
    language: str = "en",
    format: str = "freeform",
    threshold_expression: dict[str, Any] | None = None,
    verification_method: str | None = None,
    references: list[str] | None = None,
    name: str | None = None,
    existing_draft: TransactionDraft | None = None,
) -> TransactionDraft:
    """Append a new acceptance_criterion to a Requirement sidecar.

    Per Codex1 B1 absorption arc 20260531-5: emits a `requirement_changed`
    event with an `acceptance_criterion_delta.added` payload. Duplicate
    criterion id rejected at fold time (both read-side fold.py and
    proposed-state boundary._validate_proposed_fold).

    `threshold_expression`, if supplied, is the F2 canonical primitive per
    ADR/0025 §5: numeric-only, unit-REQUIRED, no free-text parsing. Layer-2
    evaluation runs at final-stage release.

    Phase C (arc 20260531-9) Codex1 B1 absorption: accepts optional
    `existing_draft` for composable propose+modify. When provided: inherits
    transaction_id; allocates event_id via `_next_event_id_in_draft`; reads
    Reservation + sidecar via `_..._with_draft` helpers; appends to
    `commit_message_lines` instead of replacing.
    """
    found = _find_reservation_entry_by_number_with_draft(workspace, existing_draft, req_number)
    if found is None:
        raise TransactionError(f"Object not found: {req_number}")
    _, entry = found
    obj_uuid = entry["object_uuid"]
    sidecar = _load_sidecar_with_draft(workspace, existing_draft, obj_uuid)
    if sidecar.get("object", {}).get("type") != "Requirement":
        raise TransactionError(
            f"add-acceptance-criterion target must be Requirement, "
            f"got {sidecar.get('object', {}).get('type')!r}"
        )

    # Build the new criterion item per shared schema shape.
    new_criterion: dict[str, Any] = {
        "id": criterion_id,
        "criterion": {
            "text": criterion_text,
            "language": language,
            "format": format,
        },
    }
    if name is not None:
        new_criterion["name"] = name
    if references is not None:
        new_criterion["references"] = list(references)
    if verification_method is not None:
        new_criterion["verification_method"] = verification_method
    if threshold_expression is not None:
        new_criterion["threshold_expression"] = deepcopy(threshold_expression)

    # Duplicate id check (cheap; full check happens at fold time too).
    existing_ids = {
        c.get("id") for c in sidecar.get("acceptance_criterion", []) if isinstance(c, dict)
    }
    if criterion_id in existing_ids:
        raise TransactionError(
            f"Criterion id {criterion_id!r} already exists on {req_number}"
        )

    new_sidecar = deepcopy(sidecar)
    new_sidecar.setdefault("acceptance_criterion", []).append(deepcopy(new_criterion))

    draft = _begin_or_extend_draft(
        workspace, bundle, TransactionKind.ADD_ACCEPTANCE_CRITERION, existing_draft,
    )
    transaction_id = draft.transaction_id
    event_id = _next_event_id_in_draft(workspace, draft, bundle.bundle_dir)
    event = {
        "schema_version": bundle.bundle_version,
        "event_id": event_id,
        "event_type": "requirement_changed",
        "timestamp": _now_iso(),
        "transaction_id": transaction_id,
        "payload": {
            "object_uuid": obj_uuid,
            "acceptance_criterion_delta": {
                "added": [deepcopy(new_criterion)],
            },
        },
    }

    draft.stage_sidecar(obj_uuid, new_sidecar)
    draft.stage_event(event)
    draft.pre_validate_hooks.append(
        _mutation_prohibition_hook(workspace, bundle.bundle_dir, [obj_uuid])
    )
    _msg_lines = [
        f"aiadra: add-acceptance-criterion {req_number} {criterion_id}",
        "",
        f"Transaction {transaction_id} appends criterion {criterion_id!r} "
        f"to Requirement {req_number}"
        + (f" with threshold_expression" if threshold_expression else "")
        + ".",
    ]
    if existing_draft is None:
        draft.commit_message_lines = _msg_lines
    else:
        if draft.commit_message_lines:
            draft.commit_message_lines.append("")
        draft.commit_message_lines.extend(_msg_lines)
    return draft


# -----------------------------------------------------------------------------
# LINK RELATIONSHIP
# -----------------------------------------------------------------------------


_RELATIONSHIP_DIRECTION = {
    # rel_type: (source_type_set, target_type_set, binding_default)
    "satisfies":         ({"Part", "Assembly"}, {"Requirement"}, "float"),
    "tested_against":    ({"Part", "Assembly"}, {"TestProcedure"}, "float"),
    "verifies":          ({"TestProcedure"}, {"Requirement"}, "float"),
    "cites":             ({"Requirement"}, {"EvidenceArtifact"}, "float"),
    "executes":          ({"TestExecution"}, {"TestProcedure"}, "fixed"),
    "executed_on":       ({"TestExecution"}, {"Part", "Assembly"}, "fixed"),
    "produces":          ({"TestExecution"}, {"EvidenceArtifact"}, "fixed"),
}


def link_relationship(
    workspace: Path,
    bundle: BundleHandle,
    rel_type: str,
    source_number: str,
    target_number: str,
    *,
    relationship_id: str | None = None,
    existing_draft: TransactionDraft | None = None,
) -> TransactionDraft:
    """Author a relationship on the source Object's sidecar. Execution-instance
    relationships (executes/executed_on/produces) are Fixed; endpoint
    revision_id read from target Object's Reservation current_revision_id
    (B3 absorption).

    Phase C (arc 20260531-9) Codex1 B1 absorption: accepts optional
    `existing_draft` for composable propose+modify. Source AND target are
    resolved against staged state first so a freshly-created Object in the
    same Transaction can be linked.
    """
    if rel_type not in _RELATIONSHIP_DIRECTION:
        raise TransactionError(f"Unknown relationship type: {rel_type}")
    src_types, tgt_types, default_binding = _RELATIONSHIP_DIRECTION[rel_type]

    src_found = _find_reservation_entry_by_number_with_draft(workspace, existing_draft, source_number)
    tgt_found = _find_reservation_entry_by_number_with_draft(workspace, existing_draft, target_number)
    if src_found is None:
        raise TransactionError(f"Source Object not found: {source_number}")
    if tgt_found is None:
        raise TransactionError(f"Target Object not found: {target_number}")
    src_uuid = src_found[1]["object_uuid"]
    tgt_uuid = tgt_found[1]["object_uuid"]

    src_sidecar = _load_sidecar_with_draft(workspace, existing_draft, src_uuid)
    tgt_sidecar = _load_sidecar_with_draft(workspace, existing_draft, tgt_uuid)
    src_type = src_sidecar["object"]["type"]
    tgt_type = tgt_sidecar["object"]["type"]

    if src_type not in src_types:
        raise TransactionError(
            f"Relationship {rel_type}: source type {src_type} not in {sorted(src_types)}"
        )
    if tgt_type not in tgt_types:
        raise TransactionError(
            f"Relationship {rel_type}: target type {tgt_type} not in {sorted(tgt_types)}"
        )

    # Build relationship record
    rel_id = relationship_id or f"rel_{rel_type}_{_next_uuid()[:8]}"
    binding = default_binding
    endpoint: dict[str, Any] = {"object_uuid": tgt_uuid}
    if binding == "fixed":
        # B3: read current_revision_id from target's Reservation (draft-aware)
        tgt_current_rev = tgt_found[1].get("current_revision_id")
        if not tgt_current_rev:
            raise TransactionError(
                f"Target {target_number} has no current_revision_id; cannot author Fixed binding"
            )
        endpoint["revision_id"] = tgt_current_rev
    relationship_record = {
        "id": rel_id,
        "type": rel_type,
        "binding": binding,
        "endpoints": [endpoint],
    }

    new_sidecar = deepcopy(src_sidecar)
    new_sidecar.setdefault("relationship", []).append(relationship_record)

    draft = _begin_or_extend_draft(
        workspace, bundle, TransactionKind.LINK_RELATIONSHIP, existing_draft,
    )
    transaction_id = draft.transaction_id
    event_id = _next_event_id_in_draft(workspace, draft, bundle.bundle_dir)
    event = {
        "schema_version": bundle.bundle_version,
        "event_id": event_id,
        "event_type": "relationship_created",
        "timestamp": _now_iso(),
        "transaction_id": transaction_id,
        "payload": {
            "source_uuid": src_uuid,
            "relationship_record": relationship_record,
        },
    }

    draft.stage_sidecar(src_uuid, new_sidecar)
    draft.stage_event(event)
    # B6: if this is an execution-instance Fixed binding, the TARGET gets bound.
    # Source mutation is OK (it's authoring a relationship). The B6 mutation
    # prohibition check applies to LATER mutations against the target.
    _msg_lines = [
        f"aiadra: link-{rel_type.replace('_', '-')} {source_number} {target_number}",
        f"",
        f"Transaction {transaction_id} authored {rel_type} from {source_number} → "
        f"{target_number} (binding {binding}).",
    ]
    if existing_draft is None:
        draft.commit_message_lines = _msg_lines
    else:
        if draft.commit_message_lines:
            draft.commit_message_lines.append("")
        draft.commit_message_lines.extend(_msg_lines)
    return draft


# -----------------------------------------------------------------------------
# ATTACH FILE
# -----------------------------------------------------------------------------


_ATTACHMENT_BEARING_TO_CHANGED_EVENT = {
    "Drawing":          "drawing_changed",
    "TestProcedure":    "test_procedure_changed",
    "TestExecution":    "test_execution_changed",
    "EvidenceArtifact": "evidence_artifact_changed",
}


def attach_file(
    workspace: Path,
    bundle: BundleHandle,
    obj_number: str,
    file_path: Path,
    role: str,
    *,
    attachment_id: str | None = None,
    derived_from_attachment_id: str | None = None,
    media_type: str | None = None,
    existing_draft: TransactionDraft | None = None,
) -> TransactionDraft:
    """Attach a file to an Attachment-bearing Object as a canonical Transaction.

    Per W2 absorption: emits `<type>_changed` event with `attachment_delta`.

    Phase C (arc 20260531-9) Codex1 B1 absorption: accepts optional
    `existing_draft` for composable propose+modify. Reservation + sidecar
    reads are draft-aware so a freshly-created Attachment-bearing Object
    can be modified within the same Transaction.
    """
    found = _find_reservation_entry_by_number_with_draft(workspace, existing_draft, obj_number)
    if found is None:
        raise TransactionError(f"Object not found: {obj_number}")
    _, entry = found
    obj_uuid = entry["object_uuid"]
    sidecar = _load_sidecar_with_draft(workspace, existing_draft, obj_uuid)
    obj_type = sidecar["object"]["type"]
    if obj_type not in _ATTACHMENT_BEARING_TO_CHANGED_EVENT:
        raise TransactionError(
            f"Object type {obj_type} is not Attachment-bearing; cannot attach-file"
        )

    file_path = Path(file_path)
    if not file_path.exists():
        raise TransactionError(f"File not found: {file_path}")
    data = file_path.read_bytes()
    content_hash = "sha256:" + hashlib.sha256(data).hexdigest()
    vault_path = f"vault/{content_hash[len('sha256:'):]}"
    media_type = media_type or mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    att_id = attachment_id or f"att_{file_path.stem.replace(' ', '_').lower()}"

    attachment_record = {
        "id": att_id,
        "role": role,
        "content_hash": content_hash,
        "vault_path": vault_path,
        "media_type": media_type,
    }
    if derived_from_attachment_id:
        attachment_record["derived_from_attachment_id"] = derived_from_attachment_id

    # Add to sidecar attachments
    new_sidecar = deepcopy(sidecar)
    new_sidecar.setdefault("attachment", []).append(attachment_record)

    draft = _begin_or_extend_draft(
        workspace, bundle, TransactionKind.ATTACH_FILE, existing_draft,
    )
    transaction_id = draft.transaction_id
    event_id = _next_event_id_in_draft(workspace, draft, bundle.bundle_dir)
    event_type = _ATTACHMENT_BEARING_TO_CHANGED_EVENT[obj_type]
    event = {
        "schema_version": bundle.bundle_version,
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": _now_iso(),
        "transaction_id": transaction_id,
        "payload": {
            "object_uuid": obj_uuid,
            "attachment_delta": {
                "operation": "add",
                "attachment_id": att_id,
                "attachment_record": attachment_record,
            },
        },
    }

    draft.stage_sidecar(obj_uuid, new_sidecar)
    draft.stage_event(event)
    # Vault bytes staged for write at commit time
    draft.stage_vault_bytes(data)
    # B6: attach-file is a mutation; check whether obj_uuid's current rev_id is bound
    draft.pre_validate_hooks.append(
        _mutation_prohibition_hook(workspace, bundle.bundle_dir, [obj_uuid])
    )
    _msg_lines = [
        f"aiadra: attach-file {obj_number} {att_id}",
        f"",
        f"Transaction {transaction_id} attached {file_path.name} to {obj_number} "
        f"as {att_id} (role={role}, content_hash={content_hash}).",
    ]
    if existing_draft is None:
        draft.commit_message_lines = _msg_lines
    else:
        if draft.commit_message_lines:
            draft.commit_message_lines.append("")
        draft.commit_message_lines.extend(_msg_lines)
    return draft


# -----------------------------------------------------------------------------
# RELEASE
# -----------------------------------------------------------------------------


def release(
    workspace: Path,
    bundle: BundleHandle,
    object_numbers: list[str],
    *,
    release_label: str | None = None,
    stage_number: int = 1,
    final_stage: bool = True,
    prior_stage_manifest_ref: dict[str, Any] | None = None,
) -> TransactionDraft:
    """Release a set of Objects. Per Decision §7: each stage IS a canonical
    Release Manifest. Per N6: appends released rev_id to released_revision_ids[]
    AND allocates fresh current_revision_id in the same Reservation update.
    """
    if not object_numbers:
        raise TransactionError("Release set is empty")

    transaction_id = next_transaction_id(workspace, bundle.bundle_dir)
    release_label = release_label or f"rev-{_now_iso().replace(':', '').replace('-', '')[:14]}"
    now = _now_iso()

    # Gather sidecars + Reservation updates
    revisions: list[dict[str, Any]] = []
    per_object_events: list[dict[str, Any]] = []
    released_uuids: list[str] = []
    reservation_updates_by_prefix: dict[str, dict[str, Any]] = {}

    draft = TransactionDraft(
        workspace=workspace, bundle=bundle, kind=TransactionKind.RELEASE,
        transaction_id=transaction_id,
    )

    event_counter = int(next_event_id(workspace, bundle.bundle_dir)[4:])

    for obj_number in object_numbers:
        found = find_reservation_entry_by_number(workspace, obj_number)
        if found is None:
            raise TransactionError(f"Object not found: {obj_number}")
        prefix, entry = found
        obj_uuid = entry["object_uuid"]
        rev_id = entry.get("current_revision_id")
        if not rev_id:
            raise TransactionError(
                f"Object {obj_number} has no current_revision_id; create-time allocation missing"
            )

        sidecar = load_sidecar_validated(workspace, obj_uuid)
        obj_type = sidecar["object"]["type"]
        # Revision content == sidecar content at release time
        revision_content = deepcopy(sidecar)

        # Pre-compute revision hash from yaml serialization (atomic_write_bytes will write same bytes)
        from ..validation.profile import dump_yaml
        rev_text = dump_yaml(revision_content)
        rev_bytes = rev_text.encode("utf-8")
        rev_hash = "sha256:" + hashlib.sha256(rev_bytes).hexdigest()

        draft.stage_revision(obj_uuid, rev_id, revision_content)

        revisions.append({
            "object_uuid": obj_uuid,
            "object_number": obj_number,
            "revision_id": rev_id,
            "revision_hash": rev_hash,
        })
        released_uuids.append(obj_uuid)

        # Per-Object <type>_released event
        released_event_type = {
            "Part": "part_released",
            "Requirement": "requirement_released",
            "TestProcedure": "test_procedure_released",
            "TestExecution": "test_execution_released",
            "EvidenceArtifact": "evidence_artifact_released",
        }[obj_type]
        event_counter += 1
        per_object_events.append({
            "schema_version": bundle.bundle_version,
            "event_id": f"evt_{event_counter:04d}",
            "event_type": released_event_type,
            "timestamp": now,
            "transaction_id": transaction_id,
            "payload": {
                "object_uuid": obj_uuid,
                "revision_id": rev_id,
                "revision_hash": rev_hash,
            },
        })
        draft.stage_event(per_object_events[-1])

        # Update Reservation per N6: append released_rev_id + allocate fresh current_revision_id
        if prefix not in reservation_updates_by_prefix:
            reservation_updates_by_prefix[prefix] = deepcopy(load_reservation(workspace, prefix))
        res = reservation_updates_by_prefix[prefix]
        res_entry = res["reservations"][obj_number]
        released_ids = res_entry.setdefault("released_revision_ids", [])
        if rev_id not in released_ids:
            released_ids.append(rev_id)
        res_entry["current_revision_id"] = _next_uuid()  # N6: fresh UUID after release

    for prefix, res in reservation_updates_by_prefix.items():
        draft.stage_reservation(prefix, res)

    # Build manifest. Per Phase 1 (this arc Claude4): event_log_boundary points
    # at the LAST <type>_released event (NOT release_staged) — the manifest is
    # sealed before release_staged is emitted as the post-release audit record.
    # This avoids the circular dependency (release_staged carries manifest_hash;
    # manifest carries event_log_boundary including release_staged would loop).
    last_released_event = per_object_events[-1]
    last_event_bytes = json.dumps(
        last_released_event, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    event_log_boundary = {
        "last_event_id": last_released_event["event_id"],
        "last_event_hash": "sha256:" + hashlib.sha256(last_event_bytes).hexdigest(),
    }

    # Per-Object schema_validation outcomes (always)
    validation_outcomes: list[dict[str, str]] = []
    for rev in revisions:
        validation_outcomes.append({
            "check_name": f"schema_validation({rev['object_number']})",
            "result": "PASS",
            "details": f"{rev['object_number']} Revision validates against bundle-resolved schema",
        })

    # Per B14/B15 absorption arc 20260531-2 round-6: build a PROTO ReleaseDraft
    # carrying proposed_revisions so the W1 validators see the authoritative
    # staged graph (NOT working sidecars). Run validators NOW (before manifest
    # hash sealing) so their outcomes go into manifest.validation_outcomes.
    proto_manifest = {
        "artifact_kind": "manifest",
        "manifest_type": "release",
        "release_label": release_label,
        "released_at": now,
        "schema_version": bundle.bundle_version,
        "revisions": revisions,
        "stage_number": stage_number,
        "final_stage": final_stage,
        "validation_outcomes": list(validation_outcomes),
        "event_log_boundary": event_log_boundary,
    }
    if prior_stage_manifest_ref:
        proto_manifest["prior_stage_manifest_ref"] = prior_stage_manifest_ref

    # Populate proposed_revisions for ReleaseDraft consumer (per B14)
    proposed_revisions = {
        (uuid, rev_id): content
        for (uuid, rev_id), content in draft.revision_writes.items()
    }
    proto_release_draft = ReleaseDraft(
        release_label=release_label,
        manifest=proto_manifest,
        manifest_hash="",  # not yet computed
        release_staged_event={"payload": {
            "released_object_uuids": released_uuids,
            "stage_number": stage_number,
            "final_stage": final_stage,
        }},
        per_object_released_events=per_object_events,
        reservation_updates=reservation_updates_by_prefix,
        proposed_revisions=proposed_revisions,
    )

    # B11: stage dependency closure (always; raises on violation)
    validate_stage_dependency_closure(workspace, bundle.bundle_dir, proto_release_draft)

    # B16 absorption arc 20260531-2 round-7: per-stage attachment integrity +
    # attachment lineage validation for Attachment-bearing Objects in THIS
    # release set. Prior-stage attachments were validated when their stage
    # was released. Outcomes baked into manifest per B15.
    integrity_outcomes = validate_attachment_integrity(
        workspace, bundle.bundle_dir, proto_release_draft,
    )
    validation_outcomes.extend(integrity_outcomes)
    lineage_outcomes = validate_attachment_lineage(
        workspace, bundle.bundle_dir, proto_release_draft,
    )
    validation_outcomes.extend(lineage_outcomes)

    # B11 + B13 + B15: final-stage validations APPEND outcomes to manifest
    if final_stage:
        cardinality_outcomes = validate_final_stage_cardinality(
            workspace, bundle.bundle_dir, proto_release_draft,
        )
        validation_outcomes.extend(cardinality_outcomes)
        vv_outcomes = validate_final_stage_vv_chain_integrity(
            workspace, bundle.bundle_dir, proto_release_draft,
        )
        validation_outcomes.extend(vv_outcomes)
        # F2 absorption Phase 4 arc 20260531-5: per ADR/0025 §5 threshold
        # checks run final-stage only (parallel to vv_chain + cardinality).
        # Unit mismatch → ReleaseConsistencyError (hard-fail). FAIL outcome
        # with a `satisfies`/`verifies` claim → ReleaseConsistencyError.
        # FAIL outcome without a claim → manifest carries FAIL diagnostic.
        threshold_outcomes = validate_final_stage_threshold_checks(
            workspace, bundle.bundle_dir, proto_release_draft,
        )
        validation_outcomes.extend(threshold_outcomes)

    # Build FINAL manifest with all outcomes baked in
    manifest = {
        "artifact_kind": "manifest",
        "manifest_type": "release",
        "release_label": release_label,
        "released_at": now,
        "schema_version": bundle.bundle_version,
        "revisions": revisions,
        "stage_number": stage_number,
        "final_stage": final_stage,
        "validation_outcomes": validation_outcomes,
        "event_log_boundary": event_log_boundary,
    }
    if prior_stage_manifest_ref:
        manifest["prior_stage_manifest_ref"] = prior_stage_manifest_ref

    manifest_bytes = serialize_manifest_inline(manifest)
    manifest_hash = "sha256:" + hashlib.sha256(manifest_bytes).hexdigest()

    draft.stage_manifest(release_label, manifest)

    # release_staged event — post-release audit record; references the sealed manifest
    event_counter += 1
    release_staged_event = {
        "schema_version": bundle.bundle_version,
        "event_id": f"evt_{event_counter:04d}",
        "event_type": "release_staged",
        "timestamp": now,
        "transaction_id": transaction_id,
        "payload": {
            "release_label": release_label,
            "manifest_hash": manifest_hash,
            "stage_number": stage_number,
            "final_stage": final_stage,
            "released_object_uuids": released_uuids,
        },
    }
    if prior_stage_manifest_ref:
        release_staged_event["payload"]["prior_stage_manifest_ref"] = prior_stage_manifest_ref
    draft.stage_event(release_staged_event)

    # N2 draft-mode release_staged consistency check (runs in validate phase).
    # The validators that PRODUCE outcomes (closure / cardinality / V&V) have
    # already run above and their outcomes are baked into manifest. The hook
    # below runs the cross-artifact consistency check (release_staged ↔
    # manifest hash, per-object events agree, etc.) — these don't produce
    # additional outcomes; they only validate.
    rd = ReleaseDraft(
        release_label=release_label,
        manifest=manifest,
        manifest_hash=manifest_hash,
        release_staged_event=release_staged_event,
        per_object_released_events=per_object_events,
        reservation_updates=reservation_updates_by_prefix,
        proposed_revisions=proposed_revisions,
    )

    def _release_validation_hook(draft_: TransactionDraft) -> None:
        validate_release_draft(workspace, bundle.bundle_dir, rd)

    draft.pre_validate_hooks.append(_release_validation_hook)

    # B8 absorption (Phase 1 round-5): final-release B6 scan against the
    # release-extended event history; N3 Reservation integrity replay.
    # Both checks run after schema validate completes but before commit.
    def _release_final_scans(draft_: TransactionDraft) -> None:
        # The proposed events are not yet on disk; B6 scan walks committed
        # history. The new events (relationship_created from THIS release
        # context don't exist; release_staged + <type>_released don't mutate
        # working state) so the scan against committed history is correct.
        violations = find_mutation_after_binding_violations(workspace, bundle.bundle_dir)
        if violations:
            raise RevisionBindingError(
                "B6 final-release scan caught mutation-after-binding violations:\n  - "
                + "\n  - ".join(violations)
            )
        # N3 invariants 1+3 (canonical state after we apply this release):
        # Invariant 2 (Fixed-endpoint resolution) is already enforced at
        # link-time in change_parameter/attach_file paths and at draft-build
        # in link_relationship. Invariants 1 and 3 are checked against the
        # proposed post-release Reservation state.
        for prefix, proposed_res in draft_.reservation_writes.items():
            for number, entry in proposed_res.get("reservations", {}).items():
                current = entry.get("current_revision_id")
                released = entry.get("released_revision_ids") or []
                if current and current in released:
                    raise ReservationIntegrityError(
                        f"N3 invariant 3 (post-release): Reservation {prefix}/{number} "
                        f"current_revision_id {current!r} appears in released_revision_ids[]"
                    )

    draft.post_validate_hooks.append(_release_final_scans)
    draft.commit_message_lines = [
        f"aiadra: release {release_label} stage={stage_number} final={final_stage}",
        f"",
        f"Transaction {transaction_id} released {len(object_numbers)} Object(s): "
        f"{', '.join(object_numbers)}.",
        f"Manifest hash {manifest_hash}.",
    ]
    return draft


def serialize_manifest_inline(manifest: dict[str, Any]) -> bytes:
    """Local helper — same as truth_model.manifest.serialize_manifest."""
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# -----------------------------------------------------------------------------
# DELETE OBJECT (ADR/0004 SCN arc 20260728-3; Codex2 SIGNOFF build contract)
# -----------------------------------------------------------------------------


def _uuid_to_number_map(workspace: Path) -> dict[str, str]:
    """Map object_uuid → its CURRENT Number (retired aliases only as fallback)."""
    mapping: dict[str, str] = {}
    fallback: dict[str, str] = {}
    for prefix in list_reservation_prefixes(workspace):
        reservation = load_reservation(workspace, prefix)
        for number, entry in (reservation.get("reservations", {}) or {}).items():
            uuid = entry.get("object_uuid")
            if not uuid:
                continue
            if entry.get("status") == "current":
                mapping[uuid] = number
            else:
                fallback.setdefault(uuid, number)
    for uuid, number in fallback.items():
        mapping.setdefault(uuid, number)
    return mapping


def _scan_deletion_blockers(workspace: Path, candidate_uuid: str) -> list[dict[str, Any]]:
    """B2 two-graph referential-integrity scan (arc 20260728-3).

    Checks the candidate as SOURCE and as ENDPOINT of every relationship, with
    no typed allowlist, across:
      1. ALL working sidecars (state="working"), and
      2. the cumulative RELEASED Revision graph — every revision named by any
         on-disk release manifest (state="released", permanently blocking).

    Returns the deterministic structured blocker list per Codex2 N2: sorted by
    (relationship_type, source number, relationship_id, state, revision_id),
    deduplicated on the full identity key.
    """
    from ..truth_model.manifest import list_release_labels, load_manifest
    from ..truth_model.revision import load_revision

    numbers = _uuid_to_number_map(workspace)
    seen: set[tuple[str, str, str, str, str, str]] = set()
    blockers: list[dict[str, Any]] = []

    def add(rel: dict[str, Any], source_uuid: str, role: str,
            state: str, revision_id: str | None) -> None:
        key = (
            str(rel.get("type", "")), numbers.get(source_uuid, ""),
            str(rel.get("id", "")), role, state, revision_id or "",
        )
        if key in seen:
            return
        seen.add(key)
        blocker: dict[str, Any] = {
            "relationship_id": rel.get("id", ""),
            "relationship_type": rel.get("type", ""),
            "source_object": {
                "uuid": source_uuid,
                "number": numbers.get(source_uuid, ""),
            },
            "candidate_role": role,
            "state": state,
        }
        if revision_id is not None:
            blocker["revision_id"] = revision_id
        blockers.append(blocker)

    def scan_content(source_uuid: str, content: dict[str, Any],
                     state: str, revision_id: str | None) -> None:
        for rel in content.get("relationship", []) or []:
            if not isinstance(rel, dict):
                continue
            if source_uuid == candidate_uuid:
                add(rel, source_uuid, "source", state, revision_id)
            for ep in rel.get("endpoints", []) or []:
                if isinstance(ep, dict) and ep.get("object_uuid") == candidate_uuid:
                    add(rel, source_uuid, "endpoint", state, revision_id)

    # 1. Working sidecars.
    for uuid in list_working_sidecar_uuids(workspace):
        try:
            sidecar = load_sidecar(workspace, uuid)
        except FileNotFoundError:
            continue
        scan_content(uuid, sidecar, "working", None)

    # 2. Cumulative released Revision graph (every manifest on disk).
    for label in list_release_labels(workspace):
        manifest = load_manifest(workspace, label)
        for rev in manifest.get("revisions", []) or []:
            obj_uuid = rev.get("object_uuid")
            rev_id = rev.get("revision_id")
            if not obj_uuid or not rev_id:
                continue
            try:
                content = load_revision(workspace, obj_uuid, rev_id)
            except FileNotFoundError:
                continue
            scan_content(obj_uuid, content, "released", rev_id)

    blockers.sort(key=lambda b: (
        b["relationship_type"], b["source_object"]["number"],
        b["relationship_id"], b["state"], b.get("revision_id", ""),
    ))
    return blockers


def delete_object(
    workspace: Path,
    bundle: BundleHandle,
    obj_number: str,
    *,
    reason: str,
    actor: str = "agent",
) -> TransactionDraft:
    """Delete a working Object (v1: Part with no released history).

    Per the arc-20260728-3 converged contract (Codex2 SIGNOFF):
      - STANDALONE Transaction (Codex1/Codex2 N1: no `existing_draft`
        parameter; `modify(kind="delete_object")` and extending a
        delete-rooted draft are rejected at the protocol layer).
      - Stages, atomically: the `object_deleted` event, the terminal
        Reservation tombstone (status=deleted, current_revision_id removed,
        the three tombstone fields added), and the working-sidecar REMOVAL.
      - B2 scan refuses on any live relationship reference (working or
        released) with the structured blocker list on `DeletionBlockedError`.
      - Vault bytes are PRESERVED; detached refs recorded on the event.
    """
    if actor not in ("agent", "human"):
        raise ValueError(f"Invalid actor {actor!r}; expected 'agent' or 'human'.")
    if not reason or not reason.strip():
        raise TransactionError("delete_object requires a non-empty reason.")

    found = find_reservation_entry_by_number(workspace, obj_number)
    if found is None:
        raise TransactionError(f"Object not found: {obj_number}")
    prefix, entry = found
    status = entry.get("status")
    if status == "deleted":
        raise TransactionError(
            f"Object {obj_number} is already deleted "
            f"(deleted_at {entry.get('deleted_at')!r}, "
            f"transaction {entry.get('deleted_by_transaction')!r})."
        )
    if status != "current":
        raise TransactionError(
            f"Number {obj_number} is a {status!r} alias; deletion targets the "
            f"Object's CURRENT Number."
        )
    obj_uuid = entry["object_uuid"]

    try:
        sidecar = load_sidecar(workspace, obj_uuid)
    except FileNotFoundError:
        raise TransactionError(
            f"Object {obj_number} has no working sidecar on disk; workspace "
            f"state is inconsistent — refusing to delete."
        )
    obj_type = sidecar.get("object", {}).get("type")
    if obj_type != "Part":
        raise TransactionError(
            f"delete_object v1 accepts only Parts; {obj_number} is {obj_type!r} "
            f"(arc 20260728-3 v1 gate)."
        )
    released = entry.get("released_revision_ids") or []
    if released:
        raise TransactionError(
            f"Object {obj_number} has released revision(s) {released}; released "
            f"Truth is permanent and its Objects cannot be deleted "
            f"(arc 20260728-3 v1 gate)."
        )

    # B2 referential-integrity scan. The candidate's own OUTGOING relationships
    # block too: deletion would silently destroy source-owned relationship
    # records rather than retire them.
    blockers = _scan_deletion_blockers(workspace, obj_uuid)
    if blockers:
        n = len(blockers)
        raise DeletionBlockedError(
            f"Deletion of {obj_number} refused: {n} live relationship "
            f"reference(s) involve it. AIADRA v1 has no relationship-retirement "
            f"operation; released references block permanently. "
            f"(`relationship_retired` is a named future design.)",
            blockers,
        )

    # Detached references (vault bytes preserved; recorded for the event).
    detached_attachments = [
        {"attachment_id": a.get("id", ""), "vault_ref": a.get("content_hash", "")}
        for a in sidecar.get("attachment", []) or []
        if isinstance(a, dict)
    ]
    detached_vault_refs = sorted({
        g["vault_ref"]
        for g in sidecar.get("geometry_ref", []) or []
        if isinstance(g, dict) and g.get("vault_ref")
    })

    draft = _begin_or_extend_draft(workspace, bundle, TransactionKind.DELETE_OBJECT, None)
    transaction_id = draft.transaction_id
    ts = _now_iso()  # ONE timestamp — event and tombstone must agree (Codex2 N2)

    # Terminal Reservation tombstone.
    reservation = load_reservation(workspace, prefix)
    new_reservation = deepcopy(reservation)
    tomb = new_reservation["reservations"][obj_number]
    tomb["status"] = "deleted"
    tomb.pop("current_revision_id", None)
    tomb["deleted_at"] = ts
    tomb["deleted_by_transaction"] = transaction_id
    tomb["deletion_reason"] = reason

    event_id = _next_event_id_in_draft(workspace, draft, bundle.bundle_dir)
    event = {
        "schema_version": bundle.bundle_version,
        "event_id": event_id,
        "event_type": "object_deleted",
        "timestamp": ts,
        "transaction_id": transaction_id,
        "actor": actor,
        "payload": {
            "object_type": "Part",
            "uuid": obj_uuid,
            "number": obj_number,
            "name": sidecar.get("object", {}).get("name", ""),
            "deletion_reason": reason,
            "detached_attachments": detached_attachments,
            "detached_vault_refs": detached_vault_refs,
        },
    }

    draft.stage_reservation(prefix, new_reservation)
    draft.stage_event(event)
    draft.stage_sidecar_delete(obj_uuid)
    draft.commit_message_lines = [
        f"aiadra: delete-object {obj_number}",
        "",
        f"Transaction {transaction_id} deleted {obj_number} ({obj_uuid}). "
        f"Reason: {reason}. Number and UUID remain permanently reserved; "
        f"vault bytes preserved.",
    ]
    return draft
