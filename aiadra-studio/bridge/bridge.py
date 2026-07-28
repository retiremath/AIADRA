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


def m_delete_object(params: dict[str, Any]) -> dict[str, Any]:
    """Delete a working Part (ADR/0004 SCN arc 20260728-3) — the standalone
    Ring-2 deletion Transaction: object_deleted event + terminal Reservation
    tombstone + working-sidecar removal in ONE Git commit.

    A referential-integrity refusal is NOT a transport error — it returns
    `{deleted: false, refusal: {message, blockers}}` so Studio renders the
    STRUCTURED blocker list without reinterpreting it (Codex2 contract: Studio
    renders, never reinterprets). Success returns `{deleted: true, commit}`.
    """
    from aiadra_core.protocol import DeletionBlockedError, commit, propose

    workspace_path = params.get("workspace_path")
    object_number = params.get("object_number")
    reason = params.get("reason")
    if not workspace_path or not object_number or not reason:
        raise ValueError("delete_object requires 'workspace_path', 'object_number', 'reason'")
    try:
        draft = propose(
            Path(workspace_path), kind="delete_object",
            params={"obj_number": object_number, "reason": reason},
            actor="human",  # Studio's RMB delete is operator-driven
        )
    except DeletionBlockedError as exc:
        return {
            "deleted": False,
            "refusal": {"message": str(exc), "blockers": exc.blockers},
        }
    # The AIADRAWork poisoning lesson (2026-07-28): `protocol.commit` does
    # NOT self-validate — the CLI validates explicitly before committing and
    # this lane MUST too, or an invalid artifact reaches the immutable log.
    draft.validate()
    result = commit(draft)
    return {"deleted": True, "commit": _to_jsonable(result)}


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


# ---- Authoring session — the Ring-2 write lane (arc 20260711-11 slice 1) ----
# A `TransactionDraft` is a stateful Python object that cannot cross the wire, so
# it lives HERE, keyed by an opaque `session_id` that Electron main mints and
# tracks as a capability (Codex B1). The renderer never touches this process;
# main brokers capability-checked verbs (begin/add/simulate/commit/rollback) and
# has already validated the `workspace_path`, the allowlisted feature `kind`, and
# the params before calling. `actor="human"` — these are user/AI authoring ops
# through the Studio, committed only on an explicit commit.
_DRAFTS: dict[str, Any] = {}


def _report_to_dict(report: Any) -> dict[str, Any]:
    d = _to_jsonable(report)
    if not isinstance(d, dict):
        d = {"report": str(report)}
    # Arc 20260715-1 P2 (a REAL pre-existing bug): core ValidationOutcome
    # carries `result` ("PASS"|"FAIL"), not `status` — the old filter matched
    # nothing, so simulate always reported valid=True through the bridge.
    # Prefer the report's own failures_count; fall back to the result filter.
    outcomes = d.get("outcomes") or []
    failed = [
        o for o in outcomes
        if isinstance(o, dict)
        and str(o.get("result", o.get("status", ""))).upper() == "FAIL"
    ]
    fc = d.get("failures_count")
    d["valid"] = (int(fc) == 0) if isinstance(fc, int) else len(failed) == 0
    return d


def _created_feature_ids(draft: Any, events_before: int) -> list[str]:
    """The ENGINE-minted feature ids this op staged (arc 20260714-3 Codex1 B1)
    — read from the draft's OWN emitted events (the per-op delta, Codex2 bar):
    every mutation handler emits `part_changed` with `feature_delta.added[]`
    carrying the records it minted. The identity authority is the engine's
    emitted record, never a recount."""
    ids: list[str] = []
    for ev in draft.events[events_before:]:
        payload = ev.get("payload") or {}
        for added in (payload.get("feature_delta") or {}).get("added", []):
            fid = added.get("id")
            if isinstance(fid, str):
                ids.append(fid)
    return ids


