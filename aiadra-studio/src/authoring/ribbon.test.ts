import { describe, it, expect } from 'vitest'
import { deriveCommandState, RIBBON_COMMANDS, roadmapTooltipGaps, type RibbonInputs } from './ribbon'
import { createPartContextStore } from './partContext'
import { simulateFailureMessage } from './backendBridge'

const RAW = (number: string, features: unknown[] = []) => ({
  sidecar: { object: { type: 'Part', number, name: number, uuid: `u-${number}` }, feature: features },
})
const EXTRUDE_PAIR = [
  { id: 'feat_0001', feature_type: 'sketch', engine: 'mechanical', adapter_schema_version: '0.1.8',
    adapter_payload: { primitives: [{ type: 'rectangle', id: 'skp_0001', x_mm: 0, y_mm: 0, width_mm: 5, height_mm: 5 }] } },
  { id: 'feat_0002', feature_type: 'extrude', engine: 'mechanical', adapter_schema_version: '0.1.8',
    depends_on_feature_ids: ['feat_0001'], adapter_payload: { sketch_feature_id: 'feat_0001', direction: 'normal+' } },
]

const inputs = (over: Partial<RibbonInputs> = {}): RibbonInputs => ({
  realLane: true,
  authoringGate: null,
  pc: { workspaceId: null, partNumber: null, generation: 0, inspection: { status: 'idle' }, selectorFacts: null },
  selection: null,
  ...over,
})

