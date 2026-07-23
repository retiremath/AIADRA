"""ADR/0038 A4.6/A4.7 — the body-history chain + graph-to-bytes normalization
(arc 20260717-2 M-identity). Pure-layer tests: predecessor extraction,
head derivation, closure, the Kahn projection's sidecar-order independence,
and the serializer's dependency-byte participation."""
from __future__ import annotations

import pytest

from aiadra_core.transaction.boundary import TransactionError
from aiadra_mechanical.body_history import (
    BODY_MUTATING_TYPES,
    body_head,
    body_predecessor,
    dependency_closure,
    project_body_recipe,
)
from aiadra_mechanical.kernel import compute_recipe_bytes


def _f(fid: str, ftype: str, deps: list[str] | None = None, **payload) -> dict:
    rec: dict = {"id": fid, "feature_type": ftype, "adapter_payload": payload or {}}
    if deps is not None:
        rec["depends_on_feature_ids"] = deps
    return rec


# The canonical two-extrude fixture (what M-add will produce): base sketch →
# base extrude → face-bound sketch on the base's cap → boss extrude.
def chain_fixture() -> list[dict]:
    return [
        _f("feat_0001", "sketch"),
        _f("feat_0002", "extrude", deps=["feat_0001"]),
        _f("feat_0003", "sketch", deps=["feat_0002"]),  # face-bound on the cap
        _f("feat_0004", "extrude", deps=["feat_0003", "feat_0002"]),  # boss
    ]


class TestPredecessorExtraction:
    def test_base_has_no_predecessor(self):
        feats = chain_fixture()
        assert body_predecessor(feats, feats[1]) is None

    def test_boss_predecessor_is_the_base(self):
        feats = chain_fixture()
        assert body_predecessor(feats, feats[3]) == "feat_0002"

    def test_reference_owner_ancestor_is_not_a_second_head(self):
        # A fillet on the boss that ALSO references a base-owned role: direct
        # deps name both the boss (head) and the base (ancestor of the head).
        feats = chain_fixture() + [
            _f("feat_0005", "fillet", deps=["feat_0004", "feat_0002"]),
        ]
        assert body_predecessor(feats, feats[4]) == "feat_0004"

    def test_incomparable_maxima_reject(self):
        # Two body mutations neither of which is an ancestor of the other.
        feats = [
            _f("feat_0001", "sketch"),
            _f("feat_0002", "extrude", deps=["feat_0001"]),
            _f("feat_0003", "sketch"),
            _f("feat_0004", "extrude", deps=["feat_0003"]),
            _f("feat_0005", "fillet", deps=["feat_0002", "feat_0004"]),
        ]
        with pytest.raises(TransactionError, match="incomparable"):
            body_predecessor(feats, feats[4])


class TestBodyHead:
    def test_no_body_features(self):
        assert body_head([_f("feat_0001", "sketch")]) is None

    def test_single_base(self):
        feats = chain_fixture()[:2]
        assert body_head(feats) == "feat_0002"

    def test_chain_head_is_the_boss(self):
        assert body_head(chain_fixture()) == "feat_0004"

    def test_two_terminal_heads_reject(self):
        feats = [
            _f("feat_0001", "sketch"),
            _f("feat_0002", "extrude", deps=["feat_0001"]),
            _f("feat_0003", "sketch"),
            _f("feat_0004", "extrude", deps=["feat_0003"]),
        ]
        with pytest.raises(TransactionError, match="terminal body heads"):
            body_head(feats)

    def test_branching_from_one_head_rejects(self):
        feats = chain_fixture() + [
            _f("feat_0005", "extrude", deps=["feat_0001", "feat_0002"]),
        ]
        with pytest.raises(TransactionError, match="same body head|terminal body heads"):
            body_head(feats)

    def test_cycle_rejects(self):
        feats = [
            _f("feat_0001", "extrude", deps=["feat_0002"]),
            _f("feat_0002", "extrude", deps=["feat_0001"]),
        ]
        # A cyclic chain rejects loud — via the zero-terminal-heads rule
        # (each feature "advances from" the other) or the closure cycle walk;
        # Core additionally rejects dependency cycles at its own layer.
        with pytest.raises(TransactionError, match="cycle|terminal body heads"):
            body_head(feats)


class TestProjection:
    def test_closure_excludes_independent_sketches(self):
        feats = chain_fixture() + [_f("feat_0009", "sketch")]  # unconsumed
        closure = dependency_closure(feats, "feat_0004")
        assert closure == {"feat_0001", "feat_0002", "feat_0003", "feat_0004"}

    def test_projection_order_is_dependency_then_stable_id(self):
        proj = project_body_recipe(chain_fixture(), "feat_0004")
        assert proj.feature_ids == ("feat_0001", "feat_0002", "feat_0003", "feat_0004")

    def test_sidecar_permutation_does_not_change_projection_bytes(self):
        # Codex3 regression: permute ALL records incl. body-contributing ones.
        feats = chain_fixture() + [_f("feat_0009", "sketch")]
        import itertools
        baseline = None
        for perm in itertools.permutations(feats):
            proj = project_body_recipe(list(perm), "feat_0004")
            data = compute_recipe_bytes(list(proj.features))
            if baseline is None:
                baseline = (proj.feature_ids, data)
            assert (proj.feature_ids, data) == baseline

    def test_dependency_only_change_changes_bytes(self):
        # Codex3 regression: payloads + array order constant; ONE edge differs.
        base = chain_fixture()
        rewired = [dict(f) for f in base]
        rewired[3] = _f("feat_0004", "extrude", deps=["feat_0003"])  # drop the head edge
        a = compute_recipe_bytes(list(project_body_recipe(base, "feat_0004").features))
        b = compute_recipe_bytes(list(project_body_recipe(rewired, "feat_0004").features))
        assert a != b

    def test_one_projection_object_supplies_ids_and_features(self):
        proj = project_body_recipe(chain_fixture(), "feat_0004")
        assert proj.id_set == set(proj.feature_ids)
        assert [f["id"] for f in proj.features] == list(proj.feature_ids)


class TestSerializerDependencyBytes:
    def test_depends_participates_sorted(self):
        a = compute_recipe_bytes([_f("feat_0002", "extrude", deps=["feat_0001"])])
        b = compute_recipe_bytes([_f("feat_0002", "extrude", deps=[])])
        assert a != b
        # sorted normalization: order of the list itself is not identity
        c = compute_recipe_bytes([_f("feat_0004", "extrude", deps=["feat_0003", "feat_0002"])])
        d = compute_recipe_bytes([_f("feat_0004", "extrude", deps=["feat_0002", "feat_0003"])])
        assert c == d

    def test_classification_is_deliberate(self):
        assert BODY_MUTATING_TYPES == {"extrude", "revolve", "fillet", "chamfer", "hole"}
