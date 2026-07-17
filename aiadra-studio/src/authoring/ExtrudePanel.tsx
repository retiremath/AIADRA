/**
 * The BASE-FEATURE dashboard (S2 D-S3 → arc 20260715-1 R3) — Creo's dual
 * entry for extrude AND revolve over ONE discriminated session (Codex2 Q1:
 * shared capture/cancel/lifecycle/source-selection shell; feature-specific
 * parameter editors — depth vs axis):
 *
 *  - **Entry A** (a sketch selected/picked): choose an UNCONSUMED committed
 *    sketch → parameters → ONE op referencing the REAL engine id. Revolve
 *    lists only ELIGIBLE sketches (the exact `simple_rectangle` + xy + axis
 *    facts — P1); ineligible ones grey with the derived reason.
 *  - **Entry B** ("New sketch…"): the chained pad — contour for extrude,
 *    RECTANGLE pinned to xy for revolve (D-R9) — committed as ONE draft via
 *    the $fromOp handshake.
 *
 * Commits through the ONE sessionLifecycle; eligibility from the generation-
 * owned partContext; terminal commits revalidate the captured authority tuple.
 */
import { useMemo } from 'react'
import type { DisplaySource } from '../display/displaySource'
import {
  buildContourFeatureOps,
  buildExtrudeOnSketchOps,
  buildRectangleRevolveOps,
  buildRevolveOnSketchOps,
  PLANE_LABELS,
  type AuthoringBackend,
} from './backend'
import { useAuthoringSession, type AuthoringSessionStore } from './authoringSession'
import { createSessionLifecycle } from './sessionLifecycle'
import { guardTerminalTarget, type PartContextStore } from './partContext'
import {
  revolveAxisRefusal,
  revolveSketchRefusal,
  unconsumedSketches,
  type InspectedPart,
  type RevolveAxis,
} from './inspectDecode'

/** S2: a face-bound sketch labels by its support role; principal by plane. */
function planeLabel(p: import('./inspectDecode').SketchPlaneBinding): string {
  return p.kind === 'principal' ? PLANE_LABELS[p.orientation] : `face ${p.faceRole}`
}

