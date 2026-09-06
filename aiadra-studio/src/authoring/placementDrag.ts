/**
 * The placement dialog's drag law (W-5, Petre's walk 2026-09-06) — pure,
 * in its own module so the component file exports only components.
 */
const clamp = (v: number, lo: number, hi: number) => (hi < lo ? lo : Math.min(hi, Math.max(lo, v)))

/** W-5 (Petre's walk 2026-09-06): the dialog docks top-right but MOVES —
 *  Creo's dialog is a floating window the user drags off whatever it
 *  covers. Dragging the title bar translates the panel; the offset is
 *  transient session state (class 4), kept for the session, never persisted;
 *  the panel stays inside its host so it cannot be lost. Pure. */
export function dragOffset(
  start: { x: number; y: number },
  delta: { x: number; y: number },
  panel: { left: number; top: number; width: number; height: number } | null,
  host: { left: number; top: number; right: number; bottom: number; width: number } | null,
): { x: number; y: number } {
  let x = start.x + delta.x
  let y = start.y + delta.y
  if (panel && host && panel.width > 0 && host.width > 0) {
    const natLeft = panel.left - start.x // the panel's un-translated place
    const natTop = panel.top - start.y
    x = clamp(x, host.left - natLeft, host.right - natLeft - panel.width)
    y = clamp(y, host.top - natTop, host.bottom - natTop - panel.height)
  }
  return { x, y }
}
