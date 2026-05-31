"""Released Revision I/O.

Released Revisions are immutable per ADR/0001 §3; the Revision file's content
hash is computed from disk bytes after write (carries Wedge-001 round-2 B2
absorption).
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from uuid import UUID

from ..validation.profile import dump_yaml, load_yaml
from .atomic import atomic_write_text
from .sidecar import revisions_dir


def revision_path(workspace: Path, obj_uuid: str | UUID, rev_id: str | UUID) -> Path:
    return revisions_dir(workspace) / str(obj_uuid) / f"{rev_id}.yaml"


def load_revision(workspace: Path, obj_uuid: str | UUID, rev_id: str | UUID) -> dict[str, Any]:
    return load_yaml(revision_path(workspace, obj_uuid, rev_id))


def materialize_revision(
    workspace: Path,
    obj_uuid: str | UUID,
    rev_id: str | UUID,
    content: dict[str, Any],
) -> str:
    """Write a released Revision and return its content hash.

    The hash is computed from the on-disk bytes after write — single source of
    truth = disk. Carries Wedge-001 round-2 B2 absorption (Windows newline
    translation bug fix).
    """
    text = dump_yaml(content)
    path = revision_path(workspace, obj_uuid, rev_id)
    atomic_write_text(path, text)
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{h}"


class RevisionHashMismatchError(ValueError):
    pass


def verify_revision_hashes(workspace: Path, revisions: list[dict[str, Any]]) -> None:
    """Re-read every pinned Revision from disk and verify its content hash."""
    for rev in revisions:
        path = revision_path(workspace, rev["object_uuid"], rev["revision_id"])
        actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != rev["revision_hash"]:
            raise RevisionHashMismatchError(
                f"Revision hash mismatch for {rev['object_number']}: "
                f"recorded {rev['revision_hash']}, actual {actual} at {path}"
            )
