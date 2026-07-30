/**
 * Settings descriptors (arc 20260619-1 / 6a; ADR/0033 D8). The registry is a
 * list of typed descriptors — schema-as-data — over a small v1 type set
 * (`color` | `number` | `boolean` | `enum`). Each descriptor carries its
 * default, label, group, and validation bounds. This is the single source of
 * truth for which settings exist, their defaults, and how a value is validated
 * before it enters live state.
 *
 * The color set is the FULL live display palette (Codex1 B2): every hard-coded
 * color on the canonical / HLR / reference path becomes a registry key, with
 * the prior literal as its default (so day-one behaviour is unchanged except
 * the new light-green background).
 */
import { DISPLAY_MODES, MODE_LABELS, type DisplayMode } from '../display/modes'

export type SettingType = 'color' | 'number' | 'boolean' | 'enum'
export type SettingValue = number | boolean | string

export interface SettingDescriptor {
  key: string
  type: SettingType
  default: SettingValue
  label: string
  group: 'Theme' | 'Behavior'
  min?: number
  max?: number
  /** A STRICT upper bound (v < exclusiveMax). Distinct from `max`, which is
   *  inclusive — the snap tolerance needs `< 45°` exactly, because at 45° a
   *  line would satisfy the horizontal AND the vertical proposal at once. */
  exclusiveMax?: number
  step?: number
  options?: { value: string; label: string }[]
  unit?: string
  help?: string
}

const MODE_OPTIONS = DISPLAY_MODES.map((m: DisplayMode) => ({ value: m, label: MODE_LABELS[m] }))

export const SETTING_DESCRIPTORS: SettingDescriptor[] = [
  // ---- Theme: viewport background + body + grid ----
  // Petre's preferred light-green default (supersedes the prior 0xe6e9ec).
  { key: 'viewportBackground', type: 'color', default: 0xdfe3e8, label: 'Background', group: 'Theme' },
  {
    key: 'paperBodyTracksBackground',
    type: 'boolean',
    default: true,
    label: 'Paper body follows background',
    group: 'Theme',
    help: 'Unshaded (Hidden Line / No Hidden) body color tracks the background unless overridden.',
  },
  { key: 'paperBody', type: 'color', default: 0xdfe3e8, label: 'Paper body (override)', group: 'Theme' },
  { key: 'gridMajor', type: 'color', default: 0xb9c0c7, label: 'Grid (major)', group: 'Theme' },
  { key: 'gridMinor', type: 'color', default: 0xcdd3d9, label: 'Grid (minor)', group: 'Theme' },
  // ---- Theme: canonical part ----
  { key: 'canonicalFace', type: 'color', default: 0xb8c2cc, label: 'Face', group: 'Theme' },
  { key: 'canonicalEdgeSharp', type: 'color', default: 0x222226, label: 'Edge — sharp', group: 'Theme' },
  { key: 'canonicalEdgeTangent', type: 'color', default: 0x4a4a52, label: 'Edge — tangent', group: 'Theme' },
  { key: 'canonicalEdgeSeam', type: 'color', default: 0x9aa0aa, label: 'Edge — seam', group: 'Theme' },
  { key: 'canonicalEdgeDefault', type: 'color', default: 0x222226, label: 'Edge — other', group: 'Theme' },
  { key: 'hiddenEdgeDim', type: 'color', default: 0xb4bac2, label: 'Hidden edge (dim)', group: 'Theme' },
  // ---- Theme: settled HLR overlay ----
  { key: 'hlrVisible', type: 'color', default: 0x222226, label: 'HLR — visible', group: 'Theme' },
  { key: 'hlrHidden', type: 'color', default: 0xb4bac2, label: 'HLR — hidden', group: 'Theme' },
  // ---- Theme: selection + reference imports ----
  { key: 'selectionHighlight', type: 'color', default: 0x16314e, label: 'Selection highlight', group: 'Theme' },
  { key: 'hoverHighlight', type: 'color', default: 0x4a7fb5, label: 'Hover pre-highlight', group: 'Theme' },
  { key: 'importedFace', type: 'color', default: 0x9aa0a6, label: 'Imported face', group: 'Theme' },
  { key: 'importedEdgeBright', type: 'color', default: 0x33373d, label: 'Imported edge', group: 'Theme' },
  { key: 'importedEdgeDim', type: 'color', default: 0xb4bac2, label: 'Imported edge (dim)', group: 'Theme' },
  // ---- Behavior (startup defaults + tunables; Codex1 N3/N4) ----
  {
    key: 'settleMs',
    type: 'number',
    default: 200,
    label: 'Camera-settle delay',
    group: 'Behavior',
    min: 0,
    max: 2000,
    step: 10,
    unit: 'ms',
    help: 'Applies on next viewport mount (Codex1 N4).',
  },
  {
    key: 'defaultDisplayMode',
    type: 'enum',
    default: 'shading-edges',
    label: 'Default display mode',
    group: 'Behavior',
    options: MODE_OPTIONS,
    help: 'Startup default; the live mode is changed transiently from the viewport (Codex1 N3).',
  },
  // ---- CAD↔AI dock chrome (arc 20260711-10 / MVP-1; ADR/0040 D5/N4). Typed
  // settings, not ad-hoc local state (Codex arc-20260711-10 note). The live
  // width/open are transient; these are the persisted startup values. ----
  {
    key: 'aiDockWidth',
    type: 'number',
    default: 340,
    label: 'AI dock width',
    group: 'Behavior',
    min: 260,
    max: 640,
    step: 10,
    unit: 'px',
    help: 'The CAD↔AI dock width; also set by dragging its edge.',
  },
  {
    key: 'aiDockOpenDefault',
    type: 'boolean',
    default: true,
    label: 'Show AI dock by default',
    group: 'Behavior',
    help: 'Startup default; the live toggle is transient (like grid/mode).',
  },
  // ---- Quick Access Toolbar (shell pass 1; Creo QAT benchmark). One boolean
  // per pinnable command — the v1 scalar type set holds, no schema change.
  // Defaults mirror Creo's out-of-box QAT (New/Open pinned). ----
  {
    key: 'qatShowNew',
    type: 'boolean',
    default: true,
    label: 'Quick Access: New…',
    group: 'Behavior',
  },
  {
    key: 'qatShowOpen',
    type: 'boolean',
    default: true,
    label: 'Quick Access: Open Workspace…',
    group: 'Behavior',
  },
  {
    key: 'qatShowImport',
    type: 'boolean',
    default: false,
    label: 'Quick Access: Import reference geometry…',
    group: 'Behavior',
  },
  {
    key: 'qatShowClose',
    type: 'boolean',
    default: false,
    label: 'Quick Access: Close',
    group: 'Behavior',
  },
  // ---- Sketcher (ADR/0044 A4; arc 20260730-1) --------------------------
  // Class-3 LOCAL preference (ADR/0045): how close to level a drawn segment
  // must be before Studio PROPOSES a horizontal/vertical fact. Studio only
  // ever proposes the FACT — the engine's solve is what moves the geometry
  // (ADR/0045 D6), so this number can never make Studio and the engine
  // disagree about where a line is.
  {
    key: 'sketch.snapAngleToleranceDeg',
    type: 'number',
    default: 3,
    label: 'Snap angle tolerance',
    group: 'Behavior',
    min: 0,
    exclusiveMax: 45,
    step: 0.5,
    unit: '°',
    help: 'Within this angle of level or plumb, a drawn segment gets a horizontal/vertical constraint. 0 disables snapping.',
  },
  // Studio-owned input threshold: the pointer travel below which a drag is a
  // click, not a segment. DELIBERATELY NOT the engine's `L_min_mm` — that is
  // a model-space non-collapse guard in a frozen solver contract, and reusing
  // it would let a UI preference leak into branch admission.
  {
    key: 'sketch.minDragPx',
    type: 'number',
    default: 4,
    label: 'Minimum drag',
    group: 'Behavior',
    min: 1,
    max: 40,
    step: 1,
    unit: 'px',
    help: 'Pointer travel below this is treated as a click rather than a drawn segment.',
  },
  {
    key: 'qatBelowRibbon',
    type: 'boolean',
    default: false,
    label: 'Quick Access below the ribbon',
    group: 'Behavior',
    help: 'Creo’s "Show Below the Ribbon" — moves the Quick Access bar under the ribbon row.',
  },
  // The navigator (tabbed tree) width — DRAG-RESIZABLE like Creo's sash
  // (Petre 2026-07-25: future columns — parameters etc. — need room).
  {
    key: 'navigatorWidth',
    type: 'number',
    default: 218,
    label: 'Navigator width',
    group: 'Behavior',
    min: 170,
    max: 640,
    step: 2,
    unit: 'px',
    help: 'Also set by dragging the navigator’s right edge.',
  },
  // The graphics toolbar's placement (Creo: movable/dismissable in-graphics
  // toolbar; shell pass 1). Right-click the bar to move/hide it; a small
  // restore handle appears when hidden.
  {
    key: 'graphicsToolbarPosition',
    type: 'enum',
    default: 'top',
    label: 'Graphics toolbar position',
    group: 'Behavior',
    options: [
      { value: 'top', label: 'Top' },
      { value: 'bottom', label: 'Bottom' },
      { value: 'hidden', label: 'Hidden' },
    ],
  },
]

