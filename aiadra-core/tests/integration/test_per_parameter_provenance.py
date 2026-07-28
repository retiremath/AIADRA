"""ADR/0044 Amendment A2 (arc 20260717-2, Gate F2a): the D3 per-parameter
provenance extension — bundle v0.28.0 -> v0.29.0; aiadra-core 0.15.0 -> 0.16.0.

`_shared/feature_record.schema.json` parameters[] items gain an OPTIONAL
`fact_provenance` object. Additive: every pre-A2 record validates unchanged;
absence of the field means the parent feature record's provenance applies.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from aiadra_core.validation.bundle_registry import BundleRegistry
from aiadra_core.validation.digest import compute_bundle_digest
from aiadra_core.validation.migration import REGISTERED_STEPS


def _bundle_dir(version: str) -> Path:
    import aiadra_core

    return Path(aiadra_core.__file__).parent / "schemas" / f"v{version}"


def _feature_record_validator(version: str) -> jsonschema.Draft202012Validator:
    root = _bundle_dir(version)
    schema_path = root / "_shared" / "feature_record.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    resolver = jsonschema.validators.RefResolver(
        base_uri=schema_path.resolve().as_uri(), referrer=schema
    )
    return jsonschema.Draft202012Validator(schema, resolver=resolver)


def _feature_record(parameter_extra: dict | None = None) -> dict:
    param = {
        "id": "featp_0001",
        "name": "depth",
        "value": 12.5,
        "datatype": "number",
        "unit": "mm",
    }
    if parameter_extra:
        param.update(parameter_extra)
    return {
        "id": "feat_0001",
        "name": "Sketch 1",
        "feature_type": "sketch",
        "engine": "mechanical",
        "adapter_schema_version": "0.1.11",
        "adapter_payload": {},
        "fact_provenance": {"category": "human_input"},
        "parameters": [param],
    }


class TestBundleV0290:
    def test_bundle_resolves_with_pinned_digest(self):
        b = BundleRegistry().bundle("0.29.0")
        assert b.bundle_version == "0.29.0"
        digest_file = json.loads(
            (_bundle_dir("0.29.0") / "_digest.json").read_text(encoding="utf-8")
        )
        assert digest_file["bundle_digest"] == compute_bundle_digest(_bundle_dir("0.29.0"))

    def test_latest_is_v0290(self):
        # v0.30.0 superseded v0.29.0 as latest (delete_object, arc 20260728-3);
        # v0.29.0 remains registered + migratable.
        assert BundleRegistry().latest().bundle_version == "0.30.0"
        assert "0.29.0" in BundleRegistry().versions()

    def test_migration_chain_reaches_v0290(self):
        step = next(
            (s for s in REGISTERED_STEPS
             if s.from_version == "0.28.0" and s.to_version == "0.29.0"),
            None,
        )
        assert step is not None
        assert any("ADR/0044" in n for n in step.notes)

    def test_v0280_bundle_is_untouched(self):
        # the prior bundle must remain byte-consistent with its own digest
        digest_file = json.loads(
            (_bundle_dir("0.28.0") / "_digest.json").read_text(encoding="utf-8")
        )
        assert digest_file["bundle_digest"] == compute_bundle_digest(_bundle_dir("0.28.0"))
        # and its parameter items still have NO fact_provenance property
        fr = json.loads(
            (_bundle_dir("0.28.0") / "_shared" / "feature_record.schema.json")
            .read_text(encoding="utf-8")
        )
        assert "fact_provenance" not in fr["properties"]["parameters"]["items"]["properties"]


class TestPerParameterProvenance:
    def test_absent_field_validates_unchanged(self):
        _feature_record_validator("0.29.0").validate(_feature_record())

    @pytest.mark.parametrize("category", ["human_input", "ai_proposal", "computed_result"])
    def test_each_admitted_category_validates(self, category):
        rec = _feature_record({"fact_provenance": {"category": category}})
        _feature_record_validator("0.29.0").validate(rec)

    def test_full_shape_validates(self):
        rec = _feature_record({"fact_provenance": {
            "category": "ai_proposal",
            "ai_agent_ref": "agent://claude",
            "derived_from": ["feature:feat_0001"],
        }})
        _feature_record_validator("0.29.0").validate(rec)

    def test_measured_is_rejected_per_parameter(self):
        # reference dimensions are parameter-free derived measurements (D3);
        # 'measured' never appears in parameters[]
        rec = _feature_record({"fact_provenance": {"category": "measured"}})
        with pytest.raises(jsonschema.ValidationError):
            _feature_record_validator("0.29.0").validate(rec)

    def test_unknown_category_rejected(self):
        rec = _feature_record({"fact_provenance": {"category": "guessed"}})
        with pytest.raises(jsonschema.ValidationError):
            _feature_record_validator("0.29.0").validate(rec)

    def test_extra_properties_rejected(self):
        rec = _feature_record({"fact_provenance": {
            "category": "human_input", "history": ["not-here"],
        }})
        with pytest.raises(jsonschema.ValidationError):
            _feature_record_validator("0.29.0").validate(rec)

    def test_category_required_when_present(self):
        rec = _feature_record({"fact_provenance": {}})
        with pytest.raises(jsonschema.ValidationError):
            _feature_record_validator("0.29.0").validate(rec)

    def test_v0280_rejects_the_extension(self):
        # the pre-A2 bundle must NOT accept the new field (additionalProperties
        # discipline) — series separation is real, not cosmetic
        rec = _feature_record({"fact_provenance": {"category": "human_input"}})
        with pytest.raises(jsonschema.ValidationError):
            _feature_record_validator("0.28.0").validate(rec)
