// Types for the preload-exposed, allowlisted bridge API (electron/preload.ts).
// `window.aiadra` is optional: in browser-only dev (`npm run dev:web`, no Electron)
// it is undefined, so the UI degrades gracefully.
export {}

type Envelope<T> = { ok: true; result: T } | { ok: false; error: { message: string } }

declare global {
  interface Window {
    aiadra?: {
      ping(): Promise<Envelope<{ pong: boolean }>>
      coreVersion(): Promise<Envelope<{ version: string }>>
      chooseWorkspace(): Promise<Envelope<{ workspaceId: string; name: string; path: string }>>
      inspect(workspaceId: string, objectRef: string): Promise<Envelope<{ object: unknown }>>
    }
  }
}
