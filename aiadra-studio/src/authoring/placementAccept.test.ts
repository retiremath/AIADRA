/**
 * The ACTUAL Sketch accept (I3; Codex3 B5): the function the App calls, with
 * REAL stores — a real Part context (ready through `setPart`) whose captured
 * target rides the dialog, the real authoring store. Proves: accept opens the
 * drawing session ONCE with the SAME captured target and the mirror frame;
 * a duplicate accept is inert; a real context change (`clear()`, a different
 * Part) before accept refuses fail-closed and opens nothing.
 */
import { describe, expect, it } from 'vitest'
import { createAuthoringSessionStore } from './authoringSession'
import { PLACEMENT_CONTEXT_CHANGED, acceptSketchPlacement } from './placementAccept'
import { captureAuthoringTarget, createPartContextStore, type InspectFetcher } from './partContext'

const io = (fetch: InspectFetcher) => ({ fetchInspect: fetch })
const RAW = (number: string) => ({
  sidecar: { object: { type: 'Part', number, name: `Part ${number}`, uuid: `u-${number}` }, feature: [] },
})

async function readyContext(number = 'P-000001') {
  const context = createPartContextStore()
  await context.setPart('ws-1', number, io(async () => RAW(number)))
  expect(context.getSnapshot().inspection.status).toBe('ready')
  return context
}

function dialogOn(context: ReturnType<typeof createPartContextStore>) {
  const snap = context.getSnapshot()
  const captured = captureAuthoringTarget(snap)
  expect(captured).not.toBeNull()
  const store = createAuthoringSessionStore()
  store.startPlacementPick(snap.generation, { number: snap.partNumber!, name: 'x' }, { accept: 'sketch', capturedTarget: captured })
  store.resolvePlanePick('xy')
  store.setPlacementMember('orientationRef', 'zx')
  store.setPlacementMember('orientation', 'top')
  store.setPlacementMember('normalSide', 'negative')
  return { store, captured: captured! }
}

describe('acceptSketchPlacement (the production accept path, real stores)', () => {
  it('opens the drawing session ONCE with the captured target and the mirror frame; a duplicate accept is inert', async () => {
    const context = await readyContext()
    const { store, captured } = dialogOn(context)
    const opened: unknown[] = []
    const out = acceptSketchPlacement(store, context.getSnapshot(), (p, f, t) => opened.push({ p, f, t }))
    expect(out.kind).toBe('opened')
    if (out.kind !== 'opened') throw new Error('unreachable')
    expect(out.target).toEqual(captured)
    expect(out.placement).toEqual({
      support: { kind: 'principal', orientation: 'xy' },
      orientation_ref: { kind: 'principal', orientation: 'zx' },
      orientation: 'top',
      normal_side: 'negative',
    })
    expect(out.frame.u.map((x) => x + 0)).toEqual([-1, 0, 0])
    expect(out.frame.normal.map((x) => x + 0)).toEqual([0, 0, -1])
    expect(opened).toHaveLength(1)
    expect(store.getSnapshot().mode).toBe('idle') // the owner retired
    // duplicate accept (a second click in the same event batch): nothing
    expect(acceptSketchPlacement(store, context.getSnapshot(), (p, f, t) => opened.push({ p, f, t })).kind).toBe('ignored')
    expect(opened).toHaveLength(1)
  })

  it('a REAL context change before accept refuses fail-closed and opens nothing', async () => {
    const context = await readyContext()
    const { store } = dialogOn(context)
    context.clear() // the workspace switch / reopen path — the generation advances
    expect(context.getSnapshot().inspection.status).not.toBe('ready')
    const opened: unknown[] = []
    const out = acceptSketchPlacement(store, context.getSnapshot(), () => opened.push(1))
    expect(out).toEqual({ kind: 'refused', reason: PLACEMENT_CONTEXT_CHANGED })
    expect(opened).toHaveLength(0)
    expect(store.getSnapshot()).toMatchObject({ mode: 'placement', message: PLACEMENT_CONTEXT_CHANGED })
  })

  it('a different ready Part under the same store also refuses (the target is the CAPTURED one, never recaptured)', async () => {
    const context = await readyContext('P-000001')
    const { store } = dialogOn(context)
    await context.setPart('ws-1', 'P-000002', io(async () => RAW('P-000002')))
    expect(context.getSnapshot().inspection.status).toBe('ready')
    const out = acceptSketchPlacement(store, context.getSnapshot(), () => {})
    expect(out.kind).toBe('refused')
  })

  it('ignores every other state (no dialog; the References continuation; a busy dialog)', async () => {
    const context = await readyContext()
    const idle = createAuthoringSessionStore()
    expect(acceptSketchPlacement(idle, context.getSnapshot(), () => {}).kind).toBe('ignored')
    const refs = createAuthoringSessionStore()
    refs.startPlacementPick(context.getSnapshot().generation, { number: 'P-000001', name: 'x' })
    refs.resolvePlanePick('zx')
    expect(acceptSketchPlacement(refs, context.getSnapshot(), () => {}).kind).toBe('ignored')
    const { store } = dialogOn(context)
    store.setPlacementBusy(true)
    expect(acceptSketchPlacement(store, context.getSnapshot(), () => {}).kind).toBe('ignored')
  })
})
