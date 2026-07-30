/**
 * The profile status-line HINT (W-2) — a pure derivation of session state,
 * separated from the component so the file exporting a React component
 * exports only that (fast-refresh rule), and so the copy is testable as data.
 *
 * The chain grammar is gesture-driven (middle-click ends, first-point
 * closes, Esc abandons); this line is where those gestures are TAUGHT.
 */
import type { ProfileSessionState } from './profileSession'

export function profileHint(s: ProfileSessionState): string {
  const n = s.tool.pending.length
  switch (s.tool.kind) {
    case 'line':
      return n === 0
        ? 'Line chain: click to start'
        : 'click to chain · middle-click ends · click the first point to close · Esc abandons the run'
    case 'rectangle':
      return n === 0 ? 'Rectangle: click the first corner' : 'click the opposite corner'
    case 'circle':
      return n === 0 ? 'Circle: click the center' : 'click a rim point'
  }
}
