---
name: adr-0013-relationship-type-allocates-to
status: accepted
date: 2026-05-19
supersedes: 0006-object-type-requirement (partial — §C3 line 109 wording clarification for `allocates_to` direction only)
superseded_by: none
resolves: []
---

# ADR/0013 — Relationship Type: `allocates_to`

## Status

**Accepted** — 2026-05-19. Sixth relationship-type schema (after `satisfies`, `composed_of`, `mated_to`, `derived_from`, `refines`); fourth and final trace relationship from the [ADR/0006 §"Decision 12"](0006-object-type-requirement.md) anticipated table. Pattern-following ADR; inherits [ADR/0009](0009-relationship-type-satisfies.md)'s thirteen base trace-relationship pattern fields, with one deliberate divergence: opts **out** of direct cross-project endpoints (target is a deliverable Object, not an external Requirement). No new pattern fields declared; one partial clarification of [ADR/0006 §C3](0006-object-type-requirement.md). Unblocks Requirement-to-Part responsibility-assignment authoring for the Wedge and downstream system-engineering work.

## ADR/0006 §"Decision 1 — Promotion" §C3 clarification (partial)

[ADR/0006 line 109](0006-object-type-requirement.md) enumerates incoming references to Requirements:

> Referenced by UUID from Parts (`satisfies` target), other Requirements (`derived_from`, `refines`), Tests (`verifies` when that lands), subsystems (`allocates_to`).

Read literally in §C3's context (a list of *incoming* references), "subsystems (`allocates_to`)" implies subsystem-as-source — which contradicts the explicit direction in [ADR/0006 §"Decision 12" line 296](0006-object-type-requirement.md):

> `allocates_to | Requirement → Part / Subsystem | binary | trace_graph | Requirement is source; target is Part now, Subsystem when that Type lands`

ADR/0013 settles the conflict: **direction is Requirement → Part / Assembly per ADR/0006 §"Decision 12".** The §C3 line 109 phrase "subsystems (`allocates_to`)" is clarified to read: *Requirements are independently referenceable and may themselves author `allocates_to` records whose targets are subsystem-like Objects (currently Part or Assembly per the seed catalogue)*. This is a wording clarification — not a direction change — and ADR/0006 §C3's substantive claim (Requirements pass the Independent referenceability test, C3) remains authoritative.

Readers consulting [ADR/0006 §C3](0006-object-type-requirement.md) for `allocates_to` direction should treat ADR/0013 as authoritative. ADR/0006's other rows, decisions, and §C3's substantive Independent-referenceability claim remain unchanged. ADR/0006's overall status remains `accepted` (partial clarification only). This mirrors the [ADR/0012](0012-relationship-types-derived-from-and-refines.md) partial-supersession pattern.

## Context

