/**
 * The **Display Representation contract** — the TypeScript mirror of the
 * `aiadra-core` `aiadra_core.protocol.display` dataclasses (ADR/0035; arc
 * 20260609-1; v1.1 view-dependent HLR added arc 20260609-2). The engine
 * produces this read-only package; Studio renders it.
 *
 * Keep in sync with `aiadra-core/src/aiadra_core/protocol/display.py`. This is
 * the SAME shape the bridge ships as JSON (`{ display: DisplayRepresentation }`
 * / `{ view_dependent: ViewDependentPayload }`).
 */
// The CURRENT contract version (ADR/0044 A4: v1.4 additive `v2_profiles` —
// solved-derived PROFILE geometry with its annotations and constraint
// glyphs) — mirrors the engine authority.
export const DISPLAY_REPRESENTATION_VERSION = '1.4'
/** Legacy fixture producers still emit 1.1 (accepted by the version matrix). */
export const LEGACY_FIXTURE_DISPLAY_VERSION = '1.1'  as const

export interface DisplayIdentity {
  object_uuid: string
  object_number: string
  geometry_ref: string
  cache_key: string
  /** Deterministic; stable across parameter edits, changes on topology edits. */
  topology_signature: string
}

export interface FaceBuffer {
  face_id: string
  positions: number[] // flat (x,y,z) triples — this face's nodes
  normals: number[] // flat (x,y,z) triples — true surface normals
  triangles: number[] // flat (i,j,k) index triples into this face's nodes
  appearance_slot: string
  /** v1.2 (SK-C1.0 S2): engine-classified surface kind. ABSENT = unknown —
   *  consumers FAIL CLOSED (no planar-pick eligibility), never guess. */
  surface_kind?: 'plane' | 'other'
}

/** v1.3 (Gate F2b): the SOLVED construction geometry of one v2 constrained
 *  sketch — the engine's A2.9 read-lifecycle output mapped to world mm.
 *  Derived display data, never Truth. */
export interface V2ConstructionSketch {
  sketch_feature_id: string
  /** The admitted skb-b0 shape (G0 | G1 | G2). */
  shape: string
  construction: true
  points: { id: string; at: [number, number, number] }[]
  lines: { id: string; a: [number, number, number]; b: [number, number, number] }[]
}

/** v1.4 (ADR/0044 A4): one DERIVED display dimension of a profile sketch.
 *
 *  Class-5 display data: regenerated from committed Truth on every read,
 *  never persisted, never identity-bearing. `value` is a sketch-LOCAL scalar
 *  in `unit`; `anchors` are WORLD points, so the renderer places witness
 *  lines without ever re-deriving the sketch plane. */
export interface ProfileAnnotation {
  id: string
  kind: 'length' | 'angle' | 'radius' | 'position_x' | 'position_y'
  value: number
  unit: 'mm' | 'deg'
  entities: string[]
  anchors: [number, number, number][]
}

/** v1.4: one constraint marker on a profile segment (the Creo-style glyph). */
export interface ConstraintGlyph {
  id: string
  kind: 'horizontal' | 'vertical'
  target: string
  anchor: [number, number, number]
}

/** v1.4: the SOLVED profile block of one 0.2.2 constrained sketch.
 *
 *  Joins this package's `sketch_frames[]` by `sketch_feature_id` — the frame
 *  lives in exactly one place. Segment endpoints and circle centres are point
 *  IDs, never repeated coordinates, so geometry can never self-contradict. */
export interface V2ProfileSketch {
  sketch_feature_id: string
  points: { id: string; world: [number, number, number] }[]
  segments: { id: string; start: string; end: string }[]
  circles: { id: string; center: string; radius_mm: number }[]
  annotations: ProfileAnnotation[]
  constraint_glyphs: ConstraintGlyph[]
}

/** The uncommitted counterpart of `V2ProfileSketch` — what
 *  `previewSketchGraph` returns while the user is still drawing.
 *
 *  Deliberately NOT a `v2_profiles[]` entry (Codex4 B2): a create preview
 *  runs before any feature exists, so it carries a caller-scoped owner and
 *  the resolved frame INLINE. Ids are the CALLER's own keys for new records.
 *  Parity with committed Display is evaluated after substituting the owner
 *  and keys — never as literal equality. */
export interface ProfileGraphPreview {
  owner: { feature_id: string } | { candidate_key: string }
  frame: SketchPlaneFrame
  points: { id: string; world: [number, number, number] }[]
  segments: { id: string; start: string; end: string }[]
  circles: { id: string; center: string; radius_mm: number }[]
  annotations: ProfileAnnotation[]
  constraint_glyphs: ConstraintGlyph[]
}

/** An engine-resolved sketch plane in world space. The ENGINE owns this
 *  mapping; Studio never re-derives a sketch plane from a placement. */
export interface SketchPlaneFrame {
  origin_mm: [number, number, number]
  u_axis: [number, number, number]
  v_axis: [number, number, number]
  normal: [number, number, number]
}

