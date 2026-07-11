/**
 * The AuthoringBackend — the dual-lane write surface (arc 20260711-11 / slice
 * 1b; ADR/0043 D5, Codex B2). Two implementations behind ONE TypeScript type:
 *   - the `dev:web` mock: deterministic, no engine, for fast dashboard iteration;
 *   - the Electron bridge: the real Ring-2 session-capability verbs (opBegin/…).
 * The mock stays honest — same types, no Product-Truth writes, and only geometry
 * the real engine can produce (a plain extruded box).
 */
import type { DisplaySource } from '../display/displaySource'

/** A single feature op: an allowlisted Ring-2 kind + its (main-validated) params. */
export interface FeatureOp {
  kind: string
  params: Record<string, unknown>
}

export interface SimulateResult {
  valid: boolean
  message?: string
}

export interface CommitResult {
  objectRef: string
  /** The display of the committed (or mock) object to show in the viewport. */
  display: DisplaySource
}

export interface AuthoringBackend {
  /** true = real engine over the bridge; false = the dev:web mock. */
  readonly isReal: boolean
  /** Open a draft with an op sequence; returns the opaque session id. */
  begin(ops: FeatureOp[]): Promise<string>
  /** Validate the draft (no write). */
  simulate(sessionId: string): Promise<SimulateResult>
  /** Commit; returns the committed object ref + its display source. */
  commit(sessionId: string, objectRef: string): Promise<CommitResult>
  /** Discard the draft (cancel). */
  rollback(sessionId: string): Promise<void>
  /**
   * Optional LIVE preview of the in-progress draft. The dev:web mock synthesizes
   * a representative box; the bridge lane returns null (no draft-display
   * primitive yet — commit shows the real geometry). When null, the dashboard
   * shows geometry on commit rather than live.
   */
  previewSource?(): Promise<DisplaySource | null>
}

/**
 * Build the op sequence for "sketch a rectangle + extrude it" — the parametric-
 * rectangle sketch of the anti-balloon guardrail (a fresh Part; sketch = feat_0001).
 */
export function buildExtrudeOps(
  partNumber: string,
  name: string,
  widthMm: number,
  heightMm: number,
  depthMm: number,
): FeatureOp[] {
  return [
    { kind: 'create_part', params: { number: partNumber, name } },
    {
      kind: 'mechanical.add_sketch_feature',
      params: {
        part_number: partNumber,
        primitives: [{ type: 'rectangle', x_mm: 0, y_mm: 0, width_mm: widthMm, height_mm: heightMm }],
      },
    },
    {
      kind: 'mechanical.add_extrude_feature',
      params: { part_number: partNumber, sketch_feature_id: 'feat_0001', depth_mm: depthMm, direction: 'z+' },
    },
  ]
}
