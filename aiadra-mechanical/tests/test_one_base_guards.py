"""S2 (arc 20260714-3; Codex1 B3) — the SAME-KIND half of the one-base rule.

The cross-kind XOR (extrude vs revolve) existed since arc 20260622-4; these
guards close the same-kind hole Codex1 caught: a SECOND extrude (or revolve)
must fail loud at the handler and — for a stored/corrupt recipe — at the
evaluator, never a silent "last one wins" that disagrees with the feature
history/tree.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from aiadra_core.protocol import propose
from aiadra_core.transaction.boundary import TransactionError

from aiadra_mechanical.adapter_payload import build_extrude_payload, build_sketch_payload
from aiadra_mechanical import display

from conftest import two_primitives  # type: ignore


def _committed_extruded_part(ws: Path) -> None:
    propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001", "primitives": two_primitives()}).commit()
    propose(ws, kind="mechanical.add_extrude_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001",
        "depth_mm": 5.0, "direction": "normal+"}).commit()


def test_second_extrude_rejected_at_the_handler(workspace_with_part: Path):
    ws = workspace_with_part
    _committed_extruded_part(ws)
    # A second sketch is fine (S2's stepwise world)…
    propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001", "primitives": two_primitives()}).commit()
    # …but a SECOND extrude is not (one base creation per Part).
    with pytest.raises(TransactionError, match="already has an extrude"):
        propose(ws, kind="mechanical.add_extrude_feature", params={
            "part_number": "P-000001", "sketch_feature_id": "feat_0003",
            "depth_mm": 3.0, "direction": "normal+"}).commit()


def test_second_revolve_rejected_at_the_handler(workspace_with_part: Path):
    ws = workspace_with_part
    offset_rect = [{"type": "rectangle", "x_mm": 0, "y_mm": 2, "width_mm": 20, "height_mm": 3}]
    propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001", "primitives": offset_rect}).commit()
    propose(ws, kind="mechanical.add_revolve_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001", "axis": "x"}).commit()
    propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001", "primitives": offset_rect}).commit()
    with pytest.raises(TransactionError, match="already has a revolve"):
        propose(ws, kind="mechanical.add_revolve_feature", params={
            "part_number": "P-000001", "sketch_feature_id": "feat_0003", "axis": "x"}).commit()


def test_corrupt_two_extrude_recipe_fails_loud_at_evaluation():
    # A stored recipe with TWO extrudes (bypassing the handler) must fail loud
    # at the evaluator — never "last extrude wins".
    def sketch(fid):
        return {"id": fid, "feature_type": "sketch",
                "adapter_payload": build_sketch_payload(
                    [{"type": "rectangle", "x_mm": 0, "y_mm": 0, "width_mm": 40, "height_mm": 30}])}

    def extrude(fid, sketch_id, param_id):
        return {"id": fid, "feature_type": "extrude",
                "depends_on_feature_ids": [sketch_id],
                "parameters": [{"id": param_id, "name": "depth_mm", "value": 5.0,
                                "datatype": "number", "unit": "mm"}],
                "adapter_payload": build_extrude_payload(
                    sketch_feature_id=sketch_id, direction="normal+",
                    depth_parameter_id=param_id)}

    feats = [sketch("feat_0001"), extrude("feat_0002", "feat_0001", "featp_0001"),
             sketch("feat_0003"), extrude("feat_0004", "feat_0003", "featp_0002")]
    with pytest.raises(TransactionError, match="exactly one base creation"):
        display.generate_display_representation(
            feats, object_uuid="u-1", object_number="PRT-0001",
            geometry_ref="sha256:deadbeef", cache_key="ck")
