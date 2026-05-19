---
name: adr-0021-relationship-types-v-and-v
status: accepted
date: 2026-05-19
supersedes: 0005-object-type-part (partial — §11 line 214 EvidenceArtifact-target half of `tested_against` pre-declaration; direct Part → EvidenceArtifact deferred to test execution model); 0007-object-type-assembly (partial — §11 line 245 EvidenceArtifact-target half of `tested_against` pre-declaration; direct Assembly → EvidenceArtifact deferred to test execution model); 0020-object-type-test-procedure (partial — Consequences line 236 `cites` forward reference direction clarified — seed pins Requirement → EvidenceArtifact lifting ADR/0019's deferral, TestProcedure-as-source deferred per Alternatives §C2)
superseded_by: none
resolves: []
---

# ADR/0021 — Relationship types: V&V family (`verifies` + `tested_against` + `cites`)

## Status

**Accepted** — 2026-05-19. Combined ADR for three relationship types — relationship types 9, 10, and 11 in the bundle's `relationship/<type>.schema.json` directory after the eight already pinned. **Closes the V&V wiring** for the V&V Object Type triad ([Part](0005-object-type-part.md) / [Assembly](0007-object-type-assembly.md) + [TestProcedure](0020-object-type-test-procedure.md) + [EvidenceArtifact](0019-object-type-evidence-artifact.md) + [Requirement](0006-object-type-requirement.md)). All three inherit [ADR/0009](0009-relationship-type-satisfies.md)'s thirteen base trace-relationship pattern fields verbatim; **no new pattern fields at the base level**. **First instance of criterion-level addressing on Requirement-side endpoints** lands via `endpoints[].fact_ref` (target-side, for `verifies`) and `source_fact_ref` (relationship-record-level, for `cites` because its source is implicit); reopens [ADR/0009 §"Alternatives §E"](0009-relationship-type-satisfies.md)'s long-deferred criterion-level addressing under the condition ADR/0009 named (TestProcedure / EvidenceArtifact / `verifies` taxonomy now exists). **Lifts the Requirement-to-EvidenceArtifact citation deferral** from [ADR/0019 §"Decision §5"](0019-object-type-evidence-artifact.md) via `cites`. **Resolves the wrong-verb guardrail-with-pending-resolution-path** from [ADR/0020 §"Decision §5"](0020-object-type-test-procedure.md) via `verifies`. **Three partial supersessions** of prior ADRs per the frontmatter (EvidenceArtifact-target half of `tested_against` pre-declaration deferred to test execution model; ADR/0020's `cites` forward reference direction clarified). **Per-type cross-project asymmetry:** `verifies` opt IN (mirrors `satisfies`); `tested_against` opt OUT (target-Type-governs per [ADR/0013](0013-relationship-type-allocates-to.md)); `cites` opt IN (with EvidenceArtifact-specific rationale per Decision §4). **Verification-method consistency** is tooling-aided diagnostic, not schema-enforced (per [Manifesto P11](../Manifesto.md) + "default" framing in [ADR/0006 §7](0006-object-type-requirement.md)).

After ADR/0021, the named relationship-type catalogue from [ADR/0009 §3](0009-relationship-type-satisfies.md) is operationally complete except `derived_geometry_from` (awaits FreeCAD Domain Adapter scope per [Manifesto P12](../Manifesto.md)).

## Context

Discussion trail in [`Docs/Discussions/20260519/20260519-11/`](../Discussions/20260519/20260519-11/). [Codex1](../Discussions/20260519/20260519-11/Codex1.md) produced three blockers and four non-blockers; all three blockers tightly scoped and structurally addressed in [Claude2](../Discussions/20260519/20260519-11/Claude2.md); [Codex2](../Discussions/20260519/20260519-11/Codex2.md) signed off. All three close conditions met:

1. Part/Assembly → EvidenceArtifact predeclaration partial supersession — encoded in frontmatter `supersedes:`, Pre-declared-constraints table, and the new Consequences entry.
2. ADR/0020 line 236 `cites` direction clarification — encoded in frontmatter `supersedes:`, Pre-declared-constraints table, and the new Consequences entry.
3. `cites` direct external EvidenceArtifact rationale strengthened — Decision §4 has a full EvidenceArtifact-specific cross-project subsection (local approval / no Binding Object / Revision-content-hash-implies-attachment-chain / Float-vs-Fixed posture); Decision §8 has explicit Float-external + Fixed-external validation rules.

Four pressures converge:

