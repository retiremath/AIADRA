"""Revolve — the first non-referencing CREATION feature since extrude (ADR/0037
D8; arc 20260622-4).

Revolve creates base geometry (it does NOT touch ADR/0038's reference machinery),
so the emphasis is the creation-feature invariants Codex flagged:
  - B1: tube↔solid is topology SKELETON (the `inner_wall` role appears/disappears),
    so the derived radial mode enters the signature; radii stay out within a mode.
  - B2: a v1 profile is EXACTLY one rectangle, enforced in handler AND evaluator.
  - B3: extrude XOR revolve, enforced symmetrically (both handlers + the evaluator).
And the new correlation: a revolve solid maps recipe-first into outer/inner-wall +
cap_lo/cap_hi roles (plane + cylinder only), fail-loud on a face-count mismatch.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from aiadra_core.protocol import propose
from aiadra_core.transaction.boundary import TransactionError

from aiadra_mechanical import geometry, topology
from aiadra_mechanical.adapter_payload import (
    build_extrude_payload,
    build_revolve_payload,
    build_sketch_payload,
)

from conftest import part_sidecar  # type: ignore


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

# An offset rectangle → a TUBE (2 cylinder walls + 2 planar caps).
_TUBE = {"x_mm": 0.0, "y_mm": 2.0, "width_mm": 20.0, "height_mm": 3.0}
# An on-axis rectangle (y touches the X axis) → a SOLID cylinder (1 wall + 2 caps).
_SOLID = {"x_mm": 0.0, "y_mm": 0.0, "width_mm": 20.0, "height_mm": 5.0}


def _add_sketch(ws: Path, primitives: list[dict]) -> None:
    propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001", "primitives": primitives}).commit()


def _make_tube(ws: Path) -> None:
    _add_sketch(ws, [{"type": "rectangle", **_TUBE}])
    propose(ws, kind="mechanical.add_revolve_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001", "axis": "x"}).commit()


def _roles(feats: list[dict]) -> set[str]:
    topo = topology.extract_part_topology(feats)
    return {f.face_id.split(":face:")[-1] for f in topo.faces}


def _revolve_recipe(rect_kw: dict, *, axis: str = "x", extra_prims=()) -> list[dict]:
    prims = [{"type": "rectangle", **rect_kw}] + [dict(p) for p in extra_prims]
    return [
        {"id": "feat_0001", "feature_type": "sketch",
         "adapter_payload": build_sketch_payload(prims)},
        {"id": "feat_0002", "feature_type": "revolve",
         "depends_on_feature_ids": ["feat_0001"],
         "adapter_payload": build_revolve_payload(sketch_feature_id="feat_0001", axis=axis)},
    ]


# ----------------------------------------------------------------------------
# Acceptance bar — API-level
# ----------------------------------------------------------------------------


def test_add_revolve_tube_happy_path(workspace_with_part: Path):
    ws = workspace_with_part
    _add_sketch(ws, [{"type": "rectangle", **_TUBE}])
    before = part_sidecar(ws)["geometry_ref"][0]["vault_ref"]

    propose(ws, kind="mechanical.add_revolve_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001", "axis": "x"}).commit()

    sc = part_sidecar(ws)
    rev = [f for f in sc["feature"] if f["feature_type"] == "revolve"][0]
    assert rev["depends_on_feature_ids"] == ["feat_0001"]
    assert rev["adapter_payload"] == {"sketch_feature_id": "feat_0001", "axis": "x"}
    assert "parameters" not in rev  # v1 revolve carries no numeric parameter
    # The revolve REPLACES the sketch's authoring_geometry (derives from both).
    geom = sc["geometry_ref"][0]
    assert geom["derived_from_feature_ids"] == ["feat_0001", rev["id"]]
    assert geom["vault_ref"] != before


def test_add_revolve_solid_cylinder_happy_path(workspace_with_part: Path):
    ws = workspace_with_part
    _add_sketch(ws, [{"type": "rectangle", **_SOLID}])
    propose(ws, kind="mechanical.add_revolve_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001", "axis": "x"}).commit()
    assert any(f["feature_type"] == "revolve" for f in part_sidecar(ws)["feature"])


def test_tube_correlates_to_outer_inner_walls_and_caps(workspace_with_part: Path):
    ws = workspace_with_part
    _make_tube(ws)
    assert _roles(part_sidecar(ws)["feature"]) == {"outer_wall", "inner_wall", "cap_lo", "cap_hi"}


def test_solid_cylinder_has_no_inner_wall(workspace_with_part: Path):
    ws = workspace_with_part
    _add_sketch(ws, [{"type": "rectangle", **_SOLID}])
    propose(ws, kind="mechanical.add_revolve_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001", "axis": "x"}).commit()
    assert _roles(part_sidecar(ws)["feature"]) == {"outer_wall", "cap_lo", "cap_hi"}


def test_roles_are_recipe_anchored_to_the_revolve_feature(workspace_with_part: Path):
    ws = workspace_with_part
    _make_tube(ws)
    feats = part_sidecar(ws)["feature"]
    rev_id = [f["id"] for f in feats if f["feature_type"] == "revolve"][0]
    faces = {f.face_id for f in topology.extract_part_topology(feats).faces}
    assert f"{rev_id}:face:outer_wall" in faces
    assert f"{rev_id}:face:inner_wall" in faces


# ----------------------------------------------------------------------------
# B3 — extrude XOR revolve, symmetric
# ----------------------------------------------------------------------------


def test_revolve_rejected_when_extrude_exists(workspace_with_part: Path):
    ws = workspace_with_part
    _add_sketch(ws, [{"type": "rectangle", **_TUBE}])
    propose(ws, kind="mechanical.add_extrude_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001",
        "depth_mm": 5.0, "direction": "z+"}).commit()
    with pytest.raises(TransactionError, match="one base creation"):
        propose(ws, kind="mechanical.add_revolve_feature", params={
            "part_number": "P-000001", "sketch_feature_id": "feat_0001", "axis": "x"})


def test_extrude_rejected_when_revolve_exists(workspace_with_part: Path):
    ws = workspace_with_part
    _make_tube(ws)
    with pytest.raises(TransactionError, match="one base creation"):
        propose(ws, kind="mechanical.add_extrude_feature", params={
            "part_number": "P-000001", "sketch_feature_id": "feat_0001",
            "depth_mm": 5.0, "direction": "z+"})


def test_both_base_features_in_a_direct_recipe_fail_loud():
    """B3 evaluator side: a stored/corrupt recipe with BOTH bases fails loud
    rather than letting 'last base wins' decide the solid."""
    feats = _revolve_recipe(_TUBE)
    feats.insert(1, {
        "id": "feat_0003", "feature_type": "extrude",
        "parameters": [{"id": "featp_0001", "name": "depth_mm", "value": 5.0,
                        "datatype": "number", "unit": "mm"}],
        "adapter_payload": build_extrude_payload(
            sketch_feature_id="feat_0001", direction="z+", depth_parameter_id="featp_0001")})
    with pytest.raises(TransactionError, match="BOTH an extrude and a revolve"):
        geometry.evaluate_part(feats)


# ----------------------------------------------------------------------------
# B2 — exactly one rectangle, handler AND evaluator
# ----------------------------------------------------------------------------


def test_non_simple_profile_rejected_by_handler(workspace_with_part: Path):
    ws = workspace_with_part
    _add_sketch(ws, [
        {"type": "rectangle", **_TUBE},
        {"type": "circle", "cx_mm": 6.0, "cy_mm": 4.0, "radius_mm": 1.0}])
    with pytest.raises(TransactionError, match="SIMPLE profile"):
        propose(ws, kind="mechanical.add_revolve_feature", params={
            "part_number": "P-000001", "sketch_feature_id": "feat_0001", "axis": "x"})


def test_non_simple_profile_fails_from_evaluator_path():
    feats = _revolve_recipe(
        _TUBE, extra_prims=[{"type": "circle", "cx_mm": 6.0, "cy_mm": 4.0, "radius_mm": 1.0}])
    with pytest.raises(TransactionError, match="SIMPLE profile"):
        geometry.evaluate_part(feats)


# ----------------------------------------------------------------------------
# B1 — radial mode is skeleton; crossing-axis is invalid
# ----------------------------------------------------------------------------


def test_crossing_axis_rejected_from_evaluator_path():
    """B1: a profile straddling the axis is a self-intersecting v1 revolve →
    Class-1 from the evaluator (the direct path), not only the handler."""
    feats = _revolve_recipe({"x_mm": 0.0, "y_mm": -2.0, "width_mm": 20.0, "height_mm": 5.0})
    with pytest.raises(TransactionError, match="crosses the x-axis"):
        geometry.evaluate_part(feats)


def test_crossing_axis_rejected_by_handler(workspace_with_part: Path):
    ws = workspace_with_part
    _add_sketch(ws, [{"type": "rectangle", "x_mm": 0.0, "y_mm": -2.0,
                      "width_mm": 20.0, "height_mm": 5.0}])
    with pytest.raises(TransactionError, match="crosses the x-axis"):
        propose(ws, kind="mechanical.add_revolve_feature", params={
            "part_number": "P-000001", "sketch_feature_id": "feat_0001", "axis": "x"})


def test_invalid_axis_rejected(workspace_with_part: Path):
    ws = workspace_with_part
    _add_sketch(ws, [{"type": "rectangle", **_TUBE}])
    with pytest.raises(TransactionError, match="axis must be 'x' or 'y'"):
        propose(ws, kind="mechanical.add_revolve_feature", params={
            "part_number": "P-000001", "sketch_feature_id": "feat_0001", "axis": "z"})


def test_radial_mode_is_skeleton_radii_are_values():
    """B1: tube vs solid have DIFFERENT signatures (the inner_wall role differs);
    two tubes that differ only in radii share a signature (value stability)."""
    tube = _revolve_recipe(_TUBE)
    solid = _revolve_recipe(_SOLID)
    tube_b = _revolve_recipe({"x_mm": 0.0, "y_mm": 5.0, "width_mm": 30.0, "height_mm": 9.0})
    sig = topology.compute_topology_signature
    assert sig(tube) != sig(solid)        # mode is skeleton
    assert sig(tube) == sig(tube_b)       # radii are values within a mode


def test_axis_is_skeleton():
    """The revolve axis changes topology → it is part of the skeleton."""
    # Offset from BOTH axes so each axis choice is a TUBE (mode held constant).
    rect = {"x_mm": 2.0, "y_mm": 2.0, "width_mm": 5.0, "height_mm": 3.0}
    sig = topology.compute_topology_signature
    assert sig(_revolve_recipe(rect, axis="x")) != sig(_revolve_recipe(rect, axis="y"))


def test_revolve_is_a_topology_change_vs_bare_sketch():
    feats = _revolve_recipe(_TUBE)
    sig = topology.compute_topology_signature
    assert sig(feats) != sig(feats[:1])


# ----------------------------------------------------------------------------
# Correlation fail-loud
# ----------------------------------------------------------------------------


def test_correlation_fails_loud_on_face_count_mismatch(monkeypatch):
    """A mode that disagrees with the built solid (here: claim 'solid' for a real
    tube) must fail loud on the face-count check — no silent fallback."""
    feats = _revolve_recipe(_TUBE)  # a real 2-cylinder tube
    monkeypatch.setattr(geometry, "revolve_radial_mode", lambda rect, axis: "solid")
    with pytest.raises(TransactionError, match="face-count mismatch"):
        topology.extract_part_topology(feats)