After [ADR/0012](0012-relationship-types-derived-from-and-refines.md) landed `derived_from` and `refines`, only `allocates_to` remained from the four trace relationships [ADR/0006 §"Decision 12"](0006-object-type-requirement.md) anticipated and [ADR/0009 §3](0009-relationship-type-satisfies.md#3-direct-cross-project-endpoint-policy--permit-with-float-semantics-owned-here) named as future inheritors of the trace pattern. ADR/0013 closes that set.

Discussion trail in [`Docs/Discussions/20260519/20260519-3/`](../Discussions/20260519/20260519-3/). [Codex1](../Discussions/20260519/20260519-3/Codex1.md) produced two blockers (direct cross-project endpoints should be **NO** in seed; the ADR/0006 §C3 ambiguity warranted explicit partial clarification rather than a charitable reading) and two non-blocking confirmations (`Part | Assembly` seed scope; no new Pattern Catalogue row). Both blockers absorbed in [Claude2](../Discussions/20260519/20260519-3/Claude2.md). [Codex2](../Discussions/20260519/20260519-3/Codex2.md) sign-off with no further findings.

Two pressures converge here:

1. **Pattern inheritance with one deliberate divergence.** ADR/0009 established the thirteen base trace-relationship pattern fields. ADR/0013 opts these into the source-anchored asymmetric binary serialization + direct-binding + minimal seed properties + eventability inheritance — but explicitly opts *out* of cross-project endpoints. The divergence is target-Type-driven: ADR/0009's cross-project trace exception was justified by the external-regulatory-Requirement use case (clauses, standards). That justification does not transfer when the target is a Part or Assembly — a deliverable Object — because external deliverable adoption is the Binding Object pattern's load-bearing case per [ADR/0008 §3](0008-cross-project-object-identity.md).

2. **Clean per-relationship cross-project decisions under [ADR/0008 §4](0008-cross-project-object-identity.md).** ADR/0008 §4's per-type opt-in for trace relationships does not mean every trace relationship should opt in; it means each relationship-type ADR must carry the rationale. The trace-family *shape* symmetry is preserved (source-anchored, direct-binding, etc.); cross-project policy varies per target Type.

## Alternatives Considered

### Endpoint Type scope (seed)

**A1. `Part | Assembly`.** *Chosen — see Decision §1.* Maps ADR/0006 §12 "Part / Subsystem" forward to the current seed catalogue (Subsystem is not a promoted Object Type; Assembly is its working analogue).

**A2. `Part` only.**

> **Rejected.** Excludes the canonical system-level allocation case (allocating a Requirement to an Assembly responsible for a subsystem-grade deliverable). Assembly is the seed catalogue's composition Type.

**A3. Include `Component` / `Subsystem` / `SoftwareModule`.**

> **Rejected.** None of these Object Types exist in the current seed. Adding them speculatively pre-commits semantics that belong with the per-Type ADRs. Schema Change Note can extend target Types when those Types land.

### Direction

**B1. Source = Requirement; target = Part / Assembly.** *Chosen — see Decision §1.* Matches [ADR/0006 §12 line 296](0006-object-type-requirement.md) literally; matches top-down architect-authoring workflow ("architect allocates Req to Part"); matches the three other trace relationships' Requirement-source pattern (`derived_from`, `refines`, and the inverse case `satisfies` whose source is Part is a deliberate cross-Type asymmetry for "Part-makes-the-claim" semantics).

**B2. Source = Part / Assembly; target = Requirement.**

> **Rejected.** Contradicts ADR/0006 §12. Forces Part-side authoring friction (the Part owner must edit its sidecar every time an architect allocates a Req to it). The §C3 line 109 incoming-reference wording reading is not strong enough to override §12's explicit table.

### Direct cross-project endpoint policy

**C1. Opt in (inherit [ADR/0009 §3](0009-relationship-type-satisfies.md#3-direct-cross-project-endpoint-policy--permit-with-float-semantics-owned-here) trace exception).** Proposed in Claude1 on trace-family-symmetry grounds.

> **Rejected.** Codex's review correctly identified that target Type — not relationship shape — governs cross-project policy under [ADR/0008 §4](0008-cross-project-object-identity.md). `allocates_to`'s target is a deliverable Object (Part / Assembly), not a regulatory Requirement. Directly allocating a local Requirement to an external Part bypasses the Binding Object boundary [ADR/0008](0008-cross-project-object-identity.md) was designed to protect: local approval boundary, adoption / binding lifecycle, procurement / supplier override semantics, where-used / BOM queries. The trace-family *shape* symmetry doesn't imply cross-project policy symmetry.

**C2. Opt out (target local Objects only; defer cross-project to Binding Objects).** *Chosen — see Decision §4.*

### Optional record properties

**D1. Add `allocation_rationale` / `allocation_strength` / `confidence`.**

> **Rejected.** Same anti-pattern as [ADR/0009 §E](0009-relationship-type-satisfies.md#optional-record-properties). Rationale belongs in source's `design_intent:` records anchored to the relationship by id; strength / confidence are author-side editorial concerns invitations to structured-free-text drift.

**D2. Minimal seed properties; standard relationship-record fields only.** *Chosen — see Decision §5.*

### Direction-reconciliation form

**E1. Charitable-reading of ADR/0006 §C3 (no supersession; document in Decision §3 only).** Initial Claude1 position.

> **Rejected.** Codex correctly noted that ambiguity will be re-opened by future readers; documentation buried in Decision §3 isn't durable enough. Partial clarification at the top of the ADR (per ADR/0012's pattern) is the small ceremony cost.

**E2. Explicit partial clarification of §C3 line 109.** *Chosen — see "ADR/0006 §C3 clarification (partial)" section above.*

## Decision

### 1. Endpoint Type constraints, arity, source-anchoring

**Source endpoint Type constraint:** `Requirement`. Per [ADR/0006 §"Decision 12" line 296](0006-object-type-requirement.md). The Requirement's owner (typically a systems architect) authors the allocation as a top-down design decision.

**Target endpoint Type constraint:** `Part | Assembly`. Per ADR/0006 §12 wording "Part / Subsystem", mapped forward to the current seed catalogue (Subsystem is not a promoted Object Type; Assembly is its working analogue — a composition responsible for a subsystem-grade deliverable). Extensible by future Schema Change Note when Component, Subsystem, or other responsibility-bearing Object Types land.

**Arity:** binary at the semantic layer. **Serialization:** implicit source (the owning Requirement sidecar, by storage location per [S3 commitment 3](../TruthModelSchema.md#3-relationships-are-source-anchored)); the `endpoints` array contains exactly one entry — the target Part or Assembly. Inherited from [ADR/0009 §1](0009-relationship-type-satisfies.md#1-endpoint-type-constraints-arity-source-anchoring).

**Source-anchoring:** record lives in the source Requirement's `relationship:` namespace. Reverse direction ("which Requirements are allocated to this Part?") is acceleration-cache-derived per [ADR/0001 §3](0001-storage-substrate.md), never stored.

### 2. Whole-Object endpoint shape

Inherited verbatim from [ADR/0009 §2](0009-relationship-type-satisfies.md#2-whole-object-endpoint-shape-in-seed-criterion-level-deferred). Allocation is whole-Part / whole-Assembly. No `fact_ref` into target Part feature namespaces in seed. Future criterion-level Schema Change Note (analogous to the deferred `satisfies` criterion case) may add scoped allocation when verification taxonomy hardens — not in scope here.

### 3. Cycle policy, self policy, default binding

**Cycle policy:** `trace_graph`. Already declared in [ADR/0006 §"Decision 12" line 296](0006-object-type-requirement.md); **no supersession needed.** Cross-Type (Requirement → Part / Assembly), so cycles via `allocates_to` alone are structurally impossible today; class declared for consistency with [S3 commitment 13](../TruthModelSchema.md#13-per-type-cycle-and-graph-class-policy)'s trace-relationship enumeration.

**Self policy:** `self_forbidden`. Structurally impossible across Types; declared explicitly for class consistency.

**Default binding mode:** `float`. Per [ADR/0009 §4](0009-relationship-type-satisfies.md#4-binding-cycle-policy-self-policy). A Requirement allocated to a Part tracks the Part's current state by default; `fixed` is available for "allocated to a specific past Revision" semantics. Allowed values: `"float" | "fixed"`.

### 4. Direct cross-project endpoint policy — opt OUT

**Direct cross-project endpoints: NO** (per-type decision under [ADR/0008 §4](0008-cross-project-object-identity.md)). `allocates_to` targets local Objects only.

Although `allocates_to` is trace-shaped — inheriting the [ADR/0009](0009-relationship-type-satisfies.md) base pattern fields verbatim in every other respect — the cross-project trace exception in [ADR/0009 §3](0009-relationship-type-satisfies.md#3-direct-cross-project-endpoint-policy--permit-with-float-semantics-owned-here) was justified by the external-regulatory-Requirement use case (clauses, standards, upstream system Requirements). That justification does not transfer to `allocates_to`, whose target is a *deliverable Object* — Part or Assembly. Cross-project deliverable adoption is the Binding Object pattern's load-bearing case; routing through a local Component (when that Type lands) preserves:

- local approval boundary,
- local adoption / binding lifecycle,
- procurement / supplier override semantics,
- where-used / BOM-adjacent queries.

Until a Binding Object Type for external deliverables is introduced (Component is the most plausible per [ADR/0008 §3](0008-cross-project-object-identity.md)), cross-project `allocates_to` is **deferred** — no syntactic support in the seed schema. The endpoint schema for `allocates_to` records does **not** carry `project_scope` — locally-resolved endpoints only.

A future Schema Change Note can extend target Types and add cross-project syntax when Component (or Subsystem) lands. The deferral is deliberate, not an oversight.

**Negative case (explicit):** unlike `satisfies`, `derived_from`, and `refines` (which all opt into [ADR/0008 §4](0008-cross-project-object-identity.md)'s direct external endpoint exception per their respective ADRs), `allocates_to` does not. This is the first trace-relationship to opt out and the asymmetry is intentional — the target-Type-governs-cross-project-policy principle this ADR establishes.

### 5. Optional record properties — minimal seed

Inherited from [ADR/0009 §5](0009-relationship-type-satisfies.md#5-optional-record-properties--minimal-in-seed).

| Field | Required | Notes |
|---|---|---|
| `id` | REQUIRED | Stable local id per [S0 commitment 4](../TruthModelSchema.md#4-hybrid-within-artifact-addressing). |
| `name` | optional | Mutable human-readable label. |
| `type` | REQUIRED | Constant `"allocates_to"`. |
| `binding` | REQUIRED | `"float"` \| `"fixed"`. Default Float per Decision §3. |
| `endpoints` | REQUIRED | Single-entry array: the target Part or Assembly endpoint only. Source is implicit (the owning Requirement). No `project_scope` (Decision §4). |
| `fact_provenance`, `fact_uncertainty` | optional | S1 annotations per [S3 commitment 4](../TruthModelSchema.md#4-relationship-properties-follow-s1-annotation-rules). Inherits from container per S1 walk. |

No `allocation_rationale`, no `allocation_strength`, no `confidence`. Source Requirement's `design_intent:` records anchor to the relationship by id when rationale is needed.

### 6. Eventability, release materialization, bundle bump

**Eventability** inherited from [ADR/0009 §6](0009-relationship-type-satisfies.md#6-eventability-release-materialization-bundle-bump). `relationship_created`, `relationship_changed`, `relationship_retired`. `_changed` fires only on author intent change (Float ↔ Fixed switch, endpoint rebind, binding semantics change). Release-time materialization is NOT a `_changed` event. Retirement is tombstoning.

**Release-time materialization** (within-project only — no cross-project case in seed):

- Every endpoint in a released source Requirement Revision record carries `revision_id` per [S2 commitment 8](../TruthModelSchema.md#8-cross-object-references-may-include-revision_id-required-in-released-revision-records).
- Float bindings materialize to Fixed at release; working sidecar preserves authoring intent per [S3 commitment 12](../TruthModelSchema.md#12-float-vs-fixed-binding-mode-is-explicit-per-relationship).
- No `revision_content_hash` machinery — that field is cross-project-only per [ADR/0008 §6](0008-cross-project-object-identity.md), and Decision §4 opts out of cross-project endpoints.

**Validation rules** (Layer 2):

- Source Object Type == Requirement.
- Target Object Type ∈ {Part, Assembly}.
- Endpoint UUID resolves to a local sidecar.
- For Fixed bindings: `revision_id` REQUIRED on target endpoint.
- In released Revision records: every endpoint carries `revision_id`.
- No `project_scope` permitted on endpoints (Decision §4 opt-out enforced at schema level).
- Self-reference (`endpoint.object_uuid == owning_uuid`): hard-fail. Structurally impossible across Types but enforced for self-policy class consistency.

**Bundle bump:** **v0.9.0 → v0.10.0**, MINOR additive per [ADR/0003 §11](0003-schema-governance.md). Adds new `relationship/allocates_to.schema.json` to the bundle. Sixth occupant of `relationship/` (after `satisfies`, `composed_of`, `mated_to`, `derived_from`, `refines`). No existing artifacts to break.

**ADR ceremony** per the [amended Promotion Rule commitment 6](../TruthModelSchema.md#6-promotion-ceremony) — pattern-following ADR; no new pattern fields declared. One partial clarification of an earlier ADR (§"ADR/0006 §C3 clarification" above) and one deliberate divergence from the trace-family default (Decision §4 cross-project opt-out, with target-Type-governs rationale).

## Worked sidecar example

A Requirement sidecar with two `allocates_to` records: one within-project Float (allocated to a local Part whose state tracks current), one within-project Fixed (allocated to a specific Assembly Revision). Both follow the implicit-source pattern.

```yaml
object:
  uuid: "0193abcd-2222-7d12-9a4b-ffffffffffff"
  type: "Requirement"
  number: "REQ-000058"
  lifecycle: "in_work"
  schema_version: "0.10.0"
  fact_provenance: { category: "human_input" }
  fact_uncertainty: "verified"

requirement:
  statement: "Drive unit shall provide continuous torque ≥ 12 Nm at rated voltage."
  category: "performance"
  default_verification_method: "test"

# (other Requirement namespaces — parameter, acceptance_criterion, design_intent, source — omitted)

relationship:
  # Within-project, Float — allocated to a local Part; tracks the Part's current state.
  # Source is implicit (this Requirement REQ-000058 by storage location).
  - id: "rel_alloc_to_motor_part"
    name: "Allocated to drive motor Part"
    type: "allocates_to"
    binding: "float"
    endpoints:
      - object_uuid: "0193abcd-3333-7890-aaaa-111111111111"  # P-000023, drive motor

  # Within-project, Fixed — allocated to a specific Revision of an Assembly (e.g., a frozen baseline).
  - id: "rel_alloc_to_drive_assy_rev"
    name: "Allocated to drive assembly baseline Revision"
    type: "allocates_to"
    binding: "fixed"
    endpoints:
      - object_uuid: "0193abcd-4444-7abc-bbbb-222222222222"  # ASM-000007, drive assembly
        revision_id: "rev_2026_05_15_baseline"
```

No cross-project example. Per Decision §4, cross-project endpoints are not supported in seed; the schema rejects `project_scope` on `allocates_to` endpoints.

Reverse direction is acceleration-cache-derived: "which Requirements are allocated to P-000023?" → cache query, never stored on P-000023's sidecar.

## Consequences

- **All four ADR/0006 §12 trace relationships now schema-pinned.** ADR/0009 (`satisfies`), ADR/0012 (`derived_from` / `refines`), ADR/0013 (`allocates_to`). The relationship-participation table ADR/0006 anticipated is fully realized; remaining named relationship-type work from [ADR/0009 §3](0009-relationship-type-satisfies.md#3-direct-cross-project-endpoint-policy--permit-with-float-semantics-owned-here) is `parameter_expression` (multi-endpoint, pattern-setting) and the specialized future ones (`derived_geometry_from`, `depicts`).
- **First per-type cross-project opt-OUT.** ADR/0013 establishes the precedent that *target Type* — not relationship shape — governs cross-project endpoint policy under [ADR/0008 §4](0008-cross-project-object-identity.md). Future relationship-type ADRs whose target is a deliverable Object should consider opt-out by default; future relationship-type ADRs whose target is a Requirement-like Object should consider opt-in.
- **Schema bundle bump.** Active bundle moves v0.9.0 → v0.10.0. New `relationship/allocates_to.schema.json` lands; sixth occupant of `relationship/`.
- **Glossary addition.** [Glossary.md](../Glossary.md) v0.14: one new entry — `allocates_to` — alongside the existing five relationship-type entries.
- **ADR/0006 §C3 partial clarification.** Readers consulting [ADR/0006 §C3 line 109](0006-object-type-requirement.md) should treat ADR/0013 as the direction authority for `allocates_to`. ADR/0006's other rows, §C3's substantive Independent-referenceability claim, and overall `accepted` status remain unchanged.
- **No new Pattern Catalogue row.** `allocates_to` does not declare a new serialization, binding, endpoint-identity, or cycle pattern. A Recent Pattern Changes entry suffices.
- **SystemState "Trace-relationship direct-external-endpoint opt-in" row unchanged.** `allocates_to` is NOT added to its Applies-to column — the opt-out is the load-bearing decision.
- **Cross-project `allocates_to` deferred.** A future Schema Change Note can add `project_scope` + cross-project semantics when Component (or Subsystem) Object Types land. Until then, projects needing cross-project responsibility assignment must author a local Component (or wait for the Type ADR).
- **Wedge readiness for systems-engineering work.** Requirement-to-Part/Assembly allocation is now schema-supported. Combined with `satisfies` (claim direction), `derived_from` / `refines` (decomposition direction), and `composed_of` (structural), the Wedge has full Requirements-tree-to-Parts coverage modulo `verifies` (Tests, future).
