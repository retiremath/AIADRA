"""S2 (arc 20260714-3) — the NO-BASE display branch.

The stepwise paradigm makes a committed-but-unconsumed sketch a routine
committed state; its display/HLR must answer honestly (zero render payload
under the Part's REAL live identity), never crash in a solid-only correlation
vocabulary (one-wall-per-segment demands walls that do not exist yet).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from aiadra_core.protocol import display_hlr, display_representation, propose

from conftest import two_primitives  # type: ignore

FRONT_VIEW = [{
    "view_id": "front", "projection": "orthographic",
    "origin": [0, 0, 0], "direction": [0, -1, 0],
    "up": [0, 0, 1], "right": [1, 0, 0],
}]


def _sketch_only_part(ws: Path) -> None:
    propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001", "primitives": two_primitives(),
        "plane": {"kind": "principal", "orientation": "zx"}}).commit()


def test_sketch_only_display_is_zero_render_with_live_identity(workspace_with_part: Path):
    ws = workspace_with_part
    _sketch_only_part(ws)
    d = display_representation(ws, "P-000001").to_dict()
    assert len(d["render"]["faces"]) == 0
    assert len(d["render"]["edges"]) == 0
    assert d["counters"]["face_count"] == 0
    # Codex3 N1: zero topology advertises zero pick capability (literal).
    assert len(d["selection"]["pickable_kinds"]) == 0
    # The identity stays REAL (not the reserved empty:v1 — features exist).
    ident = d["identity"]
    assert ident["geometry_ref"].startswith("sha256:")
    assert ident["topology_signature"].startswith("topo_")
    assert ident["cache_key"]


def test_sketch_only_hlr_answers_every_view_with_zero_segments(workspace_with_part: Path):
    ws = workspace_with_part
    _sketch_only_part(ws)
    vd = display_hlr(ws, "P-000001", views=FRONT_VIEW).to_dict()
    assert len(vd["views"]) == 1
    view = vd["views"][0]
    assert view["view_id"] == "front"
    assert len(view["segments"]) == 0
    assert view["counters"]["visible_segments"] == 0
    assert vd["identity_echo"]["topology_signature"].startswith("topo_")


def test_sketch_only_hlr_still_validates_inputs_loudly(workspace_with_part: Path):
    ws = workspace_with_part
    _sketch_only_part(ws)
    with pytest.raises(Exception, match="non-empty list"):
        display_hlr(ws, "P-000001", views=[])


def test_extruding_the_sketch_restores_the_solid_display(workspace_with_part: Path):
    ws = workspace_with_part
    _sketch_only_part(ws)
    propose(ws, kind="mechanical.add_extrude_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001",
        "depth_mm": 5.0, "direction": "normal+"}).commit()
    d = display_representation(ws, "P-000001").to_dict()
    assert d["counters"]["face_count"] > 0  # the solid path is untouched
