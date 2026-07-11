# ADR/0037 — Modeling-paradigm benchmark + AI-authoring knowledge architecture

## Frontmatter

- **Status:** **Accepted** — 2026-06-10 (arc 20260609-3; two-round convergence Claude1+draft / Codex1 / Claude2 close. Codex1 direction-accept absorbed in full: B1 operational firewall hardened into D3/D7, N1 public-claim guardrails into D1, N2 falsifier axes into D6, N3 KB manifest into D5, N4 acceptance bundle into D8).
- **What it is:** the strategic ADR that gives the "A" in AIAD its substance. It (1) extends the Creo 10 benchmark from *how models look* ([ADR/0033 D1](0033-studio-display-ux-vision.md)) to ***how models are built*** — the modeling paradigm — under the same non-clone guardrail; (2) pins the **legal boundary** for proprietary reference material; (3) pins the **AI-authoring knowledge architecture** (an original knowledge base, RAG-consumed, BYO-AI-neutral) — closing the deferral in [ADR/0026 §10 item 1](0026-ai-action-protocol-scope.md); (4) pins **RAG-first / fine-tune-later** sequencing with an explicit falsifier; (5) pins the staged **feature-taxonomy roadmap** for `aiadra-mechanical` without building it.
- **Macro direction:** Petre, 2026-06-09/10 — *"extend the benchmark to the way Creo 10 builds models — the core principles, the whole core concepts… use the Core to directly allow access by an AI model to the very core commands of our system — the Augmentation-by-AI part."* Endorsed positions from the arc discussion are pinned here.
- **Version impact:** none — vision/scope ADR. No code, no bundle/schema/Glossary/Manifesto change in this arc.

## §0 — What this ADR does

AIADRA's architecture reserved exactly the slots this direction needs: [ADR/0026 Decision §2](0026-ai-action-protocol-scope.md) left mutation granularity intentionally open for kernel-level operations and a future CAD-model DSL; ADR/0026 §10 deferred the Knowledge Base / RAG scope "until concrete agent-use cases drive requirements"; and the Truth Model already treats a Part as a feature recipe ([ADR/0031 D6](0031-aiadra-mechanical-scope.md) recipe-hash identity; [ADR/0035 D2](0035-display-representation-contract-and-topology-identity.md)'s `F12(ROUND_5)`-modeled display identity). An AI that authors models by composing feature commands is the use case arriving. This ADR pins the paradigm benchmark, the knowledge architecture that feeds such an AI, the legal discipline for the reference material that inspires both, and the order in which the learning machinery is built.

## Decisions

### D1. Creo 10's modeling paradigm is the behavioral benchmark for AIADRA authoring — paradigm, never product
The benchmark extends one level deeper than ADR/0033 D1: **feature-based, recipe-first, reference-aware, regeneration-semantic** authoring — the ontology of mechanical design intent that Creo's paradigm represents (features as the unit of intent; sketches anchoring profiles; parent-child references; deterministic regeneration; patterns and datums as first-class structure). The **non-clone guardrail hard lines** (starter set; Codex1 Q1 refines):
- No PTC/Creo/Granite naming in any public surface (API kinds, schema fields, UI labels) where our own vocabulary serves.
- No mirroring of Creo UI metaphors, menu/ribbon taxonomies, or dialog flows as such — Studio's command model ([ADR/0033 D9](0033-studio-display-ux-vision.md)) grows from our command taxonomy.
- No transliteration of Toolkit API shapes (signatures, object models, naming schemes) into Ring 2 kinds or engine handlers — operations are designed against OUR Truth Model and OCCT, then *checked* against the paradigm for conceptual completeness.
- "No UI-metaphor mirroring" explicitly includes model-tree taxonomy, feature-dialog grouping, iconography, tutorial/example ordering, and command grouping **where those are distinctive to Creo** (Codex1 N1); industry-generic concepts remain fair game.
- "Creo-like workflow feel" means a Creo-proficient engineer recognizes the *concepts* and is productive quickly — a **usability target, not a correspondence target** (Codex1 Q1): copy the engineering concept when it is industry-generic; never product expression, public naming, command grouping, dialog structure, example sequence, Toolkit object model, or UI taxonomy.
- **Public-claim guardrail** (Codex1 N1): until D4's attorney/trademark review clears anything stronger, public language defaults to *"benchmark-informed by established parametric CAD practice"* (or, where specificity is needed, *"Creo 10 used as a private acceptance reference"*). No public "Creo-benchmarked" branding before clearance.

### D2. Proprietary reference material is research material ONLY (the ADR/0027 posture, extended)
The PTC Creo 10 reference set (user help: Part Modeling / Sketcher / Assembly Design / Detailed Drawings; the Creo Toolkit book) lives at `Docs/Creo10BenchmarkDocs/` — **local-only, git-ignored** (fence enacted and untracked-verified 2026-06-10), never committed, never shipped, never embedded in any distributed artifact: not in the KB, not in documentation, not in any training or fine-tuning dataset we distribute. The same rule applies automatically to any future proprietary reference material (the folder comment carries the posture).

