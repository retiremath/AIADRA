---
name: adr-0012-relationship-types-derived-from-and-refines
status: accepted
date: 2026-05-19
supersedes: 0006-object-type-requirement (partial — Decision 12 rows for `derived_from` and `refines` only)
superseded_by: none
resolves: []
---

# ADR/0012 — Relationship Types: `derived_from` and `refines`

## Status

**Accepted** — 2026-05-19. Fourth and fifth relationship-type ADRs landing together in a single combined decision (shape-identical at seed; semantic distinction lives in the Glossary). Both inherit [ADR/0009](0009-relationship-type-satisfies.md)'s thirteen base relationship-type pattern fields. Pattern-following arc; no new pattern fields declared. One new entry to the Pattern Catalogue (Requirement-to-Requirement trace relationships, carrying partial supersession of [ADR/0006 §"Decision 12"](0006-object-type-requirement.md)'s `acyclic_dependency` rows). Unblocks intra-Requirement traceability needed for the Wedge's downstream requirements-tree work.

## ADR/0006 §"Decision 12" supersession (partial)

[ADR/0006 §"Decision 12"](0006-object-type-requirement.md) lines 294–295 provisionally declared `derived_from` and `refines` as Requirement → Requirement, `acyclic_dependency`. ADR/0012 supersedes those two rows — **and only those two rows** — replacing `acyclic_dependency` with `trace_graph`. ADR/0006's other declarations (the rest of the relationship participation table; `allocates_to` and `verifies` rows; Requirement Object Type decisions; semantic notes) remain authoritative.

