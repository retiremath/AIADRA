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

# MVP-1 (arc 20260711-10): the scripted bracket configurator's three real
# candidates. Each is a distinct evaluated recipe (a flat plate + a hole
# pattern) baked through the REAL engine so the candidate gallery previews true
# geometry (ADR/0039 P-A2; Codex2 B1) — not a re-badged single fixture. Plate is
# 82 x 52 (off the 5 mm grid — see build_part) x 6 thick; holes are Ø6.
_BRACKET_W = 82.0
_BRACKET_H = 52.0
_BRACKET_THICK = 6.0
_HOLE_R = 3.0
BRACKETS: dict[str, list[tuple[float, float]]] = {
    # keyed by candidate sourceId suffix (bracket/<key>)
    "corners": [(11.0, 11.0), (71.0, 11.0), (11.0, 41.0), (71.0, 41.0)],
    "grid": [(29.0, 19.0), (53.0, 19.0), (29.0, 33.0), (53.0, 33.0)],
    "inline": [(29.0, 26.0), (53.0, 26.0)],
}


def build_bracket(ws: Path, holes: list[tuple[float, float]]) -> None:
    """A flat plate (rectangle) with a set of circular holes, extruded."""
    propose(ws, kind="init", params={}).commit()
    propose(ws, kind="create_part", params={"number": "P-000001", "name": "Bracket"}).commit()
    primitives: list[dict] = [
        {"type": "rectangle", "x_mm": 0.0, "y_mm": 0.0, "width_mm": _BRACKET_W, "height_mm": _BRACKET_H},
    ]
    for cx, cy in holes:
        primitives.append({"type": "circle", "cx_mm": cx, "cy_mm": cy, "radius_mm": _HOLE_R})
    propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001", "primitives": primitives,
    }).commit()
    propose(ws, kind="mechanical.add_extrude_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001",
        "depth_mm": _BRACKET_THICK, "direction": "z+",
    }).commit()


def _dump_part(ws: Path, prefix: str) -> None:
    """Write <prefix>.json (display) + <prefix>-hlr-<view>.json for a built part."""
    dr = display_representation(ws, "P-000001")
    (OUT_DIR / f"{prefix}.json").write_text(json.dumps(dr.to_dict(), indent=1), encoding="utf-8")
    for view in VIEWS:
        payload = display_hlr(ws, "P-000001", views=[view], algorithm="exact")
        (OUT_DIR / f"{prefix}-hlr-{view['view_id']}.json").write_text(
            json.dumps(payload.to_dict(), indent=1), encoding="utf-8"
        )
    print(f"wrote {prefix} (display + {len(VIEWS)} hlr)")


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

    # MVP-1 bracket candidates — each a fresh workspace + a distinct hole pattern.
    for key, holes in BRACKETS.items():
        with tempfile.TemporaryDirectory() as btmp:
            bws = Path(btmp) / "ws"
            bws.mkdir()
            build_bracket(bws, holes)
            _dump_part(bws, f"bracket-{key}")

    # Slice 1b/1c (arc 20260711-11): a PLAIN extruded rectangle — a 6-face box,
    # the honest preview geometry for the extrude manual dashboard's dev:web mock
    # (the real bridge lane shows the true parametric solid). Same builder as the
    # bracket, with no holes.
    with tempfile.TemporaryDirectory() as etmp:
        ews = Path(etmp) / "ws"
        ews.mkdir()
        build_bracket(ews, [])  # rectangle only → a plain box
        _dump_part(ews, "extrude-box")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
