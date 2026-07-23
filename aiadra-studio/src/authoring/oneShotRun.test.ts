import { describe, it, expect } from 'vitest'
import { createOneShotRunner, type OneShotHooks } from './oneShotRun'
import type { AuthoringBackend, FeatureOp } from './backend'

/** Codex27 B3: the runner is proven against a fake BACKEND (not a fake
 *  lifecycle) — commit throws, rollback is OBSERVABLY asynchronous, and the
 *  terminal hook fires only after the backend's open-session set is empty.
 *  Busy truth stays attached to the ACCEPTED run: a rejected duplicate
 *  cannot clear it. */

const OPS: FeatureOp[] = [{ kind: 'mechanical.add_reference_sketch', params: { part_number: 'P-1' } }]

function fakeBackend(behavior: {
  commit: 'ok' | 'throw'
  commitGate?: Promise<void>
}) {
  const open = new Set<string>()
  let n = 0
  const backend = {
    isReal: false,
    async begin(_ops: FeatureOp[]) {
      const sessionId = `s-${++n}`
      open.add(sessionId)
      return { sessionId }
    },
    async simulate(_sid: string) {
      return { valid: true }
    },
    async commit(sid: string, _ref: string) {
      if (behavior.commitGate) await behavior.commitGate
      if (behavior.commit === 'throw') throw new Error('commit exploded')
      open.delete(sid)
      return { display: { tag: 'fresh' } }
    },
    async rollback(sid: string) {
      // OBSERVABLY asynchronous — a fire-and-forget caller would race this
      await new Promise((r) => setTimeout(r, 10))
      open.delete(sid)
    },
  } as unknown as AuthoringBackend
  return { backend, open }
}

function terminal() {
  let resolve!: (v: { kind: string; openAtTerminal: number }) => void
  const settled = new Promise<{ kind: string; openAtTerminal: number }>((r) => {
    resolve = r
  })
  const make = (open: Set<string>): OneShotHooks => ({
    isStale: () => false,
    onError: () => resolve({ kind: 'error', openAtTerminal: open.size }),
    onSuccess: () => resolve({ kind: 'success', openAtTerminal: open.size }),
    onStaleSuccess: () => resolve({ kind: 'stale', openAtTerminal: open.size }),
  })
  return { settled, make }
}

describe('createOneShotRunner (Codex27 B3 — awaited cleanup, truthful busy)', () => {
  it('a thrown commit leaves NO open backend session when the terminal fires', async () => {
    const { backend, open } = fakeBackend({ commit: 'throw' })
    const runner = createOneShotRunner(backend)
    const t = terminal()
    expect(runner.start(OPS, 'P-1', t.make(open))).toBe(true)
    const out = await t.settled
    expect(out.kind).toBe('error')
    // the AWAITED rollback completed BEFORE the terminal hook — no orphan
    expect(out.openAtTerminal).toBe(0)
    expect(open.size).toBe(0)
    expect(runner.isBusy()).toBe(false)
  })

  it('a rapid second activation is rejected synchronously and begins NO transaction', async () => {
    let release!: () => void
    const gate = new Promise<void>((r) => {
      release = r
    })
    const { backend, open } = fakeBackend({ commit: 'ok', commitGate: gate })
    const runner = createOneShotRunner(backend)
    const t = terminal()
    expect(runner.start(OPS, 'P-1', t.make(open))).toBe(true)
    expect(runner.isBusy()).toBe(true)
    // the duplicate: rejected WITHOUT any hook firing — the caller shows a
    // note and must not touch the accepted run's busy publication
    expect(runner.start(OPS, 'P-1', t.make(open))).toBe(false)
    expect(open.size).toBe(1) // exactly ONE session ever began
    // busy stays TRUE until the ORIGINAL terminal settles (gate truth)
    expect(runner.isBusy()).toBe(true)
    release()
    const out = await t.settled
    expect(out.kind).toBe('success')
    expect(runner.isBusy()).toBe(false)
  })

  it('a context change AFTER commit yields exactly committed-stale — nothing installs, Truth is reported', async () => {
    // Codex28 N1: deterministic — fresh at the begin-time check, stale at
    // the after-commit check, so the canonical controller's committed-stale
    // transition (not the begin-time failed path) is the one exercised.
    const { backend, open } = fakeBackend({ commit: 'ok' })
    const runner = createOneShotRunner(backend)
    let staleCalls = 0
    let resolve!: (v: string) => void
    const settled = new Promise<string>((r) => {
      resolve = r
    })
    runner.start(OPS, 'P-1', {
      isStale: () => ++staleCalls > 1, // false at begin; true after commit
      onError: () => resolve('error'),
      onSuccess: () => resolve('success'),
      onStaleSuccess: (ref) => resolve(`stale:${ref}`),
    })
    expect(await settled).toBe('stale:P-1')
    expect(open.size).toBe(0)
    expect(runner.isBusy()).toBe(false)
  })

  it('sequential runs reuse the one runner (persistent owner)', async () => {
    const { backend, open } = fakeBackend({ commit: 'ok' })
    const runner = createOneShotRunner(backend)
    for (let i = 0; i < 2; i++) {
      const t = terminal()
      expect(runner.start(OPS, 'P-1', t.make(open))).toBe(true)
      expect((await t.settled).kind).toBe('success')
    }
    expect(open.size).toBe(0)
  })
})
