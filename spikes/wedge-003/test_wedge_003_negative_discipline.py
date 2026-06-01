"""Wedge-003 negative-discipline tests — 9 negative tests per ADR/0030 D12
(originally 8; +1 B6 binding-scan integration test added per Codex2 B1 R3
absorption from arc 20260601-3).

Forces the engine boundary discipline (set by arcs 12/13/1) to actually fire
in real engine emissions:
- Provenance discipline (D6 + Codex2 B2 R3 from arc 13)
- Cascade rejection (D8 + ADR/0029 D12)
- B6 binding scan (D9 + Codex1 B1 R1 from arc 2 + Codex2 N1 R2 from arc 2 +
  Codex2 B1 R3 from arc 20260601-3 — INTEGRATION test using real
  link_executed_on, not just unit-test of the classifier)
- Cross-Object form rejection (Codex2 B2 R3 from arc 13)
- Canonical units (ADR/0029 D10)
- Kernel failure → NativeEngineKernelError (arc 1 Q3)
- Never-installed engine_id (arc 2 N4 R1; not destructive uninstall)
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from aiadra_core.native_engine.exceptions import (
    EngineNotAvailableError,
    NativeEngineKernelError,
)
from aiadra_core.protocol import (
    modify,
    native_engine_status,
    propose,
    refresh_native_engines,
)
from aiadra_core.transaction.boundary import TransactionError
from aiadra_core.truth_model.reservation import find_reservation_entry_by_number
from aiadra_core.truth_model.sidecar import load_sidecar
from aiadra_core.validation.binding import RevisionBindingError
from aiadra_core.validation.bundle_registry import SchemaValidationError
from aiadra_core.validation.fold import FoldInconsistencyError
from aiadra_core.vault.local_fs import LocalFSVaultAdapter


@pytest.fixture(autouse=True)
def _ensure_spike_discovered():
    refresh_native_engines()
    status = native_engine_status()
    if "mechanical_spike" not in status or status["mechanical_spike"]["status"] != "loaded":
        pytest.skip(f"mechanical_spike not loaded: {status}")


@pytest.fixture
def workspace_with_extrude(tmp_path: Path) -> Path:
    """Workspace with a Part that has sketch + extrude features (good
    starting point for negative-discipline tests)."""
    ws = tmp_path / "ws"
    ws.mkdir()
    propose(ws, kind="init", params={}).commit()
    propose(ws, kind="create_part", params={
        "number": "P-000001",
        "name": "BracketSpike",
    }).commit()
    propose(ws, kind="mechanical_spike.add_sketch_feature", params={
        "part_number": "P-000001",
        "primitives": [
            {"type": "rectangle", "x_mm": 0.0, "y_mm": 0.0, "width_mm": 20.0, "height_mm": 10.0},
        ],
    }).commit()
    propose(ws, kind="mechanical_spike.add_extrude_feature", params={
        "part_number": "P-000001",
        "sketch_feature_id": "feat_0001",
        "depth_mm": 5.0,
        "direction": "z+",
    }).commit()
    return ws


def _part_sidecar(ws: Path) -> dict:
    _, entry = find_reservation_entry_by_number(ws, "P-000001")
    return load_sidecar(ws, entry["object_uuid"])


# =============================================================================
# 1. Cascade rejection (ADR/0030 D8 + ADR/0029 D12)
# =============================================================================


def test_cascade_rejects_remove_with_dependent_feature(workspace_with_extrude: Path):
    """ADR/0030 D8: removing feat_0001 (sketch) while feat_0002 (extrude)
    depends on it raises FoldInconsistencyError at draft.validate()."""
    ws = workspace_with_extrude
    draft = propose(ws, kind="mechanical_spike.remove_feature", params={
        "part_number": "P-000001",
        "feature_ids": ["feat_0001"],
    })
    # Cascade detection fires via the DAG-dangling-dependency check during fold.
    with pytest.raises(FoldInconsistencyError, match="depends_on_feature_ids"):
        draft.validate()


def test_cascade_accepts_batched_dependent_remove(workspace_with_extrude: Path):
    """ADR/0030 D8 + ADR/0029 D12: batched-cascade-remove (sketch + extrude
    + geometry_ref all in same event) succeeds."""
    ws = workspace_with_extrude
    sc = _part_sidecar(ws)
    geom_ids = [g["id"] for g in sc["geometry_ref"]]

    propose(ws, kind="mechanical_spike.remove_feature", params={
        "part_number": "P-000001",
        "feature_ids": ["feat_0001", "feat_0002"],
        "geometry_ref_ids": geom_ids,
    }).commit()

    sc_after = _part_sidecar(ws)
    assert sc_after.get("feature", []) == []
    assert sc_after.get("geometry_ref", []) == []


# =============================================================================
# 2. Provenance discipline (D6 + Codex2 B2 R3 from arc 13)
# =============================================================================


def test_engine_computed_provenance_blocks_human_input_on_feature(workspace_with_extrude: Path):
    """ADR/0029 D6: feature.fact_provenance.category MUST match actor
    (agent→ai_proposal). A synthetic part_changed event with
    category='human_input' while actor='agent' is fold-rejected.

    Tests the fold-level cross-check directly by constructing a malformed
    event via the low-level draft API (bypassing the well-behaved spike
    handler that always uses _provenance_category_for_actor).
    """
    ws = workspace_with_extrude
    from aiadra_core.transaction.boundary import TransactionDraft
    from aiadra_core.validation.bundle_registry import BundleRegistry

    bundle = BundleRegistry().bundle_for_pin(ws)
    _, entry = find_reservation_entry_by_number(ws, "P-000001")
    part_uuid = entry["object_uuid"]
    sc = load_sidecar(ws, part_uuid)

    # Synthetically craft a bad feature record (category mismatch with actor)
    bad_feature = {
        "id": "feat_9999",
        "name": "bad_synthetic",
        "feature_type": "sketch",
        "engine": "mechanical_spike",
        "adapter_schema_version": "0.1.0",
        "adapter_payload": {"primitives": [
            {"type": "circle", "cx_mm": 0.0, "cy_mm": 0.0, "radius_mm": 1.0},
        ]},
        "fact_provenance": {"category": "human_input"},  # mismatch with actor=agent
    }

    # Construct a draft directly (bypassing the spike handler) so we can
    # craft a synthetic event that the fold will reject at validate() time.
    draft = TransactionDraft(
        workspace=ws,
        bundle=bundle,
        kind="mechanical_spike.synthetic_misbehaving",
        transaction_id="tx_9999",
    )
    # Stage updated sidecar with the bad feature
    bad_sc = copy.deepcopy(sc)
    bad_sc.setdefault("feature", []).append(copy.deepcopy(bad_feature))
    draft.stage_sidecar(part_uuid, bad_sc)
    # Stage a synthetic part_changed event with actor=agent (cross-check should fail)
    draft.stage_event({
        "schema_version": bundle.bundle_version,
        "event_id": "evt_9999",
        "event_type": "part_changed",
        "timestamp": "2026-06-01T19:00:00Z",
        "transaction_id": "tx_9999",
        "actor": "agent",
        "payload": {
            "object_uuid": part_uuid,
            "feature_delta": {"added": [bad_feature]},
        },
    })
    with pytest.raises(FoldInconsistencyError, match="ai_proposal"):
        draft.validate()


def test_engine_computed_provenance_blocks_cross_object_address_form(workspace_with_extrude: Path):
    """Codex2 B2 R3 from arc 13: geometry_ref's fact_provenance.derived_from
    entries MUST use intra-Part canonical form `feature:<feat_id>`.
    Cross-Object form `<uuid>:feature:<id>` is REJECTED in v0.28.0."""
    ws = workspace_with_extrude
    from aiadra_core.transaction.boundary import TransactionDraft
    from aiadra_core.validation.bundle_registry import BundleRegistry

    bundle = BundleRegistry().bundle_for_pin(ws)
    _, entry = find_reservation_entry_by_number(ws, "P-000001")
    part_uuid = entry["object_uuid"]
    sc = load_sidecar(ws, part_uuid)

    # Synthetically craft a geometry_ref with cross-Object form in derived_from
    bad_geom = {
        "id": "geom_9999",
        "role": "authoring_geometry",
        "vault_ref": "sha256:" + "a" * 64,
        "derived_from_feature_ids": ["feat_0001"],
        "fact_provenance": {
            "category": "computed_result",
            "derived_from": [f"{part_uuid}:feature:feat_0001"],  # cross-Object form
        },
    }
    draft = TransactionDraft(
        workspace=ws,
        bundle=bundle,
        kind="mechanical_spike.synthetic_misbehaving",
        transaction_id="tx_9999",
    )
    bad_sc = copy.deepcopy(sc)
    bad_sc.setdefault("geometry_ref", []).append(copy.deepcopy(bad_geom))
    draft.stage_sidecar(part_uuid, bad_sc)
    draft.stage_event({
        "schema_version": bundle.bundle_version,
        "event_id": "evt_9999",
        "event_type": "part_changed",
        "timestamp": "2026-06-01T19:00:00Z",
        "transaction_id": "tx_9999",
        "actor": "agent",
        "payload": {
            "object_uuid": part_uuid,
            "geometry_ref_delta": {"added": [bad_geom]},
        },
    })
    with pytest.raises(FoldInconsistencyError, match="canonical"):
        draft.validate()


# =============================================================================
# 3. Canonical units enforcement (ADR/0029 D10)
# =============================================================================


def test_canonical_unit_enforced_on_feature_parameters(workspace_with_extrude: Path):
    """ADR/0029 D10: feature.parameters[].unit MUST be from canonical_unit
    enum. Engine emitting a parameter with unit='inches' is schema-rejected."""
    ws = workspace_with_extrude
    from aiadra_core.transaction.boundary import TransactionDraft
    from aiadra_core.validation.bundle_registry import BundleRegistry

    bundle = BundleRegistry().bundle_for_pin(ws)
    _, entry = find_reservation_entry_by_number(ws, "P-000001")
    part_uuid = entry["object_uuid"]
    sc = load_sidecar(ws, part_uuid)

    # Synthetic feature with non-canonical unit
    bad_feature = {
        "id": "feat_9999",
        "name": "bad_unit_synthetic",
        "feature_type": "extrude",
        "engine": "mechanical_spike",
        "adapter_schema_version": "0.1.0",
        "adapter_payload": {"sketch_feature_id": "feat_0001", "direction": "z+", "depth_parameter_id": "featp_9999"},
        "parameters": [{
            "id": "featp_9999",
            "name": "depth_inches",
            "value": 1.0,
            "datatype": "number",
            "unit": "inches",  # NOT in canonical_unit enum
        }],
        "fact_provenance": {"category": "ai_proposal"},
    }
    draft = TransactionDraft(
        workspace=ws,
        bundle=bundle,
        kind="mechanical_spike.synthetic_bad_unit",
        transaction_id="tx_9999",
    )
    bad_sc = copy.deepcopy(sc)
    bad_sc.setdefault("feature", []).append(copy.deepcopy(bad_feature))
    draft.stage_sidecar(part_uuid, bad_sc)
    draft.stage_event({
        "schema_version": bundle.bundle_version,
        "event_id": "evt_9999",
        "event_type": "part_changed",
        "timestamp": "2026-06-01T19:00:00Z",
        "transaction_id": "tx_9999",
        "actor": "agent",
        "payload": {
            "object_uuid": part_uuid,
            "feature_delta": {"added": [bad_feature]},
        },
    })
    # Schema validation catches this BEFORE fold (unit enum is schema-level).
    with pytest.raises(SchemaValidationError):
        draft.validate()


# =============================================================================
# 4. Kernel failure → NativeEngineKernelError (arc 1 Q3)
# =============================================================================


def test_native_engine_kernel_error_wraps_kernel_exception(workspace_with_extrude: Path, monkeypatch):
    """Arc 1 Codex Q3: synthetic kernel exception → adapter wraps as
    NativeEngineKernelError with __cause__ preserved + audit emission.

    Monkeypatches the kernel.compute_geometry to raise; verifies the
    dispatch adapter wraps the error correctly.
    """
    ws = workspace_with_extrude

    def crash(*args, **kwargs):
        raise ZeroDivisionError("synthetic kernel crash")

    # Monkeypatch the binding ALREADY imported into handlers.py (not the
    # kernel module's binding — handlers.py imported compute_geometry at
    # module load via `from .kernel import compute_geometry`).
    from aiadra_mechanical_spike import handlers
    monkeypatch.setattr(handlers, "compute_geometry", crash)

    with pytest.raises(NativeEngineKernelError) as excinfo:
        propose(ws, kind="mechanical_spike.adjust_feature_parameter", params={
            "part_number": "P-000001",
            "feature_id": "feat_0002",
            "parameter_name": "depth_mm",
            "new_value": 6.0,
        })
    assert excinfo.value.engine_id == "mechanical_spike"
    assert excinfo.value.operation_kind == "mechanical_spike.adjust_feature_parameter"
    assert isinstance(excinfo.value.__cause__, ZeroDivisionError)


# =============================================================================
# 5. Never-installed engine_id (arc 2 N4 R1)
# =============================================================================


def test_engine_not_available_for_never_installed_engine_id(workspace_with_extrude: Path):
    """Codex1 N4 R1 from arc 2: missing-engine test uses NEVER-INSTALLED
    engine_id (not destructive uninstall of the spike — preserves shared
    dev venv state)."""
    ws = workspace_with_extrude
    with pytest.raises(EngineNotAvailableError, match="not installed"):
        propose(ws, kind="totally_synthetic_engine_id.foo", params={"x": 1})


# =============================================================================
# 6. Domain validation (Codex1 N2 R1 from arc 20260601-3)
# =============================================================================


def test_handler_raises_transaction_error_for_bad_input(workspace_with_extrude: Path):
    """Codex1 N2 R1 from arc 20260601-3: bad operation inputs raise
    TransactionError (NOT bare ValueError → wrapped as kernel failure)."""
    ws = workspace_with_extrude
    # Bad direction
    with pytest.raises(TransactionError, match="direction"):
        propose(ws, kind="mechanical_spike.add_extrude_feature", params={
            "part_number": "P-000001",
            "sketch_feature_id": "feat_0001",
            "depth_mm": 5.0,
            "direction": "x+",  # invalid
        })
    # Missing required param
    with pytest.raises(TransactionError, match="missing required"):
        propose(ws, kind="mechanical_spike.add_sketch_feature", params={
            "part_number": "P-000001",
            # primitives missing
        })
    # Negative depth on add
    with pytest.raises(TransactionError, match="positive"):
        propose(ws, kind="mechanical_spike.add_extrude_feature", params={
            "part_number": "P-000001",
            "sketch_feature_id": "feat_0001",
            "depth_mm": -1.0,
            "direction": "z+",
        })


def test_adjust_rejects_non_positive_new_value(workspace_with_extrude: Path):
    """Codex2 N1 R3 from arc 20260601-3: depth-domain validation on adjust
    should also reject new_value <= 0 (mirror of add_extrude's check), so the
    adjust path doesn't accept domain-invalid values."""
    ws = workspace_with_extrude
    with pytest.raises(TransactionError, match="positive"):
        propose(ws, kind="mechanical_spike.adjust_feature_parameter", params={
            "part_number": "P-000001",
            "feature_id": "feat_0002",
            "parameter_name": "depth_mm",
            "new_value": -3.0,
        })
    with pytest.raises(TransactionError, match="positive"):
        propose(ws, kind="mechanical_spike.adjust_feature_parameter", params={
            "part_number": "P-000001",
            "feature_id": "feat_0002",
            "parameter_name": "depth_mm",
            "new_value": 0.0,
        })


# =============================================================================
# 7. B6 binding-scan INTEGRATION test (Codex2 B1 R3 from arc 20260601-3)
# =============================================================================


def _seed_attachment(workspace: Path, payload: bytes, att_id: str,
                     role: str = "source_authoring",
                     media_type: str = "application/octet-stream") -> dict:
    """Pre-stage Vault bytes + return attachment record. Mirrors aiadra-core
    test pattern (test_phase_c_propose_modify.py::_seed_attachment)."""
    vault = LocalFSVaultAdapter(workspace)
    content_hash, vault_path = vault.store(payload)
    return {
        "id": att_id, "role": role,
        "content_hash": content_hash, "vault_path": vault_path,
        "media_type": media_type,
    }


def _setup_test_procedure_and_execution(workspace: Path) -> None:
    """Create TestProcedure + TestExecution with minimal valid sidecars so
    link_executed_on can pin the Part's current unreleased revision."""
    propose(workspace, kind="create_test_procedure", params={
        "number": "TST-000001", "name": "ExtrudeDimensionCheck",
        "extra_namespaces": {
            "test_procedure": {"title": "Extrude dim check", "verification_method": "test"},
            "attachment": [_seed_attachment(
                workspace, b"PROCEDURE seed", "att_tst_seed",
                media_type="application/pdf",
            )],
        },
    }).commit()
    propose(workspace, kind="create_test_execution", params={
        "number": "TEX-000001", "name": "ExtrudeDimensionRun",
        "extra_namespaces": {
            "test_execution": {
                "executed_on_date": "2026-06-01",
                "execution_status": "completed",
            },
            "attachment": [_seed_attachment(
                workspace, b"INSTRON LOG seed", "att_tex_seed",
                media_type="text/csv",
            )],
            "parameter": [{
                "id": "param_measured", "name": "measured_depth_mm",
                "datatype": "number", "unit": "mm", "value": 5.0,
                "fact_provenance": {
                    "category": "measured",
                    "derived_from": ["attachment:att_tex_seed"],
                },
            }],
        },
    }).commit()


def test_b6_binding_scan_catches_mechanical_spike_mutation_against_unreleased_bound_revision(
    workspace_with_extrude: Path,
):
    """ADR/0030 D9 + Codex1 B1 R1 from arc 20260601-2 + Codex2 B1 R3 from arc
    20260601-3: bind the UNRELEASED current revision of Part P-000001 via
    Fixed execution-instance relationship (link_executed_on); then attempt
    `mechanical_spike.adjust_feature_parameter` and assert RevisionBindingError
    at draft.validate() (per Codex2 N1 R2 from arc 20260601-2: validate() /
    commit() timing, not propose() alone; arc 9 Phase C Codex2 B1 R3
    proposed-state B6 scan fires there).

    This INTEGRATION test (vs the synthetic-event unit tests above) proves:
        1. mechanical_spike.adjust_feature_parameter correctly emits
           `part_changed` (proving v0.28.0 schema integration)
        2. `part_changed` correctly participates in the B6 binding-scan
           classifier (proving arc 20260601-1 B3 R1 absorption is live for
           Native Engine emissions)
        3. The mutation prohibition fires at draft.validate() — Native Engine
           ops correctly participate in the dual-fold proposed-state B6 scan
           (per arc 9 Phase C Codex2 B1 R3)

    No release step in the negative test. The B6 rule blocks mutations
    against UNRELEASED current_revision_id that's fixed-bound — per the
    Phase 1 + Phase C reservation model release would allocate a fresh
    current_revision_id leaving the B6 scan moot.
    """
    ws = workspace_with_extrude
    # Setup: create TestProcedure + TestExecution fixtures
    _setup_test_procedure_and_execution(ws)
    # Bind Part's current unreleased revision via link_executed_on (Fixed
    # execution-instance binding per ADR/0022 §6)
    propose(ws, kind="link_executed_on", params={
        "source_number": "TEX-000001",
        "target_number": "P-000001",
    }).commit()
    # Now attempt the mutation. propose() returns the draft; B6 scan fires
    # at draft.validate() (per the dual-fold timing).
    draft = propose(ws, kind="mechanical_spike.adjust_feature_parameter", params={
        "part_number": "P-000001",
        "feature_id": "feat_0002",
        "parameter_name": "depth_mm",
        "new_value": 9.0,
    })
    with pytest.raises(RevisionBindingError):
        draft.validate()
