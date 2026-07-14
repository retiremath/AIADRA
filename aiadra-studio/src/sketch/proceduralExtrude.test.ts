import { describe, it, expect } from 'vitest'
import { buildContourDisplay } from './proceduralExtrude'
import { DISPLAY_REPRESENTATION_VERSION } from '../display/contract'
import type { Pt } from './contour'

const L: Pt[] = [
  { x: 0, y: 0 }, { x: 60, y: 0 }, { x: 60, y: 20 },
  { x: 20, y: 20 }, { x: 20, y: 50 }, { x: 0, y: 50 },
]

describe('procedural contour extrude (dev:web mock display)', () => {
  const dr = buildContourDisplay(L, 12)

  it('synthesizes N walls + 2 caps for an N-segment contour', () => {
    expect(dr.render.faces).toHaveLength(6 + 2)
    const ids = dr.render.faces.map((f) => f.face_id)
    expect(ids).toContain('mock:cap_base')
    expect(ids).toContain('mock:cap_top')
    expect(ids.filter((i) => i.startsWith('mock:wall_'))).toHaveLength(6)
  })

  it('emits 3N edges (bottom + top + verticals), all sharp', () => {
    expect(dr.render.edges).toHaveLength(3 * 6)
    expect(dr.render.edges.every((e) => e.kind === 'sharp')).toBe(true)
    expect(dr.counters.edge_count_by_kind.sharp).toBe(18)
  })

  it('every triangle index is in range for its face', () => {
    for (const f of dr.render.faces) {
      const nodes = f.positions.length / 3
      expect(f.triangles.length % 3).toBe(0)
      expect(Math.max(...f.triangles)).toBeLessThan(nodes)
      expect(Math.min(...f.triangles)).toBeGreaterThanOrEqual(0)
      expect(f.normals.length).toBe(f.positions.length)
    }
  })

  it('carries the current contract version + a consistent bbox + counters', () => {
    expect(dr.display_representation_version).toBe(DISPLAY_REPRESENTATION_VERSION)
    expect(dr.render.bbox_min).toEqual([0, 0, 0])
    expect(dr.render.bbox_max).toEqual([60, 50, 12])
    expect(dr.counters.face_count).toBe(dr.render.faces.length)
    expect(dr.counters.vertex_count).toBe(dr.render.vertices.length)
  })
})
