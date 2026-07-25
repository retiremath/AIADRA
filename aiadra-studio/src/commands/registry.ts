/**
 * The command taxonomy (arc 20260619-2 / 6b; ADR/0033 D9) — the single source
 * of truth rendered by the toolbar, the context menu, and the keyboard
 * dispatcher. Pure data + predicates; no React, no three.js.
 *
 * Enablement (Codex1 B1): view + display-mode commands gate on
 * `hasRenderableScene` (canonical OR imported reference geometry), so the
 * milestone-1b imported-only inspection lane keeps fit/reset + mode switching.
 * The `operations` group is a reserved disabled placeholder only — no
 * model-changing command leaks into the display shell (Codex1 N6 / D10 boundary).
 */
import { DISPLAY_MODES, MODE_LABELS, type DisplayMode } from '../display/modes'
import { STANDARD_VIEW_IDS, STANDARD_VIEW_LABELS } from '../display/viewOrientation'
import type { Command, CommandActions, CommandContext } from './types'

const MODE_SHORT: Record<DisplayMode, string> = {
  wireframe: 'Wire',
  'hidden-line': 'Hidden',
  'no-hidden': 'No-Hid',
  shading: 'Shade',
  'shading-edges': 'Shade+E',
}

const renderable = (c: CommandContext) => c.hasRenderableScene
const canonical = (c: CommandContext) => c.hasCanonicalPart

