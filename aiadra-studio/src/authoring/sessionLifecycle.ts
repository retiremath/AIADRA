/**
 * Shared authoring-session lifecycle (arc 20260711-11; Codex3 B1 → Codex6 B1).
 *
 * ONE implementation of the begin→simulate→commit orchestration carrying the
 * no-orphan invariant (ADR/0043 D4) for EVERY authoring surface (the extrude
 * FeatureDashboard, the SketchPad — and slice-2 fillet/chamfer next), so the
 * protections cannot drift apart per surface:
 *
 *  - the active backend session id is RETAINED across begin/simulate/commit
 *    error paths — a failed commit keeps the handle, so retry discards it and
 *    Cancel rolls it back (never an orphaned draft, never a lost handle);
 *  - a retained stale session is rolled back BEFORE a retry begins a new one;
 *  - the terminal path is uninterruptible: `cancel()` REFUSES while a run is in
 *    flight (button guards + the Escape handler both go through it);
 *  - a generation token additionally invalidates any in-flight result after a
 *    successful cancel (belt-and-braces: a dead surface can never update the
 *    viewport or touch a session late).
 */
import type { AuthoringBackend, CommitResult, FeatureOp } from './backend'

export interface RunHooks {
  /** The run started (set the surface's busy phase). */
  onBusy(): void
  /** Terminal failure — validation or a thrown backend error. */
  onError(message: string): void
  /** Terminal success — the commit result (display + objectRef). */
  onSuccess(res: CommitResult): void
}

export interface SessionLifecycle {
  /** True while a begin→simulate→commit run is in flight (uninterruptible). */
  isRunning(): boolean
  /** Run one begin→simulate→commit. No-op if a run is already in flight. */
  run(ops: FeatureOp[], objectRef: string, hooks: RunHooks): Promise<void>
  /**
   * Cancel the surface's backend state: refuses (returns false) while the
   * terminal run is in flight; otherwise invalidates in-flight results and
   * rolls back a retained (e.g. failed-commit) session. Returns true when the
   * caller may proceed to close its UI.
   */
  cancel(): boolean
}

export function createSessionLifecycle(backend: AuthoringBackend): SessionLifecycle {
  let session: string | null = null
  let gen = 0
  let running = false

  return {
    isRunning: () => running,

    async run(ops, objectRef, hooks) {
      if (running) return
      const myGen = gen
      // A retained session from a prior failed attempt is stale — discard it
      // before beginning a new one (Codex6 B1: retry cleanup).
      if (session) {
        const stale = session
        session = null
        await backend.rollback(stale).catch(() => {})
      }
      running = true
      hooks.onBusy()
      try {
        const sid = await backend.begin(ops)
        if (myGen !== gen) {
          await backend.rollback(sid).catch(() => {})
          return
        }
        session = sid
        const sim = await backend.simulate(sid)
        if (myGen !== gen || !sim.valid) {
          session = null
          await backend.rollback(sid).catch(() => {})
          if (myGen === gen) hooks.onError(sim.message ?? 'validation failed')
          return
        }
        const res = await backend.commit(sid, objectRef)
        session = null // committed — the backend closed the session
        if (myGen !== gen) return // cancelled late: the object exists, but this surface is dead
        hooks.onSuccess(res)
      } catch (e) {
        // The backend session may still be open; keep the handle retained so
        // the user can retry (discards it) or cancel (rolls it back).
        if (myGen === gen) hooks.onError(e instanceof Error ? e.message : String(e))
      } finally {
        running = false
      }
    },

    cancel() {
      if (running) return false // the terminal commit is uninterruptible
      gen++ // invalidate any in-flight async result
      const sid = session
      session = null
      if (sid) void backend.rollback(sid).catch(() => {})
      return true
    },
  }
}
