import { describe, it, expect } from 'vitest'
import {
  abandonRun,
  applyPreview,
  cancel,
  commitIntent,
  commitPoint,
  currentProfile,
  endTool,
  hasRun,
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

// The chain grammar (W-2): a single line is click·click·end — the end is the
// viewport's middle-click / the keyboard's Enter, both of which call endTool.
const drawLine = (s: ProfileSessionState, a = { u: 0, v: 0 }, b = { u: 20, v: 0.4 }) =>
  endTool(commitPoint(commitPoint(s, a), b))

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

describe('drawing — the line CHAIN (W-2)', () => {
  it('clicks accumulate as one chain; the end gesture completes and re-arms it', () => {
    let s = openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS)
    s = commitPoint(s, { u: 0, v: 0 })
    s = commitPoint(s, { u: 20, v: 0.4 })
    // two clicks are NOT a finished line — the chain is open until ended
    expect(s.parts).toHaveLength(0)
    expect(hasRun(s)).toBe(true)
    s = endTool(s)
    expect(s.parts).toHaveLength(1)
    expect(hasRun(s)).toBe(false)
    expect(s.tool.pending).toEqual([]) // ready for the next run
  })

  it('a longer chain shares vertices: N clicks → N−1 segments off shared points', () => {
    let s = openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS)
    for (const p of [{ u: 0, v: 0 }, { u: 20, v: 0.2 }, { u: 25, v: 15 }]) s = commitPoint(s, p)
    expect(s.parts).toHaveLength(0)
    s = endTool(s)
    const profile = currentProfile(s)
    expect(profile?.points).toHaveLength(3)
    expect(profile?.segments).toHaveLength(2)
    // the shared vertex: segment 1 ends where segment 2 starts
    expect(profile?.segments?.[0].end).toEqual(profile?.segments?.[1].start)
  })

  it('clicking the FIRST point closes the ring (three or more vertices down)', () => {
    let s = openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS)
    for (const p of [{ u: 0, v: 0 }, { u: 20, v: 0 }, { u: 10, v: 15 }]) s = commitPoint(s, p)
    s = commitPoint(s, { u: 0.4, v: -0.3 }, { closeToleranceMm: 1 })
    expect(s.parts).toHaveLength(1)
    const profile = currentProfile(s)
    expect(profile?.points).toHaveLength(3) // the close click mints NO vertex
    expect(profile?.segments).toHaveLength(3) // …but the ring closes
  })

  it('a first-point click with only two vertices down chains — it cannot close a 2-ring', () => {
    let s = openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS)
    s = commitPoint(s, { u: 0, v: 0 })
    s = commitPoint(s, { u: 20, v: 0 })
    s = commitPoint(s, { u: 0.4, v: 0.3 }, { closeToleranceMm: 1 })
    expect(s.parts).toHaveLength(0)
    expect(s.tool.pending).toHaveLength(3)
  })

  it('a click on the previous point is ignored — never a zero-length segment', () => {
    let s = openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS)
    s = commitPoint(s, { u: 0, v: 0 })
    s = commitPoint(s, { u: 0.2, v: 0.1 }, { closeToleranceMm: 1 })
    expect(s.tool.pending).toHaveLength(1)
    // …and an EXACT duplicate is ignored even with no tolerance supplied
    s = commitPoint(s, { u: 0, v: 0 })
    expect(s.tool.pending).toHaveLength(1)
  })

  it('Escape abandons the run; completed shapes stay', () => {
    let s = drawLine(openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS))
    s = commitPoint(s, { u: 40, v: 0 })
    s = commitPoint(s, { u: 60, v: 5 })
    expect(hasRun(s)).toBe(true)
    s = abandonRun(s)
    expect(hasRun(s)).toBe(false)
    expect(s.parts).toHaveLength(1) // the finished line survives
    expect(s.tool.kind).toBe('line') // the tool stays armed
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

  it('a single stray click is dropped, never a degenerate entity', () => {
    let s = openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS)
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
    let s = openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS)
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

describe('the engine previews per completed SEGMENT (Codex11 B1)', () => {
  it('click 1 previews nothing — a vertex is not yet a segment', () => {
    const s = commitPoint(openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS), { u: 0, v: 0 })
    expect(previewRequest(s)).toBeNull()
  })

  it('click 2 previews the one-segment graph, snap fact included', () => {
    let s = openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS)
    s = commitPoint(s, { u: 0, v: 0 })
    s = commitPoint(s, { u: 20, v: 0.4 }) // near-horizontal at tol 3°
    const req = previewRequest(s)
    expect(req?.profile.points).toHaveLength(2)
    expect(req?.profile.segments).toHaveLength(1)
    expect(req?.profile.facts?.map((f) => f.kind)).toEqual(['horizontal'])
  })

  it('click 3 previews two segments off the SHARED vertex', () => {
    let s = openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS)
    for (const p of [{ u: 0, v: 0 }, { u: 20, v: 0.2 }, { u: 25, v: 15 }]) s = commitPoint(s, p)
    const req = previewRequest(s)
    expect(req?.profile.points).toHaveLength(3)
    expect(req?.profile.segments).toHaveLength(2)
    expect(req?.profile.segments?.[0].end).toEqual(req?.profile.segments?.[1].start)
  })

  it('the end gesture changes NOTHING — the before/after graphs are byte-identical', () => {
    let s = openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS)
    for (const p of [{ u: 0, v: 0 }, { u: 20, v: 0.2 }, { u: 25, v: 15 }]) s = commitPoint(s, p)
    const before = previewRequest(s)
    const after = previewRequest(endTool(s))
    expect(JSON.stringify(after?.profile)).toBe(JSON.stringify(before?.profile))
  })

  it('first-point close DOES change the graph — the closing segment is new geometry', () => {
    let s = openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS)
    for (const p of [{ u: 0, v: 0 }, { u: 20, v: 0 }, { u: 10, v: 15 }]) s = commitPoint(s, p)
    const open = previewRequest(s)
    const closed = previewRequest(commitPoint(s, { u: 0, v: 0 }, { closeToleranceMm: 1 }))
    expect(open?.profile.segments).toHaveLength(2)
    expect(closed?.profile.segments).toHaveLength(3)
  })

  it('Close settlement commits exactly the graph most recently previewed', () => {
    let s = openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS)
    s = commitPoint(s, { u: 0, v: 0 })
    s = commitPoint(s, { u: 20, v: 0.4 })
    const previewed = previewRequest(s)?.profile
    const intent = commitIntent(endTool(s), 'P-000001') // what close() settles to
    expect(JSON.stringify(intent?.params.profile)).toBe(JSON.stringify(previewed))
  })

  it('abandoning the run removes it from the graph', () => {
    let s = drawLine(openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS))
    s = commitPoint(s, { u: 40, v: 0 })
    s = commitPoint(s, { u: 60, v: 5 })
    expect(previewRequest(s)?.profile.segments).toHaveLength(2)
    expect(previewRequest(abandonRun(s))?.profile.segments).toHaveLength(1)
  })

  it('shrinking the graph to EMPTY clears the solved result — no stale overlay', () => {
    const solved = { points: [] } as unknown as NonNullable<ProfileSessionState['preview']>
    // abandon the only run
    let s = openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS)
    s = commitPoint(commitPoint(s, { u: 0, v: 0 }), { u: 20, v: 0 })
    s = applyPreview(s, { preview: solved, refusal: null })
    expect(abandonRun(s).preview).toBeNull()
    // undo the only part
    let t = drawLine(openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS))
    t = applyPreview(t, { preview: solved, refusal: null })
    expect(undoLastPart(t).preview).toBeNull()
    // …but with geometry REMAINING, the last solve stands until replaced
    let u = drawLine(openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS))
    u = commitPoint(commitPoint(u, { u: 40, v: 0 }), { u: 60, v: 5 })
    u = applyPreview(u, { preview: solved, refusal: null })
    expect(abandonRun(u).preview).not.toBeNull()
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
