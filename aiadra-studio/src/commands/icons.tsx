/**
 * THE icon map (arc 20260619-2 / 6b → pass icons-1, 2026-07-28): a MIXED
 * inline-monoline + vendored-asset map keyed by `IconKey` (the taxonomy's
 * typed union; a test asserts every key resolves). Two languages, one law:
 * FreeCAD glyphs (LGPL2+, vendored + attributed under
 * `src/assets/freecad-icons/` — the ADR/0034 compliance seam) replace the
 * monoline ONLY where a semantically FAITHFUL counterpart exists
 * (`FREECAD_GLYPH_KEYS` is the exact approved set, regression-pinned);
 * everything else stays 15px monoline `currentColor`. No icon npm
 * dependency. Accessible labels/tooltips come from command labels.
 */
import type { ReactNode } from 'react'
import type { IconKey } from '../authoring/ribbon'

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

export const ICONS = {
  // ---- display-shell toolbar (6b) ----
  fit: svg(
    <>
      <path d="M2.5 5.5v-3h3M13.5 5.5v-3h-3M2.5 10.5v3h3M13.5 10.5v3h-3" />
      <rect x="5.5" y="5.5" width="5" height="5" rx="0.5" />
    </>,
  ),
  'zoom-in': svg(
    <>
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.4 10.4 13.5 13.5M5 7h4M7 5v4" />
    </>,
  ),
  'zoom-out': svg(
    <>
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.4 10.4 13.5 13.5M5 7h4" />
    </>,
  ),
  reset: svg(
    <>
      <path d="M3.2 8a4.8 4.8 0 1 1 1.4 3.4" />
      <path d="M2.5 11.2 3.2 8l3.2.7" />
    </>,
  ),
  // ---- Operations / Get Data / Body ----
  regenerate: svg(
    <>
      <path d="M12.8 8a4.8 4.8 0 1 1-1.4-3.4" />
      <path d="M13.5 4.8 12.8 8l-3.2-.7" />
    </>,
  ),
  'get-data': svg(
    <>
      <path d="M8 2.5v6.5M5.5 6.5 8 9l2.5-2.5" />
      <path d="M2.5 10.5v3h11v-3" />
    </>,
  ),
  'boolean-ops': svg(
    <>
      <circle cx="6" cy="8" r="3.4" />
      <circle cx="10" cy="8" r="3.4" />
    </>,
  ),
  'split-trim-body': svg(
    <>
      <rect x="2.5" y="4" width="11" height="8" rx="1" />
      <path d="M10.5 2.5 5.5 13.5" />
    </>,
  ),
  'new-body': svg(
    <>
      <rect x="2.5" y="5.5" width="8" height="8" rx="1" />
      <path d="M12.2 2.5v4.4M10 4.7h4.4" />
    </>,
  ),
  // ---- Datum ----
  'datum-plane': svg(<path d="M4.5 4.5h9l-2 7h-9Z" />),
  'datum-axis': svg(
    <>
      <path d="M8 2.5v11" />
      <path d="M6 4.5 8 2.5l2 2M6 11.5l2 2 2-2" />
    </>,
  ),
  'datum-point': svg(
    <>
      <circle cx="8" cy="8" r="1.2" />
      <path d="M8 3v2M8 11v2M3 8h2M11 8h2" />
    </>,
  ),
  'datum-csys': svg(
    <>
      <path d="M3.5 12.5h9M3.5 12.5v-9M3.5 12.5l6.5-6.5" />
    </>,
  ),
  sketch: svg(
    <>
      <rect x="2.5" y="3.5" width="11" height="9" rx="1" strokeDasharray="2 1.4" opacity="0.7" />
      <path d="M5.5 10.5 9.7 6.3l1.5 1.5-4.2 4.2H5.5Z" />
    </>,
  ),
  // ---- Shapes ----
  extrude: svg(
    <>
      <path d="M3.5 6.5 8 4l4.5 2.5L8 9Z" />
      <path d="M3.5 6.5V11L8 13.5V9M12.5 6.5V11L8 13.5" />
    </>,
  ),
  revolve: svg(
    <>
      <ellipse cx="8" cy="5" rx="4.5" ry="1.8" />
      <path d="M3.5 5v6c0 1 2 1.8 4.5 1.8s4.5-.8 4.5-1.8V5" />
    </>,
  ),
  sweep: svg(
    <>
      <path d="M4.5 11.5c3.5 0 4.5-6 9-6" />
      <rect x="2.2" y="9.8" width="3.4" height="3.4" />
    </>,
  ),
  'swept-blend': svg(
    <>
      <path d="M4.5 11.5c3.5 0 4-6.5 8-7.2" />
      <rect x="2.2" y="9.8" width="3.4" height="3.4" />
      <circle cx="12.6" cy="4" r="1.7" />
    </>,
  ),
  // ---- Engineering ----
  hole: svg(
    <>
      <rect x="2.5" y="4.5" width="11" height="8" rx="1" />
      <circle cx="8" cy="8.5" r="2" />
    </>,
  ),
  round: svg(<path d="M4 13V8.5A4.5 4.5 0 0 1 8.5 4H13" />),
  chamfer: svg(<path d="M4 13V7.5L7.5 4H13" />),
  shell: svg(
    <>
      <path d="M2.5 4.5v8h11v-8" />
      <path d="M4.5 4.5v5.8h7V4.5" />
    </>,
  ),
  draft: svg(<path d="M3 13h10L10.5 3.5H6.5Z" />),
  rib: svg(
    <>
      <path d="M3.5 3v9.5H13" />
      <path d="M3.5 6 10 12.5" />
    </>,
  ),
  // ---- Pattern / Editing ----
  pattern: svg(
    <>
      <rect x="3" y="3" width="4" height="4" />
      <rect x="9" y="3" width="4" height="4" />
      <rect x="3" y="9" width="4" height="4" />
      <rect x="9" y="9" width="4" height="4" />
    </>,
  ),
  mirror: svg(
    <>
      <path d="M8 2.5v11" strokeDasharray="2 1.4" />
      <path d="M6 5 3 8l3 3ZM10 5l3 3-3 3Z" />
    </>,
  ),
  trim: svg(
    <>
      <path d="M2.5 9.5h11" />
      <path d="M9.5 4.5l-3 8" />
    </>,
  ),
  offset: svg(
    <>
      <path d="M3.5 13V6a2.5 2.5 0 0 1 2.5-2.5h7" />
      <path d="M6.5 13V9a2.5 2.5 0 0 1 2.5-2.5h4" opacity="0.6" />
    </>,
  ),
  extend: svg(
    <>
      <path d="M2.5 8h6.5" />
      <path d="M9 8h4.5" strokeDasharray="2 1.4" />
      <path d="M11.7 6.2 13.5 8l-1.8 1.8" />
    </>,
  ),
  project: svg(
    <>
      <circle cx="8" cy="4.3" r="1.9" />
      <path d="M8 6.8v3M6.6 8.4 8 9.8l1.4-1.4" />
      <path d="M3 12.5h10" />
    </>,
  ),
  thicken: svg(
    <>
      <path d="M3 10c3-4.5 7-4.5 10 0" />
      <path d="M3 13c3-4.5 7-4.5 10 0" opacity="0.6" />
    </>,
  ),
  solidify: svg(
    <>
      <rect x="3" y="3" width="10" height="10" rx="1" />
      <path d="M3 9l6-6M5 13l8-8M9 13l4-4" />
    </>,
  ),
  merge: svg(
    <>
      <rect x="2.5" y="5" width="5" height="6" />
      <rect x="8.5" y="5" width="5" height="6" />
    </>,
  ),
  intersect: svg(
    <>
      <rect x="3" y="3" width="8" height="8" rx="1" />
      <rect x="5" y="5" width="8" height="8" rx="1" />
    </>,
  ),
  split: svg(
    <>
      <rect x="2.5" y="4" width="11" height="8" rx="1" />
      <path d="M8 2.5v11" strokeDasharray="2 1.4" />
    </>,
  ),
  remove: svg(
    <>
      <rect x="2.5" y="4" width="11" height="8" rx="1" />
      <path d="M6.2 6.2l3.6 3.6M9.8 6.2l-3.6 3.6" />
    </>,
  ),
  unify: svg(
    <>
      <path d="M5.5 3H3v10h2.5M10.5 3H13v10h-2.5" />
      <path d="M6.5 8h3" />
    </>,
  ),
  // ---- Surfaces / Model Intent ----
  'boundary-blend': svg(
    <>
      <path d="M3 5c3 2 7 2 10 0M3 11c3 2 7 2 10 0" />
      <path d="M5 4.2v8M11 4.2v8" />
    </>,
  ),
  fill: svg(
    <>
      <rect x="3" y="3" width="10" height="10" rx="1" />
      <path d="M4.5 9.5c2-2.5 5-2.5 7 0" />
    </>,
  ),
  style: svg(
    <>
      <path d="M3.5 12c1.5-7 7.5-7 9-2" />
      <circle cx="3.5" cy="12" r="1.1" />
      <circle cx="12.5" cy="10" r="1.1" />
    </>,
  ),
  freestyle: svg(
    <>
      <circle cx="8" cy="8" r="5.5" />
      <path d="M2.5 8h11" />
      <ellipse cx="8" cy="8" rx="2.4" ry="5.5" />
    </>,
  ),
  'component-interface': svg(
    <>
      <path d="M2.5 8H6M10 8h3.5" />
      <path d="M6 5.5v5M10 5.5v5" />
    </>,
  ),
  // ---- graphics toolbar (arc 20260716-1 V-4) ----
  'display-style': svg(
    <>
      <path d="M2.5 8c1.8-3.2 9.2-3.2 11 0c-1.8 3.2-9.2 3.2-11 0Z" />
      <circle cx="8" cy="8" r="1.6" />
    </>,
  ),
  views: svg(
    <>
      <path d="M3.5 5.5 8 3l4.5 2.5v5L8 13l-4.5-2.5Z" />
      <path d="M3.5 5.5 8 8l4.5-2.5M8 8v5" />
    </>,
  ),
  'sel-filter': svg(
    <>
      <path d="M4.5 2.5 12 8.2 8.5 8.8 7 12.5Z" />
    </>,
  ),
  datums: svg(
    <>
      <path d="M2.5 6h6.5L10.5 11H4Z" />
      <path d="M8.5 3.5H13l-1.2 4" />
    </>,
  ),
  // ---- structural (menu family trigger + the responsive overflow) ----
  'menu-more': svg(
    <>
      <circle cx="4" cy="8" r="1" fill="currentColor" stroke="none" />
      <circle cx="8" cy="8" r="1" fill="currentColor" stroke="none" />
      <circle cx="12" cy="8" r="1" fill="currentColor" stroke="none" />
    </>,
  ),
  overflow: svg(<path d="M4.5 4.5 8 8l-3.5 3.5M8.5 4.5 12 8l-3.5 3.5" />),
} satisfies Record<IconKey, ReactNode> as Record<string, ReactNode>

