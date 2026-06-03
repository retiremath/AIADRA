# ADR/0032 — AIADRA Studio scope (the authoring application / primary Workspace Browser)

## Frontmatter

- **Status:** Accepted — 2026-06-03 (arc 20260602-5; two-round convergence Claude1 + Codex1 / Claude2 + Codex2).
- **What it is:** the **first application/UI scope ADR**. [ADR/0028 D13](0028-native-engine-implementation-contract.md) deferred UI "to per-engine UI scope ADRs"; this is that ADR at the application level. Scopes **AIADRA Studio** — a standalone desktop authoring application that is the **primary Workspace Browser**.
- **Partially supersedes:** the [Glossary v0.25](../Glossary.md) "Workspace Browser" entry (VSCode-primary) and [ADR/0028 D13](0028-native-engine-implementation-contract.md)'s VSCode-oriented UI assumption — re-pointed to "Studio primary / VSCode secondary" per D2 + the supersession register. **Glossary v0.25 → v0.26 co-lands at arc close.**
- **No schema bundle bump. No `aiadra-core` version bump.** Scope-only; the Studio is a separate package/repo. Local-first → [Manifesto P11](../Manifesto.md) holds (no hosted service).
- **Driven by Petre** (2026-06-03 pivot): interrupt the `aiadra-mechanical` v0.0.2 engine work (parked arc 20260602-4) to build the authoring application "professionally, get it right," modeled on **Creo + Windchill**.

## §0 — What this ADR does

AIADRA Studio is the AIADRA authoring application: a local-first **standalone desktop app** that renders + manages the AIADRA Workspace (the Git repo = Product-Truth sidecars + a Vault of geometry). It pairs a professional **3D viewport** (Creo-style) with a docked **Product-Truth data panel** (Windchill-style: model tree, parameters, relationships, provenance, validation, release). The AI engine interacts with the model through the same **Ring 2 protocol** the Studio drives (`propose` / `modify` / `inspect` / `query` / `explain`).

