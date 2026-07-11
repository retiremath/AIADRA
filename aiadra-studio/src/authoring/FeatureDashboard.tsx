/**
 * The manual feature dashboard (arc 20260711-11 / slice 1c) — the CAD-side
 * authoring surface (Creo's operation dashboard). A floating panel over the
 * viewport for the active feature op; the AI panel is its sibling view on the
 * SAME session (ADR/0040 D4). v1 = extrude a parametric rectangle. It reads the
 * feature session (source of truth) and OWNS the async side effects (the
 * AuthoringBackend begin→simulate→commit + the viewport setDisplaySource).
 */
import { useEffect, useRef, type MutableRefObject } from 'react'
import type { ViewportApi } from '../Viewport'
import { buildExtrudeOps, type AuthoringBackend } from './backend'
import { useFeatureSession, type FeatureSessionStore } from './featureSession'

const EXTRUDE_PARAMS = [
  { key: 'width_mm', label: 'Width', min: 20, max: 200, step: 1 },
  { key: 'height_mm', label: 'Height', min: 20, max: 200, step: 1 },
  { key: 'depth_mm', label: 'Depth', min: 1, max: 60, step: 1 },
] as const

export const EXTRUDE_DEFAULTS: Record<string, number> = { width_mm: 80, height_mm: 50, depth_mm: 6 }

export function FeatureDashboard({
  store,
  backend,
  viewportApi,
  onClose,
}: {
  store: FeatureSessionStore
  backend: AuthoringBackend
  viewportApi: MutableRefObject<ViewportApi | null>
  onClose: () => void
}) {
  const s = useFeatureSession(store)
  const active = s.active && s.featureKind === 'extrude'

  // Live preview on session start: the dev:web mock synthesizes a box; the
  // bridge returns null (commit shows the real geometry). Fire once per session.
  useEffect(() => {
    if (!active || !backend.previewSource) return
    let cancelled = false
    backend
      .previewSource()
      .then((src) => {
        if (src && !cancelled) void viewportApi.current?.setDisplaySource(src)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active])

  const seq = useRef(0)
  // Codex3 B1: retain the active backend session id across commit/error/cancel
  // (a failed commit's session must remain rollbackable), and a stale-async
  // token so a closed dashboard can never update the viewport/session from an
  // in-flight result.
  const sessionRef = useRef<string | null>(null)
  const genRef = useRef(0)
  const busy = s.phase === 'busy'

  if (!active) return null

  const close = () => {
    if (busy) return // the terminal commit is uninterruptible (Codex3 B1)
    genRef.current++ // invalidate any in-flight async result
    const sid = sessionRef.current
    sessionRef.current = null
    if (sid) void backend.rollback(sid).catch(() => {}) // roll back a retained (e.g. failed-commit) session
    store.cancel()
    onClose()
  }

  const commit = async () => {
    if (busy) return
    const gen = genRef.current
    // A retained session from a prior failed attempt is stale — discard it first.
    if (sessionRef.current) {
      const stale = sessionRef.current
      sessionRef.current = null
      await backend.rollback(stale).catch(() => {})
    }
    store.setPhase('busy', 'committing…')
    const num = `P-${String((seq.current++ + Math.floor(performance.now())) % 1000000).padStart(6, '0')}`
    const ops = buildExtrudeOps(num, `Extrude ${num}`, s.params.width_mm, s.params.height_mm, s.params.depth_mm)
    try {
      const sid = await backend.begin(ops)
      if (gen !== genRef.current) {
        await backend.rollback(sid).catch(() => {}) // cancelled mid-begin
        return
      }
      sessionRef.current = sid
      const sim = await backend.simulate(sid)
      if (gen !== genRef.current || !sim.valid) {
        sessionRef.current = null
        await backend.rollback(sid).catch(() => {})
        if (gen === genRef.current) store.setPhase('error', sim.message ?? 'validation failed')
        return
      }
      const res = await backend.commit(sid, num)
      sessionRef.current = null // committed — the backend closed the session
      if (gen !== genRef.current) return // dashboard closed mid-commit; the Part is committed, leave the viewport
      void viewportApi.current?.setDisplaySource(res.display)
      store.setCommitted(res.objectRef)
    } catch (e) {
      // The backend session may still be open; sessionRef keeps the handle so the
      // user can retry (rolls back the stale one) or cancel (rolls it back).
      if (gen === genRef.current) store.setPhase('error', e instanceof Error ? e.message : String(e))
    }
  }
  return (
    <div className="feature-dash">
      <div className="fd-head">
        <span className="fd-title">Extrude</span>
        <span className={`fd-lane ${backend.isReal ? 'real' : 'mock'}`}>{backend.isReal ? 'real engine' : 'dev mock'}</span>
        <button type="button" className="fd-x" title="Cancel" onClick={close} disabled={busy}>
          ✕
        </button>
      </div>
      <div className="fd-body">
        {EXTRUDE_PARAMS.map((p) => (
          <label key={p.key} className="fd-row small">
            <span className="muted">
              {p.label} <span className="param-unit">mm</span>
            </span>
            <span className="fd-ctl">
              <input
                type="range"
                min={p.min}
                max={p.max}
                step={p.step}
                value={s.params[p.key] ?? p.min}
                disabled={busy}
                onChange={(e) => store.setParam(p.key, Number(e.target.value))}
              />
              <span className="fd-val">{s.params[p.key] ?? p.min}</span>
            </span>
          </label>
        ))}
        {s.message && <div className={`fd-msg ${s.phase === 'error' ? 'err' : ''}`}>{s.message}</div>}
        {s.phase === 'committed' && <div className="fd-msg ok">✓ committed {s.objectRef}</div>}
      </div>
      <div className="fd-actions">
        <button type="button" className="btn" onClick={close} disabled={busy}>
          Cancel
        </button>
        <button type="button" className="btn primary" onClick={commit} disabled={busy}>
          {busy ? '…' : 'Commit extrude'}
        </button>
      </div>
    </div>
  )
}
