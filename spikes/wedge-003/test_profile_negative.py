"""Test that every fixtures/profile_negative/*.yaml is rejected by the AIADRA
YAML Profile lint.

Carried forward verbatim from Wedge-001 + Wedge-002 per ADR/0030 D12 +
ADR/0024 §9 precedent. The 12 fixtures are unchanged from Wedge-002 (YAML
Profile didn't change in v0.28.0).

Difference from Wedge-002: imports `ProfileViolationError` + `load_yaml`
from `aiadra_core` (not `wedge`) because Wedge-003 inherits the YAML
Profile lint from `aiadra-core` (arc 7 Phase A + arc 10 Phase D).

Run: aiadra-core/.venv/Scripts/python.exe spikes/wedge-003/test_profile_negative.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from aiadra_core.truth_model.sidecar import load_yaml
from aiadra_core.validation.profile import ProfileViolationError


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
            print(f"[FAIL] {f.name} -- should have been rejected but parsed cleanly")
            failed += 1
        except ProfileViolationError as e:
            print(f"[OK]   {f.name} -- rejected: {e}")
        except Exception as e:
            print(f"[?]    {f.name} -- unexpected exception ({type(e).__name__}): {e}")
            failed += 1

    if failed:
        print(f"\n{failed}/{len(fixtures)} fixtures failed to be rejected as expected")
        return 1
    print(f"\nAll {len(fixtures)} negative fixtures rejected as expected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
