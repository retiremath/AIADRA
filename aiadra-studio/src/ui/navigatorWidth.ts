/**
 * The navigator width law (shell-1 S1-08): the sash clamps to the
 * `navigatorWidth` DESCRIPTOR's bounds — one authority shared with the settings
 * panel's validation, no literal twin anywhere. A pure module so the frame file
 * exports only its component (react-refresh) and the law is testable alone.
 */
import { DESCRIPTOR_BY_KEY } from '../settings/descriptors'

export function clampNavigatorWidth(candidate: number): number {
  const d = DESCRIPTOR_BY_KEY.navigatorWidth
  const min = d.min ?? 0
  const max = d.max ?? Number.POSITIVE_INFINITY
  return Math.min(max, Math.max(min, Math.round(candidate)))
}
