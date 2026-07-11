import { randomUUID } from 'node:crypto'
import { type ChildProcessWithoutNullStreams, spawn } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, realpathSync, renameSync, writeFileSync } from 'node:fs'
import { join, resolve, sep } from 'node:path'
import { app, BrowserWindow, dialog, ipcMain, protocol } from 'electron'
import { contentTypeFor, resolveAppAssetRelPath } from './appProtocol'
// Shared PURE envelope validators (arc 20260619-1 / 6a, Codex1 B1 + Codex2 R2):
// main owns BOTH the settings file path AND the persisted shape. The renderer is
// the untrusted side of the IPC boundary even when sandboxed. Load is tolerant
// (structural; older versions migrate); SAVE is strict (current version only).
import {
  validatePersistedSettingsBlob,
  validatePersistedSettingsForSave,
} from '../src/settings/persisted'

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

// ---- Read-only `app://bundle` asset scheme (Codex1 B1, arc 20260603-2) ----
// The BUILT renderer is served from a custom `app://bundle` origin (not file://)
// so the import worker can fetch occt's WASM — Chromium blocks `fetch(file://)`.
// Privileged standard+secure scheme; registered BEFORE app.ready. No bypassCSP.
protocol.registerSchemesAsPrivileged([
  { scheme: 'app', privileges: { standard: true, secure: true, supportFetchAPI: true } },
])

// B2: was occt's WASM actually served over app:// during a run? (smoke assertion)
let wasmServed = false
// B2: count of `aiadra:*` IPC calls — the smoke asserts an import adds zero.
let aiadraIpcCalls = 0
const SMOKE = !!process.env.AIADRA_IMPORT_SMOKE
let rendererRoot: string | null | undefined

function getRendererRoot(): string | null {
  if (rendererRoot === undefined) {
    try {
      rendererRoot = realpathSync(join(app.getAppPath(), 'out', 'renderer'))
    } catch {
      rendererRoot = null // not built (e.g. Vite dev) — the handler is never hit then
    }
  }
  return rendererRoot
}

/**
 * Serve ONLY the Studio's own built renderer assets, read-only, under app://bundle.
 * GET/HEAD only; URL→relative path via the pure confinement helper; then a
 * realpath/symlink-escape guard; explicit MIME (WASM as application/wasm). Never a
 * general file server — no workspace/user paths, no shell, no bridge, no IPC.
 */
function appAssetResponse(request: Request): Response {
  if (request.method !== 'GET' && request.method !== 'HEAD') return new Response(null, { status: 405 })
  const root = getRendererRoot()
  if (!root) return new Response(null, { status: 404 })
  const resolved = resolveAppAssetRelPath(request.url)
  if (!resolved.ok) return new Response(null, { status: resolved.status })

  const candidate = join(root, ...resolved.relPath.split('/'))
  let realPath: string
  try {
    realPath = realpathSync(candidate) // resolves symlinks; throws if missing
  } catch {
    return new Response(null, { status: 404 })
  }
  if (realPath !== root && !realPath.startsWith(root + sep)) {
    return new Response(null, { status: 403 }) // symlink escape outside the renderer root
  }

  let body: Buffer
  try {
    body = readFileSync(realPath)
  } catch {
    return new Response(null, { status: 404 })
  }
  if (resolved.relPath.toLowerCase().endsWith('.wasm')) {
    wasmServed = true
    process.stderr.write(`[app] served ${resolved.relPath} via app://\n`)
  }
  return new Response(request.method === 'HEAD' ? null : body, {
    status: 200,
    headers: { 'content-type': contentTypeFor(resolved.relPath) },
  })
}

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
    // N3 (Codex2): fail outstanding RPCs immediately instead of waiting out the
    // 15 s timeout, so the UI sees a clear disconnected state the moment the
    // bridge dies.
    for (const p of pending.values()) {
      clearTimeout(p.timer)
      p.reject(new Error('engine bridge exited'))
    }
    pending.clear()
    // ADR/0043 D4: the bridge held every authoring draft; when it dies they are
    // gone, so forget the capabilities. A subsequent verb fails loudly with
    // 'unknown operationSessionId' rather than pretending a dead draft is live.
    authoringSessions.clear()
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

