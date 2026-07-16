/**
 * Pure contour geometry for the sketcher (arc 20260711-11 slice S/X). A contour
 * is an ordered ring of points (mm, y-up engine convention) on the sketch plane.
 *
 * `contourProblem` is a CLIENT-SIDE MIRROR of the engine's Class-1 domain gate
 * (`aiadra-mechanical/adapter_payload.require_valid_contour`) — same rules
 * (closed ≥3 / non-zero area / non-self-intersecting / no collinear adjacency) so
 * the pad gives instant, honest feedback that matches what commit will accept.
 * The engine remains the authority; this only front-runs its verdict for UX.
 */
import {
  arcGeometry,
  bulgeDomainError,
  circularSegmentArea,
  pointOnArcSpan,
  type ArcGeom,
} from './arcGeometry'

export interface Pt {
  x: number
  y: number
}

export type LineSegment = { kind: 'line'; x1_mm: number; y1_mm: number; x2_mm: number; y2_mm: number }
export type ArcSegment = { kind: 'arc'; x1_mm: number; y1_mm: number; x2_mm: number; y2_mm: number; bulge: number }
export type Segment = LineSegment | ArcSegment

const TOL = 1e-6

/** Ring of points → the engine's closed-ring segments (the closer included).
 *  SK-C0 D-C1: `bulges[i]` (0 = line) curves the segment points[i]→points[i+1];
 *  the CLOSING segment stays a line in the v1 pad. */
export function pointsToSegments(points: Pt[], bulges?: number[]): Segment[] {
  const n = points.length
  return points.map((p, i) => {
    const q = points[(i + 1) % n]
    const b = bulges?.[i] ?? 0
    return b !== 0
      ? { kind: 'arc', x1_mm: p.x, y1_mm: p.y, x2_mm: q.x, y2_mm: q.y, bulge: b }
      : { kind: 'line', x1_mm: p.x, y1_mm: p.y, x2_mm: q.x, y2_mm: q.y }
  })
}

export function dist(a: Pt, b: Pt): number {
  return Math.hypot(a.x - b.x, a.y - b.y)
}

/** Shoelace signed area (mm²); + is CCW in y-up. */
export function signedArea(points: Pt[]): number {
  let s = 0
  const n = points.length
  for (let i = 0; i < n; i++) {
    const a = points[i]
    const b = points[(i + 1) % n]
    s += a.x * b.y - b.x * a.y
  }
  return s / 2
}

/** The first client-visible reason this ring is not a valid profile, else null.
 *  With `bulges` (SK-C0), the verdict is CURVE-AWARE — the exact mirror of the
 *  engine's upgraded Class-1 gate (see segmentsProblem). */
export function contourProblem(points: Pt[], bulges?: number[]): string | null {
  if (points.length < 3) return 'Add at least 3 points to enclose an area.'
  // Codex6 B2 — exact engine parity: the engine rejects zero-length segments
  // BEFORE its other checks. A consecutive (or wrapping — the closing segment)
  // duplicate point is exactly that, and `collinearVertex` deliberately skips
  // zero-length edges, so this must be checked first.
  const n = points.length
  for (let i = 0; i < n; i++) {
    if (dist(points[i], points[(i + 1) % n]) <= TOL) {
      return 'Remove the duplicate point (a zero-length segment).'
    }
  }
  if (bulges && bulges.some((b) => b !== 0)) {
    return segmentsProblem(pointsToSegments(points, bulges))
  }
  if (Math.abs(signedArea(points)) <= TOL) return 'The contour encloses no area.'
  if (selfIntersects(points)) return 'The contour crosses itself — make it a simple loop.'
  if (collinearVertex(points) !== null) return 'Remove the redundant point (three points in a line).'
  return null
}

/** CURVE-AWARE simple-wire mirror (SK-C0 B1) over typed segments — the same
 *  policy as the engine's `require_valid_contour`: segment-corrected signed
 *  area; exact line–arc/arc–arc predicates with span filtering; TOUCH counts;
 *  adjacent pairs exempt only their shared endpoint; adjacent co-circular arcs
 *  reject; tangent line–arc joints are allowed. */
