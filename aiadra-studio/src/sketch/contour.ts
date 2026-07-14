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
export interface Pt {
  x: number
  y: number
}

export type LineSegment = { kind: 'line'; x1_mm: number; y1_mm: number; x2_mm: number; y2_mm: number }

const TOL = 1e-6

/** Ring of points → the engine's closed-ring line segments (the closer included). */
export function pointsToSegments(points: Pt[]): LineSegment[] {
  const n = points.length
  return points.map((p, i) => {
    const q = points[(i + 1) % n]
    return { kind: 'line', x1_mm: p.x, y1_mm: p.y, x2_mm: q.x, y2_mm: q.y }
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

/** The first client-visible reason this ring is not a valid profile, else null. */
export function contourProblem(points: Pt[]): string | null {
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
  if (Math.abs(signedArea(points)) <= TOL) return 'The contour encloses no area.'
  if (selfIntersects(points)) return 'The contour crosses itself — make it a simple loop.'
  if (collinearVertex(points) !== null) return 'Remove the redundant point (three points in a line).'
  return null
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
