#!/usr/bin/env python
"""AIADRA Studio engine bridge — Studio-owned stdio JSON-RPC over Tier-1
`aiadra_core.protocol` (ADR/0032 D6; arc 20260602-6).

Transport: newline-delimited JSON (NDJSON), one frame per line, on stdio.
**stdout is SACRED** — only JSON response frames are written there. All logs,
tracebacks, and diagnostics go to **stderr** (Codex1 N3). On startup the bridge
emits a `ready` notification (the handshake that proves it is up).

Security (Codex1 B2): the renderer NEVER reaches this process directly. Electron
main spawns it and brokers capability-checked requests — main resolves an opaque
`workspaceId` to a canonical path before calling `inspect`, so this bridge only
ever receives a path that main has already validated. Methods are an explicit
allowlist; faithful to Ring 2 (Codex1 N4); responses are JSON-serializable DTOs.
"""
from __future__ import annotations

import dataclasses
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable


DEBUG = bool(os.environ.get("AIADRA_BRIDGE_DEBUG"))


def _log(*args: Any) -> None:
    print("[bridge]", *args, file=sys.stderr, flush=True)


def _send(frame: dict[str, Any]) -> None:
    # default=str coerces Path / non-JSON-native values rather than leaking
    # Python reprs or crashing (Codex1 N4).
    sys.stdout.write(json.dumps(frame, default=str) + "\n")
    sys.stdout.flush()


def _to_jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    return value


# ---- Allowlisted methods (Ring 2 faithful) ----

def m_ping(_params: dict[str, Any]) -> dict[str, Any]:
    return {"pong": True}


def m_core_version(_params: dict[str, Any]) -> dict[str, Any]:
    import aiadra_core

    return {"version": getattr(aiadra_core, "__version__", "unknown")}


def m_inspect(params: dict[str, Any]) -> dict[str, Any]:
    """Inspect an Object in a workspace. `workspace_path` is supplied by main
    (already resolved from a capability + validated — Codex1 B2); `object_ref`
    is a Number or UUID per Ring 2."""
    from aiadra_core.protocol import inspect

    workspace_path = params.get("workspace_path")
    object_ref = params.get("object_ref")
    if not workspace_path or not object_ref:
        raise ValueError("inspect requires 'workspace_path' and 'object_ref'")
    view = inspect(Path(workspace_path), object_ref)
    return {"object": _to_jsonable(view)}


def m_list_parts(params: dict[str, Any]) -> dict[str, Any]:
    """List Part Objects in a workspace (arc 20260610-1 Codex1 B1). Delegates to
    Tier-1 `protocol.query(kind="Part")` — read-only, deterministically ordered
    by object_number. Returns identity fields ONLY (number / name / uuid); no
    sidecar bodies, no paths. Gives Studio an object-ref source after
    `Open Workspace` without hard-coding fixture-shaped numbers."""
    from aiadra_core.protocol import query

    workspace_path = params.get("workspace_path")
    if not workspace_path:
        raise ValueError("list_parts requires 'workspace_path'")
    views = query(Path(workspace_path), kind="Part")
    return {
        "parts": [
            {
                "object_number": v.object_number,
                "name": v.sidecar.get("object", {}).get("name", ""),
                "object_uuid": v.object_uuid,
            }
            for v in views
        ]
    }


def m_display_representation(params: dict[str, Any]) -> dict[str, Any]:
    """Engine-produced Display Representation for a canonical Object (ADR/0035;
    arc 20260609-1). Read-only Ring-2 primitive — writes nothing. `workspace_path`
    is supplied by main (resolved + validated, Codex1 B2); `object_ref` is a
    Number or UUID; `tolerance` is optional."""
    from aiadra_core.protocol import display_representation

    workspace_path = params.get("workspace_path")
    object_ref = params.get("object_ref")
    if not workspace_path or not object_ref:
        raise ValueError("display_representation requires 'workspace_path' and 'object_ref'")
    tolerance = params.get("tolerance")
    dr = display_representation(Path(workspace_path), object_ref, tolerance=tolerance)
    return {"display": dr.to_dict()}


def m_display_hlr(params: dict[str, Any]) -> dict[str, Any]:
    """View-dependent HLR overlay for a canonical Object (Display contract
    v1.1; arc 20260609-2). Read-only Ring-2 primitive — computed on camera
    settle, never per-frame; ships ONLY the classified hidden-line payload.
    Studio must attach it to a held display package only when `identity_echo`
    matches in full (Codex1 B3). `workspace_path` is supplied by main
    (resolved + validated, Codex1 B2)."""
    from aiadra_core.protocol import display_hlr

    workspace_path = params.get("workspace_path")
    object_ref = params.get("object_ref")
    views = params.get("views")
    if not workspace_path or not object_ref:
        raise ValueError("display_hlr requires 'workspace_path' and 'object_ref'")
    if not isinstance(views, list) or not views:
        raise ValueError("display_hlr requires a non-empty 'views' list")
    kwargs: dict[str, Any] = {
        "views": views,
        "algorithm": params.get("algorithm", "exact"),
    }
    if params.get("tolerance") is not None:
        kwargs["tolerance"] = params["tolerance"]
    if params.get("correlation_min_length_mm") is not None:
        kwargs["correlation_min_length_mm"] = params["correlation_min_length_mm"]
    payload = display_hlr(Path(workspace_path), object_ref, **kwargs)
    return {"view_dependent": payload.to_dict()}


METHODS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "ping": m_ping,
    "core_version": m_core_version,
    "inspect": m_inspect,
    "list_parts": m_list_parts,
    "display_representation": m_display_representation,
    "display_hlr": m_display_hlr,
}


def main() -> None:
    _send({"jsonrpc": "2.0", "method": "ready", "params": {"pid": os.getpid()}})
    _log("ready (pid", os.getpid(), ")")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            _send({"id": None, "error": {"code": -32700, "message": f"parse error: {exc}"}})
            continue
        request_id = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}
        if DEBUG:
            _log("recv", repr(method), "id", request_id)
        handler = METHODS.get(method)
        if handler is None:
            _send({"id": request_id, "error": {"code": -32601, "message": f"method not allowed: {method!r}"}})
            continue
        try:
            result = handler(params)
            _send({"id": request_id, "result": result})
        except Exception as exc:  # noqa: BLE001 — report all failures as JSON-RPC errors
            _log("error in", method, ":", repr(exc))
            _send({"id": request_id, "error": {"code": -32000, "message": f"{type(exc).__name__}: {exc}"}})


if __name__ == "__main__":
    main()
