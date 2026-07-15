import { describe, it, expect } from 'vitest'
import { createAuthoringSessionStore } from './authoringSession'

const RING = [
  { x: 0, y: 0 },
  { x: 40, y: 0 },
  { x: 40, y: 30 },
]

describe('authoringSession (S2 D-S4 — ONE discriminated session)', () => {
  it('exactly one session at a time: a second start is refused until cancel', () => {
    const s = createAuthoringSessionStore()
    s.startSketch({ plane: 'zx' })
    expect(s.getSnapshot().mode).toBe('sketch')
    s.startExtrude(null) // refused — a sketch session owns the store
    expect(s.getSnapshot().mode).toBe('sketch')
    s.cancel()
    s.startExtrude(null)
    expect(s.getSnapshot().mode).toBe('extrude')
  })

  it('sketch drawing actions only act in sketch mode', () => {
    const s = createAuthoringSessionStore()
    s.addPoint({ x: 1, y: 1 }) // idle — ignored
    expect(s.getSnapshot().mode).toBe('idle')
    s.startSketch({ plane: 'xy' })
    RING.forEach((p) => s.addPoint(p))
    s.closeRing()
    const st = s.getSnapshot()
    expect(st.mode === 'sketch' && st.closed).toBe(true)
  })

  it('dual entry A: a preselected sketch goes STRAIGHT to depth', () => {
    const s = createAuthoringSessionStore()
    s.selectSketch('feat_0001')
    s.startExtrude('feat_0001')
    const st = s.getSnapshot()
    expect(st.mode).toBe('extrude')
    expect(st.mode === 'extrude' && st.step).toBe('depth')
    expect(st.mode === 'extrude' && st.source).toEqual({ kind: 'committed', sketchId: 'feat_0001' })
  })

  it('dual entry B: select step → chained sketch → the rings come back PENDING', () => {
    const s = createAuthoringSessionStore()
    s.startExtrude(null)
    expect(s.getSnapshot().mode === 'extrude' && (s.getSnapshot() as { step: string }).step).toBe('select')
    // pick a committed sketch is one path…
    s.chooseCommittedSketch('feat_0003')
    expect((s.getSnapshot() as { step: string }).step).toBe('depth')
    s.cancel()
    // …the other: hand off to the chained in-place sketch.
    s.startExtrude(null)
    s.beginChainedSketch('zx', { number: 'P-1', name: 'A' })
    const sk = s.getSnapshot()
    expect(sk.mode).toBe('sketch')
    expect(sk.mode === 'sketch' && sk.chainToExtrude).toBe(true)
    expect(sk.mode === 'sketch' && sk.plane).toBe('zx')
    RING.forEach((p) => s.addPoint(p))
    s.closeRing()
    s.finishChainedSketch()
    const ex = s.getSnapshot()
    expect(ex.mode).toBe('extrude')
    expect(ex.mode === 'extrude' && ex.step).toBe('depth')
    expect(ex.mode === 'extrude' && ex.source).toEqual({ kind: 'pending', plane: 'zx', points: RING })
  })

  it('finishChainedSketch refuses an OPEN ring and a NON-chained sketch', () => {
    const s = createAuthoringSessionStore()
    s.startSketch({ plane: 'xy' })
    RING.forEach((p) => s.addPoint(p))
    s.closeRing()
    s.finishChainedSketch() // stepwise sketch — never hands off to extrude
    expect(s.getSnapshot().mode).toBe('sketch')
    s.cancel()
    s.startExtrude(null)
    s.beginChainedSketch('xy', null)
    s.addPoint(RING[0]) // ring not closed
    s.finishChainedSketch()
    expect(s.getSnapshot().mode).toBe('sketch')
  })

  it('the tree selection survives idle and mode changes (it feeds entry A)', () => {
    const s = createAuthoringSessionStore()
    s.selectSketch('feat_0007')
    s.startSketch({})
    s.cancel()
    expect(s.getSnapshot().selectedSketchId).toBe('feat_0007')
    s.selectSketch(null)
    expect(s.getSnapshot().selectedSketchId).toBeNull()
  })

  it('the authority TUPLE survives the chained-sketch hand-off (Codex4 B1.4 — never re-read live)', () => {
    const s = createAuthoringSessionStore()
    const tuple = { workspaceId: 'ws-1', partNumber: 'P-1', generation: 7 }
    s.startExtrude(null, tuple)
    s.beginChainedSketch('zx', { number: 'P-1', name: 'A' })
    const sk = s.getSnapshot()
    expect(sk.mode === 'sketch' && sk.targetAuth).toEqual(tuple) // the CAPTURE, not a fresh read
    RING.forEach((p) => s.addPoint(p))
    s.closeRing()
    s.finishChainedSketch()
    const ex = s.getSnapshot()
    expect(ex.mode === 'extrude' && ex.target).toEqual(tuple)
  })

  it('busy extrude refuses depth edits and sketch chaining', () => {
    const s = createAuthoringSessionStore()
    s.startExtrude('feat_0001')
    s.setExtrudePhase('busy')
    s.setDepth(50)
    expect((s.getSnapshot() as { depthMm: number }).depthMm).toBe(10)
    s.beginChainedSketch('xy', null)
    expect(s.getSnapshot().mode).toBe('extrude')
  })
})
