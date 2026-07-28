import { describe, it, expect } from 'vitest'
import { createAuthoringSessionStore } from './authoringSession'
import { supportFrame } from './backend'
import { principalFrame } from '../sketch/planeFrame'
import { routeSketchPlacement } from '../sketch/sketchPlacementRouter'

const RING = [
  { x: 0, y: 0 },
  { x: 40, y: 0 },
  { x: 40, y: 30 },
]

describe('authoringSession (S2 D-S4 — ONE discriminated session)', () => {
  it('exactly one session at a time: a second start is refused until cancel', () => {
    const s = createAuthoringSessionStore()
    s.startSketch({ generation: 0, plane: 'zx' })
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
    s.startSketch({ generation: 0, plane: 'xy' })
    RING.forEach((p) => s.addPoint(p))
    s.closeRing()
    const st = s.getSnapshot()
    expect(st.mode === 'sketch' && st.tool.kind === 'contour' && st.tool.closed).toBe(true)
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
    s.beginChainedSketch('zx', { number: 'P-1', name: 'A' }, 'contour', 0)
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
    expect(ex.mode === 'extrude' && ex.source).toEqual({ kind: 'pending', plane: 'zx', points: RING, bulges: [0, 0] })
  })

  it('finishChainedSketch refuses an OPEN ring and a NON-chained sketch', () => {
    const s = createAuthoringSessionStore()
    s.startSketch({ generation: 0, plane: 'xy' })
    RING.forEach((p) => s.addPoint(p))
    s.closeRing()
    s.finishChainedSketch() // stepwise sketch — never hands off to extrude
    expect(s.getSnapshot().mode).toBe('sketch')
    s.cancel()
    s.startExtrude(null)
    s.beginChainedSketch('xy', null, 'contour', 0)
    s.addPoint(RING[0]) // ring not closed
    s.finishChainedSketch()
    expect(s.getSnapshot().mode).toBe('sketch')
  })

  it('the tree selection survives idle and mode changes (it feeds entry A)', () => {
    const s = createAuthoringSessionStore()
    s.selectSketch('feat_0007')
    s.startSketch({ generation: 0 })
    s.cancel()
    expect(s.getSnapshot().selectedSketchId).toBe('feat_0007')
    s.selectSketch(null)
    expect(s.getSnapshot().selectedSketchId).toBeNull()
  })

  it('the authority TUPLE survives the chained-sketch hand-off (Codex4 B1.4 — never re-read live)', () => {
    const s = createAuthoringSessionStore()
    const tuple = { workspaceId: 'ws-1', partNumber: 'P-1', generation: 7 }
    s.startExtrude(null, tuple)
    s.beginChainedSketch('zx', { number: 'P-1', name: 'A' }, 'contour', 0)
    const sk = s.getSnapshot()
    expect(sk.mode === 'sketch' && sk.targetAuth).toEqual(tuple) // the CAPTURE, not a fresh read
    RING.forEach((p) => s.addPoint(p))
    s.closeRing()
    s.finishChainedSketch()
    const ex = s.getSnapshot()
    expect(ex.mode === 'extrude' && ex.target).toEqual(tuple)
  })

  it('R2: the rectangle tool — two clicks normalize; degenerate picks refuse; Restart resets', () => {
    const s = createAuthoringSessionStore()
    s.startSketch({ generation: 0, plane: 'xy', tool: 'rectangle' })
    const st0 = s.getSnapshot()
    expect(st0.mode === 'sketch' && st0.tool.kind).toBe('rectangle')
    s.addPoint({ x: 1, y: 1 }) // contour actions no-op on the rectangle tool
    s.placeRectCorner({ x: 30, y: 40 })
    s.placeRectCorner({ x: 30, y: 40 }) // zero-size → refused, anchor kept
    let st = s.getSnapshot()
    expect(st.mode === 'sketch' && st.tool.kind === 'rectangle' && st.tool.rect).toBeNull()
    expect(st.mode === 'sketch' && st.message).toMatch(/zero-size/)
    s.placeRectCorner({ x: 10, y: 10 }) // drag up-left: still normalizes
    st = s.getSnapshot()
    expect(st.mode === 'sketch' && st.tool.kind === 'rectangle' && st.tool.rect).toEqual({
      x_mm: 10, y_mm: 10, width_mm: 20, height_mm: 30,
    })
    expect(st.mode === 'sketch' && st.phase).toBe('closed')
    s.reopen() // Restart clears the rectangle
    st = s.getSnapshot()
    expect(st.mode === 'sketch' && st.tool.kind === 'rectangle' && st.tool.anchor).toBeNull()
  })

  it('R2: switching tools resets the drawing; the chained sketch pins contour', () => {
    const s = createAuthoringSessionStore()
    s.startSketch({ generation: 0, plane: 'xy' })
    s.addPoint({ x: 0, y: 0 })
    s.switchTool('rectangle')
    let st = s.getSnapshot()
    expect(st.mode === 'sketch' && st.tool.kind).toBe('rectangle')
    s.switchTool('contour')
    st = s.getSnapshot()
    expect(st.mode === 'sketch' && st.tool.kind === 'contour' && st.tool.points).toEqual([])
    s.cancel()
    s.startExtrude(null)
    s.beginChainedSketch('zx', null, 'contour', 0)
    st = s.getSnapshot()
    expect(st.mode === 'sketch' && st.tool.kind).toBe('contour')
  })

  it('R3: the chained RECTANGLE hand-back restores the REVOLVE session (feature/axis survive)', () => {
    const s = createAuthoringSessionStore()
    const tuple = { workspaceId: 'ws-1', partNumber: 'P-1', generation: 3 }
    s.startExtrude(null, tuple, 10, 'revolve')
    s.setAxis('y')
    s.beginChainedSketch('xy', { number: 'P-1', name: 'A' }, 'rectangle', 3)
    let st = s.getSnapshot()
    expect(st.mode === 'sketch' && st.tool.kind).toBe('rectangle')
    s.placeRectCorner({ x: 5, y: 5 })
    s.placeRectCorner({ x: 25, y: 15 })
    s.finishChainedSketch()
    st = s.getSnapshot()
    expect(st.mode).toBe('extrude')
    expect(st.mode === 'extrude' && st.feature).toBe('revolve')
    expect(st.mode === 'extrude' && st.axis).toBe('y')
    expect(st.mode === 'extrude' && st.target).toEqual(tuple)
    expect(st.mode === 'extrude' && st.source).toEqual({
      kind: 'pending_rectangle',
      rect: { x_mm: 5, y_mm: 5, width_mm: 20, height_mm: 10 },
    })
  })

  it('R5/R6: hole + edit sessions own their capture; only catalogued names are addressable', () => {
    const s = createAuthoringSessionStore()
    const tuple = { workspaceId: 'ws-1', partNumber: 'P-1', generation: 4 }
    // hole
    s.startHoleFeature({ target: tuple, selector: { kind: 'face', id: 'f:cap' }, edgeKind: null })
    let st = s.getSnapshot()
    expect(st.mode === 'holeFeature' && st.capture.selector.id).toBe('f:cap')
    s.setHoleParam('diameterMm', 8)
    st = s.getSnapshot()
    expect(st.mode === 'holeFeature' && st.diameterMm).toBe(8)
    s.cancel()
    // edit-dimension: the catalogue is the only addressable surface (N3)
    const params = [
      { id: 'featp_0001', name: 'depth_mm', value: 5, unit: 'mm' },
      { id: 'featp_0002', name: 'radius_mm', value: 2, unit: 'mm' },
    ]
    s.startEditParameter(tuple, 'feat_0002', params)
    st = s.getSnapshot()
    expect(st.mode === 'editParameter' && st.paramName).toBe('depth_mm')
    expect(st.mode === 'editParameter' && st.value).toBe(5)
    s.chooseEditParameter('radius_mm')
    st = s.getSnapshot()
    expect(st.mode === 'editParameter' && st.value).toBe(2)
    s.chooseEditParameter('evil_field') // NOT catalogued → refused
    st = s.getSnapshot()
    expect(st.mode === 'editParameter' && st.paramName).toBe('radius_mm')
    s.startEditParameter(tuple, 'x', []) // no catalogued params → refuses to start
    s.cancel()
    s.startEditParameter(tuple, 'x', [])
    expect(s.getSnapshot().mode).toBe('idle')
  })

  it('busy extrude refuses depth edits and sketch chaining', () => {
    const s = createAuthoringSessionStore()
    s.startExtrude('feat_0001')
    s.setExtrudePhase('busy')
    s.setDepth(50)
    expect((s.getSnapshot() as { depthMm: number }).depthMm).toBe(10)
    s.beginChainedSketch('xy', null, 'contour', 0)
    expect(s.getSnapshot().mode).toBe('extrude')
  })
})

