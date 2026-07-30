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
import { useEffect, useMemo, useRef } from 'react'
import { useAuthoringSession, type AuthoringSessionStore } from '../authoring/authoringSession'
import { createSessionLifecycle } from '../authoring/sessionLifecycle'
import type { AuthoringBackend } from '../authoring/backend'
import type { PartContextStore } from '../authoring/partContext'
import { cancelSketch, runSketchOk, sketchDerived, type SketchCommitHooks } from './sketchCommit'
// SR-09: the sketcher glyph suite (LGPL2+, pinned tag, per-file rights
// verified — src/assets/freecad-icons/README.md); one visual language.
import icoView from '../assets/freecad-icons/Sketcher_ViewSketch.svg'
import icoPolyline from '../assets/freecad-icons/Sketcher_CreatePolyline.svg'
import icoRect from '../assets/freecad-icons/Sketcher_CreateRectangle.svg'
import icoCircle from '../assets/freecad-icons/Sketcher_CreateCircle.svg'
import icoArc from '../assets/freecad-icons/Sketcher_Create3PointArc.svg'
import icoConstr from '../assets/freecad-icons/Sketcher_ToggleConstruction.svg'
import icoUndo from '../assets/freecad-icons/edit-undo.svg'
import icoVertical from '../assets/freecad-icons/Constraint_Vertical.svg'
import icoHorizontal from '../assets/freecad-icons/Constraint_Horizontal.svg'
import icoDimension from '../assets/freecad-icons/Constraint_Dimension.svg'
import icoLeave from '../assets/freecad-icons/Sketcher_LeaveSketch.svg'

const GLYPHS: Record<string, string> = {
  'Sketch view': icoView,
  Line: icoPolyline,
  Contour: icoPolyline,
  Rectangle: icoRect,
  Circle: icoCircle,
  Arc: icoArc,
  'Constr.': icoConstr,
  Undo: icoUndo,
  Vertical: icoVertical,
  Horizontal: icoHorizontal,
  Dimension: icoDimension,
  OK: icoLeave,
}

const glyph = (label: string) =>
  GLYPHS[label] ? (
    <span className="rb-ico">
      <img src={GLYPHS[label]} width={20} height={20} alt="" draggable={false} />
    </span>
  ) : null

