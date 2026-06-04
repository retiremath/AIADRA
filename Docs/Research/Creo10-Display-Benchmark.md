# Creo 10 — Display & Selection benchmark capture

> **Purpose:** the ground-truth acceptance criteria for the AIADRA Studio Display & UX strand ([ADR/0033](../ADR/0033-studio-display-ux-vision.md) D1/D10 step 2). Creo 10 is the **behavioral reference + acceptance target**, NOT a clone — we record Creo's display/selection *behavior and quality in our own terms* (colors as values, line treatments, behaviors), and we do **not** embed Creo screenshots or copy its trade dress into this repo. Petre demos Creo 10 in chat; Claude transcribes the derived specs here.
>
> **Status:** capture in progress. Items marked **[CAPTURE]** await a Creo 10 demo/export.

## 1. Color palette — CAPTURED ✅ (Creo 10 color export, both themes)

Creo 10 ships two coordinated default schemes — **Light (Previous Creo Default)** and **Dark**. This proves the background↔line-colour coupling and validates the theme model ([ADR/0033](../ADR/0033-studio-display-ux-vision.md) D8): geometry flips near-black↔white with the background. Values converted from Creo's 0–100% export to 8-bit hex. Source: `syscol2.txt` (light, `COLOR_SCHEME 6`), `syscol3.txt` (dark, `COLOR_SCHEME 5`) — kept local, not committed.

### Light theme (`COLOR_SCHEME 6`; flat background — `BLENDED_BACKGROUND no`)

| Creo role | Hex | RGB | Our display use |
|---|---|---|---|
| Background | `#F7F9FA` | 247,249,250 | viewport background (near-white, cool) |
| Geometry | `#222226` | 34,34,38 | base model **edges** (near-black) |
| Hidden Line | `#C2C2CC` | 194,194,204 | **dimmed hidden edges** (light grey) |
| Shaded Edge | `#222226` | 34,34,38 | edge colour over shaded faces |
| Edge highlight | `#FF0000` | 255,0,0 | hovered/selected edge |
| Preselection highlight | `#90F000` | 144,240,0 | hover pre-highlight (yellow-green) |
| Selected | `#33CC4D` | 51,204,77 | selected entity (green) |
| Secondary selected | `#2EE5E5` | 46,229,229 | secondary selection (cyan) |
| Previewed geometry | `#FF9500` | 255,149,0 | preview (orange) |
| Primary highlight | `#990000` | 153,0,0 | primary highlight (dark red) |
| Curve / Letter | `#0000F0` | 0,0,240 | curves / text (blue) |
| Datum | `#996633` | 153,102,51 | datum (brown) |

### Dark theme (`COLOR_SCHEME 5`)

| Creo role | Hex | RGB | Our display use |
|---|---|---|---|
| Background | `#303536` | 48,53,54 | viewport background (dark grey) |
| Geometry | `#FFFFFF` | 255,255,255 | base model **edges** (white) |
| Hidden Line | `#78787D` | 120,120,125 | **dimmed hidden edges** (mid grey) |
| Shaded Edge | `#000000` | 0,0,0 | edge colour over shaded faces (black) |
| Edge highlight | `#1E91DC` | 30,145,220 | hovered/selected edge (blue) |
| Preselection highlight | `#FF640A` | 255,100,10 | hover pre-highlight (orange) |
| Selected | `#55FF1E` | 85,255,30 | selected entity (green) |
| Secondary selected | `#78FFDC` | 120,255,220 | secondary selection (light teal) |
| Previewed geometry | `#FFAF0A` | 255,175,10 | preview (amber) |
| Primary highlight | `#C83278` | 200,50,120 | primary highlight (magenta) |
| Curve | `#005FFF` | 0,95,255 | curves (blue) |
| Datum | `#785055` | 120,80,85 | datum (mauve) |

