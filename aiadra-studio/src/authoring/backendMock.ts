/**
 * The dev:web mock AuthoringBackend (arc 20260711-11 / slice 1b; Codex B2).
 *
 * Deterministic, no engine, no Product-Truth writes — for iterating the
 * authoring UX instantly under `npm run dev:web`. It is HONEST: it returns only
 * geometry the real engine can produce, clearly badged as a mock preview, never
 * a real committed Part. The Electron bridge lane (backendBridge) is the source
 * of truth for real geometry.
 *
 * slice X: for a DRAWN contour it synthesizes the true extruded solid
 * (`proceduralContourSource`) so the browser shows exactly the shape you drew;
 * for the parametric-rectangle path it falls back to the baked `extrude-box`.
 */
import { loadExtrudeBoxSource } from '../dev/fixtureSource'
import {
  emptyMockSource,
  proceduralContourSource,
  proceduralRevolveSource,
  type PlaneOrientation,
} from '../sketch/proceduralExtrude'
import { segmentsProblem, type Pt, type Segment } from '../sketch/contour'
import { classifySketch } from '../sketch/profileClassify'
import { tessellateCircle, tessellateSegments } from '../sketch/arcGeometry'
import {
  resolveOpAliases,
  type AuthoringBackend,
  type BeginResult,
  type CommitResult,
  type FeatureOp,
  type SimulateResult,
} from './backend'

type Seg = { kind?: string; x1_mm: number; y1_mm: number; x2_mm?: number; y2_mm?: number; bulge?: number }

/** Pull the drawn contour out of an op sequence: `points` are TESSELLATED for
 *  the procedural solid (arcs faceted, SK-C0); `segments` keep the authored
 *  typed chain for the Class-1 mirror; `construction` mirrors D-C3. */
function contourFromOps(
  ops: FeatureOp[],
): { points: Pt[]; segments: Segment[]; construction: boolean; depthMm: number; plane: PlaneOrientation } | null {
  const sketch = ops.find((o) => o.kind === 'mechanical.add_sketch_feature')
  const extrude = ops.find((o) => o.kind === 'mechanical.add_extrude_feature')
  const prims = (sketch?.params.primitives as Array<{ type?: string; segments?: Seg[]; construction?: boolean }>) ?? []
  const contour = prims.find((p) => p.type === 'contour')
  if (!contour?.segments?.length) return null
  const segments = contour.segments as Segment[]
  const points = tessellateSegments(segments)
  const depthMm = Number(extrude?.params.depth_mm ?? 6)
  const planeRec = sketch?.params.plane as { orientation?: PlaneOrientation } | undefined
  const plane: PlaneOrientation = planeRec?.orientation ?? 'xy'
  return { points, segments, construction: contour.construction === true, depthMm, plane }
}

/** SK-C0 D-C2: a circle-as-outer sketch op + extrude → the faceted cylinder. */
function circleFromOps(
  ops: FeatureOp[],
): { points: Pt[]; construction: boolean; depthMm: number; plane: PlaneOrientation } | null {
  const sketch = ops.find((o) => o.kind === 'mechanical.add_sketch_feature')
  const extrude = ops.find((o) => o.kind === 'mechanical.add_extrude_feature')
  const prims = (sketch?.params.primitives as Array<Record<string, unknown>>) ?? []
  if (prims.length !== 1 || prims[0]?.type !== 'circle') return null
  const c = prims[0]
  const points = tessellateCircle(Number(c.cx_mm), Number(c.cy_mm), Number(c.radius_mm))
  const planeRec = sketch?.params.plane as { orientation?: PlaneOrientation } | undefined
  return {
    points,
    construction: c.construction === true,
    depthMm: Number(extrude?.params.depth_mm ?? 6),
    plane: (planeRec?.orientation ?? 'xy') as PlaneOrientation,
  }
}

/** An op sequence that ONLY creates a Part (EP1 commit-at-New). */
function isCreateOnly(ops: FeatureOp[]): boolean {
  return ops.length === 1 && ops[0].kind === 'create_part'
}

/** The mock backend + its honest Truth mirror: `inspectRaw` serves the SAME
 *  raw sidecar shape the bridge's `inspect` returns, so the partContext /
 *  decoder / tree pipeline runs identically in browser dev (one decoder, two
 *  lanes — never a mock-only tree shape). */
export interface MockAuthoringBackend extends AuthoringBackend {
  inspectRaw(partNumber: string): unknown
}

/** Build the raw feature records an op WOULD write to Truth (the engine's
 *  sidecar shape, adapter 0.1.8) — the mock's committed-part mirror. The
 *  `engine` stamp is LOAD-BEARING (Codex3 B1): the decoder interprets
 *  mechanical payloads only under `engine === 'mechanical'`, exactly like the
 *  real sidecar records — an unstamped mirror record would decode as a
 *  generic feature (no wire, unselectable, invisible to Extrude). */
