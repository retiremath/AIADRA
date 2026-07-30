"""The profile-payload resolver: the closed ref grammar, canonical minting,
and the same-id STRUCTURAL survival law (ADR/0044 A4; Codex4 B1/B2)."""
from __future__ import annotations

import pytest

from aiadra_core.transaction.boundary import TransactionError

from aiadra_mechanical.profile_ops import resolve_profile

OP = "mechanical.replace_sketch_graph"


def _line_payload():
    return {
        "points": [{"key": "p0", "x": 1.0, "y": 2.0},
                   {"key": "p1", "x": 9.0, "y": 2.2}],
        "segments": [{"key": "s0", "start": {"key": "p0"}, "end": {"key": "p1"}}],
        "facts": [{"key": "f0", "kind": "horizontal", "target": {"key": "s0"}}],
    }


def _existing_from(entities, constraints):
    return {**{e["id"]: e for e in entities}, **{c["id"]: c for c in constraints}}


class TestMinting:
    def test_keys_mint_canonical_ids_in_dependency_then_call_order(self):
        ents, cons, removed = resolve_profile(
            _line_payload(), op=OP, reserved_ids=["skp_0001", "skp_0002"])
        assert [e["id"] for e in ents] == ["skp_0003", "skp_0004", "skp_0005"]
        assert cons == [{"id": "c01", "kind": "horizontal", "args": ["skp_0005"]}]
        assert removed == []

    def test_refs_resolve_through_keys(self):
        ents, _, _ = resolve_profile(_line_payload(), op=OP)
        seg = [e for e in ents if e["type"] == "line"][0]
        assert (seg["start"], seg["end"]) == ("skp_0001", "skp_0002")

    def test_a_bare_string_ref_is_never_accepted(self):
        payload = _line_payload()
        payload["segments"][0]["start"] = "p0"
        with pytest.raises(TransactionError, match="bare string is never"):
            resolve_profile(payload, op=OP)

    def test_duplicate_keys_refuse(self):
        payload = _line_payload()
        payload["points"][1]["key"] = "p0"
        with pytest.raises(TransactionError, match="unique across"):
            resolve_profile(payload, op=OP)

    def test_unknown_key_reference_refuses(self):
        payload = _line_payload()
        payload["segments"][0]["end"] = {"key": "nope"}
        with pytest.raises(TransactionError, match="no record in this call"):
            resolve_profile(payload, op=OP)

    def test_a_record_carrying_both_key_and_id_refuses(self):
        payload = _line_payload()
        payload["points"][0]["id"] = "skp_0001"
        with pytest.raises(TransactionError, match="exactly one of"):
            resolve_profile(payload, op=OP)

    def test_entity_id_capacity_refuses_before_staging(self):
        full = [f"skp_{n:04d}" for n in range(1, 10000)]
        with pytest.raises(TransactionError, match="id space .* is exhausted"):
            resolve_profile({"points": [{"key": "p0", "x": 0.0, "y": 0.0}]},
                            op=OP, reserved_ids=full)


