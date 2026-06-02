"""Phase 3 W3 SCN tests — per-relationship-type schemas + bundle lookup
namespace keyed by relationship `type`; bundle v0.21.0 → v0.22.0.

Per ADR/0025 §9 + arc 20260531-4 Claude1+Codex1 absorptions:
- B1 ordering: dispatch checks bundle schema existence FIRST, then per-source
  Object Type allow-list (so unknown types yield "no schema" and known-but-
  disallowed types yield "not allowed on Object Type").
- D8: chain-aware migrator (multi-step writes pin once atomically at end).
- D10 + Codex addition: distinct error messages for unknown-type vs disallowed-type.
"""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from aiadra_core.validation.bundle_registry import (
    BundleRegistry,
    SchemaValidationError,
)
from aiadra_core.validation.migration import (
    MigrationError,
    REGISTERED_STEPS,
    apply_migration,
    plan_migration,
)


def _bundle_v0_22_0():
    return BundleRegistry().bundle("0.22.0")


def _make_uuid() -> str:
    return str(uuid4())


def _object_block(type_: str, number: str, name: str) -> dict:
    return {
        "uuid": _make_uuid(),
        "number": number,
        "type": type_,
        "name": name,
        "lifecycle": "in_work",
        "schema_version": "0.22.0",
    }


def _attachment_record(id_: str, content_hash_hex: str) -> dict:
    return {
        "id": id_,
        "role": "source_authoring",
        "media_type": "application/octet-stream",
        "vault_path": f"vault/{id_}/bytes",
        "content_hash": "sha256:" + content_hash_hex,
    }


def _minimal_part_sidecar(*, relationships: list[dict] | None = None) -> dict:
    """Minimal Part sidecar conformant to v0.22.0 Object schema.

    Note: top-level `parameter` and `relationship` are OPTIONAL on Part but
    if present must satisfy minItems 1; we omit `parameter` entirely and
    include `relationship` only when callers supply records.
    """
    sc: dict = {"object": _object_block("Part", "P-000001", "Bracket")}
    if relationships:
        sc["relationship"] = relationships
    return sc


def _minimal_test_procedure_sidecar(*, relationships: list[dict] | None = None) -> dict:
    sc: dict = {
        "object": _object_block("TestProcedure", "TST-000001", "Bracket bend test"),
        "test_procedure": {
            "title": "Bracket bend test",
            "verification_method": "test",
        },
        "attachment": [_attachment_record("att_tst_000001_proc", "0" * 64)],
    }
    if relationships:
        sc["relationship"] = relationships
    return sc


def _minimal_evidence_artifact_sidecar(*, relationships: list[dict] | None = None) -> dict:
    """EvidenceArtifact requires parameter[] (minItems 1) with fact_provenance
    carrying derived_from containing at least one `attachment:att_*` ref."""
    return {
        "object": _object_block("EvidenceArtifact", "EVD-000001", "Bend test result"),
        "evidence": {
            "summary": "Bend test result",
            "evidence_kind": "measurement",
        },
        "attachment": [_attachment_record("att_evd_000001_src", "a" * 64)],
        "parameter": [{
            "id": "param_max_load_n",
            "name": "max_load_n",
            "value": 5400.0,
            "datatype": "number",
            "unit": "N",
            "fact_provenance": {
                "category": "measured",
                "derived_from": ["attachment:att_evd_000001_src"],
            },
        }],
        "relationship": relationships or [],
    }


def _satisfies_record(*, target_uuid: str | None = None) -> dict:
    return {
        "id": "rel_satisfies_01",
        "type": "satisfies",
        "binding": "float",
        "endpoints": [{"object_uuid": target_uuid or _make_uuid()}],
    }


def _verifies_record(*, target_uuid: str | None = None) -> dict:
    return {
        "id": "rel_verifies_01",
        "type": "verifies",
        "binding": "float",
        "endpoints": [{"object_uuid": target_uuid or _make_uuid()}],
    }


