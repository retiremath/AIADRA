/**
 * The reusable RMB context menu (pass workspace-tree-1): menu semantics,
 * disabled items keep their reason as tooltip and never activate, Escape and
 * outside-pointer close, selection closes.
 */
// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ContextMenu } from './ContextMenu'

afterEach(cleanup)

const items = [
  { key: 'open', label: 'Open' },
  { key: 'delete', label: 'Delete…', disabledReason: 'P-000001 is the active model — close it first' },
]

describe('the workspace-tree context menu', () => {
  it('renders a menu with the items; disabled carries aria-disabled + its reason as tooltip', () => {
    render(
      <ContextMenu x={10} y={10} label="Part actions" items={items} onSelect={() => {}} onClose={() => {}} />,
    )
    expect(screen.getByRole('menu', { name: 'Part actions' })).toBeTruthy()
    const del = screen.getByRole('menuitem', { name: 'Delete…' })
    expect(del.getAttribute('aria-disabled')).toBe('true')
    expect(del.getAttribute('title')).toContain('close it first')
    const open = screen.getByRole('menuitem', { name: 'Open' })
    expect(open.getAttribute('aria-disabled')).toBeNull()
  })

  it('an enabled item activates then closes; a disabled item does neither', () => {
    const onSelect = vi.fn()
    const onClose = vi.fn()
    render(
      <ContextMenu x={0} y={0} label="Part actions" items={items} onSelect={onSelect} onClose={onClose} />,
    )
    fireEvent.click(screen.getByRole('menuitem', { name: 'Delete…' }))
    expect(onSelect).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('menuitem', { name: 'Open' }))
    expect(onSelect).toHaveBeenCalledWith('open')
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('Escape closes; a pointer-down outside closes; inside does not', () => {
    const onClose = vi.fn()
    render(
      <ContextMenu x={0} y={0} label="Part actions" items={items} onSelect={() => {}} onClose={onClose} />,
    )
    fireEvent.pointerDown(screen.getByRole('menuitem', { name: 'Open' }))
    expect(onClose).not.toHaveBeenCalled()
    fireEvent.pointerDown(document.body)
    expect(onClose).toHaveBeenCalledTimes(1)
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(2)
  })
})
