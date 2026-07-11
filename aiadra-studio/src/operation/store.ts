/**
 * The operation-session store (arc 20260711-10 / MVP-1; ADR/0040 D4/N2).
 *
 * The SINGLE SOURCE OF TRUTH for one in-progress authoring operation. The AI
 * dock, the status-strip session pill, and (later) the manual dashboard are all
 * PROJECTIONS of this store — none owns commit, and they can never disagree
 * (Codex arc-20260711-4 N2). It is the UI-side home of the three-state candidate
 * model (ADR/0039 D3): the session holds candidate recipes (state 1) + their
 * evaluated-display refs (state 2); accept → committed Truth (state 3) is MVP-2.
 *
 * Store actions are PURE state transitions — NO side effects (arc 20260711-10
 * B2). Recomputing candidates from answers is pure data, so it happens here;
 * the async `setDisplaySource` preview is a controller's job, driven off
 * `selectedCandidateId` (see operation/previewController).
 *
 * Mirrors the viewstate/selection store pattern: `createOperationStore()` →
 * `{ getSnapshot, subscribe, … }` + a `useOperation` hook over
 * `useSyncExternalStore` (new ref only on real change → stable snapshot).
 */
import { useSyncExternalStore } from 'react'

export type ValidationStatus = 'valid' | 'invalid' | 'pending'

/** Provenance shown on every candidate (ADR/0040 D8): where it came from + that
 *  it is transient (never Product Truth in MVP-1 — accept/commit is MVP-2). */
export interface CandidateProvenance {
  /** Source-qualified configurator id, e.g. `project:bracket/flat-plate`. */
  sourceConfigurator: string
  /** MVP-1 candidates are always transient. Made explicit so the UI can never
   *  render a candidate as committed Truth. */
  transient: true
}

/** A proposed candidate — an engine-evaluable recipe preview (ADR/0039 P-A2).
 *  Carries a STABLE `sourceId` (the baked display key, B2) + first-class
 *  provenance + validation, never loose display text (Codex note). */
export interface Candidate {
  id: string
  label: string
  /** Stable key resolving to a baked/engine display source (previewController). */
  sourceId: string
  /** The parameter set this candidate realizes (canonical `_mm` / count fields). */
  params: Readonly<Record<string, number>>
  validationStatus: ValidationStatus
  provenance: CandidateProvenance
}

export type OperationPhase = 'idle' | 'eliciting' | 'proposing' | 'refining'

export interface OperationState {
  configuratorId: string | null
  configuratorName: string | null
  phase: OperationPhase
  /** Elicitation answers keyed by question id. */
  answers: Readonly<Record<string, string | number>>
  /** Current parameter values (canonical `_mm` / count). */
  params: Readonly<Record<string, number>>
  candidates: readonly Candidate[]
  selectedCandidateId: string | null
  /** True once the user has answered/adjusted anything in this session. */
  dirty: boolean
}

/** A configurator instance the store drives — a pure recipe + a deterministic
 *  `propose` mapper (the "scripted AI"; no LLM). Held out of the snapshot so the
 *  snapshot stays data-only and reference-stable. */
export interface ActiveConfigurator {
  id: string
  name: string
  defaultParams: Readonly<Record<string, number>>
  /** answers + params → an ordered candidate set. MUST be pure + total. */
  propose(answers: Record<string, string | number>, params: Record<string, number>): Candidate[]
}

export interface OperationStore {
  getSnapshot(): OperationState
  subscribe(fn: () => void): () => void
  /** Begin a session for a configurator (from the dock OR a command — same path). */
  start(configurator: ActiveConfigurator): void
  answer(questionId: string, value: string | number): void
  setParam(key: string, value: number): void
  selectCandidate(id: string): void
  /** Cancel the active session (same action the dock and the pill both call). */
  cancel(): void
}

const IDLE: OperationState = {
  configuratorId: null,
  configuratorName: null,
  phase: 'idle',
  answers: {},
  params: {},
  candidates: [],
  selectedCandidateId: null,
  dirty: false,
}

/** Keep the current selection if it still exists, else fall back to the first
 *  candidate (or null). Stable so a re-propose doesn't drop a valid pick. */
function reconcileSelection(candidates: readonly Candidate[], current: string | null): string | null {
  if (current && candidates.some((c) => c.id === current)) return current
  return candidates.length > 0 ? candidates[0].id : null
}

export function createOperationStore(): OperationStore {
  let state: OperationState = IDLE
  let active: ActiveConfigurator | null = null
  const listeners = new Set<() => void>()

  const emit = (next: OperationState) => {
    state = next // new ref on every transition we choose to emit
    listeners.forEach((l) => l())
  }

  /** Recompute candidates from the current answers+params via the active
   *  configurator (pure), reconcile the selection, and advance the phase. */
  const reproposed = (base: OperationState, phase: OperationPhase): OperationState => {
    const candidates = active ? active.propose({ ...base.answers }, { ...base.params }) : []
    return {
      ...base,
      phase,
      candidates,
      selectedCandidateId: reconcileSelection(candidates, base.selectedCandidateId),
      dirty: true,
    }
  }

  return {
    getSnapshot: () => state,
    subscribe: (fn) => {
      listeners.add(fn)
      return () => listeners.delete(fn)
    },
    start: (configurator) => {
      active = configurator
      const params = { ...configurator.defaultParams }
      const candidates = configurator.propose({}, params)
      emit({
        configuratorId: configurator.id,
        configuratorName: configurator.name,
        phase: 'eliciting',
        answers: {},
        params,
        candidates,
        selectedCandidateId: reconcileSelection(candidates, null),
        dirty: false,
      })
    },
    answer: (questionId, value) => {
      if (!active) return
      emit(reproposed({ ...state, answers: { ...state.answers, [questionId]: value } }, 'proposing'))
    },
    setParam: (key, value) => {
      if (!active) return
      emit(reproposed({ ...state, params: { ...state.params, [key]: value } }, 'refining'))
    },
    selectCandidate: (id) => {
      // PURE (B2): selection is state only; the preview controller performs the
      // async setDisplaySource off this id. No-op if the id isn't a candidate.
      if (state.selectedCandidateId === id) return
      if (!state.candidates.some((c) => c.id === id)) return
      emit({ ...state, selectedCandidateId: id })
    },
    cancel: () => {
      active = null
      emit(IDLE)
    },
  }
}

/** React binding — one snapshot shared by the dock, the pill, and the dashboard. */
export function useOperation(store: OperationStore): OperationState {
  return useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot)
}

/** The selected candidate, or null. Convenience for projections. */
export function selectedCandidate(s: OperationState): Candidate | null {
  return s.candidates.find((c) => c.id === s.selectedCandidateId) ?? null
}
