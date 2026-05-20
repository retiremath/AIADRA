---
name: adr-0022-test-execution-model
status: accepted
date: 2026-05-20
supersedes: 0005-object-type-part (partial — §11 line 214 EvidenceArtifact-target half of `tested_against` pre-declaration; direct Part → EvidenceArtifact resolved by declining-to-add: multi-hop traversal through TestExecution is the structural answer); 0007-object-type-assembly (partial — §11 line 245 EvidenceArtifact-target half of `tested_against` pre-declaration; direct Assembly → EvidenceArtifact resolved by declining-to-add: multi-hop traversal through TestExecution is the structural answer); 0019-object-type-evidence-artifact (partial — `collection_context` field load-bearing role for TestProcedure linkage; field remains as optional prose-only context but structural linkage is now graph traversal EvidenceArtifact ←produces← TestExecution →executes→ TestProcedure); 0020-object-type-test-procedure (partial — Consequences event-payload sketch `test_execution_started` / `test_execution_completed`; promoted to first-class Object Type with Object event taxonomy `test_execution_created` / `_changed` / `_released` / `_retired`)
superseded_by: none
resolves: []
---

# ADR/0022 — Test execution model: TestExecution Object Type + `executes` / `executed_on` / `produces` relationships

## Status

**Accepted** — 2026-05-20. Ninth Object Type after Part / Requirement / Assembly / Component / SoftwareModule / Drawing / EvidenceArtifact / TestProcedure. **Fourth Attachment-bearing Object** instance — third reuse of the [ADR/0017](0017-object-type-drawing.md) template after [ADR/0019](0019-object-type-evidence-artifact.md) and [ADR/0020](0020-object-type-test-procedure.md), validating the template a third time with a TestExecution-specific `source_authoring` specialization: **canonical record of the execution event** (raw instrument output, signed inspector report, automated test framework output, video log, or equivalent), not a metadata-only stub. **Combined ADR** also lands **three new execution-instance relationship types** in one bundle per [ADR/0021](0021-relationship-types-v-and-v.md) / [ADR/0012](0012-relationship-types-derived-from-and-refines.md) precedent: `executes` (TestExecution → TestProcedure), `executed_on` (TestExecution → Part | Assembly), `produces` (TestExecution → EvidenceArtifact). After this ADR, the V&V framework is *operationally executable* end-to-end: a procedure can be executed, an executed run can be recorded, evidence produced by that run is graph-linked to procedure and tested-Object atomically.

**Pattern-setting on four counts** (each is the first instance of its category, all confirmed in [Codex1 Requested Feedback](../Discussions/20260520/20260520-1/Codex1.md) and [Codex2 sign-off](../Discussions/20260520/20260520-1/Codex2.md)):

1. **First execution-instance Object Type** — distinct from design-intent Object Types (Part / Requirement / Assembly) and Attachment-bearing canonical-record Object Types (Drawing / EvidenceArtifact / TestProcedure). The execution-instance category records *what happened in a specific historical event* rather than *what the engineering intent is*.
2. **First execution-instance relationship category** — `executes`, `executed_on`, `produces` are historically anchored. **Fixed-only binding (Float schema-rejected)**; **`endpoints[0].revision_id` unconditionally REQUIRED**. Future observation / measurement / event-recording relationships inherit this posture.
3. **First per-relationship-type cardinality-at-release rules** — `executes` exactly 1; `executed_on` ≥1; `produces` ≥0 globally with **status-sensitive normative refinement** (`completed` SHOULD ≥1, Layer-2 diagnostic if 0; `aborted` MAY 0; `inconclusive` MAY 0 or ≥1).
4. **First "resolution-by-declining-to-add"** — the [ADR/0021](0021-relationship-types-v-and-v.md) frontmatter `supersedes:` entry for the EvidenceArtifact-target half of `tested_against` is resolved by *not* adding a direct Part / Assembly → EvidenceArtifact edge; instead, the multi-hop traversal `Part →tested_against→ TestProcedure ←executes← TestExecution →produces→ EvidenceArtifact` carries the linkage with full execution-instance binding.

**Four partial supersessions** of prior ADRs per the frontmatter — ADR/0005 + ADR/0007 EvidenceArtifact-target half of `tested_against` pre-declaration resolved by declining-to-add; ADR/0019 `collection_context` load-bearing role partially superseded; ADR/0020 §"Consequences" event-payload sketch promoted to first-class Object event taxonomy.

After this ADR, the named relationship-type catalogue grows from eleven to fourteen (`satisfies`, `composed_of`, `mated_to`, `derived_from`, `refines`, `allocates_to`, `parameter_expression`, `depicts`, `verifies`, `tested_against`, `cites`, **`executes`**, **`executed_on`**, **`produces`**); the catalogue from [ADR/0009 §3](0009-relationship-type-satisfies.md) is operationally complete except `derived_geometry_from` (awaits FreeCAD Domain Adapter scope per [Manifesto P12](../Manifesto.md)).

## Context

Discussion trail in [`Docs/Discussions/20260520/20260520-1/`](../Discussions/20260520/20260520-1/). [Codex1](../Discussions/20260520/20260520-1/Codex1.md) produced two blockers and three non-blockers; both blockers tightly scoped (worked-example lineage repair + parameter `derived_from` syntax alignment) and structurally addressed in [Claude2](../Discussions/20260520/20260520-1/Claude2.md); [Codex2](../Discussions/20260520/20260520-1/Codex2.md) signed off without further objection. Codex1's eight feedback-requested decisions all converged on round 1; no model-level reopens. Both close conditions met:

1. Worked-example `derived_secondary` lineage repair — `att_post_test_photos` now carries `derived_from_attachment_id: "att_instron_log"`; validation walk aligned with [ADR/0017 §2 line 122 + §8 lines 246-248](0017-object-type-drawing.md) discipline. Multiple-`source_authoring` alternative considered and explicitly deferred to future Schema Change Note if multi-channel parallel observations become common.
2. TestExecution parameter `derived_from` syntax alignment with [ADR/0019 §4 line 169](0019-object-type-evidence-artifact.md) — all four parameter records now use `"attachment:att_instron_log"` qualified form; Decision §8 validation block expanded to mirror ADR/0019 §8 lines 233-237 verbatim.

Five pressures converge on the test execution model:

