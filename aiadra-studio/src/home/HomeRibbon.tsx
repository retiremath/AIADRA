/**
 * The Home-state ribbon (arc 20260714-1; D-H3 — Creo's contextual ribbon).
 * Shown when no model is open (the `home` app state); the Model ribbon shows in
 * `modeling`. Reuses the ribbon chrome (.ribbon/.rb-btn) so the two tabs read
 * as one system. Data-management commands only — no authoring here.
 *
 * Icons: FreeCAD command glyphs (LGPL2+, src/assets/freecad-icons/README.md)
 * — the same vendored files the Quick Access bar uses, at ribbon size.
 */
import iconNew from '../assets/freecad-icons/document-new.svg'
import iconOpen from '../assets/freecad-icons/document-open.svg'

const IconNew = <img src={iconNew} width={22} height={22} alt="" draggable={false} />
const IconOpen = <img src={iconOpen} width={22} height={22} alt="" draggable={false} />

export function HomeRibbon({
  onNewPart,
  onOpenWorkspace,
  canOpenWorkspace,
}: {
  onNewPart: () => void
  onOpenWorkspace: () => void
  canOpenWorkspace: boolean
}) {
  // The tab title lives in the shell's .ribbon-tabs strip (Creo grammar) —
  // this component is the ribbon CONTENT row only.
  return (
    <div className="ribbon" role="toolbar" aria-label="Home ribbon">
      <div className="ribbon-group">
        <div className="ribbon-btns">
          <button type="button" className="rb-btn" title="Create a new object (Part, …)" onClick={onNewPart}>
            <span className="rb-ico">{IconNew}</span>
            <span className="rb-lbl">New</span>
          </button>
          <button
            type="button"
            className="rb-btn"
            disabled={!canOpenWorkspace}
            title={canOpenWorkspace ? 'Open an AIADRA workspace folder' : 'Available in the desktop app'}
            onClick={onOpenWorkspace}
          >
            <span className="rb-ico">{IconOpen}</span>
            <span className="rb-lbl">Open</span>
          </button>
        </div>
        <div className="ribbon-group-title">Data</div>
      </div>
    </div>
  )
}
