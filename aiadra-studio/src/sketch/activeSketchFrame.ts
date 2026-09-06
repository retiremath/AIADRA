/**
 * The Sketch View authority for EVERY sketch lane (I3, arc 20260905-1;
 * Claude2 D5′): ONE selector the ribbon's Sketch View button consults — the
 * profile session's own frame (create: the placement mirror; edit: the
 * engine's display row) or the v1 lane's support frame. Null = no sketch
 * session, so there is nothing to return to. Before I3 the button served the
 * v1 lane only and was dead while drawing a profile.
 */
import type { AuthoringSessionState } from '../authoring/authoringSession'
import { supportFrame } from '../authoring/backend'
import type { PlaneFrameTS } from './planeFrame'

export function activeSketchFrame(
  v1: AuthoringSessionState,
  profile: { frame: PlaneFrameTS } | null,
): PlaneFrameTS | null {
  if (profile !== null) return profile.frame
  if (v1.mode === 'sketch') return supportFrame(v1.support)
  return null
}
