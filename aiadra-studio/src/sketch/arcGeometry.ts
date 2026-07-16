/**
 * EXACT bulge-arc geometry — the TS MIRROR of the engine's
 * `aiadra_mechanical/arc_geometry.py` (SK-C0 D-C1). Same pinned formulas,
 * fixture-locked against the same values, so the pad's live verdicts and the
 * previews match what the engine will accept and build.
 *
 * Convention (sketch-local, y-up): bulge = tan(sweep/4); positive bulge bows
 * LEFT of the directed chord P1→P2. The CENTER-relative sweep is
 * `-4*atan(bulge)` (a left-bowing minor arc traverses its center clockwise).
 * v1 domain: finite, non-zero, MINOR arcs only (1e-6 <= |bulge| < 1).
 */
import type { Pt } from './contour'

export const BULGE_MIN = 1e-6
export const BULGE_MAX = 1.0

export interface ArcGeom {
  start: Pt
  end: Pt
  bulge: number
  center: Pt
  radius: number
  /** signed CENTER-relative sweep = -4*atan(bulge), radians */
  sweep: number
  startAngle: number
  endAngle: number
}

/** The pinned v1 domain check — a human reason, or null when valid. */
export function bulgeDomainError(bulge: unknown): string | null {
  if (typeof bulge !== 'number' || !Number.isFinite(bulge)) {
    return 'bulge must be a finite number'
  }
  if (bulge === 0) return 'a zero-bulge segment is a line, not an arc'
  const ab = Math.abs(bulge)
  if (ab < BULGE_MIN) return 'the arc is flatter than the v1 minimum — use a line'
  if (ab >= BULGE_MAX) return 'v1 supports minor arcs only (less than a semicircle)'
  return null
}

export function arcGeometry(x1: number, y1: number, x2: number, y2: number, bulge: number): ArcGeom {
  const dx = x2 - x1
  const dy = y2 - y1
  const c = Math.hypot(dx, dy)
  if (c <= 0) throw new Error('arcGeometry: zero-length chord')
  const b = bulge
  const mx = (x1 + x2) / 2
  const my = (y1 + y2) / 2
  const nx = -dy / c // left unit normal of P1→P2
  const ny = dx / c
  const radius = (c * (1 + b * b)) / (4 * Math.abs(b))
  const h = (c * (b * b - 1)) / (4 * b) // signed center offset along n_left
  const center = { x: mx + nx * h, y: my + ny * h }
  const sweep = -4 * Math.atan(b)
  const startAngle = Math.atan2(y1 - center.y, x1 - center.x)
  return {
    start: { x: x1, y: y1 }, end: { x: x2, y: y2 }, bulge: b,
    center, radius, sweep, startAngle, endAngle: startAngle + sweep,
  }
}

/** The SIGNED area between arc and chord (left-bow positive) — the shoelace
 *  correction term, mirroring `circular_segment_area`. */
export function circularSegmentArea(g: ArcGeom): number {
  const theta = Math.abs(g.sweep)
  const seg = 0.5 * g.radius * g.radius * (theta - Math.sin(theta))
  return g.bulge >= 0 ? seg : -seg
}

/** Is a point on the SUPPORTING circle also within the arc's angular span? */
export function pointOnArcSpan(g: ArcGeom, px: number, py: number, tol: number): boolean {
  const ang = Math.atan2(py - g.center.y, px - g.center.x)
  const twoPi = 2 * Math.PI
  const slack = tol / Math.max(g.radius, tol)
  let off = ang - g.startAngle
  if (g.sweep >= 0) {
    off = ((off % twoPi) + twoPi) % twoPi
    return off >= -slack && off <= g.sweep + slack
  }
  off = -(((-off % twoPi) + twoPi) % twoPi)
  return off >= g.sweep - slack && off <= slack
}

/** THE named v1 angular scope policy (Codex5 B1): an accepted three-point
 *  route must be STRICTLY minor — |sweep| < π − this tolerance. The gate runs
 *  on the GEOMETRIC sweep, before the tan(sweep/4) conversion, so an exact
 *  mathematical semicircle can never round to one ulp inside |b|<1 and slip
 *  through. Routes within the tolerance of a semicircle refuse too (a
 *  deliberate sliver sacrificed for an honest boundary). */
export const SEMICIRCLE_SWEEP_TOL_RAD = 1e-9

