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

// ---- Engine-owned staged identity (S2; arc 20260714-3 Codex1 B1) -----------

/**
 * A session-local reference to a PRIOR op's product: `{ $fromOp: n }` stands
 * for "the feature id op `n` minted". Resolved INSIDE the AuthoringBackend
 * implementations against the engine's per-op `created_feature_ids` — the
 * alias never crosses the IPC boundary and is never persisted. This kills all
 * renderer-side `feat_NNNN` prediction.
 */
export interface OpProductRef {
  $fromOp: number
}

export const opRef = (n: number): OpProductRef => ({ $fromOp: n })

export function isOpRef(v: unknown): v is OpProductRef {
  if (typeof v !== 'object' || v === null || Array.isArray(v)) return false
  const keys = Object.keys(v)
  if (!('$fromOp' in v)) return false
  // Codex2 bar (loud validation): a $fromOp carrying extra keys is a malformed
  // alias, not a passthrough value — fail rather than persist it.
  if (keys.length !== 1) throw new Error(`malformed $fromOp alias: extra keys [${keys.join(', ')}]`)
  return true
}

/**
 * Resolve every `{ $fromOp: n }` in an op's params against the ids minted so
 * far (`perOpIds[n]` = op n's engine-owned created_feature_ids). LOUD on a
 * forward/out-of-range reference and on cardinality ≠ 1 (Codex2 bar) — an
 * alias must name exactly one product, never guess among several or none.
 * Pure: returns a new value, never mutates the input.
 */
export function resolveOpAliases(value: unknown, opIndex: number, perOpIds: string[][]): unknown {
  if (isOpRef(value)) {
    const n = value.$fromOp
    if (!Number.isInteger(n) || n < 0 || n >= opIndex) {
      throw new Error(`$fromOp ${String(n)} in op ${opIndex} must reference an EARLIER op (0..${opIndex - 1})`)
    }
    const ids = perOpIds[n]
    if (ids.length !== 1) {
      throw new Error(`$fromOp ${n}: op ${n} created ${ids.length} features — an alias needs exactly 1`)
    }
    return ids[0]
  }
  if (Array.isArray(value)) return value.map((v) => resolveOpAliases(v, opIndex, perOpIds))
  if (typeof value === 'object' && value !== null) {
    return Object.fromEntries(
      Object.entries(value).map(([k, v]) => [k, resolveOpAliases(v, opIndex, perOpIds)]),
    )
  }
  return value
}

/** Validate an ids array at a trust boundary (Codex2 bar: validated response
 *  arrays at EVERY boundary — main validates the bridge, this validates main). */
export function assertCreatedFeatureIds(v: unknown, where: string): string[] {
  if (!Array.isArray(v) || !v.every((id) => typeof id === 'string' && id.length > 0)) {
    throw new Error(`${where}: response is missing a valid createdFeatureIds array`)
  }
  return v as string[]
}

/** What `begin` returns: the opaque session id + each op's ENGINE-minted
 *  feature ids (per-op deltas, index-aligned with the submitted ops). */
