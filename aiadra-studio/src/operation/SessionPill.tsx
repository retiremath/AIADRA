/**
 * The status-strip session pill + stateful AI-dock toggle (arc 20260711-10 /
 * MVP-1; ADR/0040 D5 B1 — Codex arc-20260711-10 B1).
 *
 * A SECOND projection of the operation store (the dock is the first) — proving
 * the single-source-of-truth invariant (ADR/0040 D4/N2) and, crucially,
 * providing ACTIONABLE session presence OUTSIDE the dock: when the dock is
 * hidden mid-session, the pill still shows the session identity (configurator +
 * selected candidate + transient) and offers Restore AI + Cancel — so a dismissed
 * dock never means a lost operation. The toggle is stateful across three states:
 * no-session · session+shown · session+hidden.
 */
import { selectedCandidate, useOperation, type OperationStore } from './store'

export function SessionPill({
  store,
  dockOpen,
  onShowDock,
}: {
  store: OperationStore
  dockOpen: boolean
  onShowDock: () => void
}) {
  const op = useOperation(store)
  const sel = selectedCandidate(op)
  const hasSession = op.phase !== 'idle'

  // State 1 — no session: just the dock toggle.
  if (!hasSession) {
    return (
      <button
        type="button"
        className={`ai-toggle ${dockOpen ? '' : 'off'}`}
        onClick={onShowDock}
        title="Toggle the AI / Home dock"
      >
        <span className="dot" /> AI dock
      </button>
    )
  }

  const identity = (
    <span className="pill-id">
      <span className="pill-name">{op.configuratorName}</span>
      {sel && <span className="pill-sel"> · {sel.label}</span>}
      <span className="pill-transient"> · transient</span>
    </span>
  )

  // State 2 — session + dock shown: an active indicator (a click focuses/keeps
  // the dock). No restore/cancel needed here (the dock has them).
  if (dockOpen) {
    return (
      <span className="ai-toggle session on" title="An operation is active in the dock">
        <span className="dot live" /> Operation active {identity}
      </span>
    )
  }

  // State 3 — session + dock hidden: ACTIONABLE presence (B1). Restore AI +
  // Cancel (Cancel calls the SAME store.cancel() the dock uses).
  return (
    <span className="ai-toggle session hidden" title="An operation is active — the AI dock is hidden">
      <span className="dot live" /> Operation active {identity}
      <button type="button" className="pill-btn" onClick={onShowDock}>
        Restore AI
      </button>
      <button type="button" className="pill-btn danger" onClick={() => store.cancel()}>
        Cancel
      </button>
    </span>
  )
}
