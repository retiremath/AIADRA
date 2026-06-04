# Creo 10 — Display & Selection benchmark capture

> **Purpose:** the ground-truth acceptance criteria for the AIADRA Studio Display & UX strand ([ADR/0033](../ADR/0033-studio-display-ux-vision.md) D1/D10 step 2). Creo 10 is the **behavioral reference + acceptance target**, NOT a clone — we record Creo's display/selection *behavior and quality in our own terms* (colors as values, line treatments, behaviors), and we do **not** embed Creo screenshots or copy its trade dress into this repo. Petre demos Creo 10 in chat; Claude transcribes the derived specs here.
>
> **Status:** capture in progress. Items marked **[CAPTURE]** await a Creo 10 demo/export.

## 1. Color palette (from the Creo 10 Options → System Appearance → Global Colors → Graphics)

The Options dialog screenshot gave the **default palette by family**. The **exact RGB is pending the Creo color export** (Options → Colors → **Export** produces a config file with precise values).

| Creo color role | Family (from screenshot) | Exact RGB | Our display use |
|---|---|---|---|
| **Background** | very light grey | **[CAPTURE]** | viewport background |
| **Geometry** | dark navy/blue | **[CAPTURE]** | base model edge / curve colour |
| **Hidden Line** | mid grey | **[CAPTURE]** | dimmed hidden edges (Hidden Line mode) |
| **Shaded Edge** | black | **[CAPTURE]** | edge colour over shaded faces (Shading With Edges) |
| **Edge highlight** | bright blue | **[CAPTURE]** | hovered/selected edge feedback |
| **Preselection highlight** | orange | **[CAPTURE]** | hover pre-highlight |
| **Selected** | bright green | **[CAPTURE]** | selected entity |
| **Secondary selected** | teal | **[CAPTURE]** | secondary selection |
| **Datum** | dark red/maroon | **[CAPTURE]** | datum features (later) |
| **Sketch / Curve** | cyan / blue | **[CAPTURE]** | sketch entities (later) |

> **Highest-value single capture:** the Creo color **Export** file → fills the whole RGB column at once.

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

## 4. Background & environment **[CAPTURE]**
- Petre's preferred background (he asked for light grey/cream): flat or gradient? If gradient, the two colours.
- Any floor/grid/shadow in Creo's default, or clean background?

## 5. Navigation & views (interaction shell — ADR/0033 D9, later) **[CAPTURE — lower priority]**
- Navigation cube / spin-center behaviour; standard view orientations (iso/front/top/…); how view changes are triggered.

## Derived acceptance criteria (filled as captures land)

_To be written from §§1–4 once captured — these become the explicit "done" bar for the display-modes arc and feed the Display Representation contract (true edges + silhouettes + HLR + selection IDs)._
