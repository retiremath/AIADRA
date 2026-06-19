// npm wrapper for the Python fixture generator (arc 20260610-1 P7).
// Resolves the engine venv the same way electron/main.ts does (AIADRA_PYTHON
// override, else the aiadra-core sibling venv) and runs gen-dev-fixtures.py.
import { spawnSync } from 'node:child_process'
import { join, resolve } from 'node:path'
import process from 'node:process'

const root = resolve(import.meta.dirname, '..')
const python =
  process.env.AIADRA_PYTHON || resolve(root, '..', 'aiadra-core', '.venv', 'Scripts', 'python.exe')
const r = spawnSync(python, [join(root, 'scripts', 'gen-dev-fixtures.py')], { stdio: 'inherit' })
process.exit(r.status ?? 1)
