// @vitest-environment jsdom
import { describe, it, expect } from 'vitest'
import * as THREE from 'three'
import {
  createChainEcho,
  createProfileOverlay,
  formatAnnotation,
  glyphLabel,
  type ProfileGeometry,
} from './profileOverlay'
import { SKETCH_LIFT_MM, principalFrame } from './planeFrame'

const FRAME_XY = principalFrame('xy')

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
  it('a rectangle yields its segments/points + dimension FURNITURE and a glyph (W-4)', () => {
    const o = createProfileOverlay()
    o.update(rectangle(), FRAME_XY, 0.5)
    const lines = o.group.children.filter((c) => c instanceof THREE.Line)
    const sprites = o.group.children.filter((c) => c instanceof THREE.Sprite)
    const points = o.group.children.filter((c) => c instanceof THREE.Points)
    // 4 profile segments + the length dim's furniture (extension lines, the
    // offset dimension line, arrowhead strokes) — never a bare witness line
    expect(lines.length).toBeGreaterThan(4)
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
      FRAME_XY,
      0.5,
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
      principalFrame('yz'),
      0.5,
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
    o.update(g, FRAME_XY, 0.5)
    const reference = createProfileOverlay()
    reference.update(rectangle(), FRAME_XY, 0.5)
    // the dangling segment adds NOTHING — same primitive count as without it
    expect(o.group.children.length).toBe(reference.group.children.length)
    o.dispose()
    reference.dispose()
  })

  it('null clears the overlay', () => {
    const o = createProfileOverlay()
    o.update(rectangle(), FRAME_XY, 0.5)
    expect(o.group.children.length).toBeGreaterThan(0)
    o.update(null, null, 0)
    expect(o.group.children).toHaveLength(0)
    o.dispose()
  })

  it('re-updating replaces rather than accumulates', () => {
    const o = createProfileOverlay()
    o.update(rectangle(), FRAME_XY, 0.5)
    const first = o.group.children.length
    o.update(rectangle(), FRAME_XY, 0.5)
    expect(o.group.children.length).toBe(first)
    o.dispose()
  })

  it('setViewScale re-renders the LAST inputs at the new scale (W-4)', () => {
    const o = createProfileOverlay()
    o.update(rectangle(), FRAME_XY, 0.5)
    const sprite = o.group.children.find((c) => c instanceof THREE.Sprite) as THREE.Sprite
    const before = sprite.scale.y
    o.setViewScale(1.0) // zoom out 2× — text must re-rasterize larger
    const after = (
      o.group.children.find((c) => c instanceof THREE.Sprite) as THREE.Sprite
    ).scale.y
    expect(after).toBeCloseTo(before * 2, 6)
    // below the 2% threshold: no rebuild (same object identity)
    const s1 = o.group.children.find((c) => c instanceof THREE.Sprite)
    o.setViewScale(1.005)
    const s2 = o.group.children.find((c) => c instanceof THREE.Sprite)
    expect(s2).toBe(s1)
    o.dispose()
  })

  it('the chain echo renders DRAWN nominals in the session frame (W-2)', () => {
    const e = createChainEcho()
    e.update(
      { pending: [{ u: 0, v: 0 }, { u: 20, v: 0 }], cursor: { u: 20, v: 15 } },
      principalFrame('yz'), // u→Y, v→Z: the mapping is the frame's, not XY's
    )
    const lines = e.group.children.filter((c) => c instanceof THREE.Line) as THREE.Line[]
    expect(lines).toHaveLength(2) // the confirmed chain + the rubber segment
    const chain = lines[0].geometry.getAttribute('position')
    // (u=20, v=0) on the yz frame lands at world (lift, 20, 0)
    expect(chain.getX(1)).toBeCloseTo(SKETCH_LIFT_MM, 5)
    expect(chain.getY(1)).toBeCloseTo(20, 5)
    expect(chain.getZ(1)).toBeCloseTo(0, 5)
    const rubber = lines[1].geometry.getAttribute('position')
    expect(rubber.getY(1)).toBeCloseTo(20, 5)
    expect(rubber.getZ(1)).toBeCloseTo(15, 5)
    e.dispose()
  })

  it('a single-vertex run shows its point and the rubber segment only', () => {
    const e = createChainEcho()
    e.update({ pending: [{ u: 5, v: 5 }], cursor: { u: 9, v: 9 } }, principalFrame('xy'))
    expect(e.group.children.filter((c) => c instanceof THREE.Line)).toHaveLength(1) // rubber only
    expect(e.group.children.filter((c) => c instanceof THREE.Points)).toHaveLength(1)
    e.dispose()
  })

  it('the echo clears on null chain and on a null cursor drops the rubber', () => {
    const e = createChainEcho()
    e.update({ pending: [{ u: 0, v: 0 }, { u: 10, v: 0 }], cursor: null }, principalFrame('xy'))
    expect(e.group.children.filter((c) => c instanceof THREE.Line)).toHaveLength(1) // chain only
    e.update(null, principalFrame('xy'))
    expect(e.group.children).toHaveLength(0)
    e.dispose()
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
    o.update(preview, FRAME_XY, 0.5)
    expect(o.group.children.filter((c) => c instanceof THREE.Line)).toHaveLength(1)
    o.dispose()
  })
})
