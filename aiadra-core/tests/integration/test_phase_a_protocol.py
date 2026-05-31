"""Phase A tests — `aiadra_core.protocol` submodule formalizing the Ring 2
agent-facing surface per ADR/0026 §"Sequencing" Phase A.

Per arc 20260531-7 Claude1+Codex1 absorptions:
- B1 (CLI delegation scope-limit): only `inspect`/`validate`/`release` (+
  `_run_draft` commit) route through `protocol.*`; create/change/link/attach
  CLI commands continue calling `transaction.operations.*` directly.
- B2 (locality/staleness API value classes): invalid → ValueError; recognized
  non-default → NotImplementedError.
- B3 (single Ring 2 pin failure contract): `ProjectPinError` wraps the three
  Phase 1 pin-related exceptions with original as `__cause__`.
- N2 (pure validate helper): `protocol.validate()` is pure; CLI does the emission.
- N3 (UUID-or-Number inspect): both lookup paths supported.
- N4 (commit equivalence): test via sentinel, not double-commit.
- N5 (RollbackResult.discarded_change_count): broader counter for all staged
  collections rather than events-only.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from aiadra_core import protocol
from aiadra_core.protocol import (
    CommitResult,
    ObjectNotFoundError,
    ObjectView,
    ProjectPinError,
    RollbackResult,
    TransactionDraft,
    ValidationOutcome,
    ValidationReport,
    commit,
    inspect,
    release,
    rollback,
    validate,
)
from aiadra_core.transaction.boundary import TransactionKind
from aiadra_core.transaction.operations import (
    create_object,
    init_workspace,
)
from aiadra_core.truth_model.reservation import find_reservation_entry_by_number
from aiadra_core.validation.bundle_registry import BundleRegistry
from aiadra_core.validation.migration import (
    REGISTERED_STEPS,
    apply_migration,
    plan_migration,
)


def _bundle_v0_24_0():
    return BundleRegistry().bundle("0.24.0")


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_phase_a_protocol_module_exports():
    """All Phase A symbols importable from `aiadra_core.protocol`."""
    # Operations
    assert callable(inspect)
    assert callable(validate)
    assert callable(commit)
    assert callable(rollback)
    assert callable(release)
    # Type shapes
    assert ObjectView is not None
    assert ValidationReport is not None
    assert ValidationOutcome is not None
    assert CommitResult is not None
    assert RollbackResult is not None
    assert TransactionDraft is not None
    # Exceptions
    assert issubclass(ObjectNotFoundError, KeyError)
    assert issubclass(ProjectPinError, ValueError)


def test_phase_a_protocol_does_not_export_future_phase_operations():
    """Per Codex1 Q7 (arc 20260531-7): don't stub future-phase operations.

    Updated for Phase B (arc 20260531-8): `query` is now exported. The
    remaining unimplemented operations (`propose`/`modify`/`simulate` Phase C;
    `explain` Phase D) MUST still be absent — their existence as
    `NotImplementedError` stubs would confuse agents.
    """
    for name in ("propose", "modify", "simulate", "explain"):
        assert not hasattr(protocol, name), (
            f"protocol.{name} should NOT exist (no future-op stubs per Codex Q7)"
        )


# ---------------------------------------------------------------------------
# inspect()
# ---------------------------------------------------------------------------


def _make_simple_workspace(tmp_path: Path) -> tuple[Path, str]:
    """Create a workspace + a Part; return (workspace, part_uuid)."""
    workspace = tmp_path / "ws"
    bundle = _bundle_v0_24_0()
    init_workspace(workspace, bundle).commit()
    d = create_object(
        workspace, bundle, "Part", "P-000001", "Bracket",
        extra_namespaces={
            "parameter": [{
                "id": "param_thickness", "name": "plate_thickness_mm",
                "datatype": "number", "unit": "mm", "value": 7,
                "fact_provenance": {"category": "human_input"},
            }],
        },
    )
    d.validate(); d.commit()
    _, entry = find_reservation_entry_by_number(workspace, "P-000001")
    return workspace, entry["object_uuid"]


def test_phase_a_inspect_returns_object_view(tmp_path: Path):
    workspace, part_uuid = _make_simple_workspace(tmp_path)
    view = inspect(workspace, "P-000001")
    assert isinstance(view, ObjectView)
    assert view.object_uuid == part_uuid
    assert view.object_number == "P-000001"
    assert view.object_type == "Part"
    assert view.bundle_version == "0.24.0"
    assert view.sidecar["object"]["uuid"] == part_uuid


def test_phase_a_inspect_by_uuid_returns_same_view(tmp_path: Path):
    """N3 absorption: inspect accepts UUID OR Number; returns canonical fields either way."""
    workspace, part_uuid = _make_simple_workspace(tmp_path)
    view_by_number = inspect(workspace, "P-000001")
    view_by_uuid = inspect(workspace, part_uuid)
    assert view_by_number.object_uuid == view_by_uuid.object_uuid
    assert view_by_number.object_number == view_by_uuid.object_number == "P-000001"


def test_phase_a_inspect_object_view_sidecar_is_independent_copy(tmp_path: Path):
    """Q1 absorption: ObjectView.sidecar is deep-copied so caller mutations
    don't affect subsequent re-reads."""
    workspace, _ = _make_simple_workspace(tmp_path)
    view = inspect(workspace, "P-000001")
    view.sidecar["parameter"][0]["value"] = 99999  # poison the returned dict
    view2 = inspect(workspace, "P-000001")
    assert view2.sidecar["parameter"][0]["value"] == 7  # original value


