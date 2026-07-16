/**
 * Command taxonomy types (arc 20260619-2 / 6b; ADR/0033 D9). Schema-as-data:
 * a command is a typed descriptor with predicates + a `run` that calls injected
 * actions — NOT a closure over `ViewportApi` or React state (Codex1 N3), so the
 * same descriptors render as a toolbar now and a ribbon later and predicate/
 * dispatch tests stay cheap.
 */
import type { DisplayMode } from '../display/modes'
import type { StandardViewId } from '../display/viewOrientation'
import type { SelectableKind } from '../selection/store'

export type CommandKind = 'action' | 'toggle' | 'radio'
export type CommandGroup =
  | 'view'
  | 'orientation'
  | 'display'
  | 'scene'
  | 'selection'
  | 'operations'

/**
 * The enablement/active snapshot. Scene facts are SPLIT (Codex1 B1): an
 * imported-only reference scene is renderable and keeps view/grid/display-mode
 * affordances; canonical-only behavior (HLR, snap-to-canonical, topology
 * selection — none in 6b) is reserved for `hasCanonicalPart`.
 */
export interface CommandContext {
  hasCanonicalPart: boolean
  hasReferenceGeometry: boolean
  hasRenderableScene: boolean // canonical OR reference
  mode: DisplayMode
  /** The datum overlay (arc 20260714-2 EP1). */
  datumsVisible: boolean
  /** Selection filter + selection presence (arc 20260625-1 / 6c). */
  filter: { face: boolean; edge: boolean }
  hasSelection: boolean
}

/** The runtime actions a command invokes — injected, never captured (N3). */
export interface CommandActions {
  fit(): void
  reset(): void
  setMode(mode: DisplayMode): void
  toggleDatums(): void
  /** Orient the main camera to a standard view (arc 20260625-1 / 6c). */
  standardView(id: StandardViewId): void
  toggleFilterKind(kind: SelectableKind): void
  clearSelection(): void
}

export interface Command {
  id: string
  group: CommandGroup
  kind: CommandKind
  label: string
  /** Short label for the segmented control (modes); falls back to `label`. */
  shortLabel?: string
  /** Key into the icon map (`commands/icons`); text label used when absent. */
  iconKey?: string
  /** Normalized shortcut chord (e.g. `f`, `g`, `1`, `mod+shift+f`). */
  shortcut?: string
  /** For radio members — the mode this command selects. */
  radioValue?: DisplayMode
  isEnabled(ctx: CommandContext): boolean
  isActive?(ctx: CommandContext): boolean
  run(actions: CommandActions, ctx: CommandContext): void
}
