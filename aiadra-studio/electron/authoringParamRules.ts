/**
 * The MAIN-PROCESS authoring allowlist + parameter rules (ADR/0043 Codex B1),
 * extracted PURE (Codex27 B1) so the renderer's op builders can be driven
 * through the EXACT boundary in tests — the desktop-walk lesson made
 * executable: this validator once froze at the R-arc while the engine and
 * renderer moved on, and the whole sequential lane became unreachable on
 * desktop with every suite green. The parity regression
 * (`authoringParamRules.test.ts`) drives every current renderer op-builder's
 * representative output through `validateAuthoringParams` so the boundary
 * can never again silently disagree with what the app actually sends.
 *
 * Structural checks ONLY — the engine's exact validators remain the
 * authority; a shape accepted here can still refuse there.
 */

export const AUTHORING_KINDS = new Set<string>([
  'create_part',
  'mechanical.add_sketch_feature',
  // Gate F2b (arc 20260717-2): the first v2 writer — the references sketch.
  'mechanical.add_reference_sketch',
  // ADR/0044 A3.6.2 (pass sketch-place-1): the 0.2.1 placement redefine.
  'mechanical.redefine_sketch_placement',
  // ADR/0044 A4 (arc 20260730-1): the 0.2.2 profile lane — ONE fact graph
  // behind every drawing tool. Line/polyline/rectangle/circle are UI sugar
  // and deliberately have NO ops of their own.
  'mechanical.author_profile_sketch',
  'mechanical.replace_sketch_graph',
  'mechanical.add_extrude_feature',
  'mechanical.add_revolve_feature',
  'mechanical.add_fillet_feature',
  'mechanical.add_chamfer_feature',
  'mechanical.add_hole_feature',
  'mechanical.adjust_feature_parameter',
])

const posNum = (v: unknown): boolean => typeof v === 'number' && Number.isFinite(v) && v > 0

// ADR/0044 A3 wire shapes (D6: main owns the CLOSED envelope only — enums,
// keys, types; the engine owns derivation/semantic validity).
const isPrincipalRec = (rec: unknown): boolean => {
  if (rec === null || typeof rec !== 'object') return false
  const r = rec as Record<string, unknown>
  return (
    r.kind === 'principal' &&
    (r.orientation === 'xy' || r.orientation === 'yz' || r.orientation === 'zx') &&
    Object.keys(r).length === 2
  )
}
const PLACEMENT_MEMBERS = ['support', 'orientation_ref', 'orientation', 'normal_side'] as const
/** Validate ONE provided placement member's wire shape; null = ok. */
const placementMemberError = (op: string, key: string, v: unknown): string | null => {
  if (key === 'support' || key === 'orientation_ref') {
    return isPrincipalRec(v)
      ? null
      : `${op} ${key} must be exactly {kind:'principal', orientation:'xy'|'yz'|'zx'}`
  }
  if (key === 'orientation') {
    return v === 'right' || v === 'top' || v === 'left' || v === 'bottom'
      ? null
      : `${op} orientation must be 'right'|'top'|'left'|'bottom'`
  }
  return v === 'positive' || v === 'negative'
    ? null
    : `${op} normal_side must be 'positive'|'negative'`
}

// ---- ADR/0044 A4 profile wire shape (arc 20260730-1) ---------------------
// Main owns the CLOSED envelope only: which keys exist, of which type, and
// that a reference is `{key}` XOR `{id}` — never a bare string, so a ref can
// never be read two ways. Identity minting, the survival law and every
// geometric rule stay with the engine (ADR/0045 D6).
const PROFILE_KEYS = ['points', 'segments', 'circles', 'facts'] as const
const KEY_RE = /^[A-Za-z0-9_]{1,32}$/
const ENTITY_ID_RE = /^skp_[0-9]{4}$/
const FACT_ID_RE = /^c[0-9]{2}$/
const finite = (v: unknown): boolean => typeof v === 'number' && Number.isFinite(v)

const refError = (op: string, where: string, v: unknown): string | null => {
  if (v === null || typeof v !== 'object') {
    return `${op} ${where} must be {key} or {id} — a bare string is never accepted`
  }
  const r = v as Record<string, unknown>
  const keys = Object.keys(r)
  if (keys.length !== 1) return `${op} ${where} must carry exactly one of 'key' or 'id'`
  if (keys[0] === 'key') {
    return typeof r.key === 'string' && KEY_RE.test(r.key)
      ? null
      : `${op} ${where} key must match ^[A-Za-z0-9_]{1,32}$`
  }
  if (keys[0] === 'id') {
    return typeof r.id === 'string' && ENTITY_ID_RE.test(r.id)
      ? null
      : `${op} ${where} id must match ^skp_NNNN$`
  }
  return `${op} ${where} must carry 'key' or 'id'`
}

