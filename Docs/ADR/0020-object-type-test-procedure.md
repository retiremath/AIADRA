---
name: adr-0020-object-type-test-procedure
status: accepted
date: 2026-05-19
supersedes: 0006-object-type-requirement (partial — Consequences line 397 forward reference for "test procedure body" only; relocated to source_authoring attachment)
superseded_by: none
resolves: []
---

# ADR/0020 — Object Type: TestProcedure

## Status

**Accepted** — 2026-05-19. Eighth Object Type after Part / Requirement / Assembly / Component / SoftwareModule / Drawing / EvidenceArtifact. Third **Attachment-bearing Object** instance — second reuse of the [ADR/0017](0017-object-type-drawing.md) template after [ADR/0019](0019-object-type-evidence-artifact.md), validating the template a second time with a different per-Type `source_authoring` specialization. Inherits the `attachment:` namespace shape, structural D7-escape, algorithm-qualified hash discipline, and `derived_from_attachment_id` lineage rules verbatim, with **one TestProcedure-specific specialization**: `source_authoring` MUST be the canonical procedure document (signed test plan, SOP, test script, runbook, regulatory protocol), not a metadata-only stub. **`allocates_to` target Type union additively extended** to include TestProcedure, with an explicit **authoring guardrail** distinguishing procedure-deliverable Requirements (valid `allocates_to` source) from product Requirements awaiting `verifies` (invalid wrong-verb). Closes the V&V Object Type triad (TestProcedure + EvidenceArtifact + future `verifies` / `tested_against` / `cites`); unblocks the V&V relationship-type ADR which in turn lifts the Requirement-to-EvidenceArtifact citation deferral from [ADR/0019](0019-object-type-evidence-artifact.md).

Closes the TestProcedure deferral from [Glossary "Object (Managed Object)" candidate pool](../Glossary.md) Tier-2 Types and from [TruthModelSchema line 927](../TruthModelSchema.md). After ADR/0020, all three Tier-2 Object Types from the Glossary candidate pool (Drawing, TestProcedure, EvidenceArtifact) are promoted; the V&V Object Type triad is complete pending only the V&V relationship-type ADR.

## Context

Discussion trail in [`Docs/Discussions/20260519/20260519-10/`](../Discussions/20260519/20260519-10/). [Codex1](../Discussions/20260519/20260519-10/Codex1.md) produced two blockers and two non-blockers; both blockers tightly scoped and structurally addressed in [Claude2](../Discussions/20260519/20260519-10/Claude2.md); [Codex2](../Discussions/20260519/20260519-10/Codex2.md) signed off. Both close conditions met:

1. `allocates_to` wrong-verb guardrail for TestProcedure targets — encoded in Decision §5 (valid/invalid examples + tooling diagnostic) and Decision §8 (validation rule).
2. Explicit clarification / partial supersession of [ADR/0006 §"Consequences" line 397](0006-object-type-requirement.md) forward reference for "test procedure body" — encoded in status-block frontmatter (`supersedes:` entry), Pre-declared-constraints table, and the new Consequences entry.

Three pressures converge:

