/**
 * The dimension-furniture builder (W-4; Codex14 B5 batch shape) — pure
 * geometry tests: per-kind primitive inventory, the no-origin-vector
 * regression, screen-scale invariance, lane determinism, and value parity.
 */
import { describe, expect, it } from 'vitest'
import type { ProfileAnnotation } from '../display/contract'
import { formatAnnotation } from './annotationFormat'
import { buildDimensionFurniture, type FurnitureGeometry } from './dimensionFurniture'
import { principalFrame } from './planeFrame'

const XY = principalFrame('xy')
const WPP = 0.5 // mm per pixel

const ann = (
  kind: ProfileAnnotation['kind'],
  entity: string,
  value: number,
  unit: 'mm' | 'deg' = 'mm',
): ProfileAnnotation => ({
  id: `ann:${kind}:${entity}`,
  kind,
  value,
  unit,
  entities: [entity],
  anchors: [
    [0, 0, 0],
    [0, 0, 0],
  ], // legacy hints — the furniture must IGNORE them
})

/** The ruled free-line scheme: {x_start, y_start, angle, x_end}. */
const freeLine = (): FurnitureGeometry => ({
  points: [
    { id: 'p1', world: [10, 20, 0] },
    { id: 'p2', world: [50, 45, 0] },
  ],
  segments: [{ id: 's1', start: 'p1', end: 'p2' }],
  circles: [],
  annotations: [
    ann('position_x', 'p1', 10),
    ann('position_y', 'p1', 20),
    ann('angle', 's1', 32.01, 'deg'),
    ann('position_x', 'p2', 50),
  ],
  constraint_glyphs: [],
})

const near = (a: [number, number, number], b: [number, number, number], tol = 1e-6) =>
  Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]) <= tol

describe('the W-4 no-origin-vector regression', () => {
  it('NO furniture line connects a drawn vertex to the sketch origin', () => {
    // The defect that failed the walk: position anchors rendered as a raw
    // origin→point segment. Furniture may touch u=0 (the reference tick and
    // the dim line's axis end) but never as the vertex↔origin diagonal.
    const f = buildDimensionFurniture(freeLine(), XY, WPP)
    const vertices: [number, number, number][] = [
      [10, 20, 0.05],
      [50, 45, 0.05],
    ]
    const origin: [number, number, number] = [0, 0, 0.05]
    for (const pts of f.lines) {
      const touchesVertex = pts.some((p) => vertices.some((v) => near(p, v, 1e-3)))
      const touchesOrigin = pts.some((p) => near(p, origin, 1e-3))
      expect(touchesVertex && touchesOrigin).toBe(false)
    }
  })

  it('the legacy anchors member is ignored — identical output under garbage anchors', () => {
    const g = freeLine()
    const garbage = {
      ...g,
      annotations: g.annotations.map((a) => ({
        ...a,
        anchors: [[999, 999, 999], [-999, -999, -999]] as [number, number, number][],
      })),
    }
    expect(JSON.stringify(buildDimensionFurniture(garbage, XY, WPP))).toBe(
      JSON.stringify(buildDimensionFurniture(freeLine(), XY, WPP)),
    )
  })
})

