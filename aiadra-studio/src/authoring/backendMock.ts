/**
 * The dev:web mock AuthoringBackend (arc 20260711-11 / slice 1b; Codex B2).
 *
 * Deterministic, no engine, no Product-Truth writes — for iterating the extrude
 * dashboard ergonomics instantly under `npm run dev:web`. It is HONEST: it
 * returns only geometry the real engine can produce (the baked `extrude-box`
 * fixture, a plain 6-face box) and clearly badges it as a mock preview, never a
 * real committed Part. The Electron bridge lane (backendBridge) is the source of
 * truth for real geometry.
 */
import { loadExtrudeBoxSource } from '../dev/fixtureSource'
import type { AuthoringBackend, CommitResult, FeatureOp, SimulateResult } from './backend'

export function createMockAuthoringBackend(): AuthoringBackend {
  let counter = 0
  const open = new Set<string>()

  return {
    isReal: false,
    async begin(ops: FeatureOp[]): Promise<string> {
      const sessionId = `mock-op-${++counter}`
      // Shallow structural sanity so the mock can't "succeed" on nonsense the
      // real bridge would reject (keeps the mock honest).
      if (ops.length === 0) throw new Error('mock: empty op sequence')
      open.add(sessionId)
      return sessionId
    },
    async simulate(sessionId: string): Promise<SimulateResult> {
      if (!open.has(sessionId)) return { valid: false, message: 'no open session' }
      return { valid: true }
    },
    async commit(sessionId: string, objectRef: string): Promise<CommitResult> {
      if (!open.has(sessionId)) throw new Error('mock: no open session')
      const display = await loadExtrudeBoxSource(`${objectRef} — dev mock preview (not a real Part)`)
      if (!display) throw new Error('mock: extrude-box fixture unavailable')
      open.delete(sessionId)
      return { objectRef, display }
    },
    async rollback(sessionId: string): Promise<void> {
      open.delete(sessionId)
    },
    async previewSource() {
      return loadExtrudeBoxSource('extrude preview — dev mock (transient)')
    },
  }
}