1. **Second reuse of [ADR/0017](0017-object-type-drawing.md)'s Attachment-bearing template.** ADR/0019 was the first reuse; ADR/0020 is the second. Structural mechanics (`attachment:` namespace; required `source_authoring`; lineage chain; hash-as-authority) inherit verbatim. The specialization is *semantic*: TestProcedure's `source_authoring` must be the canonical procedure document (the actual method spec), not a metadata-only stub. ADR/0019's `source_authoring` specialization was "canonical evidence payload, not setup-only"; ADR/0020's is "canonical procedure document, not metadata-only stub." Same template-pattern; different per-Type semantic specialization. Validates the template's reusability with substantive divergence.
2. **TestProcedure as committed deliverable, not emergent record.** [ADR/0019 §"Alternatives §C"](0019-object-type-evidence-artifact.md) rejected `allocates_to` target extension for EvidenceArtifact because evidence is *emergent from execution* (you can't pre-commit to which specific evidence record will exist). TestProcedure differs: it IS a committed deliverable (the team commits to producing the method spec). This argues for ADDING TestProcedure to the `allocates_to` target Type union — same posture as Drawing ([ADR/0017](0017-object-type-drawing.md)). The **deliverable-vs-emergent distinction** is necessary but not sufficient — Codex1 Blocker 1 caught that it needs an additional **wrong-verb guardrail**: not every Requirement can be allocated to a given TestProcedure (only procedure-deliverable Requirements; product Requirements await `verifies`). Both cuts are operationalized in Decision §5.
3. **Snake_case block-name vs ADR/0006 pre-declaration text.** [ADR/0006 §"Consequences" line 396](0006-object-type-requirement.md) forward-referenced TestProcedure as having a `testprocedure:` block (no underscore); that pre-declaration predated the snake_case convention established by [ADR/0016](0016-object-type-software-module.md)'s `software_module:`. ADR/0020 pins the block name as `test_procedure:` (snake_case) for consistency.

## Promotion Rule walk — via Attachment-bearing Object pattern

Inherits from [ADR/0017 §"Promotion Rule walk"](0017-object-type-drawing.md). TestProcedure passes the [Promotion Rule capability test](../TruthModelSchema.md) via the same **Attachment-bearing Object** named non-disqualifier pattern from [commitment 5](../TruthModelSchema.md):

- **C1 — Independent identity.** TestProcedure `TST-000017` has stable local UUID + Number identifying *the engineering method specification* — independent of any specific test execution, of any specific Requirement it verifies, of the instrument / fixture / setup used. The same procedure is run many times (regression, recertification); the procedure identity persists.
- **C2 — Independent lifecycle.** TestProcedure has its own release cadence — `in_work` while authoring; `under_review` (per [Glossary "Lifecycle State"](../Glossary.md); common for regulated procedures); `released` when sealed as an approved procedure; `retired` if superseded. Procedure-rev-A may verify Requirement-rev-3 *or* Requirement-rev-4 depending on which Requirement Revision the procedure was authored against.
- **C3 — Independent referenceability.** Per [TruthModelSchema line 927](../TruthModelSchema.md): *"reusable across Objects, independently approved, traceable to Requirements."* Cited by multiple Requirements (future `verifies` direction), multiple Part / Assembly endpoints (future `tested_against`), multiple EvidenceArtifact records (future `cites`). The reusability across multiple verification targets is the load-bearing argument for first-class identity.
- **C4 — Independent provenance / approval.** Procedure approval is its own engineering decision — typically test engineer + methodology reviewer + (for regulated domains) certification authority sign-off, distinct from Part / Requirement / Evidence approval.

**D1–D7 disqualifier walk:**

- **D7 (Derived view)** — N/A *because* the schema requires `source_authoring` attachment at release per inherited [ADR/0017 §2](0017-object-type-drawing.md), specialized per Decision §3 to be the canonical procedure document (not a metadata-only stub). The authored canonical layer is structural; D7 is excluded. (Third operationalization of this argument; same mechanism as Drawing / EvidenceArtifact.)
- **D1–D6** — N/A or trivially pass.

Conclusion: **TestProcedure is a first-class Object Type via the Attachment-bearing Object pattern.** Eighth Object Type; third Attachment-bearing instance.

## Pre-declared constraints honored

| Constraint | Source | Disposition |
|---|---|---|
| Attachment-bearing Object pattern (TestProcedure named in Promotion Rule commitment-5 example list as "DV Procedure" parallel; reusable across Objects, independently approved, traceable to Requirements) | [TruthModelSchema line 852 + line 927](../TruthModelSchema.md) | Inherited from ADR/0017; Promotion path identical. |
| `attachment:` namespace (Vault-attached canonical bytes; `source_authoring` required at release; `derived_from_attachment_id` lineage; algorithm-qualified `content_hash` as authority) | [ADR/0017 §2](0017-object-type-drawing.md) | Inherited verbatim; specialization of `source_authoring` semantic per Decision §3 (different specialization from ADR/0019). |
| TypeSpecific singleton wrapper pattern (`testprocedure:` analogous to `requirement:` / `evidence:`) | [ADR/0006 §"Consequences" line 396](0006-object-type-requirement.md) | Inherited as pattern; block name pinned as `test_procedure:` (snake_case) per [ADR/0016](0016-object-type-software-module.md) `software_module:` precedent — see Alternatives §F. ADR/0006 line 396's run-together form predates the snake_case convention. |
| Structured-text content pattern for "test procedure body" | [ADR/0006 §"Consequences" line 397](0006-object-type-requirement.md) | **Partially superseded by ADR/0020.** Canonical procedure body lives in the `source_authoring` attachment (per Decision §3), not as sidecar structured text. `test_procedure:` carries only `title` + `verification_method` + optional prose summaries (Decision §2); structured per-step records deferred to Schema Change Note per Alternatives §H. ADR/0006 line 397's reference to "evidence summary" for EvidenceArtifact remains in force (handled by [ADR/0019](0019-object-type-evidence-artifact.md)'s `evidence.summary` field). |
| `verifies` (TestProcedure → Requirement) pre-declared | [ADR/0006 §"Decision 12" + §C3 line 109 + line 300](0006-object-type-requirement.md) | Deferred to V&V relationship-type ADR. NOT in this bundle. |
| `verification_method` enum alignment with Requirement's `default_verification_method` | [ADR/0006 §"Decision 7"](0006-object-type-requirement.md) | Honored — `test_procedure.verification_method` uses identical enum (`test \| analysis \| inspection \| demonstration`); cross-check at V&V relationship time. |
| `verified_by` / `tested_against` (Part / Assembly → TestProcedure / EvidenceArtifact) pre-declared | [ADR/0005 §11 line 214](0005-object-type-part.md), [ADR/0007 §11 line 245](0007-object-type-assembly.md) | Deferred to V&V relationship-type ADR. NOT in this bundle. |
| Target-Type-governs-cross-project-policy (engineering deliverables opt OUT of direct cross-project endpoints) | [ADR/0013 §"Cross-project"](0013-relationship-type-allocates-to.md) | Honored — TestProcedure as `allocates_to` target opts OUT of direct cross-project endpoints (same posture as Drawing / Component / SoftwareModule). |

## Alternatives Considered

### Pattern choice

**A1. Pure-sidecar — no `attachment:` namespace.** Test procedures entirely sidecar-encoded as structured `step:` records: each step with inputs, expected outputs, pass/fail criteria, references to instrumentation.

