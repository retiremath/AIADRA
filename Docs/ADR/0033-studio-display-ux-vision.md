# ADR/0033 — AIADRA Studio Display & UX: vision + scope

## Frontmatter

- **Status:** Accepted — 2026-06-03 (arc 20260603-3; two-round convergence Claude1 + Codex1 / Claude2). Vision/scope ADR — north star + roadmap; no code in this arc.
- **What it is:** the **vision and scope for the Display & UX strand** of AIADRA Studio — a first-class, multi-arc, years-horizon strand benchmarked to **Creo 10**. Elevates the seeds in [ADR/0032](0032-aiadra-studio-scope.md) D4/D8/D9/D10 into a designed foundation.
- **Driven by Petre** (a long-time CAD user, 2026-06-03): UX is **existential** for a CAD system's adoption; Creo 10 is the explicit benchmark (he holds a license; we demo against it). Approached systematically across sessions, Codex-shaped from the start.
- **No schema / bundle / `aiadra-core` / Glossary change.** A Studio UI strand.
- **Gating:** the **rendering foundation arc is gated on the Licensing ADR** (this strand deepens OCCT usage; the AGPLv3 + CLA + permissive/LGPL-only-dependency direction is in research).

## §0 — What this ADR does

The milestone-1b viewport spike ([`baf52d2`](../../aiadra-studio/src/Viewport.tsx), the "stopgap display baseline") was live-tuned and fast. It did its real job — it **discovered the requirements** (a draw-mode taxonomy, silhouettes, hidden-line dimming, theming, view toggles) — then surfaced the symptoms that matter: dashed/broken edges at grazing angles, silhouettes that miss surface-against-surface contours, no wireframe silhouettes, a mode taxonomy that doesn't match Creo. **Those are not bugs to patch; they are the ceiling of a screen-space approach** (a dihedral-angle `EdgesGeometry` heuristic + a depth-discontinuity post-process).

This ADR pins the north star, the architecture, and the roadmap for reaching Creo-grade display and interaction, and makes the central decision explicit: **Creo-grade display, hidden-line, silhouettes, and topological selection all require the same thing — a BREP-derived display representation with true edges and explicit, engine-owned topology identity — not screen-space approximation.**

## Decisions

### D1. Creo 10 is the benchmark — as a behavioral reference, not a clone
Creo 10 is the **named behavioral reference and acceptance target** for display quality, interaction affordances, and CAD terminology. **Mechanism:** for each arc, Petre demos the exact Creo 10 behavior (a *benchmark capture packet* — screenshots / short clips); we record it as that arc's **acceptance criteria**; Codex reviews our design *against* it. **Guardrail (per [Manifesto](../Manifesto.md)):** AIADRA is *inspired by, not imitating* — we benchmark quality, behavior, and terminology where useful; we do **not** copy trade dress, proprietary workflows wholesale, or layout for its own sake. Benchmark the *feel and correctness*, not the pixels.

### D2. The display foundation is BREP-derived true topology — not screen-space approximation
The screen-space stopgap is **retired as the foundation** (kept only as a labeled regression baseline, D11). The rendering foundation, the topology foundation, and the selection foundation are **one and the same**: true BREP edges + face/edge/vertex IDs + analytic classification unblock crisp complete edges, proper hidden-line/silhouette, *and* topological selection. **Milestone 2 (topological selection, ADR/0032 D8) merges into this strand's foundation arc.**

### D3. The central deliverable is a versioned **Display Representation contract** (Codex1 B1)
The foundation arc delivers a **versioned, read-only data contract** between the geometry producer (engine or import parser) and the viewport — *the* artifact Studio consumes. At minimum it covers:
- **Identity** — source object / revision / `geometry_ref`; a representation **cache key**; per-face / per-edge / per-vertex **display IDs**.
- **Render payload** — face triangle buffers **grouped by face ID**; true model-edge polylines/curves **by edge ID**; vertex markers where needed; appearance/material slots; bounding boxes; LOD / tolerance metadata.
- **Selection payload** — the exact ID returned by picking, whether it is **canonical or ephemeral**, and which operation surfaces may consume it.
- **View-dependent payload** — HLR / hidden-line overlays keyed by **camera / projection / tolerance**, kept distinct from the base topology.
- **Cache / invalidation** — when a display package is stale; how camera-specific HLR is invalidated; how the renderer learns a selection ID is no longer valid after a model edit.
- **Boundary** — read-only display data; it does **not** become Product Truth, and the renderer **cannot** call arbitrary engine/kernel methods. This keeps [Manifesto P11](../Manifesto.md) + [ADR/0032 D6](0032-aiadra-studio-scope.md) intact: Studio stays a local client over a *narrow* bridge, not a renderer with a private geometry-kernel back channel.

