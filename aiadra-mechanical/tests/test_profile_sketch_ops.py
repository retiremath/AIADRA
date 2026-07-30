"""The three A4 profile operations, end to end through the REAL Ring-2
protocol and the REAL solver (ADR/0044 A4; arc 20260730-1, increment I1).

`test_profile_ops.py` covers the resolver's laws in isolation; this file
proves the operations themselves: that a drawn profile becomes committed
Truth, that an edit obeys the survival law through a real transaction, that
the preview writes NOTHING, and that the preview and the refreshed Display
agree after substitution — the production seam Codex5 N2 pinned.
"""
from __future__ import annotations

import copy

import pytest

from aiadra_core.protocol import (
    display_representation,
    preview_sketch_graph,
    propose,
    read_kinds,
)
from aiadra_core.transaction.boundary import TransactionError

from aiadra_mechanical.solver import SolverArtifactMissingError, load_solver

from conftest import part_sidecar

PART = "P-000001"
PLACEMENT = {"support": {"kind": "principal", "orientation": "xy"}}


@pytest.fixture(scope="module", autouse=True)
def _require_artifact():
    try:
        load_solver()
    except SolverArtifactMissingError as exc:
        pytest.skip(f"native solver artifact not built locally: {exc}")


def _rectangle(coords=((0.0, 0.0), (30.0, 0.3), (30.1, 12.0), (0.2, 12.1))):
    """A HAND-DRAWN rectangle: four corners nobody clicked exactly, plus the
    four axis facts a Studio snap would propose."""
    keys = ["p0", "p1", "p2", "p3"]
    segs = ["s0", "s1", "s2", "s3"]
    return {
        "points": [{"key": k, "x": c[0], "y": c[1]} for k, c in zip(keys, coords)],
        "segments": [
            {"key": s, "start": {"key": keys[i]}, "end": {"key": keys[(i + 1) % 4]}}
            for i, s in enumerate(segs)
        ],
        "facts": [
            {"key": f"f{i}", "kind": ["horizontal", "vertical"][i % 2],
             "target": {"key": s}}
            for i, s in enumerate(segs)
        ],
    }


def _line():
    return {
        "points": [{"key": "a", "x": 0.0, "y": 0.0},
                   {"key": "b", "x": 20.0, "y": 0.4}],
        "segments": [{"key": "e", "start": {"key": "a"}, "end": {"key": "b"}}],
        "facts": [{"key": "h", "kind": "horizontal", "target": {"key": "e"}}],
    }


def _author(ws, profile=None):
    return propose(ws, kind="mechanical.author_profile_sketch", params={
        "part_number": PART, "placement": PLACEMENT,
        "profile": profile if profile is not None else _line(),
    }).commit()


def _sketch(ws, feature_id="feat_0001"):
    return [f for f in part_sidecar(ws)["feature"] if f["id"] == feature_id][0]


