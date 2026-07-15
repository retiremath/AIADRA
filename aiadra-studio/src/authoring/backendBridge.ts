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
import {
  assertCreatedFeatureIds,
  resolveOpAliases,
  type AuthoringBackend,
  type BeginResult,
  type CommitResult,
  type FeatureOp,
  type SimulateResult,
} from './backend'

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
    async begin(ops: FeatureOp[]): Promise<BeginResult> {
      if (ops.length === 0) throw new Error('empty op sequence')
      // S2 (Codex1 B1): each response carries the op's ENGINE-minted feature
      // ids; `{ $fromOp: n }` aliases resolve here against those ids — the
      // wire only ever carries real engine ids, never a renderer prediction.
      const perOpIds: string[][] = []
      const [first, ...rest] = ops
      // opIndex 0 has no earlier products — a $fromOp here fails loud in the
      // resolver instead of leaking an alias object over IPC.
      const firstParams = resolveOpAliases(first.params, 0, perOpIds) as Record<string, unknown>
      const begun = unwrap(await b.opBegin!(workspaceId, first.kind, firstParams))
      const operationSessionId = begun.operationSessionId
      if (typeof operationSessionId !== 'string' || operationSessionId.length === 0) {
        // No capability came back — nothing this side can roll back.
        throw new Error('opBegin: response is missing operationSessionId')
      }
      // Codex3 arc-11 B1 → S2 Codex3 B3: from here a session EXISTS — every
      // later failure (including the FIRST response's own id validation) must
      // roll it back before rethrowing so main/bridge don't keep a dead draft.
      try {
        perOpIds.push(assertCreatedFeatureIds(begun.createdFeatureIds, 'opBegin'))
        for (const [i, op] of rest.entries()) {
          const params = resolveOpAliases(op.params, i + 1, perOpIds) as Record<string, unknown>
          const added = unwrap(await b.opAdd!(operationSessionId, op.kind, params))
          perOpIds.push(assertCreatedFeatureIds(added.createdFeatureIds, 'opAdd'))
        }
      } catch (e) {
        try {
          await b.opRollback!(operationSessionId)
        } catch {
          /* best-effort cleanup; surface the original failure */
        }
        throw e
      }
      return { sessionId: operationSessionId, createdFeatureIds: perOpIds }
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