def test_phase_a_inspect_raises_object_not_found(tmp_path: Path):
    workspace, _ = _make_simple_workspace(tmp_path)
    with pytest.raises(ObjectNotFoundError):
        inspect(workspace, "P-999999")


def test_phase_a_inspect_raises_project_pin_error_on_missing_pin(tmp_path: Path):
    """B3 absorption: pin lookup failure → ProjectPinError with __cause__."""
    workspace = tmp_path / "ws_no_pin"
    workspace.mkdir()
    with pytest.raises(ProjectPinError) as excinfo:
        inspect(workspace, "P-000001")
    # __cause__ preserves original FileNotFoundError
    assert isinstance(excinfo.value.__cause__, FileNotFoundError)


# ---------------------------------------------------------------------------
# inspect() — locality / staleness API value classes (B2)
# ---------------------------------------------------------------------------


def test_phase_a_inspect_default_locality_staleness_pass(tmp_path: Path):
    """Default `always_local` + `any` work; behavior unchanged from Phase 1."""
    workspace, _ = _make_simple_workspace(tmp_path)
    # Explicit defaults
    view = inspect(workspace, "P-000001", locality="always_local", staleness="any")
    assert view.object_number == "P-000001"


def test_phase_a_inspect_locality_remote_only_attempts_fetch(tmp_path: Path):
    """Phase B (arc 20260531-8) replaces Phase A's NotImplementedError gate
    with actual `git fetch origin` behavior. In a remoteless test workspace
    the fetch fails and raises NetworkUnreachableError — proves the fetch
    path is wired through to network-failure handling."""
    from aiadra_core.protocol import NetworkUnreachableError
    workspace, _ = _make_simple_workspace(tmp_path)
    with pytest.raises(NetworkUnreachableError):
        inspect(workspace, "P-000001", locality="remote_only")


def test_phase_a_inspect_locality_local_if_fetched_attempts_fetch(tmp_path: Path):
    """Phase B: locality=local_if_fetched + no FETCH_HEAD → one fetch attempt
    per ADR/0001 §6 ("one fetch otherwise"). Fails in remoteless workspace."""
    from aiadra_core.protocol import NetworkUnreachableError
    workspace, _ = _make_simple_workspace(tmp_path / "ws_lif")
    with pytest.raises(NetworkUnreachableError):
        inspect(workspace, "P-000001", locality="local_if_fetched")


def test_phase_a_inspect_staleness_must_sync_attempts_fetch(tmp_path: Path):
    """Phase B: staleness=must_sync triggers fetch; fails in remoteless workspace."""
    from aiadra_core.protocol import NetworkUnreachableError
    workspace, _ = _make_simple_workspace(tmp_path)
    with pytest.raises(NetworkUnreachableError):
        inspect(workspace, "P-000001", staleness="must_sync")


