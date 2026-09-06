/**
 * The Sketch continuation of the ONE placement session (I3, arc 20260905-1;
 * Codex1 N2 + Q2): pick → the dialog with the A3.3 default and the CAPTURED
 * target riding the session → list / viewport choices through ONE member
 * setter (collision repair; Orientation and Flip retained; a face inert) →
 * Sketch accept: the facts become the COMPLETE placement, the mirror frame is
 * the drawing frame, the owner retires exactly once, the same target reaches
 * the drawing session, and the production Close intent carries that placement
 * through the exact main validator. Nothing is written before Close.
 */
import { describe, expect, it } from 'vitest'
import { validateAuthoringParams } from '../../electron/authoringParamRules'
import { commitIntent, commitPoint, endTool, openCreate } from '../sketch/profileSession'
import {
  PLACEMENT_FACE_REFUSAL,
  applyPlacementMember,
  createAuthoringSessionStore,
  placementRecordOf,
} from './authoringSession'
import { placementToPlaneFrame } from './placementFrame'

const TARGET = { workspaceId: 'ws1', partNumber: 'P-9', generation: 7 }
const OPTS = { snapAngleToleranceDeg: 3, minDragPx: 4 }

const openDialog = () => {
  const store = createAuthoringSessionStore()
  store.startPlacementPick(7, { number: 'P-9', name: 'Walk' }, { accept: 'sketch', capturedTarget: TARGET })
  expect(store.getSnapshot().mode).toBe('planePick')
  store.resolvePlanePick('xy') // TOP
  return store
}

describe('the Sketch continuation of the placement session (I3)', () => {
  it('pick → the dialog on the A3.3 default; the continuation and the captured target ride the session', () => {
    expect(openDialog().getSnapshot()).toMatchObject({
      mode: 'placement',
      accept: 'sketch',
      support: 'xy',
      orientationRef: 'yz',
      orientation: 'right',
      normalSide: 'positive',
      activeCollector: null,
      capturedTarget: TARGET,
      redefineOf: null,
    })
  })

  it('list and viewport choices go through ONE member setter: collision repairs to the engine default; Orientation and Flip are retained', () => {
    const store = openDialog()
    store.setPlacementMember('orientation', 'top')
    store.setPlacementMember('normalSide', 'negative')
    store.setPlacementCollector('plane')
    store.resolvePlacementPick('yz') // collides with the reference yz → repaired to zx (the yz default)
    expect(store.getSnapshot()).toMatchObject({
      support: 'yz',
      orientationRef: 'zx',
      orientation: 'top',
      normalSide: 'negative',
      activeCollector: null, // disarmed by the successful pick
    })
    // the pure setter is the same law for every route
    const facts = { support: 'xy', orientationRef: 'yz', orientation: 'top', normalSide: 'negative' } as const
    expect(applyPlacementMember(facts, 'support', 'yz')).toEqual({ ...facts, support: 'yz', orientationRef: 'zx' })
    expect(applyPlacementMember(facts, 'orientationRef', 'xy')).toBeNull()
  })

  it('a pick without an armed collector is ignored; a FACE never mutates placement and surfaces the honest copy', () => {
    const store = openDialog()
    store.resolvePlacementPick('zx')
    expect(store.getSnapshot()).toMatchObject({ support: 'xy', orientationRef: 'yz', message: null })
    store.setPlacementCollector('reference')
    store.resolvePlacementPick({ faceId: 'face:1' }) // an unsupported face the viewport delivered
    expect(store.getSnapshot()).toMatchObject({
      support: 'xy',
      orientationRef: 'yz',
      activeCollector: 'reference', // still armed — the user may pick a plane next
      message: PLACEMENT_FACE_REFUSAL,
    })
  })

  it('Sketch accept: the COMPLETE placement, the mirror frame, retire ONCE, the same target, and a Close intent that passes the exact main validator', () => {
    const store = openDialog()
    store.setPlacementMember('orientationRef', 'zx')
    store.setPlacementMember('orientation', 'top')
    store.setPlacementMember('normalSide', 'negative')
    const s = store.getSnapshot()
    if (s.mode !== 'placement') throw new Error('unreachable')
    const placement = placementRecordOf(s)
    expect(placement).toEqual({
      support: { kind: 'principal', orientation: 'xy' },
      orientation_ref: { kind: 'principal', orientation: 'zx' },
      orientation: 'top',
      normal_side: 'negative',
    })
    const frame = placementToPlaneFrame(placement)
    expect(frame.u.map((x) => x + 0)).toEqual([-1, 0, 0])
    expect(frame.v.map((x) => x + 0)).toEqual([0, 1, 0])
    expect(frame.normal.map((x) => x + 0)).toEqual([0, 0, -1])

    // the owner retires exactly once; a duplicate accept is inert
    store.completePlacement()
    expect(store.getSnapshot().mode).toBe('idle')
    store.completePlacement()
    expect(store.getSnapshot().mode).toBe('idle')

    // the drawing session opens on the SAME captured target and the mirror frame
    const session = openCreate(placement, 'draft1', frame, s.capturedTarget!, OPTS)
    expect(session.target).toEqual(TARGET)
    expect(session.frame).toBe(frame)
    // nothing drawn → Close is a no-op (placement commits nothing)
    expect(commitIntent(session, 'P-9')).toBeNull()

    // one line drawn → the PRODUCTION intent carries the complete placement and passes main's envelope
    const drawn = endTool(commitPoint(commitPoint(session, { u: 0, v: 0 }), { u: 20, v: 0.4 }))
    const intent = commitIntent(drawn, 'P-9')
    expect(intent?.kind).toBe('mechanical.author_profile_sketch')
    expect(intent?.params.placement).toEqual(placement)
    expect(validateAuthoringParams(intent!.kind, intent!.params)).toBeNull()
  })

  it('invalidation before accept kills the dialog fail-closed; a busy dialog refuses to retire', () => {
    const store = openDialog()
    store.invalidateForGeneration()
    expect(store.getSnapshot().mode).toBe('idle')
    store.completePlacement()
    expect(store.getSnapshot().mode).toBe('idle')

    const busy = openDialog()
    busy.setPlacementBusy(true)
    busy.completePlacement()
    expect(busy.getSnapshot()).toMatchObject({ mode: 'placement', busy: true })
  })

  it('the References route is untouched: no continuation given → Create, no captured target', () => {
    const store = createAuthoringSessionStore()
    store.startPlacementPick(1, { number: 'P-1', name: 'x' })
    store.resolvePlanePick('zx')
    expect(store.getSnapshot()).toMatchObject({ mode: 'placement', accept: 'create', capturedTarget: null, orientationRef: 'xy' })
  })
})
