/**
 * THE authoring session (S2; arc 20260714-3 D-S4) — ONE discriminated store
 * for every manual authoring surface. Exactly one session exists at a time:
 *
 *   idle ── startSketch ──────────────▶ sketch (stepwise: OK commits the
 *     │                                   sketch ALONE → `Sketch N` + wire)
 *     ├── startExtrude(preselected) ──▶ extrude:depth   (entry A — a sketch
 *     │                                   was selected in the tree)
 *     └── startExtrude(null) ─────────▶ extrude:select  (entry B — pick an
 *                        │                unconsumed sketch, or…)
 *                        └── beginChainedSketch ──▶ sketch(chained) ──OK──▶
 *                             extrude:depth with the PENDING drawn rings —
 *                             committed as ONE draft [sketch, extrude($fromOp)]
 *
 * It replaces BOTH predecessors (featureSession.ts — the rectangle dashboard's
 * store — and sketchStore.ts): one mode discriminant, one cancel, one busy
 * truth for every gate. PURE store discipline (create*Store +
 * useSyncExternalStore, new ref only on real change); all async effects live
 * in the surfaces via the ONE sessionLifecycle (the single commit owner).
 */
import { useSyncExternalStore } from 'react'
import type { Pt } from '../sketch/contour'
import type { CircleDims, PlaneOrientation, RectDims, SketchSupport } from './backend'
import { normalizeCircle, normalizeRectangle } from './backend'
import type { AuthoringTarget, SelectorCapture } from './partContext'
import type { EditableParameter } from './inspectDecode'

export type SketchPhase = 'drawing' | 'closed' | 'busy' | 'committed' | 'error'
export type ExtrudePhase = 'editing' | 'busy' | 'error'

/** What the extrude will consume: an already-committed unconsumed sketch, or
 *  the rings just drawn in the chained in-place sketch (not yet Truth — they
 *  commit WITH the extrude in one draft via the $fromOp handshake). */
export type ExtrudeSource =
  | { kind: 'committed'; sketchId: string }
  | { kind: 'pending'; plane: PlaneOrientation; points: Pt[]; bulges: number[] }
  /** The chained RECTANGLE hand-back (R3/D-R9) — revolve's create-in-place
   *  path; plane pinned xy (the engine's v1 bound). */
  | { kind: 'pending_rectangle'; rect: RectDims }

/** The DISCRIMINATED sketch tool (arc 20260715-1 Codex2 N2): contour drawing
 *  state and rectangle two-click state cannot mix — invalid cross-tool fields
 *  are unrepresentable. */
export type SketchTool =
  | {
      kind: 'contour'
      points: Pt[]
      /** SK-C0 D-C1: bulge per segment points[i]→points[i+1] (0 = line); the
       *  CLOSING segment stays a line in the v1 pad. */
      bulges: number[]
      /** Waiting for the 3-point-arc VIA click of the just-placed segment. */
      awaitingVia: boolean
      cursor: Pt | null
      closed: boolean
    }
  | { kind: 'rectangle'; anchor: Pt | null; cursor: Pt | null; rect: RectDims | null }
  | { kind: 'circle'; center: Pt | null; cursor: Pt | null; circle: CircleDims | null }

export interface SketchMeta {
  partName?: string | null
  partNumber?: string | null
  plane?: PlaneOrientation
  /** Which tool the pad opens with (default contour). */
  tool?: SketchTool['kind']
  targetPart?: { number: string; name: string } | null
  /** The SIGNED authority tuple captured at start (Codex4 B1.4) — must be
   *  present whenever `targetPart` is; the terminal commit revalidates it. */
  targetAuth?: AuthoringTarget | null
  /** SK-C1.0 Codex4/Codex5 B2: the LIVE Part-context generation at entry —
   *  REQUIRED (no sentinel defaults; every entry path captures it). */
  generation: number
}

