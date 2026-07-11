/**
 * The Model ribbon (arc 20260711-11 / slice A — the Creo-shaped shell). A top
 * command band, benchmarked on Creo 10's ribbon (ADR/0033 D1 / D9), that is the
 * front door to feature authoring: a "Model" tab with grouped feature buttons
 * (Datum · Shapes · Engineering). Clicking a feature starts a `feature`
 * operation session (featureSession.ts) — the FeatureDashboard is its editor.
 *
 * Honesty (Creo greys unavailable commands): only the features that have a
 * working dashboard are enabled. Sketch-as-its-own-step (the stepwise flow) and
 * fillet/chamfer (selection→target) are the next slices — they render greyed
 * with a tooltip so the workflow reads as intentional, not missing.
 *
 * This is a self-contained authoring surface. It deliberately does NOT route
 * through the view-command taxonomy (commands/registry `operations` slot): that
 * taxonomy's CommandActions/CommandContext are scoped to display/selection
 * state, and folding authoring into it would couple every keyboard/toolbar/menu
 * consumer to authoring. Folding features into the reserved `operations` group
 * (for shortcuts + the context menu) is a clean follow-up once the four ops
 * stabilize.
 */
import type { ReactNode } from 'react'
import { EXTRUDE_DEFAULTS } from './FeatureDashboard'
import { useFeatureSession, type FeatureSessionStore } from './featureSession'

type RibbonFeature = {
  kind: string
  label: string
  group: 'Datum' | 'Shapes' | 'Engineering'
  icon: ReactNode
  /** Present + a working dashboard → enabled. */
  defaults?: Record<string, number>
  /** Tooltip shown when the feature has no dashboard yet. */
  soon?: string
}

// --- minimal stroke icons (currentColor), Creo-ribbon scale ---
const svg = (children: ReactNode) => (
  <svg viewBox="0 0 20 20" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" strokeLinecap="round" aria-hidden="true">
    {children}
  </svg>
)
const IconSketch = svg(
  <>
    <rect x="3.5" y="4.5" width="13" height="11" rx="1" strokeDasharray="2 1.6" opacity="0.7" />
    <rect x="7" y="8" width="6" height="4" />
  </>,
)
const IconExtrude = svg(
  <>
    <path d="M4 7 L10 4 L16 7 L10 10 Z" />
    <path d="M4 7 L4 13 L10 16 L10 10" />
    <path d="M16 7 L16 13 L10 16" />
  </>,
)
const IconFillet = svg(<path d="M5 16 L5 10 A5 5 0 0 1 10 5 L16 5" />)
const IconChamfer = svg(<path d="M5 16 L5 9.5 L9.5 5 L16 5" />)

const MODEL_FEATURES: RibbonFeature[] = [
  { kind: 'sketch', label: 'Sketch', group: 'Datum', icon: IconSketch, soon: 'Standalone sketch step — arrives with the stepwise Sketch→Extrude flow (next slice)' },
  { kind: 'extrude', label: 'Extrude', group: 'Shapes', icon: IconExtrude, defaults: EXTRUDE_DEFAULTS },
  { kind: 'fillet', label: 'Fillet', group: 'Engineering', icon: IconFillet, soon: 'Round an edge — pick an edge → radius (next slice)' },
  { kind: 'chamfer', label: 'Chamfer', group: 'Engineering', icon: IconChamfer, soon: 'Bevel an edge — pick an edge → distance (next slice)' },
]

const GROUP_ORDER: RibbonFeature['group'][] = ['Datum', 'Shapes', 'Engineering']

export function ModelRibbon({ store }: { store: FeatureSessionStore }) {
  const s = useFeatureSession(store)
  const sessionOpen = s.active // one feature at a time — finish/cancel the current op first

  return (
    <div className="ribbon" role="toolbar" aria-label="Model ribbon">
      <div className="ribbon-tab">Model</div>
      {GROUP_ORDER.map((group) => (
        <div key={group} className="ribbon-group">
          <div className="ribbon-btns">
            {MODEL_FEATURES.filter((f) => f.group === group).map((f) => {
              const available = !!f.defaults
              const disabled = !available || sessionOpen
              const title = f.soon
                ? f.soon
                : sessionOpen
                  ? 'Finish or cancel the current operation first'
                  : `${f.label} a feature`
              return (
                <button
                  key={f.kind}
                  type="button"
                  className="rb-btn"
                  disabled={disabled}
                  title={title}
                  onClick={() => available && store.start(f.kind, f.defaults!)}
                >
                  <span className="rb-ico">{f.icon}</span>
                  <span className="rb-lbl">{f.label}</span>
                </button>
              )
            })}
          </div>
          <div className="ribbon-group-title">{group}</div>
        </div>
      ))}
    </div>
  )
}