export function segmentsProblem(segments: Segment[]): string | null {
  const n = segments.length
  // engine parity: zero-length chords reject FIRST (before arc math runs)
  for (const s of segments) {
    if (Math.hypot(s.x2_mm - s.x1_mm, s.y2_mm - s.y1_mm) <= TOL) {
      return 'Remove the duplicate point (a zero-length segment).'
    }
  }
  const geoms = segments.map((s) =>
    s.kind === 'arc' ? arcGeometry(s.x1_mm, s.y1_mm, s.x2_mm, s.y2_mm, s.bulge) : null,
  )
  for (let i = 0; i < n; i++) {
    const s = segments[i]
    if (s.kind === 'arc') {
      const err = bulgeDomainError(s.bulge)
      if (err) return `Arc ${i + 1}: ${err}.`
    }
  }
  // curve-corrected signed area
  let area = signedArea(segments.map((s) => ({ x: s.x1_mm, y: s.y1_mm })))
  for (const g of geoms) if (g) area += circularSegmentArea(g)
  if (Math.abs(area) <= TOL) return 'The contour encloses no area.'
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const adjacent = j === i + 1 || (i === 0 && j === n - 1)
      const shared = adjacent
        ? j === i + 1
          ? { x: segments[j].x1_mm, y: segments[j].y1_mm }
          : { x: segments[i].x1_mm, y: segments[i].y1_mm }
        : null
      const why = pairConflict(segments[i], geoms[i], segments[j], geoms[j], adjacent, shared)
      if (why) return why
    }
  }
  return null
}

function pairConflict(
  si: Segment, gi: ArcGeom | null, sj: Segment, gj: ArcGeom | null,
  adjacent: boolean, shared: Pt | null,
): string | null {
  const near = (p: Pt, q: Pt) => Math.hypot(p.x - q.x, p.y - q.y) <= TOL
  const beyondShared = (pts: Pt[]) => pts.filter((p) => !shared || !near(p, shared))
  const A = (s: Segment): Pt => ({ x: s.x1_mm, y: s.y1_mm })
  const B = (s: Segment): Pt => ({ x: s.x2_mm, y: s.y2_mm })

  if (!gi && !gj) {
    if (adjacent) {
      const d1x = B(si).x - A(si).x, d1y = B(si).y - A(si).y
      const d2x = B(sj).x - A(sj).x, d2y = B(sj).y - A(sj).y
      const n1 = Math.hypot(d1x, d1y), n2 = Math.hypot(d2x, d2y)
      if (Math.abs(d1x * d2y - d1y * d2x) / (n1 * n2) <= TOL) {
        return 'Remove the redundant point (three points in a line).'
      }
      return null
    }
    return segmentsIntersect(A(si), B(si), A(sj), B(sj))
      ? 'The contour crosses itself — make it a simple loop.'
      : null
  }
  if (gi && gj) {
    const sameCircle = near(gi.center, gj.center) && Math.abs(gi.radius - gj.radius) <= TOL
    if (sameCircle) {
      if (adjacent) return 'Adjacent arcs on the same circle — author one arc instead.'
      for (const [ga, gb] of [[gi, gj], [gj, gi]] as const) {
        const midAng = ga.startAngle + ga.sweep / 2
        const probes = [ga.start, ga.end,
          { x: ga.center.x + ga.radius * Math.cos(midAng), y: ga.center.y + ga.radius * Math.sin(midAng) }]
        for (const p of probes) {
          if (shared && near(p, shared)) continue
          if (pointOnArcSpan(gb, p.x, p.y, TOL)) return 'Two arcs overlap on the same circle.'
        }
      }
      return null
    }
    const hits = circleCircleHits(gi.center, gi.radius, gj.center, gj.radius)
    const contacts = hits.filter(
      (p) => pointOnArcSpan(gi, p.x, p.y, TOL) && pointOnArcSpan(gj, p.x, p.y, TOL),
    )
    const extra = adjacent ? beyondShared(contacts) : contacts
    return extra.length ? 'The contour crosses itself — make it a simple loop.' : null
  }
  // mixed line + arc — tangent adjacency is ALLOWED
  const line = gi ? sj : si
  const g = (gi ?? gj)!
  const hits = lineCircleHits(A(line), B(line), g.center, g.radius)
  const contacts = hits.filter((p) => pointOnArcSpan(g, p.x, p.y, TOL))
  const extra = adjacent ? beyondShared(contacts) : contacts
  return extra.length ? 'The contour crosses itself — make it a simple loop.' : null
}

