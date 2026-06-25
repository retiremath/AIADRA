import { describe, it, expect } from 'vitest'
import { createSelectionStore, kindIsPickable } from './store'

describe('selectionStore', () => {
  it('starts empty with both filter kinds on', () => {
    const s = createSelectionStore()
    expect(s.getSnapshot().selected).toBeNull()
    expect(s.getSnapshot().filter).toEqual({ face: true, edge: true })
  })

  it('sets and clears selection, notifying subscribers', () => {
    const s = createSelectionStore()
    let hits = 0
    s.subscribe(() => hits++)
    s.setSelected({ kind: 'edge', id: 'feat_2/skp_1:edge:x' })
    expect(s.getSnapshot().selected).toEqual({ kind: 'edge', id: 'feat_2/skp_1:edge:x' })
    s.clearSelected()
    expect(s.getSnapshot().selected).toBeNull()
    expect(hits).toBe(2)
  })

  it('keeps a stable snapshot when selecting the same id (no churn)', () => {
    const s = createSelectionStore()
    s.setSelected({ kind: 'face', id: 'f1' })
    const snap = s.getSnapshot()
    let hits = 0
    s.subscribe(() => hits++)
    s.setSelected({ kind: 'face', id: 'f1' }) // same → no emit, same ref
    expect(s.getSnapshot()).toBe(snap)
    expect(hits).toBe(0)
  })

  it('toggles a filter kind', () => {
    const s = createSelectionStore()
    s.toggleFilterKind('face')
    expect(s.getSnapshot().filter.face).toBe(false)
    expect(kindIsPickable(s.getSnapshot(), 'face')).toBe(false)
    expect(kindIsPickable(s.getSnapshot(), 'edge')).toBe(true)
  })

  it('drops a selection whose kind is filtered out', () => {
    const s = createSelectionStore()
    s.setSelected({ kind: 'face', id: 'f1' })
    s.setFilterKind('face', false)
    expect(s.getSnapshot().selected).toBeNull()
  })

  it('keeps a selection whose kind stays enabled', () => {
    const s = createSelectionStore()
    s.setSelected({ kind: 'edge', id: 'e1' })
    s.setFilterKind('face', false) // unrelated kind
    expect(s.getSnapshot().selected).toEqual({ kind: 'edge', id: 'e1' })
  })
})
