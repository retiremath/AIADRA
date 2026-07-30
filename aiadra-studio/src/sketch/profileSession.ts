/**
 * The profile-sketch drawing session (ADR/0044 A4; arc 20260730-1).
 *
 * A pure state machine: pointer events in, a `ProfilePayload` out. It owns no
 * three.js objects, performs no IPC, and computes no geometry — the engine
 * solves, and the caller renders whatever `preview` it was handed.
 *
 * TWO ENTRY STATES (Codex3 B1). The distinction is not cosmetic; it decides
 * what Cancel means, and an earlier design collapsed them and produced a
 * contradiction:
 *
 *   CREATE — opened from the temporary `Profile Sketch` command. Placement
 *     commits NOTHING on its own, so Cancel must leave NO feature behind.
 *     Close authors one `author_profile_sketch` transaction.
 *
 *   EDIT — opened from the tree ✎ on a committed 0.2.2 sketch. The feature
 *     already exists, so Cancel must leave it BYTE-FOR-BYTE as it was: the
 *     session holds a baseline and simply discards its own edits. Close
 *     issues `replace_sketch_graph`.
 *
 * Neither path can write on Cancel, because neither path writes at all until
 * Close — the preview is a READ.
 */
import { buildCircle, buildPolyline, buildRectangle, mergeProfiles } from './profileBuilder'
import type { ProfileGraphPreview } from '../display/contract'
import type { ProfilePayload } from './profileTypes'
import type { SketchPlacementInput } from './profileTypes'
import { isDrag, type DrawnPoint } from './snapProposal'
import type { PlaneFrameTS } from './planeFrame'

export type ProfileToolKind = 'line' | 'polyline' | 'rectangle' | 'circle'

/** The authority tuple captured at session OPEN (Codex7 B2): every preview
 *  and the terminal use THIS, never the shell's current values — a session
 *  opened against Part A can never be silently retargeted to Part B. */
export interface SessionTarget {
  workspaceId: string | null
  partNumber: string
  generation: number
}

/** The in-progress tool. `pending` are confirmed clicks; `cursor` is live. */
export interface ToolState {
  kind: ProfileToolKind
  pending: DrawnPoint[]
  cursor: DrawnPoint | null
}

export type ProfileOwner =
  | {
      kind: 'create'
      placement: SketchPlacementInput
      /** Caller-scoped, NOT a feature id — no feature exists yet. */
      candidateKey: string
    }
  | {
      kind: 'edit'
      sketchFeatureId: string
      /** The committed profile, re-sent verbatim if nothing is redrawn.
       *  Holding it is what makes Cancel a no-write guarantee rather than a
       *  hope. */
      baseline: ProfilePayload
    }

export interface ProfileSessionState {
  owner: ProfileOwner
  /** The engine-resolved drawing plane, captured at OPEN. Codex6 B2: the
   *  session owns its frame — no other lifecycle's death can take it away
   *  from an active drawing. */
  frame: PlaneFrameTS
  /** Captured at OPEN; revalidated at terminal start (Codex7 B2). */
  target: SessionTarget
  tool: ToolState
  /** Completed drawings this session, in order. */
  parts: ProfilePayload[]
  /** The last engine preview, or null before the first one / after a refusal. */
  preview: ProfileGraphPreview | null
  /** The engine's typed refusal of the CURRENT graph, if any. A refusal never
   *  ends the session — an invalid intermediate is normal while drawing. */
  refusal: string | null
  snapAngleToleranceDeg: number
  minDragPx: number
}

export interface OpenOptions {
  snapAngleToleranceDeg: number
  minDragPx: number
  tool?: ProfileToolKind
}

const freshTool = (kind: ProfileToolKind): ToolState => ({ kind, pending: [], cursor: null })

