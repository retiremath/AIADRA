import { describe, it, expect } from 'vitest'
import { buildCircle, buildPolyline, buildRectangle, mergeProfiles } from './profileBuilder'
import { isDrag, proposeAxisFact } from './snapProposal'
import { profileError } from '../../electron/authoringParamRules'

const OP = 'test'

describe('snap PROPOSALS (ADR/0045 D6 — Studio proposes, the engine moves geometry)', () => {
  const a = { u: 0, v: 0 }

  it('a nearly level segment proposes horizontal', () => {
    expect(proposeAxisFact(a, { u: 20, v: 0.4 }, 3)).toBe('horizontal')
  })

  it('a nearly plumb segment proposes vertical', () => {
    expect(proposeAxisFact(a, { u: 0.4, v: 20 }, 3)).toBe('vertical')
  })

  it('a clearly diagonal segment proposes nothing', () => {
    expect(proposeAxisFact(a, { u: 20, v: 20 }, 3)).toBeNull()
  })

  it('an exactly diagonal segment proposes nothing even at a huge tolerance', () => {
    // At 45° a line is equidistant from both axes; picking one would be
    // arbitrary, and asserting both would collapse the segment.
    expect(proposeAxisFact(a, { u: 10, v: 10 }, 44.9)).toBeNull()
  })

  it('a zero tolerance disables snapping outright', () => {
    expect(proposeAxisFact(a, { u: 20, v: 0 }, 0)).toBeNull()
  })

  it('direction never matters — the axes are symmetric', () => {
    for (const b of [
      { u: -20, v: 0.4 },
      { u: 20, v: -0.4 },
      { u: -20, v: -0.4 },
    ]) {
      expect(proposeAxisFact(a, b, 3)).toBe('horizontal')
    }
  })

  it('a zero-length segment proposes nothing', () => {
    expect(proposeAxisFact(a, { u: 0, v: 0 }, 3)).toBeNull()
  })

  it('minDragPx is a SCREEN threshold, never the solver L_min_mm', () => {
    expect(isDrag(3, 0, 4)).toBe(false)
    expect(isDrag(3, 3, 4)).toBe(true)
  })
})

describe('the tools are UI sugar over ONE fact graph (G-AI)', () => {
  it('a drawn line is two points, one segment, and a proposed fact', () => {
    const p = buildPolyline([{ u: 0, v: 0 }, { u: 20, v: 0.4 }], {
      snapAngleToleranceDeg: 3,
    })
    expect(p.points).toHaveLength(2)
    expect(p.segments).toHaveLength(1)
    expect(p.facts).toEqual([{ key: 'f1', kind: 'horizontal', target: { key: 's1' } }])
    // the DRAWN coordinates travel untouched — Studio never levels them
    expect(p.points?.[1]).toMatchObject({ x: 20, y: 0.4 })
  })

  it('a diagonal line carries no facts at all', () => {
    const p = buildPolyline([{ u: 0, v: 0 }, { u: 20, v: 20 }], {
      snapAngleToleranceDeg: 3,
    })
    expect(p.facts).toBeUndefined()
  })

  it('a polyline snaps each segment independently', () => {
    const p = buildPolyline(
      [{ u: 0, v: 0 }, { u: 20, v: 0.2 }, { u: 25, v: 15 }, { u: 25.1, v: 30 }],
      { snapAngleToleranceDeg: 3 },
    )
    expect(p.segments).toHaveLength(3)
    expect(p.facts?.map((f) => f.kind)).toEqual(['horizontal', 'vertical'])
  })

  it('a closed run adds the return segment', () => {
    const p = buildPolyline(
      [{ u: 0, v: 0 }, { u: 20, v: 0 }, { u: 10, v: 15 }],
      { snapAngleToleranceDeg: 3, closed: true },
    )
    expect(p.segments).toHaveLength(3)
    expect(p.segments?.[2]).toMatchObject({ start: { key: 'p3' }, end: { key: 'p1' } })
  })

  it('a rectangle is four points, four segments and four ASSERTED facts', () => {
    const p = buildRectangle({ u: 0, v: 0 }, { u: 30, v: 12 })
    expect(p.points).toHaveLength(4)
    expect(p.segments).toHaveLength(4)
    // asserted regardless of tolerance: the tool IS the intent
    expect(p.facts?.map((f) => f.kind)).toEqual([
      'horizontal', 'vertical', 'horizontal', 'vertical',
    ])
  })

  it('rectangle corners are ordered so consecutive ones share an axis', () => {
    const p = buildRectangle({ u: 1, v: 2 }, { u: 31, v: 14 })
    expect(p.points?.map((q) => [q.x, q.y])).toEqual([
      [1, 2], [31, 2], [31, 14], [1, 14],
    ])
  })

  it('a rectangle drawn from any opposite corner pair is still a rectangle', () => {
    const p = buildRectangle({ u: 31, v: 14 }, { u: 1, v: 2 })
    expect(p.facts).toHaveLength(4)
    expect(profileError(OP, p)).toBeNull()
  })

  it('a degenerate rectangle drag throws rather than emitting a collapsed graph', () => {
    expect(() => buildRectangle({ u: 0, v: 0 }, { u: 0, v: 12 })).toThrow(/non-degenerate/)
  })

  it('a circle is a centre point plus a radius', () => {
    const p = buildCircle({ u: 5, v: 5 }, { u: 8, v: 9 })
    expect(p.points).toHaveLength(1)
    expect(p.circles?.[0].radius_mm).toBeCloseTo(5, 12)
    expect(p.segments).toBeUndefined()
  })

  it('a zero-radius circle throws', () => {
    expect(() => buildCircle({ u: 5, v: 5 }, { u: 5, v: 5 })).toThrow(/non-zero radius/)
  })
})

