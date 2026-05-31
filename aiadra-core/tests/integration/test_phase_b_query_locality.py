"""Phase B tests — `query` cross-Object + non-default locality/staleness behavior.

Per ADR/0026 §"Sequencing" Phase B + arc 20260531-8 Claude1+Codex1 absorptions:
- B1 absorption: `query` returns BOTH working sidecars AND released Revisions
  from on-disk Release Manifests; ObjectView gains source/revision_id/release_label.
- B2 absorption: locality/staleness matrix per ADR/0001 §6 + ADR/0026 §4:
  - always_local+any: no fetch
  - remote_only: always fetch
  - must_sync: always fetch
  - fresh_within_<duration>: fetch iff FETCH_HEAD missing or older than duration
  - local_if_fetched: one fetch otherwise (ADR/0001 §6 "Free if pulled; one fetch otherwise")
  - Fetch failure (timeout / no remote / subprocess error / missing git) → NetworkUnreachableError
- B3 absorption: git fetch has bounded timeout (default 30s); TimeoutExpired → NetworkUnreachableError.
- N1: internal `predicate` rebind (no shadowing of builtin `filter`).
- N2: `_object_view_from_sidecar` helper shared by inspect + query.
- N3: deterministic ordering — working first by object_number, then released by (label, object_number).
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from aiadra_core import protocol
from aiadra_core.protocol import (
    NetworkUnreachableError,
    ObjectView,
    ProjectPinError,
    inspect,
    query,
)
from aiadra_core.transaction.operations import (
    create_object,
    init_workspace,
    link_relationship,
    release,
)
from aiadra_core.validation.bundle_registry import BundleRegistry
from aiadra_core.validation.migration import (
    REGISTERED_STEPS,
    apply_migration,
    plan_migration,
)


def _bundle_v0_25_0():
    return BundleRegistry().bundle("0.25.0")


def _make_part_workspace(tmp_path: Path) -> Path:
    """Init workspace + Part + Requirement; do NOT release."""
    workspace = tmp_path / "ws"
    bundle = _bundle_v0_25_0()
    init_workspace(workspace, bundle).commit()
    d_p = create_object(
        workspace, bundle, "Part", "P-000001", "Bracket",
        extra_namespaces={
            "parameter": [{
                "id": "param_thickness", "name": "plate_thickness_mm",
                "datatype": "number", "unit": "mm", "value": 7,
                "fact_provenance": {"category": "human_input"},
            }],
        },
    )
    d_p.validate(); d_p.commit()
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
    return workspace


def _make_released_workspace(tmp_path: Path) -> Path:
    """Init workspace + Part + Requirement + satisfies + release. Returns workspace
    with both working sidecars AND a manifest with released Revisions."""
    workspace = _make_part_workspace(tmp_path)
    bundle = _bundle_v0_25_0()
    d_link = link_relationship(workspace, bundle, "satisfies", "P-000001", "REQ-000001")
    d_link.validate(); d_link.commit()
    d_rel = release(
        workspace, bundle, ["P-000001", "REQ-000001"],
        release_label="rev-A", stage_number=1, final_stage=True,
    )
    d_rel.validate(); d_rel.commit()
    return workspace


# ---------------------------------------------------------------------------
# query — surface + module exports
# ---------------------------------------------------------------------------


def test_phase_b_protocol_exports_query_and_network_error():
    assert hasattr(protocol, "query")
    assert callable(protocol.query)
    assert hasattr(protocol, "NetworkUnreachableError")
    assert issubclass(NetworkUnreachableError, ConnectionError)


def test_phase_b_object_view_phase_b_fields_default_to_working():
    """Backward-compat: ObjectView without explicit source/revision_id/release_label
    defaults to source='working' so Phase A callers see no change."""
    view = ObjectView(
        object_uuid="01934567-89ab-7def-8123-456789abcdef",
        object_number="P-000001",
        object_type="Part",
        sidecar={"object": {}},
        bundle_version="0.25.0",
    )
    assert view.source == "working"
    assert view.revision_id is None
    assert view.release_label is None


# ---------------------------------------------------------------------------
# query — working-scope behavior (no released yet)
# ---------------------------------------------------------------------------


def test_phase_b_query_returns_all_working_objects(tmp_path: Path):
    workspace = _make_part_workspace(tmp_path)
    views = query(workspace)
    numbers = [v.object_number for v in views]
    assert numbers == ["P-000001", "REQ-000001"]  # sorted
    assert all(v.source == "working" for v in views)
    assert all(v.revision_id is None for v in views)
    assert all(v.release_label is None for v in views)


def test_phase_b_query_filter_by_kind(tmp_path: Path):
    workspace = _make_part_workspace(tmp_path)
    parts = query(workspace, kind="Part")
    assert [v.object_number for v in parts] == ["P-000001"]
    assert all(v.object_type == "Part" for v in parts)
    reqs = query(workspace, kind="Requirement")
    assert [v.object_number for v in reqs] == ["REQ-000001"]


def test_phase_b_query_unknown_kind_returns_empty_list(tmp_path: Path):
    workspace = _make_part_workspace(tmp_path)
    views = query(workspace, kind="NotARealType")
    assert views == []


def test_phase_b_query_filter_callable_predicate(tmp_path: Path):
    """N1 absorption: public `filter` works (internal `predicate` rebind
    avoids shadowing the builtin)."""
    workspace = _make_part_workspace(tmp_path)
    views = query(
        workspace, kind="Part",
        filter=lambda v: v.sidecar["object"]["lifecycle"] == "in_work",
    )
    assert len(views) == 1


def test_phase_b_query_returns_empty_when_filter_matches_nothing(tmp_path: Path):
    workspace = _make_part_workspace(tmp_path)
    views = query(workspace, filter=lambda v: v.object_type == "NotARealType")
    assert views == []


def test_phase_b_query_raises_project_pin_error_on_missing_pin(tmp_path: Path):
    workspace = tmp_path / "ws_no_pin"
    workspace.mkdir()
    with pytest.raises(ProjectPinError):
        query(workspace)


# ---------------------------------------------------------------------------
# Codex2 B1 absorption (arc 20260531-8 R3): query() fails LOUDLY on invalid
# Product Truth — does NOT silently skip corrupted sidecars / manifests /
# revisions. Silent skipping hides corrupted state from AI read consumers.
# ---------------------------------------------------------------------------


def test_phase_b_query_raises_on_invalid_working_sidecar_content(tmp_path: Path):
    """B1 absorption: query() does NOT silently skip a working sidecar that
    fails schema/profile validation. Agents need to know the substrate is
    corrupt before making downstream decisions."""
    from aiadra_core.validation.profile import ProfileViolationError
    from aiadra_core.validation.schema import SchemaValidationError
    workspace = _make_part_workspace(tmp_path)
    # Find and corrupt the Part's working.yaml on disk
    from aiadra_core.truth_model.sidecar import (
        list_working_sidecar_uuids, working_sidecar_path,
    )
    uuids = list_working_sidecar_uuids(workspace)
    assert uuids, "fixture should have at least one working sidecar"
    # Pick any sidecar; write invalid content (missing required `object` field)
    bad_path = working_sidecar_path(workspace, uuids[0])
    bad_path.write_text("not_an_object: true\n", encoding="utf-8")

    with pytest.raises((ProfileViolationError, SchemaValidationError)):
        query(workspace)


def test_phase_b_query_raises_on_invalid_released_revision_content(tmp_path: Path):
    """B1 absorption: query() does NOT silently skip a corrupted released
    Revision. Released Revisions are immutable canonical truth; corruption
    must surface immediately to AI read consumers."""
    from aiadra_core.validation.profile import ProfileViolationError
    from aiadra_core.validation.schema import SchemaValidationError
    workspace = _make_released_workspace(tmp_path)
    # Find a Revision file on disk and corrupt it
    from aiadra_core.truth_model.revision import revision_path
    from aiadra_core.truth_model.manifest import load_manifest, list_release_labels
    labels = list_release_labels(workspace)
    assert labels, "fixture should have at least one release manifest"
    manifest = load_manifest(workspace, labels[0])
    revs = manifest.get("revisions", [])
    assert revs, "manifest should reference at least one Revision"
    bad_path = revision_path(workspace, revs[0]["object_uuid"], revs[0]["revision_id"])
    bad_path.write_text("not_an_object: true\n", encoding="utf-8")

    with pytest.raises((ProfileViolationError, SchemaValidationError)):
        query(workspace)


def test_phase_b_query_raises_on_invalid_release_manifest_content(tmp_path: Path):
    """B1 absorption: query() does NOT silently skip a corrupted Release
    Manifest either. Defensive: covers the (path 2) silent-skip variant.

    Manifests are canonical JSON (per ADR/0002), so we write JSON that
    parses successfully but fails the manifest schema — exercising the
    schema-validation failure path the silent skip was hiding."""
    import json as _json
    from aiadra_core.validation.schema import SchemaValidationError
    workspace = _make_released_workspace(tmp_path)
    from aiadra_core.truth_model.manifest import (
        list_release_labels, manifest_path,
    )
    labels = list_release_labels(workspace)
    assert labels
    bad_path = manifest_path(workspace, labels[0])
    # Valid JSON; fails manifest schema (missing all required fields)
    bad_path.write_text(_json.dumps({"not_a_manifest": True}), encoding="utf-8")

    with pytest.raises(SchemaValidationError):
        query(workspace)


# ---------------------------------------------------------------------------
# query — B1: includes released Revisions from cumulative release graph
# ---------------------------------------------------------------------------


def test_phase_b_query_includes_released_revisions(tmp_path: Path):
    """B1 absorption: query covers BOTH working sidecars AND released Revisions
    from on-disk Release Manifests per ADR/0026 Phase B."""
    workspace = _make_released_workspace(tmp_path)
    views = query(workspace)
    sources = {v.source for v in views}
    assert "working" in sources
    assert "released_revision" in sources
    # At least 2 working (Part + Requirement) + 2 released (their Revisions)
    assert len(views) >= 4


def test_phase_b_query_released_views_carry_revision_id_and_release_label(tmp_path: Path):
    workspace = _make_released_workspace(tmp_path)
    released = [v for v in query(workspace) if v.source == "released_revision"]
    assert released, "expected at least one released_revision view"
    for v in released:
        assert v.revision_id is not None
        assert v.release_label == "rev-A"


def test_phase_b_query_kind_filter_applies_to_released_too(tmp_path: Path):
    workspace = _make_released_workspace(tmp_path)
    released_parts = [
        v for v in query(workspace, kind="Part") if v.source == "released_revision"
    ]
    assert len(released_parts) == 1
    assert released_parts[0].object_number == "P-000001"
    assert released_parts[0].release_label == "rev-A"


def test_phase_b_query_deterministic_ordering(tmp_path: Path):
    """N3 absorption: deterministic ordering — working sorted by object_number,
    then released sorted by (release_label, object_number)."""
    workspace = _make_released_workspace(tmp_path)
    views = query(workspace)
    # Working views come first, sorted by object_number
    working = [v for v in views if v.source == "working"]
    working_numbers = [v.object_number for v in working]
    assert working_numbers == sorted(working_numbers)
    # Released views come after, sorted by object_number within release_label
    released = [v for v in views if v.source == "released_revision"]
    released_numbers = [v.object_number for v in released]
    assert released_numbers == sorted(released_numbers)


# ---------------------------------------------------------------------------
# Locality/staleness — invalid API value gate (Phase A behavior preserved)
# ---------------------------------------------------------------------------


def test_phase_b_query_invalid_locality_raises_value_error(tmp_path: Path):
    workspace = _make_part_workspace(tmp_path)
    with pytest.raises(ValueError, match="Invalid locality"):
        query(workspace, locality="banana")


def test_phase_b_query_invalid_staleness_raises_value_error(tmp_path: Path):
    workspace = _make_part_workspace(tmp_path)
    with pytest.raises(ValueError, match="Invalid staleness"):
        query(workspace, staleness="banana")


def test_phase_b_query_invalid_fresh_within_format_raises_value_error(tmp_path: Path):
    workspace = _make_part_workspace(tmp_path)
    with pytest.raises(ValueError, match="Invalid staleness"):
        query(workspace, staleness="fresh_within_5x")  # bad unit
    with pytest.raises(ValueError, match="Invalid staleness"):
        query(workspace, staleness="fresh_within_abc")  # not numeric


def test_phase_b_query_zero_or_negative_fresh_within_raises_value_error(tmp_path: Path):
    """Codex1 Q5 absorption: reject zero / negative durations."""
    workspace = _make_part_workspace(tmp_path)
    with pytest.raises(ValueError, match="must be positive"):
        query(workspace, staleness="fresh_within_0s")


# ---------------------------------------------------------------------------
# Locality/staleness — fetch matrix (B2 absorption)
# ---------------------------------------------------------------------------


def test_phase_b_query_default_no_fetch(tmp_path: Path):
    """always_local + any: no fetch should be triggered."""
    workspace = _make_part_workspace(tmp_path)
    with patch("aiadra_core.protocol._run_git_fetch") as mock_fetch:
        query(workspace)  # defaults
        mock_fetch.assert_not_called()


def test_phase_b_query_remote_only_triggers_fetch(tmp_path: Path):
    workspace = _make_part_workspace(tmp_path)
    with patch("aiadra_core.protocol._run_git_fetch") as mock_fetch:
        query(workspace, locality="remote_only")
        mock_fetch.assert_called_once()


def test_phase_b_query_must_sync_triggers_fetch(tmp_path: Path):
    workspace = _make_part_workspace(tmp_path)
    with patch("aiadra_core.protocol._run_git_fetch") as mock_fetch:
        query(workspace, staleness="must_sync")
        mock_fetch.assert_called_once()


def test_phase_b_query_local_if_fetched_no_fetch_head_triggers_fetch(tmp_path: Path):
    """ADR/0001 §6 "one fetch otherwise" — local_if_fetched with no FETCH_HEAD
    triggers one fetch."""
    workspace = _make_part_workspace(tmp_path)
    fetch_head = workspace / ".git" / "FETCH_HEAD"
    if fetch_head.exists():
        fetch_head.unlink()
    with patch("aiadra_core.protocol._run_git_fetch") as mock_fetch:
        query(workspace, locality="local_if_fetched")
        mock_fetch.assert_called_once()


def test_phase_b_query_local_if_fetched_with_fetch_head_no_fetch(tmp_path: Path):
    """ADR/0001 §6 "Free if pulled" — local_if_fetched with existing
    FETCH_HEAD is a no-op (no fetch)."""
    workspace = _make_part_workspace(tmp_path)
    fetch_head = workspace / ".git" / "FETCH_HEAD"
    fetch_head.touch()
    with patch("aiadra_core.protocol._run_git_fetch") as mock_fetch:
        query(workspace, locality="local_if_fetched")
        mock_fetch.assert_not_called()


def test_phase_b_query_fresh_within_recent_no_fetch(tmp_path: Path):
    """Recent FETCH_HEAD within `fresh_within_X` → no fetch."""
    workspace = _make_part_workspace(tmp_path)
    fetch_head = workspace / ".git" / "FETCH_HEAD"
    fetch_head.touch()  # mtime ≈ now
    with patch("aiadra_core.protocol._run_git_fetch") as mock_fetch:
        query(workspace, staleness="fresh_within_5m")
        mock_fetch.assert_not_called()


def test_phase_b_query_fresh_within_stale_triggers_fetch(tmp_path: Path):
    """Stale FETCH_HEAD older than `fresh_within_X` → triggers fetch."""
    workspace = _make_part_workspace(tmp_path)
    fetch_head = workspace / ".git" / "FETCH_HEAD"
    fetch_head.touch()
    # Backdate mtime to 1 hour ago
    one_hour_ago = time.time() - 3600
    import os as _os
    _os.utime(fetch_head, (one_hour_ago, one_hour_ago))
    with patch("aiadra_core.protocol._run_git_fetch") as mock_fetch:
        query(workspace, staleness="fresh_within_5m")
        mock_fetch.assert_called_once()


def test_phase_b_query_fresh_within_missing_fetch_head_triggers_fetch(tmp_path: Path):
    """Missing FETCH_HEAD + fresh_within_X → triggers fetch."""
    workspace = _make_part_workspace(tmp_path)
    fetch_head = workspace / ".git" / "FETCH_HEAD"
    if fetch_head.exists():
        fetch_head.unlink()
    with patch("aiadra_core.protocol._run_git_fetch") as mock_fetch:
        query(workspace, staleness="fresh_within_5m")
        mock_fetch.assert_called_once()


# ---------------------------------------------------------------------------
# Locality/staleness — fetch failure → NetworkUnreachableError
# ---------------------------------------------------------------------------


def test_phase_b_query_fetch_failure_raises_network_unreachable(tmp_path: Path):
    """Real subprocess call on remoteless workspace fails → NetworkUnreachableError."""
    workspace = _make_part_workspace(tmp_path)
    with pytest.raises(NetworkUnreachableError):
        query(workspace, locality="remote_only")


def test_phase_b_query_fetch_timeout_raises_network_unreachable(tmp_path: Path):
    """B3 absorption: TimeoutExpired → NetworkUnreachableError. Mock subprocess.run
    to raise TimeoutExpired (without touching real network)."""
    workspace = _make_part_workspace(tmp_path)
    fake_timeout = subprocess.TimeoutExpired(cmd=["git", "fetch", "origin"], timeout=30)
    with patch("aiadra_core.protocol.subprocess.run", side_effect=fake_timeout):
        with pytest.raises(NetworkUnreachableError, match="timed out"):
            query(workspace, staleness="must_sync")


def test_phase_b_query_fetch_missing_git_raises_network_unreachable(tmp_path: Path):
    """B3 absorption: FileNotFoundError (no git binary) → NetworkUnreachableError."""
    workspace = _make_part_workspace(tmp_path)
    with patch("aiadra_core.protocol.subprocess.run",
               side_effect=FileNotFoundError("git")):
        with pytest.raises(NetworkUnreachableError, match="git binary not found"):
            query(workspace, locality="remote_only")


def test_phase_b_inspect_remote_only_triggers_fetch_too(tmp_path: Path):
    """Codex1 Q9: Phase B unlocks non-default locality/staleness on inspect too,
    not just query."""
    workspace = _make_part_workspace(tmp_path)
    with patch("aiadra_core.protocol._run_git_fetch") as mock_fetch:
        try:
            inspect(workspace, "P-000001", locality="remote_only")
        except Exception:
            pass  # we only care fetch was attempted
        mock_fetch.assert_called_once()


def test_phase_b_inspect_succeeds_when_fetch_mocked(tmp_path: Path):
    """End-to-end: with fetch mocked to succeed, non-default locality/staleness
    returns the ObjectView normally."""
    workspace = _make_part_workspace(tmp_path)
    with patch("aiadra_core.protocol._run_git_fetch") as mock_fetch:
        mock_fetch.return_value = None
        view = inspect(workspace, "P-000001", staleness="must_sync")
        assert view.object_number == "P-000001"
        mock_fetch.assert_called_once()


# ---------------------------------------------------------------------------
# Migrator v0.24.0 → v0.25.0 + chain
# ---------------------------------------------------------------------------


def test_phase_b_registered_steps_includes_v0_25_0():
    to_versions = [s.to_version for s in REGISTERED_STEPS]
    assert "0.25.0" in to_versions
    for i in range(len(REGISTERED_STEPS) - 1):
        assert REGISTERED_STEPS[i + 1].from_version == REGISTERED_STEPS[i].to_version


def test_phase_b_migrator_v0_24_0_to_v0_25_0_via_chain(tmp_path: Path):
    workspace = tmp_path / "ws"
    (workspace / ".aiadra").mkdir(parents=True)
    reg = BundleRegistry()
    v24 = reg.bundle("0.24.0")
    pin_text = f'"bundle_version": "0.24.0"\n"bundle_digest": "{v24.bundle_digest}"\n'
    (workspace / ".aiadra" / "schemas.yaml").write_bytes(pin_text.encode("utf-8"))

    plan = plan_migration(workspace, "0.25.0", reg)
    assert plan.from_bundle_version == "0.24.0"
    assert plan.to_bundle_version == "0.25.0"
    assert plan.pin_will_change is True

    apply_migration(workspace, "0.25.0", reg)
    pin_after = (workspace / ".aiadra" / "schemas.yaml").read_text(encoding="utf-8")
    assert '"bundle_version": "0.25.0"' in pin_after
    v25 = reg.bundle("0.25.0")
    assert v25.bundle_digest in pin_after


def test_phase_b_chain_migration_v0_19_0_to_v0_25_0(tmp_path: Path):
    """Full 6-step chain (v0.19.0 → ... → v0.25.0) via single atomic pin write."""
    workspace = tmp_path / "ws"
    (workspace / ".aiadra").mkdir(parents=True)
    reg = BundleRegistry()
    v19 = reg.bundle("0.19.0")
    pin_text = f'"bundle_version": "0.19.0"\n"bundle_digest": "{v19.bundle_digest}"\n'
    (workspace / ".aiadra" / "schemas.yaml").write_bytes(pin_text.encode("utf-8"))

    plan = plan_migration(workspace, "0.25.0", reg)
    notes_joined = " ".join(plan.notes)
    assert "0.19.0 → 0.20.0 → 0.21.0 → 0.22.0 → 0.23.0 → 0.24.0 → 0.25.0" in notes_joined

    apply_migration(workspace, "0.25.0", reg)
    pin_after = (workspace / ".aiadra" / "schemas.yaml").read_text(encoding="utf-8")
    assert '"bundle_version": "0.25.0"' in pin_after
    for v in ("0.19.0", "0.20.0", "0.21.0", "0.22.0", "0.23.0", "0.24.0"):
        assert v not in pin_after