Rationale: relationship-type ADRs are the cycle-policy authority per ADR/0006's own deferral ("those endpoint constraints take effect when relationship-type ADRs are written"). `trace_graph` aligns with [S3 commitment 13](../TruthModelSchema.md#13-per-type-cycle-and-graph-class-policy)'s trace-relationship enumeration and the inherited [ADR/0009 §4](0009-relationship-type-satisfies.md#4-binding-cycle-policy-self-policy) baseline. Cycles via `derived_from` / `refines` are semantically suspicious — a Requirement deriving from itself, transitively or directly, is an author error — but not physically contradictory in the way an `acyclic_dependency`-class cycle in `composed_of` is. Author-time tooling warnings (validator layer) are the appropriate discipline; schema-level hard-fail is too strict for the trace-graph class.

ADR/0006's overall status remains `accepted` (partial supersession only); readers consulting [ADR/0006 §"Decision 12"](0006-object-type-requirement.md) for these two relationship types should treat ADR/0012 as the cycle-policy authority.

## Context

After [ADR/0009](0009-relationship-type-satisfies.md) ([`satisfies`](../Glossary.md#satisfies)), [ADR/0010](0010-relationship-type-composed-of.md) ([`composed_of`](../Glossary.md#composed_of)), and [ADR/0011](0011-relationship-type-mated-to.md) ([`mated_to`](../Glossary.md#mated_to)) landed the three load-bearing relationship types for the Wedge, the next four named in [ADR/0009 §3](0009-relationship-type-satisfies.md#3-direct-cross-project-endpoint-policy--permit-with-float-semantics-owned-here) are `derived_from`, `refines`, `allocates_to`, and `parameter_expression`. `derived_from` and `refines` are the lightest of the four — both intra-Type (Requirement → Requirement), shape-identical at seed, inheriting ADR/0009's source-anchored asymmetric binary serialization + direct-binding + direct-external-endpoint opt-in cleanly.

Discussion trail in [`Docs/Discussions/20260519/20260519-2/`](../Discussions/20260519/20260519-2/) — first arc to run end-to-end on the Claude↔Codex protocol established in [arc 20260519-1](../Discussions/20260519/20260519-1/CLOSED.md). [Codex1](../Discussions/20260519/20260519-2/Codex1.md) produced two blockers (silent ADR/0006 Decision 12 conflict on cycle class; stale bundle / Glossary version targets) and three non-blocking suggestions (compact per-relationship divergence table; Requirement-only seed scope explicitly Codex-confirmed; narrower Pattern Catalogue row dropping "intra-Type" framing). All absorbed in [Claude2](../Discussions/20260519/20260519-2/Claude2.md). [Codex2](../Discussions/20260519/20260519-2/Codex2.md) sign-off with no further findings.

Two pressures converge here:

1. **Pattern inheritance, not pattern setting.** ADR/0009 established the thirteen base trace-relationship pattern fields. ADR/0012's job is to opt these two relationships into that pattern with the smallest possible deviation. The only genuinely new decisions are endpoint Type scope (Requirement-only in seed), cycle policy (`trace_graph` with explicit ADR/0006 supersession), and self policy (`self_forbidden`).
2. **Requirements traceability for the Wedge.** Basic Wedge ([ADR/0009](0009-relationship-type-satisfies.md)) needs only `satisfies`. Downstream Wedge work — a Requirements tree with parent / child relationships, regulatory-clause refinement chains, derivation lineage from higher-level system Requirements — needs `derived_from` and `refines`. Landing both in one ADR avoids two near-identical arcs.

## Alternatives Considered

### Combine vs split

**A1. Two separate ADRs** — one for `derived_from`, one for `refines`.

> **Rejected.** Schema shape is identical at seed; semantic distinction lives in the Glossary entries. Splitting doubles arc cadence for no schema-level benefit. Precedent: [ADR/0011](0011-relationship-type-mated-to.md) covered all geometric/topological mate variants in one ADR; analogous combine-when-shape-is-parallel pattern. Codex1 confirmed combination as appropriate.

**A2. One combined ADR with compact per-relationship divergence table.** *Chosen — see Decision §1.* Decision table carries per-relationship rows even when currently identical, so future divergence has an obvious place to land.

### Endpoint Type scope (seed)

**B1. Requirement → Requirement only.** *Chosen — see Decision §2.*

**B2. Include Part → Part `derived_from` for catalog / variant lineage.**

> **Rejected.** Pre-commits Part-variant semantics before the Configuration ADR (deferred per [ADR/0007 §7](0007-object-type-assembly.md)). Part-variant lineage is more naturally addressed by the configuration / variants machinery, not by a generic `derived_from` extension. [ADR/0008 §4](0008-cross-project-object-identity.md) explicitly rejected using `derived_from` as the generic cross-project binding mechanism, foreshadowing the same posture here. Add by future Schema Change Note when production case surfaces.

**B3. Include `Requirement → Part` / `Part → Requirement`.**

> **Rejected.** `Requirement → Part` allocation is the `allocates_to` relationship's job (separate forthcoming ADR; cross-Type, different shape). `Part → Requirement` is `satisfies`'s job. No additional endpoint Types belong in `derived_from` / `refines` seed.

### Cycle policy

**C1. Inherit ADR/0006 Decision 12's `acyclic_dependency`.**

> **Rejected.** Conflates structural composition (where cycles violate physical reality, as in `composed_of`) with conceptual derivation (where cycles are author errors but not physical contradictions). [S3 commitment 13](../TruthModelSchema.md#13-per-type-cycle-and-graph-class-policy)'s trace-relationship enumeration includes `derived_from` / `refines` semantics; reusing `acyclic_dependency` for trace relationships is class-confusion.

**C2. `trace_graph` with explicit partial supersession of ADR/0006 Decision 12.** *Chosen — see Decision §3 and §"ADR/0006 §'Decision 12' supersession (partial)" above.* Author-time tooling may warn on detected cycles; schema-level enforcement is graph-class-valid.

### Optional record properties

**D1. Add `derivation_rationale` / `refinement_extent` / `derivation_method` to seed.**

> **Rejected.** Same anti-pattern as [ADR/0009 §E](0009-relationship-type-satisfies.md#optional-record-properties). Rationale belongs in source's `design_intent:` records anchored to the relationship by id; extent presumes the criterion-level shape deferred per [ADR/0009 §2](0009-relationship-type-satisfies.md#2-whole-object-endpoint-shape-in-seed-criterion-level-deferred); method invites structured-free-text drift.

**D2. Minimal seed properties; standard relationship-record fields only.** *Chosen — see Decision §5.* `id`, `name?`, `type`, `binding`, `endpoints`, S1 annotations.

## Decision

### 1. Combined ADR; compact per-relationship divergence table

Both relationship types share one ADR. The decisions live in a per-relationship table so future divergence has an explicit row to attach to.

| Field | `derived_from` | `refines` |
|---|---|---|
| **Semantic meaning** | Source Requirement *is decomposed / refined out of* target — child of a parent Requirement during requirements analysis | Source Requirement *is a more specific expression of* target — added precision, narrowed scope, added constraint |
| **Source Type** | Requirement | Requirement |
| **Target Type** | Requirement | Requirement |
| **Arity** | Binary; source-anchored; single serialized target | Binary; source-anchored; single serialized target |
| **Cycle policy** | `trace_graph` (supersedes [ADR/0006 §12](0006-object-type-requirement.md) `acyclic_dependency`) | `trace_graph` (same partial supersession) |
| **Self policy** | `self_forbidden` | `self_forbidden` |
| **Default binding** | `float` | `float` |
| **Direct external endpoint** | opt-in per [ADR/0008 §4](0008-cross-project-object-identity.md) | opt-in per [ADR/0008 §4](0008-cross-project-object-identity.md) |
| **Float external semantics** | inherited from [ADR/0009 §3](0009-relationship-type-satisfies.md#3-direct-cross-project-endpoint-policy--permit-with-float-semantics-owned-here) | inherited from [ADR/0009 §3](0009-relationship-type-satisfies.md#3-direct-cross-project-endpoint-policy--permit-with-float-semantics-owned-here) |
| **Multiple parents** | Permitted (a Requirement may be `derived_from` two upstream Requirements that together produced it) | Permitted but uncommon |
| **Deferred extensions** | Part → Part via Schema Change Note when Configuration ADR lands and production case surfaces | Criterion-level via Schema Change Note when verification taxonomy lands |

Rows currently near-identical by design. The table is the divergence anchor.

### 2. Endpoint Type constraints (seed)

**Source endpoint Type constraint:** `Requirement`. Per [ADR/0006 §11–§12](0006-object-type-requirement.md). Extensible by future Schema Change Note (Part → Part for catalog / variant lineage is the most plausible future addition; deferred per Alternatives §B2).

**Target endpoint Type constraint:** `Requirement`. Per [ADR/0006 §11–§12](0006-object-type-requirement.md). For cross-project endpoints, the target Type is validated against the resolved external Object's `object.type` per the inherited [ADR/0009 §3](0009-relationship-type-satisfies.md#3-direct-cross-project-endpoint-policy--permit-with-float-semantics-owned-here) materialization rules.

**Arity:** binary at the semantic layer. **Serialization:** implicit source (the owning Requirement sidecar, by storage location per [S3 commitment 3](../TruthModelSchema.md#3-relationships-are-source-anchored)); the `endpoints` array contains exactly one entry — the target Requirement. Inherited from [ADR/0009 §1](0009-relationship-type-satisfies.md#1-endpoint-type-constraints-arity-source-anchoring).

**Source-anchoring:** record lives in the source Requirement's `relationship:` namespace. Reverse direction ("what Requirements are derived from / refine this Requirement?") is acceleration-cache-derived per [ADR/0001 §3](0001-storage-substrate.md), never stored.

### 3. Cycle policy and self policy

**Cycle policy:** `trace_graph` for both. Per [S3 commitment 13](../TruthModelSchema.md#13-per-type-cycle-and-graph-class-policy) trace-relationship enumeration. Supersedes [ADR/0006 §"Decision 12"](0006-object-type-requirement.md)'s provisional `acyclic_dependency` rows (per the partial supersession above).

Actual cycles via `derived_from` (`A derived_from B`, `B derived_from A`) or `refines` (`A refines B`, `B refines A`) are author errors but not physical contradictions. Validator behavior:

- **Schema-level:** no hard-fail. Graph class is `trace_graph`; cycles are class-valid.
- **Tooling-level (Layer-3 / authoring UX):** warning on detected cycles. Validator implementations may surface "this `derived_from` chain forms a cycle (A → B → A); is this intentional?" at write time. Tooling decision, not schema decision.

This split — schema permissive, tooling advisory — matches the broader trace-graph posture and avoids over-constraining legitimate edge cases (e.g., a Requirement that historically derived from another and was later refactored to share a common parent may transitionally show cycle-like links during refactor).

**Self policy:** `self_forbidden` for both. A Requirement cannot be `derived_from` itself; a Requirement cannot `refines` itself. Hard-fail at schema validation.

### 4. Direct cross-project endpoint policy — opt-in inherited

Both relationships opt into [ADR/0008 §4](0008-cross-project-object-identity.md)'s per-type direct external endpoint exception for trace relationships, inheriting the precedent set by [ADR/0009 §3](0009-relationship-type-satisfies.md#3-direct-cross-project-endpoint-policy--permit-with-float-semantics-owned-here).

Use cases:

- `derived_from` external — a local Requirement is derived from an upstream regulatory clause Requirement published by an external standards project (FCC, CE, ISO).
- `refines` external — a local Requirement refines a higher-level Requirement in an upstream system-spec project.

Both are trace claims, not product-structure binding; the trace-relationship exception applies. Endpoint schema for external endpoints (when `endpoints[0].project_scope` is populated) inherited verbatim from [ADR/0009 §3](0009-relationship-type-satisfies.md#3-direct-cross-project-endpoint-policy--permit-with-float-semantics-owned-here):

- `project_scope.project_id` — REQUIRED. Stable external-project identity.
- `project_scope.locator_hint` — OPTIONAL. Non-authoritative transport / discovery hint.
- `object_uuid` — REQUIRED. External Requirement's UUID within its project.
- `revision_id` — REQUIRED for Fixed; absent for Float.
- `revision_content_hash` — REQUIRED for Fixed; absent for Float (release materialization pins it).

**Float external semantics inherited.** A Float cross-project `derived_from` or `refines` endpoint resolves to the external Requirement's **current released Revision**, never the external project's working sidecar payload. Release materialization is staleness-intolerant: resolve, validate `object.type == "Requirement"`, pin `revision_id` + `revision_content_hash`, hard-fail otherwise. Per [ADR/0009 §3](0009-relationship-type-satisfies.md#3-direct-cross-project-endpoint-policy--permit-with-float-semantics-owned-here).

**Negative case (explicit, inherited):** the trace-relationship exception does not generalize to product-structure relationships.

### 5. Optional record properties — minimal seed

Inherited from [ADR/0009 §5](0009-relationship-type-satisfies.md#5-optional-record-properties--minimal-in-seed).

| Field | Required | Notes |
|---|---|---|
| `id` | REQUIRED | Stable local id per [S0 commitment 4](../TruthModelSchema.md#4-hybrid-within-artifact-addressing). |
| `name` | optional | Mutable human-readable label. |
| `type` | REQUIRED | Constant `"derived_from"` or `"refines"`. |
| `binding` | REQUIRED | `"float"` \| `"fixed"`. Default Float per Decision §1 table. |
| `endpoints` | REQUIRED | Single-entry array: the target endpoint only. Source is implicit (the owning Requirement). |
| `fact_provenance`, `fact_uncertainty` | optional | S1 annotations per [S3 commitment 4](../TruthModelSchema.md#4-relationship-properties-follow-s1-annotation-rules). Inherits from container per S1 walk. |

No `derivation_rationale`, no `refinement_extent`, no `derivation_method`. Source's `design_intent:` records anchor to the relationship by id when rationale is needed (per Alternatives §D1).

### 6. Eventability, release materialization, bundle bump

**Eventability** inherited from [ADR/0009 §6](0009-relationship-type-satisfies.md#6-eventability-release-materialization-bundle-bump). `relationship_created`, `relationship_changed`, `relationship_retired`. `_changed` fires only on author intent change (Float ↔ Fixed switch, endpoint rebind, binding semantics change). Release-time materialization is NOT a `_changed` event. Retirement is tombstoning.

**Release-time materialization** inherited from [ADR/0009 §6](0009-relationship-type-satisfies.md#6-eventability-release-materialization-bundle-bump):

- Every endpoint in a released source Requirement Revision record carries `revision_id` per [S2 commitment 8](../TruthModelSchema.md#8-cross-object-references-may-include-revision_id-required-in-released-revision-records).
- Cross-project endpoints additionally carry `revision_content_hash` per [ADR/0008 §6](0008-cross-project-object-identity.md).
- Float bindings (within-project and cross-project) materialize to Fixed at release; working sidecar preserves authoring intent per [S3 commitment 12](../TruthModelSchema.md#12-float-vs-fixed-binding-mode-is-explicit-per-relationship).
- Float external endpoints: resolve to current released Revision; validate `object.type == "Requirement"`; pin `revision_id` + `revision_content_hash` atomically. Staleness-intolerant.

**Validation rules** (Layer 2):

- Source Object Type == Requirement.
- Target Object Type == Requirement (within-project: validated against the local Object's `object.type`; cross-project: validated against the resolved external Object).
- Endpoint UUID resolves.
- For Fixed within-project bindings: `revision_id` REQUIRED on target endpoint.
- For Fixed cross-project bindings: `revision_id` + `revision_content_hash` REQUIRED.
- For Float cross-project bindings: locality-tier-appropriate behavior in working state; hard validation failure at release.
- In released Revision records: every endpoint carries `revision_id`; cross-project endpoints also carry `revision_content_hash`.
- Self-reference (`endpoint.object_uuid == owning_uuid`): hard-fail (self policy `self_forbidden`).
- Cycle detection: NOT a schema-level validation (cycle class is `trace_graph`); tooling-level warning recommended.

**Bundle bump:** **v0.8.0 → v0.9.0**, MINOR additive per [ADR/0003 §11](0003-schema-governance.md). Adds two new files to the bundle: `relationship/derived_from.schema.json`, `relationship/refines.schema.json`. Fourth and fifth occupants of the bundle's `relationship/` directory (after `satisfies`, `composed_of`, `mated_to`). No existing artifacts to break.

**ADR ceremony** per the [amended Promotion Rule commitment 6](../TruthModelSchema.md#6-promotion-ceremony) — pattern-following ADR; no new pattern fields declared. One narrow Pattern Catalogue addition (Requirement-to-Requirement trace relationships) and one partial-supersession of an earlier ADR.

## Worked sidecar example

A Requirement sidecar with one `derived_from` record (within-project, Float) and one `refines` record (cross-project, Fixed external — refining an ISO standards clause). Both follow the implicit-source pattern.

```yaml
object:
  uuid: "0193abcd-7e8f-7d12-9a4b-aaaaaaaaaaaa"
  type: "Requirement"
  number: "REQ-000041"
  lifecycle: "in_work"
  schema_version: "0.9.0"
  fact_provenance: { category: "human_input" }
  fact_uncertainty: "verified"

requirement:
  statement: "Drive enclosure shall maintain IP54 ingress protection at sustained operating temperature."
  category: "non_functional"
  default_verification_method: "test"

# (other Requirement namespaces — parameter, acceptance_criterion, design_intent, source — omitted)

relationship:
  # Within-project, Float — derived from a higher-level system Requirement in the same project.
  # Source is implicit (this Requirement REQ-000041 by storage location).
  - id: "rel_derived_from_sys_001"
    name: "Derived from system-level enclosure protection Requirement"
    type: "derived_from"
    binding: "float"
    endpoints:
      - object_uuid: "0193abcd-1234-7890-aaaa-bbbbbbbbbbbb"  # REQ-000007, system-level enclosure
        # No revision_id — Float; tracks REQ-000007's current state.

  # Cross-project, Fixed external — refines a pinned ISO 20653 clause from external standards project.
  - id: "rel_refines_iso_20653_553"
    name: "Refines ISO 20653 §5.5.3 clause"
    type: "refines"
    binding: "fixed"
    endpoints:
      - project_scope:
          project_id: "iso-standards-org:iso-20653-2013"
          locator_hint: "https://standards.iso.org/iso/20653/repository"  # non-authoritative
        object_uuid: "01923456-aaaa-7bcd-9abc-cccccccccccc"  # ISO 20653 §5.5.3
        revision_id: "rev-2013-published"
        revision_content_hash: "sha256:9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a"
```

Reverse direction is acceleration-cache-derived: "what Requirements derive from REQ-000007?" → cache query, never stored on REQ-000007's sidecar.

## Consequences

- **Pattern Catalogue addition.** [SystemState §2](../SystemState.md#2-active-pattern-catalogue) gains one row: *Requirement-to-Requirement trace relationships* — declared by ADR/0012; applies to `derived_from`, `refines`; watch-out notes the ADR/0006 partial supersession and that cycles are graph-class-valid but semantically suspicious (tooling warning, not schema hard-fail).
- **Partial ADR/0006 supersession.** Readers consulting [ADR/0006 §"Decision 12"](0006-object-type-requirement.md) for `derived_from` / `refines` cycle policy should treat ADR/0012 as authoritative. ADR/0006's other rows and decisions remain authoritative. ADR/0006's overall status remains `accepted`.
- **Schema bundle bump.** Active bundle moves v0.8.0 → v0.9.0. New `relationship/derived_from.schema.json` and `relationship/refines.schema.json` land in the `aiadra-core` bundle.
- **Glossary additions.** [Glossary.md](../Glossary.md) v0.13: two new entries — `derived_from` and `refines` — alongside the existing `satisfies`, `composed_of`, `mated_to` entries.
- **No new pattern fields declared.** All thirteen base trace-relationship pattern fields inherited from ADR/0009.
- **`allocates_to` and `parameter_expression` remain to land.** [ADR/0009 §3](0009-relationship-type-satisfies.md#3-direct-cross-project-endpoint-policy--permit-with-float-semantics-owned-here)'s list of forthcoming trace / structural relationships: `allocates_to` (cross-Type Requirement → Part/Assembly) and `parameter_expression` (multi-endpoint, indirect-binding; declares its own pattern fields) are the next two. Neither in scope here.
- **Validator tooling responsibility.** Cycle detection on `derived_from` / `refines` is a tooling-layer concern, not a schema-layer one. Implementations may add author-time warnings; the schema does not hard-fail on cycles within the `trace_graph` class.
- **Wedge downstream readiness.** Requirements-tree work (parent / child decomposition, regulatory refinement chains) is now schema-supported. Basic Wedge (one Part → one Requirement) still uses only `satisfies`; extended Wedge can include `derived_from` / `refines` for richer Requirements trees.
- **First arc on the Claude↔Codex protocol.** Arc 20260519-2 is the first arc to run end-to-end on [Discussions/Transfer/PROTOCOL.md](../Discussions/Transfer/PROTOCOL.md). The protocol caught a real Claude miss (ADR/0006 silent conflict; stale bundle bump) on round 1 — exactly the value the review layer is supposed to add.