export interface SketchSubstate {
  mode: 'sketch'
  /** Chained = launched from the base-feature select step; OK returns the
   *  drawing to that session instead of committing the sketch alone. */
  chainToExtrude: boolean
  /** The chained base-feature session's shape (restored at hand-back). */
  chainedFeature: 'extrude' | 'revolve'
  chainedDepthMm: number
  chainedAxis: 'x' | 'y'
  tool: SketchTool
  /** SK-C0 D-C3: the primitive being drawn commits as a construction guide. */
  construction: boolean
  phase: SketchPhase
  message: string | null
  objectRef: string | null
  partName: string | null
  partNumber: string | null
  /** LEGACY principal orientation (the chained/pending paths are
   *  principal-only by design); `support` is THE authority (S3). */
  plane: PlaneOrientation
  /** S3: the sketch's support — principal datum or engine-planar face. */
  support: SketchSupport
  targetPart: { number: string; name: string } | null
  targetAuth: AuthoringTarget | null
  /** SK-C1.0 Codex4 B2: the ENTRY generation, carried unconditionally from
   *  planePick/chained entry — the App invalidates on mismatch. */
  generation: number
}

interface ExtrudeSubstate {
  /** P (arc 20260717-2): the sequential operation — add (boss) | cut
   *  (pocket). Ignored by the BASE commit (always add) and by revolve. */
  operation: "add" | "cut"
  mode: 'extrude'
  /** The base-feature discriminant (arc 20260715-1 R3; Codex2 Q1): ONE
   *  session shape for extrude AND revolve — shared capture/cancel/lifecycle/
   *  source-selection; the feature selects the parameter editor (depth vs
   *  axis). Sweep stays out until its own contract exists. */
  feature: 'extrude' | 'revolve'
  step: 'select' | 'depth'
  source: ExtrudeSource | null
  /** The FULL authority tuple captured at session start (Codex3 B2 / Codex4
   *  B1.4) — the terminal commit revalidates workspace + Part number +
   *  generation against the live context, so a session can never cross Parts
   *  (or generations), even past an accidental gate bypass. */
  target: AuthoringTarget | null
  depthMm: number
  /** Revolve only: the chosen axis (engine vocabulary, structural). */
  axis: 'x' | 'y'
  phase: ExtrudePhase
  message: string | null
}

/** A topology-selection feature session (arc 20260715-1 R4): Round (fillet)
 *  or Chamfer over a CAPTURED sharp edge. The capture is session state — a
 *  later UI selection change never retargets (D-R8). */
interface EdgeFeatureSubstate {
  mode: 'edgeFeature'
  feature: 'fillet' | 'chamfer'
  capture: SelectorCapture
  /** radius_mm (fillet) / distance_mm (chamfer). */
  valueMm: number
  phase: ExtrudePhase
  message: string | null
}

/** The Hole session (R5): a CAPTURED face + the through-hole parameters.
 *  Wall-vs-cap is engine-authoritative pre-commit (P2's named limitation). */
interface HoleFeatureSubstate {
  mode: 'holeFeature'
  capture: SelectorCapture
  diameterMm: number
  centerXMm: number
  centerYMm: number
  phase: ExtrudePhase
  message: string | null
}

/** The edit-dimension session (R6): ONE catalogued parameter of ONE
 *  committed feature (identity-preserving records — Codex2 N3); the engine's
 *  regenerating `adjust_feature_parameter` is the authority. */
interface EditParameterSubstate {
  mode: 'editParameter'
  target: AuthoringTarget
  featureId: string
  parameters: EditableParameter[]
  /** The chosen catalogued parameter name (the mutation addresses by name). */
  paramName: string
  value: number
  phase: ExtrudePhase
  message: string | null
}

/** The plane-pick continuation (arc 20260716-2 SK-C1.0, Codex1 B4.1): what
 *  resolving/cancelling the pick flows into. `chained` captures the WHOLE
 *  base-feature substate so Escape restores the session VERBATIM. */
export type PlanePickContinuation =
  | { type: 'sketch'; meta: Omit<SketchMeta, 'generation'> }
  | { type: 'chained'; captured: ExtrudeSubstate; selectedSketchId: string | null; tool: SketchTool['kind']; targetPart: { number: string; name: string } | null }
  // ADR/0044 A3 / pass sketch-place-1 (Codex1 B4): the References PLACEMENT
  // session — the support pick flows into the placement-confirm substate.
  | { type: 'placement'; targetPart: { number: string; name: string } | null }

/** The placement-confirm substate (A3.6.1/A3.6.2): the Creo two-reference
 *  dialog — support picked, the engine's canonical default completed, the
 *  user may change ref/orientation/normal side, then EXPLICIT accept. One
 *  substate serves CREATE (References) and REDEFINE (the tree's ✎). */
