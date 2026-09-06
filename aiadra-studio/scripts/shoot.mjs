// THE pinned V acceptance recipe (arc 20260716-1, Codex2 B4) — measured
// browser acceptance + durable captures for the empty-part UI.
//
// Boots the browser dev lane (plain Vite, no Electron/bridge), walks the REAL
// user path — Home → File → New… → OK → the empty Part under the datum
// scaffold — then, at the 1600×900 benchmark size AND the 1200 px supported
// minimum, with the AI dock open AND closed:
//
//   1. MEASURED COLLISION: the centered graphics toolbar, the nav-cube
//      cluster (fixed 180 px reserve, top-right), and the dock must not
//      overlap; the toolbar must sit fully inside the viewport.
//   2. RIBBON ADDRESSABILITY: every one of the 38 benchmark commands is
//      reachable — a direct button, a family-menu child, or a » overflow
//      item. Folding is allowed; loss is not.
//   3. CAPTURES: the pinned 1600×900 light-default empty-Part shot (dock
//      closed, default sidebar) + the three variants, saved durably (pass an
//      outDir — the arc packet — or default aiadra-studio/shots/).
//
// Any page/console error, failed assertion, or missing command fails the run.
//
//   npm run shoot              → PNGs to aiadra-studio/shots/ (git-ignored)
//   npm run shoot -- <outDir>  → e.g. the arc's captures/ folder
//
// First run only: npx playwright install chromium
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

// The 38-command benchmark inventory (mirrors the ribbon.test.ts fixture —
// that vitest fixture is the drift gate; this list is the runtime probe).
const COMMANDS = [
  'Regenerate', 'Get Data', 'Boolean Operations', 'Split/Trim Body', 'New Body',
  'Plane', 'Axis', 'Point', 'Coordinate System',
  // I3 (arc 20260905-1): the Creo seat IS `Sketch` (the v2 placement + drawing
  // lane); the v1 lane is labeled 'Sketch (legacy)' until I4.
  'Sketch',
  'Extrude', 'Revolve', 'Sweep', 'Swept Blend',
  'Hole', 'Round', 'Chamfer', 'Shell', 'Draft', 'Rib',
  'Pattern', 'Mirror', 'Trim', 'Offset', 'Extend', 'Project', 'Thicken',
  'Solidify', 'Merge', 'Intersect', 'Split', 'Remove', 'Unify',
  'Boundary Blend', 'Fill', 'Style', 'Freestyle', 'Component Interface',
]
const GROUPS = ['Operations', 'Get Data', 'Body', 'Datum', 'Shapes', 'Engineering', 'Pattern', 'Editing', 'Surfaces', 'Model Intent']

const server = await createServer({ root: ROOT, server: { port: 0 }, logLevel: 'warn' })
await server.listen()
const url = server.resolvedUrls?.local?.[0]
if (!url) {
  console.error('dev server did not report a local URL')
  await server.close()
  process.exit(1)
}
console.log('dev server:', url)

const problems = []
const note = (ok, msg) => {
  console.log(`${ok ? '  ok ' : 'FAIL '}${msg}`)
  if (!ok) problems.push(msg)
}

