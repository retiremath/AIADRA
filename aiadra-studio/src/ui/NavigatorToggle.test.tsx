/**
 * The navigator toggle (Creo's bottom-left navigator button): a pure projection
 * of the `navigatorVisible` setting — pressed state, accessible name, and the
 * flip both ways. Where it sits (first in the status bar, both app states) is
 * the shell's decision, exercised by the desktop walk.
 */
// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { createSettingsRegistry } from '../settings/registry'
import { SettingsProvider } from '../settings/useSettings'
import { NavigatorToggle } from './NavigatorToggle'

afterEach(cleanup)

describe('the navigator toggle (Creo bottom-left navigator button)', () => {
  it('defaults to shown (pressed) and flips the persisted setting both ways', () => {
    const r = createSettingsRegistry()
    expect(r.get('navigatorVisible')).toBe(true)
    render(
      <SettingsProvider registry={r}>
        <NavigatorToggle />
      </SettingsProvider>,
    )
    const hide = screen.getByRole('button', { name: 'Hide the navigator' })
    expect(hide.getAttribute('aria-pressed')).toBe('true')
    expect(hide.className).toContain('on')

    fireEvent.click(hide)
    expect(r.get('navigatorVisible')).toBe(false)
    const show = screen.getByRole('button', { name: 'Show the navigator' })
    expect(show.getAttribute('aria-pressed')).toBe('false')
    expect(show.className).not.toContain('on')

    fireEvent.click(show)
    expect(r.get('navigatorVisible')).toBe(true)
    expect(screen.getByRole('button', { name: 'Hide the navigator' })).toBeTruthy()
  })

  it('follows an external change to the setting (one authority — the registry)', () => {
    const r = createSettingsRegistry()
    render(
      <SettingsProvider registry={r}>
        <NavigatorToggle />
      </SettingsProvider>,
    )
    act(() => r.set('navigatorVisible', false))
    expect(screen.getByRole('button', { name: 'Show the navigator' })).toBeTruthy()
  })
})
