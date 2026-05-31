"""`aiadra` CLI entry point — argparse dispatch.

Read-only subcommands implemented in Phase 0:
- `aiadra validate <workspace>`
- `aiadra inspect <workspace> <object-number>`

State-changing subcommands STUB in Phase 0 (raise NotImplementedError; print
"lands in Phase 1" and exit 99 per ADR/0025 §1).

UTF-8 stdout reconfigured at entry so Windows console can render check marks
(carries Wedge-001 minor friction-log absorption).
"""
from __future__ import annotations

import argparse
import sys

from .. import __version__

# Stubbed state-changing commands per ADR/0025 §1 — land in Phase 1+.
_STUB_COMMANDS = [
    "init",
    "change-parameter",
    "create-test-procedure",
    "create-test-execution",
    "create-evidence-artifact",
    "link-satisfies",
    "link-tested-against",
    "link-verifies",
    "link-cites",
    "link-executes",
    "link-executed-on",
    "link-produces",
    "attach-file",
    "release",
    "recover",
]


def _reconfigure_stdout_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass  # older platforms may not support reconfigure; harmless


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aiadra", description="AIADRA Core CLI")
    parser.add_argument("--version", action="version", version=f"aiadra {__version__}")
    sub = parser.add_subparsers(dest="cmd")

    p_validate = sub.add_parser("validate", help="Validate a workspace (read-only)")
    p_validate.add_argument("workspace", help="Path to AIADRA workspace")

    p_inspect = sub.add_parser("inspect", help="Inspect an Object's working sidecar")
    p_inspect.add_argument("workspace", help="Path to AIADRA workspace")
    p_inspect.add_argument("obj_number", help="Object number (e.g. P-000058)")

    for name in _STUB_COMMANDS:
        sp = sub.add_parser(name, help=f"[STUB — Phase 1+] {name}")
        sp.add_argument("rest", nargs=argparse.REMAINDER, help="(stubbed; arguments ignored)")

    return parser


def main(argv: list[str] | None = None) -> int:
    _reconfigure_stdout_utf8()
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.cmd is None:
        parser.print_help()
        return 0

    if args.cmd == "validate":
        from . import validate as _v
        return _v.cli_main([args.workspace])

    if args.cmd == "inspect":
        from . import inspect as _i
        return _i.cli_main([args.workspace, args.obj_number])

    if args.cmd in _STUB_COMMANDS:
        print(
            f"aiadra {args.cmd}: lands in Phase 1 runtime-behavior arc; see "
            f"Docs/ADR/0025-aiadra-core-runtime-scope.md §1.",
            file=sys.stderr,
        )
        return 99

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
