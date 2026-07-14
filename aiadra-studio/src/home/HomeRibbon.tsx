/**
 * The Home-state ribbon (arc 20260714-1; D-H3 — Creo's contextual ribbon).
 * Shown when no model is open (the `home` app state); the Model ribbon shows in
 * `modeling`. Reuses the ribbon chrome (.ribbon/.rb-btn) so the two tabs read
 * as one system. Data-management commands only — no authoring here.
 */
import type { ReactNode } from 'react'

const svg = (children: ReactNode) => (
  <svg viewBox="0 0 20 20" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" strokeLinecap="round" aria-hidden="true">
    {children}
  </svg>
)
const IconNew = svg(
  <>
    <path d="M6 3.5 H11.5 L14.5 6.5 V16.5 H6 Z" />
    <path d="M11.5 3.5 V6.5 H14.5" />
  </>,
)
const IconOpen = svg(
  <>
    <path d="M3.5 6.5 V4.5 H8 L9.5 6 H16.5 V8" />
    <path d="M3.5 6.5 H16.5 L15 15.5 H5 Z" />
  </>,
)

export function HomeRibbon({
  onNewPart,
  onOpenWorkspace,
  canOpenWorkspace,
}: {
  onNewPart: () => void
  onOpenWorkspace: () => void
  canOpenWorkspace: boolean
}) {
  return (
    <div className="ribbon" role="toolbar" aria-label="Home ribbon">
      <div className="ribbon-tab">Home</div>
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
