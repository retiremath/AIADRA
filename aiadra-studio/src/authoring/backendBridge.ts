/**
 * The Electron-bridge AuthoringBackend (arc 20260711-11 / slice 1b; ADR/0043).
 *
 * Wraps the session-capability write verbs (`opBegin`/`opAdd`/`opSimulate`/
 * `opCommit`/`opRollback`) over `window.aiadra`. Real Ring-2 → engine → display.
 * The renderer holds only the opaque `operationSessionId` main minted; it never
 * supplies paths or touches the engine draft. `previewSource` is intentionally
 * absent — the bridge has no draft-display primitive yet, so commit shows the
 * real geometry (a fast-follow adds live preview once the engine exposes it).
 */
import { createBridgeSource } from '../display/displaySource'
import type { AuthoringBackend, CommitResult, FeatureOp, SimulateResult } from './backend'

function unwrap<T>(env: { ok: true; result: T } | { ok: false; error: { message: string } }): T {
  if (!env.ok) throw new Error(env.error.message)
  return env.result
}

export function createBridgeAuthoringBackend(workspaceId: string): AuthoringBackend {
  const b = window.aiadra
  if (!b?.opBegin || !b.opAdd || !b.opSimulate || !b.opCommit || !b.opRollback) {
    throw new Error('authoring bridge unavailable (run as the desktop app)')
  }

  return {
    isReal: true,
    async begin(ops: FeatureOp[]): Promise<string> {
      if (ops.length === 0) throw new Error('empty op sequence')
      const [first, ...rest] = ops
      const { operationSessionId } = unwrap(await b.opBegin!(workspaceId, first.kind, first.params))
      // Codex3 B1: an opened session must not orphan if a later opAdd fails —
      // roll it back before rethrowing so main/bridge don't keep a dead draft.
      try {
        for (const op of rest) {
          unwrap(await b.opAdd!(operationSessionId, op.kind, op.params))
        }
      } catch (e) {
        try {
          await b.opRollback!(operationSessionId)
        } catch {
          /* best-effort cleanup; surface the original failure */
        }
        throw e
      }
      return operationSessionId
    },
    async simulate(sessionId: string): Promise<SimulateResult> {
      const { report } = unwrap(await b.opSimulate!(sessionId))
      return { valid: report.valid, message: report.valid ? undefined : 'validation failed' }
    },
    async commit(sessionId: string, objectRef: string): Promise<CommitResult> {
      const r = unwrap(await b.opCommit!(sessionId, objectRef))
      // The engine returned the refreshed identity (ADR/0043 D3); the display
      // reloads from the canonical lane over the same bridge.
      return { objectRef: r.object_ref ?? objectRef, display: createBridgeSource(workspaceId, r.object_ref ?? objectRef) }
    },
    async rollback(sessionId: string): Promise<void> {
      unwrap(await b.opRollback!(sessionId))
    },
  }
}
