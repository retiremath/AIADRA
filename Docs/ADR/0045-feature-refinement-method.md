# ADR/0045 — The Feature-Refinement Method

- **Status:** ACCEPTED (arc 20260725-1; Codex3 signoff)
- **Date:** 2026-07-25
- **Arc:** 20260725-1
- **Relates to:** ADR/0026 (Ring-2 contract surface), ADR/0033 D1/D8 (benchmark, never cloned; local settings ownership), ADR/0034 (licensing & dependency policy), ADR/0035 D3 + ADR/0038 D4 (identity survival/invalidation semantics), ADR/0036 (derived caches), ADR/0037 D2–D4 (benchmark research firewall), ADR/0039 (AI authoring model), ADR/0040 D4/D5 (operation session; chrome/preference separation), ADR/0044 (sketcher paradigm)

## Context

Petre's governing direction (2026-07-23): feature refinement proceeds one subject at a time to Creo-10 quality end-to-end (engine + UI), always compatible with the AI layer and the PDM layer, with the method designed BEFORE ad-hoc polish. The 28-round SK-C1 foundation arc paid for three lessons this method makes repeatable: candidate honesty (previews are validated recipes), boundary drift (green suites over a dead lane), and KB drift (AI knowledge must track refined surfaces). The shell-first pilot (Petre's ruling, 2026-07-25) exposed that a naive "everything is Truth + ops" bar cannot honestly grade chrome work — the method must classify state before it gates it. Quality bar: the refined subject matches the Creo 10 PARADIGM (ADR/0033 D1: benchmark, never cloned) at Petre's side-by-side judgment.

## Decision

### D1 — The pass, its invariant chain, and global concurrency

The unit of refinement is the **pass**: ONE bounded subject taken through
`benchmark capture → Petre gap ruling (scope FREEZE) → design packet → Codex design review → production build → automated + desktop evidence → Petre lock`.
Arc mapping is free (D10); the chain is not: no production build before the ruled ledger and Codex design review exist.

