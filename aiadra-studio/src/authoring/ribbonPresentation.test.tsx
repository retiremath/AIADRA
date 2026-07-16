/**
 * V-2 (arc 20260716-1, Codex1 B4) — the dense ribbon's executable contracts:
 * the addressability invariant (every command exactly once, direct or menu
 * child; no menu carries an undeclared member), slot integrity, the merged
 * icon map (the private-table drift dies here), the responsive fold, the
 * menu-state rules (a parent with disabled children ALWAYS opens), and the
 * clipping ban.
 */
// @vitest-environment jsdom
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ICONS } from '../commands/icons'
import { COMMANDS } from '../commands/registry'
import {
  RIBBON_COMMANDS,
  RIBBON_GROUP_ORDER,
  RIBBON_MENU_FAMILIES,
  visibleGroupCount,
  type RibbonInputs,
} from './ribbon'
import { groupCells, ModelRibbon } from './ModelRibbon'

afterEach(cleanup)

const inputs = (over: Partial<RibbonInputs> = {}): RibbonInputs => ({
  realLane: true,
  authoringGate: null,
  pc: { workspaceId: null, partNumber: null, generation: 0, inspection: { status: 'idle' }, selectorFacts: null },
  selection: null,
  ...over,
})

describe('B4 — the addressability invariant', () => {
  it('every one of the 38 command keys renders EXACTLY once: direct cell XOR menu child', () => {
    const direct = RIBBON_COMMANDS.filter((c) => c.presentation.slot)
    const menued = RIBBON_COMMANDS.filter((c) => c.presentation.menu)
    // the XOR: slot and menu never coexist, and neither is absent
    for (const c of RIBBON_COMMANDS) {
      expect(Boolean(c.presentation.slot) !== Boolean(c.presentation.menu), c.key).toBe(true)
    }
    const rendered = [...direct.map((c) => c.key), ...menued.map((c) => c.key)].sort()
    expect(rendered).toEqual(RIBBON_COMMANDS.map((c) => c.key).sort())
    expect(new Set(rendered).size).toBe(38)
  })

  it('no menu carries an undeclared member; families are non-empty and group-consistent', () => {
    const familyIds = new Set(RIBBON_MENU_FAMILIES.map((f) => f.id))
    for (const c of RIBBON_COMMANDS.filter((c) => c.presentation.menu)) {
      expect(familyIds.has(c.presentation.menu!.family), c.key).toBe(true)
      const family = RIBBON_MENU_FAMILIES.find((f) => f.id === c.presentation.menu!.family)!
      expect(c.group, `${c.key} must live in its family's group`).toBe(family.group)
    }
    for (const f of RIBBON_MENU_FAMILIES) {
      const members = RIBBON_COMMANDS.filter((c) => c.presentation.menu?.family === f.id)
      expect(members.length, f.id).toBeGreaterThan(0)
      // member order is total and collision-free within the family
      const orders = members.map((m) => m.presentation.menu!.order).sort((a, b) => a - b)
      expect(new Set(orders).size).toBe(orders.length)
    }
  })

  it('slot integrity: unique cells; anchors own their whole column at row 0; smalls stack ≤3', () => {
    for (const group of RIBBON_GROUP_ORDER) {
      const columns = groupCells(group)
      const seen = new Set<string>()
      for (const column of columns) {
        for (const cell of column) {
          const key = `${cell.column}.${cell.row}`
          expect(seen.has(key), `${group} slot ${key} collides`).toBe(false)
          seen.add(key)
          expect(cell.row).toBeGreaterThanOrEqual(0)
          expect(cell.row).toBeLessThanOrEqual(2)
        }
        const hasAnchor = column.some((c) => c.size === 'anchor')
        if (hasAnchor) {
          expect(column.length, `${group}: an anchor owns its column alone`).toBe(1)
          expect(column[0].row).toBe(0)
        } else {
          expect(column.length).toBeLessThanOrEqual(3)
        }
      }
    }
  })
})

describe('B4 — the merged icon map (the private second table is dead)', () => {
  it('every taxonomy icon, family icon, structural icon, and toolbar iconKey resolves', () => {
    const wanted = new Set<string>([
      ...RIBBON_COMMANDS.map((c) => c.presentation.icon),
      ...RIBBON_MENU_FAMILIES.map((f) => f.icon),
      'overflow',
      ...COMMANDS.flatMap((c) => (c.iconKey ? [c.iconKey] : [])),
    ])
    for (const key of wanted) {
      expect(ICONS[key], `icon '${key}' missing from the merged map`).toBeTruthy()
    }
  })
})

