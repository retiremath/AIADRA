/**
 * THE TS plane frame (arc 20260716-2 SK-C1.0 S1) — the pure geometry layer
 * of in-context sketching. Mirrors the engine's EP2 `PlaneFrame` exactly:
 * principal axes are `recipe.py::_FRAME_AXES` verbatim (xy: u=X v=Y n=Z ·
 * yz: u=Y v=Z n=X · zx: u=Z v=X n=Y) and `origin_mm` is (0,0,0) for
 * principal planes — face-bound frames arrive from the engine in S2/S3 via
 * Display v1.2 `sketch_frames` and use the same shape.
 *
 * Everything here is PURE math over plane-local millimetres: no three.js, no
 * DOM, no CSS pixels (the ray arrives as world-space origin+direction; the
 * caller owns cameras). `SKETCH_LIFT_MM` is DISPLAY-ONLY (Codex3 bar 3):
 * ray intersection, snapping, and committed coordinates always use the true
 * support plane.
 */
import type { PlaneOrientation } from '../authoring/backend'

export type Vec3 = readonly [number, number, number]

export interface PlaneFrameTS {
  /** Frame origin in world mm ((0,0,0) for principal planes). */
  origin: Vec3
  /** Unit sketch-u axis (world). */
  u: Vec3
  /** Unit sketch-v axis (world). */
  v: Vec3
  /** Unit outward plane normal (world). */
  normal: Vec3
}

/** Display-only lift of sketch curves along the normal (never a fact). */
export const SKETCH_LIFT_MM = 0.05

/** Grazing-ray guard: |ray·normal| below this ⇒ no placement (Codex3 bar 6). */
export const RAY_PLANE_PARALLEL_TOL = 1e-9

const FRAMES: Record<PlaneOrientation, PlaneFrameTS> = {
  xy: { origin: [0, 0, 0], u: [1, 0, 0], v: [0, 1, 0], normal: [0, 0, 1] },
  yz: { origin: [0, 0, 0], u: [0, 1, 0], v: [0, 0, 1], normal: [1, 0, 0] },
  zx: { origin: [0, 0, 0], u: [0, 0, 1], v: [1, 0, 0], normal: [0, 1, 0] },
}

export function principalFrame(orientation: PlaneOrientation): PlaneFrameTS {
  return FRAMES[orientation]
}

/** Plane-local (u, v) mm (+ optional DISPLAY lift w) → world mm. */
export function frameToWorld(f: PlaneFrameTS, u: number, v: number, w = 0): [number, number, number] {
  return [
    f.origin[0] + u * f.u[0] + v * f.v[0] + w * f.normal[0],
    f.origin[1] + u * f.u[1] + v * f.v[1] + w * f.normal[1],
    f.origin[2] + u * f.u[2] + v * f.v[2] + w * f.normal[2],
  ]
}

const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

/**
 * Camera ray ∩ the TRUE (unlifted) infinite sketch plane → plane-local
 * (u, v) mm. Returns null for a grazing/parallel ray or a hit behind the ray
 * origin — a null is "no placement", never a fallback point (Codex3 bar 6).
 */
export function rayPlaneUV(
  f: PlaneFrameTS,
  rayOrigin: Vec3,
  rayDir: Vec3,
): { u: number; v: number } | null {
  const denom = dot(rayDir, f.normal)
  if (Math.abs(denom) < RAY_PLANE_PARALLEL_TOL) return null
  const rel: Vec3 = [f.origin[0] - rayOrigin[0], f.origin[1] - rayOrigin[1], f.origin[2] - rayOrigin[2]]
  const t = dot(rel, f.normal) / denom
  if (t < 0) return null // the plane is behind the camera
  const p: Vec3 = [rayOrigin[0] + t * rayDir[0], rayOrigin[1] + t * rayDir[1], rayOrigin[2] + t * rayDir[2]]
  const local: Vec3 = [p[0] - f.origin[0], p[1] - f.origin[1], p[2] - f.origin[2]]
  return { u: dot(local, f.u), v: dot(local, f.v) }
}

/**
 * The `Sketch view` camera orientation (Codex2 B5.4, ONE authority): from the
 * outward side the look direction is −normal, screen-up is v — therefore
 * screen-right is u. Pure data; the viewport applies it to its camera. The
 * PlaneFrame and every sketch fact are camera-independent.
 */
export function sketchViewOrientation(f: PlaneFrameTS): { direction: Vec3; up: Vec3 } {
  return { direction: [-f.normal[0], -f.normal[1], -f.normal[2]], up: f.v }
}

