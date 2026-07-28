/**
 * The sketch click router (SK-C1.0 S1; relocated from the retired chrome in
 * pass sketch-ribbon-1 increment 2 — pure routing, not chrome). The
 * Workbench feeds it plane-local (u, v) mm from the viewport's ray-plane
 * intersection — snap, the 3-point-arc via flow, ring closing, and dedupe
 * behave exactly as before.
 *
 * Codex5 B2: the LIVE generation is checked SYNCHRONOUSLY at the placement
 * boundary — a late pointer event after a Part-generation change invalidates
 * and places NOTHING, independent of any React effect having run.
 */
import type { AuthoringSessionStore } from '../authoring/authoringSession'
import { dist, type Pt } from './contour'
import { bulgeFromThreePoints } from './arcGeometry'

const SNAP_MM = 5 // grid snap for placed points
const CLOSE_MM = 6 // click within this of the start point closes the ring

const snap = (v: number) => Math.round(v / SNAP_MM) * SNAP_MM

export function routeSketchPlacement(
  store: AuthoringSessionStore,
  uv: { u: number; v: number },
  liveGeneration: number,
): void {
  const st = store.getSnapshot()
  if (st.mode !== 'sketch' || st.phase === 'busy') return
  if (st.generation !== liveGeneration) {
    store.invalidateForGeneration()
    return
  }
  const m: Pt = { x: uv.u, y: uv.v }
  const p: Pt = { x: snap(m.x), y: snap(m.y) }
  const tool = st.tool
  if (tool.kind === 'rectangle') {
    if (tool.rect !== null) return
    store.placeRectCorner(p)
    return
  }
  if (tool.kind === 'circle') {
    store.placeCirclePoint(p)
    return
  }
  if (tool.closed) return
  if (tool.awaitingVia && tool.points.length >= 2) {
    // the 3-point-arc VIA click — the last segment curves through it
    // (UNSNAPPED: the via is geometric, not a grid vertex)
    const a = tool.points[tool.points.length - 2]
    const b = tool.points[tool.points.length - 1]
    const bulge = bulgeFromThreePoints(a, m, b)
    if (bulge !== null) store.setLastBulge(bulge)
    else store.setAwaitingVia(false) // degenerate/semicircle/major — stays a line
    return
  }
  if (tool.points.length >= 3 && dist(m, tool.points[0]) <= CLOSE_MM) {
    store.closeRing()
  } else {
    const last = tool.points[tool.points.length - 1]
    if (last && dist(p, last) === 0) return
    store.addPoint(p)
  }
}
