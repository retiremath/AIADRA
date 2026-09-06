/**
 * The navigator show/hide control (Creo: the status bar's bottom-left
 * navigator button; shell-1 S1-15, 2026-09-05). Flips the `navigatorVisible`
 * setting — the SAME key `NavigatorFrame` reads in both app states — so a
 * dismissed navigator comes back from exactly where Creo's does, at Home and
 * in modeling alike, and the choice survives a restart (ADR/0033 D8 local
 * chrome). The glyph is an original monoline panel-with-column: no third-party
 * material (ADR/0045 D8.5), and outside the icons-1 coverage law, which pins
 * ribbon command glyphs only.
 */
import { useSetting } from '../settings/useSettings'

export function NavigatorToggle() {
  const [visible, setVisible] = useSetting('navigatorVisible')
  const on = visible === true
  const label = on ? 'Hide the navigator' : 'Show the navigator'
  return (
    <button
      type="button"
      className={`nav-toggle${on ? ' on' : ''}`}
      aria-pressed={on}
      aria-label={label}
      title={label}
      onClick={() => setVisible(!on)}
    >
      <svg width="16" height="14" viewBox="0 0 16 14" aria-hidden="true" focusable="false">
        <rect x="1" y="1" width="14" height="12" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.2" />
        {/* the navigator column: solid when shown, dashed outline when hidden */}
        <rect
          x="1"
          y="1"
          width="5"
          height="12"
          rx="1.5"
          fill={on ? 'currentColor' : 'none'}
          stroke="currentColor"
          strokeWidth="1.2"
          strokeDasharray={on ? undefined : '1.6 1.4'}
        />
      </svg>
    </button>
  )
}
