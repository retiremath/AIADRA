"""AIADRA Ring 2 AI Action Protocol — canonical Python entry points.

Per [ADR/0026](../../../Docs/ADR/0026-ai-action-protocol-scope.md) §"Sequencing"
**Phase A** + **Phase B** + **Phase C** + **Phase D**. **9-of-9 ADR/0026 §2
contract surface complete.** Formalizes the existing aiadra-core surface as
the agent-facing Ring 2 contract layer + adds `query` over cumulative
release graph + working set + makes locality/staleness kwargs operational +
lifts `TransactionDraft` to a first-class Ring 2 entity via `propose` /
`modify` + adds `simulate` (no-write structured-failure-collecting
validation) + `explain` (object/relationship history walks) +
`explain_failure` (failure-tree construction) + failed-Transaction audit
log emission per §9.

Tier-1 in-process Python entry points; CLI is the Tier-2 thin wrapper
(`aiadra_core.cli`); Tier-3 RPC adapters (MCP, OpenAI tools, LSP-style,
custom JSON-RPC) live in SEPARATE ecosystem packages per Manifesto P11 and
ADR/0026 Decision §6.

**Full Phase A+B+C+D surface (9 of 9 ADR/0026 §2 contracts):**

- `inspect(workspace, object_ref, *, locality, staleness) -> ObjectView`
- `query(workspace, *, kind, filter, locality, staleness) -> list[ObjectView]`
- `propose(workspace, *, kind, params, actor) -> TransactionDraft`
- `modify(draft, *, kind, params, actor) -> TransactionDraft`
- `propose_kinds() -> tuple[str, ...]`
- `modify_kinds() -> tuple[str, ...]`
- `simulate(draft) -> ValidationReport`                                      ← NEW Phase D
- `explain(workspace, ref, *, depth, locality, staleness) -> ExplanationTree`← NEW Phase D
- `explain_failure(failure, *, bundle_version, depth) -> ExplanationTree`    ← NEW Phase D
- `validate(workspace) -> ValidationReport`
- `commit(draft) -> CommitResult`
- `rollback(draft, *, reason, reason_classification, agent_ref) -> RollbackResult`
- `release(workspace, bundle, object_numbers, ..., release_label) -> TransactionDraft`

`commit` / `rollback` is one terminal family per ADR/0026 Codex1 N2
absorption (arc 20260531-6); `rollback` emits a failed-Transaction audit
record per ADR/0026 §9 before clearing.

No future-op stubs remain. The 9-of-9 surface is in place; future Ring 2
SCNs extend behavior (per-relationship-type schemas; richer ExplanationTree
detail kinds; etc.) but do not add named operations.

**BYO-AI posture per ADR/0026 §0**: AIADRA Core ships zero AI model code;
this module is a deterministic Python API that any agent (cloud LLM, local
LLM, deterministic script) can call.
"""
from __future__ import annotations

import copy
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..transaction.boundary import (
    CommitResult,
    RollbackResult,
    TransactionDraft,
    TransactionError,
    TransactionKind,
    ValidationOutcome,
)
from ..transaction.operations import (
    add_acceptance_criterion as _add_ac_op,
    attach_file as _attach_file_op,
    change_parameter as _change_param_op,
    create_object as _create_object_op,
    init_workspace as _init_op,
    link_relationship as _link_op,
    release as _release_op,
)
from ..truth_model.manifest import list_release_labels
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
    load_manifest_validated,
    load_reservation_validated,
    load_revision_validated,
    load_sidecar_validated,
)


# ---------- Locality / staleness API value sets ----------
#
# Per ADR/0026 §4 + Codex1 B2 absorption (arc 20260531-7): API values are
# pinned in Phase A; behavior lands in Phase B. The distinction between
# "invalid value" (caller bug) and "recognized non-default" (was Phase B
# future / NOW IMPLEMENTED in this arc 20260531-8) is enforced via two
# helpers — _validate_locality_staleness rejects invalid values (Phase A
# behavior; unchanged); _enforce_locality_staleness applies non-default
# semantics by triggering `git fetch` when needed (NEW Phase B).

_VALID_LOCALITY: frozenset[str] = frozenset({"always_local", "local_if_fetched", "remote_only"})
_VALID_STALENESS_EXACT: frozenset[str] = frozenset({"any", "must_sync"})
_DEFAULT_LOCALITY = "always_local"
_DEFAULT_STALENESS = "any"

# Phase B (arc 20260531-8 Codex1 B3): bounded timeout for git fetch subprocesses.
_FETCH_TIMEOUT_SECONDS = 30

# `fresh_within_<duration>` parser per Codex1 Q5 absorption: simple suffix
# `<integer>s|m|h|d`; reject zero / negative; reject unknown suffixes with
# ValueError.
_FRESH_WITHIN_PATTERN = re.compile(r"^fresh_within_(?P<n>\d+)(?P<unit>[smhd])$")
_FRESH_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def _validate_locality_staleness(locality: str, staleness: str) -> None:
    """Reject invalid API values. ValueError = caller bug (e.g. typo or
    wrong dimension). Does NOT enforce non-default semantics; that's
    `_enforce_locality_staleness`'s job."""
    if locality not in _VALID_LOCALITY:
        raise ValueError(
            f"Invalid locality {locality!r}; expected one of {sorted(_VALID_LOCALITY)} "
            f"per ADR/0001 §6 + ADR/0026 §4."
        )
    if staleness in _VALID_STALENESS_EXACT:
        return
    m = _FRESH_WITHIN_PATTERN.match(staleness)
    if m is None:
        raise ValueError(
            f"Invalid staleness {staleness!r}; expected one of {sorted(_VALID_STALENESS_EXACT)} "
            f"or `fresh_within_<N><unit>` where unit ∈ {{s,m,h,d}} and N > 0 per ADR/0026 §4."
        )
    n = int(m.group("n"))
    if n <= 0:
        raise ValueError(
            f"Invalid staleness {staleness!r}: duration must be positive (got {n})."
        )