/** v1.2: the RESOLVED plane frame of one sketch — derived display data,
 *  identity-bound by CONTAINMENT in this package (Codex2 B3.1). */
export interface SketchFrame extends SketchPlaneFrame {
  sketch_feature_id: string
}

export type EdgeKind = 'sharp' | 'tangent' | 'seam' | 'boundary' | 'free'

export interface EdgePolyline {
  edge_id: string
  kind: EdgeKind
  polyline: number[] // flat (x,y,z) — true curve discretization
  faces: string[] // adjacent face_ids (≤2)
}

export interface VertexMarker {
  vertex_id: string
  position: [number, number, number]
}

export interface RenderPayload {
  faces: FaceBuffer[]
  edges: EdgePolyline[]
  vertices: VertexMarker[]
  bbox_min: [number, number, number]
  bbox_max: [number, number, number]
  linear_deflection_mm: number
  angular_deflection_rad: number
  buffer_encoding: 'json_arrays'
}

export interface SelectionPayload {
  id_space: 'canonical' | 'ephemeral'
  pickable_kinds: string[]
  names: Record<string, string>
}

export interface DisplayInvalidation {
  stale_when: string[]
  selection_invalid_when: string
}

export interface DisplayCounters {
  face_count: number
  edge_count_by_kind: Record<string, number>
  triangle_count: number
  vertex_count: number
  generation_ms?: number | null
  package_bytes?: number | null
}

// ---------------------------------------------------------------------------
// View-dependent HLR payload (contract v1.1; arc 20260609-2)
// ---------------------------------------------------------------------------

/**
 * The contract-complete view frame (Codex1 B2). `direction` is the unit LOOK
 * direction (eye → scene); `up`/`right` are the orthonormalized screen axes
 * with `right = direction × up`; `(right, up, -direction)` is right-handed.
 * View-plane mapping: `u = (p - origin)·right`, `v = (p - origin)·up` [mm].
 */
export interface HlrProjector {
  projection: 'orthographic'
  origin: [number, number, number]
  direction: [number, number, number]
  up: [number, number, number]
  right: [number, number, number]
  units: 'mm'
}

/**
 * Strict source union (Codex1 B5): `model_edge` carries a stable canonical
 * `edge_id`; `outline` (a silhouette) is face-anchored + per-view ephemeral —
 * NEVER a display id, never pickable, never in `selection.names`.
 */
export type HlrSegmentSource =
  | { kind: 'model_edge'; edge_id: string; face_id?: null; index?: null }
  | { kind: 'outline'; face_id: string; index: number; edge_id?: null }

export type HlrEdgeClass = 'sharp' | 'smooth' | 'sewn' | 'outline'

export interface HlrSegment {
  polyline_2d: number[] // flat (u,v) pairs in the view plane
  visibility: 'visible' | 'hidden'
  edge_class: HlrEdgeClass
  source: HlrSegmentSource
}

export interface HlrViewCounters {
  visible_segments: number
  hidden_segments: number
  outline_segments: number
  /** Codex1 B4 — dropped sub-threshold slivers are COUNTED, never silent. */
  discarded_tolerance_segments: number
  generation_ms?: number | null
}

export interface HlrView {
  view_id: string
  projector: HlrProjector
  algorithm: 'exact' | 'poly'
  coordinate_space: 'view_plane_2d'
  correlation_min_length_mm: number
  segments: HlrSegment[]
  counters: HlrViewCounters
}

/**
 * What the overlay was computed against (Codex1 B3). Attach a standalone HLR
 * payload to a held display package ONLY when every field matches — see
 * `canAttachHlr()` in `attachHlr.ts`.
 */
export interface ViewIdentityEcho {
  object_uuid: string
  object_number: string
  geometry_ref: string
  display_representation_version: string
  cache_key: string
  topology_signature: string
}

/** The value of the `view_dependent` slot — inline or standalone. */
export interface ViewDependentPayload {
  identity_echo: ViewIdentityEcho
  views: HlrView[]
}

export interface DisplayRepresentation {
  display_representation_version: string
  identity: DisplayIdentity
  render: RenderPayload
  selection: SelectionPayload
  /** Populated only at contract ≥1.1 (the HLR lane); null otherwise. */
  view_dependent: ViewDependentPayload | null
  /** v1.2: resolved face-bound sketch frames (absent on 1.0/1.1). */
  sketch_frames?: SketchFrame[]
  /** v1.3 (Gate F2b): SOLVED-derived v2 construction geometry — the A2.9
   *  read lifecycle's display output (derived, never Truth). Absent ≤1.2. */
  v2_construction?: V2ConstructionSketch[]
  /** v1.4 (ADR/0044 A4): SOLVED-derived PROFILE geometry with its annotation
   *  basis and constraint glyphs. Absent ≤1.3. */
  v2_profiles?: V2ProfileSketch[]
  invalidation: DisplayInvalidation
  counters: DisplayCounters
}