> **Rejected.** Real-world procedures span the range from short scripts to multi-hundred-page certification protocols, regulatory SOPs, and signed test plans. Forcing all into structured sidecar YAML is impractical for the heavy end; allowing both structured `step:` AND an external document invites drift. Pattern-following on Drawing / EvidenceArtifact is the established discipline: canonical method document lives as a `source_authoring` attachment; structured *nominal procedure parameters* live in `parameter:`; structured `step:` records deferred to future Schema Change Note when production case surfaces.

**A2. Attachment-bearing — inherits ADR/0017 template; canonical procedure document as `source_authoring`; `parameter:` for nominal inputs.** *Chosen — see Decision §3.*

**A3. Hybrid — Attachment-bearing AND structured `step:` namespace as first-class.**

> **Rejected (for seed).** Dual representation invites drift between the document and the structured steps; tooling has to enforce non-contradiction. Conservative seed: document is canonical, `parameter:` for queryable nominal inputs. Structured `step:` namespace can be added later as a Schema Change Note. Same posture as Drawing's deferral of structured dimensions / callouts.

### `source_authoring` semantic specialization for TestProcedure

**B1. Inherit ADR/0017's generic `source_authoring` (any authored canonical payload).**

> **Rejected (preemptively).** ADR/0019 established the per-Type specialization precedent. Generic inheritance permits a degenerate case: a TestProcedure whose `source_authoring` is a one-line metadata stub does not satisfy the "canonical procedure document" requirement that lifts TestProcedure out of D7.

**B2. TestProcedure-specific specialization: `source_authoring` must be the canonical procedure document (the actual method specification — signed test plan, SOP, test script, runbook, regulatory protocol document, or equivalent canonical record of the method to be executed), not a metadata-only stub or summary.** *Chosen — see Decision §3.*

### `allocates_to` target extension

