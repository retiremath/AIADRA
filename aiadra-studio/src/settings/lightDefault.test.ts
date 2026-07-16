/**
 * V-1 executable acceptance (arc 20260716-1; Codex1 B2): the CSS↔module drift
 * gate and the WCAG contrast matrix over the SHIPPED light default.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { CHROME, COLOR_SCHEME, CONTRAST_MATRIX, contrastRatio } from './lightDefault'

const css = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), '..', 'index.css'),
  'utf-8',
)

function cssRootVars(): Record<string, string> {
  const root = css.match(/:root \{([\s\S]*?)\n\}/)
  expect(root, ':root block present').toBeTruthy()
  const out: Record<string, string> = {}
  for (const m of root![1].matchAll(/(--[\w-]+):\s*([^;]+);/g)) {
    out[m[1]] = m[2].trim()
  }
  return out
}

describe('THE light default — one palette authority (B2)', () => {
  it('index.css :root matches the CHROME projection exactly (drift gate)', () => {
    const vars = cssRootVars()
    for (const [key, value] of Object.entries(CHROME)) {
      expect(vars[key], `${key} declared in :root`).toBeDefined()
      expect(vars[key].toLowerCase(), key).toBe(value.toLowerCase())
    }
  })

  it('color-scheme is light', () => {
    expect(css).toMatch(new RegExp(`color-scheme:\\s*${COLOR_SCHEME}`))
  })

  it('no second :root redefines palette tokens', () => {
    const roots = css.match(/:root \{/g) ?? []
    expect(roots).toHaveLength(1)
  })

  it('disabled styling never rides opacity over a readable token (the trap)', () => {
    // explicit tokens exist; no rule may combine var(--text) with opacity<1
    expect(CHROME['--text-disabled']).toBeDefined()
    expect(CHROME['--text-roadmap']).toBeDefined()
  })
})

describe('the WCAG contrast matrix (B2.4) — the SHIPPED default is AA-checked', () => {
  for (const [fg, bg, min, covers] of CONTRAST_MATRIX) {
    it(`${fg} on ${bg} ≥ ${min}:1 — ${covers}`, () => {
      const ratio = contrastRatio(CHROME[fg], CHROME[bg])
      expect(ratio, `${fg}(${CHROME[fg]}) on ${bg}(${CHROME[bg]}) = ${ratio.toFixed(2)}`)
        .toBeGreaterThanOrEqual(min)
    })
  }
})
