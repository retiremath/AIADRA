import { describe, it, expect } from 'vitest'
import { buildTreeRows, decodeInspectedPart, unconsumedSketches } from './inspectDecode'

/** The REAL DTO shape as returned by Ring 2 `inspect` over the bridge (probed
 *  live against aiadra-core 0.14.0 / adapter 0.1.8 — sidecar key `feature`,
 *  singular). Tests decode THIS shape, not an invented one. */
const feat = (over: Record<string, unknown>) => ({
  adapter_schema_version: '0.1.8',
  engine: 'mechanical',
  ...over,
})
const SKETCH_CONTOUR = feat({
  id: 'feat_0001',
  feature_type: 'sketch',
  adapter_payload: {
    plane: { kind: 'principal', orientation: 'zx' },
    primitives: [
      {
        id: 'skp_0001',
        type: 'contour',
        segments: [
          { id: 'skp_0001s01', kind: 'line', x1_mm: 0, y1_mm: 0, x2_mm: 40, y2_mm: 0 },
          { id: 'skp_0001s02', kind: 'line', x1_mm: 40, y1_mm: 0, x2_mm: 40, y2_mm: 30 },
          { id: 'skp_0001s03', kind: 'line', x1_mm: 40, y1_mm: 30, x2_mm: 0, y2_mm: 30 },
          { id: 'skp_0001s04', kind: 'line', x1_mm: 0, y1_mm: 30, x2_mm: 0, y2_mm: 0 },
        ],
      },
    ],
  },
})
const EXTRUDE = feat({
  id: 'feat_0002',
  feature_type: 'extrude',
  depends_on_feature_ids: ['feat_0001'],
  parameters: [{ id: 'featp_0001', name: 'depth_mm', value: 5.0, datatype: 'number', unit: 'mm' }],
  adapter_payload: { depth_parameter_id: 'featp_0001', direction: 'normal+', sketch_feature_id: 'feat_0001' },
})
const SKETCH_RECT = feat({
  id: 'feat_0003',
  feature_type: 'sketch',
  adapter_payload: {
    primitives: [{ id: 'skp_0001', type: 'rectangle', x_mm: 1, y_mm: 2, width_mm: 10, height_mm: 20 }],
  },
})

const view = (features: unknown[]) => ({
  object_number: 'P-000001',
  object_type: 'Part',
  sidecar: {
    object: { type: 'Part', number: 'P-000001', name: 'Probe', uuid: 'u-1', lifecycle: 'in_work' },
    feature: features,
  },
})

