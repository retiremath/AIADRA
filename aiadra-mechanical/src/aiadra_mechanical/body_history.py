"""The body-history chain + graph-to-bytes normalization (ADR/0038 A4.6/A4.7).

Sequential extrudes (arc 20260717-2) make a Part hold more than one
body-mutating feature. Body ORDER is then identity-bearing, and its authority
is the feature dependency graph (`depends_on_feature_ids`, ADR/0029 D9) —
NEVER sidecar array position. This module owns the executable rules:

- which feature kinds MUTATE the body (semantic classification);
- the A4.6 predecessor-extraction rule (unique-maximal direct body-mutating
  dependency; other body-mutating deps must be its ancestors; incomparable
  maxima fail Class-1);
- the A4.7 normalization: the body head's dependency closure ordered by a
  Kahn topological sort with STABLE FEATURE-ID ordering among
  simultaneously-ready vertices. Filtering the sidecar array in place does
  NOT satisfy the rule — the projection is derived from the graph.

One projection object (`BodyProjection`) supplies the staged recipe features,
`body_recipe_ids`, and both provenance fields — never parallel traversals
(A4.7.3). All functions are pure over feature dicts; Class-1 failures raise
`TransactionError` before any kernel work.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aiadra_core.transaction.boundary import TransactionError

# The semantic classification (A4.6): kinds that MUTATE the single v1 body.
# A sketch never mutates the body; fillet/chamfer/hole re-shape it; extrude/
# revolve create-or-mutate it. Future kinds must be classified deliberately.
BODY_MUTATING_TYPES = frozenset({"extrude", "revolve", "fillet", "chamfer", "hole"})

_OP = "mechanical.body_history"


def is_body_mutating(feature: dict[str, Any]) -> bool:
    return feature.get("feature_type") in BODY_MUTATING_TYPES


def _by_id(features: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for f in features:
        fid = f.get("id")
        if not isinstance(fid, str) or not fid:
            raise TransactionError(f"{_OP}: a feature record has no stable id")
        if fid in out:
            raise TransactionError(f"{_OP}: duplicate feature id {fid!r}")
        out[fid] = f
    return out


def _deps(feature: dict[str, Any]) -> list[str]:
    deps = feature.get("depends_on_feature_ids", []) or []
    if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
        raise TransactionError(
            f"{_OP}: feature {feature.get('id')!r} has a malformed depends_on_feature_ids"
        )
    return deps


def dependency_closure(features: list[dict[str, Any]], head_id: str) -> set[str]:
    """The dependency-closed ancestor set of `head_id`, inclusive. Cycles and
    dangling edges fail Class-1 (Core also rejects them at its own layer)."""
    index = _by_id(features)
    if head_id not in index:
        raise TransactionError(f"{_OP}: unknown head feature {head_id!r}")
    closure: set[str] = set()
    in_progress: set[str] = set()

    def visit(fid: str) -> None:
        if fid in closure:
            return
        if fid in in_progress:
            raise TransactionError(f"{_OP}: dependency cycle through {fid!r}")
        if fid not in index:
            raise TransactionError(f"{_OP}: dangling dependency {fid!r}")
        in_progress.add(fid)
        for d in _deps(index[fid]):
            visit(d)
        in_progress.discard(fid)
        closure.add(fid)

    visit(head_id)
    return closure


def _is_ancestor(features: list[dict[str, Any]], ancestor: str, descendant: str) -> bool:
    """True iff `ancestor` is in the dependency closure of `descendant`
    (strictly: reachable from it; a feature is its own ancestor here only if
    equal, which callers exclude)."""
    if ancestor == descendant:
        return True
    return ancestor in dependency_closure(features, descendant)


def body_predecessor(features: list[dict[str, Any]], feature: dict[str, Any]) -> str | None:
    """A4.6 predecessor extraction: among the feature's DIRECT body-mutating
    dependencies, the unique maximal under graph reachability is the
    immediately-preceding body head; every other direct body-mutating
    dependency must be an ancestor of that head. Returns None for a base
    mutation (no body-mutating dependency). Incomparable maxima → Class-1."""
    index = _by_id(features)
    direct_body = [d for d in _deps(feature) if d in index and is_body_mutating(index[d])]
    if not direct_body:
        return None
    # Maximal = not an ancestor of any OTHER direct body-mutating dependency.
    maxima = [
        d for d in direct_body
        if not any(other != d and _is_ancestor(features, d, other) for other in direct_body)
    ]
    if len(maxima) != 1:
        raise TransactionError(
            f"{_OP}: feature {feature.get('id')!r} has {len(maxima)} incomparable "
            f"body-mutating dependencies {sorted(maxima)!r} — the v1 single-body "
            f"model requires exactly one immediately-preceding body head"
        )
    head = maxima[0]
    for d in direct_body:
        if d != head and not _is_ancestor(features, d, head):
            raise TransactionError(
                f"{_OP}: feature {feature.get('id')!r} depends on body feature {d!r} "
                f"that is not an ancestor of its body head {head!r}"
            )
    return head


def body_head(features: list[dict[str, Any]]) -> str | None:
    """The CURRENT body head of a recipe: the unique body-mutating feature no
    other body-mutating feature advances from. None when no body exists.
    Multiple terminal heads (branching) or a broken chain fail Class-1."""
    body = [f for f in features if is_body_mutating(f)]
    if not body:
        return None
    ids = {f["id"] for f in body}
    advanced_from: set[str] = set()
    for f in body:
        pred = body_predecessor(features, f)
        if pred is not None:
            if pred not in ids:
                raise TransactionError(
                    f"{_OP}: body predecessor {pred!r} of {f.get('id')!r} is not a "
                    f"body-mutating feature of this recipe"
                )
            advanced_from.add(pred)
    heads = sorted(ids - advanced_from)
    if len(heads) != 1:
        raise TransactionError(
            f"{_OP}: the recipe has {len(heads)} terminal body heads {heads!r}; "
            f"the v1 single-body model requires exactly one"
        )
    # The chain must be linear: every non-head advances into the chain exactly
    # once (two features naming the same predecessor = branching).
    preds = [body_predecessor(features, f) for f in body]
    named = [p for p in preds if p is not None]
    if len(named) != len(set(named)):
        raise TransactionError(
            f"{_OP}: two body mutations advance from the same body head — the "
            f"v1 single-body model is a linear chain"
        )
    return heads[0]


def normalize_feature_order(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Codex6 B1 — the graph-normalized TOTAL order of an arbitrary feature
    list: a Kahn topological sort over the INDUCED subgraph (edges to features
    outside the list are ignored — prefix slices stay valid) with stable
    feature-id ordering among simultaneously-ready vertices. For every
    append-authored recipe this equals the array order (ids allocate in
    creation order), so all existing signatures stay byte-identical; a legally
    permuted sidecar normalizes back to the same sequence. Cycles fail Class-1
    (evaluation refuses them anyway)."""
    index = _by_id(features)
    ids = set(index)
    indegree: dict[str, int] = {fid: 0 for fid in ids}
    dependents: dict[str, list[str]] = {fid: [] for fid in ids}
    for fid in ids:
        for d in _deps(index[fid]):
            if d in ids:
                indegree[fid] += 1
                dependents[d].append(fid)
    ready = sorted(fid for fid, n in indegree.items() if n == 0)
    ordered: list[str] = []
    while ready:
        fid = ready.pop(0)
        ordered.append(fid)
        newly = []
        for dep in dependents[fid]:
            indegree[dep] -= 1
            if indegree[dep] == 0:
                newly.append(dep)
        if newly:
            ready = sorted(ready + newly)
    if len(ordered) != len(ids):
        raise TransactionError(f"{_OP}: dependency cycle in the feature list")
    return [index[fid] for fid in ordered]