/** The four placement facts in session vocabulary (the persisted record's
 *  camelCase twin — the op builder maps back to wire names). */
export interface PlacementFacts {
  support: PlaneOrientation
  orientationRef: PlaneOrientation
  orientation: 'right' | 'top' | 'left' | 'bottom'
  normalSide: 'positive' | 'negative'
}

export interface PlacementSubstate extends PlacementFacts {
  mode: 'placement'
  /** null = CREATE; else REDEFINE of this committed 0.2.1 sketch (seeded
   *  from its persisted record — omission-keeps is derived by diffing). */
  redefineOf: { featureId: string; current: PlacementFacts } | null
  targetPart: { number: string; name: string } | null
  generation: number
  busy: boolean
  message: string | null
}

/** The engine's A3.3 canonical default reference per support (the transient
 *  mirror — `sketch_placement.DEFAULT_ORIENTATION_REF` is the authority). */
export const PLACEMENT_DEFAULT_REF: Record<PlaneOrientation, PlaneOrientation> = {
  xy: 'yz',
  yz: 'zx',
  zx: 'xy',
}

/** The in-viewport sketch-plane pick (SK-C1.0 S1): a FIRST-CLASS state of the
 *  ONE session — entered synchronously when Sketch starts, so every global
 *  gate sees active work. Carries the generation captured at entry; a
 *  generation/workspace change cancels fail-closed (Codex1 B4.2). */
interface PlanePickSubstate {
  mode: 'planePick'
  continuation: PlanePickContinuation
  generation: number
  message: string | null
}

export type AuthoringSessionState = (
  | { mode: 'idle' }
  | PlanePickSubstate
  | PlacementSubstate
  | SketchSubstate
  | ExtrudeSubstate
  | EdgeFeatureSubstate
  | HoleFeatureSubstate
  | EditParameterSubstate
) & {
  /** The tree-selected unconsumed sketch (survives idle — it is what makes
   *  Extrude entry A possible). Cleared when consumed or deselected. */
  selectedSketchId: string | null
}

