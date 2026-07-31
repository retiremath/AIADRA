"""`compile_profile_graph` — the ONE semantic path (ADR/0044 A4).

These exercise the REAL production solver end to end: draw -> preview solve
-> exact canonical completion -> skb-b1 admission -> derived annotations and
glyphs -> engine world mapping.

The load-bearing behavioural claim of BS-2 is here: snapping is the ENGINE
moving geometry (Codex-pinned D6 split), never Studio computing snapped
coordinates.
"""
from __future__ import annotations

import pytest

from aiadra_core.transaction.boundary import TransactionError

from aiadra_mechanical.profile_graph import (
    compile_profile_graph,
    frame_from_placement,
    profile_geometry_payload,
    profile_preview_payload,
    world_point,
)
from aiadra_mechanical.sketch_placement import default_placement

O, PX, PY, AX, AY = "skp_0001", "skp_0002", "skp_0003", "skp_0004", "skp_0005"


def _reference():
    ents = [
        {"id": O, "type": "point", "construction": True, "nominal": {"x": 0.0, "y": 0.0}},
        {"id": PX, "type": "point", "construction": True, "nominal": {"x": 10.0, "y": 0.0}},
        {"id": PY, "type": "point", "construction": True, "nominal": {"x": 0.0, "y": 10.0}},
        {"id": AX, "type": "line", "construction": True, "start": O, "end": PX},
        {"id": AY, "type": "line", "construction": True, "start": O, "end": PY},
    ]
    cons = [
        {"id": "c01", "kind": "fix", "args": [O]},
        {"id": "c02", "kind": "horizontal", "args": [AX]},
        {"id": "c03", "kind": "vertical", "args": [AY]},
    ]
    return ents, cons


def _pt(eid, x, y):
    return {"id": eid, "type": "point", "construction": False,
            "nominal": {"x": x, "y": y}}


def _seg(eid, s, e):
    return {"id": eid, "type": "line", "construction": False, "start": s, "end": e}


def _circle(eid, c, r):
    return {"id": eid, "type": "circle", "construction": False,
            "center": c, "nominal": {"radius": r}}


def _line_case(y2=3.4):
    ents, cons = _reference()
    ents += [_pt("skp_0006", 2.0, 3.0), _pt("skp_0007", 22.0, y2),
             _seg("skp_0008", "skp_0006", "skp_0007")]
    return ents, cons


class TestTheNamedSchemes:
    def test_free_line_shows_the_creo_endpoint_scheme(self):
        """W-4 (Petre's ruling): {x_start, y_start, angle, x_end} — the pick
        the Creo 10 benchmark frame shows; no length dim."""
        ents, cons = _line_case()
        c = compile_profile_graph(case_id="feat_0001", entities=ents, constraints=cons)
        assert [a.kind for a in c.annotations] == [
            "position_x", "position_y", "angle", "position_x"]
        assert c.annotations[0].value == pytest.approx(2.0)
        assert c.annotations[1].value == pytest.approx(3.0)
        assert c.annotations[2].unit == "deg"
        assert c.annotations[3].value == pytest.approx(22.0)

    def test_snapping_is_the_ENGINE_moving_geometry(self):
        """Studio proposes the fact; the engine's solve is what puts the
        line exactly on the axis (ADR/0045 D6)."""
        ents, cons = _line_case(y2=3.4)          # drawn 0.4mm off horizontal
        cons = cons + [{"id": "c04", "kind": "horizontal", "args": ["skp_0008"]}]
        c = compile_profile_graph(case_id="feat_0001", entities=ents, constraints=cons)
        assert c.solved["skp_0006.y"] == pytest.approx(c.solved["skp_0007.y"])
        # the angle is DETERMINED now and leaves the basis on its own; the
        # merged y-class rejects y_end — three position coordinates remain
        assert [a.kind for a in c.annotations] == [
            "position_x", "position_y", "position_x"]
        assert c.annotations[2].value == pytest.approx(22.0, abs=1e-9)
        assert [g["id"] for g in c.glyphs] == ["glyph:horizontal:skp_0008"]

    def _rectangle(self, coords):
        ents, cons = _reference()
        a, b, cc, d = "skp_0006", "skp_0007", "skp_0008", "skp_0009"
        ents += [_pt(a, *coords[0]), _pt(b, *coords[1]),
                 _pt(cc, *coords[2]), _pt(d, *coords[3]),
                 _seg("skp_0010", a, b), _seg("skp_0011", b, cc),
                 _seg("skp_0012", cc, d), _seg("skp_0013", d, a)]
        cons = cons + [
            {"id": "c04", "kind": "horizontal", "args": ["skp_0010"]},
            {"id": "c05", "kind": "vertical", "args": ["skp_0011"]},
            {"id": "c06", "kind": "horizontal", "args": ["skp_0012"]},
            {"id": "c07", "kind": "vertical", "args": ["skp_0013"]},
        ]
        return ents, cons

    def test_exact_rectangle_is_four_descriptors(self):
        ents, cons = self._rectangle([(0.0, 0.0), (30.0, 0.0),
                                      (30.0, 12.0), (0.0, 12.0)])
        c = compile_profile_graph(case_id="feat_0001", entities=ents, constraints=cons)
        assert len(c.annotations) == 4
        assert len(c.glyphs) == 4

    def test_hand_drawn_rectangle_solves_via_the_two_phase_derivation(self):
        """Defect D-1, fixed per Petre's ruling (2026-07-30): completion runs
        at the FEASIBLE solution, so a rough rectangle no longer over-pins an
        equality class. The drawn nominals still persist as authored."""
        ents, cons = self._rectangle([(0.0, 0.0), (30.0, 0.2),
                                      (30.1, 12.0), (-0.2, 12.1)])
        c = compile_profile_graph(case_id="feat_0001", entities=ents, constraints=cons)
        assert len(c.annotations) == 4

    def test_bare_circle_shows_radius_and_centre(self):
        ents, cons = _reference()
        ents += [_pt("skp_0006", 5.0, 6.0), _circle("skp_0007", "skp_0006", 4.0)]
        c = compile_profile_graph(case_id="feat_0001", entities=ents, constraints=cons)
        assert [a.kind for a in c.annotations] == [
            "radius", "position_x", "position_y"]
        assert c.annotations[0].value == pytest.approx(4.0)


