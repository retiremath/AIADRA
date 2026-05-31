"""Atomic write should preserve raw bytes — no platform newline translation.

Carries Wedge-001 round-2 B2 regression check.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from aiadra_core.truth_model.atomic import atomic_write_bytes, atomic_write_text


def test_atomic_write_bytes_roundtrip(tmp_path: Path) -> None:
    payload = b"line1\nline2\nline3\n"
    target = tmp_path / "sub" / "file.txt"
    atomic_write_bytes(target, payload)
    assert target.exists()
    assert target.read_bytes() == payload
    expected_hash = hashlib.sha256(payload).hexdigest()
    actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    assert expected_hash == actual_hash


def test_atomic_write_text_no_newline_translation(tmp_path: Path) -> None:
    text = "line1\nline2\nline3\n"
    target = tmp_path / "file.txt"
    atomic_write_text(target, text)
    # On Windows, naive Path.write_text would convert \n to \r\n; atomic_write_text MUST not.
    assert target.read_bytes() == text.encode("utf-8")
    assert b"\r\n" not in target.read_bytes()


def test_atomic_write_replaces_existing(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    atomic_write_bytes(target, b"first")
    atomic_write_bytes(target, b"second")
    assert target.read_bytes() == b"second"


def test_atomic_write_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "c" / "file.txt"
    atomic_write_bytes(target, b"deep")
    assert target.read_bytes() == b"deep"
