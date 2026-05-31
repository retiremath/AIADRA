"""CLI command implementations — thin adapters around transaction/operations.

Each command:
1. Parses workspace + command-specific args.
2. Verifies project pin via BundleRegistry.
3. Builds a TransactionDraft via the appropriate operations function.
4. Runs draft.validate(); on FAIL outputs error + exits non-zero.
5. Runs draft.commit(); reports commit hash + event IDs.

Exit codes:
  0  success
  1  validation failure (schema / Profile / fold / reservation_integrity)
  2  CLI argument error / Object-not-found
  3  project pin failure (missing / digest mismatch)
  6  B6 revision binding error (mutation prohibited)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ..transaction.boundary import (
    CommitError,
    TransactionDraft,
    TransactionError,
    git_repo_dirty_for_aiadra_paths,
)
from ..transaction.operations import (
    attach_file,
    change_parameter,
    create_object,
    init_workspace,
    link_relationship,
    release,
)
from ..validation.binding import RevisionBindingError
from ..validation.bundle_registry import (
    BundleDigestMismatchError,
    BundleNotFoundError,
    BundleRegistry,
)
from ..validation.profile import ProfileViolationError
from ..validation.reservation_integrity import ReservationIntegrityError
from ..validation.release import ReleaseConsistencyError
from ..validation.schema import SchemaValidationError


def _registry() -> BundleRegistry:
    return BundleRegistry()


def _pin_bundle(workspace: Path):
    try:
        return _registry().bundle_for_pin(workspace)
    except (FileNotFoundError, BundleDigestMismatchError, BundleNotFoundError) as e:
        print(f"project pin failure: {e}", file=sys.stderr)
        sys.exit(3)


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
        # Fold mismatch comes from validation.fold.FoldInconsistencyError; catch broadly
        from ..validation.fold import FoldInconsistencyError
        if isinstance(e, FoldInconsistencyError):
            print(f"validation failed (FoldInconsistencyError): {e}", file=sys.stderr)
            return 1
        raise
    try:
        result = draft.commit()
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


# ---------------- CLI command entry points ----------------


def cmd_init(argv: list[str]) -> int:
    """aiadra init <workspace>"""
    if not argv:
        print("usage: aiadra init <workspace>", file=sys.stderr)
        return 2
    workspace = Path(argv[0]).resolve()
    bundle = _registry().latest()
    draft = init_workspace(workspace, bundle)
    # B9: dirty-guard skipped for init (workspace pre-init has no .git or only fresh files)
    return _run_draft(draft, allow_dirty_init=True)


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
    bundle = _pin_bundle(workspace)
    try:
        draft = create_object(
            workspace, bundle, obj_type, args.number, args.name,
            uuid=args.uuid, revision_id=args.revision_id,
        )
    except TransactionError as e:
        print(f"create-object failed: {e}", file=sys.stderr)
        return 2
    return _run_draft(draft)


def cmd_change_parameter(argv: list[str]) -> int:
    """aiadra change-parameter <workspace> <obj-number> <parameter-id> <new-value> <rationale>
                              [--provenance-category {human_input|ai_proposal|computed_result|measured}]
                              [--provenance-agent <ref>] [--provenance-derived-from <ref1,ref2,...>]

    Per F1 absorption Phase 2 (arc 20260531-3): optional provenance flags
    construct a `new_fact_provenance` dict that replaces the parameter's
    fact_provenance wholesale. If ANY --provenance-* flag is present,
    --provenance-category is REQUIRED. If none are present, fact_provenance
    is unchanged (Phase 1 backward-compat).
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
    bundle = _pin_bundle(workspace)
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
    try:
        draft = change_parameter(
            workspace, bundle, args.obj_number, args.parameter_id,
            args.new_value, args.rationale,
            new_fact_provenance=new_fact_provenance,
        )
    except TransactionError as e:
        print(f"change-parameter failed: {e}", file=sys.stderr)
        return 2
    return _run_draft(draft)


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
    bundle = _pin_bundle(workspace)
    try:
        draft = link_relationship(workspace, bundle, rel_type, args.source_number,
                                   args.target_number, relationship_id=args.relationship_id)
    except TransactionError as e:
        print(f"link failed: {e}", file=sys.stderr)
        return 2
    return _run_draft(draft)


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
    bundle = _pin_bundle(workspace)
    try:
        draft = attach_file(
            workspace, bundle, args.obj_number, Path(args.file_path), args.role,
            attachment_id=args.attachment_id,
            derived_from_attachment_id=args.derived_from_attachment_id,
            media_type=args.media_type,
        )
    except TransactionError as e:
        print(f"attach-file failed: {e}", file=sys.stderr)
        return 2
    return _run_draft(draft)


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
    bundle = _pin_bundle(workspace)
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
    try:
        draft = release(
            workspace, bundle, object_numbers,
            release_label=args.label,
            stage_number=args.stage,
            final_stage=not args.no_final,
            prior_stage_manifest_ref=prior_ref,
        )
    except TransactionError as e:
        print(f"release failed: {e}", file=sys.stderr)
        return 2
    return _run_draft(draft)


def cmd_migrate(argv: list[str]) -> int:
    """aiadra migrate <workspace> --to-bundle {0.20.0,0.21.0} [--dry-run]

    Phase 2 (arc 20260531-3): added 0.21.0 target dispatching to
    apply_migration_v0_20_0_to_v0_21_0.
    """
    import argparse
    from ..validation.migration import (
        apply_migration_v0_19_0_to_v0_20_0,
        apply_migration_v0_20_0_to_v0_21_0,
        plan_migration_v0_19_0_to_v0_20_0,
        plan_migration_v0_20_0_to_v0_21_0,
        MigrationError,
    )
    p = argparse.ArgumentParser(prog="aiadra migrate")
    p.add_argument("workspace")
    p.add_argument("--to-bundle", required=True, choices=["0.20.0", "0.21.0"])
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    plan_fn = {
        "0.20.0": plan_migration_v0_19_0_to_v0_20_0,
        "0.21.0": plan_migration_v0_20_0_to_v0_21_0,
    }[args.to_bundle]
    apply_fn = {
        "0.20.0": apply_migration_v0_19_0_to_v0_20_0,
        "0.21.0": apply_migration_v0_20_0_to_v0_21_0,
    }[args.to_bundle]
    try:
        if args.dry_run:
            plan = plan_fn(workspace)
            print(f"Migration plan: {plan.from_bundle_version} → {plan.to_bundle_version}")
            for note in plan.notes:
                print(f"  - {note}")
            print(f"(dry-run; no files changed)")
        else:
            plan = apply_fn(workspace)
            print(f"Migrated: {plan.from_bundle_version} → {plan.to_bundle_version}")
            for note in plan.notes:
                print(f"  - {note}")
    except MigrationError as e:
        print(f"migration failed: {e}", file=sys.stderr)
        return 1
    return 0
