/**
 * Inline SVG icon map (arc 20260619-2 / 6b; Codex1 N5). No icon dependency —
 * the dependency-policy posture (ADR/0034) matters and the app carries none.
 * Keyed by a command's `iconKey`; swappable for a library later WITHOUT touching
 * the taxonomy. Accessible labels/tooltips come from the command label.
 */
import type { ReactNode } from 'react'

function svg(children: ReactNode): ReactNode {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  )
}

export const ICONS: Record<string, ReactNode> = {
  fit: svg(
    <>
      <path d="M2.5 5.5v-3h3M13.5 5.5v-3h-3M2.5 10.5v3h3M13.5 10.5v3h-3" />
      <rect x="5.5" y="5.5" width="5" height="5" rx="0.5" />
    </>,
  ),
  reset: svg(
    <>
      <path d="M3.2 8a4.8 4.8 0 1 1 1.4 3.4" />
      <path d="M2.5 11.2 3.2 8l3.2.7" />
    </>,
  ),
  grid: svg(
    <>
      <rect x="2.5" y="2.5" width="11" height="11" rx="1" />
      <path d="M6.2 2.5v11M9.8 2.5v11M2.5 6.2h11M2.5 9.8h11" />
    </>,
  ),
}
