/**
 * The CONDENSED in-graphics toolbar (arc 20260619-2 / 6b → 20260716-1 V-4,
 * Codex1 B4) — Creo-benchmarked density: icon buttons + THREE dropdowns on
 * the shared `DropdownMenu` primitive (display style · named views ·
 * selection), replacing the old full-width text-chip strip. Still rendered
 * FROM the command taxonomy + the shared view-state — NOT hand-wired — so the
 * same descriptors keep driving the context menu and the keyboard dispatcher
 * (shortcuts unchanged). Every command stays reachable: fit/reset/datums as
 * icon buttons, everything else as a menu child with its own enabled state.
 */
import { commandsInGroup } from './commands/registry'
import type { Command, CommandActions } from './commands/types'
import { ICONS } from './commands/icons'
import { DropdownMenu, type MenuItem } from './ui/DropdownMenu'
import { toCommandContext, useViewState, type ViewStateStore } from './viewstate/store'
import { useSelectionState, type SelectionStore } from './selection/store'

export function Toolbar({
  store,
  selectionStore,
  actions,
}: {
  store: ViewStateStore
  selectionStore: SelectionStore
  actions: CommandActions
}) {
  const sel = useSelectionState(selectionStore)
  const ctx = toCommandContext(useViewState(store), {
    filter: sel.filter,
    hasSelection: sel.selected !== null,
  })
  const tip = (c: Command) => (c.shortcut ? `${c.label} (${c.shortcut.toUpperCase()})` : c.label)

  const iconButton = (c: Command) => (
    <button
      key={c.id}
      className={`tb-btn${c.iconKey ? '' : ' tb-text'}${c.isActive?.(ctx) ? ' on' : ''}`}
      type="button"
      disabled={!c.isEnabled(ctx)}
      title={tip(c)}
      aria-label={c.label}
      aria-pressed={c.kind === 'toggle' ? !!c.isActive?.(ctx) : undefined}
      onClick={() => c.run(actions, ctx)}
    >
      {c.iconKey ? ICONS[c.iconKey] : (c.shortLabel ?? c.label)}
    </button>
  )

  // A command group as menu items — each child keeps its OWN enabled state
  // and dispatches through its command (never re-derived in the renderer).
  const menuItems = (commands: Command[]): MenuItem[] =>
    commands.map((c) => ({
      key: c.id,
      label: c.shortcut ? `${c.label} (${c.shortcut.toUpperCase()})` : c.label,
      disabledReason: c.isEnabled(ctx) ? null : 'unavailable in the current state',
      current: !!c.isActive?.(ctx),
    }))
  const runById = (commands: Command[]) => (id: string) => {
    const c = commands.find((x) => x.id === id)
    if (c && c.isEnabled(ctx)) c.run(actions, ctx)
  }

  const display = commandsInGroup('display')
  const orientation = commandsInGroup('orientation')
  const selection = commandsInGroup('selection')
  const currentMode = display.find((c) => c.isActive?.(ctx))
  const anyRenderable = display.some((c) => c.isEnabled(ctx))

  return (
    <div className="toolbar" role="toolbar" aria-label="Display commands">
      <div className="tb-group">{commandsInGroup('view').map(iconButton)}</div>
      <span className="tb-sep" />
      <DropdownMenu
        label="Display style"
        currentValue={currentMode?.label}
        className="tb-dd"
        disabled={!anyRenderable}
        items={menuItems(display)}
        onSelect={runById(display)}
      >
        {ICONS['display-style']}
        <span className="tb-dd-lbl">{currentMode?.shortLabel ?? 'Style'}</span>
        <span className="tb-caret">▾</span>
      </DropdownMenu>
      <DropdownMenu
        label="Named views"
        className="tb-dd"
        disabled={!anyRenderable}
        items={menuItems(orientation)}
        onSelect={runById(orientation)}
      >
        {ICONS.views}
        <span className="tb-caret">▾</span>
      </DropdownMenu>
      <DropdownMenu
        label="Selection"
        className="tb-dd"
        items={menuItems(selection)}
        onSelect={runById(selection)}
      >
        {ICONS['sel-filter']}
        <span className="tb-caret">▾</span>
      </DropdownMenu>
      <span className="tb-sep" />
      <div className="tb-group">{commandsInGroup('scene').map(iconButton)}</div>
    </div>
  )
}
