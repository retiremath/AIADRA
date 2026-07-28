# FreeCAD icons (vendored assets)

Command icons taken from the FreeCAD project — deliberately, to signal AIADRA's
relation to the FreeCAD/open-CAD ecosystem (Petre's direction, 2026-07-25).
These are generic COMMAND glyphs only; the FreeCAD logo (`freecad.svg`) and any
brand identity artwork are explicitly excluded — AIADRA does not imply
affiliation with or endorsement by the FreeCAD project.

## Provenance

- Source: https://github.com/FreeCAD/FreeCAD — `src/Gui/Icons/`, tag **1.1.1**
  (fetched 2026-07-25 from `raw.githubusercontent.com/FreeCAD/FreeCAD/1.1.1/...`).
- License: **LGPL-2.1-or-later**, per each file's embedded Dublin Core metadata
  (`<dc:rights>…<dc:title>FreeCAD LGPL2+</dc:title>…`) and the FreeCAD project
  LICENSE. The SVG files are kept as identifiable, unmodified, user-replaceable
  source-form assets with their embedded license/author metadata intact —
  the same artifact-level weak-copyleft compliance posture as the OCCT/PlaneGCS
  seams (ADR/0034; LGPL is inside the permissive/weak-copyleft dependency
  policy). Flagged on the ADR/0034 attorney-review list as the repo's first
  vendored third-party artwork.

## Files

| File | Source path (tag 1.1.1) | Used for |
|---|---|---|
| `document-new.svg` | `src/Gui/Icons/` | Quick Access + Home ribbon: New… |
| `document-open.svg` | `src/Gui/Icons/` | Quick Access + Home ribbon: Open Workspace… |
| `edit-undo.svg` | `src/Gui/Icons/` | Sketch ribbon: Undo |
| `Sketcher_CreatePolyline.svg` | `src/Mod/Sketcher/Gui/Resources/icons/geometry/` | Sketch ribbon: Contour |
| `Sketcher_CreateRectangle.svg` | `…/geometry/` | Sketch ribbon: Rectangle |
| `Sketcher_CreateCircle.svg` | `…/geometry/` | Sketch ribbon: Circle |
| `Sketcher_Create3PointArc.svg` | `…/geometry/` | Sketch ribbon: Arc (3-point via) |
| `Sketcher_ToggleConstruction.svg` | `…/geometry/` | Sketch ribbon: Constr. |
| `Constraint_Vertical.svg` | `…/constraints/` | Sketch ribbon: Vertical (roadmap) |
| `Constraint_Horizontal.svg` | `…/constraints/` | Sketch ribbon: Horizontal (roadmap) |
| `Constraint_Dimension.svg` | `…/constraints/` | Sketch ribbon: Dimension (roadmap) |
| `Sketcher_ViewSketch.svg` | `…/general/` | Sketch ribbon: Sketch view |
| `Sketcher_LeaveSketch.svg` | `…/general/` | Sketch ribbon: OK (commit) |

**The Model-ribbon suite (pass icons-1, 2026-07-28)** — 31 further glyphs
from `Mod/PartDesign/…/icons/`, `Mod/Part/…/icons/{booleans,tools}/`,
`Mod/Surface/…/icons/`, `Mod/Sketcher/…/icons/`, and `Gui/Icons/`, mapped
over the `IconKey` taxonomy in `src/commands/icons.tsx` (the mapping table
lives there; coverage law: faithful counterparts only — rib/trim/extend/
project/style/freestyle/component-interface and the small graphics-toolbar
chrome keep the monoline set). `Part_ProjectionOnSurface.svg` was DROPPED
at fetch for lacking embedded rights (rule 3).

Every file's embedded `dc:rights` was verified LGPL2+ at fetch (2026-07-28,
tag 1.1.1); a rights-lacking file is dropped per rule 3.

## Rules for growing this folder

1. Fetch from a PINNED FreeCAD tag; record the tag here.
2. Never modify the SVG content (metadata carries the license); resize at the
   consumer (`<img>`), not in the file.
3. Verify the embedded `dc:rights` says LGPL before adding a file; a file
   without embedded rights needs the wiki/artwork page checked and the finding
   recorded here.
4. Never add `freecad.svg` or other logo/brand artwork.
