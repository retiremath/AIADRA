/**
 * The sketch commit invocation floors (pass sketch-ribbon-1 increment 2;
 * Codex1 B4). The lifecycle has ONE persistent owner; sketchCommit.ts is
 * pure invocation code — these floors prove the two identity hazards Codex
 * named CANNOT occur: (1) a re-render during an unresolved commit must not
 * enable Escape/Cancel around the real run; (2) after a FAILED commit the
 * retained backend session must still roll back through the SAME lifecycle.
 * Plus: the chained hand-back and the target-authority refusal move intact.
 */
import { describe, expect, it, vi } from 'vitest'
import { createSessionLifecycle } from '../authoring/sessionLifecycle'
import { createAuthoringSessionStore } from '../authoring/authoringSession'
import type { AuthoringBackend } from '../authoring/backend'
import type { PartContextStore } from '../authoring/partContext'
import { cancelSketch, runSketchOk, selectSketchOps, sketchHint } from './sketchCommit'

const CONTEXT = { getSnapshot: () => ({ generation: 1 }) } as unknown as PartContextStore

function fakeBackend(behavior: { commit: 'ok' | 'throw'; gate?: Promise<void> }) {
  const open = new Set<string>()
  let n = 0
  const backend = {
    isReal: false,
    async begin() {
      const sessionId = `s-${++n}`
      open.add(sessionId)
      return { sessionId, createdFeatureIds: [['feat_0001']] }
    },
    async simulate() {
      return { valid: true }
    },
    async commit(sid: string) {
      if (behavior.gate) await behavior.gate
      if (behavior.commit === 'throw') throw new Error('commit exploded')
      open.delete(sid)
      return { display: { tag: 'fresh' } }
    },
    async rollback(sid: string) {
      open.delete(sid)
    },
  } as unknown as AuthoringBackend
  return { backend, open }
}

const drawnStore = () => {
  const store = createAuthoringSessionStore()
  store.startSketch({
    tool: 'contour', partName: 'S', partNumber: 'P-1',
    targetPart: null, targetAuth: null, plane: 'xy', generation: 1,
  })
  store.addPoint({ x: 0, y: 0 })
  store.addPoint({ x: 20, y: 0 })
  store.addPoint({ x: 20, y: 20 })
  store.closeRing()
  return store
}

describe('the ONE lifecycle owner (Codex1 B4)', () => {
  it('a status re-render mid-commit cannot enable Cancel — the SAME lifecycle refuses it', async () => {
    let release!: () => void
    const gate = new Promise<void>((r) => { release = r })
    const { backend } = fakeBackend({ commit: 'ok', gate })
    const lifecycle = createSessionLifecycle(backend) // the persistent owner
    const store = drawnStore()
    const onClose = vi.fn()
    const running = runSketchOk(lifecycle, store, CONTEXT, {})
    await Promise.resolve() // the run has begun; the store re-rendered (busy)
    // any number of re-renders later, cancel goes to the SAME owner: refused
    cancelSketch(lifecycle, store, onClose)
    expect(onClose).not.toHaveBeenCalled()
    expect(store.getSnapshot().mode).toBe('sketch') // the session survived
    release()
    await running
    expect(store.getSnapshot().mode).toBe('idle') // the commit completed
  })

  it('after a FAILED commit, Cancel through the same lifecycle rolls back the retained session', async () => {
    const { backend, open } = fakeBackend({ commit: 'throw' })
    const lifecycle = createSessionLifecycle(backend)
    const store = drawnStore()
    await runSketchOk(lifecycle, store, CONTEXT, {})
    const st = store.getSnapshot()
    expect(st.mode === 'sketch' && st.phase).toBe('error')
    expect(open.size).toBe(1) // the failed backend session is RETAINED
    const onClose = vi.fn()
    cancelSketch(lifecycle, store, onClose)
    await Promise.resolve()
    await Promise.resolve()
    expect(open.size).toBe(0) // rolled back through the SAME owner
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(store.getSnapshot().mode).toBe('idle')
  })

  it('the chained hand-back moved intact: OK returns the sketch to Extrude, no backend touch', async () => {
    const { backend, open } = fakeBackend({ commit: 'ok' })
    const lifecycle = createSessionLifecycle(backend)
    const store = createAuthoringSessionStore()
    // the chained hand-off requires a live base-feature session (entry B)
    store.startExtrude(null)
    store.beginChainedSketch('xy', { number: 'P-1', name: 'S' }, 'contour', 1)
    store.addPoint({ x: 0, y: 0 })
    store.addPoint({ x: 20, y: 0 })
    store.addPoint({ x: 20, y: 20 })
    store.closeRing()
    await runSketchOk(lifecycle, store, CONTEXT, {})
    expect(open.size).toBe(0) // nothing began — the hand-back is store-only
    const st = store.getSnapshot()
    expect(st.mode).toBe('extrude')
  })

  it('the target-authority refusal moved intact (no captured tuple → error phase, nothing runs)', async () => {
    const { backend, open } = fakeBackend({ commit: 'ok' })
    const lifecycle = createSessionLifecycle(backend)
    const store = createAuthoringSessionStore()
    store.startSketch({
      tool: 'contour', partName: null, partNumber: null,
      targetPart: { number: 'P-1', name: 'S' }, targetAuth: null,
      plane: 'xy', generation: 1,
    })
    store.addPoint({ x: 0, y: 0 })
    store.addPoint({ x: 20, y: 0 })
    store.addPoint({ x: 20, y: 20 })
    store.closeRing()
    await runSketchOk(lifecycle, store, CONTEXT, {})
    const st = store.getSnapshot()
    expect(st.mode === 'sketch' && st.phase).toBe('error')
    expect(st.mode === 'sketch' && st.message).toMatch(/target authority/)
    expect(open.size).toBe(0)
  })
})

describe('the moved pure helpers', () => {
  it('selectSketchOps: sketch-only for a target; create+sketch otherwise (byte-faithful selection)', () => {
    const store = drawnStore()
    const st = store.getSnapshot()
    if (st.mode !== 'sketch') throw new Error('unreachable')
    const withTarget = selectSketchOps(st, { number: 'P-9', name: 'T' }, 'P-9', 'T')
    expect(withTarget.map((o) => o.kind)).toEqual(['mechanical.add_sketch_feature'])
    const createNew = selectSketchOps(st, null, 'P-1', 'S')
    expect(createNew.map((o) => o.kind)).toEqual(['create_part', 'mechanical.add_sketch_feature'])
  })

  it('sketchHint moved verbatim (ready copy for a closed contour)', () => {
    const store = drawnStore()
    const st = store.getSnapshot()
    if (st.mode !== 'sketch') throw new Error('unreachable')
    expect(sketchHint(st)).toBe('Ready — OK commits the sketch.')
  })
})
