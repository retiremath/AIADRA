"""Shared fixtures for the aiadra-mechanical v0.0.1 test suite.

Install precondition (ADR/0031 D11): aiadra-core + aiadra-mechanical must be
installed (editable) in the venv. Discovery is refreshed per test; tests skip
loudly if the `mechanical` engine is not loaded.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from aiadra_core.protocol import native_engine_status, propose, refresh_native_engines
from aiadra_core.truth_model.reservation import find_reservation_entry_by_number
from aiadra_core.truth_model.sidecar import load_sidecar

from aiadra_mechanical import cache


@pytest.fixture(autouse=True)
def _ensure_mechanical_loaded():
    refresh_native_engines()
    status = native_engine_status()
    if "mechanical" not in status or status["mechanical"]["status"] != "loaded":
        pytest.skip(
            f"mechanical Native Engine not loaded: {status}. "
            f"Install with: pip install -e ./aiadra-mechanical (aiadra-core must be present)."
        )
    cache.clear()  # deterministic D8 cache between tests


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    propose(ws, kind="init", params={}).commit()
    return ws


@pytest.fixture
def workspace_with_part(workspace: Path) -> Path:
    propose(workspace, kind="create_part", params={"number": "P-000001", "name": "Bracket"}).commit()
    return workspace


@pytest.fixture
def workspace_with_extrude(workspace_with_part: Path) -> Path:
    ws = workspace_with_part
    propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001", "primitives": two_primitives(),
    }).commit()
    propose(ws, kind="mechanical.add_extrude_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001",
        "depth_mm": 5.0, "direction": "z+",
    }).commit()
    return ws


def two_primitives() -> list[dict]:
    return [
        {"type": "rectangle", "x_mm": 0.0, "y_mm": 0.0, "width_mm": 20.0, "height_mm": 10.0},
        {"type": "circle", "cx_mm": 5.0, "cy_mm": 5.0, "radius_mm": 2.0},
    ]


def part_sidecar(ws: Path, number: str = "P-000001") -> dict:
    _, entry = find_reservation_entry_by_number(ws, number)
    return load_sidecar(ws, entry["object_uuid"])
