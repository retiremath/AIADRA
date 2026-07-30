/**
 * Snap PROPOSALS (ADR/0044 A4; arc 20260730-1).
 *
 * The load-bearing distinction of BS-2, and the reason this file is so small:
 * Studio decides WHICH FACT to propose; the ENGINE decides where the geometry
 * ends up. When a nearly-level segment gets a `horizontal` fact, Studio does
 * NOT level the endpoints — it sends the drawn coordinates and the fact, and
 * the engine's solve is what puts the line exactly on the axis (ADR/0045 D6:
 * the engine is the sole semantic authority; Studio proposes and renders).
 *
 * That is why the drawn coordinates survive as authored nominals while the
 * displayed geometry is solved: two different things, never reconciled by
 * Studio rounding something. Nothing here computes a snapped coordinate, and
 * nothing here may start to.
 */

/** A plane-local drawn point, in sketch millimetres. */
export interface DrawnPoint {
  u: number
  v: number
}

export type AxisFact = 'horizontal' | 'vertical' | null

/**
 * Which axis fact (if any) to propose for a segment drawn from `a` to `b`.
 *
 * `toleranceDeg` is the class-3 `sketch.snapAngleToleranceDeg` preference.
 * The comparison against 45° is STRICT on both sides: a segment must be
 * strictly nearer one axis than the other, so an exactly diagonal line
 * proposes nothing rather than arbitrarily picking. A tolerance of 0
 * disables snapping outright — an exactly level line still proposes nothing,
 * which is the honest reading of "no snapping".
 */
export function proposeAxisFact(a: DrawnPoint, b: DrawnPoint, toleranceDeg: number): AxisFact {
  if (!Number.isFinite(toleranceDeg) || toleranceDeg <= 0) return null
  const tol = Math.min(toleranceDeg, 45)
  const du = b.u - a.u
  const dv = b.v - a.v
  if (du === 0 && dv === 0) return null
  // Angle from the u axis, folded into [0°, 90°] — the two axes are
  // symmetric, so one measurement answers both questions.
  const deg = (Math.atan2(Math.abs(dv), Math.abs(du)) * 180) / Math.PI
  if (deg < tol) return 'horizontal'
  if (90 - deg < tol) return 'vertical'
  return null
}

/**
 * Is this pointer travel a drawn segment, or just a click?
 *
 * `minDragPx` is Studio's own `sketch.minDragPx` — a SCREEN-space input
 * threshold. It is deliberately not the solver's `L_min_mm`: that constant
 * lives in a frozen branch policy as a model-space non-collapse guard, and
 * borrowing it here would let a UI preference leak into branch admission.
 */
export function isDrag(dxPx: number, dyPx: number, minDragPx: number): boolean {
  return Math.hypot(dxPx, dyPx) >= minDragPx
}
