/**
 * The in-context sketch CHROME (arc 20260716-2 SK-C1.0 S1; Codex2 B5.1) —
 * the compact overlay strip that replaced the opaque SVG pad. The VIEWPORT is
 * the drawing surface now (ray-to-plane input, world-space live geometry via
 * `sketchEditOverlay`); this strip carries only the tools, the hint, and
 * OK/Cancel — the pad's commit semantics VERBATIM (stepwise sketch commit or
 * the chained hand-back; guardTerminalTarget; the one sessionLifecycle).
 *
 * `routeSketchPlacement` is the pad's click routing as a pure function: the
 * Workbench feeds it plane-local (u, v) mm from the viewport's ray-plane
 * intersection — snap, the 3-point-arc via flow, ring closing, and dedupe
 * behave exactly as the pad did.
 */
import { useEffect, useMemo } from 'react'
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
import { contourProblem, dist, type Pt } from './contour'
import { bulgeFromThreePoints } from './arcGeometry'

const SNAP_MM = 5 // grid snap for placed points (the pad's value)
const CLOSE_MM = 6 // click within this of the start point closes the ring

const snap = (v: number) => Math.round(v / SNAP_MM) * SNAP_MM

/** The pad's onClick, as a pure router over plane-local mm (SK-C1.0 S1).
 *  Codex5 B2: the LIVE generation is checked SYNCHRONOUSLY at the placement
 *  boundary — a late pointer event after a Part-generation change invalidates
 *  and places NOTHING, independent of any React effect having run. */
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
    // the 3-point-arc VIA click — the last segment curves through it (UNSNAPPED,
    // exactly like the pad: the via is geometric, not a grid vertex)
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

export function SketchChrome({
  store,
  backend,
  context,
  onClose,
  onCommitted,
  onSketchView,
}: {
  store: AuthoringSessionStore
  backend: AuthoringBackend
  /** The generation-owned Part context — the terminal commit REVALIDATES the
   *  captured target against it (Codex3 B2, fail closed). */
  context: PartContextStore
  onClose: () => void
  onCommitted?: (info: {
    number: string
    name: string
    createdFresh: boolean
    display: DisplaySource
  }) => void
  /** The `Sketch view` return command (Codex2 B5.4 — camera-only). */
  onSketchView: () => void
}) {
  const st = useAuthoringSession(store)
  const s = st.mode === 'sketch' ? st : null

  const lifecycle = useMemo(() => createSessionLifecycle(backend), [backend])
  const busy = s?.phase === 'busy'
  const ct = s?.tool.kind === 'contour' ? s.tool : null
  const rt = s?.tool.kind === 'rectangle' ? s.tool : null
  const ci = s?.tool.kind === 'circle' ? s.tool : null
  const problem = ct ? contourProblem(ct.points, ct.bulges) : null
  const done = ct ? ct.closed : rt ? rt.rect !== null : (ci?.circle ?? null) !== null

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

  const cancel = () => {
    if (!lifecycle.cancel()) return
    store.cancel()
    onClose()
  }

  /** OK — the stepwise sketch commit (or the chained hand-back), VERBATIM. */
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
    // S3: the SUPPORT is the commit authority — a face-bound session sends
    // the engine's face input shape through the widened builders. A face
    // support without a target Part is an impossible state (a face belongs
    // to a committed base); refuse rather than silently commit a principal.
    if (s.support.kind === 'face' && !target) {
      store.setSketchPhase('error', 'a face-bound sketch needs its target Part — cancel and reopen')
      return
    }
    const num = target?.number ?? s.partNumber ?? suggestPartNumber()
    const name = target?.name ?? s.partName ?? `Sketch ${num}`
    const construction = s.construction
    const rect = rt?.rect ?? null
    const circle = ci?.circle ?? null
    const ops = circle
      ? target
        ? buildCircleSketchOps(target.number, circle, s.support, construction)
        : buildCreateWithCircleOps(num, name, circle, s.plane, construction)
      : rect
        ? target
          ? buildRectangleSketchOps(target.number, rect, s.support, construction)
          : buildCreateWithRectangleOps(num, name, rect, s.plane, construction)
        : target
          ? buildSketchOnlyOps(target.number, ct!.points, s.support, { bulges: ct!.bulges, construction })
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
            : 'Click in the viewport to place points; close the ring at the start point.')

  return (
    <div className="sketch-chrome">
      <div className="sc-row">
        <span className="sc-title">
          {s.support.kind === 'face'
            ? `Sketch — face ${s.support.faceId}`
            : `Sketch — ${PLANE_LABELS[s.plane]} (${s.plane})`}
          {s.targetPart && <span className="muted"> · {s.targetPart.number}</span>}
          {s.chainToExtrude && <span className="muted"> · for Extrude</span>}
        </span>
        {!s.chainToExtrude && (
          <span className="sc-tools">
            <button type="button" className={`btn small${ct ? ' primary' : ''}`} disabled={busy}
              title="Draw a closed contour (click points; close the ring)"
              onClick={() => store.switchTool('contour')}>Contour</button>
            <button type="button" className={`btn small${rt ? ' primary' : ''}`} disabled={busy}
              title="Draw a rectangle (two clicks) — the native profile for Revolve/Hole"
              onClick={() => store.switchTool('rectangle')}>Rectangle</button>
            <button type="button" className={`btn small${ci ? ' primary' : ''}`} disabled={busy}
              title="Draw a circle (center + rim)"
              onClick={() => store.switchTool('circle')}>Circle</button>
            {ct && (
              <button type="button" className={`btn small${ct.awaitingVia ? ' primary' : ''}`}
                disabled={busy || ct.closed || ct.points.length < 2 || (ct.bulges[ct.bulges.length - 1] ?? 0) !== 0}
                title="Curve the LAST segment: click a via point the arc passes through (minor arcs)"
                onClick={() => store.setAwaitingVia(!ct.awaitingVia)}>Arc</button>
            )}
            <button type="button" className={`btn small${s.construction ? ' primary' : ''}`} disabled={busy}
              title="Construction guide: visible dashed, never part of the profile or the solid"
              onClick={() => store.toggleConstruction()}>Constr.</button>
          </span>
        )}
        <button type="button" className="btn small" title="Orient the view normal to the sketch plane (camera only)"
          onClick={onSketchView}>Sketch view</button>
        <span className={`fd-lane ${backend.isReal ? 'real' : 'mock'}`}>{backend.isReal ? 'real engine' : 'dev mock'}</span>
      </div>
      <div className="sc-row">
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
