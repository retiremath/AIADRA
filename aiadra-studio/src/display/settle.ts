/**
 * Camera-settle / staleness state machine (arc 20260610-1, Claude1 P4).
 * Pure module — no three.js, no IPC, injected scheduler; deterministic and
 * unit-testable.
 *
 * Discipline (ADR/0033 D6 + ADR/0036 economics):
 *  - HLR is requested ONLY after the camera has been still for `settleMs`,
 *    never per-frame.
 *  - Every settle issues a sequence-numbered request; a response is accepted
 *    only if it is the CURRENT sequence and the camera has not moved since the
 *    request was issued — anything else is stale and dropped.
 *  - Any camera movement immediately clears the attached overlay (no ghost
 *    overlays from the previous view); the attach identity gate itself
 *    (`checkAttachHlr`) is the caller's job on accept.
 */

export type Cancel = () => void

export interface SettleMachineOptions {
  settleMs: number
  /** Injected scheduler (setTimeout-shaped); returns a cancel function. */
  schedule: (fn: () => void, ms: number) => Cancel
  /** Fired once per settle — issue the HLR request carrying this sequence. */
  onSettle: (seq: number) => void
  /** Fired on the first movement after an overlay-relevant state — clear it. */
  onClear: () => void
}

export interface SettleMachine {
  /** Call on every camera change (orbit/pan/zoom/snap). */
  cameraMoved: () => void
  /** Validate an arriving response. 'accept' at most once per sequence. */
  response: (seq: number) => 'accept' | 'stale'
  /** Stop scheduling; further responses are stale. */
  dispose: () => void
}

export function createSettleMachine(opts: SettleMachineOptions): SettleMachine {
  let seq = 0
  let activeSeq: number | null = null // request in flight for the still camera
  let accepted = false // a response was accepted (an overlay may be attached)
  let pendingCancel: Cancel | null = null
  let disposed = false

  const fire = () => {
    pendingCancel = null
    activeSeq = ++seq
    opts.onSettle(activeSeq)
  }

  return {
    cameraMoved() {
      if (disposed) return
      pendingCancel?.()
      // Invalidate any in-flight request AND any attached overlay — once per
      // movement burst (onClear is not re-fired while already clean).
      if (activeSeq !== null || accepted) {
        activeSeq = null
        accepted = false
        opts.onClear()
      }
      pendingCancel = opts.schedule(fire, opts.settleMs)
    },
    response(respSeq: number) {
      if (disposed) return 'stale'
      if (respSeq !== activeSeq) return 'stale'
      // Accept exactly once: a duplicate frame for the same sequence is stale.
      activeSeq = null
      accepted = true
      return 'accept'
    },
    dispose() {
      disposed = true
      pendingCancel?.()
      pendingCancel = null
      activeSeq = null
      accepted = false
    },
  }
}
