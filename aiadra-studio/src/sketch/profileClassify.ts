/**
 * THE whole-list sketch classifier — the TS MIRROR of the engine's
 * `profile_classify.classify_sketch` (SK-C0 B3; Codex3 B2; Codex5 B2). Same
 * rejection matrix — including the atomic-construction rule (a nested contour
 * segment may NOT carry its own `construction` key) — locked by shared
 * fixtures, so Studio eligibility and the mock's honesty derive from ONE
 * interpretation.
 *
 * SCOPE (Codex5 N2): this result is an ELIGIBILITY PROJECTION of the engine's
 * discriminated verdict, not a same-shape clone — it deliberately omits the
 * engine's `topology_contributing` field (no Studio consumer needs it; the
 * 3D-signature question belongs to the engine alone). A consumer that ever
 * needs it must read the engine, not grow this mirror silently.
 */

export type ClassifiedPrimitive = {
  type?: unknown
  construction?: unknown
  segments?: unknown
}

export type SketchClassification =
  | { outerKind: 'rectangle' | 'contour' | 'circle'; outerIndex: number; holeIndex: number | null; constructionIndices: number[] }
  | { outerKind: 'none'; outerIndex: null; holeIndex: null; constructionIndices: number[] }

/** Mirrors the engine's loud rejections as a string verdict (Studio never
 *  throws for UX flows — the engine remains the committing authority). */
export type ClassifyResult =
  | { ok: true; classification: SketchClassification }
  | { ok: false; reason: string }

export function classifySketch(primitives: ClassifiedPrimitive[]): ClassifyResult {
  const construction: number[] = []
  const rects: number[] = []
  const contours: number[] = []
  const circles: number[] = []
  for (let i = 0; i < (primitives?.length ?? 0); i++) {
    const prim = primitives[i]
    const c = prim.construction
    if (c !== undefined && typeof c !== 'boolean') {
      return { ok: false, reason: `primitive[${i}] construction must be a boolean` }
    }
    // Codex5 B2 — the engine's `_construction_flag` atomic rule, mirrored
    // exactly: construction is TOP-LEVEL for a contour; a nested segment
    // carrying its own key is rejected (whatever its value), even when the
    // contour itself is construction.
    if (prim.type === 'contour') {
      const segs = Array.isArray(prim.segments) ? prim.segments : []
      for (let k = 0; k < segs.length; k++) {
        const seg = segs[k]
        if (seg !== null && typeof seg === 'object' && 'construction' in (seg as Record<string, unknown>)) {
          return {
            ok: false,
            reason: `primitive[${i}] contour segment[${k}] carries its own construction key — construction is top-level and atomic for a contour`,
          }
        }
      }
    }
    if (c === true) {
      construction.push(i)
      continue
    }
    switch (prim.type) {
      case 'rectangle': rects.push(i); break
      case 'contour': contours.push(i); break
      case 'circle': circles.push(i); break
      case 'line':
        return { ok: false, reason: `primitive[${i}] is a non-construction standalone line (construction-only in v1)` }
      default:
        return { ok: false, reason: `primitive[${i}] unknown type ${JSON.stringify(prim.type)}` }
    }
  }
  const outers = rects.length + contours.length
  if (outers === 0 && circles.length === 0) {
    return { ok: true, classification: { outerKind: 'none', outerIndex: null, holeIndex: null, constructionIndices: construction } }
  }
  if (outers > 1) {
    return { ok: false, reason: `a sketch needs exactly one outer profile; got ${rects.length} rectangle(s) + ${contours.length} contour(s)` }
  }
  if (contours.length === 1) {
    if (circles.length) return { ok: false, reason: 'v1 does not support a circle with a contour outer profile' }
    return { ok: true, classification: { outerKind: 'contour', outerIndex: contours[0], holeIndex: null, constructionIndices: construction } }
  }
  if (rects.length === 1) {
    if (circles.length > 1) return { ok: false, reason: `at most one circle hole is supported; got ${circles.length}` }
    return {
      ok: true,
      classification: {
        outerKind: 'rectangle', outerIndex: rects[0],
        holeIndex: circles.length ? circles[0] : null, constructionIndices: construction,
      },
    }
  }
  if (circles.length > 1) {
    return { ok: false, reason: `${circles.length} circles without a rectangle — exactly one circle may stand as the outer profile` }
  }
  return { ok: true, classification: { outerKind: 'circle', outerIndex: circles[0], holeIndex: null, constructionIndices: construction } }
}
