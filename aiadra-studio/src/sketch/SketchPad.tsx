/**
 * The 2D sketch pad (arc 20260711-11 slice S/X; S2 stepwise; SK-C0 palette) —
 * draw a closed contour (lines + BULGE ARCS), a rectangle, or a circle on the
 * picked plane, optionally as a CONSTRUCTION guide (D-C3). S2 (D-S2/D-S4): the
 * pad is a view over the ONE discriminated `authoringSession` store, and the
 * sketch is FIRST-CLASS — OK commits the sketch ALONE, except in the CHAINED
 * entry (launched from Extrude's "New sketch…"), where OK hands the drawing
 * back and the pair commits as ONE draft via the $fromOp handshake.
 *
 * Validity is a client-side mirror of the engine's Class-1 gate — CURVE-AWARE
 * since SK-C0 (`contourProblem(points, bulges)`) — so the hint matches what
 * commit will accept. Arc UX: toggle "Arc", place the segment's endpoint, then
 * one more click places the VIA point (3-point arc → bulge, minor arcs only).
 */
import { useEffect, useMemo, useRef } from 'react'
import type { DisplaySource } from '../display/displaySource'
import {
  buildCircleSketchOps,
  buildCreateWithCircleOps,
  buildCreateWithRectangleOps,
  buildCreateWithSketchOps,
  buildRectangleSketchOps,
  buildSketchOnlyOps,
  PLANE_LABELS,
  suggestPartNumber,
  type AuthoringBackend,
} from '../authoring/backend'
import { useAuthoringSession, type AuthoringSessionStore } from '../authoring/authoringSession'
import { createSessionLifecycle } from '../authoring/sessionLifecycle'
import { guardTerminalTarget, type PartContextStore } from '../authoring/partContext'
import { contourProblem, dist, pointsToSegments, type Pt } from './contour'
import { bulgeFromThreePoints, tessellateSegments } from './arcGeometry'

const HALF_W = 130 // mm half-width of the pad view
const HALF_H = 85 // mm half-height
const GRID_MM = 10
const SNAP_MM = 5 // grid snap for placed points
const CLOSE_MM = 6 // click within this of the start point closes the ring

const snap = (v: number) => Math.round(v / SNAP_MM) * SNAP_MM

function clientToMm(svg: SVGSVGElement, clientX: number, clientY: number): Pt {
  const pt = svg.createSVGPoint()
  pt.x = clientX
  pt.y = clientY
  const loc = pt.matrixTransform(svg.getScreenCTM()!.inverse())
  return { x: loc.x, y: -loc.y } // SVG y is down; the sketch plane is y-up
}

const plot = (p: Pt) => `${p.x},${-p.y}`

/** The drawn ring as a render polyline (arcs tessellated for preview only). */
function ringPolyline(points: Pt[], bulges: number[], closed: boolean): string {
  if (points.length === 0) return ''
  if (!closed) {
    // open: tessellate only the PLACED segments (points.length-1 of them)
    const segs = points.slice(0, -1).map((p, i) => {
      const q = points[i + 1]
      const b = bulges[i] ?? 0
      return b !== 0
        ? ({ kind: 'arc', x1_mm: p.x, y1_mm: p.y, x2_mm: q.x, y2_mm: q.y, bulge: b } as const)
        : ({ kind: 'line', x1_mm: p.x, y1_mm: p.y, x2_mm: q.x, y2_mm: q.y } as const)
    })
    const pts = segs.length ? tessellateSegments([...segs]) : []
    pts.push(points[points.length - 1])
    return pts.map(plot).join(' ')
  }
  const pts = tessellateSegments(pointsToSegments(points, bulges))
  pts.push(points[0])
  return pts.map(plot).join(' ')
}

