"""The derived annotation basis (ADR/0044 A4) — cardinality, local
independence, determinism, and the three named schemes.

NOT tested (deliberately): a global bijection. Codex2 B2 established that
locally independent gradients do not establish global invertibility for
nonlinear length/angle coordinates; the contract claims `N` locally
independent derived coordinates for `N` weak DoFs, and that is what these
tests pin.
"""
from __future__ import annotations

import math

import pytest

from aiadra_mechanical.annotation_basis import (
    build_annotation_basis,
    build_constraint_glyphs,
    annotation_id,
)


def _pt(eid, x, y):
    return {"id": eid, "type": "point", "construction": False,
            "nominal": {"x": x, "y": y}}


def _line(eid, s, e):
    return {"id": eid, "type": "line", "construction": False, "start": s, "end": e}


def _circle(eid, center, radius):
    return {"id": eid, "type": "circle", "construction": False,
            "center": center, "radius": radius}


def _kinds(anns):
    return [a.kind for a in anns]


class TestNamedSchemes:
    """The schemes the Creo benchmark walk asks for — falling out of ONE
    algorithm rather than being special-cased."""

    def test_free_line_gives_the_creo_endpoint_scheme(self):
        """W-4 (Petre's ruling): {x_start, y_start, angle, x_end} — the
        exact pick the Creo 10 benchmark frame shows; NO length dim."""
        ents = [_pt("skp_0006", 1.0, 2.0), _pt("skp_0007", 5.0, 7.0),
                _line("skp_0008", "skp_0006", "skp_0007")]
        classes = [("skp_0006.x",), ("skp_0006.y",),
                   ("skp_0007.x",), ("skp_0007.y",)]
        solved = {"skp_0006.x": 1.0, "skp_0006.y": 2.0,
                  "skp_0007.x": 5.0, "skp_0007.y": 7.0}
        anns = build_annotation_basis(entities=ents, classes=classes, solved=solved)
        assert len(anns) == 4
        assert _kinds(anns) == ["position_x", "position_y", "angle", "position_x"]
        assert anns[0].entities == ("skp_0006",)
        assert anns[1].entities == ("skp_0006",)
        assert anns[2].unit == "deg"
        assert anns[2].value == pytest.approx(math.degrees(math.atan2(5.0, 4.0)))
        assert anns[3].entities == ("skp_0007",)
        assert "length" not in _kinds(anns)

    def test_exactly_vertical_free_line_swaps_x_end_for_y_end(self):
        """x_end is DETERMINED by x_start + the 90° angle, so the rank test
        rejects it and y_end is selected — a property of the selection, not
        a special case."""
        ents = [_pt("skp_0006", 3.0, 1.0), _pt("skp_0007", 3.0, 9.0),
                _line("skp_0008", "skp_0006", "skp_0007")]
        classes = [("skp_0006.x",), ("skp_0006.y",),
                   ("skp_0007.x",), ("skp_0007.y",)]
        solved = {"skp_0006.x": 3.0, "skp_0006.y": 1.0,
                  "skp_0007.x": 3.0, "skp_0007.y": 9.0}
        anns = build_annotation_basis(entities=ents, classes=classes, solved=solved)
        assert _kinds(anns) == ["position_x", "position_y", "angle", "position_y"]
        assert anns[2].value == pytest.approx(90.0)
        assert anns[3].entities == ("skp_0007",)

    def test_snapped_horizontal_line_drops_the_angle(self):
        """The angle's projected row is EXACTLY zero once the endpoints' y
        scalars share a class, and the merged class rejects y_end — three
        position coordinates remain, exactly the walk-script expectation."""
        ents = [_pt("skp_0006", 1.0, 3.0), _pt("skp_0007", 9.0, 3.0),
                _line("skp_0008", "skp_0006", "skp_0007")]
        classes = [("skp_0006.x",), ("skp_0006.y", "skp_0007.y"), ("skp_0007.x",)]
        solved = {"skp_0006.x": 1.0, "skp_0006.y": 3.0,
                  "skp_0007.x": 9.0, "skp_0007.y": 3.0}
        anns = build_annotation_basis(entities=ents, classes=classes, solved=solved)
        assert len(anns) == 3
        assert _kinds(anns) == ["position_x", "position_y", "position_x"]
        assert [a.value for a in anns] == [pytest.approx(1.0), pytest.approx(3.0),
                                           pytest.approx(9.0)]

    def test_a_chained_vertex_contributes_its_positions_once(self):
        """Two chained free segments (p—q—r): the shared vertex q is emitted
        on first encounter only — no duplicate semantic ids — and each new
        chained vertex is dimensioned by ONE coordinate + the segment angle
        (its second coordinate is DETERMINED: given p, angle1 and q.x the
        point lies on the ray — the rank test rejects q.y with no special
        case). Scheme: {p.x, p.y, angle1, q.x, angle2, r.x}."""
        p, q, r = "skp_0006", "skp_0007", "skp_0009"
        ents = [_pt(p, 0.0, 0.0), _pt(q, 10.0, 1.0), _pt(r, 18.0, 9.0),
                _line("skp_0008", p, q), _line("skp_0010", q, r)]
        classes = [(f"{p}.x",), (f"{p}.y",), (f"{q}.x",), (f"{q}.y",),
                   (f"{r}.x",), (f"{r}.y",)]
        solved = {f"{p}.x": 0.0, f"{p}.y": 0.0, f"{q}.x": 10.0, f"{q}.y": 1.0,
                  f"{r}.x": 18.0, f"{r}.y": 9.0}
        anns = build_annotation_basis(entities=ents, classes=classes, solved=solved)
        assert len(anns) == 6
        assert _kinds(anns) == ["position_x", "position_y", "angle",
                                "position_x", "angle", "position_x"]
        assert [a.entities[0] for a in anns] == [p, p, "skp_0008", q,
                                                 "skp_0010", r]
        assert len({a.id for a in anns}) == 6

    def test_bare_circle_gives_radius_and_its_centre(self):
        ents = [_pt("skp_0006", 4.0, 6.0), _circle("skp_0007", "skp_0006", 3.0)]
        classes = [("skp_0006.x",), ("skp_0006.y",), ("skp_0007.radius",)]
        solved = {"skp_0006.x": 4.0, "skp_0006.y": 6.0, "skp_0007.radius": 3.0}
        anns = build_annotation_basis(entities=ents, classes=classes, solved=solved)
        assert len(anns) == 3
        assert _kinds(anns) == ["radius", "position_x", "position_y"]
        assert anns[0].value == pytest.approx(3.0)
        # anchors: centre + the canonical rim point at frame angle 0
        assert anns[0].anchors == ((4.0, 6.0), (7.0, 6.0))


