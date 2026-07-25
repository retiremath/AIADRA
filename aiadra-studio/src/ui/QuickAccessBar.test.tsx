/**
 * The Quick Access Toolbar (Creo QAT benchmark; shell pass 1): pinned
 * commands from typed settings, the customize dropdown on the ONE shared
 * DropdownMenu, gates shared with the File menu, persistence through the
 * settings registry (never ad-hoc local state).
 */
// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { QuickAccessBar, QAT_CATALOGUE, type QatCommand } from './QuickAccessBar'
import { SettingsProvider } from '../settings/useSettings'
import { createSettingsRegistry } from '../settings/registry'
import { isKnownSetting } from '../settings/descriptors'

afterEach(cleanup)

function mount(overrides: Partial<Record<QatCommand['key'], Partial<QatCommand>>> = {}) {
  const registry = createSettingsRegistry()
  const clicks: Record<string, ReturnType<typeof vi.fn>> = {}
  const commands: QatCommand[] = QAT_CATALOGUE.map((c) => {
    clicks[c.key] = vi.fn()
    return {
      key: c.key,
      disabledReason: null,
      title: `do ${c.key}`,
      onClick: clicks[c.key],
      ...overrides[c.key],
    }
  })
  render(
    <SettingsProvider registry={registry}>
      <QuickAccessBar commands={commands} />
    </SettingsProvider>,
  )
  return { registry, clicks }
}

const customizeTrigger = () =>
  screen.getByRole('button', { name: /Customize Quick Access Toolbar/ })

describe('the Quick Access Toolbar (Creo QAT benchmark)', () => {
  it('every catalogue row maps to a KNOWN setting (schema-as-data parity)', () => {
    for (const c of QAT_CATALOGUE) expect(isKnownSetting(c.setting), c.setting).toBe(true)
    expect(isKnownSetting('qatBelowRibbon')).toBe(true)
  })

  it('default pins mirror Creo out-of-box: New + Open visible, Import/Close hidden', () => {
    mount()
    expect(screen.getByRole('button', { name: 'New…' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Open Workspace…' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Import reference geometry…' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Close' })).toBeNull()
  })

  it('an enabled pin dispatches its command; a gated pin is disabled with the REASON as tooltip', () => {
    const { clicks } = mount({
      open: { disabledReason: 'Available in the desktop app' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'New…' }))
    expect(clicks.new).toHaveBeenCalledTimes(1)
    const open = screen.getByRole('button', { name: 'Open Workspace…' }) as HTMLButtonElement
    expect(open.disabled).toBe(true)
    expect(open.title).toBe('Available in the desktop app')
    fireEvent.click(open)
    expect(clicks.open).not.toHaveBeenCalled()
  })

  it('customize: checking a hidden command SHOWS it and persists through the registry', () => {
    const { registry } = mount()
    fireEvent.click(customizeTrigger())
    fireEvent.click(screen.getByRole('menuitem', { name: 'Import reference geometry…' }))
    expect(registry.get('qatShowImport')).toBe(true)
    expect(screen.getByRole('button', { name: 'Import reference geometry…' })).toBeTruthy()
    // and unchecking a default pin hides it (its menu name carries the ✓ mark)
    fireEvent.click(customizeTrigger())
    fireEvent.click(screen.getByRole('menuitem', { name: /New…$/ }))
    expect(registry.get('qatShowNew')).toBe(false)
    expect(screen.queryByRole('button', { name: 'New…' })).toBeNull()
  })

  it('customize marks currently-pinned commands as current (the ✓ affordance)', () => {
    mount()
    fireEvent.click(customizeTrigger())
    const item = screen.getByRole('menuitem', { name: /New…/ })
    expect(item.className).toContain('current')
    expect(screen.getByRole('menuitem', { name: /Import reference geometry…/ }).className).not.toContain(
      'current',
    )
  })

  it('"Show Below the Ribbon" flips the qatBelowRibbon setting (placement is the shell’s job)', () => {
    const { registry } = mount()
    expect(registry.get('qatBelowRibbon')).toBe(false)
    fireEvent.click(customizeTrigger())
    fireEvent.click(screen.getByRole('menuitem', { name: 'Show Below the Ribbon' }))
    expect(registry.get('qatBelowRibbon')).toBe(true)
  })

  it('"More Commands…" is roadmap-disabled with a named reason (three-state honesty)', () => {
    mount()
    fireEvent.click(customizeTrigger())
    const item = screen.getByRole('menuitem', { name: 'More Commands…' })
    expect(item.getAttribute('aria-disabled')).toBe('true')
    expect(item.title).toContain('options dialog')
  })
})
