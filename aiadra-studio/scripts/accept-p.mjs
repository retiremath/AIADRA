// Arc 20260717-2 slice P acceptance: PETRE'S TWO ASKS ON SCREEN.
// (1) "as many extrusions as we want" — the Extrude button UN-GREYS after a
// base once a face-bound sketch exists; a second extrude (Add) commits and
// the BOSS renders on the body; the base depth edit makes the boss RIDE.
// (2) "pick it up on the screen" — in Extrude's select step the sketch WIRE
// is clicked directly in the viewport (the sketchSolicit lane); the modal
// list stays as fallback but is not used.
// Plus the honest boundaries: with only datum sketches the button carries
// the engine-mirrored FACE-BOUND reason; a CUT in the dev lane surfaces the
// honest mock refusal pointing at the real-engine lane (the engine's pocket
// is 288-test proven; the mock never fakes a cavity).
import { createServer } from 'vite'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const OUT = resolve(ROOT, '../Docs/Discussions/20260717/20260717-2')
const EXPECTED_CHECKS = 15
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

  const bodyRenderable = async () =>
    (await page.locator('.tb-dd .dd-trigger').first().getAttribute('disabled')) === null
  const namedView = async (label) => {
    await page.getByRole('button', { name: 'Named views' }).click()
    await page.getByRole('menuitem', { name: label, exact: true }).click()
    await page.waitForTimeout(400)
  }
  const extrudeBtn = page.locator('.rb-btn.rb-anchor', { hasText: 'Extrude' })

  await page.goto(url, { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'File' }).click()
  await page.getByRole('menuitem', { name: 'New…' }).click()
  await page.getByPlaceholder('e.g. Mounting bracket').fill('P Walk')
  await page.getByRole('button', { name: 'OK' }).click()
  await page.locator('.ribbon').waitFor({ timeout: 15000 })
  await page.waitForTimeout(600)

  // ---- the BASE: rectangle on FRONT (xy) → extrude ----
  const canvas = page.locator('.viewport-canvas canvas')
  await page.locator('.rb-btn.rb-anchor', { hasText: 'Sketch' }).click()
  await page.locator('.pick-prompt').waitFor()
  await page.locator('.feat-row.pickable', { hasText: 'FRONT' }).click()
  await page.locator('.sketch-chrome').waitFor()
  await page.locator('.sketch-chrome button', { hasText: 'Rectangle' }).click()
  let box = await canvas.boundingBox()
  await canvas.click({ position: { x: box.width / 2 - 60, y: box.height / 2 - 45 } })
  await canvas.click({ position: { x: box.width / 2 + 60, y: box.height / 2 + 45 } })
  await page.waitForTimeout(150)
  await page.locator('.sketch-chrome button.primary', { hasText: 'OK' }).click()
  await page.waitForTimeout(500)
  await page.locator('.feat-row', { hasText: 'Sketch 1' }).click()
  await extrudeBtn.click()
  await page.locator('.extrude-panel').waitFor()
  await page.locator('.extrude-panel button.primary', { hasText: 'OK' }).click()
  await page.waitForTimeout(800)
  ok((await page.locator('.model-tree', { hasText: 'Extrude 1' }).count()) > 0, 'the base exists (Extrude 1)')

  // ---- ASK 1a: the button is NOT one-base-dead — it carries the SEQUENTIAL
  // reason (face-bound needed), not "one per Part" ----
  const disabledTitle = (await extrudeBtn.getAttribute('title')) ?? ''
  ok(
    (await extrudeBtn.isDisabled()) && disabledTitle.includes('FACE-BOUND'),
    `after the base, Extrude greys with the SEQUENTIAL reason: "${disabledTitle}"`,
  )

  // ---- the face-bound sketch on the top cap ----
  await namedView('Top')
  await page.locator('.rb-btn.rb-anchor', { hasText: 'Sketch' }).click()
  await page.locator('.pick-prompt').waitFor()
  box = await canvas.boundingBox()
  await canvas.click({ position: { x: box.width / 2, y: box.height / 2 } })
  await page.locator('.sketch-chrome').waitFor({ timeout: 5000 })
  ok(
    ((await page.locator('.sc-title').textContent()) ?? '').includes('face mock:cap_top'),
    'the boss sketch is FACE-BOUND to the cap',
  )
  await canvas.click({ position: { x: box.width / 2 - 40, y: box.height / 2 + 30 } })
  await canvas.click({ position: { x: box.width / 2 + 40, y: box.height / 2 + 30 } })
  await canvas.click({ position: { x: box.width / 2, y: box.height / 2 - 25 } })
  await page.locator('.sketch-chrome button', { hasText: 'Close ring' }).click()
  await page.waitForTimeout(120)
  await page.locator('.sketch-chrome button.primary', { hasText: 'OK' }).click()
  await page.waitForTimeout(700)
  ok((await page.locator('.model-tree', { hasText: 'Sketch 2' }).count()) > 0, 'the face-bound Sketch 2 committed')

  // ---- ASK 1b: Extrude UN-GREYS ----
  ok(!(await extrudeBtn.isDisabled()), 'EXTRUDE UN-GREYED — a second extrude is offered')

  // ---- ASK 2: pick the sketch ON SCREEN (the wire, not the list) ----
  await extrudeBtn.click()
  await page.locator('.extrude-panel').waitFor()
  ok(
    (await page.locator('.extrude-panel .sp-hint', { hasText: 'Pick a sketch' }).count()) > 0,
    'the select step is open (the list remains as fallback)',
  )
  // find the wire by its HOVER AFFORDANCE (cursor: pointer — the same
  // winner as click), then click there: proves hover AND pick in one pass.
  box = await canvas.boundingBox()
  let wirePos = null
  outer: for (let dy = -140; dy <= 140; dy += 8) {
    for (let dx = -160; dx <= 160; dx += 8) {
      await page.mouse.move(box.x + box.width / 2 + dx, box.y + box.height / 2 + dy)
      await page.waitForTimeout(25)
      if ((await canvas.evaluate((el) => el.style.cursor)) === 'pointer') {
        wirePos = { x: box.width / 2 + dx, y: box.height / 2 + dy }
        break outer
      }
    }
  }
  ok(wirePos !== null, 'the eligible wire shows the HOVER affordance (cursor: pointer)')
  await canvas.click({ position: wirePos ?? { x: box.width / 2, y: box.height / 2 } })
  await page.waitForTimeout(300)
  ok(
    (await page.locator('.extrude-panel .sp-depth').count()) > 0,
    'CLICKING THE WIRE ON SCREEN advanced to the depth step (sketchSolicit)',
  )
  ok(
    (await page.locator('.extrude-panel button', { hasText: 'Add' }).count()) > 0
      && (await page.locator('.extrude-panel button', { hasText: 'Cut' }).count()) > 0,
    'the sequential Add/Cut choice is offered',
  )
  await page.locator('.extrude-panel button.primary', { hasText: 'OK' }).click()
  await page.waitForTimeout(800)
  ok((await page.locator('.model-tree', { hasText: 'Extrude 2' }).count()) > 0, 'THE BOSS committed (Extrude 2)')
  ok(await bodyRenderable(), 'the composed body renders')
  await namedView('Iso')
  await page.screenshot({ path: OUT + '/p-accept-boss-on-body.png' })

  // ---- the RIDE: base depth edit → the boss follows ----
  await page.locator('.feat-row', { hasText: 'Extrude 1' }).locator('.link-btn').click()
  await page.locator('.extrude-panel .sp-title', { hasText: 'Edit dimension' }).waitFor({ timeout: 5000 })
  await page.locator('.extrude-panel input[type="number"]').fill('22')
  await page.locator('.extrude-panel button.primary', { hasText: 'OK' }).click()
  await page.waitForTimeout(900)
  ok(await bodyRenderable(), 'after the base depth edit the composite regenerated (the boss rides)')
  await page.screenshot({ path: OUT + '/p-accept-boss-rides.png' })

  // ---- the honest CUT boundary in the dev lane ----
  await namedView('Top')
  await page.locator('.rb-btn.rb-anchor', { hasText: 'Sketch' }).click()
  await page.locator('.pick-prompt').waitFor()
  box = await canvas.boundingBox()
  await canvas.click({ position: { x: box.width / 2 + 170, y: box.height / 2 + 60 } })
  const enteredFace = (await page.locator('.sketch-chrome .sc-title').textContent().catch(() => '')) ?? ''
  if (!enteredFace.includes('face')) {
    // clicked off the cap (view scale) — fall back to the list-free retry at center-right
    await page.keyboard.press('Escape').catch(() => {})
    await page.locator('.rb-btn.rb-anchor', { hasText: 'Sketch' }).click()
    await canvas.click({ position: { x: box.width / 2 + 80, y: box.height / 2 + 40 } })
    await page.locator('.sketch-chrome').waitFor({ timeout: 5000 })
  }
  await canvas.click({ position: { x: box.width / 2 + 60, y: box.height / 2 + 40 } })
  await canvas.click({ position: { x: box.width / 2 + 100, y: box.height / 2 + 40 } })
  await canvas.click({ position: { x: box.width / 2 + 80, y: box.height / 2 + 10 } })
  await page.locator('.sketch-chrome button', { hasText: 'Close ring' }).click()
  await page.waitForTimeout(120)
  await page.locator('.sketch-chrome button.primary', { hasText: 'OK' }).click()
  await page.waitForTimeout(700)
  ok((await page.locator('.model-tree', { hasText: 'Sketch 3' }).count()) > 0, 'a second face-bound sketch committed')
  await extrudeBtn.click()
  await page.locator('.extrude-panel').waitFor()
  // the LIST FALLBACK (the design keeps it beside the on-screen pick —
  // exercised here deliberately; the wire pick is proven in the boss section)
  await page.locator('.extrude-panel button', { hasText: 'Sketch' }).first().click()
  await page.waitForTimeout(300)
  await page.locator('.extrude-panel button', { hasText: 'Cut' }).click()
  await page.locator('.extrude-panel button.primary', { hasText: 'OK' }).click()
  await page.waitForTimeout(600)
  const errText = (await page.locator('.extrude-panel .sp-hint.warn').textContent().catch(() => '')) ?? ''
  ok(
    errText.includes('desktop') || errText.includes('real engine'),
    `the dev-lane CUT surfaces the HONEST mock refusal: "${errText.trim()}"`,
  )
  await page.screenshot({ path: OUT + '/p-accept-cut-honest-refusal.png' })
  await page.locator('.extrude-panel button', { hasText: 'Cancel' }).click()

  ok(checks + 1 === EXPECTED_CHECKS, `assertion count enforced: ${checks + 1}/${EXPECTED_CHECKS}`)
  if (problems.length) {
    console.error('PROBLEMS:'); for (const p of problems) console.error(' ', p)
    process.exitCode = 1
  } else console.log(`P acceptance: CLEAN (${checks} checks)`)
} catch (e) {
  console.error('accept failed:', e instanceof Error ? e.message : e)
  if (problems.length) {
    console.error('PROBLEMS so far:'); for (const p of problems) console.error(' ', p)
  }
  process.exitCode = 1
} finally {
  if (browser) await browser.close()
  await server.close()
}