### D3. Concepts, not content — the original-content firewall (operational, not asserted; Codex1 B1)
Feature-based modeling concepts, taxonomies, and workflow patterns are methods of operation: learnable, re-expressible, and ours to realize against OCCT. PTC *expression* is not reused: no text, no document structure, no example sequences, no API signatures. Where a concept has an industry-generic name (extrude, revolve, fillet, datum plane), the generic name is ours to use; where the name is Creo-distinctive, we name it ourselves.

**The firewall — process rules with pass/fail force** (the KB implementation arc inherits these as acceptance criteria):
1. **Context exclusion:** proprietary documents are NEVER present in the prompt/context window of any AI run that produces shippable artifacts — KB pages, code, public docs, examples, command traces, or training rows. Paradigm study (human or AI reading the PTC docs) happens in sessions/notes that produce **local-only research notes**, nothing shippable.
2. **The rewrite gate:** proprietary-derived research notes become shippable ONLY by explicit rewrite — authored against AIADRA implementation artifacts (ADRs, schemas, engine handlers, tests, golden recipes) in AIADRA vocabulary — and then reviewed as original expression. Paraphrase-from-the-page never ships; if originality cannot be attested, the artifact is excluded.
3. **Authority citation:** shippable KB pages cite AIADRA artifacts (and public standards where applicable) as their authority — never proprietary documentation, and never mirroring its structure.
4. **Naming caution:** this discipline is called **"original-content discipline (clean-room-style)"** — the stronger legal term of art "clean room" is not claimed unless D4's attorney review approves it.

### D4. Attorney-review additions (the [ADR/0034](0034-licensing-and-third-party-kernel-compliance.md) list grows by three)
(a) The concepts-not-content line for a commercial AIAD product whose paradigm benchmark is a competitor's product; (b) the clean-room threshold for KB text authored after reading PTC documentation — whether the D3 process discipline suffices or a stricter separation is advisable; (c) trademark posture for any public "Creo-benchmarked" claims. None block work under D2/D3 discipline; all are release-prerequisite confirmations like ADR/0034's existing items.

### D5. The knowledge architecture — an ORIGINAL knowledge base, RAG-consumed, BYO-AI-neutral
Closes ADR/0026 §10 item 1. Content classes (all original, all shippable):
1. **Feature-semantics documents** — per operation kind: meaning, parameters, Truth-Model footprint, invariants, failure modes — written against our schema and citing our ADRs.
2. **Design-intent vocabulary** — the conceptual layer: intent → feature-composition patterns, reference discipline, regeneration behavior — re-expressed per D3.
3. **Worked examples / golden recipes** — real models authored through our own protocol: recipe + expected validation outcomes + display baselines.
4. **Command traces** — protocol-level transcripts (propose → modify → validate → commit, with ValidationReports) generated by our own system runs, carrying the D7 provenance labels.
Consumption: **retrieval into any agent's context** — cloud frontier models, local open-weights models, deterministic scripts — per [ADR/0026 §0](0026-ai-action-protocol-scope.md) (the core ships zero AI model code; this ADR changes nothing about that). **No hosted KB service, no AIADRA-operated embedding endpoint** — project/local-first files per [Manifesto P11](../Manifesto.md) ("AIADRA Core hosts nothing" is load-bearing here).

**Shape + versioning** (Codex1 N3 absorbed): in-repo, git-tracked, plain-markdown-first (human-reviewable provenance). Versioning is **per capability/package via a compatibility manifest** (`Docs/KB/manifest.yaml` or equivalent: `kb_version`, compatible `aiadra-core` range, compatible engine-package ranges, source ADR/schema/test refs, retrieval tags) — NOT a single lockstep with `aiadra-core`, because engine-specific feature semantics version with their engine (`aiadra-mechanical` + its adapter schema), while Ring 2 command semantics version with core. **Embedding/vector indexes are generated local artifacts, never source authority — git-ignored** unless a future ADR explicitly changes posture. **KB v1 scope** (Codex1 Q3): Ring 2 command semantics + mechanical feature semantics (current feature set) + golden recipes + the trace provenance schema; deferred: cross-project/global KB, hosted retrieval of any kind, fine-tune dataset assembly.