def m_authoring_begin(params: dict[str, Any]) -> dict[str, Any]:
    """Open an authoring draft for a feature op (Ring-2 `propose`). `session_id`
    + `workspace_path` are main-minted/resolved; `kind` is a main-allowlisted
    feature kind; `op_params` are main-validated. The response carries this
    op's ENGINE-minted `created_feature_ids` so a chained op can reference them
    without predicting ids (Codex1 B1)."""
    from aiadra_core.protocol import propose

    session_id = params["session_id"]
    if session_id in _DRAFTS:
        raise ValueError(f"authoring session already open: {session_id}")
    draft = propose(
        Path(params["workspace_path"]), kind=params["kind"], params=params.get("op_params", {}), actor="human"
    )
    _DRAFTS[session_id] = draft
    return {
        "session_id": session_id,
        "op_count": 1,
        "created_feature_ids": _created_feature_ids(draft, 0),
    }


def m_authoring_add(params: dict[str, Any]) -> dict[str, Any]:
    """Extend the open draft with another op (Ring-2 `modify`) — e.g. add an
    extrude after a sketch within one authoring session. The response carries
    THIS op's engine-minted `created_feature_ids` (the per-op event delta)."""
    from aiadra_core.protocol import modify

    session_id = params["session_id"]
    draft = _DRAFTS.get(session_id)
    if draft is None:
        raise ValueError(f"no open authoring session: {session_id}")
    events_before = len(draft.events)
    modify(draft, kind=params["kind"], params=params.get("op_params", {}), actor="human")
    return {
        "session_id": session_id,
        "created_feature_ids": _created_feature_ids(draft, events_before),
    }


def m_authoring_simulate(params: dict[str, Any]) -> dict[str, Any]:
    """Validate the draft without writing (Ring-2 `simulate`) — the transient
    check before commit. Returns the ValidationReport + a `valid` flag."""
    from aiadra_core.protocol import simulate

    session_id = params["session_id"]
    draft = _DRAFTS.get(session_id)
    if draft is None:
        raise ValueError(f"no open authoring session: {session_id}")
    return {"session_id": session_id, "report": _report_to_dict(simulate(draft))}


def m_authoring_commit(params: dict[str, Any]) -> dict[str, Any]:
    """Commit the draft to Product Truth (Ring-2 `commit`) and return the
    refreshed display of the committed object so the renderer knows exactly what
    to show (Codex B1 — commit returns refreshed identity).

    Lifecycle (Codex2 B1): the draft is kept in `_DRAFTS` until commit + display
    reload SUCCEED. If any step raises, the draft stays open so the user can fix
    params, re-simulate, retry, or cancel — a failed commit never orphans the
    draft into invisible state. The session closes ONLY on success."""
    from aiadra_core.protocol import commit, display_representation

    session_id = params["session_id"]
    draft = _DRAFTS.get(session_id)  # do NOT pop yet — only on success (Codex2 B1)
    if draft is None:
        raise ValueError(f"no open authoring session: {session_id}")
    result = commit(draft)
    out: dict[str, Any] = {"session_id": session_id, "commit": _to_jsonable(result)}
    object_ref = params.get("object_ref")
    if object_ref:
        out["object_ref"] = object_ref
        out["display"] = display_representation(Path(params["workspace_path"]), object_ref).to_dict()
    _DRAFTS.pop(session_id, None)  # commit + display reload succeeded — close now
    return out


def m_authoring_rollback(params: dict[str, Any]) -> dict[str, Any]:
    """DISCARD an uncommitted authoring draft (cancel) — Codex2 B1.

    Named explicitly as a *discard*, NOT a Ring-2 failed-Transaction rollback:
    nothing was staged to disk, so dropping the in-memory draft IS the cancel,
    and no failed-Transaction audit record is warranted for a draft the user
    never committed. Infallible + idempotent; closes the session."""
    session_id = params["session_id"]
    _DRAFTS.pop(session_id, None)
    return {"session_id": session_id, "rolled_back": True}


METHODS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "ping": m_ping,
    "core_version": m_core_version,
    "inspect": m_inspect,
    "list_parts": m_list_parts,
    "delete_object": m_delete_object,
    "display_representation": m_display_representation,
    "display_hlr": m_display_hlr,
    # authoring (write) lane — arc 20260711-11 slice 1
    "authoring_begin": m_authoring_begin,
    "authoring_add": m_authoring_add,
    "authoring_simulate": m_authoring_simulate,
    "authoring_commit": m_authoring_commit,
    "authoring_rollback": m_authoring_rollback,
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
