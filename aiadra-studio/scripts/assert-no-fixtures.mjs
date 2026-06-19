// Production-exclusion proof for the dev fixture lane (arc 20260610-1 Codex1 N2).
//
// The fixture loader is reachable only behind `import.meta.env.DEV && !window.aiadra`;
// in a production build DEV is statically false, so the dynamic imports (and the
// fixture JSON chunks) must be dead-code-eliminated. This script PROVES that by
// scanning the built renderer output for markers that exist only in fixture data
// ("DevFixture" — the generated part's name) and only in the loader module
// ("hlr-front" — the fixture view file stem). Runs after every `npm run build`.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import process from 'node:process'

const ROOT = join(import.meta.dirname, '..', 'out', 'renderer')
const MARKERS = ['DevFixture', 'hlr-front']

function walk(dir, files = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) walk(p, files)
    else files.push(p)
  }
  return files
}

let files
try {
  files = walk(ROOT)
} catch {
  console.error(`[assert-no-fixtures] no built renderer at ${ROOT} — run the build first`)
  process.exit(1)
}

const hits = []
for (const f of files) {
  const text = readFileSync(f, 'latin1')
  for (const m of MARKERS) {
    if (text.includes(m)) hits.push(`${f}: contains "${m}"`)
  }
}

if (hits.length > 0) {
  console.error('[assert-no-fixtures] FAIL — dev fixture data leaked into the production bundle:')
  for (const h of hits) console.error('  ' + h)
  process.exit(1)
}
console.log(`[assert-no-fixtures] ok — ${files.length} built renderer files, no fixture markers`)
