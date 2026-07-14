/**
 * Procedural contour extrude for the dev:web mock (arc 20260711-11 slice X).
 *
 * The `dev:web` lane has no OCCT kernel, so the mock synthesizes the Display
 * Representation of the extruded DRAWN contour directly: N side walls + 2 caps,
 * exactly the topology the real engine produces for the same contour (Codex4/5).
 * This is what lets a human draw a shape and watch it become a solid in the
 * browser. It is HONEST — badged as a dev mock, ephemeral ids (never Product
 * Truth) — and the real bridge lane shows the true engine solid instead.
 *
 * Caps are triangulated concave-safe with THREE.ShapeUtils; the render path
 * (`buildCanonicalPart`) uses a DoubleSide material, so winding never culls a
 * face — normals drive only the lighting.
 */
import * as THREE from 'three'
import {
  DISPLAY_REPRESENTATION_VERSION,
  type DisplayRepresentation,
  type EdgePolyline,
  type FaceBuffer,
  type VertexMarker,
} from '../display/contract'
import type { DisplaySource } from '../display/displaySource'
import { signedArea, type Pt } from './contour'

export function buildContourDisplay(points: Pt[], depthMm: number): DisplayRepresentation {
  // CCW ring (positive area) so every wall's outward normal is consistent.
  const ring = signedArea(points) >= 0 ? points : [...points].reverse()
  const n = ring.length
  const d = depthMm

  const faces: FaceBuffer[] = []
  const edges: EdgePolyline[] = []
  const vertices: VertexMarker[] = []

  // --- caps (concave-safe triangulation) ---
  const tris = THREE.ShapeUtils.triangulateShape(ring.map((p) => new THREE.Vector2(p.x, p.y)), [])

  const capBase: FaceBuffer = { face_id: 'mock:cap_base', appearance_slot: 'default', positions: [], normals: [], triangles: [] }
  const capTop: FaceBuffer = { face_id: 'mock:cap_top', appearance_slot: 'default', positions: [], normals: [], triangles: [] }
  for (const p of ring) {
    capBase.positions.push(p.x, p.y, 0); capBase.normals.push(0, 0, -1)
    capTop.positions.push(p.x, p.y, d); capTop.normals.push(0, 0, 1)
  }
  for (const [a, b, c] of tris) {
    capBase.triangles.push(a, c, b) // reverse winding → faces -z
    capTop.triangles.push(a, b, c)  // faces +z
  }
  faces.push(capBase, capTop)

  // --- side walls: one quad per contour segment (one wall per segment) ---
  for (let i = 0; i < n; i++) {
    const p = ring[i]
    const q = ring[(i + 1) % n]
    const ex = q.x - p.x
    const ey = q.y - p.y
    const len = Math.hypot(ex, ey) || 1
    const nx = ey / len // outward normal of a CCW ring
    const ny = -ex / len
    faces.push({
      face_id: `mock:wall_${i}`,
      appearance_slot: 'default',
      positions: [p.x, p.y, 0, q.x, q.y, 0, q.x, q.y, d, p.x, p.y, d],
      normals: [nx, ny, 0, nx, ny, 0, nx, ny, 0, nx, ny, 0],
      triangles: [0, 1, 2, 0, 2, 3],
    })
  }

  // --- edges: bottom ring, top ring, verticals (all sharp) + vertices ---
  for (let i = 0; i < n; i++) {
    const p = ring[i]
    const q = ring[(i + 1) % n]
    const prevWall = `mock:wall_${(i - 1 + n) % n}`
    const wall = `mock:wall_${i}`
    edges.push({ edge_id: `mock:e_bot_${i}`, kind: 'sharp', polyline: [p.x, p.y, 0, q.x, q.y, 0], faces: ['mock:cap_base', wall] })
    edges.push({ edge_id: `mock:e_top_${i}`, kind: 'sharp', polyline: [p.x, p.y, d, q.x, q.y, d], faces: ['mock:cap_top', wall] })
    edges.push({ edge_id: `mock:e_ver_${i}`, kind: 'sharp', polyline: [p.x, p.y, 0, p.x, p.y, d], faces: [prevWall, wall] })
    vertices.push({ vertex_id: `mock:v_bot_${i}`, position: [p.x, p.y, 0] })
    vertices.push({ vertex_id: `mock:v_top_${i}`, position: [p.x, p.y, d] })
  }

  const xs = ring.map((p) => p.x)
  const ys = ring.map((p) => p.y)
  return {
    display_representation_version: DISPLAY_REPRESENTATION_VERSION,
    identity: {
      object_uuid: 'mock-contour',
      object_number: 'MOCK',
      geometry_ref: 'mock',
      cache_key: 'mock',
      topology_signature: 'mock',
    },
    render: {
      faces,
      edges,
      vertices,
      bbox_min: [Math.min(...xs), Math.min(...ys), 0],
      bbox_max: [Math.max(...xs), Math.max(...ys), d],
      linear_deflection_mm: 0.1,
      angular_deflection_rad: 0.5,
      buffer_encoding: 'json_arrays',
    },
    selection: { id_space: 'ephemeral', pickable_kinds: [], names: {} },
    view_dependent: null,
    invalidation: { stale_when: [], selection_invalid_when: 'never' },
    counters: {
      face_count: faces.length,
      edge_count_by_kind: { sharp: edges.length },
      triangle_count: faces.reduce((s, f) => s + f.triangles.length / 3, 0),
      vertex_count: vertices.length,
    },
  }
}

/** A DisplaySource for the procedurally-extruded drawn contour (dev:web mock). */
export function proceduralContourSource(points: Pt[], depthMm: number, badge: string): DisplaySource {
  const display = buildContourDisplay(points, depthMm)
  return {
    kind: 'fixture',
    badge,
    // No HLR (no kernel) — the base shaded/wireframe render works from the
    // display; empty snapViews means the viewport never requests HLR.
    snapViews: [],
    async getDisplay() {
      return display
    },
    async getHlr() {
      return { identity_echo: { ...display.identity, display_representation_version: DISPLAY_REPRESENTATION_VERSION }, views: [] }
    },
  }
}
