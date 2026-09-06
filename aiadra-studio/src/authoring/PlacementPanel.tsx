/**
 * The placement dialog (ADR/0044 A3; pass sketch-place-1 Codex1 B4; I3 —
 * arc 20260905-1): Creo's Sketch → Placement tab, honest about domain.
 *
 * Sketch Plane: the **Plane** collector (fill it by picking a datum plane in
 * the viewport while it is active, or from the list) + **Use Previous**,
 * disabled with its product reason (SP-05 deferred). Sketch Orientation:
 * **Flip** (the `normal_side` fact under Creo's label — a MODEL fact, SP-04),
 * the **Reference** collector (auto-defaulted per A3.3 when the plane is
 * picked; viewport pick or list; never parallel to the plane), and
 * **Orientation**. ONE panel serves three accept continuations — **Sketch**
 * (open the drawing session; nothing is written), **Create** (References:
 * commit a construction sketch), **Redefine** (a placed 0.2.1 References
 * sketch). Only the explicit accept acts; Escape / ✕ / Cancel leave nothing.
 */
import { useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { PLANE_LABELS, type PlaneOrientation } from './backend'
import { dragOffset } from './placementDrag'
import {
  useAuthoringSession,
  type AuthoringSessionStore,
  type PlacementCollector,
  type PlacementSubstate,
} from './authoringSession'
import { ACCEPT_LABEL, COLLECTOR_HINT, FLIP_HINT, USE_PREVIOUS_UNAVAILABLE } from './placementCopy'

const PRINCIPALS = ['xy', 'yz', 'zx'] as const
const ORIENTATIONS = ['right', 'top', 'left', 'bottom'] as const
const ORIENTATION_LABEL: Record<(typeof ORIENTATIONS)[number], string> = {
  right: 'Right',
  top: 'Top',
  left: 'Left',
  bottom: 'Bottom',
}

const planeName = (o: PlaneOrientation) => `${PLANE_LABELS[o]} (${o})`

export function PlacementPanel({
  store,
  isReal,
  onAccept,
}: {
  store: AuthoringSessionStore
  isReal: boolean
  /** The App owns what Accept does per continuation (the one-shot commit
   *  runner for Create/Redefine; the drawing session for Sketch). */
  onAccept: () => void
}) {
  const s = useAuthoringSession(store)
  const panelRef = useRef<HTMLDivElement | null>(null)
  const offsetRef = useRef({ x: 0, y: 0 })
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  if (s.mode !== 'placement') return null
  const p = s as PlacementSubstate

  // W-5: drag by the title bar (controls in the bar keep their own clicks)
  const onHeadDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return
    if ((e.target as HTMLElement).closest('button, select, input, a')) return
    const head = e.currentTarget as HTMLElement
    if (typeof head.setPointerCapture === 'function') head.setPointerCapture(e.pointerId)
    const startX = e.clientX
    const startY = e.clientY
    const start = offsetRef.current
    const panel = panelRef.current
    const pr = panel?.getBoundingClientRect() ?? null
    const hr = panel?.parentElement?.getBoundingClientRect() ?? null
    const move = (ev: PointerEvent) => {
      const next = dragOffset(start, { x: ev.clientX - startX, y: ev.clientY - startY }, pr, hr)
      offsetRef.current = next
      setOffset(next)
    }
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    e.preventDefault()
  }

  const redefine = p.accept === 'redefine' && p.redefineOf !== null
  const unchanged =
    redefine &&
    p.support === p.redefineOf!.current.support &&
    p.orientationRef === p.redefineOf!.current.orientationRef &&
    p.orientation === p.redefineOf!.current.orientation &&
    p.normalSide === p.redefineOf!.current.normalSide

  const toggleCollector = (c: PlacementCollector) =>
    store.setPlacementCollector(p.activeCollector === c ? null : c)

  const collector = (c: PlacementCollector, value: PlaneOrientation) => {
    const active = p.activeCollector === c
    return (
      <button
        type="button"
        className={`pl-collector${active ? ' active' : ''}`}
        aria-pressed={active}
        data-testid={`collector-${c}`}
        title={COLLECTOR_HINT}
        disabled={p.busy}
        onClick={() => toggleCollector(c)}
      >
        {planeName(value)}
      </button>
    )
  }

  return (
    <div
      ref={panelRef}
      className="sketchpad extrude-panel placement-panel"
      data-testid="placement-panel"
      style={{ transform: `translate(${offset.x}px, ${offset.y}px)` }}
    >
      <div className="sp-head pl-drag" title="Drag to move" onPointerDown={onHeadDown} data-testid="placement-head">
        <span className="sp-title">
          {redefine ? `Redefine placement · ${p.redefineOf!.featureId}` : 'Sketch'}
          {p.targetPart ? ` · ${p.targetPart.number}` : ''}
        </span>
        <span className={`fd-lane ${isReal ? 'real' : 'mock'}`}>{isReal ? 'real engine' : 'dev mock'}</span>
        <button type="button" className="fd-x" title="Cancel (Esc)" onClick={() => store.cancelPlacement()} disabled={p.busy}>
          ✕
        </button>
      </div>
      <div className="pl-body">
        <div className="pl-section">
          <div className="pl-section-title">Sketch Plane</div>
          <div className="pl-row">
            <span className="pl-label">Plane</span>
            {collector('plane', p.support)}
            <select
              aria-label="Sketch plane list"
              value={p.support}
              disabled={p.busy}
              onChange={(e) => store.setPlacementMember('support', e.target.value)}
            >
              {PRINCIPALS.map((o) => (
                <option key={o} value={o}>{planeName(o)}</option>
              ))}
            </select>
            <button type="button" className="btn small" disabled title={USE_PREVIOUS_UNAVAILABLE} data-testid="use-previous">
              Use Previous
            </button>
          </div>
        </div>
        <div className="pl-section">
          <div className="pl-section-title">Sketch Orientation</div>
          <div className="pl-row">
            <span className="pl-label">Sketch view direction</span>
            <button
              type="button"
              className={`btn small${p.normalSide === 'negative' ? ' pressed' : ''}`}
              aria-pressed={p.normalSide === 'negative'}
              data-testid="flip"
              title={FLIP_HINT}
              disabled={p.busy}
              onClick={() =>
                store.setPlacementMember('normalSide', p.normalSide === 'negative' ? 'positive' : 'negative')
              }
            >
              Flip
            </button>
          </div>
          <div className="pl-row">
            <span className="pl-label">Reference</span>
            {collector('reference', p.orientationRef)}
            <select
              aria-label="Orientation reference list"
              value={p.orientationRef}
              disabled={p.busy}
              onChange={(e) => store.setPlacementMember('orientationRef', e.target.value)}
            >
              {PRINCIPALS.filter((o) => o !== p.support).map((o) => (
                <option key={o} value={o}>{planeName(o)}</option>
              ))}
            </select>
          </div>
          <div className="pl-row">
            <span className="pl-label">Orientation</span>
            <select
              aria-label="Orientation"
              value={p.orientation}
              disabled={p.busy}
              onChange={(e) => store.setPlacementMember('orientation', e.target.value)}
            >
              {ORIENTATIONS.map((o) => (
                <option key={o} value={o}>{ORIENTATION_LABEL[o]}</option>
              ))}
            </select>
          </div>
        </div>
      </div>
      <div className="sp-foot">
        <span className="grow" />
        <button
          type="button"
          className="btn small primary"
          data-testid="accept"
          disabled={p.busy || unchanged}
          title={unchanged ? 'nothing changed — adjust a member or cancel' : undefined}
          onClick={onAccept}
        >
          {p.busy ? 'committing…' : ACCEPT_LABEL[p.accept]}
        </button>
        <button type="button" className="btn small" disabled={p.busy} onClick={() => store.cancelPlacement()}>
          Cancel
        </button>
      </div>
      {p.message && <div className="sp-hint warn pad">{p.message}</div>}
    </div>
  )
}
