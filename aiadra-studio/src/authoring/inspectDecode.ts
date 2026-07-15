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

export interface RectangleDims {
  x_mm: number
  y_mm: number
  width_mm: number
  height_mm: number
}

/** The EXACT whole-primitive-list profile classifier (arc 20260715-1 Codex2
 *  B1 / P1): `simple_rectangle` iff the sketch has EXACTLY ONE primitive and
 *  it is a rectangle — mirroring the engine's `require_simple_revolve_profile`
 *  and `require_simple_cap_fit` domains. Revolve eligibility AND Hole's
 *  base-domain predicate both read THIS fact; a found-a-rectangle nullable
 *  does not exist. */
export type SketchProfile =
  | { kind: 'simple_rectangle'; rectangle: RectangleDims }
  | { kind: 'other' }

export interface InspectedSketch {
  kind: 'sketch'
  id: string
  plane: PlaneOrientation
  /** The wire polyline(s) in plane (u,v) coords — one closed ring per
   *  primitive. Contours use their segment chain; rectangles their 4 corners. */
  rings: Pt[][]
  profile: SketchProfile
}

/** One editable parameter, identity-preserving (Codex2 N3): the stable
 *  engine-minted `id` travels with the canonical `name` the mutation
 *  addresses, the numeric value, and the schema-fixed unit. */
export interface EditableParameter {
  id: string
  name: string
  value: number
  unit: string
}

export interface InspectedBase {
  kind: 'extrude' | 'revolve'
  id: string
  /** The consumed sketch's feature id (canonical `depends_on_feature_ids`). */
  consumesSketchId: string
  depthMm: number | null
  /** Catalogued editable parameters (P1/N3) — only KNOWN names per type. */
  parameters: EditableParameter[]
}

export interface InspectedOther {
  kind: 'other'
  id: string
  featureType: string
  /** True iff the record is the mechanical engine's (Codex4 polish: a
   *  FOREIGN-engine namesake must not feed mechanical facts like the
   *  stacking containment). */
  mechanical: boolean
  /** Referencing mechanical features (fillet/chamfer/hole) expose their
   *  catalogued editable parameters too; foreign/unknown stay empty. */
  parameters: EditableParameter[]
}

export type InspectedFeature = InspectedSketch | InspectedBase | InspectedOther

/** The version-guarded editable-parameter CATALOGUE: per feature type, the
 *  KNOWN editable names — the renderer can only submit catalogued names; the
 *  engine stays authoritative. Revolve's axis is topology skeleton, not an
 *  editable value. */
export const EDITABLE_PARAMETERS: Record<string, readonly string[]> = {
  extrude: ['depth_mm'],
  revolve: [],
  fillet: ['radius_mm'],
  chamfer: ['distance_mm'],
  hole: ['diameter_mm', 'center_x_mm', 'center_y_mm'],
}

export interface InspectedPart {
  number: string
  name: string
  uuid: string
  /** Recipe order, verbatim from Truth. */
  features: InspectedFeature[]
  /** B3's UI mirror: base-creation eligibility comes from INSPECTED state. */
  hasExtrudeBase: boolean
  hasRevolveBase: boolean
  /** Hole's v1 one-hole bound (P1) — derived from the recipe. */
  hasHole: boolean
  /** ANY referencing feature (fillet/chamfer/hole) present (Codex3 B1.1):
   *  the engine's mid-fold resolver does not yet carry prior produced-face
   *  claims, so a SECOND referencing feature is a known-unsupported sequence
   *  — the ribbon contains it (conservative until the engine follow-up). */
  hasReferencingFeature: boolean
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

function decodeParameters(raw: Record<string, unknown>, featureType: string): EditableParameter[] {
  const catalogue = EDITABLE_PARAMETERS[featureType] ?? []
  const params = raw.parameters
  if (!Array.isArray(params) || catalogue.length === 0) return []
  const out: EditableParameter[] = []
  for (const p of params as Array<Record<string, unknown>>) {
    if (typeof p.name !== 'string' || !catalogue.includes(p.name)) continue
    const value = num(p.value)
    if (typeof p.id !== 'string' || value === null || typeof p.unit !== 'string') continue
    out.push({ id: p.id, name: p.name, value, unit: p.unit })
  }
  return out
}

/** P1: classify the WHOLE primitive list — exactly one rectangle, no extras. */
function decodeProfile(payload: Record<string, unknown>): SketchProfile {
  const prims = payload.primitives
  if (!Array.isArray(prims) || prims.length !== 1) return { kind: 'other' }
  const prim = prims[0] as Record<string, unknown>
  if (prim.type !== 'rectangle') return { kind: 'other' }
  const x = num(prim.x_mm)
  const y = num(prim.y_mm)
  const w = num(prim.width_mm)
  const h = num(prim.height_mm)
  if (x === null || y === null || w === null || h === null) return { kind: 'other' }
  return { kind: 'simple_rectangle', rectangle: { x_mm: x, y_mm: y, width_mm: w, height_mm: h } }
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
      // Arc 20260715-1 Codex3 B2: an EDITABLE catalogue is mechanical-payload
      // interpretation too — it requires the mechanical engine AND the
      // supported adapter series; a future-series fillet/hole stays an
      // inspectable OPAQUE row with NO editable parameters (no throw).
      const version = typeof raw.adapter_schema_version === 'string' ? raw.adapter_schema_version : ''
      const catalogueOk =
        isMechanical &&
        (EDITABLE_PARAMETERS[ftype]?.length ?? 0) > 0 &&
        version.startsWith(KNOWN_ADAPTER_SERIES)
      features.push({
        kind: 'other',
        id,
        featureType: ftype,
        mechanical: isMechanical,
        parameters: catalogueOk ? decodeParameters(raw, ftype) : [],
      })
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
      features.push({
        kind: 'sketch',
        id,
        plane: decodePlane(payload),
        rings: decodeRings(payload, id),
        profile: decodeProfile(payload),
      })
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
      features.push({ kind: ftype, id, consumesSketchId: deps[0], depthMm, parameters: decodeParameters(raw, ftype) })
    }
  }

  return {
    number: str(o.number, 'object number'),
    name: str(o.name, 'object name'),
    uuid: str(o.uuid, 'object uuid'),
    features,
    hasExtrudeBase: features.some((f) => f.kind === 'extrude'),
    hasRevolveBase: features.some((f) => f.kind === 'revolve'),
    hasHole: features.some((f) => f.kind === 'other' && f.mechanical && f.featureType === 'hole'),
    hasReferencingFeature: features.some(
      (f) => f.kind === 'other' && f.mechanical && ['fillet', 'chamfer', 'hole'].includes(f.featureType),
    ),
  }
}

