/**
 * The AuthoringBackend — the dual-lane write surface (arc 20260711-11 / slice
 * 1b; ADR/0043 D5, Codex B2). Two implementations behind ONE TypeScript type:
 *   - the `dev:web` mock: deterministic, no engine, for fast dashboard iteration;
 *   - the Electron bridge: the real Ring-2 session-capability verbs (opBegin/…).
 * The mock stays honest — same types, no Product-Truth writes, and only geometry
 * the real engine can produce (a plain extruded box).
 */
import type { DisplaySource } from '../display/displaySource'
import { pointsToSegments, type Pt } from '../sketch/contour'

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

// ---- Provisional Part numbers (arc 20260714-1; Codex2 B2) ------------------

export const PART_NUMBER_RE = /^P-\d{6}$/

/**
 * Suggest a PROVISIONAL Part number — an honest draft candidate, NOT a
 * Truth-Model allocation. The authority is core's creation contract: ADR/0004
 * allocates the Number atomically with `object_created` + its Reservation entry
 * at commit, and a collision FAILS LOUDLY there (surfaced by the session
 * lifecycle's error path). Random 6 digits beat the old clock-modulo for
 * collision odds, but the semantics are unchanged: validated at commit, never
 * presented as already-canonical.
 */
export function suggestPartNumber(rand: () => number = Math.random): string {
  return `P-${String(Math.floor(rand() * 1_000_000)).padStart(6, '0')}`
}

// ---- Backend lane selection (arc 20260714-1; Codex1 B2) --------------------

export type BackendLane = 'mock' | 'bridge' | 'unavailable'

/**
 * The truth-lane rule: the mock exists ONLY for browser dev (`no bridge`). The
 * desktop app NEVER falls back to the mock — with no workspace capability,
 * authoring is UNAVAILABLE and fails clearly (a missing capability must not
 * silently change the truth lane).
 */
export function chooseBackendLane(hasBridge: boolean, workspaceId: string | null): BackendLane {
  if (!hasBridge) return 'mock'
  return workspaceId ? 'bridge' : 'unavailable'
}

/** The desktop-without-workspace backend: every operation fails loud. */
export function createUnavailableBackend(): AuthoringBackend {
  const fail = (): never => {
    throw new Error(
      'No workspace is open — open an AIADRA workspace (File → Open Workspace…) before authoring',
    )
  }
  return {
    isReal: true, // the desktop lane — just not available; NEVER badged as a mock
    async begin() {
      return fail()
    },
    async simulate() {
      return fail()
    },
    async commit() {
      return fail()
    },
    async rollback() {
      /* nothing to roll back */
    },
  }
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

/**
 * Build the op sequence for "sketch a DRAWN contour + extrude it" (arc
 * 20260711-11 slice S/X). The `contour` outer profile is the engine primitive
 * slice E added — an ordered closed ring of line segments. A fresh Part; the
 * sketch is feat_0001.
 */
export function buildContourOps(
  partNumber: string,
  name: string,
  points: Pt[],
  depthMm: number,
): FeatureOp[] {
  return [
    { kind: 'create_part', params: { number: partNumber, name } },
    {
      kind: 'mechanical.add_sketch_feature',
      params: {
        part_number: partNumber,
        primitives: [{ type: 'contour', segments: pointsToSegments(points) }],
      },
    },
    {
      kind: 'mechanical.add_extrude_feature',
      params: { part_number: partNumber, sketch_feature_id: 'feat_0001', depth_mm: depthMm, direction: 'z+' },
    },
  ]
}
