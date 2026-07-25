/**
 * The Quick Access Toolbar (shell pass 1; Creo 10 QAT benchmark, 2026-07-25).
 * Creo's very first bar: a small always-visible strip of pinned commands with
 * a customize dropdown (check/uncheck pinnable commands, "Show Below the
 * Ribbon"). Ours lives in the TITLE BAR by default and moves under the ribbon
 * when `qatBelowRibbon` is set — both placements render THIS one component.
 *
 * Architecture: the QAT owns NO command logic — it renders `QatCommand`
 * entries whose enabled/title/onClick come from the same handlers as the File
 * menu (one behavior, two surfaces). Visibility + placement are TYPED SETTINGS
 * (schema-as-data, persisted, validated — never ad-hoc local state). The
 * customize menu is the ONE shared DropdownMenu primitive; its checkbox
 * affordance is the primitive's `current` mark. Divergence-by-design from
 * Creo: the menu closes on toggle (the shared one-menu contract wins over
 * Creo's stay-open checkbox list).
 *
 * Icons: FreeCAD command glyphs (LGPL2+, see src/assets/freecad-icons/README.md)
 * — the pilot of the FreeCAD-icon adoption Petre directed; commands without a
 * vendored glyph fall back to their label initial.
 */
import { DropdownMenu, type MenuItem } from './DropdownMenu'
import { useSetting } from '../settings/useSettings'
import iconNew from '../assets/freecad-icons/document-new.svg'
import iconOpen from '../assets/freecad-icons/document-open.svg'

/** The pinnable catalogue: stable key ↔ its visibility setting. */
export const QAT_CATALOGUE = [
  { key: 'new', setting: 'qatShowNew', label: 'New…' },
  { key: 'open', setting: 'qatShowOpen', label: 'Open Workspace…' },
  { key: 'import', setting: 'qatShowImport', label: 'Import reference geometry…' },
  { key: 'close', setting: 'qatShowClose', label: 'Close' },
] as const

export type QatKey = (typeof QAT_CATALOGUE)[number]['key']

const QAT_ICONS: Partial<Record<QatKey, string>> = {
  new: iconNew,
  open: iconOpen,
}

export interface QatCommand {
  key: QatKey
  /** null = enabled; a string = disabled with THIS reason (title tooltip). */
  disabledReason: string | null
  /** Tooltip for the ENABLED command. */
  title: string
  onClick: () => void
}

export function QuickAccessBar({ commands }: { commands: QatCommand[] }) {
  const [belowRibbon, setBelowRibbon] = useSetting('qatBelowRibbon')
  // one explicit useSetting per catalogue row (rules-of-hooks: no hooks in
  // loops) — order matches QAT_CATALOGUE
  const visibility = [
    useSetting('qatShowNew'),
    useSetting('qatShowOpen'),
    useSetting('qatShowImport'),
    useSetting('qatShowClose'),
  ]

  const byKey = new Map(commands.map((c) => [c.key, c]))

  const customizeItems: MenuItem[] = [
    ...QAT_CATALOGUE.map((c, i) => ({
      key: c.key,
      label: c.label,
      current: visibility[i][0] === true,
      title: 'Show or hide this command in the Quick Access bar',
    })),
    {
      key: 'below-ribbon',
      label: 'Show Below the Ribbon',
      current: belowRibbon === true,
      sepBefore: true,
    },
    {
      key: 'more-commands',
      label: 'More Commands…',
      disabledReason: 'Arrives with the options dialog (roadmap)',
      sepBefore: true,
    },
  ]

  const onCustomize = (key: string) => {
    if (key === 'below-ribbon') {
      setBelowRibbon(!(belowRibbon === true))
      return
    }
    const i = QAT_CATALOGUE.findIndex((c) => c.key === key)
    if (i >= 0) visibility[i][1](!(visibility[i][0] === true))
  }

  return (
    <div className="qat" role="toolbar" aria-label="Quick Access">
      {QAT_CATALOGUE.map((c, i) => {
        if (visibility[i][0] !== true) return null
        const cmd = byKey.get(c.key)
        if (!cmd) return null
        const icon = QAT_ICONS[c.key]
        return (
          <button
            key={c.key}
            type="button"
            className="qat-btn"
            aria-label={c.label}
            title={cmd.disabledReason ?? cmd.title}
            disabled={cmd.disabledReason !== null}
            onClick={cmd.onClick}
          >
            {icon ? (
              <img src={icon} alt="" width={16} height={16} draggable={false} />
            ) : (
              <span aria-hidden="true">{c.label[0]}</span>
            )}
          </button>
        )
      })}
      <DropdownMenu
        label="Customize Quick Access Toolbar"
        items={customizeItems}
        onSelect={onCustomize}
        className="qat-customize"
      >
        <span aria-hidden="true">▾</span>
      </DropdownMenu>
    </div>
  )
}
