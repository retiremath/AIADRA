"""Validity-gate failure classes (ADR/0031 D6/B2 + arc 20260602-1 Codex1 B1).

Class 1 (domain/payload) -> `TransactionError` (dispatch-adapter passthrough),
raised before/around the kernel. Class 2 (kernel execution) -> the engine
raises a package-local non-passthrough error; the aiadra-core dispatch adapter
(NOT the engine) wraps it as `NativeEngineKernelError`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from aiadra_core.native_engine.exceptions import EngineNotAvailableError, NativeEngineKernelError
from aiadra_core.protocol import propose
from aiadra_core.transaction.boundary import TransactionError

from aiadra_mechanical import cache, geometry
from aiadra_mechanical.geometry import MechanicalKernelEvaluationError
from conftest import two_primitives


# ---- Class 1: domain / payload -> TransactionError ----

def test_class1_negative_depth_on_add(workspace_with_part: Path):
    propose(workspace_with_part, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001", "primitives": two_primitives()}).commit()
    with pytest.raises(TransactionError, match="positive"):
        propose(workspace_with_part, kind="mechanical.add_extrude_feature", params={
            "part_number": "P-000001", "sketch_feature_id": "feat_0001",
            "depth_mm": -2.0, "direction": "z+"})


def test_class1_negative_depth_on_adjust(workspace_with_extrude: Path):
    with pytest.raises(TransactionError, match="positive"):
        propose(workspace_with_extrude, kind="mechanical.adjust_feature_parameter", params={
            "part_number": "P-000001", "feature_id": "feat_0002",
            "parameter_name": "depth_mm", "new_value": 0.0})


def test_class1_circle_outside_rectangle(workspace_with_part: Path):
    """Codex1 N2 arc 20260602-1: circle outside the rectangle is engine-domain
    (TransactionError), NOT a kernel failure."""
    with pytest.raises(TransactionError, match="inside"):
        propose(workspace_with_part, kind="mechanical.add_sketch_feature", params={
            "part_number": "P-000001", "primitives": [
                {"type": "rectangle", "x_mm": 0.0, "y_mm": 0.0, "width_mm": 20.0, "height_mm": 10.0},
                {"type": "circle", "cx_mm": 5.0, "cy_mm": 5.0, "radius_mm": 8.0}]})


def test_class1_bad_direction_and_missing_param(workspace_with_part: Path):
    propose(workspace_with_part, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001", "primitives": two_primitives()}).commit()
    with pytest.raises(TransactionError, match="direction"):
        propose(workspace_with_part, kind="mechanical.add_extrude_feature", params={
            "part_number": "P-000001", "sketch_feature_id": "feat_0001",
            "depth_mm": 5.0, "direction": "x+"})
    with pytest.raises(TransactionError, match="missing required"):
        propose(workspace_with_part, kind="mechanical.add_sketch_feature", params={
            "part_number": "P-000001"})


# ---- Class 2: kernel execution -> adapter wraps as NativeEngineKernelError ----

def test_class2_engine_local_kernel_error_is_wrapped_by_adapter(workspace_with_part: Path, monkeypatch):
    """The engine raises its package-local MechanicalKernelEvaluationError; the
    dispatch adapter wraps it as NativeEngineKernelError with __cause__. The
    engine must NEVER construct NativeEngineKernelError itself (Codex1 B1)."""
    cache.clear()

    def boom(_features):
        raise MechanicalKernelEvaluationError("synthetic OCCT failure")

    monkeypatch.setattr(geometry, "evaluate_part", boom)
    with pytest.raises(NativeEngineKernelError) as exc:
        propose(workspace_with_part, kind="mechanical.add_sketch_feature", params={
            "part_number": "P-000001", "primitives": two_primitives()})
    assert exc.value.engine_id == "mechanical"
    assert exc.value.operation_kind == "mechanical.add_sketch_feature"
    assert isinstance(exc.value.__cause__, MechanicalKernelEvaluationError)


def test_class2_raw_kernel_exception_is_wrapped(workspace_with_part: Path, monkeypatch):
    """A raw (non-package-local) exception during evaluation is also wrapped by
    the adapter — the engine never swallows it."""
    cache.clear()

    def boom(_features):
        raise ZeroDivisionError("synthetic raw kernel crash")

    monkeypatch.setattr(geometry, "evaluate_part", boom)
    with pytest.raises(NativeEngineKernelError) as exc:
        propose(workspace_with_part, kind="mechanical.add_sketch_feature", params={
            "part_number": "P-000001", "primitives": two_primitives()})
    assert isinstance(exc.value.__cause__, ZeroDivisionError)


def test_never_installed_engine_raises_engine_not_available(workspace_with_part: Path):
    with pytest.raises(EngineNotAvailableError, match="not installed"):
        propose(workspace_with_part, kind="totally_synthetic_engine_id.foo", params={"x": 1})


def test_corrupt_stored_extrude_direction_is_rejected():
    """Codex2 N1 arc 20260602-1: a corrupt stored extrude direction is rejected
    by the evaluator rather than silently treated as 'z-'."""
    features = [
        {"id": "feat_0001", "feature_type": "sketch", "adapter_payload": {"primitives": [
            {"type": "rectangle", "x_mm": 0.0, "y_mm": 0.0, "width_mm": 20.0, "height_mm": 10.0}]}},
        {"id": "feat_0002", "feature_type": "extrude",
         "adapter_payload": {"direction": "x+", "sketch_feature_id": "feat_0001"},
         "parameters": [{"id": "featp_0001", "name": "depth_mm", "value": 5.0,
                         "datatype": "number", "unit": "mm"}]},
    ]
    with pytest.raises(TransactionError, match="direction"):
        geometry.evaluate_part(features)