describe('B4 — the responsive fold (pure)', () => {
  const widths = RIBBON_GROUP_ORDER.map(() => 150) // 10 groups × 150 = 1500

  it('the 1600 benchmark width renders every group directly', () => {
    expect(visibleGroupCount(1600 - 100, widths, 40)).toBe(10)
  })

  it('below the fit point, trailing groups fold as a suffix — never below one direct group', () => {
    const at1200 = visibleGroupCount(1200 - 100, widths, 40)
    expect(at1200).toBeLessThan(10)
    expect(at1200).toBeGreaterThanOrEqual(1)
    expect(visibleGroupCount(120, widths, 40)).toBe(1) // clamp: one group always direct
    // monotone: narrower never shows MORE groups
    let prev = 10
    for (const w of [1500, 1200, 900, 600, 300, 100]) {
      const n = visibleGroupCount(w, widths, 40)
      expect(n).toBeLessThanOrEqual(prev)
      prev = n
    }
  })

  it('unmeasured widths (jsdom / pre-measure) fold nothing', () => {
    expect(visibleGroupCount(500, RIBBON_GROUP_ORDER.map(() => 0), 40)).toBe(10)
  })
})

describe('B4 — the rendered dense ribbon (jsdom)', () => {
  it('renders all ten benchmark groups and the family trigger; anchors and smalls are classed', () => {
    render(<ModelRibbon inputs={inputs()} onStart={vi.fn()} />)
    const titles = [...document.querySelectorAll('.ribbon-group-title')].map((el) => el.textContent)
    expect(titles).toEqual([...RIBBON_GROUP_ORDER])
    expect(document.querySelectorAll('.rb-btn.rb-anchor').length).toBeGreaterThan(0)
    expect(document.querySelectorAll('.rb-btn.rb-small').length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: /Editing — More/ })).toBeTruthy()
  })

  it('a family with ALL-disabled children still OPENS; children carry their own reason', () => {
    const onStart = vi.fn()
    render(<ModelRibbon inputs={inputs()} onStart={onStart} />)
    fireEvent.click(screen.getByRole('button', { name: /Editing — More/ }))
    const menu = screen.getByRole('menu')
    expect(menu).toBeTruthy()
    const solidify = screen.getByText('Solidify')
    expect(solidify.getAttribute('aria-disabled')).toBe('true')
    expect(solidify.getAttribute('title')).toMatch(/editing strand/)
    fireEvent.click(solidify)
    expect(onStart).not.toHaveBeenCalled()
  })

  it('folded groups land in the » overflow with group-prefixed tri-state items', () => {
    render(<ModelRibbon inputs={inputs()} onStart={vi.fn()} debugFoldCount={2} />)
    // the two trailing groups are gone from the direct strip…
    expect(screen.queryByText('Surfaces')).toBeNull()
    expect(screen.queryByText('Model Intent')).toBeNull()
    // …and every one of their commands is reachable through »
    fireEvent.click(screen.getByRole('button', { name: 'More ribbon groups' }))
    for (const label of ['Surfaces: Boundary Blend', 'Surfaces: Fill', 'Surfaces: Style', 'Surfaces: Freestyle', 'Model Intent: Component Interface']) {
      expect(screen.getByText(label)).toBeTruthy()
    }
  })

  it('working commands dispatch from a small cell (dev lane: Sketch works)', () => {
    const onStart = vi.fn()
    render(<ModelRibbon inputs={inputs({ realLane: false })} onStart={onStart} />)
    fireEvent.click(screen.getByRole('button', { name: 'Sketch' }))
    expect(onStart).toHaveBeenCalledWith('sketch')
  })
})

describe('B4 — the clipping ban', () => {
  it('the ribbon styles never use overflow: hidden (folding, not clipping)', () => {
    const css = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', 'index.css'), 'utf-8')
    const start = css.indexOf('/* Model ribbon')
    const end = css.indexOf('/* Model tree')
    expect(start).toBeGreaterThan(-1)
    expect(end).toBeGreaterThan(start)
    const ribbonBlock = css.slice(start, end).replace(/\/\*[\s\S]*?\*\//g, '') // rules only, not prose
    expect(ribbonBlock).not.toMatch(/overflow\s*:\s*hidden/)
    // and the banned opacity trap stays out of the disabled ribbon styles (B2)
    expect(ribbonBlock).not.toMatch(/disabled[^{]*\{[^}]*opacity/)
  })
})
