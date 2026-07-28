/**
 * The SKETCH ribbon (pass sketch-ribbon-1). While a sketch session is
 * active, the tab strip activates a dedicated Sketch tab and THIS ribbon
 * replaces the Model ribbon — the sketch tools in the ribbon's grouped
 * grammar. Same store, same actions: the ribbon is a PROJECTION of the one
 * sketch session (ADR/0040 D4 — never a second authority), and it exposes
 * EXACTLY the state transitions the session already defines (Codex1 B2):
 *
 *   open contour   → Undo (only with points) · Close ring (only when the
 *                    ring is VALID — `contourProblem === null`)
 *   closed contour → Reopen (Undo/Close are absent: a closed ring is edited
 *                    by reopening, never mutated while marked closed)
 *   rect/circle    → Restart while incomplete · Reopen once complete
 *
 * Constrain/Dimension are roadmap-disabled with their named strands per the
 * three-state taxonomy — sketcher behavior 2+ (the skb-b1 solver-contract
 * gate) brings them live. OK/Cancel stay in the sketch chrome for this
 * increment (the commit lifecycle owns them); the Close group migrates with
 * that lifecycle in increment 2 (ADR/0045 pass ledger SR-03/SR-08).
 */
import { useEffect, useMemo } from 'react'
import { useAuthoringSession, type AuthoringSessionStore } from '../authoring/authoringSession'
import { createSessionLifecycle } from '../authoring/sessionLifecycle'
import type { AuthoringBackend } from '../authoring/backend'
import type { PartContextStore } from '../authoring/partContext'
import { cancelSketch, runSketchOk, sketchDerived, type SketchCommitHooks } from './sketchCommit'

