import { describe, it, expect, vi } from 'vitest'
import { createWorkspaceSwitcher, isCloseAcked, type SwitcherDeps } from './switcher'

function deps(blocked: string | null = null) {
  return {
    isBlocked: vi.fn(() => blocked),
    clearContext: vi.fn(),
    releaseWorkspace: vi.fn(async (_id: string) => true),
    apply: vi.fn(),
  } satisfies SwitcherDeps & Record<string, ReturnType<typeof vi.fn>>
}

const A = { workspaceId: 'ws-A', name: 'alpha' }
const B = { workspaceId: 'ws-B', name: 'beta' }

describe('workspace switcher (Codex1 B1 + Codex2 B3 — gated, transition-owned, acked)', () => {
  it('a grant that resolves AFTER the gate went active is refused AND the fresh id retired', async () => {
    const d = deps('Finish or cancel the active operation first')
    const sw = createWorkspaceSwitcher(d)
    expect(await sw.adopt(A)).toMatch(/active operation/)
    expect(d.releaseWorkspace).toHaveBeenCalledWith('ws-A') // the leak Codex2 B3 named
    expect(d.clearContext).not.toHaveBeenCalled()
    expect(d.apply).not.toHaveBeenCalled()
    expect(sw.current()).toBeNull()
  })

  it('A→B: A retirement is AWAITED and ACKED before clear/apply; order is release → clear → apply', async () => {
    const order: string[] = []
    const d = deps()
    d.clearContext.mockImplementation(() => order.push('clear'))
    d.releaseWorkspace.mockImplementation(async (id: string) => {
      order.push(`release:${id}`)
      return true
    })
    d.apply.mockImplementation((ws) => order.push(`apply:${ws?.workspaceId ?? 'null'}`))
    const sw = createWorkspaceSwitcher(d)
    expect(await sw.adopt(A)).toBeNull()
    expect(await sw.adopt(B)).toBeNull()
    expect(order).toEqual(['clear', 'apply:ws-A', 'release:ws-A', 'clear', 'apply:ws-B'])
    expect(sw.current()).toEqual(B)
  })

  it('an UNACKED release aborts the switch: old context intact, fresh id retired, reason returned', async () => {
    const d = deps()
    d.releaseWorkspace.mockImplementation(async (id: string) => id !== 'ws-A') // A won't release
    const sw = createWorkspaceSwitcher(d)
    await sw.adopt(A)
    d.clearContext.mockClear()
    d.apply.mockClear()
    expect(await sw.adopt(B)).toMatch(/could not release workspace 'alpha'/)
    expect(d.releaseWorkspace).toHaveBeenCalledWith('ws-B') // fresh id retired
    expect(d.clearContext).not.toHaveBeenCalled() // old context untouched
    expect(d.apply).not.toHaveBeenCalled()
    expect(sw.current()).toEqual(A) // A stays current
  })

  it('a rejected release is treated as unacked (no silent swallow)', async () => {
    const d = deps()
    let first = true
    d.releaseWorkspace.mockImplementation(async () => {
      if (first) {
        first = false
        throw new Error('bridge down')
      }
      return true
    })
    const sw = createWorkspaceSwitcher(d)
    await sw.adopt(A)
    expect(await sw.adopt(B)).toMatch(/could not release/)
    expect(sw.current()).toEqual(A)
  })

  it('an overtaking adopt during an in-flight transition is refused and its fresh id retired', async () => {
    const d = deps()
    let releaseGate!: () => void
    const gatePromise = new Promise<boolean>((r) => (releaseGate = () => r(true)))
    // A's release hangs (keyed by id — other retirements resolve normally).
    d.releaseWorkspace.mockImplementation(async (id: string) => (id === 'ws-A' ? gatePromise : true))
    const sw = createWorkspaceSwitcher(d)
    await sw.adopt(A)
    const slow = sw.adopt(B) // in flight, awaiting A's release
    const overtake = await sw.adopt({ workspaceId: 'ws-C', name: 'gamma' })
    expect(overtake).toMatch(/transition is in flight/)
    expect(d.releaseWorkspace).toHaveBeenCalledWith('ws-C') // overtaker retired
    releaseGate()
    expect(await slow).toBeNull()
    expect(sw.current()).toEqual(B)
  })

  it('re-adopting the SAME workspace never releases its live capability', async () => {
    const d = deps()
    const sw = createWorkspaceSwitcher(d)
    await sw.adopt(A)
    await sw.adopt({ ...A })
    expect(d.releaseWorkspace).not.toHaveBeenCalled()
    expect(sw.current()?.workspaceId).toBe('ws-A')
  })

  it('work that becomes active DURING A→B aborts before apply and retires the fresh id (Codex3 B1)', async () => {
    const d = deps()
    // The op gate is free at the pre-check, then an operation starts while A's
    // release is awaited — the re-check must catch it.
    d.isBlocked
      .mockReturnValueOnce(null) // adopt(A) pre-check
      .mockReturnValueOnce(null) // adopt(B) pre-check
      .mockReturnValueOnce('Finish or cancel the active operation first') // re-check
    const sw = createWorkspaceSwitcher(d)
    await sw.adopt(A)
    d.clearContext.mockClear()
    d.apply.mockClear()
    expect(await sw.adopt(B)).toMatch(/active operation/)
    expect(d.apply).not.toHaveBeenCalled() // B never exposed
    expect(d.clearContext).not.toHaveBeenCalled()
    expect(d.releaseWorkspace).toHaveBeenCalledWith('ws-B') // fresh id retired
    expect(sw.current()).toEqual(A) // state, not just invocation
  })

  it('an UNACKED fresh-id retirement is RETAINED in pending cleanup and retried on the next transition', async () => {
    const d = deps('busy') // every adopt refused at the gate
    d.releaseWorkspace.mockResolvedValue(false) // ...and its retirement unacked
    const sw = createWorkspaceSwitcher(d)
    await sw.adopt(B)
    expect(sw.pendingCleanup()).toEqual(['ws-B']) // retained, not dropped

    // The gate lifts and retirement starts acking: the next transition retries.
    d.isBlocked.mockReturnValue(null)
    d.releaseWorkspace.mockResolvedValue(true)
    expect(await sw.adopt(A)).toBeNull()
    expect(d.releaseWorkspace).toHaveBeenCalledWith('ws-B') // retried
    expect(sw.pendingCleanup()).toEqual([]) // acked → cleared
    expect(sw.current()).toEqual(A)
  })

  it('isCloseAcked demands the TYPED acknowledgement, not just ok (Codex3 B1)', () => {
    expect(isCloseAcked({ ok: true, result: { closed: true } })).toBe(true)
    expect(isCloseAcked({ ok: true, result: { closed: false } })).toBe(false) // ok alone ≠ ack
    expect(isCloseAcked({ ok: true, result: {} })).toBe(false)
    expect(isCloseAcked({ ok: false })).toBe(false)
    expect(isCloseAcked(null)).toBe(false)
  })

  it('close awaits the ack then applies null; an unacked close refuses and keeps the workspace', async () => {
    const d = deps()
    const sw = createWorkspaceSwitcher(d)
    await sw.adopt(A)
    expect(await sw.close()).toBeNull()
    expect(d.apply).toHaveBeenLastCalledWith(null)
    expect(sw.current()).toBeNull()

    const d2 = deps()
    d2.releaseWorkspace.mockImplementation(async () => false)
    const sw2 = createWorkspaceSwitcher(d2)
    await sw2.adopt(A) // a fresh adopt with no prior workspace releases nothing
    expect(await sw2.close()).toMatch(/could not release/)
    expect(sw2.current()).toEqual(A)
  })
})