def test_phase_a_inspect_staleness_fresh_within_attempts_fetch(tmp_path: Path):
    """Phase B: staleness=fresh_within_5m fetches if FETCH_HEAD missing/stale."""
    from aiadra_core.protocol import NetworkUnreachableError
    workspace, _ = _make_simple_workspace(tmp_path / "ws_fw")
    with pytest.raises(NetworkUnreachableError):
        inspect(workspace, "P-000001", staleness="fresh_within_5m")


def test_phase_a_inspect_invalid_locality_raises_value_error(tmp_path: Path):
    """B2: bogus locality value → ValueError (caller bug, NOT a future feature)."""
    workspace, _ = _make_simple_workspace(tmp_path)
    with pytest.raises(ValueError, match="Invalid locality"):
        inspect(workspace, "P-000001", locality="banana")


def test_phase_a_inspect_invalid_staleness_raises_value_error(tmp_path: Path):
    """B2: bogus staleness value → ValueError."""
    workspace, _ = _make_simple_workspace(tmp_path)
    with pytest.raises(ValueError, match="Invalid staleness"):
        inspect(workspace, "P-000001", staleness="banana")


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------


def test_phase_a_validate_returns_validation_report(tmp_path: Path):
    workspace, _ = _make_simple_workspace(tmp_path)
    report = validate(workspace)
    assert isinstance(report, ValidationReport)
    assert isinstance(report.outcomes, tuple)
    assert report.bundle_version == "0.24.0"
    # First outcome should be project_pin PASS
    assert report.outcomes[0].check_name == "project_pin"
    assert report.outcomes[0].result == "PASS"
    assert report.failures_count == 0


def test_phase_a_validate_raises_project_pin_error_on_missing_pin(tmp_path: Path):
    """B3: pin failure raises ProjectPinError with original as __cause__."""
    workspace = tmp_path / "ws_no_pin"
    workspace.mkdir()
    with pytest.raises(ProjectPinError) as excinfo:
        validate(workspace)
    assert isinstance(excinfo.value.__cause__, FileNotFoundError)


# ---------------------------------------------------------------------------
# commit() / rollback() (terminal family)
# ---------------------------------------------------------------------------


def test_phase_a_commit_wrapper_equivalent_to_method(monkeypatch):
    """N4 absorption: test commit-wrapper contract via sentinel, not double-commit."""
    sentinel = CommitResult(commit_hash="sentinel-hash", transaction_id="tx_0001", event_ids=["e1"])

    class FakeDraft:
        def commit(self):
            return sentinel

    fake = FakeDraft()
    assert commit(fake) is sentinel


def test_phase_a_rollback_clears_all_staged_collections(tmp_path: Path):
    """Q5 + N5 absorption: rollback clears all staged mutable collections;
    discarded_change_count sums events + sidecars + reservations + etc."""
    workspace = tmp_path / "ws"
    bundle = _bundle_v0_24_0()
    init_workspace(workspace, bundle).commit()
    # Build a draft via create_object; do NOT commit
    draft = create_object(
        workspace, bundle, "Part", "P-000099", "rollback test",
    )
    # Sanity: the draft has staged events + sidecar + reservation update
    pre_events = len(draft.events)
    pre_sidecars = len(draft.sidecar_writes)
    pre_reservations = len(draft.reservation_writes)
    assert pre_events > 0
    assert pre_sidecars > 0
    assert pre_reservations > 0

    expected_count = (
        pre_events + pre_sidecars + pre_reservations
        + len(draft.sidecar_deletes) + len(draft.revision_writes)
        + len(draft.manifest_writes) + len(draft.vault_writes)
    )

    result = rollback(draft, reason="testing rollback")
    assert isinstance(result, RollbackResult)
    assert result.reason == "testing rollback"
    assert result.transaction_id == draft.transaction_id
    assert result.discarded_change_count == expected_count

    # All collections cleared
    assert len(draft.events) == 0
    assert len(draft.sidecar_writes) == 0
    assert len(draft.sidecar_deletes) == 0
    assert len(draft.reservation_writes) == 0
    assert len(draft.revision_writes) == 0
    assert len(draft.manifest_writes) == 0
    assert len(draft.vault_writes) == 0
    assert draft.project_pin_write is None
    assert len(draft.commit_message_lines) == 0
    assert len(draft.pre_validate_hooks) == 0
    assert len(draft.post_validate_hooks) == 0