describe('decodeInspectedPart (S2 Codex1 B2 — the version-guarded decoder)', () => {
  it('decodes the real bridge DTO: plane, rings, dependency edge, depth', () => {
    const p = decodeInspectedPart(view([SKETCH_CONTOUR, EXTRUDE, SKETCH_RECT]))
    expect(p.number).toBe('P-000001')
    expect(p.features).toHaveLength(3)
    const [sk, ex, rect] = p.features
    expect(sk).toMatchObject({ kind: 'sketch', id: 'feat_0001', plane: { kind: 'principal', orientation: 'zx' } })
    expect((sk as { rings: unknown[][] }).rings[0]).toHaveLength(4)
    expect(ex).toMatchObject({ kind: 'extrude', consumesSketchId: 'feat_0001', depthMm: 5.0 })
    // A plane-less sketch is xy (the EP2 legacy default); a rectangle ring has 4 corners.
    expect(rect).toMatchObject({ kind: 'sketch', plane: { kind: 'principal', orientation: 'xy' } })
    expect((rect as { rings: { x: number; y: number }[][] }).rings[0]).toEqual([
      { x: 1, y: 2 },
      { x: 11, y: 2 },
      { x: 11, y: 22 },
      { x: 1, y: 22 },
    ])
    expect(p.hasExtrudeBase).toBe(true)
    expect(p.hasRevolveBase).toBe(false)
  })

  it('an EMPTY Part (no feature key) decodes to zero features', () => {
    const raw = view([])
    delete (raw.sidecar as Record<string, unknown>).feature
    const p = decodeInspectedPart(raw)
    expect(p.features).toEqual([])
    expect(p.hasExtrudeBase).toBe(false)
  })

  it('FAILS LOUD on a KNOWN mechanical record written by a NEWER adapter series', () => {
    const alien = { ...SKETCH_RECT, adapter_schema_version: '0.2.0' }
    expect(() => decodeInspectedPart(view([alien]))).toThrow(/adapter 0\.2\.0/)
  })

  it('B1: a FOREIGN-engine "sketch" stays GENERIC — payload never interpreted', () => {
    const foreign = { ...SKETCH_CONTOUR, engine: 'electrical' }
    const p = decodeInspectedPart(view([foreign]))
    expect(p.features[0]).toEqual({ kind: 'other', id: 'feat_0001', featureType: 'sketch', mechanical: false, parameters: [] })
    expect(unconsumedSketches(p)).toEqual([]) // no wire, no Extrude candidate
    // A foreign "extrude" must not fabricate one-base eligibility either.
    const foreignExtrude = { ...EXTRUDE, engine: 'electrical' }
    expect(decodeInspectedPart(view([foreignExtrude])).hasExtrudeBase).toBe(false)
  })

  it('B1: an UNKNOWN feature type stays generic even with an out-of-series version', () => {
    const unknown = feat({
      id: 'feat_0009',
      feature_type: 'thread',
      adapter_schema_version: '0.9.0', // never version-gated — payload never read
      adapter_payload: { anything: true },
    })
    const p = decodeInspectedPart(view([unknown]))
    expect(p.features[0]).toEqual({ kind: 'other', id: 'feat_0009', featureType: 'thread', mechanical: true, parameters: [] })
    expect(buildTreeRows(p)[0].label).toBe('Thread 1') // visible generically
  })

  it('Codex3-B2: editable catalogues honor the adapter series — a FUTURE fillet/hole stays opaque (no editable params, no throw)', () => {
    const filletNew = feat({ id: 'feat_0005', feature_type: 'fillet', adapter_schema_version: '0.2.0',
      parameters: [{ id: 'p1', name: 'radius_mm', value: 2, unit: 'mm' }], adapter_payload: {} })
    const holeNew = feat({ id: 'feat_0006', feature_type: 'hole', adapter_schema_version: '1.0.0',
      parameters: [{ id: 'p2', name: 'diameter_mm', value: 6, unit: 'mm' }], adapter_payload: {} })
    const p = decodeInspectedPart(view([filletNew, holeNew]))
    expect(p.features.map((f) => f.kind === 'other' && f.parameters)).toEqual([[], []]) // OPAQUE rows
    // The SUPPORTED series exposes the catalogue (identity-preserving).
    const filletOk = feat({ id: 'feat_0007', feature_type: 'fillet', adapter_schema_version: '0.1.8',
      parameters: [{ id: 'p3', name: 'radius_mm', value: 2, unit: 'mm' }], adapter_payload: {} })
    const holeOk = feat({ id: 'feat_0008', feature_type: 'hole', adapter_schema_version: '0.1.8',
      parameters: [
        { id: 'p4', name: 'diameter_mm', value: 6, unit: 'mm' },
        { id: 'p5', name: 'evil_field', value: 1, unit: 'mm' },
      ], adapter_payload: {} })
    const p2 = decodeInspectedPart(view([filletOk, holeOk]))
    const [f, h] = p2.features
    expect(f.kind === 'other' && f.parameters).toEqual([{ id: 'p3', name: 'radius_mm', value: 2, unit: 'mm' }])
    expect(h.kind === 'other' && h.parameters).toEqual([{ id: 'p4', name: 'diameter_mm', value: 6, unit: 'mm' }]) // only CATALOGUED names
    // The stacking fact derives from referencing features.
    expect(p2.hasReferencingFeature).toBe(true)
    // Codex4 polish: a FOREIGN-engine "fillet" must NOT trip the containment.
    const foreignFillet = { id: 'feat_0009', feature_type: 'fillet', engine: 'electrical',
      adapter_schema_version: '0.1.8', adapter_payload: {} }
    const p3 = decodeInspectedPart(view([foreignFillet]))
    expect(p3.hasReferencingFeature).toBe(false)
  })

  it('B1: a supported mechanical record still decodes normally under the guard', () => {
    const p = decodeInspectedPart(view([SKETCH_CONTOUR]))
    expect(p.features[0]).toMatchObject({ kind: 'sketch', plane: { kind: 'principal', orientation: 'zx' } })
  })

  it('FAILS LOUD on a non-Part and on a malformed dependency edge', () => {
    const req = view([])
    ;((req.sidecar as Record<string, unknown>).object as Record<string, unknown>).type = 'Requirement'
    expect(() => decodeInspectedPart(req)).toThrow(/not a Part/)
    const badExtrude = { ...EXTRUDE, depends_on_feature_ids: [] }
    expect(() => decodeInspectedPart(view([SKETCH_CONTOUR, badExtrude]))).toThrow(/exactly one sketch/)
  })
})

describe('buildTreeRows — the Creo 10 shape (D-S1)', () => {
  it('consumed sketch NESTS as Section 1 under Extrude 1; unconsumed stays Sketch N', () => {
    const p = decodeInspectedPart(view([SKETCH_CONTOUR, EXTRUDE, SKETCH_RECT]))
    expect(buildTreeRows(p)).toEqual([
      { featureId: 'feat_0002', label: 'Extrude 1', depth: 0, kind: 'extrude' },
      { featureId: 'feat_0001', label: 'Section 1', depth: 1, kind: 'section' },
      // The rect sketch is the SECOND sketch — its name never changes
      // retroactively when an earlier sketch gets consumed.
      { featureId: 'feat_0003', label: 'Sketch 2', depth: 0, kind: 'sketch' },
    ])
  })

  it('an unconsumed-only Part shows Sketch 1 top-level (the pre-extrude walk)', () => {
    const p = decodeInspectedPart(view([SKETCH_CONTOUR]))
    expect(buildTreeRows(p)).toEqual([
      { featureId: 'feat_0001', label: 'Sketch 1', depth: 0, kind: 'sketch' },
    ])
  })
})

