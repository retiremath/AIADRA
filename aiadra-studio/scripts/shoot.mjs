// One-command visual capture for AIADRA Studio (committed harness).
//
// Boots the browser dev lane — the same path as `npm run dev:web`: plain Vite,
// NO Electron, NO Python bridge, NO workspace. In a dev build with no bridge the
// app auto-loads the engine-generated fixture part, so this renders the full
// UI (toolbar, theme, display modes, the box-with-hole). It screenshots a
// standard gallery, then tears the server down. It also doubles as a smoke:
// any page error or console error fails the run.
//
//   npm run shoot              → PNGs to aiadra-studio/shots/ (git-ignored)
//   npm run shoot -- <outDir>  → custom output directory
//
// First run only: download the browser binary once with
//   npx playwright install chromium
import { createServer } from 'vite'
import { mkdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import process from 'node:process'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const OUT = resolve(process.argv[2] || join(ROOT, 'shots'))
mkdirSync(OUT, { recursive: true })

let chromium
try {
  ;({ chromium } = await import('playwright'))
} catch {
  console.error('Playwright is not installed. Run `npm install`, then `npx playwright install chromium`.')
  process.exit(1)
}

// Random free port (server.port = 0) so this never collides with a dev server
// you may already have running on 5173.
const server = await createServer({ root: ROOT, server: { port: 0 }, logLevel: 'warn' })
await server.listen()
const url = server.resolvedUrls?.local?.[0]
if (!url) {
  console.error('dev server did not report a local URL')
  await server.close()
  process.exit(1)
}
console.log('dev server:', url)

const MODES = ['Wireframe', 'Hidden Line', 'No Hidden', 'Shading', 'Shading With Edges']
const slug = (s) => s.toLowerCase().replace(/\s+/g, '-')

const problems = []
let exitCode = 0
let browser
try {
  browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } })
  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`))
  page.on('console', (m) => {
    if (m.type() === 'error') problems.push(`console.error: ${m.text()}`)
  })

  await page.goto(url, { waitUntil: 'networkidle' })
  // The fixture badge proves the dev lane loaded and the part is in the scene.
  await page.getByText('dev fixture — not Product Truth').waitFor({ timeout: 15000 })
  await page.waitForTimeout(800) // initial snap + settle + overlay attach

  const canvas = page.locator('.viewport-canvas canvas')
  // Modes via the right-click menu (rendered from the same command taxonomy as
  // the toolbar — arc 20260619-2). Settle = 200 ms debounce + HLR fetch/attach.
  const setMode = async (label) => {
    await canvas.click({ button: 'right', position: { x: 700, y: 420 } })
    await page.locator('.ctx-menu li', { hasText: label }).first().click()
    await page.waitForTimeout(700)
  }
  const snap = async (id) => {
    await page.locator('.snap-views button', { hasText: id }).click()
    await page.waitForTimeout(700)
  }

  await snap('iso')
  for (const mode of MODES) {
    await setMode(mode)
    await page.screenshot({ path: join(OUT, `iso-${slug(mode)}.png`) })
    console.log('shot iso-' + slug(mode))
  }
  // Front view, Hidden Line — the hole shows only as dimmed interior hidden lines.
  await setMode('Hidden Line')
  await snap('front')
  await page.screenshot({ path: join(OUT, 'front-hidden-line.png') })
  console.log('shot front-hidden-line')
  // Tilt view, No Hidden — view-dependent classification, hidden removed.
  await setMode('No Hidden')
  await snap('tilt')
  await page.screenshot({ path: join(OUT, 'tilt-no-hidden.png') })
  console.log('shot tilt-no-hidden')

  if (problems.length) {
    console.error('PROBLEMS:')
    for (const p of problems) console.error('  ' + p)
    exitCode = 1
  } else {
    console.log(`clean run — no page errors. ${MODES.length + 2} shots in ${OUT}`)
  }
} catch (e) {
  console.error('shoot failed:', e instanceof Error ? e.message : e)
  exitCode = 1
} finally {
  if (browser) await browser.close()
  await server.close()
}
process.exit(exitCode)
