/**
 * The SKETCH ribbon (pass sketch-ribbon-1; Creo 10 Sketch-tab benchmark,
 * Petre's side-by-side 2026-07-28). When a sketch session is active the tab
 * strip activates a Sketch tab and THIS ribbon replaces the Model ribbon —
 * the tools move from the floating chrome into Creo's grouped grammar. Same
 * store, same actions: the ribbon is a PROJECTION of the one sketch session
 * (ADR/0040 D4 — never a second authority).
 *
 * Groups (Creo order, our honest capability set): Setup · Sketching ·
 * Editing · Constrain (roadmap) · Dimension (roadmap). Constrain/Dimension
 * name their strands per the three-state taxonomy — behavior 2+ (skb-b1)
 * brings them live. OK/Cancel stay in the sketch chrome for this increment
 * (the commit lifecycle owns them); the Close group migrates next.
 */
import { useAuthoringSession, type AuthoringSessionStore } from '../authoring/authoringSession'

export function SketchRibbon({
  store,
  onSketchView,
}: {
  store: AuthoringSessionStore
  /** Camera-only reorient to the sketch plane (SK-C1.0 Codex2 B5.4). */
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
          {tool('Sketch view', false, 'Orient the view normal to the sketch plane (camera only)', onSketchView)}
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
          {ct ? (
            <>
              {tool('Undo', false, 'Remove the last placed point', () => store.undoPoint(), ct.points.length === 0)}
              {tool('Close ring', false, 'Close the contour at the start point', () => store.closeRing(), ct.closed)}
            </>
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
