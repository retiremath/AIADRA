"""AIADRA Ring 2 AI Action Protocol — canonical Python entry points.

Per [ADR/0026](../../../Docs/ADR/0026-ai-action-protocol-scope.md) §"Sequencing"
**Phase A** + **Phase B**. Formalizes the existing aiadra-core surface as the
agent-facing Ring 2 contract layer + adds the first NEW Ring 2 operation
(`query` over cumulative release graph + working set) + makes
locality/staleness kwargs operational.

Tier-1 in-process Python entry points; CLI is the Tier-2 thin wrapper
(`aiadra_core.cli`); Tier-3 RPC adapters (MCP, OpenAI tools, LSP-style,
custom JSON-RPC) live in SEPARATE ecosystem packages per Manifesto P11 and
ADR/0026 Decision §6.

**Phase A + B surface (6 of 9 ADR/0026 §2 contracts):**

- `inspect(workspace, object_ref, *, locality, staleness) -> ObjectView`
- `query(workspace, *, kind, filter, locality, staleness) -> list[ObjectView]`   ← NEW Phase B
- `validate(workspace) -> ValidationReport`
- `commit(draft) -> CommitResult`
- `rollback(draft, *, reason=None) -> RollbackResult`
- `release(workspace, bundle, object_numbers, ..., release_label=None) -> TransactionDraft`

Future-phase contracts (`propose` / `modify` / `simulate` Phase C; `explain`
Phase D) are intentionally NOT exported — their absence is clearer
documentation than `NotImplementedError` stubs would be (Codex1 Q7
absorption arc 20260531-7).

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
    ValidationOutcome,
)
from ..transaction.operations import release as _release_op
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
    # Operations (Phase A + Phase B)
    "inspect",
    "query",
    "validate",
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
    # Exceptions
    "ObjectNotFoundError",
    "ProjectPinError",
    "NetworkUnreachableError",
]
