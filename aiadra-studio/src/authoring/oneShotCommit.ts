/**
 * The ONE-SHOT commit controller (arc 20260714-2 EP1; Codex5 B1).
 *
 * `sessionLifecycle` retains a failed session because its surfaces (dashboard/
 * pad) offer retry/Cancel to roll it back. Commit-at-New has NO retained
 * surface — the dialog is gone — so a one-shot run must be self-cleaning:
 *
 *  - every terminal failure AWAITS the rollback of any open session before
 *    returning (no orphaned main/bridge drafts, ADR/0043 D4);
 *  - the caller passes `isStale()` (context invalidation — e.g. the workspace
 *    changed underneath); a stale result is reported as such so the caller
 *    NEVER installs state from a dead context, while the terminal commit
 *    itself stays uninterruptible (a stale successful commit still exists in
 *    Truth — reported honestly, just not installed);
 *  - the caller owns the busy publication (this run must sit inside the same
 *    operation gate as every other start — the Workbench wires that).
 */
import type { AuthoringBackend, CommitResult, FeatureOp } from './backend'

export type OneShotResult =
  | { status: 'committed'; result: CommitResult }
  /** The commit SUCCEEDED but the context moved on — do NOT install anything. */
  | { status: 'committed-stale'; result: CommitResult }
  | { status: 'failed'; reason: string }

export async function runOneShotCommit(
  backend: AuthoringBackend,
  ops: FeatureOp[],
  objectRef: string,
  isStale: () => boolean = () => false,
): Promise<OneShotResult> {
  let sid: string | null = null
  const rollback = async () => {
    if (sid === null) return
    const s = sid
    sid = null
    try {
      await backend.rollback(s) // AWAITED — the one-shot has no retry surface
    } catch {
      /* best-effort; bridge-exit clears sessions server-side (D4) */
    }
  }
  try {
    sid = await backend.begin(ops)
    if (isStale()) {
      await rollback()
      return { status: 'failed', reason: 'the workspace context changed during creation' }
    }
    const sim = await backend.simulate(sid)
    if (!sim.valid) {
      await rollback()
      return { status: 'failed', reason: sim.message ?? 'validation failed' }
    }
    const result = await backend.commit(sid, objectRef)
    sid = null // committed — the backend closed the session
    return isStale() ? { status: 'committed-stale', result } : { status: 'committed', result }
  } catch (e) {
    await rollback()
    return { status: 'failed', reason: e instanceof Error ? e.message : String(e) }
  }
}
