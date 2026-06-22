"""Fillet/round feature — the first referencing feature (ADR/0037 D8 step 1;
ADR/0038; arc 20260621-2).

Covers the acceptance bar: the authoring op + canonical-unit radius (1,2); the
engine-owned recipe-anchored `target_edge` reference, NOT the display id (D1/B1);
parent parameter-edit survival (3) vs topology-change / removed-parent fail-loud
(4); the blend role + tangent edges through the display lane (5). Plus Codex1's
notes: deterministic role sort (N2) and the synthesized ambiguous-resolution
regression (N3).
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from aiadra_core.native_engine.exceptions import NativeEngineKernelError
from aiadra_core.protocol import propose
from aiadra_core.transaction.boundary import TransactionError
from aiadra_core.validation.fold import FoldInconsistencyError

from aiadra_mechanical import geometry, topology
from aiadra_mechanical.adapter_payload import (
    build_extrude_payload,
    build_fillet_payload,
    build_sketch_payload,
)

from conftest import part_sidecar  # type: ignore


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _make_box(ws: Path, *, w: float = 23.0, h: float = 11.0, depth: float = 6.0) -> None:
    """A plain extruded box (no hole) on P-000001 — the cleanest fillet target."""
    propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001",
        "primitives": [{"type": "rectangle", "x_mm": 0.0, "y_mm": 0.0,
                        "width_mm": w, "height_mm": h}],
    }).commit()
    propose(ws, kind="mechanical.add_extrude_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001",
        "depth_mm": depth, "direction": "z+"}).commit()


def _make_box_with_hole(ws: Path, *, w: float = 23.0, h: float = 11.0, depth: float = 6.0) -> None:
    """A box with a through-hole — its hole cylinder contributes a `seam` edge,
    the natural non-sharp target for the B1 rejection test."""
    propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001",
        "primitives": [
            {"type": "rectangle", "x_mm": 0.0, "y_mm": 0.0, "width_mm": w, "height_mm": h},
            {"type": "circle", "cx_mm": 6.0, "cy_mm": 4.5, "radius_mm": 2.0}],
    }).commit()
    propose(ws, kind="mechanical.add_extrude_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001",
        "depth_mm": depth, "direction": "z+"}).commit()


def _vertical_wall_edge_id(ws: Path) -> str:
    """A sharp vertical wall–wall corner edge (two wall roles) — the display id a
    UI pick / golden recipe would name as the fillet selector."""
    feats = part_sidecar(ws)["feature"]
    topo = topology.extract_part_topology(feats)
    cands = [e for e in topo.edges if e.kind == "sharp" and e.edge_id.count("wall_") == 2]
    assert cands, "expected a vertical wall-wall edge on a box"
    return cands[0].edge_id


def _box_with_fillet_recipe(radius: float = 2.0) -> list[dict]:
    """Engine-level recipe (no workspace): box + a fillet whose persisted
    reference + signature are built the same way the handler builds them."""
    feats = [
        {"id": "feat_0001", "feature_type": "sketch",
         "adapter_payload": build_sketch_payload(
             [{"type": "rectangle", "x_mm": 0.0, "y_mm": 0.0, "width_mm": 23.0, "height_mm": 11.0}])},
        {"id": "feat_0002", "feature_type": "extrude",
         "parameters": [{"id": "featp_0001", "name": "depth_mm", "value": 6.0,
                         "datatype": "number", "unit": "mm"}],
         "adapter_payload": build_extrude_payload(
             sketch_feature_id="feat_0001", direction="z+", depth_parameter_id="featp_0001")},
    ]
    topo = topology.extract_part_topology(feats)
    target = [e for e in topo.edges if e.kind == "sharp" and e.edge_id.count("wall_") == 2][0]
    fillet = {
        "id": "feat_0003", "feature_type": "fillet",
        "depends_on_feature_ids": ["feat_0002"],
        "parameters": [{"id": "featp_0002", "name": "radius_mm", "value": radius,
                        "datatype": "number", "unit": "mm"}],
        "adapter_payload": build_fillet_payload(
            adjacent_face_roles=list(target.adjacent_face_ids),
            edge_kind=target.kind,
            resolved_against_topology_signature=topo.topology_signature),
    }
    return feats + [fillet]


# ----------------------------------------------------------------------------
# Acceptance bar — API-level (through propose / the real handler)
# ----------------------------------------------------------------------------


def test_add_fillet_happy_path(workspace_with_part: Path):
    ws = workspace_with_part
    _make_box(ws)
    eid = _vertical_wall_edge_id(ws)
    before = part_sidecar(ws)["geometry_ref"][0]["vault_ref"]

    propose(ws, kind="mechanical.add_fillet_feature", params={
        "part_number": "P-000001", "target_edge_id": eid, "radius_mm": 2.0}).commit()

    sc = part_sidecar(ws)
    fillet = [f for f in sc["feature"] if f["feature_type"] == "fillet"][0]
    assert fillet["depends_on_feature_ids"] == ["feat_0002"]
    p = fillet["parameters"][0]
    assert p["name"] == "radius_mm" and p["value"] == 2.0
    assert p["datatype"] == "number" and p["unit"] == "mm" and p["id"].startswith("featp_")
    tgt = fillet["adapter_payload"]["target_edge"]
    assert len(tgt["adjacent_face_roles"]) == 2
    assert tgt["edge_kind"] == "sharp"
    assert tgt["resolved_against_topology_signature"].startswith("topo_")
    assert before != part_sidecar(ws)["geometry_ref"][0]["vault_ref"]


def test_target_edge_is_structured_not_the_display_string(workspace_with_part: Path):
    """ADR/0038 D1/B1: Truth stores the structured recipe anchor + signature —
    never the read-side display `edge_id` string."""
    ws = workspace_with_part
    _make_box(ws)
    eid = _vertical_wall_edge_id(ws)
    propose(ws, kind="mechanical.add_fillet_feature", params={
        "part_number": "P-000001", "target_edge_id": eid, "radius_mm": 2.0}).commit()

    tgt = [f for f in part_sidecar(ws)["feature"]
           if f["feature_type"] == "fillet"][0]["adapter_payload"]["target_edge"]
    assert set(tgt) == {"adjacent_face_roles", "edge_kind", "resolved_against_topology_signature"}
    assert eid not in tgt["adjacent_face_roles"]          # the bare roles, not "edge:…~…"
    assert not any(r.startswith("edge:") for r in tgt["adjacent_face_roles"])


def test_blend_role_and_tangent_edges_after_fillet(workspace_with_part: Path):
    """Acceptance bar 5 + ADR/0038 D4/D6: the blend gets a by-construction role
    (cylinder), tangent edges appear, and the rounded-away sharp edge is gone."""
    ws = workspace_with_part
    _make_box(ws)
    eid = _vertical_wall_edge_id(ws)
    propose(ws, kind="mechanical.add_fillet_feature", params={
        "part_number": "P-000001", "target_edge_id": eid, "radius_mm": 2.0}).commit()

    feats = part_sidecar(ws)["feature"]
    fillet_id = [f["id"] for f in feats if f["feature_type"] == "fillet"][0]
    topo = topology.extract_part_topology(feats)

    blends = [f for f in topo.faces if f.face_id == f"{fillet_id}:face:blend"]
    assert len(blends) == 1
    assert blends[0].surface_kind == "cylinder"           # NOT mislabeled hole_wall
    assert any(e.kind == "tangent" for e in topo.edges)   # the HLR smooth lane
    assert eid not in {e.edge_id for e in topo.edges}     # the sharp edge is gone


def test_fillet_survives_parent_dimension_edit(workspace_with_part: Path):
    """Acceptance bar 3 + ADR/0038 D2 survival: a parent PARAMETER edit preserves
    the skeleton, so the fillet stays resolvable and recomputes."""
    ws = workspace_with_part
    _make_box(ws)
    eid = _vertical_wall_edge_id(ws)
    propose(ws, kind="mechanical.add_fillet_feature", params={
        "part_number": "P-000001", "target_edge_id": eid, "radius_mm": 2.0}).commit()
    tgt_before = [f for f in part_sidecar(ws)["feature"]
                  if f["feature_type"] == "fillet"][0]["adapter_payload"]["target_edge"]

    propose(ws, kind="mechanical.adjust_feature_parameter", params={
        "part_number": "P-000001", "feature_id": "feat_0002",
        "parameter_name": "depth_mm", "new_value": 10.0}).commit()

    sc = part_sidecar(ws)
    fillet = [f for f in sc["feature"] if f["feature_type"] == "fillet"][0]
    assert fillet["adapter_payload"]["target_edge"] == tgt_before  # reference unchanged
    topo = topology.extract_part_topology(sc["feature"])           # still evaluates
    assert any(f.face_id.endswith(":face:blend") for f in topo.faces)


def test_fillet_radius_edit_recomputes(workspace_with_part: Path):
    ws = workspace_with_part
    _make_box(ws)
    eid = _vertical_wall_edge_id(ws)
    propose(ws, kind="mechanical.add_fillet_feature", params={
        "part_number": "P-000001", "target_edge_id": eid, "radius_mm": 2.0}).commit()
    fillet_id = [f["id"] for f in part_sidecar(ws)["feature"] if f["feature_type"] == "fillet"][0]
    before = part_sidecar(ws)["geometry_ref"][0]["vault_ref"]

    propose(ws, kind="mechanical.adjust_feature_parameter", params={
        "part_number": "P-000001", "feature_id": fillet_id,
        "parameter_name": "radius_mm", "new_value": 3.0}).commit()

    assert before != part_sidecar(ws)["geometry_ref"][0]["vault_ref"]


def test_remove_parent_with_dependent_fillet_fails_loud(workspace_with_part: Path):
    """Acceptance bar 4 + ADR/0038 D5: removing the parent solid while the fillet
    depends on it fails loud via the core cascade check (ADR/0029 D12)."""
    ws = workspace_with_part
    _make_box(ws)
    eid = _vertical_wall_edge_id(ws)
    propose(ws, kind="mechanical.add_fillet_feature", params={
        "part_number": "P-000001", "target_edge_id": eid, "radius_mm": 2.0}).commit()

    draft = propose(ws, kind="mechanical.remove_feature", params={
        "part_number": "P-000001", "feature_ids": ["feat_0002"]})  # the extrude parent
    with pytest.raises(FoldInconsistencyError, match="depends_on_feature_ids"):
        draft.validate()


def test_oversize_radius_is_class2_kernel_rejection(workspace_with_part: Path):
    """Codex1 Q3: a plausible reference with an unbuildable radius surfaces as a
    Class-2 kernel rejection — not an approximate domain precheck."""
    ws = workspace_with_part
    _make_box(ws, w=23.0, h=11.0, depth=6.0)
    eid = _vertical_wall_edge_id(ws)
    with pytest.raises(NativeEngineKernelError):
        propose(ws, kind="mechanical.add_fillet_feature", params={
            "part_number": "P-000001", "target_edge_id": eid, "radius_mm": 50.0}).commit()


def test_unknown_target_edge_id_fails_loud(workspace_with_part: Path):
    ws = workspace_with_part
    _make_box(ws)
    with pytest.raises(TransactionError, match="not found"):
        propose(ws, kind="mechanical.add_fillet_feature", params={
            "part_number": "P-000001", "target_edge_id": "edge:does:not:exist", "radius_mm": 2.0})


def test_non_sharp_edge_kind_rejected_before_staging(workspace_with_part: Path):
    """Codex2 B1: v1 rounds a SHARP edge only. A non-sharp selector (the hole
    seam) fails Class-1 BEFORE staging — unsupported topology never reaches
    Product Truth, and the error is a clear domain error, not Class-2 kernel."""
    ws = workspace_with_part
    _make_box_with_hole(ws)
    feats = part_sidecar(ws)["feature"]
    non_sharp = next(
        (e for e in topology.extract_part_topology(feats).edges if e.kind != "sharp"), None
    )
    assert non_sharp is not None, "a box-with-hole should expose a non-sharp (seam) edge"
    before = len(feats)
    with pytest.raises(TransactionError, match="SHARP"):
        propose(ws, kind="mechanical.add_fillet_feature", params={
            "part_number": "P-000001", "target_edge_id": non_sharp.edge_id, "radius_mm": 1.0})
    assert len(part_sidecar(ws)["feature"]) == before  # nothing staged


# ----------------------------------------------------------------------------
# Reference / regeneration discipline — engine-level (synthesized negatives)
# ----------------------------------------------------------------------------


def test_fillet_changes_topology_signature():
    """A fillet IS a topology change (ADR/0038 D4) — the signature differs."""
    full = _box_with_fillet_recipe()
    box = full[:2]
    assert topology.compute_topology_signature(box) != topology.compute_topology_signature(full)


def test_stale_reference_fails_loud_on_topology_change():
    """ADR/0038 D4: a parent topology-skeleton change (not a parameter edit)
    makes the stored signature stale → fail loud before any kernel mutation."""
    feats = _box_with_fillet_recipe()
    feats[0]["adapter_payload"]["primitives"].append(
        {"id": "skp_0002", "type": "circle", "cx_mm": 6.0, "cy_mm": 4.0, "radius_mm": 1.0})
    with pytest.raises(TransactionError, match="STALE"):
        geometry.evaluate_part(feats)


def test_missing_role_reference_fails_loud():
    """ADR/0038 D4: a reference whose role pair is absent resolves to no edge and
    fails loud (the prefix signature still matches — the fillet is excluded from
    the prefix — so resolution, not the stale guard, is what fires)."""
    feats = _box_with_fillet_recipe()
    feats[-1]["adapter_payload"]["target_edge"]["adjacent_face_roles"] = [
        "feat_0002/skp_0001:face:wall_x_max", "feat_0002/skp_0001:face:bogus_role"]
    with pytest.raises(TransactionError, match="NO edge"):
        geometry.evaluate_part(feats)


def test_ambiguous_reference_fails_loud(monkeypatch):
    """ADR/0038 D4 + Codex1 N3: a role pair resolving to >1 edge fails loud — it
    never guesses. Synthesized (natural v1 geometry yields one edge per pair)."""
    class _E:
        def __init__(self, roles, kind):
            self.adjacent_face_ids = tuple(sorted(roles))
            self.kind = kind
            self.edge = object()

    roles = ["a:face:x", "b:face:y"]
    monkeypatch.setattr(
        topology, "correlate_shape",
        lambda shape, features, **kw: (None, (), (_E(roles, "sharp"), _E(roles, "sharp"))),
    )
    with pytest.raises(TransactionError, match="AMBIGUOUS"):
        topology.resolve_edge_on_shape(object(), [], roles, "sharp")


def test_missed_blend_hint_fails_loud_not_placeholder(workspace_with_part: Path, monkeypatch):
    """Codex2 B2: if a blend hint is ever missed (empty Generated, or a hint face
    not found in the final map), the unclaimed cylinder must FAIL LOUD — never
    mint a fabricated `…/None:face:hole_wall` placeholder (ADR/0035 no-placeholder;
    ADR/0038 by-construction). Forced by neutering the produced-role claim."""
    feats = _box_with_fillet_recipe()  # a box (no circle primitive) + a fillet blend
    monkeypatch.setattr(topology, "_claimed_produced_roles", lambda face_map, produced_hints: {})
    with pytest.raises(TransactionError, match="unclaimed cylinder"):
        topology.extract_part_topology(feats)


def test_build_fillet_payload_sorts_roles_deterministically():
    """Codex1 N2: adjacent_face_roles are sorted at write time, so the stored
    order is deterministic regardless of selection order."""
    p1 = build_fillet_payload(adjacent_face_roles=["b:face:y", "a:face:x"],
                              edge_kind="sharp", resolved_against_topology_signature="topo_abc")
    p2 = build_fillet_payload(adjacent_face_roles=["a:face:x", "b:face:y"],
                              edge_kind="sharp", resolved_against_topology_signature="topo_abc")
    assert p1 == p2
    assert p1["target_edge"]["adjacent_face_roles"] == ["a:face:x", "b:face:y"]


def test_build_fillet_payload_rejects_bad_inputs():
    with pytest.raises(TransactionError, match="exactly two"):
        build_fillet_payload(adjacent_face_roles=["only:one"], edge_kind="sharp",
                             resolved_against_topology_signature="topo_abc")
    with pytest.raises(TransactionError, match="edge_kind"):
        build_fillet_payload(adjacent_face_roles=["a:f:x", "b:f:y"], edge_kind="round",
                             resolved_against_topology_signature="topo_abc")
    with pytest.raises(TransactionError, match="topo_"):
        build_fillet_payload(adjacent_face_roles=["a:f:x", "b:f:y"], edge_kind="sharp",
                             resolved_against_topology_signature="not-a-sig")
