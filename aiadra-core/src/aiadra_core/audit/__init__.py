"""AIADRA failed-Transaction audit log emission per [ADR/0026 §9](../../../Docs/ADR/0026-ai-action-protocol-scope.md)
+ OQ-0003 resolution.

Phase D Codex1 B3 absorption (arc 20260531-10): single-record semantics —
each `TransactionDraft` can emit at most one failed-Transaction audit
record. The draft carries a private `_audit_emitted: bool` flag set by
`_emit_audit_once()`; subsequent emission attempts no-op silently.

Triggers — three explicit paths:
  (a) `TransactionDraft.audit_failure(reason, exception)` — called by the
      operations layer when `draft.validate()` raises and the caller wants
      the failure recorded before rolling back (e.g., propose-time errors
      caught at the CLI boundary).
  (b) `TransactionDraft.rollback(reason=...)` — emits BEFORE clearing if
      `_audit_emitted == False` AND staged content exists.
  (c) `TransactionDraft.commit()` on CommitError — emits before re-raising,
      so write-time failures (rare; runtime / git crash mid-commit) are
      diagnostically visible too.

**Per ADR/0026 §9 verbatim: audit log is diagnostic, NOT truth.** Does NOT
participate in the sidecar/event fold invariant. Is NOT bundle-validated.
Agents MUST NOT use audit content to reason about Truth Model state.

Per Codex1 Q5 absorption: audit write failures (disk full / permission /
collision) NEVER mask validation, rollback, or commit errors. They warn
to stderr and mark the flag (so subsequent attempts no-op).
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..explain import REASON_CLASSIFICATIONS


# ---- AuditRecord shape per ADR/0026 §9 -------------------------------------


@dataclass(frozen=True)
class AuditRecord:
    """One failed-Transaction audit record. Fields per ADR/0026 §9 verbatim.

    Serialized to a single-line JSON record at
    `.aiadra/audit/YYYY-MM-DD/tx_NNNN-failed-<short-hash>.jsonl`.

    `validation_errors` is a list of `ExplanationNode` dicts (via
    `aiadra_core.explain.node_to_dict`); `proposed_events` is the list of
    full event dicts the draft staged. `reason_classification` is one of
    `aiadra_core.explain.REASON_CLASSIFICATIONS`.
    """
    transaction_id: str
    attempted_at: str  # ISO-8601 UTC
    kind: str
    proposed_events: list[dict[str, Any]]
    validation_errors: list[dict[str, Any]]
    reason_classification: str
    reason_text: str
    agent_ref: str | None = None

    def __post_init__(self) -> None:
        if self.reason_classification not in REASON_CLASSIFICATIONS:
            raise ValueError(
                f"AuditRecord.reason_classification must be one of "
                f"{sorted(REASON_CLASSIFICATIONS)}; got {self.reason_classification!r}"
            )

    def to_jsonl_bytes(self) -> bytes:
        """One-line JSON record + trailing newline. Deterministic key order."""
        payload = {
            "transaction_id": self.transaction_id,
            "attempted_at": self.attempted_at,
            "kind": self.kind,
            "agent_ref": self.agent_ref,
            "reason_classification": self.reason_classification,
            "reason_text": self.reason_text,
            "proposed_events": list(self.proposed_events),
            "validation_errors": list(self.validation_errors),
        }
        return (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


# ---- Path computation ------------------------------------------------------


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_short_hash(transaction_id: str, attempted_at: str) -> str:
    """First-8-hex of sha256(transaction_id + attempted_at). Per Codex1 Q4
    absorption: timestamp suffix ensures retries of the same tx_NNNN get
    distinct hashes; collision retry per `write_audit_record()` handles
    the rare birthday case."""
    h = hashlib.sha256((transaction_id + attempted_at).encode("utf-8")).hexdigest()
    return h[:8]


def audit_dir(workspace: Path, attempted_at: str) -> Path:
    """`.aiadra/audit/YYYY-MM-DD/` from the attempted_at timestamp."""
    date_prefix = attempted_at[:10]  # YYYY-MM-DD
    return workspace / ".aiadra" / "audit" / date_prefix


def audit_filename(transaction_id: str, attempted_at: str, *, counter: int = 0) -> str:
    """`tx_NNNN-failed-<short-hash>.jsonl` per ADR/0026 §9. `counter` extends
    the short-hash if a collision is detected (Codex1 Q4 absorption — retry
    with appended counter rather than overwrite)."""
    short = compute_short_hash(transaction_id, attempted_at)
    if counter > 0:
        short = f"{short}-{counter}"
    return f"{transaction_id}-failed-{short}.jsonl"


# ---- Write ------------------------------------------------------------------


def write_audit_record(workspace: Path, record: AuditRecord) -> Path | None:
    """Write `record` to `.aiadra/audit/YYYY-MM-DD/tx_NNNN-failed-<short>.jsonl`.

    Per Codex1 Q4: if filename collides with an existing file (rare), retry
    with `-1`, `-2`, ... appended to the short-hash.

    Per Codex1 Q5: NEVER raises. On any disk error, prints a stderr warning
    and returns `None`. Caller MUST treat `None` as "audit unavailable" but
    proceed with rollback/commit semantics unchanged.

    Returns the actual `Path` written on success, or `None` on failure.
    """
    try:
        d = audit_dir(workspace, record.attempted_at)
        d.mkdir(parents=True, exist_ok=True)
        # Collision retry — bounded to 1000 attempts (way past any realistic case).
        for counter in range(1000):
            path = d / audit_filename(record.transaction_id, record.attempted_at, counter=counter)
            if not path.exists():
                path.write_bytes(record.to_jsonl_bytes())
                return path
        # Pathological — give up and warn.
        print(
            f"aiadra audit: too many filename collisions for {record.transaction_id} "
            f"in {d}; audit record dropped.",
            file=sys.stderr,
        )
        return None
    except Exception as e:
        print(
            f"aiadra audit: failed to write audit record for {record.transaction_id}: "
            f"{type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return None


# ---- AuditConfig + load (config.py-style) ----------------------------------


@dataclass(frozen=True)
class AuditConfig:
    """Project-configurable audit retention. Defaults per ADR/0026 §9 verbatim:
    `max_entries_per_agent: 100`, `max_age_days: 30`, `max_total_mb: 50`."""
    max_entries_per_agent: int = 100
    max_age_days: int = 30
    max_total_mb: int = 50


_DEFAULT_CONFIG = AuditConfig()


def load_audit_config(workspace: Path, *, strict: bool = False) -> AuditConfig:
    """Read `.aiadra/audit-config.yaml` and return an `AuditConfig`.

    Per Codex1 N2 absorption: emission-path callers pass `strict=False`
    (default); missing or unparseable config falls back to defaults with a
    stderr warning, so audit emission cannot block on diagnostic config.
    `aiadra audit-prune` passes `strict=True` so config errors surface
    loudly to the operator.
    """
    path = workspace / ".aiadra" / "audit-config.yaml"
    if not path.exists():
        return _DEFAULT_CONFIG
    try:
        from ..validation.profile import load_yaml
        data = load_yaml(path)
    except Exception as e:
        if strict:
            raise
        print(
            f"aiadra audit: failed to parse {path}: {type(e).__name__}: {e}; "
            f"falling back to defaults.",
            file=sys.stderr,
        )
        return _DEFAULT_CONFIG
    retention = (data or {}).get("retention", {}) or {}
    try:
        cfg = AuditConfig(
            max_entries_per_agent=int(retention.get("max_entries_per_agent", _DEFAULT_CONFIG.max_entries_per_agent)),
            max_age_days=int(retention.get("max_age_days", _DEFAULT_CONFIG.max_age_days)),
            max_total_mb=int(retention.get("max_total_mb", _DEFAULT_CONFIG.max_total_mb)),
        )
    except (TypeError, ValueError) as e:
        if strict:
            raise
        print(
            f"aiadra audit: malformed retention values in {path}: {type(e).__name__}: {e}; "
            f"falling back to defaults.",
            file=sys.stderr,
        )
        return _DEFAULT_CONFIG
    return cfg


# ---- Prune ------------------------------------------------------------------


def list_audit_files(workspace: Path) -> list[Path]:
    """All `.jsonl` files under `.aiadra/audit/`, sorted oldest-first by mtime."""
    root = workspace / ".aiadra" / "audit"
    if not root.exists():
        return []
    files = [p for p in root.rglob("*.jsonl") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime)
    return files


_UNKNOWN_AGENT_BUCKET = "<unknown>"


def _read_agent_ref(p: Path) -> str:
    """Read `agent_ref` field from a JSONL audit record. Returns
    `_UNKNOWN_AGENT_BUCKET` for missing / null / unparseable values so
    every record has a deterministic bucket."""
    try:
        record = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _UNKNOWN_AGENT_BUCKET
    ref = record.get("agent_ref") if isinstance(record, dict) else None
    if not isinstance(ref, str) or not ref:
        return _UNKNOWN_AGENT_BUCKET
    return ref


def compute_prune_set(workspace: Path, config: AuditConfig) -> tuple[list[Path], list[Path]]:
    """Per ADR/0026 §9 retention dimensions: enforces ALL THREE caps —
    `max_age_days`, `max_total_mb`, `max_entries_per_agent`.

    Per Codex2 B1 absorption (arc 20260531-10): `max_entries_per_agent` is
    enforced via JSONL parse + per-`agent_ref` grouping. Files where
    `agent_ref` is null or missing collapse into the `<unknown>` bucket
    (so untagged records don't escape the cap). Per-agent buckets are
    INDEPENDENT — overflow in agent A does not affect agent B's quota.

    Algorithm:
      1. Walk all audit files; for each, read `agent_ref` to assign a bucket.
      2. Within each bucket, keep the NEWEST `max_entries_per_agent` files;
         mark older per-agent excess for deletion.
      3. Apply global `max_age_days` (delete any file older than).
      4. Apply global `max_total_mb` (newest-first; mark excess for deletion).

    Returns (to_delete, to_keep). All three caps applied; a file marked for
    deletion by ANY dimension goes in `to_delete`. Files appear at most once
    in `to_delete`.
    """
    files = list_audit_files(workspace)
    if not files:
        return [], []
    now = datetime.now(timezone.utc).timestamp()
    max_age_seconds = config.max_age_days * 86400
    max_total_bytes = config.max_total_mb * 1024 * 1024
    max_per_agent = config.max_entries_per_agent

    to_delete_set: set[Path] = set()

    # Per-agent cap — bucket by agent_ref (newest-last in list_audit_files
    # which sorts oldest-first by mtime), keep newest max_per_agent per bucket.
    by_agent: dict[str, list[Path]] = {}
    for p in files:
        by_agent.setdefault(_read_agent_ref(p), []).append(p)
    for bucket_files in by_agent.values():
        # bucket_files inherits oldest-first order; older excess is the prefix.
        if len(bucket_files) > max_per_agent:
            for p in bucket_files[:len(bucket_files) - max_per_agent]:
                to_delete_set.add(p)

    # Age cap — flag anything older than max_age_seconds.
    for p in files:
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        if now - mtime > max_age_seconds:
            to_delete_set.add(p)

    # Size cap — walk newest-first; keep until cumulative bytes exceed
    # max_total_bytes; mark older excess for deletion. Skip already-marked
    # files when accounting (they're going away anyway).
    total_bytes_kept = 0
    for p in reversed(files):
        if p in to_delete_set:
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if total_bytes_kept + size > max_total_bytes:
            to_delete_set.add(p)
            continue
        total_bytes_kept += size

    to_delete = [p for p in files if p in to_delete_set]
    to_keep = [p for p in files if p not in to_delete_set]
    return to_delete, to_keep


def apply_prune(workspace: Path, config: AuditConfig) -> tuple[int, int]:
    """Delete files in the prune set. Returns (count_deleted, bytes_freed)."""
    to_delete, _ = compute_prune_set(workspace, config)
    count = 0
    freed = 0
    for p in to_delete:
        try:
            size = p.stat().st_size
            p.unlink()
            count += 1
            freed += size
        except OSError as e:
            print(
                f"aiadra audit: failed to delete {p}: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
    return count, freed


__all__ = [
    "AuditRecord",
    "AuditConfig",
    "compute_short_hash",
    "audit_dir",
    "audit_filename",
    "write_audit_record",
    "load_audit_config",
    "list_audit_files",
    "compute_prune_set",
    "apply_prune",
]
