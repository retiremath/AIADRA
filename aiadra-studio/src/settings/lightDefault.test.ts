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

  it('disabled styling never rides opacity over a readable token (the trap — Codex2 B3: MECHANICAL)', () => {
    // The explicit tokens exist…
    expect(CHROME['--text-disabled']).toBeDefined()
    expect(CHROME['--text-roadmap']).toBeDefined()
    // …and the STYLESHEET ITSELF is inspected, not just the token pairs: the
    // whole chrome bans the `opacity` property outright. Alpha-compositing a
    // readable color is exactly how a passing token matrix ships a failing
    // rendered contrast (Codex2 measured 2.2–2.5:1 on three such rules).
    // A future DECORATIVE opacity must be whitelisted here, with its rule
    // named, and must never apply to text or icons.
    const rules = css.replace(/\/\*[\s\S]*?\*\//g, '') // strip prose comments
    expect(rules).not.toMatch(/opacity\s*:/)
  })

  it('every disabled-state rule that sets a text color uses an explicit full-opacity token (Codex2 B3)', () => {
    const rules = css.replace(/\/\*[\s\S]*?\*\//g, '')
    // every rule block whose selector is disabled-ish and which sets `color:`
    const re = /([^{}]+)\{([^}]*)\}/g
    let m: RegExpExecArray | null
    let inspected = 0
    while ((m = re.exec(rules)) !== null) {
      // `:not(:disabled)` is an ENABLED state — strip :not() before testing
      const selector = m[1].replace(/:not\([^)]*\)/g, '')
      if (!/(?::disabled|\.disabled|\.off\b|\.rb-roadmap)/.test(selector)) continue
      const body = m[2]
      const color = /(?:^|[;\s])color\s*:\s*([^;]+);?/.exec(body)?.[1]?.trim()
      if (!color) continue
      inspected += 1
      expect(
        ['var(--text-disabled)', 'var(--text-roadmap)', 'var(--muted)', 'var(--warn)'].includes(color),
        `${m[1].trim()} sets color ${color} — not an approved full-opacity token`,
      ).toBe(true)
    }
    expect(inspected).toBeGreaterThanOrEqual(5) // the sweep actually inspected the surface
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
