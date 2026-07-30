import { describe, it, expect } from 'vitest'
import {
  buildTreeRows,
  decodeInspectedPart,
  eligibleExtrudeSketchIds,
  unconsumedSketches,
} from './inspectDecode'

/** ADR/0044 A2 (Gate F2a): the Studio decoder is one of the FIVE skb-b0
 *  enforcement surfaces — the per-family 0.2 series gate, the closed v2
 *  payload contract, and the exact G0/G1/G2 graph admission all refuse
 *  loud here, mirroring the engine (Docs/SolverContracts/skb-b0.md). */

const view = (features: unknown[]) => ({
  object_number: 'P-000001',
  object_type: 'Part',
  sidecar: {
    object: { type: 'Part', number: 'P-000001', name: 'Probe', uuid: 'u-1', lifecycle: 'in_work' },
    feature: features,
  },
})

const pt = (id: string, x: number, y: number) => ({
  id, type: 'point', construction: true, nominal: { x, y },
})
const ln = (id: string, start: string, end: string) => ({
  id, type: 'line', construction: true, start, end,
})
const weak = (idx: number, entity: string, parameter: string, magnitude: number) => ({
  id: `w${String(idx).padStart(2, '0')}`,
  kind: 'fix_param',
  target: { entity, parameter },
  value: { magnitude, unit: 'mm' },
  strength: 'weak', role: 'driving', visibility: 'internal',
  origin: { category: 'computed_result', policy: 'skb-0', solver_contract: 'skb-c0' },
})

const v2payload = (over: Record<string, unknown> = {}) => ({
  sketch_model: 2,
  solver_contract: 'skb-c0',
  weak_policy: 'skb-0',
  branch_policy: 'skb-b0',
  plane: { kind: 'principal', orientation: 'xy' },
  entities: [pt('p1', 0, 0), pt('p2', 20, 0), ln('l1', 'p1', 'p2')],
  constraints: [
    { id: 'c01', kind: 'fix', args: ['p1'] },
    { id: 'c02', kind: 'horizontal', args: ['l1'] },
  ],
  dimensions: [],
  references: [],
  weak_completion: [weak(1, 'p2', 'x', 20)],
  witnesses: [],
  ...over,
})

const v2sketch = (over: Record<string, unknown> = {}, payload: Record<string, unknown> = {}) => ({
  id: 'feat_0001',
  feature_type: 'sketch',
  engine: 'mechanical',
  adapter_schema_version: '0.2.0',
  adapter_payload: v2payload(payload),
  ...over,
})

const V1_SKETCH = {
  id: 'feat_0002',
  feature_type: 'sketch',
  engine: 'mechanical',
  adapter_schema_version: '0.1.8',
  adapter_payload: {
    primitives: [{ id: 'skp_0001', type: 'rectangle', x_mm: 1, y_mm: 2, width_mm: 10, height_mm: 20 }],
  },
}

