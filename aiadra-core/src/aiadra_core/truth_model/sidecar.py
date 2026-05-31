"""Working sidecar I/O.

Working sidecars live at `<workspace>/revisions/<object_uuid>/working.yaml`.
Released Revisions live alongside as `<workspace>/revisions/<object_uuid>/<revision_id>.yaml`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from ..validation.profile import dump_yaml, load_yaml
from .atomic import atomic_write_text


def revisions_dir(workspace: Path) -> Path:
    return workspace / "revisions"


def working_sidecar_path(workspace: Path, obj_uuid: str | UUID) -> Path:
    return revisions_dir(workspace) / str(obj_uuid) / "working.yaml"


def load_sidecar(workspace: Path, obj_uuid: str | UUID) -> dict[str, Any]:
    """Read working sidecar. Profile-lints the raw YAML."""
    return load_yaml(working_sidecar_path(workspace, obj_uuid))


def write_sidecar(workspace: Path, obj_uuid: str | UUID, sidecar: dict[str, Any]) -> str:
    """Profile-dump + atomic write. Returns the exact UTF-8 text written."""
    text = dump_yaml(sidecar)
    atomic_write_text(working_sidecar_path(workspace, obj_uuid), text)
    return text


def list_working_sidecar_uuids(workspace: Path) -> list[str]:
    """List on-disk working sidecar object UUIDs.

    Used by the bidirectional fold check (validation.fold) — every UUID with a
    working.yaml on disk must be derivable from events; otherwise the
    sidecar/event invariant per ADR/0001 §4 is violated (per Codex1 B3
    absorption arc 20260531-1).
    """
    rdir = revisions_dir(workspace)
    if not rdir.exists():
        return []
    return [
        d.name for d in rdir.iterdir()
        if d.is_dir() and (d / "working.yaml").exists()
    ]