describe('the three-state ribbon taxonomy (D-R1 — the N3 command-state matrix)', () => {
  it('the EXACT benchmark inventory (Codex3 B3 — a missing/renamed/regrouped command fails; V-2 extends it with the presentation fields)', () => {
    const pres = (c: (typeof RIBBON_COMMANDS)[number]): string =>
      c.presentation.menu
        ? `menu(${c.presentation.menu.family}#${c.presentation.menu.order})`
        : `${c.presentation.size}@c${c.presentation.slot!.column}r${c.presentation.slot!.row}`
    const inventory = RIBBON_COMMANDS.map((c) => `${c.group}:${c.key}:${c.label}:${pres(c)}`)
    expect(inventory).toEqual([
      'Operations:regenerate:Regenerate:anchor@c0r0',
      'Get Data:get-data:Get Data:anchor@c0r0',
      'Body:boolean-ops:Boolean Operations:menu(body-ops#0)', 'Body:split-trim-body:Split/Trim Body:menu(body-ops#1)', 'Body:new-body:New Body:menu(body-ops#2)',
      'Datum:datum-plane:Plane:small@c1r0', 'Datum:datum-axis:Axis:small@c1r1', 'Datum:datum-point:Point:small@c1r2',
      'Datum:datum-csys:Coordinate System:small@c2r0', 'Datum:sketch:Sketch:anchor@c0r0',
      // Gate F2b (arc 20260717-2): the first v2 writer — the references sketch.
      'Datum:references-sketch:References:small@c2r1',
      'Shapes:extrude:Extrude:anchor@c0r0', 'Shapes:revolve:Revolve:anchor@c1r0', 'Shapes:sweep:Sweep:small@c2r0', 'Shapes:swept-blend:Swept Blend:small@c2r1',
      'Engineering:hole:Hole:anchor@c0r0', 'Engineering:round:Round:small@c1r0', 'Engineering:chamfer:Chamfer:small@c1r1',
      'Engineering:shell:Shell:small@c1r2', 'Engineering:draft:Draft:small@c2r0', 'Engineering:rib:Rib:small@c2r1',
      'Pattern:pattern:Pattern:anchor@c0r0',
      'Editing:mirror:Mirror:small@c0r0', 'Editing:trim:Trim:small@c0r1', 'Editing:offset:Offset:small@c0r2', 'Editing:extend:Extend:small@c1r0',
      'Editing:project:Project:small@c1r1', 'Editing:thicken:Thicken:small@c1r2', 'Editing:solidify:Solidify:menu(editing-more#0)',
      'Editing:merge:Merge:menu(editing-more#1)', 'Editing:intersect:Intersect:menu(editing-more#2)', 'Editing:split:Split:menu(editing-more#3)',
      'Editing:remove:Remove:menu(editing-more#4)', 'Editing:unify:Unify:menu(editing-more#5)',
      'Surfaces:boundary-blend:Boundary Blend:menu(surfaces-all#0)', 'Surfaces:fill:Fill:menu(surfaces-all#1)', 'Surfaces:style:Style:menu(surfaces-all#2)', 'Surfaces:freestyle:Freestyle:menu(surfaces-all#3)',
      'Model Intent:component-interface:Component Interface:menu(model-intent-all#0)',
    ])
    expect(new Set(RIBBON_COMMANDS.map((c) => c.key)).size).toBe(RIBBON_COMMANDS.length) // no duplicates
    expect(roadmapTooltipGaps()).toEqual([])
  })

  it('V-3 (Codex1 B1): Get Data is WORKING with the typed reference-import dispatch — the ONE semantic exception', () => {
    const getData = RIBBON_COMMANDS.find((c) => c.key === 'get-data')!
    expect(getData.dispatch).toBe('reference-import')
    expect(getData.derive(inputs())).toEqual({ state: 'working' })
    // …and it stays the ONLY exception: every other command dispatches sessions
    expect(RIBBON_COMMANDS.filter((c) => c.dispatch !== undefined).map((c) => c.key)).toEqual(['get-data'])
  })

  it('Sketch: gated → disabled with the gate reason; real lane needs a ready Part; dev idle flows', async () => {
    expect(deriveCommandState('sketch', inputs({ authoringGate: 'busy' }))).toMatchObject({
      state: 'state-disabled', reason: 'busy',
    })
    expect(deriveCommandState('sketch', inputs())).toMatchObject({
      state: 'state-disabled', reason: /Create or open a Part/,
    })
    // dev:web with NO target: the fresh-Part flow stays available
    expect(deriveCommandState('sketch', inputs({ realLane: false }))).toEqual({ state: 'working' })
    // a READY part enables in the real lane
    const store = createPartContextStore()
    await store.setPart('ws-1', 'P-1', { fetchInspect: async () => RAW('P-1') })
    expect(deriveCommandState('sketch', inputs({ pc: store.getSnapshot() }))).toEqual({ state: 'working' })
  })

  it('Sketch/Extrude: a targeted LOADING or ERROR context disables (the shared policy)', async () => {
    const store = createPartContextStore()
    const p = store.setPart('ws-1', 'P-1', { fetchInspect: async () => RAW('P-1') })
    for (const key of ['sketch', 'extrude']) {
      expect(deriveCommandState(key, inputs({ pc: store.getSnapshot() })).state).toBe('state-disabled')
    }
    await p
    await store.setPart('ws-1', 'P-2', {
      fetchInspect: async () => {
        throw new Error('inspect failed')
      },
    })
    for (const key of ['sketch', 'extrude']) {
      expect(deriveCommandState(key, inputs({ pc: store.getSnapshot() })).state).toBe('state-disabled')
    }
  })

  it('Extrude: enabled on a ready EMPTY Part; state-disabled with the one-base reason once a base exists', async () => {
    const store = createPartContextStore()
    await store.setPart('ws-1', 'P-1', { fetchInspect: async () => RAW('P-1') })
    expect(deriveCommandState('extrude', inputs({ pc: store.getSnapshot() }))).toEqual({ state: 'working' })
    await store.refresh({ fetchInspect: async () => RAW('P-1', EXTRUDE_PAIR) })
    expect(deriveCommandState('extrude', inputs({ pc: store.getSnapshot() }))).toMatchObject({
      state: 'state-disabled', reason: /base creation feature/,
    })
  })

  it('Revolve (R3 flipped): live with extrude-like base rules', async () => {
    const store = createPartContextStore()
    await store.setPart('ws-1', 'P-1', { fetchInspect: async () => RAW('P-1') })
    expect(deriveCommandState('revolve', inputs({ pc: store.getSnapshot() }))).toEqual({ state: 'working' })
    await store.refresh({ fetchInspect: async () => RAW('P-1', EXTRUDE_PAIR) })
    expect(deriveCommandState('revolve', inputs({ pc: store.getSnapshot() }))).toMatchObject({
      state: 'state-disabled', reason: /base creation feature/,
    })
  })

  it('Round/Chamfer (R4 flipped): the full state ladder — lane, base, selection, edge kind', async () => {
    const store = createPartContextStore()
    await store.setPart('ws-1', 'P-1', { fetchInspect: async () => RAW('P-1', EXTRUDE_PAIR) })
    store.publishSelectorFacts(store.getSnapshot().generation, {
      edgeKinds: new Map([['feat_0002:edge:sharp1', 'sharp'], ['feat_0002:edge:t1', 'tangent']]),
      faceIds: new Set(['feat_0002:face:cap_hi']),
      planarFaceIds: new Set<string>(),
      sketchFrames: new Map(),
    })
    const pc = store.getSnapshot()
    // dev lane: honest topology reason
    expect(deriveCommandState('round', inputs({ realLane: false, pc }))).toMatchObject({
      state: 'state-disabled', reason: /desktop real-engine lane/,
    })
    // no selection
    expect(deriveCommandState('round', inputs({ pc }))).toMatchObject({ reason: /select an edge/ })
    // stale/foreign edge id
    expect(
      deriveCommandState('round', inputs({ pc, selection: { kind: 'edge', id: 'nope' }, edgeKind: (id) => pc.selectorFacts?.edgeKinds.get(id) ?? null })),
    ).toMatchObject({ reason: /not on the current display/ })
    // non-sharp edge
    expect(
      deriveCommandState('chamfer', inputs({ pc, selection: { kind: 'edge', id: 'feat_0002:edge:t1' }, edgeKind: (id) => pc.selectorFacts?.edgeKinds.get(id) ?? null })),
    ).toMatchObject({ reason: /tangent/ })
    // sharp edge → working
    expect(
      deriveCommandState('round', inputs({ pc, selection: { kind: 'edge', id: 'feat_0002:edge:sharp1' }, edgeKind: (id) => pc.selectorFacts?.edgeKinds.get(id) ?? null })),
    ).toEqual({ state: 'working' })
  })

  it('Hole (R5 flipped): the P1 base-domain ladder — contour base refuses; rectangle base + face works; prior hole refuses', async () => {
    // A CONTOUR-extruded base: canonical cap faces exist, but v1 Hole's
    // domain refuses BEFORE any dashboard (Codex2 B1's exact scenario).
    const CONTOUR_PAIR = [
      { id: 'feat_0001', feature_type: 'sketch', engine: 'mechanical', adapter_schema_version: '0.1.8',
        adapter_payload: { primitives: [{ type: 'contour', id: 'skp_0001', segments: [
          { kind: 'line', x1_mm: 0, y1_mm: 0, x2_mm: 10, y2_mm: 0 },
          { kind: 'line', x1_mm: 10, y1_mm: 0, x2_mm: 10, y2_mm: 8 },
          { kind: 'line', x1_mm: 10, y1_mm: 8, x2_mm: 0, y2_mm: 0 },
        ] }] } },
      EXTRUDE_PAIR[1],
    ]
    const store = createPartContextStore()
    await store.setPart('ws-1', 'P-1', { fetchInspect: async () => RAW('P-1', CONTOUR_PAIR) })
    store.publishSelectorFacts(store.getSnapshot().generation, {
      edgeKinds: new Map(),
      faceIds: new Set(['feat_0002:face:cap_hi']),
      planarFaceIds: new Set<string>(),
      sketchFrames: new Map(),
    })
    const sel = { kind: 'face' as const, id: 'feat_0002:face:cap_hi' }
    const faceExistsOf = (snap: ReturnType<typeof store.getSnapshot>) => (id: string) =>
      snap.selectorFacts?.faceIds.has(id) ?? false
    expect(
      deriveCommandState('hole', inputs({ pc: store.getSnapshot(), selection: sel, faceExists: faceExistsOf(store.getSnapshot()) })),
    ).toMatchObject({
      state: 'state-disabled', reason: /not a simple rectangle/,
    })
    // The RECTANGLE-extruded base: face selected → working.
    await store.setPart('ws-1', 'P-2', { fetchInspect: async () => RAW('P-2', EXTRUDE_PAIR) })
    store.publishSelectorFacts(store.getSnapshot().generation, {
      edgeKinds: new Map(),
      faceIds: new Set(['feat_0002:face:cap_hi']),
      planarFaceIds: new Set<string>(),
      sketchFrames: new Map(),
    })
    expect(
      deriveCommandState('hole', inputs({ pc: store.getSnapshot(), selection: sel, faceExists: faceExistsOf(store.getSnapshot()) })),
    ).toEqual({ state: 'working' })
    expect(deriveCommandState('hole', inputs({ pc: store.getSnapshot() }))).toMatchObject({ reason: /select a flat cap face/ })
    // Codex3 B1.2: a STALE/foreign face id must not advertise working.
    expect(
      deriveCommandState('hole', inputs({ pc: store.getSnapshot(), selection: { kind: 'face', id: 'stale:face' }, faceExists: faceExistsOf(store.getSnapshot()) })),
    ).toMatchObject({ reason: /not on the current display/ })
    expect(deriveCommandState('hole', inputs({ realLane: false, pc: store.getSnapshot(), selection: sel }))).toMatchObject({
      reason: /desktop real-engine lane/,
    })
    // A prior hole → the one-hole v1 bound.
    const WITH_HOLE = [...EXTRUDE_PAIR,
      { id: 'feat_0003', feature_type: 'hole', engine: 'mechanical', adapter_schema_version: '0.1.8',
        adapter_payload: {} }]
    await store.setPart('ws-1', 'P-3', { fetchInspect: async () => RAW('P-3', WITH_HOLE) })
    store.publishSelectorFacts(store.getSnapshot().generation, { edgeKinds: new Map(), faceIds: new Set([sel.id]), planarFaceIds: new Set<string>(), sketchFrames: new Map() })
    expect(
      deriveCommandState('hole', inputs({ pc: store.getSnapshot(), selection: sel, faceExists: faceExistsOf(store.getSnapshot()) })),
    ).toMatchObject({
      // Codex3 B1.1: the STACKING containment fires first (conservative).
      reason: /stacked referencing features/,
    })
  })

  it('Codex3 B1: stacking containment + dev no-Part base features + the exact inventory', async () => {
    // A part WITH a fillet: Round/Chamfer/Hole all refuse with the stacking reason.
    const WITH_FILLET = [...EXTRUDE_PAIR,
      { id: 'feat_0003', feature_type: 'fillet', engine: 'mechanical', adapter_schema_version: '0.1.8',
        adapter_payload: {} }]
    const store = createPartContextStore()
    await store.setPart('ws-1', 'P-1', { fetchInspect: async () => RAW('P-1', WITH_FILLET) })
    store.publishSelectorFacts(store.getSnapshot().generation, {
      edgeKinds: new Map([['e:s', 'sharp']]),
      faceIds: new Set(['f:cap']),
      planarFaceIds: new Set<string>(),
      sketchFrames: new Map(),
    })
    const pc = store.getSnapshot()
    const kindOf = (id: string) => pc.selectorFacts?.edgeKinds.get(id) ?? null
    for (const key of ['round', 'chamfer']) {
      expect(
        deriveCommandState(key, inputs({ pc, selection: { kind: 'edge', id: 'e:s' }, edgeKind: kindOf })),
      ).toMatchObject({ reason: /stacked referencing features/ })
    }
    expect(
      deriveCommandState('hole', inputs({ pc, selection: { kind: 'face', id: 'f:cap' }, faceExists: (id) => pc.selectorFacts?.faceIds.has(id) ?? false })),
    ).toMatchObject({ reason: /stacked referencing features/ })
    // Dev idle (no Part): Extrude/Revolve are state-disabled, never a dead end.
    for (const key of ['extrude', 'revolve']) {
      expect(deriveCommandState(key, inputs({ realLane: false }))).toMatchObject({
        state: 'state-disabled', reason: /Commit a Part first/,
      })
    }
  })

  it('datum creation names the EP3 arc; unknown keys are roadmap-disabled', () => {
    expect(deriveCommandState('datum-plane', inputs())).toMatchObject({ reason: /EP3 datum arc/ })
    expect(deriveCommandState('nope', inputs()).state).toBe('roadmap-disabled')
  })
})

describe('simulateFailureMessage (P2 — verbatim first-failure details)', () => {
  it('extracts the first FAIL outcome details; falls back to check_name, then the named generic', () => {
    expect(
      simulateFailureMessage({
        outcomes: [
          { check_name: 'a', result: 'PASS' },
          { check_name: 'contour', result: 'FAIL', details: 'contour primitive[0] segment[2] is zero-length' },
        ],
      }),
    ).toBe('contour primitive[0] segment[2] is zero-length')
    expect(
      simulateFailureMessage({ outcomes: [{ check_name: 'b6_scan', result: 'FAIL', details: '' }] }),
    ).toBe('validation failed: b6_scan')
    expect(simulateFailureMessage({})).toBe('validation failed')
  })
})
