// @vitest-environment jsdom
import { describe, it, expect } from 'vitest'
import * as THREE from 'three'
import {
  createProfileOverlay,
  formatAnnotation,
  glyphLabel,
  type ProfileGeometry,
} from './profileOverlay'

const XY: [number, number, number] = [0, 0, 1]

const rectangle = (): ProfileGeometry => ({
  points: [
    { id: 'a', world: [0, 0, 0] },
    { id: 'b', world: [30, 0, 0] },
    { id: 'c', world: [30, 12, 0] },
    { id: 'd', world: [0, 12, 0] },
  ],
  segments: [
    { id: 's1', start: 'a', end: 'b' },
    { id: 's2', start: 'b', end: 'c' },
    { id: 's3', start: 'c', end: 'd' },
    { id: 's4', start: 'd', end: 'a' },
  ],
  circles: [],
  annotations: [
    {
      id: 'ann:length:s1',
      kind: 'length',
      value: 30,
      unit: 'mm',
      entities: ['s1'],
      anchors: [
        [0, -5, 0],
        [30, -5, 0],
      ],
    },
  ],
  constraint_glyphs: [
    { id: 'glyph:horizontal:s1', kind: 'horizontal', target: 's1', anchor: [15, 0, 0] },
  ],
})

describe('dimension formatting is a RENDERING of engine output', () => {
  it('lengths read in millimetres to three decimals', () => {
    expect(formatAnnotation({ value: 20, unit: 'mm' })).toBe('20.000')
  })

  it('angles carry their degree sign', () => {
    expect(formatAnnotation({ value: 1.1459, unit: 'deg' })).toBe('1.15°')
  })

  it('the unit comes from the annotation, never from its kind', () => {
    // a `length` in degrees would be a contract violation upstream — the
    // formatter must not silently "fix" it into millimetres
    expect(formatAnnotation({ value: 90, unit: 'deg' })).toBe('90.00°')
  })

  it('a solved-exact value is displayed exact, not re-rounded from a measurement', () => {
    // The engine solved 20; nothing here re-derives it from the world points.
    expect(formatAnnotation({ value: 20.0, unit: 'mm' })).toBe('20.000')
  })

  it('glyph labels are the Creo markers', () => {
    expect(glyphLabel('horizontal')).toBe('H')
    expect(glyphLabel('vertical')).toBe('V')
  })
})

describe('the overlay renders what the engine handed it', () => {
  it('a rectangle yields four segment lines, its points, a dimension and a glyph', () => {
    const o = createProfileOverlay()
    o.update(rectangle(), XY)
    const lines = o.group.children.filter((c) => c instanceof THREE.Line)
    const sprites = o.group.children.filter((c) => c instanceof THREE.Sprite)
    const points = o.group.children.filter((c) => c instanceof THREE.Points)
    expect(lines).toHaveLength(5) // 4 segments + 1 dimension witness line
    expect(points).toHaveLength(4)
    expect(sprites).toHaveLength(2) // the value + the H glyph
    o.dispose()
  })

  it('a circle is built IN the sketch plane', () => {
    const o = createProfileOverlay()
    o.update(
      {
        points: [{ id: 'c', world: [5, 5, 0] }],
        segments: [],
        circles: [{ id: 'o1', center: 'c', radius_mm: 3 }],
        annotations: [],
        constraint_glyphs: [],
      },
      XY,
    )
    const line = o.group.children.find((c) => c instanceof THREE.Line) as THREE.Line
    const pos = line.geometry.getAttribute('position')
    for (let i = 0; i < pos.count; i++) {
      expect(pos.getZ(i)).toBeCloseTo(0, 5) // never tilts out of plane
      // 5 decimals, not 9: three.js stores positions as float32, so a tighter
      // assertion would be measuring the buffer format rather than the maths.
      expect(Math.hypot(pos.getX(i) - 5, pos.getY(i) - 5)).toBeCloseTo(3, 5)
    }
    o.dispose()
  })

  it('a circle on a non-XY plane stays in THAT plane', () => {
    const o = createProfileOverlay()
    o.update(
      {
        points: [{ id: 'c', world: [0, 5, 5] }],
        segments: [],
        circles: [{ id: 'o1', center: 'c', radius_mm: 3 }],
        annotations: [],
        constraint_glyphs: [],
      },
      [1, 0, 0], // the YZ plane
    )
    const line = o.group.children.find((c) => c instanceof THREE.Line) as THREE.Line
    const pos = line.geometry.getAttribute('position')
    for (let i = 0; i < pos.count; i++) expect(pos.getX(i)).toBeCloseTo(0, 5)
    o.dispose()
  })

  it('a dangling reference is skipped, never rendered at the origin', () => {
    const g = rectangle()
    g.segments.push({ id: 's5', start: 'a', end: 'nope' })
    const o = createProfileOverlay()
    o.update(g, XY)
    expect(o.group.children.filter((c) => c instanceof THREE.Line)).toHaveLength(5)
    o.dispose()
  })

  it('null clears the overlay', () => {
    const o = createProfileOverlay()
    o.update(rectangle(), XY)
    expect(o.group.children.length).toBeGreaterThan(0)
    o.update(null, XY)
    expect(o.group.children).toHaveLength(0)
    o.dispose()
  })

  it('re-updating replaces rather than accumulates', () => {
    const o = createProfileOverlay()
    o.update(rectangle(), XY)
    const first = o.group.children.length
    o.update(rectangle(), XY)
    expect(o.group.children.length).toBe(first)
    o.dispose()
  })

  it('a live PREVIEW and a committed profile render through the same path', () => {
    // the preview echoes caller keys; the committed one carries engine ids —
    // the overlay is id-agnostic by construction
    const preview: ProfileGeometry = {
      ...rectangle(),
      points: rectangle().points.map((p, i) => ({ ...p, id: `p${i}` })),
      segments: [{ id: 's0', start: 'p0', end: 'p1' }],
      annotations: [],
      constraint_glyphs: [],
    }
    const o = createProfileOverlay()
    o.update(preview, XY)
    expect(o.group.children.filter((c) => c instanceof THREE.Line)).toHaveLength(1)
    o.dispose()
  })
})
