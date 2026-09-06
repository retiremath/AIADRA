/**
 * Creo's Default Orientation as the home/Reset view (Petre 2026-09-05, the
 * datum-plane side-by-side). The trimetric shows THREE distinct planes because
 * its look foreshortens the principal planes by three different factors, so no
 * two datum-plane edges can fall on one screen line — the isometric's hexagon
 * (which read as "just 2 planes": TOP's edges on RIGHT's) is exactly that
 * coincidence. Also pins the Z-up plane-naming law: the plane each face view
 * sees face-on carries that view's name (TOP = xy, FRONT = zx, RIGHT = yz).
 */
import { describe, expect, it } from 'vitest'
import { PLANE_LABELS, type PlaneOrientation } from '../authoring/backend'
import {
  STANDARD_VIEW_LABELS,
  TRIMETRIC_ANGLES,
  datumFrameExtent,
  homeOrientation,
  orientationFromAngles,
  standardViewOrientation,
  type Vec3,
  type ViewOrientation,
} from './viewOrientation'

const dot = (a: Vec3, b: Vec3): number => a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
const cross = (a: Vec3, b: Vec3): Vec3 => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
]
const len = (a: Vec3): number => Math.hypot(a[0], a[1], a[2])
const close = (a: Vec3, b: Vec3, eps = 1e-9): boolean => len([a[0] - b[0], a[1] - b[1], a[2] - b[2]]) < eps

/**
 * Count the pairs of datum-plane border edges that project onto ONE screen
 * line under an orthographic look. Two parallel edges (same axis direction,
 * different planes) are collinear on screen iff their offset lies in
 * span{look, axis}, i.e. offset ⟂ (look × axis).
 */
function coincidentEdgePairs(look: Vec3): number {
  const axes: Vec3[] = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
  type Edge = { axis: number; point: Vec3; plane: number }
  const edges: Edge[] = []
  for (let n = 0; n < 3; n++) {
    const inPlane = [0, 1, 2].filter((i) => i !== n)
    for (const a of inPlane) {
      const b = inPlane.find((i) => i !== a) as number
      for (const s of [-1, 1]) {
        const point: Vec3 = [0, 0, 0]
        point[b] = s
        edges.push({ axis: a, point, plane: n })
      }
    }
  }
  let count = 0
  for (let i = 0; i < edges.length; i++) {
    for (let j = i + 1; j < edges.length; j++) {
      const e = edges[i]
      const f = edges[j]
      if (e.plane === f.plane || e.axis !== f.axis) continue
      const spanNormal = cross(look, axes[e.axis])
      const offset: Vec3 = [f.point[0] - e.point[0], f.point[1] - e.point[1], f.point[2] - e.point[2]]
      if (Math.abs(dot(offset, spanNormal)) < 1e-9 * Math.max(1, len(spanNormal))) count++
    }
  }
  return count
}

const orthonormal = (o: ViewOrientation): boolean =>
  Math.abs(len(o.direction) - 1) < 1e-9 && Math.abs(len(o.up) - 1) < 1e-9 && Math.abs(dot(o.direction, o.up)) < 1e-9

describe('orientationFromAngles (Creo x_angle / y_angle from the front-right-above octant)', () => {
  it('0° turn / 0° tilt is exactly the Front view (look +Y, Z up)', () => {
    const o = orientationFromAngles(0, 0)
    expect(close(o.direction, [0, 1, 0])).toBe(true)
    expect(close(o.up, [0, 0, 1])).toBe(true)
  })

  it('45° turn / atan(1/√2) tilt is the isometric diagonal — the Iso row itself', () => {
    const iso = standardViewOrientation('iso')
    const o = orientationFromAngles(45, (Math.atan(1 / Math.SQRT2) * 180) / Math.PI)
    expect(close(o.direction, iso.direction, 1e-9)).toBe(true)
    expect(close(o.up, iso.up, 1e-9)).toBe(true)
    // the Iso eye sits FRONT-right-above (−Y side), like Creo's isometric
    expect(iso.direction[0]).toBeLessThan(0)
    expect(iso.direction[1]).toBeGreaterThan(0)
    expect(iso.direction[2]).toBeLessThan(0)
  })

  it('a positive turn moves the eye to +X (the Right side); a positive tilt lifts it to +Z', () => {
    const o = orientationFromAngles(20, 30)
    // look = eye → target, so the eye is at −direction
    expect(-o.direction[0]).toBeGreaterThan(0)
    expect(-o.direction[1]).toBeLessThan(0)
    expect(-o.direction[2]).toBeGreaterThan(0)
    expect(orthonormal(o)).toBe(true)
    // world Z stays "up" on screen: up has no negative Z and no roll
    expect(o.up[2]).toBeGreaterThan(0.8)
  })

  it('degenerate tilts (±90°) still yield an orthonormal basis', () => {
    expect(orthonormal(orientationFromAngles(0, 90))).toBe(true)
    expect(orthonormal(orientationFromAngles(33, -90))).toBe(true)
  })
})

