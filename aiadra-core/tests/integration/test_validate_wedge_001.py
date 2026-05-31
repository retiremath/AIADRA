"""End-to-end: aiadra validate against the carried Wedge-001 fixture project.

Acceptance criterion item 3 per Claude1 Decision §7 (arc 20260531-1).
"""
from __future__ import annotations

from pathlib import Path

from aiadra_core.cli.validate import run_validate


def test_validate_wedge_001_fixture_succeeds():
    workspace = Path(__file__).parent.parent / "fixtures" / "wedge_001"
    rc = run_validate(workspace)
    assert rc == 0, f"validate exited {rc} (expected 0) against Wedge-001 fixture"
