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


def fold_events_to_state(workspace: Path, bundle_dir: Path) -> dict[str, dict[str, Any]]:
    """Replay validated events; build current working-state by UUID.

    Handles generic `<type>_created` events (Wedge-002 round-1 B1 pattern:
    `et.endswith('_created') + initial_sidecar payload`), `relationship_created`,
    `parameter_changed`, and `<type>_released` (no working-state mutation —
    Revisions are separate immutable artifacts per ADR/0001 §3).
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
