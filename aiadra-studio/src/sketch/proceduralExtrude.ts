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
  opts: { wOffset?: number; idPrefix?: string } = {},
): DisplayRepresentation {
  // P (arc 20260717-2): `wOffset` places the prism ALONG the plane normal
  // (a boss stacked on the base cap); `idPrefix` keeps composite face ids
  // distinct per feature. Defaults preserve every existing call site.
  const wOffset = opts.wOffset ?? 0
  const idPrefix = opts.idPrefix ?? "mock"
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
  const capBase: FaceBuffer = { face_id: `${idPrefix}:cap_base`,
      surface_kind: 'plane', appearance_slot: 'default', positions: [], normals: [], triangles: [] }
  const capTop: FaceBuffer = { face_id: `${idPrefix}:cap_top`,
      surface_kind: 'plane', appearance_slot: 'default', positions: [], normals: [], triangles: [] }
  for (const p of ring) {
    capBase.positions.push(...to3d(plane, p.x, p.y, wOffset))
    capBase.normals.push(-N[0], -N[1], -N[2])
    capTop.positions.push(...to3d(plane, p.x, p.y, wOffset + d))
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
      face_id: `${idPrefix}:wall_${i}`,
      surface_kind: 'plane',
      appearance_slot: 'default',
      positions: [
        ...to3d(plane, p.x, p.y, wOffset), ...to3d(plane, q.x, q.y, wOffset),
        ...to3d(plane, q.x, q.y, wOffset + d), ...to3d(plane, p.x, p.y, wOffset + d),
      ],
      normals: [nx3, ny3, nz3, nx3, ny3, nz3, nx3, ny3, nz3, nx3, ny3, nz3],
      triangles: [0, 1, 2, 0, 2, 3],
    })
  }

  // --- edges: bottom ring, top ring, verticals (all sharp) + vertices ---
  for (let i = 0; i < n; i++) {
    const p = ring[i]
    const q = ring[(i + 1) % n]
    const prevWall = `${idPrefix}:wall_${(i - 1 + n) % n}`
    const wall = `${idPrefix}:wall_${i}`
    const p0 = to3d(plane, p.x, p.y, wOffset)
    const pd = to3d(plane, p.x, p.y, wOffset + d)
    const q0 = to3d(plane, q.x, q.y, wOffset)
    const qd = to3d(plane, q.x, q.y, wOffset + d)
    edges.push({ edge_id: `${idPrefix}:e_bot_${i}`, kind: 'sharp', polyline: [...p0, ...q0], faces: [`${idPrefix}:cap_base`, wall] })
    edges.push({ edge_id: `${idPrefix}:e_top_${i}`, kind: 'sharp', polyline: [...pd, ...qd], faces: [`${idPrefix}:cap_top`, wall] })
    edges.push({ edge_id: `${idPrefix}:e_ver_${i}`, kind: 'sharp', polyline: [...p0, ...pd], faces: [prevWall, wall] })
    vertices.push({ vertex_id: `${idPrefix}:v_bot_${i}`, position: p0 })
    vertices.push({ vertex_id: `${idPrefix}:v_top_${i}`, position: pd })
  }

  // The bbox from every ring corner at both sweep ends, mapped through the frame.
  const corners: [number, number, number][] = ring.flatMap((p) => [
    to3d(plane, p.x, p.y, wOffset),
    to3d(plane, p.x, p.y, wOffset + d),
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

/** P (arc 20260717-2): merge several procedural representations into ONE
 *  display (the base + stacked bosses) — ids stay distinct per idPrefix;
 *  bbox/counters recomputed. Honest composition of honest prisms. */
export function mergeDisplays(reps: DisplayRepresentation[]): DisplayRepresentation {
  if (reps.length === 0) throw new Error('mergeDisplays: nothing to merge')
  const [head, ...rest] = reps
  const faces = [...head.render.faces]
  const edges = [...head.render.edges]
  const vertices = [...head.render.vertices]
  let bboxMin = [...head.render.bbox_min] as [number, number, number]
  let bboxMax = [...head.render.bbox_max] as [number, number, number]
  for (const r of rest) {
    faces.push(...r.render.faces)
    edges.push(...r.render.edges)
    vertices.push(...r.render.vertices)
    bboxMin = bboxMin.map((v, i) => Math.min(v, r.render.bbox_min[i])) as [number, number, number]
    bboxMax = bboxMax.map((v, i) => Math.max(v, r.render.bbox_max[i])) as [number, number, number]
  }
  return {
    ...head,
    render: {
      ...head.render,
      faces, edges, vertices,
      bbox_min: bboxMin, bbox_max: bboxMax,
    },
    counters: {
      face_count: faces.length,
      edge_count_by_kind: { sharp: edges.length },
      triangle_count: faces.reduce((s2, f) => s2 + f.triangles.length / 3, 0),
      vertex_count: vertices.length,
    },
  }
}

/** A DisplaySource for the procedurally-extruded drawn contour (dev:web mock). */
/**
 * The dev-lane REVOLVE display (arc 20260715-1 R3 / D-R10): an xy rectangle
 * swept 360° around the global X or Y axis — a tube (offset profile) or a
 * solid cylinder (profile touching the axis), matching the engine's radial
 * modes. Honest mock: only geometry the real engine produces.
 */
export function buildRevolveDisplay(
  rect: { x_mm: number; y_mm: number; width_mm: number; height_mm: number },
  axis: 'x' | 'y',
  segments = 48,
): DisplayRepresentation {
  // Axial extent + radial band from the rectangle, per the engine's rule:
  // axis x → radius from y, axial from x; axis y → radius from x, axial from y.
  const a0 = axis === 'x' ? rect.x_mm : rect.y_mm
  const a1 = a0 + (axis === 'x' ? rect.width_mm : rect.height_mm)
  const rLoRaw = axis === 'x' ? rect.y_mm : rect.x_mm
  const rHiRaw = rLoRaw + (axis === 'x' ? rect.height_mm : rect.width_mm)
  const r0 = Math.min(Math.abs(rLoRaw), Math.abs(rHiRaw))
  const r1 = Math.max(Math.abs(rLoRaw), Math.abs(rHiRaw))
  const solid = r0 <= 1e-9 // the profile touches the axis

  // A point at (axial u, radius r, angle t) in world coords.
  const pt = (u: number, r: number, t: number): [number, number, number] => {
    const c = Math.cos(t) * r
    const sn = Math.sin(t) * r
    return axis === 'x' ? [u, c, sn] : [sn, u, c]
  }
  const radial = (t: number): [number, number, number] => {
    const c = Math.cos(t)
    const sn = Math.sin(t)
    return axis === 'x' ? [0, c, sn] : [sn, 0, c]
  }
  const axial = (sign: number): [number, number, number] =>
    axis === 'x' ? [sign, 0, 0] : [0, sign, 0]

  const faces: FaceBuffer[] = []
  const ring = (
    faceId: string,
    r: number,
    outward: boolean,
  ) => {
    const positions: number[] = []
    const normals: number[] = []
    const indices: number[] = []
    for (let i = 0; i <= segments; i++) {
      const t = (i / segments) * Math.PI * 2
      const n = radial(t).map((v) => (outward ? v : -v)) as [number, number, number]
      positions.push(...pt(a0, r, t), ...pt(a1, r, t))
      normals.push(...n, ...n)
    }
    for (let i = 0; i < segments; i++) {
      const k = i * 2
      if (outward) indices.push(k, k + 2, k + 3, k, k + 3, k + 1)
      else indices.push(k, k + 3, k + 2, k, k + 1, k + 3)
    }
    faces.push({ face_id: faceId, positions, normals, triangles: indices, appearance_slot: 'default' })
  }
  const cap = (faceId: string, u: number, sign: number) => {
    const positions: number[] = []
    const normals: number[] = []
    const indices: number[] = []
    const n = axial(sign)
    const rin = solid ? 0 : r0
    for (let i = 0; i <= segments; i++) {
      const t = (i / segments) * Math.PI * 2
      positions.push(...pt(u, rin, t), ...pt(u, r1, t))
      normals.push(...n, ...n)
    }
    for (let i = 0; i < segments; i++) {
      const k = i * 2
      if (sign > 0) indices.push(k, k + 1, k + 3, k, k + 3, k + 2)
      else indices.push(k, k + 3, k + 1, k, k + 2, k + 3)
    }
    faces.push({ face_id: faceId, positions, normals, triangles: indices, appearance_slot: 'default' })
  }

  ring('mock:revolve:outer_wall', r1, true)
  if (!solid) ring('mock:revolve:inner_wall', r0, false)
  cap('mock:revolve:cap_lo', a0, -1)
  cap('mock:revolve:cap_hi', a1, 1)

  const circleEdge = (edgeId: string, u: number, r: number): EdgePolyline => {
    const polyline: number[] = []
    for (let i = 0; i <= segments; i++) {
      const t = (i / segments) * Math.PI * 2
      polyline.push(...pt(u, r, t))
    }
    return { edge_id: edgeId, kind: 'sharp', polyline, faces: [] }
  }
  const edges: EdgePolyline[] = [
    circleEdge('mock:revolve:e0', a0, r1),
    circleEdge('mock:revolve:e1', a1, r1),
  ]
  if (!solid) edges.push(circleEdge('mock:revolve:e2', a0, r0), circleEdge('mock:revolve:e3', a1, r0))

  const lo = Math.min(a0, a1)
  const hi = Math.max(a0, a1)
  const bboxMin: [number, number, number] = axis === 'x' ? [lo, -r1, -r1] : [-r1, lo, -r1]
  const bboxMax: [number, number, number] = axis === 'x' ? [hi, r1, r1] : [r1, hi, r1]

  return {
    display_representation_version: DISPLAY_REPRESENTATION_VERSION,
    identity: {
      object_uuid: 'mock-revolve',
      object_number: 'mock',
      geometry_ref: 'mock:procedural-revolve',
      cache_key: 'mock',
      topology_signature: 'mock',
    },
    render: {
      faces,
      edges,
      vertices: [],
      bbox_min: bboxMin,
      bbox_max: bboxMax,
      linear_deflection_mm: 0.1,
      angular_deflection_rad: 0.5,
      buffer_encoding: 'json_arrays',
    },
    selection: { id_space: 'ephemeral', pickable_kinds: [], names: {} },
    view_dependent: null,
    invalidation: { stale_when: [], selection_invalid_when: 'topology_signature_changed' },
    counters: {
      face_count: faces.length,
      edge_count_by_kind: { sharp: edges.length },
      triangle_count: faces.reduce((n, f) => n + f.triangles.length / 3, 0),
      vertex_count: 0,
    },
  } as unknown as DisplayRepresentation
}

/** Wrap the procedural revolve as a DisplaySource (badged mock). */
export function proceduralRevolveSource(
  rect: { x_mm: number; y_mm: number; width_mm: number; height_mm: number },
  axis: 'x' | 'y',
  badge: string,
): DisplaySource {
  const display = buildRevolveDisplay(rect, axis)
  return {
    kind: 'fixture',
    badge,
    snapViews: [],
    getDisplay: async () => display,
    getHlr: async () => {
      throw new Error('mock revolve has no HLR')
    },
  } as unknown as DisplaySource
}

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

export function displayToSource(display: DisplayRepresentation, badge: string): DisplaySource {
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
