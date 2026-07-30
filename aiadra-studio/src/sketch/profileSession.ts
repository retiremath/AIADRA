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

/** W-2 (Petre's step-2 walk): `line` is the Creo-style LINE CHAIN — each
 *  click chains a segment off the previous endpoint (shared vertex), a
 *  middle-click ends the chain OPEN, clicking the first point CLOSES it.
 *  There is no separate line-vs-polyline pair; the chain IS the tool. */
export type ProfileToolKind = 'line' | 'rectangle' | 'circle'

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

/** How many confirmed points this tool needs before it completes itself.
 *  `line` is the open-ended chain: only the user ends it (middle-click /
 *  Enter for open, clicking the first point for closed). */
const CLICKS_TO_COMPLETE: Record<ProfileToolKind, number | null> = {
  line: null,
  rectangle: 2,
  circle: 2,
}

const dist = (a: DrawnPoint, b: DrawnPoint) => Math.hypot(b.u - a.u, b.v - a.v)

export interface PlaceOptions {
  /** The close-hit radius in sketch mm — the viewport derives it from the
   *  CURRENT view scale (a fixed pixel radius), so "clicking the first
   *  point" means the same gesture at every zoom. Absent ⇒ exact hits only. */
  closeToleranceMm?: number
}

/**
 * Confirm a point. Returns the next state; a tool that has all the points it
 * needs completes itself and starts fresh, so drawing several shapes in a row
 * needs no extra ceremony.
 *
 * The line CHAIN (W-2) interprets clicks rather than counting them:
 *   * a click on the previous point is an input accident and is ignored — it
 *     can never mint a zero-length segment;
 *   * a click on the FIRST point with three or more vertices down closes the
 *     ring and completes the run (the Creo close gesture);
 *   * any other click chains one more vertex.
 */
export function commitPoint(s: ProfileSessionState, at: DrawnPoint, opts?: PlaceOptions): ProfileSessionState {
  if (s.tool.kind === 'line') {
    const tol = Math.max(opts?.closeToleranceMm ?? 0, 0)
    const pending = s.tool.pending
    const last = pending[pending.length - 1]
    if (last !== undefined && dist(at, last) <= tol) return s
    if (pending.length >= 3 && dist(at, pending[0]) <= tol) {
      return completeWith({ ...s, tool: { ...s.tool, cursor: null } }, true)
    }
    return { ...s, tool: { ...s.tool, pending: [...pending, at], cursor: null } }
  }
  const pending = [...s.tool.pending, at]
  const needed = CLICKS_TO_COMPLETE[s.tool.kind]
  if (needed !== null && pending.length >= needed) {
    return completeWith({ ...s, tool: { ...s.tool, pending, cursor: null } })
  }
  return { ...s, tool: { ...s.tool, pending, cursor: null } }
}

/**
 * End the open-ended chain (the viewport's middle-click, the keyboard's
 * Enter), or force the current tool to complete. A run too short to be a
 * shape is simply dropped — an accidental click never becomes a degenerate
 * entity.
 */
export function endTool(s: ProfileSessionState, opts?: { closed?: boolean }): ProfileSessionState {
  if (s.tool.pending.length < 2) return { ...s, tool: freshTool(s.tool.kind) }
  return completeWith(s, opts?.closed === true)
}

/** Is a chain run in progress? (Confirmed vertices down, shape not ended.) */
export function hasRun(s: ProfileSessionState): boolean {
  return s.tool.pending.length > 0
}

/** Abandon the in-progress run (Escape). Completed shapes stay; the tool
 *  re-arms empty. Distinct from `setTool` in intent, identical in effect —
 *  named so the Escape path states what it does. */
export function abandonRun(s: ProfileSessionState): ProfileSessionState {
  return { ...s, tool: freshTool(s.tool.kind) }
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
