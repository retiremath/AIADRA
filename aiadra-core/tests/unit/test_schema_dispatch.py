"""Bundle index dispatch correctness.

Per ADR/0003 §2: `(bundle_version, artifact_kind, discriminator) → schema_path`.
The nested `lookups[artifact_kind][discriminator]` shape is the Phase 0 form
per Codex1 N2 absorption arc 20260531-1.
"""
from __future__ import annotations

import pytest

from aiadra_core.validation.schema import (
    SchemaValidationError,
    load_index,
    packaged_bundle_dir,
    resolve_schema_path,
)


def test_packaged_bundle_index_has_v0_19_0():
    bundle = packaged_bundle_dir("0.19.0")
    index = load_index(bundle)
    assert index["bundle_version"] == "0.19.0"
    assert "lookups" in index


def test_resolve_sidecar_part():
    bundle = packaged_bundle_dir("0.19.0")
    path = resolve_schema_path(bundle, "sidecar", "Part")
    assert path == "object/part.schema.json"


def test_resolve_every_v_and_v_object_type():
    bundle = packaged_bundle_dir("0.19.0")
    for t in ["Part", "Requirement", "TestProcedure", "TestExecution", "EvidenceArtifact"]:
        assert resolve_schema_path(bundle, "sidecar", t).startswith("object/")
        assert resolve_schema_path(bundle, "revision", t).startswith("object/")


def test_resolve_every_event_type():
    bundle = packaged_bundle_dir("0.19.0")
    expected = [
        "part_created", "requirement_created", "test_procedure_created",
        "test_execution_created", "evidence_artifact_created",
        "relationship_created", "parameter_changed",
        "part_released", "requirement_released", "test_procedure_released",
        "test_execution_released", "evidence_artifact_released",
    ]
    for et in expected:
        path = resolve_schema_path(bundle, "event", et)
        assert path == f"event/{et}.schema.json"


def test_resolve_every_reservation_prefix():
    bundle = packaged_bundle_dir("0.19.0")
    for prefix in ["P", "REQ", "TST", "TEX", "EVD"]:
        path = resolve_schema_path(bundle, "reservation", prefix)
        assert path == f"reservation/{prefix}.schema.json"


def test_resolve_unknown_artifact_kind_raises():
    bundle = packaged_bundle_dir("0.19.0")
    with pytest.raises(SchemaValidationError):
        resolve_schema_path(bundle, "nonexistent", "X")


def test_resolve_unknown_discriminator_raises():
    bundle = packaged_bundle_dir("0.19.0")
    with pytest.raises(SchemaValidationError):
        resolve_schema_path(bundle, "sidecar", "NotAType")


# Per Codex2 B2 absorption arc 20260531-1: validation traverses event/_base.schema.json
# via allOf+$ref. The test exercises both directions — a valid event passes,
# a malformed event missing a base-required field fails with an error that
# names the base-level constraint.


def _minimal_part_released_event() -> dict:
    return {
        "schema_version": "0.19.0",
        "event_id": "evt_0001",
        "event_type": "part_released",
        "timestamp": "2026-05-31T00:00:00Z",
        "transaction_id": "tx_0001",
        "payload": {
            "object_uuid": "0193abcd-1234-7890-abcd-111111111111",
            "revision_id": "0193abcd-1234-7890-abcd-aaaaaaaaaaa1",
            "revision_hash": "sha256:" + "a" * 64,
        },
    }


def test_event_validates_via_base_schema_ref():
    """Valid event passes — allOf [{$ref: _base.schema.json}] resolves cleanly."""
    from aiadra_core.validation.schema import validate_event
    bundle = packaged_bundle_dir("0.19.0")
    validate_event(_minimal_part_released_event(), bundle)


def test_event_missing_base_required_field_fails():
    """Per Codex2 B2: cross-event invariant from _base.schema.json (e.g.
    `transaction_id` REQUIRED) is enforced via the $ref. A malformed event
    missing `transaction_id` MUST fail validation."""
    from aiadra_core.validation.schema import SchemaValidationError, validate_event
    bundle = packaged_bundle_dir("0.19.0")
    event = _minimal_part_released_event()
    del event["transaction_id"]
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_event(event, bundle)
    assert "transaction_id" in str(exc_info.value)


def test_event_bad_base_pattern_fails():
    """Per Codex2 B2: base pattern constraints (e.g. `event_id` matches `^evt_[0-9]{4}$`)
    are enforced via the $ref."""
    from aiadra_core.validation.schema import SchemaValidationError, validate_event
    bundle = packaged_bundle_dir("0.19.0")
    event = _minimal_part_released_event()
    event["event_id"] = "BAD_EVENT_ID_NOT_MATCHING_PATTERN"
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_event(event, bundle)
    assert "event_id" in str(exc_info.value) or "pattern" in str(exc_info.value).lower()