class TestAuthor:
    def test_a_drawn_line_becomes_a_committed_constrained_sketch(self, workspace_with_part):
        ws = workspace_with_part
        _author(ws)
        rec = _sketch(ws)
        assert rec["adapter_schema_version"] == "0.2.2"
        payload = rec["adapter_payload"]
        assert payload["branch_policy"] == "skb-b1"
        # the reference frame + the drawn profile, in ONE graph
        assert sum(1 for e in payload["entities"] if e["construction"]) == 5
        profile = [e for e in payload["entities"] if not e["construction"]]
        assert sorted(e["type"] for e in profile) == ["line", "point", "point"]

    def test_the_drawn_nominals_persist_exactly_as_authored(self, workspace_with_part):
        """Petre's ruling (2026-07-30): completion runs at the feasible
        solution, but the DRAWN coordinates persist as authored nominals.
        Committing solved output would be an implicit rebaseline, which
        A2.5/A2.9 require to be an explicit authoring transaction."""
        ws = workspace_with_part
        _author(ws)
        profile = [e for e in _sketch(ws)["adapter_payload"]["entities"]
                   if not e["construction"] and e["type"] == "point"]
        drawn = sorted((e["nominal"]["x"], e["nominal"]["y"]) for e in profile)
        assert drawn == [(0.0, 0.0), (20.0, 0.4)]     # 0.4 NOT snapped away

    def test_the_profile_fact_does_not_collide_with_the_reference_frame(
            self, workspace_with_part):
        """The frame already owns c01/c02/c03; a minted profile fact must
        never land on one of them."""
        ws = workspace_with_part
        _author(ws)
        cons = _sketch(ws)["adapter_payload"]["constraints"]
        assert [c["id"] for c in cons] == ["c01", "c02", "c03", "c04"]
        assert cons[3]["kind"] == "horizontal"

    def test_a_hand_drawn_rectangle_commits(self, workspace_with_part):
        ws = workspace_with_part
        _author(ws, _rectangle())
        payload = _sketch(ws)["adapter_payload"]
        assert len([e for e in payload["entities"] if not e["construction"]]) == 8
        assert len(payload["weak_completion"]) == 6      # 2 reference + 4 profile

    def test_an_empty_profile_refuses_and_leaves_no_feature(self, workspace_with_part):
        ws = workspace_with_part
        with pytest.raises(TransactionError, match="non-empty profile block"):
            _author(ws, {"points": [], "segments": [], "facts": []})
        assert part_sidecar(ws).get("feature", []) == []

    def test_a_contradictory_graph_refuses_and_leaves_no_feature(self, workspace_with_part):
        """Horizontal AND vertical on one segment: no feasible solution."""
        ws = workspace_with_part
        prof = _line()
        prof["facts"].append({"key": "v", "kind": "vertical", "target": {"key": "e"}})
        with pytest.raises(TransactionError, match="more than one axis fact"):
            _author(ws, prof)
        assert part_sidecar(ws).get("feature", []) == []


class TestReplace:
    def test_moving_a_point_preserves_every_id(self, workspace_with_part):
        ws = workspace_with_part
        _author(ws)
        before = _sketch(ws)["adapter_payload"]
        ids = [e["id"] for e in before["entities"]]

        propose(ws, kind="mechanical.replace_sketch_graph", params={
            "part_number": PART, "sketch_feature_id": "feat_0001",
            "profile": {
                "points": [{"id": "skp_0006", "x": 0.0, "y": 0.0},
                           {"id": "skp_0007", "x": 35.0, "y": 0.4}],
                "segments": [{"id": "skp_0008", "start": {"id": "skp_0006"},
                              "end": {"id": "skp_0007"}}],
                "facts": [{"id": "c04", "kind": "horizontal",
                           "target": {"id": "skp_0008"}}],
            },
        }).commit()

        after = _sketch(ws)["adapter_payload"]
        assert [e["id"] for e in after["entities"]] == ids
        moved = [e for e in after["entities"] if e["id"] == "skp_0007"][0]
        assert moved["nominal"]["x"] == 35.0

    def test_the_reference_block_survives_byte_for_byte(self, workspace_with_part):
        ws = workspace_with_part
        _author(ws)
        before = copy.deepcopy([e for e in _sketch(ws)["adapter_payload"]["entities"]
                                if e["construction"]])
        propose(ws, kind="mechanical.replace_sketch_graph", params={
            "part_number": PART, "sketch_feature_id": "feat_0001",
            "profile": {
                "points": [{"id": "skp_0006", "x": 0.0, "y": 0.0},
                           {"id": "skp_0007", "x": 21.0, "y": 0.4}],
                "segments": [{"id": "skp_0008", "start": {"id": "skp_0006"},
                              "end": {"id": "skp_0007"}}],
                "facts": [{"id": "c04", "kind": "horizontal",
                           "target": {"id": "skp_0008"}}],
            },
        }).commit()
        after = [e for e in _sketch(ws)["adapter_payload"]["entities"]
                 if e["construction"]]
        assert after == before

    def test_an_edit_may_not_reach_into_the_reference_block(self, workspace_with_part):
        ws = workspace_with_part
        _author(ws)
        with pytest.raises(TransactionError, match="not a record of THIS"):
            propose(ws, kind="mechanical.replace_sketch_graph", params={
                "part_number": PART, "sketch_feature_id": "feat_0001",
                "profile": {"points": [{"id": "skp_0002", "x": 99.0, "y": 0.0}]},
            }).commit()

    def test_an_exact_no_op_refuses_before_staging(self, workspace_with_part):
        ws = workspace_with_part
        _author(ws)
        with pytest.raises(TransactionError, match="sketch-graph-unchanged"):
            propose(ws, kind="mechanical.replace_sketch_graph", params={
                "part_number": PART, "sketch_feature_id": "feat_0001",
                "profile": {
                    "points": [{"id": "skp_0006", "x": 0.0, "y": 0.0},
                               {"id": "skp_0007", "x": 20.0, "y": 0.4}],
                    "segments": [{"id": "skp_0008", "start": {"id": "skp_0006"},
                                  "end": {"id": "skp_0007"}}],
                    "facts": [{"id": "c04", "kind": "horizontal",
                               "target": {"id": "skp_0008"}}],
                },
            }).commit()

    def test_replace_refuses_a_non_0_2_2_sketch(self, workspace_with_part):
        ws = workspace_with_part
        propose(ws, kind="mechanical.add_reference_sketch", params={
            "part_number": PART, "placement": PLACEMENT}).commit()
        with pytest.raises(TransactionError, match="target literal '0.2.2'"):
            propose(ws, kind="mechanical.replace_sketch_graph", params={
                "part_number": PART, "sketch_feature_id": "feat_0001",
                "profile": _line(),
            }).commit()