class TestCardinalityAndIndependence:
    def test_cardinality_equals_the_weak_dof_count(self):
        """A rectangle has 4 weak DoFs -> exactly 4 displayed descriptors."""
        a, b, c, d = "skp_0006", "skp_0007", "skp_0008", "skp_0009"
        ents = [_pt(a, 0.0, 0.0), _pt(b, 10.0, 0.0), _pt(c, 10.0, 5.0),
                _pt(d, 0.0, 5.0),
                _line("skp_0010", a, b), _line("skp_0011", b, c),
                _line("skp_0012", c, d), _line("skp_0013", d, a)]
        classes = [(f"{a}.x", f"{d}.x"), (f"{a}.y", f"{b}.y"),
                   (f"{b}.x", f"{c}.x"), (f"{c}.y", f"{d}.y")]
        solved = {f"{a}.x": 0.0, f"{a}.y": 0.0, f"{b}.x": 10.0, f"{b}.y": 0.0,
                  f"{c}.x": 10.0, f"{c}.y": 5.0, f"{d}.x": 0.0, f"{d}.y": 5.0}
        anns = build_annotation_basis(entities=ents, classes=classes, solved=solved)
        assert len(anns) == 4

    def test_redundant_horizontal_chain_still_completes(self):
        """Three collinear horizontal segments: one merged y class + three x
        singletons = 4 descriptors, and the enumeration must reach it."""
        p, q, r = "skp_0006", "skp_0007", "skp_0008"
        ents = [_pt(p, 0.0, 3.0), _pt(q, 10.0, 3.0), _pt(r, 20.0, 3.0),
                _line("skp_0009", p, q), _line("skp_0010", q, r),
                _line("skp_0011", r, p)]
        classes = [(f"{p}.x",), (f"{p}.y", f"{q}.y", f"{r}.y"),
                   (f"{q}.x",), (f"{r}.x",)]
        solved = {f"{p}.x": 0.0, f"{p}.y": 3.0, f"{q}.x": 10.0,
                  f"{q}.y": 3.0, f"{r}.x": 20.0, f"{r}.y": 3.0}
        anns = build_annotation_basis(entities=ents, classes=classes, solved=solved)
        assert len(anns) == 4
        # the three segment lengths are NOT independent here — only some are kept
        assert _kinds(anns).count("length") < 3


