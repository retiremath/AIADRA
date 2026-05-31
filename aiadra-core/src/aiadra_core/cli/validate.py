"""`aiadra validate <workspace>` — read-only Layer-2 sweep.

Loads every artifact in the workspace, runs:
- AIADRA YAML Profile lint (via the validated load helpers)
- JSON Schema validation against the bundle-resolved schema
- Bundle digest verification against the project pin (.aiadra/schemas.yaml)
- Sidecar/event invariant fold check (bidirectional per Codex1 B3)

Reports per-check outcomes and a summary. Exit 0 on success; 1 on validation
failure; 3 on project pin mismatch.

Phase 0 scope: does NOT recompute release-time V&V chain integrity /
attachment lineage / execution cardinality (those land in Phase 1+); does
re-verify Revision hashes if a Release Manifest is present (read-only check).
"""
from __future__ import annotations

import sys
from pathlib import Path

from ..truth_model.manifest import list_release_labels
from ..truth_model.reservation import list_reservation_prefixes
from ..truth_model.revision import verify_revision_hashes, RevisionHashMismatchError
from ..truth_model.sidecar import list_working_sidecar_uuids
from ..validation.bundle_registry import (
    BundleDigestMismatchError,
    BundleNotFoundError,
    BundleRegistry,
)
from ..validation.digest import verify_project_pin  # Phase 0 back-compat re-export
from ..validation.fold import FoldInconsistencyError, validate_fold
from ..validation.profile import ProfileViolationError
from ..validation.schema import (
    SchemaValidationError,
    load_manifest_validated,
    load_reservation_validated,
    load_revision_validated,
    load_sidecar_validated,
)