export const COMMANDS: Command[] = [
  { id: 'view.fit', group: 'view', kind: 'action', label: 'Refit', iconKey: 'fit', shortcut: 'f', isEnabled: renderable, run: (a) => a.fit() },
  // Creo Zoom In / Zoom Out (shell pass 1) — stepped ortho zoom beside Refit.
  { id: 'view.zoom-in', group: 'view', kind: 'action', label: 'Zoom in', iconKey: 'zoom-in', isEnabled: renderable, run: (a) => a.zoomBy(1.25) },
  { id: 'view.zoom-out', group: 'view', kind: 'action', label: 'Zoom out', iconKey: 'zoom-out', isEnabled: renderable, run: (a) => a.zoomBy(1 / 1.25) },
  { id: 'view.reset', group: 'view', kind: 'action', label: 'Reset view', iconKey: 'reset', shortcut: 'r', isEnabled: renderable, run: (a) => a.reset() },
  // Standard views (arc 20260625-1 / 6c). The nav cube and these buttons share
  // ONE orientation table; keybindings are deferred to the benchmark packet
  // (Codex1 Q2 — the 1–5 chords already own those digits for display modes).
  ...STANDARD_VIEW_IDS.map((id): Command => ({
    id: `orientation.${id}`,
    group: 'orientation',
    kind: 'action',
    label: STANDARD_VIEW_LABELS[id],
    shortLabel: STANDARD_VIEW_LABELS[id],
    isEnabled: renderable,
    run: (a) => a.standardView(id),
  })),
  // Roadmap-honest (Creo View Manager): named/saved views are a LATER strand.
  { id: 'orientation.view-manager', group: 'orientation', kind: 'action', label: 'View Manager…', disabledReason: 'Named views arrive with the View Manager strand', isEnabled: () => false, run: () => {} },
  ...DISPLAY_MODES.map((m, i): Command => ({
    id: `display.${m}`,
    group: 'display',
    kind: 'radio',
    label: MODE_LABELS[m],
    shortLabel: MODE_SHORT[m],
    shortcut: String(i + 1),
    radioValue: m,
    isEnabled: renderable,
    isActive: (c) => c.mode === m,
    run: (a) => a.setMode(m),
  })),
  // scene.grid REMOVED (arc 20260716-1, Codex1 B3): no empty-part grid —
  // toolbar chip, context-menu row, and the `g` shortcut all died with
  // this entry. A future sketch mode mints its OWN mode-scoped command.
  // The datum overlay (arc 20260714-2 EP1) — the empty-part scaffold's
  // visibility toggle (origin triad + the three principal planes). Always
  // available (datums are useful with no geometry — that IS the empty-part
  // paradigm).
  { id: 'scene.datums', group: 'scene', kind: 'toggle', label: 'All datum display', shortLabel: 'Datums', iconKey: 'datums', shortcut: 'p', isEnabled: () => true, isActive: (c) => c.datumsVisible, run: (a) => a.toggleDatums() },
  // The Creo datum-display FILTERS (shell pass 1): per-kind refinement under
  // the master toggle. Enabled only while the master is on (a filter of a
  // hidden overlay is a no-op — honest disable, mirroring Creo's grey-out).
  { id: 'scene.datum-planes', group: 'scene', kind: 'toggle', label: 'Plane display', isEnabled: (c) => c.datumsVisible, isActive: (c) => c.datumFilters.planes, run: (a) => a.toggleDatumFilter('planes') },
  { id: 'scene.datum-fill', group: 'scene', kind: 'toggle', label: 'Plane fill display', isEnabled: (c) => c.datumsVisible, isActive: (c) => c.datumFilters.fill, run: (a) => a.toggleDatumFilter('fill') },
  { id: 'scene.datum-origin', group: 'scene', kind: 'toggle', label: 'Origin csys display', isEnabled: (c) => c.datumsVisible, isActive: (c) => c.datumFilters.origin, run: (a) => a.toggleDatumFilter('origin') },
  // Selection filters + clear (arc 20260625-1 / 6c). Selection is canonical-only,
  // so these gate on `hasCanonicalPart`. Vertex selection is deferred (no vertex
  // markers rendered yet) — like the `operations` reserved slot.
  { id: 'selection.filter-face', group: 'selection', kind: 'toggle', label: 'Select faces', shortLabel: 'Faces', isEnabled: canonical, isActive: (c) => c.filter.face, run: (a) => a.toggleFilterKind('face') },
  { id: 'selection.filter-edge', group: 'selection', kind: 'toggle', label: 'Select edges', shortLabel: 'Edges', isEnabled: canonical, isActive: (c) => c.filter.edge, run: (a) => a.toggleFilterKind('edge') },
  { id: 'selection.clear', group: 'selection', kind: 'action', label: 'Clear selection', shortLabel: 'Clear', isEnabled: (c) => c.hasSelection, run: (a) => a.clearSelection() },
  // Reserved placeholder — authoring/model-changing commands are a LATER strand
  // (ADR/0033 D10 boundary; Codex1 N6). Always disabled, no effect.
  { id: 'operations.soon', group: 'operations', kind: 'action', label: 'Operations (with selection) — soon', isEnabled: () => false, run: () => {} },
]

export const COMMANDS_BY_ID: Record<string, Command> = Object.fromEntries(
  COMMANDS.map((c) => [c.id, c]),
)

export function commandsInGroup(group: Command['group']): Command[] {
  return COMMANDS.filter((c) => c.group === group)
}

/** Normalize a keydown into a comparable chord (`mod` = ctrl/cmd). */
export function normalizeChord(e: {
  key: string
  ctrlKey: boolean
  metaKey: boolean
  shiftKey: boolean
  altKey: boolean
}): string {
  const parts: string[] = []
  if (e.ctrlKey || e.metaKey) parts.push('mod')
  if (e.altKey) parts.push('alt')
  if (e.shiftKey) parts.push('shift')
  parts.push(e.key.toLowerCase())
  return parts.join('+')
}

/**
 * Resolve a chord to a command and run it if enabled. Pure (the DOM focus guard
 * lives in the App keydown handler). Returns true if a command ran.
 */
export function dispatchShortcut(
  chord: string,
  ctx: CommandContext,
  actions: CommandActions,
): boolean {
  const cmd = COMMANDS.find((c) => c.shortcut === chord)
  if (cmd && cmd.isEnabled(ctx)) {
    cmd.run(actions, ctx)
    return true
  }
  return false
}
