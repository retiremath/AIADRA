"""View-dependent HLR tests (arc 20260609-2; Display contract v1.1).

The spike's headline assertions: the front view produces the hole's hidden
silhouette (the thing the screen-space stopgap could never draw), a tilted
view splits a model edge into visible AND hidden segments carrying the SAME
`edge_id` (partial visibility), the correlated id set survives a parameter
edit (the across-edit invariant extended to HLR), and base display + HLR
consume the SAME topology records (Codex1 B1 — no parallel identity
derivation). Plus: exact+poly, determinism, caching, the B4 sliver policy,
and the B2 contract-complete view frame.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from aiadra_core.protocol import display_hlr, display_representation
from aiadra_core.protocol.display import ViewDependentPayload
from aiadra_core.transaction.boundary import TransactionError

from aiadra_mechanical import display, hlr, topology
from aiadra_mechanical.adapter_payload import build_sketch_payload, build_extrude_payload


# ----------------------------------------------------------------------------
# Recipe + view helpers
# ----------------------------------------------------------------------------


def _recipe(depth=10.0, with_hole=True, w=40.0, h=30.0):
    prims = [{"type": "rectangle", "x_mm": 0, "y_mm": 0, "width_mm": w, "height_mm": h}]
    if with_hole:
        prims.append({"type": "circle", "cx_mm": w / 2, "cy_mm": h / 2, "radius_mm": 5})
    return [
        {"id": "feat_0001", "feature_type": "sketch",
         "adapter_payload": build_sketch_payload(prims)},
        {"id": "feat_0002", "feature_type": "extrude",
         "parameters": [{"id": "featp_0001", "name": "depth_mm", "value": depth,
                         "datatype": "number", "unit": "mm"}],
         "adapter_payload": build_extrude_payload(
             sketch_feature_id="feat_0001", direction="z+",
             depth_parameter_id="featp_0001")},
    ]


def _topo(feats, cache_key=""):
    return topology.extract_part_topology(
        feats, object_uuid="u-1", object_number="PRT-0001",
        geometry_ref="sha256:deadbeef", cache_key=cache_key)


_S3 = 1.0 / math.sqrt(3.0)
# Camera convention: `direction` is the LOOK direction (eye → scene).
FRONT = {"view_id": "front", "direction": [0.0, 1.0, 0.0], "up": [0.0, 0.0, 1.0]}
ISO = {"view_id": "iso", "direction": [-_S3, -_S3, -_S3], "up": [0.0, 0.0, 1.0]}
# Looking down the hole axis, tilted along +x: the lateral shift across the
# 10 mm depth (~2 mm) is well under the hole diameter (10 mm), so PART of the
# bottom rim is visible through the opening and the rest is hidden — the
# guaranteed partial-visibility case (the box itself is convex; only the hole
# concavity can split an edge).
_TN = 1.0 / math.sqrt(0.2 * 0.2 + 1.0)
TILT = {"view_id": "tilt", "direction": [0.2 * _TN, 0.0, -1.0 * _TN], "up": [0.0, 1.0, 0.0]}


def _model_ids(view, visibility=None):
    return {
        s["source"]["edge_id"] for s in view["segments"]
        if s["source"]["kind"] == "model_edge"
        and (visibility is None or s["visibility"] == visibility)
    }


# ----------------------------------------------------------------------------
# 1. Front view — the hole's hidden silhouette (the stopgap's impossibility)
# ----------------------------------------------------------------------------


def test_front_view_hole_outline_hidden():
    topo = _topo(_recipe())
    payload = hlr.generate_hlr(topo, views=[FRONT])
    (view,) = payload["views"]

    outlines = [s for s in view["segments"] if s["edge_class"] == "outline"]
    assert outlines, "the hole's silhouette must appear as outline segments"
    for s in outlines:
        assert s["source"]["kind"] == "outline"
        assert s["source"]["face_id"].endswith(":face:hole_wall")
        assert s["visibility"] == "hidden"  # the hole wall is inside the box
        assert "edge_id" not in s["source"] or s["source"]["edge_id"] is None

    assert view["counters"]["visible_segments"] > 0
    assert view["counters"]["hidden_segments"] > 0
    assert view["counters"]["discarded_tolerance_segments"] == 0  # probe: exact has no slivers


def test_front_view_depth_disambiguation():
    """Probe-surfaced trap: front/back box edges project COINCIDENT in 2D.
    The pinned policy must attribute visible segments to the near (y_min)
    edges and hidden ones to the far (y_max) counterparts."""
    topo = _topo(_recipe())
    payload = hlr.generate_hlr(topo, views=[FRONT])
    (view,) = payload["views"]
    visible = _model_ids(view, "visible")
    hidden = _model_ids(view, "hidden")
    assert any("wall_y_min" in e for e in visible)   # near face edges
    assert not any("wall_y_max" in e for e in visible)
    assert any("wall_y_max" in e for e in hidden)    # far face edges
    assert not any("wall_y_min" in e for e in hidden)


# ----------------------------------------------------------------------------
# 2. B1 — base display and HLR consume the SAME topology records
# ----------------------------------------------------------------------------


def test_b1_display_and_hlr_share_edge_records():
    topo = _topo(_recipe())
    base = display.build_display_payload(topo)
    base_ids = {e["edge_id"] for e in base["render"]["edges"]}
    assert base_ids == set(topo.edge_ids())  # display ids ARE the records

    payload = hlr.generate_hlr(topo, views=[FRONT, ISO])
    for view in payload["views"]:
        hlr_ids = _model_ids(view)
        assert hlr_ids  # the views see real model edges
        assert hlr_ids <= base_ids  # every HLR id comes from the same records


# ----------------------------------------------------------------------------
# 3. Partial visibility — one edge_id, both visibilities (the tilt view)
# ----------------------------------------------------------------------------


def test_partial_visibility_splits_bottom_rim():
    topo = _topo(_recipe())
    payload = hlr.generate_hlr(topo, views=[TILT])
    (view,) = payload["views"]
    split = _model_ids(view, "visible") & _model_ids(view, "hidden")
    assert split, "the tilt view must split at least one edge into visible + hidden"
    assert any("hole_wall" in e and "cap_base" in e for e in split), (
        f"expected the bottom rim among split edges, got {sorted(split)}"
    )


def test_iso_view_payload_sane():
    topo = _topo(_recipe())
    payload = hlr.generate_hlr(topo, views=[ISO])
    (view,) = payload["views"]
    assert view["counters"]["visible_segments"] > 0
    assert view["counters"]["hidden_segments"] > 0
    assert view["counters"]["outline_segments"] >= 1  # probe: 2 hidden outlines


# ----------------------------------------------------------------------------
# 4. Across-edit invariant extended to HLR (ADR/0035 D2/D3 inherited)
# ----------------------------------------------------------------------------


def test_across_edit_same_correlated_id_set():
    topo_a = _topo(_recipe(depth=10.0))
    topo_b = _topo(_recipe(depth=25.0))
    assert topo_a.topology_signature == topo_b.topology_signature  # parameter edit

    pa = hlr.generate_hlr(topo_a, views=[FRONT])
    pb = hlr.generate_hlr(topo_b, views=[FRONT])
    assert _model_ids(pa["views"][0]) == _model_ids(pb["views"][0])
    assert (pa["identity_echo"]["topology_signature"]
            == pb["identity_echo"]["topology_signature"])


# ----------------------------------------------------------------------------
# 5. Exact + poly (ADR/0033 D6 — both algorithms)
# ----------------------------------------------------------------------------


def test_poly_algorithm_produces_classified_payload():
    topo = _topo(_recipe())
    payload = hlr.generate_hlr(topo, views=[FRONT], algorithm="poly")
    (view,) = payload["views"]
    assert view["algorithm"] == "poly"
    assert view["counters"]["visible_segments"] > 0
    assert view["counters"]["hidden_segments"] > 0
    base_ids = set(topo.edge_ids())
    assert _model_ids(view) <= base_ids  # B1 holds for poly too


# ----------------------------------------------------------------------------
# 6. Determinism + caching
# ----------------------------------------------------------------------------


def _strip_timing(payload):
    p = json.loads(json.dumps(payload))
    for v in p["views"]:
        v["counters"].pop("generation_ms", None)
    return p


def test_deterministic_payload():
    a = hlr.generate_hlr(_topo(_recipe()), views=[FRONT, ISO])
    b = hlr.generate_hlr(_topo(_recipe()), views=[FRONT, ISO])
    assert json.dumps(_strip_timing(a), sort_keys=True) == json.dumps(
        _strip_timing(b), sort_keys=True)


def test_outline_indexes_deterministic_ordinals():
    payload = hlr.generate_hlr(_topo(_recipe()), views=[FRONT])
    (view,) = payload["views"]
    by_face: dict[str, list[int]] = {}
    for s in view["segments"]:
        if s["source"]["kind"] == "outline":
            by_face.setdefault(s["source"]["face_id"], []).append(s["source"]["index"])
    for face_id, indexes in by_face.items():
        assert indexes == list(range(len(indexes))), (face_id, indexes)


def test_hlr_cache_hits_on_same_view():
    hlr.clear_cache()
    topo = _topo(_recipe(), cache_key="ck-test-1")
    a = hlr.generate_hlr(topo, views=[FRONT])
    assert hlr.cache_size() == 1
    b = hlr.generate_hlr(topo, views=[FRONT])
    assert hlr.cache_size() == 1
    # generation_ms identical too — proof b came from the cache, not a recompute
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    hlr.generate_hlr(topo, views=[ISO])
    assert hlr.cache_size() == 2  # a different view is a different entry
    hlr.clear_cache()


def test_b1_cache_never_cross_contaminates_identity_echo():
    """Codex2 B1 regression: two DISTINCT objects sharing the same recipe and
    the same D8 cache material must each get their OWN identity_echo — the
    cached payload of the first must never be returned for the second."""
    hlr.clear_cache()
    feats = _recipe()
    topo_a = topology.extract_part_topology(
        feats, object_uuid="u-A", object_number="PRT-000A",
        geometry_ref="sha256:samerecipe", cache_key="ck-shared")
    topo_b = topology.extract_part_topology(
        feats, object_uuid="u-B", object_number="PRT-000B",
        geometry_ref="sha256:samerecipe", cache_key="ck-shared")
    # Identical geometry/freshness material — exactly the Codex2 B1 setup.
    assert topo_a.cache_key == topo_b.cache_key
    assert topo_a.topology_signature == topo_b.topology_signature

    pa = hlr.generate_hlr(topo_a, views=[FRONT])
    pb = hlr.generate_hlr(topo_b, views=[FRONT])
    assert pa["identity_echo"]["object_uuid"] == "u-A"
    assert pb["identity_echo"]["object_uuid"] == "u-B"          # not u-A!
    assert pb["identity_echo"]["object_number"] == "PRT-000B"
    assert hlr.cache_size() == 2  # two entries — identity is key material
    # And the cache still works per object.
    pb2 = hlr.generate_hlr(topo_b, views=[FRONT])
    assert json.dumps(pb, sort_keys=True) == json.dumps(pb2, sort_keys=True)
    assert hlr.cache_size() == 2
    hlr.clear_cache()


# ----------------------------------------------------------------------------
# 7. View-spec validation (B2 input side) + B4 sliver policy
# ----------------------------------------------------------------------------


def test_view_spec_rejections():
    topo = _topo(_recipe())
    with pytest.raises(TransactionError, match="non-empty list"):
        hlr.generate_hlr(topo, views=[])
    with pytest.raises(TransactionError, match="unit vector"):
        hlr.generate_hlr(topo, views=[{"view_id": "v", "direction": [0, 2, 0],
                                       "up": [0, 0, 1]}])
    with pytest.raises(TransactionError, match="parallel"):
        hlr.generate_hlr(topo, views=[{"view_id": "v", "direction": [0, 1, 0],
                                       "up": [0, 1, 0]}])
    with pytest.raises(TransactionError, match="algorithm"):
        hlr.generate_hlr(topo, views=[FRONT], algorithm="fast")
    with pytest.raises(TransactionError, match="view_id"):
        hlr.generate_hlr(topo, views=[{"direction": [0, 1, 0], "up": [0, 0, 1]}])
    with pytest.raises(TransactionError, match="projection"):
        hlr.generate_hlr(topo, views=[{"view_id": "v", "projection": "perspective",
                                       "direction": [0, 1, 0], "up": [0, 0, 1]}])
    with pytest.raises(TransactionError, match=">= 0"):
        hlr.generate_hlr(topo, views=[FRONT], correlation_min_length_mm=-1.0)


def test_b2_projector_echo_is_contract_complete():
    payload = hlr.generate_hlr(_topo(_recipe()), views=[FRONT])
    proj = payload["views"][0]["projector"]
    assert proj["projection"] == "orthographic"
    assert proj["units"] == "mm"
    assert proj["direction"] == [0.0, 1.0, 0.0]
    assert proj["right"] == [1.0, 0.0, 0.0]   # direction × up — pinned basis
    assert proj["up"] == [0.0, 0.0, 1.0]      # orthonormalized true up
    assert payload["views"][0]["coordinate_space"] == "view_plane_2d"


def test_b4_sliver_policy_unit():
    """The pinned discard policy, exercised directly: an UNCORRELATABLE
    non-outline segment below the threshold is dropped (None → counted by the
    caller); at/above the threshold it fails loud."""
    tiny = [(0.0, 0.0), (0.005, 0.0)]       # 0.005 mm < default 0.01
    big = [(0.0, 0.0), (5.0, 0.0)]          # 5 mm — a material segment
    assert hlr._correlate_model_edge(
        tiny, "hidden", [], 0.1, "v", 0.005, 0.01) is None
    with pytest.raises(TransactionError, match="does not correlate"):
        hlr._correlate_model_edge(big, "hidden", [], 0.1, "v", 5.0, 0.01)


# ----------------------------------------------------------------------------
# 8. End-to-end through the Ring-2 read primitive + the B3 attach check
# ----------------------------------------------------------------------------


def test_display_hlr_end_to_end_and_echo_matches_package(
        workspace_with_extrude: Path):
    payload = display_hlr(workspace_with_extrude, "P-000001",
                          views=[FRONT])
    assert isinstance(payload, ViewDependentPayload)
    (view,) = payload.views
    assert view.counters.visible_segments > 0
    assert view.counters.discarded_tolerance_segments == 0

    # B3: the standalone overlay's echo matches the held package in FULL —
    # this is exactly the Studio attach check, at the Python level.
    dr = display_representation(workspace_with_extrude, "P-000001")
    echo = payload.identity_echo
    assert echo.object_uuid == dr.identity.object_uuid
    assert echo.object_number == dr.identity.object_number
    assert echo.geometry_ref == dr.identity.geometry_ref
    assert echo.cache_key == dr.identity.cache_key
    assert echo.topology_signature == dr.identity.topology_signature
    assert echo.display_representation_version == "1.2"  # the ONE version authority (S2)

    # B1, end-to-end: every correlated id is a base-display edge id.
    base_ids = {e.edge_id for e in dr.render.edges}
    for seg in view.segments:
        if seg.source.kind == "model_edge":
            assert seg.source.edge_id in base_ids