describe('unconsumedSketches — ONE derivation for the wire overlay + the Extrude picker', () => {
  it('returns only sketches no base feature consumes', () => {
    const p = decodeInspectedPart(view([SKETCH_CONTOUR, EXTRUDE, SKETCH_RECT]))
    expect(unconsumedSketches(p).map((s) => s.id)).toEqual(['feat_0003'])
  })
})

describe('the DISCRIMINATED face plane binding (SK-C1.0 S2, Codex2 B3.4)', () => {
  const facePart = () => ({
    sidecar: {
      object: { type: 'Part', number: 'P-1', name: 'p', uuid: 'u1' },
      feature: [{
        id: 'feat_0003', feature_type: 'sketch', engine: 'mechanical',
        adapter_schema_version: '0.1.10',
        adapter_payload: {
          primitives: [{ id: 'skp_0001', type: 'rectangle', x_mm: 2, y_mm: 2, width_mm: 5, height_mm: 5 }],
          plane: {
            kind: 'face',
            face_role: 'feat_0002:face:cap_top',
            resolved_against_topology_signature: 'topo_abc123',
          },
        },
      }],
    },
  })

  it('a face-bound sketch decodes as its STRUCTURED binding (never forced principal)', () => {
    const part = decodeInspectedPart(facePart())
    const sk = part.features[0]
    expect(sk.kind).toBe('sketch')
    if (sk.kind === 'sketch') {
      expect(sk.plane).toEqual({
        kind: 'face',
        faceRole: 'feat_0002:face:cap_top',
        resolvedAgainst: 'topo_abc123',
      })
    }
  })

  it('a malformed face record FAILS LOUD (role/signature structure)', () => {
    const bad = facePart()
    ;(bad.sidecar.feature[0].adapter_payload.plane as Record<string, unknown>).face_role = 'not-a-role'
    expect(() => decodeInspectedPart(bad)).toThrow(/face_role/)
  })
})

describe('deriveSelectorFacts — the ONE v1.2 fact derivation (SK-C1.0 S2)', () => {
  it('planar eligibility is FAIL-CLOSED (absent surface_kind ≠ planar); frames join by id', async () => {
    const { deriveSelectorFacts } = await import('./partContext')
    const facts = deriveSelectorFacts({
      render: {
        edges: [{ edge_id: 'e1', kind: 'sharp' }],
        faces: [
          { face_id: 'f-plane', surface_kind: 'plane' },
          { face_id: 'f-cyl', surface_kind: 'other' },
          { face_id: 'f-legacy' }, // a 1.1 payload face — unknown kind
        ],
      },
      sketch_frames: [{
        sketch_feature_id: 'feat_0003',
        origin_mm: [0, 0, 10], u_axis: [1, 0, 0], v_axis: [0, 1, 0], normal: [0, 0, 1],
      }],
    })
    expect(facts.faceIds).toEqual(new Set(['f-plane', 'f-cyl', 'f-legacy']))
    expect(facts.planarFaceIds).toEqual(new Set(['f-plane'])) // fail-closed
    expect(facts.edgeKinds.get('e1')).toBe('sharp')
    expect(facts.sketchFrames.get('feat_0003')?.origin_mm).toEqual([0, 0, 10])
  })
})

describe('the FAIL-CLOSED frame join (Codex7 B4)', () => {
  const FRAME = {
    sketch_feature_id: 'feat_0003',
    origin_mm: [0, 0, 10] as [number, number, number],
    u_axis: [1, 0, 0] as [number, number, number],
    v_axis: [0, 1, 0] as [number, number, number],
    normal: [0, 0, 1] as [number, number, number],
  }
  const base = { render: { edges: [], faces: [] } }

  it('a DUPLICATE frame id refuses the whole publication (never silently overwrites)', async () => {
    const { deriveSelectorFacts } = await import('./partContext')
    expect(() => deriveSelectorFacts({ ...base, sketch_frames: [FRAME, { ...FRAME }] }))
      .toThrow(/duplicate sketch frame/)
  })

  it('a structurally invalid frame refuses at the TS boundary too (mocks bypass Core)', async () => {
    const { deriveSelectorFacts } = await import('./partContext')
    expect(() => deriveSelectorFacts({
      ...base,
      sketch_frames: [{ ...FRAME, v_axis: [0, -1, 0] as [number, number, number] }], // left-handed
    })).toThrow(/right-handed/)
    expect(() => deriveSelectorFacts({
      ...base,
      sketch_frames: [{ ...FRAME, normal: [0, 0, Number.NaN] as [number, number, number] }],
    })).toThrow(/malformed vector/)
  })

  it('a MISSING frame stays absent — unavailable, never guessed', async () => {
    const { deriveSelectorFacts } = await import('./partContext')
    const facts = deriveSelectorFacts({ ...base, sketch_frames: [FRAME] })
    expect(facts.sketchFrames.get('feat_0003')).toBeTruthy()
    expect(facts.sketchFrames.get('feat_0099')).toBeUndefined()
  })
})
