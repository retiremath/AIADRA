# ADR/0039 — The AIAD Authoring Model

## Frontmatter

- **Status:** **Accepted** — 2026-07-11 (arc 20260711-6; two-round: Claude1+draft / Codex1 / Claude2 close. Codex1 B1 hardened the content-lock language in D9/D10/D13 [digest, never `kb_version`], B2 made D13 a concrete co-landed patch set; N1 D3 evaluated-display wording, N2 D5 golden-recipes-not-Truth, N3 D12 roadmap-not-acceptance-gate, N4 title shortened). Consolidates two fully-converged discussion arcs: **20260711-1** (the authoring model — principles & architecture; Codex1 B1 three-state candidate model + B2 configurator-as-KB-artifact + N1–N5) and **20260711-2** (two-tier KB storage; Codex1 B1 content-addressed digest lock + B2 ranking-vs-suppression + N1–N5). The **ADR/0037 amendment (D13) is co-landed in the same commit** (arc 20260711-6 B2).
- **What it is:** the ADR that gives the **"AI-Augmented"** in AIAD ([ADR/0027](0027-aiad-positioning-and-native-engine-posture.md)) its concrete experience — the **authoring peer of [ADR/0033](0033-studio-display-ux-vision.md)** (which is the *display* vision). It pins: the **configurator-as-asset** reframe, the **interaction loop**, the **three-state candidate model**, the **configurator object model**, the decision that a configurator is a **KB artifact (not a Truth-Model Object Type) in v1**, the **layered validity domain**, the **capture discipline**, the authoring **principles P-A1…P-A8**, the **two-tier KB storage** model, and the **generate-first build roadmap**.
- **Macro direction:** Petre, 2026-07-11 — *"as an engineer who needs help with routine tasks: if I need a bracket with a few holes, I just ask AI… AI drills down by asking assisting questions and showing actual brackets to confirm… if we can't converge, the user builds it manually and then AI + user create a dictionary entry for that bracket. It is like creating part/assembly configurators for all kinds of standard, shape-only, and custom objects, which AI adjusts for a specific situation."*
- **Version impact:** vision/scope ADR — no engine/core code in this arc. Carries a **minimal amendment to [ADR/0037](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md)** (the KB manifest vocabulary gains `tier` / `source` / `lock` / `override` / `origin`; see D13). No bundle/schema/Glossary/Manifesto change.

## §0 — What this ADR does

AIADRA reserved exactly the slots this experience needs. Identity is already the **recipe-hash, not the BREP** ([ADR/0031 D6](0031-aiadra-mechanical-v0.0.1-scope.md)), so the durable asset was always the parametric recipe. The **KB already grows as a by-product of building** ([ADR/0037 D8](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md), RAG-first), so a "dictionary entry" is a KB page. **Ring 2 left mutation granularity open** ([ADR/0026 §2](0026-ai-action-protocol-scope.md)) and ships **zero AI** ([ADR/0026 §0](0026-ai-action-protocol-scope.md) BYO-AI). And the **Display Representation contract + Studio viewport** ([ADR/0035](0035-display-representation-contract-and-topology-identity.md); Studio strand step 6) already renders real evaluated geometry. This ADR pins the authoring **copilot** that sits on top of that deterministic + display stack, and it mostly *composes* what exists rather than adding a parallel system.

## Decisions

### D1. The durable asset is the CONFIGURATOR (a parametric recipe + its intent), not the geometry
The reframe that makes AIADRA AI-native. What the engineer keeps and reuses is the **configurator** — a parametric feature-recipe template plus the design intent that governs it — not a one-off evaluated solid. This is native to recipe-hash identity ([ADR/0031 D6](0031-aiadra-mechanical-v0.0.1-scope.md)) and KB-grows-as-by-product ([ADR/0037 D8](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md)). It distinguishes AIADRA from every "AI draws CAD geometry" demo, which yields orphan geometry with no reusable, intent-bearing asset.

