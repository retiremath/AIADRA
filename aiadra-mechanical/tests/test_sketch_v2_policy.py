"""skb-b0 pure policy: doc parity, the graph predicate, draft vectors.

The normative authority is Docs/SolverContracts/skb-b0.md (ADR/0044 A2.10);
these tests EXTRACT its machine-readable blocks and parity-check the
implementation's COMPLETE structures (Codex23 B4: comparing keys alone
would let normative content drift silently). The witness measures are NOT
normative under skb-b0 (its catalog is empty) — they live as DRAFT material
(witness-kinds-draft.md + solver/witness_draft.py) and are executed here
against the DRAFT doc's vectors so the prototype does not rot.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest

from aiadra_mechanical.solver import branch_policy as bp
from aiadra_mechanical.solver import witness_draft as wd

# ---------------------------------------------------------------- doc access


def _doc_text(name: str) -> str:
    for parent in Path(__file__).resolve().parents:
        cand = parent / "Docs" / "SolverContracts" / name
        if cand.is_file():
            return cand.read_text(encoding="utf-8")
    raise AssertionError(f"Docs/SolverContracts/{name} not found above tests/")


def _doc_block(doc: str, prefix: str, marker: str):
    text = _doc_text(doc)
    m = re.search(
        rf"<!-- {prefix}:{marker} -->\s*```json\s*(.*?)```", text, re.DOTALL
    )
    assert m, f"block {prefix}:{marker} missing from {doc}"
    return json.loads(m.group(1))


# ---------------------------------------------------------------- parity


class TestDocParity:
    def test_constants_match_the_normative_source(self):
        # Codex23 B4: skb-b0 carries NO epsilon — its catalog is empty and
        # freezes no measure
        assert _doc_block("skb-b0.md", "skb-b0", "constants") == bp.CONSTANTS
        assert "epsilon_dimensionless" not in bp.CONSTANTS

    def test_local_table_matches_the_normative_source(self):
        assert _doc_block("skb-b0.md", "skb-b0", "local-table") == bp.LOCAL_TABLE

    def test_graph_predicate_matches_the_normative_source_COMPLETELY(self):
        # Codex23 B4: the WHOLE structure — a normative role, fact, weak
        # target, or guard edit in the document is a red suite, not a
        # key-set coincidence
        assert _doc_block("skb-b0.md", "skb-b0", "graph-predicate") == bp.GRAPH_PREDICATE

    def test_array_order_law_matches_the_normative_source(self):
        # Codex24 B1: the ordering rule is machine-readable and parity-
        # guarded — prose can never again claim free weak ordering while
        # the executable contract rejects it
        assert _doc_block("skb-b0.md", "skb-b0", "array-order") == bp.ARRAY_ORDER
        assert {k for k, v in bp.ARRAY_ORDER.items() if v == "unordered"} == {
            "entities", "constraints", "dimensions", "references"}
        assert {k for k, v in bp.ARRAY_ORDER.items() if v == "canonical"} == {
            "weak_completion", "witnesses"}


# ---------------------------------------------------------------- draft vectors


def _num(v):
    return float("inf") if v == "inf" else float(v)


class TestDraftVectors:
    """The DRAFT measures (not skb-b0-normative) against the DRAFT doc."""

    def test_all_vectors_execute_against_the_draft_equations(self):
        vectors = _doc_block("witness-kinds-draft.md", "witness-draft",
                             "golden-vectors")
        assert len(vectors) >= 20
        for i, vec in enumerate(vectors):
            if vec["kind"] == "cross_sign":
                got = wd.cross_sign_measure(
                    tuple(map(_num, vec["a"])),
                    tuple(map(_num, vec["b"])),
                    tuple(map(_num, vec["p"])),
                )
            else:
                assert vec["kind"] == "side_of_line"
                got = wd.side_of_line_measure(
                    tuple(map(_num, vec["line_a"])),
                    tuple(map(_num, vec["line_b"])),
                    tuple(map(_num, vec["center"])),
                    _num(vec["radius"]),
                )
            want = vec["expect"]
            label = f"vector {i} ({vec['kind']}): "
            assert got.classification == want["classification"], (
                label + f"classification {got.classification} != {want['classification']}"
            )
            if "m" in want:
                assert got.m is not None, label + "measure undefined"
                assert abs(got.m - want["m"]) <= 1e-15, (
                    label + f"m {got.m!r} != {want['m']!r}"
                )

    def test_draft_epsilon_boundary_is_inclusive_both_sides(self):
        for sign in (+1.0, -1.0):
            r = wd._classify(sign * wd.DRAFT_EPSILON)
            assert r.classification == "degenerate"
            r = wd._classify(sign * wd.DRAFT_EPSILON * 2.0)
            assert r.classification == ("+1" if sign > 0 else "-1")

    def test_non_finite_measure_is_undefined_not_signed(self):
        assert wd._classify(math.inf).classification == "undefined"
        assert wd._classify(math.nan).classification == "undefined"

    def test_booleans_are_not_measure_inputs(self):
        # Codex23 B2: one number language everywhere — bools refuse
        assert wd.cross_sign_measure((0.0, 0.0), (10.0, 0.0),
                                     (True, 10.0)).classification == "undefined"
        assert wd.side_of_line_measure((0.0, 0.0), (10.0, 0.0), (5.0, 3.0),
                                       True).classification == "undefined"


# ---------------------------------------------------------------- fixtures


def pt(eid, x, y):
    return {"id": eid, "type": "point", "construction": True,
            "nominal": {"x": x, "y": y}}


def ln(eid, start, end):
    return {"id": eid, "type": "line", "construction": True,
            "start": start, "end": end}


def weak(idx, entity, parameter, magnitude):
    return {"id": f"w{idx:02d}", "kind": "fix_param",
            "target": {"entity": entity, "parameter": parameter},
            "value": {"magnitude": magnitude, "unit": "mm"},
            "strength": "weak", "role": "driving", "visibility": "internal",
            "origin": {"category": "computed_result", "policy": "skb-0",
                       "solver_contract": "skb-c0"}}


def g0():
    return ([pt("p1", 0.0, 0.0)], [{"id": "c01", "kind": "fix", "args": ["p1"]}], [], [])


def g1():
    return (
        [pt("p1", 0.0, 0.0), pt("p2", 20.0, 0.0), ln("l1", "p1", "p2")],
        [{"id": "c01", "kind": "fix", "args": ["p1"]},
         {"id": "c02", "kind": "horizontal", "args": ["l1"]}],
        [],
        [weak(1, "p2", "x", 20.0)],
    )


def g2():
    return (
        [pt("p1", 0.0, 0.0), pt("p2", 20.0, 0.0), pt("p3", 0.0, 20.0),
         ln("l1", "p1", "p2"), ln("l2", "p1", "p3")],
        [{"id": "c01", "kind": "fix", "args": ["p1"]},
         {"id": "c02", "kind": "horizontal", "args": ["l1"]},
         {"id": "c03", "kind": "vertical", "args": ["l2"]}],
        [],
        [weak(1, "p2", "x", 20.0), weak(2, "p3", "y", 20.0)],
    )


# ---------------------------------------------------------------- predicate


class TestAdmission:
    def test_g0_g1_g2_admit_with_role_binding(self):
        assert bp.admit_graph(*g0()).shape == "G0"
        a1 = bp.admit_graph(*g1())
        assert (a1.shape, a1.roles["O"], a1.roles["PX"]) == ("G1", "p1", "p2")
        a2 = bp.admit_graph(*g2())
        assert (a2.shape, a2.roles["PY"], a2.roles["AY"]) == ("G2", "p3", "l2")

    def test_matching_is_structural_not_positional(self):
        # permuting the ENTITY and CONSTRAINT arrays admits identically
        ents, cons, dims, wk = g2()
        a = bp.admit_graph(list(reversed(ents)), list(reversed(cons)), dims, wk)
        assert a.shape == "G2" and dict(a.roles) == dict(bp.admit_graph(*g2()).roles)

    def test_weak_array_order_is_canonical_not_free(self):
        # the WEAK array is contract-ordered (w01, w02 in canonical parameter
        # order) — swapping it refuses, unlike entity/fact permutation
        ents, cons, dims, wk = g2()
        with pytest.raises(bp.OutOfDomain, match="canonical"):
            bp.admit_graph(ents, cons, dims, list(reversed(wk)))

    def test_derived_witness_set_is_exactly_empty(self):
        adm = bp.admit_graph(*g1())
        assert bp.derive_witness_descriptors(adm) == ()
        bp.validate_witness_set([], adm)
        with pytest.raises(bp.OutOfDomain, match="extra witnesses are rejected"):
            bp.validate_witness_set(
                [{"id": "bw01", "kind": "cross_sign", "of": ["p1", "p2", "p1"],
                  "sign": 1}], adm)


class TestCounterexampleAndLocalTable:
    """Codex21's fixed-circle + point_on + weak-x counterexample and its
    variants — permanent named negatives (layer 1 refusals)."""

    def _counterexample(self):
        ents = [pt("o", 0.0, 0.0),
                {"id": "k1", "type": "circle", "construction": True,
                 "center": "o", "nominal": {"radius": 10.0}},
                pt("p", 6.0, 8.0)]
        cons = [{"id": "c01", "kind": "fix", "args": ["o"]},
                {"id": "c02", "kind": "point_on", "args": ["p", "k1"]}]
        wk = [weak(1, "p", "x", 6.0)]
        return ents, cons, [], wk

    def test_the_counterexample_refuses_out_of_domain(self):
        with pytest.raises(bp.OutOfDomain, match="outside the local table"):
            bp.admit_graph(*self._counterexample())

    def test_counterexample_permutation_variants_refuse_identically(self):
        ents, cons, dims, wk = self._counterexample()
        with pytest.raises(bp.OutOfDomain):
            bp.admit_graph(list(reversed(ents)), list(reversed(cons)), dims, wk)

    def test_equal_line_composition_refuses(self):
        # the equal(line,line) nonlinear composition named by Codex20/21
        ents, cons, dims, wk = g2()
        cons2 = cons + [{"id": "c04", "kind": "equal", "args": ["l1", "l2"]}]
        with pytest.raises(bp.OutOfDomain, match="outside the local table"):
            bp.admit_graph(ents, cons2, dims, wk)

    def test_dimensions_refuse(self):
        ents, cons, _, wk = g1()
        with pytest.raises(bp.OutOfDomain, match="no dimensions"):
            bp.admit_graph(ents, cons, [{"id": "d01", "kind": "length",
                                         "args": ["l1"], "value_mm": 20.0}], wk)

    def test_non_construction_entity_refuses(self):
        ents, cons, dims, wk = g0()
        ents2 = [dict(ents[0], construction=False)]
        with pytest.raises(bp.OutOfDomain, match="construction"):
            bp.admit_graph(ents2, cons, dims, wk)


class TestClosedNestedShapes:
    """Codex23 B2: unknown nested keys never become identity-bearing no-ops,
    and booleans are not numbers — the exact probes from the review."""

    def test_point_with_unknown_field_refuses(self):
        ents, cons, dims, wk = g0()
        ents2 = [dict(ents[0], ignored_semantic=123)]
        with pytest.raises(bp.OutOfDomain, match="unknown fields"):
            bp.admit_graph(ents2, cons, dims, wk)

    def test_fix_constraint_with_unknown_field_refuses(self):
        ents, cons, dims, wk = g0()
        cons2 = [dict(cons[0], ignored_semantic=123)]
        with pytest.raises(bp.OutOfDomain, match="unknown fields"):
            bp.admit_graph(ents, cons2, dims, wk)

    def test_boolean_nominal_refuses(self):
        # Python bool subclasses int; the strict predicate refuses it —
        # matching TypeScript's typeof === 'number' on the Studio surface
        ents, cons, dims, wk = g0()
        ents2 = [dict(ents[0], nominal={"x": True, "y": False})]
        with pytest.raises(bp.OutOfDomain, match="strict finite numeric"):
            bp.admit_graph(ents2, cons, dims, wk)

    def test_boolean_weak_magnitude_refuses(self):
        ents, cons, dims, wk = g1()
        bad = dict(wk[0], value={"magnitude": True, "unit": "mm"})
        with pytest.raises(bp.OutOfDomain, match="strict finite"):
            bp.admit_graph(ents, cons, dims, [bad])

    def test_weak_target_with_extra_key_refuses(self):
        ents, cons, dims, wk = g1()
        bad = dict(wk[0], target={"entity": "p2", "parameter": "x", "note": "?"})
        with pytest.raises(bp.OutOfDomain, match="target"):
            bp.admit_graph(ents, cons, dims, [bad])

    def test_line_with_non_string_refs_refuses(self):
        ents, cons, dims, wk = g1()
        ents2 = [e if e["id"] != "l1"
                 else {"id": "l1", "type": "line", "construction": True,
                       "start": 1, "end": 2}
                 for e in ents]
        with pytest.raises(bp.OutOfDomain, match="entity-id strings"):
            bp.admit_graph(ents2, cons, dims, wk)

    def test_non_record_entries_refuse_typed_at_the_policy_too(self):
        # Codex24 B2: never an interpreter AttributeError — typed everywhere
        ents, cons, dims, wk = g1()
        with pytest.raises(bp.OutOfDomain, match="not a record"):
            bp.admit_graph([123], cons, dims, wk)
        with pytest.raises(bp.OutOfDomain, match="not a record"):
            bp.admit_graph(ents, [123], dims, wk)
        with pytest.raises(bp.OutOfDomain, match="not a record"):
            bp.admit_graph(ents, cons, dims, [123])


class TestLayer2Independence:
    """Codex22 N2: fixtures that PASS layer 1 and fail ONLY the whole-graph
    predicate — layer 2 is real authority, not a duplicate of layer 1."""

    def test_g1_plus_extra_construction_point_refuses(self):
        ents, cons, dims, wk = g1()
        with pytest.raises(bp.OutOfDomain, match="matches no admitted shape"):
            bp.admit_graph(ents + [pt("p9", 5.0, 5.0)], cons, dims, wk)

    def test_wrong_weak_target_refuses(self):
        ents, cons, dims, _ = g1()
        with pytest.raises(bp.OutOfDomain, match="target"):
            bp.admit_graph(ents, cons, dims, [weak(1, "p2", "y", 0.0)])

    def test_missing_axis_fact_refuses(self):
        ents, cons, dims, wk = g1()
        cons2 = [c for c in cons if c["kind"] != "horizontal"]
        with pytest.raises(bp.OutOfDomain, match="exactly one horizontal"):
            bp.admit_graph(ents, cons2, dims, wk)

    def test_extra_horizontal_line_and_fact_refuses(self):
        ents, cons, dims, wk = g1()
        ents2 = ents + [pt("p8", 30.0, 0.0), ln("l9", "p1", "p8")]
        cons2 = cons + [{"id": "c09", "kind": "horizontal", "args": ["l9"]}]
        # the census matches G2's counts, so the refusal is G2's missing
        # vertical — still typed out-of-domain, which is the contract
        with pytest.raises(bp.OutOfDomain, match="out-of-domain"):
            bp.admit_graph(ents2, cons2, dims, wk)

    def test_g2_with_incomplete_weak_set_refuses(self):
        ents, cons, dims, wk = g2()
        with pytest.raises(bp.OutOfDomain, match="exactly two weak records"):
            bp.admit_graph(ents, cons, dims, wk[:1])

    def test_axis_not_directed_from_origin_refuses(self):
        ents, cons, dims, wk = g1()
        ents2 = [e if e["id"] != "l1" else ln("l1", "p2", "p1") for e in ents]
        with pytest.raises(bp.OutOfDomain, match="DIRECTED from the fixed origin"):
            bp.admit_graph(ents2, cons, dims, wk)


class TestN1EffectiveValuesAndGuards:
    """Codex22 N1: full verbatim weak records, magnitude == nominal, SIGNED
    guards on effective values, boundaries on both sides."""

    def test_magnitude_contradicting_nominal_refuses(self):
        ents, cons, dims, _ = g1()
        with pytest.raises(bp.OutOfDomain, match="contradicts the authored nominal"):
            bp.admit_graph(ents, cons, dims, [weak(1, "p2", "x", 19.0)])

    def test_guard_boundary_at_L_min_refuses_and_above_admits(self):
        # displacement exactly L_min → refuse (strictly-greater passes)
        ents = [pt("p1", 0.0, 0.0), pt("p2", bp.L_MIN_MM, 0.0), ln("l1", "p1", "p2")]
        cons = [{"id": "c01", "kind": "fix", "args": ["p1"]},
                {"id": "c02", "kind": "horizontal", "args": ["l1"]}]
        with pytest.raises(bp.OutOfDomain, match="signed guard failed"):
            bp.admit_graph(ents, cons, [], [weak(1, "p2", "x", bp.L_MIN_MM)])
        ents2 = [pt("p1", 0.0, 0.0), pt("p2", 3.0 * bp.L_MIN_MM, 0.0),
                 ln("l1", "p1", "p2")]
        assert bp.admit_graph(ents2, cons, [],
                              [weak(1, "p2", "x", 3.0 * bp.L_MIN_MM)]).shape == "G1"

    def test_negative_displacement_refuses_signed_direction(self):
        # the -X axis is NOT the canonical direction: signed guard refuses
        ents = [pt("p1", 0.0, 0.0), pt("p2", -20.0, 0.0), ln("l1", "p1", "p2")]
        cons = [{"id": "c01", "kind": "fix", "args": ["p1"]},
                {"id": "c02", "kind": "horizontal", "args": ["l1"]}]
        with pytest.raises(bp.OutOfDomain, match="signed guard failed"):
            bp.admit_graph(ents, cons, [], [weak(1, "p2", "x", -20.0)])

    @pytest.mark.parametrize("mutate,pattern", [
        (lambda w: dict(w, id="w02"), "canonical"),
        (lambda w: dict(w, value={"magnitude": 20.0, "unit": "deg"}), "unit"),
        (lambda w: dict(w, strength="strong"), "verbatim skb-0"),
        (lambda w: dict(w, origin={"category": "computed_result",
                                   "policy": "skb-1",
                                   "solver_contract": "skb-c0"}), "origin"),
        (lambda w: dict(w, extra_field=1), "unknown fields"),
        (lambda w: dict(w, visibility="public"), "verbatim skb-0"),
    ])
    def test_weak_record_field_violations_refuse(self, mutate, pattern):
        ents, cons, dims, wk = g1()
        with pytest.raises(bp.OutOfDomain, match=pattern):
            bp.admit_graph(ents, cons, dims, [mutate(wk[0])])
