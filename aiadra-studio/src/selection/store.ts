/**
 * The committed-selection store (arc 20260625-1 / 6c; ADR/0033 D9/D10, Codex1 Q6).
 * A sibling to `viewstate/store.ts` — focused on the LOW-frequency committed
 * selection + the pick filter. HOVER is deliberately NOT here: it is high-frequency
 * and stays imperative + rAF-coalesced inside the viewport (Codex1 Q5), so it
 * never churns React or this store.
 *
 * Selected ids are canonical engine-minted `face_id` / `edge_id` for ONE display
 * package; the viewport clears the store on any new canonical package (Codex1 B2,
 * Q4) — no cross-recompute id revalidation in v1.
 */
import { useSyncExternalStore } from 'react'

export type SelectableKind = 'face' | 'edge'

export interface Selected {
  kind: SelectableKind
  /** Canonical engine-minted display id (never an HLR/import ephemeral id). */
  id: string
}

export interface SelectionFilter {
  face: boolean
  edge: boolean
}

export interface SelectionState {
  selected: Selected | null
  filter: SelectionFilter
}

export interface SelectionStore {
  getSnapshot(): SelectionState
  subscribe(fn: () => void): () => void
  setSelected(sel: Selected | null): void
  clearSelected(): void
  setFilterKind(kind: SelectableKind, on: boolean): void
  toggleFilterKind(kind: SelectableKind): void
}

export const DEFAULT_SELECTION_STATE: SelectionState = {
  selected: null,
  filter: { face: true, edge: true },
}

export function createSelectionStore(
  initial: SelectionState = DEFAULT_SELECTION_STATE,
): SelectionStore {
  let state = initial
  const listeners = new Set<() => void>()
  const emit = () => listeners.forEach((l) => l())

  const setSelected = (selected: Selected | null) => {
    if (state.selected === selected) return
    if (
      state.selected &&
      selected &&
      state.selected.kind === selected.kind &&
      state.selected.id === selected.id
    ) {
      return // same selection → stable snapshot, no churn
    }
    state = { ...state, selected }
    emit()
  }

  const setFilterKind = (kind: SelectableKind, on: boolean) => {
    if (state.filter[kind] === on) return
    state = { ...state, filter: { ...state.filter, [kind]: on } }
    // A pick of a now-filtered-out kind cannot remain selected.
    if (!on && state.selected?.kind === kind) state = { ...state, selected: null }
    emit()
  }

  return {
    getSnapshot: () => state,
    subscribe: (fn) => {
      listeners.add(fn)
      return () => listeners.delete(fn)
    },
    setSelected,
    clearSelected: () => setSelected(null),
    setFilterKind,
    toggleFilterKind: (kind) => setFilterKind(kind, !state.filter[kind]),
  }
}

/** Is a given pickable kind currently active in the filter? */
export function kindIsPickable(state: SelectionState, kind: SelectableKind): boolean {
  return state.filter[kind]
}

/** React binding — one snapshot shared by toolbar, menu, badge, and viewport. */
export function useSelectionState(store: SelectionStore): SelectionState {
  return useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot)
}
