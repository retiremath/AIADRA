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
          { id: 's1', kind: 'line', x1_mm: 0, y1_mm: 0, x2_mm: 40, y2_mm: 0 },
          { id: 's2', kind: 'line', x1_mm: 40, y1_mm: 0, x2_mm: 40, y2_mm: 30 },
          { id: 's3', kind: 'line', x1_mm: 40, y1_mm: 30, x2_mm: 0, y2_mm: 30 },
          { id: 's4', kind: 'line', x1_mm: 0, y1_mm: 30, x2_mm: 0, y2_mm: 0 },
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
    expect(sk).toMatchObject({ kind: 'sketch', id: 'feat_0001', plane: 'zx' })
    expect((sk as { rings: unknown[][] }).rings[0]).toHaveLength(4)
    expect(ex).toMatchObject({ kind: 'extrude', consumesSketchId: 'feat_0001', depthMm: 5.0 })
    // A plane-less sketch is xy (the EP2 legacy default); a rectangle ring has 4 corners.
    expect(rect).toMatchObject({ kind: 'sketch', plane: 'xy' })
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
    expect(p.features[0]).toEqual({ kind: 'other', id: 'feat_0001', featureType: 'sketch' })
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
    expect(p.features[0]).toEqual({ kind: 'other', id: 'feat_0009', featureType: 'thread' })
    expect(buildTreeRows(p)[0].label).toBe('Thread 1') // visible generically
  })

  it('B1: a supported mechanical record still decodes normally under the guard', () => {
    const p = decodeInspectedPart(view([SKETCH_CONTOUR]))
    expect(p.features[0]).toMatchObject({ kind: 'sketch', plane: 'zx' })
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
