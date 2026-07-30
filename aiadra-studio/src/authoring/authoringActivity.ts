/**
 * The profile lane's contribution to the global lifecycle law (Codex8 B1),
 * as PURE predicates the App consumes and the tests drive directly.
 *
 * Two invariants live here:
 *
 *   1. "Active NOW" — profile activity joins `authoringBusy` as a RENDER
 *      derivation, never an effect projection. An effect publishes one render
 *      late, and most gate consumers read render-captured values, so a
 *      passive flag leaves a frame in which a second operation can start.
 *
 *   2. An in-flight TERMINAL is not an uncommitted draft. Generation
 *      invalidation unwinds a pick or an open drawing without writing — but a
 *      session whose Close is running OWNS the busy state until the backend
 *      settles. Cancelling it locally cannot cancel the transaction; it can
 *      only orphan it and reopen the gate while the engine is still writing.
 */

export interface ProfileLaneView {
  active: boolean
  closing: boolean
}

/** Does the profile lane count as authoring activity RIGHT NOW? */
export function profileActivity(pick: boolean, lane: ProfileLaneView): boolean {
  return pick || lane.active || lane.closing
}

/** ONE named predicate for the Sketch tab AND the ribbon body (Codex8 N1) —
 *  the two sites drifted once (tab on busy, body on active) and showed a
 *  Sketch tab over the Model ribbon during a pick. A PICK is not a session:
 *  it runs from the Model ribbon, exactly like the legacy planePick. */
export function sketchRibbonActive(v1Mode: string, lane: Pick<ProfileLaneView, 'active'>): boolean {
  return v1Mode === 'sketch' || lane.active
}

export type InvalidationAction =
  | 'none'
  | 'cancel-pick'
  | 'cancel-session'
  /** The terminal is writing: retain busy ownership; the runner's own
   *  generation check refuses stale display adoption when it settles. */
  | 'retain-terminal'

/** What a generation change does to the profile lane (Codex8 B1). */
export function invalidationAction(
  pick: boolean,
  session: { closing: boolean; targetGeneration: number } | null,
  liveGeneration: number,
): InvalidationAction {
  if (pick) return 'cancel-pick'
  if (session === null) return 'none'
  if (session.targetGeneration === liveGeneration) return 'none'
  if (session.closing) return 'retain-terminal'
  return 'cancel-session'
}
