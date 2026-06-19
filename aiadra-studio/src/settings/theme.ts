/**
 * The coordinated display theme (arc 20260619-1 / 6a; ADR/0033 D8). Resolves
 * the registry's color values into one `Theme` object the renderer applies.
 * This is the "these colors must be one coordinated theme" object D8 names —
 * the scattered constants now have a single owner.
 *
 * `paperBody` inheritance (Codex1 B2): when `paperBodyTracksBackground` is true
 * the unshaded-body color IS the background (so changing the background changes
 * the paper), and the standalone `paperBody` value is NOT used — no copied
 * background is materialized into the resolved theme's persistence path.
 */
import { DEFAULT_VALUES, type SettingValue } from './descriptors'

export type CanonicalEdgeKind = 'sharp' | 'tangent' | 'seam' | 'boundary' | 'free'

export interface Theme {
  viewportBackground: number
  paperBody: number
  gridMajor: number
  gridMinor: number
  canonicalFace: number
  canonicalEdge: Record<CanonicalEdgeKind, number>
  hiddenEdgeDim: number
  hlrVisible: number
  hlrHidden: number
  selectionHighlight: number
  importedFace: number
  importedEdgeBright: number
  importedEdgeDim: number
}

export function themeFromValues(v: Record<string, SettingValue>): Theme {
  const c = (k: string) => v[k] as number
  const bg = c('viewportBackground')
  const tracks = v.paperBodyTracksBackground as boolean
  const edgeDefault = c('canonicalEdgeDefault')
  return {
    viewportBackground: bg,
    paperBody: tracks ? bg : c('paperBody'),
    gridMajor: c('gridMajor'),
    gridMinor: c('gridMinor'),
    canonicalFace: c('canonicalFace'),
    canonicalEdge: {
      sharp: c('canonicalEdgeSharp'),
      tangent: c('canonicalEdgeTangent'),
      seam: c('canonicalEdgeSeam'),
      boundary: edgeDefault,
      free: edgeDefault,
    },
    hiddenEdgeDim: c('hiddenEdgeDim'),
    hlrVisible: c('hlrVisible'),
    hlrHidden: c('hlrHidden'),
    selectionHighlight: c('selectionHighlight'),
    importedFace: c('importedFace'),
    importedEdgeBright: c('importedEdgeBright'),
    importedEdgeDim: c('importedEdgeDim'),
  }
}

/** The built-in default theme — the value `buildCanonicalPart`/`buildHlrOverlay`
 * fall back to when no live theme is supplied (keeps headless tests stable). */
export const DEFAULT_THEME: Theme = themeFromValues(DEFAULT_VALUES)
