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
  ['references-sketch (F2b)', buildReferenceSketchOps('P-000001')],
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
  ])('%s refuses before bridge dispatch', (_l, params, pattern) => {
    expect(validateAuthoringParams('mechanical.add_reference_sketch', params)).toMatch(pattern)
  })
})
