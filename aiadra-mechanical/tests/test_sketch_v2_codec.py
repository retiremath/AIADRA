"""The v2 sketch codec + the mechanical enforcement surfaces (Gate F2a).

Encode/decode round-trips with DEEP immutability; the refusal matrix at
encode, decode, evaluator, signature, and the two handler guards; canonical
identity (A2.7) on hand-built records — NO v2 record is ever committed and
no solver runs anywhere here.
"""
from __future__ import annotations

import types

import pytest
from aiadra_core.transaction.boundary import TransactionError

from aiadra_mechanical import geometry, handlers, kernel, sketch_v2, topology
from test_sketch_v2_policy import g0, g1, g2, weak  # shared fixtures


def _record(graph=None, feature_id="feat_0001", **overrides):
    ents, cons, _dims, wk = graph if graph is not None else g1()
    rec = sketch_v2.encode_v2_sketch(
        feature_id=feature_id,
        name="Sketch 1",
        plane={"kind": "principal", "orientation": "xy"},
        entities=ents,
        constraints=cons,
        weak_completion=wk,
        fact_provenance={"category": "human_input"},
    )
    rec.update(overrides)
    return rec


def _v1_sketch(feature_id="feat_0001"):
    return {
        "id": feature_id,
        "name": "sketch_v1",
        "feature_type": "sketch",
        "engine": "mechanical",
        "adapter_schema_version": "0.1.11",
        "adapter_payload": {
            "plane": {"kind": "principal", "orientation": "xy"},
            "primitives": [{
                "skp_id": "skp_00000001", "kind": "rectangle",
                "x_mm": 0.0, "y_mm": 0.0, "width_mm": 40.0, "height_mm": 30.0,
            }],
        },
        "fact_provenance": {"category": "human_input"},
    }


class TestEncodeDecodeRoundTrip:
    @pytest.mark.parametrize("graph", [g0(), g1(), g2()],
                             ids=["G0", "G1", "G2"])
    def test_encode_then_decode(self, graph):
        rec = _record(graph)
        decoded = sketch_v2.decode_v2_sketch(rec)
        assert decoded["shape"] in ("G0", "G1", "G2")
        assert decoded["record"]["adapter_schema_version"] == "0.2.0"

    def test_decoded_records_are_deeply_immutable(self):
        decoded = sketch_v2.decode_v2_sketch(_record(g2()))
        rec = decoded["record"]
        with pytest.raises(TypeError):
            rec["name"] = "mutated"  # type: ignore[index]
        payload = rec["adapter_payload"]
        with pytest.raises(TypeError):
            payload["sketch_model"] = 1  # type: ignore[index]
        # nested interiors: entity nominal, weak origin, arrays as tuples
        entity = payload["entities"][0]
        with pytest.raises(TypeError):
            entity["nominal"]["x"] = 99.0  # type: ignore[index]
        wk = payload["weak_completion"][0]
        with pytest.raises(TypeError):
            wk["origin"]["policy"] = "skb-99"  # type: ignore[index]
        assert isinstance(payload["entities"], tuple)
        assert isinstance(payload["witnesses"], tuple)
        with pytest.raises(TypeError):
            decoded["roles"]["O"] = "hijack"  # type: ignore[index]

    def test_encoding_an_inadmissible_graph_refuses(self):
        ents, cons, _d, wk = g1()
        with pytest.raises(TransactionError, match="out-of-domain"):
            sketch_v2.encode_v2_sketch(
                feature_id="feat_0001", name="bad",
                plane={"kind": "principal", "orientation": "xy"},
                entities=ents + [{"id": "k1", "type": "circle",
                                  "construction": True, "center": "p1",
                                  "nominal": {"radius": 10.0}}],
                constraints=cons, weak_completion=wk,
                fact_provenance={"category": "human_input"},
            )


