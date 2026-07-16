/**
 * The File menu (arc 20260714-1 D-H3 → arc 20260716-1 Codex2 B1) — now built
 * ON the shared `DropdownMenu` primitive, so File carries the ONE pinned menu
 * interaction contract (aria-haspopup/expanded, roving Arrow/Home/End focus
 * skipping disabled, Enter/Space + pointer activation with trigger-focus
 * restoration, Escape/outside-click) instead of a second bespoke menu.
 * Honest by the slice-A discipline: anything unbuilt is visibly disabled with
 * its reason as the tooltip.
 */
import { DropdownMenu, type MenuItem } from '../ui/DropdownMenu'

export interface FileMenuItem {
  label: string
  enabled: boolean
  title?: string
  onClick?: () => void
  /** Draw a separator line above this item. */
  sep?: boolean
}

export function FileMenu({ items }: { items: FileMenuItem[] }) {
  const menuItems: MenuItem[] = items.map((it) => ({
    key: it.label,
    label: it.label,
    disabledReason: it.enabled ? null : (it.title ?? 'unavailable'),
    title: it.enabled ? it.title : undefined,
    sepBefore: it.sep,
  }))
  return (
    <DropdownMenu
      label="File"
      className="file-menu"
      items={menuItems}
      onSelect={(key) => items.find((it) => it.label === key)?.onClick?.()}
    >
      File
    </DropdownMenu>
  )
}
