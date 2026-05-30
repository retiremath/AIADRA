"""CLI for Wedge-001 spike. `python -m wedge <subcommand> ...`

Subcommands per ADR/0023 worked invocation:
  init                       — create empty Reservations + events.jsonl + dirs
  create-part                — author a Part sidecar in working state
  create-requirement         — author a Requirement sidecar in working state
  link-satisfies             — add a satisfies relationship Part-side
  propose-parameter-change   — AI Transaction lifecycle (validate + maybe commit)
  release                    — materialize Revisions + write Release Manifest

Exit codes (per Design Decision H in Claude1):
  0  success
  1  rejected transaction (validation failure) — NO state change committed
  2  AIADRA YAML Profile violation
  3  schema validation failure
  5  sidecar/event invariant fold failure
  64 CLI argument error (argparse default)
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid as _uuid
from pathlib import Path

from . import SCHEMA_BUNDLE_VERSION, vault
from .event_log import last_event_id_and_hash, next_transaction_id
from .manifest import build_manifest, hash_bytes, serialize_manifest
from .sidecar import (
    ProfileViolationError,
    atomic_write_text,
    load_yaml,
    write_yaml_atomic,
)
from .transaction import (
    add_relationship,
    append_release_event,
    change_parameter,
    create_object,
    init_workspace,
    load_rev_id_map,
    manifest_path,
    materialize_revision,
    now_iso,
    reservation_path,
    sidecar_path,
)
from .validate import (
    AttachmentIntegrityError,
    ExecutionCardinalityError,
    FoldInconsistencyError,
    IntegrityError,
    SchemaValidationError,
    VVChainIntegrityError,
    load_reservation_validated,
    load_revision_validated,
    load_sidecar_validated,
    validate_against_schema,
    validate_attachment_lineage,
    validate_execution_cardinality,
    validate_fold,
    validate_satisfies,
    validate_v_and_v_chain_integrity,
    verify_attachment_integrity,
    verify_revision_hashes,
)


def _gen_uuid(provided: str | None) -> str:
    if provided:
        return provided
    return str(_uuid.uuid4())


def _resolve_number_to_uuid(workspace: Path, number: str) -> str:
    prefix = number.split("-", 1)[0]
    res = load_reservation_validated(reservation_path(workspace, prefix), prefix)
    entry = res["reservations"].get(number)
    if entry is None:
        raise ValueError(f"{number} not allocated in Reservations/{prefix}.yaml")
    if entry["status"] != "current":
        raise ValueError(f"{number} is retired; not resolvable to current Object")
    return entry["object_uuid"]


# ---------------------- subcommand handlers ----------------------


def cmd_init(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    rev_id_map: dict[str, str] = {}
    for pair in args.rev_id or []:
        if "=" not in pair:
            print(f"✗ --rev-id must be <obj-uuid>=<rev-uuid>", file=sys.stderr)
            return 64
        k, v = pair.split("=", 1)
        rev_id_map[k] = v
    init_workspace(workspace, rev_id_map=rev_id_map if rev_id_map else None)
    print(f"✓ Initialized workspace at {workspace}")
    print(f"  - Reservations/{{P,REQ,TST,TEX,EVD}}.yaml (empty)")
    print(f"  - events.jsonl (empty)")
    print(f"  - vault/ (empty)")
    if rev_id_map:
        print(f"  - .rev-id-map (spike-local non-canonical; {len(rev_id_map)} predeclared rev_id(s))")
    return 0


_MEDIA_TYPE_BY_EXT = {
    ".txt": "text/plain",
    ".md":  "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".yaml": "application/yaml",
    ".yml":  "application/yaml",
    ".pdf":  "application/pdf",
    ".log":  "text/plain",
}


def _attachments_staging_path(workspace: Path) -> Path:
    return workspace / ".attachments-staging.yaml"


def _load_attachments_staging(workspace: Path) -> dict[str, dict[str, str]]:
    path = _attachments_staging_path(workspace)
    if not path.exists():
        return {}
    data = load_yaml(path)
    return dict(data.get("attachments", {}))


def _save_attachments_staging(workspace: Path, attachments: dict[str, dict[str, str]]) -> None:
    """Persist attachment staging info (spike-local non-canonical helper —
    same posture as .rev-id-map per ADR/0024 §2.5 + Codex2 N2)."""
    data = {
        "name": "wedge-002-attachments-staging",
        "status": "active",
        "artifact_kind": "spike_local_attachments_staging",
        "attachments": dict(sorted(attachments.items())),
    }
    write_yaml_atomic(_attachments_staging_path(workspace), data)


def cmd_attach_file(args: argparse.Namespace) -> int:
    """Workspace/Vault helper per ADR/0024 §4 — copies bytes into content-
    addressed Vault and stages an attachment record (spike-local non-canonical)
    for subsequent create-* commands to reference by id. Emits NO canonical
    event per Codex1 B3 absorption (arc 20260530-2).
    """
    workspace = Path(args.workspace)
    source = Path(args.file)
    if not source.exists():
        print(f"✗ Source file not found: {source}", file=sys.stderr)
        return 64
    if args.role not in ("source_authoring", "rendered_primary", "derived_secondary"):
        print(f"✗ --role must be one of source_authoring | rendered_primary | derived_secondary", file=sys.stderr)
        return 64
    media_type = args.media_type or _MEDIA_TYPE_BY_EXT.get(source.suffix.lower(), "application/octet-stream")
    locator = vault.store_file(workspace, source)
    staging = _load_attachments_staging(workspace)
    staging[args.id] = {
        "role": args.role,
        "media_type": media_type,
        "content_hash": locator.content_hash,
        "vault_path": locator.vault_path,
    }
    _save_attachments_staging(workspace, staging)
    print(f"✓ Stored {source.name} in Vault")
    print(f"  - id:           {args.id}")
    print(f"  - role:         {args.role}")
    print(f"  - media_type:   {media_type}")
    print(f"  - content_hash: {locator.content_hash}")
    print(f"  - vault_path:   {locator.vault_path}")
    print(f"  (Staged in .attachments-staging.yaml; no canonical event emitted.)")
    return 0


def _attachment_record_from_staging(workspace: Path, att_id: str) -> dict[str, str]:
    staging = _load_attachments_staging(workspace)
    if att_id not in staging:
        raise ValueError(f"Attachment id {att_id!r} not found in staging; run `attach-file --id {att_id}` first")
    info = staging[att_id]
    return {
        "id":           att_id,
        "role":         info["role"],
        "media_type":   info["media_type"],
        "vault_path":   info["vault_path"],
        "content_hash": info["content_hash"],
    }


def cmd_create_test_procedure(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    obj_uuid = _gen_uuid(args.uuid)
    att = _attachment_record_from_staging(workspace, args.attachment)
    sidecar = {
        "object": {
            "uuid": obj_uuid,
            "number": args.number,
            "type": "TestProcedure",
            "name": args.name,
            "lifecycle": "in_work",
            "schema_version": SCHEMA_BUNDLE_VERSION,
        },
        "test_procedure": {
            "title": args.title or args.name,
            "verification_method": args.verification_method,
        },
        "attachment": [att],
    }
    try:
        validate_against_schema(sidecar, "object_test_procedure.schema.json")
    except SchemaValidationError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 3
    tx_id, evt_id = create_object(workspace, sidecar, "TST", "test_procedure_created")
    print(f"✓ Allocated {args.number} in Reservations/TST.yaml")
    print(f"✓ Wrote revisions/{obj_uuid}/working.yaml (attachment {att['id']})")
    print(f"✓ Appended test_procedure_created event to events.jsonl ({evt_id})")
    _check_fold(workspace)
    return 0


def _parse_parameter_with_lineage(arg: str) -> dict[str, object]:
    """Parse `name=value:from=attachment:att_id` into a parameter record with
    fact_provenance.derived_from lineage per ADR/0019 §4 / ADR/0022 §11 lineage discipline."""
    if ":from=" not in arg:
        raise ValueError(
            f"--parameter must be name=value:from=attachment:att_id; got {arg!r}"
        )
    name_value, from_part = arg.split(":from=", 1)
    if "=" not in name_value:
        raise ValueError(f"--parameter must include name=value; got {name_value!r}")
    pname, pvalue_str = name_value.split("=", 1)
    pvalue = float(pvalue_str) if "." in pvalue_str else int(pvalue_str)
    if not from_part.startswith("attachment:"):
        raise ValueError(f"--parameter lineage must be 'attachment:att_id'; got {from_part!r}")
    unit = pname.rsplit("_", 1)[-1] if "_" in pname else ""
    record: dict[str, object] = {
        "id": f"param_{pname}",
        "name": pname,
        "value": pvalue,
        "datatype": "number",
        "fact_provenance": {
            "category": "measured",
            "derived_from": [from_part],
        },
    }
    if unit:
        record["unit"] = unit
    return record


def cmd_create_test_execution(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    obj_uuid = _gen_uuid(args.uuid)
    att = _attachment_record_from_staging(workspace, args.attachment)
    try:
        param = _parse_parameter_with_lineage(args.parameter)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 64
    sidecar = {
        "object": {
            "uuid": obj_uuid,
            "number": args.number,
            "type": "TestExecution",
            "name": args.name or f"TestExecution {args.number}",
            "lifecycle": "in_work",
            "schema_version": SCHEMA_BUNDLE_VERSION,
        },
        "test_execution": {
            "executed_on_date": args.executed_on_date,
            "execution_status": args.execution_status,
        },
        "parameter": [param],
        "attachment": [att],
    }
    if args.operator_identifier:
        sidecar["test_execution"]["operator_identifier"] = args.operator_identifier
    if args.instrument_identifier:
        sidecar["test_execution"]["instrument_identifier"] = args.instrument_identifier
    try:
        validate_against_schema(sidecar, "object_test_execution.schema.json")
    except SchemaValidationError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 3
    tx_id, evt_id = create_object(workspace, sidecar, "TEX", "test_execution_created")
    print(f"✓ Allocated {args.number} in Reservations/TEX.yaml")
    print(f"✓ Wrote revisions/{obj_uuid}/working.yaml (attachment {att['id']}; parameter lineage to {att['id']})")
    print(f"✓ Appended test_execution_created event to events.jsonl ({evt_id})")
    _check_fold(workspace)
    return 0


def cmd_create_evidence_artifact(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    obj_uuid = _gen_uuid(args.uuid)
    att = _attachment_record_from_staging(workspace, args.attachment)
    try:
        param = _parse_parameter_with_lineage(args.parameter)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 64
    sidecar = {
        "object": {
            "uuid": obj_uuid,
            "number": args.number,
            "type": "EvidenceArtifact",
            "name": args.name or f"EvidenceArtifact {args.number}",
            "lifecycle": "in_work",
            "schema_version": SCHEMA_BUNDLE_VERSION,
        },
        "evidence": {
            "summary": args.summary,
            "evidence_kind": args.evidence_kind,
        },
        "parameter": [param],
        "attachment": [att],
    }
    try:
        validate_against_schema(sidecar, "object_evidence_artifact.schema.json")
    except SchemaValidationError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 3
    tx_id, evt_id = create_object(workspace, sidecar, "EVD", "evidence_artifact_created")
    print(f"✓ Allocated {args.number} in Reservations/EVD.yaml")
    print(f"✓ Wrote revisions/{obj_uuid}/working.yaml (attachment {att['id']}; parameter lineage to {att['id']})")
    print(f"✓ Appended evidence_artifact_created event to events.jsonl ({evt_id})")
    _check_fold(workspace)
    return 0


def _link_float_relationship(
    args: argparse.Namespace,
    rel_type: str,
    schema_name: str,
    fact_ref_field: str | None = None,
    source_fact_ref_field: str | None = None,
) -> int:
    """Helper for design-intent (Float-default) V&V relationships."""
    workspace = Path(args.workspace)
    src_uuid = _resolve_number_to_uuid(workspace, args.source)
    tgt_uuid = _resolve_number_to_uuid(workspace, args.target)
    rec: dict[str, object] = {
        "id": f"rel_{rel_type}_{args.target.lower().replace('-', '_')}",
        "type": rel_type,
        "binding": "float",
        "endpoints": [{"object_uuid": tgt_uuid}],
        "fact_provenance": {"category": "human_input"},
    }
    if fact_ref_field and getattr(args, "target_criterion", None):
        rec["endpoints"][0][fact_ref_field] = f"acceptance_criterion:{args.target_criterion}"
    if source_fact_ref_field and getattr(args, "source_criterion", None):
        rec[source_fact_ref_field] = f"acceptance_criterion:{args.source_criterion}"
    try:
        validate_against_schema(rec, schema_name)
    except SchemaValidationError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 3
    tx_id, evt_id = add_relationship(workspace, src_uuid, rec)
    print(f"✓ Updated revisions/{src_uuid}/working.yaml relationship: list (rel_{rel_type}_*)")
    print(f"✓ Appended relationship_created event to events.jsonl ({evt_id})")
    _check_fold(workspace)
    return 0


def cmd_link_tested_against(args: argparse.Namespace) -> int:
    return _link_float_relationship(args, "tested_against", "relationship_tested_against.schema.json")


def cmd_link_verifies(args: argparse.Namespace) -> int:
    return _link_float_relationship(
        args, "verifies", "relationship_verifies.schema.json", fact_ref_field="fact_ref"
    )


def cmd_link_cites(args: argparse.Namespace) -> int:
    return _link_float_relationship(
        args, "cites", "relationship_cites.schema.json", source_fact_ref_field="source_fact_ref"
    )


def _link_fixed_execution_relationship(
    args: argparse.Namespace,
    rel_type: str,
    schema_name: str,
) -> int:
    """Helper for execution-instance (Fixed-at-authoring) relationships per
    ADR/0024 §2.5. Consults .rev-id-map; writes binding: fixed + revision_id
    at authoring."""
    workspace = Path(args.workspace)
    src_uuid = _resolve_number_to_uuid(workspace, args.source)
    tgt_uuid = _resolve_number_to_uuid(workspace, args.target)
    rev_id_map = load_rev_id_map(workspace)
    if tgt_uuid not in rev_id_map:
        print(
            f"✗ Cannot author Fixed-at-authoring relationship {rel_type}: target "
            f"{args.target} ({tgt_uuid}) has no predeclared rev_id in .rev-id-map. "
            f"Run `init --rev-id <obj-uuid>=<rev-uuid>` first per ADR/0024 §2.5.",
            file=sys.stderr,
        )
        return 64
    pinned_rev = rev_id_map[tgt_uuid]
    rec = {
        "id": f"rel_{rel_type}_{args.target.lower().replace('-', '_')}",
        "type": rel_type,
        "binding": "fixed",
        "endpoints": [{"object_uuid": tgt_uuid, "revision_id": pinned_rev}],
        "fact_provenance": {"category": "human_input"},
    }
    try:
        validate_against_schema(rec, schema_name)
    except SchemaValidationError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 3
    tx_id, evt_id = add_relationship(workspace, src_uuid, rec)
    print(f"✓ Updated revisions/{src_uuid}/working.yaml relationship: list (rel_{rel_type}_*)")
    print(f"  binding: fixed; endpoints[0].revision_id pinned to predeclared {pinned_rev}")
    print(f"✓ Appended relationship_created event to events.jsonl ({evt_id})")
    _check_fold(workspace)
    return 0


def cmd_link_executes(args: argparse.Namespace) -> int:
    return _link_fixed_execution_relationship(args, "executes", "relationship_executes.schema.json")


def cmd_link_executed_on(args: argparse.Namespace) -> int:
    return _link_fixed_execution_relationship(args, "executed_on", "relationship_executed_on.schema.json")


def cmd_link_produces(args: argparse.Namespace) -> int:
    return _link_fixed_execution_relationship(args, "produces", "relationship_produces.schema.json")


def cmd_create_part(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    obj_uuid = _gen_uuid(args.uuid)
    # Parse parameter "name=value"
    if "=" not in args.parameter:
        print(f"✗ --parameter must be name=value", file=sys.stderr)
        return 64
    pname, pvalue_str = args.parameter.split("=", 1)
    pvalue = float(pvalue_str) if "." in pvalue_str else int(pvalue_str)
    sidecar = {
        "object": {
            "uuid": obj_uuid,
            "number": args.number,
            "type": "Part",
            "name": args.name,
            "lifecycle": "in_work",
            "schema_version": SCHEMA_BUNDLE_VERSION,
        },
        "parameter": [
            {
                "id": f"param_{pname}",
                "name": pname,
                "value": pvalue,
                "datatype": "number",
                "unit": pname.rsplit("_", 1)[-1] if "_" in pname else "",
                "fact_provenance": {"category": "human_input"},
            }
        ],
    }
    if not sidecar["parameter"][0]["unit"]:
        del sidecar["parameter"][0]["unit"]
    try:
        validate_against_schema(sidecar, "object_part.schema.json")
    except SchemaValidationError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 3
    tx_id, evt_id = create_object(workspace, sidecar, "P", "part_created")
    print(f"✓ Allocated {args.number} in Reservations/P.yaml")
    print(f"✓ Wrote revisions/{obj_uuid}/working.yaml")
    print(f"✓ Appended part_created event to events.jsonl ({evt_id})")
    _check_fold(workspace)
    return 0


def cmd_create_requirement(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    obj_uuid = _gen_uuid(args.uuid)
    # Parse acceptance criterion: "<id>:<param><op><value>" -> canonical criterion text
    if ":" not in args.acceptance_criterion:
        print(f"✗ --acceptance-criterion must be id:expr", file=sys.stderr)
        return 64
    ac_id, expr = args.acceptance_criterion.split(":", 1)
    # Parse expr "<param><op><value>" where op is one of >=, <=, >, <, ==
    import re
    m = re.match(r"^([a-z][a-z0-9_]*)\s*(>=|<=|==|>|<)\s*(-?\d+(?:\.\d+)?)\s*$", expr)
    if not m:
        print(f"✗ --acceptance-criterion expr must match '<param><op><value>'", file=sys.stderr)
        return 64
    param, op, value = m.group(1), m.group(2), m.group(3)
    # Spike-local canonical criterion text per Codex1 B2 absorption: threshold
    # parsing lives in validate.py, not in canonical Requirement schema.
    op_phrase = {">=": "at least", ">": "greater than", "<=": "at most", "<": "less than", "==": "exactly"}[op]
    criterion_text = f"{param} shall be {op_phrase} {value}"
    sidecar = {
        "object": {
            "uuid": obj_uuid,
            "number": args.number,
            "type": "Requirement",
            "name": args.name or f"Requirement {args.number}",
            "lifecycle": "in_work",
            "schema_version": SCHEMA_BUNDLE_VERSION,
        },
        "requirement": {
            "statement": {
                "text": args.statement,
                "language": "en",
                "format": "freeform",
            },
            "category": args.category,
            "default_verification_method": args.verification_method,
        },
        "acceptance_criterion": [
            {
                "id": ac_id,
                "criterion": {
                    "text": criterion_text,
                    "language": "en",
                    "format": "freeform",
                },
                "references": [f"parameter:{param}"],
            }
        ],
    }
    try:
        validate_against_schema(sidecar, "object_requirement.schema.json")
    except SchemaValidationError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 3
    tx_id, evt_id = create_object(workspace, sidecar, "REQ", "requirement_created")
    print(f"✓ Allocated {args.number} in Reservations/REQ.yaml")
    print(f"✓ Wrote revisions/{obj_uuid}/working.yaml")
    print(f"✓ Appended requirement_created event to events.jsonl ({evt_id})")
    _check_fold(workspace)
    return 0


def cmd_link_satisfies(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    src_uuid = _resolve_number_to_uuid(workspace, args.source)
    tgt_uuid = _resolve_number_to_uuid(workspace, args.target)
    rec = {
        "id": f"rel_satisfies_{args.target.lower().replace('-', '_')}",
        "type": "satisfies",
        "binding": "float",
        "endpoints": [{"object_uuid": tgt_uuid}],
        "fact_provenance": {"category": "human_input"},
    }
    try:
        validate_against_schema(rec, "relationship_satisfies.schema.json")
    except SchemaValidationError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 3
    tx_id, evt_id = add_relationship(workspace, src_uuid, rec)
    print(f"✓ Updated revisions/{src_uuid}/working.yaml relationship: list")
    print(f"✓ Appended relationship_created event to events.jsonl ({evt_id})")
    _check_fold(workspace)
    return 0


def cmd_propose_parameter_change(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    obj_uuid = _resolve_number_to_uuid(workspace, args.object)
    sidecar = load_sidecar_validated(sidecar_path(workspace, obj_uuid))

    # Find parameter
    pid = None
    old_value = None
    for p in sidecar.get("parameter", []):
        if p["name"] == args.parameter or p["id"] == args.parameter or p["id"] == f"param_{args.parameter}":
            pid = p["id"]
            old_value = p["value"]
            break
    if pid is None:
        print(f"✗ Parameter {args.parameter} not found on {args.object}", file=sys.stderr)
        return 64

    # In-memory mutation
    candidate = json.loads(json.dumps(sidecar))
    for p in candidate["parameter"]:
        if p["id"] == pid:
            p["value"] = args.new_value
            p["fact_provenance"] = {"category": "ai_proposal"}

    # Synthesize transaction id for stdout (rejected case still consumes id)
    prospective_tx = next_transaction_id(workspace)
    print(f"✓ Transaction {prospective_tx} begun (in-memory; not committed)")
    print(f"✓ Modify: {args.parameter}: {old_value} → {args.new_value}")

    # Validate against all linked Requirements
    failed = False
    fail_details: list[str] = []
    for rel in candidate.get("relationship", []):
        if rel.get("type") != "satisfies":
            continue
        for ep in rel.get("endpoints", []):
            req_uuid = ep["object_uuid"]
            req = load_sidecar_validated(sidecar_path(workspace, req_uuid))
            result = validate_satisfies(candidate, req)
            if result["result"] == "FAIL":
                failed = True
                fail_details.append(f"{result['check_name']}: {result['details']}")
            else:
                print(f"✓ Validate: {result['check_name']} PASS — {result['details']}")

    if failed:
        for d in fail_details:
            print(f"✗ Validate: {d}")
        print(f"✗ Transaction REJECTED — rollback applied; no state change committed")
        print(f"  Note: failed-transaction retention remains deferred by OQ-0003 — no audit artifact written.")
        return 1

    # Human approval
    if args.auto_approve:
        print(f"? Human approval required: [y/N] y (--auto-approve)")
        approved = True
    else:
        ans = input("? Human approval required: [y/N] ").strip().lower()
        approved = ans == "y"
    if not approved:
        print(f"✗ Transaction REJECTED by human — rollback applied; no state change committed")
        return 1

    # Commit
    tx_id, evt_id, _ = change_parameter(workspace, obj_uuid, pid, args.new_value, args.rationale)
    print(f"✓ Commit: revisions/{obj_uuid}/working.yaml updated ({tx_id})")
    print(f"✓ Appended parameter_changed event to events.jsonl ({evt_id})")
    _check_fold(workspace)
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    numbers = [n.strip() for n in args.objects.split(",")]
    uuids = [_resolve_number_to_uuid(workspace, n) for n in numbers]

    # Load .rev-id-map (spike-local non-canonical per ADR/0024 §2.5) first; then
    # accept --rev-id flags as overrides; then fill missing with UUID4. This is
    # required because execution-instance relationships authored Fixed-at-authoring
    # pinned their endpoints[0].revision_id from the predeclared map; release must
    # allocate the same rev_ids or materialize_revision raises ValueError.
    rev_id_map: dict[str, str] = load_rev_id_map(workspace)
    for pair in args.rev_id or []:
        if "=" not in pair:
            print(f"✗ --rev-id must be <obj-uuid>=<rev-uuid>", file=sys.stderr)
            return 64
        k, v = pair.split("=", 1)
        rev_id_map[k] = v
    for u in uuids:
        if u not in rev_id_map:
            rev_id_map[u] = str(_uuid.uuid4())

    tx_id = next_transaction_id(workspace)

    # Materialize each Object's Revision (uses rev_id_map for endpoint pinning)
    revisions = []
    for u, number in zip(uuids, numbers):
        rid = rev_id_map[u]
        rpath, rhash = materialize_revision(workspace, u, rid, args.label, rev_id_map)
        print(f"✓ Wrote {rpath.relative_to(workspace)} (sha256: {rhash[:23]}...)")
        revisions.append({
            "object_uuid": u,
            "object_number": number,
            "revision_id": rid,
            "revision_hash": rhash,
        })

    # Validate each Revision against its schema (Part / Requirement) via the
    # schema-validated loader (per Codex2 B3 — read-time validation).
    validation_outcomes: list[dict] = []
    sidecars_by_uuid: dict[str, dict] = {}
    for u in uuids:
        rid = rev_id_map[u]
        from .transaction import revision_path
        rpath = revision_path(workspace, u, rid)
        try:
            rev_data = load_revision_validated(rpath)
            sidecars_by_uuid[u] = rev_data
            validation_outcomes.append({
                "check_name": f"schema_validation({rev_data['object']['number']})",
                "result": "PASS",
                "details": f"{rev_data['object']['number']} Revision validates against bundle-resolved schema for ({rev_data['object']['type']})",
            })
        except SchemaValidationError as e:
            validation_outcomes.append({
                "check_name": f"schema_validation(unknown)",
                "result": "FAIL",
                "details": str(e),
            })

    # Run satisfies validation per relationship in released Parts (Wedge-001 carried)
    for u, sidecar in sidecars_by_uuid.items():
        if sidecar["object"]["type"] != "Part":
            continue
        for rel in sidecar.get("relationship", []):
            if rel.get("type") != "satisfies":
                continue
            for ep in rel.get("endpoints", []):
                req_uuid = ep["object_uuid"]
                if req_uuid in sidecars_by_uuid:
                    result = validate_satisfies(sidecar, sidecars_by_uuid[req_uuid])
                    validation_outcomes.append(result)

    # Wedge-002 V&V validation: chain integrity (B5) + attachment integrity + execution cardinality
    has_vv_objects = any(
        sidecar["object"]["type"] in ("TestProcedure", "TestExecution", "EvidenceArtifact")
        for sidecar in sidecars_by_uuid.values()
    )
    if has_vv_objects:
        vv_outcome = validate_v_and_v_chain_integrity(sidecars_by_uuid)
        validation_outcomes.append(vv_outcome)
        print(f"✓ V&V chain integrity: PASS")

        att_outcomes = verify_attachment_integrity(workspace, sidecars_by_uuid)
        validation_outcomes.extend(att_outcomes)
        print(f"✓ Verified {len(att_outcomes)} attachment integrity check(s) (vault bytes re-hashed)")

        # Per Codex2 B1 absorption (arc 20260530-3): release-time validation of
        # parameter→attachment lineage resolution + derived attachment chain
        # termination. Covers the `parameter → derived_from → attachment` head
        # of ADR/0024's full lineage chain claim.
        lineage_outcomes = validate_attachment_lineage(sidecars_by_uuid)
        validation_outcomes.extend(lineage_outcomes)
        print(f"✓ Verified attachment lineage for {len(lineage_outcomes)} Object(s) (parameter→attachment same-Revision + derived chain termination)")

        cardinality_outcomes = validate_execution_cardinality(sidecars_by_uuid)
        validation_outcomes.extend(cardinality_outcomes)
        print(f"✓ Verified execution cardinality for {len(cardinality_outcomes)} TestExecution(s)")

        # Verification-method consistency tooling-aided diagnostic (stdout warning;
        # NOT a validation_outcomes entry) per ADR/0024 §"Pre-declared constraints
        # honored" + Codex1 N4 absorption from arc 20260530-2.
        for u, sidecar in sidecars_by_uuid.items():
            if sidecar["object"]["type"] != "TestProcedure":
                continue
            tp_vm = sidecar.get("test_procedure", {}).get("verification_method")
            for vr in sidecar.get("relationship", []):
                if vr.get("type") != "verifies":
                    continue
                for ep in vr.get("endpoints", []):
                    req_uuid = ep["object_uuid"]
                    if req_uuid not in sidecars_by_uuid:
                        continue
                    req_vm = sidecars_by_uuid[req_uuid].get("requirement", {}).get("default_verification_method")
                    if req_vm and tp_vm and tp_vm != req_vm:
                        req_num = sidecars_by_uuid[req_uuid]["object"]["number"]
                        tp_num = sidecar["object"]["number"]
                        print(
                            f"⚠ Verification-method mismatch (diagnostic; not validation failure): "
                            f"{tp_num}.verification_method={tp_vm!r} vs "
                            f"{req_num}.default_verification_method={req_vm!r}"
                        )

    # Emit release events
    for u in uuids:
        rev_data = sidecars_by_uuid[u]
        rid = rev_id_map[u]
        rhash = next(r["revision_hash"] for r in revisions if r["object_uuid"] == u)
        evt_id = append_release_event(workspace, tx_id, rev_data["object"]["type"], u, rid, rhash)
        print(f"✓ Appended release event for {rev_data['object']['number']} ({evt_id})")

    last_evt_id, last_evt_hash = last_event_id_and_hash(workspace)
    assert last_evt_id is not None and last_evt_hash is not None

    manifest = build_manifest(
        release_label=args.label,
        released_at=now_iso(),
        revisions=revisions,
        validation_outcomes=validation_outcomes,
        last_event_id=last_evt_id,
        last_event_hash=last_evt_hash,
    )
    try:
        validate_against_schema(manifest, "manifest.schema.json")
    except SchemaValidationError as e:
        print(f"✗ Manifest schema validation failed: {e}", file=sys.stderr)
        return 3

    manifest_bytes = serialize_manifest(manifest)
    mhash = hash_bytes(manifest_bytes)
    mpath = manifest_path(workspace, args.label)
    atomic_write_text(mpath, manifest_bytes.decode("utf-8"))
    print(f"✓ Wrote {mpath.relative_to(workspace)} (deterministic JSON)")
    print(f"✓ Release manifest hash: {mhash}")

    # Re-read every Revision file and verify recorded hash equals file bytes
    # (per Codex2 B2: defence-in-depth check that the pin is true).
    verify_revision_hashes(workspace, revisions)
    print(f"✓ Verified {len(revisions)} Revision hash(es) against on-disk bytes")

    # Final fold check
    _check_fold(workspace)
    return 0


def _check_fold(workspace: Path) -> None:
    try:
        validate_fold(workspace)
    except FoldInconsistencyError as e:
        print(f"✗ {e}", file=sys.stderr)
        sys.exit(5)


# ---------------------- argparse setup ----------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wedge", description="Wedge-002 spike CLI (V&V chain end-to-end)")
    p.add_argument("--workspace", default=".", help="Workspace directory (default: cwd)")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Initialize workspace")
    p_init.add_argument("--project-id", default="wedge-002-demo")
    p_init.add_argument("--rev-id", action="append", help="<obj-uuid>=<rev-uuid> predeclared rev_id (repeatable; per ADR/0024 §2.5)")
    p_init.set_defaults(func=cmd_init)

    # Wedge-001 carried subcommands
    p_cp = sub.add_parser("create-part", help="Author a Part sidecar")
    p_cp.add_argument("--number", required=True)
    p_cp.add_argument("--name", required=True)
    p_cp.add_argument("--parameter", required=True, help="name=value (e.g., plate_thickness_mm=6)")
    p_cp.add_argument("--uuid", default=None, help="Override generated UUID (for reproducibility)")
    p_cp.set_defaults(func=cmd_create_part)

    p_cr = sub.add_parser("create-requirement", help="Author a Requirement sidecar")
    p_cr.add_argument("--number", required=True)
    p_cr.add_argument("--name", default=None)
    p_cr.add_argument("--statement", required=True)
    p_cr.add_argument("--category", default="performance", choices=["functional", "performance", "non_functional", "interface", "design_constraint", "regulatory"])
    p_cr.add_argument("--verification-method", default="analysis", choices=["test", "analysis", "inspection", "demonstration"])
    p_cr.add_argument("--acceptance-criterion", required=True, help="id:expr (e.g., ac_min_thickness:plate_thickness_mm>=5)")
    p_cr.add_argument("--uuid", default=None)
    p_cr.set_defaults(func=cmd_create_requirement)

    p_ls = sub.add_parser("link-satisfies", help="Add a satisfies relationship to a Part")
    p_ls.add_argument("--source", required=True, help="Source Part Number (e.g., P-000058)")
    p_ls.add_argument("--target", required=True, help="Target Requirement Number (e.g., REQ-000058)")
    p_ls.set_defaults(func=cmd_link_satisfies)

    p_pp = sub.add_parser("propose-parameter-change", help="AI Transaction lifecycle for a parameter change")
    p_pp.add_argument("--object", required=True, help="Object Number (e.g., P-000058)")
    p_pp.add_argument("--parameter", required=True, help="Parameter name (e.g., plate_thickness_mm)")
    p_pp.add_argument("--new-value", required=True, type=float)
    p_pp.add_argument("--rationale", required=True)
    p_pp.add_argument("--auto-approve", action="store_true", help="Bypass interactive approval prompt (spike-local)")
    p_pp.set_defaults(func=cmd_propose_parameter_change)

    p_rl = sub.add_parser("release", help="Materialize Revisions + write Release Manifest (with V&V chain integrity)")
    p_rl.add_argument("--objects", required=True, help="Comma-separated Object Numbers")
    p_rl.add_argument("--label", required=True)
    p_rl.add_argument("--rev-id", action="append", help="<obj-uuid>=<rev-uuid> (repeatable; default UUID4 or .rev-id-map)")
    p_rl.set_defaults(func=cmd_release)

    # Wedge-002 V&V subcommands
    p_af = sub.add_parser("attach-file", help="Copy bytes into Vault + stage attachment record (no canonical event)")
    p_af.add_argument("--file", required=True, help="Local file path to attach")
    p_af.add_argument("--role", required=True, help="source_authoring | rendered_primary | derived_secondary")
    p_af.add_argument("--id", required=True, help="Attachment id (e.g., att_procedure)")
    p_af.add_argument("--media-type", default=None, help="MIME type (default: inferred from file extension)")
    p_af.set_defaults(func=cmd_attach_file)

    p_ctp = sub.add_parser("create-test-procedure", help="Author a TestProcedure sidecar")
    p_ctp.add_argument("--number", required=True)
    p_ctp.add_argument("--name", required=True)
    p_ctp.add_argument("--title", default=None, help="test_procedure.title (default: --name)")
    p_ctp.add_argument("--verification-method", required=True, choices=["test", "analysis", "inspection", "demonstration"])
    p_ctp.add_argument("--attachment", required=True, help="Attachment id (must be staged via attach-file first)")
    p_ctp.add_argument("--uuid", default=None)
    p_ctp.set_defaults(func=cmd_create_test_procedure)

    p_cte = sub.add_parser("create-test-execution", help="Author a TestExecution sidecar")
    p_cte.add_argument("--number", required=True)
    p_cte.add_argument("--name", default=None)
    p_cte.add_argument("--execution-status", required=True, choices=["completed", "aborted", "inconclusive"], help="test_execution.execution_status")
    p_cte.add_argument("--executed-on-date", required=True, help="ISO 8601 date YYYY-MM-DD")
    p_cte.add_argument("--operator-identifier", default=None)
    p_cte.add_argument("--instrument-identifier", default=None)
    p_cte.add_argument("--parameter", required=True, help="name=value:from=attachment:att_id (lineage required per ADR/0022)")
    p_cte.add_argument("--attachment", required=True, help="Attachment id (must be staged via attach-file first)")
    p_cte.add_argument("--uuid", default=None)
    p_cte.set_defaults(func=cmd_create_test_execution)

    p_cev = sub.add_parser("create-evidence-artifact", help="Author an EvidenceArtifact sidecar")
    p_cev.add_argument("--number", required=True)
    p_cev.add_argument("--name", default=None)
    p_cev.add_argument("--summary", required=True)
    p_cev.add_argument("--evidence-kind", required=True, choices=["simulation", "test_report", "measurement", "inspection", "calibration_certificate", "analysis", "other"])
    p_cev.add_argument("--parameter", required=True, help="name=value:from=attachment:att_id (lineage required per ADR/0019)")
    p_cev.add_argument("--attachment", required=True, help="Attachment id (must be staged via attach-file first)")
    p_cev.add_argument("--uuid", default=None)
    p_cev.set_defaults(func=cmd_create_evidence_artifact)

    # V&V link commands (Float-default + criterion-level fact_ref opt-in)
    p_lta = sub.add_parser("link-tested-against", help="Add tested_against (Part → TestProcedure; Float default)")
    p_lta.add_argument("--source", required=True)
    p_lta.add_argument("--target", required=True)
    p_lta.set_defaults(func=cmd_link_tested_against)

    p_lv = sub.add_parser("link-verifies", help="Add verifies (TestProcedure → Requirement; target-side fact_ref opt-in)")
    p_lv.add_argument("--source", required=True)
    p_lv.add_argument("--target", required=True)
    p_lv.add_argument("--target-criterion", default=None, help="Optional acceptance_criterion id (target-side fact_ref per ADR/0021 §6)")
    p_lv.set_defaults(func=cmd_link_verifies)

    p_lc = sub.add_parser("link-cites", help="Add cites (Requirement → EvidenceArtifact; source-side source_fact_ref opt-in)")
    p_lc.add_argument("--source", required=True)
    p_lc.add_argument("--target", required=True)
    p_lc.add_argument("--source-criterion", default=None, help="Optional acceptance_criterion id (source-side source_fact_ref per ADR/0021 §6)")
    p_lc.set_defaults(func=cmd_link_cites)

    # Execution-instance link commands (Fixed-at-authoring per ADR/0024 §2.5)
    p_lex = sub.add_parser("link-executes", help="Add executes (TestExecution → TestProcedure; Fixed-at-authoring)")
    p_lex.add_argument("--source", required=True)
    p_lex.add_argument("--target", required=True)
    p_lex.set_defaults(func=cmd_link_executes)

    p_leo = sub.add_parser("link-executed-on", help="Add executed_on (TestExecution → Part | Assembly; Fixed-at-authoring)")
    p_leo.add_argument("--source", required=True)
    p_leo.add_argument("--target", required=True)
    p_leo.set_defaults(func=cmd_link_executed_on)

    p_lpr = sub.add_parser("link-produces", help="Add produces (TestExecution → EvidenceArtifact; Fixed-at-authoring)")
    p_lpr.add_argument("--source", required=True)
    p_lpr.add_argument("--target", required=True)
    p_lpr.set_defaults(func=cmd_link_produces)

    return p


def main() -> int:
    # Force UTF-8 stdout/stderr so ✓/✗ marks render on Windows consoles too
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except ProfileViolationError as e:
        print(f"✗ AIADRA YAML Profile violation: {e}", file=sys.stderr)
        return 2
    except SchemaValidationError as e:
        print(f"✗ Schema validation failed: {e}", file=sys.stderr)
        return 3
    except FoldInconsistencyError as e:
        print(f"✗ Sidecar/event invariant violated — manual inspection required\n  {e}", file=sys.stderr)
        return 5
    except IntegrityError as e:
        print(f"✗ Integrity check failed — manifest/file hash mismatch\n  {e}", file=sys.stderr)
        return 6
    except VVChainIntegrityError as e:
        print(f"✗ V&V chain integrity violated\n  {e}", file=sys.stderr)
        return 7
    except AttachmentIntegrityError as e:
        print(f"✗ Attachment integrity violated\n  {e}", file=sys.stderr)
        return 8
    except ExecutionCardinalityError as e:
        print(f"✗ Execution cardinality rule violated\n  {e}", file=sys.stderr)
        return 9
