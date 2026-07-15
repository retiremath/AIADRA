import { describe, it, expect, vi } from 'vitest'
import { runOneShotCommit } from './oneShotCommit'
import type { AuthoringBackend, CommitResult } from './backend'

const DISPLAY = { kind: 'fixture', badge: 't', snapViews: [], getDisplay: async () => ({}) as never, getHlr: async () => ({}) as never } as never

function fakeBackend(overrides: Partial<AuthoringBackend> = {}) {
  return {
    isReal: false,
    begin: vi.fn(async () => ({ sessionId: 'S1', createdFeatureIds: [] as string[][] })),
    simulate: vi.fn(async () => ({ valid: true })),
    commit: vi.fn(async (_s: string, objectRef: string): Promise<CommitResult> => ({ objectRef, display: DISPLAY })),
    rollback: vi.fn(async () => {}),
    ...overrides,
  } as AuthoringBackend & Record<string, ReturnType<typeof vi.fn>>
}

const OPS = [{ kind: 'create_part', params: {} }]

describe('the one-shot commit (Codex5 B1 — self-cleaning, stale-aware)', () => {
  it('success installs nothing itself and needs no rollback', async () => {
    const b = fakeBackend()
    const r = await runOneShotCommit(b, OPS, 'P-1')
    expect(r.status).toBe('committed')
    expect(b.rollback).not.toHaveBeenCalled()
  })

  it('a THROWN commit AWAITS the rollback before returning — no orphaned session', async () => {
    const order: string[] = []
    const b = fakeBackend({
      commit: vi.fn(async () => {
        order.push('commit-threw')
        throw new Error('engine down')
      }),
      rollback: vi.fn(async () => {
        await new Promise((res) => setTimeout(res, 5)) // prove it is AWAITED
        order.push('rolled-back')
      }),
    })
    const r = await runOneShotCommit(b, OPS, 'P-1')
    expect(r).toEqual({ status: 'failed', reason: 'engine down' })
    expect(order).toEqual(['commit-threw', 'rolled-back']) // completed BEFORE return
    expect(b.rollback).toHaveBeenCalledWith('S1')
  })

  it('an invalid simulation rolls back (awaited) and reports the reason', async () => {
    const b = fakeBackend({ simulate: vi.fn(async () => ({ valid: false, message: 'bad ring' })) })
    const r = await runOneShotCommit(b, OPS, 'P-1')
    expect(r).toEqual({ status: 'failed', reason: 'bad ring' })
    expect(b.rollback).toHaveBeenCalledWith('S1')
  })

  it('a context that goes STALE after begin rolls back and fails — nothing to install', async () => {
    let stale = false
    const b = fakeBackend({
      begin: vi.fn(async () => {
        stale = true // e.g. a workspace switch resolved mid-flight
        return { sessionId: 'S1', createdFeatureIds: [] as string[][] }
      }),
    })
    const r = await runOneShotCommit(b, OPS, 'P-1', () => stale)
    expect(r.status).toBe('failed')
    expect(b.rollback).toHaveBeenCalledWith('S1')
    expect(b.commit).not.toHaveBeenCalled()
  })

  it('a commit that lands after the context went stale is reported committed-STALE (exists in Truth; never installed)', async () => {
    let stale = false
    const b = fakeBackend({
      commit: vi.fn(async (_s: string, objectRef: string) => {
        stale = true // the context died during the uninterruptible terminal commit
        return { objectRef, display: DISPLAY }
      }),
    })
    const r = await runOneShotCommit(b, OPS, 'P-1', () => stale)
    expect(r.status).toBe('committed-stale')
    expect(b.rollback).not.toHaveBeenCalled() // the commit is real — nothing to roll back
  })
})
