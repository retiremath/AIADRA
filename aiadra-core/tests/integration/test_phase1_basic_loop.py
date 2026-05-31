"""End-to-end Phase 1 test: init + create + link + release via aiadra-core API.

Reproduces the Wedge-001 basic loop (Part + Requirement + satisfies + release)
using the Phase 1 Transaction model + BundleRegistry + v0.20.0 bundle. Proves:
- bundle_registry pins fresh workspaces to v0.20.0
- create_object Transaction allocates Number + UUID + current_revision_id
- link_relationship works for Float bindings (satisfies)
- release Transaction emits release_staged + per-Object <type>_released events
- N6: release allocates fresh current_revision_id + appends released to history
- validate sees all artifacts after release

Does NOT cover the full V&V chain (execution-instance Fixed bindings + attachments
+ stage-closure check). That's a deferred test for Codex review or Claude5.
"""
from __future__ import annotations

from pathlib import Path

from aiadra_core.cli.validate import run_validate
from aiadra_core.transaction.operations import (
    create_object,
    init_workspace,
    link_relationship,
    release,
)
from aiadra_core.truth_model.reservation import (
    find_reservation_entry_by_number,
    load_reservation,
)
from aiadra_core.validation.bundle_registry import BundleRegistry


def test_phase1_init_create_link_release(tmp_path: Path) -> None:
    """Single Transaction-by-Transaction test of the basic Phase 1 path."""
    workspace = tmp_path / "ws"
    registry = BundleRegistry()
    bundle = registry.latest()
    assert bundle.bundle_version == "0.20.0"

    # 1. init
    draft = init_workspace(workspace, bundle)
    draft.validate()
    draft.commit()
    # init writes the pin file directly; verify it exists
    assert (workspace / ".aiadra" / "schemas.yaml").exists()

    # 2. create Part + Requirement
    draft_p = create_object(workspace, bundle, "Part", "P-000001", "Drive bracket",
                              extra_namespaces={
                                  "parameter": [
                                      {"id": "param_thickness", "name": "plate_thickness_mm",
                                       "datatype": "number", "unit": "mm", "value": 7,
                                       "fact_provenance": {"category": "human_input"}}
                                  ]
                              })
    draft_p.validate()
    draft_p.commit()

    draft_r = create_object(workspace, bundle, "Requirement", "REQ-000001", "Bracket thickness",
                              extra_namespaces={
                                  "requirement": {
                                      "statement": {
                                          "text": "Bracket plate shall be at least 5mm thick",
                                          "language": "en",
                                          "format": "freeform",
                                      },
                                      "category": "functional",
                                  },
                                  "acceptance_criterion": [
                                      {"id": "ac_min_thickness",
                                       "criterion": {"text": "plate_thickness_mm shall be at least 5",
                                                    "language": "en",
                                                    "format": "freeform"}}
                                  ],
                              })
    draft_r.validate()
    draft_r.commit()

    # Verify Reservations allocated current_revision_id per B3
    p_entry = find_reservation_entry_by_number(workspace, "P-000001")
    assert p_entry is not None
    assert p_entry[1].get("current_revision_id"), "B3: current_revision_id allocated at create-time"

    # 3. link satisfies (Float binding; no revision_id needed at link time)
    draft_link = link_relationship(workspace, bundle, "satisfies", "P-000001", "REQ-000001")
    draft_link.validate()
    draft_link.commit()

    # 4. release both Objects (single-stage)
    pre_release_p_rev = p_entry[1]["current_revision_id"]
    draft_rel = release(workspace, bundle, ["P-000001", "REQ-000001"],
                         release_label="rev-A", stage_number=1, final_stage=True)
    outcomes = draft_rel.validate()
    assert outcomes  # validate_release_draft ran via pre_validate_hook
    result = draft_rel.commit()
    assert result.commit_hash, "release commit must produce git commit hash"
    # Expect 3 events: 2 <type>_released + 1 release_staged
    assert len(result.event_ids) == 3

    # 5. Verify N6: released_revision_ids[] contains the pre-release rev_id;
    #    current_revision_id is a fresh UUID (not the pre-release one).
    p_after = find_reservation_entry_by_number(workspace, "P-000001")
    assert p_after is not None
    p_after_entry = p_after[1]
    assert pre_release_p_rev in (p_after_entry.get("released_revision_ids") or [])
    assert p_after_entry.get("current_revision_id") != pre_release_p_rev, \
        "N6: release allocates fresh current_revision_id"

    # 6. validate workspace end-to-end
    rc = run_validate(workspace)
    assert rc == 0, f"workspace validate failed; rc={rc}"


def test_phase1_bundle_registry_lists_both_bundles() -> None:
    """B2: BundleRegistry resolves both v0.19.0 and v0.20.0 bundles."""
    registry = BundleRegistry()
    versions = registry.versions()
    assert "0.19.0" in versions
    assert "0.20.0" in versions
    assert registry.latest().bundle_version == "0.20.0"


def test_phase1_archival_read_v0_19_0_fixture_against_v0_20_0_registry(tmp_path: Path) -> None:
    """B2: an artifact carrying schema_version 0.19.0 validates against v0.19.0
    bundle even though v0.20.0 is the latest packaged bundle (archival read)."""
    from aiadra_core.validation.schema import load_sidecar_validated

    # Use the existing Wedge-002 fixture (pinned to v0.19.0)
    fixture = Path(__file__).parent.parent / "fixtures" / "wedge_002"
    # Load + validate the Part working sidecar — should succeed via archival path
    sidecar = load_sidecar_validated(
        fixture, "0193abcd-1234-7890-abcd-111111111111"
    )
    assert sidecar["object"]["schema_version"] == "0.19.0"
    assert sidecar["object"]["number"] == "P-000058"