export function SketchPad({
  store,
  backend,
  context,
  onClose,
  onCommitted,
}: {
  store: AuthoringSessionStore
  backend: AuthoringBackend
  /** The generation-owned Part context — the terminal commit REVALIDATES the
   *  captured target against it (Codex3 B2, fail closed). */
  context: PartContextStore
  onClose: () => void
  /** Fired after every successful STEPWISE commit; carries the commit's
   *  display source so the Workbench installs it INSIDE the same Part
   *  transition that re-reads Truth (Codex3 B2 — no direct installs here). */
  onCommitted?: (info: {
    number: string
    name: string
    createdFresh: boolean
    display: DisplaySource
  }) => void
}) {
  const st = useAuthoringSession(store)
  const s = st.mode === 'sketch' ? st : null
  const svgRef = useRef<SVGSVGElement>(null)

  const lifecycle = useMemo(() => createSessionLifecycle(backend), [backend])
  const busy = s?.phase === 'busy'
  const ct = s?.tool.kind === 'contour' ? s.tool : null
  const rt = s?.tool.kind === 'rectangle' ? s.tool : null
  const ci = s?.tool.kind === 'circle' ? s.tool : null
  const problem = ct ? contourProblem(ct.points, ct.bulges) : null
  const done = ct ? ct.closed : rt ? rt.rect !== null : (ci?.circle ?? null) !== null
  const nearStart = ct?.cursor && ct.points.length >= 3 && dist(ct.cursor, ct.points[0]) <= CLOSE_MM

  useEffect(() => {
    if (!s) return
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA')) return
      if (e.key === 'Escape') { cancel(); e.preventDefault() }
      else if (e.key === 'Enter' && s.phase === 'drawing' && s.tool.kind === 'contour' && !problem) { store.closeRing(); e.preventDefault() }
      else if (e.key === 'Backspace' && s.phase === 'drawing' && s.tool.kind === 'contour') { store.undoPoint(); e.preventDefault() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s?.phase, !!s, problem])

  if (!s) return null

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (done || busy || !svgRef.current) return
    store.setCursor(clientToMm(svgRef.current, e.clientX, e.clientY))
  }
  const onClick = (e: React.PointerEvent<SVGSVGElement>) => {
    if (done || busy || !svgRef.current) return
    const m = clientToMm(svgRef.current, e.clientX, e.clientY)
    const p = { x: snap(m.x), y: snap(m.y) }
    if (rt) {
      store.placeRectCorner(p)
      return
    }
    if (ci) {
      store.placeCirclePoint(p)
      return
    }
    if (!ct) return
    if (ct.awaitingVia && ct.points.length >= 2) {
      // SK-C0: the 3-point-arc VIA click — the last segment curves through it.
      const a = ct.points[ct.points.length - 2]
      const b = ct.points[ct.points.length - 1]
      const bulge = bulgeFromThreePoints(a, m, b)
      if (bulge !== null) store.setLastBulge(bulge)
      else store.setAwaitingVia(false) // degenerate/major — the segment stays a line
      return
    }
    if (ct.points.length >= 3 && dist(m, ct.points[0]) <= CLOSE_MM) {
      store.closeRing()
    } else {
      const last = ct.points[ct.points.length - 1]
      if (last && dist(p, last) === 0) return
      store.addPoint(p)
    }
  }

  const cancel = () => {
    if (!lifecycle.cancel()) return
    store.cancel()
    onClose()
  }

  /** OK — the stepwise sketch commit (or the chained hand-back). */
  const ok = async () => {
    if (busy || problem || !done) return
    if (s.chainToExtrude) {
      store.finishChainedSketch()
      return
    }
    const target = s.targetPart
    if (target) {
      const refusal = s.targetAuth
        ? guardTerminalTarget(s.targetAuth, context.getSnapshot())
        : 'the session has no captured target authority — cancel and reopen the operation'
      if (refusal) {
        store.setSketchPhase('error', refusal)
        return
      }
    }
    const num = target?.number ?? s.partNumber ?? suggestPartNumber()
    const name = target?.name ?? s.partName ?? `Sketch ${num}`
    const construction = s.construction
    const rect = rt?.rect ?? null
    const circle = ci?.circle ?? null
    const ops = circle
      ? target
        ? buildCircleSketchOps(target.number, circle, s.plane, construction)
        : buildCreateWithCircleOps(num, name, circle, s.plane, construction)
      : rect
        ? target
          ? buildRectangleSketchOps(target.number, rect, s.plane, construction)
          : buildCreateWithRectangleOps(num, name, rect, s.plane, construction)
        : target
          ? buildSketchOnlyOps(target.number, ct!.points, s.plane, { bulges: ct!.bulges, construction })
          : buildCreateWithSketchOps(num, name, ct!.points, s.plane, { bulges: ct!.bulges, construction })
    await lifecycle.run(ops, num, {
      onBusy: () => store.setSketchPhase('busy', 'committing sketch…'),
      onError: (m) => store.setSketchPhase('error', m),
      onSuccess: (res) => {
        onCommitted?.({ number: num, name, createdFresh: !target, display: res.display })
        store.cancel()
      },
    })
  }

  const rubber = ct ? ct.cursor && ct.points.length > 0 && !ct.closed && !ct.awaitingVia : false
  // the live arc preview while placing the via point
  const viaPreview =
    ct?.awaitingVia && ct.cursor && ct.points.length >= 2
      ? (() => {
          const a = ct.points[ct.points.length - 2]
          const b = ct.points[ct.points.length - 1]
          const bulge = bulgeFromThreePoints(a, ct.cursor!, b)
          if (bulge === null) return null
          const pts = tessellateSegments([
            { kind: 'arc', x1_mm: a.x, y1_mm: a.y, x2_mm: b.x, y2_mm: b.y, bulge },
          ])
          pts.push(b)
          return pts.map(plot).join(' ')
        })()
      : null
  const hint =
    problem ??
    (done
      ? s.chainToExtrude
        ? 'Ready — OK returns to Extrude.'
        : 'Ready — OK commits the sketch.'
      : ct?.awaitingVia
        ? 'Click a point the arc should pass through (the via).'
        : rt
          ? rt.anchor
            ? 'Click the opposite corner.'
            : 'Click the first corner of the rectangle.'
          : ci
            ? ci.center
              ? 'Click a rim point to set the radius.'
              : 'Click the circle center.'
            : 'Click the first point to close the ring.')
  const previewRect = rt
    ? rt.rect ?? (rt.anchor && rt.cursor
        ? { x_mm: Math.min(rt.anchor.x, rt.cursor.x), y_mm: Math.min(rt.anchor.y, rt.cursor.y),
            width_mm: Math.abs(rt.cursor.x - rt.anchor.x), height_mm: Math.abs(rt.cursor.y - rt.anchor.y) }
        : null)
    : null
  const previewCircle = ci
    ? ci.circle ?? (ci.center && ci.cursor
        ? { cx_mm: ci.center.x, cy_mm: ci.center.y, radius_mm: dist(ci.center, ci.cursor) }
        : null)
    : null
  const strokeClass = s.construction ? ' construction' : ''

  return (
    <div className="sketchpad">
      <div className="sp-head">
        <span className="sp-title">
          Sketch — {PLANE_LABELS[s.plane]} ({s.plane})
          {s.targetPart && <span className="muted"> · {s.targetPart.number}</span>}
          {s.chainToExtrude && <span className="muted"> · for Extrude</span>}
        </span>
        {!s.chainToExtrude && (
          <span className="sp-tools">
            <button type="button" className={`btn small${ct ? ' primary' : ''}`} disabled={busy}
              title="Draw a closed contour (click points; close the ring)"
              onClick={() => store.switchTool('contour')}>Contour</button>
            <button type="button" className={`btn small${rt ? ' primary' : ''}`} disabled={busy}
              title="Draw a rectangle (two clicks) — the native profile for Revolve/Hole"
              onClick={() => store.switchTool('rectangle')}>Rectangle</button>
            <button type="button" className={`btn small${ci ? ' primary' : ''}`} disabled={busy}
              title="Draw a circle (center + rim) — a hole beside a rectangle, or a cylinder profile alone"
              onClick={() => store.switchTool('circle')}>Circle</button>
            {ct && (
              <button type="button" className={`btn small${ct.awaitingVia ? ' primary' : ''}`}
                disabled={busy || ct.closed || ct.points.length < 2 || (ct.bulges[ct.bulges.length - 1] ?? 0) !== 0}
                title="Curve the LAST segment: click a via point the arc passes through (minor arcs)"
                onClick={() => store.setAwaitingVia(!ct.awaitingVia)}>Arc</button>
            )}
            <button type="button" className={`btn small${s.construction ? ' primary' : ''}`} disabled={busy}
              title="Construction guide (SK-C0): visible dashed, never part of the profile or the solid"
              onClick={() => store.toggleConstruction()}>Constr.</button>
          </span>
        )}
        <span className={`fd-lane ${backend.isReal ? 'real' : 'mock'}`}>{backend.isReal ? 'real engine' : 'dev mock'}</span>
        <button type="button" className="fd-x" title="Cancel (Esc)" onClick={cancel} disabled={busy}>✕</button>
      </div>

      <svg
        ref={svgRef}
        className="sp-svg"
        viewBox={`${-HALF_W} ${-HALF_H} ${2 * HALF_W} ${2 * HALF_H}`}
        onPointerMove={onMove}
        onPointerDown={onClick}
        onPointerLeave={() => store.setCursor(null)}
      >
        <defs>
          <pattern id="sp-grid" width={GRID_MM} height={GRID_MM} patternUnits="userSpaceOnUse">
            <path d={`M${GRID_MM} 0 H0 V${GRID_MM}`} fill="none" className="sp-gridline" />
          </pattern>
        </defs>
        <rect x={-HALF_W} y={-HALF_H} width={2 * HALF_W} height={2 * HALF_H} fill="url(#sp-grid)" />
        <line x1={-HALF_W} y1={0} x2={HALF_W} y2={0} className="sp-axis" />
        <line x1={0} y1={-HALF_H} x2={0} y2={HALF_H} className="sp-axis" />

        {/* contour: the ring (closed → filled; open → polyline), arcs tessellated */}
        {ct && ct.points.length > 0 && (
          <polyline
            className={`sp-ring ${ct.closed ? 'closed' : ''}${strokeClass}`}
            points={ringPolyline(ct.points, ct.bulges, ct.closed)}
          />
        )}
        {ct && viaPreview && <polyline className={`sp-rubber arc${strokeClass}`} points={viaPreview} fill="none" />}
        {ct && rubber && <line className="sp-rubber" x1={ct.points[ct.points.length - 1].x} y1={-ct.points[ct.points.length - 1].y} x2={ct.cursor!.x} y2={-ct.cursor!.y} />}
        {ct &&
          ct.points.map((p, i) => (
            <circle key={i} className={`sp-vert ${i === 0 && nearStart ? 'snap' : ''}`} cx={p.x} cy={-p.y} r={i === 0 && nearStart ? 2.4 : 1.6} />
          ))}

        {/* rectangle: the committed rect (filled) or the anchor→cursor rubber */}
        {previewRect && (
          <rect
            className={`sp-ring ${rt?.rect ? 'closed' : ''}${strokeClass}`}
            x={previewRect.x_mm}
            y={-(previewRect.y_mm + previewRect.height_mm)}
            width={previewRect.width_mm}
            height={previewRect.height_mm}
          />
        )}
        {rt?.anchor && <circle className="sp-vert" cx={rt.anchor.x} cy={-rt.anchor.y} r={1.8} />}

        {/* circle: committed (filled) or center→cursor rubber (SK-C0 D-C2) */}
        {previewCircle && previewCircle.radius_mm > 0 && (
          <circle
            className={`sp-ring ${ci?.circle ? 'closed' : ''}${strokeClass}`}
            cx={previewCircle.cx_mm}
            cy={-previewCircle.cy_mm}
            r={previewCircle.radius_mm}
          />
        )}
        {ci?.center && <circle className="sp-vert" cx={ci.center.x} cy={-ci.center.y} r={1.8} />}
      </svg>

      <div className="sp-foot">
        <span className={`sp-hint ${problem && ct && ct.points.length >= 3 ? 'warn' : ''}`}>{hint}</span>
        <span className="grow" />
        {s.phase === 'error' && <span className="sp-hint warn">{s.message}</span>}
        {!done ? (
          ct ? (
            <>
              <button type="button" className="btn small" onClick={() => store.undoPoint()} disabled={busy || ct.points.length === 0}>Undo</button>
              <button type="button" className="btn small" onClick={() => store.closeRing()} disabled={busy || !!problem}>Close ring</button>
            </>
          ) : (
            <button type="button" className="btn small" onClick={() => store.reopen()} disabled={busy || (rt ? !rt.anchor : !ci?.center)}>Restart</button>
          )
        ) : (
          <>
            <button type="button" className="btn small" onClick={() => store.reopen()} disabled={busy}>Reopen</button>
            <button type="button" className="btn primary" onClick={ok} disabled={busy || !!problem || !done}>{busy ? '…' : 'OK'}</button>
          </>
        )}
        <button type="button" className="btn small" onClick={cancel} disabled={busy}>Cancel</button>
      </div>
    </div>
  )
}