// ---- Authoring session capabilities (arc 20260711-11; ADR/0043 D4) ----
// opaque operationSessionId -> its workspace path. Module-scope so the
// bridge-exit handler can fail/clear them (the drafts die with the bridge).
const authoringSessions = new Map<string, { wsPath: string }>()

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
  // B2: every bridge IPC bumps a counter so the smoke can prove the import path
  // makes zero bridge calls (delta over the import window).
  ipcMain.handle('aiadra:ping', () => {
    aiadraIpcCalls++
    return callBridge('ping', {})
  })
  ipcMain.handle('aiadra:coreVersion', () => {
    aiadraIpcCalls++
    return callBridge('core_version', {})
  })

  ipcMain.handle('aiadra:chooseWorkspace', async () => {
    aiadraIpcCalls++
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
    // N1 (Codex2): the canonical path stays main-side. The renderer contract
    // carries no filesystem paths (tightens B2) — only the opaque id + a display
    // name cross the wire.
    return ok({ workspaceId, name: canonical.split(/[\\/]/).pop() ?? canonical })
  })

  ipcMain.handle('aiadra:inspect', (_e, args: unknown) => {
    aiadraIpcCalls++
    const a = args as { workspaceId?: unknown; objectRef?: unknown } | null
    if (!a || typeof a.workspaceId !== 'string' || typeof a.objectRef !== 'string') {
      return err('inspect requires { workspaceId, objectRef }')
    }
    const wsPath = workspaces.get(a.workspaceId)
    if (!wsPath) return err('unknown workspaceId — open a workspace first')
    return callBridge('inspect', { workspace_path: wsPath, object_ref: a.objectRef })
  })

  // List Part Objects in an opened workspace (arc 20260610-1 Codex1 B1) —
  // the renderer's object-ref source for the canonical display lane until the
  // real model tree lands. Identity fields only (number/name/uuid); same
  // capability discipline: only the opaque workspaceId crosses the wire.
  ipcMain.handle('aiadra:listParts', (_e, args: unknown) => {
    aiadraIpcCalls++
    const a = args as { workspaceId?: unknown } | null
    if (!a || typeof a.workspaceId !== 'string') {
      return err('listParts requires { workspaceId }')
    }
    const wsPath = workspaces.get(a.workspaceId)
    if (!wsPath) return err('unknown workspaceId — open a workspace first')
    return callBridge('list_parts', { workspace_path: wsPath })
  })

  // Read-only Display Representation for a canonical Part (ADR/0035; arc
  // 20260609-1). Same capability discipline as inspect: only the opaque
  // workspaceId + object ref cross the wire; main resolves the path.
  ipcMain.handle('aiadra:displayRepresentation', (_e, args: unknown) => {
    aiadraIpcCalls++
    const a = args as { workspaceId?: unknown; objectRef?: unknown } | null
    if (!a || typeof a.workspaceId !== 'string' || typeof a.objectRef !== 'string') {
      return err('displayRepresentation requires { workspaceId, objectRef }')
    }
    const wsPath = workspaces.get(a.workspaceId)
    if (!wsPath) return err('unknown workspaceId — open a workspace first')
    return callBridge('display_representation', { workspace_path: wsPath, object_ref: a.objectRef })
  })

  // View-dependent HLR overlay (Display contract v1.1; arc 20260609-2).
  // Computed on camera settle, never per-frame. Same capability discipline:
  // only the opaque workspaceId + object ref + plain-data view specs cross
  // the wire; main resolves the path. Views are gated structurally here and
  // validated semantically by the engine (fail-loud).
  ipcMain.handle('aiadra:displayHlr', (_e, args: unknown) => {
    aiadraIpcCalls++
    const a = args as {
      workspaceId?: unknown
      objectRef?: unknown
      views?: unknown
      algorithm?: unknown
    } | null
    if (!a || typeof a.workspaceId !== 'string' || typeof a.objectRef !== 'string') {
      return err('displayHlr requires { workspaceId, objectRef, views }')
    }
    if (!Array.isArray(a.views) || a.views.length === 0) {
      return err('displayHlr requires a non-empty views array')
    }
    const algorithm = a.algorithm === undefined ? 'exact' : a.algorithm
    if (algorithm !== 'exact' && algorithm !== 'poly') {
      return err("displayHlr algorithm must be 'exact' or 'poly'")
    }
    const wsPath = workspaces.get(a.workspaceId)
    if (!wsPath) return err('unknown workspaceId — open a workspace first')
    return callBridge('display_hlr', {
      workspace_path: wsPath,
      object_ref: a.objectRef,
      views: a.views,
      algorithm,
    })
  })

  // ---- Authoring session — the Ring-2 WRITE lane (arc 20260711-11 slice 1;
  // ADR/0043). Main mints an opaque operationSessionId (a capability bound to a
  // workspace), allowlists the feature kind, and structurally validates params
  // BEFORE anything reaches the engine (Codex B1). The stateful Ring-2 draft
  // lives in bridge.py keyed by this id; NO paths / drafts / OCCT handles cross
  // to the renderer. commit returns the refreshed display; rollback/commit close
  // the session.
  const AUTHORING_KINDS = new Set<string>([
    'create_part',
    'mechanical.add_sketch_feature',
    'mechanical.add_extrude_feature',
    'mechanical.add_fillet_feature',
    'mechanical.add_chamfer_feature',
  ])
  const posNum = (v: unknown): boolean => typeof v === 'number' && Number.isFinite(v) && v > 0
  const validateAuthoringParams = (kind: string, params: unknown): string | null => {
    if (params === null || typeof params !== 'object') return 'op params must be an object'
    const p = params as Record<string, unknown>
    switch (kind) {
      case 'create_part':
        return typeof p.number === 'string' && typeof p.name === 'string'
          ? null
          : 'create_part requires string number + name'
      case 'mechanical.add_sketch_feature':
        return typeof p.part_number === 'string' && Array.isArray(p.primitives)
          ? null
          : 'add_sketch_feature requires part_number + primitives[]'
      case 'mechanical.add_extrude_feature':
        return typeof p.part_number === 'string' &&
          typeof p.sketch_feature_id === 'string' &&
          posNum(p.depth_mm)
          ? null
          : 'add_extrude_feature requires part_number + sketch_feature_id + depth_mm(>0)'
      // Codex2 non-blocking: tighten the value param before slice 2 uses targets.
      // The `target_*` field is added when the selection→target slice lands.
      case 'mechanical.add_fillet_feature':
        return typeof p.part_number === 'string' && posNum(p.radius_mm)
          ? null
          : 'add_fillet_feature requires part_number + radius_mm(>0)'
      case 'mechanical.add_chamfer_feature':
        return typeof p.part_number === 'string' && posNum(p.distance_mm)
          ? null
          : 'add_chamfer_feature requires part_number + distance_mm(>0)'
      default:
        return `feature kind not allowed: ${kind}`
    }
  }

  ipcMain.handle('aiadra:opBegin', async (_e, args: unknown) => {
    aiadraIpcCalls++
    const a = args as { workspaceId?: unknown; kind?: unknown; params?: unknown } | null
    if (!a || typeof a.workspaceId !== 'string' || typeof a.kind !== 'string') {
      return err('opBegin requires { workspaceId, kind, params }')
    }
    const wsPath = workspaces.get(a.workspaceId)
    if (!wsPath) return err('unknown workspaceId — open a workspace first')
    if (!AUTHORING_KINDS.has(a.kind)) return err(`feature kind not allowed: ${a.kind}`)
    const pErr = validateAuthoringParams(a.kind, a.params)
    if (pErr) return err(pErr)
    const operationSessionId = randomUUID()
    const r = await callBridge('authoring_begin', {
      session_id: operationSessionId,
      workspace_path: wsPath,
      kind: a.kind,
      op_params: a.params,
    })
    if (!r.ok) return r
    authoringSessions.set(operationSessionId, { wsPath })
    return ok({ operationSessionId })
  })

  ipcMain.handle('aiadra:opAdd', (_e, args: unknown) => {
    aiadraIpcCalls++
    const a = args as { operationSessionId?: unknown; kind?: unknown; params?: unknown } | null
    if (!a || typeof a.operationSessionId !== 'string' || typeof a.kind !== 'string') {
      return err('opAdd requires { operationSessionId, kind, params }')
    }
    if (!authoringSessions.has(a.operationSessionId)) return err('unknown operationSessionId')
    if (!AUTHORING_KINDS.has(a.kind)) return err(`feature kind not allowed: ${a.kind}`)
    const pErr = validateAuthoringParams(a.kind, a.params)
    if (pErr) return err(pErr)
    return callBridge('authoring_add', {
      session_id: a.operationSessionId,
      kind: a.kind,
      op_params: a.params,
    })
  })

  ipcMain.handle('aiadra:opSimulate', (_e, args: unknown) => {
    aiadraIpcCalls++
    const a = args as { operationSessionId?: unknown } | null
    if (!a || typeof a.operationSessionId !== 'string') return err('opSimulate requires { operationSessionId }')
    if (!authoringSessions.has(a.operationSessionId)) return err('unknown operationSessionId')
    return callBridge('authoring_simulate', { session_id: a.operationSessionId })
  })

  ipcMain.handle('aiadra:opCommit', async (_e, args: unknown) => {
    aiadraIpcCalls++
    const a = args as { operationSessionId?: unknown; objectRef?: unknown } | null
    if (!a || typeof a.operationSessionId !== 'string') return err('opCommit requires { operationSessionId, objectRef }')
    const s = authoringSessions.get(a.operationSessionId)
    if (!s) return err('unknown operationSessionId')
    const r = await callBridge('authoring_commit', {
      session_id: a.operationSessionId,
      workspace_path: s.wsPath,
      object_ref: typeof a.objectRef === 'string' ? a.objectRef : undefined,
    })
    // Codex2 B1: close the capability ONLY on a successful commit. On failure
    // the bridge keeps the draft open (recoverable), so main keeps its session
    // too — the two sides stay consistent and the user can fix/retry/cancel.
    if (r.ok) authoringSessions.delete(a.operationSessionId)
    return r
  })

  ipcMain.handle('aiadra:opRollback', async (_e, args: unknown) => {
    aiadraIpcCalls++
    const a = args as { operationSessionId?: unknown } | null
    if (!a || typeof a.operationSessionId !== 'string') return err('opRollback requires { operationSessionId }')
    if (!authoringSessions.has(a.operationSessionId)) return err('unknown operationSessionId')
    // Codex2 B1: confirm the bridge discarded the draft BEFORE main forgets the
    // session. On bridge failure, keep the main capability so the session isn't
    // orphaned (the bridge-exit handler clears it if the bridge is truly gone).
    const r = await callBridge('authoring_rollback', { session_id: a.operationSessionId })
    if (r.ok) authoringSessions.delete(a.operationSessionId)
    return r
  })

  // ---- App settings (arc 20260619-1 / 6a; ADR/0033 D8) ----
  // Local user preferences only — NOT Product Truth, NOT routed through the
  // Python engine bridge. One fixed file under the OS userData dir; main owns
  // the path. Saves are validated by the shared envelope validator and written
  // atomically (temp + rename); an invalid blob is rejected without touching
  // the existing file (Codex1 B1). The renderer never supplies a path.
  const settingsFile = () => join(app.getPath('userData'), 'settings.json')

  ipcMain.handle('aiadra:loadSettings', () => {
    aiadraIpcCalls++
    try {
      const file = settingsFile()
      if (!existsSync(file)) return ok({ settings: null })
      const blob: unknown = JSON.parse(readFileSync(file, 'utf8'))
      const check = validatePersistedSettingsBlob(blob)
      if (!check.ok) {
        console.error('[settings] ignoring invalid settings.json:', check.error)
        return ok({ settings: null }) // app prefs: fall back to defaults, never brick startup
      }
      return ok({ settings: blob })
    } catch (e) {
      console.error('[settings] load failed:', e instanceof Error ? e.message : e)
      return ok({ settings: null })
    }
  })

  ipcMain.handle('aiadra:saveSettings', (_e, args: unknown) => {
    aiadraIpcCalls++
    const blob = (args as { settings?: unknown } | null)?.settings
    // Strict save validation (Codex2 R2): reject any non-current version BEFORE
    // writing, so a forward/corrupt blob can never be persisted.
    const check = validatePersistedSettingsForSave(blob)
    if (!check.ok) return err(`invalid settings: ${check.error}`)
    try {
      const dir = app.getPath('userData')
      mkdirSync(dir, { recursive: true })
      const file = join(dir, 'settings.json')
      const tmp = join(dir, `settings.json.tmp-${process.pid}`)
      writeFileSync(tmp, JSON.stringify(blob))
      renameSync(tmp, file) // atomic replace
      return ok({})
    } catch (e) {
      return err(e instanceof Error ? e.message : String(e))
    }
  })
}

