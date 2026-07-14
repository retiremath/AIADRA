import { describe, it, expect } from 'vitest'
import { createMockAuthoringBackend } from './backendMock'
import {
  buildContourOps,
  chooseBackendLane,
  createUnavailableBackend,
  suggestPartNumber,
  PART_NUMBER_RE,
} from './backend'
import type { Pt } from '../sketch/contour'

const L: Pt[] = [
  { x: 0, y: 0 }, { x: 60, y: 0 }, { x: 60, y: 20 },
  { x: 20, y: 20 }, { x: 20, y: 50 }, { x: 0, y: 50 },
]

describe('mock backend Class-1 defence-in-depth (Codex6 B2)', () => {
  it('simulate REJECTS a contour with a duplicated point (the real engine would too)', async () => {
    const dup = [...L.slice(0, 2), L[1], ...L.slice(2)] // duplicate the second point
    const mock = createMockAuthoringBackend()
    const sid = await mock.begin(buildContourOps('P-1', 'test', dup, 10))
    const sim = await mock.simulate(sid)
    expect(sim.valid).toBe(false)
    expect(sim.message).toMatch(/duplicate point/)
  })

  it('simulate accepts a valid drawn contour and commit shows ITS geometry', async () => {
    const mock = createMockAuthoringBackend()
    const sid = await mock.begin(buildContourOps('P-2', 'test', L, 10))
    expect((await mock.simulate(sid)).valid).toBe(true)
    const res = await mock.commit(sid, 'P-2')
    const display = await res.display.getDisplay()
    // 6 segment walls + 2 caps — the drawn L, not a canned box
    expect(display.render.faces).toHaveLength(8)
  })
})

describe('backend lane selection (Codex1 B2 — the desktop NEVER mocks)', () => {
  it('browser dev (no bridge) → the badged mock', () => {
    expect(chooseBackendLane(false, null)).toBe('mock')
    expect(chooseBackendLane(false, 'ws-1')).toBe('mock')
  })

  it('desktop without a workspace → UNAVAILABLE, never the mock', () => {
    expect(chooseBackendLane(true, null)).toBe('unavailable')
  })

  it('desktop with a workspace → the real bridge', () => {
    expect(chooseBackendLane(true, 'ws-1')).toBe('bridge')
  })

  it('the unavailable backend cannot begin (no mock-commit path exists)', async () => {
    const b = createUnavailableBackend()
    expect(b.isReal).toBe(true) // never badged as a dev mock
    await expect(b.begin([{ kind: 'create_part', params: {} }])).rejects.toThrow(
      /No workspace is open/,
    )
  })
})

describe('EP1 — commit-at-New + plane threading through the mock lane', () => {
  it('a create_part-only commit yields the EMPTY display (the dev mirror of A4)', async () => {
    const { buildCreatePartOps } = await import('./backend')
    const mock = createMockAuthoringBackend()
    const sid = await mock.begin(buildCreatePartOps('P-000123', 'Bracket'))
    expect((await mock.simulate(sid)).valid).toBe(true)
    const res = await mock.commit(sid, 'P-000123')
    const display = await res.display.getDisplay()
    expect(display.render.faces).toHaveLength(0) // emptiness, not a canned box
    expect(display.identity.object_number).toBe('P-000123')
  })

  it('feature ops on an existing Part carry the picked plane into the display orientation', async () => {
    const { buildContourFeatureOps } = await import('./backend')
    const mock = createMockAuthoringBackend()
    const ops = buildContourFeatureOps('P-000123', L, 10, 'yz', 'feat_0001')
    expect(ops).toHaveLength(2) // NO create_part — features on the ACTIVE Part
    expect(ops[0].params.plane).toEqual({ kind: 'principal', orientation: 'yz' })
    expect(ops[1].params.direction).toBe('normal+') // EP2 canonical vocabulary
    const sid = await mock.begin(ops)
    const res = await mock.commit(sid, 'P-000123')
    const display = await res.display.getDisplay()
    // The yz frame sweeps along +X: the drawn L (u≤60, v≤50) lands on y/z.
    expect(display.render.bbox_max[0]).toBeCloseTo(10) // the depth, along +X
    expect(display.render.bbox_max[1]).toBeCloseTo(60) // u → +Y
    expect(display.render.bbox_max[2]).toBeCloseTo(50) // v → +Z
  })
})

describe('the fail-closed authoring target (Codex5 B2)', () => {
  it('the REAL lane refuses to sketch without a trustworthy target; the dev lane never does', async () => {
    const { sketchAuthoringGate } = await import('./backend')
    expect(sketchAuthoringGate(true, false)).toMatch(/Create a Part with New/)
    expect(sketchAuthoringGate(true, true)).toBeNull()
    expect(sketchAuthoringGate(false, false)).toBeNull() // the badged dev lane
    expect(sketchAuthoringGate(false, true)).toBeNull()
  })

  it('loading a DIFFERENT canonical Part clears the target; the SAME Part keeps it', async () => {
    const { reconcileLoadedPart } = await import('./backend')
    const active = { number: 'P-000001', name: 'A', featureCount: 2 }
    expect(reconcileLoadedPart(active, 'P-000002')).toBeNull() // fail closed
    expect(reconcileLoadedPart(active, 'P-000001')).toBe(active)
    expect(reconcileLoadedPart(null, 'P-000002')).toBeNull()
  })
})

describe('provisional part numbers (Codex2 B2)', () => {
  it('suggestions are well-formed P-NNNNNN across the whole random range', () => {
    expect(suggestPartNumber(() => 0)).toBe('P-000000')
    expect(suggestPartNumber(() => 0.9999999)).toBe('P-999999')
    expect(PART_NUMBER_RE.test(suggestPartNumber())).toBe(true)
  })

  it('the format gate rejects non-canonical numbers', () => {
    for (const bad of ['P-12345', 'P-1234567', 'X-123456', 'p-123456', '123456', 'P-12A456']) {
      expect(PART_NUMBER_RE.test(bad)).toBe(false)
    }
  })
})
