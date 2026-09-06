/**
 * The DENSE Model ribbon (arc 20260711-11 slice A → 20260715-1 D-R1 →
 * 20260716-1 V-2, Codex1 B4) — the Creo 10 Model tab, benchmarked never
 * cloned. The whole vocabulary renders from the ONE data-driven taxonomy
 * (`ribbon.ts`), now packed Creo-style from the typed presentation metadata:
 * anchors are tall one-per-column buttons; smalls stack up to three per
 * column; declared menu families render as `DropdownMenu` triggers whose
 * children keep their OWN tri-state + derived-reason tooltip (a parent with
 * mixed children ALWAYS opens — never a synthesized collapsed disabled
 * state). Below the supported minimum width, trailing groups fold — as a
 * suffix — into the explicit `»` overflow menu built on the same primitive;
 * clipping is banned. Icons come from the ONE merged map (`commands/icons`).
 */
import { useLayoutEffect, useRef, useState } from 'react'
import { ICONS } from '../commands/icons'
import { DropdownMenu, type MenuItem } from '../ui/DropdownMenu'
import {
  deriveCommandState,
  RIBBON_COMMANDS,
  RIBBON_GROUP_ORDER,
  RIBBON_MENU_FAMILIES,
  visibleGroupCount,
  type CommandState,
  type RibbonCommand,
  type RibbonGroup,
  type RibbonInputs,
  type RibbonMenuFamily,
} from './ribbon'

/** One column cell: a direct command or a family trigger. */
type Cell =
  | { kind: 'command'; command: RibbonCommand; column: number; row: number; size: 'anchor' | 'small' }
  | { kind: 'family'; family: RibbonMenuFamily; column: number; row: number; size: 'small' }

/** The rendered plan of one group, derived purely from the metadata. */
export function groupCells(group: RibbonGroup): Cell[][] {
  const cells: Cell[] = [
    ...RIBBON_COMMANDS.filter((c) => c.group === group && c.presentation.slot).map((c): Cell => ({
      kind: 'command', command: c,
      column: c.presentation.slot!.column, row: c.presentation.slot!.row, size: c.presentation.size,
    })),
    ...RIBBON_MENU_FAMILIES.filter((f) => f.group === group).map((f): Cell => ({
      kind: 'family', family: f, column: f.slot.column, row: f.slot.row, size: f.size,
    })),
  ]
  const columns = new Map<number, Cell[]>()
  for (const cell of cells) {
    const col = columns.get(cell.column) ?? []
    col.push(cell)
    columns.set(cell.column, col)
  }
  return [...columns.entries()]
    .sort(([a], [b]) => a - b)
    .map(([, col]) => col.sort((a, b) => a.row - b.row))
}

function familyMembers(id: RibbonMenuFamily['id']): RibbonCommand[] {
  return RIBBON_COMMANDS.filter((c) => c.presentation.menu?.family === id).sort(
    (a, b) => a.presentation.menu!.order - b.presentation.menu!.order,
  )
}

const stateTitle = (c: RibbonCommand, st: CommandState): string =>
  st.state === 'working' ? `${c.label} — ${c.hint ?? 'start'}` : st.reason

function menuItemFor(c: RibbonCommand, inputs: RibbonInputs, labelPrefix = ''): MenuItem {
  const st = c.derive(inputs)
  return {
    key: c.key,
    label: `${labelPrefix}${c.label}`,
    disabledReason: st.state === 'working' ? null : st.reason,
  }
}

function CommandButton({ c, inputs, onStart }: { c: RibbonCommand; inputs: RibbonInputs; onStart: (key: string) => void }) {
  const st = c.derive(inputs)
  const disabled = st.state !== 'working'
  return (
    <button
      type="button"
      className={`rb-btn rb-${c.presentation.size}${st.state === 'roadmap-disabled' ? ' rb-roadmap' : ''}`}
      disabled={disabled}
      title={stateTitle(c, st)}
      data-state={st.state}
      onClick={() => !disabled && onStart(c.key)}
    >
      <span className="rb-ico">{ICONS[c.presentation.icon]}</span>
      <span className="rb-lbl">{c.label}</span>
    </button>
  )
}

