/**
 * SK-C0 acceptance evidence (Codex3 B4): typed decode identity, the classifier
 * mirror matrix, dashed construction overlays, mock truthfulness, and the
 * three-point-via authoring-truth invariant (B1).
 */
import { describe, expect, it } from 'vitest'
import * as THREE from 'three'
import { decodeInspectedPart, unconsumedSketches, type InspectedSketch } from './inspectDecode'
import { classifySketch } from '../sketch/profileClassify'
import { arcGeometry, bulgeFromThreePoints, pointOnArcSpan } from '../sketch/arcGeometry'
import { createSketchWireOverlay } from '../sketch/sketchWireOverlay'
import { createMockAuthoringBackend } from './backendMock'
import { opRef, type FeatureOp, type OpProductRef } from './backend'

const B90 = Math.tan(Math.PI / 8)

function rawPart(prims: Array<Record<string, unknown>>): unknown {
  return {
    sidecar: {
      object: { type: 'Part', number: 'PRT-1', name: 'p', uuid: 'u1' },
      feature: [{
        id: 'feat_0001', feature_type: 'sketch', engine: 'mechanical',
        adapter_schema_version: '0.1.9', adapter_payload: { primitives: prims },
      }],
    },
  }
}

function sketchOf(view: unknown): InspectedSketch {
  const part = decodeInspectedPart(view)
  const sk = part.features.find((f) => f.kind === 'sketch')
  if (!sk || sk.kind !== 'sketch') throw new Error('no sketch decoded')
  return sk
}

describe('B1 — the via click is authoring truth', () => {
  it('REFUSES the Codex3 counterexample (a major route) instead of authoring a different arc', () => {
    expect(bulgeFromThreePoints({ x: 0, y: 0 }, { x: 10, y: 20 }, { x: 20, y: 0 })).toBeNull()
    // the mirrored major click on the other side refuses too
    expect(bulgeFromThreePoints({ x: 0, y: 0 }, { x: 10, y: -20 }, { x: 20, y: 0 })).toBeNull()
  })

  it('every ACCEPTED via provably lies on the authored arc (circle + span)', () => {
    const cases = [
      [{ x: 0, y: 0 }, { x: 10, y: 4 }, { x: 20, y: 0 }],   // shallow, left
      [{ x: 0, y: 0 }, { x: 10, y: -4 }, { x: 20, y: 0 }],  // shallow, right
      [{ x: 0, y: 0 }, { x: 4, y: 5 }, { x: 10, y: 10 }],   // asymmetric via
    ] as const
    for (const [s, v, e] of cases) {
      const b = bulgeFromThreePoints(s, v, e)
      expect(b).not.toBeNull()
      const g = arcGeometry(s.x, s.y, e.x, e.y, b!)
      expect(Math.hypot(v.x - g.center.x, v.y - g.center.y)).toBeCloseTo(g.radius, 9)
      expect(pointOnArcSpan(g, v.x, v.y, 1e-6)).toBe(true)
    }
  })

  it('semicircle boundary (Codex5 B1): the sweep gate — just-minor accepted, EXACT semicircle refused on both sides/orientations, just-major refused', () => {
    // chord (0,0)→(20,0), r≈10: the just-minor fixture stays accepted…
    expect(bulgeFromThreePoints({ x: 0, y: 0 }, { x: 10, y: 9.9 }, { x: 20, y: 0 })).not.toBeNull()
    // …the EXACT semicircle click refuses in ANGLE space (never one ulp
    // inside |b|<1): left bow, right bow, and the reversed orientation
    expect(bulgeFromThreePoints({ x: 0, y: 0 }, { x: 10, y: 10.0 }, { x: 20, y: 0 })).toBeNull()
    expect(bulgeFromThreePoints({ x: 0, y: 0 }, { x: 10, y: -10.0 }, { x: 20, y: 0 })).toBeNull()
    expect(bulgeFromThreePoints({ x: 20, y: 0 }, { x: 10, y: 10.0 }, { x: 0, y: 0 })).toBeNull()
    expect(bulgeFromThreePoints({ x: 20, y: 0 }, { x: 10, y: -10.0 }, { x: 0, y: 0 })).toBeNull()
    // …and the just-major fixture keeps the far side of the boundary explicit
    expect(bulgeFromThreePoints({ x: 0, y: 0 }, { x: 10, y: 10.01 }, { x: 20, y: 0 })).toBeNull()
    expect(bulgeFromThreePoints({ x: 0, y: 0 }, { x: 10, y: 12 }, { x: 20, y: 0 })).toBeNull()
    // collinear via → no arc
    expect(bulgeFromThreePoints({ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 20, y: 0 })).toBeNull()
  })
})

