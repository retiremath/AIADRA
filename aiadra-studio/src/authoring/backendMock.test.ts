import { describe, it, expect } from 'vitest'
import { createMockAuthoringBackend } from './backendMock'
import { buildContourOps } from './backend'
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
