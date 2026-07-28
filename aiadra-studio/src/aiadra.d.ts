// Types for the preload-exposed, allowlisted bridge API (electron/preload.ts).
// `window.aiadra` is optional: in browser-only dev (`npm run dev:web`, no Electron)
// it is undefined, so the UI degrades gracefully.
import type { DisplayRepresentation, ViewDependentPayload } from './display/contract'
import type { PersistedSettings } from './settings/persisted'

export {}

type Envelope<T> = { ok: true; result: T } | { ok: false; error: { message: string } }

/** One structured deletion blocker (ADR/0004 SCN arc 20260728-3 B2): a live
 * relationship reference that refuses delete_object. Deterministically sorted
 * by core; Studio renders the list without reinterpreting it. */
export interface DeletionBlocker {
  relationship_id: string
  relationship_type: string
  source_object: { uuid: string; number: string }
  candidate_role: 'source' | 'endpoint'
  state: 'working' | 'released'
  revision_id?: string
}

/** A view request for displayHlr (contract v1.1; arc 20260609-2). `direction`
 * is the unit LOOK direction (eye → scene); `up` must not be parallel to it. */
export interface HlrViewRequest {
  view_id: string
  projection?: 'orthographic'
  origin?: [number, number, number]
  direction: [number, number, number]
  up: [number, number, number]
}

declare global {
  interface Window {
    aiadra?: {
      ping(): Promise<Envelope<{ pong: boolean }>>
      coreVersion(): Promise<Envelope<{ version: string }>>
      chooseWorkspace(): Promise<Envelope<{ workspaceId: string; name: string }>>
      inspect(workspaceId: string, objectRef: string): Promise<Envelope<{ object: unknown }>>
      /** Part identity list for the opened workspace (arc 20260610-1 Codex1 B1)
       * — the object-ref source for the canonical display lane. */
      listParts(
        workspaceId: string,
      ): Promise<Envelope<{ parts: { object_number: string; name: string; object_uuid: string }[] }>>
      /** Delete a working Part (ADR/0004 SCN arc 20260728-3): the standalone
       * Ring-2 deletion Transaction. A referential-integrity refusal comes
       * back STRUCTURED (deleted:false + blockers) — Studio renders it,
       * never reinterprets it. */
      deleteObject(
        workspaceId: string,
        objectNumber: string,
        reason: string,
      ): Promise<
        Envelope<{
          deleted: boolean
          commit?: unknown
          refusal?: { message: string; blockers: DeletionBlocker[] }
        }>
      >
      displayRepresentation(
        workspaceId: string,
        objectRef: string,
      ): Promise<Envelope<{ display: DisplayRepresentation }>>
      displayHlr(
        workspaceId: string,
        objectRef: string,
        views: HlrViewRequest[],
        algorithm?: 'exact' | 'poly',
      ): Promise<Envelope<{ view_dependent: ViewDependentPayload }>>
      // Authoring session — the Ring-2 WRITE lane (arc 20260711-11; ADR/0043).
      // Optional: absent in browser-only dev (the AuthoringBackend uses a mock there).
      // S2 (arc 20260714-3 Codex1 B1): both mutating verbs return the op's
      // ENGINE-minted createdFeatureIds — the renderer NEVER predicts feat ids.
      opBegin?(
        workspaceId: string,
        kind: string,
        params: unknown,
      ): Promise<Envelope<{ operationSessionId: string; createdFeatureIds: string[] }>>
      opAdd?(
        operationSessionId: string,
        kind: string,
        params: unknown,
      ): Promise<Envelope<{ createdFeatureIds: string[] }>>
      opSimulate?(
        operationSessionId: string,
      ): Promise<Envelope<{ report: { valid: boolean } & Record<string, unknown> }>>
      opCommit?(
        operationSessionId: string,
        objectRef: string,
      ): Promise<Envelope<{ commit: unknown; object_ref?: string; display?: DisplayRepresentation }>>
      opRollback?(operationSessionId: string): Promise<Envelope<{ rolled_back: boolean }>>
      // Recent workspaces (arc 20260714-1; D-H4/Codex6 B3) — durable MAIN-owned
      // registry; views only ({recentId, name, lastOpened} — no paths), and a
      // reopen re-validates + mints a FRESH workspaceId. Optional: absent in
      // browser-only dev.
      /** Retire a live workspace capability (Codex1 B1 — the central transition
       *  calls this on Close/switch). Optional: absent in browser-only dev. */
      closeWorkspace?(workspaceId: string): Promise<Envelope<{ closed: boolean }>>
      recentsList?(): Promise<
        Envelope<{ recents: { recentId: string; name: string; lastOpened: string }[] }>
      >
      recentsRemove?(
        recentId: string,
      ): Promise<Envelope<{ recents: { recentId: string; name: string; lastOpened: string }[] }>>
      recentsClear?(): Promise<Envelope<{ recents: [] }>>
      reopenWorkspace?(recentId: string): Promise<Envelope<{ workspaceId: string; name: string }>>
      // App settings (arc 20260619-1 / 6a) — optional: absent in browser-only dev.
      loadSettings?(): Promise<Envelope<{ settings: PersistedSettings | null }>>
      saveSettings?(settings: PersistedSettings): Promise<Envelope<Record<string, never>>>
    }
  }
}
