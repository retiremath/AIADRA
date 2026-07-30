/**
 * The profile-sketch lane as one hook (ADR/0044 A4; arc 20260730-1).
 *
 * Everything the v2 drawing surface needs lives here — the session state, the
 * engine preview round trip, and the viewport interaction mode — so the
 * Workbench integrates it by calling one function rather than growing another
 * six pieces of coupled state.
 *
 * The division of labour is the D6 split, made structural:
 *   * `profileSession`  owns WHAT was drawn (pure, tested separately);
 *   * the ENGINE owns where it ends up and what it measures;
 *   * this hook owns only the plumbing between them, and the overlay renders
 *     the engine's answer.
 *
 * Nothing here computes geometry. If this file ever needs to, something has
 * gone wrong upstream.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { SketchInteractionMode } from '../Viewport'
import type { PlaneFrameTS } from './planeFrame'
import type { ProfileGeometry } from './profileOverlay'
import {
  abandonRun as abandonSessionRun,
  applyPreview,
  type SessionTarget,
  cancel as cancelSession,
  commitIntent,
  commitPoint,
  endTool,
  hasRun as sessionHasRun,
  moveCursor,
  openCreate,
  openEdit,
  type PlaceOptions,
  previewRequest,
  setTool as setSessionTool,
  undoLastPart,
  type ProfileSessionState,
  type ProfileToolKind,
} from './profileSession'
import { createPreviewRequester, type PreviewResult } from './profilePreviewRequester'
import type { ProfilePayload, SketchPlacementInput } from './profileTypes'
import type { DrawnPoint } from './snapProposal'

/** What the hook needs from the shell. Deliberately narrow — no store, no
 *  viewport handle, no bridge object: just identity and the two settings. */
export interface ProfileSketchDeps {
  snapAngleToleranceDeg: number
  minDragPx: number
  /** The engine that owns this sketch. Codex6 B3: carried EXPLICITLY from
   *  here — the domain-specific layer — all the way to Ring 2; no layer below
   *  supplies a default, because a hidden domain guess is exactly what the
   *  explicit Ring-2 parameter exists to prevent. */
  engineId?: string
  /** Injected for tests; defaults to the preload bridge. */
  preview?: (
    workspaceId: string,
    objectRef: string,
    engineId: string,
    profile: ProfilePayload,
    owner: { sketchFeatureId: string } | { placement: SketchPlacementInput; candidateKey: string },
  ) => Promise<PreviewResult>
  /** Called on Close with the operation to run. The Workbench owns the
   *  authoring session/commit lane; this hook never writes. */
  onCommit?: (intent: { kind: string; params: Record<string, unknown> }, target: SessionTarget) => void
  /** Codex7 B2: terminal-start revalidation of the CAPTURED tuple against the
   *  live shell. Non-null = the refusal to surface; Close then does NOT run.
   *  (Defense in depth — the App also cancels the session outright on
   *  generation invalidation.) */
  validateTarget?: (target: SessionTarget) => string | null
}

export interface ProfileSketchLane {
  active: boolean
  session: ProfileSessionState | null
  /** True while a Close's commit round trip is in flight (single-flight). */
  closing: boolean
  /** The engine's typed refusal of the CURRENT graph, if any. */
  refusal: string | null
  /** Null unless a session is open — merge into the Workbench's mode memo. */
  mode: SketchInteractionMode | null
  openCreateSession(placement: SketchPlacementInput, frame: PlaneFrameTS, target: SessionTarget): void
  openEditSession(
    sketchFeatureId: string,
    baseline: ProfilePayload,
    frame: PlaneFrameTS,
    target: SessionTarget,
  ): void
  setTool(kind: ProfileToolKind): void
  place(uv: { u: number; v: number }, opts?: PlaceOptions): void
  cursor(uv: { u: number; v: number } | null): void
  /** End the open-ended line chain (the viewport's middle-click / Enter). */
  finishTool(opts?: { closed?: boolean }): void
  /** True while confirmed chain vertices are down (the Escape target). */
  hasRun: boolean
  /** Abandon the in-progress run (Escape); completed shapes stay. */
  abandonRun(): void
  undo(): void
  /** Close: hands the commit intent to the shell. The session STAYS OPEN
   *  until the shell reports the outcome — a failed commit must leave a
   *  recoverable drawing, not a cleared one (Codex6 B2). */
  close(): void
  /** The shell's success report: the commit landed; end the session. */
  confirmClosed(): void
  /** The shell's failure report: the draft was rolled back; the session
   *  survives with the refusal surfaced, fully recoverable. */
  commitFailed(message: string): void
  /** Cancel: writes nothing, by construction. */
  cancel(): { wrote: false; preservedFeatureId: string | null }
}

