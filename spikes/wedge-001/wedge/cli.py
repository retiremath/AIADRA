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

from . import SCHEMA_BUNDLE_VERSION
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
    manifest_path,
    materialize_revision,
    now_iso,
    reservation_path,
    sidecar_path,
)
from .validate import (
    FoldInconsistencyError,
    IntegrityError,
    SchemaValidationError,
    load_reservation_validated,
    load_revision_validated,
    load_sidecar_validated,
    validate_against_schema,
    validate_fold,
    validate_satisfies,
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
    init_workspace(workspace)
    print(f"✓ Initialized workspace at {workspace}")
    print(f"  - Reservations/P.yaml (empty)")
    print(f"  - Reservations/REQ.yaml (empty)")
    print(f"  - events.jsonl (empty)")
    return 0


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

    # Parse --rev-id obj_uuid=rev_uuid pairs (optional; default UUID4 per Object)
    rev_id_map: dict[str, str] = {}
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

    # Run satisfies validation per relationship in released Parts
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

    # Emit release events (Part / Requirement)
    for u in uuids:
        rev_data = sidecars_by_uuid[u]
        rid = rev_id_map[u]
        rhash = next(r["revision_hash"] for r in revisions if r["object_uuid"] == u)
        evt_id = append_release_event(workspace, tx_id, rev_data["object"]["type"], u, rid, rhash)
        print(f"✓ Appended {rev_data['object']['type'].lower()}_released event ({evt_id})")

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
    p = argparse.ArgumentParser(prog="wedge", description="Wedge-001 spike CLI")
    p.add_argument("--workspace", default=".", help="Workspace directory (default: cwd)")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Initialize workspace")
    p_init.add_argument("--project-id", default="wedge-001-demo")
    p_init.set_defaults(func=cmd_init)

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

    p_rl = sub.add_parser("release", help="Materialize Revisions + write Release Manifest")
    p_rl.add_argument("--objects", required=True, help="Comma-separated Object Numbers")
    p_rl.add_argument("--label", required=True)
    p_rl.add_argument("--rev-id", action="append", help="<obj-uuid>=<rev-uuid> (repeatable; default UUID4)")
    p_rl.set_defaults(func=cmd_release)

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
