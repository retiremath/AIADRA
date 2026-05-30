"""JSONL append-only event log + event-id sequencing + fold algorithm.

Per ADR/0001 §4 sidecar/event invariant: replaying the event log from initial
state must derive a current state identical to the on-disk sidecars; if they
disagree, validation fails.

Per Codex3 B1 (arc 20260530-1): every event read MUST be schema-validated
before its contents are used for sequencing or fold derivation. Otherwise a
malformed-but-parseable record could influence a write before the post-write
fold check catches it. `read_events()` is the validated iterator; raw access
via `_read_events_raw()` is internal and not used outside this module's hash
boundary check.

Spike-grade: events carry `initial_sidecar` in part_created/requirement_created
payloads (heavier than production-grade delta-only events; documented in
FRICTION_LOG.md).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterator


def event_log_path(workspace: Path) -> Path:
    return workspace / "events.jsonl"


def _read_events_raw(workspace: Path) -> Iterator[dict[str, Any]]:
    """Internal: yield parsed events without schema validation.

    Only `last_event_id_and_hash()` uses this because it needs the raw line
    bytes (not just the parsed dict) AND it validates each event inline. All
    other callers must use `read_events()` which validates.
    """
    path = event_log_path(workspace)
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def read_events(workspace: Path) -> Iterator[dict[str, Any]]:
    """Yield each event from the log, schema-validating before yield.

    Raises SchemaValidationError on any malformed event. Per Codex3 B1: this
    is what `next_event_id`, `next_transaction_id`, `fold_state`, and
    `validate_fold` consume so sequencing/fold never trusts an unvalidated
    record. Lazy-imports `validate_event` to avoid a circular import with
    `validate.py` (which imports `fold_state` from here).
    """
    from .validate import validate_event

    for event in _read_events_raw(workspace):
        validate_event(event)
        yield event


def append_event(workspace: Path, event: dict[str, Any]) -> None:
    """Append one event as a single JSON line (UTF-8, newline-terminated)."""
    path = event_log_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


def next_event_id(workspace: Path) -> str:
    """Scan validated events for max evt_NNNN and return next."""
    max_n = 0
    for event in read_events(workspace):
        eid = event.get("event_id", "")
        if eid.startswith("evt_"):
            try:
                n = int(eid[4:])
                if n > max_n:
                    max_n = n
            except ValueError:
                pass
    return f"evt_{max_n + 1:04d}"


def next_transaction_id(workspace: Path) -> str:
    """Scan validated events for max tx_NNNN and return next."""
    max_n = 0
    for event in read_events(workspace):
        tid = event.get("transaction_id", "")
        if tid.startswith("tx_"):
            try:
                n = int(tid[3:])
                if n > max_n:
                    max_n = n
            except ValueError:
                pass
    return f"tx_{max_n + 1:04d}"


def last_event_id_and_hash(workspace: Path) -> tuple[str | None, str | None]:
    """Return (last_event_id, sha256:hex-of-last-line) or (None, None) if empty.

    Validates every event during the scan (per Codex3 B1) so the manifest's
    event-log boundary pin never trusts an unvalidated record.
    """
    from .validate import validate_event

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
            validate_event(event)
            last_line = stripped
            last_id = event.get("event_id")
    if last_line is None:
        return None, None
    h = hashlib.sha256(last_line.encode("utf-8")).hexdigest()
    return last_id, f"sha256:{h}"


def fold_state(workspace: Path) -> dict[str, dict[str, Any]]:
    """Replay validated events to derive current working-state sidecars
    keyed by object UUID.

    Spike-grade fold: handles part_created, requirement_created,
    relationship_created, parameter_changed. Release events do NOT mutate
    the working sidecar (per ADR/0009: working sidecar preserves authoring
    intent after release; the Revision file is the released artifact).
    Released Revisions are validated separately by load_revision_validated.
    Each event is schema-validated before its payload mutates state (per
    Codex3 B1).
    """
    state: dict[str, dict[str, Any]] = {}
    for event in read_events(workspace):  # validated iterator
        et = event["event_type"]
        # B1 absorption (Codex1 arc 20260530-3): generic *_created pattern handles
        # all Object-creation events (part_created, requirement_created,
        # test_procedure_created, test_execution_created, evidence_artifact_created,
        # and any future Object Type whose `_created` event carries `initial_sidecar`).
        # The `relationship_created` event is special — it mutates an existing
        # Object's relationship list, not a new state seed.
        if et.endswith("_created") and et != "relationship_created":
            uuid = event["payload"]["uuid"]
            state[uuid] = json.loads(json.dumps(event["payload"]["initial_sidecar"]))
        elif et == "relationship_created":
            src = event["payload"]["source_uuid"]
            rec = event["payload"]["relationship_record"]
            state[src].setdefault("relationship", []).append(json.loads(json.dumps(rec)))
        elif et == "parameter_changed":
            uuid = event["payload"]["object_uuid"]
            pid = event["payload"]["parameter_id"]
            new_value = event["payload"]["new_value"]
            for p in state[uuid].get("parameter", []):
                if p.get("id") == pid:
                    p["value"] = new_value
                    break
        # part_released / requirement_released: no working-state mutation
    return state