/** The STACKING containment (Codex3 B1.1): a second referencing feature is a
 *  known-unsupported engine sequence (the mid-fold resolver does not carry
 *  prior produced-face claims) — refuse conservatively until the "stacked
 *  referencing features" engine slice lands. */
export function stackingRefusal(part: InspectedPart): string | null {
  if (!part.hasReferencingFeature) return null
  return 'the Part already has a Round/Chamfer/Hole — stacked referencing features arrive with the engine follow-up slice'
}

// ---- Revolve axis eligibility (P1 — exactly the engine's straddle rule) ----

export type RevolveAxis = 'x' | 'y'
const AXIS_EPS = 1e-9

/** Mirror of the engine's `revolve_radial_mode` crossing guard: axis `x` is
 *  ineligible iff the rectangle's y-extent STRADDLES 0 (eps-tolerant); axis
 *  `y` symmetric on x. Returns the refusal reason, or null when eligible. */
export function revolveAxisRefusal(rect: RectangleDims, axis: RevolveAxis): string | null {
  const lo = axis === 'x' ? rect.y_mm : rect.x_mm
  const hi = lo + (axis === 'x' ? rect.height_mm : rect.width_mm)
  if (lo < -AXIS_EPS && hi > AXIS_EPS) {
    return `the profile crosses the ${axis}-axis — offset it to one side`
  }
  return null
}

/**
 * Hole's BASE-DOMAIN predicate (P1, Codex2 B1): a ready EXTRUDE whose
 * CONSUMED sketch (the canonical dependency edge) has the EXACT
 * `simple_rectangle` profile, and NO existing hole — mirroring the engine's
 * `require_simple_cap_fit` domain. A contour-extruded Part shows Hole
 * state-disabled with this derived reason instead of opening a dashboard
 * that must fail. (Wall-vs-cap stays ENGINE-authoritative pre-commit — the
 * display carries no cap classification; P2's named bounded limitation.)
 */
export function holeBaseRefusal(part: InspectedPart): string | null {
  if (!part.hasExtrudeBase || part.hasRevolveBase) {
    return 'Hole needs an EXTRUDED base (v1)'
  }
  const stacking = stackingRefusal(part)
  if (stacking) return stacking
  if (part.hasHole) return 'the Part already has a hole (one per Part in v1)'
  const extrude = part.features.find((f): f is InspectedBase => f.kind === 'extrude')
  if (!extrude) return 'Hole needs an EXTRUDED base (v1)'
  const consumed = part.features.find(
    (f): f is InspectedSketch => f.kind === 'sketch' && f.id === extrude.consumesSketchId,
  )
  if (!consumed || consumed.profile.kind !== 'simple_rectangle') {
    return 'v1 Hole needs a base extruded from exactly one rectangle (the consumed sketch is not a simple rectangle)'
  }
  return null
}

/** Revolve eligibility for a decoded sketch (P1): xy plane + the EXACT
 *  simple_rectangle profile + at least one non-straddling axis. */
export function revolveSketchRefusal(sk: InspectedSketch): string | null {
  if (sk.plane !== 'xy') return 'v1 revolve requires a sketch on the xy (FRONT) plane'
  if (sk.profile.kind !== 'simple_rectangle') {
    return 'v1 revolve requires exactly one rectangle primitive (no extras)'
  }
  const r = sk.profile.rectangle
  if (revolveAxisRefusal(r, 'x') !== null && revolveAxisRefusal(r, 'y') !== null) {
    return 'the profile crosses both axes — offset it to one side of an axis'
  }
  return null
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
