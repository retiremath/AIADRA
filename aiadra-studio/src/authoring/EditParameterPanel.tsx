/**
 * The edit-dimension dashboard (arc 20260715-1 R6) — Creo's "edit the value,
 * regenerate" on ONE catalogued parameter of a committed feature. The
 * decoder's version-guarded catalogue is the only addressable surface
 * (Codex2 N3 — identity-preserving records); the engine's regenerating
 * `adjust_feature_parameter` stays the authority (its refusals verbatim).
 * Real lane only (D-R10/N4: the dev mock does not model mutation).
 */
import { useMemo } from 'react'
import type { DisplaySource } from '../display/displaySource'
import { buildAdjustParameterOps, type AuthoringBackend } from './backend'
import { useAuthoringSession, type AuthoringSessionStore } from './authoringSession'
import { createSessionLifecycle } from './sessionLifecycle'
import { guardTerminalTarget, type PartContextStore } from './partContext'

export function EditParameterPanel({
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
  const e = st.mode === 'editParameter' ? st : null
  const lifecycle = useMemo(() => createSessionLifecycle(backend), [backend])

  if (!e) return null
  const busy = e.phase === 'busy'
  const chosen = e.parameters.find((p) => p.name === e.paramName)

  const cancel = () => {
    if (!lifecycle.cancel()) return
    store.cancel()
    onClose()
  }

  const commit = async () => {
    if (busy || !Number.isFinite(e.value)) return
    const refusal = guardTerminalTarget(e.target, context.getSnapshot())
    if (refusal) {
      store.setEditPhase('error', refusal)
      return
    }
    const ops = buildAdjustParameterOps(e.target.partNumber, e.featureId, e.paramName, e.value)
    await lifecycle.run(ops, e.target.partNumber, {
      onBusy: () => store.setEditPhase('busy', 'regenerating…'),
      onError: (m) => store.setEditPhase('error', m),
      onSuccess: (res) => {
        onCommitted?.(res.display)
        store.cancel()
      },
    })
  }

  return (
    <div className="sketchpad extrude-panel">
      <div className="sp-head">
        <span className="sp-title">Edit dimension · {e.featureId}</span>
        <span className={`fd-lane ${backend.isReal ? 'real' : 'mock'}`}>{backend.isReal ? 'real engine' : 'dev mock'}</span>
        <button type="button" className="fd-x" title="Cancel (Esc)" onClick={cancel} disabled={busy}>✕</button>
      </div>
      <div className="sp-foot">
        {e.parameters.length > 1 && (
          <select
            value={e.paramName}
            disabled={busy}
            onChange={(ev) => store.chooseEditParameter(ev.target.value)}
          >
            {e.parameters.map((p) => (
              <option key={p.id} value={p.name}>
                {p.name}
              </option>
            ))}
          </select>
        )}
        {e.phase === 'error' && <span className="sp-hint warn">{e.message}</span>}
        <span className="grow" />
        <label className="sp-depth">
          {e.paramName}{' '}
          <input
            type="number"
            step={0.5}
            value={e.value}
            disabled={busy}
            onChange={(ev) => store.setEditValue(Number(ev.target.value))}
          />{' '}
          {chosen?.unit ?? 'mm'}
        </label>
        <button type="button" className="btn primary" onClick={commit} disabled={busy || !Number.isFinite(e.value)}>
          {busy ? '…' : 'OK'}
        </button>
        <button type="button" className="btn small" onClick={cancel} disabled={busy}>Cancel</button>
      </div>
    </div>
  )
}
