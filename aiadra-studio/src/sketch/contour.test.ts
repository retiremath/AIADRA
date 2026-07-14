import { describe, it, expect } from 'vitest'
import {
  pointsToSegments,
  signedArea,
  contourProblem,
  selfIntersects,
  collinearVertex,
  type Pt,
} from './contour'

const L: Pt[] = [
  { x: 0, y: 0 }, { x: 60, y: 0 }, { x: 60, y: 20 },
  { x: 20, y: 20 }, { x: 20, y: 50 }, { x: 0, y: 50 },
]

describe('contour geometry', () => {
  it('turns a ring into closed line segments (the closer included)', () => {
    const segs = pointsToSegments(L)
    expect(segs).toHaveLength(6)
    // last segment closes back to the first point
    expect(segs[5]).toMatchObject({ x2_mm: 0, y2_mm: 0, x1_mm: 0, y1_mm: 50 })
    expect(segs.every((s) => s.kind === 'line')).toBe(true)
  })

  it('computes signed area (a 60×40 rectangle = 2400)', () => {
    const rect: Pt[] = [{ x: 0, y: 0 }, { x: 60, y: 0 }, { x: 60, y: 40 }, { x: 0, y: 40 }]
    expect(signedArea(rect)).toBeCloseTo(2400)
  })

  it('accepts a valid concave L (no problem)', () => {
    expect(contourProblem(L)).toBeNull()
  })

  it('rejects fewer than 3 points', () => {
    expect(contourProblem([{ x: 0, y: 0 }, { x: 10, y: 0 }])).not.toBeNull()
  })

  it('flags a self-intersecting bowtie', () => {
    const bowtie: Pt[] = [{ x: 0, y: 0 }, { x: 10, y: 10 }, { x: 10, y: 0 }, { x: 0, y: 10 }]
    expect(selfIntersects(bowtie)).toBe(true)
    expect(contourProblem(bowtie)).not.toBeNull()
  })

  it('flags a collinear (redundant) vertex', () => {
    const redundant: Pt[] = [{ x: 0, y: 0 }, { x: 30, y: 0 }, { x: 60, y: 0 }, { x: 60, y: 40 }, { x: 0, y: 40 }]
    expect(collinearVertex(redundant)).not.toBeNull()
    expect(contourProblem(redundant)).not.toBeNull()
  })

  it('a clean L turns at every vertex + is a simple loop', () => {
    expect(collinearVertex(L)).toBeNull()
    expect(selfIntersects(L)).toBe(false)
  })

  // Codex6 B2 — exact engine parity on zero-length segments: collinearVertex
  // deliberately skips zero-length edges, so duplicates need their own check.
  it('rejects a duplicated MIDDLE point (zero-length segment)', () => {
    const dup: Pt[] = [{ x: 0, y: 0 }, { x: 60, y: 0 }, { x: 60, y: 0 }, { x: 60, y: 40 }, { x: 0, y: 40 }]
    expect(contourProblem(dup)).toMatch(/duplicate point/)
  })

  it('rejects a duplicated CLOSING point (last equals first — a zero-length closer)', () => {
    const dup: Pt[] = [{ x: 0, y: 0 }, { x: 60, y: 0 }, { x: 60, y: 40 }, { x: 0, y: 40 }, { x: 0, y: 0 }]
    expect(contourProblem(dup)).toMatch(/duplicate point/)
  })
})
