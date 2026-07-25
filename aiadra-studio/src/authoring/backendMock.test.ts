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

describe('the FOLDED-recipe display (SK-C1.0 Codex5 B1.2)', () => {
  it('a sketch-only commit onto a BASED Part keeps the body (never emptiness)', async () => {
    const mock = createMockAuthoringBackend()
    // the REAL stepwise flow (and the acceptance runner's): commit the
    // rectangle sketch alone, then extrude it entry-A in a second commit
    const s0 = await mock.begin([
      { kind: 'create_part', params: { number: 'P-9', name: 'Box' } },
      { kind: 'mechanical.add_sketch_feature', params: {
        part_number: 'P-9', plane: { kind: 'principal', orientation: 'xy' },
        primitives: [{ type: 'rectangle', x_mm: 0, y_mm: 0, width_mm: 30, height_mm: 20 }] } },
    ])
    await mock.commit(s0.sessionId, 'P-9')
    const s1 = await mock.begin([
      { kind: 'mechanical.add_extrude_feature', params: {
        part_number: 'P-9', sketch_feature_id: 'feat_0001', depth_mm: 10, direction: 'normal+' } },
    ])
    const r1 = await mock.commit(s1.sessionId, 'P-9')
    const d1 = await r1.display.getDisplay()
    expect(d1.render.faces.some((f) => f.face_id.includes('wall_'))).toBe(true) // the body exists
    // commit 2: a LATER sketch-only feature — the display must come from the
    // WHOLE folded recipe, not the current delta (which has no base op)
    const s2 = await mock.begin([
      { kind: 'mechanical.add_sketch_feature', params: {
        part_number: 'P-9', plane: { kind: 'principal', orientation: 'yz' },
        primitives: [{ type: 'contour', segments: [
          { kind: 'line', x1_mm: 0, y1_mm: 0, x2_mm: 10, y2_mm: 0 },
          { kind: 'line', x1_mm: 10, y1_mm: 0, x2_mm: 10, y2_mm: 10 },
          { kind: 'line', x1_mm: 10, y1_mm: 10, x2_mm: 0, y2_mm: 0 },
        ] }] } },
    ])
    const r2 = await mock.commit(s2.sessionId, 'P-9')
    const d2 = await r2.display.getDisplay()
    expect(d2.render.faces.some((f) => f.face_id.includes('wall_'))).toBe(true) // the BODY SURVIVED
    // …and the new sketch wire derives from the UPDATED recipe (the mirror)
    const raw = mock.inspectRaw('P-9') as { sidecar: { feature: Array<{ feature_type: string }> } }
    expect(raw.sidecar.feature.filter((f) => f.feature_type === 'sketch')).toHaveLength(2)
  })

  it('a sketch-only commit on a base-LESS Part still shows honest emptiness', async () => {
    const mock = createMockAuthoringBackend()
    const s1 = await mock.begin([
      { kind: 'create_part', params: { number: 'P-8', name: 'Sketchy' } },
      { kind: 'mechanical.add_sketch_feature', params: {
        part_number: 'P-8', plane: { kind: 'principal', orientation: 'xy' },
        primitives: [{ type: 'rectangle', x_mm: 0, y_mm: 0, width_mm: 5, height_mm: 5 }] } },
    ])
    const r1 = await mock.commit(s1.sessionId, 'P-8')
    const d1 = await r1.display.getDisplay()
    expect(d1.render.faces).toHaveLength(0) // no base → honest emptiness
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
    expect(sk.plane).toEqual({ kind: 'principal', orientation: 'xy' })
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

  it('a sequential extrude after a REVOLVE refuses (the engine mirror)', async () => {
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
    // P (arc 20260717-2): the one-base wording is retired — the refusal is
    // now the SEQUENTIAL domain mirror (a datum-bound profile cannot chain).
    expect(sim.message).toMatch(/FACE-BOUND|revolve/)
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
    expect(candidates[0]).toMatchObject({ id: sketchId, plane: { kind: 'principal', orientation: 'zx' } })
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

describe('S3 — face-bound sketches + the depth-edit RIDE through the mock mirror', () => {
  /** The standard S3 fixture: P-30 with a 30x20 xy rectangle extruded 10. */
  const buildBox = async (mock: ReturnType<typeof createMockAuthoringBackend>) => {
    const s0 = await mock.begin([
      { kind: 'create_part', params: { number: 'P-30', name: 'S3 Box' } },
      { kind: 'mechanical.add_sketch_feature', params: {
        part_number: 'P-30', plane: { kind: 'principal', orientation: 'xy' },
        primitives: [{ type: 'rectangle', x_mm: 0, y_mm: 0, width_mm: 30, height_mm: 20 }] } },
    ])
    await mock.commit(s0.sessionId, 'P-30')
    const s1 = await mock.begin([
      { kind: 'mechanical.add_extrude_feature', params: {
        part_number: 'P-30', sketch_feature_id: 'feat_0001', depth_mm: 10, direction: 'normal+' } },
    ])
    await mock.commit(s1.sessionId, 'P-30')
  }
  const faceSketchOps = [
    { kind: 'mechanical.add_sketch_feature', params: {
      part_number: 'P-30', plane: { kind: 'face', target_face_id: 'mock:cap_top' },
      primitives: [{ type: 'contour', segments: [
        { kind: 'line', x1_mm: 5, y1_mm: 5, x2_mm: 15, y2_mm: 5 },
        { kind: 'line', x1_mm: 15, y1_mm: 5, x2_mm: 10, y2_mm: 12 },
        { kind: 'line', x1_mm: 10, y1_mm: 12, x2_mm: 5, y2_mm: 5 },
      ] }] } },
  ]

  it('a cap face input translates to the ENGINE record shape and emits its v1.2 frame', async () => {
    const mock = createMockAuthoringBackend()
    await buildBox(mock)
    const s2 = await mock.begin(faceSketchOps)
    expect((await mock.simulate(s2.sessionId)).valid).toBe(true)
    const res = await mock.commit(s2.sessionId, 'P-30')
    // the committed record carries the engine's stored face shape VERBATIM
    const raw = mock.inspectRaw('P-30') as { sidecar: { feature: Array<Record<string, unknown>> } }
    const sk = raw.sidecar.feature.find((f) => f.id === 'feat_0003')!
    expect((sk.adapter_payload as Record<string, unknown>).plane).toEqual({
      kind: 'face',
      face_role: 'feat_0002:face:cap_top',
      resolved_against_topology_signature: 'mock-topo',
    })
    // Display v1.2: every mock face honestly planar + the sketch frame ON the cap
    const d = (await res.display.getDisplay()) as unknown as Record<string, unknown>
    const faces = (d.render as { faces: Array<{ surface_kind?: string }> }).faces
    expect(faces.length).toBeGreaterThan(0)
    expect(faces.every((f) => f.surface_kind === 'plane')).toBe(true)
    const frames = d.sketch_frames as Array<Record<string, unknown>>
    expect(frames).toHaveLength(1)
    expect(frames[0]).toEqual({
      sketch_feature_id: 'feat_0003',
      origin_mm: [0, 0, 10],
      u_axis: [1, 0, 0],
      v_axis: [0, 1, 0],
      normal: [0, 0, 1],
    })
  })

  it('a WALL face input refuses loudly (the mock has no topology extraction)', async () => {
    const mock = createMockAuthoringBackend()
    await buildBox(mock)
    await expect(
      mock.begin([{ kind: 'mechanical.add_sketch_feature', params: {
        part_number: 'P-30', plane: { kind: 'face', target_face_id: 'mock:wall_0' },
        primitives: [] } }]),
    ).rejects.toThrow(/caps only/)
  })

  it('THE RIDE: adjusting the base depth regenerates the folded body AND the frame', async () => {
    const mock = createMockAuthoringBackend()
    await buildBox(mock)
    const s2 = await mock.begin(faceSketchOps)
    await mock.commit(s2.sessionId, 'P-30')
    const s3 = await mock.begin([
      { kind: 'mechanical.adjust_feature_parameter', params: {
        part_number: 'P-30', feature_id: 'feat_0002', parameter_name: 'depth_mm', new_value: 25 } },
    ])
    expect((await mock.simulate(s3.sessionId)).valid).toBe(true)
    const res = await mock.commit(s3.sessionId, 'P-30')
    const d = (await res.display.getDisplay()) as unknown as Record<string, unknown>
    // the FOLDED body regenerated at 25 (the depth authority is the mirror's
    // parameters catalogue — the payload never carried depth_mm)
    const faces = (d.render as { faces: Array<{ face_id: string; positions: number[] }> }).faces
    const cap = faces.find((f) => f.face_id === 'mock:cap_top')!
    for (let i = 2; i < cap.positions.length; i += 3) expect(cap.positions[i]).toBe(25)
    // ...and the face-bound sketch frame RIDES the moved cap
    const frames = d.sketch_frames as Array<Record<string, unknown>>
    expect(frames[0].origin_mm).toEqual([0, 0, 25])
    // the mirror parameter itself persisted (the catalogue reopens at 25)
    const raw = mock.inspectRaw('P-30') as { sidecar: { feature: Array<Record<string, unknown>> } }
    const ext = raw.sidecar.feature.find((f) => f.id === 'feat_0002')!
    expect((ext.parameters as Array<{ name: string; value: unknown }>).find((p) => p.name === 'depth_mm')!.value).toBe(25)
  })

  it('an adjust op naming an unknown parameter is INVALID at simulate (never a silent commit)', async () => {
    const mock = createMockAuthoringBackend()
    await buildBox(mock)
    const s = await mock.begin([
      { kind: 'mechanical.adjust_feature_parameter', params: {
        part_number: 'P-30', feature_id: 'feat_0002', parameter_name: 'girth_mm', new_value: 1 } },
    ])
    const sim = await mock.simulate(s.sessionId)
    expect(sim.valid).toBe(false)
    expect(sim.message).toMatch(/unknown feature\/parameter/)
  })
})

describe('Codex14 — the real sequential graph shape + mock honesty', () => {
  const boxOps = (n: string) => [
    { kind: 'create_part', params: { number: n, name: 'Seq' } },
    { kind: 'mechanical.add_sketch_feature', params: {
      part_number: n, plane: { kind: 'principal', orientation: 'xy' },
      primitives: [{ type: 'rectangle', x_mm: 0, y_mm: 0, width_mm: 40, height_mm: 25 }] } },
  ]
  const build = async (mock: ReturnType<typeof createMockAuthoringBackend>, n = 'P-40') => {
    const s0 = await mock.begin(boxOps(n))
    await mock.commit(s0.sessionId, n)
    const s1 = await mock.begin([{ kind: 'mechanical.add_extrude_feature', params: {
      part_number: n, sketch_feature_id: 'feat_0001', depth_mm: 10, direction: 'normal+' } }])
    await mock.commit(s1.sessionId, n)
    const s2 = await mock.begin([{ kind: 'mechanical.add_sketch_feature', params: {
      part_number: n, plane: { kind: 'face', target_face_id: 'mock:cap_top' },
      primitives: [{ type: 'rectangle', x_mm: 10, y_mm: 8, width_mm: 10, height_mm: 8 }] } }])
    await mock.commit(s2.sessionId, n)
  }

  it('B1.4: a sequential extrude authors [sketch, prior_body_head] at 0.1.11', async () => {
    const mock = createMockAuthoringBackend()
    await build(mock)
    const s3 = await mock.begin([{ kind: 'mechanical.add_extrude_feature', params: {
      part_number: 'P-40', sketch_feature_id: 'feat_0003', depth_mm: 6,
      direction: 'normal+', operation: 'add' } }])
    expect((await mock.simulate(s3.sessionId)).valid).toBe(true)
    await mock.commit(s3.sessionId, 'P-40')
    const raw = mock.inspectRaw('P-40') as { sidecar: { feature: Array<Record<string, unknown>> } }
    const boss = raw.sidecar.feature.find((f) => f.id === 'feat_0004')!
    expect(boss.depends_on_feature_ids).toEqual(['feat_0003', 'feat_0002'])
    expect(boss.adapter_schema_version).toBe('0.1.11')
    // ...and the REAL decoder accepts the sequential graph shape
    const { decodeInspectedPart } = await import('./inspectDecode')
    const part = decodeInspectedPart(raw)
    const seq = part.features.find((f) => f.id === 'feat_0004')
    expect(seq?.kind === 'extrude' && seq.consumesSketchId).toBe('feat_0003')
  })

  it('B1.5: the decoder reads the NAMED operand — dependency order never decides', async () => {
    const { decodeInspectedPart } = await import('./inspectDecode')
    const raw = {
      object_number: 'P-X', object_type: 'Part',
      sidecar: { object: { type: 'Part', number: 'P-X', name: 'X', uuid: 'u' }, feature: [
        { id: 'feat_0001', feature_type: 'sketch', engine: 'mechanical',
          adapter_schema_version: '0.1.11',
          adapter_payload: { primitives: [{ id: 'skp_0001', type: 'rectangle',
            x_mm: 0, y_mm: 0, width_mm: 40, height_mm: 25 }] } },
        { id: 'feat_0002', feature_type: 'extrude', engine: 'mechanical',
          adapter_schema_version: '0.1.11',
          depends_on_feature_ids: ['feat_0001'],
          parameters: [{ id: 'featp_0001', name: 'depth_mm', value: 10, datatype: 'number', unit: 'mm' }],
          adapter_payload: { sketch_feature_id: 'feat_0001', direction: 'normal+', operation: 'add' } },
        { id: 'feat_0003', feature_type: 'sketch', engine: 'mechanical',
          adapter_schema_version: '0.1.11',
          depends_on_feature_ids: ['feat_0002'],
          adapter_payload: { plane: { kind: 'face', face_role: 'feat_0002:face:cap_top',
            resolved_against_topology_signature: 'topo_x' },
            primitives: [{ id: 'skp_0001', type: 'rectangle', x_mm: 10, y_mm: 8, width_mm: 10, height_mm: 8 }] } },
        // the HEAD edge FIRST — position must not matter
        { id: 'feat_0004', feature_type: 'extrude', engine: 'mechanical',
          adapter_schema_version: '0.1.11',
          depends_on_feature_ids: ['feat_0002', 'feat_0003'],
          parameters: [{ id: 'featp_0002', name: 'depth_mm', value: 6, datatype: 'number', unit: 'mm' }],
          adapter_payload: { sketch_feature_id: 'feat_0003', direction: 'normal-', operation: 'cut' } },
      ] },
    }
    const part = decodeInspectedPart(raw as never)
    const cut = part.features.find((f) => f.id === 'feat_0004')
    expect(cut?.kind === 'extrude' && cut.consumesSketchId).toBe('feat_0003')
  })

  it('B2: terminal eligibility derives from the LIVE part — a consumed sketch refuses', async () => {
    const { decodeInspectedPart, eligibleExtrudeSketchIds } = await import('./inspectDecode')
    const mock = createMockAuthoringBackend()
    await build(mock, 'P-41')
    const before = decodeInspectedPart(mock.inspectRaw('P-41') as never)
    expect(eligibleExtrudeSketchIds(before).has('feat_0003')).toBe(true)
    // the race: the sketch is consumed between render and click
    const s3 = await mock.begin([{ kind: 'mechanical.add_extrude_feature', params: {
      part_number: 'P-41', sketch_feature_id: 'feat_0003', depth_mm: 6,
      direction: 'normal+', operation: 'add' } }])
    await mock.commit(s3.sessionId, 'P-41')
    const after = decodeInspectedPart(mock.inspectRaw('P-41') as never)
    // the ONE derivation, applied to the LIVE state, refuses the stale id
    expect(eligibleExtrudeSketchIds(after).has('feat_0003')).toBe(false)
  })

  it('B3: boss-on-boss REACHES the honest real-lane refusal (never a misplaced prism)', async () => {
    const mock = createMockAuthoringBackend()
    await build(mock, 'P-42')
    const s3 = await mock.begin([{ kind: 'mechanical.add_extrude_feature', params: {
      part_number: 'P-42', sketch_feature_id: 'feat_0003', depth_mm: 6,
      direction: 'normal+', operation: 'add' } }])
    await mock.commit(s3.sessionId, 'P-42')  // the boss (feat_0004)
    // a sketch on the BOSS's own cap (the composite display id mockb_...)
    const s4 = await mock.begin([{ kind: 'mechanical.add_sketch_feature', params: {
      part_number: 'P-42', plane: { kind: 'face', target_face_id: 'mockb_feat_0004:cap_top' },
      primitives: [{ type: 'rectangle', x_mm: 12, y_mm: 10, width_mm: 4, height_mm: 3 }] } }])
    await mock.commit(s4.sessionId, 'P-42')  // the sketch itself commits fine
    const s5 = await mock.begin([{ kind: 'mechanical.add_extrude_feature', params: {
      part_number: 'P-42', sketch_feature_id: 'feat_0005', depth_mm: 3,
      direction: 'normal+', operation: 'add' } }])
    const sim = await mock.simulate(s5.sessionId)
    expect(sim.valid).toBe(false)
    expect(sim.message).toMatch(/BASE top cap only.*desktop app|real engine lane/)
  })
})

describe('the mock references domain — the REAL writer’s language (Codex27 B1)', () => {
  const REF = (params: Record<string, unknown>) => [
    { kind: 'create_part', params: { number: 'P-77', name: 'Ref' } },
    { kind: 'mechanical.add_reference_sketch', params: { part_number: 'P-77', ...params } },
  ]

  it('omitted optionals take the engine defaults (G2, 20mm, xy)', async () => {
    const mock = createMockAuthoringBackend()
    const s = await mock.begin(REF({}))
    const res = await mock.commit(s.sessionId, 'P-77')
    const d = (await res.display.getDisplay()) as unknown as {
      v2_construction?: Array<{ shape: string; points: Array<{ id: string; at: number[] }> }>
    }
    expect(d.v2_construction?.[0].shape).toBe('G2')
  })

  it.each([
    ['explicit null axes', { axes: null }],
    ['unknown axes', { axes: 'diagonal' }],
    ['explicit null length', { x_axis_mm: null }],
    ['non-finite length', { y_axis_mm: Infinity }],
    ['boolean length', { x_axis_mm: true }],
    ['explicit null plane', { plane: null }],
    ['face plane', { plane: { kind: 'face', target_face_id: 'f' } }],
    ['extra-key principal plane', { plane: { kind: 'principal', orientation: 'xy', extra: 1 } }],
    ['unknown orientation', { plane: { kind: 'principal', orientation: 'ab' } }],
  ])('%s REFUSES — absence is not null; nothing collapses into a valid graph', async (_l, params) => {
    const mock = createMockAuthoringBackend()
    await expect(mock.begin(REF(params))).rejects.toThrow(/add_reference_sketch/)
  })

  it.each([
    ['xy', [20, 0, 0], [0, 20, 0]],
    ['yz', [0, 20, 0], [0, 0, 20]],
    ['zx', [0, 0, 20], [20, 0, 0]],
  ])('display maps (u,v) → world by ORIENTATION %s (the engine _FRAME_AXES table)', async (ori, px, py) => {
    const mock = createMockAuthoringBackend()
    const s = await mock.begin(REF({ plane: { kind: 'principal', orientation: ori } }))
    const res = await mock.commit(s.sessionId, 'P-77')
    const d = (await res.display.getDisplay()) as unknown as {
      v2_construction?: Array<{ points: Array<{ id: string; at: number[] }> }>
    }
    const pts = new Map(d.v2_construction?.[0].points.map((p) => [p.id, p.at]))
    expect(pts.get('skp_0002')).toEqual(px)
    expect(pts.get('skp_0003')).toEqual(py)
  })
})

describe('the mock placement lane (ADR/0044 A3; pass sketch-place-1)', () => {
  const REF = (params: Record<string, unknown>) => [
    { kind: 'create_part', params: { number: 'P-88', name: 'Placed' } },
    { kind: 'mechanical.add_reference_sketch', params: { part_number: 'P-88', ...params } },
  ]
  const getV2 = async (mock: ReturnType<typeof createMockAuthoringBackend>, sid: string) => {
    const res = await mock.commit(sid, 'P-88')
    return (await res.display.getDisplay()) as unknown as {
      v2_construction?: Array<{ points: Array<{ id: string; at: number[] }> }>
    }
  }

  it('placement selects the 0.2.1 writer with the A3.3 defaults completed', async () => {
    const mock = createMockAuthoringBackend()
    const s = await mock.begin(REF({ placement: { support: { kind: 'principal', orientation: 'xy' } } }))
    await getV2(mock, s.sessionId)
    const raw = mock.inspectRaw('P-88') as { sidecar: { feature: Array<{ adapter_schema_version?: string; adapter_payload?: Record<string, unknown> }> } }
    const sk = raw.sidecar.feature.find((f) => f.adapter_schema_version === '0.2.1')!
    expect(sk.adapter_payload!.placement).toEqual({
      support: { kind: 'principal', orientation: 'xy' },
      orientation_ref: { kind: 'principal', orientation: 'yz' },
      orientation: 'right',
      normal_side: 'positive',
    })
    expect(sk.adapter_payload!.plane).toBeUndefined()
  })

  it('mixing plane and placement refuses (A3.6.1)', async () => {
    const mock = createMockAuthoringBackend()
    await expect(mock.begin(REF({
      plane: { kind: 'principal', orientation: 'xy' },
      placement: { support: { kind: 'principal', orientation: 'xy' } },
    }))).rejects.toThrow(/mutually exclusive/)
  })

  it('a negative normal_side mirrors the v axis in the world mapping', async () => {
    const mock = createMockAuthoringBackend()
    const s = await mock.begin(REF({ placement: {
      support: { kind: 'principal', orientation: 'xy' }, normal_side: 'negative' } }))
    const d = await getV2(mock, s.sessionId)
    const pts = new Map(d.v2_construction?.[0].points.map((p) => [p.id, p.at]))
    expect(pts.get('skp_0002')).toEqual([20, 0, 0])
    expect(pts.get('skp_0003')!.map((x) => x + 0)).toEqual([0, -20, 0])
  })

  it('redefine applies the MINIMAL delta; omission keeps; no-op refuses; 0.2.0 refuses', async () => {
    const mock = createMockAuthoringBackend()
    const s1 = await mock.begin(REF({ placement: { support: { kind: 'principal', orientation: 'xy' } } }))
    await mock.commit(s1.sessionId, 'P-88')
    const feat = (mock.inspectRaw('P-88') as { sidecar: { feature: Array<{ id: string; adapter_schema_version?: string }> } }).sidecar.feature.find((f) => f.adapter_schema_version === '0.2.1')!
    // the redefine op through the full begin/simulate/commit lifecycle
    const s2 = await mock.begin([{ kind: 'mechanical.redefine_sketch_placement',
      params: { part_number: 'P-88', sketch_feature_id: feat.id, orientation: 'top' } }])
    expect((await mock.simulate(s2.sessionId)).valid).toBe(true)
    await mock.commit(s2.sessionId, 'P-88')
    const after = (mock.inspectRaw('P-88') as { sidecar: { feature: Array<{ id: string; adapter_payload?: Record<string, unknown> }> } }).sidecar.feature.find((f) => f.id === feat.id)!
    const placement = after.adapter_payload!.placement as Record<string, unknown>
    expect(placement.orientation).toBe('top')
    expect(placement.support).toEqual({ kind: 'principal', orientation: 'xy' }) // KEPT
    // the no-op refusal
    const s3 = await mock.begin([{ kind: 'mechanical.redefine_sketch_placement',
      params: { part_number: 'P-88', sketch_feature_id: feat.id, orientation: 'top' } }])
    const sim = await mock.simulate(s3.sessionId)
    expect(sim.valid).toBe(false)
    expect(sim.message).toMatch(/sketch-placement-unchanged/)
  })

  it('a 0.2.0 legacy sketch refuses redefine with the named copy', async () => {
    const mock = createMockAuthoringBackend()
    const s1 = await mock.begin(REF({ plane: { kind: 'principal', orientation: 'xy' } }))
    await mock.commit(s1.sessionId, 'P-88')
    const feat = (mock.inspectRaw('P-88') as { sidecar: { feature: Array<{ id: string; adapter_schema_version?: string }> } }).sidecar.feature.find((f) => f.adapter_schema_version === '0.2.0')!
    const s2 = await mock.begin([{ kind: 'mechanical.redefine_sketch_placement',
      params: { part_number: 'P-88', sketch_feature_id: feat.id, orientation: 'top' } }])
    const sim = await mock.simulate(s2.sessionId)
    expect(sim.valid).toBe(false)
    expect(sim.message).toMatch(/sketch-placement-redefine-v020/)
  })
})
