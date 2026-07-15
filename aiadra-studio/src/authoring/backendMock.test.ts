import { describe, it, expect } from 'vitest'
import { createMockAuthoringBackend } from './backendMock'
import {
  buildContourOps,
  chooseBackendLane,
  createUnavailableBackend,
  suggestPartNumber,
  PART_NUMBER_RE,
} from './backend'
import type { Pt } from '../sketch/contour'

const L: Pt[] = [
  { x: 0, y: 0 }, { x: 60, y: 0 }, { x: 60, y: 20 },
  { x: 20, y: 20 }, { x: 20, y: 50 }, { x: 0, y: 50 },
]

describe('mock backend Class-1 defence-in-depth (Codex6 B2)', () => {
  it('simulate REJECTS a contour with a duplicated point (the real engine would too)', async () => {
    const dup = [...L.slice(0, 2), L[1], ...L.slice(2)] // duplicate the second point
    const mock = createMockAuthoringBackend()
    const { sessionId: sid } = await mock.begin(buildContourOps('P-1', 'test', dup, 10))
    const sim = await mock.simulate(sid)
    expect(sim.valid).toBe(false)
    expect(sim.message).toMatch(/duplicate point/)
  })

  it('simulate accepts a valid drawn contour and commit shows ITS geometry', async () => {
    const mock = createMockAuthoringBackend()
    const { sessionId: sid } = await mock.begin(buildContourOps('P-2', 'test', L, 10))
    expect((await mock.simulate(sid)).valid).toBe(true)
    const res = await mock.commit(sid, 'P-2')
    const display = await res.display.getDisplay()
    // 6 segment walls + 2 caps — the drawn L, not a canned box
    expect(display.render.faces).toHaveLength(8)
  })
})

describe('backend lane selection (Codex1 B2 — the desktop NEVER mocks)', () => {
  it('browser dev (no bridge) → the badged mock', () => {
    expect(chooseBackendLane(false, null)).toBe('mock')
    expect(chooseBackendLane(false, 'ws-1')).toBe('mock')
  })

  it('desktop without a workspace → UNAVAILABLE, never the mock', () => {
    expect(chooseBackendLane(true, null)).toBe('unavailable')
  })

  it('desktop with a workspace → the real bridge', () => {
    expect(chooseBackendLane(true, 'ws-1')).toBe('bridge')
  })

  it('the unavailable backend cannot begin (no mock-commit path exists)', async () => {
    const b = createUnavailableBackend()
    expect(b.isReal).toBe(true) // never badged as a dev mock
    await expect(b.begin([{ kind: 'create_part', params: {} }])).rejects.toThrow(
      /No workspace is open/,
    )
  })
})

describe('EP1 — commit-at-New + plane threading through the mock lane', () => {
  it('a create_part-only commit yields the EMPTY display (the dev mirror of A4)', async () => {
    const { buildCreatePartOps } = await import('./backend')
    const mock = createMockAuthoringBackend()
    const { sessionId: sid } = await mock.begin(buildCreatePartOps('P-000123', 'Bracket'))
    expect((await mock.simulate(sid)).valid).toBe(true)
    const res = await mock.commit(sid, 'P-000123')
    const display = await res.display.getDisplay()
    expect(display.render.faces).toHaveLength(0) // emptiness, not a canned box
    expect(display.identity.object_number).toBe('P-000123')
  })

  it('feature ops on an existing Part carry the picked plane into the display orientation', async () => {
    const { buildContourFeatureOps } = await import('./backend')
    const mock = createMockAuthoringBackend()
    const ops = buildContourFeatureOps('P-000123', L, 10, 'yz')
    expect(ops).toHaveLength(2) // NO create_part — features on the ACTIVE Part
    expect(ops[0].params.plane).toEqual({ kind: 'principal', orientation: 'yz' })
    expect(ops[1].params.direction).toBe('normal+') // EP2 canonical vocabulary
    const { sessionId: sid } = await mock.begin(ops)
    const res = await mock.commit(sid, 'P-000123')
    const display = await res.display.getDisplay()
    // The yz frame sweeps along +X: the drawn L (u≤60, v≤50) lands on y/z.
    expect(display.render.bbox_max[0]).toBeCloseTo(10) // the depth, along +X
    expect(display.render.bbox_max[1]).toBeCloseTo(60) // u → +Y
    expect(display.render.bbox_max[2]).toBeCloseTo(50) // v → +Z
  })
})

