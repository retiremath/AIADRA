"""CLI command implementations — thin adapters around protocol.propose.

Phase C (arc 20260531-9) Codex1 B1+B2+B4 absorption: state-changing CLI
commands route through the Ring 2 `protocol.propose()` facade. The CLI is
the Tier-2 binding layer per ADR/0026 Decision §6; the human-driven
`change-parameter` path passes `actor="human"` so the operator may attest
`new_fact_provenance.category="human_input"` per ADR/0026 §5 (AI agents
MUST NOT self-attest as humans; Codex1 B4 absorption).

Each command:
1. Parses workspace + command-specific args.
2. Routes through `protocol.propose(workspace, kind=..., params=..., actor=...)`.
   `propose` handles pin resolution (BundleRegistry.bundle_for_pin for all
   kinds except `init`, which uses `BundleRegistry().latest()` per Codex1 B2).
3. Runs draft.validate(); on FAIL outputs error + exits non-zero.
4. Runs draft.commit(); reports commit hash + event IDs.

Exit codes:
  0  success
  1  validation failure (schema / Profile / fold / reservation_integrity)
  2  CLI argument error / Object-not-found / TransactionError
  3  project pin failure (missing / digest mismatch)
  4  commit error
  5  dirty AIADRA-managed working tree (B9 guard)
  6  B6 revision binding error (mutation prohibited)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from ..transaction.boundary import (
    CommitError,
    TransactionDraft,
    TransactionError,
    git_repo_dirty_for_aiadra_paths,
)
from ..validation.binding import RevisionBindingError
from ..validation.profile import ProfileViolationError
from ..validation.reservation_integrity import ReservationIntegrityError
from ..validation.release import ReleaseConsistencyError
from ..validation.schema import SchemaValidationError


def _run_draft(draft: TransactionDraft, *, allow_dirty_init: bool = False) -> int:
    """Run validate + commit phases; print outcomes; return exit code.

    Per B9 absorption: invokes `git_repo_dirty_for_aiadra_paths` guard BEFORE
    validate so a dirty AIADRA-managed working tree rejects state-changing
    Transactions. `allow_dirty_init` skips the guard for `aiadra init` (the
    workspace doesn't have a .git yet, but a re-init on a pre-existing
    workspace shouldn't be blocked by an empty pre-init state).
    """
    if not allow_dirty_init:
        dirty, reason = git_repo_dirty_for_aiadra_paths(draft.workspace)
        if dirty:
            print(
                f"workspace dirty: {reason}\n"
                f"Resolve before running state-changing AIADRA commands "
                f"(see README manual recovery).",
                file=sys.stderr,
            )
            return 5

    try:
        outcomes = draft.validate()
    except (ProfileViolationError, SchemaValidationError, RevisionBindingError,
            ReservationIntegrityError, ReleaseConsistencyError) as e:
        rc = 6 if isinstance(e, RevisionBindingError) else 1
        print(f"validation failed ({type(e).__name__}): {e}", file=sys.stderr)
        return rc
    except Exception as e:
        from ..validation.fold import FoldInconsistencyError
        if isinstance(e, FoldInconsistencyError):
            print(f"validation failed (FoldInconsistencyError): {e}", file=sys.stderr)
            return 1
        raise
    try:
        from ..protocol import commit as protocol_commit
        result = protocol_commit(draft)
    except CommitError as e:
        print(f"commit failed: {e}", file=sys.stderr)
        return 4
    for o in outcomes:
        print(f"  ✓ {o.result}  {o.check_name}")
    if result.commit_hash:
        print(f"committed: {result.commit_hash}  tx={result.transaction_id}  events={len(result.event_ids)}")
    else:
        print(f"applied: tx={result.transaction_id}  events={len(result.event_ids)}  (no git commit; init or non-git workspace)")
    return 0


def _run_protocol_propose(
    workspace: Path,
    *,
    kind: str,
    params: dict[str, Any],
    actor: str = "agent",
    allow_dirty_init: bool = False,
    failure_label: str | None = None,
) -> int:
    """Common delegation path: protocol.propose → _run_draft.

    `failure_label` is the human-readable command name used in the
    TransactionError message (default: the kind itself).
    """
    from ..protocol import propose, ProjectPinError
    try:
        draft = propose(workspace, kind=kind, params=params, actor=actor)
    except ProjectPinError as e:
        print(f"project pin failure: {e}", file=sys.stderr)
        return 3
    except TransactionError as e:
        label = failure_label or kind
        print(f"{label} failed: {e}", file=sys.stderr)
        return 2
    return _run_draft(draft, allow_dirty_init=allow_dirty_init)


_OBJ_TYPE_TO_KIND = {
    "Part":             "create_part",
    "Requirement":      "create_requirement",
    "TestProcedure":    "create_test_procedure",
    "TestExecution":    "create_test_execution",
    "EvidenceArtifact": "create_evidence_artifact",
}


# ---------------- CLI command entry points ----------------


def cmd_init(argv: list[str]) -> int:
    """aiadra init <workspace>"""
    if not argv:
        print("usage: aiadra init <workspace>", file=sys.stderr)
        return 2
    workspace = Path(argv[0]).resolve()
    # B9: dirty-guard skipped for init (workspace pre-init has no .git or only fresh files)
    return _run_protocol_propose(
        workspace, kind="init", params={}, allow_dirty_init=True,
        failure_label="init",
    )


def cmd_create_object(obj_type: str, argv: list[str]) -> int:
    """aiadra create-<type> <workspace> <number> <name> [--uuid UUID] [--revision-id UUID]"""
    import argparse
    p = argparse.ArgumentParser(prog=f"aiadra create-{obj_type.lower()}")
    p.add_argument("workspace")
    p.add_argument("number")
    p.add_argument("name")
    p.add_argument("--uuid", default=None)
    p.add_argument("--revision-id", default=None)
    args = p.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    kind = _OBJ_TYPE_TO_KIND[obj_type]
    params: dict[str, Any] = {"number": args.number, "name": args.name}
    if args.uuid is not None:
        params["uuid"] = args.uuid
    if args.revision_id is not None:
        params["revision_id"] = args.revision_id
    return _run_protocol_propose(
        workspace, kind=kind, params=params,
        failure_label="create-object",
    )


def cmd_change_parameter(argv: list[str]) -> int:
    """aiadra change-parameter <workspace> <obj-number> <parameter-id> <new-value> <rationale>
                              [--provenance-category {human_input|ai_proposal|computed_result|measured}]
                              [--provenance-agent <ref>] [--provenance-derived-from <ref1,ref2,...>]

    Per F1 absorption Phase 2 (arc 20260531-3): optional provenance flags
    construct a `new_fact_provenance` dict that replaces the parameter's
    fact_provenance wholesale. If ANY --provenance-* flag is present,
    --provenance-category is REQUIRED. If none are present, fact_provenance
    is unchanged (Phase 1 backward-compat).

    Per Codex1 B4 absorption arc 20260531-9: CLI passes actor="human" so
    the operator MAY attest provenance.category="human_input"; AI agents
    using protocol.propose with actor="agent" (default) cannot.
    """
    import argparse
    p = argparse.ArgumentParser(prog="aiadra change-parameter")
    p.add_argument("workspace")
    p.add_argument("obj_number")
    p.add_argument("parameter_id")
    p.add_argument("new_value", type=float)
    p.add_argument("rationale")
    p.add_argument(
        "--provenance-category",
        choices=["human_input", "ai_proposal", "computed_result", "measured"],
        default=None,
        help="Required if any --provenance-* flag is present. Replaces parameter's fact_provenance wholesale.",
    )
    p.add_argument("--provenance-agent", default=None,
                   help="Optional `ai_agent_ref` field of fact_provenance.")
    p.add_argument("--provenance-derived-from", default=None,
                   help="Optional `derived_from` field of fact_provenance; comma-separated.")
    args = p.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    new_fact_provenance = None
    any_provenance_flag = any([
        args.provenance_category is not None,
        args.provenance_agent is not None,
        args.provenance_derived_from is not None,
    ])
    if any_provenance_flag:
        if args.provenance_category is None:
            print("--provenance-category is REQUIRED when any --provenance-* flag is provided", file=sys.stderr)
            return 2
        new_fact_provenance = {"category": args.provenance_category}
        if args.provenance_agent is not None:
            new_fact_provenance["ai_agent_ref"] = args.provenance_agent
        if args.provenance_derived_from is not None:
            new_fact_provenance["derived_from"] = [
                s.strip() for s in args.provenance_derived_from.split(",") if s.strip()
            ]
    params: dict[str, Any] = {
        "obj_number": args.obj_number,
        "parameter_id": args.parameter_id,
        "new_value": args.new_value,
        "rationale": args.rationale,
    }
    if new_fact_provenance is not None:
        params["new_fact_provenance"] = new_fact_provenance
    return _run_protocol_propose(
        workspace, kind="change_parameter", params=params,
        actor="human",  # Codex1 B4: CLI is the human-driven binding
        failure_label="change-parameter",
    )


def cmd_delete_object(argv: list[str]) -> int:
    """aiadra delete-object <workspace> <obj-number> --reason <text>

    ADR/0004 SCN (arc 20260728-3): standalone deletion Transaction — the
    `object_deleted` event, the terminal Reservation tombstone, and the
    working-sidecar removal in ONE Git commit. Refuses with the structured
    blocker list when live relationship references (working or released)
    involve the Object. CLI passes actor="human" (operator-driven binding).
    """
    import argparse
    p = argparse.ArgumentParser(prog="aiadra delete-object")
    p.add_argument("workspace")
    p.add_argument("obj_number")
    p.add_argument("--reason", required=True,
                   help="Non-empty deletion reason recorded on the event and tombstone.")
    args = p.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    from ..protocol import propose, ProjectPinError, DeletionBlockedError
    try:
        draft = propose(
            workspace, kind="delete_object",
            params={"obj_number": args.obj_number, "reason": args.reason},
            actor="human",
        )
    except DeletionBlockedError as e:
        print(f"delete-object refused: {e}", file=sys.stderr)
        for b in e.blockers:
            rev = b.get("revision_id")
            suffix = f", revision {rev}" if rev else ""
            print(
                f"  - {b['relationship_type']} {b['relationship_id']} "
                f"on {b['source_object']['number'] or b['source_object']['uuid']} "
                f"(candidate is {b['candidate_role']}; {b['state']}{suffix})",
                file=sys.stderr,
            )
        return 2
    except ProjectPinError as e:
        print(f"project pin failure: {e}", file=sys.stderr)
        return 3
    except TransactionError as e:
        print(f"delete-object failed: {e}", file=sys.stderr)
        return 2
    return _run_draft(draft)


def cmd_add_acceptance_criterion(argv: list[str]) -> int:
    """aiadra add-acceptance-criterion <workspace> <req-number> <criterion-id> <text>
                                       [--language en] [--format freeform|ears]
                                       [--threshold-parameter-ref <uuid>:parameter:<id>]
                                       [--threshold-op {>=,<=,==,!=,>,<}]
                                       [--threshold-value <number>]
                                       [--threshold-unit <string>]
                                       [--verification-method {test,analysis,inspection,demonstration}]
                                       [--reference <ref>]*  [--name <name>]

    Per F2 absorption Phase 4 (arc 20260531-5): if ANY --threshold-* flag is
    present, the FULL quartet (--threshold-parameter-ref + --threshold-op +
    --threshold-value + --threshold-unit) is REQUIRED. Otherwise exit 2.
    """
    import argparse
    p = argparse.ArgumentParser(prog="aiadra add-acceptance-criterion")
    p.add_argument("workspace")
    p.add_argument("req_number")
    p.add_argument("criterion_id")
    p.add_argument("text")
    p.add_argument("--language", default="en")
    p.add_argument("--format", default="freeform", choices=["freeform", "ears"])
    p.add_argument(
        "--threshold-parameter-ref", default=None,
        help="Fact-level parameter reference per ADR/0015: <uuid>:parameter:<id>",
    )
    p.add_argument(
        "--threshold-op", default=None,
        choices=[">=", "<=", "==", "!=", ">", "<"],
    )
    p.add_argument("--threshold-value", default=None, type=float)
    p.add_argument(
        "--threshold-unit", default=None,
        help="Required when any --threshold-* flag is present; byte-equality "
             "to referenced parameter's unit (Layer-2 hard-fail at release).",
    )
    p.add_argument(
        "--verification-method", default=None,
        choices=["test", "analysis", "inspection", "demonstration"],
    )
    p.add_argument("--reference", action="append", default=None)
    p.add_argument("--name", default=None)
    args = p.parse_args(argv)

    threshold_flags = [
        args.threshold_parameter_ref, args.threshold_op,
        args.threshold_value, args.threshold_unit,
    ]
    threshold_expression: dict | None = None
    if any(f is not None for f in threshold_flags):
        missing = []
        if args.threshold_parameter_ref is None:
            missing.append("--threshold-parameter-ref")
        if args.threshold_op is None:
            missing.append("--threshold-op")
        if args.threshold_value is None:
            missing.append("--threshold-value")
        if args.threshold_unit is None:
            missing.append("--threshold-unit")
        if missing:
            print(
                f"add-acceptance-criterion: --threshold-* quartet incomplete; "
                f"missing {', '.join(missing)}. Per F2 (arc 20260531-5): if ANY "
                f"--threshold-* flag is present, the full quartet is REQUIRED.",
                file=sys.stderr,
            )
            return 2
        threshold_expression = {
            "parameter_ref": args.threshold_parameter_ref,
            "comparison_op": args.threshold_op,
            "value": args.threshold_value,
            "unit": args.threshold_unit,
        }

    workspace = Path(args.workspace).resolve()
    params: dict[str, Any] = {
        "req_number": args.req_number,
        "criterion_id": args.criterion_id,
        "criterion_text": args.text,
        "language": args.language,
        "format": args.format,
    }
    if threshold_expression is not None:
        params["threshold_expression"] = threshold_expression
    if args.verification_method is not None:
        params["verification_method"] = args.verification_method
    if args.reference is not None:
        params["references"] = args.reference
    if args.name is not None:
        params["name"] = args.name
    return _run_protocol_propose(
        workspace, kind="add_acceptance_criterion", params=params,
        failure_label="add-acceptance-criterion",
    )


_REL_TYPE_TO_KIND = {
    "satisfies":      "link_satisfies",
    "tested_against": "link_tested_against",
    "verifies":       "link_verifies",
    "cites":          "link_cites",
    "executes":       "link_executes",
    "executed_on":    "link_executed_on",
    "produces":       "link_produces",
}


def cmd_link_relationship(rel_type: str, argv: list[str]) -> int:
    """aiadra link-<rel> <workspace> <source-number> <target-number>"""
    import argparse
    p = argparse.ArgumentParser(prog=f"aiadra link-{rel_type.replace('_', '-')}")
    p.add_argument("workspace")
    p.add_argument("source_number")
    p.add_argument("target_number")
    p.add_argument("--id", dest="relationship_id", default=None)
    args = p.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    params: dict[str, Any] = {
        "source_number": args.source_number,
        "target_number": args.target_number,
    }
    if args.relationship_id is not None:
        params["relationship_id"] = args.relationship_id
    return _run_protocol_propose(
        workspace, kind=_REL_TYPE_TO_KIND[rel_type], params=params,
        failure_label="link",
    )


def cmd_attach_file(argv: list[str]) -> int:
    """aiadra attach-file <workspace> <obj-number> <file-path> --role <role>"""
    import argparse
    p = argparse.ArgumentParser(prog="aiadra attach-file")
    p.add_argument("workspace")
    p.add_argument("obj_number")
    p.add_argument("file_path")
    p.add_argument("--role", required=True,
                   choices=["source_authoring", "rendered_primary", "derived_secondary"])
    p.add_argument("--id", dest="attachment_id", default=None)
    p.add_argument("--derived-from", dest="derived_from_attachment_id", default=None)
    p.add_argument("--media-type", default=None)
    args = p.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    params: dict[str, Any] = {
        "obj_number": args.obj_number,
        "file_path": Path(args.file_path),
        "role": args.role,
    }
    if args.attachment_id is not None:
        params["attachment_id"] = args.attachment_id
    if args.derived_from_attachment_id is not None:
        params["derived_from_attachment_id"] = args.derived_from_attachment_id
    if args.media_type is not None:
        params["media_type"] = args.media_type
    return _run_protocol_propose(
        workspace, kind="attach_file", params=params,
        failure_label="attach-file",
    )


def cmd_release(argv: list[str]) -> int:
    """aiadra release <workspace> --objects <num1,num2,...> [--stage N] [--no-final]
                       [--prior-stage-hash sha256:<hex>] [--prior-stage-number N]
                       [--prior-stage-label LABEL] [--label LABEL]

    Per B11 absorption arc 20260531-2 round-5: prior-stage reference is split
    into 3 explicit flags to avoid ambiguity with sha256:<hex> colon syntax.
    Hash is authoritative; label is optional convenience metadata.
    """
    import argparse
    p = argparse.ArgumentParser(prog="aiadra release")
    p.add_argument("workspace")
    p.add_argument("--objects", required=True, help="Comma-separated Object Numbers")
    p.add_argument("--label", default=None, help="Release label (default: auto-generated)")
    p.add_argument("--stage", type=int, default=1, help="Stage number (default 1)")
    p.add_argument("--no-final", action="store_true", help="This stage is NOT the final stage")
    p.add_argument("--prior-stage-hash", default=None,
                   help="Prior stage manifest hash (sha256:<hex>); authoritative")
    p.add_argument("--prior-stage-number", type=int, default=None,
                   help="Prior stage_number (required when --prior-stage-hash given)")
    p.add_argument("--prior-stage-label", default=None,
                   help="Prior stage release_label (optional convenience metadata)")
    args = p.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    object_numbers = [n.strip() for n in args.objects.split(",") if n.strip()]
    prior_ref = None
    if args.prior_stage_hash:
        if args.prior_stage_number is None:
            print("--prior-stage-hash requires --prior-stage-number", file=sys.stderr)
            return 2
        prior_ref = {
            "manifest_hash": args.prior_stage_hash,
            "stage_number": args.prior_stage_number,
        }
        if args.prior_stage_label:
            prior_ref["release_label"] = args.prior_stage_label
    params: dict[str, Any] = {
        "object_numbers": object_numbers,
        "stage_number": args.stage,
        "final_stage": not args.no_final,
    }
    if args.label is not None:
        params["release_label"] = args.label
    if prior_ref is not None:
        params["prior_stage_manifest_ref"] = prior_ref
    return _run_protocol_propose(
        workspace, kind="release", params=params,
        failure_label="release",
    )


def cmd_explain(argv: list[str]) -> int:
    """aiadra explain <workspace> <object-or-relationship-ref> [--depth N] [--json]

    Phase D (arc 20260531-10) per ADR/0026 §2: walks an Object or Relationship's
    history into an `ExplanationTree`. `ref` accepts Object Number (`P-000001`),
    Object UUID, or `<obj-ref>:relationship:<rel_id>`. Default depth=1 (walks
    one hop of related Objects); `--json` switches output from human-readable
    indented text to JSON dump.
    """
    import argparse
    p = argparse.ArgumentParser(prog="aiadra explain")
    p.add_argument("workspace")
    p.add_argument("ref", help="Object Number / UUID / <obj-ref>:relationship:<rel_id>")
    p.add_argument("--depth", type=int, default=1)
    p.add_argument("--json", action="store_true", help="JSON output (default: human-readable)")
    args = p.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    from ..protocol import explain as protocol_explain, ProjectPinError, ObjectNotFoundError
    try:
        tree = protocol_explain(workspace, args.ref, depth=args.depth)
    except ProjectPinError as e:
        print(f"project pin failure: {e}", file=sys.stderr)
        return 3
    except ObjectNotFoundError as e:
        print(f"explain: not found: {e}", file=sys.stderr)
        return 2
    if args.json:
        import json
        from ..explain import tree_to_dict
        print(json.dumps(tree_to_dict(tree), indent=2, sort_keys=True))
    else:
        _print_tree_human(tree)
    return 0


def _print_tree_human(tree) -> None:
    """Indented human-readable rendering for `aiadra explain` default output."""
    print(f"# {tree.root.label}  (bundle v{tree.bundle_version})")

    def _walk(node, indent: int) -> None:
        prefix = "  " * indent
        print(f"{prefix}- [{node.kind}] {node.label}  ref={node.ref}")
        for k, v in node.details.items():
            if v is None:
                continue
            print(f"{prefix}    {k}: {v}")
        for child in node.children:
            _walk(child, indent + 1)

    _walk(tree.root, 0)


def cmd_audit(argv: list[str]) -> int:
    """aiadra audit list <workspace> [--date YYYY-MM-DD]
       aiadra audit show <workspace> <tx_NNNN> [--date YYYY-MM-DD]

    Phase D (arc 20260531-10) per ADR/0026 §9. Failures only (successes are
    queryable via `git log` + `events.jsonl`).
    """
    if not argv:
        print("usage: aiadra audit {list|show} <workspace> [...]", file=sys.stderr)
        return 2
    subcmd = argv[0]
    if subcmd == "list":
        return _cmd_audit_list(argv[1:])
    if subcmd == "show":
        return _cmd_audit_show(argv[1:])
    print(f"aiadra audit: unknown subcommand {subcmd!r}; expected 'list' or 'show'", file=sys.stderr)
    return 2


def _cmd_audit_list(argv: list[str]) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="aiadra audit list")
    p.add_argument("workspace")
    p.add_argument("--date", default=None, help="Filter to YYYY-MM-DD subdirectory")
    args = p.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    from ..audit import list_audit_files
    files = list_audit_files(workspace)
    if args.date:
        files = [f for f in files if f"/{args.date}/" in f.as_posix() or f"\\{args.date}\\" in str(f)]
    if not files:
        print("(no audit records)" if not args.date else f"(no audit records for {args.date})")
        return 0
    for f in files:
        rel = f.relative_to(workspace).as_posix() if workspace in f.parents else str(f)
        try:
            size = f.stat().st_size
        except OSError:
            size = 0
        print(f"{rel}  ({size} bytes)")
    return 0


def _cmd_audit_show(argv: list[str]) -> int:
    import argparse, json as _json
    p = argparse.ArgumentParser(prog="aiadra audit show")
    p.add_argument("workspace")
    p.add_argument("tx_id", help="Transaction id (e.g. tx_0003)")
    p.add_argument("--date", default=None, help="YYYY-MM-DD subdirectory (default: search all)")
    args = p.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    from ..audit import list_audit_files
    files = list_audit_files(workspace)
    if args.date:
        files = [f for f in files if f"/{args.date}/" in f.as_posix() or f"\\{args.date}\\" in str(f)]
    matches = [f for f in files if f.name.startswith(f"{args.tx_id}-failed-")]
    if not matches:
        scope = f" on {args.date}" if args.date else ""
        print(f"aiadra audit show: no records for {args.tx_id}{scope}", file=sys.stderr)
        return 2
    for f in matches:
        rel = f.relative_to(workspace).as_posix() if workspace in f.parents else str(f)
        print(f"# {rel}")
        try:
            record = _json.loads(f.read_text(encoding="utf-8"))
            print(_json.dumps(record, indent=2, sort_keys=True))
        except Exception as e:
            print(f"(could not parse: {type(e).__name__}: {e})", file=sys.stderr)
    return 0


def cmd_audit_prune(argv: list[str]) -> int:
    """aiadra audit-prune <workspace> [--dry-run]

    Phase D (arc 20260531-10) per ADR/0026 §9: applies retention policy from
    `.aiadra/audit-config.yaml` (defaults: max_age_days=30, max_total_mb=50).
    Per Codex1 N2: `audit-prune` reads config in STRICT mode — parse errors
    surface to the operator (unlike emission-path which falls back to
    defaults silently).
    """
    import argparse
    p = argparse.ArgumentParser(prog="aiadra audit-prune")
    p.add_argument("workspace")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    from ..audit import load_audit_config, compute_prune_set, apply_prune
    try:
        config = load_audit_config(workspace, strict=True)
    except Exception as e:
        print(f"audit-prune: config parse failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    if args.dry_run:
        to_delete, to_keep = compute_prune_set(workspace, config)
        print(f"audit-prune dry-run: would delete {len(to_delete)} file(s); keep {len(to_keep)}.")
        for p_ in to_delete:
            try:
                rel = p_.relative_to(workspace).as_posix()
            except ValueError:
                rel = str(p_)
            print(f"  would delete: {rel}")
        return 0
    count, freed = apply_prune(workspace, config)
    print(f"audit-prune: deleted {count} file(s); freed {freed} bytes.")
    return 0


def cmd_migrate(argv: list[str]) -> int:
    """aiadra migrate <workspace> --to-bundle <version> [--dry-run]

    Phase 3 W3 (arc 20260531-4): chain-aware refactor. `--to-bundle` accepts
    any registered target version; chain walks from current pin through
    REGISTERED_STEPS, writing the final pin once atomically at chain end.
    """
    import argparse
    from ..validation.migration import (
        apply_migration,
        plan_migration,
        MigrationError,
        REGISTERED_STEPS,
    )
    # arc 20260602-3 Codex1 N5: the "already pinned to target but digest stale"
    # path raises BundleDigestMismatchError (NOT a MigrationError), so it
    # previously escaped this command's error handling and surfaced as an
    # uncaught traceback. Catch it as a normal migrate failure with an
    # actionable message + nonzero exit.
    from ..validation.bundle_registry import BundleDigestMismatchError
    target_choices = sorted({s.to_version for s in REGISTERED_STEPS})
    p = argparse.ArgumentParser(prog="aiadra migrate")
    p.add_argument("workspace")
    p.add_argument("--to-bundle", required=True, choices=target_choices)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    try:
        if args.dry_run:
            plan = plan_migration(workspace, args.to_bundle)
            print(f"Migration plan: {plan.from_bundle_version} → {plan.to_bundle_version}")
            for note in plan.notes:
                print(f"  - {note}")
            print(f"(dry-run; no files changed)")
        else:
            plan = apply_migration(workspace, args.to_bundle)
            print(f"Migrated: {plan.from_bundle_version} → {plan.to_bundle_version}")
            for note in plan.notes:
                print(f"  - {note}")
    except MigrationError as e:
        print(f"migration failed: {e}", file=sys.stderr)
        return 1
    except BundleDigestMismatchError as e:
        print(f"migration failed (stale pin digest): {e}", file=sys.stderr)
        return 1
    return 0
