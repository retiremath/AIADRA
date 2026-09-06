/**
 * SK-C1.0 S1 — the pure plane-frame layer: principal frames mirror the
 * engine's `_FRAME_AXES` verbatim; ray-to-plane placement in plane-local mm
 * with the grazing guard; the Sketch-view orientation mapping (screen-right
 * = u, screen-up = v) for ALL THREE principal frames (Codex3 bar 6); the
 * ONE face-over-datum arbitration rule.
 */
import { describe, expect, it } from 'vitest'
import {
  arbitratePlanePick,
  frameFromNormalAndPoint,
  frameToWorld,
  principalFrame,
  projectedExtent,
  rayPlaneUV,
  sketchViewOrientation,
  SKETCH_LIFT_MM,
  type Vec3,
} from './planeFrame'

const cross = (a: Vec3, b: Vec3): Vec3 => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
]
const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

describe('principal frames — the engine mirror', () => {
  it('matches recipe.py _FRAME_AXES verbatim, right-handed, origin (0,0,0)', () => {
    const expected = {
      xy: { u: [1, 0, 0], v: [0, 1, 0], normal: [0, 0, 1] },
      yz: { u: [0, 1, 0], v: [0, 0, 1], normal: [1, 0, 0] },
      zx: { u: [0, 0, 1], v: [1, 0, 0], normal: [0, 1, 0] },
    } as const
    for (const ori of ['xy', 'yz', 'zx'] as const) {
      const f = principalFrame(ori)
      expect(f.u).toEqual(expected[ori].u)
      expect(f.v).toEqual(expected[ori].v)
      expect(f.normal).toEqual(expected[ori].normal)
      expect(f.origin).toEqual([0, 0, 0])
      // orthonormal + right-handed: normal = u × v
      expect(cross(f.u, f.v)).toEqual([...f.normal])
      expect(dot(f.u, f.v)).toBe(0)
    }
  })
})

describe('frameToWorld / rayPlaneUV — plane-local millimetres', () => {
  it('round-trips a point through world space on every principal frame', () => {
    for (const ori of ['xy', 'yz', 'zx'] as const) {
      const f = principalFrame(ori)
      const world = frameToWorld(f, 12.5, -7.25)
      // a ray straight down the normal onto that point
      const origin: Vec3 = [world[0] + 100 * f.normal[0], world[1] + 100 * f.normal[1], world[2] + 100 * f.normal[2]]
      const dir: Vec3 = [-f.normal[0], -f.normal[1], -f.normal[2]]
      const uv = rayPlaneUV(f, origin, dir)
      expect(uv).not.toBeNull()
      expect(uv!.u).toBeCloseTo(12.5, 9)
      expect(uv!.v).toBeCloseTo(-7.25, 9)
    }
  })

  it('an OBLIQUE ray still lands exact plane-local mm (orbiting never breaks placement)', () => {
    const f = principalFrame('xy')
    const target = frameToWorld(f, 30, 40) // (30, 40, 0)
    const origin: Vec3 = [target[0] + 50, target[1] - 80, target[2] + 60]
    const len = Math.hypot(-50, 80, -60)
    const dir: Vec3 = [-50 / len, 80 / len, -60 / len]
    const uv = rayPlaneUV(f, origin, dir)
    expect(uv!.u).toBeCloseTo(30, 9)
    expect(uv!.v).toBeCloseTo(40, 9)
  })

  it('grazing/parallel rays and behind-the-camera planes yield NO placement (never a fallback)', () => {
    const f = principalFrame('xy')
    // parallel to the plane
    expect(rayPlaneUV(f, [0, 0, 10], [1, 0, 0])).toBeNull()
    // the plane behind the ray
    expect(rayPlaneUV(f, [0, 0, 10], [0, 0, 1])).toBeNull()
  })

  it('the lift is display-only: rayPlaneUV ignores it; frameToWorld applies it on request', () => {
    const f = principalFrame('zx')
    const lifted = frameToWorld(f, 5, 5, SKETCH_LIFT_MM)
    const flat = frameToWorld(f, 5, 5)
    expect(lifted[1] - flat[1]).toBeCloseTo(SKETCH_LIFT_MM, 12) // zx normal = +Y
  })
})

describe('sketchViewOrientation — the ONE camera mapping (Codex3 bar 6)', () => {
  it('look = −normal and up = v for all three principal frames → screen-right = u', () => {
    for (const ori of ['xy', 'yz', 'zx'] as const) {
      const f = principalFrame(ori)
      const o = sketchViewOrientation(f)
      expect(o.direction).toEqual([-f.normal[0], -f.normal[1], -f.normal[2]])
      expect(o.up).toEqual(f.v)
      // screen-right = up × (−direction)... verify right = u:
      const right = cross(o.up, [-o.direction[0], -o.direction[1], -o.direction[2]] as Vec3)
      expect(right).toEqual([...f.u])
    }
  })
})

