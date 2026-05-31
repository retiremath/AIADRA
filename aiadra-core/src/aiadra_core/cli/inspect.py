"""`aiadra inspect <workspace> <object-ref>` — read-only sidecar pretty-print.

Per Phase A (arc 20260531-7): this CLI is now a thin wrapper over
`aiadra_core.protocol.inspect()`. The protocol entry point owns the
UUID-or-Number resolution + project-pin verification + sidecar load; this
module owns CLI argument parsing + stdout emission + exit-code mapping.

Exit codes preserved from Phase 1:
  0 on success
  1 on validation / profile / sidecar-load failure
  2 on object-not-found
  3 on missing or mismatched `.aiadra/schemas.yaml` project pin
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ..protocol import (
    ObjectNotFoundError,
    ProjectPinError,
    inspect as protocol_inspect,
)
from ..validation.profile import ProfileViolationError
from ..validation.schema import SchemaValidationError


def run_inspect(workspace: Path, obj_ref: str) -> int:
    try:
        view = protocol_inspect(workspace, obj_ref)
    except ProjectPinError as e:
        print(f"project pin verification failed: {e}", file=sys.stderr)
        return 3
    except ObjectNotFoundError:
        print(f"object not found: {obj_ref}", file=sys.stderr)
        return 2
    except (ProfileViolationError, SchemaValidationError) as e:
        print(f"failed to load sidecar for {obj_ref}: {e}", file=sys.stderr)
        return 1
    print(f"# {view.object_number} ({view.object_uuid})")
    print(json.dumps(view.sidecar, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def cli_main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: aiadra inspect <workspace> <object-ref>", file=sys.stderr)
        return 2
    workspace = Path(argv[0]).resolve()
    if not workspace.exists():
        print(f"workspace does not exist: {workspace}", file=sys.stderr)
        return 2
    return run_inspect(workspace, argv[1])