### D2. The interaction loop — elicit → retrieve → propose/show → refine → accept → (fallback-manual) → capture
The AI-aided design cycle, each phase riding named AIADRA machinery:
1. **Elicit** — narrow the space two ways: *questions* for non-visual constraints (load, fastener standard, material), *candidates* for shape. Answers become captured Requirements + `design_intent` ([ADR/0006](0006-object-type-requirement.md)), not ephemeral chat.
2. **Retrieve** — RAG over the configurator KB (D9/D10; [ADR/0037](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md) RAG-first) → ranked candidates.
3. **Propose + show** — each candidate is a *real, evaluated, validity-gated recipe* rendered through the Display Representation contract ([ADR/0035](0035-display-representation-contract-and-topology-identity.md)). Never a mockup (D3, P-A2).
4. **Refine** — adjust parameters or swap configurator, via controls or compilable-intent moves (P-A1).
5. **Accept → commit** — a single explicit Ring-2 accept ([ADR/0026](0026-ai-action-protocol-scope.md) propose→commit) makes it a real Part, intent attached and `satisfies`-linked ([ADR/0009](0009-relationship-type-satisfies.md)).
6. **Fallback → manual** — if convergence fails, the user authors directly with the deterministic feature ops (sketch/extrude/revolve/fillet/hole/chamfer).
7. **Capture → promote** — the result is abstracted into a new configurator (D7). The design vocabulary has grown.
**The flywheel:** what the AI can't find (2), the human builds (6); what the human builds becomes what the AI retrieves next (7→2). The vocabulary compounds with use — the moat.

### D3. The three-state candidate model — candidate recipe → evaluated display → committed Truth (arc 20260711-1 B1)
Three states are kept strictly separate so "no mockups" never manufactures Truth/audit clutter:
1. **Candidate recipe** — transient proposal material (a Ring-2 draft or an AI-side candidate); proposing never writes Product Truth.
2. **Evaluated display** — deterministic engine output from that candidate recipe: reproducible, validity-gated, safe to show *because* it is not a mockup. It is a **non-staging read over candidate recipe material** — the `NativeEngineReadContext` ([ADR/0035](0035-display-representation-contract-and-topology-identity.md)) — with **no Product Truth write and no audit event until human acceptance through Ring 2** (arc 20260711-6 N1).
3. **Committed Product Truth** — sidecars/events/relationships, written **only** after explicit human approval, through Ring 2 ([ADR/0026](0026-ai-action-protocol-scope.md)).
This aligns the vision to shipped contracts and is the basis of P-A2.

