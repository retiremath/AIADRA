import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import type { DisplayRepresentation, HlrView } from './contract'
import { buildCanonicalPart, pickTargets } from './canonicalPart'
import { buildHlrOverlay, disposeOverlay, OVERLAY_GROUP_NAME } from './overlay'

/** A synthetic settled view: an off-axis frame so the lift math is exercised
 * on all three world components, with one segment per (visibility, source). */
function syntheticView(): HlrView {
  return {
    view_id: 'test',
    projector: {
      projection: 'orthographic',
      origin: [10, 20, 30],
      direction: [0, 1, 0],
      up: [0, 0, 1],
      right: [1, 0, 0], // direction × up
      units: 'mm',
    },
    algorithm: 'exact',
    coordinate_space: 'view_plane_2d',
    correlation_min_length_mm: 0.01,
    segments: [
      {
        polyline_2d: [0, 0, 5, 0],
        visibility: 'visible',
        edge_class: 'sharp',
        source: { kind: 'model_edge', edge_id: 'feat_0002:edge:e1' },
      },
      {
        polyline_2d: [0, 1, 5, 1, 5, 4],
        visibility: 'hidden',
        edge_class: 'sharp',
        source: { kind: 'model_edge', edge_id: 'feat_0002:edge:e2' },
      },
      {
        polyline_2d: [2, 2, 3, 2],
        visibility: 'hidden',
        edge_class: 'outline',
        source: { kind: 'outline', face_id: 'feat_0001/skp_0002:face:side', index: 0 },
      },
    ],
    counters: {
      visible_segments: 1,
      hidden_segments: 2,
      outline_segments: 1,
      discarded_tolerance_segments: 0,
    },
  }
}

function positionCount(group: THREE.Group): number {
  let n = 0
  group.traverse((o) => {
    const lines = o as THREE.LineSegments
    if (lines.isLineSegments) n += lines.geometry.getAttribute('position').count
  })
  return n
}

describe('HLR overlay builder (P5)', () => {
  it('lifts 2D view-plane points to 3D via origin + u·right + v·up', () => {
    const group = buildHlrOverlay(syntheticView(), 'no-hidden') // visible only
    const lines = group.children[0] as THREE.LineSegments
    const pos = lines.geometry.getAttribute('position')
    // (u=0,v=0) → origin; (u=5,v=0) → origin + 5·right
    expect([pos.getX(0), pos.getY(0), pos.getZ(0)]).toEqual([10, 20, 30])
    expect([pos.getX(1), pos.getY(1), pos.getZ(1)]).toEqual([15, 20, 30])
  })

  it('hidden-line renders hidden dimmed + visible bright; no-hidden drops hidden', () => {
    const hl = buildHlrOverlay(syntheticView(), 'hidden-line')
    // visible: 1 segment = 2 points; hidden: 2-seg polyline + 1-seg outline = 6 points
    expect(positionCount(hl)).toBe(8)
    const nh = buildHlrOverlay(syntheticView(), 'no-hidden')
    expect(positionCount(nh)).toBe(2)
  })

  it('Shading With Edges omits hidden segments — including hidden outlines (N4)', () => {
    const group = buildHlrOverlay(syntheticView(), 'shading-edges')
    expect(positionCount(group)).toBe(2) // only the visible model edge survives
  })

  it('wireframe renders everything bright', () => {
    const group = buildHlrOverlay(syntheticView(), 'wireframe')
    expect(positionCount(group)).toBe(8)
    expect(group.children).toHaveLength(1) // a single bright pass, no dim
  })

  it('overlay materials never depth-test or depth-write (drawn above the scene)', () => {
    const group = buildHlrOverlay(syntheticView(), 'hidden-line')
    group.traverse((o) => {
      const lines = o as THREE.LineSegments
      if (lines.isLineSegments) {
        const mat = lines.material as THREE.LineBasicMaterial
        expect(mat.depthTest).toBe(false)
        expect(mat.depthWrite).toBe(false)
      }
    })
  })
})

describe('ephemeral-identity firewall (ADR/0036 B5; Codex1 N3)', () => {
  it('no object in the overlay group carries a displayId or any pickable identity', () => {
    const group = buildHlrOverlay(syntheticView(), 'hidden-line')
    expect(group.name).toBe(OVERLAY_GROUP_NAME)
    group.traverse((o) => {
      expect(o.userData.displayId).toBeUndefined()
      expect(o.userData.kind).toBeUndefined()
      expect(o.userData.edgeId).toBeUndefined()
      expect(o.userData.faceId).toBeUndefined()
    })
  })

  it('the raycast target set is exactly the canonical faces + edges — never the overlay', () => {
    const dr: DisplayRepresentation = {
      display_representation_version: '1.1',
      identity: {
        object_uuid: 'u',
        object_number: 'P-000001',
        geometry_ref: 'g',
        cache_key: 'c',
        topology_signature: 't',
      },
      render: {
        faces: [
          {
            face_id: 'feat_0001:face:top',
            positions: [0, 0, 0, 1, 0, 0, 0, 1, 0],
            normals: [0, 0, 1, 0, 0, 1, 0, 0, 1],
            triangles: [0, 1, 2],
            appearance_slot: 'default',
          },
        ],
        edges: [
          {
            edge_id: 'feat_0001:edge:rim',
            kind: 'sharp',
            polyline: [0, 0, 0, 1, 0, 0],
            faces: ['feat_0001:face:top'],
          },
        ],
        vertices: [],
        bbox_min: [0, 0, 0],
        bbox_max: [1, 1, 0],
        linear_deflection_mm: 0.1,
        angular_deflection_rad: 0.3,
        buffer_encoding: 'json_arrays',
      },
      selection: { id_space: 'canonical', pickable_kinds: ['face', 'edge'], names: {} },
      view_dependent: null,
      invalidation: { stale_when: [], selection_invalid_when: '' },
      counters: { face_count: 1, edge_count_by_kind: { sharp: 1 }, triangle_count: 1, vertex_count: 0 },
    }
    const part = buildCanonicalPart(dr)
    const overlay = buildHlrOverlay(syntheticView(), 'hidden-line')
    const targets = pickTargets(part)
    expect(targets).toHaveLength(2) // 1 face + 1 edge
    for (const t of targets) expect(t.userData.displayId).toBeTruthy()
    const overlayObjects: THREE.Object3D[] = []
    overlay.traverse((o) => overlayObjects.push(o))
    for (const o of overlayObjects) expect(targets).not.toContain(o)
    disposeOverlay(overlay)
  })
})