# ---------- 1. Bundle index shape ----------


def test_phase3_w3_bundle_index_has_relationship_namespace():
    """v0.22.0 _index.json carries both `relationship` schema-path lookup and
    `relationship_types_by_source_object_type` policy metadata per D5."""
    b = _bundle_v0_22_0()
    lookups = b.index["lookups"]
    assert "relationship" in lookups, "lookups.relationship missing"
    assert set(lookups["relationship"].keys()) == {
        "satisfies", "tested_against", "verifies", "cites",
        "executes", "executed_on", "produces",
    }
    assert "relationship_types_by_source_object_type" in lookups
    allow_map = lookups["relationship_types_by_source_object_type"]
    assert allow_map["Part"] == ["satisfies", "tested_against"]
    assert allow_map["Requirement"] == ["cites"]
    assert allow_map["TestProcedure"] == ["verifies"]
    assert allow_map["TestExecution"] == ["executes", "executed_on", "produces"]
    assert allow_map["EvidenceArtifact"] == []


# ---------- 2-3. Positive dispatch ----------


def test_phase3_w3_dispatch_validates_satisfies_on_part_passes():
    """Part sidecar with valid `satisfies` record validates (outer schema + dispatch)."""
    b = _bundle_v0_22_0()
    sc = _minimal_part_sidecar(relationships=[_satisfies_record()])
    b.validate(sc, "sidecar", "Part")  # no raise


def test_phase3_w3_dispatch_validates_verifies_on_test_procedure_passes():
    """TestProcedure sidecar with valid `verifies` record validates."""
    b = _bundle_v0_22_0()
    sc = _minimal_test_procedure_sidecar(relationships=[_verifies_record()])
    b.validate(sc, "sidecar", "TestProcedure")  # no raise


# ---------- 4-7. Negative dispatch ----------


def test_phase3_w3_dispatch_rejects_unknown_type():
    """Unknown relationship type → 'bundle has no schema for relationship type X' (B1 order)."""
    b = _bundle_v0_22_0()
    sc = _minimal_part_sidecar(relationships=[{
        "id": "rel_made_up_01",
        "type": "made_up",
        "binding": "float",
        "endpoints": [{"object_uuid": _make_uuid()}],
    }])
    with pytest.raises(SchemaValidationError) as excinfo:
        b.validate(sc, "sidecar", "Part")
    msg = str(excinfo.value)
    assert "made_up" in msg
    assert "no schema for relationship type" in msg
    # Must NOT be the disallowed-on-Object message
    assert "not allowed on Object Type" not in msg


def test_phase3_w3_dispatch_rejects_type_not_allowed_on_object():
    """Known relationship type on wrong Object Type → 'type X not allowed on Object Type Y; allowed: [...]'."""
    b = _bundle_v0_22_0()
    # Part is NOT allowed to carry `verifies` (which lives on TestProcedure source)
    sc = _minimal_part_sidecar(relationships=[_verifies_record()])
    with pytest.raises(SchemaValidationError) as excinfo:
        b.validate(sc, "sidecar", "Part")
    msg = str(excinfo.value)
    assert "verifies" in msg
    assert "not allowed on Object Type 'Part'" in msg
    assert "satisfies" in msg and "tested_against" in msg  # allowed-list cited


def test_phase3_w3_dispatch_rejects_evidence_artifact_relationship():
    """EvidenceArtifact source-side gap closed: ANY relationship record raises."""
    b = _bundle_v0_22_0()
    # Even a structurally valid satisfies record (allowed on Part) must be rejected
    # because EvidenceArtifact's allow-list is empty (cites is on it as TARGET, not source).
    sc = _minimal_evidence_artifact_sidecar(relationships=[_satisfies_record()])
    with pytest.raises(SchemaValidationError) as excinfo:
        b.validate(sc, "sidecar", "EvidenceArtifact")
    msg = str(excinfo.value)
    assert "satisfies" in msg
    assert "not allowed on Object Type 'EvidenceArtifact'" in msg
    assert "allowed: []" in msg