### D4. The configurator object model — five things, three sub-kinds
A **configurator** is a bundle of five things: (1) a **feature-recipe template** (the geometry DAG); (2) a **parameter schema** (exposed params, domains, defaults, relations); (3) a **concept-owned elicitation schema** (the questions that belong to the concept — a bracket asks mount/load/holes; a shaft asks Ø/length — making AI's questioning targeted and finite); (4) **design intent / Requirements** it is meant to satisfy; (5) a **validity domain** (D6). And three **sub-kinds**, split by *mechanism*, with a discriminator that gates the backing:
- **`select`** (standard/catalog) — choosing a **Component** ([ADR/0014](0014-object-type-component.md)); routes through local Component/Binding, never a direct catalog endpoint.
- **`generate`** (shape-only) — a parametric geometry recipe (the bracket; the core case).
- **`compose`** (assembly) — placements + mates + a parameterized count/pattern; depends on the assembly-composition scope ADR (arc 20260701-1).

### D5. A configurator is a KB ARTIFACT referencing Truth, NOT a Truth-Model Object Type (v1) + the promotion rule (arc 20260711-1 B2)
The configurator bundle mixes **Truth-backed engineering material** (template Part/Assembly/Component references, Requirements, released recipe examples, validation outcomes) with **knowledge/orchestration material** (elicitation prompts, ranking hints, retrieval tags, curation notes) — and the second class is exactly what the [ADR/0037](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md) KB exists to hold. Promoting `Configurator` to a first-class Truth-Model Object Type now would force lifecycle/Number/release/relationship/schema/validation surface **before the first bracket flow proves itself**, and risks accidentally solving the deferred configuration/variants problem. **Decision (v1):** a configurator is a **git-tracked KB artifact** (kind `configurator`, under [ADR/0037](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md) manifest discipline), carrying **stable local ids** for parameters/questions/validity-rules/examples. It **references canonical Truth where applicable** (template Part/Assembly/Component + Requirements) and **carries or links KB-owned golden recipes, command traces, and validation outcomes** (each `source_context`-attested) — it does not duplicate Truth, and its KB-owned examples are **not themselves Product Truth** (arc 20260711-6 N2, keeping the D5 boundary crisp). **The promotion rule:** `Configurator` becomes a first-class Truth-Model Object **only** when recurring workflows demonstrably need released configurator identity, relationship endpoints *to* configurators, or a change-controlled configurator lifecycle.

### D6. The layered validity domain (arc 20260711-1 architecture answer)
Four distinct planes — keep 3 and 4 separate (*buildable ≠ correct*):
1. **Parameter schema** — guards obvious invalid inputs (types, ranges, units).
2. **Validity domain** — rejects known-impossible parameter *regions* (a hole bigger than the face).
3. **OCCT** — validates *buildability* (the existing validity gate).
4. **Requirements / `satisfies`** — judges whether the result is *right* (design-intent validation, [ADR/0009](0009-relationship-type-satisfies.md)).

### D7. Capture/promotion inherits the acceptance-bundle discipline (arc 20260711-1 N4)
"By-product" must not mean "every one-off auto-promotes." A captured configurator requires a small acceptance bundle, analogous to a feature arc: (1) `source_context` attestation, (2) parameter schema, (3) elicitation schema, (4) ≥1 golden recipe, (5) ≥1 negative/repair trace or invalid-domain example, (6) references to the Truth artifacts it was abstracted from. This keeps the KB compounding without becoming uncurated prompt sediment. **Parameterizing a one-off is AI-assisted, not automatic** — the AI proposes "these look like your free parameters — adjustable?"; the human confirms.

### D8. The authoring principles P-A1…P-A8
- **P-A1** — *AI proposes recipes, parameters, and high-level design moves — never geometry.* Every move (e.g. "add a stiffening rib", "switch to an L-bracket") compiles to a configurator selection, a parameter update, or a feature-op sequence **before display or commit**; opaque geometry/topology that bypasses the engine is forbidden.
- **P-A2** — *Every geometry candidate shown is generated from an engine-evaluable candidate recipe, never hallucinated mesh/image geometry; it stays transient until human approval commits it through Ring 2.* (D3.)
- **P-A3** — *Intent is captured as first-class engineering material* (Requirements + `design_intent`; the part `satisfies` them), not ephemeral chat.
- **P-A4** — *The design vocabulary grows as a by-product — but promotion is curated, not automatic* (D7).
- **P-A5** — *Navigate the space, don't specify it:* prefer showing diverse candidates over exhaustive questioning; prefer retrieve-and-configure over generate-from-scratch.
- **P-A6** — *The human always holds the fallback and the final approval.*
- **P-A7** — *A configurator is a KB artifact* = recipe template + parameter schema + concept-owned elicitation schema + design-intent/Requirements + layered validity domain, *referencing* canonical Truth; it becomes a Truth-Model Object only when D5's promotion rule is met.
- **P-A8** — *The copilot is a BYO-AI Ring-5 client, not a hosted service;* orchestration policy lives client-side, never in Product Truth.

### D9. Two-tier KB storage — core-tier (packaged) + project-tier (git-tracked) (arc 20260711-2)
One [ADR/0037](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md) artifact shape, two homes and lifecycles:
- **Core KB** — ships **inside the domain Native Engine package** (`aiadra-mechanical`, and each future domain engine); read-only, released with the engine, **content-locked per project by the project-side digest lock (D10)** (not "version-pinned" — a version label is too weak, arc 20260711-2 B1). Domain knowledge travels with its domain engine ([ADR/0027](0027-aiad-positioning-and-native-engine-posture.md)). This repo's `Docs/KB/` is the *authoring source* of the core KB.
- **Project KB** — a **visible, git-tracked source tree** in the workspace (`KB/` or `Docs/KB/`); grows via curated capture (D7); travels/reviews/shares with the repo; P11-clean (git *is* the state). Only machine material lives under `.aiadra/`: `.aiadra/kb-lock.yaml` (the resolved lock, D10) and `.aiadra/kb-index/` (generated retrieval indexes, **git-ignored**, never authority).
- **Custom-KB scope is per-project** (Petre's call). A **per-user cross-project tier is named but deferred** (`user:` namespace reserved).
- **Reference, don't vendor:** a project references the installed engine's core KB and records a pin (D10); it does not copy the standard library into every repo. Targeted freeze = fork one configurator into the project KB, not whole-library vendoring.

### D10. KB retrieval — the digest lock, ranking vs suppression, namespaces, fork-to-customize (arc 20260711-2 B1/B2)
- **The pin is content-addressed** (a digest lock), not `kb_version`-labeled. The **project-side lockfile** (`.aiadra/kb-lock.yaml`) records, per core source: source namespace, Python distribution name+version, engine id + adapter schema version, `kb_version`, and a **manifest/tree/per-artifact content digest** (the load-bearing field), plus optional dev-install origin. It is a **list** of per-source entries (multi-engine evolves independently). Kept **distinct** from the manifest's `compatible:` block: the project lockfile is a **reproducibility lock** (exact resolved content); `compatible:` is a **compatibility declaration** (ranges) — the `package.json` / `package-lock.json` split. **`kb_version` is descriptive compatibility metadata only; the digest is the reproducibility identity** — never `kb_version` (arc 20260711-2 B1). This joins AIADRA's content-addressed-identity family (recipe-hash, `topology_signature`).
- **Ranking (soft) and suppression (hard) are separate mechanisms.** Retrieval *may* rank project artifacts higher (client-side policy, non-authoritative, never removes a candidate). A project artifact **suppresses** a core artifact **only** via an explicit, digest-qualified edge — `overrides: core:<engine_id>:…@<digest>`. No override edge → the core candidate stays in the pool.
- **Source-qualified ids:** `core:<engine_id>:…` / `project:…` / (`user:…` deferred). ID collisions are errors unless namespaced.
- **Fork-to-customize; never edit core in place.** Customizing a core configurator = capturing a project configurator that records a digest-backed `origin` to the core artifact. Determinism payoff: same core pin + same project-KB git state → the same candidate space.
- **Retrieval/merge/ranking lives in the Ring-5 client** (P-A8). A **static local KB-source discovery helper** (enumerate installed engine KB roots; return package/engine/manifest/digest; no embeddings, ranking, or hosting) is P11-clean, the same category as existing Native-Engine entry-point discovery, and may live in `aiadra-core.protocol` later; the first cut keeps discovery client-side.

### D11. Ring-5 BYO-AI orchestration — concept-owned schema vs client policy (arc 20260711-1 N2, QA3)
The **concept-owned elicitation schema** (question ids, labels, answer types, units, defaults, requirement/parameter bindings) lives *in the configurator artifact*. The **copilot orchestration policy** (when to ask vs show, how many candidates, how to diversify, which model prompt) lives in the **Ring-5 BYO-AI client** and is never Product Truth or schema. Nothing here introduces an AIADRA-hosted service, a core-side agent, or an embedding endpoint ([Manifesto P11](../Manifesto.md)).

### D12. The build roadmap — generate-first, thin metadata not a DSL (arc 20260711-1 N5)
- Aim the vision at all three sub-kinds, but **build `generate`-only, single-Part, shape-only first** — the **bracket witness**.
- Start as **thin metadata over existing feature recipes**, **not** a DSL; a richer configurator DSL (the [ADR/0026 §2](0026-ai-action-protocol-scope.md) open slot) must be *earned* by repeated pressure from real configurators.
- `compose` depends on the assembly-composition scope ADR (arc 20260701-1); `generate`-first is independent of it.

### D13. The co-landed ADR/0037 amendment — exact patch set (same commit as this ADR's acceptance)
[ADR/0037 D5](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md) described a single in-repo KB tree. This ADR's acceptance **co-lands** a minimal amendment to ADR/0037 in the **same commit** (arc 20260711-6 B2 — this is a concrete patch set, not a prose promise), applying exactly these seven changes:
1. **Add `configurator`** to the ADR/0037 D5 content classes (the fifth artifact kind, alongside feature-semantics / design-intent / golden-recipes / command-traces), with the D5 KB-artifact-not-Truth-Object boundary.
2. **Add core-tier / project-tier language** to ADR/0037 D5 shape+versioning: core KB ships as a domain-engine **package resource**; project KB is a **visible git-tracked workspace tree** (D9).
3. **Add the project-side resolved-lock vocabulary** — `.aiadra/kb-lock.yaml` as the **reproducibility lock** — **without moving the lock into the KB manifest**. The manifest keeps its `compatible:` **ranges**; the project lock pins **exact resolved content**. This is the **`package.json` (ranges) / `package-lock.json` (exact resolution)** split, stated normatively (arc 20260711-6 B1): `kb_version` is descriptive compatibility metadata, the **digest is the reproducibility identity**.
4. **Add `source` namespace rules:** `core:<engine_id>:…`, `project:…`, reserved `user:…`; id collisions are errors unless namespaced.
5. **Add `override` and `origin` semantics:** a **digest-qualified suppression edge** (`overrides: core:<engine_id>:…@<digest>`; soft ranking never suppresses) and **digest-backed fork lineage** (`origin`).
6. **Add the canonical-unit rule:** parameter and elicitation schemas carry unit-bearing or schema-fixed `_mm`/`_deg` fields — no prompt-only units.
7. **Preserve a clean deferral for the `pack:` interchange tier** and the marketplace posture to the forthcoming KB-interchange ADR (arc 20260711-5): this amendment introduces the **two-tier + retrieval** vocabulary only, and leaves room for `pack:` without deciding it.
The amendment is a **scoped addition** to ADR/0037 — it does not touch ADR/0037's benchmark / original-content-firewall / RAG-first decisions.

## Consequences

- **Positive:** the AIAD experience is pinned as ~70% composition of decided substrate; the durable asset (configurator) aligns with recipe-hash identity and the KB flywheel; every AI candidate is committable Truth by construction; intent ships attached and checked; the design vocabulary compounds; determinism (reproducible candidate space) is preserved via the digest lock; P11/BYO-AI held throughout.
- **Deferred:** `Configurator`-as-Truth-Object (promotion rule); the per-user KB tier; `compose` (assembly substrate); the configurator DSL; the interchange/marketplace ADR (arc 20260711-5).
- **Watches:** stable ids for all KB lists; canonical units; `select` routes catalog via Component/Binding; the ranking-vs-suppression split must not regress into semantic shadowing.

## Alternatives considered

- **Configurator as a first-class Truth-Model Object Type now** — rejected for v1 (D5): forces a large surface before the first flow proves itself; superseded by the promotion rule.
- **P-A2 as "every candidate is committed Truth"** — rejected (D3): overloads "committable"; manufactures audit clutter. Replaced by the three-state model.
- **A configurator DSL from the start** — rejected (D12): must be earned; thin metadata over recipes first.
- **A single-tier / per-user-only KB** — rejected (D9): per-project git-tracked is P11-clean, reviewable, shareable; per-user reopens provenance/sync questions and is deferred.
- **Vendoring the core KB into each project** — rejected (D9): bloats repos and couples to a snapshot; reference + digest-pin instead.
