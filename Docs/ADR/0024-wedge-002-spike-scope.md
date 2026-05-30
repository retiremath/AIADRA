---
name: adr-0024-wedge-002-spike-scope
status: accepted
date: 2026-05-30
supersedes: none
superseded_by: none
resolves: []
---

# ADR/0024 — Wedge-002 (V&V-instrumented Wedge) spike scope, attachment handling, posture

## Status

**Accepted** — 2026-05-30. Second code-producing-direction ADR after [ADR/0023](0023-wedge-spike-scope-and-runtime.md). Pins the **scope + attachment handling + posture + repo layout + fixture strategy + execution-instance authoring discipline + deliverable shape** for the **Wedge-002 spike implementation**, without writing any spike code in this arc. The actual implementation lands in a separate follow-up arc that references ADR/0024's pinned scope.

Builds on the [ADR/0023 + arc 20260530-1](../Discussions/20260530/20260530-1/CLOSED.md) precedent: scope-first ADR → spike-writing arc → friction log → close. After [arc 20260530-1](../Discussions/20260530/20260530-1/Claude4.md), Wedge-001 is implemented end-to-end and [`spikes/wedge-001/FRICTION_LOG.md`](../../spikes/wedge-001/FRICTION_LOG.md) confirms the basic Wedge architecture survived contact with reality cleanly. ADR/0024 opens the natural follow-up per [OQ-0007](../OpenQuestions.md)'s resolved-but-build-on framing.

**Eight pinned decisions** (each is the recommended option from [Claude1](../Discussions/20260530/20260530-2/Claude1.md) / [Codex1](../Discussions/20260530/20260530-2/Codex1.md) / [Claude2 absorptions](../Discussions/20260530/20260530-2/Claude2.md) / [Codex2 signoff](../Discussions/20260530/20260530-2/Codex2.md)):

1. **Arc structure** — scope-first ADR; spike code in follow-up arc (Decision §1).
2. **Wedge-002 scope** — full V&V chain (5 Object instances + 6 V&V relationship types) per ADRs 0019 / 0020 / 0021 / 0022 (Decision §2).
3. **Execution-instance authoring discipline** — Fixed-at-authoring with upfront `--rev-id` predeclaration; Float schema-rejected per [ADR/0022 §6](0022-test-execution-model.md) (Decision §2.5).
4. **Runtime + posture** — Python 3.11+ (consistent with Wedge-001); throwaway spike per [Glossary "Spike"](../Glossary.md) (Decision §3).
5. **Attachment handling** — minimal local-FS content-addressed Vault Adapter at `outputs/vault/<sha256-hex>/bytes`; `attach-file` is workspace/Vault helper with NO canonical event (Decision §4).
6. **Fixture identities** — reuse ADR worked-example identities per [ADR/0023 §6](0023-wedge-spike-scope-and-runtime.md) spike-local discipline (Decision §5).
7. **Repo layout** — parallel `spikes/wedge-002/` (copy-and-adapt from `spikes/wedge-001/`); workspace-relative paths (Decision §6).
8. **Wedge-001 friction items** — carry all three forward unchanged; Schema Change Notes land as independent smaller arcs (Decision §7).

Plus three auxiliary decisions: **no CI for spike** (Decision §8); **CLI + checked-in fixtures + ≤2-page friction log with NEW §4 cross-spike friction comparison vs Wedge-001** (Decision §9); **explicit deferrals** carry forward (Decision §10).

**Five firsts** (each pattern-setting):

1. First V&V-instrumented spike scope.
2. First Attachment-bearing pattern landed in code (TestProcedure + EvidenceArtifact + TestExecution).
3. First execution-instance posture landed in code (Fixed-only binding + per-relationship cardinality-at-release + status-sensitive `produces` rule).
4. First spike-grade Vault Adapter (per-project local filesystem; content-addressed).
5. **First scope ADR INFORMED by a prior spike's friction log** — Wedge-001's friction log shaped Fork E (carry forward) and Decision §7; future scope ADRs in the spike series consume the prior spike's friction log as a load-bearing input.

**No schema bundle bump.** ADR/0024 is a meta-decision (scope + posture); does NOT modify any schema. Bundle stays v0.19.0 after this ADR. The Wedge-002 spike's V&V schemas implement existing ADRs (0017 / 0019 / 0020 / 0021 / 0022); no new spec is introduced.

## Context

Discussion trail in [`Docs/Discussions/20260530/20260530-2/`](../Discussions/20260530/20260530-2/). [Codex1](../Discussions/20260530/20260530-2/Codex1.md) produced three blockers + five non-blockers; all three blockers tightly scoped (TestExecution canonical field-name drift; execution-instance Float-then-materialize masquerade; implied `attachment_*` event taxonomy outside scope) and structurally addressed in [Claude2](../Discussions/20260530/20260530-2/Claude2.md); [Codex2](../Discussions/20260530/20260530-2/Codex2.md) signed off with two non-blocking polish notes (avoid brittle validation-outcome count wording; keep `.rev-id-map` explicitly spike-local). Both Codex2 non-blockers absorbed in §"Worked invocation" + Decision §2.5 wording per this ADR.

Five pressures converge on Wedge-002:

1. **The V&V framework is operationally executable against schema but has never been exercised in code.** [ADR/0019](0019-object-type-evidence-artifact.md) + [ADR/0020](0020-object-type-test-procedure.md) + [ADR/0021](0021-relationship-types-v-and-v.md) + [ADR/0022](0022-test-execution-model.md) landed 3 Object Types + 6 relationship types describing the full chain `Part →tested_against→ TestProcedure ←executes← TestExecution →produces→ EvidenceArtifact + verifies + cites`. No spike has authored a TestProcedure sidecar, run a TestExecution, produced an EvidenceArtifact, and verified the integrity chain end-to-end at release. Per OQ-0007's resolved-but-build-on framing, Wedge-002 IS the V&V-instrumented evaluation.

2. **Attachment-bearing pattern is unexercised in code.** [ADR/0017](0017-object-type-drawing.md) operationalized the Attachment-bearing template; [ADR/0019](0019-object-type-evidence-artifact.md), [ADR/0020](0020-object-type-test-procedure.md), and [ADR/0022](0022-test-execution-model.md) reused it three times. Wedge-002 lands all three reuses in code. **First chance for the Attachment-bearing template to fail in practice.**

3. **Execution-instance posture is pattern-setting and unexercised in code.** [ADR/0022 §6](0022-test-execution-model.md) declared Fixed-only binding (Float schema-rejected); `endpoints[0].revision_id` REQUIRED unconditionally; per-relationship cardinality at release (`executes` exactly 1; `executed_on` ≥1; `produces` ≥0 with status-sensitive `completed` SHOULD ≥1 diagnostic). All theoretical until a spike enforces them.

