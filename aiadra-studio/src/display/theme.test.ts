import { describe, expect, it } from 'vitest'
import * as THREE from 'three'
import type { DisplayRepresentation, HlrView } from './contract'
import { applyPartTheme, buildCanonicalPart } from './canonicalPart'
import { buildHlrOverlay } from './overlay'
import { themeFromValues } from '../settings/theme'
import { DEFAULT_VALUES } from '../settings/descriptors'

/**
 * Codex1 B2: prove a NON-default theme actually reaches the live display
 * material surfaces (canonical face/edge + HLR overlay) — the registry owns the
 * display colors step 6 says it owns, not just `Viewport.tsx` constants. Colors
 * are compared through THREE's own round-trip so color-management rounding never
 * makes the assertion flaky.
 */
const NON_DEFAULT = themeFromValues({
  ...DEFAULT_VALUES,
  canonicalFace: 0x010203,
  canonicalEdgeSharp: 0x040506,
  hlrVisible: 0x070809,
  hlrHidden: 0x0a0b0c,
})
const hex = (n: number) => new THREE.Color(n).getHex()

function dr(): DisplayRepresentation {
  return {
    display_representation_version: '1.1',
    identity: { object_uuid: 'u', object_number: 'P-1', geometry_ref: 'g', cache_key: 'c', topology_signature: 't' },
    render: {
      faces: [
        { face_id: 'f1', positions: [0, 0, 0, 1, 0, 0, 0, 1, 0], normals: [0, 0, 1, 0, 0, 1, 0, 0, 1], triangles: [0, 1, 2], appearance_slot: 'default' },
      ],
      edges: [{ edge_id: 'e1', kind: 'sharp', polyline: [0, 0, 0, 1, 0, 0], faces: ['f1'] }],
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
}

function view(): HlrView {
  return {
    view_id: 'v',
    projector: { projection: 'orthographic', origin: [0, 0, 0], direction: [0, 1, 0], up: [0, 0, 1], right: [1, 0, 0], units: 'mm' },
    algorithm: 'exact',
    coordinate_space: 'view_plane_2d',
    correlation_min_length_mm: 0.01,
    segments: [
      { polyline_2d: [0, 0, 5, 0], visibility: 'visible', edge_class: 'sharp', source: { kind: 'model_edge', edge_id: 'e1' } },
      { polyline_2d: [0, 1, 5, 1], visibility: 'hidden', edge_class: 'sharp', source: { kind: 'model_edge', edge_id: 'e2' } },
    ],
    counters: { visible_segments: 1, hidden_segments: 1, outline_segments: 0, discarded_tolerance_segments: 0 },
  }
}

describe('B2 — a non-default theme reaches the live display surfaces', () => {
  it('canonical face + edge materials take theme colors at build', () => {
    const part = buildCanonicalPart(dr(), NON_DEFAULT)
    expect((part.faces[0].material as THREE.MeshStandardMaterial).color.getHex()).toBe(hex(0x010203))
    expect((part.edges[0].material as THREE.LineBasicMaterial).color.getHex()).toBe(hex(0x040506))
  })

  it('applyPartTheme restyles an existing part in place', () => {
    const part = buildCanonicalPart(dr()) // built with the default theme
    const def = themeFromValues(DEFAULT_VALUES)
    expect((part.faces[0].material as THREE.MeshStandardMaterial).color.getHex()).toBe(hex(def.canonicalFace))
    applyPartTheme(part, NON_DEFAULT)
    expect((part.faces[0].material as THREE.MeshStandardMaterial).color.getHex()).toBe(hex(0x010203))
    expect((part.edges[0].material as THREE.LineBasicMaterial).color.getHex()).toBe(hex(0x040506))
  })

  it('HLR overlay passes take theme colors (visible=hlrVisible, hidden=hlrHidden)', () => {
    const group = buildHlrOverlay(view(), 'hidden-line', NON_DEFAULT)
    const colors = new Set<number>()
    group.traverse((o) => {
      const l = o as THREE.LineSegments
      if (l.isLineSegments) colors.add((l.material as THREE.LineBasicMaterial).color.getHex())
    })
    expect(colors.has(hex(0x070809))).toBe(true) // bright pass = hlrVisible
    expect(colors.has(hex(0x0a0b0c))).toBe(true) // dim pass = hlrHidden
  })
})
