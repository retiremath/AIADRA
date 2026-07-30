"""Transaction boundary — Draft-then-commit per state-changing CLI command.

Per ADR/0025 §6: every state-changing CLI invocation is a Transaction with
three phases — Draft (in-memory) → Validate (in-memory) → Commit (atomic
writes + git commit). The git commit IS the atomicity boundary.

Per Phase 1 design lockdown (arc 20260531-2 Claude3): Phase 1 implements all
phases; B6 mutation-prohibition runs during Validate; B7 `recover` deferred.
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

from ..truth_model.atomic import atomic_write_bytes
from ..truth_model.event_log import event_log_path
from ..truth_model.manifest import manifest_path, serialize_manifest
from ..truth_model.reservation import reservation_path
from ..truth_model.revision import revision_path
from ..truth_model.sidecar import working_sidecar_path
from ..vault.local_fs import LocalFSVaultAdapter
from ..validation.bundle_registry import BundleHandle, BundleRegistry
from ..validation.fold import FoldInconsistencyError, fold_events_to_state, validate_fold
from ..validation.profile import ProfileViolationError, dump_yaml
from ..validation.schema import SchemaValidationError


class TransactionKind(str, Enum):
    INIT = "init"
    CHANGE_PARAMETER = "change_parameter"
    CREATE_OBJECT = "create_object"
    LINK_RELATIONSHIP = "link_relationship"
    ATTACH_FILE = "attach_file"
    RELEASE = "release"
    ADD_ACCEPTANCE_CRITERION = "add_acceptance_criterion"
    DELETE_OBJECT = "delete_object"  # ADR/0004 SCN arc 20260728-3: first shrinking kind


class TransactionError(ValueError):
    """Generic Transaction failure."""


class DeletionBlockedError(TransactionError):
    """Deletion refused by the referential-integrity scan (arc 20260728-3 B2).

    Carries `blockers`: the deterministic structured blocker list —
    `{relationship_id, relationship_type, source_object{uuid, number},
    candidate_role, state, revision_id?}` sorted by
    (relationship_type, source number, relationship_id, state, revision_id)
    per Codex2 N2. v1 is refusal-only; `relationship_retired` is a NAMED
    future design, not a promised remediation path.
    """

    def __init__(self, message: str, blockers: list[dict[str, Any]]):
        super().__init__(message)
        self.blockers = blockers


class CommitError(RuntimeError):
    """Commit-phase failure (after Validate passed). Working tree may be dirty;
    runtime SHOULD `git restore` from HEAD or surface manual-recovery instructions."""


@dataclass
class ValidationOutcome:
    """One validator's result.

    Per Phase D Codex1 B4 + D5b absorption (arc 20260531-10): extended with
    optional `tree: ExplanationNode | None` field for FAIL outcomes carrying
    structured failure data. Existing `details: str` field unchanged so
    Phase 1-C validators that produce flat string outcomes continue working
    without changes; new validators populate both `details` (rendered text)
    and `tree` (structured node).
    """
    check_name: str
    result: str  # "PASS" | "FAIL"
    details: str = ""
    tree: "ExplanationNode | None" = None  # forward ref — explain module imported lazily


@dataclass
class CommitResult:
    commit_hash: str
    transaction_id: str
    event_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RollbackResult:
    """Returned by `TransactionDraft.rollback()` per Phase A (arc 20260531-7).

    Per ADR/0026 §9 + Codex1 Q4/Q5/N1 absorption: Phase A is discard-only
    (no audit emission); Phase D adds audit log + richer post-rollback
    lifecycle semantics. `reason` is carried already so Phase D wires it
    without an API break. `discarded_change_count` sums all cleared staged
    collections (events + sidecars + reservations + revisions + manifests +
    vault byte chunks)."""
    transaction_id: str
    reason: str | None
    discarded_change_count: int


# -----------------------------------------------------------------------------
# git subprocess helpers (Decision §3 from Claude1 + Codex confirmation)
# -----------------------------------------------------------------------------


def _git(workspace: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", f"safe.directory={workspace.resolve().as_posix()}",
         "-C", str(workspace), *args],
        capture_output=True, text=True, check=check,
    )


def git_repo_dirty_for_aiadra_paths(workspace: Path) -> tuple[bool, str]:
    """Per Codex Q5 + N5 absorption: detect dirty/in-progress git state that
    would conflict with Draft-then-commit. Returns (dirty, reason).
    """
    if not (workspace / ".git").exists():
        # Not a git repo yet (e.g. `aiadra init` runs first); caller handles.
        return False, ""
    # in-progress merge/rebase/cherry-pick: check sentinel files
    git_dir = workspace / ".git"
    for sentinel, name in [
        ("MERGE_HEAD", "merge"),
        ("CHERRY_PICK_HEAD", "cherry-pick"),
        ("REBASE_HEAD", "rebase"),
        ("rebase-merge", "rebase"),
        ("rebase-apply", "rebase"),
    ]:
        if (git_dir / sentinel).exists():
            return True, f"in-progress git {name}"
    # Working tree has staged/unstaged changes in AIADRA-managed paths
    result = _git(workspace, "status", "--porcelain", check=False)
    if result.returncode != 0:
        return True, f"git status failed: {result.stderr.strip()}"
    aiadra_managed_prefixes = (
        "Reservations/", "revisions/", "Releases/", "vault/",
        ".aiadra/", "events.jsonl",
    )
    # Phase D (arc 20260531-10): per ADR/0026 §9 + Codex2 B1 path discipline
    # (arc 20260531-6), the `.aiadra/audit/` subdirectory is carved OUT of
    # the dirty-guard so failed-Transaction audit emission never blocks
    # subsequent canonical Transactions. `.aiadra/audit-config.yaml` at the
    # `.aiadra/` ROOT remains managed configuration and stays guarded.
    aiadra_carve_out_prefixes = (".aiadra/audit/",)
    for line in result.stdout.splitlines():
        # porcelain format: XY <path>
        if len(line) < 3:
            continue
        path = line[3:].strip()
        if path.startswith(aiadra_carve_out_prefixes):
            continue  # .aiadra/audit/* carved out per Phase D
        if path.startswith(tuple(aiadra_managed_prefixes)) or path == "events.jsonl":
            return True, f"AIADRA-managed path dirty: {path}"
    return False, ""


# -----------------------------------------------------------------------------
# TransactionDraft
# -----------------------------------------------------------------------------


@dataclass
class TransactionDraft:
    """In-memory accumulation of Transaction changes per ADR/0025 §6.

    Per ADR/0028 D16 + arc 20260601-1: `kind` is a plain `str` (was
    `TransactionKind` enum). Built-in callers passing `TransactionKind` enum
    members continue to work via `__post_init__` normalization — the enum
    member's `.value` (already a str-Enum) gets extracted so the invariant
    `isinstance(self.kind, str) and not isinstance(self.kind, TransactionKind)`
    holds after init. Native Engine operations pass the full namespaced kind
    string directly (e.g., `kind="mechanical.adjust_parameter"`).
    """

    workspace: Path
    bundle: BundleHandle
    kind: str  # ADR/0028 D16: was TransactionKind; now str (enum members normalized in __post_init__)
    transaction_id: str = ""

    # Staged operations (in-memory):
    sidecar_writes: dict[str, dict[str, Any]] = field(default_factory=dict)  # uuid → sidecar
    sidecar_deletes: set[str] = field(default_factory=set)
    events: list[dict[str, Any]] = field(default_factory=list)
    reservation_writes: dict[str, dict[str, Any]] = field(default_factory=dict)  # prefix → reservation
    revision_writes: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)  # (uuid, rev_id) → content
    manifest_writes: dict[str, dict[str, Any]] = field(default_factory=dict)  # label → manifest
    vault_writes: list[bytes] = field(default_factory=list)
    project_pin_write: str | None = None  # B10: pin text staged via Transaction
    commit_message_lines: list[str] = field(default_factory=list)

    # Pre-validate hooks (for B6 mutation-prohibition + N3 reservation_integrity)
    pre_validate_hooks: list[Callable[["TransactionDraft"], None]] = field(default_factory=list)
    # Post-validate hooks (final-stage scans, etc.)
    post_validate_hooks: list[Callable[["TransactionDraft"], None]] = field(default_factory=list)

    # Phase C (arc 20260531-9) Codex1 B3 absorption: terminal-state lifecycle
    # guard. "open" → may accept modify / commit / rollback; "committed" or
    # "rolled_back" → terminal; further modify/commit/rollback all raise.
    # Private; protocol.modify + commit() + rollback() inspect this; agents
    # should treat the draft as opaque post-terminal.
    _lifecycle_state: str = "open"  # "open" | "committed" | "rolled_back"

    # Phase D (arc 20260531-10) Codex1 B3 absorption: single-record audit
    # semantics. Each TransactionDraft may emit at most one failed-Transaction
    # audit record. Set by `_emit_audit_once()`; subsequent emission attempts
    # no-op silently. Triggers — `audit_failure()` (operations-layer catch
    # path), `rollback()` (only if not already emitted AND staged content
    # exists), `commit()` on CommitError (write-time crash).
    _audit_emitted: bool = False

    def __post_init__(self) -> None:
        """ADR/0028 D16 normalization: if `kind` was passed as a
        `TransactionKind` enum member (built-in callers from arc 9 onward),
        extract its str value. Native Engine callers pass plain str directly
        (no normalization needed). After this runs, `self.kind` is always a
        plain `str` (not an enum instance), so the audit + commit-message
        serialization sites can use `self.kind` directly without `.value`.
        """
        if isinstance(self.kind, TransactionKind):
            # Use object.__setattr__ to bypass dataclass-generated __setattr__
            # if frozen (this dataclass is NOT frozen but the pattern is safe).
            self.kind = self.kind.value

    def _assert_open(self, op: str) -> None:
        """Raise TransactionError if the draft is in a terminal state.
        Called by commit / rollback / modify-call-paths per Codex1 B3."""
        if self._lifecycle_state != "open":
            raise TransactionError(
                f"cannot {op}: draft is {self._lifecycle_state} (terminal state); "
                f"create a new draft via protocol.propose()"
            )

    # -------------------------------------------------------------------------
    # Phase D (arc 20260531-10) Codex1 B3 absorption: audit emission helpers.
    # -------------------------------------------------------------------------

    def _emit_audit_once(
        self,
        *,
        reason_text: str,
        reason_classification: str,
        agent_ref: str | None,
        validation_error_trees: list,
    ) -> None:
        """Write a single failed-Transaction audit record at most once per
        draft. Per Codex1 B3 absorption: short-circuits silently if
        `_audit_emitted` is already True; sets the flag regardless of
        write outcome (success or stderr-warned failure) so subsequent
        attempts no-op.

        Per Codex1 Q5: NEVER raises. Audit is diagnostic; failure to write
        MUST NOT mask validation/rollback/commit errors.
        """
        if self._audit_emitted:
            return
        try:
            from ..audit import AuditRecord, write_audit_record, _now_iso_utc
            from ..explain import node_to_dict
            attempted_at = _now_iso_utc()
            record = AuditRecord(
                transaction_id=self.transaction_id,
                attempted_at=attempted_at,
                kind=self.kind,  # ADR/0028 D16: kind is plain str post __post_init__ normalization
                proposed_events=list(self.events),
                validation_errors=[node_to_dict(t) for t in validation_error_trees if t is not None],
                reason_classification=reason_classification,
                reason_text=reason_text,
                agent_ref=agent_ref,
            )
            write_audit_record(self.workspace, record)
        except Exception as e:
            # Audit MUST NEVER mask original error per Codex1 Q5.
            import sys as _sys
            print(
                f"aiadra audit: emission failed for {self.transaction_id}: "
                f"{type(e).__name__}: {e}",
                file=_sys.stderr,
            )
        finally:
            # Always mark emitted (even on failure) so subsequent attempts
            # no-op rather than re-attempting and re-failing.
            self._audit_emitted = True

    def audit_failure(
        self,
        reason: str,
        exception: BaseException,
        *,
        agent_ref: str | None = None,
        reason_classification: str | None = None,
    ) -> None:
        """Emit a failed-Transaction audit record for a draft that raised
        from `validate()` (or any other operation-layer failure). Called
        by callers that catch the exception themselves; ensures the
        diagnostic record is on disk before the draft is discarded.

        Per Codex1 N1 absorption: `agent_ref` is explicit kwarg (NOT parsed
        from `reason`); CLI omits, Python agents pass.

        Per Codex1 Q6 absorption: if `reason_classification` is omitted, it
        is inferred from `exception`'s class via `classify_exception()`.

        No-op if a prior audit record has already been emitted for this draft.
        """
        from ..explain import classify_exception, validation_error_node
        cls = reason_classification or classify_exception(exception)
        trees = [validation_error_node(
            error_type=type(exception).__name__,
            classification=cls,
            check_name="audit_failure",
            message=str(exception),
        )]
        self._emit_audit_once(
            reason_text=reason,
            reason_classification=cls,
            agent_ref=agent_ref,
            validation_error_trees=trees,
        )

    def stage_sidecar(self, obj_uuid: str | UUID, sidecar: dict[str, Any]) -> None:
        key = str(obj_uuid)
        if key in self.sidecar_deletes:
            raise TransactionError(
                f"Cannot stage a sidecar write for {key}: its deletion is already "
                f"staged in this Transaction (arc 20260728-3 B3 mutual exclusion)."
            )
        self.sidecar_writes[key] = sidecar

    def stage_sidecar_delete(self, obj_uuid: str | UUID) -> None:
        """Stage the REMOVAL of a working sidecar (arc 20260728-3 B3).

        Commit deletes the file and Git-stages the removal so the deletion is
        part of the same atomic commit as the tombstone + event. Mutually
        exclusive with a staged write for the same uuid, in both directions.
        """
        key = str(obj_uuid)
        if key in self.sidecar_writes:
            raise TransactionError(
                f"Cannot stage sidecar deletion for {key}: a sidecar write is "
                f"already staged in this Transaction (arc 20260728-3 B3 mutual "
                f"exclusion)."
            )
        self.sidecar_deletes.add(key)

    def stage_event(self, event: dict[str, Any]) -> None:
        self.events.append(event)

    def stage_reservation(self, prefix: str, reservation: dict[str, Any]) -> None:
        self.reservation_writes[prefix] = reservation

    def stage_revision(self, obj_uuid: str | UUID, rev_id: str | UUID, content: dict[str, Any]) -> None:
        self.revision_writes[(str(obj_uuid), str(rev_id))] = content

    def stage_manifest(self, release_label: str, manifest: dict[str, Any]) -> None:
        self.manifest_writes[release_label] = manifest

    def stage_vault_bytes(self, data: bytes) -> tuple[str, str]:
        """Returns (content_hash, vault_path). Idempotent on bytes equality."""
        import hashlib
        h = "sha256:" + hashlib.sha256(data).hexdigest()
        vp = f"vault/{h[len('sha256:'):]}"
        self.vault_writes.append(data)
        return h, vp

    def stage_project_pin(self, pin_text: str) -> None:
        """B10 absorption: project pin is staged via Transaction, not written
        as a side-effect outside the draft."""
        self.project_pin_write = pin_text

    # -------------------------------------------------------------------------

    def validate(self) -> list[ValidationOutcome]:
        """Run all in-memory checks against the proposed state. Returns the
        list of outcomes; raises on hard-fail before any writes.

        Per B9 absorption arc 20260531-2 round-5: this method is now the F3
        Draft-then-commit boundary. In addition to per-artifact schema checks,
        it folds proposed events + sidecars against current on-disk state and
        rejects any sidecar/event invariant violation BEFORE commit.

        Phase D Codex1 B1 absorption (arc 20260531-10): now delegates to
        `_validate_internal(collect_failures=False)`. The commit path keeps
        raise-on-first-fail semantics; the new `simulate()` method calls
        `_validate_internal(collect_failures=True)` to collect structured
        FAIL outcomes without raising — agents reason via the report, commit
        gates via the exception.
        """
        return self._validate_internal(collect_failures=False)

    def simulate(self) -> list[ValidationOutcome]:
        """Run all validation checks in collect-mode — never raises on a known
        validation exception; converts each to a FAIL `ValidationOutcome` with
        `tree` populated. Phase D Codex1 B1 absorption (arc 20260531-10).

        Writes nothing. Emits no audit. Asserts open per Codex1 B3 lifecycle
        pattern (Phase C) — running simulate on a closed draft makes no sense.

        Returns the full outcome list (PASS + FAIL mixed) for the caller to
        wrap in `ValidationReport`. The protocol-level free function
        `protocol.simulate(draft)` is the agent-facing surface.
        """
        self._assert_open("simulate")
        return self._validate_internal(collect_failures=True)

    def _validate_internal(self, *, collect_failures: bool) -> list[ValidationOutcome]:
        """Shared validation runner. Phase D Codex1 B1 absorption.

        When `collect_failures=False` (commit path): preserves Phase 1-C
        raise-on-first-fail semantics — known validation exceptions propagate.

        When `collect_failures=True` (simulate path): catches each section's
        known exceptions, appends a structured FAIL `ValidationOutcome` with
        `tree=validation_error_node(...)`, continues to next section. Per
        Codex1 B1 absorption — agents need structured failure data without
        side effects.

        Phase D Codex2 B3 absorption (arc 20260531-10): in collect mode,
        dependent proposed-state checks (`_validate_proposed_fold` +
        `_validate_proposed_b6_scan`) are SKIPPED when earlier schema checks
        failed (a malformed event missing `event_type` would otherwise raise
        `KeyError` from fold). A "SKIPPED" outcome is recorded so the report
        explains the cascade. Additionally, the inner `_try` catches a
        broader exception set in collect mode (any Exception → "other"
        classification) as a safety net for non-validation bugs in dependent
        checks; this keeps simulate's contract — never raises on a malformed
        draft.
        """
        # Local import — keeps explain dependency lazy + breaks circular risk.
        from ..explain import classify_exception, validation_error_node
        from ..validation.binding import RevisionBindingError
        from ..validation.reservation_integrity import ReservationIntegrityError
        from ..validation.release import ReleaseConsistencyError

        # Per Codex1 B1: commit path catches only known validation exceptions.
        # Per Codex2 B3 (arc 20260531-10): simulate path also catches a
        # broader Exception in dependent-check sections as a safety net.
        _KNOWN_EXC = (
            SchemaValidationError, ProfileViolationError, FoldInconsistencyError,
            RevisionBindingError, ReservationIntegrityError, ReleaseConsistencyError,
        )
        outcomes: list[ValidationOutcome] = []

        def _try(check_name: str, body, *, broad_catch: bool = False):
            """Run body(); on exception:
              - commit mode: re-raise (known exceptions only — broad_catch ignored).
              - simulate mode: append FAIL outcome with tree, continue.
                If broad_catch=True, also catches any Exception (Codex2 B3
                safety net for dependent-check sections after schema fail).
            """
            try:
                body()
            except _KNOWN_EXC as e:
                if not collect_failures:
                    raise
                outcomes.append(ValidationOutcome(
                    check_name=check_name, result="FAIL",
                    details=str(e),
                    tree=validation_error_node(
                        error_type=type(e).__name__,
                        classification=classify_exception(e),
                        check_name=check_name,
                        message=str(e),
                    ),
                ))
                return False
            except Exception as e:
                if not (collect_failures and broad_catch):
                    raise
                outcomes.append(ValidationOutcome(
                    check_name=check_name, result="FAIL",
                    details=f"{type(e).__name__}: {e}",
                    tree=validation_error_node(
                        error_type=type(e).__name__,
                        classification="other",
                        check_name=check_name,
                        message=str(e),
                    ),
                ))
                return False
            return True

        # Pre-validate hooks (B6 mutation-prohibition, etc.)
        for i, hook in enumerate(self.pre_validate_hooks):
            _try(f"pre_validate_hook[{i}]", lambda h=hook: h(self))

        # Track schema-check failure count separately so dependent checks
        # (fold + b6 scan) can skip when schema is broken (Codex2 B3).
        schema_failures_before_dependent = 0

        def _count_schema_failures() -> int:
            return sum(
                1 for o in outcomes
                if o.result == "FAIL" and o.check_name.startswith("schema(")
            )

        # 1. Schema-validate each staged sidecar
        for uuid, sc in self.sidecar_writes.items():
            check_name = f"schema(sidecar:{uuid})"

            def _body(uuid=uuid, sc=sc):
                obj_type = sc.get("object", {}).get("type")
                if not obj_type:
                    raise SchemaValidationError(f"Staged sidecar for {uuid} missing object.type")
                self.bundle.validate(sc, "sidecar", obj_type)

            if _try(check_name, _body):
                outcomes.append(ValidationOutcome(check_name, "PASS"))

        # 2. Schema-validate each staged event
        for ev in self.events:
            check_name = f"schema(event:{ev.get('event_id', '?')})"

            def _body(ev=ev):
                et = ev.get("event_type")
                if not et:
                    raise SchemaValidationError(f"Staged event missing event_type: {ev!r}")
                self.bundle.validate(ev, "event", et)

            if _try(check_name, _body):
                outcomes.append(ValidationOutcome(check_name, "PASS"))

        # 3. Schema-validate each staged reservation
        for prefix, res in self.reservation_writes.items():
            check_name = f"schema(reservation:{prefix})"
            if _try(check_name, lambda prefix=prefix, res=res: self.bundle.validate(res, "reservation", prefix)):
                outcomes.append(ValidationOutcome(check_name, "PASS"))

        # 4. Schema-validate each staged revision
        for (uuid, rev_id), content in self.revision_writes.items():
            check_name = f"schema(revision:{rev_id})"

            def _body(content=content):
                obj_type = content.get("object", {}).get("type")
                self.bundle.validate(content, "revision", obj_type)

            if _try(check_name, _body):
                outcomes.append(ValidationOutcome(check_name, "PASS"))

        # 5. Schema-validate each staged manifest
        for label, m in self.manifest_writes.items():
            check_name = f"schema(manifest:{label})"
            if _try(check_name, lambda m=m: self.bundle.validate(m, "manifest", m.get("manifest_type", "release"))):
                outcomes.append(ValidationOutcome(check_name, "PASS"))

        schema_failures_before_dependent = _count_schema_failures()

        # 6. B9: Proposed-state sidecar/event fold check. Skip for INIT.
        # Phase D Codex2 B3 absorption: in collect mode, skip if any schema
        # check failed (fold would crash on the malformed artifact); record
        # a SKIPPED outcome so the report explains the cascade.
        if self.kind != TransactionKind.INIT:
            if collect_failures and schema_failures_before_dependent > 0:
                outcomes.append(ValidationOutcome(
                    check_name="proposed_fold_invariant",
                    result="FAIL",
                    details=f"SKIPPED: {schema_failures_before_dependent} prior schema check(s) failed; "
                            f"proposed-state fold cannot be evaluated on malformed staged artifacts.",
                    tree=validation_error_node(
                        error_type="DependencySkipped",
                        classification="other",
                        check_name="proposed_fold_invariant",
                        message=f"skipped due to {schema_failures_before_dependent} prior schema failure(s)",
                    ),
                ))
            else:
                _try(
                    "proposed_fold_invariant",
                    lambda: self._validate_proposed_fold(outcomes),
                    broad_catch=True,  # Codex2 B3 safety net
                )

        # 7. Codex2 B1 absorption (arc 20260531-9): proposed-state B6 scan.
        if self.kind != TransactionKind.INIT:
            if collect_failures and schema_failures_before_dependent > 0:
                outcomes.append(ValidationOutcome(
                    check_name="proposed_binding_mutation_scan",
                    result="FAIL",
                    details=f"SKIPPED: {schema_failures_before_dependent} prior schema check(s) failed; "
                            f"proposed-state B6 scan cannot be evaluated on malformed staged artifacts.",
                    tree=validation_error_node(
                        error_type="DependencySkipped",
                        classification="other",
                        check_name="proposed_binding_mutation_scan",
                        message=f"skipped due to {schema_failures_before_dependent} prior schema failure(s)",
                    ),
                ))
            else:
                _try(
                    "proposed_binding_mutation_scan",
                    lambda: self._validate_proposed_b6_scan(outcomes),
                    broad_catch=True,  # Codex2 B3 safety net
                )

        # Post-validate hooks (final-stage scans, etc.)
        for i, hook in enumerate(self.post_validate_hooks):
            _try(f"post_validate_hook[{i}]", lambda h=hook: h(self), broad_catch=True)

        return outcomes

    def _validate_proposed_fold(self, outcomes: list[ValidationOutcome]) -> None:
        """B9: simulate the post-Transaction fold state and compare against
        the post-Transaction proposed sidecars.

        Algorithm:
        - Read current on-disk events; fold to current state.
        - Apply each staged event to extend the state.
        - For each staged sidecar, compare against the folded state.
        Raises FoldInconsistencyError on mismatch.
        """
        if not self.events and not self.sidecar_writes and not self.sidecar_deletes:
            return  # nothing to fold

        from ..validation.fold import (
            _apply_attachment_delta,
            _apply_part_changed,
            fold_events_to_state,
            FoldInconsistencyError as _FoldErr,
        )

        # Build current state from on-disk events.
        try:
            current_state = fold_events_to_state(self.workspace, self.bundle.bundle_dir)
        except FileNotFoundError:
            current_state = {}

        # Apply staged events in order.
        state = json.loads(json.dumps(current_state))
        for event in self.events:
            et = event["event_type"]
            if et.endswith("_created") and et != "relationship_created" and et != "release_staged":
                uuid = event["payload"]["uuid"]
                state[uuid] = json.loads(json.dumps(event["payload"]["initial_sidecar"]))
            elif et == "relationship_created":
                src = event["payload"]["source_uuid"]
                rec = event["payload"]["relationship_record"]
                state.setdefault(src, {}).setdefault("relationship", []).append(
                    json.loads(json.dumps(rec))
                )
            elif et == "parameter_changed":
                uuid = event["payload"]["object_uuid"]
                pid = event["payload"]["parameter_id"]
                nv = event["payload"]["new_value"]
                # B1 absorption Phase 2 round-2 (arc 20260531-3): proposed-state
                # fold path MUST honor new_fact_provenance identically to the
                # read-side fold path in validation/fold.py. Both must agree
                # post-Transaction or the F3 boundary catches false drift.
                new_fp = event["payload"].get("new_fact_provenance")
                for p in state.get(uuid, {}).get("parameter", []):
                    if p.get("id") == pid:
                        p["value"] = nv
                        if new_fp is not None:
                            p["fact_provenance"] = json.loads(json.dumps(new_fp))
                        break
            elif et in ("drawing_changed", "test_procedure_changed",
                        "test_execution_changed", "evidence_artifact_changed"):
                _apply_attachment_delta(state, et, event["payload"])
            elif et == "requirement_changed":
                # B1 absorption Phase 4 (arc 20260531-5): proposed-state fold
                # MUST honor `acceptance_criterion_delta.added` identically to
                # the read-side fold in validation/fold.py. Added-only per
                # Codex1 B1; duplicate criterion id is FoldInconsistencyError.
                uuid = event["payload"]["object_uuid"]
                added = event["payload"]["acceptance_criterion_delta"]["added"]
                existing = state.setdefault(uuid, {}).setdefault("acceptance_criterion", [])
                existing_ids = {c["id"] for c in existing if isinstance(c, dict)}
                for crit in added:
                    if crit["id"] in existing_ids:
                        raise _FoldErr(
                            f"requirement_changed.added: criterion id {crit['id']!r} "
                            f"already exists on Requirement {uuid}"
                        )
                    existing.append(json.loads(json.dumps(crit)))
                    existing_ids.add(crit["id"])
            elif et == "part_changed":
                # ADR/0029 Part authoring SCN (arc 20260531-13): proposed-state
                # fold MUST honor part_changed identically to the read-side
                # fold in validation/fold.py. Mirrors the dual-fold discipline
                # established by Phase 2 F1 / Phase 4 F2 SCNs.
                _apply_part_changed(state, event["payload"], event["actor"])
            elif et == "object_deleted":
                # arc 20260728-3 B3: proposed-state fold MUST remove the uuid
                # from working state, mirroring the read-side fold. Deleting an
                # unknown uuid is fold inconsistency (the operation layer
                # guarantees existence; disagreement here means drift).
                uuid = event["payload"]["uuid"]
                if uuid not in state:
                    raise _FoldErr(
                        f"object_deleted: uuid {uuid} not present in folded "
                        f"working state; nothing to delete"
                    )
                state.pop(uuid)
            # release_staged + <type>_released are no-op on working state.

        # Compare each staged sidecar against the folded state.
        for uuid, proposed_sidecar in self.sidecar_writes.items():
            expected = state.get(uuid)
            if expected is None:
                raise FoldInconsistencyError(
                    f"Staged sidecar for {uuid} has no corresponding event-derived state "
                    f"(no <type>_created event found among staged + on-disk events)"
                )
            if json.dumps(proposed_sidecar, sort_keys=True) != json.dumps(expected, sort_keys=True):
                raise FoldInconsistencyError(
                    f"Proposed sidecar for {uuid} disagrees with proposed event fold: "
                    f"staged sidecar and staged events would diverge post-commit"
                )

        # arc 20260728-3 B3: each staged sidecar DELETION must agree with the
        # event fold — the uuid must be ABSENT from the folded state (the
        # object_deleted event removed it) or the deletion and the events
        # would diverge post-commit.
        for uuid in self.sidecar_deletes:
            if uuid in state:
                raise FoldInconsistencyError(
                    f"Staged sidecar deletion for {uuid} disagrees with proposed "
                    f"event fold: no staged object_deleted event removes it"
                )
        outcomes.append(ValidationOutcome("proposed_fold_invariant", "PASS"))

    def _validate_proposed_b6_scan(self, outcomes: list[ValidationOutcome]) -> None:
        """Codex2 B1 absorption arc 20260531-9: run the B6 mutation-after-binding
        scan over the combined `committed_events + draft.events` stream.

        Without this, a composable `modify()` draft could stage a Fixed
        execution binding then a mutation of the bound target in the same
        Transaction, pass `draft.validate()` (because the per-op
        `_mutation_prohibition_hook` only walked disk state), and commit a
        workspace that `protocol.validate(workspace)` immediately rejects.

        We delegate to `find_mutation_after_binding_violations_for_events` —
        the same rule the post-commit read-side scan uses — but feed it the
        proposed event stream so the Draft-then-commit boundary holds.
        """
        if not self.events:
            return  # nothing staged; nothing new to check (disk-only path runs in protocol.validate)
        from ..truth_model.event_log import read_events
        from ..validation.binding import (
            find_mutation_after_binding_violations_for_events,
            RevisionBindingError,
        )
        try:
            committed = list(read_events(self.workspace, self.bundle.bundle_dir))
        except FileNotFoundError:
            committed = []
        combined = committed + list(self.events)
        violations = find_mutation_after_binding_violations_for_events(combined)
        if violations:
            raise RevisionBindingError(
                "B6 proposed-state mutation-after-binding scan caught violation(s) "
                "(Codex2 B1 absorption arc 20260531-9):\n  - "
                + "\n  - ".join(violations)
            )
        outcomes.append(ValidationOutcome(
            "proposed_binding_mutation_scan", "PASS",
            f"no mutation-after-binding violations in committed+staged event stream "
            f"(committed={len(committed)}, staged={len(self.events)})",
        ))

    # -------------------------------------------------------------------------

    def rollback(
        self,
        *,
        reason: str | None = None,
        reason_classification: str = "other",
        agent_ref: str | None = None,
    ) -> "RollbackResult":
        """Discard the draft.

        Clears ALL staged mutable collections per Codex1 Q5 absorption (Phase A).

        Phase C (arc 20260531-9) Codex1 B3 absorption: terminal-state guard.
        Raises if the draft is already in a terminal state (committed or
        rolled_back); marks lifecycle state as "rolled_back" on success.

        Phase D (arc 20260531-10) Codex1 B3 absorption: emits a failed-
        Transaction audit record BEFORE clearing if `_audit_emitted == False`
        AND there is staged content to record. Single-record semantics —
        `_emit_audit_once()` no-ops if `audit_failure()` already emitted.
        Audit emission failure NEVER masks rollback semantics.

        Phase D Codex1 N1 absorption: `agent_ref` is explicit kwarg (NOT
        parsed from `reason`); CLI omits, Python agents pass.

        Returns a `RollbackResult` carrying the original `transaction_id`,
        optional `reason`, and `discarded_change_count` = sum of all the
        non-empty staged collections at the time of rollback.
        """
        self._assert_open("rollback")
        # Phase D Codex2 N1 absorption (arc 20260531-10): VALIDATE
        # reason_classification up-front while the draft is still open.
        # Silent coercion to "other" makes diagnostic data less trustworthy;
        # operators / agents should see typos immediately rather than later.
        from ..explain import REASON_CLASSIFICATIONS
        if reason_classification not in REASON_CLASSIFICATIONS:
            raise ValueError(
                f"rollback reason_classification must be one of "
                f"{sorted(REASON_CLASSIFICATIONS)}; got {reason_classification!r} "
                f"(Codex2 N1 absorption arc 20260531-10)."
            )
        discarded = (
            len(self.events)
            + len(self.sidecar_writes)
            + len(self.sidecar_deletes)
            + len(self.reservation_writes)
            + len(self.revision_writes)
            + len(self.manifest_writes)
            + len(self.vault_writes)
        )
        # Phase D B3: audit emit BEFORE clearing (needs staged data). Skip if
        # already emitted via audit_failure(), or if nothing was staged
        # (rollback-on-empty-draft is not a "failed Transaction"). Per
        # Codex2 N3 absorption (arc 20260531-10): validation_errors=[] is
        # the explicit wire shape for rolled-back-without-validation — null
        # would also work but empty list is simpler for consumers.
        if not self._audit_emitted and discarded > 0:
            self._emit_audit_once(
                reason_text=reason or "rollback",
                reason_classification=reason_classification,
                agent_ref=agent_ref,
                validation_error_trees=[],
            )
        self.sidecar_writes.clear()
        self.sidecar_deletes.clear()
        self.events.clear()
        self.reservation_writes.clear()
        self.revision_writes.clear()
        self.manifest_writes.clear()
        self.vault_writes.clear()
        self.project_pin_write = None
        self.commit_message_lines.clear()
        self.pre_validate_hooks.clear()
        self.post_validate_hooks.clear()
        self._lifecycle_state = "rolled_back"
        return RollbackResult(
            transaction_id=self.transaction_id,
            reason=reason,
            discarded_change_count=discarded,
        )

    # -------------------------------------------------------------------------

    def _assert_event_log_unmoved(self) -> None:
        """The log-advance guard (W-3, arc 20260730-1).

        Event and transaction ids are allocated at STAGING time against the
        event log as it then stood. If the log has advanced since — a
        concurrent draft on the same workspace, a double-dispatched terminal —
        appending this draft's events would write DUPLICATE event ids, and
        every later fold replay refuses them: the workspace stops accepting
        commits entirely (observed: tx_0050 committed twice, evt_0051
        duplicated, every subsequent transaction refused). Refuse BEFORE the
        first byte is written: the draft stays open, disk state untouched,
        and the caller re-stages against current state.

        The scan is raw (no schema pass): a collision check needs only the
        ids, and a line that cannot parse is a corrupt log — failing loudly
        on it here is correct, not incidental.
        """
        if not self.events:
            return
        staged_ns = [
            int(ev["event_id"][len("evt_"):])
            for ev in self.events
            if str(ev.get("event_id", "")).startswith("evt_")
        ]
        if not staged_ns:
            return
        first_staged = min(staged_ns)
        max_committed = 0
        elog = event_log_path(self.workspace)
        if elog.exists():
            with elog.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    eid = str(json.loads(line).get("event_id", ""))
                    if eid.startswith("evt_"):
                        try:
                            n = int(eid[len("evt_"):])
                        except ValueError:
                            continue
                        if n > max_committed:
                            max_committed = n
        if first_staged <= max_committed:
            err = CommitError(
                f"event log advanced under this draft: it staged evt_{first_staged:04d} "
                f"but the log already holds evt_{max_committed:04d} — another commit landed "
                f"after this draft staged its operations (concurrent draft or double "
                f"dispatch). Nothing was written; roll back and re-stage against "
                f"current state."
            )
            self._emit_audit_once(
                reason_text=f"commit refused: {err}",
                reason_classification="other",
                agent_ref=None,
                validation_error_trees=[],
            )
            raise err

    def commit(self) -> CommitResult:
        """Write all staged changes + git add + git commit. Atomic boundary.

        Phase C (arc 20260531-9) Codex1 B3 absorption: terminal-state guard.
        Raises if the draft is already in a terminal state (committed or
        rolled_back); marks lifecycle state as "committed" on success.

        W-3 (arc 20260730-1): the log-advance guard runs FIRST — before the
        sidecar writes, not just before the event append — because a stale
        draft's sidecar writes would clobber the newer commit's state even
        if the event append were the only thing refused.
        """
        self._assert_open("commit")
        self._assert_event_log_unmoved()
        touched_paths: list[Path] = []
        vault = LocalFSVaultAdapter(self.workspace)

        # 0. Project pin write (B10 absorption: pin staged via Transaction)
        if self.project_pin_write is not None:
            pin_dir = self.workspace / ".aiadra"
            pin_dir.mkdir(parents=True, exist_ok=True)
            pin_path = pin_dir / "schemas.yaml"
            atomic_write_bytes(pin_path, self.project_pin_write.encode("utf-8"))
            touched_paths.append(pin_path)

        # 1. Vault writes (content-addressed; idempotent)
        for data in self.vault_writes:
            ch, vp = vault.store(data)
            touched_paths.append(self.workspace / vp.replace("/", "/") / "bytes")

        # 2. Sidecar writes
        for uuid, sc in self.sidecar_writes.items():
            text = dump_yaml(sc)
            p = working_sidecar_path(self.workspace, uuid)
            atomic_write_bytes(p, text.encode("utf-8"))
            touched_paths.append(p)

        # 2b. Sidecar deletions (arc 20260728-3 B3): remove the file AND
        # remember the path so the Git step stages the REMOVAL. `git add` on
        # a tracked-but-missing path stages its deletion; the `p.exists()`
        # filter in step 7 would silently drop it, so removed paths are
        # collected separately and added unconditionally.
        removed_paths: list[Path] = []
        for uuid in sorted(self.sidecar_deletes):
            p = working_sidecar_path(self.workspace, uuid)
            if p.exists():
                p.unlink()
            removed_paths.append(p)

        # 3. Reservation writes
        for prefix, res in self.reservation_writes.items():
            text = dump_yaml(res)
            p = reservation_path(self.workspace, prefix)
            atomic_write_bytes(p, text.encode("utf-8"))
            touched_paths.append(p)

        # 4. Revision writes
        for (uuid, rev_id), content in self.revision_writes.items():
            text = dump_yaml(content)
            p = revision_path(self.workspace, uuid, rev_id)
            atomic_write_bytes(p, text.encode("utf-8"))
            touched_paths.append(p)

        # 5. Event log appends (after all sidecars/reservations/revisions written)
        if self.events:
            elog = event_log_path(self.workspace)
            elog.parent.mkdir(parents=True, exist_ok=True)
            with elog.open("a", encoding="utf-8") as f:
                for ev in self.events:
                    line = json.dumps(ev, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                    f.write(line + "\n")
            touched_paths.append(elog)

        # 6. Manifest writes
        for label, m in self.manifest_writes.items():
            payload = serialize_manifest(m)
            p = manifest_path(self.workspace, label)
            atomic_write_bytes(p, payload)
            touched_paths.append(p)

        # 7. git add + commit (only if .git exists)
        commit_hash = ""
        if (self.workspace / ".git").exists():
            # git add each touched path relative to workspace
            rel_paths = [
                str(p.relative_to(self.workspace)).replace("\\", "/")
                for p in touched_paths
                if p.exists()
            ]
            # arc 20260728-3 B3: staged sidecar removals join the same commit.
            rel_paths.extend(
                str(p.relative_to(self.workspace)).replace("\\", "/")
                for p in removed_paths
            )
            if rel_paths:
                _git(self.workspace, "add", "--", *rel_paths)
                msg = "\n".join(self.commit_message_lines) or f"aiadra: {self.kind} {self.transaction_id}"  # ADR/0028 D16
                try:
                    _git(self.workspace, "commit", "-m", msg)
                    commit_hash = _git(self.workspace, "rev-parse", "HEAD").stdout.strip()
                except subprocess.CalledProcessError as e:
                    # Phase D (arc 20260531-10) Codex1 B3 absorption: emit
                    # audit record for commit-time failure (rare; git crash
                    # mid-commit). Single-record semantics via _emit_audit_once.
                    # Audit emission failure MUST NOT mask CommitError.
                    err = CommitError(
                        f"git commit failed: {e.stderr.strip() or e.stdout.strip()}"
                    )
                    self._emit_audit_once(
                        reason_text=f"commit failed: {err}",
                        reason_classification="other",
                        agent_ref=None,
                        validation_error_trees=[],
                    )
                    raise err from e

        # Phase C (arc 20260531-9) Codex1 B3 absorption: mark terminal AFTER
        # all writes succeed. A second commit() now raises via _assert_open.
        self._lifecycle_state = "committed"
        return CommitResult(
            commit_hash=commit_hash,
            transaction_id=self.transaction_id,
            event_ids=[ev["event_id"] for ev in self.events if "event_id" in ev],
        )
