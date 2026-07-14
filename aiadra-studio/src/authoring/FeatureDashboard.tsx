/**
 * The manual feature dashboard (arc 20260711-11 / slice 1c) — the CAD-side
 * authoring surface (Creo's operation dashboard). A floating panel over the
 * viewport for the active feature op; the AI panel is its sibling view on the
 * SAME session (ADR/0040 D4). v1 = extrude a parametric rectangle. It reads the
 * feature session (source of truth) and OWNS the async side effects (the
 * AuthoringBackend begin→simulate→commit + the viewport setDisplaySource).
 */
import { useEffect, useMemo, type MutableRefObject } from 'react'
import type { ViewportApi } from '../Viewport'
import { buildExtrudeOps, suggestPartNumber, type AuthoringBackend } from './backend'
import { createSessionLifecycle } from './sessionLifecycle'
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
  onCommitted,
}: {
  store: FeatureSessionStore
  backend: AuthoringBackend
  viewportApi: MutableRefObject<ViewportApi | null>
  onClose: () => void
  /** Codex5 B2: the standalone extrude creates a FRESH Part — report it so the
   *  shell reconciles the authoring target (its known feature count is 2). */
  onCommitted?: (info: { number: string; name: string }) => void
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

  // Codex3 B1 → Codex6 B1: the begin→simulate→commit orchestration (retained
  // session id, retry cleanup, uninterruptible terminal commit, stale-async
  // token) lives in ONE shared module used by every authoring surface.
  const lifecycle = useMemo(() => createSessionLifecycle(backend), [backend])
  const busy = s.phase === 'busy'

  if (!active) return null

  const close = () => {
    if (!lifecycle.cancel()) return // the terminal commit is uninterruptible
    store.cancel()
    onClose()
  }

  const commit = async () => {
    if (busy) return
    // PROVISIONAL number (Codex2 B2) — core validates + reserves at commit.
    const num = suggestPartNumber()
    const ops = buildExtrudeOps(num, `Extrude ${num}`, s.params.width_mm, s.params.height_mm, s.params.depth_mm)
    await lifecycle.run(ops, num, {
      onBusy: () => store.setPhase('busy', 'committing…'),
      onError: (m) => store.setPhase('error', m),
      onSuccess: (res) => {
        void viewportApi.current?.setDisplaySource(res.display)
        store.setCommitted(res.objectRef)
        onCommitted?.({ number: num, name: `Extrude ${num}` }) // Codex5 B2
      },
    })
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
