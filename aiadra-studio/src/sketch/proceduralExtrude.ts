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

/** The EP2 principal frames, mirrored for the dev lane: (u, v, n) as global
 *  axis triples — xy=(X,Y,Z), yz=(Y,Z,X), zx=(Z,X,Y). The engine's
 *  `recipe.py` is the authority; this mirror keeps the mock's geometry
 *  oriented exactly as the real engine would build it. */
export type PlaneOrientation = 'xy' | 'yz' | 'zx'
const FRAME_AXES: Record<PlaneOrientation, [number[], number[], number[]]> = {
  xy: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
  yz: [[0, 1, 0], [0, 0, 1], [1, 0, 0]],
  zx: [[0, 0, 1], [1, 0, 0], [0, 1, 0]],
}

function to3d(ori: PlaneOrientation, u: number, v: number, w = 0): [number, number, number] {
  const [U, V, N] = FRAME_AXES[ori]
  return [
    u * U[0] + v * V[0] + w * N[0],
    u * U[1] + v * V[1] + w * N[1],
    u * U[2] + v * V[2] + w * N[2],
  ]
}

export function buildContourDisplay(
  points: Pt[],
  depthMm: number,
  plane: PlaneOrientation = 'xy',
): DisplayRepresentation {
  // CCW ring (positive area) so every wall's outward normal is consistent.
  const ring = signedArea(points) >= 0 ? points : [...points].reverse()
  const n = ring.length
  const d = depthMm

  const faces: FaceBuffer[] = []
  const edges: EdgePolyline[] = []
  const vertices: VertexMarker[] = []

  // --- caps (concave-safe triangulation) ---
  const tris = THREE.ShapeUtils.triangulateShape(ring.map((p) => new THREE.Vector2(p.x, p.y)), [])

  const [, , N] = FRAME_AXES[plane]
  const capBase: FaceBuffer = { face_id: 'mock:cap_base', appearance_slot: 'default', positions: [], normals: [], triangles: [] }
  const capTop: FaceBuffer = { face_id: 'mock:cap_top', appearance_slot: 'default', positions: [], normals: [], triangles: [] }
  for (const p of ring) {
    capBase.positions.push(...to3d(plane, p.x, p.y, 0))
    capBase.normals.push(-N[0], -N[1], -N[2])
    capTop.positions.push(...to3d(plane, p.x, p.y, d))
    capTop.normals.push(N[0], N[1], N[2])
  }
  for (const [a, b, c] of tris) {
    capBase.triangles.push(a, c, b) // reverse winding → faces −normal
    capTop.triangles.push(a, b, c)  // faces +normal
  }
  faces.push(capBase, capTop)

  // --- side walls: one quad per contour segment (one wall per segment) ---
  for (let i = 0; i < n; i++) {
    const p = ring[i]
    const q = ring[(i + 1) % n]
    const ex = q.x - p.x
    const ey = q.y - p.y
    const len = Math.hypot(ex, ey) || 1
    // Outward in-plane normal of a CCW ring, mapped through the frame.
    const [nx3, ny3, nz3] = to3d(plane, ey / len, -ex / len)
    faces.push({
      face_id: `mock:wall_${i}`,
      appearance_slot: 'default',
      positions: [
        ...to3d(plane, p.x, p.y, 0), ...to3d(plane, q.x, q.y, 0),
        ...to3d(plane, q.x, q.y, d), ...to3d(plane, p.x, p.y, d),
      ],
      normals: [nx3, ny3, nz3, nx3, ny3, nz3, nx3, ny3, nz3, nx3, ny3, nz3],
      triangles: [0, 1, 2, 0, 2, 3],
    })
  }

  // --- edges: bottom ring, top ring, verticals (all sharp) + vertices ---
  for (let i = 0; i < n; i++) {
    const p = ring[i]
    const q = ring[(i + 1) % n]
    const prevWall = `mock:wall_${(i - 1 + n) % n}`
    const wall = `mock:wall_${i}`
    const p0 = to3d(plane, p.x, p.y, 0)
    const pd = to3d(plane, p.x, p.y, d)
    const q0 = to3d(plane, q.x, q.y, 0)
    const qd = to3d(plane, q.x, q.y, d)
    edges.push({ edge_id: `mock:e_bot_${i}`, kind: 'sharp', polyline: [...p0, ...q0], faces: ['mock:cap_base', wall] })
    edges.push({ edge_id: `mock:e_top_${i}`, kind: 'sharp', polyline: [...pd, ...qd], faces: ['mock:cap_top', wall] })
    edges.push({ edge_id: `mock:e_ver_${i}`, kind: 'sharp', polyline: [...p0, ...pd], faces: [prevWall, wall] })
    vertices.push({ vertex_id: `mock:v_bot_${i}`, position: p0 })
    vertices.push({ vertex_id: `mock:v_top_${i}`, position: pd })
  }

  // The bbox from every ring corner at both sweep ends, mapped through the frame.
  const corners: [number, number, number][] = ring.flatMap((p) => [
    to3d(plane, p.x, p.y, 0),
    to3d(plane, p.x, p.y, d),
  ])
  const bboxMin: [number, number, number] = [0, 1, 2].map((i) =>
    Math.min(...corners.map((c) => c[i])),
  ) as [number, number, number]
  const bboxMax: [number, number, number] = [0, 1, 2].map((i) =>
    Math.max(...corners.map((c) => c[i])),
  ) as [number, number, number]
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
      bbox_min: bboxMin,
      bbox_max: bboxMax,
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
export function proceduralContourSource(
  points: Pt[],
  depthMm: number,
  badge: string,
  plane: PlaneOrientation = 'xy',
): DisplaySource {
  return displayToSource(buildContourDisplay(points, depthMm, plane), badge)
}

/** The EMPTY mock display (EP1 commit-at-New in the dev lane) — the dev
 *  mirror of core's A4 empty state: zero faces/edges, badged, ephemeral. */
export function buildEmptyMockDisplay(objectNumber: string): DisplayRepresentation {
  return {
    display_representation_version: DISPLAY_REPRESENTATION_VERSION,
    identity: {
      object_uuid: 'mock-empty',
      object_number: objectNumber,
      geometry_ref: 'mock-empty',
      cache_key: 'mock-empty',
      topology_signature: 'mock-empty',
    },
    render: {
      faces: [], edges: [], vertices: [],
      bbox_min: [0, 0, 0], bbox_max: [0, 0, 0],
      linear_deflection_mm: 0, angular_deflection_rad: 0,
      buffer_encoding: 'json_arrays',
    },
    selection: { id_space: 'ephemeral', pickable_kinds: [], names: {} },
    view_dependent: null,
    invalidation: { stale_when: [], selection_invalid_when: 'never' },
    counters: { face_count: 0, edge_count_by_kind: {}, triangle_count: 0, vertex_count: 0 },
  }
}

export function emptyMockSource(objectNumber: string, badge: string): DisplaySource {
  return displayToSource(buildEmptyMockDisplay(objectNumber), badge)
}

function displayToSource(display: DisplayRepresentation, badge: string): DisplaySource {
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