def test_phase3_w3_dispatch_per_type_error_message_format():
    """Invalid `verifies` record (binding fixed but endpoint missing revision_id)
    raises with type-named format: 'relationship[0]/verifies/endpoints/0: ...'.

    Per ADR/0025 §9 wording target — replaces noisy 'does not match any of the
    subschemas'.
    """
    b = _bundle_v0_22_0()
    bad_verifies = {
        "id": "rel_verifies_bad",
        "type": "verifies",
        "binding": "fixed",
        "endpoints": [{"object_uuid": _make_uuid()}],  # missing revision_id under fixed
    }
    sc = _minimal_test_procedure_sidecar(relationships=[bad_verifies])
    with pytest.raises(SchemaValidationError) as excinfo:
        b.validate(sc, "sidecar", "TestProcedure")
    msg = str(excinfo.value)
    # Type-named error path
    assert "relationship[0]/verifies" in msg
    # No legacy noisy oneOf wording
    assert "does not match any of the subschemas" not in msg


# ---------- 8. Base schema factor-out ----------


def test_phase3_w3_base_schema_factored_out():
    """All 7 per-type relationship schemas reference `_base.schema.json` via
    allOf, carry `unevaluatedProperties: false`, and inherit base required fields."""
    b = _bundle_v0_22_0()
    base_path = b.bundle_dir / "relationship" / "_base.schema.json"
    assert base_path.exists(), "relationship/_base.schema.json missing"
    base = json.loads(base_path.read_text(encoding="utf-8"))
    # Base captures the universal trace-relationship pattern
    assert set(base["required"]) == {"id", "type", "binding", "endpoints"}
    for t in ["satisfies", "tested_against", "verifies", "cites",
              "executes", "executed_on", "produces"]:
        per_type = json.loads(
            (b.bundle_dir / "relationship" / f"{t}.schema.json").read_text(encoding="utf-8")
        )
        # Must inherit via allOf $ref _base
        assert any(
            isinstance(sub, dict) and sub.get("$ref") == "_base.schema.json"
            for sub in per_type.get("allOf", [])
        ), f"{t} schema does not allOf-ref _base.schema.json"
        # Must close with unevaluatedProperties
        assert per_type.get("unevaluatedProperties") is False, (
            f"{t} schema must carry unevaluatedProperties: false"
        )


# ---------- 9. Chain-aware migrator (single step) ----------


def test_phase3_w3_migrator_v0_21_0_to_v0_22_0_idempotent_and_dry_run(tmp_path: Path):
    """plan_migration / apply_migration update v0.21.0 → v0.22.0; idempotent;
    dry-run plan does not touch the pin."""
    workspace = tmp_path / "ws"
    (workspace / ".aiadra").mkdir(parents=True)
    reg = BundleRegistry()
    v21 = reg.bundle("0.21.0")
    pin_text = f'"bundle_version": "0.21.0"\n"bundle_digest": "{v21.bundle_digest}"\n'
    (workspace / ".aiadra" / "schemas.yaml").write_bytes(pin_text.encode("utf-8"))

    # Dry-run
    plan = plan_migration(workspace, "0.22.0", reg)
    assert plan.from_bundle_version == "0.21.0"
    assert plan.to_bundle_version == "0.22.0"
    assert plan.pin_will_change is True
    # Plan did not write
    assert b"0.21.0" in (workspace / ".aiadra" / "schemas.yaml").read_bytes()

    # Apply
    applied = apply_migration(workspace, "0.22.0", reg)
    assert applied.to_bundle_version == "0.22.0"
    pin_after = (workspace / ".aiadra" / "schemas.yaml").read_text(encoding="utf-8")
    assert '"bundle_version": "0.22.0"' in pin_after
    v22 = reg.bundle("0.22.0")
    assert v22.bundle_digest in pin_after

    # Idempotent: re-apply on v0.22.0 returns no-op
    reapply = apply_migration(workspace, "0.22.0", reg)
    assert reapply.pin_will_change is False
    assert "no-op" in " ".join(reapply.notes).lower()

    # Rejects v0.19.0 → 0.22.0 from missing pin
    other = tmp_path / "ws_missing"
    with pytest.raises(MigrationError, match="pin missing"):
        plan_migration(other, "0.22.0", reg)


