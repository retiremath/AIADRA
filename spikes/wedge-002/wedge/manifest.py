"""Release Manifest construction + deterministic JSON + content hash.

Per ADR/0023 §2 + ADR/0009 §5 + ADR/0001 §3 + ADR/0003: manifest pins released
Object Revision (uuid, number, revision_id, revision_hash); validation
outcomes; event-log boundary. Materialized `satisfies` lives INSIDE the Part
Revision (per ADR/0009 §5), transitively pinned via Revision hash. Does NOT
pin acceleration-cache state (derived/local/never-canonical per ADR/0001 §3).

Discriminator: `manifest_type: "release"` per ADR/0003 (absorbed from
20260530-1 Codex1 B4).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from . import SCHEMA_BUNDLE_VERSION


def build_manifest(
    release_label: str,
    released_at: str,
    revisions: list[dict[str, Any]],
    validation_outcomes: list[dict[str, Any]],
    last_event_id: str,
    last_event_hash: str,
) -> dict[str, Any]:
    """Build the manifest dict (pre-serialization)."""
    return {
        "schema_version": SCHEMA_BUNDLE_VERSION,
        "artifact_kind": "manifest",
        "manifest_type": "release",
        "release_label": release_label,
        "released_at": released_at,
        "revisions": sorted(revisions, key=lambda r: r["object_uuid"]),
        "validation_outcomes": sorted(validation_outcomes, key=lambda v: v["check_name"]),
        "event_log_boundary": {
            "last_event_id": last_event_id,
            "last_event_hash": last_event_hash,
        },
    }


def serialize_manifest(manifest: dict[str, Any]) -> bytes:
    """Deterministic JSON: sorted keys, compact separators, UTF-8 bytes."""
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def hash_bytes(b: bytes) -> str:
    return f"sha256:{hashlib.sha256(b).hexdigest()}"
