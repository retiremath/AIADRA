import { describe, it, expect } from 'vitest'
import { createFeatureSessionStore } from './featureSession'

describe('feature operation session', () => {
  it('starts idle', () => {
    const s = createFeatureSessionStore().getSnapshot()
    expect(s.active).toBe(false)
    expect(s.phase).toBe('idle')
    expect(s.featureKind).toBeNull()
  })

  it('start() activates an editing session with the given params', () => {
    const store = createFeatureSessionStore()
    store.start('extrude', { width_mm: 80, height_mm: 50, depth_mm: 6 })
    const s = store.getSnapshot()
    expect(s.active).toBe(true)
    expect(s.featureKind).toBe('extrude')
    expect(s.phase).toBe('editing')
    expect(s.params).toEqual({ width_mm: 80, height_mm: 50, depth_mm: 6 })
  })

  it('setParam() updates params + returns to editing (clears prior message)', () => {
    const store = createFeatureSessionStore()
    store.start('extrude', { width_mm: 80, height_mm: 50, depth_mm: 6 })
    store.setPhase('error', 'boom')
    store.setParam('width_mm', 120)
    const s = store.getSnapshot()
    expect(s.params.width_mm).toBe(120)
    expect(s.phase).toBe('editing')
    expect(s.message).toBeNull()
  })

  it('setPhase() is a no-op when unchanged (stable ref)', () => {
    const store = createFeatureSessionStore()
    store.start('extrude', { width_mm: 80 })
    store.setPhase('busy', 'x')
    const a = store.getSnapshot()
    store.setPhase('busy', 'x')
    expect(store.getSnapshot()).toBe(a)
  })

  it('setCommitted() records the object ref + committed phase', () => {
    const store = createFeatureSessionStore()
    store.start('extrude', { width_mm: 80 })
    store.setCommitted('P-000001')
    const s = store.getSnapshot()
    expect(s.phase).toBe('committed')
    expect(s.objectRef).toBe('P-000001')
  })

  it('cancel() returns to idle; actions are no-ops after cancel', () => {
    const store = createFeatureSessionStore()
    store.start('extrude', { width_mm: 80 })
    store.cancel()
    expect(store.getSnapshot().active).toBe(false)
    store.setParam('width_mm', 10) // no active session → ignored
    expect(store.getSnapshot().phase).toBe('idle')
  })

  it('subscribe fires on real change only', () => {
    const store = createFeatureSessionStore()
    let hits = 0
    const off = store.subscribe(() => hits++)
    store.start('extrude', { width_mm: 80 })
    expect(hits).toBe(1)
    store.setPhase('editing') // already editing, message null → no change
    expect(hits).toBe(1)
    off()
  })
})
