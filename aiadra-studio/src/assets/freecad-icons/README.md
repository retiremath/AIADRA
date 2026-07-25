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

| File | FreeCAD id | Author (embedded) | Used for |
|---|---|---|---|
| `document-new.svg` | `document-new` | [maxwxyz] | Quick Access: New… |
| `document-open.svg` | `document-open` | [maxwxyz] | Quick Access: Open Workspace… |

## Rules for growing this folder

1. Fetch from a PINNED FreeCAD tag; record the tag here.
2. Never modify the SVG content (metadata carries the license); resize at the
   consumer (`<img>`), not in the file.
3. Verify the embedded `dc:rights` says LGPL before adding a file; a file
   without embedded rights needs the wiki/artwork page checked and the finding
   recorded here.
4. Never add `freecad.svg` or other logo/brand artwork.
