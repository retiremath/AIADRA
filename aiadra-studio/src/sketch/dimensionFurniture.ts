/**
 * Dimension FURNITURE (W-4; Claude14 §3 as amended by Claude15 B5) — the
 * Creo-style rendering of the engine's derived annotations: extension lines,
 * offset dimension lines with arrowheads, the angle arc, the radius leader,
 * and screen-legible weak text — replacing the raw anchor-segment drawing
 * that failed Petre's walk.
 *
 * BATCH-SHAPED, one placement owner (Codex14 B5): this module receives the
 * whole annotation set + solved entities + frame + `worldPerPixel` and owns
 * the profile bbox, the outside-side choice, orientation grouping, lane
 * staggering (sorted by value; equal values tie-broken by semantic id), and
 * every pixel→world conversion. `profileOverlay` only installs/disposes the
 * returned primitives.
 *
 * D6 floor: this module draws ONLY engine values. It converts world↔plane
 * coordinates and lays out furniture geometry, but the number a label shows
 * is `formatAnnotation(engine value)` verbatim — nothing here measures,
 * solves, or re-derives a dimension.
 */
import type { ConstraintGlyph, ProfileAnnotation } from '../display/contract'
import { frameToWorld, SKETCH_LIFT_MM, type PlaneFrameTS } from './planeFrame'
import { formatAnnotation } from './annotationFormat'

export interface FurnitureGeometry {
  points: { id: string; world: [number, number, number] }[]
  segments: { id: string; start: string; end: string }[]
  circles: { id: string; center: string; radius_mm: number }[]
  annotations: ProfileAnnotation[]
  constraint_glyphs: ConstraintGlyph[]
}

/** World-space primitives the overlay installs verbatim. */
export interface FurniturePrimitives {
  /** Polylines (extension lines, dimension lines, arcs, arrowheads, ticks). */
  lines: [number, number, number][][]
  /** Weak-dim value labels; `heightMm` is the screen-constant text height. */
  labels: { text: string; at: [number, number, number]; heightMm: number }[]
  /** Constraint glyph labels (H/V), same sizing authority. */
  glyphs: { text: string; at: [number, number, number]; heightMm: number }[]
}

// Pixel constants — every one crosses to mm through worldPerPixel, so the
// furniture reads the same at every zoom (the model-scaled sprites were the
// illegibility half of W-4).
const TEXT_PX = 14
const GLYPH_PX = 12
const ARROW_PX = 7
const GAP_PX = 4
const OVERSHOOT_PX = 5
const BASE_OFFSET_PX = 26
const LANE_SPACING_PX = 24
const TICK_PX = 6
const TEXT_LIFT_PX = 9
const ANGLE_RADIUS_PX = 36
const LEADER_PX = 22

type UV = { u: number; v: number }

const worldToLocal = (f: PlaneFrameTS, w: [number, number, number]): UV => {
  const dx = w[0] - f.origin[0]
  const dy = w[1] - f.origin[1]
  const dz = w[2] - f.origin[2]
  return {
    u: dx * f.u[0] + dy * f.u[1] + dz * f.u[2],
    v: dx * f.v[0] + dy * f.v[1] + dz * f.v[2],
  }
}

