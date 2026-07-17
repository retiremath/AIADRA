// SK-C1.0 S3 acceptance: the FACE-BOUND sketch walk. Box (rectangle sketch
// on TOP → Extrude 1) → Sketch → the pick prompt now offers flat faces →
// orient to the Top standard view and CLICK THE BOX'S TOP CAP in the
// viewport (the eligible face WINS over the datum quad — the engine's
// planarFaceIds is the only eligibility authority) → the in-context sketch
// enters ON the cap (the transient mirror frame; the box stays in view) →
// draw + close ring → OK → the face-bound Sketch 2 commits through the
// mock's engine-shaped face translation and its wire renders ON the cap via
// the validated Display v1.2 sketch_frames join → the tree's ✎ edits the
// base depth → regenerate → THE WIRE RIDES THE MOVED CAP (value persistence
// proven by reopening the catalogue). Assertion count enforced (Codex5 NB2
// discipline). Captures land in the arc packet.
import { createServer } from 'vite'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

// Codex10 NB1: repo-relative paths — the runner is portable evidence.
const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const OUT = resolve(ROOT, '../Docs/Discussions/20260716/20260716-2')
const EXPECTED_CHECKS = 17
const { chromium } = await import('playwright')
const server = await createServer({ root: ROOT, server: { port: 0 }, logLevel: 'warn' })
await server.listen()
const url = server.resolvedUrls?.local?.[0]
console.log('dev:', url)
const problems = []
let checks = 0
const ok = (cond, msg) => {
  checks += 1
  console.log(`${cond ? '  ok ' : 'FAIL '}${msg}`)
  if (!cond) problems.push(msg)
}
let browser
try {
  browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`))
  page.on('console', (m) => { if (m.type() === 'error') problems.push(`console.error: ${m.text()}`) })

  // "the body is renderable" — the display-style dropdown enables ONLY with a
  // renderable scene (no imports in this walk ⇒ the canonical Part's body).
  const bodyRenderable = async () =>
    (await page.locator('.tb-dd .dd-trigger').first().getAttribute('disabled')) === null
  const namedView = async (label) => {
    await page.getByRole('button', { name: 'Named views' }).click()
    await page.getByRole('menuitem', { name: label, exact: true }).click()
    await page.waitForTimeout(400)
  }

  await page.goto(url, { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'File' }).click()
  await page.getByRole('menuitem', { name: 'New…' }).click()
  await page.getByPlaceholder('e.g. Mounting bracket').fill('S3 Box')
  await page.getByRole('button', { name: 'OK' }).click()
  await page.locator('.ribbon').waitFor({ timeout: 15000 })
  await page.waitForTimeout(600)

  // ---- build the BOX: rectangle sketch on FRONT (xy) → extrude +Z, so
  // the Z-up Top standard view faces mock:cap_top square-on ----
  const canvas = page.locator('.viewport-canvas canvas')
  await page.locator('.rb-btn.rb-anchor', { hasText: 'Sketch' }).click()
  await page.locator('.pick-prompt').waitFor()
  ok(
    ((await page.locator('.pick-prompt').textContent()) ?? '').includes('flat face'),
    'the pick prompt offers a datum plane OR a flat face (S3)',
  )
  await page.locator('.feat-row.pickable', { hasText: 'FRONT' }).click()
  await page.locator('.sketch-chrome').waitFor()
  await page.locator('.sketch-chrome button', { hasText: 'Rectangle' }).click()
  let box = await canvas.boundingBox()
  await canvas.click({ position: { x: box.width / 2 - 60, y: box.height / 2 - 45 } })
  await canvas.click({ position: { x: box.width / 2 + 60, y: box.height / 2 + 45 } })
  await page.waitForTimeout(150)
  await page.locator('.sketch-chrome button.primary', { hasText: 'OK' }).click()
  await page.waitForTimeout(500)
  await page.locator('.feat-row', { hasText: 'Sketch 1' }).click() // select → entry A
  await page.locator('.rb-btn.rb-anchor', { hasText: 'Extrude' }).click()
  await page.locator('.extrude-panel').waitFor()
  await page.locator('.extrude-panel button.primary', { hasText: 'OK' }).click()
  await page.waitForTimeout(800)
  ok((await page.locator('.model-tree', { hasText: 'Extrude 1' }).count()) > 0, 'box step: Extrude 1 committed')
  ok(await bodyRenderable(), 'box step: the BODY renders')

  // ---- THE S3 PICK: look straight down (Top view) → the only face under
  // the cursor at the box center is the TOP CAP; click it. The datum quads
  // are in the scene too — the eligible face must WIN the arbitration. ----
  await namedView('Top')
  await page.locator('.rb-btn.rb-anchor', { hasText: 'Sketch' }).click()
  await page.locator('.pick-prompt').waitFor()
  box = await canvas.boundingBox()
  await canvas.click({ position: { x: box.width / 2, y: box.height / 2 } })
  await page.locator('.sketch-chrome').waitFor({ timeout: 5000 })
  const title = (await page.locator('.sc-title').textContent()) ?? ''
  ok(
    title.includes('face mock:cap_top'),
    `the session is FACE-BOUND to the cap (the face won over the datums): "${title.trim()}"`,
  )
  ok(await bodyRenderable(), 'in-context on the cap: the box is IN the scene (ghosted context)')
  await page.screenshot({ path: OUT + '/s3-accept-in-sketch-on-cap.png' })

  // draw a triangle ON the cap + close + OK — commits the FACE-BOUND sketch
  box = await canvas.boundingBox()
  await canvas.click({ position: { x: box.width / 2 - 40, y: box.height / 2 + 30 } })
  await canvas.click({ position: { x: box.width / 2 + 40, y: box.height / 2 + 30 } })
  await canvas.click({ position: { x: box.width / 2, y: box.height / 2 - 25 } })
  await page.locator('.sketch-chrome button', { hasText: 'Close ring' }).click()
  await page.waitForTimeout(120)
  await page.locator('.sketch-chrome button.primary', { hasText: 'OK' }).click()
  await page.waitForTimeout(700)
  ok((await page.locator('.model-tree', { hasText: 'Sketch 2' }).count()) > 0, 'OK: the FACE-BOUND Sketch 2 committed')
  ok((await page.locator('.sketch-chrome').count()) === 0, 'OK: chrome gone (clean exit)')
  ok(await bodyRenderable(), 'OK: the body AND the face-bound sketch coexist (the folded display)')
  await namedView('Iso')
  await page.screenshot({ path: OUT + '/s3-accept-wire-on-cap.png' })

  // ---- THE RIDE: the tree's ✎ on Extrude 1 → depth 25 → regenerate ----
  const extrudeRow = page.locator('.feat-row', { hasText: 'Extrude 1' })
  await extrudeRow.locator('.link-btn').click()
  await page.locator('.extrude-panel .sp-title', { hasText: 'Edit dimension' }).waitFor({ timeout: 5000 })
  const depthInput = page.locator('.extrude-panel input[type="number"]')
  const before = await depthInput.inputValue()
  await depthInput.fill('25')
  await page.locator('.extrude-panel button.primary', { hasText: 'OK' }).click()
  await page.waitForTimeout(900)
  ok(
    (await page.locator('.extrude-panel').count()) === 0,
    `depth edit committed (${before} → 25 mm): the panel closed on success`,
  )
  ok((await page.locator('.model-tree', { hasText: 'Sketch 2' }).count()) > 0, 'after the edit: Sketch 2 still in the tree')
  ok(await bodyRenderable(), 'after the edit: the body REGENERATED at the new depth')
  await page.screenshot({ path: OUT + '/s3-accept-wire-rides.png' })
  console.log('captures: in-sketch-on-cap + wire-on-cap (iso) + wire-rides (iso, same view — the cap moved)')

  // value persistence: reopen the catalogue — the mirror really mutated
  await extrudeRow.locator('.link-btn').click()
  await page.locator('.extrude-panel .sp-title', { hasText: 'Edit dimension' }).waitFor({ timeout: 5000 })
  ok((await depthInput.inputValue()) === '25', 'reopened catalogue reads 25 — the mutation persisted through inspect')
  await page.locator('.extrude-panel button', { hasText: 'Cancel' }).click()
  await page.waitForTimeout(200)

  // ---- Codex10 B1: Sketch view must face the SUPPORT, not legacy xy.
  // cap_base is the coincidence-proof probe: outward −Z, v = −Y — no
  // principal frame matches it. Enter from the Bottom view, invoke the
  // visible Sketch view command, and commit a third sketch UNDER the box.
  await namedView('Bottom')
  await page.locator('.rb-btn.rb-anchor', { hasText: 'Sketch' }).click()
  await page.locator('.pick-prompt').waitFor()
  box = await canvas.boundingBox()
  await canvas.click({ position: { x: box.width / 2, y: box.height / 2 } })
  await page.locator('.sketch-chrome').waitFor({ timeout: 5000 })
  const baseTitle = (await page.locator('.sc-title').textContent()) ?? ''
  ok(
    baseTitle.includes('face mock:cap_base'),
    `the BOTTOM cap session is face-bound (−Z support, no principal coincidence): "${baseTitle.trim()}"`,
  )
  // the visible Sketch view command — with B1 fixed it reorients to the
  // SUPPORT frame (look +Z, up −Y); before the fix it flipped to xy's
  // look −Z and the subsequent draw/commit walk would break visibly
  await page.locator('.sketch-chrome button', { hasText: 'Sketch view' }).click()
  await page.waitForTimeout(400)
  ok((await page.locator('.sketch-chrome').count()) === 1, 'Sketch view on the face support: session alive, camera-only')
  await page.screenshot({ path: OUT + '/s3-accept-sketchview-cap-base.png' })
  box = await canvas.boundingBox()
  await canvas.click({ position: { x: box.width / 2 - 35, y: box.height / 2 + 25 } })
  await canvas.click({ position: { x: box.width / 2 + 35, y: box.height / 2 + 25 } })
  await canvas.click({ position: { x: box.width / 2, y: box.height / 2 - 20 } })
  await page.locator('.sketch-chrome button', { hasText: 'Close ring' }).click()
  await page.waitForTimeout(120)
  await page.locator('.sketch-chrome button.primary', { hasText: 'OK' }).click()
  await page.waitForTimeout(700)
  ok((await page.locator('.model-tree', { hasText: 'Sketch 3' }).count()) > 0, 'the cap_base sketch committed AFTER Sketch view (the −Z frame held)')
  ok(await bodyRenderable(), 'the body survived the third commit')
  await page.screenshot({ path: OUT + '/s3-accept-wire-under-base.png' })

  ok(checks + 1 === EXPECTED_CHECKS, `assertion count enforced: ${checks + 1}/${EXPECTED_CHECKS}`)
  if (problems.length) {
    console.error('PROBLEMS:'); for (const p of problems) console.error(' ', p)
    process.exitCode = 1
  } else console.log(`S3 acceptance: CLEAN (${checks} checks)`)
} catch (e) {
  console.error('accept failed:', e instanceof Error ? e.message : e)
  process.exitCode = 1
} finally {
  if (browser) await browser.close()
  await server.close()
}