A **bootstrap spike** (`d:\VSCode-Work\aiadra-studio`, arc 20260602-5) already proved the stack (Vite 6 + React + TypeScript + three.js; first pixels) and **is the production seed, not a throwaway mockup** — an Electron app renders this same web UI in a native window. This ADR pins the production architecture **before** building features (per Petre's "loop Codex in early" discipline; Codex1 reviewed this scope and raised B1-B3, absorbed below).

## Decisions

### D1. Scope ADR; the spike is the production seed (not a mockup)

Per [ADR/0031](0031-aiadra-mechanical-v0.0.1-scope.md)/[ADR/0030](0030-wedge-003-spike-scope.md) scope-first precedent. The three.js/React spike **is** the production UI: Electron renders a web app in a native Chromium window, so the spike's code becomes the desktop app; Electron adds only the thin native layer (window/menus, native dialogs, filesystem, the bridge to Python). ~95% of UI/viewport carries over. **Caveat (Codex N5):** the spike currently proves only the Vite/React/three.js shell + first render — Electron, the STL loader, and WASM-OCCT are NOT yet in `package.json`; this ADR does not imply they are proven.

### D2. Standalone Electron desktop app = PRIMARY Workspace Browser; VSCode = SECONDARY (Codex N1)

Per Petre's choice. **AIADRA Studio becomes the primary Workspace Browser**; **VSCode + the AIADRA extension remains a developer/agent integration surface** (code, docs, reviews, agent workflows) — not erased. A dedicated app gives the authentic professional-CAD feel (full-window viewport, Creo-style layout) an editor panel can't. **Electron over Tauri:** bundled Chromium gives consistent WebGL/WASM rendering across OSes — worth the package weight for a 3D/WASM-OCCT app; Tauri's OS-webview reliance risks rendering inconsistency. **Local-first** (reads the local Git workspace; no hosted service) → P11 intact.

### D3. Stack

Electron + **React + TypeScript + Vite 6 (stable Rollup; NOT the experimental rolldown that Vite 8 defaults to)** + **three.js** + **OCCT** for tessellation/import (two lanes per D5). FreeCAD's stack for reference = Qt + Coin3D/Open Inventor + OpenGL + OCCT (native C++); we adopt its UX *patterns* (D10), not its native stack — three.js/WebGL is the modern web-CAD equivalent (Onshape, Fusion-web prove professional quality is reachable).

### D4. Geometry pipeline — BREP-first, topology-preserved tessellation (NOT STL-primary)

**All CAD viewports — Creo, SolidWorks, NX included — rasterize triangles; none draw analytic BREP to screen.** The model stays exact BREP; triangles are for display. Quality = *how* you tessellate:
- **Tessellate from the true BREP via OCCT** with **adaptive, curvature-based deflection**, **true surface normals** (from the analytic surface), **analytic edge curves** (the crisp CAD edges), and **re-tessellation on zoom (LOD)** so curves never show facets.
- **Preserve face / edge / vertex topology IDs through tessellation** (per-face triangle groups tagged with the face id; edges as tagged polylines; vertices as tagged points) — required for selection (D8).
- **STL is a FALLBACK only** — a baked, coarse mesh with no normals, no edges, **no topology** → cannot support selection or smooth zoom. It serves the external-inspection lane (D5) for non-BREP files, clearly as reference geometry.

### D5. Two geometry lanes (Codex B3) — external import is NOT Product Truth

A visual import must never silently become canonical Product Truth (the UI form of AIADRA's derived-view-vs-truth boundary):
1. **External inspection lane** — drag-drop / file-picker arbitrary STEP/STL → rendered in the viewport, clearly marked **"imported / reference"**, treated as **untrusted input**. It becomes Product Truth ONLY via an explicit future **ingest transaction** (a Data Adapter per [ADR/0028 D11](0028-native-engine-implementation-contract.md)) — never implicitly.
2. **AIADRA Workspace lane** — reads Product-Truth sidecars + Vault geometry produced by **`aiadra-mechanical`** (the parked v0.0.2 persistence work). Canonical; carries engine topology IDs (D4/D8).

### D6. The bridge — Studio-owned local stdio JSON-RPC over Tier-1 `aiadra_core.protocol` (Codex B1)

The Studio talks to the Python engine through a **Studio-owned bridge process** (spawned by Electron main) that imports **Tier-1 `aiadra_core.protocol`** and exposes an **app-private stdio JSON-RPC** contract wrapping the Ring 2 operations. **NOT** `aiadra-core` growing a long-running server command — that would blur [ADR/0026 §6](0026-ai-action-protocol-scope.md) (Tier-3 transport lives OUTSIDE core) + [Manifesto P11](../Manifesto.md). (The bridge may later be extracted as a separate ecosystem transport package, e.g. `aiadra-bridge`/`aiadra-mcp`-class.) A per-call **CLI shell-out is fallback/debug only** (too slow + stateless for a professional Studio).

**Security invariants (mandatory, pinned here before implementation):**
- Renderer: `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`.
- IPC: a **narrow allowlisted + schema-validated** preload API only; no arbitrary shell/file access from the renderer.
- Workspace roots are **explicit user-granted capabilities** (the app opens a chosen workspace; it does not roam the filesystem).
- **Untrusted geometry (external STEP/STL) is parsed off-thread** (Web Worker / isolated process), never in a privileged Node context.
- No network server in v1.

### D7. Native format = the AIADRA Workspace (Codex B2)

The **authoritative native format IS the existing AIADRA Workspace**: Product-Truth sidecars + Vault blobs, with Git/Commonspace semantics intact. Petre's "native saving format including BREP + STEP/STL + the AI language" = this Workspace (the AI language = the sidecars/Truth-Model + Ring 2). A **single portable bundled document** (geometry + Product Truth in one file, for sharing a model outside a repo) is scoped as a **FUTURE export/import package that round-trips to a Workspace** — explicitly **NOT a second source of truth**. Leaving both equal would drift the persistence UX + bridge API immediately.

### D8. Selection + interaction model

- **Hover pre-highlight + click select** a **topological entity** (face / edge / vertex / surface quilt = face-set) via GPU-picking against the topology-tagged tessellation (D4); the selection carries the **canonical AIADRA id** so the engine can act on it.
- **Selection filters** (faces-only / edges-only / vertices-only, à la Creo), multi-select, box-select.
- **Right-click context menus invoke engine operations** (e.g. edge → fillet/chamfer/measure; face → sketch-on-face/offset/section) via the bridge → Ring 2 `propose`/`modify`; the engine computes + re-tessellates + the view refreshes. **UI selects + commands; engine computes.**

### D9. v1 milestones (Codex N4 — display/import before measurement/section)

1. **Milestone 1:** Electron shell + **secure bridge skeleton** (D6) + external import lane (STL + STEP via off-thread WASM-OCCT) + orbit/pan/zoom/fit + shaded+edges draw style + model-tree stub.
2. **Milestone 2:** the selection model (D8) over topology-tagged geometry; the AIADRA Workspace lane (read real Parts once v0.0.2 persists geometry).
3. **Milestone 3:** measurement + section planes + richer draw styles + the data panel wired to Product Truth.

### D10. FreeCAD/Creo UX patterns to adopt

Navigation cube (view-orientation gizmo); standard view shortcuts (iso/front/top/…); selection + pre-selection highlighting; **draw styles** (shaded / wireframe / shaded-with-edges / flat); fit-to-view; measurement + section/clipping; a Creo-style layout (viewport + docked data/tree panel + toolbar). **Units (Codex checklist watch):** the viewport must display units from Product Truth or file metadata — no project-policy-magic units; any future *persisted* measurement carries unit-bearing field names per [ADR/0029 D10](0029-part-authoring-scn.md).

### D11. Repo + naming

`aiadra-studio` (working name, Petre-approved) as **its own git repo** at `d:\VSCode-Work\aiadra-studio` (one-repo-per-project convention; already `git init`-ed + committed). The **decision record (this ADR) + the Glossary amendment stay in `AIADRA/Docs`** (canonical ADR home), since they amend AIADRA posture.

### D12. Out of scope (v1)

Viewport authoring/editing (the engine authors; v1 displays + inspects, then gains authoring affordances that call the engine); assemblies/multi-part depth; collaboration/multi-user; web/hosted delivery (local desktop only, P11); the full PLM surface (where-used, change orders) beyond the v1 tree/properties; the portable bundled-document format (D7, future); packaging/signing/auto-update (a later release arc); GD&T/PMI.

### D13. Supersession + amendment register

- **Partially supersedes** the [Glossary v0.25](../Glossary.md) "Workspace Browser" entry: primary Workspace Browser becomes **AIADRA Studio (standalone desktop app)**; VSCode + the AIADRA extension remains a **secondary developer/agent integration surface**. **Glossary v0.25 → v0.26 co-lands at arc close.**
- **Partially supersedes** [ADR/0028 D13](0028-native-engine-implementation-contract.md)'s VSCode-oriented UI assumption (UI host re-pointed to Studio-primary). No other ADR/0028 decision changes.
- **No Manifesto change** — the Studio is local-first; P11 holds. **No schema/bundle/version bump.**

### D14. Coherence Checklist walk

11 items: **AIADRA Core hosts nothing** — PASS (Studio-owned local subprocess bridge over local Workspace state per D6; NO `aiadra-core` server). **Native engine boundary** — PASS (Studio is a UI client driving Native Engines through Ring 2 / the bridge per D5/D8; it does NOT wrap Creo/FreeCAD-the-app, and external imports never silently become Product Truth). **Canonical units at fact level** — PASS-with-watch (D10 units display). Rest N/A (no schema/relationship/geometry-truth change). No new Checklist item; no new Pattern Catalogue row.

## Consequences

- **First application/UI scope ADR.** AIADRA gets a dedicated desktop authoring app; the UI strand begins (years-horizon, like the engine).
- **Posture amended** (Studio-primary / VSCode-secondary) — recorded as a clean partial supersession; Glossary v0.26 co-lands at close. Principle-consistent (local-first; P11 holds).
- **Bridge boundary pinned** (D6) — Studio-owned local stdio JSON-RPC over Tier-1 protocol; no core server; explicit security invariants. Keeps ADR/0026 §6 + P11 intact.
- **Native format decided** (D7) — the Workspace is authoritative; a portable bundle is a future export, not a second truth.
- **Two geometry lanes** (D5) — external import (reference) vs canonical AIADRA geometry; import never silently becomes Product Truth.
- **Geometry pipeline is BREP-first with topology-preserved tessellation** (D4/D8) — enables Creo-class smoothness + topological selection; STL demoted to fallback. Favors engine-side tessellation (canonical IDs) for AIADRA Parts; browser-WASM-OCCT for external import.
- **Studio + v0.0.2 coordinate** — build Studio against imported/test files first; resume `aiadra-mechanical` v0.0.2 (geometry producer) before claiming end-to-end browsing of real AIADRA Parts.

## Alternatives rejected

- **(i) VSCode webview extension as primary** (the prior posture). Rejected per Petre + D2 — a dedicated app gives the professional-CAD feel; VSCode kept as secondary, not erased.
- **(ii) Tauri** instead of Electron. Rejected per D2 + Codex N1 — OS-webview rendering inconsistency risk for a heavy 3D/WASM app.
- **(iii) `aiadra-core` grows a long-running server** for the bridge. Rejected per Codex B1 — blurs ADR/0026 §6 (Tier-3 outside core) + P11; Studio-owned bridge instead.
- **(iv) A single portable document as the native format / second source of truth.** Rejected per Codex B2 — the Workspace is authoritative; portable bundle is a future export.
- **(v) STL as the primary render format.** Rejected per D4 + Petre's questions — no normals/edges/topology; can't support selection or smooth zoom. BREP-first.
- **(vi) Treating external imports as Product Truth.** Rejected per Codex B3 — two lanes; explicit ingest required.
- **(vii) CLI shell-out as the primary bridge.** Rejected per Codex B1 — too slow + stateless; fallback/debug only.

## References

- [ADR/0026 §6 + §0](0026-ai-action-protocol-scope.md) — Tier-3 transport lives outside core; BYO-AI; the bridge realizes this.
- [ADR/0028 D11 + D13](0028-native-engine-implementation-contract.md) — Data Adapter (the future ingest path); UI deferral this ADR fulfills.
- [ADR/0031](0031-aiadra-mechanical-v0.0.1-scope.md) — v0.0.1 engine; [arc 20260602-4 Claude1](../Discussions/20260602/20260602-4/Claude1.md) — parked v0.0.2 (the geometry producer Studio consumes).
- [Manifesto P11 + P12](../Manifesto.md) — Core hosts nothing (Studio is local-first); three-tier on Git.
- [Glossary v0.25](../Glossary.md) — Workspace Browser (amended by this ADR).
- `d:\VSCode-Work\aiadra-studio` — the bootstrap spike / production seed.