const bridgePreview: NonNullable<ProfileSketchDeps['preview']> = async (
  workspaceId,
  objectRef,
  engineId,
  profile,
  owner,
) => {
  const api = window.aiadra
  if (!api?.previewSketchGraph) {
    // Browser-only dev has no engine. Refusing honestly beats drawing a
    // mock the commit lane would never reproduce.
    return { preview: null, refusal: { message: 'the engine bridge is unavailable' } }
  }
  const res = await api.previewSketchGraph(workspaceId, objectRef, engineId, profile, owner)
  if (!res.ok) return { preview: null, refusal: { message: res.error.message } }
  return { preview: res.result.preview, refusal: res.result.refusal }
}

/** The overlay geometry of a preview — the envelope minus its owner/frame. */
export function previewGeometry(
  preview: ProfileSessionState['preview'],
): ProfileGeometry | null {
  if (!preview) return null
  return {
    points: preview.points,
    segments: preview.segments,
    circles: preview.circles,
    annotations: preview.annotations,
    constraint_glyphs: preview.constraint_glyphs,
  }
}

/** The engine this lane authors into. Named here, at the domain-specific
 *  layer, rather than defaulted in a generic one. */
const MECHANICAL = 'mechanical'

let candidateSeq = 0
/** A caller-scoped key for a create preview — never an engine id, and never
 *  reused, so two sessions can't be confused for one another. */
export function nextCandidateKey(): string {
  candidateSeq += 1
  return `draft${candidateSeq}`
}

