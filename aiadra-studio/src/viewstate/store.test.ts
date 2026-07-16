import { describe, expect, it, vi } from 'vitest'
import { createViewStateStore, toCommandContext, type ViewState } from './store'

const initial = (): ViewState => ({
  mode: 'shading-edges',
  datumsVisible: true,
  hasCanonicalPart: false,
  hasReferenceGeometry: false,
})

describe('view-state store', () => {
  it('get/set + subscribe fires on a real change only', () => {
    const s = createViewStateStore(initial())
    const fn = vi.fn()
    const unsub = s.subscribe(fn)
    s.setMode('wireframe')
    expect(s.getSnapshot().mode).toBe('wireframe')
    expect(fn).toHaveBeenCalledTimes(1)
    s.setMode('wireframe') // no-op — same value
    expect(fn).toHaveBeenCalledTimes(1)
    unsub()
    s.setMode('shading')
    expect(fn).toHaveBeenCalledTimes(1) // unsubscribed
  })

  it('snapshot ref is stable until a change (useSyncExternalStore safety)', () => {
    const s = createViewStateStore(initial())
    const a = s.getSnapshot()
    expect(s.getSnapshot()).toBe(a) // same ref, no churn
    s.setMode('wireframe') // a real change
    expect(s.getSnapshot()).not.toBe(a) // new ref on real change
  })

  it('setSceneFacts updates scene facts independently', () => {
    const s = createViewStateStore(initial())
    s.setSceneFacts({ hasCanonicalPart: true })
    expect(s.getSnapshot().hasCanonicalPart).toBe(true)
    expect(s.getSnapshot().hasReferenceGeometry).toBe(false)
    s.setSceneFacts({ hasReferenceGeometry: true })
    expect(s.getSnapshot().hasReferenceGeometry).toBe(true)
  })

  it('toCommandContext derives hasRenderableScene (Codex1 B1)', () => {
    expect(toCommandContext({ ...initial(), hasReferenceGeometry: true }).hasRenderableScene).toBe(true)
    expect(toCommandContext({ ...initial(), hasCanonicalPart: true }).hasRenderableScene).toBe(true)
    expect(toCommandContext(initial()).hasRenderableScene).toBe(false)
  })
})
