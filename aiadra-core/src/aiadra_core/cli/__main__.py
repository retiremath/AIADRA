"""`aiadra` CLI entry point — argparse dispatch per Phase 1.

Phase 1 wires all 15 state-changing commands + Phase 0 read-only commands.
`recover` deferred per Codex2 B7 → prints note + exits 99.
"""
from __future__ import annotations

import sys

from .. import __version__


def _reconfigure_stdout_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# Phase 1 Transaction kinds → CLI command names (15 state-changing + validate/inspect read-only)
_LINK_TYPES = [
    "satisfies", "tested_against", "verifies", "cites",
    "executes", "executed_on", "produces",
]
_CREATE_TYPES = [
    ("Part", "create-part"),
    ("Requirement", "create-requirement"),
    ("TestProcedure", "create-test-procedure"),
    ("TestExecution", "create-test-execution"),
    ("EvidenceArtifact", "create-evidence-artifact"),
]


def main(argv: list[str] | None = None) -> int:
    _reconfigure_stdout_utf8()
    argv = list(argv if argv is not None else sys.argv[1:])
    if not argv:
        _print_help()
        return 0
    if argv[0] in ("--version", "-V"):
        print(f"aiadra {__version__}")
        return 0
    if argv[0] in ("--help", "-h", "help"):
        _print_help()
        return 0

    cmd = argv[0]
    rest = argv[1:]

    # Read-only commands (Phase 0)
    if cmd == "validate":
        from . import validate as _v
        return _v.cli_main(rest)
    if cmd == "inspect":
        from . import inspect as _i
        return _i.cli_main(rest)

    # State-changing commands (Phase 1)
    from . import commands as c

    if cmd == "init":
        return c.cmd_init(rest)
    for obj_type, cli_name in _CREATE_TYPES:
        if cmd == cli_name:
            return c.cmd_create_object(obj_type, rest)
    if cmd == "change-parameter":
        return c.cmd_change_parameter(rest)
    if cmd == "add-acceptance-criterion":
        return c.cmd_add_acceptance_criterion(rest)
    for rel_type in _LINK_TYPES:
        if cmd == f"link-{rel_type.replace('_', '-')}":
            return c.cmd_link_relationship(rel_type, rest)
    if cmd == "attach-file":
        return c.cmd_attach_file(rest)
    if cmd == "release":
        return c.cmd_release(rest)
    if cmd == "delete-object":
        return c.cmd_delete_object(rest)
    if cmd == "migrate":
        return c.cmd_migrate(rest)
    # Phase D commands (arc 20260531-10)
    if cmd == "explain":
        return c.cmd_explain(rest)
    if cmd == "audit":
        return c.cmd_audit(rest)
    if cmd == "audit-prune":
        return c.cmd_audit_prune(rest)
    if cmd == "recover":
        print(
            "aiadra recover: not implemented in Phase 1 (per Codex2 B7 absorption).\n"
            "For manual recovery from a failed Transaction:\n"
            "  1. Run `git status` to see modified / untracked files.\n"
            "  2. Verify the modified files are AIADRA-managed paths only\n"
            "     (Reservations/, revisions/, Releases/, vault/, .aiadra/, events.jsonl).\n"
            "  3. Run `git restore -- <those-paths>` to revert.\n"
            "Workspace returns to last-committed AIADRA state.",
            file=sys.stderr,
        )
        return 99

    print(f"aiadra: unknown command {cmd!r}", file=sys.stderr)
    _print_help()
    return 2


def _print_help() -> None:
    print(f"""aiadra {__version__} — AIADRA Core CLI

Usage: aiadra <command> [options]

Read-only:
  validate <workspace>                        Validate workspace state
  inspect <workspace> <object-number>         Print Object's working sidecar

State-changing (Phase 1):
  init <workspace>                            Initialize new workspace
  create-part <workspace> <number> <name>     Create Part Object
  create-requirement <workspace> <number> <name>
  create-test-procedure <workspace> <number> <name>
  create-test-execution <workspace> <number> <name>
  create-evidence-artifact <workspace> <number> <name>
  change-parameter <workspace> <obj-num> <param-id> <new-value> <rationale>
  add-acceptance-criterion <workspace> <req-num> <criterion-id> <text>
                           [--language en] [--format freeform|ears]
                           [--threshold-parameter-ref <uuid>:parameter:<id>]
                           [--threshold-op {{>=,<=,==,!=,>,<}}]
                           [--threshold-value <number>]
                           [--threshold-unit <string>]
  link-satisfies <workspace> <part> <req>
  link-tested-against <workspace> <part> <test-proc>
  link-verifies <workspace> <test-proc> <req>
  link-cites <workspace> <req> <evidence>
  link-executes <workspace> <test-exec> <test-proc>
  link-executed-on <workspace> <test-exec> <part>
  link-produces <workspace> <test-exec> <evidence>
  attach-file <workspace> <obj-num> <file-path> --role <role>
  delete-object <workspace> <obj-num> --reason <text>
  release <workspace> --objects <num1,num2,...> [--stage N] [--no-final]
  migrate <workspace> --to-bundle {{0.20.0|0.21.0|0.22.0|0.23.0|0.24.0|0.25.0|0.26.0|0.27.0|0.28.0|0.29.0}} [--dry-run]
  explain <workspace> <object-or-relationship-ref> [--depth N] [--json]
  audit list <workspace> [--date YYYY-MM-DD]
  audit show <workspace> <tx_NNNN> [--date YYYY-MM-DD]
  audit-prune <workspace> [--dry-run]

Misc:
  --version                                   Print version
  --help                                      Print this help
""")


if __name__ == "__main__":
    raise SystemExit(main())
