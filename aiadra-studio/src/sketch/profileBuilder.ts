/**
 * The drawing tools, as ONE fact graph (ADR/0044 A4; arc 20260730-1).
 *
 * Line, polyline, rectangle and circle are UI SUGAR. Each builds the SAME
 * `ProfilePayload` an agent would author directly — there are deliberately no
 * per-tool operations, and that is precisely what keeps the G-AI gate true:
 * every modeling capability a human has through this UI is reachable through
 * the typed operation contract with no renderer in the loop.
 *
 * A rectangle is therefore not a primitive. It is four points, four segments
 * and four axis facts — which is exactly why dragging one corner of a
 * committed rectangle keeps it rectangular: the facts are real, and the
 * engine re-solves them. Creo behaves the same way for the same reason.
 *
 * The builder OWNS its key namespace (`p1`, `s1`, `f1`, …) but never mints an
 * engine id. Keys are call-scoped: the engine mints ids on commit and the
 * refreshed Display is the id authority (Codex3 B2 — the key->id wire map was
 * withdrawn because it could not cross honestly).
 */
import type {
  NewCircle,
  NewFact,
  NewPoint,
  NewSegment,
  ProfilePayload,
} from './profileTypes'
import { proposeAxisFact, type AxisFact, type DrawnPoint } from './snapProposal'

/** A key allocator scoped to ONE payload — never an engine id. */
export class KeyScope {
  // Per-prefix counters, so keys read as `p1 p2 / s1 / f1` rather than
  // `p1 p2 s3 f4`. Uniqueness across the whole call still holds — the
  // prefixes never overlap.
  private readonly n = new Map<string, number>()
  next(prefix: string): string {
    const k = (this.n.get(prefix) ?? 0) + 1
    this.n.set(prefix, k)
    return `${prefix}${k}`
  }
}

export interface BuildOptions {
  /** `sketch.snapAngleToleranceDeg` — 0 disables axis proposals. */
  snapAngleToleranceDeg: number
  /** Whether the tool CLOSES its point run back to the first point. */
  closed?: boolean
}

/**
 * Build a payload for an open or closed run of drawn points.
 *
 * This is the single implementation behind the line tool (2 points, open),
 * the polyline tool (N points, open) and any closed contour. Each consecutive
 * pair becomes a segment, and each segment independently gets at most one
 * proposed axis fact.
 */
export function buildPolyline(points: DrawnPoint[], opts: BuildOptions): ProfilePayload {
  const closed = opts.closed === true
  if (points.length < 2) {
    throw new Error('buildPolyline needs at least two points')
  }
  if (closed && points.length < 3) {
    throw new Error('a closed run needs at least three points')
  }
  const scope = new KeyScope()
  const pts: NewPoint[] = points.map((p) => ({ key: scope.next('p'), x: p.u, y: p.v }))
  const segs: NewSegment[] = []
  const facts: NewFact[] = []

  const lastIndex = closed ? points.length : points.length - 1
  for (let i = 0; i < lastIndex; i++) {
    const j = (i + 1) % points.length
    const key = scope.next('s')
    segs.push({ key, start: { key: pts[i].key }, end: { key: pts[j].key } })
    const fact = proposeAxisFact(points[i], points[j], opts.snapAngleToleranceDeg)
    if (fact !== null) {
      facts.push({ key: scope.next('f'), kind: fact, target: { key } })
    }
  }
  return facts.length > 0
    ? { points: pts, segments: segs, facts }
    : { points: pts, segments: segs }
}

/**
 * Build an axis-aligned rectangle from two opposite drag corners.
 *
 * Unlike the polyline lane this does NOT go through the snap tolerance: a
 * rectangle tool means the user asked for right angles, so all four facts are
 * asserted outright. A degenerate drag (zero width or height) throws rather
 * than emitting a graph the engine would refuse for non-collapse — the caller
 * should have gated on `isDrag` first.
 */
export function buildRectangle(a: DrawnPoint, b: DrawnPoint): ProfilePayload {
  if (a.u === b.u || a.v === b.v) {
    throw new Error('a rectangle needs a non-degenerate drag')
  }
  const scope = new KeyScope()
  // Corner order matters: consecutive corners must share an axis, or the
  // alternating horizontal/vertical facts would be wrong.
  const corners: DrawnPoint[] = [
    { u: a.u, v: a.v },
    { u: b.u, v: a.v },
    { u: b.u, v: b.v },
    { u: a.u, v: b.v },
  ]
  const pts: NewPoint[] = corners.map((c) => ({ key: scope.next('p'), x: c.u, y: c.v }))
  const segs: NewSegment[] = []
  const facts: NewFact[] = []
  const kinds: AxisFact[] = ['horizontal', 'vertical', 'horizontal', 'vertical']
  for (let i = 0; i < 4; i++) {
    const key = scope.next('s')
    segs.push({
      key,
      start: { key: pts[i].key },
      end: { key: pts[(i + 1) % 4].key },
    })
    facts.push({ key: scope.next('f'), kind: kinds[i] as 'horizontal' | 'vertical', target: { key } })
  }
  return { points: pts, segments: segs, facts }
}

/** Build a circle from its centre and a radius point. */
export function buildCircle(center: DrawnPoint, rim: DrawnPoint): ProfilePayload {
  const radius = Math.hypot(rim.u - center.u, rim.v - center.v)
  if (!(radius > 0)) throw new Error('a circle needs a non-zero radius')
  const scope = new KeyScope()
  const c = { key: scope.next('p'), x: center.u, y: center.v }
  return {
    points: [c],
    circles: [{ key: scope.next('o'), center: { key: c.key }, radius_mm: radius }],
  }
}

/** Merge payloads drawn one after another into ONE graph, re-keying so the
 *  call-wide uniqueness rule holds. Drawing a rectangle and then a circle is
 *  one sketch, not two. */
export function mergeProfiles(parts: ProfilePayload[]): ProfilePayload {
  const scope = new KeyScope()
  const points: NewPoint[] = []
  const segments: NewSegment[] = []
  const circles: NewCircle[] = []
  const facts: NewFact[] = []

  for (const part of parts) {
    const remap = new Map<string, string>()
    const rekey = (rec: { key?: string; id?: string }, prefix: string): string => {
      if (rec.id !== undefined) {
        throw new Error('mergeProfiles composes freshly drawn parts; committed ids belong to an edit payload')
      }
      const fresh = scope.next(prefix)
      remap.set(rec.key as string, fresh)
      return fresh
    }
    const ref = (r: { key?: string; id?: string }): { key: string } => {
      const mapped = r.key !== undefined ? remap.get(r.key) : undefined
      if (mapped === undefined) throw new Error(`mergeProfiles: unresolved reference ${JSON.stringify(r)}`)
      return { key: mapped }
    }
    for (const p of part.points ?? []) points.push({ ...p, key: rekey(p, 'p') })
    for (const s of part.segments ?? []) {
      segments.push({ key: rekey(s, 's'), start: ref(s.start), end: ref(s.end) })
    }
    for (const c of part.circles ?? []) {
      circles.push({ key: rekey(c, 'o'), center: ref(c.center), radius_mm: c.radius_mm })
    }
    for (const f of part.facts ?? []) {
      facts.push({ key: rekey(f, 'f'), kind: f.kind, target: ref(f.target) })
    }
  }
  const out: ProfilePayload = { points }
  if (segments.length > 0) out.segments = segments
  if (circles.length > 0) out.circles = circles
  if (facts.length > 0) out.facts = facts
  return out
}
