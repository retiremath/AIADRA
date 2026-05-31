"""AIADRA Ring 2 AI Action Protocol — canonical Python entry points.

Per [ADR/0026](../../../Docs/ADR/0026-ai-action-protocol-scope.md) §"Sequencing"
**Phase A**. Formalizes the existing aiadra-core surface as the agent-facing
Ring 2 contract layer. Tier-1 in-process Python entry points; CLI is the
Tier-2 thin wrapper (`aiadra_core.cli`); Tier-3 RPC adapters (MCP, OpenAI
tools, LSP-style, custom JSON-RPC) live in SEPARATE ecosystem packages per
Manifesto P11 and ADR/0026 Decision §6.

**Phase A surface (5 of 9 ADR/0026 §2 contracts):**

- `inspect(workspace, object_ref, *, locality, staleness) -> ObjectView`
- `validate(workspace) -> ValidationReport`
- `commit(draft) -> CommitResult`
- `rollback(draft, *, reason=None) -> RollbackResult`
- `release(workspace, bundle, object_numbers, ...) -> TransactionDraft`

Future-phase contracts (`query` Phase B; `propose` / `modify` / `simulate`
Phase C; `explain` Phase D) are intentionally NOT exported — their absence is
clearer documentation than `NotImplementedError` stubs would be (Codex1 Q7
absorption, arc 20260531-7).

**BYO-AI posture per ADR/0026 §0**: AIADRA Core ships zero AI model code;
this module is a deterministic Python API that any agent (cloud LLM, local
LLM, deterministic script) can call.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..transaction.boundary import (
    CommitResult,
    RollbackResult,
    TransactionDraft,
    ValidationOutcome,
)
from ..transaction.operations import release as _release_op
from ..truth_model.reservation import list_reservation_prefixes
from ..truth_model.sidecar import list_working_sidecar_uuids
from ..validation.bundle_registry import (
    BundleDigestMismatchError,
    BundleHandle,
    BundleNotFoundError,
    BundleRegistry,
)
from ..validation.profile import ProfileViolationError
from ..validation.schema import (
    SchemaValidationError,
    load_reservation_validated,
    load_sidecar_validated,
)


# ---------- Locality / staleness API value sets (Phase A surface) ----------
#
# Per ADR/0026 §4 + Codex1 B2 absorption (arc 20260531-7): API values are
# pinned in Phase A; non-default behavior lands in Phase B. The distinction
# between "invalid value" (caller bug) and "recognized but unimplemented"
# (Phase B future) is enforced here.

_VALID_LOCALITY: frozenset[str] = frozenset({"always_local", "local_if_fetched", "remote_only"})
_VALID_STALENESS_EXACT: frozenset[str] = frozenset({"any", "must_sync"})
_DEFAULT_LOCALITY = "always_local"
_DEFAULT_STALENESS = "any"


def _check_locality_staleness(locality: str, staleness: str) -> None:
    """Codex1 B2 absorption: invalid → ValueError; recognized non-default → NotImplementedError."""
    if locality not in _VALID_LOCALITY:
        raise ValueError(
            f"Invalid locality {locality!r}; expected one of {sorted(_VALID_LOCALITY)} "
            f"per ADR/0001 §6 + ADR/0026 §4."
        )
    if staleness not in _VALID_STALENESS_EXACT and not staleness.startswith("fresh_within_"):
        raise ValueError(
            f"Invalid staleness {staleness!r}; expected one of {sorted(_VALID_STALENESS_EXACT)} "
            f"or `fresh_within_<duration>` per ADR/0026 §4."
        )
    if locality != _DEFAULT_LOCALITY or staleness != _DEFAULT_STALENESS:
        raise NotImplementedError(
            f"Non-default locality/staleness (locality={locality!r}, "
            f"staleness={staleness!r}) lands in Phase B per ADR/0026 §4. "
            f"Phase A supports default values only."
        )


# ---------- Phase A exception taxonomy ----------


class ObjectNotFoundError(KeyError):
    """Raised by `inspect()` when `object_ref` does not resolve to any
    on-disk Object (neither as a Number nor as a UUID)."""


class ProjectPinError(ValueError):
    """Raised by `inspect()` / `validate()` when the project pin
    (`.aiadra/schemas.yaml`) is missing, unknown, or digest-mismatched.

    Per Codex1 B3 absorption (arc 20260531-7): the single Ring 2 contract
    that wraps Phase 1's three pin-related exceptions (`FileNotFoundError`,
    `BundleNotFoundError`, `BundleDigestMismatchError`). The original
    exception is preserved as `__cause__` for callers that need to discriminate.

    CLI binding layers translate this to exit code 3 (project pin failure).
    """


# ---------- Phase A type shapes ----------


@dataclass(frozen=True)
class ObjectView:
    """Returned by `inspect()`. Frozen dataclass; `sidecar` is a deep copy
    of the loaded dict so caller mutations do not affect re-reads (Codex1 Q1
    absorption arc 20260531-7).

    Per ADR/0026 §5: every fact returned carries provenance intact. Agents
    that need provenance read it from `sidecar["parameter"][...]["fact_provenance"]`
    or equivalent nested paths.
    """
    object_uuid: str
    object_number: str
    object_type: str
    sidecar: dict[str, Any]
    bundle_version: str


@dataclass(frozen=True)
class ValidationReport:
    """Returned by `validate()`. Frozen dataclass with a tuple of outcomes
    so callers cannot mutate the list."""
    outcomes: tuple[ValidationOutcome, ...]
    failures_count: int
    bundle_version: str


# `RollbackResult` is defined in `aiadra_core.transaction.boundary` (next to
# `TransactionDraft.rollback()`) and re-exported here. Single source of truth
# avoids duplication; protocol module just surfaces it for agent type hints.


# ---------- Phase A: inspect ----------


def inspect(
    workspace: Path,
    object_ref: str,
    *,
    locality: str = _DEFAULT_LOCALITY,
    staleness: str = _DEFAULT_STALENESS,
) -> ObjectView:
    """Read a single Object's current working sidecar.

    `object_ref` accepts EITHER an Object Number (e.g. `P-000001`) OR a UUID.
    Resolution prefers Number-via-Reservation; falls back to UUID-via-direct-load
    when the input matches the canonical UUID pattern (Codex1 N3 absorption
    arc 20260531-7).

    Per ADR/0026 §4: `locality` and `staleness` are pinned in Phase A as
    explicit kwargs with workspace-local defaults; non-default values raise
    `NotImplementedError` per the Phase B sequencing.

    Raises:
        ValueError: invalid locality / staleness API value.
        NotImplementedError: recognized non-default locality / staleness; Phase B.
        ProjectPinError: pin lookup failed (missing / unknown / digest mismatch).
        ObjectNotFoundError: object_ref does not resolve to any on-disk Object.
        ProfileViolationError / SchemaValidationError: artifact loaded but invalid.
    """
    _check_locality_staleness(locality, staleness)

    registry = BundleRegistry()
    try:
        bundle = registry.bundle_for_pin(workspace)
    except (FileNotFoundError, BundleDigestMismatchError, BundleNotFoundError) as e:
        raise ProjectPinError(str(e)) from e

    bundle_dir = bundle.bundle_dir
    uuid_or_none = _resolve_ref_to_uuid(workspace, bundle_dir, object_ref)
    if uuid_or_none is None:
        raise ObjectNotFoundError(object_ref)
    uuid = uuid_or_none

    sidecar = load_sidecar_validated(workspace, uuid, bundle_dir)
    obj_block = sidecar.get("object", {})
    return ObjectView(
        object_uuid=obj_block.get("uuid", uuid),
        object_number=obj_block.get("number", ""),
        object_type=obj_block.get("type", ""),
        sidecar=copy.deepcopy(sidecar),
        bundle_version=bundle.bundle_version,
    )


_UUID_PATTERN = (
    "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _looks_like_uuid(s: str) -> bool:
    import re
    return bool(re.match(_UUID_PATTERN, s))


def _resolve_ref_to_uuid(workspace: Path, bundle_dir: Path, object_ref: str) -> str | None:
    """Resolve EITHER Object Number OR UUID to a UUID present on disk."""
    if _looks_like_uuid(object_ref):
        # UUID path: check that a working sidecar exists for it.
        on_disk = set(list_working_sidecar_uuids(workspace))
        return object_ref if object_ref in on_disk else None
    # Number path (existing _resolve_number_to_uuid logic, inlined here):
    if "-" not in object_ref:
        return None
    prefix = object_ref.split("-", 1)[0]
    if prefix not in list_reservation_prefixes(workspace):
        return None
    reservation = load_reservation_validated(workspace, prefix, bundle_dir)
    entry = reservation.get("reservations", {}).get(object_ref)
    if entry is None:
        return None
    return entry.get("object_uuid")


# ---------- Phase A: validate ----------


def validate(workspace: Path) -> ValidationReport:
    """Read-only workspace integrity check. Returns structured report.

    Per Codex1 N2 absorption (arc 20260531-7): protocol `validate()` is a
    PURE function — runs all read-side checks, returns `ValidationReport`,
    does NOT print or return exit codes. CLI emission stays in CLI land.

    Raises:
        ProjectPinError: pin lookup failed (no other checks run if pin fails).
    """
    from ..validation.binding import find_mutation_after_binding_violations
    from ..validation.fold import FoldInconsistencyError, validate_fold
    from ..validation.release import (
        ReleaseConsistencyError,
        validate_release_replay,
    )
    from ..validation.reservation_integrity import (
        ReservationIntegrityError,
        validate_reservation_rev_id_history,
    )
    from ..truth_model.manifest import list_release_labels
    from ..truth_model.revision import (
        RevisionHashMismatchError,
        verify_revision_hashes,
    )
    from ..validation.schema import (
        load_manifest_validated,
        load_revision_validated,
    )

    registry = BundleRegistry()
    try:
        bundle = registry.bundle_for_pin(workspace)
    except (FileNotFoundError, BundleDigestMismatchError, BundleNotFoundError) as e:
        raise ProjectPinError(str(e)) from e

    bundle_dir = bundle.bundle_dir
    outcomes: list[ValidationOutcome] = []
    failures = 0

    # 1. Project pin (always PASS — failure raised above before reaching here)
    outcomes.append(ValidationOutcome(
        "project_pin", "PASS",
        f"bundle v{bundle.bundle_version} digest matches",
    ))

    # 2. Reservations
    for prefix in list_reservation_prefixes(workspace):
        try:
            load_reservation_validated(workspace, prefix, bundle_dir)
            outcomes.append(ValidationOutcome(f"reservation({prefix})", "PASS", ""))
        except (ProfileViolationError, SchemaValidationError) as e:
            outcomes.append(ValidationOutcome(f"reservation({prefix})", "FAIL", str(e)))
            failures += 1

    # 3. Working sidecars
    for uuid in list_working_sidecar_uuids(workspace):
        try:
            sidecar = load_sidecar_validated(workspace, uuid, bundle_dir)
            obj_num = sidecar["object"]["number"]
            outcomes.append(ValidationOutcome(f"sidecar({obj_num})", "PASS", f"uuid={uuid}"))
        except (ProfileViolationError, SchemaValidationError) as e:
            outcomes.append(ValidationOutcome(f"sidecar({uuid})", "FAIL", str(e)))
            failures += 1

    # 4. Released Revisions referenced by Release Manifests
    for label in list_release_labels(workspace):
        try:
            manifest = load_manifest_validated(workspace, label, bundle_dir)
            outcomes.append(ValidationOutcome(
                f"manifest({label})", "PASS",
                f"manifest_type={manifest.get('manifest_type')}",
            ))
            for rev in manifest.get("revisions", []):
                obj_uuid = rev["object_uuid"]
                rev_id = rev["revision_id"]
                obj_num = rev["object_number"]
                try:
                    load_revision_validated(workspace, obj_uuid, rev_id, bundle_dir)
                    outcomes.append(ValidationOutcome(
                        f"revision({obj_num})", "PASS", f"rev_id={rev_id}",
                    ))
                except (ProfileViolationError, SchemaValidationError) as e:
                    outcomes.append(ValidationOutcome(
                        f"revision({obj_num})", "FAIL", str(e),
                    ))
                    failures += 1
            try:
                verify_revision_hashes(workspace, manifest.get("revisions", []))
                outcomes.append(ValidationOutcome(
                    f"revision_hashes({label})", "PASS",
                    f"{len(manifest.get('revisions', []))} hash(es) match",
                ))
            except RevisionHashMismatchError as e:
                outcomes.append(ValidationOutcome(
                    f"revision_hashes({label})", "FAIL", str(e),
                ))
                failures += 1
        except (ProfileViolationError, SchemaValidationError) as e:
            outcomes.append(ValidationOutcome(f"manifest({label})", "FAIL", str(e)))
            failures += 1

    # 5. Sidecar/event invariant
    try:
        validate_fold(workspace, bundle_dir)
        outcomes.append(ValidationOutcome(
            "fold_invariant", "PASS",
            "events ↔ working sidecars match bidirectionally",
        ))
    except FoldInconsistencyError as e:
        outcomes.append(ValidationOutcome("fold_invariant", "FAIL", str(e)))
        failures += 1
    except (ProfileViolationError, SchemaValidationError) as e:
        outcomes.append(ValidationOutcome(
            "fold_invariant", "FAIL", f"event-validation error during fold: {e}",
        ))
        failures += 1

    # 6. Reservation rev-id history (N3)
    try:
        validate_reservation_rev_id_history(workspace, bundle_dir, registry=registry)
        outcomes.append(ValidationOutcome(
            "reservation_integrity", "PASS",
            "released/current rev-id history canonical (N3 invariants 1+2+3)",
        ))
    except ReservationIntegrityError as e:
        outcomes.append(ValidationOutcome("reservation_integrity", "FAIL", str(e)))
        failures += 1
    except (ProfileViolationError, SchemaValidationError) as e:
        outcomes.append(ValidationOutcome(
            "reservation_integrity", "FAIL", f"schema error: {e}",
        ))
        failures += 1

    # 7. B6 mutation-after-binding final-release scan
    try:
        violations = find_mutation_after_binding_violations(
            workspace, bundle_dir, registry=registry,
        )
        if violations:
            for v in violations:
                outcomes.append(ValidationOutcome("binding_mutation_scan", "FAIL", v))
                failures += 1
        else:
            outcomes.append(ValidationOutcome(
                "binding_mutation_scan", "PASS",
                "no mutation events after unreleased Fixed execution-instance "
                "binding (B6 final scan)",
            ))
    except (ProfileViolationError, SchemaValidationError) as e:
        outcomes.append(ValidationOutcome(
            "binding_mutation_scan", "FAIL", f"schema error: {e}",
        ))
        failures += 1

    # 8. release_staged replay consistency (N2 + N4)
    try:
        validate_release_replay(workspace, bundle_dir, registry=registry)
        outcomes.append(ValidationOutcome(
            "release_replay_consistency", "PASS",
            "release_staged events agree with manifests + per-Object release "
            "events + Reservation history (N2/N4)",
        ))
    except ReleaseConsistencyError as e:
        outcomes.append(ValidationOutcome(
            "release_replay_consistency", "FAIL", str(e),
        ))
        failures += 1
    except (ProfileViolationError, SchemaValidationError) as e:
        outcomes.append(ValidationOutcome(
            "release_replay_consistency", "FAIL", f"schema error: {e}",
        ))
        failures += 1

    return ValidationReport(
        outcomes=tuple(outcomes),
        failures_count=failures,
        bundle_version=bundle.bundle_version,
    )


# ---------- Phase A: commit / rollback (terminal family) ----------


def commit(draft: TransactionDraft) -> CommitResult:
    """Atomic commit + git commit of a TransactionDraft.

    Free-function wrapper over `TransactionDraft.commit()` for the verb-noun
    terminal pairing with `rollback(draft)`. The instance method stays
    authoritative; this function does not modify it.
    """
    return draft.commit()


def rollback(draft: TransactionDraft, *, reason: str | None = None) -> RollbackResult:
    """Discard a TransactionDraft. Phase A: discard-only, no audit emission
    (Phase D per ADR/0026 §9 + Codex1 N1 absorption arc 20260531-7).

    Clears ALL staged mutable collections (per Codex1 Q5 absorption):
    sidecar_writes, sidecar_deletes, events, reservation_writes,
    revision_writes, manifest_writes, vault_writes, project_pin_write,
    commit_message_lines, pre_validate_hooks, post_validate_hooks.

    `discarded_change_count` is the sum of staged events + sidecars +
    reservations + revisions + manifests + vault byte chunks; useful for
    diagnostic display + future audit emission.
    """
    return draft.rollback(reason=reason)


# ---------- Phase A: release ----------


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
    """Multi-Object release Transaction. Returns TransactionDraft; caller
    invokes `draft.validate()` + `protocol.commit(draft)` (or `draft.commit()`)
    to apply.

    Re-export of `aiadra_core.transaction.operations.release`. No behavior
    change.
    """
    return _release_op(
        workspace, bundle, object_numbers,
        release_label=release_label,
        stage_number=stage_number,
        final_stage=final_stage,
        prior_stage_manifest_ref=prior_stage_manifest_ref,
    )


# ---------- Module exports ----------


__all__ = [
    # Operations
    "inspect",
    "validate",
    "commit",
    "rollback",
    "release",
    # Type shapes (Phase A)
    "ObjectView",
    "ValidationReport",
    "ValidationOutcome",
    "CommitResult",
    "RollbackResult",
    "TransactionDraft",
    # Exceptions (Phase A)
    "ObjectNotFoundError",
    "ProjectPinError",
]
