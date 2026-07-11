/**
 * The feature operation session (arc 20260711-11 / slice 1c; ADR/0040 D4, Codex
 * Q3 — the `feature` operation session, sibling to the MVP-1 configurator
 * session). The single source of truth for one in-progress manual feature op;
 * the dashboard is its view (and, later, the AI panel drives the same session).
 *
 * PURE store (same discipline as the operation/viewstate/selection stores):
 * `create*Store()` + `useSyncExternalStore`, new ref only on real change. All
 * async side effects (begin/simulate/commit via the AuthoringBackend, and the
 * viewport `setDisplaySource`) live in the dashboard/controller, never here.
 */
import { useSyncExternalStore } from 'react'

export type FeaturePhase = 'idle' | 'editing' | 'busy' | 'committed' | 'error'

export interface FeatureSessionState {
  active: boolean
  /** e.g. `extrude` (slice 2 adds `fillet` / `chamfer`). */
  featureKind: string | null
  /** Canonical `_mm` params. */
  params: Readonly<Record<string, number>>
  phase: FeaturePhase
  message: string | null
  /** The committed object ref, once committed. */
  objectRef: string | null
}

export interface FeatureSessionStore {
  getSnapshot(): FeatureSessionState
  subscribe(fn: () => void): () => void
  start(featureKind: string, params: Record<string, number>): void
  setParam(key: string, value: number): void
  setPhase(phase: FeaturePhase, message?: string | null): void
  setCommitted(objectRef: string): void
  cancel(): void
}

const IDLE: FeatureSessionState = {
  active: false,
  featureKind: null,
  params: {},
  phase: 'idle',
  message: null,
  objectRef: null,
}

export function createFeatureSessionStore(): FeatureSessionStore {
  let state = IDLE
  const listeners = new Set<() => void>()
  const emit = (next: FeatureSessionState) => {
    state = next
    listeners.forEach((l) => l())
  }
  return {
    getSnapshot: () => state,
    subscribe: (fn) => {
      listeners.add(fn)
      return () => listeners.delete(fn)
    },
    start: (featureKind, params) =>
      emit({ active: true, featureKind, params: { ...params }, phase: 'editing', message: null, objectRef: null }),
    setParam: (key, value) => {
      if (!state.active) return
      // Editing a param invalidates any prior committed/error state for this op.
      emit({ ...state, params: { ...state.params, [key]: value }, phase: 'editing', message: null })
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
      if (!state.active && state.phase === 'idle') return
      emit(IDLE)
    },
  }
}

export function useFeatureSession(store: FeatureSessionStore): FeatureSessionState {
  return useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot)
}