function rawFeatureFromOp(kind: string, params: Record<string, unknown>, id: string): Record<string, unknown> | null {
  if (kind === 'mechanical.add_sketch_feature') {
    // SK-C0 Codex3 B3: the mock mints the SAME deterministic identity shapes
    // as the engine's build_sketch_payload — skp_NNNN primitives and
    // skp_NNNNsNN contour segments; caller-supplied ids are refused.
    const prims = (params.primitives as Array<Record<string, unknown>>).map((p, i) => {
      if ('id' in p) throw new Error('mock: primitives must not carry caller-supplied ids')
      const skp = `skp_${String(i + 1).padStart(4, '0')}`
      const out: Record<string, unknown> = { ...p, id: skp }
      if (p.type === 'contour' && Array.isArray(p.segments)) {
        out.segments = (p.segments as Array<Record<string, unknown>>).map((seg, k) => {
          if ('id' in seg) throw new Error('mock: segments must not carry caller-supplied ids')
          return { ...seg, id: `${skp}s${String(k + 1).padStart(2, '0')}` }
        })
      }
      return out
    })
    const payload: Record<string, unknown> = { primitives: prims }
    if (params.plane !== undefined) payload.plane = params.plane
    return {
      id,
      feature_type: 'sketch',
      engine: 'mechanical',
      adapter_schema_version: '0.1.9',
      adapter_payload: payload,
    }
  }
  if (kind === 'mechanical.add_extrude_feature') {
    return {
      id,
      feature_type: 'extrude',
      engine: 'mechanical',
      adapter_schema_version: '0.1.9',
      depends_on_feature_ids: [params.sketch_feature_id],
      parameters: [{ id: 'featp_mock', name: 'depth_mm', value: params.depth_mm, datatype: 'number', unit: 'mm' }],
      adapter_payload: { sketch_feature_id: params.sketch_feature_id, direction: params.direction },
    }
  }
  if (kind === 'mechanical.add_revolve_feature') {
    // R3 mock parity (D-R10): the mirror record matches the engine's shape;
    // the axis is structural (no editable parameters in v1).
    return {
      id,
      feature_type: 'revolve',
      engine: 'mechanical',
      adapter_schema_version: '0.1.9',
      depends_on_feature_ids: [params.sketch_feature_id],
      adapter_payload: { sketch_feature_id: params.sketch_feature_id, axis: params.axis },
    }
  }
  return null
}