export const DESCRIPTOR_BY_KEY: Record<string, SettingDescriptor> = Object.fromEntries(
  SETTING_DESCRIPTORS.map((d) => [d.key, d]),
)

export const DEFAULT_VALUES: Record<string, SettingValue> = Object.fromEntries(
  SETTING_DESCRIPTORS.map((d) => [d.key, d.default]),
)

export function isKnownSetting(key: string): boolean {
  return Object.prototype.hasOwnProperty.call(DESCRIPTOR_BY_KEY, key)
}

export interface ValueCheck {
  ok: boolean
  error?: string
}

/** Validate a single value against its descriptor. Fail-loud, never coerce. */
export function validateSettingValue(d: SettingDescriptor, value: unknown): ValueCheck {
  switch (d.type) {
    case 'color':
      if (typeof value !== 'number' || !Number.isInteger(value) || value < 0 || value > 0xffffff) {
        return { ok: false, error: `${d.key}: color must be an integer 0x000000..0xffffff` }
      }
      return { ok: true }
    case 'number':
      if (typeof value !== 'number' || !Number.isFinite(value)) {
        return { ok: false, error: `${d.key}: must be a finite number` }
      }
      if (d.min !== undefined && value < d.min) return { ok: false, error: `${d.key}: below min ${d.min}` }
      if (d.max !== undefined && value > d.max) return { ok: false, error: `${d.key}: above max ${d.max}` }
      if (d.exclusiveMax !== undefined && !(value < d.exclusiveMax)) {
        return { ok: false, error: `${d.key}: must be strictly below ${d.exclusiveMax}` }
      }
      return { ok: true }
    case 'boolean':
      if (typeof value !== 'boolean') return { ok: false, error: `${d.key}: must be a boolean` }
      return { ok: true }
    case 'enum':
      if (typeof value !== 'string' || !d.options?.some((o) => o.value === value)) {
        return { ok: false, error: `${d.key}: must be one of the declared options` }
      }
      return { ok: true }
  }
}
