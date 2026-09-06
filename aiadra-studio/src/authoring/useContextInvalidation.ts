/**
 * Context invalidation for the v1 authoring store (Codex4 B2 lineage; I3
 * Codex3 B1): a context-generation change kills a nonterminal pick, sketch,
 * OR placement dialog FAIL-CLOSED — a distinct transition from user cancel,
 * never resurrecting a captured session from the old generation. A BUSY
 * placement (a References / Redefine commit in flight) is left to its
 * runner, which owns the terminal and the stale-success rollback. The hook
 * is the App's ONE wiring: it subscribes to the real context store, so a test
 * can prove the reaction to a real `clear()` rather than calling the store
 * method under test directly.
 */
import { useEffect, useSyncExternalStore } from 'react'
import { useAuthoringSession, type AuthoringSessionState, type AuthoringSessionStore } from './authoringSession'
import type { PartContextStore } from './partContext'

/** Does this v1 state die with a context generation change? Pure. */
export function v1Invalidation(state: AuthoringSessionState, liveGeneration: number): boolean {
  if (state.mode === 'planePick' || state.mode === 'sketch') return state.generation !== liveGeneration
  if (state.mode === 'placement') return !state.busy && state.generation !== liveGeneration
  return false
}

export function useContextInvalidation(context: PartContextStore, store: AuthoringSessionStore): void {
  const pc = useSyncExternalStore(context.subscribe, context.getSnapshot)
  const s = useAuthoringSession(store)
  useEffect(() => {
    if (v1Invalidation(s, pc.generation)) store.invalidateForGeneration()
  }, [s, pc.generation, store])
}
