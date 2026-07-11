/**
 * Candidate preview controller (arc 20260711-10 / MVP-1; Codex B2).
 *
 * The operation store is the source of truth and its actions are PURE — the
 * async `setDisplaySource` lives here, driven off `selectedCandidateId`. Rules
 * (B2): a monotonically increasing request id so a stale load can never win
 * after a newer selection/cancel; and an INTENTIONAL restore of the prior
 * display when the session ends (cancel), rather than leaving a candidate on
 * screen. The viewport stays a projection of the session.
 */
import { useEffect, useRef, type MutableRefObject } from 'react'
import type { ViewportApi } from '../Viewport'
import { loadCandidateSource } from './candidateSource'
import { selectedCandidate, useOperation, type OperationStore } from './store'

export interface PreviewControllerOptions {
  store: OperationStore
  viewportApi: MutableRefObject<ViewportApi | null>
  ready: boolean
  /** Re-load the pre-session display when a session ends (cancel). Idempotent. */
  restoreBaseDisplay?: () => void
}

/** Pure test seam: given the request id captured at dispatch and the latest id,
 *  may this load apply its result? Only the newest selection wins (B2). */
export function isLatestPreviewRequest(dispatched: number, latest: number): boolean {
  return dispatched === latest
}

export function useCandidatePreview({
  store,
  viewportApi,
  ready,
  restoreBaseDisplay,
}: PreviewControllerOptions): void {
  const op = useOperation(store)
  const sel = selectedCandidate(op)
  const selId = sel?.id ?? null
  const reqRef = useRef(0)
  const hadSelectionRef = useRef(false)

  useEffect(() => {
    if (!ready) return
    const req = ++reqRef.current

    if (sel) {
      hadSelectionRef.current = true
      let cancelled = false
      loadCandidateSource(sel)
        .then((src) => {
          // Drop the result if this effect was torn down OR a newer selection
          // has since been dispatched (B2 — only the latest request may apply).
          if (cancelled || !src || !isLatestPreviewRequest(req, reqRef.current)) return
          void viewportApi.current?.setDisplaySource(src)
        })
        .catch(() => {
          /* preview load failed — the badge/error surface stays as-is */
        })
      return () => {
        cancelled = true
      }
    }

    // No selection. If we had one (the session just ended/cancelled), restore
    // the prior display intentionally rather than leaving a stale candidate.
    if (hadSelectionRef.current) {
      hadSelectionRef.current = false
      restoreBaseDisplay?.()
    }
    // Depend on the selected candidate id only: a pattern change reloads; pure
    // re-renders do not. (Per-param geometry reactivity lands with distinct
    // baked bracket fixtures — candidateSource NOTE.)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, selId])
}
