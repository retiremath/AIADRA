/**
 * The shared live view-state store (arc 20260619-2 / 6b; Codex1 N1). Lifts the
 * live display state OUT of `Viewport.tsx` so the toolbar, the context menu, and
 * the viewport observe and drive ONE snapshot. A `useSyncExternalStore` hook
 * gives every consumer the same value with no ad-hoc subscription drift.
 *
 * Flow is bidirectional but unambiguous: the UI surfaces write `mode` /
 * `gridVisible`; the viewport subscribes and applies them imperatively. The
 * viewport writes the scene facts (`hasCanonicalPart` / `hasReferenceGeometry`)
 * as parts load and imports come and go; the command predicates read them.
 *
 * Transient UI state — NOT persisted (the 6a registry's `defaultDisplayMode` /
 * `gridVisibleDefault` remain startup defaults only; live toggles do not write
 * settings — Codex 6a N3).
 */
import { useSyncExternalStore } from 'react'
import type { DisplayMode } from '../display/modes'
import type { CommandContext } from '../commands/types'

export interface ViewState {
  mode: DisplayMode
  gridVisible: boolean
  hasCanonicalPart: boolean
  hasReferenceGeometry: boolean
}

export interface ViewStateStore {
  getSnapshot(): ViewState
  subscribe(fn: () => void): () => void
  setMode(mode: DisplayMode): void
  setGridVisible(v: boolean): void
  setSceneFacts(facts: Partial<Pick<ViewState, 'hasCanonicalPart' | 'hasReferenceGeometry'>>): void
}

export function createViewStateStore(initial: ViewState): ViewStateStore {
  let state = initial
  const listeners = new Set<() => void>()

  const update = (patch: Partial<ViewState>) => {
    let changed = false
    for (const k of Object.keys(patch) as (keyof ViewState)[]) {
      if (state[k] !== patch[k]) {
        changed = true
        break
      }
    }
    if (!changed) return
    state = { ...state, ...patch } // new ref only on real change → stable snapshot
    listeners.forEach((l) => l())
  }

  return {
    getSnapshot: () => state,
    subscribe: (fn) => {
      listeners.add(fn)
      return () => listeners.delete(fn)
    },
    setMode: (mode) => update({ mode }),
    setGridVisible: (gridVisible) => update({ gridVisible }),
    setSceneFacts: (facts) => update(facts),
  }
}

/** Derive the command-enablement context from a view-state snapshot (B1). */
export function toCommandContext(s: ViewState): CommandContext {
  return {
    hasCanonicalPart: s.hasCanonicalPart,
    hasReferenceGeometry: s.hasReferenceGeometry,
    hasRenderableScene: s.hasCanonicalPart || s.hasReferenceGeometry,
    mode: s.mode,
    gridVisible: s.gridVisible,
  }
}

/** React binding — one snapshot shared by toolbar, menu, and viewport. */
export function useViewState(store: ViewStateStore): ViewState {
  return useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot)
}