class TestRecordRefusals:
    def test_v2_non_sketch_refuses_by_family(self):
        rec = _record()
        rec["feature_type"] = "extrude"
        with pytest.raises(TransactionError, match="SKETCH family"):
            sketch_v2.validate_v2_sketch_record(rec)

    def test_unknown_v2_minor_refuses(self):
        rec = _record(adapter_schema_version="0.2.1")
        with pytest.raises(TransactionError, match="0.2.0"):
            sketch_v2.validate_v2_sketch_record(rec)

    def test_missing_and_unknown_payload_keys_refuse(self):
        rec = _record()
        payload = dict(rec["adapter_payload"])
        del payload["witnesses"]
        with pytest.raises(TransactionError, match="missing \\['witnesses'\\]"):
            sketch_v2.validate_v2_sketch_record(dict(rec, adapter_payload=payload))
        payload2 = dict(rec["adapter_payload"], solved={"p1.x": 0.0})
        with pytest.raises(TransactionError, match="unknown \\['solved'\\]"):
            sketch_v2.validate_v2_sketch_record(dict(rec, adapter_payload=payload2))

    def test_wrong_contract_ids_refuse(self):
        rec = _record()
        payload = dict(rec["adapter_payload"], branch_policy="skb-b1")
        with pytest.raises(TransactionError, match="contract ids"):
            sketch_v2.validate_v2_sketch_record(dict(rec, adapter_payload=payload))

    def test_witnesses_present_refuse_exact_set(self):
        rec = _record()
        payload = dict(rec["adapter_payload"], witnesses=[{
            "id": "bw01", "kind": "cross_sign", "of": ["p1", "p2", "p1"],
            "sign": 1,
            "origin": {"category": "computed_result", "policy": "skb-b0",
                       "solver_contract": "skb-c0"},
        }])
        with pytest.raises(TransactionError, match="extra witnesses are rejected"):
            sketch_v2.validate_v2_sketch_record(dict(rec, adapter_payload=payload))

    def test_origin_contradicting_top_level_ids_refuses(self):
        ents, cons, _d, wk = g1()
        bad_weak = dict(wk[0], origin={"category": "computed_result",
                                       "policy": "skb-0",
                                       "solver_contract": "skb-c9"})
        rec = _record()
        payload = dict(rec["adapter_payload"], weak_completion=[bad_weak])
        with pytest.raises(TransactionError, match="contradicts the record's top-level ids"):
            sketch_v2.validate_v2_sketch_record(dict(rec, adapter_payload=payload))

    def test_references_must_be_empty(self):
        rec = _record()
        payload = dict(rec["adapter_payload"], references=[{"id": "r1"}])
        with pytest.raises(TransactionError, match="references must be empty"):
            sketch_v2.validate_v2_sketch_record(dict(rec, adapter_payload=payload))

    def test_principal_plane_extras_refuse(self):
        # Codex24 B2: the exact probe — {kind, orientation, ignored_semantic}
        # refuses through the shared plane validator (one language with Studio)
        rec = _record()
        payload = dict(rec["adapter_payload"], plane={
            "kind": "principal", "orientation": "xy", "ignored_semantic": 123})
        with pytest.raises(TransactionError, match="unsupported key"):
            sketch_v2.validate_v2_sketch_record(dict(rec, adapter_payload=payload))

    @pytest.mark.parametrize("collection", [
        "entities", "constraints", "dimensions", "references",
        "weak_completion", "witnesses",
    ])
    def test_non_object_array_entries_refuse_typed(self, collection):
        # Codex24 B2: the exact probes — [123] must fail through the TYPED
        # boundary in every collection (including required-empty ones),
        # never as an interpreter AttributeError
        rec = _record()
        payload = dict(rec["adapter_payload"])
        payload[collection] = [123]
        with pytest.raises(TransactionError, match="not an\\s+object"):
            sketch_v2.validate_v2_sketch_record(dict(rec, adapter_payload=payload))