describe('the fail-closed authoring target (Codex5 B2)', () => {
  it('the REAL lane refuses to sketch without a trustworthy target; the dev lane never does', async () => {
    const { sketchAuthoringGate } = await import('./backend')
    expect(sketchAuthoringGate(true, false)).toMatch(/Create a Part with New/)
    expect(sketchAuthoringGate(true, true)).toBeNull()
    expect(sketchAuthoringGate(false, false)).toBeNull() // the badged dev lane
    expect(sketchAuthoringGate(false, true)).toBeNull()
  })

})

describe('normalizeRectangle (arc 20260715-1 Codex2 N1 — byte-equivalent both lanes)', () => {
  it('all FOUR drag directions produce the SAME semantic record; degenerate dims refuse', async () => {
    const { normalizeRectangle } = await import('./backend')
    const want = { x_mm: 5, y_mm: 10, width_mm: 20, height_mm: 30 }
    expect(normalizeRectangle({ x: 5, y: 10 }, { x: 25, y: 40 })).toEqual(want) // down-right
    expect(normalizeRectangle({ x: 25, y: 10 }, { x: 5, y: 40 })).toEqual(want) // down-left
    expect(normalizeRectangle({ x: 5, y: 40 }, { x: 25, y: 10 })).toEqual(want) // up-right
    expect(normalizeRectangle({ x: 25, y: 40 }, { x: 5, y: 10 })).toEqual(want) // up-left
    expect(normalizeRectangle({ x: 5, y: 10 }, { x: 5, y: 40 })).toBeNull() // zero width
    expect(normalizeRectangle({ x: 5, y: 10 }, { x: 25, y: 10 })).toBeNull() // zero height
  })
})

describe('the RECTANGLE sketch through the mirror and the REAL decoder (R2/D-R9)', () => {
  it('a stepwise rectangle commit decodes with the EXACT simple_rectangle profile', async () => {
    const { buildRectangleSketchOps, buildCreatePartOps } = await import('./backend')
    const { decodeInspectedPart, unconsumedSketches } = await import('./inspectDecode')
    const mock = createMockAuthoringBackend()
    const s1 = await mock.begin(buildCreatePartOps('P-1', 'R'))
    await mock.commit(s1.sessionId, 'P-1')
    const rect = { x_mm: 5, y_mm: 10, width_mm: 20, height_mm: 30 }
    const s2 = await mock.begin(buildRectangleSketchOps('P-1', rect, 'xy'))
    await mock.commit(s2.sessionId, 'P-1')
    const part = decodeInspectedPart(mock.inspectRaw('P-1'))
    const [sk] = unconsumedSketches(part)
    expect(sk.plane).toBe('xy')
    expect(sk.profile).toEqual({ kind: 'simple_rectangle', rectangle: rect })
    expect(sk.rings[0]).toHaveLength(4) // the wire overlay renders it
  })
})

