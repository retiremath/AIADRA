// Types for the preload-exposed, allowlisted bridge API (electron/preload.ts).
// `window.aiadra` is optional: in browser-only dev (`npm run dev:web`, no Electron)
// it is undefined, so the UI degrades gracefully.
import type { DisplayRepresentation, ViewDependentPayload } from './display/contract'

export {}

type Envelope<T> = { ok: true; result: T } | { ok: false; error: { message: string } }

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
    }
  }
}
