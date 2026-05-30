"""Test that every fixtures/profile_negative/*.yaml is rejected by the AIADRA
YAML Profile lint.

Per Codex1 N1 (arc 20260530-1): spike grade is fine for Profile lint
implementation, but the spike should include tiny positive/negative fixtures
proving rejection at read time. This script is that proof.

Run: .venv/Scripts/python.exe test_profile_negative.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from wedge.sidecar import ProfileViolationError, load_yaml


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    neg_dir = Path(__file__).parent / "fixtures" / "profile_negative"
    fixtures = sorted(neg_dir.glob("*.yaml"))
    if not fixtures:
        print("No negative fixtures found")
        return 1

    failed = 0
    for f in fixtures:
        try:
            load_yaml(f)
            print(f"✗ {f.name} — should have been rejected but parsed cleanly")
            failed += 1
        except ProfileViolationError as e:
            print(f"✓ {f.name} — rejected: {e}")
        except Exception as e:
            print(f"? {f.name} — unexpected exception ({type(e).__name__}): {e}")
            failed += 1

    if failed:
        print(f"\n{failed}/{len(fixtures)} fixtures failed to be rejected as expected")
        return 1
    print(f"\nAll {len(fixtures)} negative fixtures rejected as expected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
