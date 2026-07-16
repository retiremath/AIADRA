/**
 * Codex2 B1 — the File menu carries the ONE shared menu interaction contract
 * (it is DropdownMenu now, not a bespoke second menu): ARIA state, roving
 * arrow navigation skipping disabled, disabled reasons as tooltips, Escape /
 * outside-click, activation, and trigger-focus restoration.
 */
// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { FileMenu, type FileMenuItem } from './FileMenu'

afterEach(cleanup)

function mount() {
  const onNew = vi.fn()
  const items: FileMenuItem[] = [
    { label: 'New…', enabled: true, title: 'Create a new object (Part, …)', onClick: onNew },
    { label: 'Open Workspace…', enabled: false, title: 'Available in the desktop app' },
    { label: 'Close', enabled: true, title: 'Close the model and return Home', onClick: vi.fn(), sep: true },
    { label: 'Check In', enabled: false, title: 'Performs the git-backed check-in — arrives with the PDM slice (ADR/0040 D7)', sep: true },
  ]
  render(<FileMenu items={items} />)
  return { onNew, trigger: screen.getByRole('button', { name: 'File' }) }
}

describe('the File menu on the shared primitive (Codex2 B1)', () => {
  it('carries aria-haspopup/expanded and opens by click', () => {
    const { trigger } = mount()
    expect(trigger.getAttribute('aria-haspopup')).toBe('menu')
    expect(trigger.getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(trigger)
    expect(trigger.getAttribute('aria-expanded')).toBe('true')
    expect(screen.getByRole('menu')).toBeTruthy()
  })

  it('roving arrow focus SKIPS disabled items; separators are styling, not stops', () => {
    const { trigger } = mount()
    fireEvent.click(trigger)
    const menu = screen.getByRole('menu')
    expect(document.activeElement?.textContent).toBe('New…') // first enabled
    fireEvent.keyDown(menu, { key: 'ArrowDown' }) // skips disabled Open Workspace…
    expect(document.activeElement?.textContent).toBe('Close')
    fireEvent.keyDown(menu, { key: 'ArrowDown' }) // skips disabled Check In, wraps
    expect(document.activeElement?.textContent).toBe('New…')
    expect(screen.getByText('Close').className).toContain('sep')
  })

  it('disabled items carry aria-disabled + their reason and never activate', () => {
    const { trigger } = mount()
    fireEvent.click(trigger)
    const open = screen.getByText('Open Workspace…')
    expect(open.getAttribute('aria-disabled')).toBe('true')
    expect(open.getAttribute('title')).toBe('Available in the desktop app')
    fireEvent.click(open)
    expect(screen.queryByRole('menu')).toBeTruthy() // still open, nothing ran
  })

  it('POINTER activation runs the handler, closes, and restores trigger focus', () => {
    const { onNew, trigger } = mount()
    fireEvent.click(trigger)
    fireEvent.click(screen.getByText('New…'))
    expect(onNew).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('menu')).toBeNull()
    expect(document.activeElement).toBe(trigger)
  })

  it('Enter activation and Escape both restore trigger focus; outside pointer-down closes without stealing', () => {
    const { onNew, trigger } = mount()
    fireEvent.click(trigger)
    fireEvent.keyDown(screen.getByRole('menu'), { key: 'Enter' }) // New… holds focus
    expect(onNew).toHaveBeenCalledTimes(1)
    expect(document.activeElement).toBe(trigger)
    fireEvent.click(trigger)
    fireEvent.keyDown(screen.getByRole('menu'), { key: 'Escape' })
    expect(screen.queryByRole('menu')).toBeNull()
    expect(document.activeElement).toBe(trigger)
    fireEvent.click(trigger)
    fireEvent.pointerDown(document.body)
    expect(screen.queryByRole('menu')).toBeNull()
  })

  it('enabled items keep their descriptive tooltips', () => {
    const { trigger } = mount()
    fireEvent.click(trigger)
    expect(screen.getByText('New…').getAttribute('title')).toBe('Create a new object (Part, …)')
  })
})