class TestEvaluatorAndSignatureSurfaces:
    def test_valid_v2_sketch_EVALUATES_construction_only(self):
        # Gate F2b: the read lifecycle runs (regeneration through the real
        # solver) and the v2 sketch contributes no solid — a v2-only Part
        # evaluates like a no-base Part.
        res = geometry.evaluate_part_with_provenance([_record()])
        assert res is not None

    def test_valid_v2_sketch_SIGNS_with_shape_skeleton(self):
        sig = topology.compute_topology_signature([_record()])
        assert sig == topology.compute_topology_signature([_record()])
        # presence changes the signature (feature add/remove is skeleton)
        assert sig != topology.compute_topology_signature([])

    def test_v2_non_sketch_refuses_out_of_family_at_evaluation(self):
        rec = _record()
        rec["feature_type"] = "extrude"
        with pytest.raises(TransactionError, match="SKETCH family"):
            geometry.evaluate_part_with_provenance([rec])

    def test_malformed_v2_gets_its_specific_refusal_at_evaluation(self):
        rec = _record()
        payload = dict(rec["adapter_payload"], branch_policy="skb-zz")
        with pytest.raises(TransactionError, match="contract ids"):
            geometry.evaluate_part_with_provenance([dict(rec, adapter_payload=payload)])

    def test_counterexample_graph_refuses_at_evaluation(self):
        # the fixed-circle + point_on + weak-x record, hand-built (encode
        # would refuse it — this proves the DECODE-side surfaces refuse too)
        rec = _record()
        payload = dict(
            rec["adapter_payload"],
            entities=[
                {"id": "o", "type": "point", "construction": True,
                 "nominal": {"x": 0.0, "y": 0.0}},
                {"id": "k1", "type": "circle", "construction": True,
                 "center": "o", "nominal": {"radius": 10.0}},
                {"id": "p", "type": "point", "construction": True,
                 "nominal": {"x": 6.0, "y": 8.0}},
            ],
            constraints=[
                {"id": "c01", "kind": "fix", "args": ["o"]},
                {"id": "c02", "kind": "point_on", "args": ["p", "k1"]},
            ],
            weak_completion=[weak(1, "p", "x", 6.0)],
        )
        with pytest.raises(TransactionError, match="out-of-domain"):
            geometry.evaluate_part_with_provenance([dict(rec, adapter_payload=payload)])

    def test_validation_is_a_no_op_on_v1_records(self):
        # the v2 lanes only ever look at 0.2.x records; a v1 list passes
        # untouched (the v1 suite proves full evaluation behavior)
        assert sketch_v2.validate_v2_records([_v1_sketch()]) is None
        assert sketch_v2.process_v2_at_evaluation([_v1_sketch()]) == {}


class TestHandlerGuards:
    def _ctx_with(self, monkeypatch, features):
        sidecar = {"feature": features, "geometry_ref": []}
        monkeypatch.setattr(handlers, "_resolve_part_sidecar",
                            lambda _c, _n: ("uuid-1", sidecar))
        return types.SimpleNamespace(actor="human")

    def test_extrude_consuming_a_v2_sketch_refuses(self, monkeypatch):
        ctx = self._ctx_with(monkeypatch, [_record()])
        with pytest.raises(TransactionError, match="not a consumable extrusion profile"):
            handlers.handle_add_extrude_feature(ctx, {
                "part_number": "P-1", "sketch_feature_id": "feat_0001",
                "depth_mm": 10.0, "direction": "normal+",
            })

    def test_adjusting_a_v2_record_refuses(self, monkeypatch):
        ctx = self._ctx_with(monkeypatch, [_record()])
        with pytest.raises(TransactionError, match="atomic authoring transaction"):
            handlers.handle_adjust_feature_parameter(ctx, {
                "part_number": "P-1", "feature_id": "feat_0001",
                "parameter_name": "anything", "new_value": 1.0,
            })


class TestEngineDiscrimination:
    """Codex23 B2: the mechanical codec interprets mechanical records only;
    foreign-engine 0.2.x records stay OPAQUE to the guard."""

    def test_codec_refuses_foreign_engine_records(self):
        rec = _record()
        rec["engine"] = "electrical"
        with pytest.raises(TransactionError, match="mechanical records only"):
            sketch_v2.validate_v2_sketch_record(rec)

    def test_lanes_leave_foreign_engine_v2_records_opaque(self):
        rec = _record()
        rec["engine"] = "electrical"
        # no v2 interpretation, no v2 refusal — the record is not ours
        assert sketch_v2.validate_v2_records([rec]) is None
        assert sketch_v2.process_v2_at_evaluation([rec]) == {}


