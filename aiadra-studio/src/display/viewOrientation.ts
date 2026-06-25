/**
 * View orientation table (arc 20260625-1 / 6c; ADR/0033 D9/D10). The pure,
 * three.js-free source of camera orientations for BOTH the standard-view
 * commands and the nav cube — derived + unit-tested headless (the spike proved
 * 33/33 orientations orthonormal and non-degenerate).
 *
 * Convention: right-handed, **Z up** (matching the viewport). `direction` is the
 * LOOK direction (eye → target), the same field shape as the contract's
 * `SnapView.direction`; the camera eye = target − direction·dist.
 *
 * The Z-up trap is the degenerate up at Top/Bottom (look ∥ Z): `upFor` falls back
 * to a horizontal up there, and projects world-up onto the view plane otherwise.
 * A nav-cube FACE region reproduces the matching standard view exactly, so the
 * cube and the buttons share this one table.
 */
export type Vec3 = [number, number, number]

export interface ViewOrientation {
  /** Unit look direction, eye → target. */
  direction: Vec3
  /** Unit camera up, guaranteed ⟂ direction and non-degenerate. */
  up: Vec3
}

export type StandardViewId = 'front' | 'back' | 'right' | 'left' | 'top' | 'bottom' | 'iso'

export const STANDARD_VIEW_IDS: StandardViewId[] = [
  'front', 'back', 'right', 'left', 'top', 'bottom', 'iso',
]

export const STANDARD_VIEW_LABELS: Record<StandardViewId, string> = {
  front: 'Front', back: 'Back', right: 'Right', left: 'Left',
  top: 'Top', bottom: 'Bottom', iso: 'Iso',
}

const ZUP: Vec3 = [0, 0, 1]

const len = (a: Vec3): number => Math.hypot(a[0], a[1], a[2])
// `+ 0` canonicalizes −0 → +0 so orientations compare cleanly and never carry a
// signed zero into the camera math.
const norm = (a: Vec3): Vec3 => {
  const m = len(a)
  return [a[0] / m + 0, a[1] / m + 0, a[2] / m + 0]
}
const dot = (a: Vec3, b: Vec3): number => a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
const cross = (a: Vec3, b: Vec3): Vec3 => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
]

/**
 * A non-degenerate up for a given look direction. Z-up everywhere except when the
 * look is near-parallel to Z (Top/Bottom), where up falls back to ±Y so the basis
 * never collapses.
 */
export function upFor(direction: Vec3): Vec3 {
  const d = norm(direction)
  if (Math.abs(dot(d, ZUP)) > 0.999) {
    return d[2] < 0 ? [0, 1, 0] : [0, -1, 0] // look −Z → up +Y; look +Z → up −Y
  }
  const k = dot(ZUP, d)
  return norm([ZUP[0] - k * d[0], ZUP[1] - k * d[1], ZUP[2] - k * d[2]])
}

/** The look-direction table for the 7 named standard views (pre-normalization). */
const STANDARD_LOOK: Record<StandardViewId, Vec3> = {
  front: [0, 1, 0],
  back: [0, -1, 0],
  right: [-1, 0, 0],
  left: [1, 0, 0],
  top: [0, 0, -1],
  bottom: [0, 0, 1],
  iso: [-1, -1, -1],
}

export function orientationForLook(look: Vec3): ViewOrientation {
  const direction = norm(look)
  return { direction, up: upFor(direction) }
}

export function standardViewOrientation(id: StandardViewId): ViewOrientation {
  return orientationForLook(STANDARD_LOOK[id])
}

export type RegionType = 'face' | 'edge' | 'corner'

export interface CubeRegion {
  /** The signed lattice key, e.g. `[0,1,0]` (a face) or `[1,1,1]` (a corner). */
  cell: Vec3
  type: RegionType
  /** Outward unit normal of the region. */
  normal: Vec3
  /** The orientation a click on this region snaps to (look = −normal). */
  orientation: ViewOrientation
  /** The standard-view id for a FACE region (else null). */
  standardView: StandardViewId | null
}

/** The 26 nav-cube regions: 6 faces + 12 edges + 8 corners. */
export function cubeRegions(): CubeRegion[] {
  const axes = [-1, 0, 1]
  // A face region maps to the standard view whose LOOK direction is −normal
  // (clicking the +Y face puts the camera on the +Y side looking −Y = back).
  const faceOf: Record<string, StandardViewId> = {
    '0,-1,0': 'front', '0,1,0': 'back',
    '1,0,0': 'right', '-1,0,0': 'left',
    '0,0,1': 'top', '0,0,-1': 'bottom',
  }
  const out: CubeRegion[] = []
  for (const x of axes) for (const y of axes) for (const z of axes) {
    if (x === 0 && y === 0 && z === 0) continue
    const cell: Vec3 = [x, y, z]
    const nonzero = cell.filter((c) => c !== 0).length
    const type: RegionType = nonzero === 1 ? 'face' : nonzero === 2 ? 'edge' : 'corner'
    const normal = norm(cell)
    // Click a region → look AT it from outside → look direction = −normal.
    const orientation = orientationForLook([-normal[0], -normal[1], -normal[2]])
    out.push({
      cell,
      type,
      normal,
      orientation,
      standardView: type === 'face' ? faceOf[`${x},${y},${z}`] : null,
    })
  }
  return out
}

/**
 * Roll the camera 90° about its look axis (the nav-cube roll arrows). With up ⟂
 * direction, a 90° rotation is simply ±(direction × up).
 */
export function rollUp(direction: Vec3, up: Vec3, sign: 1 | -1): Vec3 {
  const r = cross(norm(direction), norm(up))
  return sign === 1 ? norm(r) : norm([-r[0], -r[1], -r[2]])
}