export interface AuthoringSessionStore {
  getSnapshot(): AuthoringSessionState
  subscribe(fn: () => void): () => void
  // -- selection (tree) --
  selectSketch(id: string | null): void
  // -- the plane-pick mode (SK-C1.0 S1) --
  /** Enter the pick for a STANDALONE sketch (from idle). The pick's OWN
   *  generation capture is the authority the sketch inherits. */
  startPlanePick(meta: Omit<SketchMeta, 'generation'>, generation: number): void
  /** Enter the pick from a base-feature SELECT step ("New sketch…") — the
   *  current extrude substate is captured for verbatim restore on cancel. */
  startChainedPlanePick(generation: number, tool?: SketchTool['kind'], targetPart?: { number: string; name: string } | null): void
  /** A plane was picked (viewport quad / tree row / list dialog) — flow into
   *  the continuation. S1 resolves principal planes; face targets are S3. */
  resolvePlanePick(target: PlaneOrientation | { faceId: string; frame: import('../sketch/planeFrame').PlaneFrameTS }): void
  /** Escape/cancel: standalone → idle; chained → the captured base-feature
   *  session restored verbatim (Codex1 B4.6). */
  cancelPlanePick(): void
  // -- the placement session (A3; pass sketch-place-1) --
  /** References: enter the support pick whose resolution flows into the
   *  placement-confirm substate. */
  startPlacementPick(generation: number, targetPart: { number: string; name: string } | null): void
  /** The tree's ✎ on a committed 0.2.1 sketch: open the confirm substate
   *  seeded from the PERSISTED placement (redefine; keep-on-omission is
   *  derived by diffing at accept). */
  startPlacementRedefine(
    featureId: string,
    current: PlacementFacts,
    generation: number,
    targetPart: { number: string; name: string } | null,
  ): void
  /** Change one member. A support change that collides with the current
   *  reference auto-repairs the reference to the engine's default for the
   *  new support — the UI never holds a parallel (invalid) pair. */
  setPlacementMember(member: 'support' | 'orientationRef' | 'orientation' | 'normalSide', value: string): void
  setPlacementBusy(busy: boolean): void
  failPlacement(message: string): void
  cancelPlacement(): void
  /** SK-C1.0 Codex4 B2: CONTEXT INVALIDATION — distinct from user cancel.
   *  A generation/workspace change terminates planePick AND sketch to a safe
   *  idle (stale selection cleared); it NEVER restores a captured chained
   *  session from the old generation. */
  invalidateForGeneration(): void
  // -- sketch mode --
  startSketch(meta: SketchMeta): void
  addPoint(p: Pt): void
  /** SK-C0: set the bulge of the LAST placed segment (the 3-point-arc via). */
  setLastBulge(b: number): void
  setAwaitingVia(on: boolean): void
  /** Circle tool: place the center, then a rim point. */
  placeCirclePoint(p: Pt): void
  /** Toggle construction-guide mode for the primitive being drawn (D-C3). */
  toggleConstruction(): void
  setCursor(p: Pt | null): void
  undoPoint(): void
  closeRing(): void
  reopen(): void
  /** Switch the sketch tool (contour <-> rectangle); resets the drawing. */
  switchTool(kind: SketchTool['kind']): void
  /** Rectangle tool: place the anchor, then the opposite corner (normalized). */
  placeRectCorner(p: Pt): void
  setSketchPhase(phase: SketchPhase, message?: string | null): void
  // -- the base-feature mode (extrude | revolve) --
  startExtrude(
    preselectedSketchId: string | null,
    target?: AuthoringTarget | null,
    defaultDepthMm?: number,
    feature?: 'extrude' | 'revolve',
  ): void
  chooseCommittedSketch(sketchId: string): void
  setExtrudeOperation(operation: 'add' | 'cut'): void
  beginChainedSketch(
    plane: PlaneOrientation,
    target: { number: string; name: string } | null,
    tool: SketchTool['kind'] | undefined,
    generation: number,
  ): void
  /** Chained sketch OK: carry the drawn rings back into the extrude session. */
  finishChainedSketch(): void
  // -- the edit-dimension mode --
  startEditParameter(target: AuthoringTarget, featureId: string, parameters: EditableParameter[]): void
  chooseEditParameter(paramName: string): void
  setEditValue(value: number): void
  setEditPhase(phase: ExtrudePhase, message?: string | null): void
  // -- the hole mode --
  startHoleFeature(capture: SelectorCapture, defaults?: { diameterMm?: number }): void
  setHoleParam(name: 'diameterMm' | 'centerXMm' | 'centerYMm', value: number): void
  setHolePhase(phase: ExtrudePhase, message?: string | null): void
  // -- the edge-feature mode (Round | Chamfer) --
  startEdgeFeature(feature: 'fillet' | 'chamfer', capture: SelectorCapture, defaultValueMm?: number): void
  setEdgeValue(valueMm: number): void
  setEdgeFeaturePhase(phase: ExtrudePhase, message?: string | null): void
  setDepth(depthMm: number): void
  /** Revolve: choose the axis (the panel greys crossing axes from the
   *  decoded rectangle — the engine's straddle rule stays authoritative). */
  setAxis(axis: 'x' | 'y'): void
  setExtrudePhase(phase: ExtrudePhase, message?: string | null): void
  /** End the session (any mode) → idle. The surfaces own backend rollback. */
  cancel(): void
}

const IDLE: AuthoringSessionState = { mode: 'idle', selectedSketchId: null }

const SKETCH_DEFAULTS = {
  mode: 'sketch' as const,
  phase: 'drawing' as SketchPhase,
  message: null,
  objectRef: null,
  partName: null,
  partNumber: null,
}

const freshTool = (kind: SketchTool['kind']): SketchTool =>
  kind === 'rectangle'
    ? { kind: 'rectangle', anchor: null, cursor: null, rect: null }
    : kind === 'circle'
      ? { kind: 'circle', center: null, cursor: null, circle: null }
      : { kind: 'contour', points: [], bulges: [], awaitingVia: false, cursor: null, closed: false }

