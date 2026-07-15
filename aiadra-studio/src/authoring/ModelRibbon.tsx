/**
 * The Model ribbon (arc 20260711-11 slice A → arc 20260715-1 D-R1) — the
 * Creo 10 Model tab, benchmarked never cloned: the WHOLE vocabulary renders
 * in benchmark groups, every command greyed or enabled by the ONE data-driven
 * three-state taxonomy (`ribbon.ts`). Tooltips carry the DERIVED reason —
 * state-disabled commands explain what the current state lacks; roadmap
 * commands name their strand honestly.
 */
import type { ReactNode } from 'react'
import {
  deriveCommandState,
  RIBBON_COMMANDS,
  RIBBON_GROUP_ORDER,
  type RibbonInputs,
} from './ribbon'

// --- minimal stroke icons (currentColor) for the working/near commands ---
const svg = (children: ReactNode) => (
  <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" strokeLinecap="round" aria-hidden="true">
    {children}
  </svg>
)
const ICONS: Record<string, ReactNode> = {
  sketch: svg(
    <>
      <rect x="3.5" y="4.5" width="13" height="11" rx="1" strokeDasharray="2 1.6" opacity="0.7" />
      <rect x="7" y="8" width="6" height="4" />
    </>,
  ),
  extrude: svg(
    <>
      <path d="M4 7 L10 4 L16 7 L10 10 Z" />
      <path d="M4 7 L4 13 L10 16 L10 10" />
      <path d="M16 7 L16 13 L10 16" />
    </>,
  ),
  revolve: svg(
    <>
      <ellipse cx="10" cy="6" rx="6" ry="2.2" />
      <path d="M4 6 L4 13 A6 2.2 0 0 0 16 13 L16 6" />
    </>,
  ),
  round: svg(<path d="M5 16 L5 10 A5 5 0 0 1 10 5 L16 5" />),
  chamfer: svg(<path d="M5 16 L5 9.5 L9.5 5 L16 5" />),
  hole: svg(
    <>
      <rect x="3.5" y="6" width="13" height="9" rx="1" />
      <circle cx="10" cy="10.5" r="2.4" />
    </>,
  ),
}

export function ModelRibbon({
  inputs,
  onStart,
}: {
  /** The taxonomy inputs (lane, gate, Part context, selection) — derived once
   *  by the Workbench per render. */
  inputs: RibbonInputs
  /** Dispatch a WORKING command by its taxonomy key. */
  onStart: (key: string) => void
}) {
  return (
    <div className="ribbon" role="toolbar" aria-label="Model ribbon">
      <div className="ribbon-tab">Model</div>
      {RIBBON_GROUP_ORDER.map((group) => {
        const commands = RIBBON_COMMANDS.filter((c) => c.group === group)
        if (commands.length === 0) return null
        return (
          <div key={group} className="ribbon-group">
            <div className="ribbon-btns">
              {commands.map((c) => {
                const st = c.derive(inputs)
                const disabled = st.state !== 'working'
                const title = st.state === 'working' ? `${c.label} — start` : st.reason
                return (
                  <button
                    key={c.key}
                    type="button"
                    className={`rb-btn${st.state === 'roadmap-disabled' ? ' rb-roadmap' : ''}`}
                    disabled={disabled}
                    title={title}
                    data-state={st.state}
                    onClick={() => !disabled && onStart(c.key)}
                  >
                    {ICONS[c.key] && <span className="rb-ico">{ICONS[c.key]}</span>}
                    <span className="rb-lbl">{c.label}</span>
                  </button>
                )
              })}
            </div>
            <div className="ribbon-group-title">{group}</div>
          </div>
        )
      })}
    </div>
  )
}

export { deriveCommandState }
