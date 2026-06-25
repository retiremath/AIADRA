import { describe, it, expect } from 'vitest'
import {
  STANDARD_VIEW_IDS,
  standardViewOrientation,
  upFor,
  cubeRegions,
  rollUp,
  orientationForLook,
  type Vec3,
} from './viewOrientation'

const len = (a: Vec3) => Math.hypot(a[0], a[1], a[2])
const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
const orthonormal = (o: { direction: Vec3; up: Vec3 }) =>
  Math.abs(len(o.direction) - 1) < 1e-6 &&
  Math.abs(len(o.up) - 1) < 1e-6 &&
  Math.abs(dot(o.direction, o.up)) < 1e-6

describe('standard views', () => {
  it('all 7 are orthonormal and non-degenerate', () => {
    for (const id of STANDARD_VIEW_IDS) expect(orthonormal(standardViewOrientation(id))).toBe(true)
  })

  it('top/bottom avoid the Z-up degeneracy (horizontal up)', () => {
    expect(standardViewOrientation('top').up).toEqual([0, 1, 0])
    expect(standardViewOrientation('bottom').up).toEqual([0, -1, 0])
  })

  it('non-polar views keep a +Z-ish up', () => {
    for (const id of ['front', 'back', 'right', 'left'] as const) {
      expect(standardViewOrientation(id).up).toEqual([0, 0, 1])
    }
  })
})

describe('nav-cube regions', () => {
  const regions = cubeRegions()

  it('has 26 regions: 6 faces + 12 edges + 8 corners', () => {
    expect(regions).toHaveLength(26)
    expect(regions.filter((r) => r.type === 'face')).toHaveLength(6)
    expect(regions.filter((r) => r.type === 'edge')).toHaveLength(12)
    expect(regions.filter((r) => r.type === 'corner')).toHaveLength(8)
  })

  it('every region orientation is orthonormal and non-degenerate', () => {
    for (const r of regions) expect(orthonormal(r.orientation)).toBe(true)
  })

  it('each face region reproduces its standard view exactly', () => {
    const faces = regions.filter((r) => r.type === 'face')
    expect(faces.every((f) => f.standardView !== null)).toBe(true)
    for (const f of faces) {
      const std = standardViewOrientation(f.standardView!)
      expect(f.orientation.direction).toEqual(std.direction)
      expect(f.orientation.up).toEqual(std.up)
    }
  })

  it('a region looks AT the cube from outside (look = −normal)', () => {
    // The −Y face (normal −Y) is the FRONT face: clicking it puts the camera on
    // the −Y side looking +Y, which IS the front view (look +Y).
    const front = regions.find((r) => r.cell.join(',') === '0,-1,0')!
    expect(front.standardView).toBe('front')
    expect(front.orientation.direction).toEqual([0, 1, 0])
    // The +Y face is BACK (look −Y).
    const back = regions.find((r) => r.cell.join(',') === '0,1,0')!
    expect(back.standardView).toBe('back')
    expect(back.orientation.direction).toEqual([0, -1, 0])
  })
})

describe('upFor', () => {
  it('returns a unit vector perpendicular to the look direction', () => {
    const dirs: Vec3[] = [[1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, -1], [1, 1, 1], [-1, -1, -1]]
    for (const d of dirs) {
      const up = upFor(d)
      expect(Math.abs(len(up) - 1)).toBeLessThan(1e-6)
      expect(Math.abs(dot(up, d) / len(d))).toBeLessThan(1e-6)
    }
  })
})

describe('rollUp', () => {
  it('90° roll stays orthonormal and four rolls return to start', () => {
    const o = orientationForLook([0, 1, 0]) // front, up +Z
    let up = o.up
    for (let i = 0; i < 4; i++) {
      up = rollUp(o.direction, up, 1)
      expect(Math.abs(dot(up, o.direction))).toBeLessThan(1e-6)
      expect(Math.abs(len(up) - 1)).toBeLessThan(1e-6)
    }
    // back to +Z (four 90° rolls = 360°)
    expect(up[0]).toBeCloseTo(0, 6)
    expect(up[1]).toBeCloseTo(0, 6)
    expect(up[2]).toBeCloseTo(1, 6)
  })
})
