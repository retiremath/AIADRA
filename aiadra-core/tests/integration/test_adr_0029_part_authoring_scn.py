"""ADR/0029 Part authoring SCN tests — `part_changed` event with `feature_delta`
+ `geometry_ref_delta`; bundle v0.27.0 -> v0.28.0; aiadra-core 0.9.0 -> 0.10.0.

Per arc 20260531-13 Claude1+Codex1 absorptions:
- B1 absorption: part_changed uses the standard event/_base.schema.json envelope
  (event_type, timestamp, transaction_id, payload). Payload carries object_uuid +
  feature_delta + geometry_ref_delta. Actor is narrowed to enum [agent, human]
  at the event root.
- B2 absorption: serialized JSON keys are `feature` + `geometry_ref` (no colons).
  `feature:<id>` is address notation used in fact_provenance.derived_from etc.
- B3 absorption: atomic delta conflict rules (no intra-array dupes; no cross-array
  overlap; added MUST be fresh; updated/removed MUST exist; new_record.id wrapper
  consistency). Full delta applied atomically; post-conditions enforced.
- B4 absorption: feature records carry actor-derived provenance (agent ->
  ai_proposal / human -> human_input). Geometry_ref records are computed_result
  with derived_from cross-referencing derived_from_feature_ids via canonical
  `feature:<id>` address form.
- B5 absorption: geometry_ref keeps ADR/0005 D7 role enum + REQUIRED vault_ref;
  adapter_ref is OPTIONAL wrapper per ADR/0005 D9 + ADR/0027 D18.
- B6 absorption: depends_on_feature_ids forms a DAG (multi-parent), not a tree.
  Fold enforces acyclicity via Kahn's algorithm.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiadra_core.validation.bundle_registry import (
    BundleRegistry,
    SchemaValidationError,
)
from aiadra_core.validation.fold import (
    FoldInconsistencyError,
    _apply_part_changed,
)
from aiadra_core.validation.migration import (
    REGISTERED_STEPS,
)


def _bundle_v0_28_0():
    return BundleRegistry().bundle("0.28.0")


# Canonical Vault hashes for fixtures.
_VAULT_HASH_A = "sha256:" + "a" * 64
_VAULT_HASH_B = "sha256:" + "b" * 64

_PART_UUID = "01934567-89ab-7def-8123-456789abcdef"


# =============================================================================
# Fixture helpers
# =============================================================================


def _minimal_part_sidecar(*, features: list[dict] | None = None,
                          geometry_refs: list[dict] | None = None) -> dict:
    sc = {
        "object": {
            "uuid": _PART_UUID,
            "number": "P-000001",
            "type": "Part",
            "name": "fixture part",
            "lifecycle": "in_work",
            "schema_version": "0.28.0",
        },
        "parameter": [{
            "id": "param_seed",
            "name": "seed_param",
            "value": 1.0,
            "datatype": "number",
            "unit": "mm",
            "fact_provenance": {"category": "human_input"},
        }],
    }
    if features is not None:
        sc["feature"] = features
    if geometry_refs is not None:
        sc["geometry_ref"] = geometry_refs
    return sc


def _make_feature(
    feat_id: str,
    *,
    actor_category: str = "ai_proposal",
    depends_on: list[str] | None = None,
    feature_type: str = "extrude",
    parameters: list[dict] | None = None,
) -> dict:
    return {
        "id": feat_id,
        "name": f"{feature_type}_{feat_id}",
        "feature_type": feature_type,
        "depends_on_feature_ids": depends_on or [],
        "parameters": parameters or [],
        "adapter_payload": {"kernel_op": feature_type},
        "engine": "mechanical-native",
        "adapter_schema_version": "1.0.0",
        "fact_provenance": {"category": actor_category},
    }


def _make_geometry_ref(
    geom_id: str,
    *,
    role: str = "authoring_geometry",
    vault: str = _VAULT_HASH_A,
    derived_from_features: list[str] | None = None,
    derived_from_geoms: list[str] | None = None,
) -> dict:
    rec = {
        "id": geom_id,
        "role": role,
        "vault_ref": vault,
        "fact_provenance": {
            "category": "computed_result",
            "derived_from": [],
        },
    }
    if role == "authoring_geometry":
        feat_ids = derived_from_features or ["feat_0001"]
        rec["derived_from_feature_ids"] = feat_ids
        rec["fact_provenance"]["derived_from"] = [f"feature:{f}" for f in feat_ids]
    elif role == "derived_export":
        rec["derived_from"] = derived_from_geoms or ["geom_0001"]
        rec["fact_provenance"]["derived_from"] = [f"geometry_ref:{g}" for g in (derived_from_geoms or ["geom_0001"])]
    return rec


def _make_part_changed_event(
    *,
    actor: str = "agent",
    feature_delta: dict | None = None,
    geometry_ref_delta: dict | None = None,
) -> dict:
    payload = {"object_uuid": _PART_UUID}
    if feature_delta is not None:
        payload["feature_delta"] = feature_delta
    if geometry_ref_delta is not None:
        payload["geometry_ref_delta"] = geometry_ref_delta
    return {
        "schema_version": "0.28.0",
        "event_id": "evt_0001",
        "event_type": "part_changed",
        "timestamp": "2026-05-31T22:00:00Z",
        "transaction_id": "tx_0001",
        "actor": actor,
        "payload": payload,
    }


# =============================================================================
# 1. Bundle registration
# =============================================================================


def test_adr_0029_bundle_v0_28_0_registered():
    """v0.28.0 bundle resolves with the pinned digest."""
    b = _bundle_v0_28_0()
    assert b.bundle_version == "0.28.0"
    assert b.bundle_digest.startswith("sha256:")


def test_adr_0029_registered_steps_includes_v0_28_0():
    to_versions = [s.to_version for s in REGISTERED_STEPS]
    assert "0.28.0" in to_versions
    # Chain remains contiguous.
    for i in range(len(REGISTERED_STEPS) - 1):
        assert REGISTERED_STEPS[i + 1].from_version == REGISTERED_STEPS[i].to_version


# =============================================================================
# 2. Schema accept / reject — Codex1 B1 + B2 + B5
# =============================================================================


def test_adr_0029_part_sidecar_accepts_feature_and_geometry_ref_namespaces():
    """Codex1 B2: serialized JSON keys are `feature` + `geometry_ref` (no colons)."""
    b = _bundle_v0_28_0()
    sc = _minimal_part_sidecar(
        features=[_make_feature("feat_0001")],
        geometry_refs=[_make_geometry_ref("geom_0001")],
    )
    b.validate(sc, "sidecar", "Part")


def test_adr_0029_part_sidecar_rejects_colon_in_namespace_key():
    """Codex1 B2: schema rejects `feature:` / `geometry_ref:` keys with colon."""
    b = _bundle_v0_28_0()
    sc = _minimal_part_sidecar()
    sc["feature:"] = [_make_feature("feat_0001")]  # colon form is wrong
    with pytest.raises(SchemaValidationError):
        b.validate(sc, "sidecar", "Part")


def test_adr_0029_part_sidecar_works_without_feature_namespace():
    """Both new namespaces OPTIONAL — v0.27.0-shape Parts still validate."""
    b = _bundle_v0_28_0()
    sc = _minimal_part_sidecar()  # no feature, no geometry_ref
    b.validate(sc, "sidecar", "Part")


def test_adr_0029_part_changed_uses_base_envelope():
    """Codex1 B1: part_changed uses event_type + timestamp + transaction_id +
    payload from _base.schema.json (NOT custom top-level fields)."""
    b = _bundle_v0_28_0()
    ev = _make_part_changed_event(
        feature_delta={"added": [_make_feature("feat_0001")]},
    )
    b.validate(ev, "event", "part_changed")


def test_adr_0029_part_changed_rejects_wrong_envelope_keys():
    """Codex1 B1: `type` instead of `event_type` is schema-rejected
    (unevaluatedProperties: false on the part_changed schema)."""
    b = _bundle_v0_28_0()
    ev = _make_part_changed_event(
        feature_delta={"added": [_make_feature("feat_0001")]},
    )
    ev["type"] = "part_changed"  # adds illegal extra property
    del ev["event_type"]
    with pytest.raises(SchemaValidationError):
        b.validate(ev, "event", "part_changed")


def test_adr_0029_part_changed_actor_narrowed_to_enum():
    """Codex1 B1: actor narrowed to ['agent', 'human'] at part_changed level."""
    b = _bundle_v0_28_0()
    ev = _make_part_changed_event(
        actor="robot",  # not in enum
        feature_delta={"added": [_make_feature("feat_0001")]},
    )
    with pytest.raises(SchemaValidationError):
        b.validate(ev, "event", "part_changed")


def test_adr_0029_part_changed_requires_at_least_one_delta():
    """anyOf forbids ghost events with no delta section."""
    b = _bundle_v0_28_0()
    ev = _make_part_changed_event()  # neither delta provided
    with pytest.raises(SchemaValidationError):
        b.validate(ev, "event", "part_changed")


def test_adr_0029_geometry_ref_requires_vault_ref():
    """Codex1 B5: vault_ref REQUIRED per ADR/0005 D7."""
    b = _bundle_v0_28_0()
    geom = _make_geometry_ref("geom_0001")
    del geom["vault_ref"]
    sc = _minimal_part_sidecar(
        features=[_make_feature("feat_0001")],
        geometry_refs=[geom],
    )
    with pytest.raises(SchemaValidationError):
        b.validate(sc, "sidecar", "Part")


def test_adr_0029_geometry_ref_authoring_requires_derived_from_feature_ids():
    """authoring_geometry MUST include derived_from_feature_ids."""
    b = _bundle_v0_28_0()
    geom = _make_geometry_ref("geom_0001")
    del geom["derived_from_feature_ids"]
    sc = _minimal_part_sidecar(
        features=[_make_feature("feat_0001")],
        geometry_refs=[geom],
    )
    with pytest.raises(SchemaValidationError):
        b.validate(sc, "sidecar", "Part")


def test_adr_0029_geometry_ref_derived_export_requires_derived_from():
    """derived_export MUST include derived_from (geom-to-geom lineage per ADR/0005 D7)."""
    b = _bundle_v0_28_0()
    geom = _make_geometry_ref("geom_0002", role="derived_export", vault=_VAULT_HASH_B)
    del geom["derived_from"]
    sc = _minimal_part_sidecar(
        features=[_make_feature("feat_0001")],
        geometry_refs=[
            _make_geometry_ref("geom_0001"),  # authoring
            geom,                              # derived_export missing derived_from
        ],
    )
    with pytest.raises(SchemaValidationError):
        b.validate(sc, "sidecar", "Part")


def test_adr_0029_geometry_ref_provenance_category_must_be_computed_result():
    """Codex1 B4: geometry_ref records can only be computed_result."""
    b = _bundle_v0_28_0()
    geom = _make_geometry_ref("geom_0001")
    geom["fact_provenance"]["category"] = "ai_proposal"  # forbidden at geometry_ref
    sc = _minimal_part_sidecar(
        features=[_make_feature("feat_0001")],
        geometry_refs=[geom],
    )
    with pytest.raises(SchemaValidationError):
        b.validate(sc, "sidecar", "Part")


def test_adr_0029_feature_provenance_category_must_be_caller_attested():
    """Codex1 B4: feature records cannot be computed_result (only ai_proposal/human_input)."""
    b = _bundle_v0_28_0()
    feat = _make_feature("feat_0001")
    feat["fact_provenance"]["category"] = "computed_result"  # forbidden at feature
    sc = _minimal_part_sidecar(features=[feat])
    with pytest.raises(SchemaValidationError):
        b.validate(sc, "sidecar", "Part")


def test_adr_0029_feature_parameter_unit_must_be_canonical():
    """ADR/0029 D10: feature parameter unit MUST be from the canonical enum."""
    b = _bundle_v0_28_0()
    feat = _make_feature("feat_0001", parameters=[{
        "id": "featp_0001",
        "name": "depth",
        "value": 10.0,
        "datatype": "number",
        "unit": "inches",  # not in canonical enum
    }])
    sc = _minimal_part_sidecar(features=[feat])
    with pytest.raises(SchemaValidationError):
        b.validate(sc, "sidecar", "Part")


def test_adr_0029_feature_parameter_accepts_canonical_units():
    b = _bundle_v0_28_0()
    feat = _make_feature("feat_0001", parameters=[{
        "id": "featp_0001",
        "name": "depth",
        "value": 10.0,
        "datatype": "number",
        "unit": "mm",
    }])
    sc = _minimal_part_sidecar(features=[feat])
    b.validate(sc, "sidecar", "Part")


# =============================================================================
# 3. Fold semantics — Codex1 B3 atomic rules + B6 acyclicity + cascade
# =============================================================================


def _seed_state_with_part(features: list[dict] | None = None,
                          geometry_refs: list[dict] | None = None) -> dict:
    return {_PART_UUID: _minimal_part_sidecar(features=features, geometry_refs=geometry_refs)}


def test_adr_0029_fold_applies_feature_added():
    """Basic add: state gains the new feature."""
    state = _seed_state_with_part(features=[])
    payload = {
        "object_uuid": _PART_UUID,
        "feature_delta": {"added": [_make_feature("feat_0001")]},
    }
    _apply_part_changed(state, payload, actor="agent")
    assert state[_PART_UUID]["feature"][0]["id"] == "feat_0001"


def test_adr_0029_fold_rejects_added_id_collision():
    """Codex1 B3: added id that already exists -> FoldInconsistencyError."""
    state = _seed_state_with_part(features=[_make_feature("feat_0001")])
    payload = {
        "object_uuid": _PART_UUID,
        "feature_delta": {"added": [_make_feature("feat_0001")]},
    }
    with pytest.raises(FoldInconsistencyError, match="already present"):
        _apply_part_changed(state, payload, actor="agent")


def test_adr_0029_fold_rejects_intra_array_duplicate_ids():
    """Codex1 B3: same id appears twice in one added[] -> FoldInconsistencyError."""
    state = _seed_state_with_part(features=[])
    payload = {
        "object_uuid": _PART_UUID,
        "feature_delta": {
            "added": [
                _make_feature("feat_0001"),
                _make_feature("feat_0001"),
            ],
        },
    }
    with pytest.raises(FoldInconsistencyError, match="duplicate id"):
        _apply_part_changed(state, payload, actor="agent")


def test_adr_0029_fold_rejects_cross_array_overlap():
    """Codex1 B3: same id in both added[] and removed[] -> FoldInconsistencyError."""
    state = _seed_state_with_part(features=[_make_feature("feat_0001")])
    payload = {
        "object_uuid": _PART_UUID,
        "feature_delta": {
            "added": [_make_feature("feat_0001")],  # implies fresh
            "removed": ["feat_0001"],               # but also removing
        },
    }
    with pytest.raises(FoldInconsistencyError, match="appear in both"):
        _apply_part_changed(state, payload, actor="agent")


def test_adr_0029_fold_rejects_update_of_missing_id():
    state = _seed_state_with_part(features=[])
    payload = {
        "object_uuid": _PART_UUID,
        "feature_delta": {
            "updated": [{
                "id": "feat_0001",
                "new_record": _make_feature("feat_0001"),
            }],
        },
    }
    with pytest.raises(FoldInconsistencyError, match="not present"):
        _apply_part_changed(state, payload, actor="agent")


def test_adr_0029_fold_rejects_remove_of_missing_id():
    state = _seed_state_with_part(features=[])
    payload = {
        "object_uuid": _PART_UUID,
        "feature_delta": {"removed": ["feat_0001"]},
    }
    with pytest.raises(FoldInconsistencyError, match="not present"):
        _apply_part_changed(state, payload, actor="agent")


def test_adr_0029_fold_rejects_updated_wrapper_id_mismatch():
    """Codex1 B3: updated[].new_record.id MUST equal updated[].id."""
    state = _seed_state_with_part(features=[_make_feature("feat_0001")])
    payload = {
        "object_uuid": _PART_UUID,
        "feature_delta": {
            "updated": [{
                "id": "feat_0001",
                "new_record": _make_feature("feat_0002"),  # mismatched id
            }],
        },
    }
    with pytest.raises(FoldInconsistencyError, match="!="):
        _apply_part_changed(state, payload, actor="agent")


def test_adr_0029_fold_rejects_provenance_actor_mismatch_agent():
    """Codex1 B4: actor=agent + feature.fact_provenance=human_input -> reject."""
    state = _seed_state_with_part(features=[])
    payload = {
        "object_uuid": _PART_UUID,
        "feature_delta": {"added": [_make_feature("feat_0001", actor_category="human_input")]},
    }
    with pytest.raises(FoldInconsistencyError, match="ai_proposal"):
        _apply_part_changed(state, payload, actor="agent")


def test_adr_0029_fold_rejects_provenance_actor_mismatch_human():
    """Codex1 B4: actor=human + feature.fact_provenance=ai_proposal -> reject."""
    state = _seed_state_with_part(features=[])
    payload = {
        "object_uuid": _PART_UUID,
        "feature_delta": {"added": [_make_feature("feat_0001", actor_category="ai_proposal")]},
    }
    with pytest.raises(FoldInconsistencyError, match="human_input"):
        _apply_part_changed(state, payload, actor="human")


def test_adr_0029_fold_accepts_provenance_actor_match():
    """actor=human + feature.fact_provenance=human_input -> accept."""
    state = _seed_state_with_part(features=[])
    payload = {
        "object_uuid": _PART_UUID,
        "feature_delta": {"added": [_make_feature("feat_0001", actor_category="human_input")]},
    }
    _apply_part_changed(state, payload, actor="human")
    assert state[_PART_UUID]["feature"][0]["fact_provenance"]["category"] == "human_input"


def test_adr_0029_fold_geometry_provenance_derived_from_cross_check():
    """Codex1 B4: geometry_ref derived_from_feature_ids MUST be covered by
    fact_provenance.derived_from in canonical `feature:<id>` form."""
    state = _seed_state_with_part(features=[_make_feature("feat_0001")])
    # Build geom that DECLARES feat_0001 in derived_from_feature_ids but FORGETS it in derived_from.
    bad_geom = _make_geometry_ref("geom_0001", derived_from_features=["feat_0001"])
    bad_geom["fact_provenance"]["derived_from"] = []  # broken cross-ref
    payload = {
        "object_uuid": _PART_UUID,
        "geometry_ref_delta": {"added": [bad_geom]},
    }
    with pytest.raises(FoldInconsistencyError, match="missing"):
        _apply_part_changed(state, payload, actor="agent")


def test_adr_0029_fold_dag_acyclicity_simple_cycle():
    """Codex1 B6: depends_on_feature_ids forms a DAG; cycle is rejected."""
    state = _seed_state_with_part(features=[])
    payload = {
        "object_uuid": _PART_UUID,
        "feature_delta": {"added": [
            _make_feature("feat_0001", depends_on=["feat_0002"]),
            _make_feature("feat_0002", depends_on=["feat_0001"]),  # cycle
        ]},
    }
    with pytest.raises(FoldInconsistencyError, match="cycle"):
        _apply_part_changed(state, payload, actor="agent")


def test_adr_0029_fold_dag_acyclicity_multi_parent_ok():
    """Codex1 B6: multi-parent dependency is valid (NOT a tree restriction)."""
    state = _seed_state_with_part(features=[])
    payload = {
        "object_uuid": _PART_UUID,
        "feature_delta": {"added": [
            _make_feature("feat_0001"),                                  # root
            _make_feature("feat_0002"),                                  # root
            _make_feature("feat_0003", depends_on=["feat_0001", "feat_0002"]),  # multi-parent
        ]},
    }
    _apply_part_changed(state, payload, actor="agent")
    assert len(state[_PART_UUID]["feature"]) == 3


def test_adr_0029_fold_dag_rejects_dangling_dependency():
    """Codex1 B6 + ADR/0029 D9: depends_on referencing nonexistent feature -> reject."""
    state = _seed_state_with_part(features=[])
    payload = {
        "object_uuid": _PART_UUID,
        "feature_delta": {"added": [
            _make_feature("feat_0001", depends_on=["feat_9999"]),
        ]},
    }
    with pytest.raises(FoldInconsistencyError, match="do not exist"):
        _apply_part_changed(state, payload, actor="agent")


def test_adr_0029_fold_cascade_rejects_dangling_after_remove():
    """ADR/0029 D12: removing a feature still referenced by surviving geometry_ref -> reject."""
    state = _seed_state_with_part(
        features=[_make_feature("feat_0001"), _make_feature("feat_0002")],
        geometry_refs=[_make_geometry_ref("geom_0001", derived_from_features=["feat_0001"])],
    )
    payload = {
        "object_uuid": _PART_UUID,
        "feature_delta": {"removed": ["feat_0001"]},  # still referenced by geom_0001
    }
    with pytest.raises(FoldInconsistencyError, match="cascade-reject"):
        _apply_part_changed(state, payload, actor="agent")


def test_adr_0029_fold_cascade_accepts_batched_remove():
    """ADR/0029 D12 + Codex1 Q7: batched removal of dependent + parent -> OK."""
    state = _seed_state_with_part(
        features=[_make_feature("feat_0001"), _make_feature("feat_0002")],
        geometry_refs=[_make_geometry_ref("geom_0001", derived_from_features=["feat_0001"])],
    )
    payload = {
        "object_uuid": _PART_UUID,
        "feature_delta": {"removed": ["feat_0001"]},
        "geometry_ref_delta": {"removed": ["geom_0001"]},  # remove dependent in same event
    }
    _apply_part_changed(state, payload, actor="agent")
    assert state[_PART_UUID]["feature"] == [_make_feature("feat_0002")]
    assert state[_PART_UUID]["geometry_ref"] == []


def test_adr_0029_fold_applies_full_batched_delta_atomically():
    """End-to-end: add + update + remove in one event applied atomically."""
    state = _seed_state_with_part(
        features=[
            _make_feature("feat_0001"),
            _make_feature("feat_0002"),
        ],
    )
    updated_feat = _make_feature("feat_0002", feature_type="fillet")
    payload = {
        "object_uuid": _PART_UUID,
        "feature_delta": {
            "added": [_make_feature("feat_0003")],
            "updated": [{"id": "feat_0002", "new_record": updated_feat}],
            "removed": ["feat_0001"],
        },
    }
    _apply_part_changed(state, payload, actor="agent")
    by_id = {f["id"]: f for f in state[_PART_UUID]["feature"]}
    assert set(by_id) == {"feat_0002", "feat_0003"}
    assert by_id["feat_0002"]["feature_type"] == "fillet"


def test_adr_0029_fold_unknown_part_uuid_rejected():
    """part_changed on a Part that doesn't exist -> FoldInconsistencyError."""
    state = {}
    payload = {
        "object_uuid": _PART_UUID,
        "feature_delta": {"added": [_make_feature("feat_0001")]},
    }
    with pytest.raises(FoldInconsistencyError, match="unknown Object"):
        _apply_part_changed(state, payload, actor="agent")


