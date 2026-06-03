// Built-Electron STEP smoke (Codex1 B2, arc 20260603-2).
//
// Builds the app, then launches the BUILT Electron app in production mode
// (`electron .` → no dev server → the `app://bundle` origin) with
// AIADRA_IMPORT_SMOKE=1. main's smoke driver runs a bundled sample STEP through
// the real controller/worker/occt path and writes a verdict line to stderr:
//   [smoke] STEP ok: ...    → STEP parsed + rendered in the built app:// app
//   [smoke] STEP FAIL: ...  → origin not app://, WASM not served, empty geometry,
//                             or a bridge call leaked.
// This launcher scans for that line and exits 0/1. ELECTRON_RUN_AS_NODE is deleted
// (the VSCode-terminal quirk that makes Electron run as plain Node).
import { spawn } from 'node:child_process'

function run(cmd, args, env, opts = {}) {
  return new Promise((resolveExit) => {
    const child = spawn(cmd, args, { shell: true, env, stdio: 'inherit', ...opts })
    child.on('exit', (code) => resolveExit(code ?? 1))
  })
}

const baseEnv = { ...process.env }
delete baseEnv.ELECTRON_RUN_AS_NODE

process.stderr.write('[step-smoke] building…\n')
const buildCode = await run('electron-vite', ['build'], baseEnv)
if (buildCode !== 0) {
  process.stderr.write('[step-smoke] FAIL: build failed\n')
  process.exit(1)
}

process.stderr.write('[step-smoke] launching built app (app://) with smoke…\n')
const child = spawn('electron', ['.'], { shell: true, env: { ...baseEnv, AIADRA_IMPORT_SMOKE: '1' } })

let buf = ''
let settled = false
const finish = (code, why) => {
  if (settled) return
  settled = true
  process.stderr.write(`[step-smoke] ${why} (exit ${code})\n`)
  try {
    child.kill()
  } catch {
    /* best effort */
  }
  process.exit(code)
}
const scan = (chunk) => {
  const s = chunk.toString()
  process.stderr.write(s) // pass main's output through for visibility
  buf += s
  if (buf.includes('[smoke] STEP ok:')) finish(0, 'PASS')
  else if (buf.includes('[smoke] STEP FAIL:')) finish(1, 'FAIL')
}
child.stdout.on('data', scan)
child.stderr.on('data', scan)
child.on('exit', (code) => finish(buf.includes('[smoke] STEP ok:') ? 0 : 1, `electron exited (${code})`))

setTimeout(() => finish(1, 'TIMEOUT (120s)'), 120_000)
