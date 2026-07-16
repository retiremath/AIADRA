"""Shared EXACT arc geometry for bulge contour segments (SK-C0, arc 20260715-4).

ONE pure module owns the bulge convention — the engine evaluator, Class-1
validation, topology, and the Studio TS mirror all derive from these formulas
(the TS mirror is unit-tested against the same fixture table).

Convention (sketch-local (u, v), pinned in the arc's Claude2 design):
  bulge = tan(sweep_magnitude/4), dimensionless. Positive bulge = the arc bows
  to the LEFT of the directed chord P1->P2; negative = right. The
  CENTER-relative signed sweep is `-4*atan(bulge)` (a left-bowing minor arc
  traverses its center CLOCKWISE) — one convention, stated once here and
  implemented below.

Derived (never persisted):
  chord   c = |P2 - P1|
  sagitta s = bulge * c / 2          (apex at M + n_left * s)
  radius  r = c * (1 + bulge^2) / (4 * |bulge|)
  center  = M + n_left * c * (bulge^2 - 1) / (4 * bulge)
where M is the chord midpoint and n_left the left unit normal of P1->P2.

v1 domain (Class-1, scope-bounded): finite bulge, bulge != 0 (author a line),
MINOR ARCS ONLY: 1e-6 <= |bulge| < 1 (a semicircle or major arc is deferred
scope; a full circle is the circle primitive).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

BULGE_MIN = 1e-6  # below: deviates from its chord by < c*5e-7 -- author a line
BULGE_MAX = 1.0   # exclusive: minor arcs only in v1 (scope bound, not invariant)


@dataclass(frozen=True)
class ArcGeometry:
    """Exact derived geometry of one bulge segment (all lengths mm, angles rad)."""

    start: tuple[float, float]
    end: tuple[float, float]
    bulge: float
    center: tuple[float, float]
    radius: float
    sweep: float          # signed CENTER-relative sweep = -4*atan(bulge); |sweep| < pi in v1
    start_angle: float    # atan2 angle of `start` around `center`
    end_angle: float      # start_angle + sweep (signed direction preserved)


def bulge_domain_error(bulge: object) -> str | None:
    """The pinned v1 domain check. Returns a human reason or None if valid."""
    if not isinstance(bulge, (int, float)) or isinstance(bulge, bool):
        return f"bulge must be a number, got {bulge!r}"
    b = float(bulge)
    if not math.isfinite(b):
        return f"bulge must be finite, got {b!r}"
    if b == 0.0:
        return "bulge == 0 is not an arc: author kind:'line' (no silent canonicalization)"
    if abs(b) < BULGE_MIN:
        return (
            f"|bulge| = {abs(b):g} is below the v1 minimum {BULGE_MIN:g} "
            f"(sub-tolerance curvature; author a line)"
        )
    if abs(b) >= BULGE_MAX:
        return (
            f"|bulge| = {abs(b):g} is outside v1's minor-arc scope (|bulge| < 1); "
            f"a semicircle/major arc is deferred scope; a full circle is the "
            f"circle primitive"
        )
    return None


def arc_geometry(x1: float, y1: float, x2: float, y2: float, bulge: float) -> ArcGeometry:
    """Exact derived geometry; assumes the domain has been validated and the
    chord is non-degenerate (Class-1 checks both before calling)."""
    dx, dy = x2 - x1, y2 - y1
    c = math.hypot(dx, dy)
    if c <= 0.0:
        raise ValueError("arc_geometry: zero-length chord")
    b = float(bulge)
    mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    nx, ny = -dy / c, dx / c  # left unit normal of P1->P2
    radius = c * (1.0 + b * b) / (4.0 * abs(b))
    h = c * (b * b - 1.0) / (4.0 * b)  # signed center offset along n_left
    cx, cy = mx + nx * h, my + ny * h
    # Center-relative sweep sign: a LEFT-bowing minor arc has its center on the
    # RIGHT of the chord, so start->end traverses the center CLOCKWISE —
    # sweep = -4*atan(b) under the pinned left-bow-positive convention.
    # (Verified: (0,0)->(20,0) b=+0.5 -> start 143.13deg, apex 90deg, end 36.87deg.)
    sweep = -4.0 * math.atan(b)
    start_angle = math.atan2(y1 - cy, x1 - cx)
    return ArcGeometry(
        start=(x1, y1), end=(x2, y2), bulge=b, center=(cx, cy), radius=radius,
        sweep=sweep, start_angle=start_angle, end_angle=start_angle + sweep,
    )


def circular_segment_area(geom: ArcGeometry) -> float:
    """The SIGNED area between the arc and its chord (mm^2): positive when the
    arc bows LEFT of the directed chord (adds to a CCW ring's shoelace area)."""
    theta = abs(geom.sweep)
    seg = 0.5 * geom.radius * geom.radius * (theta - math.sin(theta))
    return math.copysign(seg, geom.bulge)


def point_on_arc_span(geom: ArcGeometry, px: float, py: float, tol: float) -> bool:
    """Is a point ON THE SUPPORTING CIRCLE also within the arc's angular span?
    (The caller establishes circle membership; this resolves boundedness.)"""
    ang = math.atan2(py - geom.center[1], px - geom.center[0])
    # normalize the angular offset from start into the signed sweep direction
    off = ang - geom.start_angle
    two_pi = 2.0 * math.pi
    if geom.sweep >= 0:
        off %= two_pi
        lo, hi = -tol / max(geom.radius, tol), geom.sweep + tol / max(geom.radius, tol)
        return lo <= off <= hi
    off = -((-off) % two_pi)
    lo, hi = geom.sweep - tol / max(geom.radius, tol), tol / max(geom.radius, tol)
    return lo <= off <= hi


def sagitta_tessellate(geom: ArcGeometry, sagitta_tol_mm: float = 0.05) -> list[tuple[float, float]]:
    """Preview-only polyline of the arc (start..end inclusive) at the pinned
    sagitta tolerance. NEVER validity-authoritative (the exact predicates are)."""
    theta = abs(geom.sweep)
    if geom.radius <= sagitta_tol_mm:
        n = 2
    else:
        per = 2.0 * math.acos(max(-1.0, min(1.0, 1.0 - sagitta_tol_mm / geom.radius)))
        n = max(2, math.ceil(theta / max(per, 1e-9)))
    pts = []
    for i in range(n + 1):
        a = geom.start_angle + geom.sweep * (i / n)
        pts.append((geom.center[0] + geom.radius * math.cos(a),
                    geom.center[1] + geom.radius * math.sin(a)))
    return pts
