/**
 * THE reusable accessible dropdown (arc 20260716-1 V-1; Codex1 B4.5) — one
 * menu interaction contract shared by the File menu, ribbon command families,
 * the graphics-toolbar display/orientation dropdowns, and the ribbon overflow.
 *
 * Pinned behavior: `aria-haspopup/expanded`; the trigger's accessible name
 * carries the current value when given; roving arrow-key focus (skips
 * disabled); Home/End; Enter/Space activates; Escape/outside-click closes and
 * RESTORES trigger focus; disabled items keep `aria-disabled` semantics and
 * never activate; opening is CLICK (never hover-only).
 */
import { useEffect, useId, useRef, useState } from 'react'

export interface MenuItem {
  key: string
  label: string
  /** null = enabled; a string = disabled with THIS reason (title tooltip). */
  disabledReason?: string | null
  /** Marks the currently-active option (display modes, named views). */
  current?: boolean
}

export function DropdownMenu({
  label,
  currentValue,
  items,
  onSelect,
  className,
  children,
  disabled,
}: {
  /** The trigger's visible content is `children`; `label` is the accessible name. */
  label: string
  /** Optional current value woven into the accessible name + tooltip. */
  currentValue?: string
  items: MenuItem[]
  onSelect: (key: string) => void
  className?: string
  children?: React.ReactNode
  disabled?: boolean
}) {
  const [open, setOpen] = useState(false)
  const [focusIdx, setFocusIdx] = useState(0)
  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const menuId = useId()

  const accessibleName = currentValue ? `${label} — ${currentValue}` : label

  const close = (restoreFocus = true) => {
    setOpen(false)
    if (restoreFocus) triggerRef.current?.focus()
  }

  // outside-click closes (without stealing focus back)
  useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    window.addEventListener('pointerdown', onDown)
    return () => window.removeEventListener('pointerdown', onDown)
  }, [open])

  // focus the roving item when open / focusIdx changes
  useEffect(() => {
    if (!open) return
    const el = listRef.current?.children[focusIdx] as HTMLElement | undefined
    el?.focus()
  }, [open, focusIdx])

  const enabledIdx = (from: number, dir: 1 | -1): number => {
    const n = items.length
    let i = from
    for (let step = 0; step < n; step++) {
      i = (i + dir + n) % n
      if (!items[i].disabledReason) return i
    }
    return from
  }

  const openMenu = () => {
    if (disabled || items.length === 0) return
    const first = items.findIndex((it) => !it.disabledReason)
    setFocusIdx(first >= 0 ? first : 0)
    setOpen(true)
  }

  const onListKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { close(); e.preventDefault() }
    else if (e.key === 'ArrowDown') { setFocusIdx((i) => enabledIdx(i, 1)); e.preventDefault() }
    else if (e.key === 'ArrowUp') { setFocusIdx((i) => enabledIdx(i, -1)); e.preventDefault() }
    else if (e.key === 'Home') { setFocusIdx(enabledIdx(items.length - 1, 1)); e.preventDefault() }
    else if (e.key === 'End') { setFocusIdx(enabledIdx(0, -1)); e.preventDefault() }
    else if (e.key === 'Enter' || e.key === ' ') {
      const it = items[focusIdx]
      if (it && !it.disabledReason) { onSelect(it.key); close() }
      e.preventDefault()
    } else if (e.key === 'Tab') {
      setOpen(false) // tab moves on naturally; no focus trap
    }
  }

  return (
    <div ref={rootRef} className={`dd ${className ?? ''}`}>
      <button
        ref={triggerRef}
        type="button"
        className="dd-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label={accessibleName}
        title={accessibleName}
        disabled={disabled}
        onClick={() => (open ? close(false) : openMenu())}
        onKeyDown={(e) => {
          if ((e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') && !open) {
            openMenu()
            e.preventDefault()
          }
        }}
      >
        {children ?? label}
      </button>
      {open && (
        <ul ref={listRef} id={menuId} role="menu" aria-label={label} className="dd-menu" onKeyDown={onListKey}>
          {items.map((it, i) => (
            <li
              key={it.key}
              role="menuitem"
              tabIndex={i === focusIdx ? 0 : -1}
              aria-disabled={it.disabledReason ? true : undefined}
              className={`dd-item${it.disabledReason ? ' disabled' : ''}${it.current ? ' current' : ''}`}
              title={it.disabledReason ?? undefined}
              onClick={() => {
                if (!it.disabledReason) { onSelect(it.key); close(false) }
              }}
            >
              {it.current ? '✓ ' : ''}{it.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