**C1. NO extension — defer Requirement-to-TestProcedure trace to V&V relationship-type ADR (parity with ADR/0019's EvidenceArtifact decision).**

> **Rejected.** EvidenceArtifact's rejection rationale was: "EvidenceArtifact is not responsible for fulfilling a product Requirement; it records what was observed." That rationale **does not transfer** to TestProcedure because TestProcedure is a *committed deliverable* — the project team commits to producing the procedure spec. Same engineering pattern that justified Drawing's `allocates_to` target inclusion in ADR/0017.
>
> The distinction is **deliverable-vs-emergent**: TestProcedure / Drawing / Part / Assembly / Component / SoftwareModule are committed-to-produce deliverables; projects allocate ownership of them. EvidenceArtifact is emergent from execution — you can't pre-commit to which specific evidence record will exist. `allocates_to` works for the former; the V&V relationship family is the right verb for the latter.

**C2. YES extension, with explicit wrong-verb authoring guardrail.** *Chosen — see Decision §5.* Per [Codex1 Blocker 1](../Discussions/20260519/20260519-10/Codex1.md): the deliverable-vs-emergent cut is necessary but not sufficient. Even with TestProcedure as a valid target shape, only *procedure-deliverable* Requirements may be allocated to it; product Requirements awaiting verification target the future `verifies` edge instead. Encoded in Decision §5 with valid/invalid examples and authoring-guardrail validation rule (Decision §8).

### Number prefix

**D1. `T-NNNNNN`.**

> **Rejected.** "T-" alone is too ambiguous.

**D2. `TP-NNNNNN`.**

> **Rejected (slight).** "TP" reads as test-procedure but is also "test plan" / "technical paper" / "throughput" in different industries.

**D3. `TST-NNNNNN`.** *Chosen — see Decision §1.* Established engineering convention for "test"; 3-char width matches `REQ-` / `ASM-` / `EVD-` / `DWG-`.

**D4. `TEST-NNNNNN`.**

> **Rejected.** Unnecessarily long; "TST" carries the same meaning at 3 chars.

### `verification_method` REQUIRED-vs-OPTIONAL

**E1. OPTIONAL — projects may omit if context is clear.**

> **Rejected.** The whole point of TestProcedure carrying `verification_method` is to provide a sidecar-level anchor that the future V&V `verifies` ADR cross-checks against the verified Requirement's `default_verification_method`. Optionality undermines the cross-check.

**E2. REQUIRED — every TestProcedure declares its verification method (enum aligned with Requirement's `default_verification_method`).** *Chosen — see Decision §2.* The four-value enum (`test | analysis | inspection | demonstration`) from [ADR/0006 §7](0006-object-type-requirement.md) is reused verbatim.

### Block-name snake_case divergence from ADR/0006 pre-declaration

**F1. Keep ADR/0006's pre-declaration text verbatim: `testprocedure:` (no underscore).**

> **Rejected.** ADR/0006's pre-declaration predated `software_module:` ([ADR/0016](0016-object-type-software-module.md)), which established snake_case as the convention for multi-word block names. Adopting `testprocedure:` now would lock in a one-off inconsistency. The pre-declaration was a forward-reference, not a normative pin.

**F2. `test_procedure:` (snake_case, consistent with `software_module:`).** *Chosen — see Decision §1.* Flagged in Pre-declared-constraints table; departure is visible.

### Combined TestProcedure + V&V relationship-type ADR

**G1. Land both in one ADR.**

> **Rejected.** V&V relationship taxonomy (`verifies` / `tested_against` / `cites`) has its own substantial decision surface (target Type unions; binding defaults; cycle classes; criterion-level addressing reopens [ADR/0009](0009-relationship-type-satisfies.md)'s `acceptance_criterion:` `fact_ref` deferral; coverage / verification_state semantics from ADR/0009 §"Alternatives §E"). Combining would over-pack the arc. Same separation discipline as Drawing + `depicts`.

**G2. Sequence: TestProcedure first, V&V relationship-type ADR second.** *Chosen.*

### Structured `step:` namespace inclusion

**H1. INCLUDE structured `step:` in seed (each step with `id`, `description`, `expected_outcome`, `references`).**

> **Rejected (for seed).** Risk of becoming a junk-drawer namespace duplicating attachment content. Defer until production case surfaces that requires queryable per-step structure.

**H2. EXCLUDE from seed; defer to Schema Change Note.** *Chosen.* Conservative; can extend additively later.

## Decision

### 1. Number prefix + Type name

**Type name:** `TestProcedure` (PascalCase).
**TypeSpecific block:** `test_procedure:` (snake_case singleton; matches `software_module:`). **Divergence from [ADR/0006 §"Consequences" line 396](0006-object-type-requirement.md) pre-declaration text** (`testprocedure:` without underscore) — see Alternatives §F. Glossary v0.21 reflects `test_procedure:` as the pinned form.
**Number prefix:** `TST-NNNNNN`. Six-digit zero-padded sequential allocation from the Reservation file per [ADR/0004](0004-number-allocation.md).

### 2. TypeSpecific `test_procedure:` block

Singleton TypeSpecific block. Conservative seed; `title` and `verification_method` REQUIRED.

```yaml
test_procedure:
  title: "string"                    # REQUIRED — short human-readable title
  verification_method: "string"      # REQUIRED — enum: test | analysis | inspection | demonstration
                                     #            (matches Requirement.default_verification_method per ADR/0006 §7)
  applicability_summary: "string"    # OPTIONAL — prose, when this procedure applies (which Object classes,
                                     #            which Requirement categories, environmental conditions)
  expected_outputs_summary: "string" # OPTIONAL — prose, what evidence this procedure is expected to produce
                                     #            (anchors the future cites relationship; not a structured reference)
```

**`verification_method` enum:** `test | analysis | inspection | demonstration` — verbatim from [ADR/0006 §7](0006-object-type-requirement.md). The cross-check anchor: the future `verifies` (TestProcedure → Requirement) relationship ADR will validate that `TestProcedure.verification_method` is consistent with the verified Requirement's `default_verification_method` (typically equal; project policy may allow stricter-method procedure to verify weaker-method Requirement — out of scope for ADR/0020).

**`applicability_summary` guardrail:** prose-only human-readable text. NOT a structured query expression; NOT a list of pinned Object UUIDs. Structured applicability — e.g., "this procedure applies to all Parts with parameter `mass_kg > 5.0`" — would be a query language Core does not enumerate per [Manifesto P11](../Manifesto.md). Seed treats `applicability_summary` as free-form text.

**`expected_outputs_summary` guardrail:** prose-only. NOT a structured EvidenceArtifact UUID reference (those land via the future `cites` relationship). Authoring scaffolding only.

**No `test_kind` enum in seed.** Considered (parallel to `evidence_kind` in EvidenceArtifact); rejected — `evidence_kind` classifies the *output*; classifying the method is more taxonomically ambiguous. Wait for production patterns; add via Schema Change Note if recurring need surfaces.

### 3. `attachment:` namespace — inherited from ADR/0017 with TestProcedure-specific `source_authoring` semantic

Structural shape, role enum (`source_authoring` / `rendered_primary` / `derived_secondary`), required fields, `derived_from_attachment_id` lineage discipline, algorithm-qualified `content_hash`, `vault_path` non-authoritative, pre-commit resolution, release invariants — **all inherited verbatim** from [ADR/0017 §2](0017-object-type-drawing.md).

**TestProcedure-specific specialization of `source_authoring` semantic:**

> For TestProcedure, at least one released `source_authoring` attachment MUST be the **canonical procedure document** — the actual method specification: signed test plan, standard operating procedure (SOP), test script, runbook, regulatory protocol document, or equivalent canonical record of the method to be executed. Metadata-only stubs (a one-page summary of "what we plan to test, more or less") MUST NOT be the *only* `source_authoring` attachment. A released TestProcedure must not be reconstructable as "a title + a few notes" without a canonical method specification attached and named.

Parallel to [ADR/0019 §3](0019-object-type-evidence-artifact.md)'s EvidenceArtifact-specific specialization. Template pattern: **every Attachment-bearing Object Type specializes `source_authoring` semantically when its arc lands**; the structural shape stays uniform.

**Validation guidance** (semantic check; tooling-aided where parser available):

> When a parser exists for a given procedure format (e.g., a structured test-script DSL), tooling may inspect the attachment payload to confirm it is a method specification, not a metadata stub. Where no parser exists, the schema cannot enforce semantic-document-shape; the rule is normative on the author. Same posture as ADR/0019 validation guidance.

**Common shapes for TestProcedure attachment sets:**

- Regulatory: `source_authoring` = signed regulatory protocol document (often PDF). `rendered_primary` = signed-and-sealed distribution PDF. `derived_secondary` = checklists / abbreviated runsheets.
- Internal SOP: `source_authoring` = Markdown / DOCX / structured-text source. `rendered_primary` = release-facing PDF. Optional `derived_secondary` = quick-reference cards.
- Test script (programmatic): `source_authoring` = the executable test script (Python, MATLAB, structured DSL). `rendered_primary` = formatted PDF with embedded comments. Optional `derived_secondary` = generated dependency manifests, instrument-config exports.

### 4. Namespace set

Three of Part's seven plus the inherited `attachment:` plus singleton `test_procedure:`.

| Namespace | In TestProcedure seed? | Notes |
|---|---|---|
| `parameter:` | YES | Nominal procedure inputs: applied load, duration, environmental conditions, instrument settings. Field-name-encoded units (`applied_load_n`, `duration_h`, `ambient_temperature_c`, `voltage_v`). **NO `fact_provenance.derived_from` lineage discipline** — these are design parameters of the method, not derived measurements (the latter live on EvidenceArtifact). `fact_provenance.category: "human_input"` is the typical category. |
| `design_intent:` | YES | Rationale for procedure choices (why this load case, why this duration, why this instrument); anchors by id to attachment records, parameters, or future `verifies` relationships. |
| `feature:` | NO | Not internally designed (no CAD construction history). |
| `relationship:` | YES | Future `verifies` (TestProcedure → Requirement) source endpoint; future `tested_against` participation. **No TestProcedure-authored relationship records in this namespace at seed.** The additive `allocates_to` target extension (Decision §5) is authored on the Requirement side; TestProcedure is the target, not the source. |
| `published_ref:` | NO | No geometric reference points. |
| `geometry_ref:` | NO | No kernel geometry. |
| `material:` | NO | N/A. |
| `source:` | NO in seed. | Procedure origin / upstream standard / customer-test-plan provenance can be captured in `attachment:` metadata (the upstream document as `source_authoring` or `derived_secondary`), in `design_intent:` prose, or via a future `source:` namespace extension or relationship-type if a recurring production case appears. |
| **`attachment:`** (inherited from ADR/0017) | YES | Vault-attached canonical procedure document per Decision §3 with TestProcedure-specific `source_authoring` specialization. |

**Three of Part's seven** (`parameter:`, `design_intent:`, `relationship:`) **plus inherited `attachment:` plus singleton `test_procedure:`**. Same namespace count as EvidenceArtifact (3 of Part's 7 + attachment + singleton) but **no parameter lineage discipline** — TestProcedure parameters are nominal design facts, not derived from attachment bytes.

### 5. Relationship participation + endpoint-schema extension

**In seed (this bundle):**

- **`allocates_to` target — YES, with explicit wrong-verb authoring guardrail.** TestProcedure joins the `allocates_to` target Type union additively, producing the final union:

  `Part | Assembly | Component | SoftwareModule | Drawing | TestProcedure`

  (EvidenceArtifact remains excluded per [ADR/0019 §"Alternatives §C"](0019-object-type-evidence-artifact.md) — emergent from execution, wrong verb.)

  **Authoring guardrail (load-bearing, not optional):**

  `allocates_to → TestProcedure` MUST mean the Requirement's fulfillment IS the procedure-spec deliverable itself — a Requirement asking that *a documented procedure exist* (regulatory mandate, internal test-plan policy, certification-package contract). Concretely:

  - **Valid:** *"The certification package shall include a documented static-load test procedure for the drive-bracket family."* allocated to TST-000017.
  - **Valid:** *"The project shall maintain a documented inspection method for class-A safety fasteners."* allocated to TST-000041.

  `allocates_to → TestProcedure` MUST NOT be used to record that the procedure verifies a product Requirement. Concretely:

  - **Invalid (wrong verb — disguised `verifies`):** *"The drive bracket shall withstand 5400 N static load without yielding."* allocated to TST-000017. The procedure *tests* this Requirement; it does not *fulfill* it. The "TST-000017 verifies REQ-000058" edge waits for the future `verifies` (TestProcedure → Requirement) relationship-type ADR. Authoring `allocates_to` here would canonicalize a wrong-verb trace and re-introduce the same pathology [ADR/0019 §"Alternatives §C"](0019-object-type-evidence-artifact.md) blocked for EvidenceArtifact, surfacing one hop earlier in the V&V chain.

  The schema cannot semantically distinguish these cases (both are structurally valid `allocates_to` shapes). This guardrail is normative on authoring; tooling reviewing a procedure-target `allocates_to` record MAY surface the question "is this a procedure-deliverable Requirement, or a product Requirement waiting for `verifies`?" as a non-blocking diagnostic.

**Deferred (out of seed):**

- **`verifies` (TestProcedure → Requirement)** — pre-declared in [ADR/0006 §"Decision 12" + §C3 + line 300](0006-object-type-requirement.md). Future V&V relationship-type ADR. NOT in this bundle.
- **`tested_against` (Part / Assembly → TestProcedure)** — pre-declared in [ADR/0005 §11 line 214](0005-object-type-part.md) and [ADR/0007 §11 line 245](0007-object-type-assembly.md). Future V&V relationship-type ADR. NOT in this bundle.
- **`cites` (TestProcedure → EvidenceArtifact)** — citation relationship; lifts the Requirement-to-EvidenceArtifact deferral from [ADR/0019](0019-object-type-evidence-artifact.md). Future V&V relationship-type ADR. NOT in this bundle.
- **`composed_of` / `mated_to` / `parameter_expression` / `depicts`** — semantic non-fit.
- **`satisfies` source** — plausible (a TestProcedure claiming it satisfies a "must have a documented test for X" Requirement) but redundant with `allocates_to` target arrow and future `verifies` source arrow. Defer; same posture as Component / SoftwareModule / Drawing / EvidenceArtifact.

### 6. AIADRA Core hosts nothing — explicit walk

[Manifesto P11](../Manifesto.md). Inherited from ADR/0017 / ADR/0019:

- **No Core-hosted TestProcedure registry.** Per-project procedures live in the project's own Git / Commonspace.
- **No Core-hosted test runner / instrument coordinator.** Test execution, instrument communication, environmental-chamber control, signal conditioning — all Domain Adapter / Domain Engine concerns.
- **No Core-hosted Vault.** Procedure documents live in the Vault per the Vault Adapter pattern; `vault_path` is locator-hint only; `content_hash` is authority.
- **No Core-hosted certification authority bridge.** Regulatory-domain procedure approval workflows (FAA / FDA / TÜV / etc.) are project / adapter concerns; Core does nothing.
- **No registry-shaped fields in the schema.** `vault_path` non-authoritative; `content_hash` authoritative.

### 7. Lifecycle, eventability, Revisions, bundle bump

**Lifecycle** independent per Promotion C2. States: `in_work` → `released` → `retired`. Optional `under_review` per [Glossary "Lifecycle State"](../Glossary.md) (common for regulated procedures); consumer-project policy whether to use it.

**Eventability** per [S3 commitment 5](../TruthModelSchema.md): `test_procedure_created`, `test_procedure_changed`, `test_procedure_released`, `test_procedure_retired` (snake-cased per the convention used for `software_module_*` events in [ADR/0016 §8](0016-object-type-software-module.md) and `evidence_artifact_*` events in [ADR/0019 §7](0019-object-type-evidence-artifact.md)). `_changed` fires on `test_procedure:` block edit, attachment add/remove, parameter edit, design-intent edit, relationship-namespace edit.

**Revision schema** per [S2 commitment 1](../TruthModelSchema.md). Each TestProcedure Revision is a separate immutable artifact at canonical path `revisions/<object-uuid>/<revision-id>.yaml`. Released TestProcedure Revision MUST carry at least one `attachment:` record with `role: source_authoring` AND `content_hash` resolved — and per Decision §3 specialization, that `source_authoring` attachment MUST be the canonical procedure document (semantic check).

**Bundle bump:** **v0.16.0 → v0.17.0**, MINOR additive per [ADR/0003 §11](0003-schema-governance.md). Changes:

- NEW: `sidecar/TestProcedure.schema.json`.
- NEW: `object.type = "TestProcedure"` discriminator value.
- NEW: `TST-NNNNNN` Number prefix mapping at the bundle level.
- ADDITIVE: `relationship/allocates_to.schema.json` target Type union extended (TestProcedure added).

No existing artifacts break. All MINOR additive.

### 8. Validation rules (Layer 2)

- `object.type == "TestProcedure"`.
- `test_procedure:` singleton block present with `title` (non-empty string) AND `verification_method`.
- `test_procedure.verification_method` ∈ {`test`, `analysis`, `inspection`, `demonstration`}.
- `test_procedure.applicability_summary`, `test_procedure.expected_outputs_summary` if present are non-empty strings (prose-only guardrails per Decision §2).
- `attachment:` namespace rules inherited from [ADR/0017 §"Decision §8"](0017-object-type-drawing.md): record shape; `derived_from_attachment_id` coupling; lineage chain discipline; `content_hash` unconditionally required on committed records; `vault_path` non-authoritative; **release-state invariant: at least one `source_authoring` record with resolved `content_hash`, which (per Decision §3) MUST be the canonical procedure document** (semantic check; tooling-aided where a parser exists for the procedure format).
- `parameter:` namespace canonical-unit-at-field-name discipline inherited from Part (`_n`, `_h`, `_c`, `_v`, etc. carry units in field name; no unqualified numeric facts). **No `fact_provenance.derived_from` lineage requirement** (TestProcedure parameters are design facts, not derived measurements).
- `relationship:` namespace exists; **no relationship-type-specific schema constraints in this bundle** beyond the additive `allocates_to` target extension applied at the relationship-schema level (not the TestProcedure sidecar level).
- For released `allocates_to` records targeting this TestProcedure: per [ADR/0013](0013-relationship-type-allocates-to.md) validation; direct cross-project endpoints rejected (target-Type-governs); **authoring guardrail per Decision §5 — source Requirement must be a procedure-deliverable Requirement, not a product Requirement awaiting `verifies`**. Schema cannot enforce; tooling MAY surface as a non-blocking diagnostic on `allocates_to`-target-TestProcedure records.

## Worked sidecar example

A load-test procedure for a drive bracket peak-stress verification. The canonical method document is a signed PDF SOP; nominal procedure inputs (applied load, duration, sample size) live in `parameter:` as design facts.

```yaml
object:
  uuid: "0193abcd-eeee-7b00-9ddd-555555555555"
  type: "TestProcedure"
  number: "TST-000017"
  lifecycle: "released"
  schema_version: "0.17.0"

test_procedure:
  title: "Drive bracket — static load test procedure (REV B)"
  verification_method: "test"
  applicability_summary: "Applies to all drive bracket Parts (P-000058 family) in their assembly context. Procedure assumes ambient-temperature lab conditions and Instron 5944 load frame; alternative load frames require an addendum."
  expected_outputs_summary: "Produces one EvidenceArtifact per executed run capturing peak von Mises stress, peak displacement, residual deflection after unload, and a photographic record of the post-test bracket condition."

parameter:
  - id: "param_applied_load_n"
    name: "Applied static load"
    value_n: 5400
    fact_provenance: { category: "human_input" }
    fact_uncertainty: "verified"
  - id: "param_load_duration_s"
    name: "Load hold duration"
    value_s: 600
    fact_provenance: { category: "human_input" }
    fact_uncertainty: "verified"
  - id: "param_sample_size"
    name: "Required number of test specimens"
    value_count: 3
    fact_provenance: { category: "human_input" }
    fact_uncertainty: "verified"
  - id: "param_ambient_temperature_c"
    name: "Nominal ambient temperature"
    value_c: 23
    fact_provenance: { category: "human_input" }
    fact_uncertainty: "estimate"

attachment:
  # Canonical procedure document — the signed SOP. THIS is what makes the TestProcedure reconstructable as a method.
  - id: "att_source_sop"
    role: "source_authoring"
    media_type: "application/pdf"
    vault_path: "vault:procedures/TST-000017/sop_rev_b_signed.pdf"
    content_hash: "sha256:f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2"
    page_count: 14
    fact_provenance: { category: "human_input" }
    fact_uncertainty: "verified"

  # Distribution-facing release PDF (annotated for field use).
  - id: "att_release_pdf"
    role: "rendered_primary"
    media_type: "application/pdf"
    vault_path: "vault:procedures/TST-000017/release_annotated.pdf"
    content_hash: "sha256:a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3"
    derived_from_attachment_id: "att_source_sop"
    page_count: 18
    fact_provenance: { category: "derived_for_release" }
    fact_uncertainty: "computed"

  # Abbreviated test-stand runsheet for the lab operator.
  - id: "att_lab_runsheet"
    role: "derived_secondary"
    media_type: "application/pdf"
    vault_path: "vault:procedures/TST-000017/runsheet.pdf"
    content_hash: "sha256:b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4"
    derived_from_attachment_id: "att_source_sop"
    page_count: 2
    fact_provenance: { category: "derived_for_release" }

design_intent:
  - id: "di_load_factor_basis"
    statement: "Applied load (5400 N) is the operating-load envelope derived from REQ-000058 multiplied by a 1.5x safety factor per project policy. Hold duration (600 s) gives stress relaxation time to detect any creep-mode failure before unloading."
    anchors: ["test_procedure", "param_applied_load_n", "param_load_duration_s"]
  - id: "di_sample_size_basis"
    statement: "Three specimens per certification cycle per project Test Planning Standard §4; statistical basis is acceptance of single-specimen failure as cycle failure rather than statistical bound."
    anchors: ["param_sample_size"]

relationship:
  # Empty in seed. Future `verifies` (TestProcedure → Requirement) and `tested_against` (Part / Assembly → TestProcedure)
  # relationships populate this namespace when the V&V relationship-type ADR lands.
  #
  # NOTE on `allocates_to` to this TestProcedure: a product Requirement like REQ-000058 ("drive bracket shall withstand
  # 5400 N static load without yielding") MUST NOT be allocated to TST-000017 via `allocates_to` — that edge is the
  # future `verifies`. A *procedure-deliverable* Requirement like REQ-000201 ("certification package shall include a
  # documented static-load test procedure for the drive-bracket family") IS the right `allocates_to` source. See
  # Decision §5 guardrail.
```

**Validation walk against this example:**

- `test_procedure.verification_method == "test"` — ✓ in enum.
- `parameter:` — four records, each with stable `id`, canonical-unit field name (`_n` / `_s` / `_count` / `_c`), `fact_provenance.category` ∈ allowed S1 values, `fact_uncertainty` ∈ allowed S1 values. No `derived_from` lineage discipline (correctly absent — TestProcedure parameters are design facts).
- `attachment:` — three records; `att_source_sop` is `source_authoring` with no `derived_from_attachment_id` (correctly absent); `att_release_pdf` and `att_lab_runsheet` are derived with `derived_from_attachment_id: "att_source_sop"` ✓. Lineage chain terminates at `source_authoring` ✓.
- Released-state invariant: `att_source_sop` exists with `role: source_authoring` AND resolved `content_hash` ✓.
- Decision §3 specialization: `att_source_sop` is the signed SOP PDF (canonical method spec), not a metadata stub ✓ (semantic — author-attested).
- `relationship:` empty; allocates_to records authored on the Requirement side per ADR/0013, subject to Decision §5 authoring guardrail.

## Consequences

- **Eighth Object Type lands.** Seed catalogue: Part, Requirement, Assembly, Component, SoftwareModule, Drawing, EvidenceArtifact, TestProcedure.
- **Third Attachment-bearing Object instance.** Second reuse of [ADR/0017](0017-object-type-drawing.md)'s template after [ADR/0019](0019-object-type-evidence-artifact.md), validating template reusability with a different semantic specialization on `source_authoring`. Pattern is now: **every Attachment-bearing Object Type specializes `source_authoring` semantically when its arc lands; structural shape stays uniform.** Drawing = authored canonical drawing payload; EvidenceArtifact = canonical evidence payload (not setup-only); TestProcedure = canonical procedure document (not metadata-only stub).
- **All three Tier-2 Object Types from the Glossary candidate pool promoted.** Drawing ([ADR/0017](0017-object-type-drawing.md)), EvidenceArtifact ([ADR/0019](0019-object-type-evidence-artifact.md)), TestProcedure (this ADR).
- **V&V Object Type triad complete.** TestProcedure + EvidenceArtifact + future `verifies` / `tested_against` / `cites` relationships. The V&V relationship-type ADR is the natural immediate next arc; TestProcedure existing as a peer Object Type unblocks it.
- **Pattern Catalogue Attachment-bearing Object row Applies-to extends** from `Drawing, EvidenceArtifact (future annotated-simulation candidates, etc.)` to `Drawing, EvidenceArtifact, TestProcedure (future annotated-simulation candidates, etc.)`.
- **Deliverable-vs-emergent governing principle for `allocates_to` target inclusion now operational.** ADR/0017 (Drawing YES) + ADR/0019 (EvidenceArtifact NO, emergent) + ADR/0020 (TestProcedure YES, with wrong-verb guardrail) make the principle concrete. The cut is: committed-to-produce deliverables MAY be `allocates_to` targets; emergent records MAY NOT. Within "MAY," the wrong-verb guardrail constrains *which* Requirements can target the deliverable (e.g., only procedure-deliverable Requirements for TestProcedure; only product / interface Requirements for Part / Assembly).
- **Partial supersession of [ADR/0006 §"Consequences" line 397](0006-object-type-requirement.md) for TestProcedure.** ADR/0006 forward-referenced TestProcedure as reusing the structured-text content pattern for "test procedure body." ADR/0020 instead locates the canonical procedure body in the `source_authoring` attachment per Decision §3 — the natural consequence of choosing the Attachment-bearing pattern. Structured per-step records inside the sidecar are deferred to a future Schema Change Note (Alternatives §H). The "evidence summary" half of ADR/0006 line 397's forward reference is unaffected (handled by [ADR/0019](0019-object-type-evidence-artifact.md)'s `evidence.summary` field).
- **`relationship/allocates_to.schema.json` endpoint Type union extended.** TestProcedure added to target Type union additively. [ADR/0013](0013-relationship-type-allocates-to.md)'s overall status remains `accepted` (additive extension, not supersession). Same posture as ADR/0014 / ADR/0016 / ADR/0017 extensions.
- **Schema bundle bump.** Active bundle moves v0.16.0 → v0.17.0.
- **Glossary additions.** [Glossary.md](../Glossary.md) v0.21: new `TestProcedure` entry; small update to the existing `allocates_to` entry's target Type union wording.
- **SystemState updates.** Attachment-bearing Object row Applies-to extends. Recent Pattern Changes entry. Current Front advance (seed Object Type catalogue 7 → 8).
- **V&V relationship-type ADR (`verifies` / `tested_against` / `cites`) is the natural immediate next arc.** Pre-declared in multiple earlier ADRs; will exercise the wrong-verb cut Decision §5's guardrail makes explicit; lifts the Requirement-to-EvidenceArtifact citation deferral from ADR/0019; reopens [ADR/0009 Alternatives §E](0009-relationship-type-satisfies.md)'s criterion-level `fact_ref` deferral.
- **Test execution model deferred.** When a TestProcedure is run, what records the execution? Likely an event payload (`test_execution_started` / `test_execution_completed`) plus an EvidenceArtifact whose `design_intent` anchors back to the executed TestProcedure UUID. Not designed in this ADR; future arc.
- **Structured `step:` namespace deferred** — Schema Change Note when production case surfaces per Alternatives §A3 and §H.
- **`test_kind` enum deferred** — Schema Change Note if recurring need surfaces.
- **TestProcedure as `satisfies` source deferred** — Schema Change Note if production case surfaces (same posture as Component / SoftwareModule / Drawing / EvidenceArtifact).
- **Cross-project TestProcedure adoption deferred** — N/A in seed; routes through local Binding Object pattern per [ADR/0008 §4](0008-cross-project-object-identity.md) engineering-structure default. A consumer project importing a regulatory test procedure published in a catalog project authors a local TestProcedure that references the upstream via prose / design-intent anchors; structured catalog-binding for TestProcedures is deferred until concrete case surfaces.
- **Verification-method consistency check deferred** — Future V&V ADR concern. Schema check at `verifies` relationship time: `TestProcedure.verification_method` consistent with verified Requirement's `default_verification_method`.
- **Regulated-procedure approval workflow integration** — out of scope per [Manifesto P11](../Manifesto.md); project / adapter concern.
