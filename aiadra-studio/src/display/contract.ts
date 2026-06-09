/**
 * The **Display Representation contract** — the TypeScript mirror of the
 * `aiadra-core` `aiadra_core.protocol.display` dataclasses (ADR/0035; arc
 * 20260609-1). The engine produces this read-only package; Studio renders it.
 *
 * Keep in sync with `aiadra-core/src/aiadra_core/protocol/display.py`. This is
 * the SAME shape the bridge ships as JSON (`{ display: DisplayRepresentation }`).
 */
export const DISPLAY_REPRESENTATION_VERSION = '1.0' as const

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

export interface DisplayRepresentation {
  display_representation_version: string
  identity: DisplayIdentity
  render: RenderPayload
  selection: SelectionPayload
  view_dependent: null // HLR slot — reserved (later arc)
  invalidation: DisplayInvalidation
  counters: DisplayCounters
}
