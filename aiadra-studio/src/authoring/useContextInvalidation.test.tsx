/**
 * Context invalidation through the App's ACTUAL wiring (I3; Codex3 B1): the
 * hook subscribes to the REAL context store, so a real `clear()` (workspace
 * switch / reopen) must kill an open placement dialog — owner, collector and
 * capture — without anyone calling the store method directly. A BUSY
 * placement (a commit in flight) is left to its runner. The legacy pick and
 * sketch modes keep dying the same way.
 */
// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { createAuthoringSessionStore } from './authoringSession'
import { captureAuthoringTarget, createPartContextStore, type InspectFetcher } from './partContext'
import { useContextInvalidation, v1Invalidation } from './useContextInvalidation'

const io = (fetch: InspectFetcher) => ({ fetchInspect: fetch })
const RAW = (number: string) => ({
  sidecar: { object: { type: 'Part', number, name: `Part ${number}`, uuid: `u-${number}` }, feature: [] },
})

async function ready() {
  const context = createPartContextStore()
  await context.setPart('ws-1', 'P-000001', io(async () => RAW('P-000001')))
  return context
}

describe('useContextInvalidation (the ONE wiring, real stores)', () => {
  it('a REAL context clear() kills an open placement dialog — owner, armed collector, capture', async () => {
    const context = await ready()
    const store = createAuthoringSessionStore()
    const snap = context.getSnapshot()
    store.startPlacementPick(snap.generation, { number: 'P-000001', name: 'x' }, { accept: 'sketch', capturedTarget: captureAuthoringTarget(snap) })
    store.resolvePlanePick('xy')
    store.setPlacementCollector('reference')
    renderHook(() => useContextInvalidation(context, store))
    expect(store.getSnapshot()).toMatchObject({ mode: 'placement', activeCollector: 'reference' })
    act(() => context.clear())
    expect(store.getSnapshot().mode).toBe('idle')
  })

  it('a BUSY placement (commit in flight) is NOT killed — its runner owns the terminal', async () => {
    const context = await ready()
    const store = createAuthoringSessionStore()
    store.startPlacementPick(context.getSnapshot().generation, { number: 'P-000001', name: 'x' })
    store.resolvePlanePick('zx')
    store.setPlacementBusy(true)
    renderHook(() => useContextInvalidation(context, store))
    act(() => context.clear())
    expect(store.getSnapshot()).toMatchObject({ mode: 'placement', busy: true })
  })

  it('the legacy pick and sketch modes die the same way', async () => {
    const context = await ready()
    const g = context.getSnapshot().generation
    const pick = createAuthoringSessionStore()
    pick.startPlanePick({ targetPart: null, targetAuth: null }, g)
    renderHook(() => useContextInvalidation(context, pick))
    act(() => context.clear())
    expect(pick.getSnapshot().mode).toBe('idle')
    const context2 = await ready()
    const sketch = createAuthoringSessionStore()
    sketch.startSketch({ plane: 'xy', generation: context2.getSnapshot().generation, partName: null, partNumber: null, targetPart: null, targetAuth: null })
    renderHook(() => useContextInvalidation(context2, sketch))
    act(() => context2.clear())
    expect(sketch.getSnapshot().mode).toBe('idle')
  })

  it('the pure rule: generation-bound nonterminal states invalidate; idle and busy placement do not', () => {
    const store = createAuthoringSessionStore()
    expect(v1Invalidation(store.getSnapshot(), 9)).toBe(false)
    store.startPlacementPick(3, { number: 'P-1', name: 'x' })
    store.resolvePlanePick('xy')
    expect(v1Invalidation(store.getSnapshot(), 3)).toBe(false)
    expect(v1Invalidation(store.getSnapshot(), 4)).toBe(true)
    store.setPlacementBusy(true)
    expect(v1Invalidation(store.getSnapshot(), 4)).toBe(false)
  })
})
