"""End-to-end: aiadra validate against the carried Wedge-002 fixture project.

Acceptance criterion item 4 per Claude1 Decision §7 (arc 20260531-1).
"""
from __future__ import annotations

from pathlib import Path

from aiadra_core.cli.validate import run_validate


def test_validate_wedge_002_fixture_succeeds():
    workspace = Path(__file__).parent.parent / "fixtures" / "wedge_002"
    rc = run_validate(workspace)
    assert rc == 0, f"validate exited {rc} (expected 0) against Wedge-002 fixture"