export function ModelRibbon({
  inputs,
  onStart,
  debugFoldCount,
}: {
  /** The taxonomy inputs (lane, gate, Part context, selection) — derived once
   *  by the Workbench per render. */
  inputs: RibbonInputs
  /** Dispatch a WORKING command by its taxonomy key. */
  onStart: (key: string) => void
  /** TEST ONLY: force this many trailing groups into the » overflow. */
  debugFoldCount?: number
}) {
  const rootRef = useRef<HTMLDivElement>(null)
  // Last KNOWN width per group — folded groups leave the DOM, so widths are
  // cached from renders where they were present (jsdom measures 0 → no fold).
  const widthsRef = useRef<Map<RibbonGroup, number>>(new Map())
  const [visible, setVisible] = useState(RIBBON_GROUP_ORDER.length)

  useLayoutEffect(() => {
    const root = rootRef.current
    if (!root || debugFoldCount !== undefined) return
    const remeasure = () => {
      for (const el of root.querySelectorAll<HTMLElement>('[data-ribbon-group]')) {
        const w = el.offsetWidth
        if (w > 0) widthsRef.current.set(el.dataset.ribbonGroup as RibbonGroup, w)
      }
      const widths = RIBBON_GROUP_ORDER.map((g) => widthsRef.current.get(g) ?? 0)
      const available = root.clientWidth - 40 // the » trigger's reserve
      setVisible(visibleGroupCount(available, widths, 40))
    }
    remeasure()
    if (typeof ResizeObserver === 'undefined') return // jsdom: no live re-measure
    const ro = new ResizeObserver(remeasure)
    ro.observe(root)
    return () => ro.disconnect()
  }, [debugFoldCount])

  const visibleCount = debugFoldCount !== undefined
    ? Math.max(1, RIBBON_GROUP_ORDER.length - debugFoldCount)
    : visible
  const directGroups = RIBBON_GROUP_ORDER.slice(0, visibleCount)
  const foldedGroups = RIBBON_GROUP_ORDER.slice(visibleCount)

  // Overflow items: every command of every folded group — direct cells AND
  // family members — stays reachable at any width (runtime addressability).
  const overflowItems: MenuItem[] = foldedGroups.flatMap((group) =>
    RIBBON_COMMANDS.filter((c) => c.group === group).map((c) => menuItemFor(c, inputs, `${group}: `)),
  )

  return (
    <div ref={rootRef} className="ribbon" role="toolbar" aria-label="Model ribbon">
      {directGroups.map((group) => {
        const columns = groupCells(group)
        if (columns.length === 0) return null
        return (
          <div key={group} className="ribbon-group" data-ribbon-group={group}>
            <div className="ribbon-btns">
              {columns.map((column, ci) => (
                <div key={ci} className="rb-col">
                  {column.map((cell) =>
                    cell.kind === 'command' ? (
                      <CommandButton key={cell.command.key} c={cell.command} inputs={inputs} onStart={onStart} />
                    ) : (
                      <DropdownMenu
                        key={cell.family.id}
                        label={`${cell.family.group} — ${cell.family.label}`}
                        className="rb-family"
                        items={familyMembers(cell.family.id).map((c) => menuItemFor(c, inputs))}
                        onSelect={onStart}
                      >
                        <span className="rb-ico">{ICONS[cell.family.icon]}</span>
                        <span className="rb-lbl">{cell.family.label}</span>
                      </DropdownMenu>
                    ),
                  )}
                </div>
              ))}
            </div>
            <div className="ribbon-group-title">{group}</div>
          </div>
        )
      })}
      {foldedGroups.length > 0 && (
        <DropdownMenu label="More ribbon groups" className="rb-overflow" items={overflowItems} onSelect={onStart}>
          <span className="rb-ico">{ICONS.overflow}</span>
        </DropdownMenu>
      )}
    </div>
  )
}

export { deriveCommandState }
