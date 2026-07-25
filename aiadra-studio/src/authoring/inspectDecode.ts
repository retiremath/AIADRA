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
import { tessellateCircle, tessellateSegments, type ContourSegment } from '../sketch/arcGeometry'
import { classifySketch } from '../sketch/profileClassify'
import type { PlaneOrientation } from './backend'
import { isPlacementRecord, type PlacementRecord } from './placementFrame'

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
// ADR/0044 A2.4 (arc 20260717-2): per-record-family series — ONLY the sketch
// family has defined 0.2 semantics; every other mechanical family refuses
// 0.2.x by name. The concrete writer versions are pinned (ADR/0044 A3:
// 0.2.0 legacy `plane` + 0.2.1 placed).
const SKETCH_V2_SERIES = '0.2.'
const SKETCH_V2_VERSION = '0.2.0'
const SKETCH_V21_VERSION = '0.2.1'
// skb-b0 constants (Docs/SolverContracts/skb-b0.md §1; the engine module is
// the parity-tested implementation — these mirror it at the decode surface).
const SKB_B0_L_MIN_MM = 1e-9

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
  /** SK-C0 D-C2: exactly one NON-construction circle standing alone — the
   *  cylinder profile (extrude-eligible; Revolve/Hole eligibility unchanged). */
  | { kind: 'simple_circle'; circle: { cx_mm: number; cy_mm: number; radius_mm: number } }
  /** SK-C0 D-C3: no non-construction profile at all — a guides-only sketch. */
  | { kind: 'sketch_only' }
  | { kind: 'other' }

/** A typed sketch entity (SK-C0 B4 — Codex1: no anonymous flattening): the
 *  stable engine id, exact geometry, and the construction flag survive. */
/** A contour segment WITH its engine-minted stable id (SK-C0 Codex3 B3:
 *  the `skp_NNNNsNN` anchors that produce `<segment-id>:face:wall` roles
 *  survive decode — list addressability, never dropped). */
export type IdentifiedSegment = ContourSegment & { id: string }

export type SketchEntity =
  | { id: string; kind: 'rectangle'; construction: boolean; rect: RectangleDims }
  | { id: string; kind: 'circle'; construction: boolean; circle: { cx_mm: number; cy_mm: number; radius_mm: number } }
  | { id: string; kind: 'line'; construction: boolean; a: Pt; b: Pt }
  | { id: string; kind: 'contour'; construction: boolean; segments: IdentifiedSegment[] }

/** A render wire derived from ONE entity (arcs/circles tessellated,
 *  preview-only): dashed when construction. */
export interface SketchWire {
  points: Pt[]
  construction: boolean
  closed: boolean
}

/** SK-C1.0 S2 (Codex2 B3.4): the DISCRIMINATED plane binding — a face-bound
 *  sketch decodes as its structured Truth reference, never forced through a
 *  principal orientation. The derived FRAME joins separately (Display v1.2
 *  `sketch_frames`, by sketch feature id). */
export type SketchPlaneBinding =
  | { kind: 'principal'; orientation: PlaneOrientation }
  | { kind: 'face'; faceRole: string; resolvedAgainst: string }

/** ADR/0044 A2 (arc 20260717-2, Gate F2a): a v2 CONSTRAINED sketch — adapter
 *  series 0.2.x. Decoded as its own typed member so nothing v1 (rings,
 *  profile, extrude eligibility, consumption) ever reads it: every existing
 *  `kind === 'sketch'` filter excludes it by construction. Studio VALIDATES
 *  the record (the same skb-b0 graph admission the engine enforces — the
 *  decoder is one of the five enforcement surfaces) but derives no geometry:
 *  v2 regeneration is solver-backed and arrives with Gate F2b. */
export interface InspectedSketchV2 {
  kind: 'sketchV2'
  id: string
  plane: SketchPlaneBinding
  /** The admitted skb-b0 shape (G0 | G1 | G2). */
  shape: string
  solverContract: string
  weakPolicy: string
  branchPolicy: string
  entityCount: number
  constraintCount: number
  /** ADR/0044 A3: the literal writer version ('0.2.0' legacy | '0.2.1' placed). */
  version: '0.2.0' | '0.2.1'
  /** Present iff version is 0.2.1 — the persisted placement facts (the tree's
   *  ✎ redefine entry seeds its session from these). */
  placement?: import('./placementFrame').PlacementRecord
}

