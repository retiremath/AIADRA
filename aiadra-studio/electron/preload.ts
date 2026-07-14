import { contextBridge, ipcRenderer } from 'electron'

/**
 * Preload — the ONLY bridge between renderer and main (ADR/0032 D6; Codex1 B1).
 * Exposes a narrow, allowlisted `window.aiadra` API via contextBridge. Raw
 * `ipcRenderer`, `shell`, Node, and filesystem are NEVER exposed. The renderer
 * cannot supply arbitrary paths — it holds opaque `workspaceId` capabilities
 * minted by main (Codex1 B2).
 */
contextBridge.exposeInMainWorld('aiadra', {
  ping: () => ipcRenderer.invoke('aiadra:ping'),
  coreVersion: () => ipcRenderer.invoke('aiadra:coreVersion'),
  chooseWorkspace: () => ipcRenderer.invoke('aiadra:chooseWorkspace'),
  inspect: (workspaceId: string, objectRef: string) =>
    ipcRenderer.invoke('aiadra:inspect', { workspaceId, objectRef }),
  listParts: (workspaceId: string) => ipcRenderer.invoke('aiadra:listParts', { workspaceId }),
  displayRepresentation: (workspaceId: string, objectRef: string) =>
    ipcRenderer.invoke('aiadra:displayRepresentation', { workspaceId, objectRef }),
  displayHlr: (
    workspaceId: string,
    objectRef: string,
    views: unknown[],
    algorithm?: 'exact' | 'poly',
  ) => ipcRenderer.invoke('aiadra:displayHlr', { workspaceId, objectRef, views, algorithm }),
  // Authoring session — the Ring-2 WRITE lane (arc 20260711-11; ADR/0043).
  // The renderer holds an opaque operationSessionId minted by main; it never
  // supplies paths or touches the engine draft directly.
  opBegin: (workspaceId: string, kind: string, params: unknown) =>
    ipcRenderer.invoke('aiadra:opBegin', { workspaceId, kind, params }),
  opAdd: (operationSessionId: string, kind: string, params: unknown) =>
    ipcRenderer.invoke('aiadra:opAdd', { operationSessionId, kind, params }),
  opSimulate: (operationSessionId: string) =>
    ipcRenderer.invoke('aiadra:opSimulate', { operationSessionId }),
  opCommit: (operationSessionId: string, objectRef: string) =>
    ipcRenderer.invoke('aiadra:opCommit', { operationSessionId, objectRef }),
  opRollback: (operationSessionId: string) =>
    ipcRenderer.invoke('aiadra:opRollback', { operationSessionId }),
  // Recent workspaces (arc 20260714-1; D-H4/Codex6 B3) — durable MAIN-owned
  // registry; the renderer sees {recentId, name, lastOpened} views only, and a
  // reopen re-validates + mints a FRESH workspaceId (a renewed user grant).
  closeWorkspace: (workspaceId: string) =>
    ipcRenderer.invoke('aiadra:closeWorkspace', { workspaceId }),
  recentsList: () => ipcRenderer.invoke('aiadra:recentsList'),
  recentsRemove: (recentId: string) => ipcRenderer.invoke('aiadra:recentsRemove', { recentId }),
  recentsClear: () => ipcRenderer.invoke('aiadra:recentsClear'),
  reopenWorkspace: (recentId: string) =>
    ipcRenderer.invoke('aiadra:reopenWorkspace', { recentId }),
  // App settings (arc 20260619-1 / 6a) — local userData JSON, main-owned path.
  loadSettings: () => ipcRenderer.invoke('aiadra:loadSettings'),
  saveSettings: (settings: unknown) => ipcRenderer.invoke('aiadra:saveSettings', { settings }),
})
