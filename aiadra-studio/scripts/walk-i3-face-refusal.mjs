// I3 Codex3 B2 regression (dev:web mock lane; tracked here per Codex4 N2 —
// captures go to the git-ignored shots/a4): a REAL face click reaches the
// placement refusal. Build a body first (legacy Sketch → rectangle → OK →
// Extrude → OK), then: Sketch → the initial pick → click the top cap → the
// pick banner shows the refusal (no dialog opened, no datum behind it won);
// open the dialog from TOP, arm Plane, click the cap → the dialog shows the
// refusal, keeps TOP, and the collector stays armed. Hover shows not-allowed.
import { createServer } from 'vite'
import { mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import process from 'node:process'
import { chromium } from 'playwright'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..') // repo-relative
const OUT = resolve(ROOT, 'shots/a4')
mkdirSync(OUT, { recursive: true })
const server = await createServer({ root: ROOT, server: { port: 0 }, logLevel: 'warn' })
await server.listen()
const url = server.resolvedUrls.local[0]
const browser = await chromium.launch()
const notes = []
const note = (ok, msg) => notes.push(`${ok ? 'PASS' : 'FAIL'} ${msg}`)
const REFUSAL = /Only the three datum planes can place a sketch here/
const flat = (s) => s.replace(/\r?\n/g, ' | ')
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
  await page.goto(url, { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'File' }).click()
  await page.getByRole('menuitem', { name: 'New…' }).click()
  await page.getByPlaceholder('e.g. Mounting bracket').fill('Face Part')
  await page.getByRole('button', { name: 'OK' }).click()
  const canvas = page.locator('.viewport-canvas canvas')
  await canvas.waitFor({ timeout: 15000 })
  await page.waitForTimeout(900)
  const modelBtn = (re) => page.locator('.ribbon .rb-btn').filter({ has: page.locator('.rb-lbl', { hasText: re }) })
  const sketchRibbon = page.locator('.ribbon[aria-label="Sketch ribbon"]')
  const click = async (x, y) => { await page.mouse.move(x, y); await page.mouse.down(); await page.mouse.up(); await page.waitForTimeout(250) }

  // ---- a body from the legacy lane: rectangle on TOP, extruded ----
  await modelBtn(/^Sketch \(legacy\)$/).click()
  const topRow = page.locator('.feat-row.intrinsic.pickable').filter({ hasText: 'TOP' })
  await topRow.waitFor({ timeout: 5000 })
  await topRow.click()
  await sketchRibbon.waitFor({ timeout: 5000 })
  await page.waitForTimeout(800)
  await sketchRibbon.locator('.rb-btn').filter({ has: page.locator('.rb-lbl', { hasText: /^Rectangle$/ }) }).click()
  await page.waitForTimeout(300)
  const box = await canvas.boundingBox()
  const cx = box.x + box.width / 2
  const cy = box.y + box.height / 2
  await click(cx - 80, cy - 60)
  await click(cx + 80, cy + 60)
  await sketchRibbon.locator('.rb-btn').filter({ has: page.locator('.rb-lbl', { hasText: /^OK$/ }) }).click()
  await page.waitForTimeout(1500)
  const sketchRow = page.locator('.feat-row.truth').filter({ hasText: /Sketch 1/ })
  note((await sketchRow.count()) === 1, 'legacy: Sketch 1 committed')
  await sketchRow.click()
  await page.waitForTimeout(300)
  await modelBtn(/^Extrude$/).click()
  const extrudeOk = page.locator('.extrude-panel').getByRole('button', { name: /^OK$/ })
  await extrudeOk.waitFor({ timeout: 5000 })
  await extrudeOk.click()
  await page.waitForTimeout(1500)
  note((await page.locator('.feat-row.truth').filter({ hasText: /Extrude 1/ }).count()) === 1, 'legacy: Extrude 1 committed (a body with a top cap exists)')
  await page.screenshot({ path: `${OUT}/1-body.png` })

  // ---- the initial pick: click the cap (the nearest face, above the TOP datum) ----
  await modelBtn(/^Sketch$/).click()
  await page.locator('.pick-prompt').waitFor({ timeout: 5000 })
  // the box's top cap projects near the viewport centre in the trimetric home
  // view; probe a few points until a face answers (refusal) — a datum answer
  // (dialog) or nothing is reported honestly.
  const candidates = [[cx, cy - 30], [cx, cy], [cx + 40, cy - 20], [cx - 40, cy - 40], [cx, cy - 70]]
  let hit = null
  for (const [x, y] of candidates) {
    await page.mouse.move(x, y)
    await page.waitForTimeout(150)
    const cursor = await canvas.evaluate((c) => c.style.cursor)
    await click(x, y)
    const dialog = (await page.getByTestId('placement-panel').count()) > 0
    const banner = dialog ? '' : flat(await page.locator('.pick-prompt').innerText().catch(() => ''))
    if (dialog) { hit = { x, y, cursor, outcome: 'datum (dialog opened)' }; break }
    if (REFUSAL.test(banner)) { hit = { x, y, cursor, outcome: 'refused', banner }; break }
  }
  note(hit?.outcome === 'refused', `initial pick: a real face click is REFUSED with copy (${hit ? `${hit.outcome}; cursor '${hit.cursor}' at ${Math.round(hit.x - cx)},${Math.round(hit.y - cy)}` : 'no face answered at any probe'})`)
  note(hit?.cursor === 'not-allowed', `hover over the unsupported face shows not-allowed (was '${hit?.cursor}')`)
  await page.screenshot({ path: `${OUT}/2-initial-pick-refusal.png` })

  // ---- the dialog: TOP from the tree, arm Plane, click the cap ----
  if (hit?.outcome === 'refused') {
    await topRow.click()
    const panel = page.getByTestId('placement-panel')
    await panel.waitFor({ timeout: 5000 })
    await page.getByTestId('collector-plane').click()
    // the dialog docks top-right and may cover the first probe point: probe
    // points that land on the CANVAS (elementFromPoint) until the cap answers
    let msg = ''
    let used = null
    for (const [x, y] of [[hit.x, hit.y], [cx - 40, cy - 30], [cx - 80, cy - 10], [cx - 60, cy + 10], [cx - 120, cy - 30], [cx, cy + 40]]) {
      const onCanvas = await page.evaluate(([px, py]) => document.elementFromPoint(px, py)?.tagName === 'CANVAS', [x, y])
      if (!onCanvas) continue
      await click(x, y)
      msg = (await panel.locator('.sp-hint.warn').allTextContents()).join(' ')
      used = [x, y]
      if (REFUSAL.test(msg)) break
      if ((await page.getByTestId('collector-plane').getAttribute('aria-pressed')) !== 'true') break // a datum answered: the collector disarmed
    }
    note(used !== null, `dialog: a canvas probe point was found (${used ? `${Math.round(used[0] - cx)},${Math.round(used[1] - cy)}` : 'none'})`)
    note(REFUSAL.test(msg) && (await page.getByTestId('collector-plane').textContent()) === 'TOP (xy)', `dialog: the cap click was REFUSED and Plane stayed TOP (${msg.slice(0, 60)}…)`)
    note((await page.getByTestId('collector-plane').getAttribute('aria-pressed')) === 'true', 'dialog: the collector stays armed after a refused face')
    await page.screenshot({ path: `${OUT}/3-dialog-refusal.png` })
    // the third route (Codex4 N2): the same face into the armed REFERENCE collector
    await page.getByTestId('collector-plane').click() // disarm Plane
    await page.getByTestId('collector-reference').click() // arm Reference
    const refBefore = await page.getByTestId('collector-reference').textContent()
    if (used) await click(used[0], used[1])
    const refMsg = (await panel.locator('.sp-hint.warn').allTextContents()).join(' ')
    note(REFUSAL.test(refMsg) && (await page.getByTestId('collector-plane').textContent()) === 'TOP (xy)' && (await page.getByTestId('collector-reference').textContent()) === refBefore,
      `dialog: the cap click into Reference was REFUSED; both members unchanged (Plane TOP, Reference ${refBefore})`)
    note((await page.getByTestId('collector-reference').getAttribute('aria-pressed')) === 'true', 'dialog: Reference stays armed after a refused face')
  }
  note(errors.length === 0, `no page errors (${errors.length})${errors.length ? ': ' + errors.slice(0, 3).join(' | ') : ''}`)
} catch (e) {
  note(false, `script error: ${String(e).split('\n')[0]}`)
} finally {
  console.log(notes.join('\n'))
  await browser.close()
  await server.close()
}
process.exit(notes.some((n) => n.startsWith('FAIL')) ? 1 : 0)
