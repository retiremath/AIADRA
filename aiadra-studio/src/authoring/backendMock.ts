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
import type { DisplaySource } from '../display/displaySource'
import {
  emptyMockSource,
  proceduralContourSource,
  proceduralRevolveSource,
  type PlaneOrientation,
} from '../sketch/proceduralExtrude'
import { segmentsProblem, type Pt, type Segment } from '../sketch/contour'
import { frameFromNormalAndPoint } from '../sketch/planeFrame'
import { buildContourDisplay, displayToSource, mergeDisplays } from '../sketch/proceduralExtrude'
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
      adapter_schema_version: '0.1.11',
      adapter_payload: payload,
    }
  }
  if (kind === 'mechanical.add_reference_sketch') {
    // Gate F2b: the dev-lane mirror of the engine's A2.9 references
    // transaction. The graph shape, ids, and the skb-0 weak completion are
    // DETERMINISTIC for G0/G1/G2 (the engine derives them through the real
    // solver; the mock mirrors the known result — the same honesty posture
    // as every other mock record).
    const axes = (params.axes as string) ?? 'xy'
    const x = (params.x_axis_mm as number) ?? 20.0
    const y = (params.y_axis_mm as number) ?? 20.0
    const entities: Record<string, unknown>[] = [
      { id: 'skp_0001', type: 'point', construction: true, nominal: { x: 0.0, y: 0.0 } },
    ]
    const constraints: Record<string, unknown>[] = [
      { id: 'c01', kind: 'fix', args: ['skp_0001'] },
    ]
    const weak: Record<string, unknown>[] = []
    const mkWeak = (idx: number, entity: string, parameter: string, magnitude: number) => ({
      id: `w${String(idx).padStart(2, '0')}`,
      kind: 'fix_param',
      target: { entity, parameter },
      value: { magnitude, unit: 'mm' },
      strength: 'weak', role: 'driving', visibility: 'internal',
      origin: { category: 'computed_result', policy: 'skb-0', solver_contract: 'skb-c0' },
    })
    if (axes === 'x' || axes === 'xy') {
      entities.push({ id: 'skp_0002', type: 'point', construction: true, nominal: { x, y: 0.0 } })
      entities.push({ id: 'skp_0004', type: 'line', construction: true, start: 'skp_0001', end: 'skp_0002' })
      constraints.push({ id: 'c02', kind: 'horizontal', args: ['skp_0004'] })
      weak.push(mkWeak(1, 'skp_0002', 'x', x))
    }
    if (axes === 'xy') {
      entities.push({ id: 'skp_0003', type: 'point', construction: true, nominal: { x: 0.0, y } })
      entities.push({ id: 'skp_0005', type: 'line', construction: true, start: 'skp_0001', end: 'skp_0003' })
      constraints.push({ id: 'c03', kind: 'vertical', args: ['skp_0005'] })
      weak.push(mkWeak(2, 'skp_0003', 'y', y))
    }
    return {
      id,
      feature_type: 'sketch',
      engine: 'mechanical',
      adapter_schema_version: '0.2.0',
      adapter_payload: {
        sketch_model: 2,
        solver_contract: 'skb-c0',
        weak_policy: 'skb-0',
        branch_policy: 'skb-b0',
        plane: (params.plane as Record<string, unknown>) ?? { kind: 'principal', orientation: 'xy' },
        entities,
        constraints,
        dimensions: [],
        references: [],
        weak_completion: weak,
        witnesses: [],
      },
    }
  }
  if (kind === 'mechanical.add_extrude_feature') {
    return {
      id,
      feature_type: 'extrude',
      engine: 'mechanical',
      adapter_schema_version: '0.1.11',
      // Codex14 B1.4: the SEQUENTIAL graph shape mirrors the signed engine —
      // [consumed_sketch, prior_body_head] when a body exists (`__priorHead`
      // is threaded by begin(); base extrudes keep the single operand edge).
      depends_on_feature_ids: params.__priorHead
        ? [params.sketch_feature_id, params.__priorHead]
        : [params.sketch_feature_id],
      parameters: [{ id: 'featp_mock', name: 'depth_mm', value: params.depth_mm, datatype: 'number', unit: 'mm' }],
      adapter_payload: {
        sketch_feature_id: params.sketch_feature_id,
        direction: params.direction,
        operation: (params.operation as string | undefined) ?? 'add',
      },
    }
  }
  if (kind === 'mechanical.add_revolve_feature') {
    // R3 mock parity (D-R10): the mirror record matches the engine's shape;
    // the axis is structural (no editable parameters in v1).
    return {
      id,
      feature_type: 'revolve',
      engine: 'mechanical',
      adapter_schema_version: '0.1.11',
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

  /** Codex5 B1.2: the display for a commit that adds NO base op must come
   *  from the WHOLE FOLDED mock recipe — a Part whose earlier commits built a
   *  base keeps its body when a later sketch-only feature lands. */
  const foldedBaseDisplay = (partNumber: string | null, badge: string): DisplaySource | null => {
    if (!partNumber) return null
    const part = parts.get(partNumber)
    const base = part?.features.find(
      (f) => f.feature_type === 'extrude' || f.feature_type === 'revolve',
    )
    if (!part || !base) return null
    const basePayload = (base.adapter_payload ?? {}) as Record<string, unknown>
    if (base.feature_type === 'revolve') {
      const rec = part.features.find(
        (f) => f.id === basePayload.sketch_feature_id && f.feature_type === 'sketch',
      )
      const prim = (((rec?.adapter_payload as Record<string, unknown> | undefined)?.primitives ??
        []) as Array<Record<string, unknown>>)[0]
      if (!prim || prim.type !== 'rectangle') return null
      const rect = {
        x_mm: Number(prim.x_mm), y_mm: Number(prim.y_mm),
        width_mm: Number(prim.width_mm), height_mm: Number(prim.height_mm),
      }
      return proceduralRevolveSource(rect, (basePayload.axis as 'x' | 'y') ?? 'x', badge)
    }
    const baseDepth = ((base.parameters as Array<{ name: string; value: unknown }> | undefined) ?? [])
      .find((pr) => pr.name === 'depth_mm')?.value
    const solid = mirroredContour(
      [{ kind: 'mechanical.add_extrude_feature', params: {
        sketch_feature_id: basePayload.sketch_feature_id, depth_mm: baseDepth } }],
      partNumber,
    )
    if (!solid) return null
    // P (arc 20260717-2): the folded body COMPOSES sequential bosses — each
    // committed sequential extrude whose face-bound sketch sits on the TOP
    // cap stacks its prism at the base depth (honest prisms, per-feature ids).
    const reps = [buildContourDisplay(solid.points, solid.depthMm, solid.plane)]
    for (const f of part.features) {
      if (f.feature_type !== 'extrude' || f.id === base.id) continue
      const payload = (f.adapter_payload ?? {}) as Record<string, unknown>
      if (((payload.operation as string | undefined) ?? 'add') !== 'add') continue
      const sk = part.features.find(
        (x) => x.id === payload.sketch_feature_id && x.feature_type === 'sketch',
      )
      const plane = ((sk?.adapter_payload ?? {}) as Record<string, unknown>).plane as
        | { kind?: string; face_role?: string } | undefined
      // Codex14 B3: the SAME exact predicate as simulation — only the BASE's
      // top cap composes; anything else never renders a misplaced prism.
      if (plane?.kind !== 'face' || (plane.face_role ?? '') !== `${base.id}:face:cap_top`) continue
      const prim = (((sk?.adapter_payload ?? {}) as Record<string, unknown>).primitives as
        Array<Record<string, unknown>> | undefined)?.[0]
      const depth = Number(
        ((f.parameters as Array<{ name: string; value: unknown }> | undefined) ?? [])
          .find((pr) => pr.name === 'depth_mm')?.value ?? 6,
      )
      const pts = prim?.type === 'rectangle'
        ? (() => {
            const x = Number(prim.x_mm); const y = Number(prim.y_mm)
            const w = Number(prim.width_mm); const h = Number(prim.height_mm)
            return [{ x, y }, { x: x + w, y }, { x: x + w, y: y + h }, { x, y: y + h }]
          })()
        : prim?.type === 'contour'
          ? tessellateSegments((prim.segments ?? []) as Segment[])
          : prim?.type === 'circle'
            ? tessellateCircle(Number(prim.cx_mm), Number(prim.cy_mm), Number(prim.radius_mm))
            : null
      if (!pts) continue
      reps.push(buildContourDisplay(pts, depth, solid.plane, {
        wOffset: solid.depthMm, idPrefix: `mockb_${f.id}`,
      }))
    }
    return displayToSource(mergeDisplays(reps), badge)
  }

  /** S3: synthesize Display v1.2 sketch_frames for every face-bound sketch
   *  in the folded recipe — the SAME pinned rule as the engine, through the
   *  shared TS mirror (cap frames on the mock's analytic box). */
  const foldedSketchFrames = (
    partNumber: string | null,
    sessionFeatures: Record<string, unknown>[],
  ): Array<Record<string, unknown>> => {
    const committed = partNumber ? parts.get(partNumber)?.features ?? [] : []
    const all = [...committed, ...sessionFeatures]
    const base = all.find((f) => f.feature_type === 'extrude')
    if (!base) return []
    const basePayload = (base.adapter_payload ?? {}) as Record<string, unknown>
    const baseSketch = all.find((f) => f.id === basePayload.sketch_feature_id)
    const ori = (((baseSketch?.adapter_payload as Record<string, unknown> | undefined)?.plane as
      | { orientation?: string }
      | undefined)?.orientation ?? 'xy') as 'xy' | 'yz' | 'zx'
    const N: Record<string, [number, number, number]> = {
      xy: [0, 0, 1], yz: [1, 0, 0], zx: [0, 1, 0],
    }
    const depth = Number(
      ((base.parameters as Array<{ name: string; value: unknown }> | undefined) ?? []).find(
        (pr) => pr.name === 'depth_mm',
      )?.value ?? 6,
    )
    const frames: Array<Record<string, unknown>> = []
    for (const f of all) {
      if (f.feature_type !== 'sketch') continue
      const plane = ((f.adapter_payload ?? {}) as Record<string, unknown>).plane as
        | { kind?: string; face_role?: string }
        | undefined
      if (plane?.kind !== 'face' || typeof plane.face_role !== 'string') continue
      const role = plane.face_role.split(':face:')[1]
      const n = N[ori]
      const outward: [number, number, number] =
        role === 'cap_base' ? [-n[0], -n[1], -n[2]] : n
      const point: [number, number, number] =
        role === 'cap_base' ? [0, 0, 0] : [n[0] * depth, n[1] * depth, n[2] * depth]
      const frame = frameFromNormalAndPoint(outward, point)
      if (!frame) continue
      frames.push({
        sketch_feature_id: f.id,
        origin_mm: [...frame.origin],
        u_axis: [...frame.u],
        v_axis: [...frame.v],
        normal: [...frame.normal],
      })
    }
    return frames
  }

  /** Gate F2b: synthesize Display v1.3 `v2_construction` for every committed
   *  v2 references sketch. HONEST for skb-b0's admitted frames: the
   *  single-root proofs make solved == authored nominals for the canonical
   *  graphs this mock authors, so the nominal-derived wires equal the real
   *  engine's solved-derived ones (the desktop lane derives via the solver). */
  const foldedV2Construction = (
    partNumber: string,
    pending: Array<Record<string, unknown>>,
  ): Array<Record<string, unknown>> => {
    const committed = parts.get(partNumber)?.features ?? []
    const out: Array<Record<string, unknown>> = []
    for (const f of [...committed, ...pending]) {
      const asv = f.adapter_schema_version
      if (typeof asv !== 'string' || !asv.startsWith('0.2.')) continue
      const payload = (f.adapter_payload ?? {}) as Record<string, unknown>
      const pts = new Map<string, [number, number, number]>()
      const points: Array<Record<string, unknown>> = []
      const lines: Array<Record<string, unknown>> = []
      for (const e of (payload.entities as Array<Record<string, unknown>>) ?? []) {
        if (e.type === 'point') {
          const nom = e.nominal as { x: number; y: number }
          const at: [number, number, number] = [nom.x, nom.y, 0]
          pts.set(e.id as string, at)
          points.push({ id: e.id, at })
        }
      }
      for (const e of (payload.entities as Array<Record<string, unknown>>) ?? []) {
        if (e.type === 'line') {
          lines.push({ id: e.id, a: pts.get(e.start as string), b: pts.get(e.end as string) })
        }
      }
      const nLines = lines.length
      out.push({
        sketch_feature_id: f.id,
        shape: nLines === 0 ? 'G0' : nLines === 1 ? 'G1' : 'G2',
        construction: true,
        points,
        lines,
      })
    }
    return out
  }

  const withV2Construction = (
    source: DisplaySource,
    items: Array<Record<string, unknown>>,
  ): DisplaySource => {
    if (items.length === 0) return source
    return {
      ...source,
      getDisplay: async () => {
        const d = (await source.getDisplay()) as unknown as Record<string, unknown>
        return { ...d, v2_construction: items } as unknown as Awaited<
          ReturnType<DisplaySource['getDisplay']>
        >
      },
    }
  }

  /** Attach mock sketch_frames to a display source (payload-level append). */
  const withSketchFrames = (
    source: DisplaySource,
    frames: Array<Record<string, unknown>>,
  ): DisplaySource => {
    if (frames.length === 0) return source
    return {
      ...source,
      getDisplay: async () => {
        const d = (await source.getDisplay()) as unknown as Record<string, unknown>
        return { ...d, sketch_frames: frames } as unknown as Awaited<
          ReturnType<DisplaySource['getDisplay']>
        >
      },
    }
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
      // S3 (dev-lane parity): a FACE-plane sketch input translates to the
      // engine's stored shape against the mock's own committed base — CAPS
      // ONLY (the mock has no topology extraction; walls refuse honestly).
      ops = ops.map((op) => {
        if (op.kind !== 'mechanical.add_sketch_feature') return op
        const plane = op.params.plane as { kind?: string; target_face_id?: unknown } | undefined
        if (plane?.kind !== 'face') return op
        const tid = plane.target_face_id
        if (typeof tid !== 'string') throw new Error('mock: a face plane needs target_face_id')
        const partNumber = op.params.part_number as string | undefined
        const part = partNumber ? parts.get(partNumber) : undefined
        const base = part?.features.find((f) => f.feature_type === 'extrude')
        if (!part || !base) {
          throw new Error('mock: face-bound sketches need a committed extruded base')
        }
        const m = /^mock:(cap_top|cap_base)$/.exec(tid)
        const mb = /^mockb_(feat_\d+):(cap_top|cap_base)$/.exec(tid)
        if (!m && !mb) {
          throw new Error(
            'mock: dev-lane face-bound sketches support the caps only (mock:cap_top / mock:cap_base)',
          )
        }
        // Codex14 B3: a BOSS cap display id translates to that boss's stored
        // role — simulation then refuses it with the named real-lane
        // boundary (reachable honesty, never a silent guess).
        const role = m
          ? `${base.id as string}:face:${m[1]}`
          : `${mb![1]}:face:${mb![2]}`
        return {
          ...op,
          params: {
            ...op.params,
            plane: {
              kind: 'face',
              face_role: role,
              resolved_against_topology_signature: 'mock-topo',
            },
          },
        }
      })
      const perOpIds: string[][] = []
      const features: Record<string, unknown>[] = []
      // Continue the target Part's numbering, like the engine does.
      let featSeq = targetNumber ? (parts.get(targetNumber)?.features.length ?? 0) : 0
      const resolved: FeatureOp[] = ops.map((op, i) => {
        const params = resolveOpAliases(op.params, i, perOpIds) as Record<string, unknown>
        if (op.kind === 'mechanical.adjust_feature_parameter') {
          // S3: a parameter EDIT mints no feature — it retargets a committed
          // one; the mirror mutation happens at commit, existence is checked
          // at simulate (the same honesty split as the real engine).
          perOpIds.push([])
        } else if (op.kind.startsWith('mechanical.add_')) {
          const id = `feat_${String(++featSeq).padStart(4, '0')}`
          perOpIds.push([id])
          // Codex14 B1.4: a sequential extrude records the prior body head
          // (the mock's linear mirror: the LAST committed body feature).
          if (op.kind === 'mechanical.add_extrude_feature' && targetNumber) {
            const committed = parts.get(targetNumber)?.features ?? []
            const priorHead = [...committed].reverse().find(
              (f) => f.feature_type === 'extrude' || f.feature_type === 'revolve',
            )
            if (priorHead) (params as Record<string, unknown>).__priorHead = priorHead.id
          }
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
      // S3: an adjust op must target an existing committed parameter — the
      // mock never reports valid for what its own commit would throw on.
      for (const op of session.ops) {
        if (op.kind !== 'mechanical.adjust_feature_parameter') continue
        const p = parts.get((op.params.part_number as string) ?? session.partNumber ?? '')
        const feat = p?.features.find((f) => f.id === op.params.feature_id)
        const prm = ((feat?.parameters as Array<{ name: string; value: unknown }> | undefined) ?? [])
          .find((pr) => pr.name === op.params.parameter_name)
        if (!prm) {
          return { valid: false, message: 'mock: unknown feature/parameter for adjust_feature_parameter' }
        }
      }
      // P (arc 20260717-2): the SEQUENTIAL mirror — the one-base refusal is
      // lifted for extrudes exactly as far as the mock can honestly go.
      const target = session.partNumber ? parts.get(session.partNumber) : undefined
      const priorBase = target?.features.some((f) => f.feature_type === 'extrude' || f.feature_type === 'revolve')
      const addsRevolve = session.features.some((f) => f.feature_type === 'revolve')
      if (priorBase && addsRevolve) {
        return { valid: false, message: 'mock: sequential features on a revolve are a later slice' }
      }
      const seqExtrudes = priorBase
        ? session.features.filter((f) => f.feature_type === 'extrude')
        : []
      for (const seq of seqExtrudes) {
        const payload = (seq.adapter_payload ?? {}) as Record<string, unknown>
        const sid = payload.sketch_feature_id as string | undefined
        const consumedSketch =
          target?.features.find((f) => f.id === sid && f.feature_type === 'sketch')
          ?? session.features.find((f) => f.id === sid && f.feature_type === 'sketch')
        const plane = ((consumedSketch?.adapter_payload ?? {}) as Record<string, unknown>).plane as
          | { kind?: string; face_role?: string }
          | undefined
        if (plane?.kind !== 'face') {
          return { valid: false, message: 'mock (engine mirror): a sequential extrude consumes a FACE-BOUND sketch — sketch on a face of the body' }
        }
        const alreadyConsumed = target?.features.some(
          (f) => f.feature_type === 'extrude'
            && ((f.adapter_payload ?? {}) as Record<string, unknown>).sketch_feature_id === sid,
        )
        if (alreadyConsumed) {
          return { valid: false, message: 'mock (engine mirror): the sketch is already consumed by another solid feature' }
        }
        const operation = (payload.operation as string | undefined) ?? 'add'
        const direction = payload.direction as string | undefined
        if (operation === 'cut') {
          // HONEST mock boundary: a pocket cavity has no procedural
          // synthesis here — the real engine (288-test-proven) renders it
          // in the desktop lane; the mock refuses rather than fakes.
          return { valid: false, message: 'mock: a CUT pocket has no honest procedural synthesis — run as the desktop app (real engine lane)' }
        }
        if (direction !== 'normal+') {
          return { valid: false, message: 'mock (engine mirror): an ADD extrude sweeps AWAY from the body (normal+)' }
        }
        const baseFeat = target?.features.find(
          (f) => f.feature_type === 'extrude' || f.feature_type === 'revolve',
        )
        if ((plane.face_role ?? '') !== `${baseFeat?.id}:face:cap_top`) {
          // Codex14 B3: EXACT equality with the BASE's top-cap role — a
          // boss-on-boss support (a prior boss's own cap) refuses with the
          // named real-lane boundary instead of a silently misplaced prism.
          return { valid: false, message: 'mock: dev-lane bosses build on the BASE top cap only — boss-on-boss (and cap_base) surfaces run as the desktop app (real engine lane)' }
        }
      }
      return { valid: true }
    },
    async commit(sessionId: string, objectRef: string): Promise<CommitResult> {
      const session = open.get(sessionId)
      if (!session) throw new Error('mock: no open session')
      const { ops } = session
      // S3: dev-lane ADJUST parity (R6) — a parameter edit mutates the
      // committed mirror (the folded display + frames then REGENERATE
      // from the updated value, so a depth edit visibly moves the cap
      // and every face-bound sketch riding it).
      for (const op of ops) {
        if (op.kind !== 'mechanical.adjust_feature_parameter') continue
        const part = parts.get((op.params.part_number as string) ?? objectRef)
        const feat = part?.features.find((f) => f.id === op.params.feature_id)
        const prm = ((feat?.parameters as Array<{ name: string; value: unknown }> | undefined) ?? [])
          .find((pr) => pr.name === op.params.parameter_name)
        if (!prm) throw new Error('mock: unknown feature/parameter for adjust_feature_parameter')
        prm.value = op.params.new_value
      }
      const badge = `${objectRef} — dev mock (procedural, not a real Part)`
      const contour = contourFromOps(ops)
      // A session WITHOUT a base creation op produces NO solid (S2 stepwise:
      // a sketch-only commit shows as emptiness + the wire overlay — exactly
      // what the real engine's display returns for an unconsumed sketch).
      const hasBase = ops.some(
        (o) => o.kind === 'mechanical.add_extrude_feature' || o.kind === 'mechanical.add_revolve_feature',
      )
      // P (arc 20260717-2): a SEQUENTIAL extrude commit (the target already
      // has a base) renders the WHOLE folded composite — never the boss alone.
      const targetPart = parts.get(session.partNumber ?? objectRef)
      const targetHasBase = targetPart?.features.some(
        (f) => f.feature_type === 'extrude' || f.feature_type === 'revolve',
      ) ?? false
      const sessionAddsExtrude = ops.some((o) => o.kind === 'mechanical.add_extrude_feature')
      if (targetHasBase && sessionAddsExtrude) {
        // register FIRST so the folded composite sees the new boss
        const number0 = session.partNumber ?? objectRef
        const entry0 = parts.get(number0) ?? { name: session.partName ?? number0, features: [] }
        entry0.features.push(...session.features)
        parts.set(number0, entry0)
        const composed = foldedBaseDisplay(number0, badge)
        if (!composed) throw new Error('mock: sequential composite unavailable')
        const framed0 = withV2Construction(
          withSketchFrames(composed, foldedSketchFrames(number0, [])),
          foldedV2Construction(number0, []),
        )
        open.delete(sessionId)
        return { objectRef, display: framed0 }
      }
      // Entry A (extrude a COMMITTED sketch): the session has no sketch op —
      // resolve the consumed sketch from the mirror so the mock shows the
      // DRAWN geometry, never a canned box for a real reference.
      const revolve = hasBase ? revolveFromOps(ops, session.partNumber ?? objectRef) : null
      const circleSolid = !revolve && hasBase ? circleFromOps(ops) : null
      const mirrored = !contour && !revolve && !circleSolid && hasBase ? mirroredContour(ops, session.partNumber ?? objectRef) : null
      const solid = (contour && !contour.construction ? contour : null) ?? (circleSolid && !circleSolid.construction ? circleSolid : null) ?? mirrored
      const display =
        isCreateOnly(ops) || !hasBase
          ? (foldedBaseDisplay(session.partNumber ?? objectRef, badge) ??
             emptyMockSource(objectRef, `${objectRef} — dev mock (not Truth)`))
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
      const framed = withV2Construction(
        withSketchFrames(
          display,
          foldedSketchFrames(session.partNumber ?? objectRef, session.features),
        ),
        foldedV2Construction(session.partNumber ?? objectRef, session.features),
      )
      // Register the commit in the mock's Truth mirror (feeds inspectRaw).
      const number = session.partNumber ?? objectRef
      const entry = parts.get(number) ?? { name: session.partName ?? number, features: [] }
      if (session.partName) entry.name = session.partName
      entry.features.push(...session.features)
      parts.set(number, entry)
      open.delete(sessionId)
      return { objectRef, display: framed }
    },
    async rollback(sessionId: string): Promise<void> {
      open.delete(sessionId)
    },
    async previewSource() {
      return loadExtrudeBoxSource('extrude preview — dev mock (transient)')
    },
  }
}
