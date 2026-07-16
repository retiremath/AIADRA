/**
 * SK-C0 mirror fixtures — the TS arcGeometry/classifier mirrors are LOCKED to
 * the same values as the engine's `arc_geometry.py` / Class-1 fixtures
 * (tests/test_c0_palette.py), so the pad's live verdicts match commit verdicts.
 */
import { describe, expect, it } from 'vitest'
import {
  arcGeometry,
  bulgeDomainError,
  bulgeFromThreePoints,
  circularSegmentArea,
  tessellateSegments,
} from './arcGeometry'
import { contourProblem, pointsToSegments, segmentsProblem, type Segment } from './contour'

const B90 = Math.tan(Math.PI / 8)

const L = (x1: number, y1: number, x2: number, y2: number): Segment =>
  ({ kind: 'line', x1_mm: x1, y1_mm: y1, x2_mm: x2, y2_mm: y2 })
const A = (x1: number, y1: number, x2: number, y2: number, b: number): Segment =>
  ({ kind: 'arc', x1_mm: x1, y1_mm: y1, x2_mm: x2, y2_mm: y2, bulge: b })

describe('arcGeometry — engine-locked formulas', () => {
  it('quarter arc (0,0)→(10,10) bulge tan(π/8): r=10, center (10,0), sweep −90°', () => {
    const g = arcGeometry(0, 0, 10, 10, B90)
    expect(g.radius).toBeCloseTo(10, 9)
    expect(g.center.x).toBeCloseTo(10, 9)
    expect(g.center.y).toBeCloseTo(0, 9)
    expect((g.sweep * 180) / Math.PI).toBeCloseTo(-90, 9)
  })

  it('segment area matches the analytic quarter-circle correction', () => {
    const g = arcGeometry(0, 0, 10, 10, B90)
    expect(circularSegmentArea(g)).toBeCloseTo((Math.PI / 4 - 0.5) * 100, 9)
  })

  it('the v1 bulge domain: 0/±1/sub-1e-6/inf reject; ±0.999999 pass', () => {
    for (const bad of [0, 1, -1, 5e-7, Infinity, NaN]) {
      expect(bulgeDomainError(bad)).not.toBeNull()
    }
    expect(bulgeDomainError(0.999999)).toBeNull()
    expect(bulgeDomainError(-0.999999)).toBeNull()
  })

  it('bulgeFromThreePoints round-trips the drawn arc', () => {
    // via = the true arc midpoint of the quarter arc → recovered bulge = tan(π/8)
    const g = arcGeometry(0, 0, 10, 10, B90)
    const mid = g.startAngle + g.sweep / 2
    const via = { x: g.center.x + g.radius * Math.cos(mid), y: g.center.y + g.radius * Math.sin(mid) }
    const b = bulgeFromThreePoints({ x: 0, y: 0 }, via, { x: 10, y: 10 })
    expect(b).not.toBeNull()
    expect(b!).toBeCloseTo(B90, 6)
    // collinear via → no arc
    expect(bulgeFromThreePoints({ x: 0, y: 0 }, { x: 5, y: 5 }, { x: 10, y: 10 })).toBeNull()
  })

  it('tessellation starts at the segment start and ends near the arc end', () => {
    const pts = tessellateSegments([A(0, 0, 10, 10, B90)])
    expect(pts[0]).toEqual({ x: 0, y: 0 })
    expect(pts.length).toBeGreaterThan(4) // a 90° arc needs real facets at 0.05mm
  })
})

describe('segmentsProblem — the curve-aware Class-1 mirror', () => {
  const ROUNDED_L = [L(0, 0, 40, 0), A(40, 0, 50, 10, B90), L(50, 10, 50, 40),
    L(50, 40, 0, 40), L(0, 40, 0, 0)]

  it('accepts the rounded-corner L and the tangent line–arc joint', () => {
    expect(segmentsProblem(ROUNDED_L)).toBeNull()
    expect(segmentsProblem([L(0, 20, 0, 0), A(0, 0, 10, 10, B90), L(10, 10, 10, 20), L(10, 20, 0, 20)])).toBeNull()
  })

  it('accepts the true same-circle barrel (disjoint spans, outward bulge)', () => {
    const c30 = 10 * Math.cos(Math.PI / 6)
    const b60 = -Math.tan(Math.PI / 3 / 4)
    expect(segmentsProblem([
      A(c30, -5, c30, 5, b60), L(c30, 5, -c30, 5),
      A(-c30, 5, -c30, -5, b60), L(-c30, -5, c30, -5),
    ])).toBeNull()
  })

  it('rejects adjacent co-circular arcs (the same-cylinder merge risk)', () => {
    const c30 = 10 * Math.cos(Math.PI / 6)
    const b60 = -Math.tan(Math.PI / 3 / 4)
    expect(segmentsProblem([
      A(c30, -5, c30, 5, b60), A(c30, 5, 0, 10, b60), L(0, 10, c30, -5),
    ])).toMatch(/same circle/)
  })

  it('rejects a tangential graze (touch counts) and a real crossing', () => {
    // top line at the arc apex y=5 exactly → touch; at y=4 → two crossings
    expect(segmentsProblem([A(0, 0, 20, 0, 0.5), L(20, 0, 20, 5), L(20, 5, 0, 5), L(0, 5, 0, 0)])).not.toBeNull()
    expect(segmentsProblem([A(0, 0, 20, 0, 0.5), L(20, 0, 20, 4), L(20, 4, 0, 4), L(0, 4, 0, 0)])).not.toBeNull()
    // the apex-clearing ring is legal
    expect(segmentsProblem([A(0, 0, 20, 0, 0.5), L(20, 0, 20, 6), L(20, 6, 0, 6), L(0, 6, 0, 0)])).toBeNull()
  })

  it('contourProblem(points, bulges) routes through the curve-aware mirror', () => {
    const points = [{ x: 0, y: 0 }, { x: 40, y: 0 }, { x: 40, y: 30 }, { x: 0, y: 30 }]
    expect(contourProblem(points, [0, 0, 0, 0])).toBeNull()
    expect(contourProblem(points, [0.3, 0, 0, 0])).toBeNull() // gentle outward-ish arc
    const segs = pointsToSegments(points, [0.3, 0, 0, 0])
    expect(segs[0].kind).toBe('arc')
    expect(segs[1].kind).toBe('line')
  })
})
