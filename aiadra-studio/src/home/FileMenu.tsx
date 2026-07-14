/**
 * The File menu (arc 20260714-1; D-H3). A real dropdown in the topbar, present
 * in BOTH app states. Honest by the slice-A discipline: anything unbuilt is
 * visibly disabled with a tooltip — per Codex6, "Check In" stays disabled until
 * it performs the actual git-backed transition (ADR/0040 D7 optimistic PDM).
 */
import { useEffect, useRef, useState } from 'react'

export interface FileMenuItem {
  label: string
  enabled: boolean
  title?: string
  onClick?: () => void
  /** Draw a separator line above this item. */
  sep?: boolean
}

export function FileMenu({ items }: { items: FileMenuItem[] }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('pointerdown', onDown)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('pointerdown', onDown)
      window.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className="file-menu" ref={rootRef}>
      <button
        type="button"
        className={`fm-btn ${open ? 'on' : ''}`}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        File
      </button>
      {open && (
        <div className="fm-pop" role="menu">
          {items.map((it) => (
            <button
              key={it.label}
              type="button"
              role="menuitem"
              className={`fm-item ${it.sep ? 'sep' : ''}`}
              disabled={!it.enabled}
              title={it.title}
              onClick={() => {
                if (!it.enabled) return
                setOpen(false)
                it.onClick?.()
              }}
            >
              {it.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
