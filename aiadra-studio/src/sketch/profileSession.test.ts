import { describe, it, expect } from 'vitest'
import {
  applyPreview,
  cancel,
  commitIntent,
  commitPoint,
  currentProfile,
  endTool,
  hasWork,
  moveCursor,
  openCreate,
  openEdit,
  previewRequest,
  setTool,
  undoLastPart,
  type ProfileSessionState,
} from './profileSession'
import type { ProfilePayload, SketchPlacementInput } from './profileTypes'
import { profileError } from '../../electron/authoringParamRules'

const PLACEMENT: SketchPlacementInput = {
  support: { kind: 'principal', orientation: 'xy' },
}
const OPTS = { snapAngleToleranceDeg: 3, minDragPx: 4 }
const TARGET = { workspaceId: 'ws1', partNumber: 'P-000001', generation: 7 }
const FRAME = {
  origin: [0, 0, 0] as [number, number, number],
  u: [1, 0, 0] as [number, number, number],
  v: [0, 1, 0] as [number, number, number],
  normal: [0, 0, 1] as [number, number, number],
}

const BASELINE: ProfilePayload = {
  points: [
    { id: 'skp_0006', x: 0, y: 0 },
    { id: 'skp_0007', x: 20, y: 0.4 },
  ],
  segments: [{ id: 'skp_0008', start: { id: 'skp_0006' }, end: { id: 'skp_0007' } }],
  facts: [{ id: 'c04', kind: 'horizontal', target: { id: 'skp_0008' } }],
}

const drawLine = (s: ProfileSessionState, a = { u: 0, v: 0 }, b = { u: 20, v: 0.4 }) =>
  commitPoint(commitPoint(s, a), b)

describe('the two entry states (Codex3 B1)', () => {
  it('a create session with nothing drawn has no transaction at all', () => {
    const s = openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS)
    expect(hasWork(s)).toBe(false)
    expect(commitIntent(s, 'P-000001')).toBeNull()
    expect(previewRequest(s)).toBeNull()
  })

  it('placement alone commits nothing — Close and Cancel agree on an empty create', () => {
    const s = openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS)
    expect(commitIntent(s, 'P-000001')).toBeNull()
    expect(cancel(s)).toEqual({ wrote: false, preservedFeatureId: null })
  })

  it('a drawn create session authors', () => {
    const s = drawLine(openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS))
    const intent = commitIntent(s, 'P-000001')
    expect(intent?.kind).toBe('mechanical.author_profile_sketch')
    expect(intent?.params.placement).toEqual(PLACEMENT)
    expect(intent?.params.sketch_feature_id).toBeUndefined()
  })

  it('an edit session replaces, and names its feature', () => {
    const s = drawLine(openEdit('feat_0001', BASELINE, FRAME, TARGET, OPTS), { u: 40, v: 0 }, { u: 60, v: 0.2 })
    const intent = commitIntent(s, 'P-000001')
    expect(intent?.kind).toBe('mechanical.replace_sketch_graph')
    expect(intent?.params.sketch_feature_id).toBe('feat_0001')
  })

  it('cancelling an edit preserves the feature and writes nothing', () => {
    const s = drawLine(openEdit('feat_0001', BASELINE, FRAME, TARGET, OPTS), { u: 40, v: 0 }, { u: 60, v: 0.2 })
    expect(cancel(s)).toEqual({ wrote: false, preservedFeatureId: 'feat_0001' })
  })

  it('an untouched edit re-sends the committed records under their OWN ids', () => {
    const s = openEdit('feat_0001', BASELINE, FRAME, TARGET, OPTS)
    expect(currentProfile(s)).toEqual(BASELINE)
    // ...but there is no work, so Close makes no transaction (the engine
    // would refuse the no-op anyway; not sending it is the honest form).
    expect(commitIntent(s, 'P-000001')).toBeNull()
  })

  it('an edit keeps every untouched record identical while adding new ones', () => {
    const s = drawLine(openEdit('feat_0001', BASELINE, FRAME, TARGET, OPTS), { u: 40, v: 0 }, { u: 60, v: 0.2 })
    const profile = currentProfile(s)
    // the survival law lives in the engine, but the payload must GIVE it the
    // chance: preserved ids, byte-identical structure
    expect(profile?.points?.slice(0, 2)).toEqual(BASELINE.points)
    expect(profile?.segments?.[0]).toEqual(BASELINE.segments?.[0])
    expect(profile?.facts?.[0]).toEqual(BASELINE.facts?.[0])
    expect(profile?.points).toHaveLength(4)
  })
})

