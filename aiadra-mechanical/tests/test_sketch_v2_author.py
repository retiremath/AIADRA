"""Gate F2b: the A2.9 authoring transaction, regeneration, and the first
v2 writer — the slice-1 references sketch.

Everything runs through the REAL verified solver artifact (skipped loudly
when it is absent, like the corpus floor). Solved coordinates are proven
DERIVED-only: never persisted, never identity-bearing.
"""
from __future__ import annotations

import types

import pytest
from aiadra_core.transaction.boundary import TransactionError

from aiadra_mechanical import display as display_mod
from aiadra_mechanical import handlers, kernel, sketch_v2
from aiadra_mechanical.solver import SolverArtifactMissingError, load_solver


@pytest.fixture(scope="module", autouse=True)
def _require_artifact():
    try:
        load_solver()
    except SolverArtifactMissingError as exc:
        pytest.skip(f"native solver artifact not built locally: {exc}")


def _author(axes="xy", x=20.0, y=20.0, fid="feat_0001"):
    return sketch_v2.author_reference_sketch(
        feature_id=fid, name=f"references_{fid}",
        plane={"kind": "principal", "orientation": "xy"},
        axes=axes, x_axis_mm=x, y_axis_mm=y,
        fact_provenance={"category": "human_input"},
    )


class TestAuthoringTransaction:
    @pytest.mark.parametrize("axes,shape,n_weak", [
        ("none", "G0", 0), ("x", "G1", 1), ("xy", "G2", 2),
    ])
    def test_authoring_produces_the_admitted_shape(self, axes, shape, n_weak):
        rec = _author(axes=axes)
        decoded = sketch_v2.decode_v2_sketch(rec)
        assert decoded["shape"] == shape
        assert len(rec["adapter_payload"]["weak_completion"]) == n_weak

    def test_weak_completion_is_the_solver_lane_verbatim(self):
        # the skb-0 records come from the SOLVE RESULT, never hand-built:
        # canonical ids, targets, magnitudes == authored nominals, the
        # verbatim origin block
        rec = _author()
        w1, w2 = rec["adapter_payload"]["weak_completion"]
        assert (w1["id"], w1["target"]) == ("w01", {"entity": "skp_0002", "parameter": "x"})
        assert (w2["id"], w2["target"]) == ("w02", {"entity": "skp_0003", "parameter": "y"})
        assert w1["value"] == {"magnitude": 20.0, "unit": "mm"}
        assert w1["origin"] == {"category": "computed_result", "policy": "skb-0",
                                "solver_contract": "skb-c0"}

    def test_no_solved_coordinate_is_persisted(self):
        # structurally guaranteed by the closed payload key set — asserted
        # anyway: the record carries facts only
        rec = _author()
        payload = rec["adapter_payload"]
        assert set(payload.keys()) == {
            "sketch_model", "solver_contract", "weak_policy", "branch_policy",
            "plane", "entities", "constraints", "dimensions", "references",
            "weak_completion", "witnesses"}
        # identity is solve-independent: authoring twice yields identical bytes
        assert kernel.recipe_hash([rec]) == kernel.recipe_hash([_author()])

    def test_atomicity_nothing_exists_on_refusal(self):
        with pytest.raises(TransactionError, match="axes must be one of"):
            _author(axes="diagonal")
        with pytest.raises(TransactionError, match="strictly positive"):
            _author(x=-5.0)
        with pytest.raises(TransactionError, match="strictly positive"):
            _author(x=True)  # bools are not numbers anywhere


class TestRegeneration:
    def test_read_lifecycle_returns_derived_solved(self):
        rec = _author()
        solved = sketch_v2.regenerate_v2_sketch(rec)
        assert solved["skp_0002.x"] == 20.0 and solved["skp_0002.y"] == 0.0
        assert solved["skp_0003.x"] == 0.0 and solved["skp_0003.y"] == 20.0

    def test_regeneration_performs_no_mutation(self):
        rec = _author()
        before = kernel.recipe_hash([rec])
        for _ in range(3):
            sketch_v2.regenerate_v2_sketch(rec)
        assert kernel.recipe_hash([rec]) == before

    def test_committed_weak_differing_from_derivation_cannot_exist_under_skb_b0(self):
        # A2.9's never-remint check compares committed vs derived; under
        # skb-b0 a shape-valid-but-different weak set is unrepresentable
        # (admission pins target AND magnitude==nominal), so tampering
        # refuses at ADMISSION first — the earlier boundary
        rec = _author(axes="x")
        payload = dict(rec["adapter_payload"])
        weak = [dict(payload["weak_completion"][0])]
        weak[0] = dict(weak[0], value={"magnitude": 19.0, "unit": "mm"})
        payload["weak_completion"] = weak
        with pytest.raises(TransactionError, match="contradicts the authored nominal"):
            sketch_v2.regenerate_v2_sketch(dict(rec, adapter_payload=payload))

    def test_evaluation_lane_returns_the_solved_map(self):
        rec = _author()
        solved = sketch_v2.process_v2_at_evaluation([rec, ])
        assert set(solved.keys()) == {"feat_0001"}


