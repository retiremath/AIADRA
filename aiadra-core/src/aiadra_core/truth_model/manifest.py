"""Release Manifest I/O.

Per ADR/0001 §3: manifests are deterministic JSON (sorted keys, canonical
serialization) so they are content-hashable + signable + reproducible.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .atomic import atomic_write_bytes


def releases_dir(workspace: Path) -> Path:
    return workspace / "Releases"


def manifest_path(workspace: Path, release_label: str) -> Path:
    return releases_dir(workspace) / release_label / "manifest.json"


def serialize_manifest(manifest: dict[str, Any]) -> bytes:
    """Canonical deterministic JSON bytes — sorted keys, no whitespace."""
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def write_manifest(workspace: Path, release_label: str, manifest: dict[str, Any]) -> str:
    """Serialize + atomic write. Returns the manifest's content hash."""
    payload = serialize_manifest(manifest)
    atomic_write_bytes(manifest_path(workspace, release_label), payload)
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def load_manifest(workspace: Path, release_label: str) -> dict[str, Any]:
    return json.loads(manifest_path(workspace, release_label).read_text(encoding="utf-8"))


def list_release_labels(workspace: Path) -> list[str]:
    rdir = releases_dir(workspace)
    if not rdir.exists():
        return []
    return sorted(d.name for d in rdir.iterdir() if d.is_dir() and manifest_path(workspace, d.name).exists())
