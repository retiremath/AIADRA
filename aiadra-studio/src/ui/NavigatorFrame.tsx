/**
 * The navigator frame (Creo navigator benchmark; shell-1 S1-08 as AMENDED
 * 2026-09-05 through the "new benchmark ruling" door — Petre's Home-state
 * side-by-side): ONE drag-resizable, dismissable column hosting BOTH the Home
 * state's Workspaces panel and the modeling state's tabbed tree. Creo has one
 * navigator; so does Studio — one width, one visibility, one sash.
 *
 * Width = the `navigatorWidth` setting; the sash clamps to the DESCRIPTOR's
 * min/max (one authority — no literal twin of the bounds lives here).
 * Visibility = the `navigatorVisible` setting, flipped by the status bar's
 * bottom-left `NavigatorToggle` (Creo's navigator button). Hidden renders
 * NOTHING — no zero-width ghost, no sash — so the main surface takes the whole
 * width and the viewport's ResizeObserver (S1-13) tracks it. Both keys are
 * ADR/0033 D8 local chrome (ADR/0045 class 3): persisted, never Truth.
 */
import { useRef, type PointerEvent as ReactPointerEvent, type ReactNode } from 'react'
import { clampNavigatorWidth } from './navigatorWidth'
import { useSetting } from '../settings/useSettings'

export function NavigatorFrame({
  className,
  children,
}: {
  /** The hosted aside's class (`sidebar` in modeling, `home-left` at Home). */
  className: string
  children: ReactNode
}) {
  const [visible] = useSetting('navigatorVisible')
  const [width, setWidth] = useSetting('navigatorWidth')
  const dragging = useRef(false)

  // Dismissed: nothing at all — the status-bar toggle is the way back (Creo).
  if (visible !== true) return null

  // The sash: dragging the right edge widens/narrows the column. Pointer
  // capture (where the platform offers it) keeps the drag alive off the grip.
  const onGripDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    dragging.current = true
    const target = e.target as HTMLElement
    if (typeof target.setPointerCapture === 'function') target.setPointerCapture(e.pointerId)
    const startX = e.clientX
    const startW = width as number
    const move = (ev: PointerEvent) => {
      if (!dragging.current) return
      setWidth(clampNavigatorWidth(startW + (ev.clientX - startX)))
    }
    const up = () => {
      dragging.current = false
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }

  return (
    <div className="sidebar-wrap" style={{ width: width as number }} data-testid="navigator-frame">
      <aside className={className}>{children}</aside>
      <div
        className="nav-grip"
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize the navigator"
        title="Drag to resize"
        onPointerDown={onGripDown}
      />
    </div>
  )
}
