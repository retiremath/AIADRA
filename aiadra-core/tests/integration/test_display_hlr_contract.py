"""Display Representation contract v1.1 — view-dependent payload validation
(arc 20260609-2). Pure-dict tests: no engine, no OCCT — the contract layer
must reject malformed producer output on its own (Manifesto P5; the viewport
never renders guesswork).

Covers the Codex1 close conditions: B2 (contract-complete view frame —
non-unit / non-orthogonal / wrong-basis / wrong-units rejections), B3 (echo
cross-check for inline payloads), B5 (strict source union — outline never
carries an edge_id, model_edge never carries face/index), Q7 (core accepts
BOTH "1.0" and "1.1"; "1.0" still rejects a populated slot), plus counter
consistency and polyline integrity.
"""
from __future__ import annotations

import copy

import pytest

from aiadra_core.protocol.display import (
    DisplayContractError,
    DisplayRepresentation,
    ViewDependentPayload,
)


# ----------------------------------------------------------------------------
# Fixtures — minimal valid payloads, mutated per test
# ----------------------------------------------------------------------------


def _echo():
    return {
        "object_uuid": "u-1",
        "object_number": "PRT-0001",
        "geometry_ref": "sha256:deadbeef",
        "display_representation_version": "1.1",
        "cache_key": "ck-1",
        "topology_signature": "topo_abc123",
    }


def _segment_model():
    return {
        "polyline_2d": [0.0, 0.0, 10.0, 0.0],
        "visibility": "visible",
        "edge_class": "sharp",
        "source": {"kind": "model_edge", "edge_id": "edge:a~b"},
    }


def _segment_outline():
    return {
        "polyline_2d": [1.0, 2.0, 3.0, 4.0],
        "visibility": "hidden",
        "edge_class": "outline",
        "source": {"kind": "outline", "face_id": "feat_0002:face:hole_wall",
                   "index": 0},
    }


def _view():
    return {
        "view_id": "front",
        "projector": {
            "projection": "orthographic",
            "origin": [0.0, 0.0, 0.0],
            "direction": [0.0, 1.0, 0.0],
            "up": [0.0, 0.0, 1.0],
            "right": [1.0, 0.0, 0.0],
            "units": "mm",
        },
        "algorithm": "exact",
        "coordinate_space": "view_plane_2d",
        "correlation_min_length_mm": 0.01,
        "segments": [_segment_model(), _segment_outline()],
        "counters": {
            "visible_segments": 1,
            "hidden_segments": 1,
            "outline_segments": 1,
            "discarded_tolerance_segments": 0,
            "generation_ms": 1.0,
        },
    }


def _payload():
    return {"identity_echo": _echo(), "views": [_view()]}


def _display(version="1.1", view_dependent=None):
    return {
        "display_representation_version": version,
        "identity": {
            "object_uuid": "u-1",
            "object_number": "PRT-0001",
            "geometry_ref": "sha256:deadbeef",
            "cache_key": "ck-1",
            "topology_signature": "topo_abc123",
        },
        "render": {
            "faces": [{"face_id": "f", "positions": [0, 0, 0, 1, 0, 0, 0, 1, 0],
                       "normals": [0, 0, 1, 0, 0, 1, 0, 0, 1],
                       "triangles": [0, 1, 2]}],
            "edges": [{"edge_id": "edge:a~b", "kind": "sharp",
                       "polyline": [0, 0, 0, 1, 0, 0], "faces": ["f"]}],
            "vertices": [{"vertex_id": "v", "position": [0, 0, 0]}],
            "bbox_min": [0, 0, 0],
            "bbox_max": [1, 1, 0],
            "linear_deflection_mm": 0.1,
            "angular_deflection_rad": 0.5,
        },
        "selection": {"id_space": "canonical", "pickable_kinds": ["face"],
                      "names": {}},
        "invalidation": {"stale_when": ["cache_key_changed"],
                         "selection_invalid_when": "topology_signature_changed"},
        "counters": {"face_count": 1, "edge_count_by_kind": {"sharp": 1},
                     "triangle_count": 1, "vertex_count": 1},
        "view_dependent": view_dependent,
    }


