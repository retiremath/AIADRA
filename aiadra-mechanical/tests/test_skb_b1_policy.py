"""skb-b1 pure policy: doc parity, the profile-family graph predicate, guards.

The normative authority is Docs/SolverContracts/skb-b1.md (ADR/0044 A4);
these tests EXTRACT its machine-readable blocks and parity-check the
implementation's COMPLETE structures — comparing keys alone would let
normative content drift silently.

Required by the doc §7 enforcement clause: BOTH layer-1 failures AND
layer-2-only failures that PASS layer 1 (proving layer 2 is real
authority), plus the POSITIVE redundant chain/cycle fixtures so
strong-row independence is never assumed (Codex1 B3).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from aiadra_mechanical.solver import branch_policy_b1 as bp1
from aiadra_mechanical.solver.branch_policy_b1 import OutOfDomain

# ---------------------------------------------------------------- doc access


def _doc_text(name: str) -> str:
    for parent in Path(__file__).resolve().parents:
        cand = parent / "Docs" / "SolverContracts" / name
        if cand.is_file():
            return cand.read_text(encoding="utf-8")
    raise AssertionError(f"Docs/SolverContracts/{name} not found above tests/")


def _doc_block(marker: str):
    text = _doc_text("skb-b1.md")
    m = re.search(rf"<!-- skb-b1:{marker} -->\s*```json\s*(.*?)```", text, re.DOTALL)
    assert m, f"block skb-b1:{marker} missing from skb-b1.md"
    return json.loads(m.group(1))


# ---------------------------------------------------------------- builders

O, PX, PY, AX, AY = "skp_0001", "skp_0002", "skp_0003", "skp_0004", "skp_0005"


def _pt(eid, x, y, construction=False):
    return {"id": eid, "type": "point", "construction": construction,
            "nominal": {"x": x, "y": y}}


def _line(eid, s, e, construction=False):
    return {"id": eid, "type": "line", "construction": construction,
            "start": s, "end": e}


def _circle(eid, center, radius, construction=False):
    return {"id": eid, "type": "circle", "construction": construction,
            "center": center, "radius": radius}


def _con(cid, kind, target):
    return {"id": cid, "kind": kind, "args": [target]}


def _weak(index, entity, parameter, magnitude, unit="mm"):
    return {"id": f"w{index + 1:02d}", "kind": "fix_param",
            "target": {"entity": entity, "parameter": parameter},
            "value": {"magnitude": magnitude, "unit": unit},
            "strength": "weak", "role": "driving", "visibility": "internal",
            "origin": {"category": "computed_result", "policy": "skb-0",
                       "solver_contract": "skb-c0"}}


def _reference_g2(x_axis=10.0, y_axis=10.0):
    """The G2 reference frame, verbatim."""
    ents = [_pt(O, 0.0, 0.0, True), _pt(PX, x_axis, 0.0, True),
            _pt(PY, 0.0, y_axis, True),
            _line(AX, O, PX, True), _line(AY, O, PY, True)]
    cons = [_con("c01", "fix", O), _con("c02", "horizontal", AX),
            _con("c03", "vertical", AY)]
    return ents, cons


def _weaks(targets):
    """targets: [(entity, parameter, magnitude)] in canonical order."""
    return [_weak(i, e, p, m) for i, (e, p, m) in enumerate(targets)]


def _admit(ents, cons, weaks, dims=()):
    return bp1.admit_graph(ents, cons, list(dims), weaks)


# ---------------------------------------------------------------- parity


class TestDocParity:
    def test_constants(self):
        assert _doc_block("constants") == bp1.CONSTANTS
        # the catalog is empty everywhere -> no measure, no epsilon
        assert "epsilon_dimensionless" not in bp1.CONSTANTS
        assert bp1.CONSTANTS["policy_id"] == "skb-b1"

    def test_local_table(self):
        assert _doc_block("local-table") == bp1.LOCAL_TABLE

    def test_array_order(self):
        assert _doc_block("array-order") == bp1.ARRAY_ORDER

    def test_reference_predicate_COMPLETELY(self):
        assert _doc_block("reference-predicate") == bp1.REFERENCE_PREDICATE

    def test_profile_predicate_COMPLETELY(self):
        assert _doc_block("profile-predicate") == bp1.PROFILE_PREDICATE

    def test_joint_rules(self):
        assert _doc_block("joint-rules") == bp1.JOINT_RULES

    def test_equality_classes(self):
        assert _doc_block("equality-classes") == bp1.EQUALITY_CLASSES

    def test_policy_is_self_contained_from_skb_b0(self):
        """A policy id never incorporates another by reference."""
        import inspect
        from aiadra_mechanical.solver import branch_policy_b1 as mod
        src = inspect.getsource(mod)
        assert "from .branch_policy import" not in src
        assert "import branch_policy\n" not in src


# ---------------------------------------------------------------- positive


class TestAdmittedFamily:
    def test_free_line_admits_with_four_singleton_classes(self):
        ents, cons = _reference_g2()
        ents += [_pt("skp_0006", 5.0, 5.0), _pt("skp_0007", 20.0, 12.0),
                 _line("skp_0008", "skp_0006", "skp_0007")]
        weaks = _weaks([(PX, "x", 10.0), (PY, "y", 10.0),
                        ("skp_0006", "x", 5.0), ("skp_0006", "y", 5.0),
                        ("skp_0007", "x", 20.0), ("skp_0007", "y", 12.0)])
        adm = _admit(ents, cons, weaks)
        assert adm.shape == "B1" and adm.reference_shape == "G2"
        assert adm.counts == {"K": 2, "M": 1, "C": 0, "A": 0}
        assert len(adm.classes) == 4
        assert bp1.derive_witness_descriptors(adm) == ()

    def test_snapped_horizontal_line_merges_the_y_class(self):
        ents, cons = _reference_g2()
        ents += [_pt("skp_0006", 5.0, 5.0), _pt("skp_0007", 20.0, 5.0),
                 _line("skp_0008", "skp_0006", "skp_0007")]
        cons = cons + [_con("c04", "horizontal", "skp_0008")]
        weaks = _weaks([(PX, "x", 10.0), (PY, "y", 10.0),
                        ("skp_0006", "x", 5.0), ("skp_0006", "y", 5.0),
                        ("skp_0007", "x", 20.0)])
        adm = _admit(ents, cons, weaks)
        assert adm.counts["A"] == 1
        assert len(adm.classes) == 3
        # the merged class carries both endpoint y scalars
        merged = [c for c in adm.classes if len(c) == 2]
        assert merged == [("skp_0006.y", "skp_0007.y")]
        # effective values propagate across the class (what the solve pins)
        assert adm.effective["skp_0007.y"] == 5.0

    def test_rectangle_is_four_classes(self):
        ents, cons = _reference_g2()
        a, b, c, d = "skp_0006", "skp_0007", "skp_0008", "skp_0009"
        ents += [_pt(a, 0.0, 0.0), _pt(b, 10.0, 0.0),
                 _pt(c, 10.0, 5.0), _pt(d, 0.0, 5.0),
                 _line("skp_0010", a, b), _line("skp_0011", b, c),
                 _line("skp_0012", c, d), _line("skp_0013", d, a)]
        cons = cons + [_con("c04", "horizontal", "skp_0010"),
                       _con("c05", "vertical", "skp_0011"),
                       _con("c06", "horizontal", "skp_0012"),
                       _con("c07", "vertical", "skp_0013")]
        weaks = _weaks([(PX, "x", 10.0), (PY, "y", 10.0),
                        (a, "x", 0.0), (a, "y", 0.0), (b, "x", 10.0), (c, "y", 5.0)])
        adm = _admit(ents, cons, weaks)
        assert adm.counts == {"K": 4, "M": 4, "C": 0, "A": 4}
        assert len(adm.classes) == 4  # x-pos, y-pos, width, height

    def test_redundant_horizontal_cycle_admits(self):
        """Codex1 B3's counterexample: three horizontal segments P-Q, Q-R,
        R-P give three strong rows of rank TWO. Admission must not assume
        strong-row independence."""
        ents, cons = _reference_g2()
        p, q, r = "skp_0006", "skp_0007", "skp_0008"
        ents += [_pt(p, 0.0, 3.0), _pt(q, 10.0, 3.0), _pt(r, 20.0, 3.0),
                 _line("skp_0009", p, q), _line("skp_0010", q, r),
                 _line("skp_0011", r, p)]
        cons = cons + [_con("c04", "horizontal", "skp_0009"),
                       _con("c05", "horizontal", "skp_0010"),
                       _con("c06", "horizontal", "skp_0011")]
        weaks = _weaks([(PX, "x", 10.0), (PY, "y", 10.0),
                        (p, "x", 0.0), (p, "y", 3.0), (q, "x", 10.0), (r, "x", 20.0)])
        adm = _admit(ents, cons, weaks)
        assert adm.counts["A"] == 3
        # ONE merged y class of three members + three singleton x classes
        assert len(adm.classes) == 4
        assert ("skp_0006.y", "skp_0007.y", "skp_0008.y") in adm.classes

    def test_bare_circle_admits(self):
        ents, cons = _reference_g2()
        ents += [_pt("skp_0006", 4.0, 4.0), _circle("skp_0007", "skp_0006", 3.0)]
        weaks = _weaks([(PX, "x", 10.0), (PY, "y", 10.0),
                        ("skp_0006", "x", 4.0), ("skp_0006", "y", 4.0),
                        ("skp_0007", "radius", 3.0)])
        adm = _admit(ents, cons, weaks)
        assert adm.counts == {"K": 1, "M": 0, "C": 1, "A": 0}
        assert len(adm.classes) == 3

    def test_g0_reference_with_profile_admits(self):
        ents = [_pt(O, 0.0, 0.0, True), _pt("skp_0006", 1.0, 1.0),
                _pt("skp_0007", 4.0, 5.0), _line("skp_0008", "skp_0006", "skp_0007")]
        cons = [_con("c01", "fix", O)]
        weaks = _weaks([("skp_0006", "x", 1.0), ("skp_0006", "y", 1.0),
                        ("skp_0007", "x", 4.0), ("skp_0007", "y", 5.0)])
        adm = _admit(ents, cons, weaks)
        assert adm.reference_shape == "G0"


# ------------------------------------------------- layer-1 negative fixtures


class TestLayerOneRefusals:
    def test_any_dimension_refuses(self):
        ents, cons = _reference_g2()
        ents += [_pt("skp_0006", 0.0, 0.0), _pt("skp_0007", 5.0, 0.0),
                 _line("skp_0008", "skp_0006", "skp_0007")]
        with pytest.raises(OutOfDomain, match="no dimensions"):
            _admit(ents, cons, [], dims=[{"id": "d01", "kind": "length"}])

    def test_arc_entity_kind_refuses(self):
        ents, cons = _reference_g2()
        ents += [{"id": "skp_0006", "type": "arc", "construction": False,
                  "center": O, "radius": 3.0}]
        with pytest.raises(OutOfDomain, match="outside the local table"):
            _admit(ents, cons, [])

    def test_tangent_constraint_kind_refuses(self):
        ents, cons = _reference_g2()
        ents += [_pt("skp_0006", 0.0, 0.0), _pt("skp_0007", 5.0, 0.0),
                 _line("skp_0008", "skp_0006", "skp_0007")]
        cons = cons + [_con("c04", "tangent", "skp_0008")]
        with pytest.raises(OutOfDomain, match="outside the local table"):
            _admit(ents, cons, [])


# ------------------------------- layer-2-only negatives (they PASS layer 1)


class TestLayerTwoRefusals:
    def _base(self):
        return _reference_g2()

    def test_empty_profile_refuses(self):
        ents, cons = self._base()
        weaks = _weaks([(PX, "x", 10.0), (PY, "y", 10.0)])
        with pytest.raises(OutOfDomain, match="non-empty profile"):
            _admit(ents, cons, weaks)

    def test_segment_with_identical_endpoint_ids_refuses(self):
        ents, cons = self._base()
        ents += [_pt("skp_0006", 1.0, 1.0), _line("skp_0007", "skp_0006", "skp_0006")]
        with pytest.raises(OutOfDomain, match="topological distinctness"):
            _admit(ents, cons, [])

    def test_zero_length_unconstrained_segment_refuses(self):
        """The axis guard only covers CONSTRAINED segments (Codex1 B2)."""
        ents, cons = self._base()
        ents += [_pt("skp_0006", 2.0, 2.0), _pt("skp_0007", 2.0, 2.0),
                 _line("skp_0008", "skp_0006", "skp_0007")]
        weaks = _weaks([(PX, "x", 10.0), (PY, "y", 10.0),
                        ("skp_0006", "x", 2.0), ("skp_0006", "y", 2.0),
                        ("skp_0007", "x", 2.0), ("skp_0007", "y", 2.0)])
        with pytest.raises(OutOfDomain, match="non-collapse"):
            _admit(ents, cons, weaks)

    def test_sub_floor_radius_refuses(self):
        ents, cons = self._base()
        ents += [_pt("skp_0006", 0.0, 0.0), _circle("skp_0007", "skp_0006", 1e-12)]
        weaks = _weaks([(PX, "x", 10.0), (PY, "y", 10.0),
                        ("skp_0006", "x", 0.0), ("skp_0006", "y", 0.0),
                        ("skp_0007", "radius", 1e-12)])
        with pytest.raises(OutOfDomain, match="R_min_mm"):
            _admit(ents, cons, weaks)

    def test_orphan_profile_point_refuses(self):
        ents, cons = self._base()
        ents += [_pt("skp_0006", 1.0, 1.0), _pt("skp_0007", 4.0, 4.0),
                 _line("skp_0008", "skp_0006", "skp_0007"),
                 _pt("skp_0009", 9.0, 9.0)]  # touched by nothing
        with pytest.raises(OutOfDomain, match="orphan"):
            _admit(ents, cons, [])

    def test_duplicate_edge_refuses(self):
        ents, cons = self._base()
        ents += [_pt("skp_0006", 0.0, 0.0), _pt("skp_0007", 5.0, 0.0),
                 _line("skp_0008", "skp_0006", "skp_0007"),
                 _line("skp_0009", "skp_0006", "skp_0007")]
        with pytest.raises(OutOfDomain, match="duplicate"):
            _admit(ents, cons, [])

    def test_reversed_duplicate_edge_refuses(self):
        ents, cons = self._base()
        ents += [_pt("skp_0006", 0.0, 0.0), _pt("skp_0007", 5.0, 0.0),
                 _line("skp_0008", "skp_0006", "skp_0007"),
                 _line("skp_0009", "skp_0007", "skp_0006")]
        with pytest.raises(OutOfDomain, match="duplicate"):
            _admit(ents, cons, [])

    def test_two_axis_facts_on_one_segment_refuse(self):
        ents, cons = self._base()
        ents += [_pt("skp_0006", 0.0, 0.0), _pt("skp_0007", 5.0, 0.0),
                 _line("skp_0008", "skp_0006", "skp_0007")]
        cons = cons + [_con("c04", "horizontal", "skp_0008"),
                       _con("c05", "vertical", "skp_0008")]
        with pytest.raises(OutOfDomain, match="more than one axis fact"):
            _admit(ents, cons, [])

    def test_cross_block_reference_refuses(self):
        """A profile segment may not reach into the reference block."""
        ents, cons = self._base()
        ents += [_pt("skp_0006", 5.0, 5.0), _line("skp_0007", "skp_0006", O)]
        with pytest.raises(OutOfDomain, match="across the reference/profile"):
            _admit(ents, cons, [])

    def test_wrong_weak_count_refuses(self):
        ents, cons = self._base()
        ents += [_pt("skp_0006", 1.0, 1.0), _pt("skp_0007", 4.0, 5.0),
                 _line("skp_0008", "skp_0006", "skp_0007")]
        weaks = _weaks([(PX, "x", 10.0), (PY, "y", 10.0),
                        ("skp_0006", "x", 1.0)])  # 3 of the 6 required
        with pytest.raises(OutOfDomain, match="canonical skb-0 completion"):
            _admit(ents, cons, weaks)

    def test_permuted_weak_array_refuses(self):
        ents, cons = self._base()
        ents += [_pt("skp_0006", 1.0, 1.0), _pt("skp_0007", 4.0, 5.0),
                 _line("skp_0008", "skp_0006", "skp_0007")]
        good = [(PX, "x", 10.0), (PY, "y", 10.0),
                ("skp_0006", "x", 1.0), ("skp_0006", "y", 1.0),
                ("skp_0007", "x", 4.0), ("skp_0007", "y", 5.0)]
        swapped = good[:2] + [good[3], good[2]] + good[4:]
        with pytest.raises(OutOfDomain, match="expected target"):
            _admit(ents, cons, _weaks(swapped))

    def test_weak_record_with_foreign_origin_refuses(self):
        ents, cons = self._base()
        ents += [_pt("skp_0006", 1.0, 1.0), _pt("skp_0007", 4.0, 5.0),
                 _line("skp_0008", "skp_0006", "skp_0007")]
        weaks = _weaks([(PX, "x", 10.0), (PY, "y", 10.0),
                        ("skp_0006", "x", 1.0), ("skp_0006", "y", 1.0),
                        ("skp_0007", "x", 4.0), ("skp_0007", "y", 5.0)])
        weaks[2]["origin"]["policy"] = "skb-1"
        with pytest.raises(OutOfDomain, match="origin block"):
            _admit(ents, cons, weaks)

    def test_reference_block_beyond_g2_refuses(self):
        ents, cons = self._base()
        ents += [_pt("skp_0090", 1.0, 1.0, True)]  # a 4th construction point
        ents += [_pt("skp_0006", 1.0, 1.0), _pt("skp_0007", 4.0, 5.0),
                 _line("skp_0008", "skp_0006", "skp_0007")]
        with pytest.raises(OutOfDomain, match="G0, G1 nor G2|outside the"):
            _admit(ents, cons, [])

    def test_missing_anchor_refuses(self):
        ents, _ = self._base()
        ents += [_pt("skp_0006", 1.0, 1.0), _pt("skp_0007", 4.0, 5.0),
                 _line("skp_0008", "skp_0006", "skp_0007")]
        cons = [_con("c02", "horizontal", AX), _con("c03", "vertical", AY)]
        with pytest.raises(OutOfDomain, match="exactly one fix"):
            _admit(ents, cons, [])


# ---------------------------------------------------------------- catalog


class TestEmptyCatalog:
    def _admitted(self):
        ents, cons = _reference_g2()
        ents += [_pt("skp_0006", 1.0, 1.0), _pt("skp_0007", 4.0, 5.0),
                 _line("skp_0008", "skp_0006", "skp_0007")]
        weaks = _weaks([(PX, "x", 10.0), (PY, "y", 10.0),
                        ("skp_0006", "x", 1.0), ("skp_0006", "y", 1.0),
                        ("skp_0007", "x", 4.0), ("skp_0007", "y", 5.0)])
        return _admit(ents, cons, weaks)

    def test_derived_set_is_empty(self):
        assert bp1.derive_witness_descriptors(self._admitted()) == ()

    def test_empty_witness_set_validates(self):
        bp1.validate_witness_set([], self._admitted())

    def test_any_present_witness_is_extra_and_refuses(self):
        adm = self._admitted()
        with pytest.raises(OutOfDomain, match="exact-set rule"):
            bp1.validate_witness_set(
                [{"id": "bw01", "kind": "cross_sign", "of": [], "sign": 1}], adm)
