"""DRAFT witness-kind measures — NOT normative, NOT frozen (Codex23 B4).

`skb-b0`'s catalog derives the EMPTY witness set for every admitted graph,
so no witness kind, measure, or degeneracy threshold is part of that frozen
id. This module is the draft prototype for the FIRST NON-EMPTY branch
policy (`skb-b1`, arriving with the strong-dimension slice), kept
executable so the machinery and its vectors do not rot:

- the draft normative text + golden vectors live in
  `Docs/SolverContracts/witness-kinds-draft.md` (explicitly informative);
- nothing in production consumes this module — `branch_policy` (the skb-b0
  authority) never imports it; only the draft-parity tests execute it;
- freezing these semantics requires, per Codex23 B4: a scale-aware operand
  DOMAIN (including a positive lower bound for radius), an error bound
  proven against the worst admitted scale, boundary vectors matching that
  domain, and solver evidence — under the new policy id's own gate. The
  current DRAFT_EPSILON is a placeholder pending exactly that proof
  (L_min alone does NOT establish mm-scale operands; a denominator just
  above L_min amplifies solver-scale noise by orders of magnitude).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .branch_policy import L_MIN_MM, _is_number

DRAFT_EPSILON = 1e-9  # placeholder — frozen only by the first non-empty policy

DRAFT_WITNESS_KINDS = ("cross_sign", "side_of_line")


@dataclass(frozen=True)
class MeasureResult:
    """Total classification of one witness measure evaluation.

    classification ∈ {"+1", "-1", "degenerate", "undefined"}; `m` is the
    normalized dimensionless measure when DEFINED, else None. ε classifies
    only a defined measure; operand/domain failures are "undefined" and
    never receive a sign.
    """

    classification: str
    m: float | None


def _classify(m: float) -> MeasureResult:
    if not math.isfinite(m):
        return MeasureResult("undefined", None)
    if abs(m) <= DRAFT_EPSILON:
        return MeasureResult("degenerate", m)
    return MeasureResult("+1" if m > 0.0 else "-1", m)


def cross_sign_measure(a: tuple[float, float], b: tuple[float, float],
                       p: tuple[float, float]) -> MeasureResult:
    """DRAFT: m = cross(b − a, p − b) / (|b − a| · |p − b|)."""
    coords = (*a, *b, *p)
    if not all(_is_number(c) for c in coords):
        return MeasureResult("undefined", None)
    ab = (b[0] - a[0], b[1] - a[1])
    bp = (p[0] - b[0], p[1] - b[1])
    n_ab = math.hypot(*ab)
    n_bp = math.hypot(*bp)
    if n_ab <= L_MIN_MM or n_bp <= L_MIN_MM:
        return MeasureResult("undefined", None)
    m = (ab[0] * bp[1] - ab[1] * bp[0]) / (n_ab * n_bp)
    return _classify(m)


def side_of_line_measure(line_a: tuple[float, float], line_b: tuple[float, float],
                         center: tuple[float, float], radius: Any) -> MeasureResult:
    """DRAFT: m = signed_point_line(center, line) / radius (the skb-1 §2b
    construction: (p.x−a.x)·u_y − (p.y−a.y)·u_x with u the unit direction)."""
    coords = (*line_a, *line_b, *center)
    if not all(_is_number(c) for c in coords):
        return MeasureResult("undefined", None)
    if not (_is_number(radius) and radius > 0.0):
        return MeasureResult("undefined", None)
    d = (line_b[0] - line_a[0], line_b[1] - line_a[1])
    n = math.hypot(*d)
    if n <= L_MIN_MM:
        return MeasureResult("undefined", None)
    ux, uy = d[0] / n, d[1] / n
    signed = (center[0] - line_a[0]) * uy - (center[1] - line_a[1]) * ux
    return _classify(signed / radius)
