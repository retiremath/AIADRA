/**
 * Race-safe, coalesced preview requests (ADR/0044 A4; arc 20260730-1).
 *
 * The preview is an engine SOLVE behind an IPC round trip, driven by pointer
 * movement — so two failure modes are structural rather than unlucky:
 *
 *   1. A stale reply landing after a newer one would paint geometry the user
 *      has already moved past. The monotonic request id makes that impossible:
 *      only the newest dispatch may apply. (Same rule as the candidate
 *      preview controller, for the same reason.)
 *
 *   2. Firing a solve per pointer event would queue solves faster than they
 *      complete. Requests coalesce: while one is in flight the latest payload
 *      is held, and exactly one follow-up runs when it settles — never a
 *      backlog, and never a dropped FINAL state.
 *
 * A refusal is a normal outcome, not an error: an intermediate graph the
 * engine will not admit (a collapsed segment mid-drag) must leave the drawing
 * session alive. Only a transport failure is exceptional.
 */
import type { ProfileGraphPreview } from '../display/contract'

export interface PreviewResult {
  preview: ProfileGraphPreview | null
  refusal: { message: string } | null
}

export type PreviewFn<Req> = (request: Req) => Promise<PreviewResult>

export interface Requester<Req> {
  /** Ask for a preview of `request`. Coalesces while one is in flight. */
  request(request: Req): void
  /** Drop any pending/in-flight result — nothing more will be applied. */
  cancel(): void
  /** True while a solve is outstanding (for a subtle busy affordance). */
  isBusy(): boolean
}

export interface RequesterOptions<Req> {
  run: PreviewFn<Req>
  apply: (result: PreviewResult) => void
  /** Transport failure — NOT an engine refusal, which arrives via `apply`. */
  onError?: (error: unknown) => void
}

/** Pure test seam: may a reply dispatched at `dispatched` still apply? */
export function isLatest(dispatched: number, latest: number): boolean {
  return dispatched === latest
}

export function createPreviewRequester<Req>({
  run,
  apply,
  onError,
}: RequesterOptions<Req>): Requester<Req> {
  let seq = 0
  let inFlight = false
  let queued: { req: Req } | null = null
  let cancelled = false

  const dispatch = (req: Req): void => {
    seq += 1
    const mine = seq
    inFlight = true
    run(req)
      .then((result) => {
        // Two independent guards: a newer request supersedes this reply, and
        // a cancel invalidates every outstanding one.
        if (cancelled || !isLatest(mine, seq)) return
        apply(result)
      })
      .catch((e) => {
        if (cancelled || !isLatest(mine, seq)) return
        onError?.(e)
      })
      .finally(() => {
        if (!isLatest(mine, seq)) return
        inFlight = false
        const next = queued
        queued = null
        if (next && !cancelled) dispatch(next.req)
      })
  }

  return {
    request(req) {
      cancelled = false
      if (inFlight) {
        // Hold only the LATEST — intermediate states the user has already
        // drawn past are not worth a solve.
        queued = { req }
        return
      }
      dispatch(req)
    },
    cancel() {
      cancelled = true
      queued = null
      // Bump the sequence so every outstanding reply is already stale.
      seq += 1
      inFlight = false
    },
    isBusy() {
      return inFlight
    },
  }
}
