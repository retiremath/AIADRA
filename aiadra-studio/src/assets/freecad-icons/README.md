# FreeCAD icons (vendored assets)

Command icons taken from the FreeCAD project — deliberately, to signal AIADRA's
relation to the FreeCAD/open-CAD ecosystem (Petre's direction, 2026-07-25).
These are generic COMMAND glyphs only; the FreeCAD logo (`freecad.svg`) and any
brand identity artwork are explicitly excluded — AIADRA does not imply
affiliation with or endorsement by the FreeCAD project.

## Provenance

- Source: https://github.com/FreeCAD/FreeCAD — pinned tag **1.1.1** (all files;
  fetched via `raw.githubusercontent.com/FreeCAD/FreeCAD/1.1.1/<path>`).
- License: **LGPL-2.1-or-later**, per each file's embedded Dublin Core metadata
  (`<dc:rights>…<dc:title>FreeCAD LGPL2+</dc:title>…`) — VERIFIED PER FILE at
  fetch; a file lacking embedded rights is dropped (rule 3 below;
  `Part_ProjectionOnSurface.svg` was dropped on 2026-07-28 for this reason).
- Modification status: ALL files are UNMODIFIED, identifiable, user-replaceable
  source-form SVGs with their embedded license/author metadata intact — the
  artifact-level weak-copyleft posture of ADR/0034 (LGPL is inside the
  permissive/weak-copyleft dependency policy).
- **ADR/0034 Attorney-review item 7** records this suite (the repo's first
  vendored third-party artwork) as a release-prerequisite confirmation.
- **SBOM/NOTICES consequence**: the packaged renderer bundles these SVGs —
  the Licensing-implementation arc's `THIRD-PARTY-NOTICES` and SBOM must carry
  a FreeCAD-icons entry (LGPL-2.1-or-later, tag 1.1.1, this manifest).

## Manifest (exact upstream path at tag 1.1.1; all unmodified)

