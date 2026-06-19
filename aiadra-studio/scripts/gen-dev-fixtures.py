#!/usr/bin/env python
"""Generate the browser-dev display fixtures (arc 20260610-1, Claude1 P7).

Builds the ADR/0036-style box-with-hole part in a throwaway workspace via the
REAL Tier-1 lane, then dumps the engine's
actual `DisplayRepresentation` and per-view `ViewDependentPayload` JSON into
`aiadra-studio/dev-fixtures/`. Because the payloads come from the same
`display_representation` / `display_hlr` primitives the bridge calls, fixture
shape parity with the wire format is by construction, not by hand-maintenance.

Dev tooling only — never shipped, never Product Truth. The renderer loads these
ONLY in browser dev (`import.meta.env.DEV && !window.aiadra`) and version-gates
them (a stale fixture fails loudly, it never renders silently).

Run from the aiadra-core venv (both packages installed editable):
    ..\\aiadra-core\\.venv\\Scripts\\python.exe scripts\\gen-dev-fixtures.py

Views are the proven spike set (front / iso / tilt — `tests/test_hlr.py` in
aiadra-mechanical): front shows the hole as hidden outlines; tilt splits one
edge_id visible+hidden.
"""
from __future__ import annotations

import json
import math
import sys
import tempfile
from pathlib import Path

from aiadra_core.protocol import (
    display_hlr,
    display_representation,
    native_engine_status,
    propose,
    refresh_native_engines,
)

_S3 = 1.0 / math.sqrt(3.0)
_TN = 1.0 / math.sqrt(0.2 * 0.2 + 1.0)

VIEWS = [
    {"view_id": "front", "direction": [0.0, 1.0, 0.0], "up": [0.0, 0.0, 1.0]},
    {"view_id": "iso", "direction": [-_S3, -_S3, -_S3], "up": [0.0, 0.0, 1.0]},
    {"view_id": "tilt", "direction": [0.2 * _TN, 0.0, -1.0 * _TN], "up": [0.0, 1.0, 0.0]},
]

OUT_DIR = Path(__file__).resolve().parent.parent / "dev-fixtures"


def build_part(ws: Path) -> None:
    # Deliberately NOT grid-quantized: a 5 mm-multiple box on the viewport's
    # 5 mm grid projects its rim edges EXACTLY onto grid lines under standard
    # views — every edge camouflages and the demo looks broken (found via the
    # arc 20260610-1 screenshot pass). Off-multiple dimensions keep every edge
    # visually separable from the grid.
    propose(ws, kind="init", params={}).commit()
    propose(ws, kind="create_part", params={"number": "P-000001", "name": "DevFixture"}).commit()
    propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001",
        "primitives": [
            {"type": "rectangle", "x_mm": 0.0, "y_mm": 0.0, "width_mm": 23.0, "height_mm": 11.0},
            {"type": "circle", "cx_mm": 6.0, "cy_mm": 4.5, "radius_mm": 2.2},
        ],
    }).commit()
    propose(ws, kind="mechanical.add_extrude_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001",
        "depth_mm": 6.0, "direction": "z+",
    }).commit()


def main() -> int:
    refresh_native_engines()
    status = native_engine_status()
    if "mechanical" not in status or status["mechanical"]["status"] != "loaded":
        print(f"mechanical Native Engine not loaded: {status}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        ws.mkdir()
        build_part(ws)

        OUT_DIR.mkdir(exist_ok=True)
        dr = display_representation(ws, "P-000001")
        (OUT_DIR / "display.json").write_text(
            json.dumps(dr.to_dict(), indent=1), encoding="utf-8"
        )
        print(f"wrote display.json (version {dr.to_dict()['display_representation_version']})")

        for view in VIEWS:
            payload = display_hlr(ws, "P-000001", views=[view], algorithm="exact")
            name = f"hlr-{view['view_id']}.json"
            (OUT_DIR / name).write_text(
                json.dumps(payload.to_dict(), indent=1), encoding="utf-8"
            )
            d = payload.to_dict()
            counters = d["views"][0]["counters"]
            print(f"wrote {name} (visible={counters['visible_segments']} "
                  f"hidden={counters['hidden_segments']} outline={counters['outline_segments']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
