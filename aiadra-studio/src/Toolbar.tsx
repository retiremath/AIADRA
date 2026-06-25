/**
 * The compact CAD toolbar (arc 20260619-2 / 6b; ADR/0033 D9). Rendered FROM the
 * command taxonomy + the shared view-state — NOT hand-wired — so the same
 * descriptors drive the toolbar, the context menu, and (later) a ribbon. View
 * actions + grid render as icon buttons; the display modes render as a
 * segmented radio control. Active/disabled/tooltip(+shortcut) all come from the
 * command predicates against the live context.
 */
import { commandsInGroup } from './commands/registry'
import type { Command, CommandActions } from './commands/types'
import { ICONS } from './commands/icons'
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

  return (
    <div className="toolbar" role="toolbar" aria-label="Display commands">
      <div className="tb-group">{commandsInGroup('view').map(iconButton)}</div>
      <span className="tb-sep" />
      <div className="tb-group tb-segmented" role="group" aria-label="Display mode">
        {commandsInGroup('display').map((c) => (
          <button
            key={c.id}
            className={`tb-seg${c.isActive?.(ctx) ? ' on' : ''}`}
            type="button"
            disabled={!c.isEnabled(ctx)}
            title={tip(c)}
            aria-pressed={!!c.isActive?.(ctx)}
            onClick={() => c.run(actions, ctx)}
          >
            {c.shortLabel ?? c.label}
          </button>
        ))}
      </div>
      <span className="tb-sep" />
      <div className="tb-group" role="group" aria-label="Standard views">
        {commandsInGroup('orientation').map((c) => (
          <button
            key={c.id}
            className="tb-btn tb-text"
            type="button"
            disabled={!c.isEnabled(ctx)}
            title={c.label}
            aria-label={c.label}
            onClick={() => c.run(actions, ctx)}
          >
            {c.shortLabel ?? c.label}
          </button>
        ))}
      </div>
      <span className="tb-sep" />
      <div className="tb-group" role="group" aria-label="Selection">
        {commandsInGroup('selection').map(iconButton)}
      </div>
      <span className="tb-sep" />
      <div className="tb-group">{commandsInGroup('scene').map(iconButton)}</div>
    </div>
  )
}