describe('the v2 sketch decode (G0/G1/G2 admission at the Studio surface)', () => {
  it('decodes a valid G1 references sketch as its own typed member', () => {
    const p = decodeInspectedPart(view([v2sketch()]))
    const f = p.features[0]
    expect(f.kind).toBe('sketchV2')
    if (f.kind !== 'sketchV2') throw new Error('unreachable')
    expect(f.shape).toBe('G1')
    expect(f.branchPolicy).toBe('skb-b0')
    expect(f.entityCount).toBe(3)
  })

  it('decodes G0 and G2', () => {
    const g0 = v2sketch({}, {
      entities: [pt('p1', 0, 0)],
      constraints: [{ id: 'c01', kind: 'fix', args: ['p1'] }],
      weak_completion: [],
    })
    const g2 = v2sketch({}, {
      entities: [pt('p1', 0, 0), pt('p2', 20, 0), pt('p3', 0, 20), ln('l1', 'p1', 'p2'), ln('l2', 'p1', 'p3')],
      constraints: [
        { id: 'c01', kind: 'fix', args: ['p1'] },
        { id: 'c02', kind: 'horizontal', args: ['l1'] },
        { id: 'c03', kind: 'vertical', args: ['l2'] },
      ],
      weak_completion: [weak(1, 'p2', 'x', 20), weak(2, 'p3', 'y', 20)],
    })
    const p = decodeInspectedPart(view([g0, { ...g2, id: 'feat_0002' }]))
    expect(p.features.map((f) => (f.kind === 'sketchV2' ? f.shape : ''))).toEqual(['G0', 'G2'])
  })

  it('a v2 sketch never feeds v1 eligibility, consumption, or extrusion', () => {
    const p = decodeInspectedPart(view([v2sketch(), V1_SKETCH]))
    expect(unconsumedSketches(p).map((s) => s.id)).toEqual(['feat_0002'])
    expect(eligibleExtrudeSketchIds(p).has('feat_0001')).toBe(false)
  })

  it('renders a labeled constrained-sketch tree row sharing the sketch ordinal', () => {
    const p = decodeInspectedPart(view([v2sketch(), V1_SKETCH]))
    const rows = buildTreeRows(p)
    expect(rows[0]).toMatchObject({ label: 'Sketch 1 (constrained)', kind: 'sketchV2' })
    expect(rows[1]).toMatchObject({ label: 'Sketch 2', kind: 'sketch' })
  })

  it('mixed v1/v2 Parts decode together (A2.4)', () => {
    const p = decodeInspectedPart(view([V1_SKETCH, v2sketch()]))
    expect(p.features.map((f) => f.kind)).toEqual(['sketch', 'sketchV2'])
  })
})

