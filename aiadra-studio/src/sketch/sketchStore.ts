/**
 * The sketch session store (arc 20260711-11 slice S). PURE store (same discipline
 * as featureSession/operation/viewstate): `create*Store()` + `useSyncExternalStore`,
 * a new snapshot ref only on real change. Holds the in-progress contour drawing;
 * the SketchPad is its view, and the async extrude side effects live there.
 *
 * v1 sketches head-on on the XY datum plane (as Creo orients to the sketch plane).
 * Points are mm, y-up (engine convention). Drawing on arbitrary 3D planes/surfaces
 * + references is the incremental follow-up.
 */
import { useSyncExternalStore } from 'react'
import type { Pt } from './contour'

export type SketchPhase = 'drawing' | 'closed' | 'busy' | 'committed' | 'error'

export interface SketchState {
  active: boolean
  points: Pt[]
  /** Live cursor (mm) for the rubber-band segment; null when off-pad. */
  cursor: Pt | null
  closed: boolean
  phase: SketchPhase
  message: string | null
  objectRef: string | null
}

export interface SketchStore {
  getSnapshot(): SketchState
  subscribe(fn: () => void): () => void
  start(): void
  addPoint(p: Pt): void
  setCursor(p: Pt | null): void
  undoPoint(): void
  closeRing(): void
  reopen(): void
  setPhase(phase: SketchPhase, message?: string | null): void
  setCommitted(objectRef: string): void
  cancel(): void
}

const IDLE: SketchState = {
  active: false,
  points: [],
  cursor: null,
  closed: false,
  phase: 'drawing',
  message: null,
  objectRef: null,
}

export function createSketchStore(): SketchStore {
  let state = IDLE
  const listeners = new Set<() => void>()
  const emit = (next: SketchState) => {
    state = next
    listeners.forEach((l) => l())
  }
  const busy = () => state.phase === 'busy'
  return {
    getSnapshot: () => state,
    subscribe: (fn) => {
      listeners.add(fn)
      return () => listeners.delete(fn)
    },
    start: () => emit({ ...IDLE, active: true }),
    addPoint: (p) => {
      if (!state.active || state.closed || busy()) return
      emit({ ...state, points: [...state.points, p], message: null })
    },
    setCursor: (p) => {
      if (!state.active || state.closed) return
      emit({ ...state, cursor: p })
    },
    undoPoint: () => {
      if (!state.active || busy() || state.points.length === 0) return
      emit({ ...state, points: state.points.slice(0, -1), message: null })
    },
    closeRing: () => {
      if (!state.active || busy() || state.points.length < 3) return
      emit({ ...state, closed: true, cursor: null, phase: 'closed', message: null })
    },
    reopen: () => {
      if (!state.active || busy()) return
      emit({ ...state, closed: false, phase: 'drawing', message: null })
    },
    setPhase: (phase, message = null) => {
      if (!state.active) return
      if (state.phase === phase && state.message === message) return
      emit({ ...state, phase, message })
    },
    setCommitted: (objectRef) => {
      if (!state.active) return
      emit({ ...state, phase: 'committed', objectRef, message: null })
    },
    cancel: () => {
      if (!state.active && state.phase === 'drawing') return
      emit(IDLE)
    },
  }
}

export function useSketch(store: SketchStore): SketchState {
  return useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot)
}
