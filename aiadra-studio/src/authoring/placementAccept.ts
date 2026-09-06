/**
 * The Sketch accept (I3; Codex3 B5): the ONE production path from the
 * placement dialog to the drawing session — extracted from the App so the
 * actual caller can be exercised with REAL stores. It revalidates the
 * CAPTURED target against the live context (never recaptures), builds the
 * complete four-member placement and the mirror frame, retires the placement
 * owner exactly once, and hands the SAME target to the drawing session.
 * Nothing is written here; Close is the only writer.
 */
import type { PlaneFrameTS } from '../sketch/planeFrame'
import { placementRecordOf, type AuthoringSessionStore, type PlacementTarget } from './authoringSession'
import type { PartContextState } from './partContext'
import { placementToPlaneFrame, type PlacementRecord } from './placementFrame'

export const PLACEMENT_CONTEXT_CHANGED = 'the Part context changed — cancel and start Sketch again'

export type SketchAcceptOutcome =
  | { kind: 'opened'; placement: PlacementRecord; frame: PlaneFrameTS; target: PlacementTarget }
  | { kind: 'refused'; reason: string }
  | { kind: 'ignored' }

export function acceptSketchPlacement(
  store: AuthoringSessionStore,
  live: PartContextState,
  open: (placement: PlacementRecord, frame: PlaneFrameTS, target: PlacementTarget) => void,
): SketchAcceptOutcome {
  const s = store.getSnapshot()
  if (s.mode !== 'placement' || s.busy || s.accept !== 'sketch') return { kind: 'ignored' }
  const captured = s.capturedTarget
  if (
    !captured ||
    live.inspection.status !== 'ready' ||
    captured.generation !== live.generation ||
    captured.partNumber !== live.partNumber ||
    captured.workspaceId !== live.workspaceId
  ) {
    store.failPlacement(PLACEMENT_CONTEXT_CHANGED)
    return { kind: 'refused', reason: PLACEMENT_CONTEXT_CHANGED }
  }
  const placement = placementRecordOf(s)
  const frame = placementToPlaneFrame(placement)
  store.completePlacement()
  open(placement, frame, captured)
  return { kind: 'opened', placement, frame, target: captured }
}