describe('projectedExtent — ONE derivation for sheet AND camera (Codex5 B1.1)', () => {
  it('an OFF-ORIGIN box projects to a non-zero center; margin + minimum floor apply', () => {
    const f = principalFrame('xy')
    // a 40×20×10 box centered at (100, 50, 5) — nowhere near the origin
    const e = projectedExtent([80, 40, 0], [120, 60, 10], f)
    expect(e.centerU).toBeCloseTo(100, 9)
    expect(e.centerV).toBeCloseTo(50, 9)
    expect(e.halfU).toBe(130) // 20*1.15=23 < the 130 floor
    expect(e.halfV).toBe(85)
    // a LARGE part beats the floor with the margin applied
    const big = projectedExtent([-200, -150, 0], [200, 150, 10], f)
    expect(big.halfU).toBeCloseTo(200 * 1.15, 9)
    expect(big.halfV).toBeCloseTo(150 * 1.15, 9)
    expect(big.centerU).toBeCloseTo(0, 9)
  })

  it('projects through a NON-xy frame correctly (zx: u=Z, v=X)', () => {
    const f = principalFrame('zx')
    const e = projectedExtent([10, 0, 30], [20, 5, 50], f) // x∈[10,20], z∈[30,50]
    expect(e.centerU).toBeCloseTo(40, 9) // u = z
    expect(e.centerV).toBeCloseTo(15, 9) // v = x
  })
})

describe('arbitratePlanePick — face-over-datum, ONE rule', () => {
  const planar = new Set(['feat_0002:face:cap_hi'])
  it('an eligible planar face beats a datum; an UNSUPPORTED face in front is reported for refusal (I3 Codex3 B2)', () => {
    const cap = { faceId: 'feat_0002:face:cap_hi', distance: 10 }
    const wall = { faceId: 'feat_0002:face:outer_wall', distance: 10 }
    const xy = { orientation: 'xy' as const, distance: 30 }
    expect(arbitratePlanePick(cap, xy, planar)).toEqual({ kind: 'face', faceId: 'feat_0002:face:cap_hi' })
    // the wall is not planar: it is what was clicked, so the datum behind it never wins
    expect(arbitratePlanePick(wall, xy, planar)).toEqual({ kind: 'unsupported-face', faceId: 'feat_0002:face:outer_wall' })
    // a datum IN FRONT of an unsupported face still wins
    expect(arbitratePlanePick({ ...wall, distance: 50 }, xy, planar)).toEqual({ kind: 'datum', orientation: 'xy' })
  })
  it('datum alone picks the datum; nothing yields null; an EMPTY eligibility set (principal-only) reports a clicked face as unsupported', () => {
    expect(arbitratePlanePick(null, { orientation: 'yz', distance: 5 }, planar)).toEqual({ kind: 'datum', orientation: 'yz' })
    expect(arbitratePlanePick(null, null, planar)).toBeNull()
    const cap = { faceId: 'feat_0002:face:cap_hi', distance: 1 }
    expect(arbitratePlanePick(cap, { orientation: 'zx', distance: 2 }, new Set())).toEqual({ kind: 'unsupported-face', faceId: 'feat_0002:face:cap_hi' })
    expect(arbitratePlanePick(cap, null, new Set())).toEqual({ kind: 'unsupported-face', faceId: 'feat_0002:face:cap_hi' })
  })
})

describe('frameFromNormalAndPoint — the S3 TRANSIENT mirror of the pinned engine rule', () => {
  it('a +Z cap at depth 10 reproduces the engine frame EXACTLY (test_face_frame cap_top)', () => {
    // face_frame.py on the box top cap: u from global X, v = n x u,
    // origin = the world origin projected onto the plane = (0, 0, 10) —
    // REGARDLESS of where on the face the pick landed.
    const f = frameFromNormalAndPoint([0, 0, 1], [7, 3, 10])
    expect(f).not.toBeNull()
    expect(f!.u).toEqual([1, 0, 0])
    expect(f!.v).toEqual([0, 1, 0])
    expect(f!.normal).toEqual([0, 0, 1])
    expect(f!.origin).toEqual([0, 0, 10])
  })

  it('an X-parallel normal tie-breaks to Y (the engine wall rule), right-handed v = n x u', () => {
    const f = frameFromNormalAndPoint([1, 0, 0], [30, 5, 5])
    expect(f!.u).toEqual([0, 1, 0])
    expect(f!.v).toEqual([0, 0, 1]) // n x u
    expect(f!.origin).toEqual([30, 0, 0]) // origin projection, not the pick point
  })

  it('an oblique normal yields an orthonormal right-handed frame with the projected origin', () => {
    const f = frameFromNormalAndPoint([1, 1, 1], [1, 1, 1])!
    expect(Math.hypot(...f.u)).toBeCloseTo(1, 12)
    expect(Math.hypot(...f.v)).toBeCloseTo(1, 12)
    expect(dot(f.u, f.normal)).toBeCloseTo(0, 12)
    expect(dot(f.v, f.normal)).toBeCloseTo(0, 12)
    expect(dot(f.u, f.v)).toBeCloseTo(0, 12)
    const rh = cross(f.normal, f.u)
    expect(rh[0]).toBeCloseTo(f.v[0], 12)
    expect(rh[1]).toBeCloseTo(f.v[1], 12)
    expect(rh[2]).toBeCloseTo(f.v[2], 12)
    // point (1,1,1) lies ON the plane -> the projected origin IS (1,1,1)
    expect(f.origin[0]).toBeCloseTo(1, 12)
    expect(f.origin[1]).toBeCloseTo(1, 12)
    expect(f.origin[2]).toBeCloseTo(1, 12)
  })

  it('normalizes an unnormalized input normal; refuses a zero normal', () => {
    const f = frameFromNormalAndPoint([0, 0, 5], [0, 0, 10])!
    expect(f.normal).toEqual([0, 0, 1])
    expect(f.origin).toEqual([0, 0, 10])
    expect(frameFromNormalAndPoint([0, 0, 0], [1, 2, 3])).toBeNull()
  })
})
