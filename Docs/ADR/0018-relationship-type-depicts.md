---
name: adr-0018-relationship-type-depicts
status: accepted
date: 2026-05-19
supersedes: none
superseded_by: none
resolves: []
---

# ADR/0018 — Relationship Type: `depicts`

## Status

**Accepted** — 2026-05-19. Eighth relationship type after `satisfies`, `composed_of`, `mated_to`, `derived_from`, `refines`, `allocates_to`, `parameter_expression`. Closes the `depicts` pre-declarations in [ADR/0005 §11 line 212](0005-object-type-part.md) and [ADR/0007 §11 line 242](0007-object-type-assembly.md). After ADR/0018, the named relationship-type catalogue from [ADR/0009 §3](0009-relationship-type-satisfies.md#3-direct-cross-project-endpoint-policy--permit-with-float-semantics-owned-here) is operationally complete except for two specialized future ones: `derived_geometry_from` (awaits FreeCAD Domain Adapter scope) and `verifies` (awaits TestProcedure per-Type ADR).

Pattern-following ADR; inherits the thirteen base trace-relationship pattern fields from [ADR/0009](0009-relationship-type-satisfies.md). **One pattern-setting addition:** the `occurrence_context` sub-field on occurrence-qualified target endpoints. This is the first source-anchored asymmetric binary trace relationship whose source (Drawing) does NOT have implicit composition visibility into the target — necessitating explicit Assembly context for occurrence-path resolution. Sets the precedent for any future trace relationship that documents placed instances from outside the containing Assembly's namespace.

## Context

[ADR/0017](0017-object-type-drawing.md) landed Drawing as the sixth Object Type, structurally enabling `depicts`. The pre-declarations in [ADR/0005 §11](0005-object-type-part.md) and [ADR/0007 §11](0007-object-type-assembly.md) — `depicts | Drawing → Part`, `depicts | Drawing → Assembly`, both binary `trace_graph` — wait for this ADR to crystallize the schema. [ADR/0007 §2 line 121](0007-object-type-assembly.md) additionally pre-declared that future Drawing `depicts` of placed instances would be occurrence-qualified.

Discussion trail in [`Docs/Discussions/20260519/20260519-8/`](../Discussions/20260519/20260519-8/). [Codex1](../Discussions/20260519/20260519-8/Codex1.md) produced one blocker — Claude1's occurrence-qualified `depicts` was non-reconstructable because the record lives on the Drawing, not on the containing Assembly; bare `occurrence_ref` had no resolver starting Object. Absorbed in [Claude2](../Discussions/20260519/20260519-8/Claude2.md) with the explicit `occurrence_context` repair. [Codex2](../Discussions/20260519/20260519-8/Codex2.md) sign-off with three implementation-precision notes (all preserved here): coupling strict; examples differentiate resolver root from terminal cross-check; Component target guardrail preserved.

Two pressures converge:

1. **First occurrence-qualified target where source lacks implicit Assembly visibility.** Prior occurrence-qualified relationships (`mated_to`, `parameter_expression` cross-constituent) source-anchor on the containing Assembly itself — the `occurrence_ref` resolves inside the same Assembly's `composed_of` namespace, no context needed. `depicts` source-anchors on Drawing, which has no `composed_of` namespace at all. The `occurrence_context` sub-field makes the address self-contained: explicit Assembly resolver root, explicit terminal target cross-check, both pinned at release.
2. **Cross-project documentation policy.** `depicts` targets deliverable Objects (Part / Assembly / Component). The target-Type-governs precedent from [ADR/0013](0013-relationship-type-allocates-to.md) applies: cross-project documentation routes through the local Component Binding, not direct external endpoints. Same posture as `allocates_to`'s cross-project opt-out.

## Pre-declared constraints honored

| Constraint | Source | Disposition |
|---|---|---|
| Endpoint Types: Drawing → Part / Assembly | [ADR/0005 §11](0005-object-type-part.md), [ADR/0007 §11](0007-object-type-assembly.md) | Inherited; Decision §2 extends to include Component (additive). |
| Arity: binary; Drawing is source | [ADR/0005 §11](0005-object-type-part.md), [ADR/0007 §11](0007-object-type-assembly.md) | Inherited. |
| Cycle policy: `trace_graph` | [ADR/0005 §11](0005-object-type-part.md), [ADR/0007 §11](0007-object-type-assembly.md) | Inherited (no supersession needed). |
| Target may be occurrence-qualified for placed instances | [ADR/0007 §2 line 121](0007-object-type-assembly.md) | Inherited; Decision §3 supplies the `occurrence_context` shape that makes the address reconstructable. |
| Source-anchored asymmetric binary serialization (implicit source + single serialized target) | [ADR/0009 §1](0009-relationship-type-satisfies.md), inherited by `satisfies` / `derived_from` / `refines` / `allocates_to` | Inherited. |
| Trace-relationship base pattern fields (13) | [ADR/0009](0009-relationship-type-satisfies.md) | Inherited. |
| Default binding `float`; release materialization pins | [ADR/0009 §4 + §6](0009-relationship-type-satisfies.md) | Inherited. |
| Self policy `self_forbidden` (cross-Type) | Trace-relationship class consistency | Inherited. |
| Cross-project: target-Type-governs | [ADR/0013](0013-relationship-type-allocates-to.md) precedent | Inherited; Decision §4 opts out. |

## Alternatives Considered

### Endpoint Type union

**A1. `Part | Assembly` only.**

> **Rejected.** Drawing-of-catalog-Component is a real production case (vendor datasheet replicas; locally-annotated catalog references). Excluding Component would force a near-term Schema Change Note.

**A2. `Part | Assembly | Component`.** *Chosen — see Decision §2.*

**A3. `Part | Assembly | Component | SoftwareModule`.**

> **Rejected.** Software has no geometry to depict; documentation of software is a different relationship type (a future `documents` / `describes` if needed), not `depicts`.

**A4. Include Drawing-to-Drawing references.**

> **Rejected.** Cross-Drawing references (supersession, parent-of-detail) are a different relationship semantic. Schema Change Note if a production case surfaces.

### Occurrence-qualification of target

**B1. Bare `occurrence_ref` with implicit Assembly inferred from the namespace.** Claude1's original proposal.

> **Rejected (per Codex1 Blocker 1).** Drawing has no implicit Assembly visibility; `occurrence_ref` is a local id with no authoritative resolver starting Object. Address non-reconstructable. Release pinning incomplete.

**B2. Explicit `occurrence_context: { object_uuid, revision_id }` paired with `occurrence_ref`.** *Chosen — see Decision §3.*

**B3. Target-is-context: occurrence-qualified `depicts` targets the containing Assembly directly; the terminal Object is recovered from the path.**

> **Rejected.** Loses the semantic claim "Drawing documents this specific Part occurrence." Forces consumers to re-walk the path to identify what the Drawing is actually about. The chosen variant preserves the semantic.

### Cross-project endpoint policy

**C1. Direct cross-project endpoint opt-in (symmetric with `satisfies` external Requirement).**

> **Rejected.** `depicts` targets engineering deliverable Objects; the target-Type-governs precedent from [ADR/0013](0013-relationship-type-allocates-to.md) places deliverable targets under the Binding-Object route. No external-Requirement analogue justifies opt-in.

**C2. Direct cross-project endpoints NO; cross-project documentation routes through local Component.** *Chosen — see Decision §4.*

### View / region qualifier

**D1. Include `view:` / `region:` sub-block in seed.**

> **Rejected.** Substantial decision space (cross-section plane definition; callout bounding rectangle; exploded-view transform); overdesign risk for seed. Defer to Schema Change Note when use case shape stabilizes.

**D2. Defer to Schema Change Note; whole-Object / whole-occurrence trace in seed.** *Chosen — see Decision §6.*

### Multiple depicts per Drawing

**E1. Single primary depicts per Drawing.**

> **Rejected.** Common case is multiple — a system-level layout drawing depicts multiple constituents.

**E2. Multiple permitted; no record-level "primary" flag in seed.** *Chosen — see Decision §5.*

## Decision

### 1. Inherited from ADR/0009 (no new decisions)

Inherited verbatim:

- **Source-anchored asymmetric binary serialization** — implicit source (the owning Drawing), single target serialized. Per [ADR/0009 §1](0009-relationship-type-satisfies.md#1-endpoint-type-constraints-arity-source-anchoring).
- **Whole-Object endpoints in seed** — no `fact_ref` into target Object's feature namespaces; view/region deferred per Decision §6.
- **Default Float binding** — release materializes Float to Fixed atomically per [ADR/0009 §4](0009-relationship-type-satisfies.md#4-binding-cycle-policy-self-policy).
- **Cycle policy `trace_graph`** — already declared in [ADR/0005 §11](0005-object-type-part.md) and [ADR/0007 §11](0007-object-type-assembly.md). Cross-Type (Drawing source; Part/Assembly/Component target), structurally cycle-free.
- **Self policy `self_forbidden`** — class consistency.
- **Minimal seed properties** — inherited from [ADR/0009 §5](0009-relationship-type-satisfies.md#5-optional-record-properties--minimal-in-seed).
- **Eventability** — `relationship_created` / `relationship_changed` / `relationship_retired` per [ADR/0009 §6](0009-relationship-type-satisfies.md#6-eventability-release-materialization-bundle-bump).

### 2. Endpoint Type union

**Source endpoint Type constraint:** `Drawing`. Per [ADR/0017](0017-object-type-drawing.md). Drawing's `relationship:` namespace carries the `depicts` record.

**Target endpoint Type constraint:** `Part | Assembly | Component`.

- **Part** — per [ADR/0005 §11](0005-object-type-part.md). Detail drawings, single-part assembly drawings.
- **Assembly** — per [ADR/0007 §11](0007-object-type-assembly.md). Assembly drawings, system-level layouts.
- **Component** — extension. Drawings of catalog Parts (vendor datasheet replicas; locally-annotated catalog references).

**Component-target authority guardrail:** when `depicts` target is a Component, the Drawing documents the **local Component Binding Object** and its approved upstream identity — not arbitrary external vendor bytes. If the Drawing is a locally-stored copy of a vendor datasheet, the Drawing's own `attachment:` integrity (per [ADR/0017 §2](0017-object-type-drawing.md)) governs the local copy's `content_hash`; the Component's upstream binding (per [ADR/0014 §3](0014-object-type-component.md)) governs the referenced catalog item. The two integrity anchors are distinct: Drawing's `content_hash` for the locally-stored Drawing payload; Component's upstream `revision_content_hash` / `datasheet_content_hash` / etc. for the upstream item. The `depicts` relationship is the trace link between them. This prevents the "we copied a vendor datasheet into a local Drawing, so we don't need a Component Binding" anti-pattern.

**Excluded:** `SoftwareModule` (no geometry to depict); `Requirement` (documentation of Requirements is `satisfies` / `allocates_to` territory); `Drawing` (Drawing-to-Drawing references out of scope).

### 3. Occurrence-qualified target — explicit `occurrence_context`

Three endpoint shape variants:

**Variant A — Object-only target** (most common):

```yaml
endpoints:
  - object_uuid: "0193-P-019-..."         # the depicted Object (Part / Assembly / Component) — reusable definition
    revision_id: "..."                     # cross-check; present in released records
```

`occurrence_ref` ABSENT. `occurrence_context` ABSENT. Depicts the reusable Object definition regardless of where it's placed.

**Variant B — Occurrence-qualified target:**

```yaml
endpoints:
  - object_uuid: "0193-P-019-..."         # terminal depicted Object (cross-check against path resolution)
    occurrence_context:                    # REQUIRED when occurrence_ref present
      object_uuid: "0193-ASM-007-..."     # containing Assembly — resolver starting Object
      revision_id: "..."                   # cross-check; pinned in released Drawing Revisions
    occurrence_ref: "rel_composed_bolt_3" # path resolved inside occurrence_context per ADR/0010 §3
    revision_id: "..."                     # terminal Object's Revision; cross-check
```

Used when the Drawing documents a specific placed instance — e.g., a detail view of the third bolt in a 4-bolt pattern.

**Variant C — Schema-rejected:**

`occurrence_ref` present without `occurrence_context`, or `occurrence_context` present without `occurrence_ref`. Both fields are coupled — both present or both absent. Hard-fail at write.

**Address resolution semantics** (Variant B):

- `occurrence_context.object_uuid` MUST resolve to an Object whose Type is `Assembly` (Component does not own composition; sub-Assemblies that ARE Assemblies are valid context Objects).
- `occurrence_ref` MUST resolve inside that Assembly's `composed_of` namespace per the [ADR/0010 §3](0010-relationship-type-composed-of.md) binding-aware occurrence-path rules. Nested paths (`rel_composed_subassy/rel_composed_part`) per the same machinery.
- The terminal resolved Object Type MUST be in the depicts target Type union (`Part | Assembly | Component`).
- `endpoint.object_uuid` MUST equal the terminal resolved Object's UUID. Acts as a **cross-check** against path resolution — hard-fail on mismatch.

**Release materialization** (Variant B):

The Drawing's released Revision pins BOTH:

1. `endpoint.revision_id` — the terminal depicted Object's resolved Revision.
2. `endpoint.occurrence_context.revision_id` — the containing Assembly's Revision whose composition path is authoritative for resolving `occurrence_ref`.

Both materialized atomically per [S2 commitment 11](../TruthModelSchema.md). The Assembly Revision is the authority for path validity (placement transform, nested path, terminal target); the terminal `revision_id` is the authority for what the depicted Object looked like at the moment the Drawing was released. Mismatch between recorded and resolved at fetch / release is hard-fail.

This is the first source-anchored asymmetric binary trace relationship whose target endpoint requires a context Object explicitly — necessitated by the Drawing source-anchor's lack of implicit composition visibility. Future trace relationships authored outside a containing Assembly's namespace that need to address placed instances should inherit this `occurrence_context` shape.

### 4. Direct cross-project endpoint policy: NO

Per the target-Type-governs precedent from [ADR/0013](0013-relationship-type-allocates-to.md). `depicts` targets engineering deliverable Objects (Part / Assembly / Component); cross-project documentation routes through the local Component Binding Object. Same posture as `allocates_to`'s cross-project opt-out.

Schema rejects `project_scope` on `depicts` endpoints. Cross-project documentation use case is well-served by Drawing → local Component → upstream Part — no semantic gap.

### 5. Multiple `depicts` records per Drawing — permitted; no primary flag

A Drawing may carry multiple `depicts` records (typical for system-level layout drawings). Each record has its own stable `id` and may carry a different `binding` mode. No record-level "primary subject" flag in seed; consumer-policy convention (or `design_intent:` records anchored to the relationship id) carries primary-subject semantics if needed.

### 6. View / region qualifier — DEFERRED

The seed `depicts` is whole-Object or whole-occurrence trace. View / region semantics (cross-section plane definition; callout bounding rectangle; exploded-view transform; coverage percent) deferred to Schema Change Note when use case shape stabilizes. Authoring rationale via `design_intent:` records (anchored to the depicts relationship by id) covers working state until structured machinery lands.

### 7. Optional record properties

Minimal seed per [ADR/0009 §5](0009-relationship-type-satisfies.md#5-optional-record-properties--minimal-in-seed):

| Field | Required | Notes |
|---|---|---|
| `id` | REQUIRED | Stable local id per [S0 commitment 4](../TruthModelSchema.md). |
| `name` | optional | Mutable human-readable label. |
| `type` | REQUIRED | Constant `"depicts"`. |
| `binding` | REQUIRED | `"float"` \| `"fixed"`. Default Float. |
| `endpoints` | REQUIRED | Single-entry array per Decision §1. |
| `endpoints[0].occurrence_context` | OPTIONAL | Per Decision §3 Variant B; mandatory when `occurrence_ref` present. |
| `endpoints[0].occurrence_ref` | OPTIONAL | Per Decision §3 Variant B; mandatory when `occurrence_context` present. |
| `fact_provenance`, `fact_uncertainty` | optional | S1 annotations per [S3 commitment 4](../TruthModelSchema.md). |

No `view:`, no `region:`, no `coverage_percent` — all deferred per Decision §6.

### 8. Eventability, release materialization, bundle bump

**Eventability** inherited from [ADR/0009 §6](0009-relationship-type-satisfies.md#6-eventability-release-materialization-bundle-bump): `relationship_created`, `relationship_changed`, `relationship_retired`. `_changed` fires on target re-target, occurrence_context / occurrence_ref edit, binding flip.

**Release materialization:**

- Every endpoint in a released Drawing Revision carries `revision_id` (terminal target's Revision) per [S2 commitment 8](../TruthModelSchema.md).
- For occurrence-qualified targets: `occurrence_context.revision_id` ALSO materialized (the Assembly Revision used to resolve the occurrence path).
- Float bindings materialize to Fixed at release; working sidecar preserves authoring intent per [S3 commitment 12](../TruthModelSchema.md).

**Bundle bump:** **v0.14.0 → v0.15.0**, MINOR additive per [ADR/0003 §11](0003-schema-governance.md). New `relationship/depicts.schema.json`. Eighth occupant of `relationship/` (after `satisfies`, `composed_of`, `mated_to`, `derived_from`, `refines`, `allocates_to`, `parameter_expression`).

### 9. Validation rules (Layer 2)

- Source Object Type == Drawing.
- Target Object Type ∈ {Part, Assembly, Component}.
- Endpoint UUID resolves locally.
- For Fixed bindings: `revision_id` REQUIRED on target endpoint.
- **Occurrence-qualification coupling:** `occurrence_context` and `occurrence_ref` are both present or both absent. Hard-fail at write if only one is present.
- **For occurrence-qualified targets:**
  - `occurrence_context.object_uuid` resolves to an Object whose Type is `Assembly`. Hard-fail if Component or other Type.
  - `occurrence_ref` resolves inside `occurrence_context.object_uuid`'s `composed_of` namespace per [ADR/0010 §3](0010-relationship-type-composed-of.md) occurrence-path rules.
  - Terminal resolved Object Type ∈ {Part, Assembly, Component}.
  - `endpoint.object_uuid` equals the terminal resolved Object's UUID. Hard-fail on mismatch.
- **In released Drawing Revisions:**
  - Every endpoint carries `revision_id`.
  - For occurrence-qualified targets: `occurrence_context.revision_id` ALSO carried.
  - Retrieved Assembly Revision's `composed_of` path resolves to the recorded terminal Object UUID at the recorded path. Hard-fail on any mismatch.
- Cross-project endpoints: NONE permitted directly. Schema rejects `project_scope` on any `endpoints[]` field.
- **Component-target authority guardrail:** if `depicts` target is a Component, the Drawing's local `attachment:` records own the local-Drawing-payload integrity; the Component's upstream binding owns the upstream catalog-item integrity. Two integrity anchors are distinct; documented in Decision §2 for authoring guidance (no schema-enforceable check, but called out in ADR text and Glossary).

## Worked sidecar examples

### Example 1 — Object-only target on a Part

A Drawing depicting the reusable Part definition (typical detail drawing).

```yaml
# In DWG-000017 (drive bracket detail drawing)
object:
  uuid: "0193abcd-aaaa-7700-9fff-111111111111"
  type: "Drawing"
  number: "DWG-000017"
  lifecycle: "in_work"
  schema_version: "0.15.0"

drawing:
  title: "Drive bracket — detail drawing"
  sheet_size: "A3"
  scale: "1:2"
  projection_type: "third_angle"

attachment:
  - id: "att_source_dwg"
    role: "source_authoring"
    media_type: "image/vnd.dwg"
    vault_path: "vault:drawings/DWG-000017/source.dwg"
    content_hash: "sha256:..."

relationship:
  - id: "rel_depicts_bracket_part"
    name: "Documents drive bracket Part definition"
    type: "depicts"
    binding: "float"
    endpoints:
      - object_uuid: "0193-P-000023-..."    # the drive bracket Part definition
        # No occurrence_context / occurrence_ref — Variant A; documents reusable definition.
```

### Example 2 — Object-only target on a Component (catalog-Part documentation)

A Drawing documenting a catalog motor that the consumer project adopted as a local Component. The Drawing's `attachment:` is a locally-annotated copy of the vendor datasheet; the Component's `catalog_ref` carries the upstream binding.

```yaml
# In DWG-000023 (motor catalog datasheet — locally annotated)
object:
  uuid: "0193abcd-bbbb-7800-9aaa-222222222222"
  type: "Drawing"
  number: "DWG-000023"
  lifecycle: "released"
  schema_version: "0.15.0"

drawing:
  title: "Drive motor — annotated catalog datasheet"
  sheet_size: "A4"
  scale: "NTS"
  projection_type: "third_angle"

attachment:
  - id: "att_source_pdf"
    role: "source_authoring"
    media_type: "application/pdf"
    vault_path: "vault:drawings/DWG-000023/annotated.pdf"
    content_hash: "sha256:..."        # local Drawing payload integrity

relationship:
  - id: "rel_depicts_motor_component"
    name: "Documents drive motor Component"
    type: "depicts"
    binding: "float"
    endpoints:
      - object_uuid: "0193-C-000017-..."    # local Component C-000017 (motor)
        # No occurrence_context / occurrence_ref — Variant A; depicts the Component definition itself.
```

The local annotated PDF is in `vault:drawings/DWG-000023/annotated.pdf`; its integrity anchor is the Drawing's `attachment.content_hash`. The upstream catalog motor (the actual datasheet from the vendor) is referenced through the Component `C-000017`'s `catalog_ref` upstream binding (per [ADR/0014](0014-object-type-component.md)). The `depicts` relationship is the trace link.

### Example 3 — Occurrence-qualified target (detail view of one bolt in a fastener pattern)

A Drawing showing a detail view of one specific bolt occurrence in a multi-bolt pattern within an Assembly. Uses `occurrence_context` to anchor the resolver.

```yaml
# In DWG-000045 (detail view of third bolt in M8 fastener pattern)
object:
  uuid: "0193abcd-cccc-7900-9bbb-333333333333"
  type: "Drawing"
  number: "DWG-000045"
  lifecycle: "in_work"
  schema_version: "0.15.0"

drawing:
  title: "Detail view — third M8 bolt in fastener pattern"
  sheet_size: "A4"
  scale: "5:1"
  projection_type: "third_angle"

attachment:
  - id: "att_source_dwg"
    role: "source_authoring"
    media_type: "image/vnd.dwg"
    vault_path: "vault:drawings/DWG-000045/detail.dwg"
    content_hash: "sha256:..."

relationship:
  - id: "rel_depicts_bolt_3"
    name: "Detail view of third M8 bolt occurrence in drive assembly"
    type: "depicts"
    binding: "float"
    endpoints:
      - object_uuid: "0193-P-000019-..."         # the M8 bolt Part definition (terminal cross-check)
        occurrence_context:
          object_uuid: "0193-ASM-000007-..."     # the drive assembly (resolver starting Object)
          # revision_id absent in working Float; pinned at release.
        occurrence_ref: "rel_composed_bolt_3"   # path inside the drive assembly's composed_of namespace
        # revision_id absent in working Float; pinned at release.
```

At release, both `occurrence_context.revision_id` (the drive Assembly's released Revision used to resolve the path) and the terminal `revision_id` (the M8 bolt Part's released Revision) are materialized.

## Consequences

- **Eighth relationship type lands.** Named relationship-type catalogue from [ADR/0009 §3](0009-relationship-type-satisfies.md#3-direct-cross-project-endpoint-policy--permit-with-float-semantics-owned-here) is now operationally complete except for two specialized future ones: `derived_geometry_from` (awaits FreeCAD Domain Adapter scope) and `verifies` (awaits TestProcedure per-Type ADR).
- **Closes ADR/0005 §11 / ADR/0007 §11 pre-declarations.** Both ADRs' relationship-participation tables anticipated `depicts | Drawing → Part/Assembly | binary | trace_graph`; ADR/0018 realizes them. Component is added additively in the same bundle bump.
- **First explicit `occurrence_context` shape.** Sets the precedent for any future source-anchored trace relationship whose source lacks implicit composition visibility into placed-instance targets. Future trace relationships authored outside a containing Assembly's namespace should inherit this shape.
- **Component target authority guardrail.** Drawing of a Component documents the local Binding Object's identity and approved upstream binding — Drawing's `attachment.content_hash` and Component's upstream `revision_content_hash` / etc. are distinct integrity anchors connected by the `depicts` trace link.
- **Schema bundle bump.** Active bundle moves v0.14.0 → v0.15.0. New `relationship/depicts.schema.json`. Eighth occupant of `relationship/`.
- **Glossary additions.** [Glossary.md](../Glossary.md) v0.19: new `depicts` entry; small `Drawing` entry touch-up noting realized `depicts` participation.
- **SystemState updates.** Recent Pattern Changes entry. Pattern Catalogue Applies-to edits on existing rows (Source-anchored asymmetric binary serialization; Direct-binding) to include the now-landed trace family relationships (`derived_from`, `refines`, `allocates_to`, `depicts`) — these were previously listed as "future" and are now actual. No new Pattern Catalogue row.
- **Wedge readiness for documented-deliverable scenarios.** A Wedge variant with `Part + Requirement + satisfies + Drawing + depicts + allocates_to(Requirement → Drawing)` is now schema-feasible. Documentation deliverables are first-class.
- **`derived_geometry_from` and `verifies` remain.** The two specialized future relationships from ADR/0009 §3's enumeration; each awaits its own prerequisite (FreeCAD Domain Adapter scope; TestProcedure Type ADR respectively).
