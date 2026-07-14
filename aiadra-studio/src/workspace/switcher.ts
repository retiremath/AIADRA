/**
 * The workspace switcher (arc 20260714-1; Codex1 B1 + Codex2 B3 + Codex3 B1) —
 * ONE owner of the current-workspace state and ONE gated, TRANSITION-OWNED
 * async adoption that every surface routes through.
 *
 * Invariants:
 *  - adopt/close REFUSE (returning the reason) while an authoring op or an
 *    operation session is active, or while another transition is in flight;
 *  - the transition itself is PUBLISHED (`onTransition`) so the Workbench gates
 *    every OPERATION START (ribbon authoring, New, the AI entry) for the whole
 *    async window — the other half of the context-integrity invariant
 *    (Codex3 B1: an op must not start against A while A→B awaits retirement);
 *  - adopt RE-CHECKS the operation gate after its awaited work and before
 *    clear/apply (defence in depth) — B is never exposed under work that
 *    became active mid-transition;
 *  - a freshly minted capability that cannot be adopted is retired; if that
 *    retirement is itself unacknowledged, the id is RETAINED in pending-cleanup
 *    state and retried on subsequent transitions — never silently dropped;
 *  - the previous capability's retirement is AWAITED and must be ACKED before
 *    the new workspace becomes current; a failed release aborts the switch;
 *  - a same-workspace re-adopt never releases the live capability.
 */
import type { OpenedWorkspace } from '../home/HomeShared'

export interface SwitcherDeps {
  /** The OPERATION gate (authoring/op-session): a reason, or null when free.
   *  Must NOT include the transition itself (the switcher owns that). */
  isBlocked(): string | null
  /** Clear display + selection + transient badges of the OLD context. */
  clearContext(): void
  /** Retire a main-side workspace capability; resolves true ONLY on a real ack. */
  releaseWorkspace(workspaceId: string): Promise<boolean>
  /** Commit the new current workspace (null = none) to the application state. */
  apply(ws: OpenedWorkspace | null): void
  /** Published transition state — include it in every operation-start gate. */
  onTransition?(active: boolean): void
}

export interface WorkspaceSwitcher {
  current(): OpenedWorkspace | null
  /** Fresh-capability ids whose retirement is not yet acknowledged. */
  pendingCleanup(): string[]
  adopt(ws: OpenedWorkspace): Promise<string | null>
  close(): Promise<string | null>
}

/** The typed close acknowledgement (Codex3 B1): `ok` alone is not an ack. */
export function isCloseAcked(env: { ok: boolean; result?: { closed?: boolean } } | null | undefined): boolean {
  return !!env && env.ok && env.result?.closed === true
}

export function createWorkspaceSwitcher(deps: SwitcherDeps): WorkspaceSwitcher {
  let cur: OpenedWorkspace | null = null
  let transitioning = false
  const pending = new Set<string>()

  const setTransition = (active: boolean) => {
    transitioning = active
    deps.onTransition?.(active)
  }

  const tryRelease = async (id: string): Promise<boolean> => {
    try {
      return await deps.releaseWorkspace(id)
    } catch {
      return false
    }
  }

  /** Retire a fresh, unadoptable capability; retain it on an unacked release. */
  const retireFresh = async (ws: OpenedWorkspace) => {
    // Never retire the LIVE capability on a refused same-id re-adopt.
    if (cur && cur.workspaceId === ws.workspaceId) return
    if (!(await tryRelease(ws.workspaceId))) pending.add(ws.workspaceId)
  }

  /** Retry previously unacknowledged retirements (best-effort, acked removed). */
  const retryPending = async () => {
    for (const id of [...pending]) {
      if (await tryRelease(id)) pending.delete(id)
    }
  }

  return {
    current: () => cur,
    pendingCleanup: () => [...pending],

    async adopt(ws) {
      if (transitioning) {
        await retireFresh(ws)
        return 'another workspace transition is in flight'
      }
      const blocked = deps.isBlocked()
      if (blocked) {
        await retireFresh(ws) // the grant resolved after the gate went active
        return blocked
      }
      setTransition(true)
      try {
        await retryPending()
        if (cur && cur.workspaceId !== ws.workspaceId) {
          if (!(await tryRelease(cur.workspaceId))) {
            await retireFresh(ws)
            return `could not release workspace '${cur.name}' — try again`
          }
        }
        // Codex3 B1 defence in depth: re-check the OPERATION gate after the
        // awaited work — never expose the new workspace under work that became
        // active mid-transition.
        const blockedNow = deps.isBlocked()
        if (blockedNow) {
          await retireFresh(ws)
          return blockedNow
        }
        deps.clearContext()
        cur = ws
        deps.apply(ws)
        return null
      } finally {
        setTransition(false)
      }
    },

    async close() {
      if (transitioning) return 'another workspace transition is in flight'
      const blocked = deps.isBlocked()
      if (blocked) return blocked
      setTransition(true)
      try {
        await retryPending()
        if (cur) {
          if (!(await tryRelease(cur.workspaceId))) {
            return `could not release workspace '${cur.name}' — try again`
          }
        }
        deps.clearContext()
        cur = null
        deps.apply(null)
        return null
      } finally {
        setTransition(false)
      }
    },
  }
}