class TestPreviewWritesNothing:
    """Codex5 N2: the production seam. A preview is a READ — it must leave
    the workspace bit-identical and mint no identity."""

    def test_a_create_preview_leaves_the_sidecar_untouched(self, workspace_with_part):
        ws = workspace_with_part
        _author(ws)
        before = copy.deepcopy(part_sidecar(ws))
        out = preview_sketch_graph(
            ws, PART, engine_id="mechanical", profile=_rectangle(),
            placement=PLACEMENT, candidate_key="draft1")
        assert out["owner"] == {"candidate_key": "draft1"}
        assert part_sidecar(ws) == before

    def test_a_preview_echoes_the_caller_keys_and_mints_no_id(self, workspace_with_part):
        ws = workspace_with_part
        out = preview_sketch_graph(
            ws, PART, engine_id="mechanical", profile=_line(),
            placement=PLACEMENT, candidate_key="draft1")
        assert [p["id"] for p in out["points"]] == ["a", "b"]
        assert [s["id"] for s in out["segments"]] == ["e"]
        assert [g["id"] for g in out["constraint_glyphs"]] == ["glyph:horizontal:e"]

    def test_a_create_preview_carries_the_frame_inline(self, workspace_with_part):
        ws = workspace_with_part
        out = preview_sketch_graph(
            ws, PART, engine_id="mechanical", profile=_line(),
            placement=PLACEMENT, candidate_key="draft1")
        assert out["frame"]["u_axis"] == [1.0, 0.0, 0.0]
        assert out["frame"]["normal"] == [0.0, 0.0, 1.0]
        assert "sketch_feature_id" not in out

    def test_the_preview_snaps_exactly_as_the_commit_would(self, workspace_with_part):
        """Snapping is the ENGINE moving geometry. The preview must show the
        SAME solve the commit will perform, or the user is being lied to."""
        ws = workspace_with_part
        out = preview_sketch_graph(
            ws, PART, engine_id="mechanical", profile=_line(),
            placement=PLACEMENT, candidate_key="draft1")
        ends = {p["id"]: p["world"] for p in out["points"]}
        assert ends["a"][1] == pytest.approx(ends["b"][1])     # snapped level
        lengths = [a for a in out["annotations"] if a["kind"] == "length"]
        assert lengths[0]["value"] == pytest.approx(20.0, abs=1e-9)

    def test_an_edit_preview_is_owned_by_its_feature(self, workspace_with_part):
        ws = workspace_with_part
        _author(ws)
        out = preview_sketch_graph(
            ws, PART, engine_id="mechanical", sketch_feature_id="feat_0001",
            profile={
                "points": [{"id": "skp_0006", "x": 0.0, "y": 0.0},
                           {"id": "skp_0007", "x": 40.0, "y": 0.4}],
                "segments": [{"id": "skp_0008", "start": {"id": "skp_0006"},
                              "end": {"id": "skp_0007"}}],
                "facts": [{"id": "c04", "kind": "horizontal",
                           "target": {"id": "skp_0008"}}],
            })
        assert out["owner"] == {"feature_id": "feat_0001"}
        lengths = [a for a in out["annotations"] if a["kind"] == "length"]
        assert lengths[0]["value"] == pytest.approx(40.0, abs=1e-9)

    def test_naming_both_owners_refuses(self, workspace_with_part):
        ws = workspace_with_part
        _author(ws)
        with pytest.raises(TransactionError, match="exactly one of"):
            preview_sketch_graph(
                ws, PART, engine_id="mechanical", profile=_line(),
                placement=PLACEMENT, sketch_feature_id="feat_0001")

    def test_naming_no_owner_refuses(self, workspace_with_part):
        ws = workspace_with_part
        with pytest.raises(TransactionError, match="exactly one of"):
            preview_sketch_graph(ws, PART, engine_id="mechanical", profile=_line())

    def test_a_key_shaped_like_an_engine_id_refuses(self, workspace_with_part):
        ws = workspace_with_part
        prof = _line()
        prof["points"][0]["key"] = "skp_0001"
        prof["segments"][0]["start"] = {"key": "skp_0001"}
        with pytest.raises(TransactionError, match="collides with an id"):
            preview_sketch_graph(
                ws, PART, engine_id="mechanical", profile=prof,
                placement=PLACEMENT, candidate_key="draft1")

    def test_the_read_kind_is_registered(self):
        assert "mechanical.preview_sketch_graph" in read_kinds()


