/**
 * The 2D sketch pad (arc 20260711-11 slice S/X; S2 stepwise) — draw a closed
 * contour on the picked plane. S2 (D-S2/D-S4): the pad is a view over the ONE
 * discriminated `authoringSession` store, and the sketch is FIRST-CLASS —
 * OK commits the sketch ALONE (→ `Sketch N` in the tree + its wire in the
 * viewport; Extrude consumes it later), except in the CHAINED entry (launched
 * from Extrude's "New sketch…"), where OK hands the drawn rings back to the
 * extrude session and the pair commits as ONE draft via the $fromOp handshake.
 *
 * Validity is a client-side mirror of the engine's Class-1 gate
 * (`contourProblem`) so the hint matches what commit will accept.
 */
import { useEffect, useMemo, useRef } from 'react'
import type { DisplaySource } from '../display/displaySource'
import {
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
import { contourProblem, dist, type Pt } from './contour'

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

  // Codex6 B1 → S2: the SAME shared begin→simulate→commit lifecycle as every
  // authoring surface — retained session, retry cleanup, uninterruptible commit.
  const lifecycle = useMemo(() => createSessionLifecycle(backend), [backend])
  const busy = s?.phase === 'busy'
  // The DISCRIMINATED tool (arc 20260715-1 Codex2 N2): contour drawing state
  // and rectangle two-click state never mix.
  const ct = s?.tool.kind === 'contour' ? s.tool : null
  const rt = s?.tool.kind === 'rectangle' ? s.tool : null
  const problem = ct ? contourProblem(ct.points) : null
  const done = ct ? ct.closed : (rt?.rect ?? null) !== null
  const nearStart = ct?.cursor && ct.points.length >= 3 && dist(ct.cursor, ct.points[0]) <= CLOSE_MM

  // Esc cancels; Enter closes a valid ring; Backspace undoes — guarded off inputs.
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
      // The rectangle tool: anchor, then the opposite corner (normalized
      // min-corner + abs dims — Codex2 N1; a degenerate pick refuses).
      store.placeRectCorner(p)
      return
    }
    if (!ct) return
    if (ct.points.length >= 3 && dist(m, ct.points[0]) <= CLOSE_MM) {
      store.closeRing()
    } else {
      // Ignore a click that lands on the last placed point (grid snap makes a
      // double-click an exact duplicate → a zero-length segment, Codex6 B2).
      const last = ct.points[ct.points.length - 1]
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

  /** OK — the stepwise sketch commit (or the chained hand-back). */
  const ok = async () => {
    if (busy || problem || !done) return
    if (s.chainToExtrude) {
      // The chained in-place sketch: NO commit here — the rings return to the
      // extrude session and the pair commits as ONE draft ($fromOp).
      store.finishChainedSketch()
      return
    }
    const target = s.targetPart
    // Codex3 B2 / Codex4 B1.4: the terminal boundary revalidates the CAPTURED
    // authority tuple — a targeted session whose tuple is missing or no longer
    // exact (workspace, Part number, generation, ready) fails closed.
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
    const rect = rt?.rect ?? null
    const ops = rect
      ? target
        ? buildRectangleSketchOps(target.number, rect, s.plane)
        : buildCreateWithRectangleOps(num, name, rect, s.plane)
      : target
        ? buildSketchOnlyOps(target.number, ct!.points, s.plane)
        : buildCreateWithSketchOps(num, name, ct!.points, s.plane)
    await lifecycle.run(ops, num, {
      onBusy: () => store.setSketchPhase('busy', 'committing sketch…'),
      onError: (m) => store.setSketchPhase('error', m),
      onSuccess: (res) => {
        // The sketch alone makes no solid — the Workbench installs the display
        // inside the SAME transition that re-reads Truth (the wire follows).
        onCommitted?.({ number: num, name, createdFresh: !target, display: res.display })
        store.cancel()
      },
    })
  }

  const rubber = ct ? ct.cursor && ct.points.length > 0 && !ct.closed : false
  const hint =
    problem ??
    (done
      ? s.chainToExtrude
        ? 'Ready — OK returns to Extrude.'
        : 'Ready — OK commits the sketch.'
      : rt
        ? rt.anchor
          ? 'Click the opposite corner.'
          : 'Click the first corner of the rectangle.'
        : 'Click the first point to close the ring.')
  // The live rectangle preview: committed rect, or anchor->cursor rubber.
  const previewRect = rt
    ? rt.rect ?? (rt.anchor && rt.cursor
        ? { x_mm: Math.min(rt.anchor.x, rt.cursor.x), y_mm: Math.min(rt.anchor.y, rt.cursor.y),
            width_mm: Math.abs(rt.cursor.x - rt.anchor.x), height_mm: Math.abs(rt.cursor.y - rt.anchor.y) }
        : null)
    : null

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

        {/* contour: the ring (closed → filled; open → polyline) */}
        {ct && ct.points.length > 0 && (
          <polyline
            className={`sp-ring ${ct.closed ? 'closed' : ''}`}
            points={ct.points.map(plot).join(' ') + (ct.closed ? ' ' + plot(ct.points[0]) : '')}
          />
        )}
        {ct && rubber && <line className="sp-rubber" x1={ct.points[ct.points.length - 1].x} y1={-ct.points[ct.points.length - 1].y} x2={ct.cursor!.x} y2={-ct.cursor!.y} />}
        {ct &&
          ct.points.map((p, i) => (
            <circle key={i} className={`sp-vert ${i === 0 && nearStart ? 'snap' : ''}`} cx={p.x} cy={-p.y} r={i === 0 && nearStart ? 2.4 : 1.6} />
          ))}

        {/* rectangle: the committed rect (filled) or the anchor→cursor rubber */}
        {previewRect && (
          <rect
            className={`sp-ring ${rt?.rect ? 'closed' : ''}`}
            x={previewRect.x_mm}
            y={-(previewRect.y_mm + previewRect.height_mm)}
            width={previewRect.width_mm}
            height={previewRect.height_mm}
          />
        )}
        {rt?.anchor && <circle className="sp-vert" cx={rt.anchor.x} cy={-rt.anchor.y} r={1.8} />}
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
            <button type="button" className="btn small" onClick={() => store.reopen()} disabled={busy || !rt?.anchor}>Restart</button>
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