### D4. Engine-side OCCT for canonical Workspace geometry; renderer WASM for reference imports (Q1 = (c) + hybrid)
- **Canonical AIADRA Workspace geometry** → the **Python engine** (`cadquery-ocp` / OCCT) produces the Display Representation over the bridge. One authoritative mechanical kernel; mints AIADRA IDs; no second full OCCT WASM stack; aligns with [ADR/0028](0028-native-engine-implementation-contract.md)'s Native-Engine boundary.
- **External reference imports** (ADR/0032 D5 lane 1) → keep **`occt-import-js`** in the renderer (proven, browser-safe; mesh + `brep_faces` ranges). It is **not** promoted to canonical topology authority.
- **`opencascade.js`** → a **spike option** for browser-local experiments / custom builds, **not** the default for canonical parts (it duplicates the kernel surface the engine already owns).

### D5. Topology identity is AIADRA/engine-owned, with lifetime + invalidation (Codex1 B2)
Stable selection IDs are **engine-minted** — explicitly **not** raw OCCT transient subshape handles, traversal order, or `occt-import-js` `brep_faces` mesh ranges (those are display/reference metadata, insufficient as canonical identity).
- **Workspace geometry** gets canonical engine-minted face/edge/vertex IDs with **documented lifetime + invalidation rules** across edits/recompute.
- **External STEP/STL imports** get **ephemeral display/reference IDs only**, until — and unless — a future explicit **ingest Data Adapter** ([ADR/0028 D11](0028-native-engine-implementation-contract.md)) converts them into Product Truth.
- **The foundation spike must test identity across at least one edit/recompute**, not only initial import/render — this is the central selection trap (a screen can show gorgeous edges yet be unable to durably answer "which AIADRA edge did the user select?").
- HLR results reference these IDs where possible, but HLR is view-dependent classification, **not** the identity source.

### D6. HLR is view-dependent display classification, cached on camera-settle (Q2)
Target **OCCT HLR** (`HLRBRep` — exact BREP HLR + polyhedral HLR; visible/hidden sharp/smooth/sewn/outline edges) for the hidden-line / no-hidden modes — the CAD-grade vocabulary this strand needs. **Runtime posture:**
- **Interactive orbit** — shaded faces + precomputed true edges (+ optional cheap GPU/depth assists for responsiveness).
- **Camera settled / hidden-line mode / drawing-like output** — cached HLR computed for the view / projection / tolerance.
- Two internal algorithms as needed: **exact** HLR for settled/high-quality, **poly** HLR for fast preview.
Base selection and base edge display do **not** wait on per-frame exact HLR.

### D7. Display modes taxonomy = the Creo set, on the true-edge foundation
Wireframe · Hidden Line (hidden edges **dimmed**) · No Hidden (hidden **removed**) · Shading · Shading With Edges. **Shading With Reflections is deferred** (Codex1 N4 — until a material/environment policy exists; for v1, geometry legibility beats rendering flourish). This corrects the stopgap's mis-naming (the stopgap "Hidden line" was really *No Hidden*) and completes the set.

### D8. Local settings registry under OS user-data — infrastructure, not just a panel (Q4, Codex1 N3)
The Appearance/Options arc delivers a **typed settings registry** (keys, defaults, value types, labels, version/migration, reset-to-default, optional import/export, UI binding) — reusable for display settings now and command/navigation/editor preferences later. **Persisted as versioned JSON in Electron `app.getPath('userData')`.** Layering: built-in defaults → local user preferences → (later) per-session/per-window view state. App preferences are **local-first (P11)** and are **never** persisted in the Workspace/Product Truth unless a setting becomes genuinely project-authoritative. The background↔line-color coupling we hit in the spike is the proof these colors must be one coordinated theme.

### D9. A command model that renders as a toolbar now, a ribbon later (Q3)
Do not hard-code a ribbon. Build a **command taxonomy** (command IDs, groups, icons, enablement predicates, keyboard shortcuts, selection-filter state) that renders as a **compact CAD toolbar** in v1 and is **ribbon-renderable later**. v1 should *feel* like a serious CAD app without committing to ribbon chrome before the command taxonomy exists.