describe('drawing', () => {
  it('a two-click line completes itself and re-arms the tool', () => {
    let s = openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS)
    s = commitPoint(s, { u: 0, v: 0 })
    expect(s.parts).toHaveLength(0)
    s = commitPoint(s, { u: 20, v: 0.4 })
    expect(s.parts).toHaveLength(1)
    expect(s.tool.pending).toEqual([]) // ready for the next line
  })

  it('drawing several shapes accumulates ONE graph', () => {
    let s = drawLine(openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS))
    s = setTool(s, 'circle')
    s = commitPoint(commitPoint(s, { u: 40, v: 5 }), { u: 43, v: 5 })
    const profile = currentProfile(s)
    expect(profile?.segments).toHaveLength(1)
    expect(profile?.circles).toHaveLength(1)
    expect(profileError('test', profile)).toBeNull()
  })

  it('a polyline waits for an explicit end', () => {
    let s = setTool(openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS), 'polyline')
    s = commitPoint(s, { u: 0, v: 0 })
    s = commitPoint(s, { u: 20, v: 0.2 })
    s = commitPoint(s, { u: 25, v: 15 })
    expect(s.parts).toHaveLength(0)
    s = endTool(s)
    expect(s.parts).toHaveLength(1)
    expect(currentProfile(s)?.segments).toHaveLength(2)
  })

  it('a polyline can close its run', () => {
    let s = setTool(openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS), 'polyline')
    for (const p of [{ u: 0, v: 0 }, { u: 20, v: 0 }, { u: 10, v: 15 }]) s = commitPoint(s, p)
    s = endTool(s, { closed: true })
    expect(currentProfile(s)?.segments).toHaveLength(3)
  })

  it('a single stray click is dropped, never a degenerate entity', () => {
    let s = setTool(openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS), 'polyline')
    s = commitPoint(s, { u: 5, v: 5 })
    s = endTool(s)
    expect(s.parts).toHaveLength(0)
    expect(currentProfile(s)).toBeNull()
  })

  it('a zero-size rectangle is dropped rather than sent', () => {
    let s = setTool(openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS), 'rectangle')
    s = commitPoint(commitPoint(s, { u: 5, v: 5 }), { u: 5, v: 5 })
    expect(s.parts).toHaveLength(0)
    expect(s.tool.pending).toEqual([])
  })

  it('switching tools abandons the in-progress run without half-committing', () => {
    let s = setTool(openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS), 'polyline')
    s = commitPoint(s, { u: 0, v: 0 })
    s = commitPoint(s, { u: 20, v: 0 })
    s = setTool(s, 'circle')
    expect(s.parts).toHaveLength(0)
    expect(s.tool).toEqual({ kind: 'circle', pending: [], cursor: null })
  })

  it('undo drops the last completed shape only', () => {
    let s = drawLine(openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS))
    s = drawLine(s, { u: 40, v: 0 }, { u: 60, v: 0.2 })
    expect(s.parts).toHaveLength(2)
    s = undoLastPart(s)
    expect(s.parts).toHaveLength(1)
    expect(undoLastPart(openCreate(PLACEMENT, 'd', FRAME, TARGET, OPTS)).parts).toEqual([])
  })

  it('the cursor is live state and never becomes geometry', () => {
    let s = commitPoint(openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS), { u: 0, v: 0 })
    s = moveCursor(s, { u: 99, v: 99 })
    expect(s.parts).toHaveLength(0)
    expect(currentProfile(s)).toBeNull()
  })
})

describe('the preview is a READ that never ends the session', () => {
  it('the request carries the owner the engine expects', () => {
    const create = previewRequest(drawLine(openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS)))
    expect(create?.owner).toEqual({ placement: PLACEMENT, candidateKey: 'draft1' })
    const edit = previewRequest(openEdit('feat_0001', BASELINE, FRAME, TARGET, OPTS))
    expect(edit?.owner).toEqual({ sketchFeatureId: 'feat_0001' })
  })

  it('preview and commit are built from the SAME graph', () => {
    const s = drawLine(openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS))
    expect(previewRequest(s)?.profile).toEqual(commitIntent(s, 'P-000001')?.params.profile)
  })

  it('a refusal is recorded, and the drawing survives it', () => {
    let s = drawLine(openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS))
    s = applyPreview(s, { preview: null, refusal: { message: 'segment collapsed' } })
    expect(s.refusal).toBe('segment collapsed')
    expect(s.parts).toHaveLength(1)
    // and the user can keep drawing straight out of the refused state
    s = drawLine(s, { u: 40, v: 0 }, { u: 60, v: 0.2 })
    expect(s.parts).toHaveLength(2)
  })

  it('a successful preview clears a previous refusal', () => {
    let s = drawLine(openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS))
    s = applyPreview(s, { preview: null, refusal: { message: 'bad' } })
    const preview = {
      owner: { candidate_key: 'draft1' },
      frame: { origin_mm: [0, 0, 0], u_axis: [1, 0, 0], v_axis: [0, 1, 0], normal: [0, 0, 1] },
      points: [],
      segments: [],
      circles: [],
      annotations: [],
      constraint_glyphs: [],
    } as unknown as NonNullable<ProfileSessionState['preview']>
    s = applyPreview(s, { preview, refusal: null })
    expect(s.refusal).toBeNull()
    expect(s.preview).toBe(preview)
  })
})

describe('every session payload passes the wire boundary the commit goes through', () => {
  it.each([
    ['a line', drawLine(openCreate(PLACEMENT, 'd', FRAME, TARGET, OPTS))],
    [
      'a rectangle',
      commitPoint(
        commitPoint(setTool(openCreate(PLACEMENT, 'd', FRAME, TARGET, OPTS), 'rectangle'), { u: 0, v: 0 }),
        { u: 30, v: 12 },
      ),
    ],
    ['an edited sketch', drawLine(openEdit('feat_0001', BASELINE, FRAME, TARGET, OPTS), { u: 40, v: 0 }, { u: 60, v: 0.2 })],
  ])('%s', (_label, s) => {
    const intent = commitIntent(s as ProfileSessionState, 'P-000001')
    expect(profileError('test', intent?.params.profile)).toBeNull()
  })
})
