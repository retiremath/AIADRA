/**
 * Sketch View for EVERY lane (I3, Claude2 D5′): the profile session's frame
 * wins while it is open; the v1 lane answers with its support frame; idle
 * has nothing to return to. Before I3 the button was dead while drawing a
 * profile.
 */
import { describe, expect, it } from 'vitest'
import { createAuthoringSessionStore } from '../authoring/authoringSession'
import { principalFrame, type PlaneFrameTS } from './planeFrame'
import { activeSketchFrame } from './activeSketchFrame'

const profileFrame: PlaneFrameTS = { origin: [0, 0, 0], u: [-1, 0, 0], v: [0, 1, 0], normal: [0, 0, -1] }

describe('activeSketchFrame (ONE Sketch View authority)', () => {
  it('idle + no profile session → null', () => {
    const store = createAuthoringSessionStore()
    expect(activeSketchFrame(store.getSnapshot(), null)).toBeNull()
  })

  it('the v1 sketch lane answers with its support frame', () => {
    const store = createAuthoringSessionStore()
    store.startSketch({ plane: 'yz', generation: 3, partName: null, partNumber: null, targetPart: null, targetAuth: null })
    expect(store.getSnapshot().mode).toBe('sketch')
    expect(activeSketchFrame(store.getSnapshot(), null)).toEqual(principalFrame('yz'))
  })

  it('the profile session’s own frame wins whenever it is open — even beside an idle v1 store', () => {
    const store = createAuthoringSessionStore()
    expect(activeSketchFrame(store.getSnapshot(), { frame: profileFrame })).toBe(profileFrame)
  })

  it('a placement dialog (no drawing yet) has nothing to return to', () => {
    const store = createAuthoringSessionStore()
    store.startPlacementPick(1, { number: 'P-1', name: 'x' }, { accept: 'sketch', capturedTarget: null })
    store.resolvePlanePick('xy')
    expect(store.getSnapshot().mode).toBe('placement')
    expect(activeSketchFrame(store.getSnapshot(), null)).toBeNull()
  })
})