def _parse_fresh_within_seconds(staleness: str) -> int:
    """Return the duration of a `fresh_within_<N><unit>` staleness in seconds.
    Caller MUST have already passed `_validate_locality_staleness`."""
    m = _FRESH_WITHIN_PATTERN.match(staleness)
    assert m is not None, "must have been validated already"
    return int(m.group("n")) * _FRESH_UNIT_SECONDS[m.group("unit")]


def _should_fetch(workspace: Path, locality: str, staleness: str) -> bool:
    """Decide whether `git fetch` is required for this (locality, staleness)
    combination per Codex1 B2 absorption matrix (arc 20260531-8):

    - `remote_only` always fetches.
    - `staleness="must_sync"` always fetches.
    - `staleness="fresh_within_<N><unit>"` fetches iff FETCH_HEAD missing or
      its mtime is older than the requested duration.
    - `locality="local_if_fetched"` with no FETCH_HEAD fetches once (per
      ADR/0001 §6 "Free if pulled; one fetch otherwise").
    """
    if locality == "remote_only":
        return True
    if staleness == "must_sync":
        return True
    fetch_head = workspace / ".git" / "FETCH_HEAD"
    if staleness != _DEFAULT_STALENESS and _FRESH_WITHIN_PATTERN.match(staleness):
        if not fetch_head.exists():
            return True
        max_age = _parse_fresh_within_seconds(staleness)
        import time
        age = time.time() - fetch_head.stat().st_mtime
        return age > max_age
    if locality == "local_if_fetched" and not fetch_head.exists():
        return True
    return False


def _run_git_fetch(workspace: Path, *, timeout: int = _FETCH_TIMEOUT_SECONDS) -> None:
    """Run `git fetch origin` with a bounded timeout. Per Codex1 B3 absorption
    arc 20260531-8: any failure (subprocess error / timeout / missing git /
    no remote configured) raises `NetworkUnreachableError`.

    Protocol-local subprocess wrapper rather than reusing transaction.boundary._git
    so the Transaction subprocess shape remains timeout-free (per Codex1 Q7
    absorption — `_git` reuse okay but not required; protocol-local helper
    acceptable).
    """
    try:
        subprocess.run(
            ["git", "fetch", "origin"],
            cwd=workspace,
            check=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise NetworkUnreachableError(
            f"git fetch origin timed out after {timeout}s in {workspace}"
        ) from e
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or b"").decode("utf-8", errors="replace").strip()
        raise NetworkUnreachableError(
            f"git fetch origin failed in {workspace}: {stderr}"
        ) from e
    except FileNotFoundError as e:
        raise NetworkUnreachableError(
            f"git binary not found; cannot fetch in {workspace}"
        ) from e


def _enforce_locality_staleness(
    workspace: Path,
    locality: str,
    staleness: str,
    *,
    timeout: int = _FETCH_TIMEOUT_SECONDS,
) -> None:
    """Phase B (arc 20260531-8): trigger `git fetch origin` when the locality
    + staleness matrix requires it. Failure raises `NetworkUnreachableError`.

    Callers MUST have first run `_validate_locality_staleness` (Phase A gate).
    For the default `(always_local, any)` combination this is a no-op.
    """
    if _should_fetch(workspace, locality, staleness):
        _run_git_fetch(workspace, timeout=timeout)


# ---------- Phase A exception taxonomy + Phase B additions ----------


class ObjectNotFoundError(KeyError):
    """Raised by `inspect()` when `object_ref` does not resolve to any
    on-disk Object (neither as a Number nor as a UUID)."""


class ProjectPinError(ValueError):
    """Raised by `inspect()` / `query()` / `validate()` when the project pin
    (`.aiadra/schemas.yaml`) is missing, unknown, or digest-mismatched.

    Per Codex1 B3 absorption (arc 20260531-7): the single Ring 2 contract
    that wraps Phase 1's three pin-related exceptions (`FileNotFoundError`,
    `BundleNotFoundError`, `BundleDigestMismatchError`). The original
    exception is preserved as `__cause__`.
    """


class NetworkUnreachableError(ConnectionError):
    """Raised by `inspect()` / `query()` when a locality/staleness operation
    needs network access but the `git fetch origin` subprocess fails (timeout,
    non-zero exit, no remote configured, missing git binary, auth failure).

    Per Codex1 B3 absorption (arc 20260531-8): wraps subprocess errors with
    a bounded timeout (default 30s). Original exception preserved as
    `__cause__`.
    """


# ---------- Phase A type shapes (Phase B extends ObjectView) ----------


@dataclass(frozen=True)
class ObjectView:
    """Returned by `inspect()` and `query()`. Frozen dataclass; `sidecar` is
    a deep copy of the loaded dict so caller mutations do not affect re-reads
    (Codex1 Q1 absorption arc 20260531-7).

    Per ADR/0026 §5: every fact returned carries provenance intact. Agents
    that need provenance read it from `sidecar["parameter"][...]["fact_provenance"]`
    or equivalent nested paths.

    Phase B (arc 20260531-8 Codex1 B1) extends with `source` / `revision_id`
    / `release_label`. `source="working"` (default) is the Phase A behavior;
    Phase B `query` also returns `source="released_revision"` views from the
    cumulative release graph, in which case `revision_id` + `release_label`
    identify the specific released Revision.
    """
    object_uuid: str
    object_number: str
    object_type: str
    sidecar: dict[str, Any]
    bundle_version: str
    source: str = "working"  # "working" | "released_revision"
    revision_id: str | None = None  # set iff source == "released_revision"
    release_label: str | None = None  # set iff source == "released_revision"