// ---------------------------------------------------------------------------
// Pass icons-1 (2026-07-28, Petre's ruling): the FreeCAD glyph suite over the
// SAME IconKey taxonomy — exactly the "swappable without touching any
// taxonomy" seam this file promised. Coverage law: a glyph replaces the
// monoline ONLY where a semantically FAITHFUL counterpart exists (rib, trim,
// extend, project, style, freestyle, component-interface and the small
// graphics-toolbar chrome keep the monoline set — no invented mismatches).
// Provenance: LGPL2+ per-file-verified, pinned tag 1.1.1 — see
// src/assets/freecad-icons/README.md (a rights-lacking file is dropped:
// Part_ProjectionOnSurface was).
// ---------------------------------------------------------------------------
import icoRefresh from '../assets/freecad-icons/view-refresh.svg'
import icoImport from '../assets/freecad-icons/Std_Import.svg'
import icoBooleans from '../assets/freecad-icons/Part_Booleans.svg'
import icoSliceApart from '../assets/freecad-icons/Part_SliceApart.svg'
import icoBody from '../assets/freecad-icons/PartDesign_Body.svg'
import icoDatumPlane from '../assets/freecad-icons/PartDesign_Plane.svg'
import icoDatumLine from '../assets/freecad-icons/PartDesign_Line.svg'
import icoDatumPoint from '../assets/freecad-icons/PartDesign_Point.svg'
import icoDatumCsys from '../assets/freecad-icons/PartDesign_CoordinateSystem.svg'
import icoSketch from '../assets/freecad-icons/Sketcher_Sketch.svg'
import icoPad from '../assets/freecad-icons/PartDesign_Pad.svg'
import icoRevolution from '../assets/freecad-icons/PartDesign_Revolution.svg'
import icoSweep from '../assets/freecad-icons/Part_Sweep.svg'
import icoHole from '../assets/freecad-icons/PartDesign_Hole.svg'
import icoFillet from '../assets/freecad-icons/PartDesign_Fillet.svg'
import icoChamfer from '../assets/freecad-icons/PartDesign_Chamfer.svg'
import icoShell from '../assets/freecad-icons/PartDesign_Thickness.svg'
import icoDraft from '../assets/freecad-icons/PartDesign_Draft.svg'
import icoMirror from '../assets/freecad-icons/PartDesign_Mirrored.svg'
import icoOffset from '../assets/freecad-icons/Part_Offset.svg'
import icoThicken from '../assets/freecad-icons/Part_Thickness.svg'
import icoSolid from '../assets/freecad-icons/Part_MakeSolid.svg'
import icoFuse from '../assets/freecad-icons/Part_Fuse.svg'
import icoCommon from '../assets/freecad-icons/Part_Common.svg'
import icoSlice from '../assets/freecad-icons/Part_Slice.svg'
import icoFilling from '../assets/freecad-icons/Surface_Filling.svg'