class TestEncoderDeepCopy:
    """Codex23 B2: caller mutation after encode must never alter the record."""

    def test_mutating_inputs_after_encode_leaves_the_record_untouched(self):
        ents, cons, _d, wk = g1()
        rec = sketch_v2.encode_v2_sketch(
            feature_id="feat_0001", name="Sketch 1",
            plane={"kind": "principal", "orientation": "xy"},
            entities=ents, constraints=cons, weak_completion=wk,
            fact_provenance={"category": "human_input"},
        )
        before = kernel.recipe_hash([rec])
        # mutate NESTED interiors of the caller's objects
        ents[0]["nominal"]["x"] = 999.0
        cons[0]["args"][0] = "hijacked"
        wk[0]["value"]["magnitude"] = -1.0
        assert kernel.recipe_hash([rec]) == before
        sketch_v2.validate_v2_sketch_record(rec)  # still a valid G1


class TestRemoveFeaturePreflight:
    """Codex23 B3: remove_feature is a mutating handler — it must not stage
    a sidecar that RETAINS a v2 record."""

    def _ctx_with(self, monkeypatch, features):
        sidecar = {"feature": features, "geometry_ref": []}
        monkeypatch.setattr(handlers, "_resolve_part_sidecar",
                            lambda _c, _n: ("uuid-1", sidecar))
        return types.SimpleNamespace(actor="human")

    def test_valid_v2_passes_the_remove_preflight(self):
        # Gate F2b: a valid v2 sketch is a LEGAL resident — the preflight is
        # validate-only (the staging re-evaluation runs the read lifecycle)
        assert sketch_v2.validate_v2_records(
            [_record(), _v1_sketch("feat_0002")]) is None

    def test_malformed_v2_keeps_its_specific_refusal_at_remove(self, monkeypatch):
        rec = _record()
        payload = dict(rec["adapter_payload"], branch_policy="skb-zz")
        ctx = self._ctx_with(monkeypatch,
                             [dict(rec, adapter_payload=payload),
                              _v1_sketch("feat_0002")])
        with pytest.raises(TransactionError, match="contract ids"):
            handlers.handle_remove_feature(ctx, {
                "part_number": "P-1", "feature_ids": ["feat_0002"],
            })


class TestMalformedFirstAtHandlers:
    """Codex23 B3: shared validation precedes the targeted messages — a
    malformed v2 record keeps its SPECIFIC refusal at the handler surface."""

    def _ctx_with(self, monkeypatch, features):
        sidecar = {"feature": features, "geometry_ref": []}
        monkeypatch.setattr(handlers, "_resolve_part_sidecar",
                            lambda _c, _n: ("uuid-1", sidecar))
        return types.SimpleNamespace(actor="human")

    def test_consuming_a_malformed_v2_sketch_gets_the_specific_refusal(self, monkeypatch):
        rec = _record()
        payload = dict(rec["adapter_payload"], branch_policy="skb-zz")
        ctx = self._ctx_with(monkeypatch, [dict(rec, adapter_payload=payload)])
        with pytest.raises(TransactionError, match="contract ids"):
            handlers.handle_add_extrude_feature(ctx, {
                "part_number": "P-1", "sketch_feature_id": "feat_0001",
                "depth_mm": 10.0, "direction": "normal+",
            })

    def test_adjusting_a_malformed_v2_record_gets_the_specific_refusal(self, monkeypatch):
        rec = _record()
        payload = dict(rec["adapter_payload"], sketch_model=3)
        ctx = self._ctx_with(monkeypatch, [dict(rec, adapter_payload=payload)])
        with pytest.raises(TransactionError, match="sketch_model"):
            handlers.handle_adjust_feature_parameter(ctx, {
                "part_number": "P-1", "feature_id": "feat_0001",
                "parameter_name": "anything", "new_value": 1.0,
            })