class TestFirstWriterHandler:
    def _ctx(self, monkeypatch, features=None):
        sidecar = {"feature": list(features or []), "geometry_ref": []}
        staged = {}
        events = []
        monkeypatch.setattr(handlers, "_resolve_part_sidecar",
                            lambda _c, _n: ("uuid-1", sidecar))
        # the OCCT validity gate is exercised by the evaluator suite; the
        # handler test isolates STAGING (atomic single-record semantics)
        monkeypatch.setattr(handlers, "_gate_validity", lambda _c, _f: None)
        ctx = types.SimpleNamespace(
            actor="human",
            stage_sidecar=lambda uuid, sc: staged.update({uuid: sc}),
            emit_event=lambda kind, payload: events.append((kind, payload)),
            # the defensive check in _stage_recipe demands the CANONICAL hash
            stage_vault_bytes=lambda data: (
                handlers.vault_ref_for_bytes(data), "vault/x"),
        )
        return ctx, staged, events

    def test_the_first_v2_write_stages_one_record_atomically(self, monkeypatch):
        ctx, staged, events = self._ctx(monkeypatch)
        handlers.handle_add_reference_sketch(ctx, {"part_number": "P-1"})
        sc = staged["uuid-1"]
        assert len(sc["feature"]) == 1 and len(sc["geometry_ref"]) == 1
        rec = sc["feature"][0]
        assert rec["adapter_schema_version"] == "0.2.0"
        assert sketch_v2.decode_v2_sketch(rec)["shape"] == "G2"
        (kind, payload), = events
        assert kind == "part_changed"
        assert payload["feature_delta"]["added"][0]["id"] == rec["id"]

    def test_a_refused_authoring_stages_nothing(self, monkeypatch):
        ctx, staged, events = self._ctx(monkeypatch)
        with pytest.raises(TransactionError, match="axes must be one of"):
            handlers.handle_add_reference_sketch(
                ctx, {"part_number": "P-1", "axes": "bogus"})
        assert staged == {} and events == []

    def test_the_op_is_registered(self):
        import aiadra_mechanical

        seen = {}
        registrar = types.SimpleNamespace(
            add_operation=lambda k, h: seen.update({k: h}),
            add_read_operation=lambda *a, **kw: None,
        )
        aiadra_mechanical.register(registrar)
        assert seen["mechanical.add_reference_sketch"] is handlers.handle_add_reference_sketch


class TestDisplayV2Construction:
    def test_solved_derived_world_geometry(self):
        rec = _author()
        items = display_mod.build_v2_construction([rec])
        (item,) = items
        assert item["shape"] == "G2" and item["construction"] is True
        pts = {p["id"]: p["at"] for p in item["points"]}
        assert pts["skp_0001"] == [0.0, 0.0, 0.0]
        assert pts["skp_0002"] == [20.0, 0.0, 0.0]
        assert pts["skp_0003"] == [0.0, 20.0, 0.0]
        assert {ln["id"] for ln in item["lines"]} == {"skp_0004", "skp_0005"}

    def test_no_solid_display_carries_v2_construction_at_1_3(self):
        rec = _author()
        payload = display_mod._no_solid_display(
            [rec], object_uuid="u-1", object_number="P-1",
            geometry_ref="sha256:" + "0" * 64, cache_key="ck",
            linear_deflection_mm=0.1, angular_deflection_rad=0.3,
        )
        assert payload["display_representation_version"] == "1.3"
        assert len(payload["v2_construction"]) == 1

    def test_core_contract_validates_the_1_3_payload(self):
        from aiadra_core.protocol.display import DisplayRepresentation

        rec = _author()
        payload = display_mod._no_solid_display(
            [rec], object_uuid="u-1", object_number="P-1",
            geometry_ref="sha256:" + "0" * 64, cache_key="ck",
            linear_deflection_mm=0.1, angular_deflection_rad=0.3,
        )
        dr = DisplayRepresentation.from_engine_dict(payload)
        assert dr.v2_construction[0].shape == "G2"
        assert dr.v2_construction[0].points[1].at == (20.0, 0.0, 0.0)

    def test_populated_v2_construction_on_a_pre_1_3_version_is_a_producer_error(self):
        from aiadra_core.protocol.display import (
            DisplayContractError, DisplayRepresentation)

        rec = _author()
        payload = display_mod._no_solid_display(
            [rec], object_uuid="u-1", object_number="P-1",
            geometry_ref="sha256:" + "0" * 64, cache_key="ck",
            linear_deflection_mm=0.1, angular_deflection_rad=0.3,
        )
        payload["display_representation_version"] = "1.2"
        with pytest.raises(DisplayContractError, match="requires contract v1.3"):
            DisplayRepresentation.from_engine_dict(payload)
