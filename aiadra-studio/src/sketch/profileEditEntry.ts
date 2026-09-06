/**
 * The profile EDIT entry (I3, arc 20260905-1; Codex1 N1 / Codex2): the
 * session frame of an edit is the ENGINE's `sketch_frames[]` row for the
 * CURRENT display generation — never the TS mirror — and the target tuple is
 * captured from the SAME context snapshot, so frame and target can never
 * disagree. A missing or stale row refuses: the display is not installed for
 * this generation, or the feature carries no row — the honest fix is to
 * refresh or reopen the Part, never a guessed frame.
 */
import { captureAuthoringTarget, type PartContextState } from '../authoring/partContext'
import type { SketchFrame } from '../display/contract'
import type { PlaneFrameTS } from './planeFrame'
import type { SessionTarget } from './profileSession'

export const EDIT_FRAME_UNAVAILABLE =
  'this sketch’s frame is not in the current display — refresh or reopen the Part, then edit again'
export const EDIT_CONTEXT_NOT_READY = 'the Part is not ready — refresh or reopen it, then edit again'

/** The engine row's wire names → the session's frame shape; values preserved. */
export function sketchFrameToPlaneFrame(row: SketchFrame): PlaneFrameTS {
  return { origin: row.origin_mm, u: row.u_axis, v: row.v_axis, normal: row.normal }
}

export type ProfileEditEntry =
  | { ok: true; frame: PlaneFrameTS; target: SessionTarget }
  | { ok: false; reason: string }

/** Resolve an edit's frame + target from ONE snapshot (Codex2's clarification). */
export function resolveProfileEditEntry(snapshot: PartContextState, featureId: string): ProfileEditEntry {
  const target = captureAuthoringTarget(snapshot)
  if (target === null) return { ok: false, reason: EDIT_CONTEXT_NOT_READY }
  const row = snapshot.selectorFacts?.sketchFrames.get(featureId) ?? null
  if (row === null) return { ok: false, reason: EDIT_FRAME_UNAVAILABLE }
  return { ok: true, frame: sketchFrameToPlaneFrame(row), target }
}