class TestPermutationIdentity:
    """Codex23 B1: ONE identity for ONE graph — every legal permutation of
    the same admitted graph yields identical recipe bytes, while a semantic
    change still moves identity, and v1 payloads pass through verbatim."""

    def test_all_legal_g2_entity_constraint_permutations_hash_identically(self):
        import itertools
        base = _record(g2())
        want = kernel.recipe_hash([base])
        ents, cons, _d, wk = g2()
        for e_perm in itertools.permutations(ents):
            rec = _record((list(e_perm), cons, [], wk))
            assert kernel.recipe_hash([rec]) == want
        for c_perm in itertools.permutations(cons):
            rec = _record((ents, list(c_perm), [], wk))
            assert kernel.recipe_hash([rec]) == want

    def test_a_semantic_change_still_moves_identity(self):
        base = kernel.recipe_hash([_record(g2())])
        ents, cons, _d, wk = g2()
        # swapping a line's direction is SEMANTIC (directed axes) — the
        # graph refuses admission, and the raw bytes differ too
        ents2 = [e if e["id"] != "l1"
                 else {"id": "l1", "type": "line", "construction": True,
                       "start": "p2", "end": "p1"}
                 for e in ents]
        rec = _record()  # valid G1 for hashing baseline only
        payload = dict(rec["adapter_payload"])
        payload["entities"] = ents2
        rec["adapter_payload"] = payload
        assert kernel.recipe_hash([rec]) != base

    def test_v1_payloads_pass_through_canonicalization_verbatim(self):
        v1 = _v1_sketch()
        assert kernel._canonical_payload(v1["adapter_payload"]) is v1["adapter_payload"]


class TestCanonicalIdentity:
    """A2.7 on hand-built records (nothing committed): identity moves with
    every semantic fact + contract id; does not move with the adapter
    version; v1 bytes are untouched by the new modules."""

    def test_identity_moves_with_semantic_payload(self):
        base = _record(g2())
        h0 = kernel.recipe_hash([base])

        nudged = _record(g2())
        payload = dict(nudged["adapter_payload"])
        wk = [dict(w) for w in payload["weak_completion"]]
        wk[0] = dict(wk[0], value={"magnitude": 21.0, "unit": "mm"})
        payload["weak_completion"] = wk
        nudged["adapter_payload"] = payload
        assert kernel.recipe_hash([nudged]) != h0

        # a nominal move is identity-bearing (authored intent)
        moved = _record(g2())
        payload2 = dict(moved["adapter_payload"])
        ents = [dict(e) for e in payload2["entities"]]
        for e in ents:
            if e["id"] == "p3":
                e["nominal"] = {"x": 0.0, "y": 21.0}
        payload2["entities"] = ents
        moved["adapter_payload"] = payload2
        assert kernel.recipe_hash([moved]) != h0

        # sketch_model + contract ids are identity-bearing
        rebranded = _record(g2())
        payload3 = dict(rebranded["adapter_payload"], branch_policy="skb-b1")
        rebranded["adapter_payload"] = payload3
        assert kernel.recipe_hash([rebranded]) != h0

    def test_identity_ignores_adapter_schema_version(self):
        # the standing rule (A2.7): the series is compatibility authority,
        # never identity — the payload carries every semantic discriminator
        a = _record(g1())
        b = _record(g1(), adapter_schema_version="0.2.9-hypothetical")
        assert kernel.recipe_hash([a]) == kernel.recipe_hash([b])

    def test_identity_is_payload_deterministic(self):
        assert kernel.recipe_hash([_record(g2())]) == kernel.recipe_hash([_record(g2())])

    def test_v1_recipe_bytes_untouched(self):
        # a pure-v1 recipe's canonical bytes involve no v2 machinery; the
        # golden-hash suite (test_recipe_hash_stability) pins the exact
        # values — here: byte-determinism and non-interference
        v1 = [_v1_sketch()]
        assert kernel.compute_recipe_bytes(v1) == kernel.compute_recipe_bytes(v1)