/** One record's own identity slot: exactly one of `key` (mint) or `id` (preserve). */
const identityError = (op: string, where: string, r: Record<string, unknown>,
                       idRe: RegExp): string | null => {
  const hasKey = r.key !== undefined
  const hasId = r.id !== undefined
  if (hasKey === hasId) {
    return `${op} ${where} must carry exactly one of 'key' (new) or 'id' (preserve)`
  }
  if (hasKey) {
    return typeof r.key === 'string' && KEY_RE.test(r.key)
      ? null
      : `${op} ${where} key must match ^[A-Za-z0-9_]{1,32}$`
  }
  return typeof r.id === 'string' && idRe.test(r.id)
    ? null
    : `${op} ${where} id has the wrong shape`
}

export function profileError(op: string, profile: unknown): string | null {
  if (profile === null || typeof profile !== 'object' || Array.isArray(profile)) {
    return `${op} profile must be an object`
  }
  const prof = profile as Record<string, unknown>
  const unknownKeys = Object.keys(prof).filter(
    (k) => !(PROFILE_KEYS as readonly string[]).includes(k),
  )
  if (unknownKeys.length > 0) {
    return `${op} profile carries unknown keys ${JSON.stringify(unknownKeys)}`
  }
  for (const collection of PROFILE_KEYS) {
    if (prof[collection] !== undefined && !Array.isArray(prof[collection])) {
      return `${op} profile ${collection} must be an array`
    }
  }
  const points = (prof.points as unknown[]) ?? []
  const segments = (prof.segments as unknown[]) ?? []
  const circles = (prof.circles as unknown[]) ?? []
  const facts = (prof.facts as unknown[]) ?? []

  for (let i = 0; i < points.length; i++) {
    const r = points[i] as Record<string, unknown> | null
    if (r === null || typeof r !== 'object') return `${op} profile points[${i}] must be an object`
    const e = identityError(op, `points[${i}]`, r, ENTITY_ID_RE)
    if (e !== null) return e
    if (!finite(r.x) || !finite(r.y)) return `${op} profile points[${i}] needs finite x + y`
  }
  for (let i = 0; i < segments.length; i++) {
    const r = segments[i] as Record<string, unknown> | null
    if (r === null || typeof r !== 'object') return `${op} profile segments[${i}] must be an object`
    const e = identityError(op, `segments[${i}]`, r, ENTITY_ID_RE)
    if (e !== null) return e
    for (const end of ['start', 'end'] as const) {
      const re = refError(op, `segments[${i}].${end}`, r[end])
      if (re !== null) return re
    }
  }
  for (let i = 0; i < circles.length; i++) {
    const r = circles[i] as Record<string, unknown> | null
    if (r === null || typeof r !== 'object') return `${op} profile circles[${i}] must be an object`
    const e = identityError(op, `circles[${i}]`, r, ENTITY_ID_RE)
    if (e !== null) return e
    const re = refError(op, `circles[${i}].center`, r.center)
    if (re !== null) return re
    if (!posNum(r.radius_mm)) return `${op} profile circles[${i}] radius_mm must be a number > 0`
  }
  for (let i = 0; i < facts.length; i++) {
    const r = facts[i] as Record<string, unknown> | null
    if (r === null || typeof r !== 'object') return `${op} profile facts[${i}] must be an object`
    const e = identityError(op, `facts[${i}]`, r, FACT_ID_RE)
    if (e !== null) return e
    if (r.kind !== 'horizontal' && r.kind !== 'vertical') {
      return `${op} profile facts[${i}] kind must be 'horizontal'|'vertical'`
    }
    const re = refError(op, `facts[${i}].target`, r.target)
    if (re !== null) return re
  }
  return null
}

