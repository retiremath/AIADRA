// SK-C1.0 S1 acceptance (Codex4 B1 + Codex5 B1): the NONEMPTY-Part
// principal-datum walk with MECHANICAL postconditions. Box (rectangle sketch
// → extrude) → Sketch on FRONT → in-context with the box visible/ghosted →
// live line → oblique orbit (no placement) → hover a body EDGE and RECORD
// the canonical id (edges-only filter) → Sketch view → CANCEL restores AND
// THE BODY SURVIVES → re-enter (body still present) → draw + close → OK →
// Sketch 2 AND the body together. The assertion count is enforced — the
// headline cannot drift (Codex5 NB2).
import { createServer } from 'vite'
import process from 'node:process'

const ROOT = 'd:/VSCode-Work/AIADRA/aiadra-studio'
const OUT = 'd:/VSCode-Work/AIADRA/Docs/Discussions/20260716/20260716-2'
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

  await page.goto(url, { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'File' }).click()
  await page.getByRole('menuitem', { name: 'New…' }).click()
  await page.getByPlaceholder('e.g. Mounting bracket').fill('B1 Box')
  await page.getByRole('button', { name: 'OK' }).click()
  await page.locator('.ribbon').waitFor({ timeout: 15000 })
  await page.waitForTimeout(600)

  // ---- build the BOX: rectangle sketch on TOP (zx) → extrude ----
  const canvas = page.locator('.viewport-canvas canvas')
  await page.locator('.rb-btn.rb-anchor', { hasText: 'Sketch' }).click()
  await page.locator('.pick-prompt').waitFor()
  await page.locator('.feat-row.pickable', { hasText: 'TOP' }).click()
  await page.locator('.sketch-chrome').waitFor()
  await page.locator('.sketch-chrome button', { hasText: 'Rectangle' }).click()
  let box = await canvas.boundingBox()
  await canvas.click({ position: { x: box.width / 2 - 60, y: box.height / 2 - 45 } })
  await canvas.click({ position: { x: box.width / 2 + 60, y: box.height / 2 + 45 } })
  await page.waitForTimeout(150)
  await page.locator('.sketch-chrome button.primary', { hasText: 'OK' }).click()
  await page.waitForTimeout(500)
  ok((await page.locator('.model-tree', { hasText: 'Sketch 1' }).count()) > 0, 'box step: Sketch 1 committed')
  await page.locator('.feat-row', { hasText: 'Sketch 1' }).click() // select → entry A
  await page.locator('.rb-btn.rb-anchor', { hasText: 'Extrude' }).click()
  await page.locator('.extrude-panel').waitFor()
  await page.locator('.extrude-panel button.primary', { hasText: 'OK' }).click()
  await page.waitForTimeout(700)
  ok((await page.locator('.model-tree', { hasText: 'Extrude 1' }).count()) > 0, 'box step: Extrude 1 committed (the NONEMPTY Part)')
  await page.waitForTimeout(600)
  ok(await bodyRenderable(), 'box step: the BODY renders (display controls enabled)')

  // ---- THE ACCEPTANCE: Sketch on FRONT with the box present ----
  await page.locator('.rb-btn.rb-anchor', { hasText: 'Sketch' }).click()
  await page.locator('.pick-prompt').waitFor()
  await page.locator('.feat-row.pickable', { hasText: 'FRONT' }).click()
  await page.locator('.sketch-chrome').waitFor()
  ok(await bodyRenderable(), 'acceptance: in-context on FRONT — the box is IN the scene')

  // live geometry: two points = a world-space line
  box = await canvas.boundingBox()
  await canvas.click({ position: { x: box.width / 2 - 80, y: box.height / 2 + 60 } })
  await canvas.click({ position: { x: box.width / 2 + 80, y: box.height / 2 + 60 } })
  await page.waitForTimeout(150)

  // oblique orbit (middle-drag) — must NOT place a point
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  await page.mouse.down({ button: 'middle' })
  await page.mouse.move(box.x + box.width / 2 + 90, box.y + box.height / 2 + 70, { steps: 6 })
  await page.mouse.up({ button: 'middle' })
  await page.waitForTimeout(300)
  ok((await page.locator('.sketch-chrome').count()) === 1, 'orbit mid-sketch: session alive, no errors')

  // hover a body EDGE specifically: narrow the selection filter to EDGES so
  // face hits cannot win the raycast (Codex5 B1.4)
  await page.getByRole('button', { name: 'Selection' }).click()
  await page.getByRole('menuitem', { name: /Select faces/ }).click() // faces OFF
  await page.waitForTimeout(120)
  let recordedEdgeId = null
  outer: for (let dx = -120; dx <= 120; dx += 12) {
    for (let dy = -110; dy <= 30; dy += 12) {
      await page.mouse.move(box.x + box.width / 2 + dx, box.y + box.height / 2 + dy)
      await page.waitForTimeout(40)
      const chip = page.locator('.context-hover')
      if (await chip.count()) {
        const text = await chip.textContent()
        if (text?.includes('context edge:')) {
          recordedEdgeId = await chip.getAttribute('data-context-id')
          break outer
        }
      }
    }
  }
  ok(recordedEdgeId !== null, `hover recovers a canonical EDGE id while sketching: ${recordedEdgeId ?? 'NONE'}`)
  // restore the faces filter for the rest of the walk
  await page.getByRole('button', { name: 'Selection' }).click()
  await page.getByRole('menuitem', { name: /Select faces/ }).click()
  await page.screenshot({ path: OUT + '/s1-accept-in-sketch-box.png' })

  // Sketch view returns; CANCEL must restore everything INCLUDING the body
  await page.locator('.sketch-chrome button', { hasText: 'Sketch view' }).click()
  await page.waitForTimeout(200)
  await page.locator('.sketch-chrome button', { hasText: 'Cancel' }).click()
  await page.waitForTimeout(300)
  ok((await page.locator('.sketch-chrome').count()) === 0, 'cancel: chrome gone')
  ok((await page.locator('.context-hover').count()) === 0, 'cancel: the context chip cleared')
  const datumsPressed = await page.getByRole('button', { name: 'Datum planes' }).getAttribute('aria-pressed')
  ok(datumsPressed === 'true', 'cancel: datum visibility restored to the user setting')
  ok(await bodyRenderable(), 'cancel: THE BODY SURVIVED (display controls still enabled)')
  ok((await page.locator('.model-tree', { hasText: 'Extrude 1' }).count()) > 0, 'cancel: Extrude 1 still in the tree')
  await page.screenshot({ path: OUT + '/s1-accept-after-cancel.png' })

  // the OK path: re-enter (the SECOND entry must still be a nonempty context)
  await page.locator('.rb-btn.rb-anchor', { hasText: 'Sketch' }).click()
  await page.locator('.feat-row.pickable', { hasText: 'FRONT' }).click()
  await page.locator('.sketch-chrome').waitFor()
  ok(await bodyRenderable(), 'second entry: STILL a nonempty contextual sketch')
  box = await canvas.boundingBox()
  await canvas.click({ position: { x: box.width / 2 - 70, y: box.height / 2 + 70 } })
  await canvas.click({ position: { x: box.width / 2 + 70, y: box.height / 2 + 70 } })
  await canvas.click({ position: { x: box.width / 2, y: box.height / 2 - 30 } })
  await page.locator('.sketch-chrome button', { hasText: 'Close ring' }).click()
  await page.waitForTimeout(120)
  await page.locator('.sketch-chrome button.primary', { hasText: 'OK' }).click()
  await page.waitForTimeout(600)
  ok((await page.locator('.model-tree', { hasText: 'Sketch 2' }).count()) > 0, 'OK: Sketch 2 committed on FRONT')
  ok((await page.locator('.sketch-chrome').count()) === 0, 'OK: chrome gone (cleanup)')
  ok(await bodyRenderable(), 'OK: THE BODY AND Sketch 2 coexist (the folded display)')
  ok((await page.locator('.model-tree', { hasText: 'Extrude 1' }).count()) > 0, 'OK: Extrude 1 still in the tree')
  await page.screenshot({ path: OUT + '/s1-accept-after-ok.png' })

  ok(checks + 1 === EXPECTED_CHECKS, `assertion count enforced: ${checks + 1}/${EXPECTED_CHECKS}`)
  if (problems.length) {
    console.error('PROBLEMS:'); for (const p of problems) console.error(' ', p)
    process.exitCode = 1
  } else console.log(`S1 acceptance: CLEAN (${checks} checks)`)
} catch (e) {
  console.error('accept failed:', e instanceof Error ? e.message : e)
  process.exitCode = 1
} finally {
  if (browser) await browser.close()
  await server.close()
}