# =============================================================================
# 4. Codex2 R3 absorption — actor required + provenance set-equality
# =============================================================================


def test_adr_0029_part_changed_missing_actor_schema_rejected():
    """Codex2 B1: actor is REQUIRED at part_changed root.

    Without root `required: ["actor"]`, a part_changed event with no actor
    validates against schema and is interpreted as agent — silently
    manufacturing provenance context. The repair adds the explicit requirement.
    """
    b = _bundle_v0_28_0()
    ev = _make_part_changed_event(
        feature_delta={"added": [_make_feature("feat_0001")]},
    )
    del ev["actor"]
    with pytest.raises(SchemaValidationError):
        b.validate(ev, "event", "part_changed")


def test_adr_0029_fold_rejects_extra_dangling_feature_provenance_ref():
    """Codex2 B2: STRICT set-equality between derived_from_feature_ids and
    fact_provenance.derived_from. A `feature:feat_9999` entry not declared in
    derived_from_feature_ids is REJECTED (was previously allowed as a silent
    dangling extra under the old coverage-only check).
    """
    state = _seed_state_with_part(features=[_make_feature("feat_0001")])
    # Build geom that DECLARES feat_0001 in derived_from_feature_ids and ALSO
    # carries a dangling feature:feat_9999 in fact_provenance.derived_from.
    bad_geom = _make_geometry_ref("geom_0001", derived_from_features=["feat_0001"])
    bad_geom["fact_provenance"]["derived_from"] = [
        "feature:feat_0001",
        "feature:feat_9999",  # extra dangling — not in derived_from_feature_ids
    ]
    payload = {
        "object_uuid": _PART_UUID,
        "geometry_ref_delta": {"added": [bad_geom]},
    }
    with pytest.raises(FoldInconsistencyError, match="extras"):
        _apply_part_changed(state, payload, actor="agent")


