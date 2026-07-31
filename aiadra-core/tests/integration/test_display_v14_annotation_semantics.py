"""Display contract v1.4 — the ENFORCED per-kind annotation semantics
(Codex14 B4, arc 20260730-1).

The pinned table — position_x/position_y measure exactly one POINT in mm;
length exactly one SEGMENT in mm; angle exactly one SEGMENT in deg within
[0, 360); radius exactly one CIRCLE in mm; ids are the semantic
`ann:{kind}:{entity}` — is validation, not documentation. A producer cannot
ship `angle(point, mm)` and leave the renderer to guess. Pure-dict tests:
no engine, no OCCT.
"""
from __future__ import annotations

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


def _ann(kind: str, entity: str, *, value: float = 20.0, unit: str = "mm",
         ann_id: str | None = None) -> dict:
    return {
        "id": ann_id if ann_id is not None else f"ann:{kind}:{entity}",
        "kind": kind, "value": value, "unit": unit, "entities": [entity],
        "anchors": [[0.0, 0.0, 0.0], [20.0, 0.0, 0.0]],
    }


def _profile(annotations: list) -> dict:
    return {
        "sketch_feature_id": "feat_0001",
        "points": [{"id": "skp_0006", "world": [0.0, 0.0, 0.0]},
                   {"id": "skp_0007", "world": [20.0, 0.0, 0.0]},
                   {"id": "skp_0009", "world": [5.0, 5.0, 0.0]}],
        "segments": [{"id": "skp_0008", "start": "skp_0006", "end": "skp_0007"}],
        "circles": [{"id": "skp_0010", "center": "skp_0009", "radius_mm": 3.0}],
        "annotations": annotations,
        "constraint_glyphs": [],
    }


def _package(annotations: list) -> dict:
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
        "sketch_frames": [_frame("feat_0001")],
        "v2_construction": [],
        "v2_profiles": [_profile(annotations)],
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


def test_the_full_conforming_kind_set_validates():
    dr = DisplayRepresentation.from_engine_dict(_package([
        _ann("length", "skp_0008"),
        _ann("angle", "skp_0008", value=15.0, unit="deg"),
        _ann("position_x", "skp_0006"),
        _ann("position_y", "skp_0006", value=0.0),
        _ann("radius", "skp_0010", value=3.0),
    ]))
    assert len(dr.v2_profiles[0].annotations) == 5


@pytest.mark.parametrize("kind,entity", [
    ("angle", "skp_0006"),        # angle over a POINT
    ("radius", "skp_0008"),       # radius over a SEGMENT
    ("position_x", "skp_0008"),   # position over a SEGMENT
    ("length", "skp_0010"),       # length over a CIRCLE
])
def test_a_kind_measuring_the_wrong_entity_domain_refuses(kind: str, entity: str):
    unit = "deg" if kind == "angle" else "mm"
    with pytest.raises(DisplayContractError, match="measures exactly one"):
        DisplayRepresentation.from_engine_dict(
            _package([_ann(kind, entity, unit=unit)]))


def test_the_wrong_unit_for_a_kind_refuses():
    with pytest.raises(DisplayContractError, match="carries unit 'deg' exactly"):
        DisplayRepresentation.from_engine_dict(
            _package([_ann("angle", "skp_0008", unit="mm")]))
    with pytest.raises(DisplayContractError, match="carries unit 'mm' exactly"):
        DisplayRepresentation.from_engine_dict(
            _package([_ann("length", "skp_0008", unit="deg")]))


@pytest.mark.parametrize("value", [360.0, -0.1, 400.0])
def test_an_angle_outside_the_range_refuses(value: float):
    with pytest.raises(DisplayContractError, match=r"must lie in \[0, 360\)"):
        DisplayRepresentation.from_engine_dict(
            _package([_ann("angle", "skp_0008", value=value, unit="deg")]))


def test_two_entities_on_one_annotation_refuse():
    ann = _ann("length", "skp_0008")
    ann["entities"] = ["skp_0008", "skp_0006"]
    with pytest.raises(DisplayContractError, match="measures exactly one"):
        DisplayRepresentation.from_engine_dict(_package([ann]))


def test_a_non_semantic_id_refuses():
    with pytest.raises(DisplayContractError, match="must be the semantic"):
        DisplayRepresentation.from_engine_dict(
            _package([_ann("length", "skp_0008", ann_id="an01")]))


def test_an_id_naming_a_different_entity_refuses():
    with pytest.raises(DisplayContractError, match="must be the semantic"):
        DisplayRepresentation.from_engine_dict(_package([
            _ann("position_x", "skp_0006", ann_id="ann:position_x:skp_0007"),
        ]))
