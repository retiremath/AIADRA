/**
 * Reusable right-mouse-button context menu (pass workspace-tree-1, arc
 * 20260728-4). Same interaction contract as DropdownMenu's list — disabled
 * items keep `aria-disabled` + show their reason as the tooltip and never
 * activate; Escape / outside-pointer closes. Positioned fixed at the pointer,
 * clamped to the viewport.
 *
 * The OWNER holds the open state: render `<ContextMenu … />` only while open
 * (mirrors the graphics toolbar's position menu), passing the anchor point
 * from the triggering onContextMenu event.
 */
import { useEffect, useRef } from 'react'
import type { MenuItem } from './DropdownMenu'

export interface ContextMenuProps {
  x: number
  y: number
  label: string
  items: MenuItem[]
  onSelect: (key: string) => void
  onClose: () => void
}

export function ContextMenu({ x, y, label, items, onSelect, onClose }: ContextMenuProps) {
  const ref = useRef<HTMLUListElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    const onDown = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('pointerdown', onDown)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('pointerdown', onDown)
    }
  }, [onClose])

  // Clamp so the menu never overflows the viewport.
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const r = el.getBoundingClientRect()
    if (r.right > window.innerWidth) el.style.left = `${Math.max(0, window.innerWidth - r.width - 4)}px`
    if (r.bottom > window.innerHeight) el.style.top = `${Math.max(0, window.innerHeight - r.height - 4)}px`
  }, [x, y])

  return (
    <ul
      ref={ref}
      className="rmb-menu dd-menu"
      role="menu"
      aria-label={label}
      style={{ position: 'fixed', left: x, top: y, zIndex: 1000 }}
    >
      {items.map((it) => {
        const disabled = it.disabledReason != null
        return (
          <li
            key={it.key}
            role="menuitem"
            aria-disabled={disabled || undefined}
            tabIndex={-1}
            className={`dd-item${disabled ? ' disabled' : ''}${it.sepBefore ? ' sep' : ''}`}
            title={disabled ? (it.disabledReason ?? undefined) : it.title}
            onPointerDown={(e) => e.stopPropagation()}
            onClick={() => {
              if (disabled) return
              onSelect(it.key)
              onClose()
            }}
          >
            {it.label}
          </li>
        )
      })}
    </ul>
  )
}