describe('the trimetric home (Creo 10 default look)', () => {
  const trimetric = homeOrientation('trimetric', { turnDeg: 0, tiltDeg: 0 })

  it('foreshortens the three principal planes by three DIFFERENT factors — RIGHT narrowest, FRONT widest', () => {
    const [dx, dy, dz] = trimetric.direction.map(Math.abs)
    // apparent plane size ∝ |look · normal|: RIGHT (normal X) < TOP (normal Z) < FRONT (normal Y)
    expect(dx).toBeLessThan(dz)
    expect(dz).toBeLessThan(dy)
    expect(orthonormal(trimetric)).toBe(true)
  })

  it('no two datum-plane edges coincide on screen — the isometric has such coincidences', () => {
    expect(coincidentEdgePairs(trimetric.direction)).toBe(0)
    expect(coincidentEdgePairs(standardViewOrientation('iso').direction)).toBeGreaterThan(0)
  })

  it('pins the angles', () => {
    expect(TRIMETRIC_ANGLES).toEqual({ turnDeg: 20, tiltDeg: 30 })
    expect(close(trimetric.direction, orientationFromAngles(20, 30).direction)).toBe(true)
  })
})

describe('homeOrientation resolves the Default Orientation setting through the ONE authority', () => {
  it('isometric = the Iso row; custom = the given angles; trimetric ignores the custom angles', () => {
    const iso = standardViewOrientation('iso')
    expect(homeOrientation('isometric', { turnDeg: 5, tiltDeg: 5 })).toEqual(iso)
    expect(homeOrientation('custom', { turnDeg: 5, tiltDeg: 12 })).toEqual(orientationFromAngles(5, 12))
    expect(homeOrientation('trimetric', { turnDeg: 5, tiltDeg: 12 })).toEqual(orientationFromAngles(20, 30))
  })
})

describe('the Z-up plane-naming law (TOP = xy, FRONT = zx, RIGHT = yz)', () => {
  const PLANE_NORMAL: Record<PlaneOrientation, Vec3> = {
    xy: [0, 0, 1],
    yz: [1, 0, 0],
    zx: [0, 1, 0],
  }

  it('the plane each face view sees face-on carries that view’s name', () => {
    for (const id of ['front', 'right', 'top'] as const) {
      const look = standardViewOrientation(id).direction
      const faceOn = (Object.keys(PLANE_NORMAL) as PlaneOrientation[]).find(
        (p) => Math.abs(Math.abs(dot(look, PLANE_NORMAL[p])) - 1) < 1e-9,
      )
      expect(faceOn).toBeDefined()
      expect(PLANE_LABELS[faceOn as PlaneOrientation]).toBe(STANDARD_VIEW_LABELS[id].toUpperCase())
    }
  })

  it('is exactly the three names, once each', () => {
    expect(Object.values(PLANE_LABELS).sort()).toEqual(['FRONT', 'RIGHT', 'TOP'])
  })
})

describe('datumFrameExtent (the empty-part frame derives from the scaffold, never a pinned constant)', () => {
  it('the Front view sees exactly the +/-halfSize square', () => {
    const e = datumFrameExtent(standardViewOrientation('front'), 60)
    expect(e.up).toBeCloseTo(60, 9)
    expect(e.right).toBeCloseTo(60, 9)
  })

  it('the trimetric needs MORE height than the isometric (the tall RIGHT plane) — the clip a pinned 80 caused', () => {
    const iso = datumFrameExtent(standardViewOrientation('iso'), 60)
    const tri = datumFrameExtent(homeOrientation('trimetric', { turnDeg: 0, tiltDeg: 0 }), 60)
    expect(iso.up).toBeCloseTo(60 * (Math.sqrt(1 / 6) + Math.sqrt(2 / 3)), 6) // 73.48
    expect(tri.up).toBeGreaterThan(80) // 80.2 > the old DATUM_FRAME_HALF = 80
    expect(tri.up).toBeLessThan(85) // and never beyond a corner's own length (60 * sqrt 2)
    expect(tri.right).toBeLessThan(60 * Math.SQRT2 + 1e-9)
  })

  it('never exceeds a corner length for any angles (the frame margin is a bound, not a guess)', () => {
    for (const turn of [-170, -45, 0, 20, 45, 90, 135]) {
      for (const tilt of [-80, -30, 0, 30, 60, 89]) {
        const e = datumFrameExtent(orientationFromAngles(turn, tilt), 60)
        expect(e.up).toBeLessThanOrEqual(60 * Math.SQRT2 + 1e-9)
        expect(e.right).toBeLessThanOrEqual(60 * Math.SQRT2 + 1e-9)
        expect(e.up).toBeGreaterThan(0)
      }
    }
  })
})