let browser
try {
  browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`))
  page.on('console', (m) => {
    if (m.type() === 'error') problems.push(`console.error: ${m.text()}`)
  })

  // ---- The real user path: Home → File → New… → OK → empty Part ----
  await page.goto(url, { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'File' }).click()
  await page.getByRole('menuitem', { name: 'New…' }).click()
  await page.getByPlaceholder('e.g. Mounting bracket').fill('Acceptance Part')
  await page.getByRole('button', { name: 'OK' }).click()
  await page.locator('.ribbon').waitFor({ timeout: 15000 })
  await page.locator('.toolbar').waitFor()
  await page.locator('.viewport-canvas canvas').waitFor()
  await page.waitForTimeout(900) // scaffold + settle

  const box = async (sel) => {
    const el = page.locator(sel)
    return (await el.count()) ? el.first().boundingBox() : null
  }
  const overlap = (a, b) =>
    !!a && !!b && a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height

  const NAV_RESERVE = 180 // the fixed top-right nav-cube reserve (GL + arrows)

  const assertLayout = async (label) => {
    const toolbar = await box('.toolbar')
    const viewport = await box('.viewport')
    const cluster = await box('.nav-cube-cluster')
    const dock = await box('.ai-dock')
    note(!!toolbar && !!viewport, `${label}: toolbar + viewport present`)
    if (!toolbar || !viewport) return
    const inside =
      toolbar.x >= viewport.x && toolbar.y >= viewport.y &&
      toolbar.x + toolbar.width <= viewport.x + viewport.width &&
      toolbar.y + toolbar.height <= viewport.y + viewport.height
    note(inside, `${label}: toolbar fully inside the viewport`)
    // the nav reserve: the GL cube renders in-canvas top-right even where the
    // HTML cluster is the only measurable box — assert against BOTH.
    const reserve = { x: viewport.x + viewport.width - NAV_RESERVE, y: viewport.y, width: NAV_RESERVE, height: NAV_RESERVE }
    note(!overlap(toolbar, reserve), `${label}: toolbar clear of the ${NAV_RESERVE}px nav-cube reserve`)
    if (cluster) note(!overlap(toolbar, cluster), `${label}: toolbar clear of the nav-cube cluster`)
    if (dock) {
      note(!overlap(toolbar, dock), `${label}: toolbar clear of the dock`)
      note(!overlap(reserve, dock), `${label}: nav-cube reserve clear of the dock`)
    }
  }

  const assertAddressability = async (label, { requireAllDirect = false } = {}) => {
    // collect every reachable command label: direct buttons…
    const direct = await page.locator('.ribbon .rb-btn .rb-lbl').allTextContents()
    const reachable = new Set(direct)
    // …family-menu children (open every family trigger)…
    for (const fam of await page.locator('.ribbon .rb-family .dd-trigger').all()) {
      await fam.click()
      for (const t of await page.locator('.dd-menu .dd-item').allTextContents()) reachable.add(t.replace(/^✓ /, ''))
      await page.keyboard.press('Escape')
    }
    // …and » overflow items ("Group: Label")
    const overflowTrigger = page.locator('.rb-overflow .dd-trigger')
    const folded = (await overflowTrigger.count()) > 0
    if (folded) {
      await overflowTrigger.click()
      for (const t of await page.locator('.dd-menu .dd-item').allTextContents()) {
        reachable.add(t.replace(/^✓ /, '').replace(/^[^:]+: /, ''))
      }
      await page.keyboard.press('Escape')
    }
    const missing = COMMANDS.filter((c) => !reachable.has(c))
    note(missing.length === 0, `${label}: all 38 commands reachable${folded ? ' (with » fold)' : ''}${missing.length ? ' — MISSING: ' + missing.join(', ') : ''}`)
    const titles = await page.locator('.ribbon-group-title').allTextContents()
    if (requireAllDirect) {
      // Codex3 N1: the 1600 benchmark is PINNED — folding there is a failure
      note(!folded && GROUPS.every((g) => titles.includes(g)), label + ': all ten groups DIRECT (pinned at the benchmark width)')
    } else {
      note(folded || GROUPS.every((g) => titles.includes(g)), label + ': ' + (folded ? 'folded suffix in »' : 'all ten groups direct'))
    }
  }

  const dockOpenNow = async () => (await page.locator('.ai-dock').count()) > 0
  const closeDock = async () => {
    if (await dockOpenNow()) await page.locator('.dock-x').click()
  }
  const openDock = async () => {
    if (!(await dockOpenNow())) await page.locator('.statusbar .ai-toggle').click()
  }

  // ---- 1600×900 (the benchmark) ----
  // captures FIRST (an addressability probe leaves a legitimate focus ring —
  // correct behavior, wrong moment to photograph), assertions after.
  const blur = () => page.evaluate(() => (document.activeElement instanceof HTMLElement) && document.activeElement.blur())
  await openDock()
  await blur()
  await page.screenshot({ path: join(OUT, 'empty-part-1600-dock.png') })
  await assertLayout('1600 dock-open')
  await assertAddressability('1600 dock-open', { requireAllDirect: true })
  await closeDock()
  await page.waitForTimeout(200)
  await blur()
  // THE pinned capture: 1600×900, light default, empty Part, dock closed
  await page.screenshot({ path: join(OUT, 'empty-part-1600.png') })
  console.log('shot empty-part-1600 (the pinned capture)')
  await assertLayout('1600 dock-closed')
  await assertAddressability('1600 dock-closed', { requireAllDirect: true })

  // ---- 1200×900 (the supported minimum) ----
  await page.setViewportSize({ width: 1200, height: 900 })
  await page.waitForTimeout(400)
  await blur()
  await page.screenshot({ path: join(OUT, 'empty-part-1200.png') })
  await assertLayout('1200 dock-closed')
  await assertAddressability('1200 dock-closed')
  await openDock()
  await page.waitForTimeout(400)
  await blur()
  await page.screenshot({ path: join(OUT, 'empty-part-1200-dock.png') })
  await assertLayout('1200 dock-open')
  await assertAddressability('1200 dock-open')

  if (problems.length) {
    console.error('PROBLEMS:')
    for (const p of problems) console.error('  ' + p)
    process.exitCode = 1
  } else {
    console.log(`clean run — measured acceptance passed; 4 captures in ${OUT}`)
  }
} catch (e) {
  console.error('shoot failed:', e instanceof Error ? e.message : e)
  process.exitCode = 1
} finally {
  if (browser) await browser.close()
  await server.close()
}
