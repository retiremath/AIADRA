// I3 browser-lane check (dev:web mock lane; tracked here per Codex4 N2 —
// captures go to the git-ignored shots/a3): Sketch → pick TOP from the tree →
// the Creo-grammar placement dialog with the A3.3 default (RIGHT) → Flip and a
// reference/orientation change → the view-direction arrow → Sketch → the
// drawing session opens oriented to the dialog's frame; the Sketch ribbon has
// the shared layout (Codex3 B3) with Setup first; Sketch View returns the
// camera (Codex3 verified the matrices); a REAL context-generation change
// while the dialog is open unwinds it (Codex3 B1).
//
// B1's reproduction path is Codex3's own: File → New is GATED while the
// dialog is open ("Finish or cancel the active operation first" — one
// operation at a time), so no UI gesture can change the generation under an
// open dialog. A temporary Vite transform (in memory; no source file edited)
// exposes the App's REAL context store, the viewport's glyph, its pick flag
// and its saved datum exposure, and the check invokes the store's real
// `clear()` — the workspace-switch/reopen path — then reads the mounted App.
// (The mock lane has no engine preview, so drawing itself is the desktop walk.)
import { createServer } from 'vite'
import { mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import process from 'node:process'
import { chromium } from 'playwright'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..') // repo-relative
const OUT = resolve(ROOT, 'shots/a3')
mkdirSync(OUT, { recursive: true })

// the in-memory probe (Codex3's method): each anchor must match exactly once
const inject = (code, anchor, extra, file) => {
  const n = code.split(anchor).length - 1
  if (n !== 1) throw new Error(`probe anchor in ${file} matched ${n} times: ${anchor}`)
  return code.replace(anchor, `${anchor}\n${extra}`)
}
const probe = {
  name: 'aiadra-a3-probe',
  enforce: 'pre',
  transform(code, id) {
    const p = id.split('?')[0].replace(/\\/g, '/')
    if (p.endsWith('/src/App.tsx')) {
      return { code: inject(code, 'useContextInvalidation(partContext, authoringStore)', '  ;(globalThis as unknown as { __probe: unknown }).__probe = { partContext, authoringStore }', 'App.tsx'), map: null }
    }
    if (p.endsWith('/src/Viewport.tsx')) {
      let c = inject(code, 'scene.add(placementGlyph.group)', '    ;(globalThis as unknown as { __glyph: unknown }).__glyph = placementGlyph.group', 'Viewport.tsx')
      c = inject(c, 'let pickActive = false', "    Object.defineProperty(globalThis, '__pickActive', { get: () => pickActive, configurable: true })", 'Viewport.tsx')
      c = inject(c, 'let datumsPriorVisible: boolean | null = null', "    Object.defineProperty(globalThis, '__datumsPrior', { get: () => datumsPriorVisible, configurable: true })", 'Viewport.tsx')
      c = inject(c, 'const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.01, 5000)', '    ;(globalThis as unknown as { __camera: unknown }).__camera = camera', 'Viewport.tsx')
      return { code: c, map: null }
    }
    if (p.endsWith('/src/datums/datumOverlay.ts')) {
      return { code: inject(code, 'const group = new THREE.Group()', '  ;(globalThis as unknown as { __datumGroup: unknown }).__datumGroup = group', 'datumOverlay.ts'), map: null }
    }
    return null
  },
}

const server = await createServer({ root: ROOT, server: { port: 0 }, logLevel: 'warn', plugins: [probe] })
await server.listen()
const url = server.resolvedUrls.local[0]
const browser = await chromium.launch()
const notes = []
const note = (ok, msg) => notes.push(`${ok ? 'PASS' : 'FAIL'} ${msg}`)
const flat = (s) => s.split('\n').join(' | ')
let step = 'start'
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
  const newPart = async (name) => {
    step = `${name}: File`
    await page.getByRole('button', { name: 'File' }).click({ timeout: 8000 })
    const item = page.getByRole('menuitem', { name: 'New…' })
    step = `${name}: New… (aria-disabled=${await item.getAttribute('aria-disabled')}; title=${await item.getAttribute('title')})`
    await item.click({ timeout: 8000 })
    step = `${name}: name`
    await page.getByPlaceholder('e.g. Mounting bracket').fill(name, { timeout: 8000 })
    step = `${name}: OK`
    await page.getByRole('button', { name: 'OK' }).click({ timeout: 8000 })
    await page.locator('.viewport-canvas canvas').waitFor({ timeout: 15000 })
    await page.waitForTimeout(900)
  }
  // the mounted App's real state, through the probe
  const live = () => page.evaluate(() => {
    const g = globalThis
    const s = g.__probe?.authoringStore.getSnapshot()
    return {
      mode: s?.mode ?? null,
      collector: s?.activeCollector ?? null,
      captured: s?.capturedTarget?.generation ?? null,
      generation: g.__probe?.partContext.getSnapshot().generation ?? null,
      glyph: g.__glyph?.visible ?? null,
      picking: g.__pickActive ?? null,
      datumsPrior: g.__datumsPrior === undefined ? 'unset' : g.__datumsPrior,
      datumsShown: g.__datumGroup?.visible ?? null,
      cursor: document.querySelector('.viewport-canvas canvas')?.style.cursor ?? null,
    }
  })
  await page.goto(url, { waitUntil: 'networkidle' })
  await newPart('I3 Part')

  // the Creo seat is `Sketch`; the legacy lane keeps its label
  const sketchBtn = page.locator('.ribbon .rb-btn').filter({ has: page.locator('.rb-lbl', { hasText: /^Sketch$/ }) })
  note((await sketchBtn.count()) === 1, 'ribbon: exactly one `Sketch` seat')
  note((await page.locator('.ribbon .rb-lbl', { hasText: 'Sketch (legacy)' }).count()) === 1, 'ribbon: the legacy lane stays labeled')
  await sketchBtn.click()
  // N1: the pick banner speaks the dialog's datum-only vocabulary
  const banner = await page.locator('.pick-prompt').innerText()
  note(/Select the sketch plane/.test(banner) && /TOP, FRONT or RIGHT/.test(banner), `pick banner copy: ${banner.split('\n')[0].slice(0, 70)}`)
  const topRow = page.locator('.feat-row.intrinsic.pickable').filter({ hasText: 'TOP' })
  await topRow.waitFor({ timeout: 5000 })
  await topRow.click()

  const panel = page.getByTestId('placement-panel')
  await panel.waitFor({ timeout: 5000 })
  note((await page.getByTestId('collector-plane').textContent()) === 'TOP (xy)', 'dialog: Plane = TOP (xy)')
  note((await page.getByTestId('collector-reference').textContent()) === 'RIGHT (yz)', 'dialog: Reference defaults to RIGHT (yz) (A3.3)')
  note((await page.getByTestId('accept').textContent()) === 'Sketch', 'dialog: accept says Sketch')
  note(await page.getByTestId('use-previous').isDisabled(), 'dialog: Use Previous is disabled with its reason')
  await page.screenshot({ path: `${OUT}/1-dialog-default.png` })

  // the corrected scenario: reference FRONT, Orientation Top, Flip on
  await page.getByLabel('Orientation reference list').selectOption('zx')
  await page.getByLabel('Orientation', { exact: true }).selectOption('top')
  await page.getByTestId('flip').click()
  note((await page.getByTestId('flip').getAttribute('aria-pressed')) === 'true', 'dialog: Flip pressed')
  note((await page.getByTestId('collector-reference').textContent()) === 'FRONT (zx)', 'dialog: Reference = FRONT (zx)')
  await page.waitForTimeout(300)
  await page.screenshot({ path: `${OUT}/2-dialog-flipped.png` })

  // the Reference collector arms the pick; the tree row fills it through the same setter
  await page.getByTestId('collector-reference').click()
  note((await page.getByTestId('collector-reference').getAttribute('aria-pressed')) === 'true', 'dialog: collector armed')
  const rightRow = page.locator('.feat-row.intrinsic.pickable').filter({ hasText: 'RIGHT' })
  await rightRow.waitFor({ timeout: 3000 })
  await rightRow.click()
  note((await page.getByTestId('collector-reference').textContent()) === 'RIGHT (yz)', 'dialog: the tree pick filled the collector')
  await page.getByLabel('Orientation reference list').selectOption('zx') // back to the scenario

  // Sketch → the drawing session; the Sketch ribbon has the SHARED layout (B3)
  await page.getByTestId('accept').click()
  const ribbon = page.locator('.ribbon[aria-label="Sketch ribbon"]')
  await ribbon.waitFor({ timeout: 5000 })
  note((await panel.count()) === 0, 'entering the sketch closed the dialog')
  const afterAccept = await live()
  note(afterAccept.glyph === false && afterAccept.picking === false, `accept (a real transition): glyph hidden=${!afterAccept.glyph}, pick surface off=${!afterAccept.picking}`)
  const groups = await ribbon.locator('.ribbon-group').evaluateAll((els) =>
    els.map((e) => ({ title: e.querySelector('.ribbon-group-title')?.textContent ?? '', top: e.getBoundingClientRect().top, width: e.getBoundingClientRect().width })),
  )
  const display = await ribbon.evaluate((e) => getComputedStyle(e).display)
  const tops = groups.map((g) => Math.round(g.top))
  note(display === 'flex' && groups.length >= 3 && Math.max(...tops) - Math.min(...tops) <= 2, `ribbon layout: display=${display}, groups on ONE row (tops ${tops.join('/')})`)
  note(groups[0]?.title === 'Setup' && groups.every((g) => g.width < 700), `ribbon groups: ${groups.map((g) => `${g.title}:${Math.round(g.width)}px`).join(' · ')}`)
  const sketchView = ribbon.locator('.rb-btn').filter({ has: page.locator('.rb-lbl', { hasText: /^Sketch view$/ }) })
  note((await sketchView.count()) === 1 && !(await sketchView.isDisabled()), 'Sketch view button present and enabled in the drawing lane')
  await page.waitForTimeout(700)
  await page.screenshot({ path: `${OUT}/3-in-sketch.png` })
  // floor 4: orbit away with the middle button, then Sketch view returns the camera EXACTLY to entry
  const cam = () => page.evaluate(() => { const c = globalThis.__camera; return { q: c.quaternion.toArray(), p: c.position.toArray(), m: c.projectionMatrix.toArray() } })
  const maxDelta = (a, b) => Math.max(...a.map((x, i) => Math.abs(x - b[i])))
  step = 'orbit'
  const entry = await cam()
  const vb = await page.locator('.viewport-canvas canvas').boundingBox()
  const ox = vb.x + vb.width * 0.45, oy = vb.y + vb.height * 0.55
  await page.mouse.move(ox, oy)
  await page.mouse.down({ button: 'middle' })
  await page.mouse.move(ox + 140, oy + 70, { steps: 12 })
  await page.mouse.up({ button: 'middle' })
  await page.waitForTimeout(400)
  const orbited = await cam()
  const orbitDelta = maxDelta(entry.q, orbited.q)
  note(orbitDelta > 0.05, `orbit: the middle-button drag moved the camera (max quaternion delta ${orbitDelta.toFixed(4)})`)
  step = 'Sketch view'
  await sketchView.click()
  await page.waitForTimeout(400)
  const back = await cam()
  const dq = maxDelta(entry.q, back.q), dp = maxDelta(entry.p, back.p), dm = maxDelta(entry.m, back.m)
  note(dq <= 1e-9 && dp <= 1e-9 && dm <= 1e-9, `Sketch view returned the camera to entry (max deltas: quaternion ${dq}, position ${dp}, projection ${dm})`)
  await ribbon.locator('.rb-btn').filter({ has: page.locator('.rb-lbl', { hasText: /^Cancel$/ }) }).click()
  // the Model ribbon returns once the profile session has ended
  await page.locator('.ribbon .rb-lbl', { hasText: /^Extrude$/ }).first().waitFor({ timeout: 8000 })
  note(true, 'Cancel ended the drawing session; the Model ribbon is back')

  // ---- B1: a REAL context-generation change while the dialog is open ----
  // the user's datum display OFF first, so the pick's TEMPORARY exposure is observable
  step = 'datums off'
  await page.locator('.viewport-canvas canvas').hover()
  await page.keyboard.press('p') // the `scene.datums` toggle shortcut (focus-guarded App dispatcher)
  await page.waitForTimeout(200)
  note((await live()).datumsShown === false, 'setup: the datum overlay is hidden by the user before the pick')
  step = 'Sketch after Cancel'
  await sketchBtn.click({ timeout: 8000 })
  step = 'TOP row after Cancel'
  await topRow.waitFor({ timeout: 5000 })
  await topRow.click({ timeout: 8000 })
  step = 'dialog after Cancel'
  await panel.waitFor({ timeout: 5000 })
  step = 'arm collector'
  await page.getByTestId('collector-reference').click({ timeout: 8000 })
  await page.waitForTimeout(200)
  const before = await live()
  note(before.mode === 'placement' && before.collector === 'reference' && before.captured === before.generation,
    `before: dialog open, Reference armed, captured generation ${before.captured} == live ${before.generation}`)
  note(before.glyph === true && before.picking === true && before.datumsShown === true && before.datumsPrior === false,
    `before: glyph visible=${before.glyph}, pick surface on=${before.picking}, datums TEMPORARILY exposed=${before.datumsShown} (saved user choice ${before.datumsPrior})`)
  // the UI gate: File → New refuses while the dialog is open (one operation at a time)
  step = 'File menu under the dialog'
  await page.getByRole('button', { name: 'File' }).click({ timeout: 8000 })
  const newItem = page.getByRole('menuitem', { name: 'New…' })
  const newDisabled = (await newItem.getAttribute('aria-disabled')) === 'true'
  note(newDisabled, `File → New is gated while the dialog is open (${await newItem.getAttribute('title')})`)
  await page.keyboard.press('Escape')
  await page.waitForTimeout(150)
  // the REAL store's clear() — the workspace-switch/reopen path (Codex3's reproduction)
  step = 'partContext.clear()'
  await page.evaluate(() => globalThis.__probe.partContext.clear())
  await page.waitForTimeout(400)
  const after = await live()
  note(after.generation === before.generation + 1, `the real context generation advanced ${before.generation} → ${after.generation}`)
  note(after.mode === 'idle' && (await panel.count()) === 0, `B1: the dialog unwound through the App's wiring — owner ${after.mode}, panel gone`)
  note(after.collector === null && (await page.locator('.feat-row.intrinsic.pickable').count()) === 0, 'B1: the armed collector died with it — no tree row is a pick surface')
  note(after.glyph === false && after.picking === false && after.cursor === '', `B1: glyph hidden=${!after.glyph}, pick surface off=${!after.picking}, cursor reset`)
  note(after.datumsShown === false && after.datumsPrior === null, `B1: the temporary datum exposure unwound — overlay hidden again=${!after.datumsShown}, saved choice cleared`)
  await page.screenshot({ path: `${OUT}/4-after-real-clear.png` })
  // recovery: the gate lifts, a new Part opens, and the seat works on the NEW generation
  await newPart('Another Part')
  step = 'Sketch on the new part'
  await sketchBtn.click({ timeout: 8000 })
  await topRow.waitFor({ timeout: 5000 })
  await topRow.click({ timeout: 8000 })
  await panel.waitFor({ timeout: 5000 })
  const fresh = await live()
  note(fresh.mode === 'placement' && fresh.captured === fresh.generation && fresh.generation > after.generation,
    `recovery: File → New works again; a fresh dialog captures the new generation ${fresh.captured}`)
  note(errors.length === 0, `no page errors (${errors.length})${errors.length ? ': ' + errors.slice(0, 3).join(' | ') : ''}`)
} catch (e) {
  note(false, `script error at [${step}]: ${String(e).split('\n')[0]}`)
} finally {
  console.log(notes.join('\n'))
  await browser.close()
  await server.close()
}
process.exit(notes.some((n) => n.startsWith('FAIL')) ? 1 : 0)