export function createMockAuthoringBackend(): MockAuthoringBackend {
  let counter = 0
  const open = new Map<string, { ops: FeatureOp[]; features: Record<string, unknown>[]; partNumber: string | null; partName: string | null }>()
  // The committed mirror: partNumber → { name, features } (grows per commit,
  // ids continue across commits — same numbering behavior as the engine).
  const parts = new Map<string, { name: string; features: Record<string, unknown>[] }>()

  /** R3: resolve a revolve op's rectangle — from THIS session's sketch op
   *  (the chained path) or the mirror's committed sketch (entry A). */
  const revolveFromOps = (
    ops: FeatureOp[],
    partNumber: string,
  ): { rect: { x_mm: number; y_mm: number; width_mm: number; height_mm: number }; axis: 'x' | 'y' } | null => {
    const rev = ops.find((o) => o.kind === 'mechanical.add_revolve_feature')
    if (!rev) return null
    const axis = rev.params.axis as 'x' | 'y'
    const sessionSketch = ops.find((o) => o.kind === 'mechanical.add_sketch_feature')
    const prim = sessionSketch
      ? ((sessionSketch.params.primitives ?? []) as Array<Record<string, unknown>>)[0]
      : (() => {
          const recSk = parts
            .get(partNumber)
            ?.features.find((f) => f.id === rev.params.sketch_feature_id && f.feature_type === 'sketch')
          const payload = (recSk?.adapter_payload ?? {}) as Record<string, unknown>
          return ((payload.primitives ?? []) as Array<Record<string, unknown>>)[0]
        })()
    if (!prim || prim.type !== 'rectangle') return null
    return {
      rect: {
        x_mm: Number(prim.x_mm),
        y_mm: Number(prim.y_mm),
        width_mm: Number(prim.width_mm),
        height_mm: Number(prim.height_mm),
      },
      axis,
    }
  }

  /** Entry-A support: resolve the extruded COMMITTED sketch from the mirror
   *  into drawable points + plane (contour chain or rectangle corners). */
  const mirroredContour = (
    ops: FeatureOp[],
    partNumber: string,
  ): { points: Pt[]; depthMm: number; plane: PlaneOrientation } | null => {
    const ext = ops.find((o) => o.kind === 'mechanical.add_extrude_feature')
    if (!ext) return null
    const rec = parts
      .get(partNumber)
      ?.features.find((f) => f.id === ext.params.sketch_feature_id && f.feature_type === 'sketch')
    if (!rec) return null
    const payload = (rec.adapter_payload ?? {}) as Record<string, unknown>
    const prim = ((payload.primitives ?? []) as Array<Record<string, unknown>>)[0]
    if (!prim) return null
    if (prim.construction === true) return null // a guide never extrudes (D-C3)
    let points: Pt[]
    if (prim.type === 'contour') {
      points = tessellateSegments((prim.segments ?? []) as Segment[])
    } else if (prim.type === 'circle') {
      points = tessellateCircle(Number(prim.cx_mm), Number(prim.cy_mm), Number(prim.radius_mm))
    } else if (prim.type === 'rectangle') {
      const x = Number(prim.x_mm)
      const y = Number(prim.y_mm)
      const w = Number(prim.width_mm)
      const h = Number(prim.height_mm)
      points = [{ x, y }, { x: x + w, y }, { x: x + w, y: y + h }, { x, y: y + h }]
    } else return null
    const plane = ((payload.plane as { orientation?: PlaneOrientation } | undefined)?.orientation ?? 'xy') as PlaneOrientation
    return { points, depthMm: Number(ext.params.depth_mm ?? 6), plane }
  }

  return {
    isReal: false,
    async begin(ops: FeatureOp[]): Promise<BeginResult> {
      const sessionId = `mock-op-${++counter}`
      // Shallow structural sanity so the mock can't "succeed" on nonsense the
      // real bridge would reject (keeps the mock honest).
      if (ops.length === 0) throw new Error('mock: empty op sequence')
      // S2 honest-mock mirror of the engine handshake: each `mechanical.add_*`
      // op mints exactly one feature record; `$fromOp` aliases resolve through
      // the SAME shared resolver (same loud cardinality/reference failures).
      const createOp = ops.find((o) => o.kind === 'create_part')
      const targetNumber =
        (createOp?.params.number as string | undefined) ??
        (ops.find((o) => typeof o.params.part_number === 'string')?.params.part_number as string | undefined) ??
        null
      const perOpIds: string[][] = []
      const features: Record<string, unknown>[] = []
      // Continue the target Part's numbering, like the engine does.
      let featSeq = targetNumber ? (parts.get(targetNumber)?.features.length ?? 0) : 0
      const resolved: FeatureOp[] = ops.map((op, i) => {
        const params = resolveOpAliases(op.params, i, perOpIds) as Record<string, unknown>
        if (op.kind.startsWith('mechanical.add_')) {
          const id = `feat_${String(++featSeq).padStart(4, '0')}`
          perOpIds.push([id])
          const raw = rawFeatureFromOp(op.kind, params, id)
          if (raw === null) {
            // D-R10 (Codex1 B4): the mock REFUSES what its mirror cannot
            // materialize — silent mock success is worse than a loud refusal.
            // The ribbon disables these in dev:web; this is defence-in-depth.
            throw new Error(`mock: ${op.kind} requires the desktop real-engine lane`)
          }
          features.push(raw)
        } else if (op.kind.startsWith('mechanical.')) {
          throw new Error(`mock: ${op.kind} requires the desktop real-engine lane`)
        } else {
          perOpIds.push([])
        }
        return { kind: op.kind, params }
      })
      open.set(sessionId, {
        ops: resolved,
        features,
        partNumber: targetNumber,
        partName: (createOp?.params.name as string | undefined) ?? null,
      })
      return { sessionId, createdFeatureIds: perOpIds }
    },
    inspectRaw(partNumber: string): unknown {
      const p = parts.get(partNumber)
      if (!p) throw new Error(`mock: no committed Part ${partNumber}`)
      return {
        object_number: partNumber,
        object_type: 'Part',
        sidecar: {
          object: { type: 'Part', number: partNumber, name: p.name, uuid: `mock-${partNumber}` },
          feature: p.features,
        },
      }
    },
    async simulate(sessionId: string): Promise<SimulateResult> {
      const session = open.get(sessionId)
      if (!session) return { valid: false, message: 'no open session' }
      // Codex6 B2 (defence-in-depth): the mock must never report success the
      // real engine would reject — run the SAME pure Class-1 mirror on a drawn
      // contour (zero-length/duplicate, open, self-intersecting, collinear).
      const contour = contourFromOps(session.ops)
      const sessionHasBase = session.ops.some(
        (o) => o.kind === 'mechanical.add_extrude_feature' || o.kind === 'mechanical.add_revolve_feature',
      )
      if (contour) {
        // SK-C0: the CURVE-AWARE Class-1 mirror over the authored segments.
        const problem = segmentsProblem(contour.segments)
        if (problem) return { valid: false, message: `mock Class-1: ${problem}` }
        if (sessionHasBase && !(contour.depthMm > 0)) {
          return { valid: false, message: 'mock Class-1: depth must be positive' }
        }
        if (sessionHasBase && contour.construction) {
          return { valid: false, message: 'mock Class-1: a construction-only sketch cannot be extruded' }
        }
      }
      const circleOp = circleFromOps(session.ops)
      if (circleOp && sessionHasBase && circleOp.construction) {
        return { valid: false, message: 'mock Class-1: a construction-only sketch cannot be extruded' }
      }
      // SK-C0 Codex3 B2 + Codex5 B2: ENTRY A — an extrude consuming a
      // previously COMMITTED sketch resolves eligibility through the ONE
      // classifier mirror (never a reimplemented special case): a classifier
      // failure refuses, and outerKind 'none' — EMPTY or construction-only —
      // refuses too, exactly like the engine.
      if (sessionHasBase && !contour && !circleOp) {
        const ext = session.ops.find((o) => o.kind === 'mechanical.add_extrude_feature')
        const target = session.partNumber ? parts.get(session.partNumber) : undefined
        const rec = target?.features.find(
          (f) => f.id === ext?.params.sketch_feature_id && f.feature_type === 'sketch',
        )
        if (rec) {
          const payload = (rec.adapter_payload ?? {}) as Record<string, unknown>
          const prims = (payload.primitives ?? []) as Array<Record<string, unknown>>
          const verdict = classifySketch(prims)
          if (!verdict.ok) return { valid: false, message: `mock Class-1: ${verdict.reason}` }
          if (verdict.classification.outerKind === 'none') {
            return { valid: false, message: 'mock Class-1: the consumed sketch has no extrudable profile (empty or construction-only)' }
          }
        }
      }
      // S2 B3 mirror: the engine rejects a second base creation — so does the mock.
      const target = session.partNumber ? parts.get(session.partNumber) : undefined
      const priorBase = target?.features.some((f) => f.feature_type === 'extrude' || f.feature_type === 'revolve')
      const addsBase = session.features.some((f) => f.feature_type === 'extrude' || f.feature_type === 'revolve')
      if (priorBase && addsBase) {
        return { valid: false, message: 'mock one-base rule: the Part already has a base creation feature' }
      }
      return { valid: true }
    },
    async commit(sessionId: string, objectRef: string): Promise<CommitResult> {
      const session = open.get(sessionId)
      if (!session) throw new Error('mock: no open session')
      const { ops } = session
      const badge = `${objectRef} — dev mock (procedural, not a real Part)`
      const contour = contourFromOps(ops)
      // A session WITHOUT a base creation op produces NO solid (S2 stepwise:
      // a sketch-only commit shows as emptiness + the wire overlay — exactly
      // what the real engine's display returns for an unconsumed sketch).
      const hasBase = ops.some(
        (o) => o.kind === 'mechanical.add_extrude_feature' || o.kind === 'mechanical.add_revolve_feature',
      )
      // Entry A (extrude a COMMITTED sketch): the session has no sketch op —
      // resolve the consumed sketch from the mirror so the mock shows the
      // DRAWN geometry, never a canned box for a real reference.
      const revolve = hasBase ? revolveFromOps(ops, session.partNumber ?? objectRef) : null
      const circleSolid = !revolve && hasBase ? circleFromOps(ops) : null
      const mirrored = !contour && !revolve && !circleSolid && hasBase ? mirroredContour(ops, session.partNumber ?? objectRef) : null
      const solid = (contour && !contour.construction ? contour : null) ?? (circleSolid && !circleSolid.construction ? circleSolid : null) ?? mirrored
      const display =
        isCreateOnly(ops) || !hasBase
          ? emptyMockSource(objectRef, `${objectRef} — dev mock (not Truth)`)
          : revolve
            ? proceduralRevolveSource(revolve.rect, revolve.axis, badge)
            : solid
              ? proceduralContourSource(solid.points, solid.depthMm, badge, solid.plane)
              : (() => {
                  // SK-C0 Codex3 B2: NO canned fallback — a base op the mock
                  // cannot honestly synthesize is a loud refusal, never a box.
                  throw new Error(
                    'mock: this base feature has no honest procedural synthesis (unsupported/ineligible source)',
                  )
                })()
      if (!display) throw new Error('mock: display unavailable')
      // Register the commit in the mock's Truth mirror (feeds inspectRaw).
      const number = session.partNumber ?? objectRef
      const entry = parts.get(number) ?? { name: session.partName ?? number, features: [] }
      if (session.partName) entry.name = session.partName
      entry.features.push(...session.features)
      parts.set(number, entry)
      open.delete(sessionId)
      return { objectRef, display }
    },
    async rollback(sessionId: string): Promise<void> {
      open.delete(sessionId)
    },
    async previewSource() {
      return loadExtrudeBoxSource('extrude preview — dev mock (transient)')
    },
  }
}
