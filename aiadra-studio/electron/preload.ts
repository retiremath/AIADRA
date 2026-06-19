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
})
