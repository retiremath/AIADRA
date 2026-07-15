/**
 * The dual-entry Extrude (S2; arc 20260714-3 D-S3) — Creo's extrude semantics:
 *
 *  - **Entry A** (a sketch is selected / picked here): choose an UNCONSUMED
 *    committed sketch → set a depth → commit ONE extrude op referencing the
 *    REAL engine id from inspected Truth.
 *  - **Entry B** (no sketch): "New sketch…" hands off to the sketch pad
 *    (chained); its rings come back PENDING and commit as ONE draft
 *    [sketch, extrude($fromOp 0)] — the engine mints the sketch id mid-draft.
 *
 * A view over the ONE `authoringSession` store; commits through the ONE shared
 * sessionLifecycle. The selectable-sketch list and the eligibility both come
 * from the generation-owned partContext (inspected Truth, fail-closed) — the
 * retired rectangle dashboard's invented geometry has no successor here.
 */
import { useMemo } from 'react'
import type { DisplaySource } from '../display/displaySource'
import {
  buildContourFeatureOps,
  buildExtrudeOnSketchOps,
  PLANE_LABELS,
  type AuthoringBackend,
  type PlaneOrientation,
} from './backend'
import { useAuthoringSession, type AuthoringSessionStore } from './authoringSession'
import { createSessionLifecycle } from './sessionLifecycle'
import { guardTerminalTarget, type PartContextStore } from './partContext'
import { unconsumedSketches, type InspectedPart } from './inspectDecode'

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
  /** Entry B: open the plane picker → chained sketch pad. */
  onNewSketch?: () => void
}) {
  const st = useAuthoringSession(store)
  const e = st.mode === 'extrude' ? st : null
  const lifecycle = useMemo(() => createSessionLifecycle(backend), [backend])

  if (!e) return null
  const busy = e.phase === 'busy'
  const candidates = part ? unconsumedSketches(part) : []

  const cancel = () => {
    if (!lifecycle.cancel()) return
    store.cancel()
    onClose()
  }

  const commit = async () => {
    if (busy || !e.source) return
    if (!part) {
      store.setExtrudePhase('error', 'no inspected Part context — cannot extrude')
      return
    }
    // Codex3 B2 / Codex4 B1.4: the terminal boundary revalidates the CAPTURED
    // authority tuple (workspace + Part number + generation) — an accidental
    // gate bypass fails closed, never a cross-Part/cross-generation commit.
    const refusal = guardTerminalTarget(e.target, context.getSnapshot())
    if (refusal) {
      store.setExtrudePhase('error', refusal)
      return
    }
    const ops =
      e.source.kind === 'committed'
        ? buildExtrudeOnSketchOps(part.number, e.source.sketchId, e.depthMm)
        : buildContourFeatureOps(part.number, e.source.points, e.depthMm, e.source.plane)
    await lifecycle.run(ops, part.number, {
      onBusy: () => store.setExtrudePhase('busy', 'extruding…'),
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
        <span className="sp-title">Extrude{part ? ` · ${part.number}` : ''}</span>
        <span className={`fd-lane ${backend.isReal ? 'real' : 'mock'}`}>{backend.isReal ? 'real engine' : 'dev mock'}</span>
        <button type="button" className="fd-x" title="Cancel (Esc)" onClick={cancel} disabled={busy}>✕</button>
      </div>

      {e.step === 'select' ? (
        <div className="sp-foot" style={{ flexWrap: 'wrap' }}>
          <span className="sp-hint">Pick a sketch to extrude:</span>
          {candidates.map((sk, i) => (
            <button
              key={sk.id}
              type="button"
              className="btn small"
              disabled={busy}
              onClick={() => store.chooseCommittedSketch(sk.id)}
            >
              Sketch {i + 1} · {PLANE_LABELS[sk.plane]}
            </button>
          ))}
          {candidates.length === 0 && <span className="muted small">no unconsumed sketches</span>}
          <span className="grow" />
          <button type="button" className="btn small" disabled={busy} onClick={() => onNewSketch?.()}>
            New sketch…
          </button>
          <button type="button" className="btn small" onClick={cancel} disabled={busy}>Cancel</button>
        </div>
      ) : (
        <div className="sp-foot">
          <span className="sp-hint">
            {e.source?.kind === 'committed'
              ? `sketch ${e.source.sketchId}`
              : e.source
                ? `drawn sketch on ${PLANE_LABELS[(e.source as { plane: PlaneOrientation }).plane]}`
                : ''}
          </span>
          {e.phase === 'error' && <span className="sp-hint warn">{e.message}</span>}
          <span className="grow" />
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
          <button type="button" className="btn primary" onClick={commit} disabled={busy || !e.source}>
            {busy ? '…' : 'OK'}
          </button>
          <button type="button" className="btn small" onClick={cancel} disabled={busy}>Cancel</button>
        </div>
      )}
    </div>
  )
}
