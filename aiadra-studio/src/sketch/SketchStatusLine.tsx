/**
 * The sketch STATUS LINE (pass sketch-ribbon-1 increment 2, SR-08; Codex1
 * B5 tenancy contract). Renders in the statusbar's EXCLUSIVE transient slot
 * while a sketch session is active: identity + the exact live hint/error +
 * the lane badge, with the context-hover readout MERGED in (retained, never
 * dropped). The slot owns truncation (flex + min-width:0 + ellipsis at the
 * hint) so the fixed tenants (SessionPill left, BYO-AI right) can never be
 * pushed off-screen. `shellNote` REPLACES this line while present — the
 * exclusivity is enforced at the statusbar mount, not here.
 */
import { PLANE_LABELS } from '../authoring/backend'
import { useAuthoringSession, type AuthoringSessionStore } from '../authoring/authoringSession'
import { sketchHint } from './sketchCommit'

export function SketchStatusLine({
  store,
  isReal,
  hover,
}: {
  store: AuthoringSessionStore
  isReal: boolean
  /** The canonical-selection hover readout (merged tenant; B5). */
  hover: { kind: 'face' | 'edge'; id: string } | null
}) {
  const st = useAuthoringSession(store)
  if (st.mode !== 'sketch') return null
  const s = st
  const identity =
    s.support.kind === 'face'
      ? `Sketch — face ${s.support.faceId}`
      : `Sketch — ${PLANE_LABELS[s.plane]} (${s.plane})`
  return (
    <span className="sketch-status small" data-testid="sketch-status">
      <span className="ss-id">
        {identity}
        {s.targetPart ? ` · ${s.targetPart.number}` : ''}
        {s.chainToExtrude ? ' · for Extrude' : ''}
      </span>
      <span className={`ss-hint${s.phase === 'error' ? ' warn' : ''}`}>
        {s.phase === 'error' && s.message ? s.message : sketchHint(s)}
      </span>
      {hover && (
        <span className="muted context-hover" data-context-id={hover.id}>
          context {hover.kind}: <span className="mono">{hover.id}</span>
        </span>
      )}
      <span className={`fd-lane ${isReal ? 'real' : 'mock'}`}>{isReal ? 'real engine' : 'dev mock'}</span>
    </span>
  )
}
