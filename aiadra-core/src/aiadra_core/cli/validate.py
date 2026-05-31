"""`aiadra validate <workspace>` — read-only Layer-2 sweep.

Per Phase A (arc 20260531-7): this CLI is now a thin wrapper over
`aiadra_core.protocol.validate()`. The protocol entry point is a pure
function that returns a structured `ValidationReport`; this module owns
stdout emission + exit-code mapping (Codex1 N2 absorption — keep CLI
emission in CLI land; protocol returns data).

Exit codes preserved from Phase 1:
  0 on success
  1 on validation failure
  3 on missing or mismatched `.aiadra/schemas.yaml` project pin
"""
from __future__ import annotations

import sys
from pathlib import Path

from ..protocol import (
    ProjectPinError,
    validate as protocol_validate,
)


def run_validate(workspace: Path) -> int:
    """Run all read-side checks against a workspace. Return exit code."""
    try:
        report = protocol_validate(workspace)
    except ProjectPinError as e:
        # Preserve Phase 1 output shape: emit a fake project_pin FAIL outcome
        # then the FAILED banner. CLI exit 3 per Phase 1 contract.
        _emit_outcomes([("project_pin", "FAIL", str(e))])
        print("FAILED: project pin or digest mismatch; aborting before reads.",
              file=sys.stderr)
        return 3
    _emit_outcomes([(o.check_name, o.result, o.details) for o in report.outcomes])
    print(f"\nSummary: {len(report.outcomes)} check(s); {report.failures_count} failure(s).")
    return 0 if report.failures_count == 0 else 1


def _emit_outcomes(outcomes: list[tuple[str, str, str]]) -> None:
    for name, result, details in outcomes:
        mark = "✓" if result == "PASS" else "✗"
        line = f"  {mark} {result}  {name}"
        if details:
            line += f"  — {details}"
        print(line)


def cli_main(argv: list[str]) -> int:
    if len(argv) < 1:
        print("usage: aiadra validate <workspace>", file=sys.stderr)
        return 2
    workspace = Path(argv[0]).resolve()
    if not workspace.exists():
        print(f"workspace does not exist: {workspace}", file=sys.stderr)
        return 2
    return run_validate(workspace)
