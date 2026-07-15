/**
 * The Hole dashboard (arc 20260715-1 R5) — a circular through-hole on a
 * CAPTURED cap face. Eligibility came from the P1 base-domain predicate
 * (extruded from exactly one rectangle; no prior hole) + the D-R8 face
 * capture; the WALL-vs-CAP distinction stays ENGINE-authoritative and
 * surfaces verbatim before commit (P2's named bounded limitation — the
 * display carries no cap classification, so aim for a flat cap face).
 * Center coordinates are sketch-plane mm (the engine validates fit).
 */
import { useMemo } from 'react'
import type { DisplaySource } from '../display/displaySource'
import { buildHoleOps, type AuthoringBackend } from './backend'
import { useAuthoringSession, type AuthoringSessionStore } from './authoringSession'
import { createSessionLifecycle } from './sessionLifecycle'
import { guardTerminalTarget, type PartContextStore } from './partContext'

export function HolePanel({
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
  const e = st.mode === 'holeFeature' ? st : null
  const lifecycle = useMemo(() => createSessionLifecycle(backend), [backend])

  if (!e) return null
  const busy = e.phase === 'busy'

  const cancel = () => {
    if (!lifecycle.cancel()) return
    store.cancel()
    onClose()
  }

  const commit = async () => {
    if (busy || !(e.diameterMm > 0)) return
    const refusal = guardTerminalTarget(e.capture.target, context.getSnapshot())
    if (refusal) {
      store.setHolePhase('error', refusal)
      return
    }
    const ops = buildHoleOps(
      e.capture.target.partNumber,
      e.capture.selector.id,
      e.diameterMm,
      e.centerXMm,
      e.centerYMm,
    )
    await lifecycle.run(ops, e.capture.target.partNumber, {
      onBusy: () => store.setHolePhase('busy', 'cutting…'),
      onError: (m) => store.setHolePhase('error', m), // wall/cap/fit refusals VERBATIM
      onSuccess: (res) => {
        onCommitted?.(res.display)
        store.cancel()
      },
    })
  }

  const num = (name: 'diameterMm' | 'centerXMm' | 'centerYMm', label: string, min?: number) => (
    <label className="sp-depth" key={name}>
      {label}{' '}
      <input
        type="number"
        min={min}
        step={0.5}
        value={e[name]}
        disabled={busy}
        onChange={(ev) => store.setHoleParam(name, Number(ev.target.value) || 0)}
      />{' '}
      mm
    </label>
  )

  return (
    <div className="sketchpad extrude-panel">
      <div className="sp-head">
        <span className="sp-title">Hole · {e.capture.target.partNumber}</span>
        <span className={`fd-lane ${backend.isReal ? 'real' : 'mock'}`}>{backend.isReal ? 'real engine' : 'dev mock'}</span>
        <button type="button" className="fd-x" title="Cancel (Esc)" onClick={cancel} disabled={busy}>✕</button>
      </div>
      <div className="sp-foot">
        <span className="sp-hint" title={e.capture.selector.id}>
          face · pick a flat CAP face (the engine refuses walls before commit)
        </span>
        {e.phase === 'error' && <span className="sp-hint warn">{e.message}</span>}
        <span className="grow" />
        {num('diameterMm', 'Ø', 0.1)}
        {num('centerXMm', 'X')}
        {num('centerYMm', 'Y')}
        <button type="button" className="btn primary" onClick={commit} disabled={busy || !(e.diameterMm > 0)}>
          {busy ? '…' : 'OK'}
        </button>
        <button type="button" className="btn small" onClick={cancel} disabled={busy}>Cancel</button>
      </div>
    </div>
  )
}