@dataclass(frozen=True)
class BodyProjection:
    """A4.7.3 — the ONE projection object. `features` is the normalized
    ordered body recipe (the staged bytes' input); `feature_ids` is its
    ordered id list; both provenance fields derive from HERE."""

    features: tuple[dict[str, Any], ...]
    feature_ids: tuple[str, ...] = field(default=())

    @property
    def id_set(self) -> set[str]:
        return set(self.feature_ids)


def project_body_recipe(features: list[dict[str, Any]], head_id: str) -> BodyProjection:
    """A4.7.1 — the graph-to-bytes normalization: the body head's dependency
    closure ordered by a Kahn topological sort with stable feature-id ordering
    among simultaneously-ready vertices. Deterministic for any two evaluators
    given the same graph; sidecar array position never participates."""
    index = _by_id(features)
    closure = dependency_closure(features, head_id)
    # Kahn over the closure-induced subgraph.
    indegree: dict[str, int] = {fid: 0 for fid in closure}
    dependents: dict[str, list[str]] = {fid: [] for fid in closure}
    for fid in closure:
        for d in _deps(index[fid]):
            if d in closure:
                indegree[fid] += 1
                dependents[d].append(fid)
    ready = sorted(fid for fid, n in indegree.items() if n == 0)
    ordered: list[str] = []
    while ready:
        fid = ready.pop(0)  # stable id order among simultaneously-ready
        ordered.append(fid)
        newly: list[str] = []
        for dep in dependents[fid]:
            indegree[dep] -= 1
            if indegree[dep] == 0:
                newly.append(dep)
        if newly:
            ready = sorted(ready + newly)
    if len(ordered) != len(closure):
        raise TransactionError(f"{_OP}: dependency cycle inside the body closure")
    return BodyProjection(
        features=tuple(index[fid] for fid in ordered),
        feature_ids=tuple(ordered),
    )
