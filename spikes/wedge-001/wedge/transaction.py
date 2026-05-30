"""Transaction lifecycle coordinator: allocate Number + write sidecar +
append event in one (spike-grade) coherent commit.

Per ADR/0004 §6 cross-artifact Transaction-atomic invariant. The spike's
per-artifact atomicity uses temp-file-then-rename (os.replace, atomic on same
volume); cross-artifact atomicity (sidecar + event + Reservation) is NOT
enforced beyond ordering — a crash between writes leaves the sidecar/event
invariant violated, which the fold check detects on next run. Documented in
FRICTION_LOG.md.

Commit order: Reservation → sidecar → event. Fold check runs after every
write to catch ordering bugs immediately.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any

from . import SCHEMA_BUNDLE_VERSION
from .event_log import append_event, next_event_id, next_transaction_id
from .sidecar import load_yaml, write_yaml_atomic
from .validate import (
    load_reservation_validated,
    load_sidecar_validated,
)


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def reservation_path(workspace: Path, prefix: str) -> Path:
    return workspace / "Reservations" / f"{prefix}.yaml"


def sidecar_path(workspace: Path, object_uuid: str) -> Path:
    return workspace / "revisions" / object_uuid / "working.yaml"


def revision_path(workspace: Path, object_uuid: str, revision_id: str) -> Path:
    return workspace / "revisions" / object_uuid / f"{revision_id}.yaml"


def manifest_path(workspace: Path, release_label: str) -> Path:
    return workspace / "Releases" / release_label / "manifest.json"


def init_workspace(workspace: Path) -> None:
    """Create empty Reservations + events.jsonl + revisions/ + Releases/."""
    (workspace / "revisions").mkdir(parents=True, exist_ok=True)
    (workspace / "Releases").mkdir(parents=True, exist_ok=True)
    for prefix in ("P", "REQ"):
        rpath = reservation_path(workspace, prefix)
        if not rpath.exists():
            initial = {
                "schema_version": SCHEMA_BUNDLE_VERSION,
                "name": f"aiadra-reservation-{prefix}",
                "status": "active",
                "artifact_kind": "reservation",
                "discriminator": prefix,
                "reservations": {},
            }
            write_yaml_atomic(rpath, initial)
    events = workspace / "events.jsonl"
    if not events.exists():
        events.touch()


def _allocate_number(workspace: Path, prefix: str, number: str, object_uuid: str, tx_id: str) -> None:
    """Add a current Reservation entry; reject if number already present."""
    rpath = reservation_path(workspace, prefix)
    res = load_reservation_validated(rpath, prefix)
    if number in res["reservations"]:
        raise ValueError(f"Number {number} already allocated in {rpath}")
    res["reservations"][number] = {
        "object_uuid": object_uuid,
        "status": "current",
        "allocated_at": now_iso(),
        "allocated_by_transaction": tx_id,
    }
    # Sort by number-key for deterministic diffs
    res["reservations"] = dict(sorted(res["reservations"].items()))
    write_yaml_atomic(rpath, res)


def create_object(
    workspace: Path,
    sidecar_data: dict[str, Any],
    prefix: str,
    event_type: str,
) -> tuple[str, str]:
    """Allocate Number + write working sidecar + append event. Returns (tx_id, event_id)."""
    tx_id = next_transaction_id(workspace)
    evt_id = next_event_id(workspace)
    obj = sidecar_data["object"]
    object_uuid = obj["uuid"]
    number = obj["number"]

    _allocate_number(workspace, prefix, number, object_uuid, tx_id)
    write_yaml_atomic(sidecar_path(workspace, object_uuid), sidecar_data)

    event = {
        "schema_version": SCHEMA_BUNDLE_VERSION,
        "event_id": evt_id,
        "event_type": event_type,
        "timestamp": now_iso(),
        "transaction_id": tx_id,
        "payload": {
            "uuid": object_uuid,
            "number": number,
            "initial_sidecar": json.loads(json.dumps(sidecar_data)),
        },
    }
    append_event(workspace, event)
    return tx_id, evt_id


def add_relationship(
    workspace: Path,
    source_uuid: str,
    relationship_record: dict[str, Any],
) -> tuple[str, str]:
    """Append a relationship record to source Object's working sidecar + emit event."""
    tx_id = next_transaction_id(workspace)
    evt_id = next_event_id(workspace)
    spath = sidecar_path(workspace, source_uuid)
    sidecar = load_sidecar_validated(spath)
    sidecar.setdefault("relationship", []).append(json.loads(json.dumps(relationship_record)))
    write_yaml_atomic(spath, sidecar)

    event = {
        "schema_version": SCHEMA_BUNDLE_VERSION,
        "event_id": evt_id,
        "event_type": "relationship_created",
        "timestamp": now_iso(),
        "transaction_id": tx_id,
        "payload": {
            "source_uuid": source_uuid,
            "relationship_record": json.loads(json.dumps(relationship_record)),
        },
    }
    append_event(workspace, event)
    return tx_id, evt_id