export function SketchRibbon({
  store,
  backend,
  context,
  onClose,
  onCommitted,
  onSketchView,
}: {
  store: AuthoringSessionStore
  backend: AuthoringBackend
  /** The generation-owned Part context — the terminal commit REVALIDATES the
   *  captured target against it (fail closed). */
  context: PartContextStore
  onClose: () => void
  onCommitted?: SketchCommitHooks['onCommitted']
  /** Camera-only reorient to the sketch plane (SK-C1.0 Codex2 B5.4). Stays
   *  available during a commit — a camera move mutates nothing (Codex1 N1:
   *  the pre-ribbon surface allowed it; the projection preserves it). */
  onSketchView: () => void
}) {
  const st = useAuthoringSession(store)
  // Codex1 B4: ONE SessionLifecycle per mount × backend identity — NEVER
  // recreated by store renders or hook-identity changes. sketchCommit.ts is
  // pure invocation code over this persistent owner.
  const lifecycle = useMemo(() => createSessionLifecycle(backend), [backend])
  const inSketch = st.mode === 'sketch'

  // The ONE sketch keyboard owner (moved with the lifecycle): Escape=cancel
  // (lifecycle-guarded), Enter=close a valid drawing contour, Backspace=undo.
  useEffect(() => {
    if (!inSketch) return
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA')) return
      const live = store.getSnapshot()
      if (live.mode !== 'sketch') return
      if (e.key === 'Escape') {
        cancelSketch(lifecycle, store, onClose)
        e.preventDefault()
      } else if (e.key === 'Enter' && live.phase === 'drawing' && live.tool.kind === 'contour'
          && sketchDerived(live).problem === null) {
        store.closeRing()
        e.preventDefault()
      } else if (e.key === 'Backspace' && live.phase === 'drawing' && live.tool.kind === 'contour') {
        store.undoPoint()
        e.preventDefault()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [inSketch, lifecycle, store, onClose])

  if (st.mode !== 'sketch') return null
  const s = st
  const { ct, rt, ci, problem, done, busy } = sketchDerived(s)
  const chained = s.chainToExtrude

  const tool = (
    label: string,
    active: boolean,
    title: string,
    onClick: () => void,
    disabled = false,
  ) => (
    <button
      type="button"
      className={`rb-btn${active ? ' on' : ''}`}
      disabled={busy || disabled}
      title={title}
      onClick={onClick}
    >
      <span className="rb-lbl">{label}</span>
    </button>
  )

  const roadmap = (label: string, reason: string) => (
    <button type="button" className="rb-btn rb-roadmap" disabled title={reason}>
      <span className="rb-lbl">{label}</span>
    </button>
  )

  return (
    <div className="ribbon" role="toolbar" aria-label="Sketch ribbon">
      <div className="ribbon-group">
        <div className="ribbon-btns">
          <button
            type="button"
            className="rb-btn"
            title="Orient the view normal to the sketch plane (camera only)"
            onClick={onSketchView}
          >
            <span className="rb-lbl">Sketch view</span>
          </button>
        </div>
        <div className="ribbon-group-title">Setup</div>
      </div>
      {!chained && (
        <div className="ribbon-group">
          <div className="ribbon-btns">
            {tool('Contour', !!ct, 'Draw a closed contour (click points; close the ring)', () => store.switchTool('contour'))}
            {tool('Rectangle', !!rt, 'Draw a rectangle (two clicks) — the native profile for Revolve/Hole', () => store.switchTool('rectangle'))}
            {tool('Circle', !!ci, 'Draw a circle (center + rim)', () => store.switchTool('circle'))}
            {tool(
              'Arc',
              !!ct?.awaitingVia,
              'Curve the LAST segment: click a via point the arc passes through (minor arcs)',
              () => store.setAwaitingVia(!ct?.awaitingVia),
              !ct || ct.closed || ct.points.length < 2 || (ct.bulges[ct.bulges.length - 1] ?? 0) !== 0,
            )}
            {tool('Constr.', s.construction, 'Construction guide: visible dashed, never part of the profile or the solid', () => store.toggleConstruction())}
          </div>
          <div className="ribbon-group-title">Sketching</div>
        </div>
      )}
      <div className="ribbon-group">
        <div className="ribbon-btns">
          {ct && !done ? (
            <>
              {tool('Undo', false, 'Remove the last placed point', () => store.undoPoint(), ct.points.length === 0)}
              {tool(
                'Close ring',
                false,
                problem ?? 'Close the contour at the start point',
                () => store.closeRing(),
                problem !== null,
              )}
            </>
          ) : done ? (
            tool('Reopen', false, 'Reopen the shape for editing', () => store.reopen())
          ) : (
            tool('Restart', false, 'Discard the shape and start again', () => store.reopen(), rt ? !rt.anchor : !ci?.center)
          )}
        </div>
        <div className="ribbon-group-title">Editing</div>
      </div>
      <div className="ribbon-group">
        <div className="ribbon-btns">
          {roadmap('Vertical', 'Constraints arrive with sketcher behavior 2+ (the skb-b1 solver-contract gate)')}
          {roadmap('Horizontal', 'Constraints arrive with sketcher behavior 2+ (the skb-b1 solver-contract gate)')}
        </div>
        <div className="ribbon-group-title">Constrain</div>
      </div>
      <div className="ribbon-group">
        <div className="ribbon-btns">
          {roadmap('Dimension', 'Dimensions arrive with sketcher behaviors 2–3 (auto-dimension, then strong-dimension edit)')}
        </div>
        <div className="ribbon-group-title">Dimension</div>
      </div>
      {/* increment 2 (SR-03): the terminal commit/cancel — ONE lifecycle
          owner; OK runs the verbatim stepwise commit or the chained
          hand-back; Cancel is lifecycle-guarded (refused mid-terminal). */}
      <div className="ribbon-group">
        <div className="ribbon-btns">
          <button
            type="button"
            className="rb-btn rb-ok"
            disabled={busy || problem !== null || !done}
            title={s.chainToExtrude ? 'OK — return the sketch to Extrude' : 'OK — commit the sketch'}
            onClick={() => void runSketchOk(lifecycle, store, context, { onCommitted })}
          >
            <span className="rb-lbl">{busy ? '…' : 'OK'}</span>
          </button>
          <button
            type="button"
            className="rb-btn"
            disabled={busy}
            title="Cancel the sketch (Esc)"
            onClick={() => cancelSketch(lifecycle, store, onClose)}
          >
            <span className="rb-lbl">Cancel</span>
          </button>
        </div>
        <div className="ribbon-group-title">Close</div>
      </div>
    </div>
  )
}