describe('the classifier mirror matrix (shared rows with the engine)', () => {
  const R = { type: 'rectangle' }
  const C = { type: 'circle' }
  const K = { type: 'contour' }
  const cases: Array<[Array<Record<string, unknown>>, string]> = [
    [[R], 'rectangle'],
    [[R, C], 'rectangle'],       // + hole
    [[K], 'contour'],
    [[C], 'circle'],
    [[], 'none'],                // EMPTY is valid sketch-only (the converged row)
    [[{ ...R, construction: true }], 'none'], // all-construction
  ]
  for (const [prims, outer] of cases) {
    it(`${JSON.stringify(prims.map((p) => p.type))} → ${outer}`, () => {
      const v = classifySketch(prims)
      expect(v.ok).toBe(true)
      if (v.ok) expect(v.classification.outerKind).toBe(outer)
    })
  }
  it('rejects: two circles · contour+circle · stray line · two outers · bad flag', () => {
    for (const bad of [[C, C], [K, C], [{ type: 'line' }], [R, R], [{ ...R, construction: 'yes' }]]) {
      expect(classifySketch(bad as Array<Record<string, unknown>>).ok).toBe(false)
    }
  })
  it('rejects nested segment construction exactly like the engine (atomic rule, Codex5 B2)', () => {
    const rows: Array<Array<Record<string, unknown>>> = [
      // whatever the nested value…
      [{ type: 'contour', segments: [{ kind: 'line', construction: true }] }],
      [{ type: 'contour', segments: [{ kind: 'line', construction: false }] }],
      // …and even when the CONTOUR itself is construction
      [{ type: 'contour', construction: true, segments: [{ kind: 'line', construction: true }] }],
    ]
    for (const prims of rows) {
      const v = classifySketch(prims)
      expect(v.ok).toBe(false)
      if (!v.ok) expect(v.reason).toMatch(/top-level and atomic/)
    }
  })
})