describe('the v2 refusal matrix at the Studio surface', () => {
  it('0.2.x on a NON-sketch family refuses BY NAME (A2.4)', () => {
    const extrudeV2 = {
      id: 'feat_0009', feature_type: 'extrude', engine: 'mechanical',
      adapter_schema_version: '0.2.0', adapter_payload: {},
    }
    expect(() => decodeInspectedPart(view([extrudeV2]))).toThrow(/only the SKETCH family/)
  })

  it('Codex23 B3: a GENERICIZED mechanical family (hole) at 0.2.0 refuses — no opaque bypass', () => {
    const holeV2 = {
      id: 'feat_0009', feature_type: 'hole', engine: 'mechanical',
      adapter_schema_version: '0.2.0', adapter_payload: {},
    }
    expect(() => decodeInspectedPart(view([holeV2]))).toThrow(/only the SKETCH family/)
  })

  it('Codex23 B3: an UNKNOWN mechanical family at 0.2.0 refuses — no opaque bypass', () => {
    const unknownV2 = {
      id: 'feat_0009', feature_type: 'warp_drive', engine: 'mechanical',
      adapter_schema_version: '0.2.0', adapter_payload: {},
    }
    expect(() => decodeInspectedPart(view([unknownV2]))).toThrow(/only the SKETCH family/)
  })

  it('Codex23 B2: a FOREIGN-engine 0.2.0 record stays OPAQUE (engine discrimination first)', () => {
    const foreignV2 = {
      id: 'feat_0009', feature_type: 'sketch', engine: 'electrical',
      adapter_schema_version: '0.2.0', adapter_payload: { anything: true },
    }
    const p = decodeInspectedPart(view([foreignV2]))
    expect(p.features[0]).toMatchObject({ kind: 'other', mechanical: false })
  })

  it('Codex23 B2: unknown nested entity/constraint fields refuse (closed shapes)', () => {
    const entityExtra = v2sketch({}, {
      entities: [{ ...pt('p1', 0, 0), ignored_semantic: 123 }],
      constraints: [{ id: 'c01', kind: 'fix', args: ['p1'] }],
      weak_completion: [],
    })
    expect(() => decodeInspectedPart(view([entityExtra]))).toThrow(/unknown field "ignored_semantic"/)
    const constraintExtra = v2sketch({}, {
      constraints: [
        { id: 'c01', kind: 'fix', args: ['p1'], ignored_semantic: 123 },
        { id: 'c02', kind: 'horizontal', args: ['l1'] },
      ],
    })
    expect(() => decodeInspectedPart(view([constraintExtra]))).toThrow(/unknown field "ignored_semantic"/)
  })

  it('Codex23 B2: boolean nominals are NOT numbers (one language, five surfaces)', () => {
    const boolNominal = v2sketch({}, {
      entities: [
        { id: 'p1', type: 'point', construction: true, nominal: { x: true, y: false } },
      ],
      constraints: [{ id: 'c01', kind: 'fix', args: ['p1'] }],
      weak_completion: [],
    })
    expect(() => decodeInspectedPart(view([boolNominal]))).toThrow(/finite \{x, y\}/)
  })

  it('Codex23 B2: a weak target with an extra key refuses', () => {
    const extraTarget = v2sketch({}, {
      weak_completion: [{
        ...weak(1, 'p2', 'x', 20),
        target: { entity: 'p2', parameter: 'x', note: '?' },
      }],
    })
    expect(() => decodeInspectedPart(view([extraTarget]))).toThrow(/target/)
  })

  it('Codex24 B2: principal-plane extras refuse (the exact cross-runtime probe)', () => {
    const planeExtra = v2sketch({}, {
      plane: { kind: 'principal', orientation: 'xy', ignored_semantic: 123 },
    })
    expect(() => decodeInspectedPart(view([planeExtra]))).toThrow(/unsupported key "ignored_semantic"/)
  })

  it('Codex24 B2: non-object array entries refuse (same JSON as the Python probes)', () => {
    for (const collection of ['entities', 'constraints', 'weak_completion'] as const) {
      const broken = v2sketch({}, { [collection]: [123] })
      expect(() => decodeInspectedPart(view([broken]))).toThrow(/not an object/)
    }
  })

  it('an unknown 0.2.x minor refuses rather than guessing', () => {
    // 0.2.1 became a DEFINED writer version (ADR/0044 A3) — the unknown
    // minor moves up; the refusal law is unchanged.
    expect(() => decodeInspectedPart(view([v2sketch({ adapter_schema_version: '0.2.3' })])))
      .toThrow(/unknown 0\.2\.x minor/)
  })

  it('a 0.2.1 record with a 0.2.0-shaped payload refuses (per-version key sets)', () => {
    // stamping the placed version over a legacy `plane` payload is a
    // producer error — the closed key set catches it by name
    expect(() => decodeInspectedPart(view([v2sketch({ adapter_schema_version: '0.2.1' })])))
      .toThrow(/unknown payload key "plane" for 0\.2\.1|missing payload key "placement"/)
  })

  it('the fixed-circle + point_on + weak-x counterexample refuses (layer 1)', () => {
    const counter = v2sketch({}, {
      entities: [
        pt('o', 0, 0),
        { id: 'k1', type: 'circle', construction: true, center: 'o', nominal: { radius: 10 } },
        pt('p', 6, 8),
      ],
      constraints: [
        { id: 'c01', kind: 'fix', args: ['o'] },
        { id: 'c02', kind: 'point_on', args: ['p', 'k1'] },
      ],
      weak_completion: [weak(1, 'p', 'x', 6)],
    })
    expect(() => decodeInspectedPart(view([counter]))).toThrow(/outside the skb-b0 local table/)
  })

  it('layer-2-only failures refuse (Codex22 N2: table passes, graph fails)', () => {
    const extraPoint = v2sketch({}, {
      entities: [pt('p1', 0, 0), pt('p2', 20, 0), pt('p9', 5, 5), ln('l1', 'p1', 'p2')],
    })
    expect(() => decodeInspectedPart(view([extraPoint]))).toThrow(/matches no admitted shape/)
    const wrongWeakTarget = v2sketch({}, { weak_completion: [weak(1, 'p2', 'y', 0)] })
    expect(() => decodeInspectedPart(view([wrongWeakTarget]))).toThrow(/target/)
    const missingAxisFact = v2sketch({}, {
      constraints: [{ id: 'c01', kind: 'fix', args: ['p1'] }],
    })
    expect(() => decodeInspectedPart(view([missingAxisFact]))).toThrow(/exactly one horizontal/)
  })

  it('a magnitude contradicting the authored nominal refuses (N1)', () => {
    const contradiction = v2sketch({}, { weak_completion: [weak(1, 'p2', 'x', 19)] })
    expect(() => decodeInspectedPart(view([contradiction]))).toThrow(/contradicts the authored nominal/)
  })

  it('the signed L_min guard refuses a negative-direction axis', () => {
    const negative = v2sketch({}, {
      entities: [pt('p1', 0, 0), pt('p2', -20, 0), ln('l1', 'p1', 'p2')],
      weak_completion: [weak(1, 'p2', 'x', -20)],
    })
    expect(() => decodeInspectedPart(view([negative]))).toThrow(/signed guard failed/)
  })

  it('any present witness is EXTRA and refuses (exact-set rule)', () => {
    const withWitness = v2sketch({}, {
      witnesses: [{
        id: 'bw01', kind: 'cross_sign', of: ['p1', 'p2', 'p1'], sign: 1,
        origin: { category: 'computed_result', policy: 'skb-b0', solver_contract: 'skb-c0' },
      }],
    })
    expect(() => decodeInspectedPart(view([withWitness]))).toThrow(/witness set mismatch/)
  })

  it('wrong contract ids refuse', () => {
    const wrong = v2sketch({}, { branch_policy: 'skb-b9' })
    expect(() => decodeInspectedPart(view([wrong]))).toThrow(/contract ids/)
  })

  it('a missing payload key refuses (the v2 contract is closed)', () => {
    const payload = v2payload()
    delete (payload as Record<string, unknown>).references
    const missing = v2sketch({ adapter_payload: payload })
    expect(() => decodeInspectedPart(view([missing]))).toThrow(/missing payload key "references"/)
  })

  it('a weak origin contradicting the top-level ids refuses (A2.8)', () => {
    const badOrigin = v2sketch({}, {
      weak_completion: [{
        ...weak(1, 'p2', 'x', 20),
        origin: { category: 'computed_result', policy: 'skb-0', solver_contract: 'skb-c9' },
      }],
    })
    expect(() => decodeInspectedPart(view([badOrigin]))).toThrow(/origin/)
  })
})

