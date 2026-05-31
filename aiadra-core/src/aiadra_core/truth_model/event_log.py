"""JSONL append-only event log + validated iterator + sequencing helpers.

Per ADR/0001 §4 sidecar/event invariant: replaying the event log must derive a
current state identical to on-disk working sidecars.

Per Wedge-001 round-3 B1 absorption: every event read MUST be schema-validated
before its contents are used for sequencing or fold derivation. `read_events()`
is the validated iterator; `_read_events_raw()` is internal-only.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterator


def event_log_path(workspace: Path) -> Path:
    return workspace / "events.jsonl"


def _read_events_raw(workspace: Path) -> Iterator[dict[str, Any]]:
    """Internal: yield parsed events without schema validation."""
    path = event_log_path(workspace)
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def read_events(workspace: Path, bundle_dir: Path) -> Iterator[dict[str, Any]]:
    """Yield each event, schema-validating before yield.

    Lazy-imports `validate_event` to avoid a circular import with the
    validation layer. The bundle_dir argument keeps validation bundle-aware
    rather than hard-coding "current packaged bundle" (per Codex1 N3 arc
    20260531-1).
    """
    from ..validation.schema import validate_event

    for event in _read_events_raw(workspace):
        validate_event(event, bundle_dir)
        yield event


def append_event(workspace: Path, event: dict[str, Any]) -> None:
    """Append one event as a single canonical JSON line."""
    path = event_log_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


def next_event_id(workspace: Path, bundle_dir: Path) -> str:
    max_n = 0
    for event in read_events(workspace, bundle_dir):
        eid = event.get("event_id", "")
        if eid.startswith("evt_"):
            try:
                n = int(eid[4:])
                if n > max_n:
                    max_n = n
            except ValueError:
                pass
    return f"evt_{max_n + 1:04d}"


def next_transaction_id(workspace: Path, bundle_dir: Path) -> str:
    max_n = 0
    for event in read_events(workspace, bundle_dir):
        tid = event.get("transaction_id", "")
        if tid.startswith("tx_"):
            try:
                n = int(tid[3:])
                if n > max_n:
                    max_n = n
            except ValueError:
                pass
    return f"tx_{max_n + 1:04d}"


def last_event_id_and_hash(workspace: Path, bundle_dir: Path) -> tuple[str | None, str | None]:
    """Return (last_event_id, sha256:hex-of-last-line) or (None, None)."""
    from ..validation.schema import validate_event

    path = event_log_path(workspace)
    if not path.exists():
        return None, None
    last_line: str | None = None
    last_id: str | None = None
    with path.open(encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            event = json.loads(stripped)
            validate_event(event, bundle_dir)
            last_line = stripped
            last_id = event.get("event_id")
    if last_line is None:
        return None, None
    h = hashlib.sha256(last_line.encode("utf-8")).hexdigest()
    return last_id, f"sha256:{h}"
