/**
 * Main-boundary guards for the authoring write lane (S2; arc 20260714-3).
 *
 * Pure/injected so the capability-lifecycle rules are TESTABLE outside
 * Electron (same pattern as appProtocol.ts/recents.ts):
 *
 *  - `extractCreatedFeatureIds` — Codex2's "validated response arrays at every
 *    boundary": main never forwards an unvalidated bridge payload.
 *  - `finalizeBegunAuthoring` — Codex3 B3: once `authoring_begin` SUCCEEDS the
 *    bridge owns a live draft, so main owns cleanup for every later
 *    validation failure. The capability registers FIRST (the draft is never
 *    unreachable); malformed ids trigger an AWAITED rollback (unregister only
 *    on an acked discard — a failed rollback RETAINS the capability so
 *    opRollback/bridge-exit clearing can still reach the draft, D4).
 */

/** Validate a bridge response's `created_feature_ids`. Returns the ids array,
 *  or the error MESSAGE (string) when the payload is malformed. */
export function extractCreatedFeatureIds(result: unknown): string[] | string {
  const raw = (result as { created_feature_ids?: unknown } | null)?.created_feature_ids
  if (!Array.isArray(raw)) return 'bridge response missing created_feature_ids array'
  if (!raw.every((id) => typeof id === 'string' && id.length > 0)) {
    return 'bridge response created_feature_ids must be non-empty strings'
  }
  return raw as string[]
}

export interface BegunSessionIO {
  /** Register the session capability (main's authoringSessions map). */
  register(): void
  /** Forget the capability — ONLY after an acked discard. */
  unregister(): void
  /** Awaited bridge `authoring_rollback`; true = the draft was discarded. */
  rollback(): Promise<boolean>
}

/** Settle a SUCCESSFUL `authoring_begin` response: validate its ids with full
 *  cleanup ownership. Returns the validated ids, or the error message after
 *  the awaited cleanup ran. */
export async function finalizeBegunAuthoring(
  result: unknown,
  io: BegunSessionIO,
): Promise<{ ok: true; ids: string[] } | { ok: false; error: string }> {
  io.register()
  const ids = extractCreatedFeatureIds(result)
  if (typeof ids === 'string') {
    if (await io.rollback()) io.unregister()
    return { ok: false, error: ids }
  }
  return { ok: true, ids }
}