export function ExtrudePanel({
  store,
  backend,
  context,
  part,
  onClose,
  onCommitted,
  onNewSketch,
}: {
  store: AuthoringSessionStore
  backend: AuthoringBackend
  /** The generation-owned Part context — the terminal commit REVALIDATES the
   *  session's captured target against it (Codex3 B2, fail closed). */
  context: PartContextStore
  /** The READY inspected Part (partContext authority) — null refuses commits
   *  (fail closed; the panel should not open without it). */
  part: InspectedPart | null
  onClose: () => void
  /** The commit's display source — the Workbench installs it INSIDE the same
   *  Part transition that re-reads Truth (Codex3 B2; no direct installs here). */
  onCommitted?: (display: DisplaySource) => void
  /** Entry B: open the chained sketch (the App pins plane/tool per feature). */
  onNewSketch?: (feature: 'extrude' | 'revolve') => void
}) {
  const st = useAuthoringSession(store)
  const e = st.mode === 'extrude' ? st : null
  const lifecycle = useMemo(() => createSessionLifecycle(backend), [backend])

  if (!e) return null
  const busy = e.phase === 'busy'
  const isRevolve = e.feature === 'revolve'
  const featureLabel = isRevolve ? 'Revolve' : 'Extrude'
  const all = part ? unconsumedSketches(part) : []
  // Entry A candidates: extrude takes any unconsumed sketch; revolve derives
  // per-sketch eligibility from the EXACT decoded facts (P1) — ineligible
  // sketches stay visible but greyed with the derived reason.
  const candidates = all.map((sk, i) => ({
    sk,
    n: i + 1,
    // SK-C0 Codex3 B2: a guides-only sketch stays VISIBLE (its dashed overlay
    // is real) but is never extrudable — the derived refusal mirrors the
    // engine's construction-only rejection instead of reaching it loudly.
    refusal:
      sk.profile.kind === 'sketch_only'
        ? 'a construction-only sketch has no profile to extrude'
        : isRevolve
          ? revolveSketchRefusal(sk)
          : null,
  }))

  // Revolve axis eligibility for the CHOSEN source (committed or pending rect).
  const sourceRect = (() => {
    if (!isRevolve || !e.source) return null
    if (e.source.kind === 'pending_rectangle') return e.source.rect
    if (e.source.kind === 'committed') {
      const src = e.source
      const sk = all.find((s) => s.id === src.sketchId)
      return sk?.profile.kind === 'simple_rectangle' ? sk.profile.rectangle : null
    }
    return null
  })()
  const axisRefusal = (axis: RevolveAxis): string | null =>
    sourceRect ? revolveAxisRefusal(sourceRect, axis) : null

  const cancel = () => {
    if (!lifecycle.cancel()) return
    store.cancel()
    onClose()
  }

  const commit = async () => {
    if (busy || !e.source) return
    if (!part) {
      store.setExtrudePhase('error', `no inspected Part context — cannot ${featureLabel.toLowerCase()}`)
      return
    }
    // Codex3 B2 / Codex4 B1.4: the terminal boundary revalidates the CAPTURED
    // authority tuple — an accidental gate bypass fails closed.
    const refusal = guardTerminalTarget(e.target, context.getSnapshot())
    if (refusal) {
      store.setExtrudePhase('error', refusal)
      return
    }
    if (isRevolve && axisRefusal(e.axis)) {
      store.setExtrudePhase('error', axisRefusal(e.axis)!)
      return
    }
    const ops = isRevolve
      ? e.source.kind === 'committed'
        ? buildRevolveOnSketchOps(part.number, e.source.sketchId, e.axis)
        : e.source.kind === 'pending_rectangle'
          ? buildRectangleRevolveOps(part.number, e.source.rect, e.axis)
          : null
      : e.source.kind === 'committed'
        ? buildExtrudeOnSketchOps(part.number, e.source.sketchId, e.depthMm)
        : e.source.kind === 'pending'
          ? buildContourFeatureOps(part.number, e.source.points, e.depthMm, e.source.plane, 0, e.source.bulges)
          : null
    if (ops === null) {
      store.setExtrudePhase('error', `the drawn source does not fit ${featureLabel} — cancel and retry`)
      return
    }
    await lifecycle.run(ops, part.number, {
      onBusy: () => store.setExtrudePhase('busy', `${featureLabel.toLowerCase()}…`),
      onError: (m) => store.setExtrudePhase('error', m),
      onSuccess: (res) => {
        store.selectSketch(null) // the selected sketch is consumed now
        onCommitted?.(res.display)
        store.cancel()
      },
    })
  }

  return (
    <div className="sketchpad extrude-panel">
      <div className="sp-head">
        <span className="sp-title">{featureLabel}{part ? ` · ${part.number}` : ''}</span>
        <span className={`fd-lane ${backend.isReal ? 'real' : 'mock'}`}>{backend.isReal ? 'real engine' : 'dev mock'}</span>
        <button type="button" className="fd-x" title="Cancel (Esc)" onClick={cancel} disabled={busy}>✕</button>
      </div>

      {e.step === 'select' ? (
        <div className="sp-foot" style={{ flexWrap: 'wrap' }}>
          <span className="sp-hint">Pick a sketch to {featureLabel.toLowerCase()}:</span>
          {candidates.map(({ sk, n, refusal }) => (
            <button
              key={sk.id}
              type="button"
              className="btn small"
              disabled={busy || refusal !== null}
              title={refusal ?? `Sketch ${n} · ${planeLabel(sk.plane)}`}
              onClick={() => refusal === null && store.chooseCommittedSketch(sk.id)}
            >
              Sketch {n} · {planeLabel(sk.plane)}
            </button>
          ))}
          {candidates.length === 0 && <span className="muted small">no unconsumed sketches</span>}
          <span className="grow" />
          <button
            type="button"
            className="btn small"
            disabled={busy}
            title={isRevolve ? 'Draw a rectangle on FRONT (xy) — the v1 revolve profile' : 'Draw a contour on a picked plane'}
            onClick={() => onNewSketch?.(e.feature)}
          >
            New sketch…
          </button>
          <button type="button" className="btn small" onClick={cancel} disabled={busy}>Cancel</button>
        </div>
      ) : (
        <div className="sp-foot">
          <span className="sp-hint">
            {e.source?.kind === 'committed'
              ? `sketch ${e.source.sketchId}`
              : e.source?.kind === 'pending'
                ? `drawn sketch on ${PLANE_LABELS[e.source.plane]}`
                : e.source
                  ? 'drawn rectangle on FRONT (xy)'
                  : ''}
          </span>
          {e.phase === 'error' && <span className="sp-hint warn">{e.message}</span>}
          <span className="grow" />
          {isRevolve ? (
            <span className="sp-depth">
              Axis{' '}
              {(['x', 'y'] as const).map((axis) => (
                <button
                  key={axis}
                  type="button"
                  className={`btn small${e.axis === axis ? ' primary' : ''}`}
                  disabled={busy || axisRefusal(axis) !== null}
                  title={axisRefusal(axis) ?? `revolve 360° around the global ${axis.toUpperCase()} axis`}
                  onClick={() => store.setAxis(axis)}
                >
                  {axis.toUpperCase()}
                </button>
              ))}
            </span>
          ) : (
            <label className="sp-depth">
              Depth{' '}
              <input
                type="number"
                min={1}
                max={200}
                value={e.depthMm}
                disabled={busy}
                onChange={(ev) => store.setDepth(Number(ev.target.value) || 1)}
              />{' '}
              mm
            </label>
          )}
          <button type="button" className="btn primary" onClick={commit} disabled={busy || !e.source}>
            {busy ? '…' : 'OK'}
          </button>
          <button type="button" className="btn small" onClick={cancel} disabled={busy}>Cancel</button>
        </div>
      )}
    </div>
  )
}
