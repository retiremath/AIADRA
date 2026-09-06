/**
 * The TRANSIENT TS mirror of the engine's placement law (ADR/0044 A3;
 * `aiadra_mechanical/sketch_placement.py` is THE authority — this mirror
 * exists for pre-commit interaction and the dev-lane mock only, and is
 * parity-tested against the engine's literal derivation matrix. Nothing
 * derived here ever persists (the engine mints Truth records).
 */
import type { PlaneFrameTS } from '../sketch/planeFrame'

export type PrincipalOrientation = 'xy' | 'yz' | 'zx'
export type PlacementOrientation = 'right' | 'top' | 'left' | 'bottom'
export type NormalSide = 'positive' | 'negative'

export interface PrincipalRecord {
  kind: 'principal'
  orientation: PrincipalOrientation
}

export interface PlacementRecord {
  support: PrincipalRecord
  orientation_ref: PrincipalRecord
  orientation: PlacementOrientation
  normal_side: NormalSide
}

export const PRINCIPALS: readonly PrincipalOrientation[] = ['xy', 'yz', 'zx']
export const PLACEMENT_ORIENTATIONS: readonly PlacementOrientation[] = ['right', 'top', 'left', 'bottom']
export const NORMAL_SIDES: readonly NormalSide[] = ['positive', 'negative']

export type Vec3 = [number, number, number]

const CANONICAL_NORMALS: Record<PrincipalOrientation, Vec3> = {
  xy: [0, 0, 1],
  yz: [1, 0, 0],
  zx: [0, 1, 0],
}

/** A3.3 — the canonical default reference per support (engine table). */
export const DEFAULT_ORIENTATION_REF: Record<PrincipalOrientation, PrincipalOrientation> = {
  xy: 'yz',
  yz: 'zx',
  zx: 'xy',
}

export function defaultPlacement(support: PrincipalOrientation): PlacementRecord {
  return {
    support: { kind: 'principal', orientation: support },
    orientation_ref: { kind: 'principal', orientation: DEFAULT_ORIENTATION_REF[support] },
    orientation: 'right',
    normal_side: 'positive',
  }
}

export function isPrincipalRecord(rec: unknown): rec is PrincipalRecord {
  if (rec === null || typeof rec !== 'object') return false
  const r = rec as Record<string, unknown>
  return (
    r.kind === 'principal' &&
    PRINCIPALS.includes(r.orientation as PrincipalOrientation) &&
    Object.keys(r).length === 2
  )
}

/** Validate one COMPLETE placement record (A3.2) — the mirror admission. */
export function isPlacementRecord(rec: unknown): rec is PlacementRecord {
  if (rec === null || typeof rec !== 'object') return false
  const r = rec as Record<string, unknown>
  const keys = Object.keys(r).sort()
  if (keys.join(',') !== 'normal_side,orientation,orientation_ref,support') return false
  if (!isPrincipalRecord(r.support) || !isPrincipalRecord(r.orientation_ref)) return false
  if ((r.support as PrincipalRecord).orientation === (r.orientation_ref as PrincipalRecord).orientation) return false
  if (!PLACEMENT_ORIENTATIONS.includes(r.orientation as PlacementOrientation)) return false
  return NORMAL_SIDES.includes(r.normal_side as NormalSide)
}

const cross = (a: Vec3, b: Vec3): Vec3 => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
]
const scale = (a: Vec3, s: number): Vec3 => [a[0] * s, a[1] * s, a[2] * s]

/** A3.5 — the exact derivation, mirrored. Signed normal FIRST, then the
 *  projected reference, then the four-edge mapping; v = n × u both sides.
 *  (Principal normals are mutually orthogonal, so projection is identity.) */
export function deriveFrame(p: PlacementRecord): { u: Vec3; v: Vec3; n: Vec3 } {
  const n0 = CANONICAL_NORMALS[p.support.orientation]
  const n = p.normal_side === 'positive' ? n0 : scale(n0, -1)
  const proj = CANONICAL_NORMALS[p.orientation_ref.orientation]
  let u: Vec3
  let v: Vec3
  if (p.orientation === 'right') {
    u = proj
    v = cross(n, u)
  } else if (p.orientation === 'left') {
    u = scale(proj, -1)
    v = cross(n, u)
  } else if (p.orientation === 'top') {
    v = proj
    u = cross(v, n)
  } else {
    v = scale(proj, -1)
    u = cross(v, n)
  }
  return { u, v, n }
}

/** World mapping through the derived frame (origin = the world origin for
 *  principal supports; display-lane use only). */
export function placementToWorld(p: PlacementRecord, x: number, y: number): Vec3 {
  const { u, v } = deriveFrame(p)
  return [u[0] * x + v[0] * y, u[1] * x + v[1] * y, u[2] * x + v[2] * y]
}

/** I3 (arc 20260905-1): the pre-commit SESSION frame for a create — the
 *  mirror's {u, v, n} as a `PlaneFrameTS` at the world origin (principal
 *  supports). After Close the engine's `sketch_frames[]` row governs. */
export function placementToPlaneFrame(p: PlacementRecord): PlaneFrameTS {
  const { u, v, n } = deriveFrame(p)
  return { origin: [0, 0, 0], u, v, normal: n }
}

/** Creo's sketch view-direction arrow (I3): the sketch view's LOOK direction
 *  (-n, with n signed by Flip) standing at the support origin. Presentation
 *  only — it reverses with Flip and never persists. */
export function placementViewGlyph(p: PlacementRecord): { origin: Vec3; direction: Vec3 } {
  const { n } = deriveFrame(p)
  return { origin: [0, 0, 0], direction: scale(n, -1) }
}