**At most ONE refinement pass is ACTIVE globally** (Petre's one-subject-at-a-time rule). Method/process/design-discussion arcs are not themselves refinement passes. A pass opens with a stable pass id and ONE canonical ledger path (D7), both named at open. A pass transitions only through named states: `active → locked` (D9) or `active → parked` — parking requires Petre's explicit ruling recorded with the incomplete ledger rows and the re-entry condition. The next refinement subject may start only after the current pass is locked or explicitly parked.

### D2 — State classification (mandatory per ruled gap)

Every ruled gap names its class; the class selects the obligations:

1. **Product-authoring state/affordance** — expressible through the Native Engine / Ring-2 operation contract; committed facts live in workspace Truth.
2. **Project-authoritative non-geometry state** — lives in the proper git-tracked workspace artifact; participates in PDM; not automatically a feature op.
3. **Local user/application preference** — the typed, versioned settings registry (ADR/0033 D8); never Product Truth; no Ring-2 twin required.
4. **Transient operation/session state** — capability-scoped, terminally cleaned up (ADR/0040 D4/D5); never durable.
5. **Derived display/cache state** — reproducible and discardable (ADR/0035/0036); never authority.

### D3 — Pass profiles (obligation selectors, NEVER gate exemptions)

The profile selects which D4 feature-semantic obligations apply per ledger row; **the D5 gates apply to every pass regardless of profile** — their applicability follows the D2 state class of each row, not the pass label.

- **Feature pass** (authoring semantics in scope): the full D4 bar.
- **Shell/application pass**: command-model addressability, settings ownership + schema migration, focus/keyboard behavior, viewport non-interference, real-desktop behavior. Preview/regeneration/identity/KB items are N/A for shell-only rows; any row that adds, reroutes, or changes a product-modeling capability pulls the applicable D4 items back in (a new Extrude entry path is chrome work AND a class-1 row).

### D4 — The DONE bar (feature profile; shell analogues in parentheses)

1. **Entry parity** — every ruled-in-scope entry path exists and leads to the ONE operation session (shell: to the one command model).
2. **Preview honesty** — what previews is what commits (ADR/0039 three-state candidates; no mockups).
3. **Refusal honesty under D6** — semantic refusals are the ENGINE'S, crossing the bridge unweakened; envelope refusals carry main's own stable voice; the mock mirrors public behavior as a drift detector.
4. **Lifecycle** — one session authority through begin/update/preview/commit/cancel/failure/bridge-exit; exactly one terminal outcome; awaited rollback; no orphan draft or session (shell: no orphan chrome state).
5. **Persisted compatibility** — every payload/settings/Display/adapter change declares version impact, legacy decode or migration/refusal, and a reopen/regenerate regression over PRE-pass committed material (shell: settings-schema migration + command-registry addressability stability).
6. **Identity semantics, precise** — prove the applicable SURVIVAL case (parameter edit: topology skeleton + surviving roles persist) AND the applicable INVALIDATION case (skeleton change: held selection invalidated; stale persistent references fail loudly before commit) per ADR/0035 D3 + ADR/0038 D4. Never an unqualified "identity preserved."
7. **Boundary coverage** — new ops/params land WITH their main-envelope rule + parity-floor case + mock parity in the same change; the D6 proof obligations hold.
8. **Desktop walk** — the real-engine desktop lane passes; suites alone are insufficient (the boundary-drift class).
9. **KB currency** — the subject's KB page + golden recipe + negative trace reflect the refined surface (feature profile only).

### D5 — The two gates (every pass; applicability per D2 class, per row)

- **G-AI**: every **class-1** product-modeling capability touched or exposed by ANY pass — including a shell pass adding or rerouting an entry path to an existing operation — is also expressible through the same typed operation contract. Evidence is proportional to the ledger: each class-1 row maps to representative no-renderer op-sequence/parity evidence; duplicate entry paths to the SAME operation share one engine proof. G-AI is N/A only for a pass whose ledger contains no class-1 row. Presentation, navigation, and local-preference affordances are explicitly exempt and must not mutate Product Truth.
- **G-PDM (ownership/no-leak — every pass, every ledger row)**: the gate verifies each row's D2 class landed with its correct OWNER. Product/project-authoritative state is **git-trackable, reviewable, and committable, and — after check-in — clone-reproducible** under the committed compatibility pins/digests and the supported runtime (a working workspace is legitimately dirty mid-authoring; no byte-identity promise under arbitrary kernels). No authoritative state may exist only as untracked machine/session/cache material. Local preferences stay local; sessions stay transient; display/cache stays derived. A shell-only pass satisfies G-PDM without creating workspace state.

### D6 — Boundary authority split

| Surface | Owns | Never |
|---|---|---|
| Renderer builder | constructing the typed request | geometry semantics |
| Electron main | transport/security envelope; closed wire shape (known op, closed keys/literals, primitive/finite checks, capability/session validity) | topology-, history-, solver-, kernel-dependent validity |
| Native Engine | ALL operation semantics, references, regeneration, admissibility, domain refusal | — |
| Dev mock | honest projection of public behavior; drift detection | being an authority / a fourth contract |

Parity-floor proof obligations: (a) every real builder output passes the exact main validator; (b) malformed/out-of-contract envelopes refuse at main; (c) representative semantic invalidity reaches and is refused by the REAL engine.

### D7 — The pass ledger (one canonical copy)

One table, THE pass artifact, stable pass-local ids (`<pass>-NN`):
`id | observed interaction | classification (MATCH/GAP/DIVERGENT-BY-DESIGN) | Petre ruling | state/profile class (D2/D3) | design consequence | automated evidence | desktop verdict`.
Scope freeze is mechanical: after the ruling checkpoint a new id requires an explicit scope-change ruling.

**Canonical ownership**: the ledger's path is named when the pass opens (its opening arc's folder) and NEVER moves or forks. When a pass spans arcs (D10), every later review packet CITES that same path and appends evidence/verdicts to it — no copies. Only the `locked` transition (D9) writes the acceptance summary into SystemState.

### D8 — The benchmark research firewall (ADR/0037 D2–D4, operationalized)

Benchmark capture, screenshots, and research notes are local-only, non-shippable research material. No proprietary text, document structure, example sequence, API shape, or distinctive naming crosses into code, KB, tests, or public docs. Shippable expression is REWRITTEN against AIADRA operations, ADRs, schemas, and observed system behavior, citing those AIADRA artifacts as authority. AI runs producing shippable artifacts honor ADR/0037's context-exclusion rule. Public/product wording is benchmark-informed, never Creo-branded.

**D8.5 — Third-party material (conditional):** a pass introducing third-party code, binaries, icons, fonts, or reference material records in its ledger: license, provenance, pinned source, modification status, attribution/SBOM consequence, and any ADR/0034 attorney item.

### D9 — LOCK semantics

LOCKED is an acceptance BASELINE: the ledger revision + evidence are recorded together with the named reopen conditions (a named regression, a new benchmark ruling, a contract migration, an accessibility/performance defect, a deliberate product-direction change). A later pass may amend a locked surface through those doors; it must not silently erode accepted behavior.

### D10 — Arc mapping and authority

Small passes default to one arc (ruling = a mid-arc gate). A pass whose ruled scope changes a schema, a solver/Display contract, or a persistent-identity rule spans a design arc + a build arc under the SAME pass id and the SAME canonical ledger (D7); the design arc may close on its review while the pass stays `active` — pass state (D1) and arc state are independent axes. This ADR is the method's authority; SystemState carries the pointer, the current pass + state, and the LIVE queue of upcoming subjects — the queue is direction (Petre + prerequisite leverage), never method-frozen.

## Alternatives considered