# ---------- 10. Chain-aware multi-step ----------


def test_phase3_w3_chain_migration_v0_19_0_to_v0_22_0(tmp_path: Path):
    """Multi-step chain v0.19.0 → v0.22.0 walks all 3 registered steps and writes
    the final pin ONCE atomically per Codex1 D8 absorption."""
    workspace = tmp_path / "ws"
    (workspace / ".aiadra").mkdir(parents=True)
    reg = BundleRegistry()
    v19 = reg.bundle("0.19.0")
    pin_text = f'"bundle_version": "0.19.0"\n"bundle_digest": "{v19.bundle_digest}"\n'
    (workspace / ".aiadra" / "schemas.yaml").write_bytes(pin_text.encode("utf-8"))

    # Dry-run multi-step plan mentions chain
    plan = plan_migration(workspace, "0.22.0", reg)
    assert plan.from_bundle_version == "0.19.0"
    assert plan.to_bundle_version == "0.22.0"
    notes_joined = " ".join(plan.notes)
    assert "Multi-step chain: 0.19.0 → 0.20.0 → 0.21.0 → 0.22.0" in notes_joined
    # Dry-run did not write
    assert b"0.19.0" in (workspace / ".aiadra" / "schemas.yaml").read_bytes()

    # Apply: single atomic pin write at end
    applied = apply_migration(workspace, "0.22.0", reg)
    pin_after = (workspace / ".aiadra" / "schemas.yaml").read_text(encoding="utf-8")
    assert '"bundle_version": "0.22.0"' in pin_after
    v22 = reg.bundle("0.22.0")
    assert v22.bundle_digest in pin_after
    # Intermediate versions NOT in final pin
    assert "0.19.0" not in pin_after
    assert "0.20.0" not in pin_after
    assert "0.21.0" not in pin_after


# ---------- 11. Codex D10 addition: distinct error messages ----------


def test_phase3_w3_distinct_unknown_vs_disallowed_error_messages():
    """Per Codex1 B1 absorption + D10 addition: unknown-type and known-but-
    disallowed-type produce DISTINCT, recognizable error messages. The B1
    ordering is what makes this assertion meaningful (without it, both errors
    would collapse to 'not allowed')."""
    b = _bundle_v0_22_0()

    # Unknown type on Part
    sc_unknown = _minimal_part_sidecar(relationships=[{
        "id": "rel_x",
        "type": "totally_made_up_type",
        "binding": "float",
        "endpoints": [{"object_uuid": _make_uuid()}],
    }])
    with pytest.raises(SchemaValidationError) as ex_unknown:
        b.validate(sc_unknown, "sidecar", "Part")
    unknown_msg = str(ex_unknown.value)

    # Known type on wrong Object Type (verifies on Part)
    sc_disallowed = _minimal_part_sidecar(relationships=[_verifies_record()])
    with pytest.raises(SchemaValidationError) as ex_disallowed:
        b.validate(sc_disallowed, "sidecar", "Part")
    disallowed_msg = str(ex_disallowed.value)

    # Distinct shapes
    assert "no schema for relationship type" in unknown_msg
    assert "not allowed on Object Type" in disallowed_msg
    assert unknown_msg != disallowed_msg
    # Cross-check non-collision
    assert "not allowed on Object Type" not in unknown_msg
    assert "no schema for relationship type" not in disallowed_msg