describe('the plane-pick substate (SK-C1.0 S1 — Codex1 B4)', () => {
  const AUTH = { workspaceId: 'ws-1', partNumber: 'P-1', generation: 3 }

  it('standalone: enter synchronously from idle, resolve → sketch on the picked plane', () => {
    const s = createAuthoringSessionStore()
    s.startPlanePick({ targetPart: { number: 'P-1', name: 'Bracket' }, targetAuth: AUTH }, 3)
    let st = s.getSnapshot()
    expect(st.mode).toBe('planePick') // the global gate sees active work NOW
    expect(st.mode === 'planePick' && st.generation).toBe(3)
    s.resolvePlanePick('yz')
    st = s.getSnapshot()
    expect(st.mode).toBe('sketch')
    if (st.mode === 'sketch') {
      expect(st.plane).toBe('yz')
      expect(st.targetAuth).toEqual(AUTH) // the ENTRY capture, not a live re-read
      expect(st.chainToExtrude).toBe(false)
    }
  })

  it('standalone: Escape/cancel → idle (selection survives); a LATE point after cancel is a no-op', () => {
    const s = createAuthoringSessionStore()
    s.selectSketch('feat_0009')
    s.startPlanePick({}, 1)
    s.cancelPlanePick()
    expect(s.getSnapshot()).toMatchObject({ mode: 'idle', selectedSketchId: 'feat_0009' })
    s.addPoint({ x: 1, y: 1 }) // the Codex3 bar-6 late-gesture guard
    expect(s.getSnapshot().mode).toBe('idle')
  })

  it('chained: captures the extrude session VERBATIM; cancel restores it; resolve chains the sketch', () => {
    const s = createAuthoringSessionStore()
    s.startExtrude(null, AUTH, 25)
    s.startChainedPlanePick(3, 'contour', { number: 'P-1', name: 'Bracket' })
    expect(s.getSnapshot().mode).toBe('planePick')
    // Escape → the base-feature session comes back exactly as captured
    s.cancelPlanePick()
    let st = s.getSnapshot()
    expect(st.mode).toBe('extrude')
    if (st.mode === 'extrude') {
      expect(st.step).toBe('select')
      expect(st.depthMm).toBe(25)
      expect(st.target).toEqual(AUTH)
    }
    // …and the resolve path chains with the CAPTURED authority
    s.startChainedPlanePick(3, 'contour', { number: 'P-1', name: 'Bracket' })
    s.resolvePlanePick('zx')
    st = s.getSnapshot()
    expect(st.mode).toBe('sketch')
    if (st.mode === 'sketch') {
      expect(st.chainToExtrude).toBe(true)
      expect(st.plane).toBe('zx')
      expect(st.chainedDepthMm).toBe(25)
      expect(st.targetAuth).toEqual(AUTH)
      expect(st.targetPart).toEqual({ number: 'P-1', name: 'Bracket' })
    }
  })

  it('B2: the generation rides planePick → sketch (standalone AND chained)', () => {
    const s = createAuthoringSessionStore()
    s.startPlanePick({}, 7)
    s.resolvePlanePick('xy')
    expect((s.getSnapshot() as { generation: number }).generation).toBe(7)
    s.cancel()
    s.startExtrude(null, AUTH, 10)
    s.startChainedPlanePick(7)
    s.resolvePlanePick('xy')
    expect((s.getSnapshot() as { generation: number }).generation).toBe(7)
  })

  it('B2: invalidation is DISTINCT from cancel — planePick (standalone + chained) terminates to idle, never the chained restore', () => {
    const s = createAuthoringSessionStore()
    s.selectSketch('feat_0009')
    s.startPlanePick({}, 1)
    s.invalidateForGeneration()
    expect(s.getSnapshot()).toMatchObject({ mode: 'idle', selectedSketchId: null }) // stale selection cleared
    // chained: the OLD generation's extrude session must NOT come back
    s.startExtrude(null, AUTH, 25)
    s.startChainedPlanePick(3)
    s.invalidateForGeneration()
    expect(s.getSnapshot().mode).toBe('idle')
  })

  it('B2: invalidation owns the ACTIVE sketch too (standalone + chained)', () => {
    const s = createAuthoringSessionStore()
    s.startPlanePick({}, 2)
    s.resolvePlanePick('yz')
    expect(s.getSnapshot().mode).toBe('sketch')
    s.invalidateForGeneration()
    expect(s.getSnapshot().mode).toBe('idle')
    s.startExtrude(null, AUTH, 25)
    s.startChainedPlanePick(3)
    s.resolvePlanePick('zx')
    expect(s.getSnapshot().mode).toBe('sketch')
    s.invalidateForGeneration()
    expect(s.getSnapshot().mode).toBe('idle') // not the captured extrude
  })

  it('B2 (Codex5): the SYNCHRONOUS live-generation boundary — a stale placement invalidates and lands nothing', () => {
    const s = createAuthoringSessionStore()
    s.startPlanePick({}, 2)
    s.resolvePlanePick('xy')
    routeSketchPlacement(s, { u: 0, v: 0 }, 2) // live matches → places
    expect((s.getSnapshot() as { tool: { points: unknown[] } }).tool.points).toHaveLength(1)
    // the context moved; the effect has NOT run — the boundary itself refuses
    routeSketchPlacement(s, { u: 10, v: 0 }, 3)
    expect(s.getSnapshot().mode).toBe('idle') // invalidated synchronously
  })

  it('B2: pointer-down → generation change → pointer-up lands NO late point', () => {
    const s = createAuthoringSessionStore()
    s.startPlanePick({}, 2)
    s.resolvePlanePick('xy')
    s.addPoint({ x: 0, y: 0 }) // the gesture began against generation 2
    s.invalidateForGeneration() // the context moved mid-gesture
    s.addPoint({ x: 10, y: 0 }) // the late pointer-up routes here…
    expect(s.getSnapshot().mode).toBe('idle') // …and lands NOTHING
  })

  it('guards: no pick from a non-idle/non-extrude state; resolve/cancel outside the mode are no-ops', () => {
    const s = createAuthoringSessionStore()
    s.startSketch({ generation: 0, plane: 'xy' })
    s.startPlanePick({}, 1) // refused — a sketch is active
    expect(s.getSnapshot().mode).toBe('sketch')
    s.resolvePlanePick('xy') // no-op outside the mode
    expect(s.getSnapshot().mode).toBe('sketch')
    s.cancel()
    s.cancelPlanePick() // no-op from idle
    expect(s.getSnapshot().mode).toBe('idle')
  })
})