class TestTheNominalRuling:
    """Petre's ruling (2026-07-30) on defect D-1, pinned:

    completion runs at the accepted feasible solution WHILE the drawn
    coordinates persist as authored nominals. Committing solved output as
    nominals would be an implicit rebaseline, and ADR/0044 A2.5/A2.9 require
    a rebaseline to be an explicit authoring transaction.
    """

    def _snapped(self):
        ents, cons = _line_case(y2=3.4)          # drawn 0.4mm off horizontal
        cons = cons + [{"id": "c04", "kind": "horizontal", "args": ["skp_0008"]}]
        return compile_profile_graph(case_id="feat_0001",
                                     entities=ents, constraints=cons), ents

    def test_authored_nominals_are_the_RAW_drawn_coordinates(self):
        compiled, drawn = self._snapped()
        by_id = {e["id"]: e for e in compiled.entities}
        assert by_id["skp_0007"]["nominal"] == {"x": 22.0, "y": 3.4}
        # ... i.e. exactly what was drawn, untouched by the solve
        assert by_id["skp_0007"]["nominal"] == \
            {e["id"]: e for e in drawn}["skp_0007"]["nominal"]

    def test_weak_values_come_from_the_FEASIBLE_snapped_solution(self):
        compiled, _ = self._snapped()
        weak = {(w["target"]["entity"], w["target"]["parameter"]):
                w["value"]["magnitude"] for w in compiled.weak_completion}
        # the drawn y was 3.0/3.4; the feasible (snapped) shared y is 3.0
        assert weak[("skp_0006", "y")] == pytest.approx(3.0)
        assert ("skp_0007", "y") not in weak      # determined by the H fact

    def test_solved_coordinates_stay_DERIVED(self):
        compiled, _ = self._snapped()
        assert compiled.solved["skp_0007.y"] == pytest.approx(3.0)
        by_id = {e["id"]: e for e in compiled.entities}
        assert by_id["skp_0007"]["nominal"]["y"] == 3.4   # never overwritten

    def test_skb_b1_does_not_inherit_magnitude_equals_nominal(self):
        """skb-b0's rule 2 is specific to G0/G1/G2, where weak-pinned
        coordinates do not move. Under skb-b1 a weak magnitude legitimately
        differs from its authored nominal."""
        compiled, _ = self._snapped()
        by_id = {e["id"]: e for e in compiled.entities}
        weak = {(w["target"]["entity"], w["target"]["parameter"]):
                w["value"]["magnitude"] for w in compiled.weak_completion}
        drawn_y = by_id["skp_0006"]["nominal"]["y"]
        assert weak[("skp_0006", "y")] == pytest.approx(drawn_y)
        # and the record still validates as a whole (admission ran on the
        # DRAWN nominals plus the FEASIBLE weak set)
        assert compiled.admission.shape == "B1"