export function createAuthoringSessionStore(): AuthoringSessionStore {
  let state = IDLE
  const listeners = new Set<() => void>()
  const emit = (next: AuthoringSessionState) => {
    state = next
    listeners.forEach((l) => l())
  }
  const sketch = () => (state.mode === 'sketch' ? state : null)
  const extrude = () => (state.mode === 'extrude' ? state : null)

  return {
    getSnapshot: () => state,
    subscribe: (fn) => {
      listeners.add(fn)
      return () => listeners.delete(fn)
    },

    selectSketch: (id) => {
      if (state.selectedSketchId === id) return
      emit({ ...state, selectedSketchId: id })
    },

    startPlanePick: (meta, generation) => {
      if (state.mode !== 'idle') return
      emit({
        mode: 'planePick',
        continuation: { type: 'sketch', meta },
        generation,
        message: null,
        selectedSketchId: state.selectedSketchId,
      })
    },
    startChainedPlanePick: (generation, tool = 'contour', targetPart = null) => {
      const e = extrude()
      if (!e || e.phase === 'busy') return
      const { selectedSketchId, ...captured } = e
      emit({
        mode: 'planePick',
        continuation: { type: 'chained', captured, selectedSketchId, tool, targetPart },
        generation,
        message: null,
        selectedSketchId,
      })
    },
    resolvePlanePick: (target) => {
      if (state.mode !== 'planePick') return
      const c = state.continuation
      const isFace = typeof target !== 'string'
      // the CHAINED and PLACEMENT continuations are principal-only (the pick
      // surfaces never offer faces there; this guard keeps it true — A3.2's
      // BS-1 domain for placement)
      if (isFace && (c.type === 'chained' || c.type === 'placement')) return
      if (c.type === 'placement') {
        const support = target as PlaneOrientation
        emit({
          mode: 'placement',
          support,
          orientationRef: PLACEMENT_DEFAULT_REF[support],
          orientation: 'right',
          normalSide: 'positive',
          redefineOf: null,
          targetPart: c.targetPart,
          generation: state.generation,
          busy: false,
          message: null,
          selectedSketchId: state.selectedSketchId,
        })
        return
      }
      const plane: PlaneOrientation = isFace ? 'xy' : target
      const support: SketchSupport = isFace
        ? { kind: 'face', faceId: target.faceId, frame: target.frame }
        : { kind: 'principal', orientation: target }
      if (c.type === 'sketch') {
        emit({
          ...SKETCH_DEFAULTS,
          chainToExtrude: false,
          chainedFeature: 'extrude',
          chainedDepthMm: 10,
          chainedAxis: 'x',
          tool: freshTool(c.meta.tool ?? 'contour'),
          construction: false,
          plane,
          support,
          generation: state.generation,
          partName: c.meta.partName?.trim() || null,
          partNumber: c.meta.partNumber?.trim() || null,
          targetPart: c.meta.targetPart ?? null,
          targetAuth: c.meta.targetAuth ?? null,
          selectedSketchId: state.selectedSketchId,
        })
        return
      }
      // chained: the same hand-off beginChainedSketch performs, sourced from
      // the CAPTURED session (the authority tuple is the capture's — B4.1).
      emit({
        ...SKETCH_DEFAULTS,
        chainToExtrude: true,
        chainedFeature: c.captured.feature,
        chainedDepthMm: c.captured.depthMm,
        chainedAxis: c.captured.axis,
        tool: freshTool(c.tool),
        construction: false,
        plane,
        support,
        generation: state.generation,
        targetPart: c.targetPart,
        targetAuth: c.captured.target,
        selectedSketchId: state.selectedSketchId,
      })
    },
    invalidateForGeneration: () => {
      if (state.mode !== 'planePick' && state.mode !== 'sketch' && state.mode !== 'placement') return
      // FAIL-CLOSED: never the chained restore (that session belongs to the
      // OLD generation); the part-scoped selection is stale too. A placement
      // capture (create OR redefine) dies whole with its generation (B4).
      emit({ mode: 'idle', selectedSketchId: null })
    },
    cancelPlanePick: () => {
      if (state.mode !== 'planePick') return
      const c = state.continuation
      if (c.type === 'chained') {
        emit({ ...c.captured, selectedSketchId: c.selectedSketchId })
        return
      }
      emit({ mode: 'idle', selectedSketchId: state.selectedSketchId })
    },

    startPlacementPick: (generation, targetPart) => {
      if (state.mode !== 'idle') return
      emit({
        mode: 'planePick',
        continuation: { type: 'placement', targetPart },
        generation,
        message: null,
        selectedSketchId: state.selectedSketchId,
      })
    },
    startPlacementRedefine: (featureId, current, generation, targetPart) => {
      if (state.mode !== 'idle') return
      emit({
        mode: 'placement',
        ...current,
        redefineOf: { featureId, current },
        targetPart,
        generation,
        busy: false,
        message: null,
        selectedSketchId: state.selectedSketchId,
      })
    },
    setPlacementMember: (member, value) => {
      if (state.mode !== 'placement' || state.busy) return
      const next = { ...state, [member]: value } as typeof state
      // never hold the invalid parallel pair: a colliding support change
      // auto-repairs the reference to the ENGINE default for that support
      if (member === 'support' && next.orientationRef === next.support) {
        next.orientationRef = PLACEMENT_DEFAULT_REF[next.support]
      }
      if (member === 'orientationRef' && next.orientationRef === next.support) return
      emit({ ...next, message: null })
    },
    setPlacementBusy: (busy) => {
      if (state.mode !== 'placement') return
      emit({ ...state, busy, message: busy ? null : state.message })
    },
    failPlacement: (message) => {
      if (state.mode !== 'placement') return
      emit({ ...state, busy: false, message })
    },
    cancelPlacement: () => {
      if (state.mode !== 'placement' || state.busy) return
      emit({ mode: 'idle', selectedSketchId: state.selectedSketchId })
    },

    startSketch: (meta) => {
      if (state.mode !== 'idle') return
      emit({
        ...SKETCH_DEFAULTS,
        chainToExtrude: false,
        chainedFeature: 'extrude',
        chainedDepthMm: 10,
        chainedAxis: 'x',
        tool: freshTool(meta?.tool ?? 'contour'),
        construction: false,
        plane: meta?.plane ?? 'xy',
        support: { kind: 'principal', orientation: meta?.plane ?? 'xy' },
        generation: meta.generation,
        partName: meta?.partName?.trim() || null,
        partNumber: meta?.partNumber?.trim() || null,
        targetPart: meta?.targetPart ?? null,
        targetAuth: meta?.targetAuth ?? null,
        selectedSketchId: state.selectedSketchId,
      })
    },
    addPoint: (p) => {
      const s = sketch()
      if (!s || s.tool.kind !== 'contour' || s.tool.closed || s.phase === 'busy') return
      const bulges = s.tool.points.length >= 1 ? [...s.tool.bulges, 0] : s.tool.bulges
      emit({ ...s, tool: { ...s.tool, points: [...s.tool.points, p], bulges }, message: null })
    },
    setLastBulge: (b) => {
      const s = sketch()
      if (!s || s.tool.kind !== 'contour' || s.phase === 'busy') return
      if (s.tool.bulges.length === 0) return
      const bulges = [...s.tool.bulges]
      bulges[bulges.length - 1] = b
      emit({ ...s, tool: { ...s.tool, bulges, awaitingVia: false }, message: null })
    },
    setAwaitingVia: (on) => {
      const s = sketch()
      if (!s || s.tool.kind !== 'contour' || s.phase === 'busy') return
      emit({ ...s, tool: { ...s.tool, awaitingVia: on } })
    },
    placeCirclePoint: (p) => {
      const s = sketch()
      if (!s || s.tool.kind !== 'circle' || s.phase === 'busy' || s.tool.circle !== null) return
      if (s.tool.center === null) {
        emit({ ...s, tool: { ...s.tool, center: p }, message: null })
        return
      }
      const circle = normalizeCircle(s.tool.center, p)
      if (!circle) return // degenerate radius — ignore the click
      emit({ ...s, tool: { ...s.tool, circle, cursor: null }, phase: 'closed', message: null })
    },
    toggleConstruction: () => {
      const s = sketch()
      if (!s || s.phase === 'busy') return
      emit({ ...s, construction: !s.construction })
    },
    setCursor: (p) => {
      const s = sketch()
      if (!s) return
      if (s.tool.kind === 'contour') {
        if (s.tool.closed) return
        emit({ ...s, tool: { ...s.tool, cursor: p } })
      } else if (s.tool.kind === 'rectangle') {
        if (s.tool.rect !== null) return
        emit({ ...s, tool: { ...s.tool, cursor: p } })
      } else {
        if (s.tool.circle !== null) return
        emit({ ...s, tool: { ...s.tool, cursor: p } })
      }
    },
    undoPoint: () => {
      const s = sketch()
      if (!s || s.tool.kind !== 'contour' || s.phase === 'busy' || s.tool.points.length === 0) return
      emit({
        ...s,
        tool: {
          ...s.tool,
          points: s.tool.points.slice(0, -1),
          bulges: s.tool.bulges.length ? s.tool.bulges.slice(0, -1) : s.tool.bulges,
          awaitingVia: false,
        },
        message: null,
      })
    },
    closeRing: () => {
      const s = sketch()
      if (!s || s.tool.kind !== 'contour' || s.phase === 'busy' || s.tool.points.length < 3) return
      emit({ ...s, tool: { ...s.tool, closed: true, cursor: null }, phase: 'closed', message: null })
    },
    reopen: () => {
      const s = sketch()
      if (!s || s.phase === 'busy') return
      if (s.tool.kind === 'contour') {
        emit({ ...s, tool: { ...s.tool, closed: false }, phase: 'drawing', message: null })
      } else {
        emit({ ...s, tool: freshTool(s.tool.kind), phase: 'drawing', message: null })
      }
    },
    switchTool: (kind) => {
      const s = sketch()
      if (!s || s.phase === 'busy' || s.tool.kind === kind) return
      emit({ ...s, tool: freshTool(kind), phase: 'drawing', message: null })
    },
    placeRectCorner: (p) => {
      const s = sketch()
      if (!s || s.tool.kind !== 'rectangle' || s.phase === 'busy' || s.tool.rect !== null) return
      if (s.tool.anchor === null) {
        emit({ ...s, tool: { ...s.tool, anchor: p }, message: null })
        return
      }
      // The second click NORMALIZES (Codex2 N1): min-corner + abs dims; a
      // degenerate dimension refuses and keeps the anchor for a retry.
      const rect = normalizeRectangle(s.tool.anchor, p)
      if (rect === null) {
        emit({ ...s, message: 'zero-size rectangle — click a different opposite corner' })
        return
      }
      emit({ ...s, tool: { ...s.tool, rect, cursor: null }, phase: 'closed', message: null })
    },
    setSketchPhase: (phase, message = null) => {
      const s = sketch()
      if (!s) return
      if (s.phase === phase && s.message === message) return
      emit({ ...s, phase, message })
    },

    startExtrude: (preselectedSketchId, target = null, defaultDepthMm = 10, feature = 'extrude') => {
      if (state.mode !== 'idle') return
      emit({
        mode: 'extrude',
        feature,
        step: preselectedSketchId ? 'depth' : 'select',
        operation: 'add',
        source: preselectedSketchId ? { kind: 'committed', sketchId: preselectedSketchId } : null,
        target,
        depthMm: defaultDepthMm,
        axis: 'x',
        phase: 'editing',
        message: null,
        selectedSketchId: state.selectedSketchId,
      })
    },
    setExtrudeOperation: (operation) => {
      const e = extrude()
      if (!e || e.phase === 'busy') return
      if (e.feature !== 'extrude') return // revolve has no operation
      emit({ ...e, operation })
    },
    chooseCommittedSketch: (sketchId) => {
      const e = extrude()
      if (!e || e.phase === 'busy') return
      emit({ ...e, step: 'depth', source: { kind: 'committed', sketchId }, message: null })
    },
    beginChainedSketch: (plane, target, tool = 'contour', generation) => {
      const e = extrude()
      if (!e || e.phase === 'busy') return
      // The base-feature session HANDS OFF to the sketch surface; OK hands
      // back. The authority tuple is the SESSION's capture (Codex4 B1.4) —
      // never re-read live at the hand-off. Revolve pins tool=rectangle and
      // plane=xy at the caller (D-R9); the chained feature survives via
      // chainedFeature so the hand-back restores the SAME session shape.
      emit({
        ...SKETCH_DEFAULTS,
        chainToExtrude: true,
        chainedFeature: e.feature,
        chainedDepthMm: e.depthMm,
        chainedAxis: e.axis,
        tool: freshTool(tool),
        construction: false,
        plane,
        support: { kind: 'principal', orientation: plane },
        generation,
        targetPart: target,
        targetAuth: e.target,
        selectedSketchId: state.selectedSketchId,
      })
    },
    finishChainedSketch: () => {
      const s = sketch()
      if (!s || !s.chainToExtrude) return
      const source: ExtrudeSource | null =
        s.tool.kind === 'contour' && s.tool.closed
          ? { kind: 'pending', plane: s.plane, points: s.tool.points, bulges: s.tool.bulges }
          : s.tool.kind === 'rectangle' && s.tool.rect !== null
            ? { kind: 'pending_rectangle', rect: s.tool.rect }
            : null
      if (source === null) return // the drawing is not complete
      emit({
        mode: 'extrude',
        feature: s.chainedFeature,
        step: 'depth',
        operation: 'add',  // a chained source is datum-bound — base-only
        source,
        // The captured TUPLE survives the sketch hand-off (Codex4 B1.4).
        target: s.targetAuth,
        depthMm: s.chainedDepthMm,
        axis: s.chainedAxis,
        phase: 'editing',
        message: null,
        selectedSketchId: s.selectedSketchId,
      })
    },
    startEditParameter: (target, featureId, parameters) => {
      if (state.mode !== 'idle' || parameters.length === 0) return
      emit({
        mode: 'editParameter',
        target,
        featureId,
        parameters,
        paramName: parameters[0].name,
        value: parameters[0].value,
        phase: 'editing',
        message: null,
        selectedSketchId: state.selectedSketchId,
      })
    },
    chooseEditParameter: (paramName) => {
      if (state.mode !== 'editParameter' || state.phase === 'busy') return
      const p = state.parameters.find((x) => x.name === paramName)
      if (!p) return // only CATALOGUED names are addressable (N3)
      emit({ ...state, paramName, value: p.value, phase: 'editing', message: null })
    },
    setEditValue: (value) => {
      if (state.mode !== 'editParameter' || state.phase === 'busy') return
      emit({ ...state, value, phase: 'editing', message: null })
    },
    setEditPhase: (phase, message = null) => {
      if (state.mode !== 'editParameter') return
      if (state.phase === phase && state.message === message) return
      emit({ ...state, phase, message })
    },
    startHoleFeature: (capture, defaults) => {
      if (state.mode !== 'idle') return
      emit({
        mode: 'holeFeature',
        capture,
        diameterMm: defaults?.diameterMm ?? 5,
        centerXMm: 0,
        centerYMm: 0,
        phase: 'editing',
        message: null,
        selectedSketchId: state.selectedSketchId,
      })
    },
    setHoleParam: (name, value) => {
      if (state.mode !== 'holeFeature' || state.phase === 'busy') return
      emit({ ...state, [name]: value, phase: 'editing', message: null })
    },
    setHolePhase: (phase, message = null) => {
      if (state.mode !== 'holeFeature') return
      if (state.phase === phase && state.message === message) return
      emit({ ...state, phase, message })
    },
    startEdgeFeature: (feature, capture, defaultValueMm = 2) => {
      if (state.mode !== 'idle') return
      emit({
        mode: 'edgeFeature',
        feature,
        capture,
        valueMm: defaultValueMm,
        phase: 'editing',
        message: null,
        selectedSketchId: state.selectedSketchId,
      })
    },
    setEdgeValue: (valueMm) => {
      if (state.mode !== 'edgeFeature' || state.phase === 'busy') return
      emit({ ...state, valueMm, phase: 'editing', message: null })
    },
    setEdgeFeaturePhase: (phase, message = null) => {
      if (state.mode !== 'edgeFeature') return
      if (state.phase === phase && state.message === message) return
      emit({ ...state, phase, message })
    },
    setDepth: (depthMm) => {
      const e = extrude()
      if (!e || e.phase === 'busy') return
      emit({ ...e, depthMm, phase: 'editing', message: null })
    },
    setAxis: (axis) => {
      const e = extrude()
      if (!e || e.phase === 'busy') return
      emit({ ...e, axis, phase: 'editing', message: null })
    },
    setExtrudePhase: (phase, message = null) => {
      const e = extrude()
      if (!e) return
      if (e.phase === phase && e.message === message) return
      emit({ ...e, phase, message })
    },

    cancel: () => {
      if (state.mode === 'idle') return
      emit({ ...IDLE, selectedSketchId: state.selectedSketchId })
    },
  }
}

export function useAuthoringSession(store: AuthoringSessionStore): AuthoringSessionState {
  return useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot)
}