export function validateAuthoringParams(kind: string, params: unknown): string | null {
  if (params === null || typeof params !== 'object') return 'op params must be an object'
  const p = params as Record<string, unknown>
  switch (kind) {
    case 'create_part':
      return typeof p.number === 'string' && typeof p.name === 'string'
        ? null
        : 'create_part requires string number + name'
    case 'mechanical.add_sketch_feature': {
      if (typeof p.part_number !== 'string' || !Array.isArray(p.primitives)) {
        return 'add_sketch_feature requires part_number + primitives[]'
      }
      // EP1/EP2 + SK-C1.0 S2 (Petre's desktop walk 2026-07-24: this boundary
      // had FROZEN at principal-only while the engine gained the face
      // binding — the allowlist must track the op surface): the optional
      // DISCRIMINATED plane record — structural check only; the engine's
      // exact validator is the authority.
      if (p.plane !== undefined) {
        const pl = p.plane as {
          kind?: unknown
          orientation?: unknown
          target_face_id?: unknown
        } | null
        const principalOk =
          pl !== null &&
          typeof pl === 'object' &&
          pl.kind === 'principal' &&
          (pl.orientation === 'xy' || pl.orientation === 'yz' || pl.orientation === 'zx')
        // ADR/0038 INPUT vocabulary at the op boundary: the renderer names
        // the DISPLAY face id; the ENGINE re-anchors it into the stored
        // {face_role, resolved_against_topology_signature} reference at
        // commit. The boundary validates the op shape, never the record.
        const faceOk =
          pl !== null &&
          typeof pl === 'object' &&
          pl.kind === 'face' &&
          typeof pl.target_face_id === 'string' &&
          pl.target_face_id.length > 0
        if (!principalOk && !faceOk) {
          return "add_sketch_feature plane must be {kind:'principal', orientation:'xy'|'yz'|'zx'} or {kind:'face', target_face_id}"
        }
      }
      return null
    }
    case 'mechanical.add_reference_sketch': {
      // Gate F2b (Codex27 B1): part_number required; every other field is
      // optional with engine-side defaults — but a PRESENT member must be
      // valid (explicit null/face/extra-key planes refuse HERE, before
      // bridge dispatch; absence ≠ null). The v2 references contract is
      // closed principal-only in F2b.
      if (typeof p.part_number !== 'string') {
        return 'add_reference_sketch requires part_number'
      }
      if (p.axes !== undefined && p.axes !== 'none' && p.axes !== 'x' && p.axes !== 'xy') {
        return "add_reference_sketch axes must be 'none'|'x'|'xy'"
      }
      if (p.x_axis_mm !== undefined && !posNum(p.x_axis_mm)) return 'add_reference_sketch x_axis_mm must be a finite number > 0'
      if (p.y_axis_mm !== undefined && !posNum(p.y_axis_mm)) return 'add_reference_sketch y_axis_mm must be a finite number > 0'
      if (p.plane !== undefined) {
        const pl = p.plane as { kind?: unknown; orientation?: unknown } | null
        const ok =
          pl !== null &&
          typeof pl === 'object' &&
          pl.kind === 'principal' &&
          (pl.orientation === 'xy' || pl.orientation === 'yz' || pl.orientation === 'zx') &&
          Object.keys(pl).length === 2
        if (!ok) {
          return "add_reference_sketch plane must be exactly {kind:'principal', orientation:'xy'|'yz'|'zx'} (face-bound v2 references refuse in F2b)"
        }
      }
      // A3.6.1: the explicit 0.2.1 lane — `placement` is a closed object
      // with REQUIRED support; the two lanes are mutually exclusive at the
      // wire (the engine refuses too; main refuses the SHAPE early).
      if (p.placement !== undefined) {
        if (p.plane !== undefined) {
          return 'add_reference_sketch plane and placement are mutually exclusive (A3.6.1)'
        }
        const pm = p.placement as Record<string, unknown> | null
        if (pm === null || typeof pm !== 'object') {
          return 'add_reference_sketch placement must be an object'
        }
        const unknown = Object.keys(pm).filter((k) => !(PLACEMENT_MEMBERS as readonly string[]).includes(k))
        if (unknown.length > 0) {
          return `add_reference_sketch placement carries unknown members ${JSON.stringify(unknown)}`
        }
        if (pm.support === undefined) return 'add_reference_sketch placement requires support'
        for (const key of PLACEMENT_MEMBERS) {
          if (pm[key] === undefined) continue
          const err = placementMemberError('add_reference_sketch placement', key, pm[key])
          if (err !== null) return err
        }
      }
      return null
    }
    case 'mechanical.redefine_sketch_placement': {
      // A3.6.2 wire shape: target + any PROVIDED placement members must be
      // well-formed; omission semantics (keep-current) are the ENGINE's.
      if (typeof p.part_number !== 'string' || typeof p.sketch_feature_id !== 'string') {
        return 'redefine_sketch_placement requires part_number + sketch_feature_id'
      }
      for (const key of PLACEMENT_MEMBERS) {
        if (p[key] === undefined) continue
        const err = placementMemberError('redefine_sketch_placement', key, p[key])
        if (err !== null) return err
      }
      return null
    }
    case 'mechanical.author_profile_sketch': {
      // A4 create lane: a placed sketch plus the drawn profile graph. The
      // placement is REQUIRED here (a sketch is always placed) and is the
      // same closed A3 record the reference writer uses.
      if (typeof p.part_number !== 'string') {
        return 'author_profile_sketch requires part_number'
      }
      const pm = p.placement as Record<string, unknown> | null
      if (pm === null || typeof pm !== 'object') {
        return 'author_profile_sketch requires a placement object'
      }
      const unknown = Object.keys(pm).filter(
        (k) => !(PLACEMENT_MEMBERS as readonly string[]).includes(k),
      )
      if (unknown.length > 0) {
        return `author_profile_sketch placement carries unknown members ${JSON.stringify(unknown)}`
      }
      if (pm.support === undefined) return 'author_profile_sketch placement requires support'
      for (const key of PLACEMENT_MEMBERS) {
        if (pm[key] === undefined) continue
        const e = placementMemberError('author_profile_sketch placement', key, pm[key])
        if (e !== null) return e
      }
      if (p.axes !== undefined && p.axes !== 'none' && p.axes !== 'x' && p.axes !== 'xy') {
        return "author_profile_sketch axes must be 'none'|'x'|'xy'"
      }
      if (p.x_axis_mm !== undefined && !posNum(p.x_axis_mm)) {
        return 'author_profile_sketch x_axis_mm must be a finite number > 0'
      }
      if (p.y_axis_mm !== undefined && !posNum(p.y_axis_mm)) {
        return 'author_profile_sketch y_axis_mm must be a finite number > 0'
      }
      return profileError('author_profile_sketch', p.profile)
    }
    case 'mechanical.replace_sketch_graph': {
      // A4 edit lane. Absence of a record from the profile is MEANINGFUL
      // (it removes it), so main must not "helpfully" default anything.
      if (typeof p.part_number !== 'string' || typeof p.sketch_feature_id !== 'string') {
        return 'replace_sketch_graph requires part_number + sketch_feature_id'
      }
      return profileError('replace_sketch_graph', p.profile)
    }
    case 'mechanical.add_extrude_feature':
      return typeof p.part_number === 'string' &&
        typeof p.sketch_feature_id === 'string' &&
        posNum(p.depth_mm)
        ? null
        : 'add_extrude_feature requires part_number + sketch_feature_id + depth_mm(>0)'
    case 'mechanical.add_revolve_feature':
      // Arc 20260715-1 R3: axis is structural x|y; the engine's rectangle/
      // crossing validators are the authority.
      return typeof p.part_number === 'string' &&
        typeof p.sketch_feature_id === 'string' &&
        (p.axis === 'x' || p.axis === 'y')
        ? null
        : "add_revolve_feature requires part_number + sketch_feature_id + axis 'x'|'y'"
    // Arc 20260715-1 R4: the selection→target slice — target_edge is the
    // ADR/0038 INPUT vocabulary (the engine re-anchors it).
    case 'mechanical.add_fillet_feature':
      return typeof p.part_number === 'string' && posNum(p.radius_mm) &&
        typeof p.target_edge_id === 'string'
        ? null
        : 'add_fillet_feature requires part_number + target_edge_id + radius_mm(>0)'
    case 'mechanical.add_chamfer_feature':
      return typeof p.part_number === 'string' && posNum(p.distance_mm) &&
        typeof p.target_edge_id === 'string'
        ? null
        : 'add_chamfer_feature requires part_number + target_edge_id + distance_mm(>0)'
    case 'mechanical.add_hole_feature':
      // Codex3 N2: structured clone can carry NaN/Infinity — centers must
      // be FINITE numbers at the allowlist boundary.
      return typeof p.part_number === 'string' &&
        typeof p.target_face_id === 'string' &&
        posNum(p.diameter_mm) &&
        typeof p.center_x_mm === 'number' && Number.isFinite(p.center_x_mm) &&
        typeof p.center_y_mm === 'number' && Number.isFinite(p.center_y_mm)
        ? null
        : 'add_hole_feature requires part_number + target_face_id + diameter_mm(>0) + finite center_x_mm/center_y_mm'
    case 'mechanical.adjust_feature_parameter':
      return typeof p.part_number === 'string' &&
        typeof p.feature_id === 'string' &&
        typeof p.parameter_name === 'string' &&
        typeof p.new_value === 'number' && Number.isFinite(p.new_value)
        ? null
        : 'adjust_feature_parameter requires part_number + feature_id + parameter_name + numeric new_value'
    default:
      return `feature kind not allowed: ${kind}`
  }
}
