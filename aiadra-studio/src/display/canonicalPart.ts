/**
 * Canonical-part render path (ADR/0035; arc 20260609-1). Builds three.js
 * geometry from the engine's Display Representation — the FIRST renderer path
 * that draws true BREP topology (face-grouped tessellation + true model edges)
 * rather than the screen-space stopgap. Distinct from the reference-import
 * lane (`src/import/*`, occt-import-js, ephemeral ids).
 *
 * Crucially, every face mesh / edge line carries its **engine-minted display
 * id** in `userData` so a pick (raycast) recovers the stable topology id —
 * proving the id survives the wire + the render buffers into the picking layer
 * (the selection foundation; Codex N3).
 */
import * as THREE from 'three'
import type { DisplayRepresentation, EdgePolyline, FaceBuffer } from './contract'
import { DEFAULT_THEME, type CanonicalEdgeKind, type Theme } from '../settings/theme'

export interface PickResult {
  kind: 'face' | 'edge'
  displayId: string
}

export interface CanonicalPart {
  group: THREE.Group
  faces: THREE.Mesh[]
  edges: THREE.LineSegments[]
}

// Face/edge colors are theme-owned (arc 20260619-1 / 6a, Codex1 B2). The theme
// param defaults to the built-in theme so headless callers/tests need not pass
// one; the live viewport passes the registry theme and restyles via
// `applyPartTheme` on change.
function edgeColor(theme: Theme, kind: string): number {
  return theme.canonicalEdge[kind as CanonicalEdgeKind] ?? theme.canonicalEdge.boundary
}

export function buildFaceMesh(face: FaceBuffer, theme: Theme = DEFAULT_THEME): THREE.Mesh {
  const geom = new THREE.BufferGeometry()
  geom.setAttribute('position', new THREE.Float32BufferAttribute(face.positions, 3))
  if (face.normals.length === face.positions.length && face.normals.some((n) => n !== 0)) {
    geom.setAttribute('normal', new THREE.Float32BufferAttribute(face.normals, 3))
  } else {
    geom.computeVertexNormals()
  }
  geom.setIndex(face.triangles)
  const mat = new THREE.MeshStandardMaterial({
    color: theme.canonicalFace,
    metalness: 0.1,
    roughness: 0.75,
    side: THREE.DoubleSide,
  })
  const mesh = new THREE.Mesh(geom, mat)
  mesh.name = face.face_id
  // The pickable identity — recovered from a raycast hit.
  mesh.userData = { kind: 'face', displayId: face.face_id, faceId: face.face_id }
  return mesh
}

export function buildEdgeLine(edge: EdgePolyline, theme: Theme = DEFAULT_THEME): THREE.LineSegments {
  // A polyline of N points → 2·(N−1) endpoints for LineSegments.
  const pts = edge.polyline
  const seg: number[] = []
  for (let i = 0; i + 5 < pts.length; i += 3) {
    seg.push(pts[i], pts[i + 1], pts[i + 2], pts[i + 3], pts[i + 4], pts[i + 5])
  }
  const geom = new THREE.BufferGeometry()
  geom.setAttribute('position', new THREE.Float32BufferAttribute(seg.length ? seg : pts, 3))
  const line = new THREE.LineSegments(
    geom,
    new THREE.LineBasicMaterial({ color: edgeColor(theme, edge.kind) }),
  )
  line.name = edge.edge_id
  line.userData = { kind: 'edge', displayId: edge.edge_id, edgeId: edge.edge_id, edgeKind: edge.kind }
  return line
}

export function buildCanonicalPart(
  dr: DisplayRepresentation,
  theme: Theme = DEFAULT_THEME,
): CanonicalPart {
  const group = new THREE.Group()
  group.name = dr.identity.object_number || dr.identity.object_uuid
  group.userData = {
    topologySignature: dr.identity.topology_signature,
    geometryRef: dr.identity.geometry_ref,
    cacheKey: dr.identity.cache_key,
  }
  const faces = dr.render.faces.map((f) => buildFaceMesh(f, theme))
  const edges = dr.render.edges.map((e) => buildEdgeLine(e, theme))
  faces.forEach((m) => group.add(m))
  edges.forEach((l) => group.add(l))
  return { group, faces, edges }
}

/**
 * Live re-theming of an already-built part (arc 20260619-1 / 6a, Codex1 B2).
 * Restyles the shaded face material + per-kind bright edge colors in place — no
 * rebuild. Updates the SHADED material (the one stashed in `userData` when the
 * viewport swaps to the paper body) so the change survives a paper↔shaded swap.
 * Paper body, the dim pass, the HLR overlay, grid, and selection are the
 * viewport's to restyle (it owns those materials).
 */
export function applyPartTheme(part: CanonicalPart, theme: Theme): void {
  for (const mesh of part.faces) {
    const shaded =
      (mesh.userData.shadedMaterial as THREE.MeshStandardMaterial | undefined) ??
      (mesh.material as THREE.MeshStandardMaterial)
    shaded.color.setHex(theme.canonicalFace)
  }
  for (const line of part.edges) {
    const kind = (line.userData.edgeKind as string) ?? 'sharp'
    ;(line.material as THREE.LineBasicMaterial).color.setHex(edgeColor(theme, kind))
  }
}

/**
 * The viewport's raycast target set: canonical faces + edges ONLY. The settled
 * HLR overlay and render-assist passes (e.g. the hidden-line dim pass) are
 * NEVER pick targets — ephemeral view classification carries no identity
 * (ADR/0036 Codex1 B5; arc 20260610-1 Codex1 N3).
 */
export function pickTargets(part: CanonicalPart): THREE.Object3D[] {
  return [...part.faces, ...part.edges]
}

/**
 * The picking layer: resolve a raycast against the part's objects to the
 * engine-minted display id. This is the contract's selection payload made live.
 */
export function pickDisplayId(
  raycaster: THREE.Raycaster,
  objects: THREE.Object3D[],
): PickResult | null {
  const hits = raycaster.intersectObjects(objects, false)
  for (const h of hits) {
    const ud = h.object.userData
    if (ud && (ud.kind === 'face' || ud.kind === 'edge')) {
      return { kind: ud.kind, displayId: ud.displayId as string }
    }
  }
  return null
}

/** Dispose all GPU resources for a built part (call on remove/unmount). */
export function disposeCanonicalPart(part: CanonicalPart): void {
  for (const m of part.faces) {
    m.geometry.dispose()
    ;(m.material as THREE.Material).dispose()
  }
  for (const l of part.edges) {
    l.geometry.dispose()
    ;(l.material as THREE.Material).dispose()
  }
}
