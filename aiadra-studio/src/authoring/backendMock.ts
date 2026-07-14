/**
 * The dev:web mock AuthoringBackend (arc 20260711-11 / slice 1b; Codex B2).
 *
 * Deterministic, no engine, no Product-Truth writes — for iterating the
 * authoring UX instantly under `npm run dev:web`. It is HONEST: it returns only
 * geometry the real engine can produce, clearly badged as a mock preview, never
 * a real committed Part. The Electron bridge lane (backendBridge) is the source
 * of truth for real geometry.
 *
 * slice X: for a DRAWN contour it synthesizes the true extruded solid
 * (`proceduralContourSource`) so the browser shows exactly the shape you drew;
 * for the parametric-rectangle path it falls back to the baked `extrude-box`.
 */
import { loadExtrudeBoxSource } from '../dev/fixtureSource'
import { proceduralContourSource } from '../sketch/proceduralExtrude'
import { contourProblem, type Pt } from '../sketch/contour'
import type { AuthoringBackend, CommitResult, FeatureOp, SimulateResult } from './backend'

type Seg = { x1_mm: number; y1_mm: number }

/** Pull the drawn contour points + depth out of an op sequence, if it is one. */
function contourFromOps(ops: FeatureOp[]): { points: Pt[]; depthMm: number } | null {
  const sketch = ops.find((o) => o.kind === 'mechanical.add_sketch_feature')
  const extrude = ops.find((o) => o.kind === 'mechanical.add_extrude_feature')
  const prims = (sketch?.params.primitives as Array<{ type?: string; segments?: Seg[] }>) ?? []
  const contour = prims.find((p) => p.type === 'contour')
  if (!contour?.segments?.length) return null
  const points: Pt[] = contour.segments.map((s) => ({ x: Number(s.x1_mm), y: Number(s.y1_mm) }))
  const depthMm = Number(extrude?.params.depth_mm ?? 6)
  return { points, depthMm }
}

export function createMockAuthoringBackend(): AuthoringBackend {
  let counter = 0
  const open = new Map<string, FeatureOp[]>()

  return {
    isReal: false,
    async begin(ops: FeatureOp[]): Promise<string> {
      const sessionId = `mock-op-${++counter}`
      // Shallow structural sanity so the mock can't "succeed" on nonsense the
      // real bridge would reject (keeps the mock honest).
      if (ops.length === 0) throw new Error('mock: empty op sequence')
      open.set(sessionId, ops)
      return sessionId
    },
    async simulate(sessionId: string): Promise<SimulateResult> {
      const ops = open.get(sessionId)
      if (!ops) return { valid: false, message: 'no open session' }
      // Codex6 B2 (defence-in-depth): the mock must never report success the
      // real engine would reject — run the SAME pure Class-1 mirror on a drawn
      // contour (zero-length/duplicate, open, self-intersecting, collinear).
      const contour = contourFromOps(ops)
      if (contour) {
        const problem = contourProblem(contour.points)
        if (problem) return { valid: false, message: `mock Class-1: ${problem}` }
        if (!(contour.depthMm > 0)) return { valid: false, message: 'mock Class-1: depth must be positive' }
      }
      return { valid: true }
    },
    async commit(sessionId: string, objectRef: string): Promise<CommitResult> {
      const ops = open.get(sessionId)
      if (!ops) throw new Error('mock: no open session')
      const badge = `${objectRef} — dev mock (procedural, not a real Part)`
      const contour = contourFromOps(ops)
      const display = contour
        ? proceduralContourSource(contour.points, contour.depthMm, badge)
        : await loadExtrudeBoxSource(`${objectRef} — dev mock preview (not a real Part)`)
      if (!display) throw new Error('mock: display unavailable')
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