export function buildDimensionFurniture(
  geometry: FurnitureGeometry,
  frame: PlaneFrameTS,
  worldPerPixel: number,
): FurniturePrimitives {
  const out: FurniturePrimitives = { lines: [], labels: [], glyphs: [] }
  const wpp = worldPerPixel > 0 ? worldPerPixel : 1
  const px = (n: number) => n * wpp

  const local = new Map<string, UV>()
  for (const p of geometry.points) local.set(p.id, worldToLocal(frame, p.world))
  const segById = new Map(geometry.segments.map((s) => [s.id, s]))
  const circById = new Map(geometry.circles.map((c) => [c.id, c]))

  const W = (u: number, v: number): [number, number, number] =>
    frameToWorld(frame, u, v, SKETCH_LIFT_MM)
  const line = (...pts: UV[]) => out.lines.push(pts.map((p) => W(p.u, p.v)))

  // The profile bbox — the outside-side authority. Circles extend it by
  // their radius so a dim never lands inside a drawn circle.
  let minU = Infinity, maxU = -Infinity, minV = Infinity, maxV = -Infinity
  for (const p of local.values()) {
    minU = Math.min(minU, p.u); maxU = Math.max(maxU, p.u)
    minV = Math.min(minV, p.v); maxV = Math.max(maxV, p.v)
  }
  for (const c of geometry.circles) {
    const ctr = local.get(c.center)
    if (!ctr) continue
    minU = Math.min(minU, ctr.u - c.radius_mm); maxU = Math.max(maxU, ctr.u + c.radius_mm)
    minV = Math.min(minV, ctr.v - c.radius_mm); maxV = Math.max(maxV, ctr.v + c.radius_mm)
  }
  if (!isFinite(minU)) return out
  const midU = (minU + maxU) / 2
  const midV = (minV + maxV) / 2

  const arrow = (tipU: number, tipV: number, dirU: number, dirV: number) => {
    // A V-head at the tip, pointing along (dirU, dirV) (unit).
    const L = px(ARROW_PX)
    const bU = tipU - dirU * L
    const bV = tipV - dirV * L
    const pU = -dirV, pV = dirU
    line({ u: tipU, v: tipV }, { u: bU + pU * L * 0.38, v: bV + pV * L * 0.38 })
    line({ u: tipU, v: tipV }, { u: bU - pU * L * 0.38, v: bV - pV * L * 0.38 })
  }

  const label = (text: string, u: number, v: number) =>
    out.labels.push({ text, at: W(u, v), heightMm: px(TEXT_PX) })

  // ---- Grouping (the batch policy) -------------------------------------
  type Linear = { a: ProfileAnnotation; point: UV }
  const groups = new Map<string, Linear[]>()
  const others: ProfileAnnotation[] = []
  for (const a of geometry.annotations) {
    if (a.kind === 'position_x' || a.kind === 'position_y') {
      const point = local.get(a.entities[0])
      if (!point) continue // dangling — the validator refuses committed packages
      const key =
        a.kind === 'position_x'
          ? `h:${point.v <= midV ? 'below' : 'above'}`
          : `v:${point.u <= midU ? 'left' : 'right'}`
      const bucket = groups.get(key)
      if (bucket) bucket.push({ a, point })
      else groups.set(key, [{ a, point }])
    } else {
      others.push(a)
    }
  }

  // Deterministic order: groups by key; within a group by value, ties by
  // semantic id (Codex14 B5). Lane 0 is nearest the profile.
  for (const key of [...groups.keys()].sort()) {
    const members = groups.get(key)!
    members.sort((x, y) => x.a.value - y.a.value || (x.a.id < y.a.id ? -1 : 1))
    members.forEach(({ a, point }, lane) => {
      const off = px(BASE_OFFSET_PX) + lane * px(LANE_SPACING_PX)
      if (a.kind === 'position_x') {
        const laneV = key === 'h:below' ? minV - off : maxV + off
        const dir = Math.sign(laneV - point.v) || 1
        // extension line from the point toward the lane, with gap + overshoot
        line(
          { u: point.u, v: point.v + dir * px(GAP_PX) },
          { u: point.u, v: laneV + dir * px(OVERSHOOT_PX) },
        )
        // reference tick where the dim meets the v-axis (u = 0)
        line({ u: 0, v: laneV - px(TICK_PX) }, { u: 0, v: laneV + px(TICK_PX) })
        // dimension line + inward-facing arrowheads at both ends
        line({ u: 0, v: laneV }, { u: point.u, v: laneV })
        const s = Math.sign(point.u) || 1
        arrow(point.u, laneV, s, 0)
        arrow(0, laneV, -s, 0)
        label(formatAnnotation(a), point.u / 2, laneV + px(TEXT_LIFT_PX))
      } else {
        const laneU = key === 'v:left' ? minU - off : maxU + off
        const dir = Math.sign(laneU - point.u) || 1
        line(
          { u: point.u + dir * px(GAP_PX), v: point.v },
          { u: laneU + dir * px(OVERSHOOT_PX), v: point.v },
        )
        line({ u: laneU - px(TICK_PX), v: 0 }, { u: laneU + px(TICK_PX), v: 0 })
        line({ u: laneU, v: 0 }, { u: laneU, v: point.v })
        const s = Math.sign(point.v) || 1
        arrow(laneU, point.v, 0, s)
        arrow(laneU, 0, 0, -s)
        // Codex17 B2: the value sits CENTRED along the measured span and is
        // displaced PERPENDICULAR to the vertical dimension line — outside
        // it (further from the profile), never along/over it.
        const outward = key === 'v:left' ? -1 : 1
        label(formatAnnotation(a), laneU + outward * px(TEXT_LIFT_PX), point.v / 2)
      }
    })
  }

  // ---- Length dims: the SAME batch lane policy (Codex17 B3) --------------
  // A fallback length is still a linear dimension: group by (line
  // orientation mod 180°, outside-side normal direction) so same-side
  // parallel/collinear lengths stagger deterministically, exactly like the
  // position groups — sorted by value, ties by semantic id.
  type LengthPrep = {
    a: ProfileAnnotation
    A: UV; B: UV
    tU: number; tV: number
    nU: number; nV: number
  }
  const lengthGroups = new Map<string, LengthPrep[]>()
  for (const a of others) {
    if (a.kind !== 'length') continue
    const seg = segById.get(a.entities[0])
    const A = seg && local.get(seg.start)
    const B = seg && local.get(seg.end)
    if (!seg || !A || !B) continue
    const len = Math.hypot(B.u - A.u, B.v - A.v)
    if (!(len > 0)) continue
    const tU = (B.u - A.u) / len, tV = (B.v - A.v) / len
    let nU = -tV, nV = tU
    const mU = (A.u + B.u) / 2, mV = (A.v + B.v) / 2
    if ((midU - mU) * nU + (midV - mV) * nV > 0) { nU = -nU; nV = -nV }
    const lineAngle = ((Math.atan2(tV, tU) % Math.PI) + Math.PI) % Math.PI
    const key = `L:${lineAngle.toFixed(6)}:${Math.atan2(nV, nU).toFixed(6)}`
    const bucket = lengthGroups.get(key)
    const prep = { a, A, B, tU, tV, nU, nV }
    if (bucket) bucket.push(prep)
    else lengthGroups.set(key, [prep])
  }
  for (const key of [...lengthGroups.keys()].sort()) {
    const members = lengthGroups.get(key)!
    members.sort((x, y) => x.a.value - y.a.value || (x.a.id < y.a.id ? -1 : 1))
    members.forEach(({ a, A, B, tU, tV, nU, nV }, lane) => {
      const off = px(BASE_OFFSET_PX) + lane * px(LANE_SPACING_PX)
      const ext = (P: UV) =>
        line(
          { u: P.u + nU * px(GAP_PX), v: P.v + nV * px(GAP_PX) },
          { u: P.u + nU * (off + px(OVERSHOOT_PX)), v: P.v + nV * (off + px(OVERSHOOT_PX)) },
        )
      ext(A); ext(B)
      const A2 = { u: A.u + nU * off, v: A.v + nV * off }
      const B2 = { u: B.u + nU * off, v: B.v + nV * off }
      line(A2, B2)
      arrow(A2.u, A2.v, -tU, -tV)
      arrow(B2.u, B2.v, tU, tV)
      label(
        formatAnnotation(a),
        (A2.u + B2.u) / 2 + nU * px(TEXT_LIFT_PX),
        (A2.v + B2.v) / 2 + nV * px(TEXT_LIFT_PX),
      )
    })
  }

  // ---- Non-linear kinds -------------------------------------------------
  for (const a of others) {
    if (a.kind === 'angle') {
      const seg = segById.get(a.entities[0])
      const A = seg && local.get(seg.start)
      const B = seg && local.get(seg.end)
      if (!seg || !A || !B) continue
      const segLen = Math.hypot(B.u - A.u, B.v - A.v)
      // Codex14-accepted: the arc anchors at the START vertex, between the
      // +u reference ray and the directed segment ray. The swept angle IS
      // the engine value (CCW from +u) — never re-measured from geometry.
      const R = Math.min(px(ANGLE_RADIUS_PX), segLen * 0.45)
      const phi = (a.value * Math.PI) / 180
      line({ u: A.u, v: A.v }, { u: A.u + R + px(GAP_PX), v: A.v }) // the +u ray
      const steps = Math.max(8, Math.ceil(a.value / 6))
      const arc: UV[] = []
      for (let i = 0; i <= steps; i++) {
        const t = (phi * i) / steps
        arc.push({ u: A.u + R * Math.cos(t), v: A.v + R * Math.sin(t) })
      }
      line(...arc)
      const mid = phi / 2
      label(
        formatAnnotation(a),
        A.u + (R + px(TEXT_LIFT_PX + 4)) * Math.cos(mid),
        A.v + (R + px(TEXT_LIFT_PX + 4)) * Math.sin(mid),
      )
    } else if (a.kind === 'radius') {
      const circle = circById.get(a.entities[0])
      const C = circle && local.get(circle.center)
      if (!circle || !C) continue
      const d = Math.SQRT1_2 // the 45° leader direction
      const rim = { u: C.u + circle.radius_mm * d, v: C.v + circle.radius_mm * d }
      const end = { u: rim.u + px(LEADER_PX) * d, v: rim.v + px(LEADER_PX) * d }
      line(rim, end)
      arrow(rim.u, rim.v, -d, -d)
      label(`R ${formatAnnotation(a)}`, end.u + px(6), end.v + px(TEXT_LIFT_PX - 3))
    }
  }

  // ---- Constraint glyphs (H/V) — the same screen-constant sizing --------
  for (const g of geometry.constraint_glyphs) {
    out.glyphs.push({
      text: g.kind === 'horizontal' ? 'H' : 'V',
      at: [g.anchor[0], g.anchor[1], g.anchor[2]],
      heightMm: px(GLYPH_PX),
    })
  }

  return out
}
