/**
 * The typed, VERSION-GUARDED runtime decoder for an inspected Part (S2;
 * arc 20260714-3 Codex1 B2). Ring 2 `inspect` returns the raw sidecar DTO;
 * everything Studio derives from Truth — the model tree, the sketch-wire
 * overlay, selection targets, authoring eligibility — reads THIS decoded
 * shape, never the raw JSON. One decoder, both lanes (the bridge view and the
 * honest mock feed the same function), fail-loud on anything unexpected:
 * a malformed or newer-versioned sidecar becomes a partContext ERROR state,
 * never a silently wrong tree.
 */
import type { Pt } from '../sketch/contour'
import type { PlaneOrientation } from './backend'

/** The ONE engine whose recipes this decoder is authorized to interpret
 *  (Codex3 B1 — the native-engine boundary reaches the renderer): mechanical
 *  payloads (rings, planes, dependencies, eligibility) are read ONLY under
 *  `engine === 'mechanical'` + a supported adapter series. Anything else
 *  stays a GENERIC tree entry — visible, never interpreted. */
const MECHANICAL_ENGINE = 'mechanical'

/** The adapter payload series this decoder understands. A KNOWN mechanical
 *  record written by a different series fails loud/closed (forward-compat is
 *  an explicit decision, not a guess) — mirrors the settings registry's
 *  version discipline. */
const KNOWN_ADAPTER_SERIES = '0.1.'

export interface InspectedSketch {
  kind: 'sketch'
  id: string
  plane: PlaneOrientation
  /** The wire polyline(s) in plane (u,v) coords — one closed ring per
   *  primitive. Contours use their segment chain; rectangles their 4 corners. */
  rings: Pt[][]
}

export interface InspectedBase {
  kind: 'extrude' | 'revolve'
  id: string
  /** The consumed sketch's feature id (canonical `depends_on_feature_ids`). */
  consumesSketchId: string
  depthMm: number | null
}

export interface InspectedOther {
  kind: 'other'
  id: string
  featureType: string
}

export type InspectedFeature = InspectedSketch | InspectedBase | InspectedOther

export interface InspectedPart {
  number: string
  name: string
  uuid: string
  /** Recipe order, verbatim from Truth. */
  features: InspectedFeature[]
  /** B3's UI mirror: base-creation eligibility comes from INSPECTED state. */
  hasExtrudeBase: boolean
  hasRevolveBase: boolean
}

function fail(msg: string): never {
  throw new Error(`inspect decode: ${msg}`)
}

function str(v: unknown, what: string): string {
  if (typeof v !== 'string' || v.length === 0) fail(`${what} must be a non-empty string`)
  return v
}

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null
}

function decodePlane(payload: Record<string, unknown>): PlaneOrientation {
  const plane = payload.plane
  if (plane === undefined) return 'xy' // EP2: absent ≡ xy (legacy byte-identity)
  if (typeof plane !== 'object' || plane === null) fail('sketch plane record malformed')
  const p = plane as Record<string, unknown>
  if (p.kind !== 'principal') fail(`sketch plane kind ${JSON.stringify(p.kind)} not understood`)
  const ori = p.orientation
  if (ori !== 'xy' && ori !== 'yz' && ori !== 'zx') fail(`sketch plane orientation ${JSON.stringify(ori)}`)
  return ori
}

function decodeRings(payload: Record<string, unknown>, featId: string): Pt[][] {
  const prims = payload.primitives
  if (!Array.isArray(prims)) fail(`sketch ${featId} has no primitives array`)
  const rings: Pt[][] = []
  for (const prim of prims as Array<Record<string, unknown>>) {
    if (prim.type === 'rectangle') {
      const x = num(prim.x_mm)
      const y = num(prim.y_mm)
      const w = num(prim.width_mm)
      const h = num(prim.height_mm)
      if (x === null || y === null || w === null || h === null) fail(`sketch ${featId} rectangle malformed`)
      rings.push([
        { x, y },
        { x: x + w, y },
        { x: x + w, y: y + h },
        { x, y: y + h },
      ])
    } else if (prim.type === 'contour') {
      const segs = prim.segments
      if (!Array.isArray(segs) || segs.length === 0) fail(`sketch ${featId} contour has no segments`)
      const ring: Pt[] = []
      for (const seg of segs as Array<Record<string, unknown>>) {
        const x = num(seg.x1_mm)
        const y = num(seg.y1_mm)
        if (x === null || y === null) fail(`sketch ${featId} contour segment malformed`)
        ring.push({ x, y })
      }
      rings.push(ring)
    } else {
      fail(`sketch ${featId} primitive type ${JSON.stringify(prim.type)} not understood`)
    }
  }
  return rings
}

/**
 * Decode the raw `inspect` DTO (`{ object: { sidecar, ... } }`'s inner object
 * view) into the typed Part. Throws (loud, specific) on anything malformed,
 * non-Part, or written by an adapter series this Studio doesn't know.
 */