/** ADR/0044 A4 (arc 20260730-1, Codex6 B2): the 0.2.2 PROFILE lane at the
 *  decoder surface. Before this, a committed profile sketch KILLED the whole
 *  Part context — inspect refused the record, and since Part readiness is the
 *  JOIN of display+inspect, the tree, eligibility and every entry died with
 *  it. The walk would have ended at its second step. */
describe('the 0.2.2 profile sketch at the decoder surface', () => {
  const placement = {
    support: { kind: 'principal', orientation: 'xy' },
    orientation_ref: { kind: 'principal', orientation: 'yz' },
    orientation: 'right',
    normal_side: 'positive',
  }
  const cpt = (id: string, x: number, y: number, construction = false) => ({
    id, type: 'point', construction, nominal: { x, y },
  })
  const cln = (id: string, start: string, end: string, construction = false) => ({
    id, type: 'line', construction, start, end,
  })
  const v22payload = (over: Record<string, unknown> = {}) => ({
    sketch_model: 2,
    solver_contract: 'skb-c0',
    weak_policy: 'skb-0',
    branch_policy: 'skb-b1',
    placement,
    entities: [
      // the G2 reference frame
      cpt('skp_0001', 0, 0, true), cpt('skp_0002', 20, 0, true), cpt('skp_0003', 0, 20, true),
      cln('skp_0004', 'skp_0001', 'skp_0002', true), cln('skp_0005', 'skp_0001', 'skp_0003', true),
      // the drawn profile: one near-horizontal line, snapped by a fact
      cpt('skp_0006', 0, 0), cpt('skp_0007', 20, 0.4),
      cln('skp_0008', 'skp_0006', 'skp_0007'),
    ],
    constraints: [
      { id: 'c01', kind: 'fix', args: ['skp_0001'] },
      { id: 'c02', kind: 'horizontal', args: ['skp_0004'] },
      { id: 'c03', kind: 'vertical', args: ['skp_0005'] },
      { id: 'c04', kind: 'horizontal', args: ['skp_0008'] },
    ],
    dimensions: [],
    references: [],
    // cardinality only at this surface: G2 (2) + profile classes (3 — the
    // horizontal fact unions the two y scalars). Magnitudes are engine-side.
    weak_completion: [weak(1, 'skp_0002', 'x', 20), weak(2, 'skp_0003', 'y', 20),
      weak(3, 'skp_0006', 'x', 0), weak(4, 'skp_0006', 'y', 0), weak(5, 'skp_0007', 'x', 20)],
    witnesses: [],
    ...over,
  })
  const v22sketch = (payload: Record<string, unknown> = {}) => ({
    id: 'feat_0001',
    feature_type: 'sketch',
    engine: 'mechanical',
    adapter_schema_version: '0.2.2',
    adapter_payload: v22payload(payload),
  })

  it('a committed profile sketch decodes — the Part context SURVIVES the commit', () => {
    const part = decodeInspectedPart(view([v22sketch()]))
    const feat = part.features[0]
    expect(feat.kind).toBe('sketchV2')
    if (feat.kind !== 'sketchV2') return
    expect(feat.version).toBe('0.2.2')
    expect(feat.branchPolicy).toBe('skb-b1')
    expect(feat.shape).toBe('G2')
  })

  it('the decoded baseline is the committed profile block in id-form, byte-exact', () => {
    const part = decodeInspectedPart(view([v22sketch()]))
    const feat = part.features[0]
    if (feat.kind !== 'sketchV2') throw new Error('not a sketchV2')
    expect(feat.profile).toEqual({
      points: [
        { id: 'skp_0006', x: 0, y: 0 },
        { id: 'skp_0007', x: 20, y: 0.4 },
      ],
      segments: [{ id: 'skp_0008', start: { id: 'skp_0006' }, end: { id: 'skp_0007' } }],
      circles: [],
      facts: [{ id: 'c04', kind: 'horizontal', target: { id: 'skp_0008' } }],
    })
  })

  it('the version×policy matrix is CLOSED in both directions', () => {
    expect(() => decodeInspectedPart(view([v22sketch({ branch_policy: 'skb-b0' })])))
      .toThrow(/skb-b1.*for 0\.2\.2/)
    // the reverse direction needs a well-formed 0.2.1 payload (placement,
    // not plane) so the POLICY check is what fires, not the key set
    const p021 = v22payload({ branch_policy: 'skb-b1' }) as Record<string, unknown>
    expect(() =>
      decodeInspectedPart(view([{
        id: 'feat_0001', feature_type: 'sketch', engine: 'mechanical',
        adapter_schema_version: '0.2.1', adapter_payload: p021,
      }])),
    ).toThrow(/skb-b0.*for 0\.2\.1/)
  })

  it('a reference-only 0.2.2 graph refuses — that is a skb-b0 record', () => {
    const payload = v22payload()
    const entities = (payload.entities as Record<string, unknown>[]).filter(
      (e) => e.construction === true)
    const constraints = (payload.constraints as Record<string, unknown>[]).filter(
      (c) => c.id !== 'c04')
    expect(() => decodeInspectedPart(view([v22sketch({
      entities, constraints,
      weak_completion: [weak(1, 'skp_0002', 'x', 20), weak(2, 'skp_0003', 'y', 20)],
    })]))).toThrow(/non-empty profile block/)
  })

  it('two axis facts on one segment refuse at THIS surface too', () => {
    const payload = v22payload()
    const constraints = [...(payload.constraints as Record<string, unknown>[]),
      { id: 'c05', kind: 'vertical', args: ['skp_0008'] }]
    expect(() => decodeInspectedPart(view([v22sketch({ constraints })])))
      .toThrow(/more than one axis fact/)
  })

  it('a wrong weak CARDINALITY refuses (magnitudes stay engine-side)', () => {
    expect(() => decodeInspectedPart(view([v22sketch({
      weak_completion: [weak(1, 'skp_0002', 'x', 20)],
    })]))).toThrow(/canonical completion for this graph has 5/)
  })

  it('a cross-block segment refuses', () => {
    const payload = v22payload()
    const entities = (payload.entities as Record<string, unknown>[]).map((e) =>
      e.id === 'skp_0008' ? { ...e, start: 'skp_0001' } : e)
    expect(() => decodeInspectedPart(view([v22sketch({ entities })])))
      .toThrow(/across the reference\/profile block boundary/)
  })
})
