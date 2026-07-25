/**
 * The shared live view-state store (arc 20260619-2 / 6b; Codex1 N1). Lifts the
 * live display state OUT of `Viewport.tsx` so the toolbar, the context menu, and
 * the viewport observe and drive ONE snapshot. A `useSyncExternalStore` hook
 * gives every consumer the same value with no ad-hoc subscription drift.
 *
 * Flow is bidirectional but unambiguous: the UI surfaces write `mode` /
 * the display mode; the viewport subscribes and applies them imperatively. The
 * viewport writes the scene facts (`hasCanonicalPart` / `hasReferenceGeometry`)
 * as parts load and imports come and go; the command predicates read them.
 *
 * Transient UI state — NOT persisted (the 6a registry's `defaultDisplayMode` /
 * settings remain startup defaults only; live toggles do not write
 * settings — Codex 6a N3).
 */
import { useSyncExternalStore } from 'react'
import type { DisplayMode } from '../display/modes'
import type { CommandContext } from '../commands/types'

/** The Creo datum-display filters (shell pass 1) — refine WHICH datum kinds
 *  show while the master `datumsVisible` toggle gates the whole overlay. */
export interface DatumFilters {
  planes: boolean
  fill: boolean
  origin: boolean
}

export interface ViewState {
  mode: DisplayMode
  /** The datum overlay (EP1): the origin triad + three principal planes. */
  datumsVisible: boolean
  datumFilters: DatumFilters
  hasCanonicalPart: boolean
  hasReferenceGeometry: boolean
}

export interface ViewStateStore {
  getSnapshot(): ViewState
  subscribe(fn: () => void): () => void
  setMode(mode: DisplayMode): void
  setDatumsVisible(v: boolean): void
  setDatumFilter(kind: keyof DatumFilters, v: boolean): void
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
    setDatumsVisible: (datumsVisible) => update({ datumsVisible }),
    setDatumFilter: (kind, v) => {
      if (state.datumFilters[kind] === v) return // shallow-compare guard for the nested object
      update({ datumFilters: { ...state.datumFilters, [kind]: v } })
    },
    setSceneFacts: (facts) => update(facts),
  }
}

/**
 * Derive the command-enablement context from a view-state snapshot (B1) plus the
 * committed-selection snapshot (arc 20260625-1 / 6c). Selection lives in its own
 * store (`selection/store.ts`); the toolbar/menu pass its snapshot here so the
 * filter toggles + clear command can read filter/selection state.
 */
export function toCommandContext(
  s: ViewState,
  sel: { filter: { face: boolean; edge: boolean }; hasSelection: boolean } = {
    filter: { face: true, edge: true },
    hasSelection: false,
  },
): CommandContext {
  return {
    hasCanonicalPart: s.hasCanonicalPart,
    hasReferenceGeometry: s.hasReferenceGeometry,
    hasRenderableScene: s.hasCanonicalPart || s.hasReferenceGeometry,
    mode: s.mode,
    datumsVisible: s.datumsVisible,
    datumFilters: s.datumFilters,
    filter: sel.filter,
    hasSelection: sel.hasSelection,
  }
}

/** React binding — one snapshot shared by toolbar, menu, and viewport. */
export function useViewState(store: ViewStateStore): ViewState {
  return useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot)
}
