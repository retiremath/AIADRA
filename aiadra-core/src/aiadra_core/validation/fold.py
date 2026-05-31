"""Sidecar/event invariant per ADR/0001 §4.

**Bidirectional check** (per Codex1 B3 absorption arc 20260531-1):

1. Every folded UUID has a matching on-disk working sidecar with identical state.
2. Every on-disk `revisions/<uuid>/working.yaml` UUID is present in the folded
   state (i.e., no stray sidecars not derivable from events).

The spike implementation only verified (1). Carrying that forward would preserve
a known hole — a handwritten or stale working.yaml not derivable from events
would silently pass validation, violating "sidecars and events must agree;
neither silently wins."
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..truth_model.event_log import read_events
from ..truth_model.sidecar import list_working_sidecar_uuids
from .schema import load_sidecar_validated


class FoldInconsistencyError(ValueError):
    """Sidecar/event invariant violation."""


_ATTACHMENT_CHANGED_EVENTS = (
    "drawing_changed",
    "test_procedure_changed",
    "test_execution_changed",
    "evidence_artifact_changed",
)


def _apply_attachment_delta(
    state: dict[str, dict[str, Any]],
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Apply a `<type>_changed.attachment_delta` event to fold state.

    Per B5 absorption (Phase 1 arc 20260531-2): enforces add/update/remove
    semantic invariants — add MUST fail if id exists; update/remove MUST fail
    if id missing; record.id MUST equal attachment_id.
    """
    uuid = payload["object_uuid"]
    delta = payload["attachment_delta"]
    op = delta["operation"]
    att_id = delta["attachment_id"]
    if uuid not in state:
        raise FoldInconsistencyError(
            f"{event_type} for unknown Object {uuid!r} (no <type>_created event)"
        )
    sidecar_attachments = state[uuid].setdefault("attachment", [])
    by_id = {a["id"]: i for i, a in enumerate(sidecar_attachments)}

    if op == "add":
        if att_id in by_id:
            raise FoldInconsistencyError(
                f"{event_type} add attachment_id {att_id!r} but already present on {uuid}"
            )
        rec = delta.get("attachment_record")
        if not rec:
            raise FoldInconsistencyError(
                f"{event_type} add missing attachment_record"
            )
        if rec.get("id") != att_id:
            raise FoldInconsistencyError(
                f"{event_type} attachment_record.id {rec.get('id')!r} != "
                f"attachment_id {att_id!r}"
            )
        sidecar_attachments.append(json.loads(json.dumps(rec)))
    elif op == "update":
        if att_id not in by_id:
            raise FoldInconsistencyError(
                f"{event_type} update attachment_id {att_id!r} but not present on {uuid}"
            )
        rec = delta.get("attachment_record")
        if not rec:
            raise FoldInconsistencyError(
                f"{event_type} update missing attachment_record"
            )
        if rec.get("id") != att_id:
            raise FoldInconsistencyError(
                f"{event_type} attachment_record.id {rec.get('id')!r} != "
                f"attachment_id {att_id!r}"
            )
        sidecar_attachments[by_id[att_id]] = json.loads(json.dumps(rec))
    elif op == "remove":
        if att_id not in by_id:
            raise FoldInconsistencyError(
                f"{event_type} remove attachment_id {att_id!r} but not present on {uuid}"
            )
        sidecar_attachments[:] = [a for a in sidecar_attachments if a["id"] != att_id]


def fold_events_to_state(workspace: Path, bundle_dir: Path) -> dict[str, dict[str, Any]]:
    """Replay validated events; build current working-state by UUID.

    Handles generic `<type>_created` events (Wedge-002 round-1 B1 pattern:
    `et.endswith('_created') + initial_sidecar payload`), `relationship_created`,
    `parameter_changed`, `<type>_changed` (W2 absorption — attachment_delta with
    B5 invariants), `release_staged` (audit-oriented; no working-state mutation),
    and `<type>_released` (no working-state mutation — Revisions are separate
    immutable artifacts per ADR/0001 §3).
    """
    state: dict[str, dict[str, Any]] = {}
    for event in read_events(workspace, bundle_dir):  # validated iterator
        et = event["event_type"]
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
        elif et in _ATTACHMENT_CHANGED_EVENTS:
            _apply_attachment_delta(state, et, event["payload"])
        elif et == "release_staged":
            # Audit-oriented per B1 absorption; no working-state mutation.
            pass
        # <type>_released and <type>_retired events do not mutate working state.
    return state


def validate_fold(workspace: Path, bundle_dir: Path) -> None:
    """Verify the sidecar/event invariant — bidirectionally.

    Raises FoldInconsistencyError on either direction's violation.
    """
    folded = fold_events_to_state(workspace, bundle_dir)
    on_disk_uuids = set(list_working_sidecar_uuids(workspace))
    folded_uuids = set(folded.keys())

    # Direction 1: every folded UUID has matching on-disk sidecar with
    # identical state (the spike's existing check).
    for uuid, expected in folded.items():
        if uuid not in on_disk_uuids:
            raise FoldInconsistencyError(
                f"Events derive Object {uuid}; on-disk working sidecar missing"
            )
        on_disk = load_sidecar_validated(workspace, uuid, bundle_dir)
        if json.dumps(on_disk, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise FoldInconsistencyError(
                f"Sidecar/event invariant violated for {uuid}: "
                f"on-disk working sidecar does not match event fold"
            )

    # Direction 2: every on-disk working sidecar UUID is present in the
    # folded state (per Codex1 B3 absorption arc 20260531-1). A working.yaml
    # not derivable from events is a disagreement — "neither silently wins."
    extra_uuids = on_disk_uuids - folded_uuids
    if extra_uuids:
        raise FoldInconsistencyError(
            f"On-disk working sidecar(s) not derivable from events "
            f"(no corresponding creation event found): {sorted(extra_uuids)}"
        )