**Derivable now — the hidden-line spec:** Hidden Line mode = **visible edges in the Geometry colour + hidden edges in the Hidden Line colour** (light-grey `#C2C2CC` on light / mid-grey `#78787D` on dark) — i.e. a **dimmed grey**, NOT a faded geometry colour. Line *style* (solid vs dashed) isn't in the colour file → confirm from a mode screenshot (Creo's default Hidden Line is solid dimmed grey). **Implication for us:** both Light and Dark must be first-class themes in the Appearance system; the dim-hidden colour is a distinct theme entry, not a computed tint.

## 2. Display modes — CAPTURED ✅ (Creo 10 View → Display Style)

Creo's exact taxonomy is **six** modes (Ctrl+1..6), with these tooltip definitions:

| Creo mode | Key | Creo tooltip | Our target |
|---|---|---|---|
| Shading With Reflections | Ctrl+1 | shaded + reflections | **deferred** (D7/N4 — needs material/env policy) |
| Shading With Edges | Ctrl+2 | "Show the model shaded and with edges." | Shaded + edges |
| Shading | Ctrl+3 | "Show the model shaded." | Shaded |
| No Hidden | Ctrl+4 | "wireframe display, and do not show hidden lines." | No Hidden *(our stopgap mis-named this "Hidden line")* |
| Hidden Line | Ctrl+5 | "wireframe display, with the hidden lines shown lighter." | Hidden Line — true dimmed-hidden *(we lacked it)* |
| Wireframe | Ctrl+6 | "wireframe display." (all edges) | Wireframe — all edges equal *(we lacked the proper version)* |