describe('typed decode — identity, geometry, construction (B3)', () => {
  it('decodes every kind with ids, exact bulge, and construction flags', () => {
    const sk = sketchOf(rawPart([
      { id: 'skp_0001', type: 'contour', segments: [
        { id: 'skp_0001s01', kind: 'line', x1_mm: 0, y1_mm: 0, x2_mm: 40, y2_mm: 0 },
        { id: 'skp_0001s02', kind: 'arc', x1_mm: 40, y1_mm: 0, x2_mm: 50, y2_mm: 10, bulge: B90 },
        { id: 'skp_0001s03', kind: 'line', x1_mm: 50, y1_mm: 10, x2_mm: 0, y2_mm: 10 },
        { id: 'skp_0001s04', kind: 'line', x1_mm: 0, y1_mm: 10, x2_mm: 0, y2_mm: 0 },
      ] },
      { id: 'skp_0002', type: 'line', x1_mm: -5, y1_mm: -5, x2_mm: 60, y2_mm: 60, construction: true },
    ]))
    const contour = sk.entities[0]
    expect(contour.kind).toBe('contour')
    if (contour.kind === 'contour') {
      expect(contour.id).toBe('skp_0001')
      expect(contour.segments.map((s) => s.id)).toEqual(
        ['skp_0001s01', 'skp_0001s02', 'skp_0001s03', 'skp_0001s04'])
      const arc = contour.segments[1]
      expect(arc.kind).toBe('arc')
      if (arc.kind === 'arc') expect(arc.bulge).toBe(B90)
    }
    const guide = sk.entities[1]
    expect(guide.kind).toBe('line')
    expect(guide.construction).toBe(true)
    // wires: closed contour + open dashed guide; rings exclude the guide
    expect(sk.wires).toHaveLength(2)
    expect(sk.wires[0].closed).toBe(true)
    expect(sk.wires[1]).toMatchObject({ closed: false, construction: true })
    expect(sk.rings).toHaveLength(1)
  })

  it('profiles: simple_circle · sketch_only · rectangle+hole=other', () => {
    expect(sketchOf(rawPart([{ id: 'skp_0001', type: 'circle', cx_mm: 1, cy_mm: 2, radius_mm: 8 }])).profile)
      .toEqual({ kind: 'simple_circle', circle: { cx_mm: 1, cy_mm: 2, radius_mm: 8 } })
    expect(sketchOf(rawPart([{ id: 'skp_0001', type: 'rectangle', x_mm: 0, y_mm: 0, width_mm: 5, height_mm: 5, construction: true }])).profile)
      .toEqual({ kind: 'sketch_only' })
    expect(sketchOf(rawPart([
      { id: 'skp_0001', type: 'rectangle', x_mm: 0, y_mm: 0, width_mm: 20, height_mm: 20 },
      { id: 'skp_0002', type: 'circle', cx_mm: 10, cy_mm: 10, radius_mm: 3 },
    ])).profile).toEqual({ kind: 'other' })
  })

  it('FAILS LOUD on missing primitive/segment ids (never an empty placeholder)', () => {
    expect(() => sketchOf(rawPart([{ type: 'circle', cx_mm: 0, cy_mm: 0, radius_mm: 5 }])))
      .toThrow(/skp_ id/)
    expect(() => sketchOf(rawPart([{ id: 'skp_0001', type: 'contour', segments: [
      { kind: 'line', x1_mm: 0, y1_mm: 0, x2_mm: 1, y2_mm: 0 },
      { kind: 'line', x1_mm: 1, y1_mm: 0, x2_mm: 0, y2_mm: 1 },
      { kind: 'line', x1_mm: 0, y1_mm: 1, x2_mm: 0, y2_mm: 0 },
    ] }]))).toThrow(/segment lacks/)
  })

  it('FAILS LOUD on ids that are not stable engine identities (Codex5 B3): grammar, duplicates, ownership', () => {
    // malformed primitive id — present but not the engine grammar
    expect(() => sketchOf(rawPart([{ id: 'x', type: 'circle', cx_mm: 0, cy_mm: 0, radius_mm: 5 }])))
      .toThrow(/skp_NNNN grammar/)
    // duplicate primitive ids
    expect(() => sketchOf(rawPart([
      { id: 'skp_0001', type: 'circle', cx_mm: 0, cy_mm: 0, radius_mm: 5 },
      { id: 'skp_0001', type: 'circle', cx_mm: 9, cy_mm: 9, radius_mm: 2 },
    ]))).toThrow(/duplicate primitive id/)
    // a segment id not owned by its contour's prefix
    expect(() => sketchOf(rawPart([{ id: 'skp_0001', type: 'contour', segments: [
      { id: 'skp_0002s01', kind: 'line', x1_mm: 0, y1_mm: 0, x2_mm: 1, y2_mm: 0 },
    ] }]))).toThrow(/not owned by skp_0001/)
    // duplicate segment ids within the contour
    expect(() => sketchOf(rawPart([{ id: 'skp_0001', type: 'contour', segments: [
      { id: 'skp_0001s01', kind: 'line', x1_mm: 0, y1_mm: 0, x2_mm: 1, y2_mm: 0 },
      { id: 'skp_0001s01', kind: 'line', x1_mm: 1, y1_mm: 0, x2_mm: 0, y2_mm: 1 },
    ] }]))).toThrow(/duplicate segment id/)
  })

  it('FAILS LOUD on a nested segment construction key (Codex5 B2 — never silently erased)', () => {
    expect(() => sketchOf(rawPart([{ id: 'skp_0001', type: 'contour', segments: [
      { id: 'skp_0001s01', kind: 'line', x1_mm: 0, y1_mm: 0, x2_mm: 1, y2_mm: 0, construction: true },
    ] }]))).toThrow(/top-level and atomic/)
  })
})

