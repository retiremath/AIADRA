import { describe, it, expect } from 'vitest'
import { AUTHORING_KINDS, validateAuthoringParams } from './authoringParamRules'
import {
  buildAdjustParameterOps,
  buildCircleSketchOps,
  buildContourFeatureOps,
  buildContourOps,
  buildCreatePartOps,
  buildCreateWithCircleOps,
  buildCreateWithRectangleOps,
  buildCreateWithSketchOps,
  buildEdgeFeatureOps,
  buildExtrudeOnSketchOps,
  buildHoleOps,
  buildRectangleRevolveOps,
  buildRectangleSketchOps,
  buildRedefinePlacementOps,
  buildReferenceSketchOps,
  buildRevolveOnSketchOps,
  buildSketchOnlyOps,
  type SketchSupport,
} from '../src/authoring/backend'

/** Codex27 B1 — the desktop-walk lesson as a REGRESSION: this boundary
 *  validator once froze at the R-arc while the renderer moved on, and the
 *  whole sequential lane became unreachable on desktop with every suite
 *  green. Here, EVERY renderer op-builder's representative output drives
 *  through the exact main-process validator — the boundary can never again
 *  silently disagree with what the app actually sends. */

const PTS = [
  { x: 0, y: 0 },
  { x: 40, y: 0 },
  { x: 40, y: 30 },
  { x: 0, y: 30 },
]
const RECT = { x_mm: 0, y_mm: 0, width_mm: 40, height_mm: 30 }
const CIRCLE = { cx_mm: 10, cy_mm: 10, radius_mm: 5 }
const FACE_SUPPORT: SketchSupport = {
  kind: 'face',
  faceId: 'feat_0002:face:cap_top',
  // the frame is a renderer-side transient; supportPlaneParam sends ONLY
  // the display id across the boundary (the S2 handler input shape)
  frame: {
    orientation: 'xy',
    origin: [0, 0, 5],
    uAxis: [1, 0, 0],
    vAxis: [0, 1, 0],
    normal: [0, 0, 1],
  } as unknown as SketchSupport extends { frame: infer F } ? F : never,
} as SketchSupport

const REPRESENTATIVE: Array<[string, ReturnType<typeof buildCreatePartOps>]> = [
  ['create-part', buildCreatePartOps('P-000001', 'Probe')],
  ['contour-feature', buildContourFeatureOps('P-000001', PTS, 5, 'xy')],
  ['contour-chained', buildContourOps('P-000001', 'Probe', PTS, 5)],
  ['rectangle-sketch datum', buildRectangleSketchOps('P-000001', RECT, 'xy', false)],
  ['rectangle-sketch FACE', buildRectangleSketchOps('P-000001', RECT, FACE_SUPPORT, false)],
  ['create+rectangle', buildCreateWithRectangleOps('P-000001', 'Probe', RECT, 'xy', false)],
  ['references-sketch (F2b/A3 default placement)', buildReferenceSketchOps('P-000001')],
  ['references-sketch (A3 full placement)', buildReferenceSketchOps('P-000001', {
    support: { kind: 'principal', orientation: 'zx' },
    orientation_ref: { kind: 'principal', orientation: 'xy' },
    orientation: 'top',
    normal_side: 'negative',
  })],
  ['redefine-placement (A3.6.2)', buildRedefinePlacementOps('P-000001', 'feat_0001', {
    orientation: 'left',
    normal_side: 'negative',
  })],
  ['sketch-only datum', buildSketchOnlyOps('P-000001', PTS, 'zx')],
  // the EXACT walk omission: the face-bound sketch input vocabulary
  ['sketch-only FACE', buildSketchOnlyOps('P-000001', PTS, FACE_SUPPORT)],
  ['circle-sketch', buildCircleSketchOps('P-000001', CIRCLE, 'xy', false)],
  ['create+circle', buildCreateWithCircleOps('P-000001', 'Probe', CIRCLE, 'xy', false)],
  ['create+sketch', buildCreateWithSketchOps('P-000001', 'Probe', PTS, 'xy')],
  ['revolve-on-sketch', buildRevolveOnSketchOps('P-000001', 'feat_0001', 'x')],
  ['rectangle+revolve', buildRectangleRevolveOps('P-000001', RECT, 'x')],
  ['fillet', buildEdgeFeatureOps('fillet', 'P-000001', 'feat_0002:edge:e1', 2)],
  ['chamfer', buildEdgeFeatureOps('chamfer', 'P-000001', 'feat_0002:edge:e1', 1.5)],
  ['hole', buildHoleOps('P-000001', 'feat_0002:face:cap_top', 6, 10, 12)],
  ['adjust-parameter', buildAdjustParameterOps('P-000001', 'feat_0002', 'depth_mm', 7)],
  ['extrude add', buildExtrudeOnSketchOps('P-000001', 'feat_0001', 5)],
  ['extrude cut', buildExtrudeOnSketchOps('P-000001', 'feat_0001', 5, 'cut')],
]

