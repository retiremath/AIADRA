/**
 * The profile terminal — ONE owner for Close (Codex6 B2).
 *
 * The lane's `close()` hands over an intent and KEEPS the session open; this
 * runner performs the transaction and reports the outcome back through
 * exactly one of `confirmClosed()` / `commitFailed()`. The postconditions it
 * exists to guarantee:
 *
 *   * a FAILED commit rolls the draft back and leaves the drawing session
 *     alive with the refusal surfaced — recoverable, never silently cleared;
 *   * a generation change during the round trip can never install a STALE
 *     success: the commit stands in Truth, but its display is not adopted
 *     into a Part context it no longer describes;
 *   * begin→commit run under the no-orphan discipline — a draft opened here
 *     is committed or rolled back, never abandoned.
 *
 * Pure orchestration over injected seams, so the production wiring and the
 * tests drive the SAME code.
 */
import type { DisplaySource } from '../display/displaySource'

export interface CloseIntent {
  kind: string
  params: Record<string, unknown>
}

export interface CloseBackend {
  begin(ops: { kind: string; params: Record<string, unknown> }[]): Promise<{ sessionId: string }>
  commit(sessionId: string, objectRef: string): Promise<{ display: DisplaySource }>
  rollback(sessionId: string): Promise<void>
}

export interface CloseLane {
  confirmClosed(): void
  commitFailed(message: string): void
}

export interface CloseDeps {
  backend: CloseBackend
  lane: CloseLane
  partNumber: string
  /** LIVE generation getter — read again after the commit settles. */
  generation: () => number
  /** Install the refreshed display into the Part context. */
  adopt: (display: DisplaySource) => void
}

export type CloseOutcome = 'committed' | 'stale-success' | 'failed'

export async function runProfileClose(intent: CloseIntent, deps: CloseDeps): Promise<CloseOutcome> {
  const generationAtStart = deps.generation()

  let sessionId: string
  try {
    const begun = await deps.backend.begin([{ kind: intent.kind, params: intent.params }])
    sessionId = begun.sessionId
  } catch (e) {
    // Nothing was opened; nothing to roll back. The session survives.
    deps.lane.commitFailed(e instanceof Error ? e.message : String(e))
    return 'failed'
  }

  let display: DisplaySource
  try {
    const done = await deps.backend.commit(sessionId, deps.partNumber)
    display = done.display
  } catch (e) {
    // The no-orphan discipline: a draft opened by this runner is committed
    // or rolled back — never left for the bridge to time out on.
    try {
      await deps.backend.rollback(sessionId)
    } catch {
      // the bridge death case: the draft died with it (ADR/0043 D4)
    }
    deps.lane.commitFailed(e instanceof Error ? e.message : String(e))
    return 'failed'
  }

  if (deps.generation() !== generationAtStart) {
    // The commit stands in Truth, but the Part context has moved on — the
    // new generation's own refresh is the display authority now. Installing
    // this display would be a stale success (Codex6 B2). The session still
    // ends: the feature exists, and keeping the drawing open would invite a
    // double commit.
    deps.lane.confirmClosed()
    return 'stale-success'
  }

  deps.adopt(display)
  deps.lane.confirmClosed()
  return 'committed'
}
