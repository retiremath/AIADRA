import { describe, it, expect } from 'vitest'
import { createSketchStore } from './sketchStore'

describe('sketch session metadata scoping (Codex2 B1)', () => {
  it('start with New-dialog meta carries it for THIS session only', () => {
    const s = createSketchStore()
    s.start({ partName: 'Mounting bracket', partNumber: 'P-123456' })
    expect(s.getSnapshot().partName).toBe('Mounting bracket')
    expect(s.getSnapshot().partNumber).toBe('P-123456')
  })

  it('cancel clears the metadata with the session (nothing sticky)', () => {
    const s = createSketchStore()
    s.start({ partName: 'Mounting bracket', partNumber: 'P-123456' })
    s.cancel() // both the Cancel path AND the successful-commit path reset via cancel
    expect(s.getSnapshot().active).toBe(false)
    expect(s.getSnapshot().partName).toBeNull()
    expect(s.getSnapshot().partNumber).toBeNull()
  })

  it('an ORDINARY Sketch (ribbon) starts with no New-dialog metadata', () => {
    const s = createSketchStore()
    s.start({ partName: 'Named part', partNumber: 'P-000001' })
    s.cancel()
    s.start() // the plain ribbon path
    expect(s.getSnapshot().partName).toBeNull()
    expect(s.getSnapshot().partNumber).toBeNull()
    expect(s.getSnapshot().active).toBe(true)
  })

  it('blank/whitespace meta normalizes to null', () => {
    const s = createSketchStore()
    s.start({ partName: '   ', partNumber: '' })
    expect(s.getSnapshot().partName).toBeNull()
    expect(s.getSnapshot().partNumber).toBeNull()
  })

  it('carries the picked plane + the active target Part for ONE session (EP1)', () => {
    const s = createSketchStore()
    s.start({ plane: 'yz', targetPart: { number: 'P-000123', name: 'Bracket' } })
    expect(s.getSnapshot().plane).toBe('yz')
    expect(s.getSnapshot().targetPart?.number).toBe('P-000123')
    s.cancel()
    s.start() // a plain session defaults back to FRONT (xy), no target
    expect(s.getSnapshot().plane).toBe('xy')
    expect(s.getSnapshot().targetPart).toBeNull()
  })
})
