import { describe, it, expect, vi } from 'vitest'
import { createSessionLifecycle } from './sessionLifecycle'
import type { AuthoringBackend, CommitResult } from './backend'

const DISPLAY = { kind: 'fixture', badge: 'test', snapViews: [], getDisplay: async () => ({}) as never, getHlr: async () => ({}) as never } as never

function fakeBackend(overrides: Partial<AuthoringBackend> = {}): AuthoringBackend & {
  rollback: ReturnType<typeof vi.fn>
} {
  let n = 0
  return {
    isReal: false,
    begin: vi.fn(async () => `S${++n}`),
    simulate: vi.fn(async () => ({ valid: true })),
    commit: vi.fn(async (_sid: string, objectRef: string): Promise<CommitResult> => ({ objectRef, display: DISPLAY })),
    rollback: vi.fn(async () => {}),
    ...overrides,
  } as never
}

function hooks() {
  return { onBusy: vi.fn(), onError: vi.fn(), onSuccess: vi.fn() }
}

const OPS = [{ kind: 'create_part', params: {} }]

describe('sessionLifecycle (Codex3 B1 → Codex6 B1, one shared implementation)', () => {
  it('success: commits, clears the session, no rollback; cancel afterwards is clean', async () => {
    const b = fakeBackend()
    const lc = createSessionLifecycle(b)
    const h = hooks()
    await lc.run(OPS, 'P-1', h)
    expect(h.onBusy).toHaveBeenCalled()
    expect(h.onSuccess).toHaveBeenCalledWith(expect.objectContaining({ objectRef: 'P-1' }))
    expect(b.rollback).not.toHaveBeenCalled()
    expect(lc.cancel()).toBe(true) // nothing retained — no rollback
    expect(b.rollback).not.toHaveBeenCalled()
  })

  it('simulate failure: rolls the session back and reports the error', async () => {
    const b = fakeBackend({ simulate: vi.fn(async () => ({ valid: false, message: 'bad ring' })) })
    const lc = createSessionLifecycle(b)
    const h = hooks()
    await lc.run(OPS, 'P-1', h)
    expect(b.rollback).toHaveBeenCalledWith('S1')
    expect(h.onError).toHaveBeenCalledWith('bad ring')
    expect(h.onSuccess).not.toHaveBeenCalled()
  })

  it('thrown commit: RETAINS the session; Cancel rolls it back (no lost handle)', async () => {
    const b = fakeBackend({ commit: vi.fn(async () => { throw new Error('engine down') }) })
    const lc = createSessionLifecycle(b)
    const h = hooks()
    await lc.run(OPS, 'P-1', h)
    expect(h.onError).toHaveBeenCalledWith('engine down')
    expect(b.rollback).not.toHaveBeenCalled() // retained, not dropped
    expect(lc.cancel()).toBe(true)
    expect(b.rollback).toHaveBeenCalledWith('S1') // Cancel rolled back the retained session
  })

  it('retry after a failed commit: discards the retained stale session BEFORE beginning anew', async () => {
    const commit = vi
      .fn()
      .mockRejectedValueOnce(new Error('flaky'))
      .mockImplementation(async (_sid: string, objectRef: string) => ({ objectRef, display: DISPLAY }))
    const b = fakeBackend({ commit })
    const lc = createSessionLifecycle(b)
    await lc.run(OPS, 'P-1', hooks()) // fails; retains S1
    const h2 = hooks()
    await lc.run(OPS, 'P-2', h2) // retry
    expect(b.rollback).toHaveBeenCalledWith('S1') // stale discarded first
    expect(h2.onSuccess).toHaveBeenCalledWith(expect.objectContaining({ objectRef: 'P-2' }))
    expect(b.begin).toHaveBeenCalledTimes(2)
  })

  it('cancel DURING the terminal run refuses (uninterruptible — the Escape path)', async () => {
    let release!: () => void
    const gate = new Promise<void>((r) => (release = r))
    const b = fakeBackend({
      commit: vi.fn(async (_sid: string, objectRef: string) => {
        await gate
        return { objectRef, display: DISPLAY }
      }),
    })
    const lc = createSessionLifecycle(b)
    const h = hooks()
    const running = lc.run(OPS, 'P-1', h)
    await vi.waitFor(() => expect(lc.isRunning()).toBe(true))
    expect(lc.cancel()).toBe(false) // refused mid-commit
    release()
    await running
    expect(h.onSuccess).toHaveBeenCalled() // the run completed untouched
    expect(b.rollback).not.toHaveBeenCalled()
  })

  it('a second run while one is in flight is a no-op', async () => {
    let release!: () => void
    const gate = new Promise<void>((r) => (release = r))
    const b = fakeBackend({ simulate: vi.fn(async () => { await gate; return { valid: true } }) })
    const lc = createSessionLifecycle(b)
    const first = lc.run(OPS, 'P-1', hooks())
    await vi.waitFor(() => expect(lc.isRunning()).toBe(true))
    const h2 = hooks()
    await lc.run(OPS, 'P-2', h2) // ignored
    expect(h2.onBusy).not.toHaveBeenCalled()
    release()
    await first
    expect(b.begin).toHaveBeenCalledTimes(1)
  })
})
