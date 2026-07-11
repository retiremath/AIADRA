#!/usr/bin/env python
"""Authoring write-lane smoke (arc 20260711-11 slice 1).

Drives the bridge's authoring session methods directly — the SAME handlers
Electron main brokers — to prove real geometry is created + committed through the
Ring-2 write lane: begin (create_part) -> add (sketch rectangle) -> add (extrude)
-> simulate -> commit -> the committed Part's display shows a 6-face box.

Run from the aiadra-core venv:
    ..\\aiadra-core\\.venv\\Scripts\\python.exe scripts\\authoring-smoke.py
"""
from __future__ import annotations

import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bridge"))
import bridge  # noqa: E402
from aiadra_core.protocol import propose, refresh_native_engines  # noqa: E402


def main() -> int:
    refresh_native_engines()
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        ws.mkdir()
        # An opened Studio workspace is already init'd; the smoke inits its temp ws.
        propose(ws, kind="init", params={}).commit()

        sid = uuid.uuid4().hex
        wsp = str(ws)

        bridge.m_authoring_begin({
            "session_id": sid, "workspace_path": wsp, "kind": "create_part",
            "op_params": {"number": "P-000001", "name": "SmokePart"},
        })
        bridge.m_authoring_add({
            "session_id": sid, "kind": "mechanical.add_sketch_feature",
            "op_params": {"part_number": "P-000001", "primitives": [
                {"type": "rectangle", "x_mm": 0.0, "y_mm": 0.0, "width_mm": 82.0, "height_mm": 52.0},
            ]},
        })
        bridge.m_authoring_add({
            "session_id": sid, "kind": "mechanical.add_extrude_feature",
            "op_params": {"part_number": "P-000001", "sketch_feature_id": "feat_0001",
                          "depth_mm": 6.0, "direction": "z+"},
        })

        sim = bridge.m_authoring_simulate({"session_id": sid})
        if not sim["report"].get("valid"):
            print(f"SIMULATE NOT VALID: {sim['report']}", file=sys.stderr)
            return 1

        res = bridge.m_authoring_commit({
            "session_id": sid, "workspace_path": wsp, "object_ref": "P-000001",
        })
        faces = res["display"]["counters"]["face_count"]
        print(f"committed P-000001 via the authoring session; face_count={faces}")
        if faces != 6:
            print(f"expected a 6-face box (extruded rectangle), got {faces}", file=sys.stderr)
            return 1

        # Lifecycle (Codex2 B1): discard/rollback closes the session — a later
        # verb on that id must fail loudly, never silently touch a live draft.
        sid2 = uuid.uuid4().hex
        bridge.m_authoring_begin({
            "session_id": sid2, "workspace_path": wsp, "kind": "create_part",
            "op_params": {"number": "P-000002", "name": "Discarded"},
        })
        bridge.m_authoring_rollback({"session_id": sid2})
        try:
            bridge.m_authoring_simulate({"session_id": sid2})
            print("LIFECYCLE FAIL: simulate after discard should have raised", file=sys.stderr)
            return 1
        except ValueError:
            pass
        print("discard OK — the session is gone after rollback")

        print("AUTHORING SMOKE OK — real extrude created + committed through the write bridge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
