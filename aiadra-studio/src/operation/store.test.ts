import { describe, it, expect } from 'vitest'
import {
  createOperationStore,
  selectedCandidate,
  type ActiveConfigurator,
  type Candidate,
} from './store'

// A tiny deterministic stub configurator so the store tests are isolated from
// the bracket configurator. `propose` returns one candidate per answered
// "count", else two defaults.
function stubConfigurator(): ActiveConfigurator {
  const cand = (id: string, params: Record<string, number>): Candidate => ({
    id,
    label: id,
    sourceId: `src/${id}`,
    params,
    validationStatus: 'valid',
    provenance: { sourceConfigurator: 'test:stub', transient: true },
  })
  return {
    id: 'test:stub',
    name: 'Stub',
    defaultParams: { size_mm: 10 },
    propose: (answers, params) => {
      if (answers.pick === 'one') return [cand('a', params)]
      return [cand('a', params), cand('b', params)]
    },
  }
}

describe('operation store', () => {
  it('starts idle', () => {
    const s = createOperationStore().getSnapshot()
    expect(s.phase).toBe('idle')
    expect(s.configuratorId).toBeNull()
    expect(s.candidates).toEqual([])
    expect(s.selectedCandidateId).toBeNull()
    expect(s.dirty).toBe(false)
  })

  it('start() elicits, seeds default params + candidates, selects the first', () => {
    const store = createOperationStore()
    store.start(stubConfigurator())
    const s = store.getSnapshot()
    expect(s.phase).toBe('eliciting')
    expect(s.configuratorId).toBe('test:stub')
    expect(s.params).toEqual({ size_mm: 10 })
    expect(s.candidates.map((c) => c.id)).toEqual(['a', 'b'])
    expect(s.selectedCandidateId).toBe('a')
    expect(s.dirty).toBe(false)
  })

  it('answer() re-proposes, advances to proposing, marks dirty', () => {
    const store = createOperationStore()
    store.start(stubConfigurator())
    store.answer('pick', 'one')
    const s = store.getSnapshot()
    expect(s.phase).toBe('proposing')
    expect(s.answers).toEqual({ pick: 'one' })
    expect(s.candidates.map((c) => c.id)).toEqual(['a'])
    expect(s.selectedCandidateId).toBe('a') // survived the re-propose
    expect(s.dirty).toBe(true)
  })

  it('setParam() re-proposes with the new params, advances to refining', () => {
    const store = createOperationStore()
    store.start(stubConfigurator())
    store.setParam('size_mm', 25)
    const s = store.getSnapshot()
    expect(s.phase).toBe('refining')
    expect(s.params).toEqual({ size_mm: 25 })
    expect(s.candidates[0].params).toEqual({ size_mm: 25 })
    expect(s.dirty).toBe(true)
  })

  it('selectCandidate() is a pure state change; ignores unknown / same ids', () => {
    const store = createOperationStore()
    store.start(stubConfigurator())
    const before = store.getSnapshot()
    store.selectCandidate('nope') // unknown → no-op (no throw, no change)
    expect(store.getSnapshot()).toBe(before)
    store.selectCandidate('b')
    expect(store.getSnapshot().selectedCandidateId).toBe('b')
    const after = store.getSnapshot()
    store.selectCandidate('b') // same → no-op, stable ref
    expect(store.getSnapshot()).toBe(after)
  })

  it('cancel() returns to idle and detaches the configurator', () => {
    const store = createOperationStore()
    store.start(stubConfigurator())
    store.cancel()
    expect(store.getSnapshot().phase).toBe('idle')
    // After cancel, answer() is a no-op (no active configurator).
    store.answer('pick', 'one')
    expect(store.getSnapshot().phase).toBe('idle')
  })

  it('subscribe fires on real change; snapshot ref is stable when unchanged', () => {
    const store = createOperationStore()
    let hits = 0
    const off = store.subscribe(() => {
      hits++
    })
    store.start(stubConfigurator())
    expect(hits).toBe(1)
    store.selectCandidate('a') // already selected (first) → no emit
    expect(hits).toBe(1)
    store.selectCandidate('b')
    expect(hits).toBe(2)
    off()
    store.cancel()
    expect(hits).toBe(2) // unsubscribed
  })

  it('selectedCandidate() resolves the selection', () => {
    const store = createOperationStore()
    store.start(stubConfigurator())
    expect(selectedCandidate(store.getSnapshot())?.id).toBe('a')
    store.selectCandidate('b')
    expect(selectedCandidate(store.getSnapshot())?.id).toBe('b')
  })
})