# ---------- 12. REGISTERED_STEPS coverage ----------


def test_phase3_w3_registered_steps_cover_all_bundle_transitions():
    """REGISTERED_STEPS should contain all transitions for packaged bundles.

    With v0.19.0 / v0.20.0 / v0.21.0 / v0.22.0 packaged, we expect 3 steps
    forming a chain 0.19.0 → 0.20.0 → 0.21.0 → 0.22.0.
    """
    versions = [s.from_version for s in REGISTERED_STEPS]
    to_versions = [s.to_version for s in REGISTERED_STEPS]
    # Phase 3 invariants: chain starts at 0.19.0 and is contiguous.
    assert versions[0] == "0.19.0"
    assert "0.20.0" in to_versions and "0.21.0" in to_versions and "0.22.0" in to_versions
    # Future-proof: chain links from_version[i+1] == to_version[i].
    for i in range(len(REGISTERED_STEPS) - 1):
        assert REGISTERED_STEPS[i + 1].from_version == REGISTERED_STEPS[i].to_version


# ---------- 13. arc 20260602-3 housekeeping: legacy wrappers + stale-digest CLI ----------


def test_legacy_v0_19_0_to_v0_20_0_wrappers_delegate_to_first_step(tmp_path: Path):
    """Codex1 N4 (arc 20260602-3): direct test for the Phase-1 back-compat
    wrappers `plan_migration_v0_19_0_to_v0_20_0` / `apply_migration_v0_19_0_to_v0_20_0`.
    Broad chain + REGISTERED_STEPS coverage already existed; these specific
    first-step wrappers did not have a direct test."""
    from aiadra_core.validation.migration import (
        apply_migration_v0_19_0_to_v0_20_0,
        plan_migration_v0_19_0_to_v0_20_0,
    )
    workspace = tmp_path / "ws"
    (workspace / ".aiadra").mkdir(parents=True)
    reg = BundleRegistry()
    v19 = reg.bundle("0.19.0")
    (workspace / ".aiadra" / "schemas.yaml").write_bytes(
        f'"bundle_version": "0.19.0"\n"bundle_digest": "{v19.bundle_digest}"\n'.encode("utf-8")
    )
    # plan wrapper → first step, no write
    plan = plan_migration_v0_19_0_to_v0_20_0(workspace)
    assert plan.from_bundle_version == "0.19.0"
    assert plan.to_bundle_version == "0.20.0"
    assert b'"bundle_version": "0.19.0"' in (workspace / ".aiadra" / "schemas.yaml").read_bytes()
    # apply wrapper → pin advances to 0.20.0
    apply_migration_v0_19_0_to_v0_20_0(workspace)
    pin_after = (workspace / ".aiadra" / "schemas.yaml").read_text(encoding="utf-8")
    assert '"bundle_version": "0.20.0"' in pin_after
    assert reg.bundle("0.20.0").bundle_digest in pin_after


def test_cmd_migrate_reports_stale_pin_digest_cleanly(tmp_path: Path, capsys):
    """Codex1 N5 (arc 20260602-3): when a workspace is already pinned to the
    target version but with a STALE digest, `aiadra migrate` reports it as a
    clean migrate failure (nonzero exit + actionable message) instead of letting
    BundleDigestMismatchError escape as an uncaught traceback."""
    from aiadra_core.cli.commands import cmd_migrate
    workspace = tmp_path / "ws"
    (workspace / ".aiadra").mkdir(parents=True)
    # Pinned to 0.20.0 but with a deliberately STALE digest.
    (workspace / ".aiadra" / "schemas.yaml").write_bytes(
        b'"bundle_version": "0.20.0"\n"bundle_digest": "sha256:' + b"0" * 64 + b'"\n'
    )
    rc = cmd_migrate([str(workspace), "--to-bundle", "0.20.0"])
    assert rc == 1
    assert "stale pin digest" in capsys.readouterr().err
