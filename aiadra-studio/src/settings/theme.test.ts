import { describe, expect, it } from 'vitest'
import { DEFAULT_THEME, themeFromValues } from './theme'
import { DEFAULT_VALUES } from './descriptors'

describe('theme', () => {
  it('default background is the light-green default (Petre)', () => {
    expect(DEFAULT_THEME.viewportBackground).toBe(0xe4efdf)
  })

  it('paperBody tracks background when tracking is on (no copied background — Codex1 B2)', () => {
    const t = themeFromValues({
      ...DEFAULT_VALUES,
      viewportBackground: 0x102030,
      paperBodyTracksBackground: true,
    })
    expect(t.paperBody).toBe(0x102030)
  })

  it('paperBody uses the explicit override when tracking is off', () => {
    const t = themeFromValues({
      ...DEFAULT_VALUES,
      viewportBackground: 0x102030,
      paperBodyTracksBackground: false,
      paperBody: 0xabcdef,
    })
    expect(t.paperBody).toBe(0xabcdef)
  })

  it('maps canonical edge kinds; boundary/free fall back to the default edge', () => {
    const t = themeFromValues({
      ...DEFAULT_VALUES,
      canonicalEdgeSharp: 0x111111,
      canonicalEdgeDefault: 0x222222,
    })
    expect(t.canonicalEdge.sharp).toBe(0x111111)
    expect(t.canonicalEdge.boundary).toBe(0x222222)
    expect(t.canonicalEdge.free).toBe(0x222222)
  })

  it('owns every B2 display surface', () => {
    const t = DEFAULT_THEME
    expect(typeof t.viewportBackground).toBe('number')
    expect(typeof t.paperBody).toBe('number')
    expect(typeof t.gridMajor).toBe('number')
    expect(typeof t.gridMinor).toBe('number')
    expect(typeof t.canonicalFace).toBe('number')
    expect(typeof t.canonicalEdge.sharp).toBe('number')
    expect(typeof t.canonicalEdge.tangent).toBe('number')
    expect(typeof t.canonicalEdge.seam).toBe('number')
    expect(typeof t.hiddenEdgeDim).toBe('number')
    expect(typeof t.hlrVisible).toBe('number')
    expect(typeof t.hlrHidden).toBe('number')
    expect(typeof t.selectionHighlight).toBe('number')
    expect(typeof t.importedFace).toBe('number')
    expect(typeof t.importedEdgeBright).toBe('number')
    expect(typeof t.importedEdgeDim).toBe('number')
  })
})