### D6. RAG-first, fine-tune-later — pinned sequencing with a falsifier
The "fine-tuning is cheaper" intuition inverts under real costs: the **dataset** is the dominant cost and presupposes the KB + a mature command surface; weights-baked knowledge goes **stale per release** (the Tier-1 surface moved 0.12.0 → 0.13.0 the day this arc opened) and costs a retrain + behavioral re-validation cycle; fine-tuning teaches *behavior*, not reliable, citable *facts* — and citability aligns with the Manifesto's explainability posture; and a small fine-tuned model flooding the validation gate with rejects burns the trust an AIAD platform sells. Therefore:
- **Phase 1 — KB + RAG** (D5): works with every BYO-AI model the day it exists.
- **Phase 2 — golden traces accumulate from real use as a by-product** (the endorsed crux: *the fine-tuning dataset for free*), under D7 provenance.
- **Phase 3 — a fine-tuned local open-weights model becomes a shipped LOCAL OPTION** (cheap / offline / private) — one BYO-AI choice among several; never the platform's marriage.
**Falsifier — four named evaluation gates** (Codex1 N2; numeric thresholds land with the evaluation arc, the AXES are pinned now so the bar cannot move casually):
- **Coverage gate:** traces cover each shipped feature family, error/recovery paths, validation failures, and cross-feature edits — not just happy-path creation.
- **Economics gate:** real measured workflows show RAG context cost/latency is a dominant bottleneck AFTER retrieval compression and caching have been tried.
- **Quality gate:** a local candidate model reaches a named pass rate on command validity, validation-pass-after-bounded-repair, provenance correctness, and refusal on unsupported operations.
- **Staleness gate:** retraining/revalidation cost is acceptable for the expected release cadence.
Fine-tuning moves earlier only when ALL four gates are evidenced in a short evaluation report. **Cheap GPU-hours are not a falsifier** (Codex1 Q4).

### D7. Trainable-materials provenance — auditable by construction (hardened per Codex1 B1)
Every command trace and golden recipe carries:
- **`source_context` attestation** — an explicit label proving NO proprietary documents were in the producing context (the D3 rule 1 invariant, recorded per artifact, not asserted per project);
- producing-actor material: actor (`human` / `agent`), model identity, prompt/template id, and retrieval corpus ids when AI-authored;
- system-state material: `aiadra-core` + engine package versions, bundle/schema versions, workspace/event boundary;
- outcome material: the full validation outcomes.
A future fine-tuning dataset is then assembled by **filtering on these labels** — never by laundering; every row is traceable to AIADRA-owned artifacts and validation outcomes, with proprietary-reference exclusion explicit (Codex1 Q6). An artifact whose provenance cannot be attested is excluded. The trace schema's exact shape lands with the KB implementation arc, carrying these fields as its floor.

### D8. The feature-taxonomy roadmap — pinned, staged, NOT built here
`aiadra-mechanical` speaks sketch(rectangle|circle) + extrude today. The paradigm implies the staged growth path: **fillet/round** (first — the tangent display classifier and the HLR smooth-class lane are already proven and waiting) → **revolve / sweep** → **hole-as-feature** → **patterns** → **datum features** → **references / parent-child + regeneration semantics** (the paradigm-defining hard part — where general topological naming, deferred since ADR/0035, gets real). Per-feature discipline — the **acceptance bundle** every feature arc ships (Codex1 N4 made it explicit):
1. the authoring operation + schema/adapter payload;
2. regeneration behavior + parent/child invalidation behavior, where applicable;
3. display identity + HLR/display-mode implications;
4. the KB feature-semantics page;
5. a golden recipe **plus at least one negative/repair trace**.
The KB grows as a *by-product of building*, never as a documentation debt — the AI's knowledge and the deterministic engine stay in lockstep. Each step is its own scoped arc with its own Codex loop; this ADR pins the order and the discipline only.

### D9. Boundary + strand relations
- **This arc ships no code.** The KB implementation, the first taxonomy arcs, and any evaluation harness are follow-up arcs.
- The **Display strand** (ADR/0033 steps 5–6) proceeds independently; the **Licensing implementation arc** (ADR/0034 D6) gains the D4 items.
- Nothing here weakens ADR/0026 §0 (BYO-AI), Manifesto P11 (no hosted services), or ADR/0027 (Native Engines use kernels as libraries; third-party *applications* — and now their documentation — are research material only).

