/**
 * V-1: the pinned menu interaction contract (Codex1 B4.5) — aria semantics,
 * roving keyboard focus, activation, Escape/outside-click + focus restore,
 * disabled-item behavior, click-not-hover.
 */
// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DropdownMenu, type MenuItem } from './DropdownMenu'

afterEach(cleanup)

const ITEMS: MenuItem[] = [
  { key: 'a', label: 'Alpha' },
  { key: 'b', label: 'Bravo', disabledReason: 'not ready' },
  { key: 'c', label: 'Charlie', current: true },
]

function mount(onSelect = vi.fn()) {
  render(
    <DropdownMenu label="Display style" currentValue="Charlie" items={ITEMS} onSelect={onSelect}>
      DS
    </DropdownMenu>,
  )
  return { onSelect, trigger: screen.getByRole('button', { name: /Display style — Charlie/ }) }
}

describe('DropdownMenu — the shared contract', () => {
  it('trigger carries aria-haspopup/expanded + the current value in its name', () => {
    const { trigger } = mount()
    expect(trigger.getAttribute('aria-haspopup')).toBe('menu')
    expect(trigger.getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(trigger)
    expect(trigger.getAttribute('aria-expanded')).toBe('true')
    expect(screen.getByRole('menu')).toBeTruthy()
  })

  it('opens by CLICK (never hover): hover alone shows no menu', () => {
    const { trigger } = mount()
    fireEvent.mouseOver(trigger)
    expect(screen.queryByRole('menu')).toBeNull()
  })

  it('roving arrow-key focus SKIPS disabled items; Enter activates; focus restores', () => {
    const { onSelect, trigger } = mount()
    fireEvent.click(trigger)
    const menu = screen.getByRole('menu')
    // first enabled item (Alpha) holds roving focus
    expect(document.activeElement?.textContent).toContain('Alpha')
    fireEvent.keyDown(menu, { key: 'ArrowDown' }) // skips disabled Bravo
    expect(document.activeElement?.textContent).toContain('Charlie')
    fireEvent.keyDown(menu, { key: 'Enter' })
    expect(onSelect).toHaveBeenCalledWith('c')
    expect(screen.queryByRole('menu')).toBeNull()
    expect(document.activeElement).toBe(trigger) // focus restored
  })

  it('disabled items carry aria-disabled + the reason and never activate', () => {
    const { onSelect, trigger } = mount()
    fireEvent.click(trigger)
    const bravo = screen.getByText(/Bravo/)
    expect(bravo.getAttribute('aria-disabled')).toBe('true')
    expect(bravo.getAttribute('title')).toBe('not ready')
    fireEvent.click(bravo)
    expect(onSelect).not.toHaveBeenCalled()
  })

  it('Escape closes and restores trigger focus; outside pointer-down closes', () => {
    const { trigger } = mount()
    fireEvent.click(trigger)
    fireEvent.keyDown(screen.getByRole('menu'), { key: 'Escape' })
    expect(screen.queryByRole('menu')).toBeNull()
    expect(document.activeElement).toBe(trigger)
    fireEvent.click(trigger)
    expect(screen.getByRole('menu')).toBeTruthy()
    fireEvent.pointerDown(document.body)
    expect(screen.queryByRole('menu')).toBeNull()
  })

  it('marks the current option', () => {
    const { trigger } = mount()
    fireEvent.click(trigger)
    expect(screen.getByText(/Charlie/).className).toContain('current')
  })
})
