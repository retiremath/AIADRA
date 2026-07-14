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