class TestRefusals:
    def test_zero_length_segment_refuses_typed(self):
        ents, cons = _reference()
        ents += [_pt("skp_0006", 4.0, 4.0), _pt("skp_0007", 4.0, 4.0),
                 _seg("skp_0008", "skp_0006", "skp_0007")]
        with pytest.raises(TransactionError, match="non-collapse|solve refused"):
            compile_profile_graph(case_id="x", entities=ents, constraints=cons)

    def test_orphan_point_refuses_typed(self):
        ents, cons = _reference()
        ents += [_pt("skp_0006", 1.0, 1.0), _pt("skp_0007", 5.0, 5.0),
                 _seg("skp_0008", "skp_0006", "skp_0007"), _pt("skp_0009", 8.0, 8.0)]
        with pytest.raises(TransactionError, match="orphan"):
            compile_profile_graph(case_id="x", entities=ents, constraints=cons)

    def test_empty_profile_refuses_typed(self):
        ents, cons = _reference()
        with pytest.raises(TransactionError, match="non-empty profile"):
            compile_profile_graph(case_id="x", entities=ents, constraints=cons)


class TestEngineOwnedWorldMapping:
    def test_geometry_is_emitted_in_world_space_for_the_placed_frame(self):
        """Studio renders what it is given; it never re-derives a plane."""
        ents, cons = _line_case()
        c = compile_profile_graph(case_id="feat_0001", entities=ents, constraints=cons)
        xy = profile_geometry_payload(c, frame_from_placement(default_placement("xy")))
        zx = profile_geometry_payload(c, frame_from_placement(default_placement("zx")))
        assert xy["points"][0]["world"] != zx["points"][0]["world"]
        # every drawable anchor is world; annotation VALUES stay local scalars
        assert len(xy["annotations"][0]["anchors"][0]) == 3
        assert xy["annotations"][0]["unit"] == "mm"

    def test_world_point_uses_the_frame_axes(self):
        frame = {"origin_mm": [1.0, 0.0, 0.0], "u_axis": [0.0, 1.0, 0.0],
                 "v_axis": [0.0, 0.0, 1.0], "normal": [1.0, 0.0, 0.0]}
        assert world_point(frame, 2.0, 3.0) == [1.0, 2.0, 3.0]

    def test_circle_carries_no_duplicate_world_centre(self):
        """Codex4 B3: the centre point already carries `world` — a second
        unchecked world centre could contradict it."""
        ents, cons = _reference()
        ents += [_pt("skp_0006", 5.0, 6.0), _circle("skp_0007", "skp_0006", 4.0)]
        c = compile_profile_graph(case_id="feat_0001", entities=ents, constraints=cons)
        payload = profile_geometry_payload(c, frame_from_placement(default_placement("xy")))
        assert set(payload["circles"][0]) == {"id", "center", "radius_mm"}
        assert payload["circles"][0]["center"] == "skp_0006"

    def test_points_carry_no_local_duplicate(self):
        ents, cons = _line_case()
        c = compile_profile_graph(case_id="feat_0001", entities=ents, constraints=cons)
        payload = profile_geometry_payload(c, frame_from_placement(default_placement("xy")))
        assert set(payload["points"][0]) == {"id", "world"}


class TestPreviewEnvelope:
    def test_create_preview_uses_a_candidate_key_not_a_fake_feature_id(self):
        ents, cons = _line_case()
        c = compile_profile_graph(case_id="cand", entities=ents, constraints=cons)
        frame = frame_from_placement(default_placement("xy"))
        prev = profile_preview_payload(c, frame, {"candidate_key": "cand-1"})
        assert prev["owner"] == {"candidate_key": "cand-1"}
        assert "sketch_feature_id" not in prev
        # the frame rides INLINE — an uncommitted sketch has no sketch_frames[]
        # entry to join, and Studio needs it to map pointer rays
        assert set(prev["frame"]) == {"origin_mm", "u_axis", "v_axis", "normal"}

    def test_edit_preview_may_name_the_real_feature(self):
        ents, cons = _line_case()
        c = compile_profile_graph(case_id="feat_0009", entities=ents, constraints=cons)
        prev = profile_preview_payload(
            c, frame_from_placement(default_placement("xy")),
            {"feature_id": "feat_0009"})
        assert prev["owner"] == {"feature_id": "feat_0009"}

    def test_a_mixed_or_empty_owner_refuses(self):
        ents, cons = _line_case()
        c = compile_profile_graph(case_id="x", entities=ents, constraints=cons)
        frame = frame_from_placement(default_placement("xy"))
        for bad in ({}, {"feature_id": "f", "candidate_key": "k"}, {"other": "x"}):
            with pytest.raises(TransactionError, match="preview owner"):
                profile_preview_payload(c, frame, bad)

    def test_preview_content_matches_the_committed_geometry_payload(self):
        """Parity is equality AFTER the owner/frame projection (Codex4 B2) —
        the CONTENT comes from one compiler, so it is identical."""
        ents, cons = _line_case()
        c = compile_profile_graph(case_id="feat_0009", entities=ents, constraints=cons)
        frame = frame_from_placement(default_placement("xy"))
        prev = profile_preview_payload(c, frame, {"feature_id": "feat_0009"})
        committed = profile_geometry_payload(c, frame)
        for key in ("points", "segments", "circles", "annotations",
                    "constraint_glyphs"):
            assert prev[key] == committed[key]
