/**
 * The 2D sketch pad (arc 20260711-11 slice S/X) — draw a closed contour, then
 * extrude it into a real solid. v1 sketches head-on on the XY datum plane, as
 * Creo orients to the sketch plane; drawing on arbitrary 3D planes/surfaces +
 * references is the incremental follow-up.
 *
 * The pad is the VIEW over the pure `sketchStore` (source of truth); it owns the
 * async extrude side effect (buildContourOps → the AuthoringBackend → the
 * viewport display swap). Validity is a client-side mirror of the engine's
 * Class-1 gate (`contourProblem`) so the hint matches what commit will accept.
 */
import { useEffect, useMemo, useRef, useState, type MutableRefObject } from 'react'
import type { ViewportApi } from '../Viewport'
import { buildContourOps, suggestPartNumber, type AuthoringBackend } from '../authoring/backend'
import { createSessionLifecycle } from '../authoring/sessionLifecycle'
import { contourProblem, dist, type Pt } from './contour'
import { useSketch, type SketchStore } from './sketchStore'

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

export function SketchPad({
  store,
  backend,
  viewportApi,
  onClose,
}: {
  store: SketchStore
  backend: AuthoringBackend
  viewportApi: MutableRefObject<ViewportApi | null>
  onClose: () => void
}) {
  const s = useSketch(store)
  const svgRef = useRef<SVGSVGElement>(null)
  const [depthMm, setDepthMm] = useState(10)

  // Codex6 B1: the SAME shared begin→simulate→commit lifecycle as the
  // FeatureDashboard — retained session, retry cleanup, uninterruptible commit.
  const lifecycle = useMemo(() => createSessionLifecycle(backend), [backend])
  const busy = s.phase === 'busy'
  const problem = contourProblem(s.points)
  const nearStart = s.cursor && s.points.length >= 3 && dist(s.cursor, s.points[0]) <= CLOSE_MM

  // Esc cancels; Enter closes a valid ring; Backspace undoes — guarded off inputs.
  useEffect(() => {
    if (!s.active) return
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA')) return
      if (e.key === 'Escape') { cancel(); e.preventDefault() }
      else if (e.key === 'Enter' && s.phase === 'drawing' && !problem) { store.closeRing(); e.preventDefault() }
      else if (e.key === 'Backspace' && s.phase === 'drawing') { store.undoPoint(); e.preventDefault() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s.active, s.phase, problem])

  if (!s.active) return null

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (s.closed || busy || !svgRef.current) return
    store.setCursor(clientToMm(svgRef.current, e.clientX, e.clientY))
  }
  const onClick = (e: React.PointerEvent<SVGSVGElement>) => {
    if (s.closed || busy || !svgRef.current) return
    const m = clientToMm(svgRef.current, e.clientX, e.clientY)
    if (s.points.length >= 3 && dist(m, s.points[0]) <= CLOSE_MM) {
      store.closeRing()
    } else {
      const p = { x: snap(m.x), y: snap(m.y) }
      // Ignore a click that lands on the last placed point (grid snap makes a
      // double-click an exact duplicate → a zero-length segment, Codex6 B2).
      const last = s.points[s.points.length - 1]
      if (last && dist(p, last) === 0) return
      store.addPoint(p)
    }
  }

  const cancel = () => {
    // Refuses while the terminal commit is in flight (Codex6 B1 — this guards
    // the Escape path too, not just the disabled buttons), and rolls back a
    // retained failed-commit session before the pad closes.
    if (!lifecycle.cancel()) return
    store.cancel()
    onClose()
  }

  const extrude = async () => {
    if (busy || problem) return
    // The session's meta (Codex2 B1 — scoped, never ambient). The number is
    // PROVISIONAL either way: core validates + reserves it at commit (ADR/0004)
    // and a collision fails loudly through the lifecycle's error path (B2).
    const num = s.partNumber ?? suggestPartNumber()
    const ops = buildContourOps(num, s.partName ?? `Sketch ${num}`, s.points, depthMm)
    await lifecycle.run(ops, num, {
      onBusy: () => store.setPhase('busy', 'extruding…'),
      onError: (m) => store.setPhase('error', m),
      onSuccess: (res) => {
        void viewportApi.current?.setDisplaySource(res.display)
        // Success: close the pad and KEEP the drawn solid in the viewport. Do
        // NOT call onClose — that is the CANCEL path (it restores the base
        // display, which would overwrite the solid we just showed).
        store.cancel()
      },
    })
  }

  const rubber = s.cursor && s.points.length > 0 && !s.closed
  const hint = problem ?? (s.closed ? 'Ring closed — set a depth and extrude.' : 'Click the first point to close the ring.')

  return (
    <div className="sketchpad">
      <div className="sp-head">
        <span className="sp-title">Sketch — XY plane</span>
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

        {/* the ring (closed → filled; open → polyline) */}
        {s.points.length > 0 && (
          <polyline
            className={`sp-ring ${s.closed ? 'closed' : ''}`}
            points={s.points.map(plot).join(' ') + (s.closed ? ' ' + plot(s.points[0]) : '')}
          />
        )}
        {rubber && <line className="sp-rubber" x1={s.points[s.points.length - 1].x} y1={-s.points[s.points.length - 1].y} x2={s.cursor!.x} y2={-s.cursor!.y} />}

        {/* placed vertices; the start point highlights when it can close */}
        {s.points.map((p, i) => (
          <circle key={i} className={`sp-vert ${i === 0 && nearStart ? 'snap' : ''}`} cx={p.x} cy={-p.y} r={i === 0 && nearStart ? 2.4 : 1.6} />
        ))}
      </svg>

      <div className="sp-foot">
        <span className={`sp-hint ${problem && s.points.length >= 3 ? 'warn' : ''}`}>{hint}</span>
        <span className="grow" />
        {s.phase === 'error' && <span className="sp-hint warn">{s.message}</span>}
        {!s.closed ? (
          <>
            <button type="button" className="btn small" onClick={() => store.undoPoint()} disabled={busy || s.points.length === 0}>Undo</button>
            <button type="button" className="btn small" onClick={() => store.closeRing()} disabled={busy || !!problem}>Close ring</button>
          </>
        ) : (
          <>
            <button type="button" className="btn small" onClick={() => store.reopen()} disabled={busy}>Reopen</button>
            <label className="sp-depth">Depth <input type="number" min={1} max={200} value={depthMm} disabled={busy} onChange={(e) => setDepthMm(Number(e.target.value) || 1)} /> mm</label>
            <button type="button" className="btn primary" onClick={extrude} disabled={busy || !!problem}>{busy ? '…' : 'Extrude'}</button>
          </>
        )}
        <button type="button" className="btn small" onClick={cancel} disabled={busy}>Cancel</button>
      </div>
    </div>
  )
}
