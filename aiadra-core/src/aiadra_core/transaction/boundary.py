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


class TransactionError(ValueError):
    """Generic Transaction failure."""


class CommitError(RuntimeError):
    """Commit-phase failure (after Validate passed). Working tree may be dirty;
    runtime SHOULD `git restore` from HEAD or surface manual-recovery instructions."""


@dataclass
class ValidationOutcome:
    check_name: str
    result: str  # "PASS" | "FAIL"
    details: str = ""


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
    for line in result.stdout.splitlines():
        # porcelain format: XY <path>
        if len(line) < 3:
            continue
        path = line[3:].strip()
        if path.startswith(tuple(aiadra_managed_prefixes)) or path == "events.jsonl":
            return True, f"AIADRA-managed path dirty: {path}"
    return False, ""


# -----------------------------------------------------------------------------
# TransactionDraft
# -----------------------------------------------------------------------------


@dataclass
class TransactionDraft:
    """In-memory accumulation of Transaction changes per ADR/0025 §6."""

    workspace: Path
    bundle: BundleHandle
    kind: TransactionKind
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

    def stage_sidecar(self, obj_uuid: str | UUID, sidecar: dict[str, Any]) -> None:
        self.sidecar_writes[str(obj_uuid)] = sidecar

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
        """
        outcomes: list[ValidationOutcome] = []

        # Run pre-validate hooks (B6 mutation-prohibition, etc.)
        for hook in self.pre_validate_hooks:
            hook(self)

        # 1. Schema-validate each staged sidecar
        for uuid, sc in self.sidecar_writes.items():
            obj_type = sc.get("object", {}).get("type")
            if not obj_type:
                raise SchemaValidationError(f"Staged sidecar for {uuid} missing object.type")
            self.bundle.validate(sc, "sidecar", obj_type)
            outcomes.append(ValidationOutcome(f"schema(sidecar:{uuid})", "PASS"))

        # 2. Schema-validate each staged event
        for ev in self.events:
            et = ev.get("event_type")
            if not et:
                raise SchemaValidationError(f"Staged event missing event_type: {ev!r}")
            self.bundle.validate(ev, "event", et)
            outcomes.append(ValidationOutcome(f"schema(event:{ev.get('event_id', '?')})", "PASS"))

        # 3. Schema-validate each staged reservation
        for prefix, res in self.reservation_writes.items():
            self.bundle.validate(res, "reservation", prefix)
            outcomes.append(ValidationOutcome(f"schema(reservation:{prefix})", "PASS"))

        # 4. Schema-validate each staged revision
        for (uuid, rev_id), content in self.revision_writes.items():
            obj_type = content.get("object", {}).get("type")
            self.bundle.validate(content, "revision", obj_type)
            outcomes.append(ValidationOutcome(f"schema(revision:{rev_id})", "PASS"))

        # 5. Schema-validate each staged manifest
        for label, m in self.manifest_writes.items():
            self.bundle.validate(m, "manifest", m.get("manifest_type", "release"))
            outcomes.append(ValidationOutcome(f"schema(manifest:{label})", "PASS"))

        # 6. B9: Proposed-state sidecar/event fold check. Skip for INIT
        # (workspace empty; no events to fold; reservations are seeded fresh).
        if self.kind != TransactionKind.INIT:
            self._validate_proposed_fold(outcomes)

        # Run post-validate hooks (final-stage scans, etc.)
        for hook in self.post_validate_hooks:
            hook(self)

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
        if not self.events and not self.sidecar_writes:
            return  # nothing to fold

        from ..validation.fold import _apply_attachment_delta, fold_events_to_state, FoldInconsistencyError as _FoldErr

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
        outcomes.append(ValidationOutcome("proposed_fold_invariant", "PASS"))

    # -------------------------------------------------------------------------

    def rollback(self, *, reason: str | None = None) -> "RollbackResult":
        """Discard the draft. Phase A per ADR/0026 §9 + arc 20260531-7:
        discard-only, no audit emission (Phase D adds audit).

        Clears ALL staged mutable collections per Codex1 Q5 absorption:
        sidecar_writes, sidecar_deletes, events, reservation_writes,
        revision_writes, manifest_writes, vault_writes, project_pin_write,
        commit_message_lines, pre_validate_hooks, post_validate_hooks.

        Returns a `RollbackResult` carrying the original `transaction_id`,
        optional `reason`, and `discarded_change_count` = sum of all the
        non-empty staged collections at the time of rollback.
        """
        discarded = (
            len(self.events)
            + len(self.sidecar_writes)
            + len(self.sidecar_deletes)
            + len(self.reservation_writes)
            + len(self.revision_writes)
            + len(self.manifest_writes)
            + len(self.vault_writes)
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
        return RollbackResult(
            transaction_id=self.transaction_id,
            reason=reason,
            discarded_change_count=discarded,
        )

    # -------------------------------------------------------------------------

    def commit(self) -> CommitResult:
        """Write all staged changes + git add + git commit. Atomic boundary."""
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
            if rel_paths:
                _git(self.workspace, "add", "--", *rel_paths)
                msg = "\n".join(self.commit_message_lines) or f"aiadra: {self.kind.value} {self.transaction_id}"
                try:
                    _git(self.workspace, "commit", "-m", msg)
                    commit_hash = _git(self.workspace, "rev-parse", "HEAD").stdout.strip()
                except subprocess.CalledProcessError as e:
                    raise CommitError(
                        f"git commit failed: {e.stderr.strip() or e.stdout.strip()}"
                    ) from e

        return CommitResult(
            commit_hash=commit_hash,
            transaction_id=self.transaction_id,
            event_ids=[ev["event_id"] for ev in self.events if "event_id" in ev],
        )