describe('REVOLVE through the mirror and the decoder (R3/D-R9 — mock lathe parity)', () => {
  it('entry A: committed rectangle → revolve → Revolve 1 → Section 1 + a TUBE display', async () => {
    const { buildCreatePartOps, buildRectangleSketchOps, buildRevolveOnSketchOps } = await import('./backend')
    const { decodeInspectedPart, buildTreeRows, unconsumedSketches } = await import('./inspectDecode')
    const mock = createMockAuthoringBackend()
    const s1 = await mock.begin(buildCreatePartOps('P-9', 'W'))
    await mock.commit(s1.sessionId, 'P-9')
    // Offset from the x-axis (y from 10) → a TUBE around X.
    const rect = { x_mm: 0, y_mm: 10, width_mm: 20, height_mm: 5 }
    const s2 = await mock.begin(buildRectangleSketchOps('P-9', rect, 'xy'))
    const sketchId = s2.createdFeatureIds[0][0]
    await mock.commit(s2.sessionId, 'P-9')
    const s3 = await mock.begin(buildRevolveOnSketchOps('P-9', sketchId, 'x'))
    const res = await mock.commit(s3.sessionId, 'P-9')
    const display = await res.display.getDisplay()
    // tube: outer wall + inner wall + two caps
    expect(display.render.faces.map((f) => f.face_id)).toEqual([
      'mock:revolve:outer_wall', 'mock:revolve:inner_wall', 'mock:revolve:cap_lo', 'mock:revolve:cap_hi',
    ])
    const part = decodeInspectedPart(mock.inspectRaw('P-9'))
    expect(buildTreeRows(part).map((r) => r.label)).toEqual(['Revolve 1', 'Section 1'])
    expect(unconsumedSketches(part)).toHaveLength(0)
    expect(part.hasRevolveBase).toBe(true)
  })

  it('the CHAINED one-draft rectangle revolve produces a SOLID when the profile touches the axis', async () => {
    const { buildCreatePartOps, buildRectangleRevolveOps } = await import('./backend')
    const mock = createMockAuthoringBackend()
    const s1 = await mock.begin(buildCreatePartOps('P-8', 'S'))
    await mock.commit(s1.sessionId, 'P-8')
    // y from 0 → touches the x-axis → SOLID (no inner wall).
    const ops = buildRectangleRevolveOps('P-8', { x_mm: 0, y_mm: 0, width_mm: 15, height_mm: 8 }, 'x')
    const s2 = await mock.begin(ops)
    expect(s2.createdFeatureIds).toEqual([[ 'feat_0001' ], ['feat_0002']]) // $fromOp resolved
    const res = await mock.commit(s2.sessionId, 'P-8')
    const display = await res.display.getDisplay()
    expect(display.render.faces.map((f) => f.face_id)).toEqual([
      'mock:revolve:outer_wall', 'mock:revolve:cap_lo', 'mock:revolve:cap_hi',
    ])
  })

  it('the mock one-base mirror refuses a base after a REVOLVE too', async () => {
    const { buildCreatePartOps, buildRectangleRevolveOps, buildSketchOnlyOps, buildExtrudeOnSketchOps } = await import('./backend')
    const mock = createMockAuthoringBackend()
    const s1 = await mock.begin(buildCreatePartOps('P-7', 'B'))
    await mock.commit(s1.sessionId, 'P-7')
    const s2 = await mock.begin(buildRectangleRevolveOps('P-7', { x_mm: 0, y_mm: 2, width_mm: 5, height_mm: 3 }, 'x'))
    await mock.commit(s2.sessionId, 'P-7')
    const s3 = await mock.begin(buildSketchOnlyOps('P-7', L, 'xy'))
    const skId = s3.createdFeatureIds[0][0]
    await mock.commit(s3.sessionId, 'P-7')
    const s4 = await mock.begin(buildExtrudeOnSketchOps('P-7', skId, 5))
    const sim = await mock.simulate(s4.sessionId)
    expect(sim.valid).toBe(false)
    expect(sim.message).toMatch(/one-base/)
  })
})