export interface InspectedSketch {
  kind: 'sketch'
  id: string
  plane: SketchPlaneBinding
  /** The wire polyline(s) in plane (u,v) coords — one closed ring per
   *  NON-construction primitive (compat view; arcs tessellated). */
  rings: Pt[][]
  /** SK-C0: every primitive as a typed entity (ids + exact geometry + flag). */
  entities: SketchEntity[]
  /** SK-C0: per-entity render wires incl. DASHED construction guides. */
  wires: SketchWire[]
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

export type InspectedFeature =
  | InspectedSketch
  | InspectedSketchV2
  | InspectedBase
  | InspectedOther

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

function decodePlane(payload: Record<string, unknown>): SketchPlaneBinding {
  const plane = payload.plane
  if (plane === undefined) return { kind: 'principal', orientation: 'xy' } // EP2: absent ≡ xy
  if (typeof plane !== 'object' || plane === null) fail('sketch plane record malformed')
  const p = plane as Record<string, unknown>
  if (p.kind === 'face') {
    // Codex7 NB3: the EXACT stored-record shape (engine parity) — extra keys
    // fail loud at the mock/fixture boundary too.
    for (const k of Object.keys(p)) {
      if (k !== 'kind' && k !== 'face_role' && k !== 'resolved_against_topology_signature') {
        fail(`face plane record carries unknown key ${JSON.stringify(k)}`)
      }
    }
    // the STORED engine reference (adapter 0.1.10) — structural checks only;
    // resolution/frames are the engine's (the display's sketch_frames join)
    const role = p.face_role
    const sig = p.resolved_against_topology_signature
    if (typeof role !== 'string' || !role.includes(':face:')) fail('face plane record lacks its face_role')
    if (typeof sig !== 'string' || sig.length === 0) fail('face plane record lacks its resolved-against signature')
    return { kind: 'face', faceRole: role, resolvedAgainst: sig }
  }
  if (p.kind !== 'principal') fail(`sketch plane kind ${JSON.stringify(p.kind)} not understood`)
  const ori = p.orientation
  if (ori !== 'xy' && ori !== 'yz' && ori !== 'zx') fail(`sketch plane orientation ${JSON.stringify(ori)}`)
  // Codex24 B2: the principal record is CLOSED to exactly {kind, orientation}
  // — the engine's shared validator refuses extras (v1 and v2 alike), and an
  // ignored field must never participate in recipe identity while Studio
  // assigns it no semantics. One language, five surfaces.
  for (const k of Object.keys(p)) {
    if (k !== 'kind' && k !== 'orientation') {
      fail(`principal plane record carries unsupported key ${JSON.stringify(k)} (exactly {kind, orientation})`)
    }
  }
  return { kind: 'principal', orientation: ori }
}

// ---------------------------------------------------------------------------
// ADR/0044 A2 (Gate F2a): the v2 constrained-sketch decode — the Studio
// decoder is one of the FIVE skb-b0 enforcement surfaces. It mirrors the
// engine's graph-level admission (Docs/SolverContracts/skb-b0.md §2/§3:
// local table + the exact G0/G1/G2 predicate incl. full weak-record
// validation, magnitude/nominal equality, and the SIGNED L_min guards) and
// fails loud on everything else. No geometry is derived: v2 regeneration is
// solver-backed and arrives with Gate F2b.
// ---------------------------------------------------------------------------

const SKETCH_V2_PAYLOAD_KEYS = new Set([
  'sketch_model', 'solver_contract', 'weak_policy', 'branch_policy', 'plane',
  'entities', 'constraints', 'dimensions', 'references', 'weak_completion',
  'witnesses',
])

interface V2Point { id: string; x: number; y: number }

function v2fail(id: string, msg: string): never {
  fail(`v2 sketch ${id}: ${msg}`)
}

function decodeSketchV2(
  payload: Record<string, unknown>,
  id: string,
  version: '0.2.0' | '0.2.1' = '0.2.0',
): InspectedSketchV2 {
  // A3.1/A3.2 mirror: per-version closed key sets — 0.2.1 replaces `plane`
  // with the 4-member `placement` record; dispatch is explicit, never guessed.
  const wantKeys = version === '0.2.0'
    ? SKETCH_V2_PAYLOAD_KEYS
    : new Set([...SKETCH_V2_PAYLOAD_KEYS].map((k) => (k === 'plane' ? 'placement' : k)))
  const keys = Object.keys(payload)
  for (const k of keys) if (!wantKeys.has(k)) v2fail(id, `unknown payload key ${JSON.stringify(k)} for ${version}`)
  for (const k of wantKeys) if (!(k in payload)) v2fail(id, `missing payload key ${JSON.stringify(k)} for ${version}`)
  if (payload.sketch_model !== 2) v2fail(id, `sketch_model ${JSON.stringify(payload.sketch_model)} !== 2`)
  const solverContract = payload.solver_contract
  const weakPolicy = payload.weak_policy
  const branchPolicy = payload.branch_policy
  if (solverContract !== 'skb-c0' || weakPolicy !== 'skb-0' || branchPolicy !== 'skb-b0') {
    v2fail(id, `contract ids (${JSON.stringify(solverContract)}, ${JSON.stringify(weakPolicy)}, ` +
      `${JSON.stringify(branchPolicy)}) are not the supported (skb-c0, skb-0, skb-b0)`)
  }
  let plane: SketchPlaneBinding
  let placement: PlacementRecord | undefined
  if (version === '0.2.0') {
    if (payload.plane === undefined) v2fail(id, 'plane is required (the v2 contract is closed)')
    plane = decodePlane(payload)
  } else {
    if (!isPlacementRecord(payload.placement)) {
      v2fail(id, 'placement must be the closed 4-member A3.2 record (principal-only; ref ≠ support)')
    }
    placement = payload.placement
    // the tree's plane binding shows the SUPPORT (derived view, never persisted)
    plane = { kind: 'principal', orientation: placement.support.orientation }
  }

  const arr = (name: string): Record<string, unknown>[] => {
    const v = payload[name]
    if (!Array.isArray(v)) v2fail(id, `${name} must be an array`)
    return v.map((x) => {
      if (typeof x !== 'object' || x === null) v2fail(id, `${name} entry is not an object`)
      return x as Record<string, unknown>
    })
  }
  const entities = arr('entities')
  const constraints = arr('constraints')
  const dimensions = arr('dimensions')
  const references = arr('references')
  const weak = arr('weak_completion')
  const witnesses = arr('witnesses')
  if (dimensions.length > 0) v2fail(id, 'skb-b0 admits no dimensions')
  if (references.length > 0) v2fail(id, 'references must be empty under skb-b0 (SK-E territory)')
  if (witnesses.length > 0) {
    v2fail(id, `witness set mismatch: ${witnesses.length} present; the skb-b0 catalog derives ` +
      'exactly 0 for every admitted shape — extra witnesses are rejected (exact-set rule)')
  }

  const shape = admitSkbB0Graph(entities, constraints, weak, (m) => v2fail(id, m),
    { solverContract, weakPolicy })
  return {
    kind: 'sketchV2', id, plane, shape,
    solverContract, weakPolicy, branchPolicy,
    entityCount: entities.length, constraintCount: constraints.length,
    version, placement,
  }
}

/** The skb-b0 whole-fact-graph admission predicate (TS mirror of
 *  `aiadra_mechanical.solver.branch_policy.admit_graph`). Returns the shape
 *  name; every violation refuses through `bad`. */
function admitSkbB0Graph(
  entities: Record<string, unknown>[],
  constraints: Record<string, unknown>[],
  weak: Record<string, unknown>[],
  bad: (msg: string) => never,
  top: { solverContract: unknown; weakPolicy: unknown },
): string {
  const points = new Map<string, V2Point>()
  const lines = new Map<string, { start: string; end: string }>()
  for (const e of entities) {
    const eid = e.id
    if (typeof eid !== 'string' || eid.length === 0) bad('entity without a non-empty string id')
    if (points.has(eid) || lines.has(eid)) bad(`duplicate entity id ${JSON.stringify(eid)}`)
    if (e.construction !== true) bad(`entity ${eid} is not construction geometry (skb-b0 admits construction references only)`)
    // type membership FIRST (the local-table refusal names the real cause),
    // THEN Codex23 B2's closed-shape check — an unknown nested key must
    // never become identity-bearing without semantics.
    if (e.type !== 'point' && e.type !== 'line') {
      bad(`entity ${eid} type ${JSON.stringify(e.type)} is outside the skb-b0 local table`)
    }
    const wantKeys = e.type === 'point'
      ? ['id', 'type', 'construction', 'nominal']
      : ['id', 'type', 'construction', 'start', 'end']
    for (const k of Object.keys(e)) {
      if (!wantKeys.includes(k)) bad(`entity ${eid} carries unknown field ${JSON.stringify(k)} (the skb-b0 entity shapes are closed)`)
    }
    if (e.type === 'point') {
      const nom = e.nominal
      if (typeof nom !== 'object' || nom === null) bad(`point ${eid} has no nominal`)
      const n = nom as Record<string, unknown>
      const nk = Object.keys(n)
      if (nk.length !== 2 || typeof n.x !== 'number' || typeof n.y !== 'number' ||
          !Number.isFinite(n.x) || !Number.isFinite(n.y)) {
        bad(`point ${eid} nominal is not a finite {x, y}`)
      }
      points.set(eid, { id: eid, x: n.x, y: n.y })
    } else if (e.type === 'line') {
      if (typeof e.start !== 'string' || typeof e.end !== 'string') bad(`line ${eid} lacks start/end refs`)
      lines.set(eid, { start: e.start, end: e.end })
    } else {
      bad(`entity ${eid} type ${JSON.stringify(e.type)} is outside the skb-b0 local table`)
    }
  }
  const fixes: string[] = []
  const horizontals: string[] = []
  const verticals: string[] = []
  const cids = new Set<string>()
  for (const c of constraints) {
    const cid = c.id
    if (typeof cid !== 'string' || cid.length === 0 || cids.has(cid)) bad('constraint without a unique non-empty string id')
    cids.add(cid)
    for (const k of Object.keys(c)) {
      if (k !== 'id' && k !== 'kind' && k !== 'args') bad(`constraint ${cid} carries unknown field ${JSON.stringify(k)} (the skb-b0 constraint shape is closed)`)
    }
    const args = c.args
    if (!Array.isArray(args) || args.length !== 1 || typeof args[0] !== 'string') {
      bad(`constraint ${cid} must carry exactly one string arg under skb-b0`)
    }
    if (c.kind === 'fix') fixes.push(args[0])
    else if (c.kind === 'horizontal') horizontals.push(args[0])
    else if (c.kind === 'vertical') verticals.push(args[0])
    else bad(`constraint ${cid} kind ${JSON.stringify(c.kind)} is outside the skb-b0 local table`)
  }
  if (fixes.length !== 1) bad('exactly one fix(point) anchor is required')
  const origin = points.get(fixes[0])
  if (!origin) bad(`fix names ${JSON.stringify(fixes[0])}, which is not a point entity`)

  const validWeak = (w: Record<string, unknown>, index: number, entity: string, parameter: string): number => {
    const wantId = `w${String(index + 1).padStart(2, '0')}`
    if (w.id !== wantId) bad(`weak record ${index} id ${JSON.stringify(w.id)} !== canonical ${wantId}`)
    if (w.kind !== 'fix_param') bad(`weak record ${wantId} kind !== 'fix_param'`)
    const t = w.target as Record<string, unknown> | undefined
    if (typeof t !== 'object' || t === null || t.entity !== entity || t.parameter !== parameter ||
        Object.keys(t).length !== 2) {
      bad(`weak record ${wantId} target !== {entity: ${entity}, parameter: ${parameter}}`)
    }
    const v = w.value as Record<string, unknown> | undefined
    if (typeof v !== 'object' || v === null || v.unit !== 'mm' ||
        typeof v.magnitude !== 'number' || !Number.isFinite(v.magnitude) ||
        Object.keys(v).length !== 2) {
      bad(`weak record ${wantId} value must be {magnitude: finite, unit: 'mm'}`)
    }
    if (w.strength !== 'weak' || w.role !== 'driving' || w.visibility !== 'internal') {
      bad(`weak record ${wantId} strength/role/visibility are not the verbatim skb-0 shape`)
    }
    const o = w.origin as Record<string, unknown> | undefined
    if (typeof o !== 'object' || o === null || o.category !== 'computed_result' ||
        o.policy !== top.weakPolicy || o.solver_contract !== top.solverContract ||
        Object.keys(o).length !== 3) {
      bad(`weak record ${wantId} origin is not the verbatim skb-0 origin block cross-checked against the top-level ids`)
    }
    const known = new Set(['id', 'kind', 'target', 'value', 'strength', 'role', 'visibility', 'origin'])
    for (const k of Object.keys(w)) if (!known.has(k)) bad(`weak record ${wantId} carries unknown field ${JSON.stringify(k)}`)
    return v.magnitude
  }

  const axis = (list: string[], kindName: string): { lineId: string; end: V2Point } => {
    if (list.length !== 1) bad(`exactly one ${kindName}(line) is required for this shape`)
    const line = lines.get(list[0])
    if (!line) bad(`${kindName} names ${JSON.stringify(list[0])}, which is not a line entity`)
    if (line.start !== origin!.id) {
      bad(`axis line ${list[0]} must be DIRECTED from the fixed origin (the reference axes are directed)`)
    }
    const end = points.get(line.end)
    if (!end || end.id === origin!.id) bad(`axis line ${list[0]} end must be a distinct point entity`)
    return { lineId: list[0], end }
  }

  if (points.size === 1 && lines.size === 0) {
    if (horizontals.length || verticals.length || weak.length) bad('G0 admits no axis facts and an empty weak completion')
    return 'G0'
  }
  if (points.size === 2 && lines.size === 1) {
    if (verticals.length) bad('G1 has no vertical axis; a lone vertical axis is not an admitted shape under skb-b0')
    const { end: px } = axis(horizontals, 'horizontal')
    if (weak.length !== 1) bad('G1 requires exactly one weak record (fix_param on the axis endpoint x)')
    const mag = validWeak(weak[0], 0, px.id, 'x')
    if (mag !== px.x) bad(`weak magnitude ${mag} contradicts the authored nominal ${px.x} for ${px.id}.x`)
    if (!(mag - origin!.x > SKB_B0_L_MIN_MM)) {
      bad(`signed guard failed: ${px.id}.x − ${origin!.id}.x must exceed L_min`)
    }
    return 'G1'
  }
  if (points.size === 3 && lines.size === 2) {
    const { lineId: ax, end: px } = axis(horizontals, 'horizontal')
    const { lineId: ay, end: py } = axis(verticals, 'vertical')
    if (ax === ay || px.id === py.id) bad('the two axes (and their endpoints) must be distinct')
    if (weak.length !== 2) bad('G2 requires exactly two weak records (fix_param on PX.x and PY.y)')
    const expected = [[px.id, 'x'] as const, [py.id, 'y'] as const]
      .sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0))
    const mags = expected.map(([ent, par], i) => [ent, par, validWeak(weak[i], i, ent, par)] as const)
    for (const [ent, par, mag] of mags) {
      const p = points.get(ent)!
      const nominal = par === 'x' ? p.x : p.y
      if (mag !== nominal) bad(`weak magnitude contradicts the authored nominal for ${ent}.${par}`)
      const oCoord = par === 'x' ? origin!.x : origin!.y
      if (!(mag - oCoord > SKB_B0_L_MIN_MM)) bad(`signed guard failed: ${ent}.${par} displacement must exceed L_min`)
    }
    return 'G2'
  }
  bad(`entity census (points=${points.size}, lines=${lines.size}) matches no admitted shape`)
}