class TestPreviewDisplayParity:
    """Codex5 N2: the last preview must EQUAL the refreshed Display after the
    declared substitution — never as literal equality (the preview echoes
    caller keys; Display carries minted ids)."""

    def test_preview_then_commit_agree_after_substitution(self, workspace_with_part):
        ws = workspace_with_part
        prof = _rectangle()
        preview = preview_sketch_graph(
            ws, PART, engine_id="mechanical", profile=prof,
            placement=PLACEMENT, candidate_key="draft1")
        _author(ws, prof)

        pkg = display_representation(ws, PART)
        assert pkg.display_representation_version == "1.4"
        assert len(pkg.v2_profiles) == 1
        entry = pkg.v2_profiles[0]
        assert entry.sketch_feature_id == "feat_0001"

        # substitution: caller key -> minted id, in canonical mint order
        subst = dict(zip(["p0", "p1", "p2", "p3"],
                         [p.id for p in entry.points]))
        subst.update(zip(["s0", "s1", "s2", "s3"],
                         [s.id for s in entry.segments]))

        assert [p["world"] for p in preview["points"]] == \
            [list(p.world) for p in entry.points]
        assert [(subst[s["start"]], subst[s["end"]]) for s in preview["segments"]] == \
            [(s.start, s.end) for s in entry.segments]
        assert [(a["kind"], round(a["value"], 9)) for a in preview["annotations"]] == \
            [(a.kind, round(a.value, 9)) for a in entry.annotations]
        assert [(g["kind"], subst[g["target"]]) for g in preview["constraint_glyphs"]] == \
            [(g.kind, g.target) for g in entry.constraint_glyphs]

    def test_display_joins_the_profile_to_a_frame(self, workspace_with_part):
        ws = workspace_with_part
        _author(ws)
        pkg = display_representation(ws, PART)
        frames = {f.sketch_feature_id for f in pkg.sketch_frames}
        assert {p.sketch_feature_id for p in pkg.v2_profiles} <= frames

    def test_construction_and_profile_geometry_do_not_overlap(self, workspace_with_part):
        ws = workspace_with_part
        _author(ws)
        pkg = display_representation(ws, PART)
        construction = {p.id for c in pkg.v2_construction for p in c.points}
        profile = {p.id for e in pkg.v2_profiles for p in e.points}
        assert construction and profile and not (construction & profile)

    def test_display_dimensions_follow_an_edit(self, workspace_with_part):
        ws = workspace_with_part
        _author(ws)
        propose(ws, kind="mechanical.replace_sketch_graph", params={
            "part_number": PART, "sketch_feature_id": "feat_0001",
            "profile": {
                "points": [{"id": "skp_0006", "x": 0.0, "y": 0.0},
                           {"id": "skp_0007", "x": 55.0, "y": 0.4}],
                "segments": [{"id": "skp_0008", "start": {"id": "skp_0006"},
                              "end": {"id": "skp_0007"}}],
                "facts": [{"id": "c04", "kind": "horizontal",
                           "target": {"id": "skp_0008"}}],
            },
        }).commit()
        entry = display_representation(ws, PART).v2_profiles[0]
        length = [a for a in entry.annotations if a.kind == "length"][0]
        assert length.value == pytest.approx(55.0, abs=1e-9)