describe('Codex10 B1 — the SUPPORT is the sole camera-frame authority', () => {
  // cap_base of an xy-based box: outward −Z, v = n×u = −Y — a frame that
  // DIFFERS from every principal (the coincidence trap the cap_top walk hid)
  const CAP_BASE = {
    origin: [0, 0, 0], u: [1, 0, 0], v: [0, -1, 0], normal: [0, 0, -1],
  } as const
  // a real-lane wall shape: outward +X, tie-break u = Y, v = n×u = +Z
  const WALL = {
    origin: [30, 0, 0], u: [0, 1, 0], v: [0, 0, 1], normal: [1, 0, 0],
  } as const

  it('a face pick stores the EXACT frame and supportFrame returns it BY REFERENCE', () => {
    for (const frame of [CAP_BASE, WALL]) {
      const s = createAuthoringSessionStore()
      s.startPlanePick({}, 3)
      s.resolvePlanePick({ faceId: 'feat_0002:face:probe', frame })
      const st = s.getSnapshot()
      expect(st.mode).toBe('sketch')
      if (st.mode !== 'sketch') return
      expect(st.support).toEqual({ kind: 'face', faceId: 'feat_0002:face:probe', frame })
      // the ONE projection every camera consumer (Sketch view, the
      // interaction mode) goes through — identity, never a re-derivation,
      // and NEVER the legacy `st.plane` (which stays a principal)
      expect(supportFrame(st.support)).toBe(frame)
      expect(supportFrame(st.support)).not.toEqual(principalFrame(st.plane))
    }
  })

  it('a principal pick projects through principalFrame (the same table as before)', () => {
    const s = createAuthoringSessionStore()
    s.startPlanePick({}, 1)
    s.resolvePlanePick('zx')
    const st = s.getSnapshot()
    if (st.mode !== 'sketch') throw new Error('expected sketch')
    expect(supportFrame(st.support)).toEqual(principalFrame('zx'))
  })
})
