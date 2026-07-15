/**
 * The Round/Chamfer dashboard (arc 20260715-1 R4) — the first ribbon features
 * driven by CANONICAL topology selection. The session OWNS its capture (D-R8):
 * `{AuthoringTarget, selector, edge kind}` resolved against the generation-
 * bound selectorFacts at start — a later selection change never retargets.
 * The display edge_id crosses as ADR/0038 INPUT vocabulary; the engine
 * re-anchors it and remains the final authority (its refusals surface
 * verbatim at begin/simulate). Real lane only (D-R10) — the ribbon greys
 * these in dev:web.
 */
import { useMemo } from 'react'
import type { DisplaySource } from '../display/displaySource'
import { buildEdgeFeatureOps, type AuthoringBackend } from './backend'
import { useAuthoringSession, type AuthoringSessionStore } from './authoringSession'
import { createSessionLifecycle } from './sessionLifecycle'
import { guardTerminalTarget, type PartContextStore } from './partContext'

const LABELS = { fillet: 'Round', chamfer: 'Chamfer' } as const
const VALUE_LABEL = { fillet: 'Radius', chamfer: 'Distance' } as const

export function EdgeFeaturePanel({
  store,
  backend,
  context,
  onClose,
  onCommitted,
}: {
  store: AuthoringSessionStore
  backend: AuthoringBackend
  context: PartContextStore
  onClose: () => void
  onCommitted?: (display: DisplaySource) => void
}) {
  const st = useAuthoringSession(store)
  const e = st.mode === 'edgeFeature' ? st : null
  const lifecycle = useMemo(() => createSessionLifecycle(backend), [backend])

  if (!e) return null
  const busy = e.phase === 'busy'
  const label = LABELS[e.feature]

  const cancel = () => {
    if (!lifecycle.cancel()) return
    store.cancel()
    onClose()
  }

  const commit = async () => {
    if (busy || !(e.valueMm > 0)) return
    // The terminal boundary revalidates the CAPTURED tuple (Codex4 B1.4).
    const refusal = guardTerminalTarget(e.capture.target, context.getSnapshot())
    if (refusal) {
      store.setEdgeFeaturePhase('error', refusal)
      return
    }
    const ops = buildEdgeFeatureOps(e.feature, e.capture.target.partNumber, e.capture.selector.id, e.valueMm)
    await lifecycle.run(ops, e.capture.target.partNumber, {
      onBusy: () => store.setEdgeFeaturePhase('busy', `${label.toLowerCase()}…`),
      onError: (m) => store.setEdgeFeaturePhase('error', m),
      onSuccess: (res) => {
        onCommitted?.(res.display)
        store.cancel()
      },
    })
  }

  return (
    <div className="sketchpad extrude-panel">
      <div className="sp-head">
        <span className="sp-title">{label} · {e.capture.target.partNumber}</span>
        <span className={`fd-lane ${backend.isReal ? 'real' : 'mock'}`}>{backend.isReal ? 'real engine' : 'dev mock'}</span>
        <button type="button" className="fd-x" title="Cancel (Esc)" onClick={cancel} disabled={busy}>✕</button>
      </div>
      <div className="sp-foot">
        <span className="sp-hint" title={e.capture.selector.id}>
          edge · {e.capture.selector.id.length > 42 ? `${e.capture.selector.id.slice(0, 42)}…` : e.capture.selector.id}
        </span>
        {e.phase === 'error' && <span className="sp-hint warn">{e.message}</span>}
        <span className="grow" />
        <label className="sp-depth">
          {VALUE_LABEL[e.feature]}{' '}
          <input
            type="number"
            min={0.1}
            max={100}
            step={0.5}
            value={e.valueMm}
            disabled={busy}
            onChange={(ev) => store.setEdgeValue(Number(ev.target.value) || 0.1)}
          />{' '}
          mm
        </label>
        <button type="button" className="btn primary" onClick={commit} disabled={busy || !(e.valueMm > 0)}>
          {busy ? '…' : 'OK'}
        </button>
        <button type="button" className="btn small" onClick={cancel} disabled={busy}>Cancel</button>
      </div>
    </div>
  )
}