export interface BeginResult {
  sessionId: string
  createdFeatureIds: string[][]
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
  /** Open a draft with an op sequence; returns the opaque session id + each
   *  op's engine-minted feature ids. `{ $fromOp: n }` aliases in params are
   *  resolved inside the implementation and never leave the renderer. */
  begin(ops: FeatureOp[]): Promise<BeginResult>
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

// ---- The authoring-target policy (EP1; Codex5 B2 — fail closed) ------------

/**
 * May a sketch START, given the lane and the trust state of the authoring
 * target? The REAL lane refuses without a trustworthy active Part (created
 * this session with a known feature count) — never the fresh-Part fallback
 * against a hidden/different Part. The badged browser-dev lane keeps the
 * fresh-Part flow (it writes no Truth).
 */
export function sketchAuthoringGate(
  isRealLane: boolean,
  hasTrustedTarget: boolean,
): string | null {
  if (!isRealLane || hasTrustedTarget) return null
  return 'Create a Part with New… first — sketching an existing Part arrives with the S2 slice'
}

// (EP1's `reconcileLoadedPart` fail-close is superseded in S2: loading a
// canonical Part now ADOPTS it into the generation-owned partContext — the
// tree, target, and eligibility all follow the displayed Part by construction.)

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

// (The parametric-rectangle `buildExtrudeOps` retired in S2 with its dashboard
//  — Extrude is now dual-entry over real sketches, never a canned rectangle.)

/** The three principal sketch planes (EP2). Studio labels follow the Creo
 *  convention; the ENGINE speaks geometry — labels never cross the wire. */
export type PlaneOrientation = 'xy' | 'yz' | 'zx'
export const PLANE_LABELS: Record<PlaneOrientation, string> = {
  xy: 'FRONT',
  yz: 'RIGHT',
  zx: 'TOP',
}
/** Stable overlay-lane ids (arc 20260714-2 Codex1 — never leaked into Truth). */
export const INTRINSIC_PLANE_IDS: Record<PlaneOrientation, string> = {
  xy: 'intrinsic-plane:xy',
  yz: 'intrinsic-plane:yz',
  zx: 'intrinsic-plane:zx',
}
export const INTRINSIC_CSYS_ID = 'intrinsic-csys:origin'

/** The op that commits an EMPTY Part (EP1 commit-at-New — displayable via
 *  the EP0 empty-state contract). */
export function buildCreatePartOps(partNumber: string, name: string): FeatureOp[] {
  return [{ kind: 'create_part', params: { number: partNumber, name } }]
}

/** Sketch + extrude feature ops targeting an EXISTING Part (EP1: features are
 *  edits to the active Part, never a new Part per commit). The extrude
 *  references the sketch via `{ $fromOp: sketchOpIndex }` — the ENGINE mints
 *  the id; the renderer never predicts it (S2 Codex1 B1). `sketchOpIndex` is
 *  the sketch's index in the FINAL submitted sequence (0 when these two ops
 *  stand alone; shift it when ops are prepended). */
export function buildContourFeatureOps(
  partNumber: string,
  points: Pt[],
  depthMm: number,
  plane: PlaneOrientation,
  sketchOpIndex = 0,
): FeatureOp[] {
  return [
    {
      kind: 'mechanical.add_sketch_feature',
      params: {
        part_number: partNumber,
        primitives: [{ type: 'contour', segments: pointsToSegments(points) }],
        plane: { kind: 'principal', orientation: plane },
      },
    },
    {
      kind: 'mechanical.add_extrude_feature',
      params: {
        part_number: partNumber,
        sketch_feature_id: opRef(sketchOpIndex),
        depth_mm: depthMm,
        direction: 'normal+',
      },
    },
  ]
}

/**
 * Build the op sequence for "sketch a DRAWN contour + extrude it" on a FRESH
 * Part (the workspace-less dev flow; arc 20260711-11 slice S/X + the EP2
 * plane). create_part is op 0, so the sketch sits at op index 1.
 */
export function buildContourOps(
  partNumber: string,
  name: string,
  points: Pt[],
  depthMm: number,
  plane: PlaneOrientation = 'xy',
): FeatureOp[] {
  return [
    { kind: 'create_part', params: { number: partNumber, name } },
    ...buildContourFeatureOps(partNumber, points, depthMm, plane, 1),
  ]
}

// ---- The rectangle primitive (arc 20260715-1 R2; Codex2 N1) ---------------

export interface RectDims {
  x_mm: number
  y_mm: number
  width_mm: number
  height_mm: number
}

/** Sketch epsilon shared with the contour gate: dimensions at or below this
 *  are a refusal, mirroring the engine's positive-width/height requirement. */
export const RECT_EPS_MM = 1e-6

/** Normalize a two-click rectangle (Codex2 N1): min-corner + absolute dims —
 *  ALL four drag directions produce the SAME semantic record, so the mock and
 *  the real lane receive byte-equivalent primitives. Returns null when either
 *  dimension is degenerate (at/below epsilon). */
export function normalizeRectangle(a: Pt, b: Pt, epsMm: number = RECT_EPS_MM): RectDims | null {
  const width = Math.abs(b.x - a.x)
  const height = Math.abs(b.y - a.y)
  if (width <= epsMm || height <= epsMm) return null
  return { x_mm: Math.min(a.x, b.x), y_mm: Math.min(a.y, b.y), width_mm: width, height_mm: height }
}

/** The stepwise RECTANGLE sketch commit (D-R9): one native `rectangle`
 *  primitive — the engine's revolve/hole vocabulary, never a contour. */
export function buildRectangleSketchOps(
  partNumber: string,
  rect: RectDims,
  plane: PlaneOrientation,
): FeatureOp[] {
  return [
    {
      kind: 'mechanical.add_sketch_feature',
      params: {
        part_number: partNumber,
        primitives: [{ type: 'rectangle', ...rect }],
        plane: { kind: 'principal', orientation: plane },
      },
    },
  ]
}

/** The dev-lane fresh-Part rectangle flow (create + rectangle sketch). */
export function buildCreateWithRectangleOps(
  partNumber: string,
  name: string,
  rect: RectDims,
  plane: PlaneOrientation,
): FeatureOp[] {
  return [{ kind: 'create_part', params: { number: partNumber, name } }, ...buildRectangleSketchOps(partNumber, rect, plane)]
}

/** The STEPWISE sketch commit (S2 D-S2): the sketch alone becomes Truth —
 *  `Sketch N` in the tree + its wire in the viewport; Extrude consumes it
 *  later (dual entry A). */
export function buildSketchOnlyOps(
  partNumber: string,
  points: Pt[],
  plane: PlaneOrientation,
): FeatureOp[] {
  return [
    {
      kind: 'mechanical.add_sketch_feature',
      params: {
        part_number: partNumber,
        primitives: [{ type: 'contour', segments: pointsToSegments(points) }],
        plane: { kind: 'principal', orientation: plane },
      },
    },
  ]
}

/** The dev-lane stepwise flow without an active Part: create + sketch (the
 *  drawn ring becomes the fresh Part's first unconsumed sketch). */
export function buildCreateWithSketchOps(
  partNumber: string,
  name: string,
  points: Pt[],
  plane: PlaneOrientation,
): FeatureOp[] {
  return [{ kind: 'create_part', params: { number: partNumber, name } }, ...buildSketchOnlyOps(partNumber, points, plane)]
}

/** Revolve an ALREADY-COMMITTED eligible rectangle sketch (R3 entry A): one
 *  op on the REAL inspected id; the engine's rectangle/crossing validators
 *  stay authoritative. */
export function buildRevolveOnSketchOps(
  partNumber: string,
  sketchFeatureId: string,
  axis: 'x' | 'y',
): FeatureOp[] {
  return [
    {
      kind: 'mechanical.add_revolve_feature',
      params: { part_number: partNumber, sketch_feature_id: sketchFeatureId, axis },
    },
  ]
}

/** The chained one-draft revolve (R3 entry B): the rectangle sketch and the
 *  revolve commit TOGETHER — the engine mints the sketch id mid-draft via the
 *  $fromOp handshake. Plane pinned xy (the engine's v1 bound). */
export function buildRectangleRevolveOps(
  partNumber: string,
  rect: RectDims,
  axis: 'x' | 'y',
): FeatureOp[] {
  return [
    ...buildRectangleSketchOps(partNumber, rect, 'xy'),
    {
      kind: 'mechanical.add_revolve_feature',
      params: { part_number: partNumber, sketch_feature_id: opRef(0), axis },
    },
  ]
}

/** Round (fillet) / Chamfer over a CAPTURED sharp edge (R4): ONE op; the
 *  display edge_id crosses as ADR/0038 INPUT vocabulary — the engine
 *  re-anchors it as a recipe reference and stays the final authority. */
export function buildEdgeFeatureOps(
  feature: 'fillet' | 'chamfer',
  partNumber: string,
  targetEdgeId: string,
  valueMm: number,
): FeatureOp[] {
  return [
    feature === 'fillet'
      ? {
          kind: 'mechanical.add_fillet_feature',
          params: { part_number: partNumber, target_edge_id: targetEdgeId, radius_mm: valueMm },
        }
      : {
          kind: 'mechanical.add_chamfer_feature',
          params: { part_number: partNumber, target_edge_id: targetEdgeId, distance_mm: valueMm },
        },
  ]
}

/** A circular through-hole on a CAPTURED cap face (R5): ONE op; the display
 *  face_id is ADR/0038 INPUT vocabulary; wall-vs-cap + fit are the ENGINE's
 *  refusals (surfaced verbatim at begin/simulate). */
export function buildHoleOps(
  partNumber: string,
  targetFaceId: string,
  diameterMm: number,
  centerXMm: number,
  centerYMm: number,
): FeatureOp[] {
  return [
    {
      kind: 'mechanical.add_hole_feature',
      params: {
        part_number: partNumber,
        target_face_id: targetFaceId,
        diameter_mm: diameterMm,
        center_x_mm: centerXMm,
        center_y_mm: centerYMm,
      },
    },
  ]
}

/** Edit ONE catalogued dimension (R6): the engine's regenerating
 *  `adjust_feature_parameter` — addressed by feature id + parameter NAME
 *  (the identity-preserving record travels in the session; the engine
 *  validates the name/value authoritatively). */
export function buildAdjustParameterOps(
  partNumber: string,
  featureId: string,
  parameterName: string,
  newValue: number,
): FeatureOp[] {
  return [
    {
      kind: 'mechanical.adjust_feature_parameter',
      params: { part_number: partNumber, feature_id: featureId, parameter_name: parameterName, new_value: newValue },
    },
  ]
}

/** Extrude an ALREADY-COMMITTED unconsumed sketch (S2 D-S3 entry A): one op,
 *  a REAL engine id from inspected Truth — nothing predicted. */
export function buildExtrudeOnSketchOps(
  partNumber: string,
  sketchFeatureId: string,
  depthMm: number,
): FeatureOp[] {
  return [
    {
      kind: 'mechanical.add_extrude_feature',
      params: {
        part_number: partNumber,
        sketch_feature_id: sketchFeatureId,
        depth_mm: depthMm,
        direction: 'normal+',
      },
    },
  ]
}