describe('the dashed construction overlay (B4)', () => {
  it('construction wires use LineDashedMaterial with computed line distances; profile wires stay solid', () => {
    const overlay = createSketchWireOverlay()
    const sk = sketchOf(rawPart([
      { id: 'skp_0001', type: 'rectangle', x_mm: 0, y_mm: 0, width_mm: 10, height_mm: 5 },
      { id: 'skp_0002', type: 'line', x1_mm: 0, y1_mm: 0, x2_mm: 30, y2_mm: 30, construction: true },
    ]))
    overlay.setSketches([sk])
    const lines = overlay.group.children as THREE.Line[]
    expect(lines).toHaveLength(2)
    const solid = lines.find((l) => l.userData.construction === false)!
    const dashed = lines.find((l) => l.userData.construction === true)!
    expect(solid.material).toBeInstanceOf(THREE.LineBasicMaterial)
    expect(dashed.material).toBeInstanceOf(THREE.LineDashedMaterial)
    // computeLineDistances materializes the lineDistance attribute
    expect(dashed.geometry.getAttribute('lineDistance')).toBeDefined()
    // closed rectangle ring = 4 pts + closer; open guide = 2 pts
    expect(solid.geometry.getAttribute('position').count).toBe(5)
    expect(dashed.geometry.getAttribute('position').count).toBe(2)
    // noncanonical, non-pickable metadata
    expect(dashed.userData.kind).toBe('sketch-wire')
    overlay.dispose()
  })
})