export function decodeInspectedPart(view: unknown): InspectedPart {
  if (typeof view !== 'object' || view === null) fail('view is not an object')
  const v = view as Record<string, unknown>
  const sidecar = v.sidecar
  if (typeof sidecar !== 'object' || sidecar === null) fail('view has no sidecar')
  const sc = sidecar as Record<string, unknown>
  const obj = sc.object
  if (typeof obj !== 'object' || obj === null) fail('sidecar has no object record')
  const o = obj as Record<string, unknown>
  if (o.type !== 'Part') fail(`object type ${JSON.stringify(o.type)} is not a Part`)

  const rawFeatures = sc.feature
  const featureList = rawFeatures === undefined ? [] : rawFeatures
  if (!Array.isArray(featureList)) fail('sidecar feature list is not an array')

  const features: InspectedFeature[] = []
  for (const raw of featureList as Array<Record<string, unknown>>) {
    const id = str(raw.id, 'feature id')
    const ftype = str(raw.feature_type, `feature ${id} feature_type`)
    const isMechanical = raw.engine === MECHANICAL_ENGINE
    const isKnownMechanicalType = ftype === 'sketch' || ftype === 'extrude' || ftype === 'revolve'

    if (!isMechanical || !isKnownMechanicalType) {
      // Codex3 B1: a foreign-engine feature — even one CALLED "sketch" — and
      // any unknown mechanical type stay GENERIC: visible in the tree, payload
      // never read as rings/planes/dependencies/eligibility.
      features.push({ kind: 'other', id, featureType: ftype })
      continue
    }

    // Inside the mechanical guard only: the version gate for KNOWN records.
    const version = str(raw.adapter_schema_version, `feature ${id} adapter_schema_version`)
    if (!version.startsWith(KNOWN_ADAPTER_SERIES)) {
      fail(
        `mechanical ${ftype} ${id} was written by adapter ${version} — this Studio understands ${KNOWN_ADAPTER_SERIES}x only`,
      )
    }
    const payload = (raw.adapter_payload ?? {}) as Record<string, unknown>

    if (ftype === 'sketch') {
      features.push({ kind: 'sketch', id, plane: decodePlane(payload), rings: decodeRings(payload, id) })
    } else {
      // The CANONICAL dependency edge is depends_on_feature_ids (the payload's
      // sketch_feature_id must agree — the engine's resolver enforces that on
      // write; here the canonical edge is what the tree nests by).
      const deps = raw.depends_on_feature_ids
      if (!Array.isArray(deps) || deps.length !== 1 || typeof deps[0] !== 'string') {
        fail(`${ftype} ${id} must depend on exactly one sketch`)
      }
      let depthMm: number | null = null
      const params = raw.parameters
      if (Array.isArray(params)) {
        const depth = (params as Array<Record<string, unknown>>).find((p) => p.name === 'depth_mm')
        depthMm = depth ? num(depth.value) : null
      }
      features.push({ kind: ftype, id, consumesSketchId: deps[0], depthMm })
    }
  }

  return {
    number: str(o.number, 'object number'),
    name: str(o.name, 'object name'),
    uuid: str(o.uuid, 'object uuid'),
    features,
    hasExtrudeBase: features.some((f) => f.kind === 'extrude'),
    hasRevolveBase: features.some((f) => f.kind === 'revolve'),
  }
}

// ---- The Creo-shaped tree (D-S1) -------------------------------------------

export interface TreeRow {
  featureId: string
  /** The Creo-convention display label: `Sketch N` (unconsumed, top-level),
   *  `Extrude N`/`Revolve N` (base), `Section N` (consumed sketch, NESTED). */
  label: string
  /** 0 = top level; 1 = nested under the preceding base feature. */
  depth: 0 | 1
  kind: InspectedFeature['kind'] | 'section'
}

/**
 * Derive the Creo-shaped rows from decoded Truth (pure): features in recipe
 * order; a sketch consumed by a base feature disappears from the top level and
 * reappears NESTED under its consumer as `Section N` (N = its ordinal among
 * that consumer's sections — one in v1). Unconsumed sketches stay top-level as
 * `Sketch N` (N = the sketch's ordinal among ALL sketches, so a name never
 * changes retroactively when a later sketch is consumed).
 */
export function buildTreeRows(part: InspectedPart): TreeRow[] {
  const sketchOrdinal = new Map<string, number>()
  let nSketch = 0
  for (const f of part.features) if (f.kind === 'sketch') sketchOrdinal.set(f.id, ++nSketch)

  const consumedBy = new Map<string, InspectedBase>()
  for (const f of part.features) {
    if (f.kind === 'extrude' || f.kind === 'revolve') consumedBy.set(f.consumesSketchId, f)
  }

  const rows: TreeRow[] = []
  const kindCount: Record<string, number> = {}
  for (const f of part.features) {
    if (f.kind === 'sketch') {
      if (consumedBy.has(f.id)) continue // appears nested under its consumer
      rows.push({ featureId: f.id, label: `Sketch ${sketchOrdinal.get(f.id)}`, depth: 0, kind: 'sketch' })
    } else if (f.kind === 'extrude' || f.kind === 'revolve') {
      const n = (kindCount[f.kind] = (kindCount[f.kind] ?? 0) + 1)
      const name = f.kind === 'extrude' ? 'Extrude' : 'Revolve'
      rows.push({ featureId: f.id, label: `${name} ${n}`, depth: 0, kind: f.kind })
      // v1: exactly one consumed sketch per base → Section 1 under it.
      rows.push({ featureId: f.consumesSketchId, label: 'Section 1', depth: 1, kind: 'section' })
    } else if (f.kind === 'other') {
      const n = (kindCount[f.featureType] = (kindCount[f.featureType] ?? 0) + 1)
      const name = f.featureType.charAt(0).toUpperCase() + f.featureType.slice(1)
      rows.push({ featureId: f.id, label: `${name} ${n}`, depth: 0, kind: 'other' })
    }
  }
  return rows
}

/** The unconsumed sketches (recipe order) — the wire-overlay set AND the
 *  Extrude dialog's selectable-sketch set (one derivation, both consumers). */
export function unconsumedSketches(part: InspectedPart): InspectedSketch[] {
  const consumed = new Set<string>()
  for (const f of part.features) {
    if (f.kind === 'extrude' || f.kind === 'revolve') consumed.add(f.consumesSketchId)
  }
  return part.features.filter((f): f is InspectedSketch => f.kind === 'sketch' && !consumed.has(f.id))
}
