/**
 * The pre-mount display coordinator (S2; Codex5 B1.1 — completing Codex4
 * B1.1+B1.5). Commit-at-New from Home adopts a Part while NO viewport exists
 * yet; the display install must still be part of the Part transition's JOIN:
 *
 *  - `defer()` returns a promise the transition's `installDisplay` awaits —
 *    partContext stays `loading` until the MOUNTED viewport actually installs
 *    the source (or fails: the rejection reaches the join → fail-closed
 *    `error`), never `ready` on a merely-queued display;
 *  - deferring anew SETTLES the superseded entry (its transition is already
 *    generation-dead — it resolves harmlessly and joins as a no-op) — an old
 *    transition promise is never left hanging;
 *  - `cancel()` (workspace clear / leaving before mount) settles likewise;
 *  - `drain()` (the mount effect) installs ONLY if the deferring transition
 *    still holds its generation (`stillCurrent`), then settles the promise.
 *
 * Pure/injected so the whole contract is testable without a viewport.
 */
import type { DisplaySource } from '../display/displaySource'

interface Pending {
  src: DisplaySource
  stillCurrent: () => boolean
  resolve: () => void
  reject: (e: unknown) => void
}

export interface PendingDisplayCoordinator {
  /** Queue a pre-mount install; the returned promise settles when the mounted
   *  viewport installs (or fails), or when superseded/cancelled. */
  defer(src: DisplaySource, stillCurrent: () => boolean): Promise<void>
  /** The mount effect: install the queued source iff its transition still
   *  holds the generation, and settle its promise either way. */
  drain(install: (src: DisplaySource) => Promise<void>): Promise<void>
  /** Settle and drop any queued work (workspace clear / close-to-Home). */
  cancel(): void
  /** True when a deferred install is queued (introspection for tests). */
  hasPending(): boolean
}

export function createPendingDisplayCoordinator(): PendingDisplayCoordinator {
  let pending: Pending | null = null

  const settleSuperseded = () => {
    // The superseded transition is generation-dead: resolving lets its join
    // complete as a silent no-op (stillCurrent() is false there).
    pending?.resolve()
    pending = null
  }

  return {
    defer(src, stillCurrent) {
      settleSuperseded()
      return new Promise<void>((resolve, reject) => {
        pending = { src, stillCurrent, resolve, reject }
      })
    },

    async drain(install) {
      const p = pending
      if (!p) return
      pending = null
      if (!p.stillCurrent()) {
        p.resolve() // stale — never installs, but the old join completes
        return
      }
      try {
        await install(p.src)
        p.resolve()
      } catch (e) {
        p.reject(e) // the transition join publishes fail-closed `error`
      }
    },

    cancel: settleSuperseded,
    hasPending: () => pending !== null,
  }
}
