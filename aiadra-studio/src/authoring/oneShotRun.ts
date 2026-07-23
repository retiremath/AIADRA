/**
 * The persistent ONE-SHOT runner (Codex26 B3 → Codex27 B3) — the
 * single-flight owner for dashboard-less single-op commands (the F2b
 * References write), built AROUND the canonical `runOneShotCommit`
 * controller (EP1 Codex5 B1), which AWAITS rollback on every terminal
 * failure. No fire-and-forget cleanup exists on this path:
 *
 *  - a terminal hook fires ONLY after `runOneShotCommit` has settled, and
 *    that controller awaits the rollback of any open session first — when
 *    `onError` runs, the backend's open-session set is provably empty
 *    (tested against a fake BACKEND with observably-async rollback);
 *  - SINGLE-FLIGHT with truthful busy: `start()` returns false
 *    synchronously for a duplicate activation — the caller shows a note
 *    and must NOT touch its busy publication (the accepted run owns it
 *    until ITS terminal settles);
 *  - the workspace/generation staleness distinction is the controller's:
 *    a stale SUCCESS reports `onStaleSuccess` (Truth committed; nothing
 *    installs into the moved-on context).
 */
import type { AuthoringBackend, CommitResult, FeatureOp } from './backend'
import { runOneShotCommit } from './oneShotCommit'

export interface OneShotHooks {
  /** Terminal-time staleness check (workspace/Part/generation authority). */
  isStale: () => boolean
  onError: (message: string) => void
  onSuccess: (result: CommitResult) => void
  /** The commit LANDED on the committed target, but the live context moved
   *  on — nothing is installed; the caller decides how to phrase it. */
  onStaleSuccess: (objectRef: string) => void
}

export interface OneShotRunner {
  isBusy(): boolean
  /** Returns false SYNCHRONOUSLY when a run is already in flight (the
   *  duplicate is rejected; the accepted run's busy state is untouched).
   *  Returns true when this activation started; exactly one terminal hook
   *  will fire after the controller settles. */
  start(ops: FeatureOp[], objectRef: string, hooks: OneShotHooks): boolean
}

export function createOneShotRunner(backend: AuthoringBackend): OneShotRunner {
  let busy = false
  return {
    isBusy: () => busy,
    start(ops, objectRef, hooks) {
      if (busy) return false
      busy = true
      void (async () => {
        try {
          const out = await runOneShotCommit(backend, ops, objectRef, hooks.isStale)
          busy = false
          if (out.status === 'committed') hooks.onSuccess(out.result)
          else if (out.status === 'committed-stale') hooks.onStaleSuccess(objectRef)
          else hooks.onError(out.reason)
        } catch (e) {
          // defense in depth: the controller catches its own path; anything
          // beyond it still clears busy and reports
          busy = false
          hooks.onError(e instanceof Error ? e.message : String(e))
        }
      })()
      return true
    },
  }
}