def _rejects_standalone(mutate, match=None):
    d = _payload()
    mutate(d)
    with pytest.raises(DisplayContractError, match=match):
        ViewDependentPayload.from_engine_dict(d)


# ----------------------------------------------------------------------------
# 1. Standalone payload — acceptance + B2 frame rejections
# ----------------------------------------------------------------------------


def test_valid_standalone_payload_parses():
    p = ViewDependentPayload.from_engine_dict(_payload())
    assert p.identity_echo.cache_key == "ck-1"
    (view,) = p.views
    assert view.projector.units == "mm"
    assert view.coordinate_space == "view_plane_2d"
    assert len(view.segments) == 2


def test_rejects_non_unit_direction():
    _rejects_standalone(
        lambda d: d["views"][0]["projector"].update(direction=[0.0, 2.0, 0.0]),
        match="unit vector")


def test_rejects_non_orthogonal_up():
    _rejects_standalone(
        lambda d: d["views"][0]["projector"].update(
            up=[0.0, 0.70710678, 0.70710678]),
        match="orthogonal|right")


def test_rejects_wrong_right_basis():
    _rejects_standalone(
        lambda d: d["views"][0]["projector"].update(right=[-1.0, 0.0, 0.0]),
        match="direction × up|direction x up|right")


def test_rejects_wrong_units():
    _rejects_standalone(
        lambda d: d["views"][0]["projector"].update(units="cm"),
        match="units")


def test_rejects_perspective_projection():
    _rejects_standalone(
        lambda d: d["views"][0]["projector"].update(projection="perspective"),
        match="projection")


def test_rejects_unknown_coordinate_space():
    _rejects_standalone(
        lambda d: d["views"][0].update(coordinate_space="model_space_3d"),
        match="coordinate_space")


def test_rejects_unknown_algorithm():
    _rejects_standalone(
        lambda d: d["views"][0].update(algorithm="fast"), match="algorithm")


def test_rejects_empty_views():
    _rejects_standalone(lambda d: d.update(views=[]), match="non-empty")


def test_rejects_echo_version_not_1_1():
    _rejects_standalone(
        lambda d: d["identity_echo"].update(
            display_representation_version="1.0"),
        match="1.1")


def test_rejects_missing_echo_field():
    def mutate(d):
        del d["identity_echo"]["cache_key"]
    _rejects_standalone(mutate)


# ----------------------------------------------------------------------------
# 2. Segment integrity + the B5 strict source union
# ----------------------------------------------------------------------------


def test_rejects_odd_polyline():
    _rejects_standalone(
        lambda d: d["views"][0]["segments"][0].update(
            polyline_2d=[0.0, 0.0, 1.0]),
        match="polyline_2d")


def test_rejects_single_point_polyline():
    _rejects_standalone(
        lambda d: d["views"][0]["segments"][0].update(polyline_2d=[0.0, 0.0]),
        match="polyline_2d")


def test_rejects_non_finite_polyline():
    _rejects_standalone(
        lambda d: d["views"][0]["segments"][0].update(
            polyline_2d=[0.0, 0.0, float("nan"), 1.0]),
        match="polyline_2d")


def test_rejects_bad_visibility_and_class():
    _rejects_standalone(
        lambda d: d["views"][0]["segments"][0].update(visibility="dimmed"),
        match="visibility")
    _rejects_standalone(
        lambda d: d["views"][0]["segments"][0].update(edge_class="silhouette"),
        match="edge_class")


def test_b5_outline_source_never_carries_edge_id():
    _rejects_standalone(
        lambda d: d["views"][0]["segments"][1]["source"].update(
            edge_id="edge:a~b"),
        match="B5|edge_id")


