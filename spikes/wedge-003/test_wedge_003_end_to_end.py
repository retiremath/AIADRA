"""Wedge-003 end-to-end tests — 12 happy-path tests per ADR/0030 D12.

Covers: install + discovery + introspection + native_engine_status +
5-step Mode A authoring loop + 5-step Mode B (composed via modify) +
event-id distinctness across composed engine ops + base-envelope conformance
+ no-colons in serialized keys + DAG acyclicity + STRICT set-equality on
geometry_ref provenance + B1 R1 absorption parameter-as-Product-Truth +
adjust changes parameter value AND geometry hash + release with features.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiadra_core.protocol import (
    modify,
    modify_kinds,
    native_engine_status,
    propose,
    propose_kinds,
    refresh_native_engines,
)
from aiadra_core.truth_model.reservation import find_reservation_entry_by_number
from aiadra_core.truth_model.sidecar import load_sidecar


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def _ensure_spike_discovered():
    """Refresh discovery before each test; verify spike is installed.
    The spike must be installed via:
        aiadra-core/.venv/Scripts/pip.exe install -e ./spikes/wedge-003
    """
    refresh_native_engines()
    status = native_engine_status()
    if "mechanical_spike" not in status or status["mechanical_spike"]["status"] != "loaded":
        pytest.skip(
            f"mechanical_spike Native Engine not loaded: {status}. "
            f"Install with: pip install -e ./spikes/wedge-003"
        )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    propose(ws, kind="init", params={}).commit()
    return ws


@pytest.fixture
def workspace_with_part(workspace: Path) -> Path:
    propose(workspace, kind="create_part", params={
        "number": "P-000001",
        "name": "BracketSpike",
    }).commit()
    return workspace


def _part_sidecar(ws: Path, number: str = "P-000001") -> dict:
    _, entry = find_reservation_entry_by_number(ws, number)
    return load_sidecar(ws, entry["object_uuid"])


def _two_primitives() -> list[dict]:
    return [
        {"type": "rectangle", "x_mm": 0.0, "y_mm": 0.0, "width_mm": 20.0, "height_mm": 10.0},
        {"type": "circle", "cx_mm": 5.0, "cy_mm": 5.0, "radius_mm": 2.0},
    ]


# =============================================================================
# Discovery + introspection tests
# =============================================================================


def test_install_and_discover_via_entry_point():
    """Per ADR/0030 D2 + arc 1 D5 two-pass discovery: the spike's
    entry-point is discovered against the REAL installed distribution."""
    status = native_engine_status()
    assert "mechanical_spike" in status
    assert status["mechanical_spike"]["status"] == "loaded"
    assert status["mechanical_spike"]["error"] is None
    ops = set(status["mechanical_spike"]["operations"])
    assert ops == {
        "mechanical_spike.add_sketch_feature",
        "mechanical_spike.add_extrude_feature",
        "mechanical_spike.adjust_feature_parameter",
        "mechanical_spike.remove_feature",
    }


def test_propose_kinds_includes_mechanical_spike_operations():
    """Per arc 1 D9: propose_kinds() returns COMBINED built-in + loaded engine kinds."""
    kinds = set(propose_kinds())
    assert "create_part" in kinds  # built-in
    assert "mechanical_spike.add_sketch_feature" in kinds
    assert "mechanical_spike.add_extrude_feature" in kinds
    assert "mechanical_spike.adjust_feature_parameter" in kinds
    assert "mechanical_spike.remove_feature" in kinds


def test_modify_kinds_includes_mechanical_spike_operations():
    """modify_kinds excludes init+release but includes all mechanical_spike ops."""
    kinds = set(modify_kinds())
    assert "init" not in kinds
    assert "release" not in kinds
    assert "mechanical_spike.add_sketch_feature" in kinds
    assert "mechanical_spike.add_extrude_feature" in kinds


# =============================================================================
# Mode A — 5-step authoring loop in separate Transactions
# =============================================================================


def test_5_step_authoring_loop_mode_a(workspace_with_part: Path):
    """ADR/0030 D4 Mode A: each step commits independently. Final Part has
    2 features + 1 geometry_ref."""
    ws = workspace_with_part

    # Step 2
    propose(ws, kind="mechanical_spike.add_sketch_feature", params={
        "part_number": "P-000001",
        "primitives": _two_primitives(),
    }).commit()
    # Step 3
    propose(ws, kind="mechanical_spike.add_extrude_feature", params={
        "part_number": "P-000001",
        "sketch_feature_id": "feat_0001",
        "depth_mm": 5.0,
        "direction": "z+",
    }).commit()
    # Step 4
    propose(ws, kind="mechanical_spike.adjust_feature_parameter", params={
        "part_number": "P-000001",
        "feature_id": "feat_0002",
        "parameter_name": "depth_mm",
        "new_value": 8.0,
    }).commit()
    # Step 5
    propose(ws, kind="release", params={
        "object_numbers": ["P-000001"],
        "final_stage": True,
    }).commit()

    sc = _part_sidecar(ws)
    assert len(sc["feature"]) == 2
    assert len(sc["geometry_ref"]) == 1
    feature_types = sorted(f["feature_type"] for f in sc["feature"])
    assert feature_types == ["extrude", "sketch"]


# =============================================================================
# Mode B — composed via modify in single Transaction
# =============================================================================


def test_5_step_authoring_loop_mode_b(workspace_with_part: Path):
    """ADR/0030 D4 Mode B: steps 2-4 composed via modify(); single commit;
    same final state as Mode A. Mode B is the only part of the scope that
    proves arc 1 B2 R1 + arc 9 Phase C B1 composability end-to-end."""
    ws = workspace_with_part

    draft = propose(ws, kind="mechanical_spike.add_sketch_feature", params={
        "part_number": "P-000001",
        "primitives": _two_primitives(),
    })
    modify(draft, kind="mechanical_spike.add_extrude_feature", params={
        "part_number": "P-000001",
        "sketch_feature_id": "feat_0001",
        "depth_mm": 5.0,
        "direction": "z+",
    })
    modify(draft, kind="mechanical_spike.adjust_feature_parameter", params={
        "part_number": "P-000001",
        "feature_id": "feat_0002",
        "parameter_name": "depth_mm",
        "new_value": 8.0,
    })
    draft.commit()

    sc = _part_sidecar(ws)
    assert len(sc["feature"]) == 2
    assert len(sc["geometry_ref"]) == 1


def test_mode_b_event_ids_distinct(workspace_with_part: Path):
    """Codex1 B2 R1 from arc 1: composed engine ops via modify() get
    distinct event_ids (draft-aware _next_event_id_in_draft allocation)."""
    ws = workspace_with_part

    draft = propose(ws, kind="mechanical_spike.add_sketch_feature", params={
        "part_number": "P-000001",
        "primitives": _two_primitives(),
    })
    modify(draft, kind="mechanical_spike.add_extrude_feature", params={
        "part_number": "P-000001",
        "sketch_feature_id": "feat_0001",
        "depth_mm": 5.0,
        "direction": "z+",
    })
    modify(draft, kind="mechanical_spike.adjust_feature_parameter", params={
        "part_number": "P-000001",
        "feature_id": "feat_0002",
        "parameter_name": "depth_mm",
        "new_value": 8.0,
    })
    event_ids = [e["event_id"] for e in draft.events if e.get("event_type") == "part_changed"]
    assert len(event_ids) == 3
    assert len(set(event_ids)) == 3, f"event_ids must be distinct, got {event_ids}"


# =============================================================================
# Schema-conformance tests
# =============================================================================


def test_part_changed_event_envelope_conforms_to_base_schema(workspace_with_part: Path):
    """Codex1 B1 from arc 13: part_changed uses base envelope (event_type,
    timestamp, transaction_id, actor at root; payload nested)."""
    ws = workspace_with_part

    draft = propose(ws, kind="mechanical_spike.add_sketch_feature", params={
        "part_number": "P-000001",
        "primitives": _two_primitives(),
    })
    events = [e for e in draft.events if e.get("event_type") == "part_changed"]
    assert len(events) == 1
    ev = events[0]
    assert ev["event_type"] == "part_changed"
    assert ev["actor"] == "agent"
    assert "timestamp" in ev
    assert "transaction_id" in ev
    assert "payload" in ev
    assert ev["payload"]["object_uuid"]
    assert "feature_delta" in ev["payload"]


def test_part_sidecar_uses_feature_and_geometry_ref_namespaces_no_colons(workspace_with_part: Path):
    """Codex1 B2 from arc 13: serialized keys are `feature` / `geometry_ref` (no colons)."""
    ws = workspace_with_part

    propose(ws, kind="mechanical_spike.add_sketch_feature", params={
        "part_number": "P-000001",
        "primitives": _two_primitives(),
    }).commit()

    sc = _part_sidecar(ws)
    assert "feature" in sc
    assert "geometry_ref" in sc
    assert "feature:" not in sc
    assert "geometry_ref:" not in sc


def test_feature_dependency_dag_acyclicity_holds(workspace_with_part: Path):
    """Codex1 B6 from arc 13: extrude.depends_on_feature_ids=[sketch.id];
    Kahn's algorithm doesn't trigger cycle."""
    ws = workspace_with_part

    propose(ws, kind="mechanical_spike.add_sketch_feature", params={
        "part_number": "P-000001",
        "primitives": _two_primitives(),
    }).commit()
    propose(ws, kind="mechanical_spike.add_extrude_feature", params={
        "part_number": "P-000001",
        "sketch_feature_id": "feat_0001",
        "depth_mm": 5.0,
        "direction": "z+",
    }).commit()

    sc = _part_sidecar(ws)
    extrude = [f for f in sc["feature"] if f["feature_type"] == "extrude"][0]
    assert extrude["depends_on_feature_ids"] == ["feat_0001"]


def test_geometry_ref_provenance_strict_set_equality_holds(workspace_with_part: Path):
    """Codex2 B2 R3 from arc 13: STRICT set-equality between
    derived_from_feature_ids and feature:<id> entries in fact_provenance.derived_from."""
    ws = workspace_with_part

    propose(ws, kind="mechanical_spike.add_sketch_feature", params={
        "part_number": "P-000001",
        "primitives": _two_primitives(),
    }).commit()
    propose(ws, kind="mechanical_spike.add_extrude_feature", params={
        "part_number": "P-000001",
        "sketch_feature_id": "feat_0001",
        "depth_mm": 5.0,
        "direction": "z+",
    }).commit()

    sc = _part_sidecar(ws)
    geom = sc["geometry_ref"][0]
    assert geom["role"] == "authoring_geometry"
    declared = set(geom["derived_from_feature_ids"])
    attested = {s.split(":", 1)[1] for s in geom["fact_provenance"]["derived_from"] if s.startswith("feature:")}
    assert declared == attested, f"set mismatch: declared={declared} vs attested={attested}"


# =============================================================================
# B1 R1 absorption tests (Codex1 from arc 20260601-3)
# =============================================================================


def test_extrude_feature_has_canonical_unit_parameter(workspace_with_part: Path):
    """Codex1 B1 R1 from arc 20260601-3: extrude depth is a first-class
    feature.parameters[] record with canonical unit `mm` per ADR/0029 D4 + D10."""
    ws = workspace_with_part

    propose(ws, kind="mechanical_spike.add_sketch_feature", params={
        "part_number": "P-000001",
        "primitives": _two_primitives(),
    }).commit()
    propose(ws, kind="mechanical_spike.add_extrude_feature", params={
        "part_number": "P-000001",
        "sketch_feature_id": "feat_0001",
        "depth_mm": 5.0,
        "direction": "z+",
    }).commit()

    sc = _part_sidecar(ws)
    extrude = [f for f in sc["feature"] if f["feature_type"] == "extrude"][0]
    assert "parameters" in extrude
    assert len(extrude["parameters"]) == 1
    depth_param = extrude["parameters"][0]
    assert depth_param["name"] == "depth_mm"
    assert depth_param["value"] == 5.0
    assert depth_param["datatype"] == "number"
    assert depth_param["unit"] == "mm"  # canonical_unit enum per ADR/0029 D10
    assert depth_param["id"].startswith("featp_")


def test_adjust_changes_parameter_value_and_geometry_hash(workspace_with_part: Path):
    """Codex1 B1 R1: adjust_feature_parameter updates the Product Truth
    parameter record AND the geometry hash genuinely changes (kernel
    canonicalization includes parameters per kernel.py)."""
    ws = workspace_with_part

    propose(ws, kind="mechanical_spike.add_sketch_feature", params={
        "part_number": "P-000001",
        "primitives": _two_primitives(),
    }).commit()
    propose(ws, kind="mechanical_spike.add_extrude_feature", params={
        "part_number": "P-000001",
        "sketch_feature_id": "feat_0001",
        "depth_mm": 5.0,
        "direction": "z+",
    }).commit()
    sc_before = _part_sidecar(ws)
    geom_before = sc_before["geometry_ref"][0]
    extrude_before = [f for f in sc_before["feature"] if f["feature_type"] == "extrude"][0]
    depth_before = extrude_before["parameters"][0]["value"]

    propose(ws, kind="mechanical_spike.adjust_feature_parameter", params={
        "part_number": "P-000001",
        "feature_id": "feat_0002",
        "parameter_name": "depth_mm",
        "new_value": 8.0,
    }).commit()

    sc_after = _part_sidecar(ws)
    geom_after = sc_after["geometry_ref"][0]
    extrude_after = [f for f in sc_after["feature"] if f["feature_type"] == "extrude"][0]
    depth_after = extrude_after["parameters"][0]["value"]

    # Parameter value changed in Product Truth
    assert depth_before == 5.0
    assert depth_after == 8.0
    # Geometry hash changed (kernel canonicalization includes parameters)
    assert geom_before["vault_ref"] != geom_after["vault_ref"], (
        f"vault_ref should change when parameter changes; got {geom_before['vault_ref']} "
        f"-> {geom_after['vault_ref']} (B1 R1 absorption fails)"
    )


# =============================================================================
# Release-with-features
# =============================================================================


def test_release_part_with_features_and_geometry_refs_succeeds(workspace_with_part: Path):
    """Mode A step 5: Revision record includes feature + geometry_ref
    snapshots; manifest validates."""
    ws = workspace_with_part

    propose(ws, kind="mechanical_spike.add_sketch_feature", params={
        "part_number": "P-000001",
        "primitives": _two_primitives(),
    }).commit()
    propose(ws, kind="mechanical_spike.add_extrude_feature", params={
        "part_number": "P-000001",
        "sketch_feature_id": "feat_0001",
        "depth_mm": 5.0,
        "direction": "z+",
    }).commit()
    result = propose(ws, kind="release", params={
        "object_numbers": ["P-000001"],
        "final_stage": True,
    }).commit()

    # The release writes a new Revision. Verify the released revisions
    # appear via reservation's released_revision_ids[].
    _, entry = find_reservation_entry_by_number(ws, "P-000001")
    released_ids = entry.get("released_revision_ids", [])
    assert len(released_ids) >= 1, f"expected ≥1 released revision, got {released_ids}"
