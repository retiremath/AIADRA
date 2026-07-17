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
// The CURRENT contract version (SK-C1.0 S2) — mirrors the engine authority.
export const DISPLAY_REPRESENTATION_VERSION = '1.2'
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

/** v1.2: the RESOLVED plane frame of one face-bound sketch — derived display
 *  data, identity-bound by CONTAINMENT in this package (Codex2 B3.1). */
export interface SketchFrame {
  sketch_feature_id: string
  origin_mm: [number, number, number]
  u_axis: [number, number, number]
  v_axis: [number, number, number]
  normal: [number, number, number]
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
  invalidation: DisplayInvalidation
  counters: DisplayCounters
}
