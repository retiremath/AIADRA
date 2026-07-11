# ADR/0040 — AIADRA Studio: Application Shell, AI Integration & PDM UX

## Frontmatter

- **Status:** **Accepted** — 2026-07-11 (arc 20260711-7; two-round: Claude1+draft / Codex1 / Claude2 close. Codex1 verdict "strong consolidation, close-ready"; B1 co-land a one-line ADR/0033 "step-6-consumed" pointer (done); a wording watch — keep Creo-referential phrasing internal-only per ADR/0037 D1 (noted in Watches)). Consolidates two fully-converged discussion arcs: **20260711-3** (Studio application/AI/PDM UX vision; Codex1 B1 the operation session + B2 optimistic checkout + N1–N6) and **20260711-4** (the CAD↔AI dock; Codex1 B1 the operation-session presence invariant + B2 tab-isolation + N1–N5). The one-line **ADR/0033 pointer is co-landed in the same commit**.
- **What it is:** the **application-phase sibling of [ADR/0033](0033-studio-display-ux-vision.md)** (which is the *display* vision). ADR/0033's step 6 (display + interaction shell) is now **consumed** by this application strand. It pins the **three surfaces in one interface** (app shell + CAD↔AI + PDM), the **operation session** mechanism, the **CAD↔AI dock**, **optimistic GitHub-as-PDM checkout**, provenance-as-UI-primitive, the principles **P-U1…P-U8**, and a **build roadmap led by the physical-testing MVP**. It is the *surface* through which the authoring model ([ADR/0039](0039-the-aiad-authoring-model.md)) and the git-backed session model (arc 20260701-1) are driven.
- **Macro direction:** Petre, 2026-07-11 — *"I would like to physically test the features and the concepts we implement as we introduce them; for that I need the (almost) final UI concept functional… a standalone app with all the toolboxes… but most important, a smart and user-friendly interface between the CAD-like portion and the AI-assist portion, plus the check-in/check-out mechanism between AIADRA and GitHub (as a PDM system)."* And on the AI surface: *"as Creo's internal browser does — resizable horizontally, an ✕ to dismiss, a bottom-left toggle."*
- **Version impact:** vision/scope ADR — no code in this arc. References [ADR/0039](0039-the-aiad-authoring-model.md) (the authoring model rendered here), [ADR/0033](0033-studio-display-ux-vision.md) (display vision; D9 command model; step 6 consumed), [ADR/0032](0032-aiadra-studio-scope.md) (Electron scope), [ADR/0026](0026-ai-action-protocol-scope.md) (Ring 2), [ADR/0001](0001-storage-substrate.md)/[ADR/0004](0004-number-allocation.md) (session/Reservation). No bundle/schema/Glossary/Manifesto change.

## §0 — What this ADR does

The models are designed; this ADR pins the *surface*. The authoring loop ([ADR/0039](0039-the-aiad-authoring-model.md)), the git-backed session (no session server; git working tree + Vault + locality/staleness; Float/Fixed — arc 20260701-1), the Display Representation contract + interaction shell ([ADR/0033](0033-studio-display-ux-vision.md) step 6), and the Ring-2 client surface ([ADR/0026](0026-ai-action-protocol-scope.md)) already exist. This ADR is **~60% composition** of those; the genuinely new design is the two interaction models (CAD↔AI, PDM) and how the three surfaces share one screen. **The integration is the point:** get the seams right and Studio feels like one tool; get them wrong and it feels like three bolted together.

## Decisions

### D1. One interface, three surfaces (the integration thesis — P-U1)
CAD authoring, AI assistance, and PDM check-in/out are **docks of a single window over one model**, never three apps in tabs. The AI proposes into the same model the human edits by hand; committing that model is a first-class PDM act.

### D2. Packaging: Electron reaffirmed, with an empirical revisit trigger (arc 20260711-3 N1)
[ADR/0032](0032-aiadra-studio-scope.md)'s Electron choice stands. The reasons reinforce each other: a **WebGL-heavy** UI (three.js), a **Python/OCCT engine subprocess**, and P11's **local filesystem + git** requirement are all marshalled by Electron's Node main process, and the bridge is already Node. The honest alternative (Tauri: smaller binaries, better security defaults) moves the engine bridge to a Rust sidecar and bets a CAD-grade WebGL workload on three inconsistent OS webviews — not worth the rewrite while Electron works and step 6 shipped on it. **Revisit-if trigger:** binary size / RAM / startup becomes a real user complaint → evaluate Tauri. Not reopened here.

