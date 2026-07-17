import { describe, expect, it } from 'vitest'
import type { DisplayRepresentation, ViewDependentPayload } from './contract'
import { canAttachHlr, checkAttachHlr } from './attachHlr'

/**
 * The B3 attach check (arc 20260609-2): a standalone HLR overlay may attach
 * to a held display package ONLY when its identity_echo matches in full.
 * Wrong object / stale cache / recomputed topology → drop + re-request,
 * never render.
 */

function heldPackage(): DisplayRepresentation {
  return {
    display_representation_version: '1.1',
    identity: {
      object_uuid: 'u-1',
      object_number: 'PRT-0001',
      geometry_ref: 'sha256:abc',
      cache_key: 'ck-1',
      topology_signature: 'topo_deadbeef',
    },
    render: {
      faces: [],
      edges: [],
      vertices: [],
      bbox_min: [0, 0, 0],
      bbox_max: [1, 1, 1],
      linear_deflection_mm: 0.1,
      angular_deflection_rad: 0.5,
      buffer_encoding: 'json_arrays',
    },
    selection: { id_space: 'canonical', pickable_kinds: ['face'], names: {} },
    view_dependent: null,
    invalidation: {
      stale_when: ['cache_key_changed'],
      selection_invalid_when: 'topology_signature_changed',
    },
    counters: {
      face_count: 0,
      edge_count_by_kind: {},
      triangle_count: 0,
      vertex_count: 0,
    },
  }
}

function overlay(): ViewDependentPayload {
  return {
    identity_echo: {
      object_uuid: 'u-1',
      object_number: 'PRT-0001',
      geometry_ref: 'sha256:abc',
      display_representation_version: '1.1',
      cache_key: 'ck-1',
      topology_signature: 'topo_deadbeef',
    },
    views: [
      {
        view_id: 'front',
        projector: {
          projection: 'orthographic',
          origin: [0, 0, 0],
          direction: [0, 1, 0],
          up: [0, 0, 1],
          right: [1, 0, 0],
          units: 'mm',
        },
        algorithm: 'exact',
        coordinate_space: 'view_plane_2d',
        correlation_min_length_mm: 0.01,
        segments: [
          {
            polyline_2d: [0, 0, 10, 0],
            visibility: 'hidden',
            edge_class: 'outline',
            source: { kind: 'outline', face_id: 'feat_0002:face:hole_wall', index: 0 },
          },
        ],
        counters: {
          visible_segments: 0,
          hidden_segments: 1,
          outline_segments: 1,
          discarded_tolerance_segments: 0,
        },
      },
    ],
  }
}

describe('checkAttachHlr (Codex1 B3)', () => {
  it('attaches when the echo matches the package in full', () => {
    const res = checkAttachHlr(heldPackage(), overlay())
    expect(res.ok).toBe(true)
    expect(res.mismatches).toEqual([])
    expect(canAttachHlr(heldPackage(), overlay())).toBe(true)
  })

  it('rejects a stale cache key (the common recompute case)', () => {
    const p = overlay()
    p.identity_echo.cache_key = 'ck-STALE'
    const res = checkAttachHlr(heldPackage(), p)
    expect(res.ok).toBe(false)
    expect(res.mismatches).toEqual(['cache_key'])
  })

  it('rejects the wrong object outright', () => {
    const p = overlay()
    p.identity_echo.object_uuid = 'u-OTHER'
    p.identity_echo.object_number = 'PRT-0002'
    const res = checkAttachHlr(heldPackage(), p)
    expect(res.ok).toBe(false)
    expect(res.mismatches).toContain('object_uuid')
    expect(res.mismatches).toContain('object_number')
  })

  it('rejects a changed topology signature (held selection ids may be invalid)', () => {
    const p = overlay()
    p.identity_echo.topology_signature = 'topo_other'
    expect(canAttachHlr(heldPackage(), p)).toBe(false)
  })

  it('rejects a changed geometry_ref (different recipe state)', () => {
    const p = overlay()
    p.identity_echo.geometry_ref = 'sha256:other'
    expect(checkAttachHlr(heldPackage(), p).mismatches).toEqual(['geometry_ref'])
  })

  it('rejects an overlay not produced at the HELD package version', () => {
    const p = overlay()
    p.identity_echo.display_representation_version = '1.0'
    expect(checkAttachHlr(heldPackage(), p).mismatches).toEqual([
      'display_representation_version',
    ])
  })

  it('S2 (Codex2 B3.1.3): the version check is the HELD package MATRIX, never a literal — 1.1↔1.1 and 1.2↔1.2 attach; BOTH cross directions refuse', () => {
    const at = (held: string, echoed: string) => {
      const d = heldPackage()
      ;(d as { display_representation_version: string }).display_representation_version = held
      const p = overlay()
      p.identity_echo.display_representation_version = echoed
      return checkAttachHlr(d, p)
    }
    expect(at('1.1', '1.1').mismatches).toEqual([])
    expect(at('1.2', '1.2').mismatches).toEqual([])
    expect(at('1.2', '1.1').mismatches).toEqual(['display_representation_version'])
    expect(at('1.1', '1.2').mismatches).toEqual(['display_representation_version'])
  })
})