function constructionFlag(prim: Record<string, unknown>, featId: string): boolean {
  const c = prim.construction
  if (c === undefined) return false
  if (typeof c !== 'boolean') fail(`sketch ${featId} construction flag must be boolean`)
  return c
}

// Codex5 B3: the ENGINE's minted identity grammar — decode enforces it, not
// mere non-emptiness. List-addressability needs unique, grammar-valid anchors.
const PRIM_ID_GRAMMAR = /^skp_[0-9]{4}$/

function decodeEntities(payload: Record<string, unknown>, featId: string): SketchEntity[] {
  const prims = payload.primitives
  if (!Array.isArray(prims)) fail(`sketch ${featId} has no primitives array`)
  const entities: SketchEntity[] = []
  const seenPrimIds = new Set<string>()
  for (const prim of prims as Array<Record<string, unknown>>) {
    // SK-C0 Codex3 B3: every 0.1.x primitive since 0.1.1 carries an
    // engine-minted skp_ id — a missing id is a corrupt/foreign record and
    // fails LOUD. '' is never a stable-id placeholder. Codex5 B3 tightens
    // this to the engine grammar + uniqueness.
    if (typeof prim.id !== 'string' || prim.id.length === 0) {
      fail(`sketch ${featId} primitive lacks its engine-minted skp_ id`)
    }
    const id = prim.id as string
    if (!PRIM_ID_GRAMMAR.test(id)) {
      fail(`sketch ${featId} primitive id ${JSON.stringify(id)} violates the engine skp_NNNN grammar`)
    }
    if (seenPrimIds.has(id)) fail(`sketch ${featId} duplicate primitive id ${id}`)
    seenPrimIds.add(id)
    const construction = constructionFlag(prim, featId)
    if (prim.type === 'rectangle') {
      const x = num(prim.x_mm)
      const y = num(prim.y_mm)
      const w = num(prim.width_mm)
      const h = num(prim.height_mm)
      if (x === null || y === null || w === null || h === null) fail(`sketch ${featId} rectangle malformed`)
      entities.push({ id, kind: 'rectangle', construction, rect: { x_mm: x, y_mm: y, width_mm: w, height_mm: h } })
    } else if (prim.type === 'circle') {
      const cx = num(prim.cx_mm)
      const cy = num(prim.cy_mm)
      const r = num(prim.radius_mm)
      if (cx === null || cy === null || r === null) fail(`sketch ${featId} circle malformed`)
      entities.push({ id, kind: 'circle', construction, circle: { cx_mm: cx, cy_mm: cy, radius_mm: r } })
    } else if (prim.type === 'line') {
      const x1 = num(prim.x1_mm)
      const y1 = num(prim.y1_mm)
      const x2 = num(prim.x2_mm)
      const y2 = num(prim.y2_mm)
      if (x1 === null || y1 === null || x2 === null || y2 === null) fail(`sketch ${featId} line malformed`)
      entities.push({ id, kind: 'line', construction, a: { x: x1, y: y1 }, b: { x: x2, y: y2 } })
    } else if (prim.type === 'contour') {
      const segs = prim.segments
      if (!Array.isArray(segs) || segs.length === 0) fail(`sketch ${featId} contour has no segments`)
      const out: IdentifiedSegment[] = []
      // Codex5 B3: a segment id must be OWNED by its contour — the engine
      // grammar is `<owning skp id>sNN` — and unique within it.
      const segIdGrammar = new RegExp(`^${id}s[0-9]{2}$`)
      const seenSegIds = new Set<string>()
      for (const seg of segs as Array<Record<string, unknown>>) {
        if (typeof seg.id !== 'string' || seg.id.length === 0) {
          fail(`sketch ${featId} contour segment lacks its engine-minted id`)
        }
        const sid = seg.id as string
        if (!segIdGrammar.test(sid)) {
          fail(`sketch ${featId} segment id ${JSON.stringify(sid)} is not owned by ${id} (engine grammar ${id}sNN)`)
        }
        if (seenSegIds.has(sid)) fail(`sketch ${featId} duplicate segment id ${sid}`)
        seenSegIds.add(sid)
        // Codex5 B2: construction is TOP-LEVEL and atomic for a contour — a
        // nested segment carrying its own key is an engine Class-1 reject and
        // fails loud here too (never silently erased before classification).
        if ('construction' in seg) {
          fail(`sketch ${featId} contour segment ${sid} carries its own construction key — construction is top-level and atomic`)
        }
        const x1 = num(seg.x1_mm)
        const y1 = num(seg.y1_mm)
        const x2 = num(seg.x2_mm)
        const y2 = num(seg.y2_mm)
        if (x1 === null || y1 === null || x2 === null || y2 === null) fail(`sketch ${featId} contour segment malformed`)
        if (seg.kind === 'arc') {
          const b = num(seg.bulge)
          if (b === null) fail(`sketch ${featId} arc segment missing bulge`)
          out.push({ id: sid, kind: 'arc', x1_mm: x1, y1_mm: y1, x2_mm: x2, y2_mm: y2, bulge: b })
        } else if (seg.kind === 'line') {
          out.push({ id: sid, kind: 'line', x1_mm: x1, y1_mm: y1, x2_mm: x2, y2_mm: y2 })
        } else {
          fail(`sketch ${featId} segment kind ${JSON.stringify(seg.kind)} not understood`)
        }
      }
      entities.push({ id, kind: 'contour', construction, segments: out })
    } else {
      fail(`sketch ${featId} primitive type ${JSON.stringify(prim.type)} not understood`)
    }
  }
  return entities
}