1. **The V&V chain breaks at "what records an execution."** [ADR/0021](0021-relationship-types-v-and-v.md) wired the design-intent V&V family (`verifies` / `tested_against` / `cites`) — every link is a declarative engineering statement (procedure verifies requirement; part is tested against procedure; requirement cites evidence). But the engineering act *underneath* — a specific run on a specific date with a specific operator producing a specific evidence record — had no addressable record. [ADR/0020 §"Consequences"](0020-object-type-test-procedure.md) sketched it as an event payload; that sketch is insufficient because (a) one run can produce multiple EvidenceArtifacts (stress-strain curve + post-test photo log + raw instrument trace, each as its own evidence record per [ADR/0019](0019-object-type-evidence-artifact.md)'s `evidence_kind` enum), (b) one run can test multiple Objects in a shared fixture, (c) re-runs of the same procedure produce a *sequence* of execution records over time, each independently approvable.
2. **ADR/0021's deferrals stack here.** Four explicit deferrals pointed at this arc: Part / Assembly → EvidenceArtifact direct edge (frontmatter `supersedes:`); TestProcedure-as-source for `cites` (Alternatives §C2); coverage / verification_state / evidence_ref properties (Alternatives §G); and the "natural near-term arc" naming in §"Consequences". Resolving the structural ones as a bundle prevents arc-boundary re-litigation; TestProcedure-as-source for `cites` and coverage/verification_state remain explicitly deferred per Decision §10.
3. **EvidenceArtifact lineage to TestProcedure was prose-only.** [ADR/0019 §3 + §"Decision §5"](0019-object-type-evidence-artifact.md) handled procedure-evidence linkage via `collection_context` (prose-only) + `design_intent:` (prose anchor). Sufficient for narrative traceability but does not enforce *which* TestProcedure produced *which* EvidenceArtifact at *which* moment in time. The ADR/0019 guardrail ("structured TestProcedure citation lives in the future V&V relationship family") is now fulfilled by the V&V family from ADR/0021 + the execution-instance family from this ADR jointly.
4. **Execution-instance relationships are a new category — pattern-setting decision needed.** Every named relationship type in the catalogue before ADR/0022 was *design-intent* (declares engineering meaning between Objects whose canonical state changes over time). Execution-instance relationships are *historical-event* (the run happened at a specific moment, against specific Revisions of everything involved). The Float-default posture from [ADR/0009 §"Decision §4"](0009-relationship-type-satisfies.md) assumes "consumer wants to track the target's current state" — semantically wrong for execution records. Pattern-setting departure required (Decision §6); future observation / measurement / event-recording relationships inherit the posture.
5. **The boundary between "first-class Object Type" and "structured event" was sharper here than for any prior Object Type.** TestExecution has identity (UUID + Number, separate per run), lifecycle (in-work while authoring; released when sealed), referenceability (multiple Evidence records produced; multiple tested Objects), and provenance (test engineer + reviewer sign-off — distinct from procedure approval and evidence approval). The C1-C4 Promotion criteria pass cleanly. Treating it as event-only would force every prior Attachment-bearing-Object decision to be re-decided on event-payload terms. The Promotion path is the right home.

## Promotion Rule walk — via Attachment-bearing Object pattern

Inherits from [ADR/0017 §"Promotion Rule walk"](0017-object-type-drawing.md). TestExecution passes the [Promotion Rule capability test](../TruthModelSchema.md) via the same **Attachment-bearing Object** named non-disqualifier pattern from [commitment 5](../TruthModelSchema.md):

- **C1 — Independent identity.** TestExecution `TEX-000007` has stable local UUID + Number identifying *the specific run event* — independent of the procedure that was executed (TST-000017 can be executed many times producing many TEX-NNNNNN records), of the tested Object (P-000058 may be tested in many runs), of the evidence produced (a single run may produce multiple EVD-NNNNNN records, each separately identified). The run is the engineering event itself; subsequent re-runs, re-tests, and re-certifications each get a new TEX identity.
- **C2 — Independent lifecycle.** TestExecution has its own release cadence — `in_work` while authoring (typically during/just after the physical run, while attachments resolve and parameters are tabulated); `under_review` (per [Glossary "Lifecycle State"](../Glossary.md); common for safety-critical run-review workflows); `released` when the test engineer signs off "this run is sealed as an engineering record"; `retired` if superseded (re-run with corrected fixture; mis-recorded instrument settings discovered post-hoc; etc.). Lifecycle is *distinct from* the procedure's lifecycle (`released` procedure can have many `in_work` and `released` runs against it) and *distinct from* the produced evidence's lifecycle.
- **C3 — Independent referenceability.** Per Pressure 1 and Promotion C3 cases: referenced by multiple EvidenceArtifacts via inverse-of-`produces`; referenced by multiple Parts via inverse-of-`executed_on`; referenced via prose in certification records, audit trails, and design-intent anchors. The reusability across multiple downstream references is the load-bearing argument for first-class identity.
- **C4 — Independent provenance / approval.** Run approval is its own engineering decision — typically test engineer + run reviewer + (for regulated domains) certification authority sign-off "this run was clean / under controlled conditions / data is engineering-truth." Distinct from procedure approval (test engineer + methodology reviewer) and evidence approval (test engineer + technical reviewer). The signing-act on `released` lifecycle transition is the engineering-canonical record that the run-as-recorded is engineering-truth.

**D1–D7 disqualifier walk:**

- **D7 (Derived view)** — N/A *because* the schema requires `source_authoring` attachment at release per inherited [ADR/0017 §2](0017-object-type-drawing.md), specialized per Decision §2 to be the canonical record of the execution event (not a metadata stub). The canonical layer is structural; D7 is excluded. (Fourth operationalization of this argument; same mechanism as Drawing / EvidenceArtifact / TestProcedure.)
- **D1–D6** — N/A or trivially pass.

Conclusion: **TestExecution is a first-class Object Type via the Attachment-bearing Object pattern.** Ninth Object Type; fourth Attachment-bearing instance.

## Pre-declared constraints honored

| Constraint | Source | Disposition |
|---|---|---|
| Test execution model (atomic binding of procedure-revision + executed-run + produced-evidence + tested-Object) is the natural near-term arc | [ADR/0020 §"Consequences"](0020-object-type-test-procedure.md), [ADR/0021 §"Consequences"](0021-relationship-types-v-and-v.md) | Honored — this ADR lands it. |
| Part / Assembly → EvidenceArtifact direct edge (EvidenceArtifact-target half of `tested_against` pre-declaration from ADR/0005 §11 / ADR/0007 §11) | [ADR/0021 §"Pre-declared constraints honored"](0021-relationship-types-v-and-v.md) frontmatter `supersedes:` entry | **Resolved by declining to add the direct edge.** Multi-hop traversal `Part →tested_against→ TestProcedure ←executes← TestExecution →produces→ EvidenceArtifact` per Decision §3 / §5. The ADR/0021 deferred half lands as a *non-addition* (no direct shape introduced); the structural answer is the execution model. ADR/0005 §11 / ADR/0007 §11 partial-supersession ceremony from ADR/0021 carries forward unchanged; this ADR is the resolution venue named there. `tested_against` shape from ADR/0021 §3 stays unchanged. |
| Test execution events (`test_execution_started` / `test_execution_completed`) deferred to test execution model | [ADR/0020 §"Consequences"](0020-object-type-test-procedure.md) | **Partial supersession.** Event taxonomy lands as Object-event family per [S3 commitment 5](../TruthModelSchema.md), NOT as standalone event payload. Events: `test_execution_created` / `test_execution_changed` / `test_execution_released` / `test_execution_retired` (snake_case per ADR/0016 / ADR/0019 / ADR/0020 convention). The ADR/0020 §"Consequences" "started" / "completed" wording is non-normative; promoting TestExecution to Object Type subsumes both lifecycle moments into the standard Object event taxonomy (`_created` ≈ run authored; `_released` ≈ run sealed; intermediate state changes ≈ `_changed`). |
| EvidenceArtifact-back-to-TestProcedure lineage currently expressed only via `design_intent:` prose / `collection_context` prose | [ADR/0019 §3 + worked-example line 257 + §"Decision §5"](0019-object-type-evidence-artifact.md) | **Partial supersession of ADR/0019 §3 `collection_context` load-bearing role.** `collection_context` REMAINS in the seed `evidence:` block (prose-only human-readable context — test stand identifier, environmental notes, instrument settings prose) but is no longer load-bearing as the TestProcedure linkage anchor. After this ADR, structural linkage is the graph traversal `EvidenceArtifact ←produces← TestExecution →executes→ TestProcedure`. The `design_intent:` prose anchor pattern from ADR/0019 worked-example line 257 remains available for additional engineering rationale; the load-bearing procedure linkage is now structural. ADR/0019 §3's "structured TestProcedure citation lives in the future V&V relationship family" guardrail is jointly fulfilled by ADR/0021 + this ADR. |
| TestProcedure-as-source for `cites` (procedure-cites-prerequisite-evidence — calibration certs) | [ADR/0021 §"Alternatives §C2"](0021-relationship-types-v-and-v.md) | **Still deferred** per Decision §10 / Alternatives §F. Procedure-cites-prior-evidence is a distinct case from execution-produces-evidence (this ADR handles the latter via `produces`); out of scope for execution model. Future Schema Change Note. |
| Coverage / verification_state / evidence_ref properties deferred | [ADR/0009 §"Consequences"](0009-relationship-type-satisfies.md), [ADR/0021 §"Alternatives §G"](0021-relationship-types-v-and-v.md) | **Still deferred** per Decision §10 / Alternatives §G. Execution model existing makes these derivable from graph traversal (acceleration cache per [ADR/0001 §3](0001-storage-substrate.md)); explicit aggregation properties wait for production case. |
| Attachment-bearing Object pattern + structural D7-escape + `derived_from_attachment_id` lineage + algorithm-qualified `content_hash` as authority | [ADR/0017 §2 + §8](0017-object-type-drawing.md) | Inherited verbatim — fourth Attachment-bearing instance (third reuse of the template). TestExecution-specific `source_authoring` specialization per Decision §2: canonical record of the execution event (raw instrument output / signed inspector report / automated test framework output / video log / equivalent), not a metadata-only stub. |
| Parameter lineage discipline (`fact_provenance.derived_from` with at least one `"attachment:<id>"` entry) | [ADR/0019 §"Decision §4" line 169 + §8 lines 233-237](0019-object-type-evidence-artifact.md) | Inherited verbatim — TestExecution parameters are derived measurements / observed values from the run record, parallel to EvidenceArtifact's parameter lineage discipline. Full chain: parameter → `derived_from` → attachment → `content_hash` → Vault bytes. (Note: divergence from [ADR/0020 §4](0020-object-type-test-procedure.md) — TestProcedure parameters are nominal design facts with no lineage discipline; TestExecution parameters are observed measurements with lineage required.) |
| Per-relationship-schema opt-in discipline for criterion-level addressing primitives (`endpoints[].fact_ref` / `source_fact_ref`) | [ADR/0021 §"Decision §6" + §9](0021-relationship-types-v-and-v.md) | Honored — none of the three new relationship types opt in (no Requirement endpoint on `executes` / `executed_on` / `produces`); explicit do-not-opt-in declared in Decision §8. |
| Target-Type-governs cross-project policy | [ADR/0013 §"Cross-project"](0013-relationship-type-allocates-to.md), [ADR/0008 §4](0008-cross-project-object-identity.md) | Honored — all three new relationships opt OUT of direct cross-project endpoints (target Types are local deliverables / local emergent records; execution-producing-external-evidence is exotic; defer). Decision §7. Adds a fifth implicit cross-project rationale dimension: **event-locality** — execution events are intrinsically local. |
| Thirteen base trace-relationship pattern fields | [ADR/0009 §"Pattern declaration"](0009-relationship-type-satisfies.md) | Inherited verbatim by all three execution-instance relationship types; no new base-level pattern fields. **Departure on binding default only** per Decision §6 — execution-instance relationships forbid Float (Fixed-only). |

## Alternatives Considered

### A. TestExecution shape — Object Type vs event vs namespace-on-EvidenceArtifact (load-bearing)

**A1. TestExecution as ninth first-class Object Type via Attachment-bearing template.** *Chosen — see Decisions §1 + §2.*

> Third reuse of [ADR/0017](0017-object-type-drawing.md) template after EvidenceArtifact (ADR/0019) and TestProcedure (ADR/0020). Promotion C1-C4 pass: independent UUID + Number per run; independent in-work → released → retired lifecycle (run gets sealed when test engineer signs off); referenced by multiple EvidenceArtifacts via `produces` (one run, multiple evidence records — Pressure 1 Case 2); independent approval (test engineer + run reviewer; distinct from procedure approval and evidence approval). D7-escape via specialized `source_authoring` (canonical record of execution event — raw instrument output / signed inspector report / automated test framework output / video log / equivalent — not metadata-only stub). [Codex1 agreed](../Discussions/20260520/20260520-1/Codex1.md) the C1-C4 walk is tight.

**A2. Event-only (no Object Type).** [ADR/0020 §"Consequences"](0020-object-type-test-procedure.md) sketch: `test_execution_started` / `test_execution_completed` events; EvidenceArtifact carries execution metadata via `design_intent:` prose anchors.

> **Rejected.** (a) Events in AIADRA are not addressable per [S0 commitment 1](../TruthModelSchema.md); a run cannot be referenced from multiple EvidenceArtifacts as a single shared identity, forcing duplication of execution metadata across each produced evidence record. (b) One run produces multiple Evidence records is a load-bearing case (Pressure 1); event-only collapses it to "each Evidence record carries its own run timestamp / operator / instrument fields," with no shared addressable run. (c) Run approval is a distinct engineering act from evidence approval and procedure approval; event-only has no place to hold that approval as a first-class lifecycle transition. (d) The ADR/0020 §"Consequences" sketch is non-normative; this ADR is the venue to pin the shape.

**A3. Execution metadata as structured namespace inside EvidenceArtifact (extension to ADR/0019).** Add `execution:` block on EvidenceArtifact carrying (procedure_uuid, procedure_revision, tested_object_uuid, date, instrument, operator); no new Object Type.

> **Rejected.** (a) Same Case-2 / Case-3 pathology as A2 — when one run produces multiple Evidence records, the execution metadata duplicates across them; if it drifts, integrity is lost. (b) Conflates the *execution event* with the *produced evidence* — distinct engineering concepts deserving distinct addressable identities. (c) Forces EvidenceArtifact to carry tested-Object endpoints inside its sidecar, which is a hidden relationship masquerading as a parameter — pattern violation. (d) Cross-project semantics get murky: a consumer Requirement that `cites` an upstream EvidenceArtifact would transitively pin the upstream's execution metadata, leaking implementation detail across project boundaries.

**A4. TestExecution as a "lighter" tier — addressable record without full Object Type status.** Sidecar without Promotion Rule walk.

> **Rejected.** AIADRA has no "lighter tier" — [S0 commitment 1](../TruthModelSchema.md) establishes Objects as the universal addressable unit. Introducing a sub-Object tier is a substantial framework change requiring its own ADR; out of scope here and not justified.

### B. ADR scope — combined vs split

**B1. Combined ADR (Object Type + three relationships in one bundle).** *Chosen — Decisions §1-§7.*

> Precedent: [ADR/0021](0021-relationship-types-v-and-v.md) combined three relationship types citing "the family is coupled enough that one ADR is easier to reason about than three sequential ones" (Codex2 sign-off on that arc). The execution-instance family is *more* coupled — the Object Type and its three relationships are interdependent (Object Type alone is dead-letter without relationships; relationships alone are undefined without the source Object Type). Splitting would force re-decision of cross-cutting concerns (Float-default departure; cross-project per-type policy; cardinality-at-release) across arc boundaries. [Codex1 agreed](../Discussions/20260520/20260520-1/Codex1.md) splitting would leave a dead-letter Object Type.

**B2. Split — ADR/0022 (TestExecution Object Type) → ADR/0023 (execution relationships).**

> **Rejected.** Mirrors the (ADR/0020 TestProcedure → ADR/0021 V&V relationships) two-arc split, which was the closest historical parallel. The case for split: cleaner per-arc decision surface. The case against (and why combined chosen): the Object Type's worked example is dead-letter without relationships; the Float-default departure (Decision §6) and the declined-direct-edge resolution (Decision §3 / §5) are most cleanly settled with the full picture visible.

**B3. Even-larger combined — also land coverage / verification_state / evidence_ref properties + TestProcedure-as-source for `cites`.**

> **Rejected.** Coverage / verification_state aggregation depends on outcome semantics (deferred per [ADR/0019 §"Alternatives §E1"](0019-object-type-evidence-artifact.md)); landing them here would force a separate decision surface on pass/fail framing; outside this arc. TestProcedure-as-source for `cites` is structurally distinct (procedure-cites-prior-evidence, not procedure-produces-evidence); separate Schema Change Note venue. Both stay deferred (Decision §10).

### C. Execution-instance relationship binding default (pattern-setting)

**C1. Fixed-only — execution-instance relationships forbid Float entirely.** *Chosen — Decision §6.*

> Execution records are historically anchored. "This past run tracks the procedure's current Revision" is semantic nonsense: the run *happened against* a specific procedure Revision; subsequent procedure changes do not retroactively change what was run. Same logic applies to `executed_on` (the run tested a specific Part Revision at a specific moment) and `produces` (the run produced a specific EvidenceArtifact Revision). All three pin Revision ids unconditionally at authoring. Pattern-setting: future observation / measurement / event-recording relationships inherit this posture. [Codex1 agreed](../Discussions/20260520/20260520-1/Codex1.md): "Float is not just a poor default here; it is the wrong semantic for a historical event."

**C2. Float-default per ADR/0009 §"Decision §4".**

> **Rejected.** Float on execution-instance relationships is semantically meaningless (see C1). Defaulting to it would invite authoring bugs and weaken the load-bearing invariant.

**C3. Indirect-binding per ADR/0011 §5 `mated_to` posture.**

> **Rejected.** Indirect-binding delegates to address mechanism (occurrence path resolution). Execution relationships have no address mechanism — the binding IS the direct relationship-record-level Revision pin. C3 misapplies the mechanism.

### D. Part / Assembly → EvidenceArtifact direct edge resolution

**D1. Decline to add the direct edge; multi-hop traversal is the structural answer.** *Chosen — Decision §3 / §5.*

> The [ADR/0021](0021-relationship-types-v-and-v.md) deferral named "atomic binding of procedure-revision + executed-run + produced-evidence + tested-Object" as the load-bearing case. Atomic binding requires a single addressable record (TestExecution per Decision §1) connecting all four pieces. A direct Part → EvidenceArtifact edge does NOT carry the binding (it elides procedure-revision and execution-instance); a direct edge would canonicalize half the linkage. Cleaner: declare the direct edge structurally unnecessary; traversal `Part →tested_against→ TestProcedure ←executes← TestExecution →produces→ EvidenceArtifact` IS the relationship between Part and Evidence, encoded as a graph path rather than a single edge. [Codex1 agreed](../Discussions/20260520/20260520-1/Codex1.md): "Multi-hop traversal through TestExecution is the cleaner structural answer."

**D2. Add `tested_against` target Type extension to include EvidenceArtifact (per the original ADR/0005 §11 / ADR/0007 §11 pre-declaration).**

> **Rejected.** This was ADR/0021's pre-supersession pre-declaration shape; partially superseded for the load-bearing reason that `tested_against` alone cannot carry execution-instance semantics (which Revision of procedure? which run? which operator?). Reintroducing the direct edge here without those bindings would re-create the pathology ADR/0021 flagged.

**D3. Add a new Part / Assembly → EvidenceArtifact relationship type with execution semantics baked in.**

> **Rejected.** Conflates execution-instance with declarative-trace. The proposed `produces` (TestExecution → EvidenceArtifact) carries execution-instance semantics on the execution side; a separate Part / Assembly → EvidenceArtifact relationship type would either duplicate or fragment.

### E. TestExecution `source_authoring` semantic specialization

**E1. Inherit ADR/0017's generic `source_authoring` (any authored canonical payload).**

> **Rejected** (preemptively, per ADR/0019 / ADR/0020 precedent). Permits a degenerate case: a TestExecution whose `source_authoring` is a one-line "we ran the test, more or less" stub does not satisfy the C1-C4 Promotion criteria. Per-Type specialization is now the template pattern.

**E2. TestExecution-specific specialization: `source_authoring` MUST be the canonical record of the execution event (raw instrument output / signed inspector report / automated test framework output / video log / equivalent canonical record of what occurred during the run), not a metadata-only stub.** *Chosen — Decision §2.*

> Parallel to ADR/0019's "canonical evidence payload, not setup-only" and ADR/0020's "canonical procedure document, not metadata-only stub." Same template pattern; different per-Type semantic specialization. Validates the template's reusability for a third time with substantive divergence. [Codex1 agreed](../Discussions/20260520/20260520-1/Codex1.md) the enumeration covers the run-record taxonomy without over-prescribing.

**E3. Multiple `source_authoring` records (parallel-independent canonical captures).** Treat instrument data and visual observation as parallel-canonical instead of source + derived; permitted by ADR/0017's "at least one `source_authoring`" framing.

> **Considered and deferred** (per [Claude2 §B1 absorption](../Discussions/20260520/20260520-1/Claude2.md)). Engineering-honest for runs where multiple primary observation channels exist with no causal lineage between them. However: (i) preserving the single-source-anchor mental model of the Attachment-bearing template (Drawing / EvidenceArtifact / TestProcedure all pin a privileged source); (ii) the temporal/causal-lineage justification for treating photos as `derived_secondary` of the instrument log is coherent (photos document post-run state, which the run produced); (iii) arc velocity favors the smaller repair. If a future production case shows multi-channel parallel observations are common (e.g., synchronized multi-instrument runs in safety-critical V&V), a Schema Change Note can pin the "multiple `source_authoring` for execution-instance Attachment-bearing Objects" alternative. Seed adopts single-`source_authoring` posture per [Codex1 recommendation](../Discussions/20260520/20260520-1/Codex1.md) and [Codex2 sign-off](../Discussions/20260520/20260520-1/Codex2.md).

### F. TestProcedure-as-source for `cites` (procedure-cites-prerequisite-evidence)

**F1. Land procedure-cites-prerequisite-evidence as TestProcedure-source extension to `cites`.**

> **Rejected (for seed).** Distinct case from procedure-produces-evidence (handled by `produces` in this ADR). Procedure-cites-prior-evidence is e.g. "this test procedure requires the instrument's most recent calibration certificate to be cited in the test setup." Real engineering pattern, but conflates with the produces-graph if landed here. Future Schema Change Note when concrete production case surfaces.

**F2. Defer per ADR/0021 §"Alternatives §C2".** *Chosen — Decision §10.* Carries forward unchanged.

### G. Coverage / verification_state / evidence_ref properties

**G1. Land coverage / verification_state / evidence_ref properties on `verifies` records now that execution model exists.**

> **Rejected (still deferred).** Each presupposes pass/fail outcome semantics (deferred per [ADR/0019 §"Alternatives §E1"](0019-object-type-evidence-artifact.md)). Landing them here would force outcome-framing into seed; outside this arc.

**G2. Keep deferred per ADR/0021 §"Alternatives §G".** *Chosen — Decision §10.*

> Execution model existing makes aggregation derivable from graph traversal (acceleration cache per [ADR/0001 §3](0001-storage-substrate.md)). Explicit properties wait for production case where derivation cost is unacceptable.

### H. Number prefix for TestExecution

**H1. `TEX-NNNNNN`** — Test EXecution. *Chosen — Decision §1.*

> Alphabetical match to `TST-` (TestProcedure); 3-char width matches the established prefix convention. [Codex1 agreed](../Discussions/20260520/20260520-1/Codex1.md): "better than `RUN` for avoiding generic workflow/event ambiguity."

**H2. `RUN-NNNNNN`** — short, intuitive.

> **Defensible but rejected.** "Run" reads cleanly. Concern: "RUN" is generic; the established convention favors Type-specific 3-char abbreviations.

**H3. `TER-NNNNNN`** (Test Execution Record). **H4. `EXE-NNNNNN`** (clashes with software-domain "executable").

> Rejected.

### I. Cardinality of `executes` at release + status-sensitive `produces` cardinality

**I1. Exactly one `executes` record per released TestExecution.** *Chosen — Decision §3 / §8.*

> A TestExecution represents one run of one procedure. If two procedures were executed back-to-back as a "campaign," each is its own TestExecution. Layer-2 validator hard-fails released TestExecution with !=1 `executes` records. First per-relationship-type-cardinality-at-release rule in the catalogue.

**I2. Status-sensitive `produces` cardinality.** *Chosen — Decision §5 / §8 / §9* (per [Codex1 N1 absorption](../Discussions/20260520/20260520-1/Codex1.md)).

> Global ≥0; status-sensitive normative rule: `completed` SHOULD ≥1 (Layer-2 diagnostic if 0, NOT hard-fail — preserves the legitimate exception where the TestExecution's own `source_authoring` IS the canonical record and no separate EvidenceArtifact is needed, e.g., simple inspection runs); `aborted` MAY 0; `inconclusive` MAY 0 or ≥1 (diagnostic if 0). Future Schema Change Note may escalate completed-case to MUST if production patterns show the inspection-only exception is uncommon.

**I3. Hard-fail `produces ≥1` for completed runs.**

> **Rejected (for seed).** Doubles bookkeeping for simple inspection workflows where the TestExecution's `source_authoring` attachment (signed inspector declaration) IS the evidence; forcing a parallel EvidenceArtifact Object would be ceremonial without engineering benefit. Diagnostic surfaces the boundary for project-policy decision; hard-fail can be added in future Schema Change Note.

## Decision

### 1. Number prefix + Type name

**Type name:** `TestExecution` (PascalCase).
**TypeSpecific block:** `test_execution:` (snake_case singleton; matches `test_procedure:`, `software_module:`, `evidence:` per the established convention from [ADR/0016](0016-object-type-software-module.md)+).
**Number prefix:** `TEX-NNNNNN`. Six-digit zero-padded sequential allocation from the Reservation file per [ADR/0004](0004-number-allocation.md).

### 2. `attachment:` namespace — inherited from ADR/0017 with TestExecution-specific `source_authoring` semantic

Structural shape, role enum (`source_authoring` / `rendered_primary` / `derived_secondary`), required fields, `derived_from_attachment_id` lineage discipline, algorithm-qualified `content_hash`, `vault_path` non-authoritative, pre-commit resolution, release invariants — **all inherited verbatim** from [ADR/0017 §2](0017-object-type-drawing.md).

**TestExecution-specific specialization of `source_authoring` semantic:**

> For TestExecution, at least one released `source_authoring` attachment MUST be the **canonical record of the execution event** — the actual run record: raw instrument output (oscilloscope trace, sensor log, FEA solver run output), signed inspector report (for inspection-method runs), automated test framework output (test script log, CI artifact), video log (for visual inspections / demonstrations), or equivalent canonical record of what occurred during the run. Metadata-only stubs ("we ran the procedure on this date") MUST NOT be the only `source_authoring` attachment. A released TestExecution must not be reconstructable as "a date + an operator name" without a canonical record of the event attached and named.

Parallel to [ADR/0019 §3](0019-object-type-evidence-artifact.md) and [ADR/0020 §3](0020-object-type-test-procedure.md). Third operationalization of the per-Type specialization template; structural shape stays uniform.

**Validation guidance** (semantic check; tooling-aided where parser available):

> When a parser exists for a given run-record format (instrument-output schema; test framework output schema), tooling may inspect the attachment to confirm it is an execution record, not a metadata stub. Where no parser exists, the schema cannot enforce semantic-document-shape; the rule is normative on the author. Same posture as ADR/0019 / ADR/0020 validation guidance.

### 3. `executes` (TestExecution → TestProcedure)

**Source Type:** `TestExecution`. Source-anchored on TestExecution's `relationship:` namespace per [S3 commitment 3](../TruthModelSchema.md).

**Target Type:** `TestProcedure`. Single-endpoint `endpoints` array; target only.

**Arity:** binary; source-anchored asymmetric binary serialization (Pattern Catalogue row applies).

**Cycle policy:** `trace_graph`. Cross-Type; cycles structurally impossible today.

**Self policy:** `self_forbidden`.

**Default binding:** **`fixed` (Float forbidden — pattern-setting per Decision §6).** A TestExecution executing a TestProcedure pins the procedure Revision under which the run occurred; subsequent procedure changes do not retroactively change what was executed.

**Cross-project endpoint policy:** **opt OUT.** TestProcedure is a local deliverable per [ADR/0020](0020-object-type-test-procedure.md); cross-project execution-against-external-procedure routes through local Binding Object pattern.

**Cardinality at release:** **exactly 1** `executes` record per released TestExecution (Layer-2 validator hard-fail otherwise per Decision §8).

**Criterion-level addressing:** N/A (no Requirement endpoint).

### 4. `executed_on` (TestExecution → Part | Assembly)

**Source Type:** `TestExecution`.

**Target Type union:** `Part | Assembly` per Pre-declared constraints (mirrors `tested_against` Decision §3 source-side from [ADR/0021](0021-relationship-types-v-and-v.md)). Component / SoftwareModule deferred to Schema Change Note (same parity as ADR/0021 §"Alternatives §B").

**Arity:** binary; source-anchored asymmetric binary serialization.

**Cycle policy:** `trace_graph`. Cross-Type; cycles structurally impossible today.

**Self policy:** `self_forbidden`.

**Default binding:** **`fixed` (Float forbidden per Decision §6).** A TestExecution tests a specific Part / Assembly Revision at a specific moment; pinning is unconditional.

**Cross-project endpoint policy:** **opt OUT.** Part / Assembly is a local deliverable; cross-project execution-against-external-deliverable routes through local Binding Object pattern (parity with ADR/0021 `tested_against`).

**Cardinality at release:** ≥1 `executed_on` records per released TestExecution. A run tests at least one Object (multiple specimens in a shared fixture is the multi-record case per Pressure 1 Case 2). Layer-2 validator hard-fails 0-record case.

**Criterion-level addressing:** N/A (no Requirement endpoint).

### 5. `produces` (TestExecution → EvidenceArtifact)

**Source Type:** `TestExecution`.

**Target Type:** `EvidenceArtifact`. Single Target Type; per Pressure 1 Case 2, one run may produce multiple Evidence records — that's reflected in *cardinality* on the source side (`produces` records may be multiple), not in target Type union.

**Arity:** binary; source-anchored asymmetric binary serialization.

**Cycle policy:** `trace_graph`. Cross-Type; cycles structurally impossible today.

**Self policy:** `self_forbidden`.

**Default binding:** **`fixed` (Float forbidden per Decision §6).** A TestExecution produces a specific EvidenceArtifact Revision; the produced record is the historical artifact of the run.

**Cross-project endpoint policy:** **opt OUT.** EvidenceArtifact is a local emergent record per [ADR/0019](0019-object-type-evidence-artifact.md); cross-project execution-produces-external-evidence is exotic and is not load-bearing for seed (consumer projects citing upstream evidence via `cites` per [ADR/0021 §4](0021-relationship-types-v-and-v.md) is the established cross-project shape).

**Cardinality at release** (status-sensitive per [Codex1 N1](../Discussions/20260520/20260520-1/Codex1.md) absorption):

- Global (any released TestExecution): ≥0 `produces` records.
- **Status-sensitive normative rule:**
  - `execution_status: completed` — SHOULD have ≥1 `produces` records. The central promise of the execution model is structural EvidenceArtifact lineage from execution; a completed run producing no evidence Object leaves the chain *Part → tested_against → TestProcedure ← executes ← TestExecution → produces → ?* with a missing rung. Layer-2 validator emits a non-blocking diagnostic ("completed TestExecution with no `produces` records; verify execution-evidence linkage is intended") if 0. Legitimate exception: inspection-style runs whose canonical record is the inspector's signed declaration attached to the TestExecution itself with no separate EvidenceArtifact created — the diagnostic surfaces the boundary for project-policy decision.
  - `execution_status: aborted` — MAY have 0. Aborted runs commonly produce no evidence; partial-data evidence MAY still be authored if engineering-meaningful, but is never required.
  - `execution_status: inconclusive` — MAY have 0 or ≥1. If 0, tooling MAY surface as diagnostic (a finished-but-inconclusive run without any captured evidence is unusual); not hard-fail.
- Future Schema Change Note may escalate completed-case to MUST (Layer-2 hard-fail ≥1 for completed) if production patterns show the inspection-only exception is uncommon.

**Criterion-level addressing:** N/A (no Requirement endpoint).

**Inverse view (`produced_by`):** Graph-derivable from `produces` via [ADR/0001 §3](0001-storage-substrate.md) acceleration cache; not authored as a separate relationship type. Same posture as `where-used` / `composes` / `verified_by` inverses.

### 6. Pattern-setting: execution-instance relationships forbid Float (Fixed-only)

All three new relationship types (`executes`, `executed_on`, `produces`) **MUST be `binding: fixed`** at authoring. Float is schema-rejected by each of the three relationship-type schemas.

**Rationale.** Float binding ("track target's current Revision") is meaningful for design-intent relationships (consumer Requirement satisfaction tracks the current target Revision because the engineering intent persists). It is semantically nonsensical for execution-instance relationships: the execution event is historically anchored; the run *happened against* a specific Revision; subsequent target changes do not retroactively change what was run. Permitting Float for "consistency" would invite authoring bugs and weaken the load-bearing invariant.

**Pattern-setting** (recorded in SystemState Pattern Catalogue per Codex2 N3 absorption — single row for execution-instance relationships). Execution-instance relationships are Fixed-only. Future observation / measurement / event-recording relationships inherit this posture. The Float / Fixed cut from [ADR/0009 §"Decision §4"](0009-relationship-type-satisfies.md) applies to design-intent trace relationships; execution-instance relationships are a distinct category with distinct binding semantics.

**Schema mechanism.** Each of the three relationship-type schemas explicitly enumerates `binding: "fixed"` as the only legal value (not a default-with-other-options). Endpoint `revision_id` is REQUIRED (not Conditional); `endpoints[0].revision_content_hash` REQUIRED for cross-project (currently opt OUT, but the requirement statement is forward-compatible).

### 7. Cross-project per-type policy — all three opt OUT

Per Pressure 4 / Decision §3-§5: `executes` target = TestProcedure (local deliverable; opt OUT); `executed_on` target = Part | Assembly (local deliverables; opt OUT); `produces` target = EvidenceArtifact (local emergent record; opt OUT per execution-locality argument — the execution event is a local engineering act, even when the procedure / part / evidence are conceptually upstream-derived).

**Posture summary** (extending the [ADR/0021](0021-relationship-types-v-and-v.md) family across the full trace catalogue): `satisfies` IN, `derived_from` / `refines` IN, `allocates_to` OUT, `depicts` OUT, `verifies` IN, `tested_against` OUT, `cites` IN, **`executes` OUT**, **`executed_on` OUT**, **`produces` OUT**. Cross-project rationale dimension carried forward and extended: execution events introduce a fifth implicit dimension — *event-locality* (execution events are intrinsically local; cross-project authoring of "a run that happened in another project's lab" is structurally meaningless); local-Binding-Object pattern handles cross-project deliverable adoption *before* execution-record authoring.

### 8. Validation rules (Layer 2)

**TestExecution Object:**

- `object.type == "TestExecution"`.
- `test_execution:` singleton block present with `executed_on_date` (ISO 8601 date) AND `execution_status` (enum).
- `test_execution.execution_status` ∈ {`completed`, `aborted`, `inconclusive`} (see Decision §9).
- `test_execution.operator_identifier`, `test_execution.instrument_identifier`, `test_execution.environmental_conditions_summary` if present are non-empty strings.
- `attachment:` namespace rules inherited from [ADR/0017 §"Decision §8"](0017-object-type-drawing.md); **release-state invariant: at least one `source_authoring` record with resolved `content_hash`, which (per Decision §2) MUST be the canonical record of the execution event** (semantic check; tooling-aided where parser exists).
- `parameter:` namespace canonical-unit-at-field-name discipline inherited from EvidenceArtifact (`_n`, `_s`, `_mpa`, etc.). **`fact_provenance.derived_from` lineage discipline applies** (TestExecution parameters are derived measurements / observed values from the run, parallel to EvidenceArtifact's parameter lineage discipline from [ADR/0019 §4](0019-object-type-evidence-artifact.md)): every `parameter:` record carries `fact_provenance.derived_from`; the list is non-empty; at least one entry has the form `"attachment:<id>"` referencing an existing `attachment:` record in the same sidecar; dangling `attachment:<id>` references are hard-fail at write; the referenced attachment's `derived_from_attachment_id` lineage chain (when applicable) terminates at a `source_authoring` record per ADR/0017 lineage rules. Same chain enforcement as ADR/0019: parameter → `derived_from` → attachment → `content_hash` → Vault bytes.

**`executes`:**

- `type == "executes"`.
- `endpoints` length exactly 1.
- `endpoints[0].object_uuid` resolves to `object.type == "TestProcedure"` (hard-fail otherwise).
- Source Object's `object.type == "TestExecution"` (hard-fail otherwise).
- `binding == "fixed"` (no other value permitted; schema-reject Float).
- `endpoints[0].revision_id` REQUIRED.
- **Per-record cardinality at release: exactly 1 `executes` record per released TestExecution** (Layer-2 hard-fail !=1 per Decision §3 / Alternatives §I1).
- No `endpoints[0].project_scope` permitted (schema-reject per Decision §7).
- No `endpoints[].fact_ref` or `source_fact_ref` permitted (Decision §6 inheritance from ADR/0021 §6 — execution-instance relationships do not opt in to criterion-level primitives).

**`executed_on`:**

- `type == "executed_on"`.
- `endpoints` length exactly 1.
- `endpoints[0].object_uuid` resolves to `object.type ∈ {Part, Assembly}` (hard-fail otherwise).
- Source Object's `object.type == "TestExecution"`.
- `binding == "fixed"` (no other value permitted).
- `endpoints[0].revision_id` REQUIRED.
- **Per-record cardinality at release: ≥1 `executed_on` records per released TestExecution.**
- No cross-project endpoints (per Decision §7).
- No `fact_ref` / `source_fact_ref`.

**`produces`:**

- `type == "produces"`.
- `endpoints` length exactly 1.
- `endpoints[0].object_uuid` resolves to `object.type == "EvidenceArtifact"`.
- Source Object's `object.type == "TestExecution"`.
- `binding == "fixed"`.
- `endpoints[0].revision_id` REQUIRED.
- **Per-record cardinality at release** — ≥0 globally; status-sensitive normative rule per Decision §5: `completed` SHOULD ≥1 (Layer-2 diagnostic if 0, not hard-fail); `aborted` MAY 0; `inconclusive` MAY 0 or ≥1 (diagnostic if 0).
- No cross-project endpoints (per Decision §7).
- No `fact_ref` / `source_fact_ref`.

**Cross-cutting (inherits ADR/0009 base + ADR/0021 patterns):**

- All three inherit ADR/0009's 13 base trace-relationship pattern field validations.
- All three are source-anchored: record lives in the source TestExecution's `relationship:` namespace.
- All three are `trace_graph` cycle class; `self_forbidden`.

### 9. TypeSpecific `test_execution:` block

Singleton TypeSpecific block. Conservative seed.

```yaml
test_execution:
  executed_on_date: "ISO 8601 date"       # REQUIRED — when the run occurred (YYYY-MM-DD)
  execution_status: "string"              # REQUIRED — enum: completed | aborted | inconclusive
  operator_identifier: "string"           # OPTIONAL — who ran it (project-policy whether name, role, AI agent id)
  instrument_identifier: "string"         # OPTIONAL — what hardware / software / facility was used
  environmental_conditions_summary: "string"  # OPTIONAL — prose; additional context beyond the procedure's spec
```

**`execution_status` enum (load-bearing — first introduction):**

- `completed` — run finished per procedure. Pass / fail judgment is a separate V&V concern (deferred per [ADR/0019 §"Alternatives §E1"](0019-object-type-evidence-artifact.md) — outcome lives with V&V relationships, not on the execution record).
- `aborted` — run did not finish per procedure (instrument fault, fixture failure, premature termination, environmental excursion). May produce no Evidence; if it does produce partial Evidence, the evidence record's status / completeness is its own concern.
- `inconclusive` — run finished mechanically but data quality insufficient (sensor malfunction during run; environmental contamination of result). Evidence may still be produced but is flagged as suspect.

**Cross-reference:** The `produces` relationship cardinality at release is status-sensitive per Decision §5 — `completed` typically produces ≥1 EvidenceArtifact (Layer-2 diagnostic if 0); `aborted` may produce 0; `inconclusive` may produce 0 or ≥1.

**Explicit non-decision: pass/fail framing is NOT on `test_execution:`.** Pass/fail is a V&V judgment relative to the verified Requirement / acceptance criterion; the same execution can pass criterion A and fail criterion B. Belongs in V&V relationships (`verifies` records) when outcome framing eventually lands; outside this ADR's scope per ADR/0021 §"Alternatives §G2" carry-forward.

**`operator_identifier` guardrail:** free-form string (project-policy shape). NOT a structured Object reference. AI agents that authored an execution under Workspace-native authority per [Manifesto P13](../Manifesto.md) may carry an AI-agent identifier here; the seed schema does not enumerate identifier shapes.

**`instrument_identifier` guardrail:** free-form string. NOT a structured Object reference (instruments are out-of-Core engineering elements per [ADR/0008](0008-cross-project-object-identity.md)'s catalog-project posture; if a Component-instrument linkage is needed, it lives in a future Schema Change Note).

### 10. Explicit deferrals (carried forward from ADR/0021)

- **TestProcedure-as-source for `cites`** (procedure-cites-prerequisite-evidence — calibration certs) — **still deferred** per Alternatives §F. Future Schema Change Note when production case surfaces.
- **Coverage / verification_state / evidence_ref properties** — **still deferred** per Alternatives §G. Execution model existing makes derivation possible from graph traversal; explicit aggregation primitives wait for production case.
- **`executed_on` / `produces` source extension to Component / SoftwareModule** — **deferred** to Schema Change Notes when concrete cases surface (parity with ADR/0021 §"Alternatives §B" `tested_against` source).
- **Pass / fail outcome semantics** — **still deferred** per [ADR/0019 §"Alternatives §E1"](0019-object-type-evidence-artifact.md) carry-forward. Outcome framing is its own arc when production case demands.
- **Test-campaign aggregation** (when multiple TestExecutions form a single campaign — e.g., a certification suite running 17 procedures) — deferred. Each run is its own TestExecution; an aggregating Object Type (TestCampaign / VerificationActivity) is a future arc if needed.
- **Multiple parallel `source_authoring` posture** (multi-channel independent canonical captures per Alternatives §E3) — deferred to future Schema Change Note if production case surfaces (synchronized multi-instrument runs in safety-critical V&V).

### 11. Namespace set

Three of Part's seven plus inherited `attachment:` plus singleton `test_execution:`. Same count as TestProcedure ([ADR/0020 §4](0020-object-type-test-procedure.md)) and EvidenceArtifact ([ADR/0019 §4](0019-object-type-evidence-artifact.md)).

| Namespace | In TestExecution seed? | Notes |
|---|---|---|
| `parameter:` | YES | Measured / observed run values: applied loads, durations, peak readings, post-test residuals. Field-name-encoded units. **`fact_provenance.derived_from` lineage to supporting attachment(s) REQUIRED** (parallel to EvidenceArtifact's parameter lineage per [ADR/0019 §4](0019-object-type-evidence-artifact.md) — TestExecution parameters are derived measurements from the run record, not nominal design facts). `fact_provenance.category: "measured"` typical. |
| `design_intent:` | YES | Rationale for run-time decisions / deviations / observations: why this fixture configuration, why this instrument calibration was accepted, why this run is included / excluded from the certification record. Anchors to `test_execution`, `parameter:` records, `attachment:` records, relationships. |
| `feature:` | NO | N/A. |
| `relationship:` | YES | `executes`, `executed_on`, `produces` records authored here. |
| `published_ref:` | NO | N/A. |
| `geometry_ref:` | NO | N/A. |
| `material:` | NO | N/A. |
| `source:` | NO in seed. | Run origin / upstream campaign provenance via `design_intent:` or `attachment:` metadata; future namespace extension if recurring case. |
| **`attachment:`** | YES | Vault-attached canonical run record per Decision §2 with TestExecution-specific `source_authoring` specialization. |

### 12. Lifecycle, eventability, Revisions, bundle bump

**Lifecycle** independent per Promotion C2. States: `in_work` → `released` → `retired`. Optional `under_review` per [Glossary "Lifecycle State"](../Glossary.md) (common for regulated-domain run-review workflows). A TestExecution is `released` when the test engineer signs off "this run is sealed as an engineering record."

**Eventability** per [S3 commitment 5](../TruthModelSchema.md): `test_execution_created`, `test_execution_changed`, `test_execution_released`, `test_execution_retired` (snake_case per the convention from ADR/0016 / ADR/0019 / ADR/0020). **Partial supersession of [ADR/0020 §"Consequences"](0020-object-type-test-procedure.md)** event sketch (`test_execution_started` / `test_execution_completed`): those names presumed event-only semantics; promoting TestExecution to first-class Object Type unifies under the Object event taxonomy. `_created` ≈ run record authored (typically during/after the physical run); `_changed` ≈ parameter / attachment / relationship edits; `_released` ≈ test-engineer sign-off; `_retired` ≈ run superseded (e.g., re-run with corrected fixture).

**Revision schema** per [S2 commitment 1](../TruthModelSchema.md). Each TestExecution Revision is a separate immutable artifact at canonical path `revisions/<object-uuid>/<revision-id>.yaml`. Released TestExecution Revision MUST carry at least one `attachment:` record with `role: source_authoring` AND `content_hash` resolved — and per Decision §2 specialization, that `source_authoring` attachment MUST be the canonical record of the execution event.

**Bundle bump:** **v0.18.0 → v0.19.0**, MINOR additive per [ADR/0003 §11](0003-schema-governance.md). Changes:

- NEW: `sidecar/TestExecution.schema.json`.
- NEW: `object.type = "TestExecution"` discriminator value.
- NEW: `TEX-NNNNNN` Number prefix mapping at the bundle level.
- NEW: `relationship/executes.schema.json` — `binding: fixed` only (no other value); `endpoints[0].revision_id` REQUIRED; opt OUT of `endpoints[].fact_ref` / `source_fact_ref`; cardinality-at-release exactly 1.
- NEW: `relationship/executed_on.schema.json` — `binding: fixed` only; `endpoints[0].revision_id` REQUIRED; opt OUT of fact-ref primitives; cardinality-at-release ≥1.
- NEW: `relationship/produces.schema.json` — `binding: fixed` only; `endpoints[0].revision_id` REQUIRED; opt OUT of fact-ref primitives; cardinality-at-release ≥0 globally with status-sensitive refinement.
- ADDITIVE: per-relationship-type `binding-must-be-fixed` constraint primitive at the trace-relationship base schema level (opt-in per relationship schema; same per-relationship-schema opt-in discipline from ADR/0021 §9). Currently opted-in by all three new types; reserved for future opt-ins via Schema Change Notes (future observation / measurement / event-recording relationships).

No existing artifacts break. All MINOR additive. The `binding-must-be-fixed` primitive is the first base-level binding-constraint primitive (parallel to ADR/0021's `endpoints[].fact_ref` / `source_fact_ref` primitives — both opt-in at the per-relationship-schema level).

**ADR ceremony** per the [amended Promotion Rule commitment 6](../TruthModelSchema.md): pattern-setting on multiple counts (ninth Object Type; first execution-instance relationship category; first Fixed-only binding posture; first per-relationship-type-cardinality-at-release rule; first status-sensitive cardinality refinement).

## Worked sidecar example

A static-load run on a drive bracket specimen, executing TST-000017 rev B against P-000058 rev B, producing EVD-000043 rev A.

```yaml
object:
  uuid: "0193abcd-ffff-7b00-aaaa-666666666666"
  type: "TestExecution"
  number: "TEX-000007"
  lifecycle: "released"
  schema_version: "0.19.0"

test_execution:
  executed_on_date: "2026-04-15"
  execution_status: "completed"
  operator_identifier: "test_engineer:emp_5839"
  instrument_identifier: "Instron 5944 SN 12345; calibration cert CAL-2026-Q1-031"
  environmental_conditions_summary: "Lab ambient 22.3°C / 38% RH; airflow stable; specimen acclimated 4h prior. No deviations from TST-000017 environmental envelope."

parameter:
  - id: "param_actual_applied_load_n"
    name: "Actual applied static load (peak)"
    value_n: 5395
    fact_provenance:
      category: "measured"
      derived_from: ["attachment:att_instron_log"]
    fact_uncertainty: "verified"
  - id: "param_actual_hold_duration_s"
    name: "Actual load hold duration"
    value_s: 605
    fact_provenance:
      category: "measured"
      derived_from: ["attachment:att_instron_log"]
    fact_uncertainty: "verified"
  - id: "param_peak_von_mises_stress_mpa"
    name: "Peak von Mises stress observed"
    value_mpa: 387
    fact_provenance:
      category: "measured"
      derived_from: ["attachment:att_instron_log"]
    fact_uncertainty: "verified"
  - id: "param_residual_deflection_mm"
    name: "Residual deflection after unload"
    value_mm: 0.04
    fact_provenance:
      category: "measured"
      derived_from: ["attachment:att_instron_log"]
    fact_uncertainty: "estimate"

attachment:
  # Canonical run record — the raw Instron output log + DAQ time-series. THIS is what makes
  # the run reconstructable as engineering truth.
  - id: "att_instron_log"
    role: "source_authoring"
    media_type: "application/octet-stream"
    vault_path: "vault:executions/TEX-000007/instron_5944_run_20260415.dat"
    content_hash: "sha256:c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5"
    fact_provenance: { category: "measured" }
    fact_uncertainty: "verified"
  # Distribution-facing PDF summary (annotated for the certification record).
  - id: "att_run_summary_pdf"
    role: "rendered_primary"
    media_type: "application/pdf"
    vault_path: "vault:executions/TEX-000007/run_summary.pdf"
    content_hash: "sha256:d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6"
    derived_from_attachment_id: "att_instron_log"
    page_count: 8
    fact_provenance: { category: "derived_for_release" }
    fact_uncertainty: "computed"
  # Photographic record of post-test specimen condition.
  - id: "att_post_test_photos"
    role: "derived_secondary"
    media_type: "image/jpeg"
    vault_path: "vault:executions/TEX-000007/post_test_photos.zip"
    content_hash: "sha256:e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7"
    derived_from_attachment_id: "att_instron_log"
    fact_provenance: { category: "human_input" }

design_intent:
  - id: "di_acceptance_basis"
    statement: "Run completed within TST-000017 rev B envelope; applied load 5395 N (target 5400 N ±0.5%); residual deflection 0.04 mm well below 0.5 mm yield indicator. Specimen acceptable for inclusion in P-000058 rev B certification record."
    anchors: ["test_execution", "param_actual_applied_load_n", "param_residual_deflection_mm"]

relationship:
  # The atomic binding: procedure rev + tested Object rev + produced evidence rev.
  - id: "rel_executes_001"
    type: "executes"
    binding: "fixed"
    endpoints:
      - object_uuid: "<tst-000017-uuid>"
        revision_id: "rev_b"
    fact_provenance: { category: "human_input" }
    fact_uncertainty: "verified"
  - id: "rel_executed_on_001"
    type: "executed_on"
    binding: "fixed"
    endpoints:
      - object_uuid: "<p-000058-uuid>"
        revision_id: "rev_b"
    fact_provenance: { category: "human_input" }
    fact_uncertainty: "verified"
  - id: "rel_produces_001"
    type: "produces"
    binding: "fixed"
    endpoints:
      - object_uuid: "<evd-000043-uuid>"
        revision_id: "rev_a"
    fact_provenance: { category: "human_input" }
    fact_uncertainty: "verified"
```

**Validation walk against this example:**

- `test_execution.execution_status == "completed"` — ✓ in enum.
- `parameter:` — four records, each with `fact_provenance.derived_from` containing `"attachment:att_instron_log"` ✓ (form matches [ADR/0019 §"Decision §4"](0019-object-type-evidence-artifact.md) line 169 `"attachment:<id>"` discipline; reference resolves to the `att_instron_log` attachment record in the same sidecar); canonical-unit field names (`_n` / `_s` / `_mpa` / `_mm`) ✓; `category: "measured"` ✓.
- `attachment:` — three records; `att_instron_log` is `source_authoring` with no `derived_from_attachment_id` (correctly absent — FORBIDDEN for source_authoring per [ADR/0017 §2 line 122](0017-object-type-drawing.md)); `att_run_summary_pdf` is `rendered_primary` with `derived_from_attachment_id: "att_instron_log"` ✓; `att_post_test_photos` is `derived_secondary` with `derived_from_attachment_id: "att_instron_log"` ✓ (lineage chain terminates at `source_authoring` per inherited [ADR/0017 §2](0017-object-type-drawing.md) discipline). Lineage chain terminates at source ✓.
- Released-state invariant: `att_instron_log` exists with `role: source_authoring` AND resolved `content_hash` ✓.
- Decision §2 specialization: `att_instron_log` is the raw instrument output (canonical run record), not a metadata stub ✓.
- `relationship:` — three records; `executes` cardinality = 1 ✓; `executed_on` cardinality ≥1 ✓; `produces` cardinality ≥0 ✓ (one record present, `completed` status SHOULD ≥1 satisfied). All three `binding: fixed` ✓. All three `endpoints[0].revision_id` present ✓. No `project_scope` ✓.

**Combined V&V execution graph** (across this example, [ADR/0020](0020-object-type-test-procedure.md)'s TST-000017, [ADR/0019](0019-object-type-evidence-artifact.md)'s EVD-000043, [ADR/0021](0021-relationship-types-v-and-v.md)'s `verifies` / `tested_against` / `cites`):

- P-000058 `tested_against` TST-000017 rev B (declarative — ADR/0021 §3 shape; coexists with the execution-instance shape below)
- TST-000017 `verifies` REQ-000058 acceptance criterion `ac_load_bearing_5400n` (ADR/0021 §2)
- **TEX-000007 `executes` TST-000017 rev B** (this ADR)
- **TEX-000007 `executed_on` P-000058 rev B** (this ADR)
- **TEX-000007 `produces` EVD-000043 rev A** (this ADR)
- REQ-000058 acceptance criterion `ac_load_bearing_5400n` `cites` EVD-000043 (ADR/0021 §4)

The full chain — *Part was tested under procedure rev B in a specific run on a specific date producing this evidence record, which satisfies an acceptance criterion of a Requirement that this procedure verifies* — is now expressible end-to-end with atomic binding.

## Consequences

- **Ninth Object Type lands.** Seed catalogue: Part, Requirement, Assembly, Component, SoftwareModule, Drawing, EvidenceArtifact, TestProcedure, **TestExecution**.
- **Fourth Attachment-bearing Object instance / third reuse of the [ADR/0017](0017-object-type-drawing.md) template** after [ADR/0019](0019-object-type-evidence-artifact.md) and [ADR/0020](0020-object-type-test-procedure.md), with a different per-Type `source_authoring` specialization (canonical record of execution event; raw instrument output / signed inspector report / automated test framework output / video log / equivalent). Template pattern continues to hold; per-Type specialization continues to be where the semantic divergence lives.
- **Three new relationship types land** in one combined ADR per ADR/0021 / ADR/0012 precedent: `executes`, `executed_on`, `produces`. Named relationship-type catalogue at fourteen (was eleven); operationally complete except `derived_geometry_from` (awaits FreeCAD Domain Adapter scope per [Manifesto P12](../Manifesto.md)) — that gap is unaffected by this ADR.
- **First execution-instance relationship category.** Pattern-setting: execution-instance relationships are Fixed-only (Float forbidden) per Decision §6. Future observation / measurement / event-recording relationships inherit this posture. New SystemState Pattern Catalogue row consolidates the four execution-instance properties into one entry per [Codex2 N3](../Discussions/20260520/20260520-1/Codex2.md).
- **First per-relationship-type-cardinality-at-release rule + status-sensitive refinement** per Decision §3 / §4 / §5 / Alternatives §I (`executes` exactly 1; `executed_on` ≥1; `produces` ≥0 globally with `completed` SHOULD ≥1 diagnostic). Recorded inside the consolidated execution-instance Pattern Catalogue row; narrow Coherence Checklist item added per Codex2 N3 acceptance.
- **V&V framework operationally executable end-to-end.** After this ADR, the chain *procedure verifies requirement → part tested against procedure → execution executes procedure on part producing evidence → requirement cites evidence* is fully wired with atomic binding. Wedge spike-implementation can now exercise full V&V instrumentation against schema with no missing pieces.
- **Resolution-by-declining-to-add: Part / Assembly → EvidenceArtifact direct edge.** [ADR/0021](0021-relationship-types-v-and-v.md) §"Pre-declared constraints honored" deferred the EvidenceArtifact-target half of `tested_against` to this ADR's test execution model; the resolution is that the direct edge is *structurally unnecessary* — multi-hop traversal via TestExecution carries the linkage with full execution-instance binding. ADR/0005 §11 / ADR/0007 §11 partial-supersession ceremony from ADR/0021 carries forward unchanged; this ADR is the resolution venue named there. `tested_against` shape from ADR/0021 §3 stays unchanged.
- **Partial supersession of [ADR/0019 §3](0019-object-type-evidence-artifact.md) `collection_context` load-bearing role.** Field remains as prose-only optional human-readable context (test stand identifier, environmental notes); load-bearing TestProcedure linkage is now structural via graph traversal `EvidenceArtifact ←produces← TestExecution →executes→ TestProcedure`. ADR/0019 §3's "structured TestProcedure citation lives in the future V&V relationship family" guardrail is now fulfilled (the V&V relationship family from ADR/0021 + the execution-instance family from this ADR jointly close it).
- **Partial supersession of [ADR/0020 §"Consequences"](0020-object-type-test-procedure.md) event sketch.** ADR/0020 sketched `test_execution_started` / `test_execution_completed` event payloads as the test execution model. This ADR replaces that sketch with first-class Object Type + Object event taxonomy (`test_execution_created` / `_changed` / `_released` / `_retired`). The "started/completed" wording was non-normative; the structural answer is the Object Type.
- **Cross-project per-type asymmetry across the trace family extends to fourteen-of-fourteen explicitly settled.** `satisfies` IN, `derived_from` / `refines` IN, `allocates_to` OUT, `depicts` OUT, `verifies` IN, `tested_against` OUT, `cites` IN, **`executes` OUT**, **`executed_on` OUT**, **`produces` OUT**. The four rationale dimensions (local-approval semantics, Binding-Object-applicability, integrity anchoring, Float-vs-Fixed meaningfulness) continue to be the framework; execution-instance relationships add a fifth implicit dimension — *event-locality* (execution events are intrinsically local).
- **Pattern Catalogue Attachment-bearing Object row Applies-to extends** from `Drawing, EvidenceArtifact, TestProcedure (future annotated-simulation candidates, etc.)` to `Drawing, EvidenceArtifact, TestProcedure, TestExecution (future annotated-simulation candidates, etc.)`.
- **New Pattern Catalogue row: execution-instance relationship category.** Declared by this ADR; applies to `executes`, `executed_on`, `produces`; future observation / measurement / event-recording relationships. Watch-out: (a) Fixed-only binding posture (Float schema-rejected); (b) `endpoints[0].revision_id` REQUIRED unconditionally; (c) cross-project opt-OUT default (event-locality dimension — execution events are intrinsically local); (d) per-relationship-type cardinality-at-release rules with status-sensitive refinement where applicable (`executes` exactly 1; `executed_on` ≥1; `produces` ≥0 globally with `completed` SHOULD ≥1 diagnostic per Decision §5); (e) no `endpoints[].fact_ref` / `source_fact_ref` (no Requirement endpoint in this category).
- **New Coherence Checklist item** per Codex2 N3: *"Execution-record cardinality invariants — for relationship categories with release-cardinality invariants (e.g., the execution-instance family from ADR/0022), are those invariants stated per relationship type and per status / lifecycle where needed?"*
- **Schema bundle bump.** Active bundle moves v0.18.0 → v0.19.0.
- **Glossary additions.** [Glossary.md](../Glossary.md) v0.23: new `TestExecution` entry; three new relationship-type entries (`executes`, `executed_on`, `produces`); small updates to `tested_against` and `cites` framing to note multi-hop alternative paths through execution model; small update to `EvidenceArtifact` entry noting `collection_context` prose-only role after execution model lands.
- **SystemState updates.** One new Pattern Catalogue row (execution-instance relationship category — consolidated per Codex2 N3); one new Coherence Checklist item (narrowly phrased per Codex2 N3); Recent Pattern Changes entry; Current Front advance (seed Object Type catalogue 8 → 9; named relationship-type catalogue 11 → 14).
- **Test-campaign aggregation deferred.** When multiple TestExecutions form a single campaign (a certification suite running 17 procedures), an aggregating Object Type (TestCampaign / VerificationActivity) is a future arc if needed. Each run is its own TestExecution; aggregation is graph-derivable for tooling.
- **Pass / fail outcome semantics still deferred** per [ADR/0019 §"Alternatives §E1"](0019-object-type-evidence-artifact.md) carry-forward. Belongs in V&V relationships (`verifies` records) when outcome framing eventually lands; outside this ADR's scope.
- **Multiple parallel `source_authoring` posture deferred** to future Schema Change Note per Alternatives §E3 — if multi-channel independent canonical captures become common (synchronized multi-instrument runs in safety-critical V&V).
- **Test execution model ADR is the natural close of Ring 1 catalogue work** for the spec-arc strand. After this arc: nine Object Types, fourteen named relationship types (operationally complete except `derived_geometry_from`), V&V framework fully wired with execution-instance atomic binding. Natural next posture-shift is into Wedge spike-implementation — basic Wedge loop is fully schema-feasible end-to-end with V&V execution instrumentation. The `derived_geometry_from` gap is unaffected; it gates on FreeCAD Domain Adapter scope per [Manifesto P12](../Manifesto.md) and not on further Ring 1 spec work.
