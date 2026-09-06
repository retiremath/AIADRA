// W-6 label check (Codex21 B1/B2) — the NODE half: serves the production
// modules through Vite, runs `walk-w6-labels.probe.mjs` in headless Chromium
// (real canvas text + WebGL), and reports per label × zoom:
//   B2  the visible ink clears its own measured line by ≥ 6 screen px;
//   B1  the rendered text is as dark as its dimension line (sRGB textures).
// Captures go to the git-ignored shots/w6. Run: `npm run walk:w6`.
import { createServer } from 'vite'
import { mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import process from 'node:process'
import { chromium } from 'playwright'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..') // repo-relative
const OUT = resolve(ROOT, 'shots/w6')
mkdirSync(OUT, { recursive: true })
const HTML = '<!doctype html><html><head><meta charset="utf-8"><title>w6</title></head><body style="margin:0;background:#e8eee2"><script type="module" src="/scripts/walk-w6-labels.probe.mjs"></script></body></html>'
const page_plugin = {
  name: 'w6-page',
  configureServer(server) {
    server.middlewares.use((req, res, next) => {
      if (req.url === '/w6.html') {
        res.setHeader('Content-Type', 'text/html')
        res.end(HTML)
        return
      }
      next()
    })
  },
}
const server = await createServer({ root: ROOT, server: { port: 0 }, logLevel: 'warn', plugins: [page_plugin] })
await server.listen()
const url = server.resolvedUrls.local[0]
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] })
const notes = []
const note = (ok, msg) => notes.push(`${ok ? 'PASS' : 'FAIL'} ${msg}`)
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 600 } })
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
  await page.goto(`${url}w6.html`, { waitUntil: 'load' })
  await page.waitForFunction(() => globalThis.__w6?.done === true, null, { timeout: 120000 })
  const results = await page.evaluate(() => globalThis.__w6.results)
  await page.screenshot({ path: `${OUT}/free-line-0.2.png` })
  const scenarios = [...new Set(results.map((r) => r.scenario))]
  note(results.length >= 40, `${results.length} label×zoom checks over ${scenarios.length} scenarios at zooms 0.1 / 0.2 / 0.4`)
  for (const r of results) {
    const tag = `${r.scenario} · wpp ${r.wpp} · ${r.text} (${r.owner.replace('ann:', '')})`
    note(r.ok2, `B2 ${tag}: ink clears its own line by ${r.minDistPx} px (outward ${r.outward.map((x) => x.toFixed(2)).join(',')})`)
    note(r.ok1, `B1 ${tag}: darkest grey in the ink: luminance ${r.textLum} (rgb ${r.textRgb?.join('/')}; palette 0x4b5563 = 84) — its line's darkest pixel ${r.lineLum}`)
  }
  const worst2 = Math.min(...results.map((r) => r.minDistPx))
  const worst1 = Math.max(...results.map((r) => r.textLum ?? 999))
  note(true, `summary: smallest ink-to-line gap ${worst2} px; lightest text luminance ${worst1}`)
  note(errors.length === 0, `no page errors (${errors.length})${errors.length ? ': ' + errors.slice(0, 3).join(' | ') : ''}`)
} catch (e) {
  note(false, `script error: ${String(e).split('\n')[0]}`)
} finally {
  console.log(notes.filter((n) => n.startsWith('FAIL') || /^PASS (\d+ label|summary|no page)/.test(n)).join('\n'))
  console.log(`(${notes.filter((n) => n.startsWith('PASS')).length} PASS / ${notes.filter((n) => n.startsWith('FAIL')).length} FAIL)`)
  await browser.close()
  await server.close()
}
process.exit(notes.some((n) => n.startsWith('FAIL')) ? 1 : 0)
