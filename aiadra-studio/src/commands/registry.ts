/**
 * The command taxonomy (arc 20260619-2 / 6b; ADR/0033 D9) — the single source
 * of truth rendered by the toolbar, the context menu, and the keyboard
 * dispatcher. Pure data + predicates; no React, no three.js.
 *
 * Enablement (Codex1 B1): view + display-mode commands gate on
 * `hasRenderableScene` (canonical OR imported reference geometry), so the
 * milestone-1b imported-only inspection lane keeps fit/reset + mode switching.
 * Grid is always available (the ground plane is useful even with no geometry).
 * The `operations` group is a reserved disabled placeholder only — no
 * model-changing command leaks into the display shell (Codex1 N6 / D10 boundary).
 */
import { DISPLAY_MODES, MODE_LABELS, type DisplayMode } from '../display/modes'
import type { Command, CommandActions, CommandContext } from './types'

const MODE_SHORT: Record<DisplayMode, string> = {
  wireframe: 'Wire',
  'hidden-line': 'Hidden',
  'no-hidden': 'No-Hid',
  shading: 'Shade',
  'shading-edges': 'Shade+E',
}

const renderable = (c: CommandContext) => c.hasRenderableScene

export const COMMANDS: Command[] = [
  { id: 'view.fit', group: 'view', kind: 'action', label: 'Fit to view', iconKey: 'fit', shortcut: 'f', isEnabled: renderable, run: (a) => a.fit() },
  { id: 'view.reset', group: 'view', kind: 'action', label: 'Reset view', iconKey: 'reset', shortcut: 'r', isEnabled: renderable, run: (a) => a.reset() },
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
  { id: 'scene.grid', group: 'scene', kind: 'toggle', label: 'Grid', iconKey: 'grid', shortcut: 'g', isEnabled: () => true, isActive: (c) => c.gridVisible, run: (a) => a.toggleGrid() },
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
