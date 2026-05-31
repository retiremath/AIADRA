"""`aiadra inspect <workspace> <object-number>` — read-only sidecar pretty-print.

Resolves the Object's Number (e.g. `P-000058`) to its UUID via the appropriate
Reservation file, loads the working sidecar, validates it, and pretty-prints
the resulting state.

Per Codex2 B1 absorption arc 20260531-1: verifies `.aiadra/schemas.yaml`
project pin BEFORE any artifact reads, parallel to `aiadra validate`. ADR/0003
§9 digest-before-read applies to ALL reads, not only `validate`.

Exit codes:
  0 on success
  1 on validation / profile / sidecar-load failure
  2 on object-not-found
  3 on missing or mismatched `.aiadra/schemas.yaml` project pin
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ..truth_model.reservation import list_reservation_prefixes
from ..validation.bundle_registry import (
    BundleDigestMismatchError,
    BundleNotFoundError,
    BundleRegistry,
)
from ..validation.profile import ProfileViolationError
from ..validation.schema import (
    SchemaValidationError,
    load_reservation_validated,
    load_sidecar_validated,
)


def _resolve_number_to_uuid(workspace: Path, bundle_dir: Path, obj_number: str) -> str | None:
    """Walk Reservations for the prefix to find object_uuid for obj_number."""
    if "-" not in obj_number:
        return None
    prefix = obj_number.split("-", 1)[0]
    if prefix not in list_reservation_prefixes(workspace):
        return None
    reservation = load_reservation_validated(workspace, prefix, bundle_dir)
    entries = reservation.get("reservations", {})
    entry = entries.get(obj_number)
    if entry is None:
        return None
    return entry.get("object_uuid")


def run_inspect(workspace: Path, obj_number: str) -> int:
    # Per Codex2 B1 (arc 20260531-1): verify project pin BEFORE any artifact read.
    # Phase 1 (arc 20260531-2): use BundleRegistry to honor project-pin bundle_version.
    registry = BundleRegistry()
    try:
        bundle = registry.bundle_for_pin(workspace)
        bundle_dir = bundle.bundle_dir
    except (FileNotFoundError, BundleDigestMismatchError, BundleNotFoundError) as e:
        print(f"project pin verification failed: {e}", file=sys.stderr)
        return 3

    try:
        uuid = _resolve_number_to_uuid(workspace, bundle_dir, obj_number)
    except (ProfileViolationError, SchemaValidationError) as e:
        print(f"failed to resolve {obj_number}: {e}", file=sys.stderr)
        return 1
    if uuid is None:
        print(f"object not found: {obj_number}", file=sys.stderr)
        return 2
    try:
        sidecar = load_sidecar_validated(workspace, uuid, bundle_dir)
    except (ProfileViolationError, SchemaValidationError) as e:
        print(f"failed to load sidecar for {obj_number} ({uuid}): {e}", file=sys.stderr)
        return 1
    print(f"# {obj_number} ({uuid})")
    print(json.dumps(sidecar, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def cli_main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: aiadra inspect <workspace> <object-number>", file=sys.stderr)
        return 2
    workspace = Path(argv[0]).resolve()
    if not workspace.exists():
        print(f"workspace does not exist: {workspace}", file=sys.stderr)
        return 2
    return run_inspect(workspace, argv[1])