def run_validate(workspace: Path) -> int:
    """Run all read-side checks against a workspace. Return exit code.

    Phase 1 (arc 20260531-2): uses BundleRegistry to honor project-pin's
    bundle_version. Phase 0 had only one packaged bundle; Phase 1 ships
    v0.19.0 + v0.20.0 side-by-side.
    """
    registry = BundleRegistry()
    outcomes: list[tuple[str, str, str]] = []  # (check_name, result, details)
    failures = 0

    # 1. Project pin / bundle digest (BundleRegistry path)
    try:
        bundle = registry.bundle_for_pin(workspace)
        bundle_dir = bundle.bundle_dir
        outcomes.append(("project_pin", "PASS", f"bundle v{bundle.bundle_version} digest matches"))
    except (FileNotFoundError, BundleDigestMismatchError, BundleNotFoundError) as e:
        outcomes.append(("project_pin", "FAIL", str(e)))
        _emit_outcomes(outcomes)
        print("FAILED: project pin or digest mismatch; aborting before reads.", file=sys.stderr)
        return 3

    # 2. Reservations
    for prefix in list_reservation_prefixes(workspace):
        try:
            load_reservation_validated(workspace, prefix, bundle_dir)
            outcomes.append((f"reservation({prefix})", "PASS", ""))
        except (ProfileViolationError, SchemaValidationError) as e:
            outcomes.append((f"reservation({prefix})", "FAIL", str(e)))
            failures += 1

    # 3. Working sidecars
    for uuid in list_working_sidecar_uuids(workspace):
        try:
            sidecar = load_sidecar_validated(workspace, uuid, bundle_dir)
            obj_num = sidecar["object"]["number"]
            outcomes.append((f"sidecar({obj_num})", "PASS", f"uuid={uuid}"))
        except (ProfileViolationError, SchemaValidationError) as e:
            outcomes.append((f"sidecar({uuid})", "FAIL", str(e)))
            failures += 1

    # 4. Released Revisions referenced by Release Manifests
    for label in list_release_labels(workspace):
        try:
            manifest = load_manifest_validated(workspace, label, bundle_dir)
            outcomes.append((f"manifest({label})", "PASS", f"manifest_type={manifest.get('manifest_type')}"))
            # Per-Revision schema validation
            for rev in manifest.get("revisions", []):
                obj_uuid = rev["object_uuid"]
                rev_id = rev["revision_id"]
                obj_num = rev["object_number"]
                try:
                    load_revision_validated(workspace, obj_uuid, rev_id, bundle_dir)
                    outcomes.append((f"revision({obj_num})", "PASS", f"rev_id={rev_id}"))
                except (ProfileViolationError, SchemaValidationError) as e:
                    outcomes.append((f"revision({obj_num})", "FAIL", str(e)))
                    failures += 1
            # Revision hashes verified against on-disk bytes (read-only)
            try:
                verify_revision_hashes(workspace, manifest.get("revisions", []))
                outcomes.append((f"revision_hashes({label})", "PASS", f"{len(manifest.get('revisions', []))} hash(es) match"))
            except RevisionHashMismatchError as e:
                outcomes.append((f"revision_hashes({label})", "FAIL", str(e)))
                failures += 1
        except (ProfileViolationError, SchemaValidationError) as e:
            outcomes.append((f"manifest({label})", "FAIL", str(e)))
            failures += 1

    # 5. Sidecar/event invariant — bidirectional per Codex1 B3
    try:
        validate_fold(workspace, bundle_dir)
        outcomes.append(("fold_invariant", "PASS", "events ↔ working sidecars match bidirectionally"))
    except FoldInconsistencyError as e:
        outcomes.append(("fold_invariant", "FAIL", str(e)))
        failures += 1
    except (ProfileViolationError, SchemaValidationError) as e:
        outcomes.append(("fold_invariant", "FAIL", f"event-validation error during fold: {e}"))
        failures += 1

    # 6. B8 absorption (Phase 1 round-5): Reservation rev-id history (N3 invariants)
    from ..validation.reservation_integrity import (
        ReservationIntegrityError,
        validate_reservation_rev_id_history,
    )
    try:
        validate_reservation_rev_id_history(workspace, bundle_dir, registry=registry)
        outcomes.append(("reservation_integrity",
                         "PASS",
                         "released/current rev-id history canonical (N3 invariants 1+2+3)"))
    except ReservationIntegrityError as e:
        outcomes.append(("reservation_integrity", "FAIL", str(e)))
        failures += 1
    except (ProfileViolationError, SchemaValidationError) as e:
        outcomes.append(("reservation_integrity", "FAIL", f"schema error: {e}"))
        failures += 1

    # 7. B8 absorption: B6 mutation-after-binding final-release scan (replay)
    from ..validation.binding import find_mutation_after_binding_violations
    try:
        violations = find_mutation_after_binding_violations(workspace, bundle_dir, registry=registry)
        if violations:
            for v in violations:
                outcomes.append(("binding_mutation_scan", "FAIL", v))
                failures += 1
        else:
            outcomes.append(("binding_mutation_scan",
                             "PASS",
                             "no mutation events after unreleased Fixed execution-instance binding (B6 final scan)"))
    except (ProfileViolationError, SchemaValidationError) as e:
        outcomes.append(("binding_mutation_scan", "FAIL", f"schema error: {e}"))
        failures += 1

    # 8. B8 absorption: release_staged replay consistency (N2 + N4)
    from ..validation.release import (
        ReleaseConsistencyError,
        validate_release_replay,
    )
    try:
        validate_release_replay(workspace, bundle_dir, registry=registry)
        outcomes.append(("release_replay_consistency",
                         "PASS",
                         "release_staged events agree with manifests + per-Object release events + Reservation history (N2/N4)"))
    except ReleaseConsistencyError as e:
        outcomes.append(("release_replay_consistency", "FAIL", str(e)))
        failures += 1
    except (ProfileViolationError, SchemaValidationError) as e:
        outcomes.append(("release_replay_consistency", "FAIL", f"schema error: {e}"))
        failures += 1

    _emit_outcomes(outcomes)
    print(f"\nSummary: {len(outcomes)} check(s); {failures} failure(s).")
    return 0 if failures == 0 else 1


def _emit_outcomes(outcomes: list[tuple[str, str, str]]) -> None:
    for name, result, details in outcomes:
        mark = "✓" if result == "PASS" else "✗"
        line = f"  {mark} {result}  {name}"
        if details:
            line += f"  — {details}"
        print(line)


def cli_main(argv: list[str]) -> int:
    if len(argv) < 1:
        print("usage: aiadra validate <workspace>", file=sys.stderr)
        return 2
    workspace = Path(argv[0]).resolve()
    if not workspace.exists():
        print(f"workspace does not exist: {workspace}", file=sys.stderr)
        return 2
    return run_validate(workspace)
