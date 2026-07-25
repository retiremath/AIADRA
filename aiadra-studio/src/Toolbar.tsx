/**
 * The CONDENSED in-graphics toolbar (arc 20260619-2 / 6b → 20260716-1 V-4,
 * Codex1 B4 → shell pass 1) — Creo-benchmarked density: icon buttons + FOUR
 * dropdowns on the shared `DropdownMenu` primitive (display style · named
 * views · selection · datum display), rendered FROM the command taxonomy +
 * the shared view-state — NOT hand-wired — so the same descriptors keep
 * driving the context menu and the keyboard dispatcher.
 *
 * Shell pass 1 adds the Creo CHROME behaviors: the bar is MOVABLE (top /
 * bottom of the graphics area) and DISMISSABLE — right-click the bar for the
 * position menu; when hidden, a small edge handle restores it. Placement is a
 * TYPED SETTING (persisted), never ad-hoc state.
 */
import { useEffect, useState } from 'react'
import { commandsInGroup } from './commands/registry'
import type { Command, CommandActions } from './commands/types'
import { ICONS } from './commands/icons'
import { DropdownMenu, type MenuItem } from './ui/DropdownMenu'
import { useSetting } from './settings/useSettings'
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
  const [position, setPosition] = useSetting('graphicsToolbarPosition')
  const [ctxMenu, setCtxMenu] = useState(false)
  useEffect(() => {
    if (!ctxMenu) return
    const close = () => setCtxMenu(false)
    window.addEventListener('pointerdown', close)
    return () => window.removeEventListener('pointerdown', close)
  }, [ctxMenu])

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
  // A command's declared `disabledReason` (roadmap honesty) wins over the
  // generic state copy.
  const menuItems = (commands: Command[]): MenuItem[] =>
    commands.map((c) => ({
      key: c.id,
      label: c.shortcut ? `${c.label} (${c.shortcut.toUpperCase()})` : c.label,
      disabledReason: c.isEnabled(ctx)
        ? null
        : (c.disabledReason ?? 'unavailable in the current state'),
      current: !!c.isActive?.(ctx),
    }))
  const runById = (commands: Command[]) => (id: string) => {
    const c = commands.find((x) => x.id === id)
    if (c && c.isEnabled(ctx)) c.run(actions, ctx)
  }

  const display = commandsInGroup('display')
  const orientation = commandsInGroup('orientation')
  const selection = commandsInGroup('selection')
  const scene = commandsInGroup('scene')
  const currentMode = display.find((c) => c.isActive?.(ctx))
  const anyRenderable = display.some((c) => c.isEnabled(ctx))

  // Dismissed: a small, always-discoverable restore handle (the user must
  // never need a buried setting to get the bar back — Petre's UX rule).
  if (position === 'hidden') {
    return (
      <button
        type="button"
        className="tb-restore"
        title="Show the graphics toolbar"
        aria-label="Show the graphics toolbar"
        onClick={() => setPosition('top')}
      >
        ▾
      </button>
    )
  }

  const positionItems: MenuItem[] = [
    { key: 'top', label: 'Top', current: position === 'top' },
    { key: 'bottom', label: 'Bottom', current: position === 'bottom' },
    { key: 'hidden', label: 'Hide toolbar', sepBefore: true },
  ]

  return (
    <div
      className={`toolbar pos-${position}`}
      role="toolbar"
      aria-label="Display commands"
      onContextMenu={(e) => {
        e.preventDefault()
        setCtxMenu(true)
      }}
    >
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
      {/* The datum-display dropdown (Creo's checkbox filter list): the master
          toggle + the per-kind filters, all taxonomy rows. */}
      <DropdownMenu
        label="Datum display"
        className="tb-dd"
        items={menuItems(scene)}
        onSelect={runById(scene)}
      >
        {ICONS.datums}
        <span className="tb-caret">▾</span>
      </DropdownMenu>
      {ctxMenu && (
        <ul className="tb-ctx dd-menu" role="menu" aria-label="Toolbar position">
          {positionItems.map((it) => (
            <li
              key={it.key}
              role="menuitem"
              tabIndex={-1}
              className={`dd-item${it.current ? ' current' : ''}${it.sepBefore ? ' sep' : ''}`}
              onPointerDown={(e) => e.stopPropagation()}
              onClick={() => {
                setPosition(it.key)
                setCtxMenu(false)
              }}
            >
              {it.current ? '✓ ' : ''}
              {it.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