describe('mock truthfulness walks (B2/B3)', () => {
  const sketchOp = (prims: Array<Record<string, unknown>>): FeatureOp => ({
    kind: 'mechanical.add_sketch_feature',
    params: { part_number: 'PRT-9', primitives: prims, plane: { kind: 'principal', orientation: 'xy' } },
  })
  const extrudeOp = (sketchId: string | OpProductRef): FeatureOp => ({
    kind: 'mechanical.add_extrude_feature',
    params: { part_number: 'PRT-9', sketch_feature_id: sketchId, depth_mm: 5, direction: 'normal+' },
  })
  const create: FeatureOp = { kind: 'create_part', params: { number: 'PRT-9', name: 'p' } }

  it('mints engine-shaped primitive + segment ids (decode parity via inspectRaw)', async () => {
    const mock = createMockAuthoringBackend()
    const ops = [create, sketchOp([{ type: 'contour', segments: [
      { kind: 'line', x1_mm: 0, y1_mm: 0, x2_mm: 10, y2_mm: 0 },
      { kind: 'arc', x1_mm: 10, y1_mm: 0, x2_mm: 15, y2_mm: 5, bulge: B90 },
      { kind: 'line', x1_mm: 15, y1_mm: 5, x2_mm: 0, y2_mm: 5 },
      { kind: 'line', x1_mm: 0, y1_mm: 5, x2_mm: 0, y2_mm: 0 },
    ] }])]
    const { sessionId } = await mock.begin(ops)
    await mock.commit(sessionId, 'PRT-9')
    const part = decodeInspectedPart(mock.inspectRaw('PRT-9'))
    const sk = part.features.find((f) => f.kind === 'sketch')!
    if (sk.kind !== 'sketch') throw new Error('no sketch')
    expect(sk.entities[0].id).toBe('skp_0001')
    if (sk.entities[0].kind === 'contour') {
      expect(sk.entities[0].segments[1]).toMatchObject({ id: 'skp_0001s02', kind: 'arc', bulge: B90 })
    }
  })

  it('guides-only stepwise commit shows EMPTINESS (wire-only), and entry-A extrude of it REFUSES', async () => {
    const mock = createMockAuthoringBackend()
    const guides = [create, sketchOp([{ type: 'line', x1_mm: 0, y1_mm: 0, x2_mm: 9, y2_mm: 9, construction: true }])]
    const s1 = await mock.begin(guides)
    expect((await mock.simulate(s1.sessionId)).valid).toBe(true) // sketch-only IS valid
    await mock.commit(s1.sessionId, 'PRT-9')
    // entry A: extrude the committed guides-only sketch → simulate refuses
    const s2 = await mock.begin([extrudeOp('feat_0001')])
    const verdict = await mock.simulate(s2.sessionId)
    expect(verdict.valid).toBe(false)
    expect(verdict.message).toMatch(/construction-only/)
    // and commit NEVER falls back to a canned box
    await expect(mock.commit(s2.sessionId, 'PRT-9')).rejects.toThrow(/honest procedural synthesis/)
  })

  it('circle→cylinder extrusion synthesizes procedurally through the REAL structured $fromOp handshake (Codex5 N1)', async () => {
    const mock = createMockAuthoringBackend()
    const s1 = await mock.begin([create, sketchOp([{ type: 'circle', cx_mm: 0, cy_mm: 0, radius_mm: 6 }]), extrudeOp(opRef(1))])
    expect((await mock.simulate(s1.sessionId)).valid).toBe(true)
    const r1 = await mock.commit(s1.sessionId, 'PRT-9')
    expect(JSON.stringify(r1.display)).toMatch(/procedural|contour/i)
    // the alias RESOLVED: the committed extrude depends on the minted sketch id
    const raw = mock.inspectRaw('PRT-9') as { sidecar: { feature: Array<Record<string, unknown>> } }
    const sk = raw.sidecar.feature.find((f) => f.feature_type === 'sketch')!
    const ext = raw.sidecar.feature.find((f) => f.feature_type === 'extrude')!
    expect(sk.id).toMatch(/^feat_/)
    expect((ext.adapter_payload as Record<string, unknown>).sketch_feature_id).toBe(sk.id)
    expect(ext.depends_on_feature_ids).toEqual([sk.id])
  })

  it('entry-A extrude of a committed EMPTY sketch refuses via the ONE classifier (Codex5 B2)', async () => {
    const mock = createMockAuthoringBackend()
    const s1 = await mock.begin([create, sketchOp([])])
    expect((await mock.simulate(s1.sessionId)).valid).toBe(true) // empty IS a valid sketch-only commit
    await mock.commit(s1.sessionId, 'PRT-9')
    const s2 = await mock.begin([extrudeOp('feat_0001')])
    const verdict = await mock.simulate(s2.sessionId)
    expect(verdict.valid).toBe(false)
    expect(verdict.message).toMatch(/no extrudable profile/)
  })
})

describe('the Extrude picker refusal for guides-only sketches (B2)', () => {
  it('unconsumedSketches keeps the sketch visible; profile says sketch_only', () => {
    const part = decodeInspectedPart(rawPart([
      { id: 'skp_0001', type: 'circle', cx_mm: 0, cy_mm: 0, radius_mm: 5, construction: true },
    ]))
    const sketches = unconsumedSketches(part)
    expect(sketches).toHaveLength(1) // visible for its dashed overlay
    expect(sketches[0].profile.kind).toBe('sketch_only') // the picker derives the refusal
  })
})
