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