## Consequences
- AIADRA gains a pinned answer to "what does the AI learn from, and what language does it speak?" — an original KB feeding any model, over a command surface grown against a proven paradigm.
- The feature-taxonomy roadmap and the KB grow in lockstep (D8's per-feature discipline), so agent-usable knowledge tracks the engine's real capabilities release by release.
- The PTC reference set is usable for what it is — paradigm study — with the legal exposure fenced (D2–D4).
- The fine-tuning option matures from a cost intuition into an evidenced, falsifiable phase gate (D6).

## Alternatives rejected
- **Fine-tune-first on an open-weights model** — inverted cost intuition: the dataset presupposes the KB; staleness per release; behavior-not-facts; quality risk at the validation gate (D6 rationale).
- **Embedding PTC-derived content in the KB / training data** — legal exposure and contrary to the original-content posture; rejected outright (D2/D3).
- **A hosted knowledge service** — violates Manifesto P11; the KB is files + consumer-side retrieval (D5).
- **Splitting into two ADRs now** (paradigm vision + KB scope) — the decisions interlock (the paradigm defines what the KB documents; the KB defines what the AI consumes; sequencing binds both); ONE vision ADR with implementation detail deferred to its arcs keeps the rationale whole. Codex1 Q5 may overturn this; the split remains cheap later.
- **Wrapping Creo / Toolkit integration** — out per ADR/0027; the paradigm is benchmarked, the product is not touched.

## References
- [ADR/0026](0026-ai-action-protocol-scope.md) — §0 BYO-AI; Decision §2 open mutation granularity; §10 the KB deferral this ADR closes.
- [ADR/0027](0027-aiad-positioning-and-native-engine-posture.md) — AIAD positioning; research-material-only posture (extended by D2).
- [ADR/0033](0033-studio-display-ux-vision.md) — D1 the benchmark-not-clone guardrail (extended by D1 here); D9 the command model.
- [ADR/0034](0034-licensing-and-third-party-kernel-compliance.md) — the licensing/attorney frame (D4 joins it).
- [ADR/0031](0031-aiadra-mechanical-scope.md) / [ADR/0035](0035-display-representation-contract-and-topology-identity.md) — recipe-first identity (the paradigm already in the Truth Model).
- Arc `Docs/Discussions/20260609/20260609-3/` — Claude1 (positions + Q1–Q6) / this draft / Codex1 (pending).

## Amendment A1 — two-tier KB storage + retrieval vocabulary (co-landed with [ADR/0039](0039-the-aiad-authoring-model.md), 2026-07-11, arc 20260711-6)

[ADR/0039 D9/D10/D13](0039-the-aiad-authoring-model.md) extends the KB architecture from a single in-repo tree (D5) to a **two-tier** model. This amendment is a **scoped addition** — it does not touch D1 (paradigm benchmark), D2–D4 (original-content firewall / attorney frame), D6 (RAG-first), or D7 (provenance). The seven changes:

- **A1.1 — `configurator` content class.** The D5 content classes gain a fifth artifact kind, **`configurator`** — a parametric feature-recipe template + parameter schema + concept-owned elicitation schema + design-intent/Requirements refs + validity domain. Per [ADR/0039 D5](0039-the-aiad-authoring-model.md) it is a **KB artifact that references canonical Truth, NOT a Truth-Model Object Type** (until the D5 promotion rule is met); its KB-owned golden recipes/traces/examples are not themselves Product Truth.
- **A1.2 — core-tier / project-tier.** D5's "in-repo, git-tracked" shape is refined into two homes: **core KB** ships as a domain-engine **package resource** (read-only, released with the engine); **project KB** is a **visible git-tracked workspace tree** (`KB/` or `Docs/KB/`). Generated indexes stay local/git-ignored (unchanged from D5).
- **A1.3 — project-side resolved lock (distinct from the manifest).** A **`.aiadra/kb-lock.yaml`** records the **exact resolved core-KB content** per source (manifest/tree/per-artifact **digest**, plus source namespace, distribution+version, engine id, adapter schema version, `kb_version`). The KB **manifest** keeps its `compatible:` **ranges**; the **project lock pins exact content** — the `package.json`(ranges) / `package-lock.json`(exact) split. **`kb_version` is descriptive compatibility metadata; the digest is the reproducibility identity.** The lock does **not** live in the KB manifest.
- **A1.4 — source namespaces.** KB artifact ids are source-qualified: **`core:<engine_id>:…`**, **`project:…`**, reserved **`user:…`**. Id collisions are errors unless namespaced.
- **A1.5 — `override` / `origin` semantics.** Suppression of a core artifact by a project artifact is **only** via an explicit **digest-qualified edge** (`overrides: core:<engine_id>:…@<digest>`); soft retrieval ranking never suppresses. A fork records a **digest-backed `origin`** to the artifact it descends from.
- **A1.6 — canonical units.** Parameter and elicitation schemas carry unit-bearing or schema-fixed **`_mm`/`_deg`** fields — no prompt-only units.
- **A1.7 — `pack:` deferral → decided in [ADR/0041](0041-kb-interchange-and-ecosystem.md).** This amendment introduced the two-tier + retrieval vocabulary only and left room for the interchange `pack:` source tier without deciding it. That deferral is now **filled by [ADR/0041](0041-kb-interchange-and-ecosystem.md)** (KB Interchange & Ecosystem, 2026-07-11): the `pack:<publisher>/<name>:` read-only digest-locked source tier, the two-group import lock (content lineage + license/import state), the data-only prompt-injection-hardened trust boundary, and the ecosystem-not-Core marketplace posture.