/** The AuthoringBackends resolve `{ $fromOp: n }` staged-identity aliases
 *  RENDERER-side against engine-created ids BEFORE anything crosses IPC (the
 *  S2 handshake) — main only ever sees resolved string ids. The parity floor
 *  therefore validates the POST-resolution shape, exactly what main
 *  receives; the raw alias is separately asserted to REFUSE. */
const resolveAliases = (params: Record<string, unknown>): Record<string, unknown> =>
  Object.fromEntries(
    Object.entries(params).map(([k, v]) => [
      k,
      v !== null && typeof v === 'object' && '$fromOp' in (v as object) ? 'feat_0001' : v,
    ]),
  )

describe('the op-builder → main-validator PARITY floor (Codex27 B1)', () => {
  it.each(REPRESENTATIVE)('%s: every op passes the allowlist AND the param rules', (_label, ops) => {
    expect(ops.length).toBeGreaterThan(0)
    for (const op of ops) {
      expect(AUTHORING_KINDS.has(op.kind), `kind not allowlisted: ${op.kind}`).toBe(true)
      const refusal = validateAuthoringParams(op.kind, resolveAliases(op.params as Record<string, unknown>))
      expect(refusal, `${op.kind}: ${refusal ?? ''}`).toBeNull()
    }
  })

  it('an UNRESOLVED staged-identity alias refuses at main (never crosses raw)', () => {
    const [, extrude] = buildContourFeatureOps('P-000001', PTS, 5, 'xy')
    expect(validateAuthoringParams(extrude.kind, extrude.params)).toMatch(/sketch_feature_id/)
  })

  it('every allowlisted kind has an explicit rule (no default fall-through)', () => {
    for (const kind of AUTHORING_KINDS) {
      // a rule exists iff an empty object produces a kind-specific refusal,
      // never the allowlist default message
      const refusal = validateAuthoringParams(kind, {})
      expect(refusal, kind).not.toBeNull()
      expect(refusal, kind).not.toMatch(/not allowed/)
    }
  })
})

describe('add_reference_sketch boundary negatives (Codex27 B1: absence ≠ null)', () => {
  const base = { part_number: 'P-000001' }
  it('absent optionals are accepted (engine-side defaults apply)', () => {
    expect(validateAuthoringParams('mechanical.add_reference_sketch', base)).toBeNull()
  })
  it.each([
    ['explicit null axes', { ...base, axes: null }, /axes/],
    ['unknown axes', { ...base, axes: 'diagonal' }, /axes/],
    ['explicit null length', { ...base, x_axis_mm: null }, /x_axis_mm/],
    ['non-finite length', { ...base, y_axis_mm: Infinity }, /y_axis_mm/],
    ['explicit null plane', { ...base, plane: null }, /plane/],
    ['face plane', { ...base, plane: { kind: 'face', target_face_id: 'f' } }, /principal/],
    ['extra-key principal plane', { ...base, plane: { kind: 'principal', orientation: 'xy', extra: 1 } }, /plane/],
    // A3.6.1 placement wire shapes
    ['plane AND placement together', { ...base, plane: { kind: 'principal', orientation: 'xy' }, placement: { support: { kind: 'principal', orientation: 'xy' } } }, /mutually exclusive/],
    ['null placement', { ...base, placement: null }, /placement must be an object/],
    ['placement without support', { ...base, placement: { orientation: 'right' } }, /requires support/],
    ['placement with unknown member', { ...base, placement: { support: { kind: 'principal', orientation: 'xy' }, flip: true } }, /unknown members/],
    ['placement with bad orientation', { ...base, placement: { support: { kind: 'principal', orientation: 'xy' }, orientation: 'diagonal' } }, /orientation must be/],
    ['placement with bad normal_side', { ...base, placement: { support: { kind: 'principal', orientation: 'xy' }, normal_side: 'up' } }, /normal_side must be/],
    ['placement with face support', { ...base, placement: { support: { kind: 'face', target_face_id: 'f' } } }, /principal/],
  ])('%s refuses before bridge dispatch', (_l, params, pattern) => {
    expect(validateAuthoringParams('mechanical.add_reference_sketch', params)).toMatch(pattern)
  })
})

describe('redefine_sketch_placement boundary (A3.6.2 wire shape)', () => {
  const base = { part_number: 'P-000001', sketch_feature_id: 'feat_0001' }
  it('the target pair is required; provided members validate; omission is the ENGINE’s (keep-current)', () => {
    expect(validateAuthoringParams('mechanical.redefine_sketch_placement', base)).toBeNull()
    expect(validateAuthoringParams('mechanical.redefine_sketch_placement', { part_number: 'P-1' }))
      .toMatch(/sketch_feature_id/)
    expect(validateAuthoringParams('mechanical.redefine_sketch_placement',
      { ...base, orientation: 'top' })).toBeNull()
    expect(validateAuthoringParams('mechanical.redefine_sketch_placement',
      { ...base, orientation: 'diagonal' })).toMatch(/orientation must be/)
    expect(validateAuthoringParams('mechanical.redefine_sketch_placement',
      { ...base, normal_side: null })).toMatch(/normal_side must be/)
    expect(validateAuthoringParams('mechanical.redefine_sketch_placement',
      { ...base, support: { kind: 'principal', orientation: 'xy', extra: 1 } })).toMatch(/support/)
  })
})