function entityWire(e: SketchEntity): SketchWire {
  if (e.kind === 'rectangle') {
    const { x_mm: x, y_mm: y, width_mm: w, height_mm: h } = e.rect
    return { points: [{ x, y }, { x: x + w, y }, { x: x + w, y: y + h }, { x, y: y + h }], construction: e.construction, closed: true }
  }
  if (e.kind === 'circle') {
    return { points: tessellateCircle(e.circle.cx_mm, e.circle.cy_mm, e.circle.radius_mm), construction: e.construction, closed: true }
  }
  if (e.kind === 'line') {
    return { points: [e.a, e.b], construction: e.construction, closed: false }
  }
  return { points: tessellateSegments(e.segments), construction: e.construction, closed: true }
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

/** P1 → SK-C0 Codex3 B2: the profile derives from THE classifier mirror —
 *  one whole-list interpretation shared with the engine's matrix. */
function decodeProfile(entities: SketchEntity[]): SketchProfile {
  const verdict = classifySketch(entities.map((e) => ({
    type: e.kind, construction: e.construction,
  })))
  if (!verdict.ok) return { kind: 'other' }
  const cls = verdict.classification
  if (cls.outerKind === 'none') return { kind: 'sketch_only' }
  if (cls.holeIndex !== null) return { kind: 'other' } // rectangle + hole
  const outer = entities[cls.outerIndex]
  if (outer.kind === 'rectangle') return { kind: 'simple_rectangle', rectangle: outer.rect }
  if (outer.kind === 'circle') return { kind: 'simple_circle', circle: outer.circle }
  return { kind: 'other' }
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

    // ADR/0044 A2.4 + Codex23 B3: the mechanical 0.2 gate runs BEFORE the
    // known/generic split — a mechanical fillet/hole/chamfer/unknown type
    // stamped 0.2.x must refuse BY NAME, never slip into the opaque branch.
    // Foreign engines remain opaque (engine discrimination precedes any 0.2
    // interpretation, mirroring the engine-side guard).
    if (isMechanical) {
      const v2v = typeof raw.adapter_schema_version === 'string' ? raw.adapter_schema_version : ''
      if (v2v.startsWith(SKETCH_V2_SERIES)) {
        if (ftype !== 'sketch') {
          fail(
            `mechanical ${ftype} ${id} carries adapter ${v2v}, but only the SKETCH ` +
              `family has defined 0.2 semantics (ADR/0044 A2.4) — refuse`,
          )
        }
        if (v2v !== SKETCH_V2_VERSION && v2v !== SKETCH_V21_VERSION) {
          fail(
            `v2 sketch ${id} carries ${v2v}; the defined v2 writer versions are ` +
              `${SKETCH_V2_VERSION} and ${SKETCH_V21_VERSION} (an unknown 0.2.x minor refuses rather than guessing)`,
          )
        }
        features.push(decodeSketchV2(
          (raw.adapter_payload ?? {}) as Record<string, unknown>, id,
          v2v as '0.2.0' | '0.2.1'))
        continue
      }
    }

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

    // Inside the mechanical guard only: the v1 series gate for KNOWN
    // records (the 0.2 family gate already ran above the generic split).
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
        ...(() => {
          const entities = decodeEntities(payload, id)
          const wires = entities.map(entityWire)
          return {
            entities,
            wires,
            rings: wires.filter((w) => !w.construction && w.closed).map((w) => w.points),
            profile: decodeProfile(entities),
          }
        })(),
      })
    } else {
      // Codex14 B1 (arc 20260717-2): the consumed sketch is the NAMED
      // operand — adapter_payload.sketch_feature_id — never a dependency-
      // list position. A SEQUENTIAL extrude (the signed A4.6 shape) carries
      // [consumed_sketch, prior_body_head]; the decoder permits the extra
      // chain edge on extrudes and requires the named operand to be present
      // in a well-formed, duplicate-free string dependency list. Revolve
      // keeps the stricter exactly-one shape (its adapter has no sequential
      // form).
      const payloadSketch = (raw.adapter_payload as Record<string, unknown> | undefined)?.sketch_feature_id
      if (typeof payloadSketch !== 'string' || payloadSketch.length === 0) {
        fail(`${ftype} ${id} names no consumed sketch (adapter_payload.sketch_feature_id)`)
      }
      const deps = raw.depends_on_feature_ids
      if (
        !Array.isArray(deps)
        || deps.length === 0
        || !deps.every((d) => typeof d === 'string' && d.length > 0)
        || new Set(deps).size !== deps.length
      ) {
        fail(`${ftype} ${id} has a malformed depends_on_feature_ids list`)
      }
      if (!(deps as string[]).includes(payloadSketch as string)) {
        fail(`${ftype} ${id} does not declare its consumed sketch ${String(payloadSketch)} as a dependency`)
      }
      if (ftype === 'revolve' && (deps as string[]).length !== 1) {
        fail(`revolve ${id} must depend on exactly one sketch`)
      }
      let depthMm: number | null = null
      const params = raw.parameters
      if (Array.isArray(params)) {
        const depth = (params as Array<Record<string, unknown>>).find((p) => p.name === 'depth_mm')
        depthMm = depth ? num(depth.value) : null
      }
      features.push({ kind: ftype, id, consumesSketchId: payloadSketch as string, depthMm, parameters: decodeParameters(raw, ftype) })
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
  if (sk.plane.kind !== 'principal' || sk.plane.orientation !== 'xy') return 'v1 revolve requires a sketch on the xy (FRONT) plane'
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
  // v1 and v2 sketches share ONE user-facing ordinal sequence — a sketch is
  // a sketch in the tree; the v2 row is labeled as constrained.
  for (const f of part.features) {
    if (f.kind === 'sketch' || f.kind === 'sketchV2') sketchOrdinal.set(f.id, ++nSketch)
  }

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
    } else if (f.kind === 'sketchV2') {
      // A v2 constrained sketch is never consumable in F2a (nothing v1 reads
      // it); it always renders top-level, labeled for what it is.
      rows.push({
        featureId: f.id,
        label: `Sketch ${sketchOrdinal.get(f.id)} (constrained)`,
        depth: 0,
        kind: 'sketchV2',
      })
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

/** P (arc 20260717-2): the SEQUENTIAL eligibility refusal for one unconsumed
 *  sketch — the engine's v1 domain mirrored (never predicted): with a body,
 *  a sequential extrude consumes a FACE-BOUND sketch. Null = eligible. */
export function sequentialSketchRefusal(
  part: InspectedPart, sk: InspectedSketch,
): string | null {
  if (!part.hasExtrudeBase) return null // the BASE lane — any plane
  if (sk.plane.kind !== 'face') {
    return 'datum-bound — a sequential extrude consumes a FACE-BOUND sketch (sketch on a face of the body)'
  }
  return null
}

/** Codex14 B2: THE one eligible-sequential-sketch derivation — shared by
 *  the ribbon, canExtrude, the panel/solicit rendering, AND the terminal
 *  solicit revalidation (never a render-captured copy). */
export function eligibleExtrudeSketchIds(part: InspectedPart): Set<string> {
  return new Set(
    unconsumedSketches(part)
      .filter((sk) => sk.profile.kind !== 'sketch_only')
      .filter((sk) => sequentialSketchRefusal(part, sk) === null)
      .map((sk) => sk.id),
  )
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