**Captured behaviors (the acceptance bar):**
- **Hidden Line dimming = "shown lighter":** hidden edges are a **lighter tint of the edge colour, SOLID — not dashed.** (Matches the §1 Hidden Line colour entry; it's a lighter line, not a dash pattern.)
- **Real visible/hidden classification (HLR):** Wireframe shows **all** edges incl. the true *hidden/back* edges at equal weight; No Hidden **removes** the hidden set; Hidden Line **lightens** it. This is computed visible/hidden classification, not feature-edges-drawn-see-through. → the foundation needs **OCCT HLR** (ADR/0033 D6).
- **Tangent edges ARE drawn** — in Shading With Edges the fillet/round boundary edges (smooth *tangent* edges) appear. A dihedral-angle heuristic (our stopgap) cannot produce these. → needs **true BREP edges incl. tangent** (ADR/0033 D2/D5).
- **Curved-surface silhouettes/outlines ARE drawn** in the wireframe modes (rounded outer corners show their outline). → needs **HLR outline edges**, not only topological edges.
- **Line weight:** thin (~1 px), crisp/anti-aliased; uniform weight (no special heavier "outline" weight in these defaults).
- **Edge colour is theme/scheme-dependent:** in these captures wireframe edges render **blue** while Shading-With-Edges renders **dark** — so *shaded-edge colour* and *wireframe-edge colour* are likely **distinct theme entries**; the renderer drives edge colour from the active theme per mode (§1 is the configurable source of truth).
- **Shading (no edges):** smooth shaded faces, no edge lines; silhouette reads implicitly from the shape vs background.
- **[CAPTURE — minor]** mode-switch latency (instant vs a settle for HLR) + default mode on open.

**Net for us:** the corrected target set is **Shading · Shading With Edges · No Hidden · Hidden Line · Wireframe** (+ Reflections deferred). Our stopgap's 4 modes were mis-named and lacked true HLR; the foundation must provide HLR (visible/hidden/outline classification) + true BREP edges (incl. tangent).

## 3. Selection & pre-highlight — CAPTURED ✅ (drives the topology-identity work, ADR/0033 D5)

**Pre-highlight (hover) by entity type:**
- **Edge** → the edge line highlights in the **preselection colour (orange in this scheme)**, slightly thickened, with an **identity tooltip** — e.g. `Edge:F12(ROUND_5)`.
- **Surface / face** → an **orange boundary outline + a translucent fill tint** over the face.
- **Feature / Body** → the whole feature's edges highlight + a translucent fill — e.g. tooltip `F9(SHELL_1)` (the shell feature = the entire shelled solid).

**Selection identity model — the key finding for D5 / Codex1 B2:** Creo's selection identity is **feature-relative and feature-named**: `F12(ROUND_5)` = Feature 12, named `ROUND_5`; `F9(SHELL_1)` = Feature 9, `SHELL_1`. An edge is identified as *belonging to a feature* (the round), NOT as a raw mesh element. → This is precisely the **engine-minted, feature-anchored topology identity** ADR/0033 D5 requires. The Display Representation **selection payload** (D3) should return the engine's stable feature/topology ID + a human-readable name (a `<feature>:<entity-kind>:<id>`-style handle), never an `occt-import-js` mesh-triangle range. Creo's feature-naming (`ROUND_5`, `SHELL_1`) is a concrete model for our ID scheme.

**Selection filter** (bottom-right dropdown) scopes what is pickable: **Geometry → Edge / Surface / Datums / Curve / Quilt / Body / Annotation; Vertex; Sketch Region; Feature.** The active filter sets the hover/click target level (Surface was the active filter in the capture). → the interaction shell (ADR/0033 D9) needs a selection-filter control with at least **Edge / Surface / Vertex / Feature / Body** for v1.

**Colours:** preselection = orange in this active scheme — note this **differs from the "Light (Previous Creo Default)" export** (where preselection was `#90F000` yellow-green); Creo's *newer* default uses orange. Selected / edge-highlight per §1, all theme-configurable; the renderer drives every highlight colour from the active theme.

**[CAPTURE — minor]** click-select colour (green/blue) confirmation + multi-select / de-select behaviour.

## 4. Background & environment — partly captured ✅
- **Light default = flat `#F7F9FA`** (`BLENDED_BACKGROUND no`). A **disabled** gradient is on file (top `#FBFBFC` → bottom `#EEF0F1`) — so Creo supports an optional vertical gradient, off by default. Our stopgap used `#E6E9EC` (a touch darker/greyer) — Creo's `#F7F9FA` is the exact target.
- **Dark default = flat `#303536`.**
- **[CAPTURE]** confirm there's no floor/grid/shadow in Creo's default viewport (clean background expected).

## 5. Navigation & views (interaction shell — ADR/0033 D9, later) **[CAPTURE — lower priority]**
- Navigation cube / spin-center behaviour; standard view orientations (iso/front/top/…); how view changes are triggered.

## Derived acceptance criteria (the "done" bar the foundation + display-modes arcs inherit)

Synthesized from §§1–4 (colors ✅, modes ✅, selection ✅; minor confirmations pending):

1. **Themes:** two coordinated themes — Light (`#F7F9FA` bg, near-black edges) and Dark (`#303536` bg, white edges) — with line colours coupled to the background; configurable via the Appearance system (ADR/0033 D8). Background flat by default (optional gradient, off).
2. **Display modes (5 + reflections deferred):** Shading · Shading With Edges · No Hidden · Hidden Line · Wireframe (Ctrl+1..6 parity optional).
3. **Edges:** **true BREP edges including smooth tangent edges**; thin (~1 px), crisp/anti-aliased; colour from the active theme (shaded-edge vs wireframe-edge may be distinct entries).
4. **Hidden-line classification (HLR):** No Hidden = visible edges only; **Hidden Line = visible + hidden edges in a lighter (dimmed) solid line**; Wireframe = all edges. Curved-surface **silhouettes/outlines** drawn in the wireframe modes. Requires OCCT HLR visible/hidden/outline classification (ADR/0033 D6).
5. **Selection:** hover **pre-highlight** per entity — edge line (orange, thickened) / face (orange outline + translucent tint) / feature-body — each with an **identity tooltip**; click-select feedback in the theme's selected/edge-highlight colour. Selection returns an **engine-minted, feature-anchored topology ID + human name** (model: `F12(ROUND_5)`), per the Display Representation selection payload (D3) + identity rules (D5).
6. **Selection filter:** a control scoping pickable entities — at least Edge / Surface / Vertex / Feature / Body (ADR/0033 D9).