1. **V&V family coherence argued for combined ADR.** Three tightly coupled relationship types — change in `cites` semantics affects `verifies` semantics affects `tested_against` semantics; criterion-level addressing applies to two of three; verification-method consistency anchors `verifies` to `tested_against`-execution; the wrong-verb cuts from ADR/0019 / ADR/0020 are most cleanly settled together. Precedent: [ADR/0012](0012-relationship-types-derived-from-and-refines.md) combined `derived_from` + `refines`.
2. **Criterion-level addressing reopens with concrete use case.** ADR/0009 §"Alternatives §E" deferred criterion-level on the principled basis that "TestProcedure / EvidenceArtifact ADRs and the verification taxonomy" weren't yet in scope. They now are. A `verifies` claim is naturally per-criterion ("this procedure verifies acceptance criterion ac_temp_range_test of REQ-000058"); a `cites` claim is naturally per-criterion ("this Requirement's criterion ac_load_bearing is supported by EVD-000043"). Decision §6 lands the primitive.
3. **Cross-project per-type asymmetry surfaces.** `verifies` targets Requirements (opt IN, mirrors `satisfies`); `tested_against` targets local-deliverable TestProcedures (opt OUT, target-Type-governs); `cites` targets EvidenceArtifacts (opt IN, with explicit EvidenceArtifact-specific rationale per Decision §4 — EvidenceArtifact differs from Requirement on local-approval / Binding-Object / integrity-anchoring dimensions and needed its own justification beyond shape-only inference per [Codex1 Blocker 3](../Discussions/20260519/20260519-11/Codex1.md)). The deliverable-vs-emergent governing principle from [ADR/0020 §"Decision §5"](0020-object-type-test-procedure.md) interacts with but does not directly determine cross-project posture.
4. **Verification-method consistency posture needs explicit choice.** TestProcedure carries `verification_method` per [ADR/0020 §2](0020-object-type-test-procedure.md); Requirement carries `default_verification_method` per [ADR/0006 §7](0006-object-type-requirement.md). The `verifies` relationship is where these meet. ADR/0021 picks tooling-aided diagnostic over schema-enforced equality (the "default" framing in ADR/0006 §7's field name admits divergence; Manifesto P11 forbids Core enumerating project-policy methodology orderings; project policy may escalate). Decision §7.

## Pre-declared constraints honored

| Constraint | Source | Disposition |
|---|---|---|
| `verifies` (TestProcedure → Requirement) pre-declared | [ADR/0006 §C3 line 109 + §"Decision 12" line 300](0006-object-type-requirement.md), [ADR/0020 §"Decision §5"](0020-object-type-test-procedure.md) | Honored — relationship type 9 lands per Decision §2. |
| `verified_by` / `tested_against` (Part / Assembly → TestProcedure) pre-declared | [ADR/0005 §11 line 214](0005-object-type-part.md), [ADR/0007 §11 line 245](0007-object-type-assembly.md) | Honored — relationship type 10 (`tested_against`, target = TestProcedure) lands per Decision §3. |
| `verified_by` / `tested_against` (Part / Assembly → EvidenceArtifact) pre-declared | [ADR/0005 §11 line 214](0005-object-type-part.md), [ADR/0007 §11 line 245](0007-object-type-assembly.md) | **Partially superseded / deferred by ADR/0021.** Direct deliverable-to-evidence edge is NOT in the seed `tested_against` shape (which keeps target = TestProcedure only per Decision §3). The Part / Assembly → EvidenceArtifact link belongs with the future test execution model, which can atomically bind procedure-revision + executed-run + produced-evidence + tested-Object without overloading `tested_against` with execution semantics. Until the test execution model lands, the chain expresses indirectly via `Part tested_against TestProcedure ←(future test execution record)→ EvidenceArtifact`. See Consequences. |
| Requirement-to-EvidenceArtifact citation deferred to V&V ADR | [ADR/0019 §"Decision §5" + §"Alternatives §C"](0019-object-type-evidence-artifact.md) | Honored — relationship type 11 (`cites`) lands per Decision §4, lifts the deferral. |
| `cites` forward reference direction | [ADR/0020 §"Decision §5" line 236](0020-object-type-test-procedure.md) | **Partially clarified by ADR/0021.** ADR/0020 line 236 named the relationship as "`cites` (TestProcedure → EvidenceArtifact)" while simultaneously claiming it would lift ADR/0019's Requirement-to-EvidenceArtifact deferral (two different directions). ADR/0021 pins seed `cites` as `Requirement → EvidenceArtifact` per Decision §4, lifting ADR/0019's deferral cleanly. TestProcedure-as-source for `cites` is deferred per Alternatives §C2 (procedure-cites-prerequisite-evidence belongs with the test execution model). |
| `allocates_to → TestProcedure` wrong-verb guardrail: product Requirements awaiting verification target the future `verifies` edge | [ADR/0020 §"Decision §5"](0020-object-type-test-procedure.md) | Honored — `verifies` per Decision §2 is now the right verb. The wrong-verb guardrail from ADR/0020 stays in force; the resolution path now exists. |
| Thirteen base trace-relationship pattern fields | [ADR/0009 §"Pattern declaration"](0009-relationship-type-satisfies.md) | Inherited verbatim for all three V&V types; no new pattern fields at the base level. |
| Criterion-level `fact_ref` on target endpoint deferred until V&V taxonomy hardens | [ADR/0009 §"Alternatives §E" + §"Decision §2"](0009-relationship-type-satisfies.md) | **Reopened by this ADR.** Criterion-level addressing lands as optional sub-field on Requirement-side endpoints for `verifies` and `cites` per Decision §6. Per-relationship-schema opt-in: `verifies` opts in (target-side `endpoints[].fact_ref`); `cites` opts in (source-side `source_fact_ref`); `tested_against` does NOT opt in (no Requirement endpoint); `satisfies` does NOT opt in in this bundle (separate Schema Change Note if retrofit needed). |
| `coverage` / `satisfaction_extent` / `evidence_ref` / `verification_state` properties deferred | [ADR/0009 §"Consequences"](0009-relationship-type-satisfies.md) | Mostly **still deferred** — Decision §6 carries criterion-level addressing only. Coverage roll-up, verification-state machine, and evidence aggregation logic deferred to future Schema Change Notes when production case surfaces. Rationale in Alternatives §G. |
| Target-Type-governs cross-project policy | [ADR/0013 §"Cross-project"](0013-relationship-type-allocates-to.md), [ADR/0008 §4](0008-cross-project-object-identity.md) | Honored — `verifies` opts IN (target is Requirement; mirrors `satisfies`); `tested_against` opts OUT (target is local TestProcedure deliverable); `cites` opts IN with explicit EvidenceArtifact-specific rationale per Decision §4 (not inferred from shape). |

## Alternatives Considered

### Scope — combined vs split

**A1. Three separate ADRs sequentially.**

> **Rejected.** Coordination cost: criterion-level addressing applies to two of three; verification-method consistency anchors verifies-to-tested_against-execution; wrong-verb cuts from ADR/0019 / ADR/0020 are most cleanly settled together; cross-project per-type policy needs the full picture. Three arc boundaries introduce re-litigation risk.

**A2. Combined ADR (one ADR; three relationship types).** *Chosen.* Precedent: [ADR/0012](0012-relationship-types-derived-from-and-refines.md). The V&V family is even more tightly coupled.

### `tested_against` source Type union

**B1. Source Type = Part | Assembly only in seed.** *Chosen — see Decision §3.* Physically-testable engineering deliverables; matches ADR/0005 §11 / ADR/0007 §11 pre-declarations exactly (for the TestProcedure-target half).

**B2. Source Type = Part | Assembly | Component.** Component-as-source: a Component (consumer's local Binding Object for a purchased item) was tested against a TestProcedure.

> **Defensible but deferred.** Component is a Binding Object; the actual physically-tested entity is the upstream Object. Defer to Schema Change Note when concrete need surfaces.

**B3. Source Type = Part | Assembly | Component | SoftwareModule.** Add software testing.

> **Rejected (for seed).** Software tests have their own taxonomy (unit / integration / contract / property-based / fuzz) that doesn't fit naturally into the four-method `verification_method` enum. Defer until a software-V&V-specific ADR or a software-test taxonomy emerges.

### `cites` source Type union

**C1. Source Type = Requirement only in seed.** *Chosen — see Decision §4.* Lifts ADR/0019's deferral; single source Type keeps the seed clean.

**C2. Source Type = Requirement | TestProcedure.** TestProcedure-as-source: a TestProcedure cites prior evidence (e.g., calibration certificates required to execute the procedure).

> **Defensible but deferred.** Procedure-cites-evidence is a real engineering pattern but conflates two distinct relationships: (i) "this procedure produced this evidence record" (deferred per [ADR/0020 §"Consequences"](0020-object-type-test-procedure.md) test execution model) and (ii) "this procedure cites prerequisite evidence." Both deferred until test execution model lands.

### `cites` target Type union

**D1. Target Type = EvidenceArtifact only in seed.** *Chosen — see Decision §4.*

**D2. Target Type = EvidenceArtifact | Requirement.** Generic "this Requirement cites this other Requirement / this Evidence" relationship.

> **Rejected.** Requirement-to-Requirement citation is already covered by `derived_from` / `refines` per [ADR/0012](0012-relationship-types-derived-from-and-refines.md). Adding citation-of-Requirement here would create relationship-type overlap and ambiguity about which verb to use.

### Verification-method consistency posture

**E1. Schema-enforce equality at release.** `TestProcedure.verification_method == Requirement.default_verification_method` (or per-criterion `verification_method` per [ADR/0006 §"Decision §6"](0006-object-type-requirement.md)) is a hard-fail validation at release.

> **Rejected.** [ADR/0006](0006-object-type-requirement.md)'s field name is `default_verification_method` — the "default" framing implies the actual verification method may differ. Strict equality at release would force every project to either override the Requirement's `default_verification_method` to match the actual procedure (awkward when multiple procedures verify) or wrap each `verifies` in a project-policy override mechanism that doesn't exist in seed.

**E2. Tooling-aided diagnostic; no schema enforcement.** *Chosen — see Decision §7.* Project-policy strictness escalation deferred to Schema Change Note.

**E3. Schema-enforce taxonomic compatibility (stricter-method-OK).**

> **Rejected.** The "stricter than" ordering is project-policy-specific; AIADRA Core enumerating an ordering contradicts [Manifesto P11](../Manifesto.md).

### Criterion-level addressing surface area

**F1. NO criterion-level addressing in seed.** Whole-Requirement endpoints only; mirrors [ADR/0009 §"Decision §2"](0009-relationship-type-satisfies.md).

> **Rejected.** ADR/0009 §"Alternatives §E" deferred criterion-level *specifically* because TestProcedure / EvidenceArtifact / `verifies` taxonomy wasn't yet in scope. The deferral was conditional; the condition is now met. Continuing the deferral when the load-bearing use case is now live would be the deferred-by-default anti-pattern.

**F2. Optional criterion-level addressing on Requirement-side endpoints for `verifies` and `cites`.** *Chosen — see Decision §6.* Per-relationship-schema opt-in (Decision §9 makes opt-in explicit).

**F3. Criterion-level addressing on `tested_against` too.**

> **Rejected.** `tested_against` has neither endpoint as Requirement; criterion-level scope doesn't apply.

### Coverage / verification_state / evidence_ref properties

**G1. Land coverage / verification_state / evidence_ref properties on relationship records.**

> **Rejected (still deferred).** Each presupposes either aggregation logic depending on usage patterns we don't yet have, or a state machine depending on the test-execution model (deferred per [ADR/0020 §"Consequences"](0020-object-type-test-procedure.md)), or is redundant with `cites` graph traversal.

**G2. Defer all three.** *Chosen.* Schema Change Notes when production cases surface.

### Cross-project per-type policy

**H1. Uniform — all three opt OUT.**

> **Rejected.** `verifies` targets Requirements, not deliverables.

**H2. Uniform — all three opt IN.**

> **Rejected.** `tested_against` targets a local TestProcedure deliverable; cross-project opt-IN would violate target-Type-governs.

**H3. Per-type asymmetry: verifies opt IN (Requirement target, mirrors satisfies); tested_against opt OUT (TestProcedure target, target-Type-governs); cites opt IN (with explicit EvidenceArtifact-specific rationale per Decision §4).** *Chosen.*

## Decision

### 1. Scope: combined ADR landing three relationship types

This ADR lands three relationship types under one bundle bump:

- **`verifies`** — TestProcedure → Requirement (relationship type 9 in the catalogue)
- **`tested_against`** — Part | Assembly → TestProcedure (relationship type 10)
- **`cites`** — Requirement → EvidenceArtifact (relationship type 11)

After this ADR, the named relationship-type catalogue from [ADR/0009 §3](0009-relationship-type-satisfies.md) is operationally complete except `derived_geometry_from` (awaits FreeCAD Domain Adapter scope per [Manifesto P12](../Manifesto.md)).

All three inherit ADR/0009's thirteen base trace-relationship pattern fields verbatim; no new pattern fields at the base level. Criterion-level addressing per Decision §6 is the only new endpoint primitive in this bundle.

### 2. `verifies` (TestProcedure → Requirement)

**Source Type:** `TestProcedure`. Source-anchored on TestProcedure's `relationship:` namespace per [S3 commitment 3](../TruthModelSchema.md#3-relationships-are-source-anchored).

**Target Type:** `Requirement`. Single-endpoint `endpoints` array; target only (source implicit per ADR/0009 §1 pattern).

**Arity:** binary at the semantic layer; source-anchored asymmetric binary serialization (Pattern Catalogue row applies).

**Cycle policy:** `trace_graph`. Cycles structurally impossible today; declared for class consistency.

**Self policy:** `self_forbidden`. Cross-Type; declared for class consistency.

**Default binding:** `float` per [S3 commitment 12](../TruthModelSchema.md#12-float-vs-fixed-binding-mode-is-explicit-per-relationship). A TestProcedure verifying a Requirement tracks the Requirement's current state by default; `fixed` is available for "verifies a specific past Revision" semantics.

**Cross-project endpoint policy:** **opt IN** — direct external Requirement endpoints permitted, mirroring [ADR/0009 §3](0009-relationship-type-satisfies.md). Rationale: regulatory clauses published in catalog projects are natural targets ("TST-000041 verifies external FCC §15.247 emissions limit clause"). Float external semantics inherited from ADR/0009 §3 (resolves to external Requirement's current released Revision; staleness-intolerant release; `revision_content_hash` pinned at release).

**Criterion-level addressing on target endpoint:** optional per Decision §6. Whole-Requirement is the default; criterion-scoped `verifies` is opt-in via `endpoints[0].fact_ref: "acceptance_criterion:<id>"`.

**Verification-method coherence:** tooling-aided diagnostic per Decision §7; not schema-enforced.

**Per-record fields** (inherited from ADR/0009 §5):

| Field | Required | Notes |
|---|---|---|
| `id` | YES | Stable local id per [S0 commitment 7](../TruthModelSchema.md#7-list-addressability-rule). |
| `name` | OPTIONAL | Human-readable. |
| `type` | YES | Discriminator: `"verifies"`. |
| `binding` | OPTIONAL | Default `"float"`; explicit `"fixed"` pins target Revision. |
| `endpoints` | YES | Length-1 array; single target endpoint. |
| `endpoints[0].object_uuid` | YES | Target Requirement UUID. |
| `endpoints[0].revision_id` | Conditional | Required for Fixed; absent for Float. |
| `endpoints[0].project_scope` | OPTIONAL | Present for direct external Requirement endpoints per cross-project policy. |
| `endpoints[0].revision_content_hash` | Conditional | Required for Fixed cross-project endpoints; pinned at release for Float cross-project endpoints. |
| `endpoints[0].fact_ref` | OPTIONAL | Criterion-level addressing per Decision §6; form `"acceptance_criterion:<id>"`. |
| `fact_provenance` | INHERITED | S1 annotations. |
| `fact_uncertainty` | INHERITED | S1 annotations. |

### 3. `tested_against` (Part | Assembly → TestProcedure)

**Source Type union (seed):** `Part | Assembly`. Per Alternatives §B. Component / SoftwareModule deferred (B2, B3).

**Target Type:** `TestProcedure`. Single-endpoint; target only.

**Arity:** binary; source-anchored asymmetric binary serialization.

**Cycle policy:** `trace_graph`. Cross-Type; cycles structurally impossible today.

**Self policy:** `self_forbidden`. Cross-Type.

**Default binding:** `float`. A Part / Assembly tested-against a TestProcedure tracks the procedure's current released Revision by default; `fixed` pins a historical procedure Revision (useful for evidence-bearing audit trails — "tested under TST-000017 rev A; subsequent rev B procedural change does not invalidate this test record").

**Cross-project endpoint policy:** **opt OUT** — direct cross-project TestProcedure endpoints NOT permitted. Per [ADR/0013 target-Type-governs](0013-relationship-type-allocates-to.md) and [ADR/0020 §"Decision §5"](0020-object-type-test-procedure.md): TestProcedure is a deliverable Object; cross-project deliverable adoption routes through local Binding Objects (a consumer project adopting a regulatory test procedure authors a local TestProcedure that references the upstream via prose / `design_intent:` anchors / `attachment:` metadata, then `tested_against` targets the local TestProcedure).

**Criterion-level addressing:** N/A per Alternatives §F3.

**Per-record fields:** structurally identical to `verifies` except (a) `type: "tested_against"`, (b) no `fact_ref` (no criterion-level), (c) `endpoints[0].project_scope` schema-rejected (cross-project opt OUT).

### 4. `cites` (Requirement → EvidenceArtifact)

**Source Type:** `Requirement`. Per Alternatives §C1; TestProcedure-as-source deferred (C2). Lifts the deferral from [ADR/0019 §"Decision §5"](0019-object-type-evidence-artifact.md).

**Target Type:** `EvidenceArtifact`. Per Alternatives §D1; Requirement-as-target rejected (D2).

**Arity:** binary; source-anchored asymmetric binary serialization.

**Cycle policy:** `trace_graph`. Cross-Type; cycles structurally impossible today.

**Self policy:** `self_forbidden`.

**Default binding:** `float`. A Requirement citing an EvidenceArtifact tracks the evidence's current released Revision by default; `fixed` pins a historical evidence Revision.

**Cross-project endpoint policy: opt IN, with explicit EvidenceArtifact-specific rationale.**

Direct cross-project `cites` endpoints permitted on both source and target sides. The opt-in mirrors `satisfies`'s opt-in for external Requirements but requires its own rationale because EvidenceArtifact differs from Requirement on every dimension cross-project policy weighs:

- **Local approval semantics.** The consumer Requirement's authorial act of writing a `cites` record (and the Requirement's release transaction approving it) IS the local approval. The consumer is not adopting the external evidence as a local deliverable; the consumer is approving "this external evidence record, at this specific Revision, is engineering-truth I am willing to base my Requirement satisfaction claim on." That approval is local; the evidence lifecycle (release / retire / supersede) remains upstream.
- **No local Binding Object needed.** Component / SoftwareModule's local-Binding-Object pattern protects consumer control over (i) local lifecycle separate from upstream, (ii) local approval boundary for adopting the upstream as a local engineering element, (iii) local overrides / variants. None of those apply to citing external evidence: the consumer is not adopting evidence as a local design element; there's no consumer-side override of "the evidence said X"; lifecycle decoupling is via `binding: fixed` pinning a historical Revision, not via Binding Object indirection.
- **Integrity anchoring through Revision content hash.** Release materialization pins `endpoints[0].revision_id` + `endpoints[0].revision_content_hash` per [ADR/0008 §6](0008-cross-project-object-identity.md). The external EvidenceArtifact Revision is immutable per [S2 commitment 1](../TruthModelSchema.md#1-revisions-are-immutable-per-object); its attachment hash chain (per [ADR/0017 §2](0017-object-type-drawing.md) lineage + [ADR/0019 §3](0019-object-type-evidence-artifact.md) canonical-evidence-payload specialization) is *content* of that Revision, so pinning the Revision content hash implicitly pins the attachment-hash-chain integrity. Validators reading the resolved external Revision MUST verify the resolved bytes match `revision_content_hash`; the attachment chain inside that Revision is then trustable by transitive hash integrity. No additional pin-on-attachment-hash field is needed at the `cites` relationship level.
- **Float external acceptable; Fixed available.** Float external `cites` resolves to the external EvidenceArtifact's current released Revision per [ADR/0009 §3](0009-relationship-type-satisfies.md)'s template (mirrors `satisfies`-external-Requirement Float semantics). The "current best evidence" semantic is meaningful for citation: a consumer Requirement citing external regulatory-test evidence wants to track the upstream's current released evidence Revision by default; an upstream re-execution producing a new evidence Revision should propagate the citation. Fixed external `cites` is the historical-pinning case ("REQ-X is supported by EVD-Y rev A; the upstream's re-execution producing rev B is a separate citation if intended"). Release materialization is staleness-intolerant for both Float and Fixed external endpoints per [ADR/0009 §3](0009-relationship-type-satisfies.md) inheritance.

**Negative case (explicit):** The opt-in does NOT generalize. `tested_against` opts OUT (Decision §3); `verifies` opts IN with its own Requirement-target rationale (Decision §2); future V&V relationships make their own per-type case. The deliverable-vs-emergent governing principle from [ADR/0020 §"Decision §5"](0020-object-type-test-procedure.md) interacts with but does not directly determine cross-project posture — the per-type rationale dimensions are local-approval semantics, Binding-Object-applicability, integrity anchoring, and Float-vs-Fixed meaningfulness.

**Criterion-level addressing on source side:** optional per Decision §6. Source-side criterion-scoped `cites` is opt-in via `source_fact_ref: "acceptance_criterion:<id>"` on the relationship record (not inside `endpoints`, since source is implicit per ADR/0009 §1).

**Per-record fields:**

| Field | Required | Notes |
|---|---|---|
| `id` | YES | Stable local id. |
| `name` | OPTIONAL | Human-readable. |
| `type` | YES | Discriminator: `"cites"`. |
| `binding` | OPTIONAL | Default `"float"`. |
| `source_fact_ref` | OPTIONAL | Criterion-level addressing on source per Decision §6; form `"acceptance_criterion:<id>"` (resolves against the owning Requirement's `acceptance_criterion:` namespace). |
| `endpoints` | YES | Length-1 array; single target endpoint. |
| `endpoints[0].object_uuid` | YES | Target EvidenceArtifact UUID. |
| `endpoints[0].revision_id` | Conditional | Required for Fixed; absent for Float. |
| `endpoints[0].project_scope` | OPTIONAL | Present for direct external EvidenceArtifact endpoints. |
| `endpoints[0].revision_content_hash` | Conditional | Required for Fixed cross-project; pinned at release for Float cross-project. |
| `fact_provenance` | INHERITED | S1 annotations. |
| `fact_uncertainty` | INHERITED | S1 annotations. |

### 5. Wrong-verb guardrails carried forward + made explicit

- **`allocates_to` MUST NOT be used as a stand-in for Requirement → EvidenceArtifact citation** per [ADR/0019 §"Decision §5"](0019-object-type-evidence-artifact.md). The right verb is now `cites` per this ADR. ADR/0019's deferral is closed.
- **`allocates_to → TestProcedure` for product Requirements MUST NOT be authored** per [ADR/0020 §"Decision §5"](0020-object-type-test-procedure.md). The right verb for product-Requirement-to-procedure verification is now `verifies` (TestProcedure → Requirement direction) per this ADR. ADR/0020's wrong-verb guardrail carries forward unchanged; the resolution path now exists.
- **`cites` MUST NOT be used as a stand-in for `verifies` or `tested_against`.** Each of the three V&V types has a distinct semantic; the wrong-verb risk pattern applies symmetrically. Tooling MAY surface mis-direction (a Requirement citing a TestProcedure via `cites` would be schema-rejected — wrong target Type).

### 6. Criterion-level addressing on Requirement-side endpoints

**Reopens [ADR/0009 §"Alternatives §E"](0009-relationship-type-satisfies.md)'s deferral.** The condition ("when TestProcedure / EvidenceArtifact and the verification taxonomy harden") is now met; the V&V family is the load-bearing use case.

**Mechanism on target endpoint** (for `verifies`):

```yaml
endpoints:
  - object_uuid: "<requirement-uuid>"
    revision_id: "..."
    fact_ref: "acceptance_criterion:ac_temp_range_test"   # OPTIONAL
```

The `fact_ref` field is OPTIONAL. When absent: whole-Requirement claim (per ADR/0009 §2 normative semantics). When present: scoped to that specific criterion.

**Mechanism on source side** (for `cites` — source is implicit):

```yaml
relationship:
  - id: "rel_cite_001"
    type: "cites"
    source_fact_ref: "acceptance_criterion:ac_load_bearing"   # OPTIONAL
    endpoints:
      - object_uuid: "<evidence-uuid>"
        ...
```

The `source_fact_ref` field lives at the relationship record level (not inside `endpoints`) because source is implicit per ADR/0009 §1. Schema-validates that the referenced criterion exists in the source Requirement's current Revision.

**Per-relationship-schema opt-in (load-bearing).** Both primitives are defined at the trace-relationship base schema level (Decision §9), but each relationship-type schema explicitly opts in or rejects:

- `verifies`: opts in to `endpoints[].fact_ref` (target-side); does NOT opt in to `source_fact_ref` (source-side criterion-scoping not applicable — source is TestProcedure, not Requirement).
- `cites`: opts in to `source_fact_ref` (source-side); does NOT opt in to `endpoints[].fact_ref` (target-side criterion-scoping would require fact-level addressing within EvidenceArtifact, overkill for seed).
- `tested_against`: does NOT opt in to either (no Requirement endpoint).
- **`satisfies` does NOT opt in to either in this bundle.** [ADR/0009 §"Decision §2"](0009-relationship-type-satisfies.md) keeps whole-Requirement-only endpoint shape; the primitive being defined at the base level does NOT retrofit `satisfies`; a separate Schema Change Note can land `satisfies` retrofit if production case surfaces.

**Validation rules** (added in Decision §8):

- `endpoints[0].fact_ref` (target-side) — when present, must have form `"<namespace>:<id>"`. Currently only `"acceptance_criterion:<id>"` recognized; the referenced criterion must exist in the target Requirement's resolved Revision's `acceptance_criterion:` namespace. Schema-rejects dangling references.
- `source_fact_ref` (source-side, `cites` only) — when present, same form constraint. Referenced criterion must exist in the source Requirement's `acceptance_criterion:` namespace. Schema-rejects dangling references.
- **Whole-Requirement vs criterion-scoped claims are NOT equivalent.** A whole-Requirement and a per-criterion claim on the same Requirement-Pair can coexist; tooling MAY surface as redundant but neither is schema-rejected.
- **No retrofit to `satisfies`.** Separate Schema Change Note venue per the per-relationship-schema-opt-in rule above.

### 7. Verification-method consistency posture — tooling-aided diagnostic only

Per Alternatives §E2. Mismatch between `TestProcedure.verification_method` (per [ADR/0020 §2](0020-object-type-test-procedure.md)) and the verified Requirement's `default_verification_method` (or per-criterion `verification_method` override per [ADR/0006 §"Decision §6"](0006-object-type-requirement.md)) at a `verifies` link is a non-blocking diagnostic surfaced by tooling. Schema does not enforce equality at release.

Rationale:

- [ADR/0006](0006-object-type-requirement.md)'s field naming (`default_verification_method`) explicitly admits divergence.
- Project policy varies (strict-equality, stricter-method-OK, any-method-OK). Per [Manifesto P11](../Manifesto.md), AIADRA Core does not enumerate the policy.
- Tooling can warn at mismatch; project-policy validators can escalate to error.
- Schema Change Note can land a project-policy escalation mechanism if recurring need surfaces.

When criterion-level addressing is in play (Decision §6): the consistency check compares `TestProcedure.verification_method` against the *referenced criterion's* `verification_method` (if set) or the Requirement's `default_verification_method` (if not). Same tooling-aided posture.

### 8. Validation rules (Layer 2)

**`verifies`:**

- `type == "verifies"`.
- `endpoints` length exactly 1.
- `endpoints[0].object_uuid` resolves to `object.type == "Requirement"` (hard-fail otherwise).
- Cross-project endpoints validated per [ADR/0008 §6](0008-cross-project-object-identity.md): `revision_id` + `revision_content_hash` required for Fixed; Float resolves to external Requirement's current released Revision at release with staleness-intolerant materialization.
- `endpoints[0].fact_ref` (when present) form `"acceptance_criterion:<id>"`; the referenced criterion must exist in the target Requirement's resolved Revision; hard-fail on dangling reference.
- Verification-method consistency: tooling-aided diagnostic per Decision §7; schema does not enforce.

**`tested_against`:**

- `type == "tested_against"`.
- `endpoints` length exactly 1.
- `endpoints[0].object_uuid` resolves to `object.type == "TestProcedure"` (hard-fail otherwise).
- Source Object's `object.type` ∈ {`Part`, `Assembly`} (hard-fail otherwise).
- **No cross-project endpoints permitted** — `endpoints[0].project_scope` is schema-rejected per Decision §3 cross-project opt-OUT.
- No `fact_ref` or `source_fact_ref` permitted (schema-rejected — neither opt-in per Decision §6).

**`cites`:**

- `type == "cites"`.
- `endpoints` length exactly 1.
- `endpoints[0].object_uuid` resolves to `object.type == "EvidenceArtifact"` (hard-fail otherwise).
- Source Object's `object.type == "Requirement"` (hard-fail otherwise).
- Cross-project endpoints validated per [ADR/0008 §6](0008-cross-project-object-identity.md): `revision_id` + `revision_content_hash` required for Fixed; Float resolves to external EvidenceArtifact's current released Revision at release.
- **Cross-project Float `cites` endpoints** (external EvidenceArtifact, no `revision_id` in working state): at release, resolve to the external EvidenceArtifact's current released Revision; pin `revision_id` + `revision_content_hash`; verify retrieved Revision bytes hash to the pinned `revision_content_hash`. The Revision's internal attachment-hash-chain integrity is implicit via the Revision content hash per Decision §4 cross-project subsection.
- **Cross-project Fixed `cites` endpoints** carry `revision_id` + `revision_content_hash` per [ADR/0008 §6](0008-cross-project-object-identity.md); release-time hash mismatch is hard-fail. Same Revision-content-hash-implies-attachment-chain semantics as Float.
- `source_fact_ref` (when present) form `"acceptance_criterion:<id>"`; the referenced criterion must exist in the source Requirement's `acceptance_criterion:` namespace; hard-fail on dangling reference.
- No `endpoints[].fact_ref` permitted (schema-rejected — `cites` does NOT opt in to target-side criterion-level per Decision §6).

**Shared:**

- All three inherit ADR/0009's 13 base trace-relationship pattern field validations.
- All three inherit `binding` ∈ {`"float"`, `"fixed"`}, default `"float"`.
- All three are source-anchored: record lives in the source Object's `relationship:` namespace.
- All three are `trace_graph` cycle class; `self_forbidden` self policy.

### 9. Lifecycle, eventability, bundle bump

**Eventability** per [S3 commitment 5](../TruthModelSchema.md): relationships-as-records emit `relationship_created` / `relationship_changed` / `relationship_retired` events (per [ADR/0009 §"Eventability"](0009-relationship-type-satisfies.md) inheritance); the new types use the existing relationship event taxonomy without new event Type discriminators.

**Bundle bump:** **v0.17.0 → v0.18.0**, MINOR additive per [ADR/0003 §11](0003-schema-governance.md). Changes:

- NEW: `relationship/verifies.schema.json` — opts in to `endpoints[].fact_ref` per Decision §6 target-side mechanism.
- NEW: `relationship/tested_against.schema.json` — does NOT opt in to `fact_ref` or `source_fact_ref` (criterion-level addressing N/A per Alternatives §F3).
- NEW: `relationship/cites.schema.json` — opts in to `source_fact_ref` per Decision §6 source-side mechanism.
- ADDITIVE: `endpoints[].fact_ref` field primitive defined at the trace-relationship base schema level; **opt-in per relationship schema** (each relationship-type schema explicitly permits or rejects the field). Currently opted-in by `verifies`; reserved for future opt-ins via Schema Change Notes.
- ADDITIVE: `source_fact_ref` field primitive at the trace-relationship base schema level; **opt-in per relationship schema** (each relationship-type schema explicitly permits or rejects the field). Currently opted-in by `cites`; reserved for future opt-ins.
- **`satisfies` does NOT accept `endpoints[].fact_ref` or `source_fact_ref` in this bundle.** [ADR/0009 §"Decision §2"](0009-relationship-type-satisfies.md) keeps whole-Requirement-only endpoint shape; the primitive being defined at the base level does NOT retrofit `satisfies`; the `satisfies` schema explicitly does not enumerate either field. A separate Schema Change Note can land `satisfies` retrofit if production case surfaces.

No existing artifacts break. All MINOR additive.

**ADR ceremony** per the [amended Promotion Rule commitment 6](../TruthModelSchema.md): pattern-setting on multiple counts (three new relationship types; first criterion-level addressing landing; first source-side `fact_ref` primitive; verification-method consistency posture pinning).

## Worked sidecar examples

### Example 1 — `verifies` (TestProcedure side)

A TestProcedure verifying a Requirement at the criterion level.

```yaml
# Excerpt from TST-000017's relationship: namespace
relationship:
  - id: "rel_verifies_001"
    type: "verifies"
    binding: "float"
    endpoints:
      - object_uuid: "<req-000058-uuid>"
        fact_ref: "acceptance_criterion:ac_load_bearing_5400n"   # criterion-scoped
    fact_provenance: { category: "human_input" }
    fact_uncertainty: "verified"
  - id: "rel_verifies_002"
    type: "verifies"
    binding: "float"
    endpoints:
      - object_uuid: "<req-000058-uuid>"   # same Requirement
                                            # NO fact_ref → whole-Requirement claim
    fact_provenance: { category: "human_input" }
```

This TestProcedure makes two verifies-claims against the same Requirement: one criterion-scoped, one whole-Requirement. Both valid per Decision §6's "not equivalent; tooling may surface as redundant" rule.

### Example 2 — `tested_against` (Part side)

A Part claiming it was tested against a TestProcedure.

```yaml
# Excerpt from P-000058's relationship: namespace
relationship:
  - id: "rel_tested_001"
    type: "tested_against"
    binding: "fixed"
    endpoints:
      - object_uuid: "<tst-000017-uuid>"
        revision_id: "rev_b"
                                            # NO project_scope (cross-project opt-OUT per Decision §3)
                                            # NO fact_ref (N/A — no Requirement endpoint)
    fact_provenance: { category: "human_input" }
    fact_uncertainty: "verified"
```

Fixed binding pins TST-000017 rev B as the procedure version under which the test was performed; subsequent procedure-revision changes do not invalidate this trace.

### Example 3 — `cites` (Requirement side)

A Requirement citing an EvidenceArtifact at the criterion level.

```yaml
# Excerpt from REQ-000058's relationship: namespace
relationship:
  - id: "rel_cites_001"
    type: "cites"
    binding: "float"
    source_fact_ref: "acceptance_criterion:ac_load_bearing_5400n"   # source-side criterion
    endpoints:
      - object_uuid: "<evd-000043-uuid>"
    fact_provenance: { category: "human_input" }
    fact_uncertainty: "verified"
```

This Requirement's `ac_load_bearing_5400n` criterion is supported by EVD-000043 (the FEA simulation evidence record from ADR/0019's worked example).

**Combined V&V graph** (across the three examples):

- TST-000017 `verifies` REQ-000058 (criterion `ac_load_bearing_5400n`)
- P-000058 `tested_against` TST-000017 rev B
- REQ-000058 (criterion `ac_load_bearing_5400n`) `cites` EVD-000043

The full chain — *Part was tested under a procedure that verifies a criterion that is supported by evidence* — is now expressible end-to-end with the three new relationship types.

## Consequences

- **Three new relationship types land.** Named relationship-type catalogue at eleven (was eight): `satisfies`, `composed_of`, `mated_to`, `derived_from`, `refines`, `allocates_to`, `parameter_expression`, `depicts`, `verifies`, `tested_against`, `cites`. After this ADR the catalogue from [ADR/0009 §3](0009-relationship-type-satisfies.md) is operationally complete except `derived_geometry_from` (awaits FreeCAD Domain Adapter scope per [Manifesto P12](../Manifesto.md)).
- **V&V Object Type triad fully wired end-to-end.** TestProcedure + EvidenceArtifact + Part / Assembly + Requirement; all four are now interconnected via the V&V relationship family. The chain *Part `tested_against` TestProcedure `verifies` Requirement `cites` EvidenceArtifact* is expressible without wrong-verb workarounds.
- **First criterion-level addressing landing.** Reopens [ADR/0009 §"Alternatives §E"](0009-relationship-type-satisfies.md)'s deferral; the primitive (`endpoints[].fact_ref` / `source_fact_ref`) is reusable for future opt-ins. Per-relationship-schema opt-in discipline is the new pattern: each relationship type explicitly permits or rejects each primitive.
- **First source-side fact-ref primitive (`source_fact_ref`).** `cites` is the first relationship type to need source-side criterion addressing because its source (Requirement) is implicit per ADR/0009 §1. The primitive is reserved for future opt-ins; same opt-in discipline as `endpoints[].fact_ref`.
- **Verification-method consistency posture pinned.** Tooling-aided diagnostic; not schema-enforced. Project-policy strictness escalation deferred to Schema Change Note.
- **Partial supersession of [ADR/0005 §11 line 214](0005-object-type-part.md) and [ADR/0007 §11 line 245](0007-object-type-assembly.md) — EvidenceArtifact-target half of `tested_against`.** ADR/0005 and ADR/0007 forward-referenced `tested_against` with target Type union `TestProcedure | EvidenceArtifact`. ADR/0021 lands `tested_against` with target = `TestProcedure` only (Decision §3); the direct `Part / Assembly → EvidenceArtifact` edge is deferred to the future test execution model. Rationale: direct deliverable-to-evidence linkage requires atomic binding of procedure-revision + executed-run + produced-evidence + tested-Object, which is execution-record semantics. Overloading `tested_against` with execution semantics would conflate the procedure-relationship layer with the execution-instance layer. Until the test execution model lands, the deliverable-evidence chain expresses indirectly: `Part tested_against TestProcedure` + (future test execution record connecting procedure to evidence) + `Requirement cites EvidenceArtifact` per Decision §4.
- **Partial clarification of [ADR/0020 §"Decision §5" line 236](0020-object-type-test-procedure.md) — `cites` direction.** ADR/0020's forward reference ambiguously declared `cites` as both TestProcedure-as-source AND as lifting ADR/0019's Requirement-as-source deferral (different directions). ADR/0021 pins seed `cites` as `Requirement → EvidenceArtifact` per Decision §4, lifting ADR/0019's deferral exactly as worded there. TestProcedure-as-source for `cites` is deferred per Alternatives §C2 — procedure-cites-prerequisite-evidence conflates with the test execution model's procedure-produces-evidence linkage; a future Schema Change Note or the test execution model ADR is the right venue. Future readers: the ADR/0020 line 236 wording's TestProcedure-source half is non-normative; the seed `cites` is Requirement-source-only.
- **Cross-project per-type asymmetry operationally complete across the trace family.** `satisfies` opt IN, `derived_from` / `refines` opt IN, `allocates_to` opt OUT (first opt-out), `depicts` opt OUT, `verifies` opt IN, `tested_against` opt OUT, `cites` opt IN. The deliverable-vs-emergent governing principle from [ADR/0020 §"Decision §5"](0020-object-type-test-procedure.md) interacts with cross-project policy but does not directly determine it — per-type rationale dimensions are local-approval semantics, Binding-Object-applicability, integrity anchoring, and Float-vs-Fixed meaningfulness.
- **Schema bundle bump.** Active bundle moves v0.17.0 → v0.18.0.
- **Glossary additions.** [Glossary.md](../Glossary.md) v0.22: three new relationship-type entries (`verifies`, `tested_against`, `cites`); small update to `tested_against` framing in any prior reference; small update to `satisfies` entry noting criterion-level addressing remains deferred for `satisfies` specifically.
- **SystemState additions.** New Pattern Catalogue row for criterion-level Requirement addressing per [Codex1 N1](../Discussions/20260519/20260519-11/Codex1.md); Recent Pattern Changes entry; Current Front advance.
- **Test execution model is the natural near-term arc** — deferred per [ADR/0020 §"Consequences"](0020-object-type-test-procedure.md); lifts the Part/Assembly → EvidenceArtifact direct edge deferred per ADR/0021's Blocker 1 absorption; lifts the TestProcedure-as-source for `cites` deferred per Alternatives §C2; lifts the coverage / verification_state / evidence_ref properties deferred per Alternatives §G. Alternative: Wedge spike-implementation (basic Wedge loop + V&V instrumentation now schema-feasible end-to-end).
- **`satisfies` retrofit with criterion-level addressing remains deferred** to separate Schema Change Note. The `endpoints[].fact_ref` primitive exists at the base level but `satisfies` does NOT opt in.
- **`tested_against` source Type extensions (Component / SoftwareModule)** deferred to Schema Change Notes when concrete cases surface.
- **`verified_by` (Requirement / Part / Assembly → TestProcedure) inverse direction** — graph-derivable from `verifies` via the acceleration cache per [ADR/0001 §3](0001-storage-substrate.md); not authored as a separate relationship type. Same posture as `where-used` / `composes` inverses.
