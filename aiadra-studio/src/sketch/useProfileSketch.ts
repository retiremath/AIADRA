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
  applyPreview,
  cancel as cancelSession,
  commitIntent,
  commitPoint,
  endTool,
  moveCursor,
  openCreate,
  openEdit,
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
  workspaceId: string | null
  partNumber: string | null
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
  onCommit?: (intent: { kind: string; params: Record<string, unknown> }) => void
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
  openCreateSession(placement: SketchPlacementInput, frame: PlaneFrameTS): void
  openEditSession(sketchFeatureId: string, baseline: ProfilePayload, frame: PlaneFrameTS): void
  setTool(kind: ProfileToolKind): void
  place(uv: { u: number; v: number }): void
  cursor(uv: { u: number; v: number } | null): void
  /** End an open-ended tool (the polyline's Enter / double-click). */
  finishTool(opts?: { closed?: boolean }): void
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
      }>({
        run: (req) => {
          const { workspaceId, partNumber } = depsRef.current
          if (!workspaceId || !partNumber) {
            return Promise.resolve({
              preview: null,
              refusal: { message: 'no open workspace or active Part' },
            })
          }
          return run(
            workspaceId,
            partNumber,
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
    requester.request(req)
  }, [session, requester])

  useEffect(() => () => requester.cancel(), [requester])

  const [closing, setClosing] = useState(false)

  const openCreateSession = useCallback(
    (placement: SketchPlacementInput, frame: PlaneFrameTS) => {
      const d = depsRef.current
      setClosing(false)
      setSession(
        openCreate(placement, nextCandidateKey(), frame, {
          snapAngleToleranceDeg: d.snapAngleToleranceDeg,
          minDragPx: d.minDragPx,
        }),
      )
    },
    [],
  )

  const openEditSession = useCallback(
    (sketchFeatureId: string, baseline: ProfilePayload, frame: PlaneFrameTS) => {
      const d = depsRef.current
      setClosing(false)
      setSession(
        openEdit(sketchFeatureId, baseline, frame, {
          snapAngleToleranceDeg: d.snapAngleToleranceDeg,
          minDragPx: d.minDragPx,
        }),
      )
    },
    [],
  )

  const place = useCallback((uv: DrawnPoint) => {
    setSession((s) => (s === null ? s : commitPoint(s, uv)))
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

  const undo = useCallback(() => {
    setSession((s) => (s === null ? s : undoLastPart(s)))
  }, [])

  const closingRef = useRef(false)
  const close = useCallback(() => {
    const d = depsRef.current
    if (closingRef.current) return // single-flight: one terminal in motion
    setSession((s) => {
      if (s === null) return s
      if (!d.partNumber) return s
      const intent = commitIntent(s, d.partNumber)
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
      d.onCommit?.(intent)
      return s
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
    const outcome = session === null ? { wrote: false as const, preservedFeatureId: null } : cancelSession(session)
    closingRef.current = false
    setClosing(false)
    setSession(null)
    requester.cancel()
    return outcome
  }, [session, requester])

  const mode = useMemo<SketchInteractionMode | null>(() => {
    if (session === null) return null
    return {
      kind: 'profile',
      frame: session.frame,
      geometry: previewGeometry(session.preview),
      // An EDIT session owns its committed feature: the viewport suppresses
      // that feature's committed overlay while the live preview replaces it,
      // and restores it the moment the session ends (Codex6 B1).
      ownedFeatureId: session.owner.kind === 'edit' ? session.owner.sketchFeatureId : null,
    }
  }, [session])

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
    undo,
    close,
    confirmClosed,
    commitFailed,
    cancel,
  }
}