def test_phase_a_rollback_default_reason_is_none(tmp_path: Path):
    workspace = tmp_path / "ws"
    bundle = _bundle_v0_24_0()
    init_workspace(workspace, bundle).commit()
    draft = create_object(workspace, bundle, "Part", "P-000099", "test")
    result = rollback(draft)
    assert result.reason is None


# ---------------------------------------------------------------------------
# release() (re-export)
# ---------------------------------------------------------------------------


def test_phase_a_release_returns_transaction_draft(tmp_path: Path):
    """Q-implicit: protocol.release is a re-export; returns TransactionDraft."""
    workspace, _ = _make_simple_workspace(tmp_path)
    # Need a Requirement + link for a meaningful release
    bundle = _bundle_v0_24_0()
    d_r = create_object(
        workspace, bundle, "Requirement", "REQ-000001", "Bracket thickness",
        extra_namespaces={
            "requirement": {
                "statement": {"text": "Plate shall be 5mm thick",
                              "language": "en", "format": "freeform"},
                "category": "functional",
            },
            "acceptance_criterion": [{
                "id": "ac_min", "criterion": {"text": ">=5mm",
                                              "language": "en", "format": "freeform"},
            }],
        },
    )
    d_r.validate(); d_r.commit()
    draft = release(
        workspace, bundle, ["P-000001", "REQ-000001"],
        release_label="rev-A", stage_number=1, final_stage=True,
    )
    assert isinstance(draft, TransactionDraft)
    assert draft.kind == TransactionKind.RELEASE
    # Don't commit — we just check the return shape


# ---------------------------------------------------------------------------
# CLI thin-wrapper unchanged behavior (B1 scope-limited)
# ---------------------------------------------------------------------------