4. **Vault Adapter scope must be navigated.** [ADR/0023 §10](0023-wedge-spike-scope-and-runtime.md) explicitly deferred Vault Adapter (basic Wedge-001 had no attachments). Wedge-002 has at least three attachments (one per Attachment-bearing Object). Spike-grade boundary needs an explicit decision (Decision §4); production-grade Vault Adapter (LFS / S3 / MinIO / IPFS per [ADR/0001 §3](0001-storage-substrate.md)) stays a separate future ADR.

5. **Prior spike's friction log informs scope decisions.** First scope decision INFORMED by a prior spike's friction log. ADR/0023 was prospective ("here's what Wedge-001 should be"); ADR/0024 has [Wedge-001's evidence](../../spikes/wedge-001/FRICTION_LOG.md). Three load-bearing items become Fork E (Decision §7). Pattern-setting for future scope ADRs in the spike series.

## Pre-declared constraints honored

| Constraint | Source | Disposition |
|---|---|---|
| Wedge-002 (V&V-instrumented) is the natural next spike if Wedge-001 surfaces interesting friction | [ADR/0023 §"Alternatives §A2"](0023-wedge-spike-scope-and-runtime.md), [SystemState §1](../SystemState.md) Track A | Honored — this ADR lands Wedge-002 scope. |
| Throwaway-spike posture per Glossary "Spike" | [Glossary](../Glossary.md), [ADR/0023 §4](0023-wedge-spike-scope-and-runtime.md) | Honored — Decision §3 keeps throwaway. |
| Python 3.11+ spike-only runtime (NOT production commitment) | [ADR/0023 §3](0023-wedge-spike-scope-and-runtime.md) | Inherited — Wedge-002 uses the same Python 3.11+ posture; production runtime still NOT decided. |
| Spike-local fixture identities — Numbers are per-project per ADR/0004; reuse does NOT reserve | [ADR/0023 §6](0023-wedge-spike-scope-and-runtime.md), [ADR/0004 §6](0004-number-allocation.md) | Honored — Decision §5 reuses ADR worked-example identities. |
| AIADRA Core hosts nothing | [Manifesto P11](../Manifesto.md) | Honored — spike-grade Vault Adapter is per-project local filesystem; no AIADRA-Core-operated service. |
| Acceleration cache is derived / local / never-canonical | [ADR/0001 §3](0001-storage-substrate.md) | Honored — Wedge-002 Release Manifest does NOT pin acceleration cache state. |
| Failed-transaction audit retention deferred to Ring 2 per OQ-0003 | [OQ-0003](../OpenQuestions.md), [ADR/0023 §10](0023-wedge-spike-scope-and-runtime.md) | Honored — Wedge-002 rejected transactions still produce NO canonical artifact + NO checked-in audit-log artifact; stdout-only. |
| AIADRA YAML Profile spike-grade enforcement (normative, not optional) | [ADR/0002 §1](0002-canonical-format.md), [ADR/0023 §3](0023-wedge-spike-scope-and-runtime.md) | Inherited — Wedge-002 reuses Wedge-001's spike-grade Profile lint + force-quote dumper. Negative-fixture suite inherits 12 from Wedge-001 + extends. |
| Execution-instance Fixed-only binding + cardinality-at-release rules | [ADR/0022 §6 + §8](0022-test-execution-model.md) | Honored — Decision §2 + Decision §2.5 require Fixed-at-authoring + cardinality enforcement. |
| TestExecution canonical field names (`execution_status` / `executed_on_date` / `operator_identifier` + optional `instrument_identifier` / `environmental_conditions_summary`) | [ADR/0022 §9 lines 360-367](0022-test-execution-model.md) | Honored — Decision §2 pins canonical names; Decision §2 CLI flag mapping table makes the artifact-shape vs CLI-flag distinction explicit. Per [Codex1 B1 absorption](../Discussions/20260530/20260530-2/Codex1.md). |
| Per-relationship-schema opt-in for criterion-level addressing | [ADR/0021 §6 + §9](0021-relationship-types-v-and-v.md) | Honored — `relationship_verifies.schema.json` opts IN target-side `endpoints[].fact_ref`; `relationship_cites.schema.json` opts IN source-side `source_fact_ref`; `tested_against` and the three execution-instance relationships do NOT opt in. Criterion-level opt-in lives in relationship schemas, NOT Requirement schema (per [Codex1 N4 absorption](../Discussions/20260530/20260530-2/Codex1.md)). |
| Verification-method consistency = tooling-aided diagnostic, NOT schema-enforced | [ADR/0021 §7](0021-relationship-types-v-and-v.md) | Honored — spike emits warning to stdout if `TestProcedure.verification_method ≠ Requirement.default_verification_method` (or per-criterion `verification_method`), but does NOT fail validation. |
| Attachment-bearing template (`source_authoring` REQUIRED at release; `derived_from_attachment_id` lineage; algorithm-qualified `content_hash` authority; `vault_path` non-authoritative locator hint) | [ADR/0017 §2 + §8](0017-object-type-drawing.md) | Honored — Decision §4 implements the template at spike grade with content-addressed local-FS Vault. Three Attachment-bearing instances exercised. |
| Per-Type specialization of `source_authoring` semantic | [ADR/0019 §4](0019-object-type-evidence-artifact.md), [ADR/0020 §4](0020-object-type-test-procedure.md), [ADR/0022 §2](0022-test-execution-model.md) | Honored — TestProcedure attachment = canonical procedure document; EvidenceArtifact = canonical evidence payload; TestExecution = canonical record of execution event. Metadata-only stubs forbidden; spike fixtures MUST be semantically inspectable per [Codex1 N2 absorption](../Discussions/20260530/20260530-2/Codex1.md). |
| Parameter lineage discipline (EvidenceArtifact + TestExecution parameters carry `fact_provenance.derived_from: ["attachment:<id>"]` lineage) | [ADR/0019 §4 line 169 + §8](0019-object-type-evidence-artifact.md), [ADR/0022 §"Pre-declared constraints honored"](0022-test-execution-model.md) | Honored — Decision §4 requires the spike to emit + validate the lineage chain (parameter → derived_from → attachment → content_hash → vault bytes). TestProcedure parameters are nominal design facts (no `derived_from` discipline; matches ADR/0020 §4). |
| No standalone `attachment_*` event family | [ADR/0017](0017-object-type-drawing.md), [ADR/0019 §"Eventability"](0019-object-type-evidence-artifact.md) | Honored — `event.schema.json` carries V&V Object event types ONLY; `attach-file` is workspace/Vault helper with NO canonical event; attachment records become Product Truth only inside Object-creation event payloads. Per [Codex1 B3 absorption](../Discussions/20260530/20260530-2/Codex1.md). |
| Manifest authority model unchanged from Wedge-001 | [Wedge-001 manifest shape per ADR/0023 §2](0023-wedge-spike-scope-and-runtime.md) | Honored — manifest pins Revision hashes + validation outcomes + event-log boundary; attachment content_hashes are TRANSITIVELY pinned via Revision content (Revision body contains `attachment:` records). `attachment_integrity(att_*)` checks land as validation_outcomes entries, NOT a new top-level manifest section. Per [Codex1 N3 absorption](../Discussions/20260530/20260530-2/Codex1.md). |

## Alternatives Considered

### A. Wedge-002 scope (load-bearing)

**A1. Full V&V chain — all 5 Object instances + all 6 relationship types end-to-end.** *Chosen — Decision §2.*

> Exercises the complete V&V framework: Part + Requirement carry over from Wedge-001 (no new shapes); TestProcedure introduces the Attachment-bearing template in code; EvidenceArtifact introduces parameter-lineage-to-attachment discipline; TestExecution introduces execution-instance posture (Fixed-only + status-sensitive cardinality). All 6 V&V relationships exercised. Smallest scope that validates the V&V framework as a coherent whole; smaller subsets either skip an Object Type or skip a relationship. [Codex1 N1](../Discussions/20260530/20260530-2/Codex1.md): *"Wedge-002 is methodology-sized precisely because all three are coupled in the V&V chain."*

**A2. Minimal V&V subset — Part + TestProcedure + EvidenceArtifact + `tested_against` + `cites`; skip TestExecution + Requirement-target verifies + execution-instance posture.**

> **Rejected.** Skips TestExecution (execution-instance posture stays untested in code); skips `verifies` (V&V triad's central anchor stays untested); chain `Part tested_against TestProcedure ←produces← TestExecution →EvidenceArtifact ←cites← Requirement` collapses to `Part tested_against TestProcedure → EvidenceArtifact ← cites Requirement` which loses execution-time atomic binding that [ADR/0022](0022-test-execution-model.md) was specifically introduced to provide.

**A3. Delta-only — extend Wedge-001 in-place with just `tested_against` + TestProcedure; defer the rest to Wedge-003.**

> **Rejected.** Too small to be methodology arc; chain still doesn't close; friction log wouldn't surface anything beyond Wedge-001.

**A4. Maximum — full V&V chain PLUS Component / SoftwareModule / Drawing.**

> **Rejected.** Five more Object Types adds substantial schema surface for marginal additional learning. Component / SoftwareModule are External pointer Objects (different pattern); Drawing's `depicts` is the load-bearing test. Defer to Wedge-003+.

### B. Attachment handling at spike grade (load-bearing)

**B1. Minimal local-filesystem content-addressed Vault Adapter.** *Chosen — Decision §4.*

> Spike stores attachment bytes under `outputs/vault/<sha256-hex>/bytes` (content-addressed). `attach-file` CLI subcommand computes SHA-256 over file bytes; copies to content-addressed location; returns `(content_hash, vault_path)` for the sidecar to record. Idempotent — re-attaching same bytes reuses same location. Makes the integrity claim TRUE without fakery. [Codex1 N2](../Discussions/20260530/20260530-2/Codex1.md): *"Local-FS Vault is the right spike-grade boundary."* Production Vault Adapter (LFS / S3 / etc.) remains separate future ADR informed by Wedge-002 friction.

**B2. Placeholder content_hash (`sha256:0000...`).**

> **Rejected.** Breaks integrity claim. The Manifest can't honestly pin a Revision whose embedded `attachment.content_hash` is fake; the deeper claim — "content_hash is authority for attachment bytes" per [ADR/0017](0017-object-type-drawing.md) — becomes a lie at spike grade. Wrong shape for a V&V spike whose central job is integrity claims. [Codex1](../Discussions/20260530/20260530-2/Codex1.md): *"placeholder hashes are too dishonest for an integrity spike."*

**B3. Defer attachments entirely — sidecars with REQUIRED fields except `content_hash` ("deferred").**

> **Rejected.** Breaks [ADR/0017 §"C2"](0017-object-type-drawing.md)'s structural decision (`content_hash` unconditionally required on every committed `attachment:` record). Re-introducing the contradiction at spike grade would invalidate the schema set against ADR/0017.

**B4. Maximal — S3-protocol Vault Adapter with MinIO local at spike grade.**

> **Rejected.** Premature; couples spike to a specific production-grade adapter; obscures throwaway posture.

### C. Posture — throwaway vs production-graduation (load-bearing)

**C1. Throwaway spike.** *Chosen — Decision §3.*

> Per [Glossary "Spike"](../Glossary.md). Wedge-002 is throwaway per the same logic as Wedge-001. Combined Wedge-001 + Wedge-002 friction logs inform the future production-grade `aiadra-core` runtime ADR; jumping to production-grade now would mix spike-grade discovery with production-grade design. [Codex1](../Discussions/20260530/20260530-2/Codex1.md): *"Two friction logs before `aiadra-core` is a good evidence threshold."*

**C2. Production-grade graduation — Wedge-001 friction is enough to start `aiadra-core`.**

> **Rejected for this arc.** Wedge-002 will surface Attachment-bearing-pattern friction + execution-instance posture friction + Vault Adapter spike-grade friction; graduating now commits to design decisions without that evidence.

**C3. Hybrid — spike-velocity but in production location.**

> **Rejected.** Same anti-pattern as Wedge-001 (rejected in [ADR/0023 §"Alternatives §C3"](0023-wedge-spike-scope-and-runtime.md)).

### D. Repo layout (load-bearing)

**D1. Parallel `spikes/wedge-002/` (copy-and-adapt from `spikes/wedge-001/`).** *Chosen — Decision §6.*

> Standalone Python package at `spikes/wedge-002/wedge/`. Copies Wedge-001 machinery wholesale; adapts schemas + adds `vault.py` + extends CLI. Keeps per-spike throwaway posture clean; friction logs comparable apples-to-apples; mirrors [ADR/0023 §5](0023-wedge-spike-scope-and-runtime.md) `spikes/` layout discipline.

**D2. Extend `spikes/wedge-001/` in place with v2-branch.**

> **Rejected.** Conflates two spikes' friction in one tree; breaks Wedge-001's reproducibility; friction logs can't be compared.

**D3. Hybrid — shared `spikes/_core/` library + per-spike CLI + schemas.**

> **Rejected.** Premature factoring of throwaway shared bits; cross-spike coupling at v2 stage. [Codex1](../Discussions/20260530/20260530-2/Codex1.md): *"Shared `_core` would prematurely harden throwaway code."*

### E. Wedge-001 friction items — address now or carry forward? (load-bearing — first scope decision informed by prior spike's friction log)

[Wedge-001 FRICTION_LOG.md §2](../../spikes/wedge-001/FRICTION_LOG.md) surfaces three load-bearing items:

- **F1**: `parameter_changed` event payload cannot derive `fact_provenance` mutation.
- **F2**: Acceptance-criterion threshold-expression has no canonical primitive.
- **F3**: Cross-artifact atomicity gap.

**E1. Carry forward all three into Wedge-002 unchanged.** *Chosen — Decision §7.*

> Wedge-002 inherits Wedge-001's spike-grade workarounds. Friction log §3 / §4 / §5 already document; Wedge-002 friction log adds any new occurrences in its §4 (cross-spike friction comparison). Schema Change Notes land as independent smaller arcs. Wedge-002 surface is substantial (3 new Object Types + 6 new relationships + Attachment-bearing pattern + Vault Adapter); adding Schema Change Note scope dilutes focus.

**E2. Address F1 (`parameter_changed` event payload) NOW via inline Schema Change Note.**

> **Rejected.** Inline Schema Change Note bundles scope into methodology arc; complicates convergence; Schema Change Note benefits from focused arc.

**E3. Address all three now.**

> **Rejected.** Triples change surface; methodology arc already has 5 load-bearing forks.

### F. Execution-instance authoring discipline (load-bearing — Codex1 B2)

**F1. Upfront `--rev-id` predeclaration; Fixed-at-authoring.** *Chosen — Decision §2.5.*

> `init` accepts repeated `--rev-id <obj-uuid>=<rev-uuid>` for all future Revision ids. Link commands (`link-executes`, `link-executed-on`, `link-produces`) author `binding: fixed` + `endpoints[0].revision_id` set to predeclared rev_id at authoring time. Release allocates predeclared rev_ids exactly. Preserves single-release demo rhythm per [Codex1 B2 (Option 1)](../Discussions/20260530/20260530-2/Codex1.md).

**F2. Staged releases — release prerequisites first, then author execution-instance relationships against existing Revisions, then release TestExecution.**

> **Rejected for this spike.** More semantically faithful to real V&V cadence but breaks single-release demo rhythm; requires multiple release commands (rev-A design, rev-A-evd evidence, rev-A-tex execution); friction-log analysis becomes harder. Production-grade ADR may revisit.

**F3. Non-canonical "pending execution relationship" Transaction preview.**

> **Rejected.** Introduces new lifecycle state (pending) outside ADR/0022; complicates spike for marginal gain. Stays as production-grade option for `aiadra-core` runtime ADR.

### G. Workspace path convention

**G1. `--workspace <dir>`-relative paths.** *Chosen — Decision §6.*

> Workspace-relative is cleaner for spike-as-standalone-tree. Resolves [Wedge-001 FRICTION_LOG.md §2 workspace path divergence](../../spikes/wedge-001/FRICTION_LOG.md).

**G2. AIADRA-repo-layout-mirroring paths (`Docs/Reservations/` etc.).**

> **Rejected for spike.** Forces spike to emulate AIADRA repo layout inside its own tree; confusing.

## Decision

### 1. Arc-structure: scope-first ADR; spike code lands in follow-up arc

**This arc (20260530-2) lands ADR/0024.** No spike code is written in this arc. The follow-up arc (proposed `20260530-3` or later) references ADR/0024's pinned scope and writes the Wedge-002 spike. Matches [AIADRA working style](../../../.claude/projects/d--VSCode-Work/memory/aiadra_working_style.md) (*discuss → plan → architect → code*) AND mirrors the proven [ADR/0023 + 20260530-1](../Discussions/20260530/20260530-1/CLOSED.md) rhythm.

### 2. Wedge-002 scope: full V&V chain (3 new Object Types + 6 new relationship types)

Wedge-002 implements the full V&V chain end-to-end.

**Object instances (5 total — Part + Requirement carry forward from Wedge-001 with no new schema):**

- **Part** `P-000058` (drive bracket, reused from Wedge-001) — 1 parameter `plate_thickness_mm`; spike-local demo record per [ADR/0023 §6](0023-wedge-spike-scope-and-runtime.md).
- **Requirement** `REQ-000058` (drive bracket minimum thickness, reused) — 1 acceptance criterion `ac_min_thickness`; spike-local.
- **TestProcedure** `TST-000017` (drive bracket plate thickness test per [ADR/0020 worked example](0020-object-type-test-procedure.md)) — first Attachment-bearing instance in code; `source_authoring` attachment = canonical procedure document (per [ADR/0020 §4](0020-object-type-test-procedure.md)); `test_procedure:` singleton with `title` + `verification_method`; 0 parameters in seed (nominal design facts; no `derived_from` discipline per [ADR/0020 §4](0020-object-type-test-procedure.md) divergence from EvidenceArtifact / TestExecution).
- **TestExecution** `TEX-000007` (one run of TST-000017 on P-000058 per [ADR/0022 worked example](0022-test-execution-model.md)) — first execution-instance Object Type in code; `source_authoring` attachment = canonical record of execution event; `test_execution:` singleton with **canonical field names per [ADR/0022 §9](0022-test-execution-model.md)**:
  - `executed_on_date` (REQUIRED, ISO 8601 *date*, e.g., `"2026-04-15"`, not a timestamp)
  - `execution_status` (REQUIRED enum: `completed` | `aborted` | `inconclusive`; spike-demo uses `completed`)
  - `operator_identifier` (OPTIONAL, free-form per [ADR/0022 §9 line 379](0022-test-execution-model.md))
  - `instrument_identifier`, `environmental_conditions_summary` OPTIONAL
  
  Plus 1 parameter `measured_thickness_mm` with `fact_provenance.derived_from: ["attachment:att_instron_log"]` per [ADR/0019 §4](0019-object-type-evidence-artifact.md) + [ADR/0022 §"Pre-declared constraints honored"](0022-test-execution-model.md).
- **EvidenceArtifact** `EVD-000043` (drive bracket plate thickness measurement per [ADR/0019 worked example](0019-object-type-evidence-artifact.md)) — second Attachment-bearing instance in code; `source_authoring` attachment = canonical evidence payload; `evidence:` singleton with `summary` + `evidence_kind: "measurement"`; 1 parameter `reported_thickness_mm` with `fact_provenance.derived_from: ["attachment:att_measurement_data"]` per [ADR/0019 §4](0019-object-type-evidence-artifact.md).

**CLI-to-sidecar field mapping** (explicit per [Codex1 B1 absorption](../Discussions/20260530/20260530-2/Codex1.md)):

| CLI flag | Sidecar field |
|---|---|
| `--execution-status <enum>` | `test_execution.execution_status` |
| `--executed-on-date <YYYY-MM-DD>` | `test_execution.executed_on_date` |
| `--operator-identifier <string>` | `test_execution.operator_identifier` |
| `--instrument-identifier <string>` | `test_execution.instrument_identifier` |
| `--environmental-conditions <prose>` | `test_execution.environmental_conditions_summary` |

CLI flag names are user-friendly hyphenated; sidecar fields are canonical snake_case per [ADR/0022 §9](0022-test-execution-model.md). **The cardinality status check (per [ADR/0022 §8](0022-test-execution-model.md) status-sensitive `produces` rule) keys off `test_execution.execution_status`, never the CLI flag.**

**Relationship instances (6 total — all new vs Wedge-001):**

- **`tested_against`** (P-000058 → TST-000017) — source-anchored on Part; Float default per [ADR/0009](0009-relationship-type-satisfies.md); Fixed at release.
- **`verifies`** (TST-000017 → REQ-000058) — source-anchored on TestProcedure; criterion-level addressing via `endpoints[].fact_ref: "acceptance_criterion:ac_min_thickness"` per [ADR/0021 §6](0021-relationship-types-v-and-v.md).
- **`executes`** (TEX-000007 → TST-000017) — source-anchored on TestExecution; **Fixed-only at authoring** per Decision §2.5; `endpoints[0].revision_id` REQUIRED.
- **`executed_on`** (TEX-000007 → P-000058) — source-anchored on TestExecution; **Fixed-only at authoring** per Decision §2.5.
- **`produces`** (TEX-000007 → EVD-000043) — source-anchored on TestExecution; **Fixed-only at authoring** per Decision §2.5; `execution_status: "completed"` SHOULD have ≥1 `produces` per [ADR/0022 §8](0022-test-execution-model.md); Wedge-002 emits exactly 1.
- **`cites`** (REQ-000058 → EVD-000043) — source-anchored on Requirement; criterion-level addressing via `source_fact_ref: "acceptance_criterion:ac_min_thickness"` per [ADR/0021 §6](0021-relationship-types-v-and-v.md).

**Criterion-level opt-in** lives in `relationship_verifies.schema.json` (target-side `endpoints[].fact_ref`) and `relationship_cites.schema.json` (source-side `source_fact_ref`), NOT in Requirement schema (per [Codex1 N4 absorption](../Discussions/20260530/20260530-2/Codex1.md)). Wedge-001's Requirement schema already exposes `acceptance_criterion` ids; no Requirement schema change needed. Wedge-002 Layer-2 validator resolves any `fact_ref` / `source_fact_ref` against the resolved Requirement Revision's `acceptance_criterion:<id>` namespace; dangling references hard-fail at release per [ADR/0021 §6](0021-relationship-types-v-and-v.md).

**Explicit non-scope:** no Assembly; no Component / SoftwareModule / Drawing; no `composed_of` / `mated_to` / `parameter_expression` / `depicts`; no cross-project; no Domain Engine.

### 2.5. Execution-instance relationship authoring discipline

Execution-instance relationships (`executes` / `executed_on` / `produces`) **MUST be authored with `binding: fixed` + `endpoints[0].revision_id` pinned at the moment of authoring**, never as Float-then-release-materialized. Per [ADR/0022 §6](0022-test-execution-model.md): Float is schema-rejected; `endpoints[0].revision_id` is REQUIRED unconditionally.

**Spike-grade discipline: upfront `--rev-id` predeclaration.** The `run_demo.sh` invocation predeclares the future Revision ids of all five Objects via repeated `--rev-id <obj-uuid>=<rev-uuid>` flags BEFORE any execution-instance relationship is authored. The `link-executes`, `link-executed-on`, `link-produces` CLI commands consult the predeclared map and write `binding: fixed` + `endpoints[0].revision_id` set to the predeclared rev_id at authoring time. The single `release` command later allocates exactly the predeclared rev_ids to the released Revisions; if any predeclared rev_id isn't ultimately used (Object not included in release), the release transaction hard-fails.

**`.rev-id-map` (spike-local helper).** If the spike persists the predeclared map between commands as a file at `outputs/.rev-id-map` (or equivalent), it MUST be marked **spike-local non-canonical** in code + documentation. This file is an authoring convenience supporting Fixed-relationship authoring before target Revision files exist; it is NOT Product Truth; it does NOT get pinned by the manifest; it MAY be checked into `outputs/` for demo reproducibility but the friction log should explicitly call it out as a spike helper, not part of the authority model. Per [Codex2 N2 absorption](../Discussions/20260530/20260530-2/Codex2.md).

**Validation behavior at authoring:**
- Schema validation passes (relationship record is well-formed: Fixed binding + revision_id present).
- Endpoint resolution against the target Revision file is **deferred to release** (Revision file doesn't exist yet at authoring).
- Release transaction verifies each `executes` / `executed_on` / `produces` endpoint `revision_id` matches a Revision file created in the same release transaction.

**Friction-log direction for production-grade:** spike-grade upfront `--rev-id` predeclaration is unrealistic in production (users don't know rev_ids upfront). Production-grade likely uses one of:
- staged releases (release prerequisites first, then author execution-instance relationships against existing Revisions, then release TestExecution);
- transaction-preview mechanism that allocates rev_ids when commit boundary is reached and rewrites in-flight relationships before commit;
- a "deferred-Fixed" intermediate state explicitly distinct from Float.

Wedge-002 friction log captures this gap; the production-grade `aiadra-core` runtime ADR resolves it.

### 3. Runtime + posture: Python 3.11+ (consistent with Wedge-001); throwaway

Spike uses Python 3.11+ per [ADR/0023 §3](0023-wedge-spike-scope-and-runtime.md). Dependencies identical to Wedge-001 (`ruamel.yaml >=0.18,<0.19`; `jsonschema >=4.0,<5.0`; `argparse` stdlib). **Production runtime still NOT decided.**

Throwaway posture per [Glossary "Spike"](../Glossary.md). Primary deliverable is `spikes/wedge-002/FRICTION_LOG.md`; secondary is runnable CLI + checked-in fixtures + checked-in outputs.

### 4. Attachment handling: minimal local-FS content-addressed Vault Adapter

Spike implements a minimal local-FS Vault Adapter at `spikes/wedge-002/wedge/vault.py`:

- **Content-addressed storage layout:** `outputs/vault/<sha256-hex>/bytes`.
- **`attach-file` CLI subcommand:** takes a local file path; reads bytes; computes SHA-256; copies to content-addressed location; returns `(content_hash, vault_path)` for the sidecar to record. Idempotent.
- **Sidecar attachment record:** carries `content_hash: "sha256:<hex>"` (algorithm-qualified per [ADR/0016](0016-object-type-software-module.md) convention) + `vault_path: "vault/<sha256-hex>"` (non-authoritative locator hint per [ADR/0017 §2](0017-object-type-drawing.md)) + `role: "source_authoring"` (or `rendered_primary` / `derived_secondary` for derived) + `derived_from_attachment_id: "att_<id>"` for derived roles.
- **`attach-file` is a workspace/Vault helper, NOT a canonical-event trigger.** Per [Codex1 B3 absorption](../Discussions/20260530/20260530-2/Codex1.md): copying attachment bytes into Vault does NOT emit any canonical event. The attachment becomes Product Truth only when a subsequent `create-test-procedure` / `create-evidence-artifact` / `create-test-execution` (or post-creation `<object_type>_changed`) command commits a sidecar carrying an `attachment:` record. The Object-creation event's `initial_sidecar` payload (carry-forward from Wedge-001) contains the attachment record; no separate `attachment_created` event exists.
- **Per-Type specialization** per [ADR/0019 §4](0019-object-type-evidence-artifact.md) + [ADR/0020 §4](0020-object-type-test-procedure.md) + [ADR/0022 §2](0022-test-execution-model.md):
  - TestProcedure `source_authoring` = canonical procedure document. Spike fixture `procedure_TST-000017.txt`.
  - EvidenceArtifact `source_authoring` = canonical evidence payload. Spike fixture `measurement_EVD-000043.csv`.
  - TestExecution `source_authoring` = canonical record of execution event. Spike fixture `instron_log_TEX-000007.txt`.
- **Fixture payloads MUST be semantically inspectable** per [Codex1 N2 absorption](../Discussions/20260530/20260530-2/Codex1.md). One-line placeholder content is forbidden:
  - `procedure_TST-000017.txt` — ≥10 lines describing an actual test method.
  - `measurement_EVD-000043.csv` — CSV with header row + ≥3 data rows; the spike-reported `reported_thickness_mm` value MUST appear in the file.
  - `instron_log_TEX-000007.txt` — ≥5 lines including measured value + date matching `executed_on_date` + operator matching `operator_identifier` + instrument reading.
- **Parameter lineage discipline** per [ADR/0019 §4](0019-object-type-evidence-artifact.md) + [ADR/0022 §"Pre-declared constraints honored"](0022-test-execution-model.md): EvidenceArtifact + TestExecution parameter records carry `fact_provenance.derived_from: ["attachment:<id>"]` referring to their `source_authoring` attachment. Spike validates the lineage chain at release time.
- **Release-time integrity check:** spike re-reads each attachment from Vault, re-computes SHA-256, verifies match against the sidecar's `content_hash` (analogous to Wedge-001's `verify_revision_hashes`).
- **Manifest authority model unchanged from Wedge-001** per [Codex1 N3 absorption](../Discussions/20260530/20260530-2/Codex1.md). Manifest pins **Revision hashes + validation outcomes + event-log boundary**. **Attachment content_hashes are TRANSITIVELY pinned via Revision content** (Revision body contains `attachment:` records carrying `content_hash`). `attachment_integrity(att_*)` checks land as **validation_outcomes entries**, NOT a new top-level manifest section. Wedge-002 manifest shape is byte-compatible with Wedge-001 manifest shape.
- **Production Vault Adapter (LFS / S3 / MinIO / IPFS per [ADR/0001 §3](0001-storage-substrate.md) menu)** remains separate future ADR per [ADR/0023 §10](0023-wedge-spike-scope-and-runtime.md).

### 5. Fixture identities — reuse ADR worked-example identities

Per [ADR/0023 §6](0023-wedge-spike-scope-and-runtime.md) spike-local discipline:

- `P-000058` UUID `0193abcd-1234-7890-abcd-111111111111` (carried from Wedge-001).
- `REQ-000058` UUID `0193abcd-1234-7890-abcd-222222222222` (carried from Wedge-001).
- `TST-000017` UUID `0193abcd-1234-7890-abcd-555555555555` (TestProcedure worked example from [ADR/0020](0020-object-type-test-procedure.md)).
- `TEX-000007` UUID `0193abcd-1234-7890-abcd-666666666666` (TestExecution worked example from [ADR/0022](0022-test-execution-model.md)).
- `EVD-000043` UUID `0193abcd-1234-7890-abcd-777777777777` (EvidenceArtifact worked example from [ADR/0019](0019-object-type-evidence-artifact.md)).

Numbers are per-project namespaces per [ADR/0004 §6](0004-number-allocation.md). Reused identities are **spike-local demo records**, NOT reservations against future real project data.

### 6. Repo layout: `spikes/wedge-002/` parallel to `spikes/wedge-001/`

```
spikes/wedge-002/
├── README.md
├── pyproject.toml
├── run_demo.sh
├── test_profile_negative.py               # inherits Wedge-001 negative fixtures + extends
├── FRICTION_LOG.md                        # PRIMARY DELIVERABLE
├── wedge/
│   ├── __init__.py                        # __version__ = "0.0.1"; SCHEMA_BUNDLE_VERSION = "0.19.0"
│   ├── __main__.py
│   ├── cli.py                             # 6 existing commands + V&V additions
│   ├── sidecar.py                         # carried from wedge-001
│   ├── event_log.py                       # carried from wedge-001
│   ├── manifest.py                        # carried from wedge-001
│   ├── transaction.py                     # carried + extended for V&V Object creates + attachment writes
│   ├── validate.py                        # carried + extended for V&V satisfies + attachment integrity check
│   ├── vault.py                           # NEW — content-addressed local-FS Vault per Decision §4
│   └── schemas/
│       ├── _bundle_v0.19.0.json           # extended with TestProcedure / TestExecution / EvidenceArtifact + 6 V&V relationship entries
│       ├── object_part.schema.json        # carried from wedge-001 (NO changes)
│       ├── object_requirement.schema.json # carried from wedge-001 (NO opt-in additions; acceptance_criterion ids already present)
│       ├── object_test_procedure.schema.json    # NEW
│       ├── object_test_execution.schema.json    # NEW
│       ├── object_evidence_artifact.schema.json # NEW
│       ├── relationship_satisfies.schema.json   # carried from wedge-001
│       ├── relationship_tested_against.schema.json # NEW
│       ├── relationship_verifies.schema.json    # NEW (target-side endpoints[].fact_ref opt-in per ADR/0021 §6)
│       ├── relationship_cites.schema.json       # NEW (source-side source_fact_ref opt-in per ADR/0021 §6)
│       ├── relationship_executes.schema.json    # NEW (Fixed-only per ADR/0022 §6)
│       ├── relationship_executed_on.schema.json # NEW (Fixed-only)
│       ├── relationship_produces.schema.json    # NEW (Fixed-only)
│       ├── event.schema.json              # carried + extended for V&V Object event types ONLY — no attachment_* event family per Codex1 B3
│       ├── manifest.schema.json           # carried from wedge-001 (manifest authority model unchanged)
│       ├── reservation_P.schema.json      # carried from wedge-001
│       ├── reservation_REQ.schema.json    # carried from wedge-001
│       ├── reservation_TST.schema.json    # NEW (TST- prefix per ADR/0020 §2)
│       ├── reservation_TEX.schema.json    # NEW (TEX- prefix per ADR/0022 §1)
│       └── reservation_EVD.schema.json    # NEW (EVD- prefix per ADR/0019 §2)
├── fixtures/
│   ├── profile_negative/                  # inherits all 12 from wedge-001
│   ├── procedure_TST-000017.txt           # semantically inspectable per Codex1 N2
│   ├── measurement_EVD-000043.csv         # semantically inspectable per Codex1 N2
│   └── instron_log_TEX-000007.txt         # semantically inspectable per Codex1 N2
└── outputs/                               # spike-produced (checked in)
    ├── Reservations/{P,REQ,TST,TEX,EVD}.yaml
    ├── events.jsonl
    ├── revisions/<uuid>/{working,<rev_id>}.yaml  # 5 directories
    ├── Releases/rev-A/manifest.json
    ├── vault/<sha256-hex>/bytes           # 3 attachments at minimum
    └── .rev-id-map                        # spike-local non-canonical (per Codex2 N2)
```

`spikes/wedge-002/` is NOT git-ignored. `.venv/` inside it IS git-ignored. Workspace-relative paths per Decision G1.

### 7. Wedge-001 friction items: carry forward unchanged

Three Wedge-001 friction items carry forward to Wedge-002 unchanged:

- **F1 `parameter_changed` event payload + `fact_provenance` mutation:** spike does NOT mutate `fact_provenance` on `parameter_changed`. TestExecution parameter authoring uses initial `fact_provenance.category: "ai_proposal"` (AI Action Protocol surface) or `"human_input"` (hand-authored). Friction log notes Wedge-002 also hits this.
- **F2 acceptance-criterion threshold-expression:** spike continues regex-parse `"<param> shall be at least <value>"` for `verifies` check. Same convention as Wedge-001's `satisfies` check.
- **F3 cross-artifact atomicity:** spike continues per-artifact temp-file-then-rename + fold-detection. Wedge-002 has more cross-artifact writes per Transaction (5 Revisions + 5 release events + 1 manifest + 3 attachment integrity checks); friction log captures whether the gap manifests at larger scale.

Schema Change Notes for F1 / F2 / F3 land as independent smaller arcs.

### 8. CI / packaging: none

No CI for Wedge-002 (consistent with [ADR/0023 §7](0023-wedge-spike-scope-and-runtime.md)). Spike runs locally only.

### 9. Deliverable shape: CLI + checked-in fixtures + friction log

Three artifacts:

1. **Runnable Python CLI** at `spikes/wedge-002/wedge/`.
2. **Checked-in input/output fixtures** at `spikes/wedge-002/fixtures/` and `spikes/wedge-002/outputs/`.
3. **Friction log** at `spikes/wedge-002/FRICTION_LOG.md` — Markdown, ≤2 pages, structured: (a) assumptions validated; (b) friction encountered with ADR / spec reference + severity; (c) proposed clarifications / corrections / Schema Change Notes; **(d) NEW: comparison vs Wedge-001 friction log — which items recurred (with workaround propagation note), which are V&V-specific.**

The friction log is the PRIMARY deliverable.

### 10. Explicit deferrals (out of Wedge-002 scope)

- **Assembly + `composed_of` + `mated_to` + `parameter_expression` + `depicts`** — orthogonal to V&V; future Wedge-003+.
- **Component + SoftwareModule + Drawing** — External pointer / different-Attachment-bearing-instance patterns; future spikes.
- **Cross-project** — separate later spike; needs two-project test bed.
- **Domain Engine (FreeCAD Adapter)** — Ring 3 / Ring 4; out of Wedge spike series.
- **Production-grade `aiadra-core` runtime + repo layout + posture** — separate future arc after Wedge-002 friction is logged.
- **Production-grade Vault Adapter** — separate future arc; informed by Wedge-002 friction with spike-grade local-FS Vault.
- **Schema Change Notes for FRICTION_LOG.md F1 / F2 / F3** — independent smaller arcs.
- **Acceleration cache** — out of Wedge-002.
- **Schema bundle migrators** — out of Wedge-002.
- **Failed-transaction audit retention per OQ-0003** — still deferred-to-ring-2.
- **Multiple parallel `source_authoring` attachments on a single Attachment-bearing Object** — deferred per [ADR/0022 §"Alternatives §E3"](0022-test-execution-model.md).
- **TestProcedure-as-source for `cites`** — deferred per [ADR/0022 §"Decision §10"](0022-test-execution-model.md).
- **Coverage / verification_state / evidence_ref aggregation properties** — deferred per [ADR/0022 §"Decision §10"](0022-test-execution-model.md).
- **Pass / fail outcome semantics on V&V relationships** — deferred per [ADR/0019 §"Alternatives §E1"](0019-object-type-evidence-artifact.md) carry-forward.
- **Test-campaign aggregation (TestCampaign Object Type)** — deferred per [ADR/0022 §"Decision §10"](0022-test-execution-model.md).

## Worked invocation (target spike behavior, not implementation)

Mirrors [ADR/0023 §"Worked invocation"](0023-wedge-spike-scope-and-runtime.md) format. Not normative; spike-writing arc may adjust subcommand surface.

```bash
# Init AND predeclare all 5 future Revision ids upfront (spike-grade discipline per Decision §2.5)
$ python -m wedge --workspace outputs init --project-id "wedge-002-demo" \
    --rev-id 0193abcd-1234-7890-abcd-111111111111=<part-rev-uuid> \
    --rev-id 0193abcd-1234-7890-abcd-222222222222=<req-rev-uuid> \
    --rev-id 0193abcd-1234-7890-abcd-555555555555=<tst-rev-uuid> \
    --rev-id 0193abcd-1234-7890-abcd-666666666666=<tex-rev-uuid> \
    --rev-id 0193abcd-1234-7890-abcd-777777777777=<evd-rev-uuid>
✓ Workspace initialized; 5 future Revision ids predeclared in .rev-id-map (spike-local non-canonical)

# Author Part + Requirement
$ python -m wedge --workspace outputs create-part \
    --number P-000058 --name "Drive bracket" --parameter plate_thickness_mm=7 \
    --uuid 0193abcd-1234-7890-abcd-111111111111
$ python -m wedge --workspace outputs create-requirement \
    --number REQ-000058 --name "Drive bracket minimum thickness" \
    --statement "Drive bracket plate thickness shall be at least 5 mm." \
    --acceptance-criterion "ac_min_thickness:plate_thickness_mm>=5" \
    --uuid 0193abcd-1234-7890-abcd-222222222222

# Author TestProcedure with semantically inspectable attachment
$ python -m wedge --workspace outputs attach-file \
    --file ../fixtures/procedure_TST-000017.txt --role source_authoring --id att_procedure
$ python -m wedge --workspace outputs create-test-procedure \
    --number TST-000017 --name "Drive bracket plate thickness test" \
    --verification-method analysis --attachment att_procedure \
    --uuid 0193abcd-1234-7890-abcd-555555555555

# Design-intent links (Float at authoring; materialize Fixed at release per ADR/0009 §4)
$ python -m wedge --workspace outputs link-tested-against --source P-000058 --target TST-000017
$ python -m wedge --workspace outputs link-verifies \
    --source TST-000017 --target REQ-000058 --target-criterion ac_min_thickness

# Author EvidenceArtifact with attachment + parameter lineage
$ python -m wedge --workspace outputs attach-file \
    --file ../fixtures/measurement_EVD-000043.csv --role source_authoring --id att_measurement_data
$ python -m wedge --workspace outputs create-evidence-artifact \
    --number EVD-000043 --summary "Drive bracket plate thickness measurement" \
    --evidence-kind measurement \
    --parameter "reported_thickness_mm=6.98:from=attachment:att_measurement_data" \
    --attachment att_measurement_data \
    --uuid 0193abcd-1234-7890-abcd-777777777777

# Author TestExecution with canonical field names per ADR/0022 §9 (per Codex1 B1)
$ python -m wedge --workspace outputs attach-file \
    --file ../fixtures/instron_log_TEX-000007.txt --role source_authoring --id att_instron_log
$ python -m wedge --workspace outputs create-test-execution \
    --number TEX-000007 \
    --execution-status completed \
    --executed-on-date 2026-04-15 \
    --operator-identifier "test_engineer:emp_5839" \
    --parameter "measured_thickness_mm=6.98:from=attachment:att_instron_log" \
    --attachment att_instron_log \
    --uuid 0193abcd-1234-7890-abcd-666666666666

# Execution-instance links — Fixed at authoring; pins predeclared rev_ids per Decision §2.5
$ python -m wedge --workspace outputs link-executes --source TEX-000007 --target TST-000017
✓ Authored as binding: fixed; endpoints[0].revision_id pinned to predeclared <tst-rev-uuid>
$ python -m wedge --workspace outputs link-executed-on --source TEX-000007 --target P-000058
✓ Authored as binding: fixed; endpoints[0].revision_id pinned to predeclared <part-rev-uuid>
$ python -m wedge --workspace outputs link-produces --source TEX-000007 --target EVD-000043
✓ Authored as binding: fixed; endpoints[0].revision_id pinned to predeclared <evd-rev-uuid>

# cites — design-intent (Requirement → EvidenceArtifact); Float at authoring; Fixed at release
$ python -m wedge --workspace outputs link-cites \
    --source REQ-000058 --target EVD-000043 --source-criterion ac_min_thickness

# Release ALL 5 Objects atomically
$ python -m wedge --workspace outputs release \
    --objects "P-000058,REQ-000058,TST-000017,TEX-000007,EVD-000043" --label rev-A
✓ Allocated predeclared rev_ids to released Revisions
✓ Materialized Float bindings: tested_against / verifies / cites pinned to terminal Revisions
✓ Verified pre-pinned Fixed bindings: executes / executed_on / produces endpoints resolve to released Revisions
✓ 5 release events appended (part_released / requirement_released / test_procedure_released / test_execution_released / evidence_artifact_released)
✓ Manifest pins 5 Revision hashes + validation outcomes including schema validation,
  attachment integrity, V&V chain integrity, and execution cardinality:
    - satisfies(P-000058,REQ-000058) — derived via the V&V chain traversal — PASS
    - schema_validation(<each>) — 5 Revisions validate
    - attachment_integrity(att_procedure) — re-hashed vault bytes match TST Revision embedded content_hash — PASS
    - attachment_integrity(att_instron_log) — re-hashed vault bytes match TEX Revision embedded content_hash — PASS
    - attachment_integrity(att_measurement_data) — re-hashed vault bytes match EVD Revision embedded content_hash — PASS
    - vv_chain_integrity — full chain traversal closes — PASS
    - execution_cardinality(TEX-000007) — executes==1 ✓; executed_on>=1 ✓; produces>=1 ✓ (completed)
✓ Release manifest hash: sha256:<computed>
```

Wedge-002 succeeds if every line runs cleanly with no manual fixup; resulting sidecars / events / Revisions / manifest pass fold-consistency + attachment-integrity + V&V-chain-integrity + execution-cardinality checks.

## Consequences

- **Second code-producing-direction ADR pinned.** ADR/0024 lands the Wedge-002 scope; the spike-writing arc that implements it is the third code-producing arc.
- **Schema bundle: no bump.** Bundle stays v0.19.0. Wedge-002 spike's V&V schemas implement existing ADRs (0017 / 0019 / 0020 / 0021 / 0022); no new spec.
- **First scope ADR informed by a prior spike's friction log.** Pattern-setting: future scope ADRs in the spike series consume the prior spike's friction log as a load-bearing input.
- **First Attachment-bearing pattern in code.** Three instances exercise [ADR/0017](0017-object-type-drawing.md)'s template at minimum scale.
- **First execution-instance posture in code.** Fixed-at-authoring + per-relationship cardinality with status-sensitive refinement (`completed` SHOULD ≥1 `produces`) enforced for the first time.
- **First spike-grade Vault Adapter.** Content-addressed local-FS layout; idempotent; integrity-checking.
- **Wedge-001 friction items carried forward as spike-grade workarounds.** Schema Change Notes land as independent smaller arcs.
- **AIADRA YAML Profile spike-grade enforcement** inherited from Wedge-001.
- **Workspace-relative path convention** per Decision G1; resolves Wedge-001 FRICTION_LOG.md §2 workspace path divergence.
- **`.rev-id-map`** declared spike-local non-canonical per [Codex2 N2 absorption](../Discussions/20260530/20260530-2/Codex2.md). Not Product Truth; not pinned by manifest.
- **Validation-outcome wording** non-counting per [Codex2 N1 absorption](../Discussions/20260530/20260530-2/Codex2.md). Worked invocation lists categories ("schema validation, attachment integrity, V&V chain integrity, execution cardinality") not an exact count.
- **Manifest authority model unchanged** from Wedge-001. Attachment hashes transitively pinned via Revision content; `attachment_integrity` lands as validation_outcomes entries.
- **Methodology arc flag** — first V&V-instrumented spike scope + first Attachment-bearing in code + first execution-instance posture in code + first spike-grade Vault Adapter + first scope informed by prior friction log. Reserves pipeline.
- **SystemState updates.** §1 Current Front advances "Wedge-001 spike implementation complete" → "Wedge-002 scope pinned (ADR/0024); spike-writing arc is next natural step." §5 Deferred refresh. §6 Recent Pattern Changes entry.
- **OpenQuestions update.** No OQ resolved by this arc directly. OQ-0007 stays resolved.
- **Glossary update.** No new entries required.
- **No new ADR slot reservation.** Wedge-002 spike-writing arc references ADR/0024 as its scope spec; no further ADR for the spike implementation itself per [ADR/0023 + 20260530-1](../Discussions/20260530/20260530-1/CLOSED.md) precedent.

## Codex2 sign-off summary

[Codex2](../Discussions/20260530/20260530-2/Codex2.md) signed off without further objection. All three Codex1 blockers retracted after Claude2 absorptions; both Codex2 non-blockers (validation-outcome count wording + `.rev-id-map` spike-local) absorbed in this ADR. The agreed direction (scope-first ADR; full V&V chain; minimal local-FS content-addressed Vault Adapter; throwaway posture; parallel `spikes/wedge-002/`; carry Wedge-001 friction forward; Fixed-at-authoring execution-instance discipline with upfront `--rev-id` predeclaration) is unchanged from Claude1 + Claude2; ADR/0024 lands the converged form.