### D3. The application shell — Creo-10-benchmarked, non-clone
The full frame: **menu bar** (File / Edit / View / Insert / Applications / Tools / Options / Window / Help) / **ribbon or toolbar** / **model tree** (left) / **operation dashboards** (Creo's contextual top-of-window feature panels) / **graphics window** (done). It **extends the [ADR/0033 D9](0033-studio-display-ux-vision.md) command taxonomy** (already feeding toolbar+menu+keyboard — the menu bar/ribbon is a growth of it, not a new system). Under the [ADR/0033 D1](0033-studio-display-ux-vision.md) non-clone guardrail: Creo 10 is the benchmark for completeness and muscle-memory, never a skin. **Command infrastructure before ribbon completeness** — render only the commands a slice needs; no wide dead ribbon (arc 20260711-3 N4).

### D4. The operation session — the mechanism that makes "AI is a spectrum, not a mode" real (arc 20260711-3 B1; arc 20260711-4 N2)
The manual feature dashboard and the AI candidate/refinement panel are **two views of ONE shared operation session**. Decisions:
- **One editing context per in-progress feature/configurator instance**, holding: candidate recipe · parameter state · selected topology refs · validation state · provenance material.
- **Created by** a manual command, AI retrieval, or an AI compilable-intent move ([ADR/0039](0039-the-aiad-authoring-model.md) P-A1) — same shape regardless of origin.
- **Strict single source of truth (arc 20260711-4 N2):** the operation-session *store* owns all parameters/refs/candidate-identity/validation/dirty/commit-readiness; the dashboard and the dock are **projections** with different affordances; **neither owns commit**; both call the same `accept`/`cancel`/`update` actions; they can never show different values.
- **Accept/commit is a single explicit Ring-2 action** ([ADR/0026](0026-ai-action-protocol-scope.md)). **Invariant:** *all authoring roads converge before commit.*
- It is the **UI-side home of the three-state candidate model** ([ADR/0039 D3](0039-the-aiad-authoring-model.md)): the session *is* the candidate recipe (state 1) + its evaluated display (state 2); accept transitions to committed Product Truth (state 3).

### D5. The CAD↔AI dock — resizable / dismissable / multi-purpose, coupled to the operation session (arc 20260711-4)
The AI/Home surface is a **first-class resizable, dismissable, dockable panel** — not a full-screen takeover, not a fixed sidebar. Modeled on Creo's internal browser (horizontal resize, ✕ dismiss, bottom-left toggle); **the drag-divider between dock and canvas is the "AI-is-a-spectrum" principle made physical** (wide = AI-forward welcome; narrow = CAD-forward companion). **Default side: right** (tree left, canvas center, AI right; dockable to the left later — arc 20260711-4 N1). **Multi-tab:** `Design` (session-coupled) / `Home` / `Catalogs & KB` (browse). Sub-decisions:
- **B1 — operation-session presence invariant.** The dock **may** be dismissed during an active session (the pure-CAD escape hatch is preserved; the Design tab is **not** made non-dismissable). Dismissal **hides** AI/candidates/browse but **never** closes, cancels, or commits the session; the **manual operation dashboard stays visible** as the authoritative control surface; a **persistent session indicator** carries **restore-AI** + **cancel-session**; the **bottom-left toggle is stateful** — *no session* / *session + AI shown* / *session + AI hidden*.
- **B2 — tab-isolation.** `Design` is operation-session-coupled; `Home` and `Catalogs & KB` are browse surfaces. When a session is active, a **persistent active-session banner rides across all tabs**; **switching tabs never mutates or suspends** the session; a Catalog/KB candidate becomes a session **only via an explicit "Use / Start operation"** action (never passive browsing); unsaved parameter edits → **confirm / discard / fork**.
- **Chrome is a local app preference** (dock width/side/open-closed/last-tab, under the [ADR/0033 D8](0033-studio-display-ux-vision.md) settings registry); the **active operation session is separate transient application state** (arc 20260711-4 N4).
- **Catalogs & KB is local-first library browsing** (arc 20260711-4 N3): *allowed* — project KB, core-KB package resources, local catalogs, BYO catalog sources, explicit import flows; *not allowed* — a hosted AIADRA catalog, an embedded remote marketplace as a default dependency, silent import-to-Truth, or remote content canonical without Component/Binding routing. The forthcoming KB-interchange ADR (arc 20260711-5) extends this with the `pack:` import lane.

### D6. The three-affordance AI surface (arc 20260711-3 N2)
Not panel *vs* palette *vs* inline — three affordances for different moments, **unified by the operation session (D4)**: a **docked AI panel** (persistent conversation, elicitation cards, candidate gallery, provenance), a **command palette / omnibox** (quick "make this…" against the current selection — an entry point), and **inline viewport affordances** (lightweight candidate preview/selection anchors, not a chat surface).

### D7. The PDM interface — GitHub-as-PDM, engineering language, OPTIMISTIC v1 (arc 20260711-3 B2)
Check-in/out in **engineering language, not git jargon**, over the git-backed session model (arc 20260701-1): per-object **status/locality** (modified / committed / released rev N / remote-only), a **retrieve/fetch** affordance, a **check-in** dialog (→ commit/release + Revision), and history/where-used/conflict. **v1 checkout is OPTIMISTIC** — edit locally, show dirty/remote/stale/conflict status clearly, require sync/fetch for high-stakes release/check-in. **No exclusive-lock semantics in v1**, and **not via [ADR/0004](0004-number-allocation.md) Reservation** (Reservation allocates human-readable Numbers, not locks; [ADR/0001](0001-storage-substrate.md) rejected live coordination locks; an exclusive remote checkout would overload the mechanism and risk P11). Check-in/out *language* is kept; the v1 semantics are **open / retrieve / edit / check-in over git state**. A future optional **advisory checkout/claim** is deferred as its own scoped artifact (explicit stale/offline/merge; never authoritative without a server).

### D8. Provenance is a UI primitive, not a footnote (P-U3; arc 20260711-3 N6)
Every AI candidate wears a **provenance strip** showing compact trust material: source configurator, core/project KB source, parameter values, validation status, and **whether it is transient or committed**. UI must **never** let a transient candidate read as Product Truth — the three-state model ([ADR/0039 D3](0039-the-aiad-authoring-model.md)) made visible. This transparency is the differentiator over "AI draws CAD" demos.

### D9. The application principles P-U1…P-U8
- **P-U1** — one interface, three surfaces (docks of one window over one model).
- **P-U2** — AI is a spectrum *with* manual CAD, not a mode — realized by the operation session (D4) and the resizable dock (D5).
- **P-U3** — every AI candidate wears its provenance, incl. why-it's-safe-to-show + transient-vs-committed (D8).
- **P-U4** — PDM speaks engineering, not git (D7).
- **P-U5** — local-first (P11); the app *is* the workspace (git working tree + Vault + local caches).
- **P-U6** — BYO-AI client; Core hosts no copilot / lock server / retrieval service.
- **P-U7** — Creo-benchmarked, not Creo-cloned ([ADR/0033 D1](0033-studio-display-ux-vision.md)).
- **P-U8** — the operation session: a manual dashboard and the AI panel are two views of one shared editing context, committed by a single explicit Ring-2 accept; all authoring roads converge before commit.

### D10. The build roadmap — led by the physical-testing MVP (arc 20260711-3 N3/N5)
The fastest route to Petre's "physically test features" goal is a **thin vertical slice**, not building horizontal slices in order — and the **first MVP uses a scripted/deterministic AI** (schema-driven elicitation + 2–3 fixed candidate recipes, **no model-provider dependency**), so we test the *workflow shape* before wiring any LLM:
1. **App-shell regions** — model-tree placeholder + viewport (done) + an operation/AI dock + a PDM/status strip.
2. **One `generate` configurator** — a simple bracket/plate on shipped primitives (extrude/hole/fillet…).
3. **Scripted AI panel** — schema-driven elicitation + 2–3 fixed candidate recipes.
4. **Candidate preview** — via the evaluated-display tier ([ADR/0039 D3](0039-the-aiad-authoring-model.md)).
5. **Accept → commit a Part via Ring 2.**
6. **PDM/status** — dirty → committed/released, in engineering terms.
Broader shell/ribbon, real LLM wiring, and the full candidate gallery build *after* this proves the workflow shape. This ADR **consumes [ADR/0033](0033-studio-display-ux-vision.md)'s step 6** and does **not** amend its display roadmap beyond noting step 6 is now consumed by the application strand (arc 20260711-3 N5).

## Consequences

- **Positive:** the AIAD product surface is pinned as one coherent interface; the operation session gives "AI-as-spectrum" a crisp, testable mechanism (single source of truth, single accept); optimistic PDM keeps P11 clean; the MVP slice (scripted-AI-first) de-risks the workflow shape independently of model quality; ~60% composition of shipped substrate.
- **Deferred:** the full ribbon; advisory/pessimistic checkout; the `pack:` interchange lane (arc 20260711-5); real LLM wiring beyond the scripted MVP; `compose`/assembly authoring UX (assembly-composition ADR).
- **Watches:** stable ids for operation sessions / candidates / cards / provenance if persisted; PDM must not expose direct catalog Part endpoints (`select` via Component/Binding); Float/Fixed status visible; unit-bearing facts (`_mm`/`_deg`) not prompt-only; no live lock server / hosted copilot / core-side AI. **Public-wording guardrail:** Creo-referential phrasing in this ADR (e.g. "modeled on Creo's internal browser") is **internal-ADR context only**; public/product surfaces stay *benchmark-informed*, not Creo-branded, per the [ADR/0037 D1](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md) public-claim guardrail (arc 20260711-7 wording watch).

## Alternatives considered

- **Three separate apps / a full-screen "AI mode"** — rejected (D1/D5): breaks the one-model integration; the resizable dock + operation session is the spectrum.
- **Pessimistic checkout via ADR/0004 Reservation** — rejected (D7): overloads a Number-allocation mechanism, and an exclusive remote lock risks P11; optimistic-with-clear-status is v1.
- **A non-dismissable AI panel while a session is active** — rejected (D5 B1): violates the pure-CAD escape hatch; the presence invariant (dashboard stays authoritative + stateful toggle) is the answer instead.
- **Building the shell/ribbon breadth-first** — rejected (D10): a thin vertical MVP slice reaches physical testing far sooner; command infra before ribbon chrome.
- **Reopening Electron for Tauri now** — rejected (D2): re-litigates a shipped, working decision; empirical revisit trigger instead.