def change_parameter(
    workspace: Path,
    object_uuid: str,
    parameter_id: str,
    new_value: float,
    rationale: str,
) -> tuple[str, str, float]:
    """Update parameter in working sidecar + emit event. Returns (tx, evt, old_value).

    Caller is responsible for validating BEFORE calling this; rejected
    transactions must NOT reach this function (per ADR/0023 §10 + OQ-0003 —
    no canonical Product Truth artifact for rejected transactions).
    """
    tx_id = next_transaction_id(workspace)
    evt_id = next_event_id(workspace)
    spath = sidecar_path(workspace, object_uuid)
    sidecar = load_sidecar_validated(spath)
    old_value: float | None = None
    for p in sidecar.get("parameter", []):
        if p["id"] == parameter_id:
            old_value = p["value"]
            p["value"] = new_value
            # NOTE: fact_provenance NOT updated here. The parameter_changed
            # event payload carries only old_value/new_value/rationale; if the
            # spike mutated fact_provenance the fold check would fail because
            # it can't derive that mutation from event data. Production-grade
            # should either extend the event payload with new_fact_provenance
            # or have the fold derive fact_provenance from event_type.
            # See FRICTION_LOG.md.
            break
    if old_value is None:
        raise ValueError(f"Parameter {parameter_id} not present on {object_uuid}")
    write_yaml_atomic(spath, sidecar)

    event = {
        "schema_version": SCHEMA_BUNDLE_VERSION,
        "event_id": evt_id,
        "event_type": "parameter_changed",
        "timestamp": now_iso(),
        "transaction_id": tx_id,
        "payload": {
            "object_uuid": object_uuid,
            "parameter_id": parameter_id,
            "old_value": old_value,
            "new_value": new_value,
            "rationale": rationale,
        },
    }
    append_event(workspace, event)
    return tx_id, evt_id, old_value


def materialize_revision(
    workspace: Path,
    object_uuid: str,
    revision_id: str,
    revision_label: str,
    revision_id_map: dict[str, str],
) -> tuple[Path, str]:
    """Build released Revision file with materialized Fixed bindings.

    For every relationship in the working sidecar with binding=float, switch
    to fixed and pin endpoints[0].revision_id from revision_id_map (keyed by
    target object_uuid). Set object.lifecycle=released and add revision_id /
    revision_label / released_at.

    Returns (revision_path, revision_hash). The hash is computed from the
    EXACT bytes written to disk (post-write re-read), so manifest pins
    always match what reviewers / consumers see. Per Codex2 B2.
    """
    import hashlib

    sidecar = load_sidecar_validated(sidecar_path(workspace, object_uuid))
    sidecar["object"]["lifecycle"] = "released"
    sidecar["object"]["revision_id"] = revision_id
    sidecar["object"]["revision_label"] = revision_label
    sidecar["object"]["released_at"] = now_iso()

    for rel in sidecar.get("relationship", []):
        if rel.get("binding") == "float":
            rel["binding"] = "fixed"
        for ep in rel.get("endpoints", []):
            target_uuid = ep["object_uuid"]
            if target_uuid not in revision_id_map:
                raise ValueError(f"Cannot materialize satisfies endpoint: target {target_uuid} not in release set")
            ep["revision_id"] = revision_id_map[target_uuid]

    rpath = revision_path(workspace, object_uuid, revision_id)
    write_yaml_atomic(rpath, sidecar)
    # Hash the bytes ACTUALLY on disk (post-write), not the in-memory text.
    h = hashlib.sha256(rpath.read_bytes()).hexdigest()
    return rpath, f"sha256:{h}"


def append_release_event(
    workspace: Path,
    tx_id: str,
    object_type: str,
    object_uuid: str,
    revision_id: str,
    revision_hash: str,
) -> str:
    evt_id = next_event_id(workspace)
    event = {
        "schema_version": SCHEMA_BUNDLE_VERSION,
        "event_id": evt_id,
        "event_type": f"{object_type.lower()}_released",
        "timestamp": now_iso(),
        "transaction_id": tx_id,
        "payload": {
            "object_uuid": object_uuid,
            "revision_id": revision_id,
            "revision_hash": revision_hash,
        },
    }
    append_event(workspace, event)
    return evt_id