- **Method-as-convention (CLOSED.md + SystemState only)** — rejected: a rule claimed as governing all feature work cannot live in git-ignored/cache artifacts (SystemState is explicitly not an authority layer).
- **Uniform bar for all passes** — rejected: the shell pilot proved it ungradeable; chrome preferences are not Truth (ADR/0033 D8) and must not acquire Ring-2 twins.
- **Same-domain refusal at all three surfaces** — rejected: parallel semantic validators ARE the drift the parity floor exists to prevent; authority is split per D6 instead.

## Consequences

- The shell work of 2026-07-25 (`524f32b`, `bf571e6`) is recorded as a Petre-authorized PRE-METHOD pilot: it informs this ADR and is assessed under the completed shell-pass ledger before any LOCK — it is not retroactively method-conformant evidence.
- **The shell pilot pass must be resolved BEFORE the sketcher pass activates** (D1 concurrency): either back-filled, desktop-walked, and locked, or explicitly parked by Petre with its open rows and re-entry condition recorded. The sketcher arc's existing design packet stands as pre-pass design input pending that ruling; method-design and contract-design arcs are not passes and may proceed meanwhile.
- The FreeCAD-icon ledger row distinguishes **pass acceptance** (provenance, pinned source, attribution — provable now) from **release prerequisites** (the ADR/0034 attorney item stays a NAMED release gate; "listed for attorney" is never recorded as "legally cleared").
- Every future pass produces one canonical ledger; SystemState's §6 records pattern changes only, per its charter.

## Amendment A1 (2026-09-05, arc 20260905-1 — Petre's standing direction, recorded from Codex2 §"Petre's standing direction") — designing for the AI user

**Direction (Petre, 2026-09-05):** AIADRA is designed for BOTH of its users — the human engineer at the desktop and the AI collaborator at the typed contract. Codex holds the AI user's perspective in every review alongside Petre's experienced mechanical-designer perspective, and proactively identifies the tools an AI needs to design engineering devices. Claude remains implementation lead; Petre sets engineering priorities and acceptance judgments. ADR/0039 (intent-bearing configurators, real evaluated candidates, human acceptance, BYO-AI orchestration) and D5's G-AI already establish typed-operation parity; this amendment makes the *usability* of that access a reviewed obligation.

**A1.1 — G-AI is usability, not existence (extends D5).** An exposed typed operation alone does not satisfy G-AI. For each class-1 row the evidence must show that an agent can (i) **discover** the operation's schema, units, supported entity types, preconditions and capability limits from the installed engine/client contract and the KB — documentation and examples agreeing with the actual tool surface; (ii) **address** the intended geometry through engine identities or semantic criteria, with ambiguous matches inspectable and stale references detected (persistent-reference laws stay authoritative); (iii) **interpret** the result, distinguishing authored facts, evaluated geometry, and unavailable information; and (iv) **act on a refusal** — the failed operation, the implicated entities/constraints and actionable context are named, and the engine's established reason is distinguishable from an agent's proposed repair.

**A1.2 — The representative agent workflow (extends D4 item 8).** For each applicable feature pass, beside Petre's desktop walk, the canonical ledger records ONE representative agent workflow: discover/inspect the relevant context → select a target → propose through the real typed operations → evaluate → inspect a refusal or result → produce a concrete candidate for human acceptance. It exercises the actual public boundary wherever available, distinguishes engine-level feasibility from a proven client/tool workflow, and keeps its evidence proportional to the feature — a pass never proves the whole future platform.

**A1.3 — The seven standing questions (the review lens AND the roadmap lens; candidate needs, not claims that these capabilities exist):** 1 *Discover the available tools.* 2 *Understand the model* — bounded structured queries over features, parameters, frames, dependencies, constraints and requirements; focused visual evidence where numbers do not judge shape or access. 3 *Address geometry reliably* — "the mounting face" resolves transparently, never a silent first match. 4 *Make controlled edits and explore alternatives* — intent parameters, candidate/sequence evaluation, comparison, discard; no Product-Truth litter, no lost recoverable session. 5 *Verify engineering outcomes* — dimensions, clearances, interference, degrees of freedom and per-domain checks with units and explicit applicability; a valid solid proves no requirement. 6 *Understand failure and repair it.* 7 *Share intent and hand work back* — the same selection, candidate, parameter and requirement addressable by both; durable homes for assumptions and rationale; completed designs feed ADR/0039's curated configurator capture. Newly discovered needs are recorded in the canonical ledger or the SystemState queue and taken through the existing design gates; the roadmap grows incrementally from concrete engineering workflows.

**Scope note.** The direction adds no assembly, analysis, profile-redefine or AI-service implementation to the pass in flight (`sketch-line-1` I3); it reinforces I3's accepted floors — the explicit four-member placement, discoverable vocabulary and defaults, useful principal-only refusals, sketch-local H/V semantics, and agreement between human-created and directly authored records.
