"""End-to-end: aiadra inspect against the carried Wedge-002 fixture project.

Acceptance criterion item 7 per Claude1 Decision §7 (arc 20260531-1). Target
is P-000058 per Codex1 B2 absorption (the actual Part number in the Wedge-002
manifest is P-000058, not P-000023 as Claude1 misstated).

Per Codex2 B1 absorption arc 20260531-1: inspect MUST verify project pin
before reading artifacts; tests for missing/mismatched pins are parallel to
the validate tests in `tests/unit/test_bundle_digest.py`.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aiadra_core.cli.inspect import run_inspect


def test_inspect_part_p_000058_succeeds(capsys):
    workspace = Path(__file__).parent.parent / "fixtures" / "wedge_002"
    rc = run_inspect(workspace, "P-000058")
    captured = capsys.readouterr()
    assert rc == 0, f"inspect exited {rc}; stdout=\n{captured.out}\nstderr=\n{captured.err}"
    assert "P-000058" in captured.out
    # Spike-known Part uuid
    assert "0193abcd-1234-7890-abcd-111111111111" in captured.out


def test_inspect_nonexistent_object_returns_2():
    workspace = Path(__file__).parent.parent / "fixtures" / "wedge_002"
    rc = run_inspect(workspace, "P-999999")
    assert rc == 2


def test_inspect_missing_pin_returns_3(tmp_path: Path):
    """Per Codex2 B1: inspect must abort before reads when project pin is missing."""
    src_fixture = Path(__file__).parent.parent / "fixtures" / "wedge_002"
    workspace = tmp_path / "wedge_002_no_pin"
    shutil.copytree(src_fixture, workspace)
    # Remove the project pin
    pin = workspace / ".aiadra" / "schemas.yaml"
    pin.unlink()
    rc = run_inspect(workspace, "P-000058")
    assert rc == 3


def test_inspect_mismatched_pin_returns_3(tmp_path: Path):
    """Per Codex2 B1: inspect must abort before reads when pin digest mismatches."""
    src_fixture = Path(__file__).parent.parent / "fixtures" / "wedge_002"
    workspace = tmp_path / "wedge_002_bad_pin"
    shutil.copytree(src_fixture, workspace)
    pin = workspace / ".aiadra" / "schemas.yaml"
    pin.write_bytes(
        b'"bundle_version": "0.19.0"\n'
        b'"bundle_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000"\n'
    )
    rc = run_inspect(workspace, "P-000058")
    assert rc == 3