class TestSurvivalLaw:
    """Codex4 B1: under a preserved id ONLY authored nominals may change.
    Structural change must omit the id and supply a new key."""

    def _committed(self):
        ents, cons, _ = resolve_profile(_line_payload(), op=OP)
        return ents, cons, _existing_from(ents, cons)

    def test_preserved_point_id_may_move_its_nominal(self):
        ents, cons, existing = self._committed()
        payload = {
            "points": [{"id": "skp_0001", "x": 5.0, "y": 5.0},
                       {"id": "skp_0002", "x": 9.0, "y": 2.2}],
            "segments": [{"id": "skp_0003", "start": {"id": "skp_0001"},
                          "end": {"id": "skp_0002"}}],
            "facts": [{"id": "c01", "kind": "horizontal",
                       "target": {"id": "skp_0003"}}],
        }
        out, out_cons, removed = resolve_profile(
            payload, op=OP, existing=existing,
            reserved_ids=list(existing))
        assert out[0]["nominal"] == {"x": 5.0, "y": 5.0}
        assert [e["id"] for e in out] == ["skp_0001", "skp_0002", "skp_0003"]
        assert removed == []

    def test_rewiring_a_segment_under_a_preserved_id_REFUSES(self):
        """The identity hole Codex4 B1 caught: I2 uses the segment id as wall
        identity, so a rewired segment must never keep it."""
        ents, cons, existing = self._committed()
        payload = {
            "points": [{"id": "skp_0001", "x": 1.0, "y": 2.0},
                       {"id": "skp_0002", "x": 9.0, "y": 2.2},
                       {"key": "p2", "x": 4.0, "y": 8.0}],
            "segments": [{"id": "skp_0003", "start": {"id": "skp_0001"},
                          "end": {"key": "p2"}}],       # <- rewired
        }
        with pytest.raises(TransactionError, match="changes its endpoints"):
            resolve_profile(payload, op=OP, existing=existing,
                            reserved_ids=list(existing))

    def test_retargeting_a_fact_under_a_preserved_id_REFUSES(self):
        ents, cons, existing = self._committed()
        payload = {
            "points": [{"id": "skp_0001", "x": 1.0, "y": 2.0},
                       {"id": "skp_0002", "x": 9.0, "y": 2.2},
                       {"key": "p2", "x": 4.0, "y": 8.0}],
            "segments": [{"id": "skp_0003", "start": {"id": "skp_0001"},
                          "end": {"id": "skp_0002"}},
                         {"key": "s1", "start": {"id": "skp_0002"},
                          "end": {"key": "p2"}}],
            "facts": [{"id": "c01", "kind": "horizontal",
                       "target": {"key": "s1"}}],       # <- retargeted
        }
        with pytest.raises(TransactionError, match="changes its kind or target"):
            resolve_profile(payload, op=OP, existing=existing,
                            reserved_ids=list(existing))

    def test_same_id_kind_mutation_refuses(self):
        ents, cons, existing = self._committed()
        payload = {"circles": [{"id": "skp_0001", "center": {"key": "c"},
                                "radius_mm": 3.0}],
                   "points": [{"key": "c", "x": 0.0, "y": 0.0}]}
        with pytest.raises(TransactionError, match="same-id kind mutation"):
            resolve_profile(payload, op=OP, existing=existing,
                            reserved_ids=list(existing))

    def test_an_absent_id_is_REMOVED_the_skeleton_case(self):
        ents, cons, existing = self._committed()
        payload = {
            "points": [{"id": "skp_0001", "x": 1.0, "y": 2.0},
                       {"id": "skp_0002", "x": 9.0, "y": 2.2}],
            "segments": [{"id": "skp_0003", "start": {"id": "skp_0001"},
                          "end": {"id": "skp_0002"}}],
        }                                     # c01 omitted
        _, out_cons, removed = resolve_profile(
            payload, op=OP, existing=existing, reserved_ids=list(existing))
        assert out_cons == []
        assert removed == ["c01"]

    def test_a_foreign_id_refuses(self):
        _, _, existing = self._committed()
        payload = {"points": [{"id": "skp_0099", "x": 0.0, "y": 0.0}]}
        with pytest.raises(TransactionError, match="not a record of THIS"):
            resolve_profile(payload, op=OP, existing=existing,
                            reserved_ids=list(existing))


class TestClosedShapes:
    def test_unknown_profile_key_refuses(self):
        with pytest.raises(TransactionError, match="unknown keys"):
            resolve_profile({"points": [], "arcs": []}, op=OP)

    def test_non_axis_fact_kind_refuses(self):
        payload = _line_payload()
        payload["facts"][0]["kind"] = "tangent"
        with pytest.raises(TransactionError, match="outside skb-b1"):
            resolve_profile(payload, op=OP)
