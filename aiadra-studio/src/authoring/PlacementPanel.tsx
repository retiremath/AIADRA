/**
 * The placement-confirm panel (ADR/0044 A3; pass sketch-place-1, Codex1 B4)
 * — the Creo two-reference sketch dialog: the picked SUPPORT, the engine's
 * auto-defaulted orientation reference (changeable), the orientation edge,
 * and the normal side (labeled Flip per the Creo grammar; the Truth name is
 * `normal_side` — Petre's experiment proved it model semantics). ONE panel
 * serves CREATE (References) and REDEFINE (the tree's ✎); only the explicit
 * Accept constructs the op and starts the one-shot commit lifecycle.
 */
import { PLANE_LABELS } from './backend'
import {
  useAuthoringSession,
  type AuthoringSessionStore,
  type PlacementSubstate,
} from './authoringSession'

const PRINCIPALS = ['xy', 'yz', 'zx'] as const
const ORIENTATIONS = ['right', 'top', 'left', 'bottom'] as const

export function PlacementPanel({
  store,
  isReal,
  onAccept,
}: {
  store: AuthoringSessionStore
  isReal: boolean
  /** The App owns the commit lifecycle (the persistent one-shot runner). */
  onAccept: () => void
}) {
  const s = useAuthoringSession(store)
  if (s.mode !== 'placement') return null
  const p = s as PlacementSubstate

  const redefine = p.redefineOf !== null
  const unchanged =
    redefine &&
    p.support === p.redefineOf!.current.support &&
    p.orientationRef === p.redefineOf!.current.orientationRef &&
    p.orientation === p.redefineOf!.current.orientation &&
    p.normalSide === p.redefineOf!.current.normalSide

  return (
    <div className="sketchpad extrude-panel placement-panel">
      <div className="sp-head">
        <span className="sp-title">
          {redefine ? `Redefine placement · ${p.redefineOf!.featureId}` : 'Sketch placement'}
          {p.targetPart ? ` · ${p.targetPart.number}` : ''}
        </span>
        <span className={`fd-lane ${isReal ? 'real' : 'mock'}`}>{isReal ? 'real engine' : 'dev mock'}</span>
        <button type="button" className="fd-x" title="Cancel (Esc)" onClick={() => store.cancelPlacement()} disabled={p.busy}>
          ✕
        </button>
      </div>
      <div className="sp-foot" style={{ flexWrap: 'wrap', gap: 10 }}>
        <label className="sp-hint">
          Support{' '}
          <select
            value={p.support}
            disabled={p.busy}
            onChange={(e) => store.setPlacementMember('support', e.target.value)}
          >
            {PRINCIPALS.map((o) => (
              <option key={o} value={o}>{PLANE_LABELS[o]}</option>
            ))}
          </select>
        </label>
        <label className="sp-hint">
          Reference{' '}
          <select
            value={p.orientationRef}
            disabled={p.busy}
            onChange={(e) => store.setPlacementMember('orientationRef', e.target.value)}
          >
            {PRINCIPALS.filter((o) => o !== p.support).map((o) => (
              <option key={o} value={o}>{PLANE_LABELS[o]}</option>
            ))}
          </select>
        </label>
        <label className="sp-hint">
          Orientation{' '}
          <select
            value={p.orientation}
            disabled={p.busy}
            onChange={(e) => store.setPlacementMember('orientation', e.target.value)}
          >
            {ORIENTATIONS.map((o) => (
              <option key={o} value={o}>{o}</option>
            ))}
          </select>
        </label>
        <label className="sp-hint" title="Creo's Flip — the SIGNED sketch normal (a model fact: a positive-depth feature grows to the other side)">
          <input
            type="checkbox"
            checked={p.normalSide === 'negative'}
            disabled={p.busy}
            onChange={(e) =>
              store.setPlacementMember('normalSide', e.target.checked ? 'negative' : 'positive')
            }
          />{' '}
          Flip
        </label>
        <button
          type="button"
          className="btn small primary"
          disabled={p.busy || unchanged}
          title={unchanged ? 'nothing changed — adjust a member or cancel' : undefined}
          onClick={onAccept}
        >
          {p.busy ? 'committing…' : redefine ? 'Redefine' : 'Create'}
        </button>
      </div>
      {p.message && <div className="sp-hint warn pad">{p.message}</div>}
    </div>
  )
}
