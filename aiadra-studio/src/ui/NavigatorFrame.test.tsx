/**
 * The navigator frame (Creo navigator; shell-1 S1-08 amended + S1-15): ONE
 * resizable, dismissable column for both app states. Pins: the sash clamps to
 * the DESCRIPTOR bounds (no literal twin), a drag writes the shared setting and
 * stops at release, hidden renders nothing (no zero-width ghost, no sash), and
 * the status-bar toggle brings it back.
 */
// @vitest-environment jsdom
import type { ReactNode } from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeAll, describe, expect, it } from 'vitest'
import { DESCRIPTOR_BY_KEY } from '../settings/descriptors'
import { createSettingsRegistry, type SettingsRegistry } from '../settings/registry'
import { SettingsProvider } from '../settings/useSettings'
import { NavigatorFrame } from './NavigatorFrame'
import { clampNavigatorWidth } from './navigatorWidth'
import { NavigatorToggle } from './NavigatorToggle'

afterEach(cleanup)
beforeAll(() => {
  // jsdom ships no PointerEvent constructor; the frame's listeners only read
  // the MouseEvent coordinate shape.
  const w = window as unknown as Record<string, unknown>
  if (typeof w.PointerEvent === 'undefined') w.PointerEvent = MouseEvent
})

function mount(ui: ReactNode, registry: SettingsRegistry = createSettingsRegistry()): SettingsRegistry {
  render(<SettingsProvider registry={registry}>{ui}</SettingsProvider>)
  return registry
}

const bounds = DESCRIPTOR_BY_KEY.navigatorWidth

describe('the navigator frame (Creo navigator — one column, both app states)', () => {
  it('clamps to the navigatorWidth descriptor bounds — one authority, no literal twin', () => {
    expect(bounds.min).toBeDefined()
    expect(bounds.max).toBeDefined()
    expect(clampNavigatorWidth((bounds.min as number) - 500)).toBe(bounds.min)
    expect(clampNavigatorWidth((bounds.max as number) + 500)).toBe(bounds.max)
    expect(clampNavigatorWidth(300.4)).toBe(300)
  })

  it('renders the hosted aside at the setting width, with the sash', () => {
    const r = mount(
      <NavigatorFrame className="home-left">
        <span>Workspaces</span>
      </NavigatorFrame>,
    )
    const frame = screen.getByTestId('navigator-frame')
    expect(frame.style.width).toBe(`${r.get('navigatorWidth')}px`)
    expect(frame.querySelector('aside.home-left')?.textContent).toBe('Workspaces')
    expect(screen.getByRole('separator', { name: 'Resize the navigator' })).toBeTruthy()
  })

  it('dragging the sash writes the shared setting, clamped, and stops at release', () => {
    const r = mount(<NavigatorFrame className="sidebar">tree</NavigatorFrame>)
    const start = r.get('navigatorWidth') as number
    const grip = screen.getByRole('separator', { name: 'Resize the navigator' })
    fireEvent.pointerDown(grip, { clientX: 400 })
    fireEvent.pointerMove(window, { clientX: 460 })
    expect(r.get('navigatorWidth')).toBe(start + 60)
    expect(screen.getByTestId('navigator-frame').style.width).toBe(`${start + 60}px`)
    fireEvent.pointerMove(window, { clientX: -5000 })
    expect(r.get('navigatorWidth')).toBe(bounds.min)
    fireEvent.pointerUp(window)
    fireEvent.pointerMove(window, { clientX: 900 }) // released — no effect
    expect(r.get('navigatorWidth')).toBe(bounds.min)
  })

  it('hidden renders NOTHING (no zero-width ghost, no sash); the toggle restores it', () => {
    const r = createSettingsRegistry()
    r.set('navigatorVisible', false)
    mount(
      <>
        <NavigatorFrame className="sidebar">tree</NavigatorFrame>
        <NavigatorToggle />
      </>,
      r,
    )
    expect(screen.queryByTestId('navigator-frame')).toBeNull()
    expect(screen.queryByRole('separator')).toBeNull()
    expect(screen.queryByText('tree')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Show the navigator' }))
    expect(r.get('navigatorVisible')).toBe(true)
    expect(screen.getByTestId('navigator-frame')).toBeTruthy()
    expect(screen.getByText('tree')).toBeTruthy()
  })
})