| File | Upstream path | Fetched | Used for |
|---|---|---|---|
| `document-new.svg` | `src/Gui/Icons/document-new.svg` | 2026-07-25 | QAT + Home ribbon: New… |
| `document-open.svg` | `src/Gui/Icons/document-open.svg` | 2026-07-25 | QAT + Home ribbon: Open Workspace… |
| `edit-undo.svg` | `src/Gui/Icons/edit-undo.svg` | 2026-07-28 | Sketch ribbon: Undo |
| `Sketcher_CreatePolyline.svg` | `src/Mod/Sketcher/Gui/Resources/icons/geometry/Sketcher_CreatePolyline.svg` | 2026-07-28 | Sketch ribbon: Contour |
| `Sketcher_CreateRectangle.svg` | `src/Mod/Sketcher/Gui/Resources/icons/geometry/Sketcher_CreateRectangle.svg` | 2026-07-28 | Sketch ribbon: Rectangle |
| `Sketcher_CreateCircle.svg` | `src/Mod/Sketcher/Gui/Resources/icons/geometry/Sketcher_CreateCircle.svg` | 2026-07-28 | Sketch ribbon: Circle |
| `Sketcher_Create3PointArc.svg` | `src/Mod/Sketcher/Gui/Resources/icons/geometry/Sketcher_Create3PointArc.svg` | 2026-07-28 | Sketch ribbon: Arc |
| `Sketcher_ToggleConstruction.svg` | `src/Mod/Sketcher/Gui/Resources/icons/geometry/Sketcher_ToggleConstruction.svg` | 2026-07-28 | Sketch ribbon: Constr. |
| `Constraint_Vertical.svg` | `src/Mod/Sketcher/Gui/Resources/icons/constraints/Constraint_Vertical.svg` | 2026-07-28 | Sketch ribbon: Vertical (roadmap) |
| `Constraint_Horizontal.svg` | `src/Mod/Sketcher/Gui/Resources/icons/constraints/Constraint_Horizontal.svg` | 2026-07-28 | Sketch ribbon: Horizontal (roadmap) |
| `Constraint_Dimension.svg` | `src/Mod/Sketcher/Gui/Resources/icons/constraints/Constraint_Dimension.svg` | 2026-07-28 | Sketch ribbon: Dimension (roadmap) |
| `Sketcher_ViewSketch.svg` | `src/Mod/Sketcher/Gui/Resources/icons/general/Sketcher_ViewSketch.svg` | 2026-07-28 | Sketch ribbon: Sketch view |
| `Sketcher_LeaveSketch.svg` | `src/Mod/Sketcher/Gui/Resources/icons/general/Sketcher_LeaveSketch.svg` | 2026-07-28 | Sketch ribbon: OK |
| `Sketcher_Sketch.svg` | `src/Mod/Sketcher/Gui/Resources/icons/Sketcher_Sketch.svg` | 2026-07-28 | Model ribbon: Sketch |
| `view-refresh.svg` | `src/Gui/Icons/view-refresh.svg` | 2026-07-28 | Model ribbon: Regenerate |
| `Std_Import.svg` | `src/Gui/Icons/Std_Import.svg` | 2026-07-28 | Model ribbon: Get Data |
| `PartDesign_Pad.svg` | `src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Pad.svg` | 2026-07-28 | Model ribbon: Extrude |
| `PartDesign_Revolution.svg` | `src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Revolution.svg` | 2026-07-28 | Model ribbon: Revolve |
| `Part_Sweep.svg` | `src/Mod/Part/Gui/Resources/icons/tools/Part_Sweep.svg` | 2026-07-28 | Model ribbon: Sweep |
| `PartDesign_Hole.svg` | `src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Hole.svg` | 2026-07-28 | Model ribbon: Hole |
| `PartDesign_Fillet.svg` | `src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Fillet.svg` | 2026-07-28 | Model ribbon: Round |
| `PartDesign_Chamfer.svg` | `src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Chamfer.svg` | 2026-07-28 | Model ribbon: Chamfer |
| `PartDesign_Thickness.svg` | `src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Thickness.svg` | 2026-07-28 | Model ribbon: Shell |
| `PartDesign_Draft.svg` | `src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Draft.svg` | 2026-07-28 | Model ribbon: Draft |
| `PartDesign_Mirrored.svg` | `src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Mirrored.svg` | 2026-07-28 | Model ribbon: Mirror |
| `PartDesign_Body.svg` | `src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Body.svg` | 2026-07-28 | Model ribbon: New Body |
| `PartDesign_Plane.svg` | `src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Plane.svg` | 2026-07-28 | Model ribbon: Plane |
| `PartDesign_Line.svg` | `src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Line.svg` | 2026-07-28 | Model ribbon: Axis |
| `PartDesign_Point.svg` | `src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Point.svg` | 2026-07-28 | Model ribbon: Point |
| `PartDesign_CoordinateSystem.svg` | `src/Mod/PartDesign/Gui/Resources/icons/PartDesign_CoordinateSystem.svg` | 2026-07-28 | Model ribbon: Coordinate System |
| `Part_Booleans.svg` | `src/Mod/Part/Gui/Resources/icons/booleans/Part_Booleans.svg` | 2026-07-28 | Model ribbon: Body Ops |
| `Part_Fuse.svg` | `src/Mod/Part/Gui/Resources/icons/booleans/Part_Fuse.svg` | 2026-07-28 | Model ribbon: Merge |
| `Part_Common.svg` | `src/Mod/Part/Gui/Resources/icons/booleans/Part_Common.svg` | 2026-07-28 | Model ribbon: Intersect |
| `Part_Slice.svg` | `src/Mod/Part/Gui/Resources/icons/booleans/Part_Slice.svg` | 2026-07-28 | Model ribbon: Split |
| `Part_SliceApart.svg` | `src/Mod/Part/Gui/Resources/icons/booleans/Part_SliceApart.svg` | 2026-07-28 | Model ribbon: Split/Trim Body |
| `Part_Offset.svg` | `src/Mod/Part/Gui/Resources/icons/tools/Part_Offset.svg` | 2026-07-28 | Model ribbon: Offset |
| `Part_Thickness.svg` | `src/Mod/Part/Gui/Resources/icons/tools/Part_Thickness.svg` | 2026-07-28 | Model ribbon: Thicken |
| `Part_MakeSolid.svg` | `src/Mod/Part/Gui/Resources/icons/tools/Part_MakeSolid.svg` | 2026-07-28 | Model ribbon: Solidify |
| `Surface_Filling.svg` | `src/Mod/Surface/Gui/Resources/icons/Surface_Filling.svg` | 2026-07-28 | Model ribbon: Fill |

(The Codex1-B1 reverted assets — `PartDesign_AdditiveLoft`, `PartDesign_LinearPattern`,
`Part_Cut`, `Part_Refine_Shape`, `Surface_Sections` — were REMOVED from the repo:
their commands keep the monoline set per the coverage law in `src/commands/icons.tsx`.)

## Rules for growing this folder

1. Fetch from a PINNED FreeCAD tag; record the exact upstream path + date here.
2. Never modify the SVG content (metadata carries the license); resize at the
   consumer (`<img>`), not in the file.
3. Verify the embedded `dc:rights` says LGPL before adding a file; a file
   without embedded rights is DROPPED (enforced: `Part_ProjectionOnSurface.svg`).
4. Never add `freecad.svg` or other logo/brand artwork.
5. A glyph maps to a command ONLY with a semantically faithful counterpart
   (the coverage law + its regression in `src/commands/icons.test.tsx`).