def test_b5_model_edge_source_never_carries_face_or_index():
    _rejects_standalone(
        lambda d: d["views"][0]["segments"][0]["source"].update(
            face_id="feat_0002:face:hole_wall"),
        match="strict union|face_id")


def test_b5_outline_class_requires_outline_source():
    def mutate(d):
        d["views"][0]["segments"][1]["source"] = {
            "kind": "model_edge", "edge_id": "edge:a~b"}
        # keep counters consistent: still 1 visible / 1 hidden / 1 outline class
    _rejects_standalone(mutate, match="outline")


def test_b5_sharp_class_rejects_outline_source():
    def mutate(d):
        d["views"][0]["segments"][0]["source"] = {
            "kind": "outline", "face_id": "f", "index": 0}
    _rejects_standalone(mutate, match="outline")


def test_rejects_negative_outline_index():
    _rejects_standalone(
        lambda d: d["views"][0]["segments"][1]["source"].update(index=-1),
        match="index")


def test_rejects_unknown_source_kind():
    def mutate(d):
        d["views"][0]["segments"][0]["source"] = {"kind": "mystery"}
    _rejects_standalone(mutate, match="kind")


def test_rejects_counter_mismatch():
    _rejects_standalone(
        lambda d: d["views"][0]["counters"].update(hidden_segments=7),
        match="counters disagree")


# ----------------------------------------------------------------------------
# 3. Version acceptance (Q7) + the inline B3 echo cross-check
# ----------------------------------------------------------------------------


def test_accepts_1_0_with_null_slot():
    dr = DisplayRepresentation.from_engine_dict(_display(version="1.0"))
    assert dr.display_representation_version == "1.0"
    assert dr.view_dependent is None


def test_accepts_1_1_with_null_slot():
    dr = DisplayRepresentation.from_engine_dict(_display(version="1.1"))
    assert dr.view_dependent is None


def test_accepts_1_1_with_valid_inline_payload():
    dr = DisplayRepresentation.from_engine_dict(
        _display(version="1.1", view_dependent=_payload()))
    assert dr.view_dependent is not None
    assert dr.view_dependent.views[0].view_id == "front"


def test_1_0_rejects_populated_slot_even_when_valid():
    with pytest.raises(DisplayContractError, match="must be null"):
        DisplayRepresentation.from_engine_dict(
            _display(version="1.0", view_dependent=_payload()))


def test_rejects_unknown_version():
    with pytest.raises(DisplayContractError, match="unsupported"):
        DisplayRepresentation.from_engine_dict(_display(version="2.0"))


def test_b3_inline_echo_mismatch_rejected():
    payload = _payload()
    payload["identity_echo"]["cache_key"] = "ck-STALE"
    with pytest.raises(DisplayContractError, match="cache_key"):
        DisplayRepresentation.from_engine_dict(
            _display(version="1.1", view_dependent=payload))


def test_b3_inline_echo_wrong_object_rejected():
    payload = _payload()
    payload["identity_echo"]["object_uuid"] = "u-OTHER"
    with pytest.raises(DisplayContractError, match="object_uuid"):
        DisplayRepresentation.from_engine_dict(
            _display(version="1.1", view_dependent=payload))


def test_b2_inline_echo_version_mismatch_rejected():
    """Codex2 B2 regression: an inline echo claiming a contract version other
    than the enclosing package's must be rejected — matching the standalone
    rule and the Studio attach check (the echo is SIX fields, all enforced)."""
    payload = _payload()
    payload["identity_echo"]["display_representation_version"] = "1.0"
    with pytest.raises(DisplayContractError,
                       match="display_representation_version"):
        DisplayRepresentation.from_engine_dict(
            _display(version="1.1", view_dependent=payload))


def test_round_trip_to_dict_preserves_payload():
    p = ViewDependentPayload.from_engine_dict(_payload())
    again = ViewDependentPayload.from_engine_dict(
        copy.deepcopy(p.to_dict()))
    assert again == p