/** bulge from the 3-point arc UX (start → via → end): the UNIQUE arc through
 *  all three points, as a bulge. Returns null when the points are degenerate/
 *  collinear OR the through-via route is a semicircle/major arc (outside the
 *  v1 domain, gated on the sweep itself per SEMICIRCLE_SWEEP_TOL_RAD) — the
 *  click is REFUSED, never silently replaced by a different curve (SK-C0
 *  Codex3 B1 + Codex5 B1). Every accepted via provably lies ON the authored
 *  arc (same circumcircle, inside the span) — invariant-tested. */
export function bulgeFromThreePoints(start: Pt, via: Pt, end: Pt): number | null {
  // circumcenter of the three points (null when collinear/degenerate)
  const d = 2 * (start.x * (via.y - end.y) + via.x * (end.y - start.y) + end.x * (start.y - via.y))
  const chord = Math.hypot(end.x - start.x, end.y - start.y)
  if (chord <= 1e-9 || Math.abs(d) <= 1e-9 * chord * chord) return null
  const s2 = start.x * start.x + start.y * start.y
  const v2 = via.x * via.x + via.y * via.y
  const e2 = end.x * end.x + end.y * end.y
  const ox = (s2 * (via.y - end.y) + v2 * (end.y - start.y) + e2 * (start.y - via.y)) / d
  const oy = (s2 * (end.x - via.x) + v2 * (start.x - end.x) + e2 * (via.x - start.x)) / d
  // oriented CENTER-relative sweep start→end PASSING THROUGH via
  const twoPi = 2 * Math.PI
  const as = Math.atan2(start.y - oy, start.x - ox)
  const av = Math.atan2(via.y - oy, via.x - ox)
  const ae = Math.atan2(end.y - oy, end.x - ox)
  const dv = (((av - as) % twoPi) + twoPi) % twoPi // CCW offset of via from start
  const de = (((ae - as) % twoPi) + twoPi) % twoPi // CCW offset of end from start
  const sweep = dv < de ? de : de - twoPi // via on the CCW route → CCW, else CW
  // Codex5 B1: the scope gate runs on the SWEEP, not the converted bulge —
  // semicircle (|sweep| = π) and major routes refuse here, in angle space.
  if (Math.abs(sweep) >= Math.PI - SEMICIRCLE_SWEEP_TOL_RAD) return null
  // our pinned convention: center-relative sweep = -4*atan(bulge)
  const bulge = -Math.tan(sweep / 4)
  return bulgeDomainError(bulge) === null ? bulge : null
}

export type ContourSegment =
  | { kind: 'line'; x1_mm: number; y1_mm: number; x2_mm: number; y2_mm: number }
  | { kind: 'arc'; x1_mm: number; y1_mm: number; x2_mm: number; y2_mm: number; bulge: number }

/** Preview/mock tessellation at the pinned sagitta tolerance (0.05 mm) —
 *  NEVER validity-authoritative. Returns the ring's points, arcs faceted. */
export function tessellateSegments(segments: ContourSegment[], sagittaMm = 0.05): Pt[] {
  const out: Pt[] = []
  for (const seg of segments) {
    out.push({ x: seg.x1_mm, y: seg.y1_mm })
    if (seg.kind === 'arc') {
      const g = arcGeometry(seg.x1_mm, seg.y1_mm, seg.x2_mm, seg.y2_mm, seg.bulge)
      const theta = Math.abs(g.sweep)
      const per = g.radius <= sagittaMm
        ? theta
        : 2 * Math.acos(Math.max(-1, Math.min(1, 1 - sagittaMm / g.radius)))
      const n = Math.max(2, Math.ceil(theta / Math.max(per, 1e-9)))
      for (let i = 1; i < n; i++) {
        const ang = g.startAngle + (g.sweep * i) / n
        out.push({ x: g.center.x + g.radius * Math.cos(ang), y: g.center.y + g.radius * Math.sin(ang) })
      }
    }
  }
  return out
}

/** A full circle as a preview polygon (for the honest mock cylinder + wires). */
export function tessellateCircle(cx: number, cy: number, r: number, n = 48): Pt[] {
  const pts: Pt[] = []
  for (let i = 0; i < n; i++) {
    const a = (2 * Math.PI * i) / n
    pts.push({ x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) })
  }
  return pts
}
