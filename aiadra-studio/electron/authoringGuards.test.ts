import { describe, it, expect, vi } from 'vitest'
import { extractCreatedFeatureIds, finalizeBegunAuthoring } from './authoringGuards'

describe('extractCreatedFeatureIds (Codex2 — validated response arrays)', () => {
  it('accepts a valid array (including empty — create_part mints no features)', () => {
    expect(extractCreatedFeatureIds({ created_feature_ids: [] })).toEqual([])
    expect(extractCreatedFeatureIds({ created_feature_ids: ['feat_0001'] })).toEqual(['feat_0001'])
  })

  it('returns the error message on a missing array or non-string entries', () => {
    expect(extractCreatedFeatureIds({ session_id: 'S1' })).toMatch(/missing created_feature_ids/)
    expect(extractCreatedFeatureIds({ created_feature_ids: ['feat_0001', 7] })).toMatch(/non-empty strings/)
    expect(extractCreatedFeatureIds({ created_feature_ids: [''] })).toMatch(/non-empty strings/)
    expect(extractCreatedFeatureIds(null)).toMatch(/missing created_feature_ids/)
  })
})

describe('finalizeBegunAuthoring (Codex3 B3 — cleanup owns the begun draft)', () => {
  it('valid ids: registers the capability, no rollback', async () => {
    const io = { register: vi.fn(), unregister: vi.fn(), rollback: vi.fn(async () => true) }
    const r = await finalizeBegunAuthoring({ created_feature_ids: ['feat_0001'] }, io)
    expect(r).toEqual({ ok: true, ids: ['feat_0001'] })
    expect(io.register).toHaveBeenCalledTimes(1)
    expect(io.rollback).not.toHaveBeenCalled()
    expect(io.unregister).not.toHaveBeenCalled()
  })

  it('malformed ids: AWAITED rollback runs BEFORE the error returns; the acked discard unregisters', async () => {
    const order: string[] = []
    const io = {
      register: vi.fn(() => order.push('register')),
      unregister: vi.fn(() => order.push('unregister')),
      rollback: vi.fn(async () => {
        await new Promise((res) => setTimeout(res, 5)) // prove it is AWAITED
        order.push('rolled-back')
        return true
      }),
    }
    const r = await finalizeBegunAuthoring({ session_id: 'S1' }, io)
    expect(r.ok).toBe(false)
    // register-first (never unreachable) → awaited rollback → unregister.
    expect(order).toEqual(['register', 'rolled-back', 'unregister'])
  })

  it('malformed ids + FAILED rollback: the capability is RETAINED (no silent orphan)', async () => {
    const io = { register: vi.fn(), unregister: vi.fn(), rollback: vi.fn(async () => false) }
    const r = await finalizeBegunAuthoring({ session_id: 'S1' }, io)
    expect(r.ok).toBe(false)
    expect(io.register).toHaveBeenCalledTimes(1)
    expect(io.unregister).not.toHaveBeenCalled() // still reachable via opRollback / bridge exit
  })
})
