// Run the bridge endpoint pytest regressions (Codex14 B1) with the
// aiadra-core venv — the bridge is Python, its tests live beside it, and
// this wrapper gives them a suite name (`npm run test:bridge`) so the
// evidence line can cite them like every other gate.
import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const candidates = [
  join(root, '..', 'aiadra-core', '.venv', 'Scripts', 'python.exe'), // Windows
  join(root, '..', 'aiadra-core', '.venv', 'bin', 'python'), // POSIX
]
const python = candidates.find((p) => existsSync(p))
if (!python) {
  console.error('[test:bridge] aiadra-core venv not found — create it first (see aiadra-core/README.md)')
  process.exit(1)
}
const r = spawnSync(python, ['-m', 'pytest', join(root, 'bridge'), '-q'], {
  stdio: 'inherit',
})
process.exit(r.status ?? 1)