// B1 (Codex2 N2): in dev we load ELECTRON_RENDERER_URL (set by electron-vite, not
// renderer-controlled). Assert it points at a loopback origin so a poisoned
// environment cannot aim Studio at a remote page. The port is intentionally NOT
// pinned (Vite may fall back off 5173); the security-relevant invariant is the host.
function isLoopbackDevUrl(raw: string): boolean {
  try {
    const u = new URL(raw)
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return false
    const host = u.hostname
    return host === 'localhost' || host === '127.0.0.1' || host === '::1' || host === '[::1]'
  } catch {
    return false
  }
}

function createWindow(): void {
  win = new BrowserWindow({
    width: 1320,
    height: 860,
    backgroundColor: '#16171d',
    title: 'AIADRA Studio',
    show: !SMOKE, // headless window for the built-Electron smoke
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

  // B1: load ONLY the Vite dev server (dev) or the built local app over the
  // read-only app://bundle origin (prod). Never file:// (occt WASM fetch needs a
  // fetchable origin); never a renderer-controlled URL.
  const devUrl = process.env.ELECTRON_RENDERER_URL
  if (devUrl && isLoopbackDevUrl(devUrl)) {
    win.loadURL(devUrl)
  } else {
    if (devUrl) {
      process.stderr.write(`[main] refusing non-loopback ELECTRON_RENDERER_URL: ${devUrl}\n`)
    }
    win.loadURL(`app://bundle/index.html${SMOKE ? '?smoke=1' : ''}`)
  }

  if (SMOKE) runStepSmoke(win)

  win.on('closed', () => {
    win = null
  })
}

// B2 (Codex1): the built-Electron STEP smoke. Drives the renderer's smoke hook,
// which runs a bundled sample STEP through the REAL controller/worker/occt path
// (occt fetches its WASM over app://). Asserts the actual missing path, not just
// that bytes can be parsed: app:// origin + handler served the WASM + non-zero
// geometry + zero window.aiadra bridge calls. Exits 0 on pass, 1 on fail.
function runStepSmoke(w: BrowserWindow): void {
  w.webContents.once('did-finish-load', async () => {
    const fail = (msg: string) => {
      process.stderr.write(`[smoke] STEP FAIL: ${msg}\n`)
      bridge?.kill()
      app.exit(1)
    }
    try {
      const url = w.webContents.getURL()
      if (!url.startsWith('app://bundle')) return fail(`renderer origin is ${url}, expected app://bundle`)
      // Let the EnginePanel's on-mount coreVersion() call settle, then snapshot the
      // bridge-IPC counter so the delta reflects ONLY the import (must be zero).
      await new Promise((r) => setTimeout(r, 600))
      wasmServed = false
      const bridgeBefore = aiadraIpcCalls
      // Poll for the hook (registered under ?smoke=1), then run it. No raw fixture
      // interpolation — the hook fetches the sample over app:// itself.
      const result = (await w.webContents.executeJavaScript(
        '(async () => { for (let i = 0; i < 100 && !window.__aiadraStepSmoke; i++) { await new Promise((r) => setTimeout(r, 50)) } return window.__aiadraStepSmoke ? window.__aiadraStepSmoke() : null })()',
      )) as { origin?: string; triangles?: number; meshCount?: number } | null
      const bridgeDelta = aiadraIpcCalls - bridgeBefore
      if (!result) return fail('renderer smoke hook (window.__aiadraStepSmoke) never registered')
      if (result.origin !== 'app://bundle') return fail(`location.origin=${result.origin}`)
      if (!wasmServed) return fail('app:// handler did not serve occt WASM during import')
      if (!(result.meshCount! > 0) || !(result.triangles! > 0)) {
        return fail(`empty geometry (meshes=${result.meshCount}, triangles=${result.triangles})`)
      }
      if (bridgeDelta !== 0) return fail(`import made ${bridgeDelta} aiadra:* IPC calls (expected 0)`)
      process.stderr.write(
        `[smoke] STEP ok: ${result.meshCount} meshes, ${result.triangles} triangles, origin ${result.origin}, WASM served via app://, ${bridgeDelta} bridge calls during import\n`,
      )
      bridge?.kill()
      app.exit(0)
    } catch (e) {
      fail(e instanceof Error ? e.message : String(e))
    }
  })
}

app.whenReady().then(() => {
  protocol.handle('app', appAssetResponse) // B1: serve app://bundle from the default session
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
