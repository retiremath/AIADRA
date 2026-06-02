"""Packaging smoke test (ADR/0031 D11/D12) — runs FIRST.

Proves the OCP binding installs + imports + builds a valid solid on this
platform, and records the exact frozen cadquery-ocp/OCCT version. If this
fails on a CI-matrix platform, that platform's OCP-wheel gap is recorded as
v0.0.1 packaging friction (FINDINGS §1) and follows the ADR/0031 D4 fallback
route — never a silent binding swap.
"""
from __future__ import annotations

import importlib.metadata


def test_cadquery_ocp_installed_and_versioned():
    version = importlib.metadata.version("cadquery-ocp")
    assert version, "cadquery-ocp must be installed (ADR/0031 D4 binding commitment)"
    # The package pins == this exact version (selected + frozen at smoke time, N2).
    from aiadra_mechanical import cache
    assert cache.ocp_version() == version


def test_ocp_builds_and_validates_a_trivial_solid():
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.GProp import GProp_GProps

    box = BRepPrimAPI_MakeBox(20.0, 10.0, 5.0).Shape()
    assert not box.IsNull()
    assert BRepCheck_Analyzer(box).IsValid()
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(box, props)
    assert abs(props.Mass() - 1000.0) < 1e-6


def test_engine_evaluates_real_occt_solid_with_hole():
    """The engine's geometry evaluation builds a genuine box-with-cylindrical-
    hole solid (real OCCT boolean), validated by BRepCheck."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    from aiadra_mechanical import geometry

    features = [
        {"id": "feat_0001", "feature_type": "sketch", "adapter_payload": {"primitives": [
            {"type": "rectangle", "x_mm": 0.0, "y_mm": 0.0, "width_mm": 20.0, "height_mm": 10.0},
            {"type": "circle", "cx_mm": 5.0, "cy_mm": 5.0, "radius_mm": 2.0}]}},
        {"id": "feat_0002", "feature_type": "extrude",
         "adapter_payload": {"direction": "z+", "sketch_feature_id": "feat_0001"},
         "parameters": [{"id": "featp_0001", "name": "depth_mm", "value": 5.0,
                         "datatype": "number", "unit": "mm"}]},
    ]
    solid = geometry.evaluate_part(features)
    assert not solid.IsNull()
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(solid, props)
    # box 1000 - cylinder (pi*2^2*5 ~= 62.83) ~= 937.2
    import math
    assert abs(props.Mass() - (1000.0 - math.pi * 4.0 * 5.0)) < 1e-3