class TestDeterminismAndIdentity:
    def _case(self):
        ents = [_pt("skp_0006", 1.0, 2.0), _pt("skp_0007", 5.0, 7.0),
                _line("skp_0008", "skp_0006", "skp_0007")]
        classes = [("skp_0006.x",), ("skp_0006.y",),
                   ("skp_0007.x",), ("skp_0007.y",)]
        solved = {"skp_0006.x": 1.0, "skp_0006.y": 2.0,
                  "skp_0007.x": 5.0, "skp_0007.y": 7.0}
        return ents, classes, solved

    def test_selection_is_deterministic_across_entity_permutations(self):
        ents, classes, solved = self._case()
        a = build_annotation_basis(entities=ents, classes=classes, solved=solved)
        b = build_annotation_basis(entities=list(reversed(ents)),
                                   classes=classes, solved=solved)
        assert [x.id for x in a] == [x.id for x in b]

    def test_ids_are_semantic_not_ordinal(self):
        ents, classes, solved = self._case()
        anns = build_annotation_basis(entities=ents, classes=classes, solved=solved)
        assert anns[0].id == "ann:position_x:skp_0006"
        assert all(not a.id.startswith("an0") for a in anns)
        assert annotation_id("position_x", ("skp_0006",)) == "ann:position_x:skp_0006"

    def test_ids_survive_a_value_only_change(self):
        """Moving a point keeps the same selected descriptors' ids."""
        ents, classes, solved = self._case()
        before = build_annotation_basis(entities=ents, classes=classes, solved=solved)
        moved = dict(solved, **{"skp_0007.x": 6.5})
        after = build_annotation_basis(entities=ents, classes=classes, solved=moved)
        assert [x.id for x in before] == [x.id for x in after]
        # the moved scalar is Q.x — the scheme's fourth descriptor
        assert before[3].value != after[3].value

    def test_ids_are_unique(self):
        ents, classes, solved = self._case()
        anns = build_annotation_basis(entities=ents, classes=classes, solved=solved)
        assert len({a.id for a in anns}) == len(anns)


class TestGlyphs:
    def test_glyphs_are_emitted_per_profile_axis_fact_with_semantic_ids(self):
        cons = [{"id": "c01", "kind": "fix", "args": ["skp_0001"]},
                {"id": "c02", "kind": "horizontal", "args": ["skp_0004"]},
                {"id": "c04", "kind": "horizontal", "args": ["skp_0008"]},
                {"id": "c05", "kind": "vertical", "args": ["skp_0009"]}]
        glyphs = build_constraint_glyphs(cons, ["skp_0008", "skp_0009"])
        assert [g["id"] for g in glyphs] == [
            "glyph:horizontal:skp_0008", "glyph:vertical:skp_0009"]
        # the REFERENCE axis fact (skp_0004) never becomes a profile glyph
        assert all(g["target"] != "skp_0004" for g in glyphs)