export function openCreate(
  placement: SketchPlacementInput,
  candidateKey: string,
  frame: PlaneFrameTS,
  target: SessionTarget,
  opts: OpenOptions,
): ProfileSessionState {
  return {
    owner: { kind: 'create', placement, candidateKey },
    frame,
    target,
    tool: freshTool(opts.tool ?? 'line'),
    parts: [],
    preview: null,
    refusal: null,
    snapAngleToleranceDeg: opts.snapAngleToleranceDeg,
    minDragPx: opts.minDragPx,
  }
}

export function openEdit(
  sketchFeatureId: string,
  baseline: ProfilePayload,
  frame: PlaneFrameTS,
  target: SessionTarget,
  opts: OpenOptions,
): ProfileSessionState {
  return {
    owner: { kind: 'edit', sketchFeatureId, baseline },
    frame,
    target,
    tool: freshTool(opts.tool ?? 'line'),
    parts: [],
    preview: null,
    refusal: null,
    snapAngleToleranceDeg: opts.snapAngleToleranceDeg,
    minDragPx: opts.minDragPx,
  }
}

export function setTool(s: ProfileSessionState, kind: ProfileToolKind): ProfileSessionState {
  // Switching tools abandons the in-progress run — it never half-commits a
  // partial shape into `parts`.
  return { ...s, tool: freshTool(kind) }
}

export function moveCursor(s: ProfileSessionState, at: DrawnPoint | null): ProfileSessionState {
  return { ...s, tool: { ...s.tool, cursor: at } }
}

/** How many confirmed points this tool needs before it completes itself. */
const CLICKS_TO_COMPLETE: Record<ProfileToolKind, number | null> = {
  line: 2,
  rectangle: 2,
  circle: 2,
  polyline: null, // open-ended: the user ends it explicitly
}

/**
 * Confirm a point. Returns the next state; a tool that has all the points it
 * needs completes itself and starts fresh, so drawing several lines in a row
 * needs no extra ceremony.
 */
export function commitPoint(s: ProfileSessionState, at: DrawnPoint): ProfileSessionState {
  const pending = [...s.tool.pending, at]
  const needed = CLICKS_TO_COMPLETE[s.tool.kind]
  if (needed !== null && pending.length >= needed) {
    return completeWith({ ...s, tool: { ...s.tool, pending, cursor: null } })
  }
  return { ...s, tool: { ...s.tool, pending, cursor: null } }
}

/**
 * End an open-ended tool (the polyline's double-click / Enter), or force the
 * current one to complete. A run too short to be a shape is simply dropped —
 * an accidental click never becomes a degenerate entity.
 */
export function endTool(s: ProfileSessionState, opts?: { closed?: boolean }): ProfileSessionState {
  if (s.tool.pending.length < 2) return { ...s, tool: freshTool(s.tool.kind) }
  return completeWith(s, opts?.closed === true)
}

function completeWith(s: ProfileSessionState, closed = false): ProfileSessionState {
  const pts = s.tool.pending
  let part: ProfilePayload
  try {
    switch (s.tool.kind) {
      case 'rectangle':
        part = buildRectangle(pts[0], pts[1])
        break
      case 'circle':
        part = buildCircle(pts[0], pts[1])
        break
      default:
        part = buildPolyline(pts, {
          snapAngleToleranceDeg: s.snapAngleToleranceDeg,
          closed,
        })
    }
  } catch {
    // A degenerate drag (zero-size rectangle, zero-radius circle) is dropped
    // silently — the user clicked twice in the same place, which is an input
    // accident, not a modeling intent worth a dialog.
    return { ...s, tool: freshTool(s.tool.kind) }
  }
  return { ...s, parts: [...s.parts, part], tool: freshTool(s.tool.kind) }
}

/** Drop the most recent completed drawing (the sketcher's undo). */
export function undoLastPart(s: ProfileSessionState): ProfileSessionState {
  if (s.parts.length === 0) return s
  return { ...s, parts: s.parts.slice(0, -1) }
}