const glyph = (src: string): ReactNode => (
  <img src={src} width={20} height={20} alt="" draggable={false} />
)

const FREECAD_GLYPHS = {
  regenerate: glyph(icoRefresh),
  'get-data': glyph(icoImport),
  'boolean-ops': glyph(icoBooleans),
  'split-trim-body': glyph(icoSliceApart),
  'new-body': glyph(icoBody),
  'datum-plane': glyph(icoDatumPlane),
  'datum-axis': glyph(icoDatumLine),
  'datum-point': glyph(icoDatumPoint),
  'datum-csys': glyph(icoDatumCsys),
  sketch: glyph(icoSketch),
  extrude: glyph(icoPad),
  revolve: glyph(icoRevolution),
  sweep: glyph(icoSweep),
  hole: glyph(icoHole),
  round: glyph(icoFillet),
  chamfer: glyph(icoChamfer),
  shell: glyph(icoShell),
  draft: glyph(icoDraft),
  mirror: glyph(icoMirror),
  offset: glyph(icoOffset),
  thicken: glyph(icoThicken),
  solidify: glyph(icoSolid),
  merge: glyph(icoFuse),
  intersect: glyph(icoCommon),
  split: glyph(icoSlice),
  fill: glyph(icoFilling),
} satisfies Partial<Record<IconKey, ReactNode>>

/** The EXACT approved glyph key set (Codex1 N1 — the coverage law's
 *  regression anchor; an accidental future override of a deliberately
 *  monoline key fails the icons test, not a reviewer's eye). */
export const FREECAD_GLYPH_KEYS = Object.keys(FREECAD_GLYPHS).sort() as readonly string[]

Object.assign(ICONS, FREECAD_GLYPHS)