def test_phase_a_cli_inspect_unchanged_behavior(tmp_path: Path):
    """B1 scope-limited: `aiadra inspect` CLI delegates to protocol.inspect
    but preserves Phase 1 stdout shape + exit codes."""
    workspace, _ = _make_simple_workspace(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "aiadra_core.cli", "inspect",
         str(workspace), "P-000001"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert "P-000001" in result.stdout
    # Old CLI format: `# <number> (<uuid>)` then JSON
    assert result.stdout.startswith("# P-000001")


def test_phase_a_cli_inspect_unknown_object_exits_2(tmp_path: Path):
    workspace, _ = _make_simple_workspace(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "aiadra_core.cli", "inspect",
         str(workspace), "P-999999"],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "not found" in result.stderr.lower()


def test_phase_a_cli_validate_unchanged_behavior(tmp_path: Path):
    workspace, _ = _make_simple_workspace(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "aiadra_core.cli", "validate", str(workspace)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert "project_pin" in result.stdout
    assert "Summary:" in result.stdout


def test_phase_a_cli_validate_no_pin_exits_3(tmp_path: Path):
    workspace = tmp_path / "ws_no_pin"
    workspace.mkdir()
    result = subprocess.run(
        [sys.executable, "-m", "aiadra_core.cli", "validate", str(workspace)],
        capture_output=True, text=True,
    )
    assert result.returncode == 3
    assert "project pin" in result.stderr.lower() or "FAILED" in result.stderr


# ---------------------------------------------------------------------------
# Migrator v0.23.0 → v0.24.0 + chain v0.19.0 → v0.24.0
# ---------------------------------------------------------------------------


def test_phase_a_registered_steps_includes_v0_24_0():
    to_versions = [s.to_version for s in REGISTERED_STEPS]
    assert "0.24.0" in to_versions
    # Chain contiguity
    for i in range(len(REGISTERED_STEPS) - 1):
        assert REGISTERED_STEPS[i + 1].from_version == REGISTERED_STEPS[i].to_version


def test_phase_a_migrator_v0_23_0_to_v0_24_0_via_chain(tmp_path: Path):
    """Chain-aware migrator from Phase 3 picks up the new step trivially."""
    workspace = tmp_path / "ws"
    (workspace / ".aiadra").mkdir(parents=True)
    reg = BundleRegistry()
    v23 = reg.bundle("0.23.0")
    pin_text = f'"bundle_version": "0.23.0"\n"bundle_digest": "{v23.bundle_digest}"\n'
    (workspace / ".aiadra" / "schemas.yaml").write_bytes(pin_text.encode("utf-8"))

    plan = plan_migration(workspace, "0.24.0", reg)
    assert plan.from_bundle_version == "0.23.0"
    assert plan.to_bundle_version == "0.24.0"
    assert plan.pin_will_change is True

    applied = apply_migration(workspace, "0.24.0", reg)
    assert applied.to_bundle_version == "0.24.0"
    pin_after = (workspace / ".aiadra" / "schemas.yaml").read_text(encoding="utf-8")
    assert '"bundle_version": "0.24.0"' in pin_after
    v24 = reg.bundle("0.24.0")
    assert v24.bundle_digest in pin_after

    # Idempotent
    reapply = apply_migration(workspace, "0.24.0", reg)
    assert reapply.pin_will_change is False


def test_phase_a_chain_migration_v0_19_0_to_v0_24_0(tmp_path: Path):
    """Full 5-step chain (v0.19.0 → v0.20.0 → v0.21.0 → v0.22.0 → v0.23.0 → v0.24.0)
    written as ONE atomic pin write at chain end per Phase 3 D8 absorption."""
    workspace = tmp_path / "ws"
    (workspace / ".aiadra").mkdir(parents=True)
    reg = BundleRegistry()
    v19 = reg.bundle("0.19.0")
    pin_text = f'"bundle_version": "0.19.0"\n"bundle_digest": "{v19.bundle_digest}"\n'
    (workspace / ".aiadra" / "schemas.yaml").write_bytes(pin_text.encode("utf-8"))

    plan = plan_migration(workspace, "0.24.0", reg)
    notes_joined = " ".join(plan.notes)
    assert "Multi-step chain: 0.19.0 → 0.20.0 → 0.21.0 → 0.22.0 → 0.23.0 → 0.24.0" in notes_joined

    apply_migration(workspace, "0.24.0", reg)
    pin_after = (workspace / ".aiadra" / "schemas.yaml").read_text(encoding="utf-8")
    assert '"bundle_version": "0.24.0"' in pin_after
    # Intermediate versions NOT in final pin
    for v in ("0.19.0", "0.20.0", "0.21.0", "0.22.0", "0.23.0"):
        assert v not in pin_after


# ---------------------------------------------------------------------------
# End-to-end sanity: init + create + release + commit, all via protocol where applicable
# ---------------------------------------------------------------------------


def test_phase_a_end_to_end_via_protocol(tmp_path: Path):
    """init → create_object (direct) → protocol.release → protocol.commit."""
    workspace, _ = _make_simple_workspace(tmp_path)
    bundle = _bundle_v0_24_0()
    d_r = create_object(
        workspace, bundle, "Requirement", "REQ-000001", "Bracket thickness",
        extra_namespaces={
            "requirement": {
                "statement": {"text": "Plate shall be 5mm thick",
                              "language": "en", "format": "freeform"},
                "category": "functional",
            },
            "acceptance_criterion": [{
                "id": "ac_min", "criterion": {"text": ">=5mm",
                                              "language": "en", "format": "freeform"},
            }],
        },
    )
    d_r.validate()
    commit(d_r)  # protocol.commit
    rel_draft = release(
        workspace, bundle, ["P-000001", "REQ-000001"],
        release_label="rev-A", stage_number=1, final_stage=True,
    )
    rel_draft.validate()
    rel_result = commit(rel_draft)  # protocol.commit
    assert rel_result.commit_hash
