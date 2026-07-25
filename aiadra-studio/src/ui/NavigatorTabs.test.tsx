/**
 * The navigator tab strip (Creo tabbed tree): a pure control — proper tablist
 * semantics, active marking, selection callback. The shell's auto-switching
 * (part-load → Model Tree; plane pick forces Model Tree) lives in App and is
 * exercised by the desktop walk.
 */
// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { NavigatorTabs } from './NavigatorTabs'

afterEach(cleanup)

describe('the navigator tab strip (Creo tabbed tree)', () => {
  it('renders a tablist with Model Tree + Workspace and marks the active tab', () => {
    render(<NavigatorTabs active="workspace" onSelect={() => {}} />)
    const list = screen.getByRole('tablist', { name: 'Navigator' })
    expect(list).toBeTruthy()
    const model = screen.getByRole('tab', { name: 'Model Tree' })
    const ws = screen.getByRole('tab', { name: 'Workspace' })
    expect(model.getAttribute('aria-selected')).toBe('false')
    expect(ws.getAttribute('aria-selected')).toBe('true')
    expect(ws.className).toContain('active')
  })

  it('clicking a tab reports its key (selection is the shell’s decision)', () => {
    const onSelect = vi.fn()
    render(<NavigatorTabs active="workspace" onSelect={onSelect} />)
    fireEvent.click(screen.getByRole('tab', { name: 'Model Tree' }))
    expect(onSelect).toHaveBeenCalledWith('model')
    // clicking the active tab still reports — idempotent for the shell
    fireEvent.click(screen.getByRole('tab', { name: 'Workspace' }))
    expect(onSelect).toHaveBeenCalledWith('workspace')
  })
})