describe('the mock Truth mirror feeds the REAL decoder (Codex3 B1 fallout)', () => {
  it("Petre's walk in dev:web: sketch-only commit → the decoded sketch is MECHANICAL (wire + selectable + Extrude candidate), then entry A consumes it", async () => {
    const { buildCreatePartOps, buildSketchOnlyOps, buildExtrudeOnSketchOps } = await import('./backend')
    const { decodeInspectedPart, unconsumedSketches, buildTreeRows } = await import('./inspectDecode')
    const mock = createMockAuthoringBackend()
    // New… commits the empty Part.
    const s1 = await mock.begin(buildCreatePartOps('P-867967', 'hdgdt'))
    await mock.commit(s1.sessionId, 'P-867967')
    // Sketch on TOP → OK (the STEPWISE commit).
    const s2 = await mock.begin(buildSketchOnlyOps('P-867967', L, 'zx'))
    const sketchId = s2.createdFeatureIds[0][0]
    await mock.commit(s2.sessionId, 'P-867967')
    // The mirror record must decode as a REAL mechanical sketch — the engine
    // stamp is what makes it a wire, a selectable row, and an Extrude
    // candidate (an unstamped record silently degrades to generic).
    const part = decodeInspectedPart(mock.inspectRaw('P-867967'))
    const candidates = unconsumedSketches(part)
    expect(candidates).toHaveLength(1)
    expect(candidates[0]).toMatchObject({ id: sketchId, plane: 'zx' })
    expect(candidates[0].rings[0].length).toBeGreaterThanOrEqual(3)
    expect(buildTreeRows(part)).toEqual([
      { featureId: sketchId, label: 'Sketch 1', depth: 0, kind: 'sketch' },
    ])
    // Entry A: extrude the committed sketch → Extrude 1 → Section 1.
    const s3 = await mock.begin(buildExtrudeOnSketchOps('P-867967', sketchId, 12))
    await mock.commit(s3.sessionId, 'P-867967')
    const after = decodeInspectedPart(mock.inspectRaw('P-867967'))
    expect(unconsumedSketches(after)).toHaveLength(0)
    expect(buildTreeRows(after).map((r) => r.label)).toEqual(['Extrude 1', 'Section 1'])
  })
})

describe('the mock mirror of the id handshake (S2 Codex1 B1 — same loud rules)', () => {
  it('mints per-op ids (one per mechanical.add_*, none for create_part) and resolves $fromOp', async () => {
    const mock = createMockAuthoringBackend()
    const { createdFeatureIds } = await mock.begin(buildContourOps('P-9', 'test', L, 10))
    expect(createdFeatureIds).toEqual([[], ['feat_0001'], ['feat_0002']])
  })

  it('rejects a $fromOp referencing an op that minted nothing — same rule as the bridge', async () => {
    const { opRef } = await import('./backend')
    const mock = createMockAuthoringBackend()
    await expect(
      mock.begin([
        { kind: 'create_part', params: { number: 'P-9', name: 't' } },
        { kind: 'mechanical.add_extrude_feature', params: { sketch_feature_id: opRef(0) } },
      ]),
    ).rejects.toThrow(/created 0 features/)
  })

  it('rejects a MALFORMED alias (extra keys) instead of persisting it as a value', async () => {
    const mock = createMockAuthoringBackend()
    await expect(
      mock.begin([
        { kind: 'mechanical.add_sketch_feature', params: { primitives: [] } },
        {
          kind: 'mechanical.add_extrude_feature',
          params: { sketch_feature_id: { $fromOp: 0, oops: true } },
        },
      ]),
    ).rejects.toThrow(/malformed \$fromOp/)
  })
})

describe('provisional part numbers (Codex2 B2)', () => {
  it('suggestions are well-formed P-NNNNNN across the whole random range', () => {
    expect(suggestPartNumber(() => 0)).toBe('P-000000')
    expect(suggestPartNumber(() => 0.9999999)).toBe('P-999999')
    expect(PART_NUMBER_RE.test(suggestPartNumber())).toBe(true)
  })

  it('the format gate rejects non-canonical numbers', () => {
    for (const bad of ['P-12345', 'P-1234567', 'X-123456', 'p-123456', '123456', 'P-12A456']) {
      expect(PART_NUMBER_RE.test(bad)).toBe(false)
    }
  })
})