export function applyPreview(
  s: ProfileSessionState,
  result: { preview: ProfileGraphPreview | null; refusal: { message: string } | null },
): ProfileSessionState {
  return {
    ...s,
    preview: result.preview,
    refusal: result.refusal?.message ?? null,
  }
}

/**
 * The graph as it currently stands — what both the preview and the commit are
 * built from, so they can never describe different things.
 *
 * On the EDIT path the committed baseline leads: records the user did not
 * touch are re-sent under their own ids, which is what preserves their
 * identity under the survival law. Newly drawn parts follow under fresh keys.
 */
export function currentProfile(s: ProfileSessionState): ProfilePayload | null {
  const drawn = s.parts.length > 0 ? mergeProfiles(s.parts) : null
  if (s.owner.kind === 'create') return drawn
  if (drawn === null) return s.owner.baseline
  return {
    points: [...(s.owner.baseline.points ?? []), ...(drawn.points ?? [])],
    segments: [...(s.owner.baseline.segments ?? []), ...(drawn.segments ?? [])],
    circles: [...(s.owner.baseline.circles ?? []), ...(drawn.circles ?? [])],
    facts: [...(s.owner.baseline.facts ?? []), ...(drawn.facts ?? [])],
  }
}

/** Is there anything worth sending? A create session with nothing drawn has
 *  no transaction to make; an edit session with nothing redrawn is a no-op the
 *  engine would refuse anyway. */
export function hasWork(s: ProfileSessionState): boolean {
  return s.owner.kind === 'create' ? s.parts.length > 0 : s.parts.length > 0
}

/** The preview request for the CURRENT graph, or null if there is nothing to
 *  preview yet. Owner-shaped exactly as `previewSketchGraph` expects. */
export function previewRequest(s: ProfileSessionState):
  | {
      profile: ProfilePayload
      owner: { sketchFeatureId: string } | { placement: SketchPlacementInput; candidateKey: string }
    }
  | null {
  const profile = currentProfile(s)
  if (profile === null) return null
  return {
    profile,
    owner:
      s.owner.kind === 'edit'
        ? { sketchFeatureId: s.owner.sketchFeatureId }
        : { placement: s.owner.placement, candidateKey: s.owner.candidateKey },
  }
}

/**
 * What Close should send. `null` means Close is a no-op — and on the CREATE
 * path that is indistinguishable from Cancel, exactly as intended: a placement
 * with nothing drawn on it leaves no feature.
 */
export function commitIntent(
  s: ProfileSessionState,
  partNumber: string,
):
  | { kind: 'mechanical.author_profile_sketch'; params: Record<string, unknown> }
  | { kind: 'mechanical.replace_sketch_graph'; params: Record<string, unknown> }
  | null {
  if (!hasWork(s)) return null
  const profile = currentProfile(s)
  if (profile === null) return null
  if (s.owner.kind === 'create') {
    return {
      kind: 'mechanical.author_profile_sketch',
      params: { part_number: partNumber, placement: s.owner.placement, profile },
    }
  }
  return {
    kind: 'mechanical.replace_sketch_graph',
    params: {
      part_number: partNumber,
      sketch_feature_id: s.owner.sketchFeatureId,
      profile,
    },
  }
}

/**
 * Cancel. There is deliberately no state to unwind: the session never wrote
 * anything, so cancelling is discarding the object. The function exists to
 * make that postcondition explicit and testable rather than implied by the
 * absence of code.
 */
export function cancel(s: ProfileSessionState): { wrote: false; preservedFeatureId: string | null } {
  return {
    wrote: false,
    preservedFeatureId: s.owner.kind === 'edit' ? s.owner.sketchFeatureId : null,
  }
}

/** Should this pointer travel be treated as a drag (a shape) or a click? */
export function isDragFor(s: ProfileSessionState, dxPx: number, dyPx: number): boolean {
  return isDrag(dxPx, dyPx, s.minDragPx)
}
