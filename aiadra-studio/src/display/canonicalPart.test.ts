import { describe, expect, it } from 'vitest'
import * as THREE from 'three'
import type { DisplayRepresentation } from './contract'
import {
  buildCanonicalPart,
  disposeCanonicalPart,
  faceBoundaryEdges,
  pickDisplayId,
  pickTargetsFiltered,
} from './canonicalPart'

/**
 * Pick-path smoke (ADR/0035; arc 20260609-1 Codex N3): prove an engine-minted
 * face_id / edge_id survives the wire → the render buffers → a raycast pick.
 * The face_id is NOT decorative JSON: a real ray recovers it from the picking
 * layer. No DOM / WebGL needed — THREE.Raycaster is pure geometry.
 */

// A minimal but valid v1.0 contract: one cap_top quad at z=12 (+z normal) and
// one cap_base quad at z=0 (−z normal), plus a sharp edge between them.
function sampleContract(): DisplayRepresentation {
  return {
    display_representation_version: '1.0',
    identity: {
      object_uuid: 'u-1',
      object_number: 'PRT-0001',
      geometry_ref: 'sha256:abc',
      cache_key: 'ck',
      topology_signature: 'topo_deadbeef',
    },
    render: {
      faces: [
        {
          face_id: 'feat_0002:face:cap_top',
          positions: [0, 0, 12, 40, 0, 12, 40, 30, 12, 0, 30, 12],
          normals: [0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1],
          triangles: [0, 1, 2, 0, 2, 3],
          appearance_slot: 'default',
        },
        {
          face_id: 'feat_0002:face:cap_base',
          positions: [0, 0, 0, 40, 0, 0, 40, 30, 0, 0, 30, 0],
          normals: [0, 0, -1, 0, 0, -1, 0, 0, -1, 0, 0, -1],
          triangles: [0, 2, 1, 0, 3, 2],
          appearance_slot: 'default',
        },
      ],
      edges: [
        {
          edge_id: 'edge:feat_0002:face:cap_top~feat_0002/skp_0001:face:wall_x_min',
          kind: 'sharp',
          polyline: [0, 0, 12, 0, 30, 12],
          faces: ['feat_0002:face:cap_top', 'feat_0002/skp_0001:face:wall_x_min'],
        },
      ],
      vertices: [],
      bbox_min: [0, 0, 0],
      bbox_max: [40, 30, 12],
      linear_deflection_mm: 0.1,
      angular_deflection_rad: 0.5,
      buffer_encoding: 'json_arrays',
    },
    selection: {
      id_space: 'canonical',
      pickable_kinds: ['face', 'edge', 'vertex'],
      names: { 'feat_0002:face:cap_top': 'CAP_TOP' },
    },
    view_dependent: null,
    invalidation: { stale_when: [], selection_invalid_when: 'topology_signature_changed' },
    counters: {
      face_count: 2,
      edge_count_by_kind: { sharp: 1 },
      triangle_count: 4,
      vertex_count: 0,
    },
  }
}

describe('canonical-part render path', () => {
  it('builds one mesh per face, each carrying its engine-minted face_id', () => {
    const part = buildCanonicalPart(sampleContract())
    expect(part.faces).toHaveLength(2)
    const ids = part.faces.map((m) => m.userData.faceId).sort()
    expect(ids).toEqual(['feat_0002:face:cap_base', 'feat_0002:face:cap_top'])
    // geometry is indexed + has positions
    for (const m of part.faces) {
      expect(m.geometry.getIndex()?.count).toBe(6)
      expect(m.geometry.getAttribute('position').count).toBe(4)
    }
    disposeCanonicalPart(part)
  })

  it('edges carry their edge_id + kind into userData', () => {
    const part = buildCanonicalPart(sampleContract())
    expect(part.edges).toHaveLength(1)
    expect(part.edges[0].userData.edgeId).toContain('cap_top')
    expect(part.edges[0].userData.edgeKind).toBe('sharp')
    disposeCanonicalPart(part)
  })

  it('a raycast recovers the stable face_id from the picking layer', () => {
    const part = buildCanonicalPart(sampleContract())
    // Shoot a ray straight down (−z) through the centre of the top cap (z=12).
    const ray = new THREE.Raycaster()
    ray.set(new THREE.Vector3(20, 15, 100), new THREE.Vector3(0, 0, -1))
    const picked = pickDisplayId(ray, part.faces)
    expect(picked).not.toBeNull()
    expect(picked!.kind).toBe('face')
    // The FIRST hit (nearest the camera) is the top cap — its engine id survives.
    expect(picked!.displayId).toBe('feat_0002:face:cap_top')
    disposeCanonicalPart(part)
  })

  it('the part group records the topology signature for invalidation', () => {
    const part = buildCanonicalPart(sampleContract())
    expect(part.group.userData.topologySignature).toBe('topo_deadbeef')
    disposeCanonicalPart(part)
  })

  // --- 6c (arc 20260625-1; Codex1 B2) ---
  it('face→boundary edges come from contract adjacency (edges[].faces), not id parsing', () => {
    const part = buildCanonicalPart(sampleContract())
    // The sample edge lists cap_top among its `faces`; cap_base does not.
    const topBoundary = faceBoundaryEdges(part, 'feat_0002:face:cap_top')
    expect(topBoundary).toHaveLength(1)
    expect(topBoundary[0].userData.edgeId).toContain('cap_top')
    expect(faceBoundaryEdges(part, 'feat_0002:face:cap_base')).toHaveLength(0)
    disposeCanonicalPart(part)
  })

  it('the pick filter honors face/edge kinds — still canonical-only (the firewall)', () => {
    const part = buildCanonicalPart(sampleContract())
    const both = pickTargetsFiltered(part, { face: true, edge: true })
    const facesOnly = pickTargetsFiltered(part, { face: true, edge: false })
    const edgesOnly = pickTargetsFiltered(part, { face: false, edge: true })
    expect(both).toHaveLength(3) // 2 faces + 1 edge
    expect(facesOnly).toHaveLength(2)
    expect(edgesOnly).toHaveLength(1)
    // Every target is a canonical face/edge object — never an overlay/import.
    for (const o of both) {
      expect(o.userData.kind === 'face' || o.userData.kind === 'edge').toBe(true)
      expect(typeof o.userData.displayId).toBe('string')
    }
    disposeCanonicalPart(part)
  })
})
