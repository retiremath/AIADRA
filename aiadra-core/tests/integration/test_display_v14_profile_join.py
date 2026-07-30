"""Display contract v1.4 — the mandatory profile→frame join (Codex6 B1).

The v1.4 contract says every `v2_profiles[]` entry joins its resolved frame in
`sketch_frames[]` by `sketch_feature_id`. A promise the validator does not
enforce is a promise the consumer ends up re-checking (or worse, trusting) —
so the join is refused HERE, at the contract layer, exactly like every other
producer error. Pure-dict tests: no engine, no OCCT.
"""
from __future__ import annotations

import copy

import pytest

from aiadra_core.protocol.display import DisplayContractError, DisplayRepresentation


def _frame(sid: str) -> dict:
    return {
        "sketch_feature_id": sid,
        "origin_mm": [0.0, 0.0, 0.0],
        "u_axis": [1.0, 0.0, 0.0],
        "v_axis": [0.0, 1.0, 0.0],
        "normal": [0.0, 0.0, 1.0],
    }


def _profile(sid: str) -> dict:
    return {
        "sketch_feature_id": sid,
        "points": [{"id": "skp_0006", "world": [0.0, 0.0, 0.0]},
                   {"id": "skp_0007", "world": [20.0, 0.0, 0.0]}],
        "segments": [{"id": "skp_0008", "start": "skp_0006", "end": "skp_0007"}],
        "circles": [],
        "annotations": [],
        "constraint_glyphs": [],
    }


def _package(profiles: list, frames: list) -> dict:
    return {
        "display_representation_version": "1.4",
        "identity": {
            "object_uuid": "u-1",
            "object_number": "P-000001",
            "geometry_ref": "sha256:" + "0" * 64,
            "cache_key": "ck-1",
            "topology_signature": "topo_x",
        },
        "render": {
            "faces": [], "edges": [], "vertices": [],
            "bbox_min": [0.0, 0.0, 0.0], "bbox_max": [0.0, 0.0, 0.0],
            "linear_deflection_mm": 0.1, "angular_deflection_rad": 0.3,
            "buffer_encoding": "json_arrays",
        },
        "selection": {"id_space": "canonical", "pickable_kinds": [], "names": {}},
        "sketch_frames": frames,
        "v2_construction": [],
        "v2_profiles": profiles,
        "view_dependent": None,
        "invalidation": {
            "stale_when": ["geometry_ref_changed", "cache_key_changed"],
            "selection_invalid_when": "topology_signature_changed",
        },
        "counters": {
            "face_count": 0, "edge_count_by_kind": {},
            "triangle_count": 0, "vertex_count": 0,
        },
    }


def test_a_joined_profile_validates():
    dr = DisplayRepresentation.from_engine_dict(
        _package([_profile("feat_0001")], [_frame("feat_0001")]))
    assert dr.v2_profiles[0].sketch_feature_id == "feat_0001"
    assert dr.sketch_frames[0].sketch_feature_id == "feat_0001"


def test_a_profile_without_a_frame_is_a_producer_error():
    with pytest.raises(DisplayContractError, match="no matching sketch_frames"):
        DisplayRepresentation.from_engine_dict(
            _package([_profile("feat_0001")], []))


def test_a_profile_joined_to_the_WRONG_frame_id_refuses():
    with pytest.raises(DisplayContractError, match="feat_0002.*join is mandatory"):
        DisplayRepresentation.from_engine_dict(
            _package([_profile("feat_0002")], [_frame("feat_0001")]))


def test_duplicate_frames_for_one_sketch_refuse():
    """The ambiguous side of the join — already refused by the sketch_frames
    validator's uniqueness rule; pinned here so the join stays two-sided."""
    with pytest.raises(DisplayContractError, match="duplicates"):
        DisplayRepresentation.from_engine_dict(
            _package([_profile("feat_0001")],
                     [_frame("feat_0001"), _frame("feat_0001")]))


def test_frames_without_profiles_stay_valid():
    """The reverse direction is NOT mandatory: a face-bound v1 sketch has a
    frame and no profile entry — that has been valid since v1.2."""
    dr = DisplayRepresentation.from_engine_dict(
        _package([], [_frame("feat_0001")]))
    assert dr.v2_profiles == ()


def test_multiple_profiles_each_need_their_own_frame():
    pkg = _package(
        [_profile("feat_0001"), {**copy.deepcopy(_profile("feat_0002"))}],
        [_frame("feat_0001")])
    with pytest.raises(DisplayContractError, match="feat_0002"):
        DisplayRepresentation.from_engine_dict(pkg)