@dataclass(frozen=True)
class ValidationReport:
    """Returned by `validate()`. Frozen dataclass with a tuple of outcomes
    so callers cannot mutate the list."""
    outcomes: tuple[ValidationOutcome, ...]
    failures_count: int
    bundle_version: str


# ---------- Internal helpers ----------


_UUID_PATTERN = (
    "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _looks_like_uuid(s: str) -> bool:
    return bool(re.match(_UUID_PATTERN, s))


def _resolve_ref_to_uuid(workspace: Path, bundle_dir: Path, object_ref: str) -> str | None:
    """Resolve EITHER Object Number OR UUID to a UUID present on disk."""
    if _looks_like_uuid(object_ref):
        on_disk = set(list_working_sidecar_uuids(workspace))
        return object_ref if object_ref in on_disk else None
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


def _object_view_from_sidecar(
    sidecar: dict[str, Any],
    bundle_version: str,
    *,
    fallback_uuid: str = "",
    source: str = "working",
    revision_id: str | None = None,
    release_label: str | None = None,
) -> ObjectView:
    """Codex1 N2 absorption arc 20260531-8: factor the ObjectView construction
    so working-sidecar reads (inspect) and released-Revision reads (query)
    share identical provenance / deep-copy / bundle-version behavior.
    """
    obj_block = sidecar.get("object", {})
    return ObjectView(
        object_uuid=obj_block.get("uuid", fallback_uuid),
        object_number=obj_block.get("number", ""),
        object_type=obj_block.get("type", ""),
        sidecar=copy.deepcopy(sidecar),
        bundle_version=bundle_version,
        source=source,
        revision_id=revision_id,
        release_label=release_label,
    )


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

    Per ADR/0026 §4 + Phase B (arc 20260531-8): `locality` and `staleness`
    are operational kwargs. Non-default values may trigger `git fetch origin`
    against the project's remote; subprocess failure raises
    `NetworkUnreachableError`.

    Raises:
        ValueError: invalid locality / staleness API value.
        NetworkUnreachableError: required `git fetch` failed (timeout / no
            remote / subprocess error / missing git).
        ProjectPinError: pin lookup failed (missing / unknown / digest mismatch).
        ObjectNotFoundError: object_ref does not resolve to any on-disk Object.
        ProfileViolationError / SchemaValidationError: artifact loaded but invalid.
    """
    _validate_locality_staleness(locality, staleness)
    _enforce_locality_staleness(workspace, locality, staleness)

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
    return _object_view_from_sidecar(
        sidecar,
        bundle.bundle_version,
        fallback_uuid=uuid,
        source="working",
    )


# ---------- Phase B: query ----------


def query(
    workspace: Path,
    *,
    kind: str | None = None,
    filter: Callable[[ObjectView], bool] | None = None,
    locality: str = _DEFAULT_LOCALITY,
    staleness: str = _DEFAULT_STALENESS,
) -> list[ObjectView]:
    """Cross-Object query over cumulative release graph + working set
    (Codex1 B1 absorption arc 20260531-8 per ADR/0026 §"Sequencing" Phase B).

    Returns a deterministically-ordered list of `ObjectView`:
      1. working views (sidecars on disk), sorted by object_number.
      2. released-Revision views (from on-disk release manifests), sorted by
         (release_label, object_number).

    A working view and a released view for the same Object are BOTH returned;
    agents distinguish them via `ObjectView.source` + `revision_id` +
    `release_label` (per Codex1 B1).

    `kind`: optional Object Type filter (e.g. "Part"); `None` = all kinds.
    `filter`: optional Python predicate `(view) -> bool`. Internally bound
              to `predicate` to avoid shadowing the builtin (Codex1 N1).
    `locality` / `staleness`: per ADR/0026 §4; may trigger `git fetch origin`
              per the Phase B matrix.

    Raises (same taxonomy as `inspect`; fail-loud per Codex2 B1 arc 20260531-8 R3):
        ValueError, NetworkUnreachableError, ProjectPinError,
        ProfileViolationError, SchemaValidationError.

    `query` is an AI read primitive over the Product Truth, NOT a best-effort
    search index. Invalid working sidecars / Release Manifests / Revisions
    propagate their schema/profile errors rather than being silently skipped
    — agents need to know when the substrate is corrupt because downstream
    actions may be based on the returned view. Agents that want to filter
    out failures should call `validate()` first to surface them explicitly.
    """
    predicate = filter  # Codex1 N1: rebind to avoid shadowing builtin
    _validate_locality_staleness(locality, staleness)
    _enforce_locality_staleness(workspace, locality, staleness)

    registry = BundleRegistry()
    try:
        bundle = registry.bundle_for_pin(workspace)
    except (FileNotFoundError, BundleDigestMismatchError, BundleNotFoundError) as e:
        raise ProjectPinError(str(e)) from e

    bundle_dir = bundle.bundle_dir
    bundle_version = bundle.bundle_version

    # Pass 1: working sidecars. Per Codex2 B1 absorption (arc 20260531-8 R3):
    # invalid working sidecars MUST fail loudly. Agents that want lenient
    # iteration can call `validate()` first to surface failures explicitly.
    # Silent skipping hides corrupted Product Truth from AI read consumers
    # and contradicts the function's advertised raise taxonomy.
    working_views: list[ObjectView] = []
    for uuid in list_working_sidecar_uuids(workspace):
        sidecar = load_sidecar_validated(workspace, uuid, bundle_dir)
        view = _object_view_from_sidecar(
            sidecar, bundle_version,
            fallback_uuid=uuid,
            source="working",
        )
        working_views.append(view)
    working_views.sort(key=lambda v: (v.object_number, v.object_uuid))

    # Pass 2: released Revisions from manifest list. Per Codex2 B1: invalid
    # Release Manifests and Revisions fail loudly. Missing fields on a
    # validated manifest's revisions[] entry would mean schema validation
    # was bypassed; treat as explicit SchemaValidationError rather than
    # silently skipping.
    released_views: list[ObjectView] = []
    for label in sorted(list_release_labels(workspace)):
        manifest = load_manifest_validated(workspace, label, bundle_dir)
        per_release: list[ObjectView] = []
        for rev in manifest.get("revisions", []) or []:
            obj_uuid = rev.get("object_uuid")
            rev_id = rev.get("revision_id")
            if not obj_uuid or not rev_id:
                raise SchemaValidationError(
                    f"manifest({label}) revisions[] entry missing required "
                    f"object_uuid or revision_id: {rev!r}"
                )
            content = load_revision_validated(
                workspace, obj_uuid, rev_id, bundle_dir,
            )
            view = _object_view_from_sidecar(
                content, bundle_version,
                fallback_uuid=obj_uuid,
                source="released_revision",
                revision_id=rev_id,
                release_label=label,
            )
            per_release.append(view)
        per_release.sort(key=lambda v: (v.object_number, v.object_uuid))
        released_views.extend(per_release)

    all_views = working_views + released_views

    # Filter by kind + predicate
    if kind is not None:
        all_views = [v for v in all_views if v.object_type == kind]
    if predicate is not None:
        all_views = [v for v in all_views if predicate(v)]
    return all_views


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
    from ..truth_model.revision import (
        RevisionHashMismatchError,
        verify_revision_hashes,
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


def rollback(
    draft: TransactionDraft,
    *,
    reason: str | None = None,
    reason_classification: str = "other",
    agent_ref: str | None = None,
) -> RollbackResult:
    """Discard a TransactionDraft.

    Clears ALL staged mutable collections (per Codex1 Q5 absorption arc
    20260531-7): sidecar_writes, sidecar_deletes, events, reservation_writes,
    revision_writes, manifest_writes, vault_writes, project_pin_write,
    commit_message_lines, pre_validate_hooks, post_validate_hooks.

    Phase D (arc 20260531-10) per ADR/0026 §9: emits a failed-Transaction
    audit record at `.aiadra/audit/YYYY-MM-DD/tx_NNNN-failed-<short>.jsonl`
    BEFORE clearing IF the draft has staged content AND no prior audit
    emission via `draft.audit_failure()`. Audit emission failure NEVER
    masks rollback semantics (Codex1 Q5).

    `reason_classification` is one of the 6 enum values per ADR/0026 §9
    (`schema_validation` / `profile_violation` / `fold_inconsistency` /
    `binding_violation` / `release_consistency` / `other`); defaults to
    `"other"`. `agent_ref` is optional per Codex1 N1 — CLI omits, Python
    agents pass.

    `discarded_change_count` is the sum of staged events + sidecars +
    reservations + revisions + manifests + vault byte chunks.
    """
    return draft.rollback(
        reason=reason,
        reason_classification=reason_classification,
        agent_ref=agent_ref,
    )


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


# ---------- Phase C: propose / modify ----------
#
# Per [ADR/0026](../../../Docs/ADR/0026-ai-action-protocol-scope.md) §"Sequencing"
# Phase C: `propose` allocates a fresh `TransactionDraft` for a named kind;
# `modify` extends an existing draft by stacking another operation on it.
# Underlying `transaction.operations.*` were extended with `existing_draft`
# kwargs in this arc (Codex1 B1 absorption) so a single Transaction can
# carry create + mutate + link without intermediate commits.
#
# Codex1 B2 absorption (arc 20260531-9):
#   - `propose(kind="init")` resolves bundle via `BundleRegistry().latest()`
#     because there is no project pin yet.
#   - All other kinds resolve via `bundle_for_pin(workspace)`.
#   - `modify(kind="init")` is REJECTED (init bootstraps an empty workspace).
#   - `modify(kind="release")` is REJECTED (release allocates fresh
#     current_revision_ids + validates the whole post-release graph; cannot
#     compose with in-flight mutations in the same Transaction without
#     conflating authorship and publication).
#
# Codex1 B4 absorption (arc 20260531-9): `actor` defaults to `"agent"`. The
# CLI binding for the human-driven change-parameter path passes `actor="human"`.
# `change_parameter` raises if `actor="agent"` AND `new_fact_provenance.category
# == "human_input"` per ADR/0026 §5 (AI agents MUST NOT self-attest as humans).


def _propose_init(workspace, bundle, params, actor, existing_draft):
    if existing_draft is not None:
        raise TransactionError(
            "init cannot be composed (Codex1 B2 absorption arc 20260531-9): "
            "init bootstraps an empty workspace and must start a fresh "
            "Transaction. Call protocol.propose(kind='init') to begin."
        )
    return _init_op(workspace, bundle)


def _propose_create_object_factory(obj_type: str):
    def handler(workspace, bundle, params, actor, existing_draft):
        return _create_object_op(
            workspace, bundle, obj_type,
            params["number"], params["name"],
            uuid=params.get("uuid"),
            revision_id=params.get("revision_id"),
            extra_namespaces=params.get("extra_namespaces"),
            existing_draft=existing_draft,
        )
    return handler


def _propose_change_parameter(workspace, bundle, params, actor, existing_draft):
    return _change_param_op(
        workspace, bundle,
        params["obj_number"], params["parameter_id"],
        params["new_value"], params["rationale"],
        new_fact_provenance=params.get("new_fact_provenance"),
        actor=actor,
        existing_draft=existing_draft,
    )


def _propose_add_acceptance_criterion(workspace, bundle, params, actor, existing_draft):
    return _add_ac_op(
        workspace, bundle,
        params["req_number"], params["criterion_id"], params["criterion_text"],
        language=params.get("language", "en"),
        format=params.get("format", "freeform"),
        threshold_expression=params.get("threshold_expression"),
        verification_method=params.get("verification_method"),
        references=params.get("references"),
        name=params.get("name"),
        existing_draft=existing_draft,
    )


def _propose_link_relationship_factory(rel_type: str):
    def handler(workspace, bundle, params, actor, existing_draft):
        return _link_op(
            workspace, bundle, rel_type,
            params["source_number"], params["target_number"],
            relationship_id=params.get("relationship_id"),
            existing_draft=existing_draft,
        )
    return handler


def _propose_attach_file(workspace, bundle, params, actor, existing_draft):
    return _attach_file_op(
        workspace, bundle,
        params["obj_number"], params["file_path"], params["role"],
        attachment_id=params.get("attachment_id"),
        derived_from_attachment_id=params.get("derived_from_attachment_id"),
        media_type=params.get("media_type"),
        existing_draft=existing_draft,
    )


def _propose_release(workspace, bundle, params, actor, existing_draft):
    if existing_draft is not None:
        raise TransactionError(
            "release cannot be composed (Codex1 B2 absorption arc 20260531-9): "
            "release allocates fresh current_revision_ids and validates the "
            "entire post-release graph; composing with in-flight mutations "
            "would conflate authorship and publication. Call "
            "protocol.propose(kind='release') as a standalone Transaction."
        )
    return _release_op(
        workspace, bundle,
        params["object_numbers"],
        release_label=params.get("release_label"),
        stage_number=params.get("stage_number", 1),
        final_stage=params.get("final_stage", True),
        prior_stage_manifest_ref=params.get("prior_stage_manifest_ref"),
    )


# Dispatch table — keys ARE the public propose-kind catalogue.
_PROPOSE_DISPATCH: dict[str, Callable[..., TransactionDraft]] = {
    "init": _propose_init,
    "create_part":             _propose_create_object_factory("Part"),
    "create_requirement":      _propose_create_object_factory("Requirement"),
    "create_test_procedure":   _propose_create_object_factory("TestProcedure"),
    "create_test_execution":   _propose_create_object_factory("TestExecution"),
    "create_evidence_artifact": _propose_create_object_factory("EvidenceArtifact"),
    "change_parameter": _propose_change_parameter,
    "add_acceptance_criterion": _propose_add_acceptance_criterion,
    "link_satisfies":      _propose_link_relationship_factory("satisfies"),
    "link_tested_against": _propose_link_relationship_factory("tested_against"),
    "link_verifies":       _propose_link_relationship_factory("verifies"),
    "link_cites":          _propose_link_relationship_factory("cites"),
    "link_executes":       _propose_link_relationship_factory("executes"),
    "link_executed_on":    _propose_link_relationship_factory("executed_on"),
    "link_produces":       _propose_link_relationship_factory("produces"),
    "attach_file": _propose_attach_file,
    "release": _propose_release,
}

# Kinds REJECTED from modify per Codex1 B2 absorption.
_MODIFY_REJECTED_KINDS: frozenset[str] = frozenset({"init", "release"})


def propose_kinds() -> tuple[str, ...]:
    """Introspection: sorted tuple of all kinds accepted by `propose`."""
    return tuple(sorted(_PROPOSE_DISPATCH.keys()))


def modify_kinds() -> tuple[str, ...]:
    """Introspection: sorted tuple of all kinds accepted by `modify`
    (= propose_kinds() minus init + release per Codex1 B2 absorption)."""
    return tuple(sorted(k for k in _PROPOSE_DISPATCH if k not in _MODIFY_REJECTED_KINDS))


def propose(
    workspace: Path,
    *,
    kind: str,
    params: dict[str, Any],
    actor: str = "agent",
) -> TransactionDraft:
    """Create a fresh `TransactionDraft` for the named kind.

    Per ADR/0026 §"Sequencing" Phase C: the catalogue of `kind` values is
    `propose_kinds()`. Each kind is a state-changing operation; this returns
    a draft for the caller to subsequently `modify()` (compose more ops),
    `simulate()` (Phase D — not yet implemented), or `commit()`.

    `params` is a kwargs-style dict; per-kind keys mirror the underlying
    `transaction.operations.*` function signatures.

    `actor`: per ADR/0026 §5 (Codex1 B4 absorption arc 20260531-9), one of
    `"agent"` (default) or `"human"`. Only `change_parameter` currently
    consumes this; other kinds ignore it. CLI bindings that know the
    operator is a human pass `actor="human"`.

    Raises:
        ValueError: invalid `kind` or invalid `actor`.
        ProjectPinError: pin lookup failed (for all kinds except `init`).
        TransactionError: kind-specific validation failure.
    """
    if actor not in ("agent", "human"):
        raise ValueError(
            f"Invalid actor {actor!r}; expected 'agent' or 'human' "
            f"per ADR/0026 §5 (Codex1 B4 absorption arc 20260531-9)."
        )
    if kind not in _PROPOSE_DISPATCH:
        raise ValueError(
            f"Unknown propose kind {kind!r}; expected one of {propose_kinds()}."
        )

    if kind == "init":
        # B2: init has no project pin yet; resolve via BundleRegistry().latest().
        bundle = BundleRegistry().latest()
    else:
        try:
            bundle = BundleRegistry().bundle_for_pin(workspace)
        except (FileNotFoundError, BundleDigestMismatchError, BundleNotFoundError) as e:
            raise ProjectPinError(str(e)) from e

    return _PROPOSE_DISPATCH[kind](workspace, bundle, params, actor, None)


def modify(
    draft: TransactionDraft,
    *,
    kind: str,
    params: dict[str, Any],
    actor: str = "agent",
) -> TransactionDraft:
    """Extend an existing `TransactionDraft` with another operation.

    Returns the SAME draft instance (mutation in place) so callers can chain:

        draft = propose(workspace, kind="create_part", params={"number": "P-000001", "name": "Bracket"})
        modify(draft, kind="change_parameter", params={...})
        commit(draft)

    Per Codex1 B2 absorption (arc 20260531-9): `kind="init"` and
    `kind="release"` are REJECTED — init bootstraps an empty workspace,
    release allocates fresh current_revision_ids and validates the entire
    post-release graph; neither composes with in-flight mutations.

    Per Codex1 B3 absorption (arc 20260531-9): if `draft` is in a terminal
    state (committed or rolled-back), the underlying `_begin_or_extend_draft`
    raises `TransactionError` via `draft._assert_open("modify")`.

    `actor`: same semantics as `propose` (Codex1 B4 absorption).

    Raises:
        ValueError: invalid `kind` or invalid `actor`.
        TransactionError: kind rejected (init/release), draft terminal, or
            kind-specific validation failure.
    """
    if actor not in ("agent", "human"):
        raise ValueError(
            f"Invalid actor {actor!r}; expected 'agent' or 'human' "
            f"per ADR/0026 §5 (Codex1 B4 absorption arc 20260531-9)."
        )
    if kind in _MODIFY_REJECTED_KINDS:
        if kind == "init":
            raise TransactionError(
                "modify(kind='init') not allowed: init bootstraps an empty "
                "workspace and must start a fresh Transaction (Codex1 B2 "
                "absorption arc 20260531-9)."
            )
        raise TransactionError(
            "modify(kind='release') not allowed: release allocates fresh "
            "current_revision_ids and validates the entire post-release "
            "graph; composing with in-flight mutations would conflate "
            "authorship and publication (Codex1 B2 absorption arc 20260531-9). "
            "Use propose(kind='release') as a standalone Transaction."
        )
    if kind not in _PROPOSE_DISPATCH:
        raise ValueError(
            f"Unknown modify kind {kind!r}; expected one of {modify_kinds()}."
        )

    return _PROPOSE_DISPATCH[kind](
        draft.workspace, draft.bundle, params, actor, draft,
    )


# ---------- Phase D: simulate / explain / explain_failure ----------
#
# Per [ADR/0026 §"Sequencing" Phase D](../../../Docs/ADR/0026-ai-action-protocol-scope.md):
# - `simulate(draft) → ValidationReport` (Codex2 N1 absorption arc 20260531-6:
#   "simulate and validate are functionally identical no-write operations").
#   Phase D Codex1 B1 absorption (arc 20260531-10): simulate MUST return
#   structured FAIL outcomes (no exceptions, no audit) so agents can iterate
#   over failure trees without side effects. Achieved via
#   `TransactionDraft.simulate()` which calls `_validate_internal(collect_failures=True)`.
# - `explain(workspace, ref, *, depth=1) → ExplanationTree`: object/relationship
#   history walk. Phase D Codex1 B2 absorption: SIBLING to `explain_failure`
#   (workspace-ref-based traversal).
# - `explain_failure(failure, *, depth=0) → ExplanationTree`: failure-tree
#   construction. Phase D Codex1 B2 absorption: satisfies ADR/0026's
#   `explain(failure, *, depth)` contract directly. Accepts a `ValidationOutcome`
#   with `tree` populated OR a bare `ExplanationNode`.


def simulate(draft: TransactionDraft) -> "ValidationReport":
    """No-write validation pass over a `TransactionDraft`. Returns a
    `ValidationReport` carrying ALL validation outcomes — both PASS and FAIL
    — without raising on known validation exceptions (per Codex1 B1
    absorption arc 20260531-10). Agents reason over the structured failure
    trees in each FAIL outcome's `tree` field.

    Per Codex2 N1 absorption (arc 20260531-6): simulate and validate are
    functionally identical no-write operations differing in lifecycle
    position — `simulate` is iterative agent reasoning over a draft;
    `validate(workspace)` is the post-commit/standalone gate.

    Per Codex1 B1: simulate emits NO audit (no failed-Transaction record
    written). Commit-path validation continues to raise on first failure.

    Asserts open per Codex1 B3 lifecycle pattern (Phase C); raises
    `TransactionError` on closed drafts.
    """
    outcomes = draft.simulate()
    failures = sum(1 for o in outcomes if o.result == "FAIL")
    return ValidationReport(
        outcomes=tuple(outcomes),
        failures_count=failures,
        bundle_version=draft.bundle.bundle_version,
    )


def explain(
    workspace: Path,
    ref: str,
    *,
    depth: int = 1,
    locality: str = _DEFAULT_LOCALITY,
    staleness: str = _DEFAULT_STALENESS,
) -> "ExplanationTree":
    """Walk an Object or Relationship's history into an `ExplanationTree`.

    `ref` accepts:
      - Object Number: `"P-000001"`
      - Object UUID: `"0193abcd-1234-7890-abcd-444444444444"`
      - Relationship ref: `"<obj-ref>:relationship:<rel_id>"` per ADR/0015
        fact-level addressing pattern.

    Root node carries an `object_node()` (or `relationship_node()`); children
    are event nodes (ordered by event_id ascending) for events that affected
    this ref + any deeper traversal (for `depth>0`, walks ALL relationship
    types where the Object is source or target, capped at `depth` per Codex
    Q3+N4 absorption; deterministic ordering by
    `(relationship.type, relationship.id, endpoint.object_uuid)` with a
    visited set so graph cycles cannot explode the tree per Codex N4).

    Per Codex1 B2 absorption (arc 20260531-10): sibling to `explain_failure`;
    this function explains canonical Truth Model state; `explain_failure`
    explains failure trees. Both return `ExplanationTree`.
    """
    from ..explain import (
        ExplanationTree, KIND_RELATIONSHIP,
        event_node, object_node, relationship_node,
    )

    _validate_locality_staleness(locality, staleness)
    _enforce_locality_staleness(workspace, locality, staleness)

    registry = BundleRegistry()
    try:
        bundle = registry.bundle_for_pin(workspace)
    except (FileNotFoundError, BundleDigestMismatchError, BundleNotFoundError) as e:
        raise ProjectPinError(str(e)) from e
    bundle_dir = bundle.bundle_dir

    # Relationship ref parses as "<obj-ref>:relationship:<rel_id>"
    rel_id: str | None = None
    obj_ref = ref
    if ":relationship:" in ref:
        obj_ref, _, rel_id = ref.partition(":relationship:")

    uuid_or_none = _resolve_ref_to_uuid(workspace, bundle_dir, obj_ref)
    if uuid_or_none is None:
        raise ObjectNotFoundError(obj_ref)
    obj_uuid = uuid_or_none

    sidecar = load_sidecar_validated(workspace, obj_uuid, bundle_dir)
    obj_block = sidecar.get("object", {})

    # If relationship ref, focus root on the relationship record
    if rel_id is not None:
        rels = sidecar.get("relationship", []) or []
        match = next((r for r in rels if r.get("id") == rel_id), None)
        if match is None:
            raise ObjectNotFoundError(f"{obj_ref}:relationship:{rel_id}")
        root = relationship_node(
            source_uuid=obj_uuid,
            relationship_id=rel_id,
            type=match.get("type", ""),
            endpoints=list(match.get("endpoints", []) or []),
            children=_walk_object_event_history(workspace, bundle_dir, obj_uuid),
        )
    else:
        root_children: list = list(_walk_object_event_history(workspace, bundle_dir, obj_uuid))
        if depth > 0:
            related = _walk_related_objects(
                workspace, bundle_dir, obj_uuid, sidecar,
                depth=depth, visited={obj_uuid},
            )
            root_children.extend(related)
        root = object_node(
            number=obj_block.get("number", ""),
            uuid=obj_uuid,
            type=obj_block.get("type", ""),
            source="working",
            children=tuple(root_children),
        )
    return ExplanationTree(root=root, bundle_version=bundle.bundle_version)


def _walk_object_event_history(workspace: Path, bundle_dir: Path, obj_uuid: str) -> tuple:
    """Read events.jsonl; emit `event_node`s for every event whose payload
    references `obj_uuid` (as `uuid`, `object_uuid`, or `source_uuid`)."""
    from ..explain import event_node
    from ..truth_model.event_log import read_events

    try:
        events = list(read_events(workspace, bundle_dir))
    except FileNotFoundError:
        return ()
    matches = []
    for ev in events:
        payload = ev.get("payload", {}) or {}
        refs_uuid = (
            payload.get("uuid") == obj_uuid
            or payload.get("object_uuid") == obj_uuid
            or payload.get("source_uuid") == obj_uuid
        )
        if refs_uuid:
            matches.append(event_node(ev))
    matches.sort(key=lambda n: n.details.get("event_id", ""))
    return tuple(matches)


def _walk_related_objects(
    workspace: Path, bundle_dir: Path, obj_uuid: str, sidecar: dict[str, Any],
    *, depth: int, visited: set[str],
) -> tuple:
    """Per Codex Q3+N4 absorption + Codex2 B2 absorption (arc 20260531-10):
    walk ALL relationship types where this Object is source OR target,
    capped at `depth`. Deterministic ordering. `visited` set prevents cycle
    explosion.

    Outgoing direction: relationship records owned by THIS Object's sidecar
    (`sidecar["relationship"][...]`); each endpoint's `object_uuid` is a
    related Object.

    Incoming direction (Codex2 B2 absorption): relationship records live on
    the source sidecar, so for the TARGET side we MUST scan all working
    sidecars and check for endpoints whose `object_uuid == obj_uuid`. The
    matching source Object is the related Object. Without this, explaining
    `REQ-000001` after `P-000001 satisfies REQ-000001` returned no related
    objects — contract violation per the "source OR target" docstring.

    Per Codex2 B2 "fail loudly on invalid Product Truth as `query` does":
    `load_sidecar_validated` exceptions propagate (no silent skip).
    """
    from ..explain import object_node
    from ..truth_model.sidecar import list_working_sidecar_uuids

    if depth <= 0:
        return ()

    # Collect (related_obj_uuid, sort_key) pairs from BOTH directions.
    candidates: list[tuple[str, str, str]] = []  # (sort_rel_type, sort_rel_id_or_uuid, related_uuid)

    # Outgoing: rels on this Object's sidecar
    rels_out = sidecar.get("relationship", []) or []
    for r in rels_out:
        if not isinstance(r, dict):
            continue
        rtype = r.get("type", "")
        rid = r.get("id", "")
        for ep in r.get("endpoints", []) or []:
            if not isinstance(ep, dict):
                continue
            tgt = ep.get("object_uuid")
            if tgt and tgt != obj_uuid:
                candidates.append((rtype, rid, tgt))

    # Incoming: scan ALL working sidecars for relationships pointing at obj_uuid
    for src_uuid in list_working_sidecar_uuids(workspace):
        if src_uuid == obj_uuid:
            continue
        src_sidecar = load_sidecar_validated(workspace, src_uuid, bundle_dir)
        for r in src_sidecar.get("relationship", []) or []:
            if not isinstance(r, dict):
                continue
            rtype = r.get("type", "")
            rid = r.get("id", "")
            for ep in r.get("endpoints", []) or []:
                if not isinstance(ep, dict):
                    continue
                if ep.get("object_uuid") == obj_uuid:
                    candidates.append((rtype, rid, src_uuid))
                    break  # one match per relationship record is enough

    # Deterministic ordering per Codex Q3+N4: (rel.type, rel.id, related_uuid)
    candidates.sort(key=lambda t: (t[0], t[1], t[2]))

    children = []
    for _, _, related_uuid in candidates:
        if related_uuid in visited:
            continue
        related_sidecar = load_sidecar_validated(workspace, related_uuid, bundle_dir)
        related_obj = related_sidecar.get("object", {})
        visited.add(related_uuid)
        sub_children = _walk_object_event_history(workspace, bundle_dir, related_uuid)
        deeper = _walk_related_objects(
            workspace, bundle_dir, related_uuid, related_sidecar,
            depth=depth - 1, visited=visited,
        )
        children.append(object_node(
            number=related_obj.get("number", ""),
            uuid=related_uuid,
            type=related_obj.get("type", ""),
            source="working",
            children=tuple(list(sub_children) + list(deeper)),
        ))
    return tuple(children)


def explain_failure(
    failure: "ValidationOutcome | ExplanationNode | dict[str, Any]",
    *,
    bundle_version: str = "",
    depth: int = 0,
) -> "ExplanationTree":
    """Build an `ExplanationTree` rooted at a failure node.

    Per Codex1 B2 absorption (arc 20260531-10): satisfies ADR/0026's
    `explain(failure, *, depth)` contract directly. Accepts:
      - `ValidationOutcome` whose `tree` field is populated (or `details`
        carries a string message; in that case a single-node tree is built).
      - bare `ExplanationNode` (e.g., from `validation_error_node(...)`).
      - dict shape (e.g., the `validation_errors[i]` from an audit record
        loaded from JSONL).

    `depth=0` (default): the failure tree is returned as-is.
    `depth>0`: future SCN — could traverse from `check_name` back to
    referenced Objects/relationships. Not implemented in this arc.
    """
    from ..explain import ExplanationNode, ExplanationTree, validation_error_node
    if isinstance(failure, ExplanationNode):
        root = failure
    elif isinstance(failure, ValidationOutcome):
        if failure.tree is not None:
            root = failure.tree
        else:
            root = validation_error_node(
                error_type="ValidationOutcome",
                classification="other",
                check_name=failure.check_name,
                message=failure.details or failure.result,
            )
    elif isinstance(failure, dict):
        # Reconstruct ExplanationNode from a dict (e.g., audit record entry).
        root = _node_from_dict(failure)
    else:
        raise TypeError(
            f"explain_failure: failure must be ValidationOutcome | ExplanationNode | "
            f"dict; got {type(failure).__name__}"
        )
    if depth > 0:
        # Future SCN: would traverse `check_name` to referenced Objects.
        # Phase D scope-limits this to depth=0 per Codex1 B2 minimum-viable.
        pass
    return ExplanationTree(root=root, bundle_version=bundle_version)


def _node_from_dict(d: dict[str, Any]) -> "ExplanationNode":
    """Recursive: rebuild `ExplanationNode` from a serialized dict (audit
    record `validation_errors[i]` shape per `node_to_dict()`)."""
    from ..explain import ExplanationNode
    return ExplanationNode(
        kind=d.get("kind", "validation_error"),
        ref=d.get("ref", ""),
        label=d.get("label", ""),
        details=dict(d.get("details", {})),
        children=tuple(_node_from_dict(c) for c in d.get("children", []) or []),
    )


# Re-export ExplanationNode + ExplanationTree from the explain module for
# convenience (so agents can `from aiadra_core.protocol import ExplanationTree`).
from ..explain import ExplanationNode, ExplanationTree  # noqa: E402


# ---------- Module exports ----------


__all__ = [
    # Operations (Phase A + Phase B + Phase C + Phase D)
    "inspect",
    "query",
    "propose",
    "modify",
    "propose_kinds",
    "modify_kinds",
    "validate",
    "simulate",
    "explain",
    "explain_failure",
    "commit",
    "rollback",
    "release",
    # Type shapes
    "ObjectView",
    "ValidationReport",
    "ValidationOutcome",
    "CommitResult",
    "RollbackResult",
    "TransactionDraft",
    "TransactionError",
    "ExplanationNode",
    "ExplanationTree",
    # Exceptions
    "ObjectNotFoundError",
    "ProjectPinError",
    "NetworkUnreachableError",
]