function lineCircleHits(a: Pt, b: Pt, center: Pt, radius: number): Pt[] {
  const dx = b.x - a.x, dy = b.y - a.y
  const fx = a.x - center.x, fy = a.y - center.y
  const A2 = dx * dx + dy * dy
  const B2 = 2 * (fx * dx + fy * dy)
  const C2 = fx * fx + fy * fy - radius * radius
  let disc = B2 * B2 - 4 * A2 * C2
  if (disc < -TOL * A2) return []
  disc = Math.max(disc, 0)
  const out: Pt[] = []
  for (const t of [(-B2 - Math.sqrt(disc)) / (2 * A2), (-B2 + Math.sqrt(disc)) / (2 * A2)]) {
    if (t >= -TOL && t <= 1 + TOL) {
      const p = { x: a.x + t * dx, y: a.y + t * dy }
      if (!out.some((q) => Math.hypot(p.x - q.x, p.y - q.y) <= TOL)) out.push(p)
    }
  }
  return out
}

function circleCircleHits(c1: Pt, r1: number, c2: Pt, r2: number): Pt[] {
  let d = Math.hypot(c2.x - c1.x, c2.y - c1.y)
  if (d > r1 + r2 + TOL || d < Math.abs(r1 - r2) - TOL) return []
  d = Math.max(d, 1e-12)
  const a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
  const h = Math.sqrt(Math.max(r1 * r1 - a * a, 0))
  const ux = (c2.x - c1.x) / d, uy = (c2.y - c1.y) / d
  const m = { x: c1.x + a * ux, y: c1.y + a * uy }
  const p1 = { x: m.x - h * uy, y: m.y + h * ux }
  const p2 = { x: m.x + h * uy, y: m.y - h * ux }
  return Math.hypot(p1.x - p2.x, p1.y - p2.y) <= TOL ? [p1] : [p1, p2]
}

/** True if any two non-adjacent ring edges touch/cross (a bowtie / vertex-on-edge). */
export function selfIntersects(points: Pt[]): boolean {
  const n = points.length
  const edge = (i: number): [Pt, Pt] => [points[i], points[(i + 1) % n]]
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      if (j === i + 1 || (i === 0 && j === n - 1)) continue // adjacent — share a vertex
      const [a, b] = edge(i)
      const [c, d] = edge(j)
      if (segmentsIntersect(a, b, c, d)) return true
    }
  }
  return false
}

/** The first ring vertex whose incoming/outgoing edges are collinear, else null. */
export function collinearVertex(points: Pt[]): Pt | null {
  const n = points.length
  for (let i = 0; i < n; i++) {
    const a = points[(i - 1 + n) % n]
    const b = points[i]
    const c = points[(i + 1) % n]
    const d1x = b.x - a.x
    const d1y = b.y - a.y
    const d2x = c.x - b.x
    const d2y = c.y - b.y
    const n1 = Math.hypot(d1x, d1y)
    const n2 = Math.hypot(d2x, d2y)
    if (n1 <= TOL || n2 <= TOL) continue
    const sinTurn = Math.abs(d1x * d2y - d1y * d2x) / (n1 * n2)
    if (sinTurn <= TOL) return b
  }
  return null
}

function cross(o: Pt, a: Pt, b: Pt): number {
  return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)
}

function onSegment(p: Pt, a: Pt, b: Pt): boolean {
  return (
    Math.min(a.x, b.x) - TOL <= p.x &&
    p.x <= Math.max(a.x, b.x) + TOL &&
    Math.min(a.y, b.y) - TOL <= p.y &&
    p.y <= Math.max(a.y, b.y) + TOL
  )
}

function segmentsIntersect(a: Pt, b: Pt, c: Pt, d: Pt): boolean {
  const d1 = cross(c, d, a)
  const d2 = cross(c, d, b)
  const d3 = cross(a, b, c)
  const d4 = cross(a, b, d)
  if (
    d1 > TOL !== d2 > TOL &&
    d3 > TOL !== d4 > TOL &&
    Math.abs(d1) > TOL &&
    Math.abs(d2) > TOL &&
    Math.abs(d3) > TOL &&
    Math.abs(d4) > TOL
  ) {
    return true
  }
  if (Math.abs(d1) <= TOL && onSegment(a, c, d)) return true
  if (Math.abs(d2) <= TOL && onSegment(b, c, d)) return true
  if (Math.abs(d3) <= TOL && onSegment(c, a, b)) return true
  if (Math.abs(d4) <= TOL && onSegment(d, a, b)) return true
  return false
}