def test_adr_0029_fold_rejects_cross_object_feature_provenance_form():
    """Codex2 B2: cross-Object form `<uuid>:feature:<id>` REJECTED in v0.28.0
    (reserved for future SCN per ADR/0029 D14 item 6)."""
    state = _seed_state_with_part(features=[_make_feature("feat_0001")])
    bad_geom = _make_geometry_ref("geom_0001", derived_from_features=["feat_0001"])
    bad_geom["fact_provenance"]["derived_from"] = [
        f"{_PART_UUID}:feature:feat_0001",  # cross-Object form
    ]
    payload = {
        "object_uuid": _PART_UUID,
        "geometry_ref_delta": {"added": [bad_geom]},
    }
    with pytest.raises(FoldInconsistencyError, match="cross-Object"):
        _apply_part_changed(state, payload, actor="agent")


def test_adr_0029_fold_rejects_non_canonical_provenance_form():
    """Codex2 B2: any non-canonical address form is rejected (e.g., bare feat_NNNN
    without the `feature:` prefix, or wrong namespace)."""
    state = _seed_state_with_part(features=[_make_feature("feat_0001")])
    bad_geom = _make_geometry_ref("geom_0001", derived_from_features=["feat_0001"])
    bad_geom["fact_provenance"]["derived_from"] = ["feat_0001"]  # missing "feature:" prefix
    payload = {
        "object_uuid": _PART_UUID,
        "geometry_ref_delta": {"added": [bad_geom]},
    }
    with pytest.raises(FoldInconsistencyError, match="canonical"):
        _apply_part_changed(state, payload, actor="agent")


