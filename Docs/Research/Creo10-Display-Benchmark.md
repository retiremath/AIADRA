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

## 2. Display modes — the target taxonomy (ADR/0033 D7)

For each mode, capture on **one representative part** (ideally the imported gear/housing, same view/angle, so we can compare directly). Record the specs in our terms; no Creo image needed.

### 2.1 Shading **[CAPTURE]**
- Face colour / material feel (matte vs glossy); lighting (single key? ambient?).
- Any edges/silhouette drawn in *pure* shaded, or faces only?
- Background.

### 2.2 Shading With Edges **[CAPTURE]**
- Edge colour (Shaded Edge = black?) + **line weight** (px).
- Are **curved-surface silhouettes** drawn (the cylinder outline), or only sharp topological edges?
- Are **smooth tangent edges** (fillet-to-face) drawn?
- Anti-aliasing / crispness.

### 2.3 No Hidden (visible edges only, hidden removed) **[CAPTURE]**
- Which edges show: all *visible* topological edges + **curved-surface silhouettes**?
- Edge colour (Geometry navy?) + line weight.
- This is the mode where Creo's curved silhouette must appear — confirm it does.

### 2.4 Hidden Line (visible solid + hidden **dimmed**) **[CAPTURE]**
- Visible edges: colour + weight.
- **Hidden edges: dimmed how?** — grey (Hidden Line colour)? thinner? **dashed or solid**? This is the exact spec Petre asked for ("hidden lines should be dimmed").
- Are hidden silhouettes also shown dimmed?

### 2.5 Wireframe (all edges) **[CAPTURE]**
- Does Wireframe show hidden edges at the **same** weight/colour as visible (true see-through), or is that what Hidden Line is for? Clarify the Creo distinction between Wireframe vs Hidden Line.
- Silhouettes shown?

### 2.6 Cross-mode notes **[CAPTURE]**
- How mode switching feels (instant? any settle delay for hidden-line?).
- Default mode on model open.

## 3. Selection & pre-highlight (drives the topology-identity work, ADR/0033 D5) **[CAPTURE]**
- **Hover pre-highlight:** hover over an edge, then a face — what highlights (the entity under cursor? the whole part?), what colour (Preselection = orange?), and the style (colour swap? glow/thicken?).
- **Click selection:** select an edge, then a face — colour (Selected = green? Edge highlight = blue?), and what exactly gets the feedback (just the edge? the face quilt?).
- **Selection filters:** how Creo filters faces-only / edges-only / vertices-only, and how that's surfaced.
- **Multi-select** + de-select behaviour.

## 4. Background & environment — partly captured ✅
- **Light default = flat `#F7F9FA`** (`BLENDED_BACKGROUND no`). A **disabled** gradient is on file (top `#FBFBFC` → bottom `#EEF0F1`) — so Creo supports an optional vertical gradient, off by default. Our stopgap used `#E6E9EC` (a touch darker/greyer) — Creo's `#F7F9FA` is the exact target.
- **Dark default = flat `#303536`.**
- **[CAPTURE]** confirm there's no floor/grid/shadow in Creo's default viewport (clean background expected).

## 5. Navigation & views (interaction shell — ADR/0033 D9, later) **[CAPTURE — lower priority]**
- Navigation cube / spin-center behaviour; standard view orientations (iso/front/top/…); how view changes are triggered.

## Derived acceptance criteria (filled as captures land)

_To be written from §§1–4 once captured — these become the explicit "done" bar for the display-modes arc and feed the Display Representation contract (true edges + silhouettes + HLR + selection IDs)._
