/**
 * The UI-route floor (ledger floor 6/7/8, Studio side): the ACTUAL placement
 * session route — pick → the engine-default confirm state → member changes →
 * the PRODUCTION builder's exact output through the main-process validator →
 * the mock commit lane. (The real-engine leg is the desktop walk + the
 * authoring-smoke script; the datum-overlay raycast test covers the pick's
 * first link.) Lifecycle: Escape at each stage, generation invalidation,
 * busy-cancel refusal.
 */
import { describe, expect, it } from 'vitest'
import { AUTHORING_KINDS, validateAuthoringParams } from '../../electron/authoringParamRules'
import { createAuthoringSessionStore } from './authoringSession'
import { buildRedefinePlacementOps, buildReferenceSketchOps } from './backend'
import { createMockAuthoringBackend } from './backendMock'

const pickToConfirm = () => {
  const store = createAuthoringSessionStore()
  store.startPlacementPick(7, { number: 'P-9', name: 'Walk' })
  expect(store.getSnapshot().mode).toBe('planePick')
  store.resolvePlanePick('zx')
  return store
}

describe('the placement session route (A3.6.1 create)', () => {
  it('pick → the ENGINE default confirm state (zx → ref xy, right, positive)', () => {
    const store = pickToConfirm()
    const s = store.getSnapshot()
    expect(s).toMatchObject({
      mode: 'placement',
      support: 'zx',
      orientationRef: 'xy',
      orientation: 'right',
      normalSide: 'positive',
      redefineOf: null,
    })
  })

  it('a support change auto-repairs a colliding reference to the engine default', () => {
    const store = pickToConfirm()
    store.setPlacementMember('support', 'xy')
    const s = store.getSnapshot()
    expect(s).toMatchObject({ support: 'xy', orientationRef: 'yz' })
    // and a direct colliding ref change is refused outright
    store.setPlacementMember('orientationRef', 'xy')
    expect(store.getSnapshot()).toMatchObject({ orientationRef: 'yz' })
  })

  it('the session state builds the PRODUCTION op that passes the exact main validator and commits through the mock', async () => {
    const store = pickToConfirm()
    store.setPlacementMember('orientation', 'top')
    store.setPlacementMember('normalSide', 'negative')
    const s = store.getSnapshot()
    if (s.mode !== 'placement') throw new Error('unreachable')
    const ops = buildReferenceSketchOps('P-9', {
      support: { kind: 'principal', orientation: s.support },
      orientation_ref: { kind: 'principal', orientation: s.orientationRef },
      orientation: s.orientation,
      normal_side: s.normalSide,
    })
    for (const op of ops) {
      expect(AUTHORING_KINDS.has(op.kind)).toBe(true)
      expect(validateAuthoringParams(op.kind, op.params as Record<string, unknown>)).toBeNull()
    }
    // the mock lane accepts the exact same op set end-to-end
    const mock = createMockAuthoringBackend()
    const s1 = await mock.begin([
      { kind: 'create_part', params: { number: 'P-9', name: 'Walk' } },
      ...ops,
    ])
    await mock.commit(s1.sessionId, 'P-9')
    const raw = mock.inspectRaw('P-9') as {
      sidecar: { feature: Array<{ adapter_schema_version?: string; adapter_payload?: Record<string, unknown> }> }
    }
    const sk = raw.sidecar.feature.find((f) => f.adapter_schema_version === '0.2.1')!
    expect(sk.adapter_payload!.placement).toEqual({
      support: { kind: 'principal', orientation: 'zx' },
      orientation_ref: { kind: 'principal', orientation: 'xy' },
      orientation: 'top',
      normal_side: 'negative',
    })
  })
})

describe('the placement session route (A3.6.2 redefine)', () => {
  it('redefine seeds from the persisted facts; the DIFF builds the op; it passes the validator', () => {
    const store = createAuthoringSessionStore()
    store.startPlacementRedefine(
      'feat_0001',
      { support: 'xy', orientationRef: 'yz', orientation: 'right', normalSide: 'positive' },
      3,
      { number: 'P-9', name: 'Walk' },
    )
    const s0 = store.getSnapshot()
    expect(s0).toMatchObject({ mode: 'placement', support: 'xy', redefineOf: { featureId: 'feat_0001' } })
    store.setPlacementMember('normalSide', 'negative')
    const s = store.getSnapshot()
    if (s.mode !== 'placement' || !s.redefineOf) throw new Error('unreachable')
    // the App sends ONLY the changed members (omission-keeps is the engine's)
    const ops = buildRedefinePlacementOps('P-9', s.redefineOf.featureId, { normal_side: s.normalSide })
    expect(validateAuthoringParams(ops[0].kind, ops[0].params as Record<string, unknown>)).toBeNull()
    expect(ops[0].params).toEqual({
      part_number: 'P-9',
      sketch_feature_id: 'feat_0001',
      normal_side: 'negative',
    })
  })
})

describe('the placement session lifecycle (B4)', () => {
  it('Escape at the pick stage returns to idle with nothing captured', () => {
    const store = createAuthoringSessionStore()
    store.startPlacementPick(1, null)
    store.cancelPlanePick()
    expect(store.getSnapshot().mode).toBe('idle')
  })

  it('Escape at the confirm stage returns to idle; a BUSY session refuses cancel', () => {
    const store = pickToConfirm()
    store.setPlacementBusy(true)
    store.cancelPlacement()
    expect(store.getSnapshot().mode).toBe('placement') // uninterruptible terminal
    store.setPlacementBusy(false)
    store.cancelPlacement()
    expect(store.getSnapshot().mode).toBe('idle')
  })

  it('a generation change invalidates the WHOLE capture fail-closed', () => {
    const store = pickToConfirm()
    store.invalidateForGeneration()
    expect(store.getSnapshot()).toMatchObject({ mode: 'idle', selectedSketchId: null })
  })

  it('faces never resolve a placement pick (the BS-1 principal-only domain)', () => {
    const store = createAuthoringSessionStore()
    store.startPlacementPick(1, null)
    store.resolvePlanePick({ faceId: 'feat_0002:face:cap_top', frame: {
      orientation: 'xy', origin: [0, 0, 5], uAxis: [1, 0, 0], vAxis: [0, 1, 0], normal: [0, 0, 1],
    } as never })
    expect(store.getSnapshot().mode).toBe('planePick') // unresolved, still picking
  })
})
