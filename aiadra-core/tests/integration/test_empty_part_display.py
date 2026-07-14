"""EP0 — the EMPTY-Part display state (arc 20260714-2; ADR/0035 Amendment A4).

Proves, THROUGH THE PUBLIC Ring-2 APIs (per Codex1 B1 — an engine-local
generator test would bypass the blocker), that a committed zero-feature Part:
- yields a valid empty Display Representation with the reserved A4 identity;
- yields empty HLR for the requested views under the standard identity echo;
- keeps machine-readable invalidation predicates;
and that the mixed features-without-geometry state fails LOUD as inconsistent
(never masquerading as empty). The first-feature identity transition is proven
end-to-end in aiadra-mechanical (the engine is required to commit a sketch).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from aiadra_core.protocol import display_hlr, display_representation, propose
from aiadra_core.protocol.display import DISPLAY_REPRESENTATION_VERSION
from aiadra_core.protocol.empty_display import (
    EMPTY_GEOMETRY_REF,
    build_empty_display,
    empty_cache_key,
    empty_topology_signature,
    is_empty_part,
    require_consistent_for_display,
)
from aiadra_core.transaction.boundary import TransactionError


def _init_workspace(tmp_path: Path, name: str = "ws") -> Path:
    workspace = tmp_path / name
    propose(workspace, kind="init", params={}).commit()
    return workspace


def _create_empty_part(workspace: Path, number: str = "P-000001") -> None:
    propose(
        workspace, kind="create_part", params={"number": number, "name": "Empty part"}
    ).commit()


# ---------------------------------------------------------------------------
# 1. The public empty display (Ring-2 display_representation)
# ---------------------------------------------------------------------------


def test_zero_feature_part_displays_empty_with_the_a4_identity(tmp_path):
    ws = _init_workspace(tmp_path)
    _create_empty_part(ws)
    dr = display_representation(ws, "P-000001")

    assert dr.display_representation_version == DISPLAY_REPRESENTATION_VERSION
    assert dr.identity.geometry_ref == EMPTY_GEOMETRY_REF  # reserved, never a vault ref
    assert dr.identity.topology_signature == "topo_4f53cda18c2baa0c"  # sha256(b"[]")[:16]
    assert dr.identity.cache_key == empty_cache_key(dr.identity.object_uuid)
    assert dr.identity.object_number == "P-000001"

    assert dr.render.faces == ()
    assert dr.render.edges == ()
    assert dr.render.vertices == ()
    assert dr.counters.face_count == 0
    assert dr.counters.triangle_count == 0
    assert dr.selection.pickable_kinds == ()  # nothing pickable when empty
    assert dr.view_dependent is None
    # Machine-readable invalidation — identical to the engine's predicates.
    assert dr.invalidation.stale_when == ("geometry_ref_changed", "cache_key_changed")
    assert dr.invalidation.selection_invalid_when == "topology_signature_changed"


def test_empty_signature_constant_matches_the_pinned_canonical_bytes():
    import hashlib

    assert empty_topology_signature() == "topo_" + hashlib.sha256(b"[]").hexdigest()[:16]
    # The A4.3 pin: canonical empty-skeleton bytes are json.dumps([], sort_keys=True).
    import json

    assert json.dumps([], sort_keys=True).encode("utf-8") == b"[]"


# ---------------------------------------------------------------------------
# 2. The public empty HLR (Ring-2 display_hlr)
# ---------------------------------------------------------------------------


def test_zero_feature_part_hlr_returns_requested_views_with_zero_segments(tmp_path):
    ws = _init_workspace(tmp_path)
    _create_empty_part(ws)
    payload = display_hlr(
        ws,
        "P-000001",
        views=[
            {"view_id": "front", "direction": [0, 0, -1], "up": [0, 1, 0]},
            {"view_id": "iso", "direction": [-1, -1, -1], "up": [0, 0, 1]},
        ],
        algorithm="exact",
    )
    assert [v.view_id for v in payload.views] == ["front", "iso"]
    for v in payload.views:
        assert v.segments == ()
        assert v.counters.visible_segments == 0
        assert v.counters.hidden_segments == 0
        assert v.algorithm == "exact"
    # The standard identity echo — Studio's attach gate works unchanged.
    echo = payload.identity_echo
    assert echo.geometry_ref == EMPTY_GEOMETRY_REF
    assert echo.topology_signature == empty_topology_signature()
    assert echo.display_representation_version == DISPLAY_REPRESENTATION_VERSION


def test_empty_hlr_still_validates_view_specs(tmp_path):
    ws = _init_workspace(tmp_path)
    _create_empty_part(ws)
    with pytest.raises(TransactionError):
        display_hlr(ws, "P-000001", views=[], algorithm="exact")
    with pytest.raises(TransactionError):
        display_hlr(
            ws,
            "P-000001",
            views=[{"view_id": "bad", "direction": [0, 0, -1], "up": [0, 0, 1]}],
            algorithm="exact",
        )  # up parallel to direction
    with pytest.raises(TransactionError):
        display_hlr(
            ws,
            "P-000001",
            views=[{"view_id": "v", "direction": [0, 0, -1], "up": [0, 1, 0]}],
            algorithm="wrong",
        )


# ---------------------------------------------------------------------------
# 3. The EXACT empty state — mixed states fail loud (Codex2 build bar 3)
# ---------------------------------------------------------------------------


def test_features_without_geometry_is_inconsistent_never_empty():
    sidecar = {"object": {"type": "Part"}, "feature": [{"id": "feat_0001"}], "geometry_ref": []}
    assert is_empty_part(sidecar) is False
    with pytest.raises(TransactionError, match="INCONSISTENT"):
        require_consistent_for_display(sidecar, "P-000001")


def test_geometry_without_features_is_not_empty_either():
    sidecar = {
        "object": {"type": "Part"},
        "feature": [],
        "geometry_ref": [{"role": "authoring_geometry", "derived_from_feature_ids": []}],
    }
    # Not empty (the branch must not swallow it) — it flows to engine
    # resolution, which fails loud on the missing engine discriminator.
    assert is_empty_part(sidecar) is False
    require_consistent_for_display(sidecar, "P-000001")  # no masquerade error here


def test_truly_empty_part_sidecar_is_empty():
    part = {"object": {"type": "Part"}, "feature": [], "geometry_ref": []}
    assert is_empty_part(part) is True


def test_the_empty_state_is_part_only_codex3_b1():
    # A4's iff-domain: a featureless NON-Part is NOT CAD emptiness.
    req = {"object": {"type": "Requirement"}, "feature": [], "geometry_ref": []}
    assert is_empty_part(req) is False
    require_consistent_for_display(req, "REQ-000001")  # non-Part: no mixed-state claim
    assert is_empty_part({}) is False  # no object type → never empty:v1


def test_featureless_requirement_never_returns_empty_v1_via_public_apis(tmp_path):
    """Codex3 B1 public regression: a valid committed Requirement keeps the
    normal fail-loud no-display path on BOTH public APIs."""
    from aiadra_core.protocol import ObjectNotFoundError

    ws = _init_workspace(tmp_path)
    propose(ws, kind="create_requirement", params={
        "number": "REQ-000001", "name": "Bracket strength",
        "extra_namespaces": {
            "requirement": {
                "statement": {"text": "shall hold", "language": "en", "format": "freeform"},
                "category": "functional",
            },
        },
    }).commit()
    with pytest.raises(ObjectNotFoundError, match="no authoring_geometry"):
        display_representation(ws, "REQ-000001")
    with pytest.raises(ObjectNotFoundError, match="no authoring_geometry"):
        display_hlr(
            ws, "REQ-000001",
            views=[{"view_id": "front", "direction": [0, 0, -1], "up": [0, 1, 0]}],
            algorithm="exact",
        )


# ---------------------------------------------------------------------------
# 4. The empty payload passes the standard contract gate
# ---------------------------------------------------------------------------


def test_empty_payload_is_contract_valid_via_the_standard_gate():
    from aiadra_core.protocol.display import DisplayRepresentation

    dr = DisplayRepresentation.from_engine_dict(build_empty_display("uuid-1", "P-000009"))
    assert dr.identity.geometry_ref == EMPTY_GEOMETRY_REF
    assert dr.counters.vertex_count == 0
