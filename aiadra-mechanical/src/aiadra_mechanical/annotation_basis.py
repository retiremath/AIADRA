"""The derived annotation basis — Creo-style grey dimensions as class-5 DISPLAY.

Authority: ADR/0044 Amendment A4 (arc 20260730-1, Codex5 signoff). This is
NOT branch identity: `skb-b1` owns the graph/scalar/equality-class rules that
support its single-root proof; THIS module owns descriptor enumeration,
gradients, normalization, selection, and the semantic-id grammar. A
display-only choice never becomes part of a policy id (Codex3 N2).

What it produces: for a sketch with `N` weak degrees of freedom, exactly `N`
**locally independent derived coordinates** — deliberately NOT the global
bijection an earlier round claimed (Codex2 B2: nonlinear length/angle
coordinates admit wrap and global ambiguity even when their gradients are
locally independent).

The algorithm (A4, fully deterministic):

1. `ker(A)` is the union-find equality-class basis handed over by the branch
   policy — an exact integer basis, never an implementation-chosen SVD/QR.
2. Candidates are enumerated in a FIXED id-based order: per segment
   `length` then `angle`; per circle `radius`; per point `position_x` then
   `position_y`.
3. Each candidate's gradient is projected into the class basis (the exact
   chain rule for `x = sum_C t_C * 1_C`), then NORMALIZED — mm, degree and
   dimensionless gradients have different natural scales, so an unnormalized
   rank test would be scale-dependent.
4. Selection is modified Gram-Schmidt in candidate order; a candidate is
   accepted iff its residual norm exceeds `RANK_PIVOT`. Enumeration always
   reaches `N` because the position/radius candidates project exactly to the
   class indicators, which span the space.

The named schemes fall out rather than being special-cased: a free line
gives `length, angle, P.x, P.y`; snapping it horizontal drops the angle
(its projected row is exactly zero) leaving `length, P.x, P.y`; a bare
circle gives `radius, C.x, C.y`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

# Matches the skb-0 completion's rank tolerance (SCHEMA.md §4 pivot).
RANK_PIVOT = 1e-7
# Below this a projected row is DETERMINED (the constraint fixed the quantity).
ZERO_ROW = 1e-12

_DEG_PER_RAD = 180.0 / math.pi


@dataclass(frozen=True)
class Annotation:
    """One derived display dimension. Never persisted, never identity-bearing."""

    id: str
    kind: str                 # length | angle | radius | position_x | position_y
    value: float
    unit: str                 # mm | deg
    entities: tuple           # exactly one entity id (per-kind law, A4)
    anchors: tuple            # exactly two sketch-local (x, y) anchor points


def annotation_id(kind: str, targets: Sequence[str]) -> str:
    """Semantic derived id (Codex3 B2): ordinal `an01…` was withdrawn because a
    departing earlier candidate silently re-points it. `kind + targets` is
    unique by construction and survives value-only regeneration."""
    return f"ann:{kind}:{'+'.join(targets)}"


def glyph_id(kind: str, segment_id: str) -> str:
    return f"glyph:{kind}:{segment_id}"


def _scalar(entity_id: str, parameter: str) -> str:
    return f"{entity_id}.{parameter}"


def _project(grad: Mapping[str, float], classes: Sequence[Sequence[str]]) -> list:
    """The component along class C is the SUM of the gradient over its members
    — the exact chain rule for the parameterization x = sum_C t_C * 1_C."""
    return [sum(grad.get(s, 0.0) for s in cls) for cls in classes]


def _norm(row: Sequence[float]) -> float:
    return math.sqrt(sum(v * v for v in row))


def build_annotation_basis(
    *,
    entities: Sequence[Mapping[str, Any]],
    classes: Sequence[Sequence[str]],
    solved: Mapping[str, float],
) -> tuple:
    """Return the selected annotations, in acceptance order.

    `entities` are the PROFILE entities (construction geometry carries no
    annotations); `classes` is the branch policy's canonical equality-class
    basis; `solved` maps scalar id -> solved value.
    """
    by_id = {e["id"]: e for e in entities}
    points = sorted(i for i, e in by_id.items() if e["type"] == "point")
    segments = sorted(i for i, e in by_id.items() if e["type"] == "line")
    circles = sorted(i for i, e in by_id.items() if e["type"] == "circle")

    def xy(pid: str) -> tuple:
        return solved[_scalar(pid, "x")], solved[_scalar(pid, "y")]

    candidates: list[tuple] = []   # (kind, targets, value, unit, grad, anchors)

    for sid in segments:
        p, q = by_id[sid]["start"], by_id[sid]["end"]
        px, py = xy(p)
        qx, qy = xy(q)
        dx, dy = qx - px, qy - py
        length = math.hypot(dx, dy)
        if length <= 0.0:          # the policy guard already excluded this
            continue
        ux, uy = dx / length, dy / length
        # length: d/dP = -u, d/dQ = +u
        candidates.append((
            "length", (sid,), length, "mm",
            {_scalar(p, "x"): -ux, _scalar(p, "y"): -uy,
             _scalar(q, "x"): ux, _scalar(q, "y"): uy},
            ((px, py), (qx, qy)),
        ))
        # angle: atan2(dy, dx) in degrees over [0, 360) per the frozen catalogue
        deg = math.degrees(math.atan2(dy, dx)) % 360.0
        l2 = length * length
        candidates.append((
            "angle", (sid,), deg, "deg",
            {_scalar(p, "x"): dy * _DEG_PER_RAD / l2,
             _scalar(p, "y"): -dx * _DEG_PER_RAD / l2,
             _scalar(q, "x"): -dy * _DEG_PER_RAD / l2,
             _scalar(q, "y"): dx * _DEG_PER_RAD / l2},
            ((px, py), (qx, qy)),
        ))

    for cid in circles:
        ctr = by_id[cid]["center"]
        cx, cy = xy(ctr)
        r = solved[_scalar(cid, "radius")]
        candidates.append((
            "radius", (cid,), r, "mm",
            {_scalar(cid, "radius"): 1.0},
            ((cx, cy), (cx + r, cy)),     # centre + the canonical rim point at angle 0
        ))

    for pid in points:
        px, py = xy(pid)
        candidates.append((
            "position_x", (pid,), px, "mm",
            {_scalar(pid, "x"): 1.0}, ((0.0, 0.0), (px, py)),
        ))
        candidates.append((
            "position_y", (pid,), py, "mm",
            {_scalar(pid, "y"): 1.0}, ((0.0, 0.0), (px, py)),
        ))

    target_rank = len(classes)
    accepted: list[Annotation] = []
    ortho: list[list] = []          # orthonormal rows of the accepted span

    for kind, targets, value, unit, grad, anchors in candidates:
        if len(accepted) == target_rank:
            break
        row = _project(grad, classes)
        n0 = _norm(row)
        if n0 <= ZERO_ROW:
            continue                # DETERMINED by the constraints — correctly skipped
        row = [v / n0 for v in row]
        # modified Gram-Schmidt against the accepted span
        for basis in ortho:
            dot = sum(a * b for a, b in zip(row, basis))
            row = [a - dot * b for a, b in zip(row, basis)]
        residual = _norm(row)
        if residual <= RANK_PIVOT:
            continue                # dependent on already-selected descriptors
        ortho.append([v / residual for v in row])
        accepted.append(Annotation(
            id=annotation_id(kind, targets), kind=kind, value=value,
            unit=unit, entities=tuple(targets), anchors=tuple(anchors),
        ))

    if len(accepted) != target_rank:
        raise AssertionError(
            f"annotation basis reached {len(accepted)} of {target_rank} "
            "independent descriptors — the position/radius fallbacks must "
            "always complete the basis (A4 termination proof)"
        )
    return tuple(accepted)


def build_constraint_glyphs(constraints: Sequence[Mapping[str, Any]],
                            profile_segment_ids: Sequence[str]) -> tuple:
    """H/V glyphs for profile segments — the Creo-style constraint markers.
    One glyph per admitted axis fact; `target` is exactly one segment."""
    seg = set(profile_segment_ids)
    out = []
    for c in sorted(constraints, key=lambda c: str(c.get("id"))):
        kind = c.get("kind")
        if kind not in ("horizontal", "vertical"):
            continue
        target = c["args"][0]
        if target not in seg:
            continue
        out.append({"id": glyph_id(kind, target), "kind": kind, "target": target})
    return tuple(out)
