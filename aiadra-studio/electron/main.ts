import { randomUUID } from 'node:crypto'
import { type ChildProcessWithoutNullStreams, spawn } from 'node:child_process'
import { existsSync, realpathSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { app, BrowserWindow, dialog, ipcMain } from 'electron'

/**
 * AIADRA Studio — Electron main process (ADR/0032 D6; arc 20260602-6).
 *
 * Security (Codex1 B1) is enforced here EXPLICITLY: contextIsolation + sandbox
 * on, nodeIntegration off, webSecurity on, navigation + window-open denied, only
 * the Vite dev URL / built local app loaded. The renderer reaches the engine
 * ONLY through the allowlisted, schema-validated IPC handlers below — never raw
 * fs/shell/ipcRenderer.
 *
 * Capabilities (Codex1 B2): the renderer never supplies arbitrary paths. It asks
 * main to open a workspace (native dialog); main canonicalizes + validates it,
 * stores it under an opaque `workspaceId`, and only that id crosses the wire.
 */

let win: BrowserWindow | null = null
let bridge: ChildProcessWithoutNullStreams | null = null

// ---- JSON-RPC client over the Python bridge's stdio (NDJSON) ----
type Pending = { resolve: (v: BridgeFrame) => void; reject: (e: Error) => void; timer: NodeJS.Timeout }
type BridgeFrame = { id?: number; result?: unknown; error?: { code: number; message: string }; method?: string }

const pending = new Map<number, Pending>()
let nextId = 1
let stdoutBuf = ''

function startBridge(): void {
  const root = app.getAppPath() // project root (aiadra-studio) — format-agnostic, no __dirname
  const python =
    process.env.AIADRA_PYTHON ||
    resolve(root, '..', 'aiadra-core', '.venv', 'Scripts', 'python.exe')
  const script = resolve(root, 'bridge', 'bridge.py')
  bridge = spawn(python, [script], { stdio: ['pipe', 'pipe', 'pipe'] })
  bridge.stdout.setEncoding('utf8')
  bridge.stdout.on('data', (chunk: string) => {
    stdoutBuf += chunk
    let nl: number
    while ((nl = stdoutBuf.indexOf('\n')) >= 0) {
      const line = stdoutBuf.slice(0, nl).trim()
      stdoutBuf = stdoutBuf.slice(nl + 1)
      if (!line) continue
      let frame: BridgeFrame
      try {
        frame = JSON.parse(line)
      } catch {
        continue // stdout is JSON-only; ignore anything malformed
      }
      if (frame.method === 'ready') continue // startup handshake
      if (typeof frame.id === 'number') {
        const p = pending.get(frame.id)
        if (p) {
          clearTimeout(p.timer)
          pending.delete(frame.id)
          p.resolve(frame)
        }
      }
    }
  })
  bridge.stderr.setEncoding('utf8')
  bridge.stderr.on('data', (d: string) => process.stderr.write(d))
  bridge.on('exit', (code) => {
    process.stderr.write(`[main] bridge exited (code ${code})\n`)
    bridge = null
  })
  process.stderr.write(`[main] spawned bridge: ${python} ${script}\n`)
}

function rpc(method: string, params: Record<string, unknown>): Promise<BridgeFrame> {
  return new Promise((resolveP, rejectP) => {
    if (!bridge) {
      rejectP(new Error('engine bridge is not running'))
      return
    }
    const id = nextId++
    const timer = setTimeout(() => {
      pending.delete(id)
      rejectP(new Error(`engine bridge timeout: ${method}`))
    }, 15000)
    pending.set(id, { resolve: resolveP, reject: rejectP, timer })
    bridge.stdin.write(`${JSON.stringify({ id, method, params })}\n`)
  })
}

// ---- Capability map (B2): opaque workspaceId -> canonical, validated path ----
const workspaces = new Map<string, string>()

function isAiadraWorkspace(dir: string): boolean {
  return existsSync(join(dir, '.aiadra'))
}

// ---- Typed IPC envelopes ----
type Ok<T> = { ok: true; result: T }
type Err = { ok: false; error: { message: string } }
const ok = <T,>(result: T): Ok<T> => ({ ok: true, result })
const err = (message: string): Err => ({ ok: false, error: { message } })

async function callBridge(method: string, params: Record<string, unknown>): Promise<Ok<unknown> | Err> {
  try {
    const frame = await rpc(method, params)
    return frame.error ? err(frame.error.message) : ok(frame.result)
  } catch (e) {
    return err(e instanceof Error ? e.message : String(e))
  }
}

function registerIpc(): void {
  ipcMain.handle('aiadra:ping', () => callBridge('ping', {}))
  ipcMain.handle('aiadra:coreVersion', () => callBridge('core_version', {}))

  ipcMain.handle('aiadra:chooseWorkspace', async () => {
    if (!win) return err('no window')
    const res = await dialog.showOpenDialog(win, {
      title: 'Open AIADRA Workspace',
      properties: ['openDirectory'],
    })
    if (res.canceled || res.filePaths.length === 0) return err('cancelled')
    let canonical: string
    try {
      canonical = realpathSync(res.filePaths[0])
    } catch {
      canonical = resolve(res.filePaths[0])
    }
    if (!isAiadraWorkspace(canonical)) {
      return err('not an AIADRA workspace (no .aiadra/ directory found)')
    }
    const workspaceId = randomUUID()
    workspaces.set(workspaceId, canonical)
    return ok({ workspaceId, name: canonical.split(/[\\/]/).pop() ?? canonical, path: canonical })
  })

  ipcMain.handle('aiadra:inspect', (_e, args: unknown) => {
    const a = args as { workspaceId?: unknown; objectRef?: unknown } | null
    if (!a || typeof a.workspaceId !== 'string' || typeof a.objectRef !== 'string') {
      return err('inspect requires { workspaceId, objectRef }')
    }
    const wsPath = workspaces.get(a.workspaceId)
    if (!wsPath) return err('unknown workspaceId — open a workspace first')
    return callBridge('inspect', { workspace_path: wsPath, object_ref: a.objectRef })
  })
}

function createWindow(): void {
  win = new BrowserWindow({
    width: 1320,
    height: 860,
    backgroundColor: '#16171d',
    title: 'AIADRA Studio',
    webPreferences: {
      preload: join(app.getAppPath(), 'out', 'preload', 'index.cjs'),
      contextIsolation: true, // B1
      nodeIntegration: false, // B1
      sandbox: true, // B1
      webSecurity: true, // B1
      allowRunningInsecureContent: false, // B1
    },
  })

  // B1: deny renderer-initiated navigation + new windows.
  win.webContents.on('will-navigate', (e) => e.preventDefault())
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))

  // B1: load ONLY the Vite dev server (dev) or the built local app (prod).
  if (process.env.ELECTRON_RENDERER_URL) {
    win.loadURL(process.env.ELECTRON_RENDERER_URL)
  } else {
    win.loadFile(join(app.getAppPath(), 'out', 'renderer', 'index.html'))
  }

  win.on('closed', () => {
    win = null
  })
}

app.whenReady().then(() => {
  startBridge()
  registerIpc()
  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  bridge?.kill()
  if (process.platform !== 'darwin') app.quit()
})
app.on('before-quit', () => bridge?.kill())
