/**
 * THE LIGHT DEFAULT — the single palette authority (arc 20260716-1 V-1;
 * Codex1 B2). One named source feeds BOTH surfaces:
 *
 *  - CHROME: the css custom properties `index.css` declares on `:root` —
 *    an executable drift test parses the stylesheet and FAILS if the two
 *    diverge (`lightDefault.test.ts`);
 *  - the VIEWPORT/display defaults remain the settings-registry descriptors
 *    (`descriptors.ts` — already Petre's light set; re-exported here so both
 *    projections are reachable from one module).
 *
 * The shipped default is AA-checked by the executable contrast matrix
 * (normal text >= 4.5:1, large/UI/icons >= 3:1, and the PROJECT FLOOR for
 * disabled text >= 3:1 — deliberately above the WCAG exception). Custom
 * user-selected colors carry NO such guarantee (the settings UI does not
 * validate contrast); the guarantee is about THIS default.
 */

export { DEFAULT_VALUES as VIEWPORT_DEFAULTS } from './descriptors'

/** Chrome custom properties, exactly as `:root` must declare them. */
export const CHROME: Record<string, string> = {
  '--bg': '#eceef1',
  '--panel': '#f7f8fa',
  '--panel-2': '#e2e5ea',
  '--border': '#c2c8d1',
  '--text': '#24272c',
  '--text-h': '#0d0f12',
  '--muted': '#5b6470',
  // explicit disabled tokens at FULL OPACITY (the opacity-multiplication trap
  // is banned — Codex1 non-blocker): both hold the >=3:1 project floor.
  '--text-disabled': '#767f8b',
  '--text-roadmap': '#767f8b',
  // the single accent (the green File/primary identity, AA on light chrome)
  '--accent': '#2e6d3f',
  '--accent-ink': '#ffffff',
  '--warn': '#8a5a14',
  '--ok': '#2e6d3f',
  '--err': '#a13232',
  '--focus': '#164a86',
  // plane name hues (legible on light panels)
  '--plane-xy': '#2b5e8f',
  '--plane-yz': '#9a5220',
  '--plane-zx': '#2e6d3f',
  '--committed': '#2e6d3f',
}

export const COLOR_SCHEME = 'light'

/** The executable contrast matrix (Codex1 B2.4): [foreground, background,
 *  minimum ratio, what it covers]. Enumerated against ACTUAL backgrounds. */
export const CONTRAST_MATRIX: Array<[fg: string, bg: string, min: number, covers: string]> = [
  ['--text', '--panel', 4.5, 'body text on panels (ribbon labels, sidebar, tree)'],
  ['--text', '--panel-2', 4.5, 'body text on inset panels (menus, inputs)'],
  ['--text', '--bg', 4.5, 'body text on the window background (status bar)'],
  ['--text-h', '--panel', 4.5, 'headings/selected text'],
  ['--muted', '--panel', 4.5, 'secondary text (hints, badges)'],
  ['--muted', '--bg', 4.5, 'secondary text on the window background'],
  ['--text-disabled', '--panel', 3.0, 'DISABLED command labels (project floor)'],
  ['--text-roadmap', '--panel', 3.0, 'roadmap-disabled labels (project floor)'],
  ['--accent', '--panel', 3.0, 'accent icons/boundaries on panels'],
  ['--accent-ink', '--accent', 4.5, 'text on accent (active tab, primary buttons)'],
  ['--warn', '--panel', 4.5, 'warning text'],
  ['--err', '--panel', 4.5, 'error text'],
  ['--ok', '--panel', 3.0, 'success glyphs'],
  ['--focus', '--panel', 3.0, 'the keyboard focus ring vs panels'],
  ['--focus', '--panel-2', 3.0, 'the focus ring vs inset panels'],
  ['--border', '--panel', 1.35, 'hairline borders (non-text; visibility floor)'],
  ['--plane-xy', '--panel', 4.5, 'plane names in pickers'],
  ['--plane-yz', '--panel', 4.5, 'plane names in pickers'],
  ['--plane-zx', '--panel', 4.5, 'plane names in pickers'],
]

/** WCAG relative luminance of a #rrggbb hex. */
export function relativeLuminance(hex: string): number {
  const n = parseInt(hex.replace('#', ''), 16)
  const chan = (v: number) => {
    const c = v / 255
    return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
  }
  return (
    0.2126 * chan((n >> 16) & 0xff) + 0.7152 * chan((n >> 8) & 0xff) + 0.0722 * chan(n & 0xff)
  )
}

export function contrastRatio(hexA: string, hexB: string): number {
  const la = relativeLuminance(hexA)
  const lb = relativeLuminance(hexB)
  const [hi, lo] = la >= lb ? [la, lb] : [lb, la]
  return (hi + 0.05) / (lo + 0.05)
}