export function SketchRibbon({
  store,
  backend,
  context,
  onClose,
  onCommitted,
  onSketchView,
  profile,
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
  /** ADR/0044 A4 (arc 20260730-1): the v2 PROFILE lane, when the shell
   *  provides it. Optional so the v1 pad keeps working untouched — the two
   *  lanes share this ribbon but never each other's state. */
  profile?: {
    active: boolean
    /** True while the Close commit is in flight (single-flight terminal). */
    closing: boolean
    refusal: string | null
    close(): void
    cancel(): void
    setTool(kind: 'line' | 'rectangle' | 'circle'): void
    /** End the open line chain (Enter here; middle-click in the viewport). */
    finishTool(opts?: { closed?: boolean }): void
    /** W-2: a chain run is in progress — the Escape target. */
    hasRun: boolean
    /** Abandon the in-progress run; completed shapes stay. */
    abandonRun(): void
    undo(): void
    toolKind: 'line' | 'rectangle' | 'circle' | null
  }
}) {
  const st = useAuthoringSession(store)
  // Codex1 B4: ONE SessionLifecycle per mount × backend identity — NEVER
  // recreated by store renders or hook-identity changes. sketchCommit.ts is
  // pure invocation code over this persistent owner.
  const lifecycle = useMemo(() => createSessionLifecycle(backend), [backend])
  const inSketch = st.mode === 'sketch'
  const inProfile = profile?.active === true
  // The profile prop is an inline literal at the call site; handlers read the
  // ref so the keyboard owner below subscribes once per session, not per
  // render (the sketchCbRef idiom).
  const profileRef = useRef(profile)
  useEffect(() => {
    profileRef.current = profile
  })

  // The ONE profile keyboard owner (W-2): Escape abandons the in-progress
  // chain run (completed shapes stay — session cancel remains the explicit
  // Cancel button); Enter ends the open chain, the keyboard twin of the
  // viewport's middle-click.
  useEffect(() => {
    if (!inProfile) return
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA')) return
      const p = profileRef.current
      if (!p || !p.active || p.closing) return
      if (e.key === 'Escape' && p.hasRun) {
        p.abandonRun()
        e.preventDefault()
      } else if (e.key === 'Enter' && p.hasRun) {
        p.finishTool()
        e.preventDefault()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [inProfile])

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

  // Codex6 B2: EXACTLY ONE terminal owner. While a profile session is live
  // the v1 store is idle (the entries never nest), so this ribbon renders the
  // profile grammar ALONE — the legacy groups and their OK/Cancel do not
  // exist on screen, and cannot end a session they do not own.
  if (inProfile && profile) {
    const ptool = (label: string, active: boolean, title: string, onClick: () => void, disabled = false) => (
      <button
        type="button"
        className={`rb-btn${active ? ' rb-active' : ''}`}
        disabled={disabled || profile.closing}
        title={title}
        onClick={onClick}
      >
        {glyph(label)}
        <span className="rb-lbl">{label}</span>
      </button>
    )
    return (
      <div className="ribbon-groups">
        <div className="ribbon-group">
          <div className="ribbon-btns">
            {ptool('Line', profile.toolKind === 'line', 'Line chain — each click chains a segment; middle-click ends it; click the first point to close; Esc abandons the run', () => profile.setTool('line'))}
            {ptool('Rectangle', profile.toolKind === 'rectangle', 'Draw a rectangle (two clicks) — four segments with asserted right angles', () => profile.setTool('rectangle'))}
            {ptool('Circle', profile.toolKind === 'circle', 'Draw a circle (center + rim)', () => profile.setTool('circle'))}
            {ptool('Undo', false, 'Remove the last drawn shape', () => profile.undo())}
          </div>
          <div className="ribbon-group-title">Profile</div>
        </div>
        {profile.refusal && (
          <div className="ribbon-group">
            <div className="ribbon-btns">
              <span className="rb-lbl" title={profile.refusal} style={{ maxWidth: 260, color: '#b0453a' }}>
                {profile.refusal}
              </span>
            </div>
            <div className="ribbon-group-title">Engine</div>
          </div>
        )}
        <div className="ribbon-group">
          <div className="ribbon-btns">
            <button
              type="button"
              className="rb-btn rb-ok"
              disabled={profile.closing}
              title="OK — commit the constrained profile"
              onClick={() => profile.close()}
            >
              {glyph('OK')}
              <span className="rb-lbl">{profile.closing ? '…' : 'OK'}</span>
            </button>
            <button
              type="button"
              className="rb-btn"
              disabled={profile.closing}
              title="Cancel — nothing is written"
              onClick={() => profile.cancel()}
            >
              <span className="rb-lbl">Cancel</span>
            </button>
          </div>
          <div className="ribbon-group-title">Close</div>
        </div>
      </div>
    )
  }
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
      {glyph(label)}
      <span className="rb-lbl">{label}</span>
    </button>
  )

  const roadmap = (label: string, reason: string) => (
    <button type="button" className="rb-btn rb-roadmap" disabled title={reason}>
      {glyph(label)}
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
            {glyph('Sketch view')}
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
          {roadmap('Vertical', 'In the Profile lane, vertical is PROPOSED automatically from what you draw (ADR/0044 A4); asserting one by hand arrives with BS-3')}
          {roadmap('Horizontal', 'In the Profile lane, horizontal is PROPOSED automatically from what you draw (ADR/0044 A4); asserting one by hand arrives with BS-3')}
        </div>
        <div className="ribbon-group-title">Constrain</div>
      </div>
      <div className="ribbon-group">
        <div className="ribbon-btns">
          {roadmap('Dimension', 'In the Profile lane, dimensions are DERIVED and shown grey (ADR/0044 A4); editing one as a strong fact arrives with BS-3')}
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
            {glyph('OK')}
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
