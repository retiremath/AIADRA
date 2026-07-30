import { describe, it, expect, vi } from 'vitest'
import { runProfileClose, type CloseDeps } from './profileCloseRunner'
import type { DisplaySource } from '../display/displaySource'

const INTENT = {
  kind: 'mechanical.author_profile_sketch',
  params: { part_number: 'P-000001', profile: {} },
}
const DISPLAY = { tag: 'refreshed' } as unknown as DisplaySource

function deps(overrides: Partial<CloseDeps> = {}) {
  const lane = { confirmClosed: vi.fn(), commitFailed: vi.fn() }
  const backend = {
    begin: vi.fn(async () => ({ sessionId: 'op-1' })),
    commit: vi.fn(async () => ({ display: DISPLAY })),
    rollback: vi.fn(async () => {}),
  }
  const adopt = vi.fn()
  const d: CloseDeps = {
    backend,
    lane,
    partNumber: 'P-000001',
    generation: () => 7,
    adopt,
    ...overrides,
  }
  return { d, lane, backend, adopt }
}

describe('the ONE profile terminal (Codex6 B2)', () => {
  it('success: begin → commit → adopt → confirmClosed, in that order', async () => {
    const { d, lane, backend, adopt } = deps()
    const outcome = await runProfileClose(INTENT, d)
    expect(outcome).toBe('committed')
    expect(backend.begin).toHaveBeenCalledWith([INTENT])
    expect(backend.commit).toHaveBeenCalledWith('op-1', 'P-000001')
    expect(adopt).toHaveBeenCalledWith(DISPLAY)
    expect(lane.confirmClosed).toHaveBeenCalledOnce()
    expect(lane.commitFailed).not.toHaveBeenCalled()
    expect(backend.rollback).not.toHaveBeenCalled()
  })

  it('a FAILED commit rolls the draft back and leaves the session recoverable', async () => {
    const { d, lane, backend, adopt } = deps()
    backend.commit.mockRejectedValueOnce(new Error('the engine refused the graph'))
    const outcome = await runProfileClose(INTENT, d)
    expect(outcome).toBe('failed')
    // the no-orphan discipline: the draft this runner opened is closed
    expect(backend.rollback).toHaveBeenCalledWith('op-1')
    // the failure is SURFACED into the still-open session, never swallowed
    expect(lane.commitFailed).toHaveBeenCalledWith('the engine refused the graph')
    expect(lane.confirmClosed).not.toHaveBeenCalled()
    expect(adopt).not.toHaveBeenCalled()
  })

  it('a failed BEGIN has nothing to roll back and still surfaces the refusal', async () => {
    const { d, lane, backend } = deps()
    backend.begin.mockRejectedValueOnce(new Error('bridge exited'))
    const outcome = await runProfileClose(INTENT, d)
    expect(outcome).toBe('failed')
    expect(backend.rollback).not.toHaveBeenCalled()
    expect(lane.commitFailed).toHaveBeenCalledWith('bridge exited')
  })

  it('a rollback failure (dead bridge) does not mask the ORIGINAL refusal', async () => {
    const { d, lane, backend } = deps()
    backend.commit.mockRejectedValueOnce(new Error('validation failed'))
    backend.rollback.mockRejectedValueOnce(new Error('engine bridge exited'))
    const outcome = await runProfileClose(INTENT, d)
    expect(outcome).toBe('failed')
    expect(lane.commitFailed).toHaveBeenCalledWith('validation failed')
  })

  it('a GENERATION change during the round trip never installs stale success', async () => {
    const { lane, backend, adopt } = deps()
    let generation = 7
    backend.commit.mockImplementationOnce(async () => {
      generation = 8 // the workspace moved on mid-flight
      return { display: DISPLAY }
    })
    const outcome = await runProfileClose(INTENT, {
      backend,
      lane,
      partNumber: 'P-000001',
      generation: () => generation,
      adopt,
    })
    expect(outcome).toBe('stale-success')
    // the commit stands in Truth, but its display is NOT adopted into a
    // Part context it no longer describes...
    expect(adopt).not.toHaveBeenCalled()
    // ...and the session still ends — the feature exists, so keeping the
    // drawing open would invite a double commit.
    expect(lane.confirmClosed).toHaveBeenCalledOnce()
  })
})
