---
name: adr-0006-object-type-requirement
status: accepted
date: 2026-05-18
supersedes: none
superseded_by: none
resolves: []
---

# ADR/0006 — Object Type: Requirement

## Status

**Accepted** — 2026-05-18. Second per-Type Object catalogue ADR; **first non-physical Object Type**. Establishes the patterns subsequent non-physical Types (TestProcedure, EvidenceArtifact) will follow: TypeSpecific singleton fields under a wrapper block, structured-text content (`statement`, `acceptance_criterion.criterion`), source/origin traceability (`source:` namespace), and the principle that the seven-namespace shape from [ADR/0005 (Part)](0005-object-type-part.md) is a *template* — non-physical Types select which namespaces apply.

## Context

[ADR/0005 (Part)](0005-object-type-part.md) pinned the first concrete Object Type and set patterns for physical Types: seven namespaces including `feature:`, `geometry_ref:`, and `material:`, plus the governed adapter shell for Domain-Engine-backed content. The [amended Promotion Rule commitment 6](../TruthModelSchema.md#6-promotion-ceremony) (TruthModelSchema v0.7) decoupled governance ceremony from bundle bump class: ADR ceremony is required when the promotion introduces novel patterns, regardless of bundle bump class.

Requirement is the second seed Object Type per [ADR/0003 §1 / §2](0003-schema-governance.md) named examples and [Promotion Rule commitment 8](../TruthModelSchema.md#8-seed-catalogue-is-grandfathered). Its *promotion* is grandfathered; what this ADR settles is the **Type-specific schema content** for the first non-physical Type:

- **First non-physical-Type patterns.** Requirement has no `feature:`, `geometry_ref:`, `material:`, or adapter shell. It introduces structured *singleton* content (the statement itself is the canonical fact, exactly one per Requirement) and a new `source:` namespace for origin traceability. The seven-namespace shape from Part is a template, not a quota.
- **Statement-as-canonical-content pattern.** A Requirement's primary content is its statement text. This is fundamentally different from Part, where canonical content lives in record namespaces and the envelope carries only identity. Requirement establishes TypeSpecific singleton fields under a typed wrapper block (`requirement:`) for the case where exactly-one-per-Object content has no natural collection.
- **Source / origin traceability.** Requirements come from somewhere — customer, stakeholder, regulation, parent Requirement, imported tool. This is engineering truth distinct from S1 `fact_provenance` (which categorizes *how* a value was produced, not *where it came from* in the domain).
- **Verification linkage foundation.** Requirements are verified by Tests (when TestProcedure ADR lands) against acceptance criteria. The seed Requirement schema introduces the `acceptance_criterion:` namespace and the `default_verification_method` singleton, laying the foundation for the future verification model.

The discussion trail in [`Docs/Discussions/20260518-5/`](../Discussions/20260518-5/) carries the full alternatives reasoning. Codex1 produced twelve findings; all twelve accepted. Codex2 produced one specific fix (worked-example S1 validity) plus green-light on substance.

## Alternatives Considered

### Statement representation

**A1. `statement:` as a record-collection namespace.** A Requirement could have multiple statement formulations (parent + clarifications + worked examples + translations).

> **Rejected.** Each Requirement has exactly one canonical statement at a given Revision. Variations belong elsewhere: clarifications go in `design_intent:`; worked examples go in `acceptance_criterion:`; translations are language-tagged fields within the single `statement` (Decision §4). Treating statement as a collection invites ambiguity about which is canonical.

**A2. `statement` as an unstructured string envelope field.** Plain text under `object.statement` or similar.

> **Rejected.** Conflates BaseObject envelope semantics (identity-only per spine S0 commitment 2) with TypeSpecific payload. Also forecloses future format diversity (EARS, structured templates, multi-language).

**A3. Structured singleton under a TypeSpecific wrapper.** *Chosen — see Decision §3 and §4.* `requirement.statement` is a structured object `{text, language, format}` under the `requirement:` wrapper block. Preserves the spine's envelope-vs-payload separation while accommodating singleton content.

### Verification method placement

**B1. Required `verification_method` singleton, "primary" method per Requirement.** Each Requirement declares one dominant verification method.

> **Rejected.** Many real Requirements have combined verification (test + analysis, inspection + test). Forcing a primary method invites low-quality values for complex cases — the worst kind of field: present, validated, and quietly misleading. Per-criterion verification on `acceptance_criterion:` records is the real truth.

**B2. Per-criterion only.** Verification method lives only on `acceptance_criterion:` records.

> **Rejected.** Simple Requirements with no separate criteria still need a verification approach. Requiring criteria authoring for the simple case is overhead.

**B3. Optional default + per-criterion override.** *Chosen — see Decision §6.* `requirement.default_verification_method` optional; per-criterion `verification_method` on `acceptance_criterion:` records overrides. Release-validation rule: at least one of (default, per-criterion on every criterion) must be set.

### Source / origin representation

**C1. No source modeling.** Source lives in `design_intent:` records as prose, or in `fact_provenance` categories.

> **Rejected.** S1 `fact_provenance` answers "how was this value produced" (human_input / ai_proposal / computed_result), not "where did this Requirement come from in the domain" (customer / regulation / parent Requirement). Source is engineering truth and traceability data, distinct from value production lineage. Hiding it in `design_intent:` prose is the silent-default-becomes-a-mess failure mode.

**C2. Per-source-type top-level fields.** `requirement.regulation_ref`, `requirement.stakeholder_ref`, etc.

> **Rejected.** Multiplies envelope-like fields per source type; doesn't scale to multiple sources of the same type; conflates source identity (records) with source citation (fields).

**C3. `source:` namespace with `source_type` enum.** *Chosen — see Decision §9.* Records under `source:` with discriminator field; carries citation, URI, Vault attachment, and source-type-specific traceability (e.g., `external_id` for `imported_tool` sources).

### Crosscutting concerns (safety, security, environmental, usability)

**D1. Add as top-level category enum values.** Six primary categories become ten.

> **Rejected.** These concerns cut across the primary taxonomy. A safety requirement may be functional, performance, interface, or design_constraint depending on its nature. Forcing them into primary categories creates classification ambiguity and false dichotomies.

**D2. Optional `classifications:` tags field.** List of strings carrying crosscutting tags.

> **Deferred.** Useful future addition but not blocking. Adding via additive Schema Change Note when a project surfaces a concrete use case (per [Promotion Rule commitment 9](../TruthModelSchema.md#9-catalogue-work-is-use-case-driven)).

**D3. Six-value primary category, no crosscutting field.** *Chosen — see Decision §5.* Seed schema stays conservative; crosscutting concerns handled through `source:` (`source_type: regulation` carries safety regulations) or future Schema Change Note.

### Priority and status

**E1. Required priority enum.** Every Requirement carries `priority` (must / should / could / won't or numeric).

> **Rejected.** Priority schemes vary wildly across projects (MoSCoW, customer priority, release priority, safety ASIL/SIL, severity tiers). Forcing one scheme on the seed is over-constraining; making the field optional-with-no-enum is weak documentation. Defer to project policy or future Schema Change Note when a need surfaces.

**E2. Workflow status field separate from lifecycle.** `requirement.status: draft | agreed | verified`.

> **Rejected.** `draft / agreed` overlaps with lifecycle (`in_work / under_review / released`); `verified` should be derived from Test / EvidenceArtifact outcomes when those Types land, not manually asserted. Project workflow beyond lifecycle belongs to Layer 4 project control, not the Object Type schema.

**E3. No priority, no separate status.** *Chosen — see Decision §11.* Lifecycle covers progression; verification is derived; priority deferred.

### Relationship endpoints

**F1. Introduce `requires` relationship.** Part → Requirement, "this Part has this Requirement," distinct from `satisfies`.

> **Rejected.** Near-duplicate of `satisfies` (implementation claim) and `allocates_to` (responsibility assignment). Discipline in the initial relationship vocabulary matters. No `requires` until a concrete distinct use case proves it's not a duplicate.

**F2. Conservative four-relationship seed.** `satisfies`, `derived_from`, `refines`, `allocates_to`.

> **Chosen — see Decision §12.** Plus forward-references for `verifies` (TestProcedure → Requirement, when that ADR lands).

## Decision

### 1. Promotion

Requirement passes the [Promotion Rule](../TruthModelSchema.md#promotion-rule-for-first-class-object-types) capability test:

- **C1 — Independent identity.** A Requirement `REQ-000014` is the same Requirement regardless of which Parts satisfy it; the same Requirement can be satisfied by multiple Parts and verified by multiple Tests.
- **C2 — Independent lifecycle.** Progresses on its own cadence, separate from Parts. A Requirement can be released before any Part satisfies it.
- **C3 — Independent referenceability.** Referenced by UUID from Parts (`satisfies` target), other Requirements (`derived_from`, `refines`), Tests (`verifies` when that lands), subsystems (`allocates_to`).
- **C4 — Independent provenance / approval.** Released on its own approval; typically stakeholder sign-off rather than engineering review.

No D1–D7 disqualifier applies. Grandfathered as seed per ADR/0003 §1 / §2 and Promotion Rule commitment 8.

### 2. Number prefix

`REQ-NNNNNN` — six-digit zero-padded sequential allocation from the Reservation file. AIADRA Core default; per-project override per [S2.5 commitment 10](../TruthModelSchema.md#10-number-format-and-type--prefix-mapping-are-per-project-policy). Six digits matches Part's `P-NNNNNN` for consistency and gives Tier-L headroom; engineering convention's four-digit (`REQ-0014`) is too tight once derived/lower-level Requirements multiply.

Exhaustion mechanics belong to OQ-0015 / ADR/0004.

### 3. TypeSpecific shape — three singletons + five namespaces

Different from Part's seven namespaces. Requirement is the first non-physical Type and demonstrates that the seven-namespace shape is a *template*.

**TypeSpecific singletons under the `requirement:` block** (semantic addresses; exactly one per Requirement):

- `requirement.statement` — canonical requirement text (Decision §4).
- `requirement.category` — REQUIRED enum (Decision §5).
- `requirement.default_verification_method` — OPTIONAL enum with release-validation rule (Decision §6).
- `requirement.fact_provenance`, `requirement.fact_uncertainty` — optional payload defaults for the singletons (Decision §7).

**TypeSpecific namespaces** (user-authored record collections under stable local ids per [S0 commitment 4](../TruthModelSchema.md#4-hybrid-within-artifact-addressing)):

1. `parameter:` — numerical constraints (same shape as Part).
2. `acceptance_criterion:` — verifiable criteria (new namespace; Decision §8).
3. `design_intent:` — rationale (same shape as Part with anchors-or-object-level guardrail).
4. `relationship:` — links to other Objects (S3 source-anchored).
5. `source:` — origin and traceability records (new namespace; Decision §9).

**Not present:** `feature:`, `geometry_ref:`, `material:`, `published_ref:`, adapter shell. The first Type to show the namespace shape is selective per Type.

### 4. `requirement.statement`

The canonical requirement text. Structured object:

```yaml
requirement:
  statement:
    text: "Operating temperature shall remain between 0°C and 60°C under continuous load."
    language: "en"
    format: "freeform"            # "freeform" | "ears" — recognized values
```

`format: ears` (Easy Approach to Requirements Syntax — WHEN/WHERE/WHILE/IF/THEN structured form) is a recognized value; per-format validation rules are deferred to future Schema Change Notes. The seed schema accepts both values without enforcing structural rules for `ears`. Per-project policy may tighten.

Each Requirement has exactly one `statement`. Changing it within `in_work` lifecycle follows S1's atomic-value-plus-annotation pattern via a `requirement_statement_changed` event (lands when concrete event taxonomy work happens).

### 5. `requirement.category`

REQUIRED enum at the singleton level. Initial seed values aligned with ISO/IEC/IEEE 29148 / INCOSE Systems Engineering Handbook taxonomy:

- `functional` — what the product does
- `performance` — how well (timing, throughput, accuracy, tolerance)
- `non_functional` — reliability, maintainability, usability, security
- `interface` — how it connects to other systems / subsystems / users
- `design_constraint` — how it's built (process, material, tooling, environmental)
- `regulatory` — compliance with external standards (FCC, CE, FDA, ROHS, etc.)

Crosscutting concerns (safety, security, environmental, usability) are *not* primary categories — they cut across the taxonomy. An optional `classifications:` field for crosscutting tags can land additively via Schema Change Note when use case arises.

Enum extensible by future Schema Change Notes or per-project ADRs.

### 6. `requirement.default_verification_method`

OPTIONAL enum at the singleton level. Initial seed values: `test | analysis | inspection | demonstration` — standard four-method systems-engineering taxonomy.

**Release-validation rule:** a released Requirement must have either `requirement.default_verification_method` set OR a `verification_method` on every `acceptance_criterion:` record. If both are present, the per-criterion value overrides the default at that criterion.

This handles both shapes:

- Simple Requirement, one dominant method → singleton default; criteria inherit.
- Complex Requirement, mixed methods → per-criterion `verification_method`; singleton optional.

Forcing a "primary" method on every Requirement invites low-quality values for complex cases. Optional-default-with-criterion-override is the right shape.

### 7. S1 annotation pattern for singletons under `requirement:`

`requirement.fact_provenance` and `requirement.fact_uncertainty` are TypeSpecific payload defaults for singleton fields under `requirement:`. Per [S1 commitment 2](../TruthModelSchema.md#2-deterministic-four-level-resolver-walk)'s deterministic four-level resolver walk, for an address like `requirement.statement`:

1. `requirement.statement.fact_provenance` if explicit.
2. (No containing record — singleton is not inside a user-authored record.)
3. `requirement.fact_provenance` — the singleton-wrapper default (level 3, "namespace default declared as explicit data" per [S1 commitment 3](../TruthModelSchema.md#3-no-canonical-project-level-defaults)).
4. `object.fact_provenance` — the envelope default (level 4).

The `requirement:` wrapper acts as the "namespace" for S1 walk purposes for singleton fields under it. Defaults declared inside the wrapper are level-3 fallbacks; individual singleton fields may override at level 1; everything ultimately falls through to the envelope default at level 4.

The S1 resolver still requires every concrete address to resolve to effective provenance and uncertainty. No escape hatch.

### 8. `acceptance_criterion:` namespace

Verifiable criteria that operationalize the Requirement. Each criterion is a testable statement with structured `criterion.text` mirroring `statement`'s shape:

```yaml
acceptance_criterion:
  - id: "ac_temp_range_test"
    name: "Temperature range — operational test"
    criterion:
      text: "Device functions per functional spec across the operating temperature range, measured at 5°C increments."
      language: "en"
      format: "freeform"
    references:                       # optional addresses inside this Requirement
      - "parameter:param_temp_min"
      - "parameter:param_temp_max"
    verification_method: "test"       # optional per-criterion override of singleton default
    fact_provenance: { category: "human_input" }
```

Acceptance criteria are operational verification targets, distinct from:

- `parameter:` — value-and-unit facts, not testable statements.
- `design_intent:` — rationale, not operational criteria.
- `relationship:` — links to other Objects, not internal criteria.

They're the bridge between the Requirement's statement and Tests that verify it. When TestProcedure ADR lands, Tests cite specific acceptance criteria.

Optional namespace.

### 9. `source:` namespace *(new)*

Origin and traceability records. Each `source:` record captures where the Requirement came from in domain terms — distinct from S1 `fact_provenance` (value production lineage).

```yaml
source:
  - id: "src_mkt_12"
    name: "Deployment plan MKT-12"
    source_type: "stakeholder_doc"
    citation: "MKT-12 section 3.2"
    uri: "https://internal-docs.example/MKT-12"     # optional
    vault_ref: "sha256:..."                          # optional content hash for archived source
    fact_provenance: { category: "human_input" }
```

`source_type` initial seed enum:

- `stakeholder_doc` — customer / market / internal stakeholder document
- `regulation` — externally mandated regulatory clause (FCC, CE, FDA, ROHS, etc.)
- `standard` — voluntary or referenced engineering standard (ISO, IEEE, ASTM, etc.)
- `customer` — direct customer interview or written request
- `derived` — parent Requirement or system analysis (the source for derived Requirements)
- `imported_tool` — imported from external requirements-management tool (DOORS, Polarion, Jama, ReqIF); carries `external_id`
- `internal` — internal design decision with no external citation

Both `uri` and `vault_ref` are optional — some sources are abstract (a stakeholder conversation; an internal design call) and have no citable artifact. The `citation` field is the human-readable reference.

`imported_tool` sources carry an `external_id` field referencing the foreign system's identifier:

```yaml
source:
  - id: "src_doors_1234"
    name: "Imported from DOORS"
    source_type: "imported_tool"
    external_id: "DOORS-1234"
    fact_provenance: { category: "imported_supplier_data" }
```

`external_id` is loose in the seed schema (optional, no type enforcement); a future Schema Change Note may tighten it to required-when-`source_type: imported_tool` when adapter contract solidifies.

Compliance modeling (multi-clause regulations, traceability matrices) is *not* introduced here. If standards / clauses later need to be reusable managed Objects, a future `ComplianceRequirement` or `StandardClause` Type can be promoted through the normal Promotion Rule.

Optional namespace. A Requirement may have zero, one, or many sources.

### 10. `parameter:`, `design_intent:`, `relationship:` namespaces

Same shapes as Part's per [ADR/0005 §4, §5, §11](0005-object-type-part.md). Reused without modification.

- `parameter:` — numerical constraints with `id`, `name`, `value`, `datatype`, `unit?`, S1 annotations; supports computed parameters with `derived_from` per [S1 commitment 5](../TruthModelSchema.md#5-computed-facts-carry-derived_from-inside-fact-provenance).
- `design_intent:` — rationale records with anchors-or-object-level guardrail.
- `relationship:` — source-anchored relationship records per [S3 commitment 3](../TruthModelSchema.md#3-relationships-are-source-anchored).

All three are optional namespaces.

### 11. No status field, no priority field

`requirement.status: draft | agreed | verified` is *not* introduced. `draft / agreed` overlap with lifecycle (`in_work / under_review / released`); `verified` is derived from Test / EvidenceArtifact relationships when those Types land. Project workflow states beyond lifecycle belong to Layer 4 project control, not the Object Type schema.

`requirement.priority` is *not* introduced. Priority schemes vary widely (MoSCoW, severity, ASIL/SIL, customer priority, release priority); the seed schema doesn't pre-commit a scheme. Project policy or future Schema Change Note when a concrete need surfaces.

### 12. Relationship endpoint participation, Revision schema, bundle bump

**Relationship endpoint participation.** Initial seed:

| Relationship | Direction | Arity | Cycle policy | Notes |
|---|---|---|---|---|
| `satisfies` | Part → Requirement | binary | `trace_graph` | Requirement is target; source is Part per [ADR/0005 §11](0005-object-type-part.md) |
| `derived_from` | Requirement → Requirement | binary | `acyclic_dependency` | Requirement is source and target (deriving lower-level from higher-level Requirements) |
| `refines` | Requirement → Requirement | binary | `acyclic_dependency` | Requirement is source and target |
| `allocates_to` | Requirement → Part / Subsystem | binary | `trace_graph` | Requirement is source; target is Part now, Subsystem when that Type lands |

Future endpoint participations (out of scope; flagged):

- `verifies` — TestProcedure → Requirement (when TestProcedure ADR lands).
- `traces_to` — generic traceability, likely derived from `derived_from` + `refines` graphs.

A proposed `requires` relationship (Part → Requirement, distinct from `satisfies`) is **explicitly not introduced** — near-duplicate of `satisfies` / `allocates_to`. No introduction until a concrete distinct use case proves it.

**Revision schema.** Same as Part per [S2 commitment 1](../TruthModelSchema.md#1-revisions-are-separate-immutable-schema-governed-artifacts). Each Revision record carries the full reconstructable release-time snapshot per [S2 commitment 13](../TruthModelSchema.md#13-revision-snapshot-boundary) — three singletons + five namespaces frozen at release time. Canonical path: `revisions/<object-uuid>/<revision-id>.yaml`.

**Bundle bump:** MINOR / additive per [ADR/0003 §11](0003-schema-governance.md). Bundle bumps v0.2.0 → v0.3.0 (from where ADR/0005 left it). New `object.type = "Requirement"` discriminator value, new `sidecar/Requirement.schema.json`. No existing artifacts to break.

**ADR ceremony** per the [amended Promotion Rule commitment 6](../TruthModelSchema.md#6-promotion-ceremony) — first non-physical Object Type, introduces TypeSpecific singleton wrapper pattern, introduces `source:` namespace, introduces structured-text content patterns. Multiple pattern-setting decisions qualify.

## Worked sidecar example

Showing the full structure with S1 annotations resolved through the four-level walk. Record annotations are omitted where they inherit from the envelope-level `object.fact_provenance` / `object.fact_uncertainty` default (level 4 of the S1 resolver walk per [commitment 2](../TruthModelSchema.md#2-deterministic-four-level-resolver-walk)). One `acceptance_criterion:` record shows an explicit override to demonstrate the level-1 pattern.

```yaml
object:
  uuid: "0193abcd-1234-7890-..."
  type: "Requirement"
  number: "REQ-000014"
  lifecycle: "in_work"
  schema_version: "0.3.0"
  fact_provenance: { category: "human_input" }    # envelope-level default (S1 level 4)
  fact_uncertainty: "verified"

requirement:
  statement:
    text: "Operating temperature shall remain between 0°C and 60°C under continuous load."
    language: "en"
    format: "freeform"
  category: "performance"
  default_verification_method: "test"

parameter:
  - id: "param_temp_min"
    name: "min_operating_temperature_c"
    value: 0.0
    datatype: "number"
    unit: "°C"
  - id: "param_temp_max"
    name: "max_operating_temperature_c"
    value: 60.0
    datatype: "number"
    unit: "°C"

acceptance_criterion:
  - id: "ac_temp_range_test"
    name: "Temperature range — operational test"
    criterion:
      text: "Device functions per functional spec across the operating temperature range, measured at 5°C increments."
      language: "en"
      format: "freeform"
    references:
      - "parameter:param_temp_min"
      - "parameter:param_temp_max"
    verification_method: "test"
    fact_provenance: { category: "ai_proposal", ai_agent_ref: "agent_xyz_2026q2" }   # level-1 override
    fact_uncertainty: "requires_validation"

design_intent:
  - id: "di_temp_range_rationale"
    name: "Operating temperature range rationale"
    purpose: "Covers expected deployment environments per MKT-12 deployment plan."
    scope: "object"

relationship:
  - id: "rel_derived_from_sys_001"
    type: "derived_from"
    binding: "float"
    endpoints:
      - project_scope: null
        object_uuid: "0193aaaa-1234-..."

source:
  - id: "src_mkt_12"
    name: "Deployment plan MKT-12"
    source_type: "stakeholder_doc"
    citation: "MKT-12 section 3.2"
    uri: "https://internal-docs.example/MKT-12"
```

Effective S1 annotations under this sidecar:

- `requirement.statement.text` → `human_input` / `verified` (inherits envelope default; no singleton wrapper override).
- `parameter:param_temp_min.value` → `human_input` / `verified` (inherits envelope default).
- `acceptance_criterion:ac_temp_range_test.criterion.text` → `ai_proposal` / `requires_validation` (explicit level-1 override on the record).
- `source:src_mkt_12.citation` → `human_input` / `verified` (inherits envelope default).

Every concrete address resolves to effective provenance and uncertainty under the four-level walk.

## Consequences

- **Schema bundle bump.** Active bundle moves v0.2.0 → v0.3.0. New `sidecar/Requirement.schema.json` lands in the `aiadra-core` bundle. Number prefix mapping for `Requirement → REQ-NNNNNN` declared at the bundle.
- **Glossary update.** [Glossary](../Glossary.md) bumps v0.6 → v0.7 with the existing *Requirement* entry rewritten to cite this ADR, list three singletons + five namespaces, reference `REQ-NNNNNN` default, and enumerate category / verification-method enums.
- **Forward references in relationship-type schemas.** Endpoint constraints in Decision §12 take effect when relationship-type ADRs are written. `satisfies` (Part → Requirement) was already declared in ADR/0005's table; the seed catalogue's relationship-type schemas land after Assembly.
- **Non-physical-Type patterns established.** TestProcedure and EvidenceArtifact ADRs (Tier-2 promotions) will reuse:
  - TypeSpecific singleton wrapper pattern (`testprocedure:`, `evidence:` analogous to `requirement:`).
  - Structured-text content pattern for any "textual canonical fact" (test procedure body, evidence summary).
  - Source / origin namespace where applicable.
  - Selective namespace adoption — neither will use `feature:` / `geometry_ref:` / `material:`.
- **`source:` namespace shape.** Reusable by future non-physical Types that need origin traceability. The seven `source_type` enum values cover the seed range; extensible via Schema Change Notes.
- **Crosscutting `classifications:` field, priority, status — all deferred.** Schema Change Notes when concrete project use case appears.
- **`requirement_statement_changed` event** — lands in concrete event taxonomy work alongside other Type-specific events.
- **EARS-format validation** deferred to Schema Change Note when EARS-structured Requirements are actually authored at scale.
- **Requirements-management adapter** (DOORS / Polarion / ReqIF) — additive future extension. `source.source_type: imported_tool` with `external_id` provides lightweight traceability now; full adapter contract awaits Domain Adapter ADR.
- **`sidecar/Requirement.schema.json`** — lives in the `aiadra-core` schema bundle, not in this ADR. The ADR governs decisions; the schema implements them.

## References

- [Manifesto.md](../Manifesto.md) — P3 (UUID identity), P4 (Design Intent first-class), P7 (provenance + uncertainty), P10 (event-based history), P11 (AIADRA Core hosts nothing — bounds future requirements-tool integration).
- [Glossary.md](../Glossary.md) — *Object (Managed Object)* (carries catalogue verdicts including Requirement as seed), *Requirement* (entry rewritten in Glossary v0.7), *UUID*, *Number*, *Sidecar*, *Revision*, *Released Truth*.
- [TruthModelSchema.md](../TruthModelSchema.md) — S0 (compositional schema; addressing), S1 (provenance / uncertainty four-level walk), S2 (release / Revision), S2.5 (Number-binding lifecycle), S3 (relationships), Promotion Rule (C1–C4, D1–D7, amended commitment 6 governance-vs-schema decoupling).
- [ADR/0001](0001-storage-substrate.md) — Storage substrate.
- [ADR/0002](0002-canonical-format.md) — Canonical format.
- [ADR/0003](0003-schema-governance.md) — Schema governance. §2 (discriminator), §5 (event immutability), §11 (bump ceremony — MINOR additive for Requirement).
- [ADR/0005](0005-object-type-part.md) — Object Type: Part. Pattern source for `parameter:`, `design_intent:` (anchors guardrail), `relationship:` (source-anchored), Revision schema, Number prefix conventions, governance ceremony for first concrete Object Type.
- [OpenQuestions.md](../OpenQuestions.md) — OQ-0003 (failed-transaction audit-log scope; AI-proposed Requirement provenance), OQ-0015 (Reservation file shape, downstream of REQ Number prefix decision), OQ-0016 (cross-project Object identity, downstream of future MaterialSpec / Component promotion and possible cross-project Requirement reuse).
- Discussion trail (git-ignored, local only): `Docs/Discussions/20260518-5/Claude1.md` → `Codex1.md` → `Claude2.md` → `Codex2.md` — full working-out across one substantive Codex round plus a small final example-validity correction.