/**
 * The sketch-entry extent (Codex4 B1.1 / Codex5 B1.1) — the CANONICAL Part's
 * axis-aligned bounds projected onto the sketch plane, expanded by a margin
 * and floored at the minimum sheet. ONE pure derivation consumed by BOTH the
 * support-sheet placement and the camera entry fit, so they cannot disagree
 * (the off-origin case is the test). Presentation state, never Truth.
 */
export function projectedExtent(
  min: Vec3,
  max: Vec3,
  f: PlaneFrameTS,
  margin = 1.15,
  minHalf: readonly [number, number] = [130, 85],
): { halfU: number; halfV: number; centerU: number; centerV: number } {
  let minU = Infinity, maxU = -Infinity, minV = Infinity, maxV = -Infinity
  for (const x of [min[0], max[0]]) {
    for (const y of [min[1], max[1]]) {
      for (const z of [min[2], max[2]]) {
        const lx = x - f.origin[0], ly = y - f.origin[1], lz = z - f.origin[2]
        const u = lx * f.u[0] + ly * f.u[1] + lz * f.u[2]
        const v = lx * f.v[0] + ly * f.v[1] + lz * f.v[2]
        minU = Math.min(minU, u); maxU = Math.max(maxU, u)
        minV = Math.min(minV, v); maxV = Math.max(maxV, v)
      }
    }
  }
  return {
    centerU: (minU + maxU) / 2,
    centerV: (minV + maxV) / 2,
    halfU: Math.max(((maxU - minU) / 2) * margin, minHalf[0]),
    halfV: Math.max(((maxV - minV) / 2) * margin, minHalf[1]),
  }
}

/**
 * The MIRROR of the engine's pinned face-frame rule (S3) — the TRANSIENT
 * drawing frame for a face picked BEFORE its sketch commits. Same rule,
 * verbatim: u = the first global axis X → Y → Z whose in-plane projection
 * exceeds the tolerance, v = n × u, origin = the world origin projected onto
 * the plane. The ENGINE re-derives authoritatively at commit and owns every
 * regeneration (`face_frame.py`); this mirror exists only so the operator can
 * draw on the picked face pre-commit — it never persists, and it applies only
 * to faces the ENGINE classified planar (`planarFaceIds` — Studio never
 * classifies surfaces itself, per the Codex9 boundary).
 */
export function frameFromNormalAndPoint(normal: Vec3, point: Vec3): PlaneFrameTS | null {
  const nLen = Math.hypot(normal[0], normal[1], normal[2])
  if (!(nLen > 1e-9)) return null
  const n: Vec3 = [normal[0] / nLen, normal[1] / nLen, normal[2] / nLen]
  let u: Vec3 | null = null
  for (const g of [[1, 0, 0], [0, 1, 0], [0, 0, 1]] as const) {
    const gn = g[0] * n[0] + g[1] * n[1] + g[2] * n[2]
    const proj: Vec3 = [g[0] - gn * n[0], g[1] - gn * n[1], g[2] - gn * n[2]]
    const m = Math.hypot(proj[0], proj[1], proj[2])
    if (m > 1e-6) {
      u = [proj[0] / m, proj[1] / m, proj[2] / m]
      break
    }
  }
  if (u === null) return null // impossible for a unit normal; refuse, never guess
  const v: Vec3 = [
    n[1] * u[2] - n[2] * u[1],
    n[2] * u[0] - n[0] * u[2],
    n[0] * u[1] - n[1] * u[0],
  ]
  const d = point[0] * n[0] + point[1] * n[1] + point[2] * n[2]
  return { origin: [d * n[0], d * n[1], d * n[2]], u, v, normal: n }
}

/**
 * The plane-pick arbitration rule (Codex2 B4.3, ONE rule for hover AND
 * click): an ELIGIBLE planar canonical face wins over a datum quad; with no
 * eligible face hit, the datum wins. Pure — the viewport feeds it raycast
 * results; S1 passes an empty eligibility set (face picking arrives in S3).
 */
export type PlanePickHit =
  | { kind: 'face'; faceId: string }
  | { kind: 'datum'; orientation: PlaneOrientation }

export function arbitratePlanePick(
  faceHit: string | null,
  datumHit: PlaneOrientation | null,
  planarFaceIds: ReadonlySet<string>,
): PlanePickHit | null {
  if (faceHit !== null && planarFaceIds.has(faceHit)) return { kind: 'face', faceId: faceHit }
  if (datumHit !== null) return { kind: 'datum', orientation: datumHit }
  return null
}