describe('every tool output passes the SAME wire boundary the commit goes through', () => {
  it.each([
    ['line', buildPolyline([{ u: 0, v: 0 }, { u: 20, v: 0.4 }], { snapAngleToleranceDeg: 3 })],
    ['diagonal line', buildPolyline([{ u: 0, v: 0 }, { u: 9, v: 20 }], { snapAngleToleranceDeg: 3 })],
    ['polyline', buildPolyline([{ u: 0, v: 0 }, { u: 20, v: 0.2 }, { u: 25, v: 15 }], { snapAngleToleranceDeg: 3 })],
    ['closed triangle', buildPolyline([{ u: 0, v: 0 }, { u: 20, v: 0 }, { u: 10, v: 15 }], { snapAngleToleranceDeg: 3, closed: true })],
    ['rectangle', buildRectangle({ u: 0, v: 0 }, { u: 30, v: 12 })],
    ['circle', buildCircle({ u: 5, v: 5 }, { u: 8, v: 9 })],
  ])('%s', (_label, payload) => {
    expect(profileError(OP, payload)).toBeNull()
  })
})

describe('merging drawn parts into ONE sketch', () => {
  it('a rectangle and a circle become one graph with unique keys', () => {
    const merged = mergeProfiles([
      buildRectangle({ u: 0, v: 0 }, { u: 30, v: 12 }),
      buildCircle({ u: 15, v: 6 }, { u: 18, v: 6 }),
    ])
    expect(merged.points).toHaveLength(5)
    expect(merged.segments).toHaveLength(4)
    expect(merged.circles).toHaveLength(1)
    const keys = [
      ...(merged.points ?? []),
      ...(merged.segments ?? []),
      ...(merged.circles ?? []),
      ...(merged.facts ?? []),
    ].map((r) => (r as { key: string }).key)
    expect(new Set(keys).size).toBe(keys.length)
    expect(profileError(OP, merged)).toBeNull()
  })

  it('references are re-pointed at the re-keyed records, never left dangling', () => {
    const merged = mergeProfiles([
      buildPolyline([{ u: 0, v: 0 }, { u: 20, v: 0.4 }], { snapAngleToleranceDeg: 3 }),
      buildPolyline([{ u: 40, v: 0 }, { u: 60, v: 0.4 }], { snapAngleToleranceDeg: 3 }),
    ])
    const pointKeys = new Set((merged.points ?? []).map((p) => (p as { key: string }).key))
    for (const s of merged.segments ?? []) {
      expect(pointKeys.has((s.start as { key: string }).key)).toBe(true)
      expect(pointKeys.has((s.end as { key: string }).key)).toBe(true)
    }
    const segKeys = new Set((merged.segments ?? []).map((s) => (s as { key: string }).key))
    for (const f of merged.facts ?? []) {
      expect(segKeys.has((f.target as { key: string }).key)).toBe(true)
    }
  })

  it('committed ids are refused — merging composes freshly drawn parts only', () => {
    expect(() =>
      mergeProfiles([{ points: [{ id: 'skp_0006', x: 0, y: 0 }] }]),
    ).toThrow(/committed ids/)
  })
})
