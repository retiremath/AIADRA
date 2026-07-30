/**
 * The middle-button PAIR tracker (W-2, hardened per Codex11 N3) — the pure
 * half of the MMB-click-vs-orbit distinction. A middle CLICK (ends the line
 * chain) is an up that pairs with ITS OWN down: same pointer id, travel
 * within the slop. Everything else — an orbit drag, a cancelled or lost
 * gesture, an up whose down was swallowed by the nav-cube island, a foreign
 * pointer — is NOT a click. The caller clears the pair on pointercancel /
 * pointerleave / teardown so a dead gesture can never lend its coordinates
 * to a later up.
 */
export interface MidPair {
  x: number
  y: number
  pointerId: number
}

export function midPairDown(e: {
  pointerId: number
  clientX: number
  clientY: number
}): MidPair {
  return { x: e.clientX, y: e.clientY, pointerId: e.pointerId }
}

/** The same 4px default slop the LMB place-vs-orbit guard uses. */
export function midPairIsClick(
  pair: MidPair | null,
  e: { pointerId: number; clientX: number; clientY: number },
  slopPx = 4,
): boolean {
  if (pair === null || pair.pointerId !== e.pointerId) return false
  return Math.hypot(e.clientX - pair.x, e.clientY - pair.y) <= slopPx
}