### D10. Strand roadmap + boundary (Q5, Q6)
**Sequence — foundation first, but capture the Creo benchmark immediately:**
1. **ADR/0033 vision** (this).
2. **Benchmark capture packet** — Creo 10 screenshots/clips for wireframe, hidden-line, no-hidden, shaded-with-edges, selection/pre-highlight.
3. **Foundation spike** — engine-generated Display Representation for **one** canonical part: face/edge IDs + true edges, the contract (D3) proven, **identity tested across an edit/recompute** (D5).
4. **HLR spike** — exact/poly HLR for one or two fixed camera views, cached after camera settle (D6).
5. **Display modes** (D7) on that foundation.
6. **Appearance/options** (D8) + **interaction shell** (D9).

**Boundary:** *controls that determine what & how the user sees and selects* — display modes, navigation cube, standard views, selection filters, pre-highlight, appearance/options — belong to **this strand**. *Commands that change the model* — authoring, feature dialogs, operation palettes, Product-Truth editing — belong to **later authoring / data-panel strands**, even if their buttons later live in the same shell.

**Performance budgets** (Codex1 N2) get a home in the foundation arc — provisional acceptance numbers for: initial display-package latency, camera-interaction frame target, HLR-recompute-on-settle latency, cache memory limit, max sample model size. "Correct" is not enough for a professional viewport.

### D11. Gating, dependencies, and the stopgap's fate
- **Gated on the Licensing ADR** (OCCT-heavy; AGPLv3 + CLA + permissive/LGPL-only-dependency is the working direction, in research).
- **Realizes/extends** ADR/0032 D4 (tessellation), D8 (selection), D9 (milestones), D10 (UX patterns). Milestone 2 merges into the foundation arc.
- **The stopgap viewport** (`baf52d2`) is preserved as a **labeled regression baseline only** (Codex1 N5) — useful evidence of where screen-space helped and where it failed; its pieces are deliberately replaced as the foundation lands, not silently depended upon.
- **No schema / bundle / `aiadra-core` change** in this strand.

## Consequences
- **Display & UX becomes a first-class, years-horizon strand**, benchmarked to Creo 10, run through the protocol arc-by-arc.
- **The next arc is the rendering & topology foundation** (the Display Representation contract + engine-side display package + topology IDs), preceded by a Creo benchmark-capture packet — once the Licensing ADR clears.
- **The screen-space stopgap is end-of-lifed as the foundation** — kept only as a regression baseline.
- **The engine grows a read-only display-generation capability** (OCCT edges/tessellation/HLR over the bridge) as a Native-Engine concern — to be pinned by the Display Representation contract so the bridge stays narrow (Native-engine-boundary watch).
- **A reusable typed settings registry** arrives with the Appearance/Options arc.

## Alternatives rejected
- **Keep polishing the screen-space stopgap.** Rejected (D2) — it cannot reach Creo-grade edges/hidden-line/selection by construction; Petre's expert eye already found its ceiling.
- **`opencascade.js` (full OCCT in the renderer) as the default for canonical parts.** Rejected as the default (D4) — duplicates the kernel the Python engine already owns; large WASM. Retained as a spike option.
- **`occt-import-js` `brep_faces` ranges as canonical selection identity.** Rejected (D5) — mesh-oriented, insufficient as a stable AIADRA topology contract.
- **Exact per-frame HLR.** Rejected (D6) — too costly interactively; HLR is cached on camera-settle.
- **A full Creo ribbon clone up front.** Rejected (D9) — build the command taxonomy first; ribbon is a later rendering of it.
- **Workspace-persisted display preferences.** Rejected (D8) — app preferences are local-first, not Product Truth.

## References
- [ADR/0032](0032-aiadra-studio-scope.md) — Studio scope (D4 tessellation, D5 two geometry lanes, D6 bridge, D8 selection, D9 milestones, D10 UX patterns).
- [ADR/0028](0028-native-engine-implementation-contract.md) — Native-Engine boundary + D11 the ingest Data Adapter.
- [Manifesto](../Manifesto.md) P11 — local-first, no hosted service; not-a-clone posture.
- OCCT HLR (`HLRBRep`) — exact + polyhedral hidden-line removal (Codex1 primary-source check).
- Stopgap baseline: `aiadra-studio/src/Viewport.tsx` @ `baf52d2`.
- Licensing & third-party-kernel-compliance ADR — *in research* (AGPLv3 + CLA + permissive/LGPL-only deps); gates the foundation arc.
