/**
 * The navigator tab strip (Creo navigator benchmark; shell pass 1). Creo's
 * tree panel is TABBED — Model Tree / Folder Browser; ours is Model Tree /
 * Workspace. This is the strip only: the shell owns which tab is active and
 * what each tab shows (including its part-loaded / plane-pick auto-switching),
 * so the strip stays a pure, testable control.
 */
export type NavTabKey = 'model' | 'workspace'

const TABS: { key: NavTabKey; label: string }[] = [
  { key: 'model', label: 'Model Tree' },
  { key: 'workspace', label: 'Workspace' },
]

export function NavigatorTabs({
  active,
  onSelect,
}: {
  active: NavTabKey
  onSelect: (key: NavTabKey) => void
}) {
  return (
    <div className="nav-tabs" role="tablist" aria-label="Navigator">
      {TABS.map((t) => (
        <button
          key={t.key}
          type="button"
          role="tab"
          aria-selected={active === t.key}
          className={`nav-tab${active === t.key ? ' active' : ''}`}
          onClick={() => onSelect(t.key)}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}