def test_adr_0029_fold_derived_export_provenance_set_equality():
    """Codex2 B2 (recommended): same agreement pattern applied to derived_export
    records — `derived_from` (geom-to-geom lineage per ADR/0005 D7) MUST equal
    the intra-Part `geometry_ref:<id>` entries in fact_provenance.derived_from."""
    state = _seed_state_with_part(
        features=[_make_feature("feat_0001")],
        geometry_refs=[_make_geometry_ref("geom_0001")],
    )
    # derived_export geom that has a dangling extra in fact_provenance.derived_from.
    bad_export = _make_geometry_ref(
        "geom_0002",
        role="derived_export",
        vault=_VAULT_HASH_B,
        derived_from_geoms=["geom_0001"],
    )
    bad_export["fact_provenance"]["derived_from"] = [
        "geometry_ref:geom_0001",
        "geometry_ref:geom_9999",  # extra dangling
    ]
    payload = {
        "object_uuid": _PART_UUID,
        "geometry_ref_delta": {"added": [bad_export]},
    }
    with pytest.raises(FoldInconsistencyError, match="extras"):
        _apply_part_changed(state, payload, actor="agent")


def test_adr_0029_fold_derived_export_provenance_happy_path():
    """derived_export with matching set-equality across derived_from and
    fact_provenance.derived_from."""
    state = _seed_state_with_part(
        features=[_make_feature("feat_0001")],
        geometry_refs=[_make_geometry_ref("geom_0001")],
    )
    good_export = _make_geometry_ref(
        "geom_0002",
        role="derived_export",
        vault=_VAULT_HASH_B,
        derived_from_geoms=["geom_0001"],
    )
    payload = {
        "object_uuid": _PART_UUID,
        "geometry_ref_delta": {"added": [good_export]},
    }
    _apply_part_changed(state, payload, actor="agent")
    by_id = {g["id"]: g for g in state[_PART_UUID]["geometry_ref"]}
    assert "geom_0002" in by_id


def test_adr_0029_fold_cascade_rejects_dangling_derived_export_geom_ref():
    """Codex2 B2 absorption: removing a geometry_ref still referenced by a
    surviving derived_export (geom-to-geom lineage) is cascade-rejected."""
    state = _seed_state_with_part(
        features=[_make_feature("feat_0001")],
        geometry_refs=[
            _make_geometry_ref("geom_0001"),
            _make_geometry_ref(
                "geom_0002",
                role="derived_export",
                vault=_VAULT_HASH_B,
                derived_from_geoms=["geom_0001"],
            ),
        ],
    )
    payload = {
        "object_uuid": _PART_UUID,
        "geometry_ref_delta": {"removed": ["geom_0001"]},  # geom_0002 still references it
    }
    with pytest.raises(FoldInconsistencyError, match="derived_export"):
        _apply_part_changed(state, payload, actor="agent")
