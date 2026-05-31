"""Atomic byte writes via temp-file-then-rename.

Writes raw bytes so platform newline translation cannot diverge the on-disk
bytes from the in-memory text's UTF-8 hash. Carries Wedge-001 round-2 B2
absorption.
"""
from __future__ import annotations

import os
from pathlib import Path


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Atomically write raw bytes to `path` via temp-file-then-rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, path)


def atomic_write_text(path: Path, text: str) -> None:
    """Atomically write UTF-8-encoded text — no newline translation."""
    atomic_write_bytes(path, text.encode("utf-8"))
