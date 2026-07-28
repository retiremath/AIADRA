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
import { useAuthoringSession, type AuthoringSessionStore } from '../authoring/authoringSession'
import { contourProblem } from './contour'

export function SketchRibbon({
  store,
  onSketchView,
}: {
  store: AuthoringSessionStore
  /** Camera-only reorient to the sketch plane (SK-C1.0 Codex2 B5.4). Stays
   *  available during a commit — a camera move mutates nothing (Codex1 N1:
   *  the pre-ribbon surface allowed it; the projection preserves it). */
  onSketchView: () => void
}) {
  const st = useAuthoringSession(store)
  if (st.mode !== 'sketch') return null
  const s = st
  const busy = s.phase === 'busy'
  const ct = s.tool.kind === 'contour' ? s.tool : null
  const rt = s.tool.kind === 'rectangle' ? s.tool : null
  const ci = s.tool.kind === 'circle' ? s.tool : null
  const chained = s.chainToExtrude
  const problem = ct ? contourProblem(ct.points, ct.bulges) : null
  const done = ct ? ct.closed : rt ? rt.rect !== null : (ci?.circle ?? null) !== null

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
    </div>
  )
}
