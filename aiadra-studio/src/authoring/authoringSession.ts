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
import type { PlaneOrientation } from './backend'
import type { AuthoringTarget } from './partContext'

export type SketchPhase = 'drawing' | 'closed' | 'busy' | 'committed' | 'error'
export type ExtrudePhase = 'editing' | 'busy' | 'error'

/** What the extrude will consume: an already-committed unconsumed sketch, or
 *  the rings just drawn in the chained in-place sketch (not yet Truth — they
 *  commit WITH the extrude in one draft via the $fromOp handshake). */
export type ExtrudeSource =
  | { kind: 'committed'; sketchId: string }
  | { kind: 'pending'; plane: PlaneOrientation; points: Pt[] }

export interface SketchMeta {
  partName?: string | null
  partNumber?: string | null
  plane?: PlaneOrientation
  targetPart?: { number: string; name: string } | null
  /** The SIGNED authority tuple captured at start (Codex4 B1.4) — must be
   *  present whenever `targetPart` is; the terminal commit revalidates it. */
  targetAuth?: AuthoringTarget | null
}

interface SketchSubstate {
  mode: 'sketch'
  /** Chained = launched from the Extrude select step; OK returns the rings to
   *  the extrude session instead of committing the sketch alone. */
  chainToExtrude: boolean
  points: Pt[]
  cursor: Pt | null
  closed: boolean
  phase: SketchPhase
  message: string | null
  objectRef: string | null
  partName: string | null
  partNumber: string | null
  plane: PlaneOrientation
  targetPart: { number: string; name: string } | null
  targetAuth: AuthoringTarget | null
}

interface ExtrudeSubstate {
  mode: 'extrude'
  step: 'select' | 'depth'
  source: ExtrudeSource | null
  /** The FULL authority tuple captured at session start (Codex3 B2 / Codex4
   *  B1.4) — the terminal commit revalidates workspace + Part number +
   *  generation against the live context, so a session can never cross Parts
   *  (or generations), even past an accidental gate bypass. */
  target: AuthoringTarget | null
  depthMm: number
  phase: ExtrudePhase
  message: string | null
}

export type AuthoringSessionState = ({ mode: 'idle' } | SketchSubstate | ExtrudeSubstate) & {
  /** The tree-selected unconsumed sketch (survives idle — it is what makes
   *  Extrude entry A possible). Cleared when consumed or deselected. */
  selectedSketchId: string | null
}

export interface AuthoringSessionStore {
  getSnapshot(): AuthoringSessionState
  subscribe(fn: () => void): () => void
  // -- selection (tree) --
  selectSketch(id: string | null): void
  // -- sketch mode --
  startSketch(meta?: SketchMeta): void
  addPoint(p: Pt): void
  setCursor(p: Pt | null): void
  undoPoint(): void
  closeRing(): void
  reopen(): void
  setSketchPhase(phase: SketchPhase, message?: string | null): void
  // -- extrude mode --
  startExtrude(
    preselectedSketchId: string | null,
    target?: AuthoringTarget | null,
    defaultDepthMm?: number,
  ): void
  chooseCommittedSketch(sketchId: string): void
  beginChainedSketch(plane: PlaneOrientation, target: { number: string; name: string } | null): void
  /** Chained sketch OK: carry the drawn rings back into the extrude session. */
  finishChainedSketch(): void
  setDepth(depthMm: number): void
  setExtrudePhase(phase: ExtrudePhase, message?: string | null): void
  /** End the session (any mode) → idle. The surfaces own backend rollback. */
  cancel(): void
}

const IDLE: AuthoringSessionState = { mode: 'idle', selectedSketchId: null }

const SKETCH_DEFAULTS = {
  mode: 'sketch' as const,
  points: [] as Pt[],
  cursor: null,
  closed: false,
  phase: 'drawing' as SketchPhase,
  message: null,
  objectRef: null,
  partName: null,
  partNumber: null,
}

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

    startSketch: (meta) => {
      if (state.mode !== 'idle') return
      emit({
        ...SKETCH_DEFAULTS,
        chainToExtrude: false,
        plane: meta?.plane ?? 'xy',
        partName: meta?.partName?.trim() || null,
        partNumber: meta?.partNumber?.trim() || null,
        targetPart: meta?.targetPart ?? null,
        targetAuth: meta?.targetAuth ?? null,
        selectedSketchId: state.selectedSketchId,
      })
    },
    addPoint: (p) => {
      const s = sketch()
      if (!s || s.closed || s.phase === 'busy') return
      emit({ ...s, points: [...s.points, p], message: null })
    },
    setCursor: (p) => {
      const s = sketch()
      if (!s || s.closed) return
      emit({ ...s, cursor: p })
    },
    undoPoint: () => {
      const s = sketch()
      if (!s || s.phase === 'busy' || s.points.length === 0) return
      emit({ ...s, points: s.points.slice(0, -1), message: null })
    },
    closeRing: () => {
      const s = sketch()
      if (!s || s.phase === 'busy' || s.points.length < 3) return
      emit({ ...s, closed: true, cursor: null, phase: 'closed', message: null })
    },
    reopen: () => {
      const s = sketch()
      if (!s || s.phase === 'busy') return
      emit({ ...s, closed: false, phase: 'drawing', message: null })
    },
    setSketchPhase: (phase, message = null) => {
      const s = sketch()
      if (!s) return
      if (s.phase === phase && s.message === message) return
      emit({ ...s, phase, message })
    },

    startExtrude: (preselectedSketchId, target = null, defaultDepthMm = 10) => {
      if (state.mode !== 'idle') return
      emit({
        mode: 'extrude',
        step: preselectedSketchId ? 'depth' : 'select',
        source: preselectedSketchId ? { kind: 'committed', sketchId: preselectedSketchId } : null,
        target,
        depthMm: defaultDepthMm,
        phase: 'editing',
        message: null,
        selectedSketchId: state.selectedSketchId,
      })
    },
    chooseCommittedSketch: (sketchId) => {
      const e = extrude()
      if (!e || e.phase === 'busy') return
      emit({ ...e, step: 'depth', source: { kind: 'committed', sketchId }, message: null })
    },
    beginChainedSketch: (plane, target) => {
      const e = extrude()
      if (!e || e.phase === 'busy') return
      // The extrude session HANDS OFF to the sketch surface; OK hands back.
      // The authority tuple is the EXTRUDE session's capture (Codex4 B1.4) —
      // never re-read live at the hand-off.
      emit({
        ...SKETCH_DEFAULTS,
        chainToExtrude: true,
        plane,
        targetPart: target,
        targetAuth: e.target,
        selectedSketchId: state.selectedSketchId,
      })
    },
    finishChainedSketch: () => {
      const s = sketch()
      if (!s || !s.chainToExtrude || !s.closed) return
      emit({
        mode: 'extrude',
        step: 'depth',
        source: { kind: 'pending', plane: s.plane, points: s.points },
        // The captured TUPLE survives the sketch hand-off (Codex4 B1.4).
        target: s.targetAuth,
        depthMm: 10,
        phase: 'editing',
        message: null,
        selectedSketchId: s.selectedSketchId,
      })
    },
    setDepth: (depthMm) => {
      const e = extrude()
      if (!e || e.phase === 'busy') return
      emit({ ...e, depthMm, phase: 'editing', message: null })
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
