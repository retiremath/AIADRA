/**
 * V-4 (arc 20260716-1, Codex1 B4) — the CONDENSED graphics toolbar contract:
 * icon buttons + three DropdownMenu dropdowns (display style / named views /
 * selection), Creo-benchmarked density. Every command stays reachable and
 * dispatches through its own taxonomy entry; children keep their own enabled
 * state; the display trigger carries the CURRENT mode in its accessible name.
 */
// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Toolbar } from './Toolbar'
import { COMMANDS, commandsInGroup } from './commands/registry'
import type { CommandActions } from './commands/types'
import { createViewStateStore, type ViewState } from './viewstate/store'
import { createSelectionStore } from './selection/store'

afterEach(cleanup)

const state = (over: Partial<ViewState> = {}): ViewState => ({
  mode: 'shading-edges',
  datumsVisible: true,
  hasCanonicalPart: true,
  hasReferenceGeometry: false,
  ...over,
})

function mount(over: Partial<ViewState> = {}) {
  const actions: CommandActions = {
    fit: vi.fn(),
    reset: vi.fn(),
    setMode: vi.fn(),
    toggleDatums: vi.fn(),
    standardView: vi.fn(),
    toggleFilterKind: vi.fn(),
    clearSelection: vi.fn(),
  }
  render(
    <Toolbar store={createViewStateStore(state(over))} selectionStore={createSelectionStore()} actions={actions} />,
  )
  return actions
}

describe('the condensed graphics toolbar (V-4)', () => {
  it('renders icon buttons + the three dropdowns; the display trigger names the CURRENT mode', () => {
    mount()
    expect(screen.getByRole('button', { name: 'Fit to view' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Reset view' })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Display style — Shading With Edges/ })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Named views' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Selection' })).toBeTruthy()
    const datums = screen.getByRole('button', { name: 'Datum planes' })
    expect(datums.getAttribute('aria-pressed')).toBe('true')
  })

  it('the display menu lists all five modes with the current marked; selecting dispatches', () => {
    const actions = mount()
    fireEvent.click(screen.getByRole('button', { name: /Display style/ }))
    const items = screen.getAllByRole('menuitem')
    expect(items).toHaveLength(5)
    expect(screen.getByText(/Shading With Edges/).className).toContain('current')
    fireEvent.click(screen.getByText(/Wireframe/))
    expect(actions.setMode).toHaveBeenCalledWith('wireframe')
  })

  it('the views menu lists all seven named views and dispatches standardView', () => {
    const actions = mount()
    fireEvent.click(screen.getByRole('button', { name: 'Named views' }))
    expect(screen.getAllByRole('menuitem')).toHaveLength(commandsInGroup('orientation').length)
    fireEvent.click(screen.getByText('Front'))
    expect(actions.standardView).toHaveBeenCalledWith('front')
  })

  it('selection children keep their OWN enabled state: clear is disabled with no selection', () => {
    const actions = mount()
    fireEvent.click(screen.getByRole('button', { name: 'Selection' }))
    const clear = screen.getByText('Clear selection')
    expect(clear.getAttribute('aria-disabled')).toBe('true')
    fireEvent.click(clear)
    expect(actions.clearSelection).not.toHaveBeenCalled()
    fireEvent.click(screen.getByText(/Select faces/))
    expect(actions.toggleFilterKind).toHaveBeenCalledWith('face')
  })

  it('no renderable scene: display/views triggers disable; datums stays available', () => {
    mount({ hasCanonicalPart: false })
    expect((screen.getByRole('button', { name: /Display style/ }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Named views' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Datum planes' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('toolbar addressability: every taxonomy command is reachable (button or menu child)', () => {
    mount()
    const reachable = new Set<string>()
    for (const c of [...commandsInGroup('view'), ...commandsInGroup('scene')]) reachable.add(c.id)
    for (const group of ['display', 'orientation', 'selection'] as const) {
      for (const c of commandsInGroup(group)) reachable.add(c.id)
    }
    reachable.add('operations.soon') // the reserved 6b placeholder — deliberately unrendered
    for (const c of COMMANDS) {
      expect(reachable.has(c.id), `command ${c.id} unreachable from the toolbar`).toBe(true)
    }
  })
})