export function useProfileSketch(deps: ProfileSketchDeps): ProfileSketchLane {
  const [session, setSession] = useState<ProfileSessionState | null>(null)
  const run = deps.preview ?? bridgePreview
  const depsRef = useRef(deps)
  depsRef.current = deps

  // ONE requester for the lane's lifetime: its monotonic id is what makes a
  // stale reply unable to paint, so it must not be re-created per render.
  const requester = useMemo(
    () =>
      createPreviewRequester<{
        profile: ProfilePayload
        owner: { sketchFeatureId: string } | { placement: SketchPlacementInput; candidateKey: string }
        target: SessionTarget
      }>({
        run: (req) => {
          // Codex7 B2: the CAPTURED tuple, never the shell's current values —
          // a preview can never silently retarget to a navigated-to Part.
          if (!req.target.workspaceId) {
            return Promise.resolve({
              preview: null,
              refusal: { message: 'no open workspace' },
            })
          }
          return run(
            req.target.workspaceId,
            req.target.partNumber,
            depsRef.current.engineId ?? MECHANICAL,
            req.profile,
            req.owner,
          )
        },
        apply: (result) => setSession((s) => (s === null ? s : applyPreview(s, result))),
        onError: (e) =>
          setSession((s) =>
            s === null
              ? s
              : applyPreview(s, {
                  preview: null,
                  refusal: { message: e instanceof Error ? e.message : String(e) },
                }),
          ),
      }),
    [run],
  )

  // Every change to the drawn graph asks for a fresh preview. Requests
  // coalesce, so a fast sequence of clicks cannot outrun the engine.
  const lastSent = useRef<string | null>(null)
  useEffect(() => {
    if (session === null) {
      lastSent.current = null
      return
    }
    const req = previewRequest(session)
    if (req === null) {
      lastSent.current = null
      return
    }
    // The cursor is live state and is NOT part of the graph, so hovering
    // must not trigger a solve: only a real change to the drawn records does.
    const key = JSON.stringify(req.profile)
    if (key === lastSent.current) return
    lastSent.current = key
    requester.request({ ...req, target: session.target })
  }, [session, requester])

  useEffect(() => () => requester.cancel(), [requester])

  const [closing, setClosing] = useState(false)

  const openCreateSession = useCallback(
    (placement: SketchPlacementInput, frame: PlaneFrameTS, target: SessionTarget) => {
      const d = depsRef.current
      setClosing(false)
      setSession(
        openCreate(placement, nextCandidateKey(), frame, target, {
          snapAngleToleranceDeg: d.snapAngleToleranceDeg,
          minDragPx: d.minDragPx,
        }),
      )
    },
    [],
  )

  const openEditSession = useCallback(
    (sketchFeatureId: string, baseline: ProfilePayload, frame: PlaneFrameTS, target: SessionTarget) => {
      const d = depsRef.current
      setClosing(false)
      setSession(
        openEdit(sketchFeatureId, baseline, frame, target, {
          snapAngleToleranceDeg: d.snapAngleToleranceDeg,
          minDragPx: d.minDragPx,
        }),
      )
    },
    [],
  )

  const place = useCallback((uv: DrawnPoint, opts?: PlaceOptions) => {
    setSession((s) => (s === null ? s : commitPoint(s, uv, opts)))
  }, [])

  const cursor = useCallback((uv: DrawnPoint | null) => {
    setSession((s) => (s === null ? s : moveCursor(s, uv)))
  }, [])

  const setTool = useCallback((kind: ProfileToolKind) => {
    setSession((s) => (s === null ? s : setSessionTool(s, kind)))
  }, [])

  const finishTool = useCallback((opts?: { closed?: boolean }) => {
    setSession((s) => (s === null ? s : endTool(s, opts)))
  }, [])

  const abandonRun = useCallback(() => {
    setSession((s) => (s === null ? s : abandonSessionRun(s)))
  }, [])

  const undo = useCallback(() => {
    setSession((s) => (s === null ? s : undoLastPart(s)))
  }, [])

  const closingRef = useRef(false)
  const close = useCallback(() => {
    const d = depsRef.current
    if (closingRef.current) return // single-flight: one terminal in motion
    setSession((s) => {
      if (s === null) return s
      // W-2: Close SETTLES an endable open chain run first — OK straight
      // after click·click (no end gesture) commits the drawn line rather
      // than silently discarding it. endTool's own rule still drops a lone
      // stray click, so an empty create still coincides with Cancel.
      const settled = s.tool.pending.length > 0 ? endTool(s) : s
      // Codex7 B2: terminal-start revalidation of the CAPTURED tuple — the
      // mid-flight check in the runner cannot see a retarget that happened
      // BEFORE Close was pressed.
      const staleness = d.validateTarget?.(settled.target) ?? null
      if (staleness !== null) {
        return applyPreview(settled, { preview: null, refusal: { message: staleness } })
      }
      const intent = commitIntent(settled, settled.target.partNumber)
      if (intent === null) {
        // A create session with nothing drawn has no transaction at all —
        // Close and Cancel coincide, which is the correct behaviour.
        requester.cancel()
        return null
      }
      // The session SURVIVES the round trip: only confirmClosed()/
      // commitFailed() resolve it (Codex6 B2 — a failed commit must leave a
      // recoverable drawing, and a cleared session cannot be recovered).
      closingRef.current = true
      setClosing(true)
      d.onCommit?.(intent, settled.target)
      return settled
    })
  }, [requester])

  const confirmClosed = useCallback(() => {
    closingRef.current = false
    setClosing(false)
    setSession(null)
    requester.cancel()
  }, [requester])

  const commitFailed = useCallback((message: string) => {
    closingRef.current = false
    setClosing(false)
    setSession((s) =>
      s === null ? s : applyPreview(s, { preview: null, refusal: { message } }),
    )
  }, [])

  const cancel = useCallback(() => {
    // Codex8 B1 (defense in depth): a session whose Close is writing OWNS
    // the busy state — cancelling locally cannot cancel the transaction, it
    // can only orphan it. The terminal resolves through confirmClosed()/
    // commitFailed(); if the bridge wedges, its 15s timeout reaches
    // commitFailed and Cancel works again.
    if (closingRef.current) {
      return {
        wrote: false as const,
        preservedFeatureId:
          session?.owner.kind === 'edit' ? session.owner.sketchFeatureId : null,
      }
    }
    const outcome = session === null ? { wrote: false as const, preservedFeatureId: null } : cancelSession(session)
    setClosing(false)
    setSession(null)
    requester.cancel()
    return outcome
  }, [session, requester])

  // Reference-stable per PREVIEW, not per session change: cursor motion and
  // chain clicks re-derive the mode every time, and the viewport uses this
  // reference to skip rebuilding the (sprite-heavy) solved overlay when only
  // the live chain moved.
  const preview = session?.preview ?? null
  const geometry = useMemo(() => previewGeometry(preview), [preview])

  const mode = useMemo<SketchInteractionMode | null>(() => {
    if (session === null) return null
    return {
      kind: 'profile',
      frame: session.frame,
      geometry,
      // An EDIT session owns its committed feature: the viewport suppresses
      // that feature's committed overlay while the live preview replaces it,
      // and restores it the moment the session ends (Codex6 B1).
      ownedFeatureId: session.owner.kind === 'edit' ? session.owner.sketchFeatureId : null,
      // W-2: the in-progress chain — DRAWN nominals, display-only. The engine
      // preview still updates per completed shape and stays the solve
      // authority; this echo only makes the run visible while it is drawn.
      chain:
        session.tool.kind === 'line' && session.tool.pending.length > 0
          ? { pending: session.tool.pending, cursor: session.tool.cursor }
          : null,
    }
  }, [session, geometry])

  return {
    active: session !== null,
    session,
    closing,
    refusal: session?.refusal ?? null,
    mode,
    openCreateSession,
    openEditSession,
    setTool,
    place,
    cursor,
    finishTool,
    hasRun: session !== null && sessionHasRun(session),
    abandonRun,
    undo,
    close,
    confirmClosed,
    commitFailed,
    cancel,
  }
}
