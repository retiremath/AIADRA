/**
 * The profile EDIT entry (I3; Codex1 N1 / Codex2): the edit's frame is the
 * ENGINE's `sketch_frames[]` row of the CURRENT display generation and the
 * target comes from the SAME snapshot; a missing row, an inspect-only context
 * (no display installed), or a not-ready context REFUSE — never a mirror
 * fallback, never a guessed frame.
 */
import { describe, expect, it } from 'vitest'
import type { PartContextState } from '../authoring/partContext'
import type { SketchFrame } from '../display/contract'
import {
  EDIT_CONTEXT_NOT_READY,
  EDIT_FRAME_UNAVAILABLE,
  resolveProfileEditEntry,
  sketchFrameToPlaneFrame,
} from './profileEditEntry'

// the corrected acceptance scenario's engine row (xy / zx / top / negative)
const ROW: SketchFrame = {
  sketch_feature_id: 'feat_0007',
  origin_mm: [0, 0, 0],
  u_axis: [-1, 0, 0],
  v_axis: [0, 1, 0],
  normal: [0, 0, -1],
}

const facts = (rows: SketchFrame[]) => ({
  sketchFrames: new Map(rows.map((r) => [r.sketch_feature_id, r])),
  edgeKinds: new Map<string, string>(),
  faceIds: new Set<string>(),
  planarFaceIds: new Set<string>(),
})

const context = (over: Partial<PartContextState>): PartContextState =>
  ({
    workspaceId: 'ws-1',
    partNumber: 'P-000001',
    generation: 4,
    inspection: { status: 'ready', part: {} as never },
    selectorFacts: facts([ROW]),
    ...over,
  }) as PartContextState

describe('resolveProfileEditEntry', () => {
  it('joins the engine row (wire names → session names, values preserved) and captures the target from the same snapshot', () => {
    const r = resolveProfileEditEntry(context({}), 'feat_0007')
    expect(r.ok).toBe(true)
    if (!r.ok) throw new Error('unreachable')
    expect(r.frame).toEqual({ origin: [0, 0, 0], u: [-1, 0, 0], v: [0, 1, 0], normal: [0, 0, -1] })
    expect(r.target).toEqual({ workspaceId: 'ws-1', partNumber: 'P-000001', generation: 4 })
  })

  it('refuses when the feature has no row in this display (no mirror fallback)', () => {
    const r = resolveProfileEditEntry(context({}), 'feat_0099')
    expect(r).toEqual({ ok: false, reason: EDIT_FRAME_UNAVAILABLE })
  })

  it('refuses an inspect-only context (facts not published for this generation)', () => {
    const r = resolveProfileEditEntry(context({ selectorFacts: null }), 'feat_0007')
    expect(r).toEqual({ ok: false, reason: EDIT_FRAME_UNAVAILABLE })
  })

  it('refuses a context that is not ready, before looking at any frame', () => {
    const loading = resolveProfileEditEntry(context({ inspection: { status: 'loading' } }), 'feat_0007')
    expect(loading).toEqual({ ok: false, reason: EDIT_CONTEXT_NOT_READY })
    const noPart = resolveProfileEditEntry(context({ partNumber: null }), 'feat_0007')
    expect(noPart).toEqual({ ok: false, reason: EDIT_CONTEXT_NOT_READY })
  })

  it('sketchFrameToPlaneFrame preserves the row’s values verbatim', () => {
    const f = sketchFrameToPlaneFrame({ ...ROW, origin_mm: [1, 2, 3] })
    expect(f.origin).toEqual([1, 2, 3])
    expect(f.normal).toBe(ROW.normal)
  })
})