describe('per-kind furniture inventory', () => {
  it('the free line renders three linear dims + one angle arc, values verbatim', () => {
    const f = buildDimensionFurniture(freeLine(), XY, WPP)
    expect(f.labels.map((l) => l.text).sort()).toEqual(
      ['10.000', '20.000', '32.01°', '50.000'].sort(),
    )
    // every label is the ENGINE value through the one formatter (D6)
    for (const [i, a] of freeLine().annotations.entries()) {
      void i
      expect(f.labels.some((l) => l.text === formatAnnotation(a))).toBe(true)
    }
  })

  it('the angle arc anchors at the segment START vertex, spanning the +u ray', () => {
    const f = buildDimensionFurniture(freeLine(), XY, WPP)
    // the +u reference ray starts AT the start vertex
    const start: [number, number, number] = [10, 20, 0.05]
    const ray = f.lines.find(
      (pts) => pts.length === 2 && near(pts[0], start, 1e-6) && pts[1][1] === start[1],
    )
    expect(ray).toBeTruthy()
    // the arc's first sample lies on the +u ray at radius R from the start
    const arc = f.lines.find((pts) => pts.length > 8)
    expect(arc).toBeTruthy()
    expect(arc![0][1]).toBeCloseTo(20, 6) // v of the start vertex ⇒ angle 0
    expect(arc![0][0]).toBeGreaterThan(10)
  })

  it('an H-snapped line renders ONLY linear dims — no arc', () => {
    const g: FurnitureGeometry = {
      ...freeLine(),
      points: [
        { id: 'p1', world: [10, 20, 0] },
        { id: 'p2', world: [50, 20, 0] },
      ],
      annotations: [
        ann('position_x', 'p1', 10),
        ann('position_y', 'p1', 20),
        ann('position_x', 'p2', 50),
      ],
      constraint_glyphs: [
        { id: 'glyph:horizontal:s1', kind: 'horizontal', target: 's1', anchor: [30, 20, 0] },
      ],
    }
    const f = buildDimensionFurniture(g, XY, WPP)
    expect(f.lines.some((pts) => pts.length > 8)).toBe(false) // no arc
    expect(f.glyphs).toEqual([
      { text: 'H', at: [30, 20, 0], heightMm: 12 * WPP },
    ])
  })

  it('a radius renders a leader with the R-prefixed engine value', () => {
    const g: FurnitureGeometry = {
      points: [{ id: 'c', world: [5, 5, 0] }],
      segments: [],
      circles: [{ id: 'o1', center: 'c', radius_mm: 3 }],
      annotations: [
        ann('radius', 'o1', 3),
        ann('position_x', 'c', 5),
        ann('position_y', 'c', 5),
      ],
      constraint_glyphs: [],
    }
    const f = buildDimensionFurniture(g, XY, WPP)
    expect(f.labels.some((l) => l.text === 'R 3.000')).toBe(true)
  })
})

describe('the batch placement policy (Codex14 B5)', () => {
  it('two same-side position_x dims stagger into distinct lanes, sorted by value', () => {
    const f = buildDimensionFurniture(freeLine(), XY, WPP)
    // both x-dims group below the bbox (p1 lower half) / p2 above? p1.v=20
    // is the bbox min ⇒ below; p2.v=45 is max ⇒ above — they split sides.
    // Force one side: both points at the same v.
    const g: FurnitureGeometry = {
      ...freeLine(),
      points: [
        { id: 'p1', world: [10, 20, 0] },
        { id: 'p2', world: [50, 20, 0] },
      ],
      annotations: [ann('position_x', 'p1', 10), ann('position_x', 'p2', 50)],
    }
    const one = buildDimensionFurniture(g, XY, WPP)
    // dimension lines are the horizontals ending at u=0 with a tick partner;
    // find distinct v-levels of horizontal lines starting at u≈0
    const dimLevels = one.lines
      .filter((pts) => pts.length === 2 && Math.abs(pts[0][0]) < 1e-6 && pts[0][1] === pts[1][1])
      .map((pts) => pts[0][1])
    expect(new Set(dimLevels.map((v) => v.toFixed(6))).size).toBe(2)
    void f
  })

  it('equal values tie-break by semantic id — deterministic output', () => {
    const g: FurnitureGeometry = {
      ...freeLine(),
      points: [
        { id: 'p1', world: [10, 20, 0] },
        { id: 'p2', world: [10, 20, 0] },
      ],
      annotations: [ann('position_x', 'p2', 10), ann('position_x', 'p1', 10)],
    }
    const a = buildDimensionFurniture(g, XY, WPP)
    const b = buildDimensionFurniture(
      { ...g, annotations: [...g.annotations].reverse() },
      XY,
      WPP,
    )
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })

  it('pixel constants scale with worldPerPixel — text height doubles when wpp doubles', () => {
    const a = buildDimensionFurniture(freeLine(), XY, WPP)
    const b = buildDimensionFurniture(freeLine(), XY, WPP * 2)
    expect(b.labels[0].heightMm).toBeCloseTo(a.labels[0].heightMm * 2, 9)
    expect(b.glyphs.length).toBe(a.glyphs.length)
  })

  it('the furniture lays out in the FRAME, not in world XY', () => {
    const yz = principalFrame('yz') // u→Y, v→Z
    const g = freeLine()
    const remapped: FurnitureGeometry = {
      ...g,
      points: [
        { id: 'p1', world: [0, 10, 20] },
        { id: 'p2', world: [0, 50, 45] },
      ],
    }
    const f = buildDimensionFurniture(remapped, yz, WPP)
    // every primitive lies in the YZ plane (x = lift along the normal)
    for (const pts of f.lines) {
      for (const p of pts) expect(p[0]).toBeCloseTo(0.05, 6)
    }
  })
})