describe('profile wire shape (ADR/0044 A4 — author_profile_sketch / replace_sketch_graph)', () => {
  const placement = { support: { kind: 'principal', orientation: 'xy' } }
  const line = {
    points: [
      { key: 'p0', x: 0, y: 0 },
      { key: 'p1', x: 20, y: 0.4 },
    ],
    segments: [{ key: 's0', start: { key: 'p0' }, end: { key: 'p1' } }],
    facts: [{ key: 'f0', kind: 'horizontal', target: { key: 's0' } }],
  }
  const create = { part_number: 'P-000001', placement, profile: line }
  const edit = { part_number: 'P-000001', sketch_feature_id: 'feat_0001', profile: line }

  it('both kinds are allowlisted', () => {
    expect(AUTHORING_KINDS.has('mechanical.author_profile_sketch')).toBe(true)
    expect(AUTHORING_KINDS.has('mechanical.replace_sketch_graph')).toBe(true)
  })

  it('a drawn line passes both lanes', () => {
    expect(validateAuthoringParams('mechanical.author_profile_sketch', create)).toBeNull()
    expect(validateAuthoringParams('mechanical.replace_sketch_graph', edit)).toBeNull()
  })

  it('a preserved-id edit payload passes', () => {
    expect(
      validateAuthoringParams('mechanical.replace_sketch_graph', {
        ...edit,
        profile: {
          points: [
            { id: 'skp_0006', x: 0, y: 0 },
            { id: 'skp_0007', x: 35, y: 0.4 },
          ],
          segments: [{ id: 'skp_0008', start: { id: 'skp_0006' }, end: { id: 'skp_0007' } }],
          facts: [{ id: 'c04', kind: 'horizontal', target: { id: 'skp_0008' } }],
        },
      }),
    ).toBeNull()
  })

  it('a circle passes', () => {
    expect(
      validateAuthoringParams('mechanical.author_profile_sketch', {
        ...create,
        profile: {
          points: [{ key: 'c', x: 5, y: 5 }],
          circles: [{ key: 'o', center: { key: 'c' }, radius_mm: 3 }],
        },
      }),
    ).toBeNull()
  })

  it.each([
    ['no placement', { part_number: 'P-1', profile: line }, /requires a placement object/],
    ['placement without support', { ...create, placement: { orientation: 'right' } }, /requires support/],
    ['no profile', { part_number: 'P-1', placement }, /profile must be an object/],
    ['unknown profile key', { ...create, profile: { ...line, arcs: [] } }, /unknown keys/],
    [
      'a BARE STRING reference',
      { ...create, profile: { ...line, segments: [{ key: 's0', start: 'p0', end: { key: 'p1' } }] } },
      /bare string is never accepted/,
    ],
    [
      'both key and id on one record',
      { ...create, profile: { ...line, points: [{ key: 'p0', id: 'skp_0001', x: 0, y: 0 }] } },
      /exactly one of/,
    ],
    [
      'neither key nor id',
      { ...create, profile: { ...line, points: [{ x: 0, y: 0 }] } },
      /exactly one of/,
    ],
    [
      'a non-finite coordinate',
      { ...create, profile: { ...line, points: [{ key: 'p0', x: Infinity, y: 0 }] } },
      /finite x \+ y/,
    ],
    [
      'an out-of-vocabulary fact kind',
      { ...create, profile: { ...line, facts: [{ key: 'f0', kind: 'tangent', target: { key: 's0' } }] } },
      /horizontal.*vertical/,
    ],
    [
      'a malformed engine id',
      { ...create, profile: { ...line, points: [{ id: 'skp_1', x: 0, y: 0 }] } },
      /wrong shape/,
    ],
    [
      'a zero-radius circle',
      { ...create, profile: { points: [{ key: 'c', x: 0, y: 0 }], circles: [{ key: 'o', center: { key: 'c' }, radius_mm: 0 }] } },
      /radius_mm/,
    ],
  ])('%s refuses before bridge dispatch', (_l, params, pattern) => {
    expect(validateAuthoringParams('mechanical.author_profile_sketch', params)).toMatch(pattern)
  })

  it('the edit lane requires its target pair', () => {
    expect(validateAuthoringParams('mechanical.replace_sketch_graph', { profile: line }))
      .toMatch(/part_number \+ sketch_feature_id/)
  })
})
