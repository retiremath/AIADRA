"""EP0 (arc 20260714-2; ADR/0035 A4) — the empty→first-feature identity
transition, proven end-to-end through the PUBLIC Ring-2 display APIs against
the real engine (Codex2 build bar 5): the empty state first, then the first
committed sketch flips `geometry_ref`, `topology_signature`, and `cache_key`,
and the old (empty) selection is invalid under the standard signature gate.
"""
from __future__ import annotations

from pathlib import Path

from aiadra_core.protocol import display_hlr, display_representation, propose
from aiadra_core.protocol.empty_display import EMPTY_GEOMETRY_REF

from conftest import two_primitives  # type: ignore


def test_empty_part_displays_then_first_sketch_flips_the_identity(
    workspace_with_part: Path,
):
    ws = workspace_with_part  # P-000001 exists with ZERO features

    # 1. The empty state, through the public API — no engine dispatch occurs.
    empty = display_representation(ws, "P-000001")
    assert empty.identity.geometry_ref == EMPTY_GEOMETRY_REF
    assert empty.render.faces == ()
    assert empty.selection.pickable_kinds == ()
    empty_sig = empty.identity.topology_signature
    empty_key = empty.identity.cache_key

    hlr = display_hlr(
        ws,
        "P-000001",
        views=[{"view_id": "front", "direction": [0, 0, -1], "up": [0, 1, 0]}],
        algorithm="exact",
    )
    assert hlr.views[0].segments == ()
    assert hlr.identity_echo.geometry_ref == EMPTY_GEOMETRY_REF

    # 2. The FIRST committed feature — the sketch — replaces the empty state.
    propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001", "primitives": two_primitives()}).commit()

    full = display_representation(ws, "P-000001")
    # All three identity fields flip in one step (A4 consequence).
    assert full.identity.geometry_ref != EMPTY_GEOMETRY_REF
    assert full.identity.geometry_ref.startswith("sha256:")  # a REAL vault ref now
    assert full.identity.topology_signature != empty_sig
    assert full.identity.cache_key != empty_key
    # Real geometry present; the old empty selection is invalid under the
    # STANDARD gate (selection_invalid_when: topology_signature_changed).
    assert len(full.render.faces) > 0
    assert full.invalidation.selection_invalid_when == "topology_signature_changed"
