/**
 * The PROFILE status line (W-2). The statusbar's exclusive transient slot
 * went silent during a profile session — the SR-08 prompt idiom (identity +
 * live hint + lane badge) applied only to the v1 store. The chain grammar is
 * gesture-driven (middle-click ends, first-point closes, Esc abandons), so
 * the hint line is where the idiom is TAUGHT — the same tenancy contract as
 * SketchStatusLine, mounted in the same slot, never both at once (the two
 * lifecycles never nest).
 */
import { PLANE_LABELS } from '../authoring/backend'
import { profileHint } from './profileHint'
import type { ProfileSessionState } from './profileSession'

export function ProfileStatusLine({
  session,
  isReal,
}: {
  session: ProfileSessionState
  isReal: boolean
}) {
  const identity =
    session.owner.kind === 'edit'
      ? `Profile Sketch — editing ${session.owner.sketchFeatureId}`
      : `Profile Sketch — ${PLANE_LABELS[session.owner.placement.support.orientation]} (${session.owner.placement.support.orientation})`
  return (
    <span className="sketch-status small" data-testid="profile-status">
      <span className="ss-id">
        {identity}
        {` · ${session.target.partNumber}`}
      </span>
      <span className="ss-hint">{profileHint(session)}</span>
      <span className={`fd-lane ${isReal ? 'real' : 'mock'}`}>{isReal ? 'real engine' : 'dev mock'}</span>
    </span>
  )
}
