---
name: adr-0011-relationship-type-mated-to
status: accepted
date: 2026-05-18
supersedes: none
superseded_by: none
resolves: []
---

# ADR/0011 — Relationship Type: `mated_to`

## Status

**Accepted** — 2026-05-18. Third relationship-type ADR; first **geometric / topological** relationship per [S3 commitment 2](../TruthModelSchema.md#2-three-kinds-of-relationships-are-explicitly-recognized)'s three-kind taxonomy; first **undirected** multi-endpoint relationship (legitimate pattern break from ADR/0009 / 0010's source-anchored implicit-source pattern); first **indirect-binding** relationship (no relationship-level `binding` field; delegated to occurrence-path resolution per [ADR/0010 §3](0010-relationship-type-composed-of.md)); first **multi-endpoint stable-id** relationship per [S0 commitment 7](../TruthModelSchema.md#7-list-addressability-rule); first cycle-class **`undirected_constraint_graph`** activation at runtime. Pins three new pattern declarations on top of ADR/0009 / 0010's previous five (undirected multi-endpoint serialization; indirect-binding; multi-endpoint stable ids) for a total of eight seed catalogue patterns. Supersedes [ADR/0010 §3](0010-relationship-type-composed-of.md)'s worked-example placeholder `mated_to` records (which predated this ADR's schema).

## Context

The seed catalogue's relationship-endpoint declarations ([ADR/0005 §11](0005-object-type-part.md), [ADR/0006 §12](0006-object-type-requirement.md), [ADR/0007 §11](0007-object-type-assembly.md)) named `mated_to` as feature ↔ feature, Assembly-owned, cycle policy `undirected_constraint_graph`. The first two relationship-type ADRs ([ADR/0009](0009-relationship-type-satisfies.md) `satisfies`, [ADR/0010](0010-relationship-type-composed-of.md) `composed_of`) established five pattern declarations for source-anchored asymmetric binary relationships and direct-binding semantics. `mated_to` is the first relationship type that legitimately breaks these patterns — symmetric multi-endpoint with binding delegated through occurrence paths.

Three pressures converge here:

1. **Mate-type taxonomy.** Standard mechanical CAD mates (coincident, concentric, parallel, perpendicular, distance, angle, tangent, planar) are universal vocabulary across SolidWorks / Creo / Onshape / FreeCAD. The seed pins the static set. `lock` was initially proposed but doesn't fit the feature-pair endpoint model (it locks two whole occurrences via transform freezing); deferred to future Schema Change Note when its endpoint shape is concretely settled. Kinematic mates (gear / path / cam / universal / screw) belong with the simulation / motion semantics layer; less-universal mates (`symmetric`, `width`, `profile_*`) deferred until concrete use case surfaces.
2. **Undirected multi-endpoint serialization.** ADR/0009 / 0010 established implicit-source + single-entry-target serialization for source-anchored asymmetric binary relationships. `mated_to` is symmetric — neither endpoint is semantically privileged as "source"; both must be serialized. The owning Assembly is the storage carrier (per [S3 commitment 3](../TruthModelSchema.md#3-relationships-are-source-anchored) source-anchoring) but not a semantic endpoint. This break is the explicit-rather-than-discover-by-accident pattern declaration Codex2 from arc 10 anticipated.
3. **Indirect binding and endpoint addressability.** A mate between two placed instances depends on the `composed_of` records that placed them; the target Revision of each endpoint is determined by occurrence-path resolution per ADR/0010 §3, not by a relationship-level `binding` field. The endpoint `revision_id`, if present, is a cross-check against the resolved Revision (hard-fail on mismatch), never authority. Combined with the multi-endpoint serialization, this requires endpoint-level stable identity per [S0 commitment 7](../TruthModelSchema.md#7-list-addressability-rule) — endpoint-local annotations and rebinds need stable addresses since position-as-identity collides with non-semantic order.

The discussion trail in [`Docs/Discussions/20260518-11/`](../Discussions/20260518-11/) carries the full alternatives reasoning. Codex1 produced four hard blockers (`lock` doesn't fit feature-endpoint model; raw selector encoded as fake `fact_ref` overload; binding semantics composition with `occurrence_ref`; solver status needs release rule) plus four refinements; all absorbed. Codex2 caught a new schema-contract issue surfaced in the absorption (endpoint list members carrying independent annotations without stable identity, colliding with S0 commitment 7); absorbed via Option A endpoint stable ids. Codex3 green-lit Claude3's absorption.

## Alternatives Considered

### Mate-type taxonomy scope

**A1. Include `lock` in seed taxonomy.** Original Claude1 draft; nine mate types.

> **Rejected.** `lock` is fundamentally different — it locks two whole occurrences via transform freezing, not a feature pair. Forcing arbitrary `published_ref`s to satisfy the seed's feature-pair endpoint model either invents fake anchors or hides the actual locked payload (relative occurrence transform). Caught by Codex1 §1.

**A2. Eight-type seed; `lock` deferred to future Schema Change Note.** *Chosen — see Decision §2.* Seed: `coincident`, `concentric`, `parallel`, `perpendicular`, `distance`, `angle`, `tangent`, `planar`. `lock` returns when its endpoint shape (likely occurrence-frame + `locked_transform` per ADR/0010's transform pattern) is concretely settled.

**A3. Include kinematic mates** (`gear`, `path`, `cam`, `universal`, `screw`).

> **Rejected.** Kinematic mates depend on motion / simulation semantics that AIADRA's simulation layer has not yet pinned. Belong to future simulation-layer ADR or post-Wedge work.

**A4. Include `symmetric` / `width` / profile mates.**

> **Deferred.** Useful future additions but not blocking. Schema Change Notes when concrete production use case surfaces, per [Promotion Rule commitment 9](../TruthModelSchema.md#9-catalogue-work-is-use-case-driven).

### Endpoint shape

**B1. `fact_ref` overloaded with sentinel `selector:<inline>` for raw selectors.** Original Claude1 draft.

> **Rejected.** Overloads `fact_ref`'s S0 address semantics with a sentinel string saying "look in another field." Breaks S0 addressing cleanliness. Caught by Codex1 §2.

**B2. `oneOf` endpoint shape — `fact_ref` (S0 address) OR `selector` (S3 layered object), mutually exclusive.** *Chosen — see Decision §3.* Keeps `fact_ref` as a real S0 address (seed-mandated `published_ref:<id>` for release-bound cross-Object); `selector` is the layered topological selector per [S3 commitment 9](../TruthModelSchema.md#9-geometric--topological-endpoints-use-a-layered-selector). Mutual exclusion makes the release rule obvious: released cross-Object mates use `fact_ref: published_ref:<id>`; raw `selector` endpoints are working / transitional with `requires_validation` per S3 §11 narrow exception.

### Binding semantics composition

**C1. `mated_to.binding` field with Float / Fixed + endpoint `revision_id`.** Original Claude1 draft; competing-with-`composed_of`-binding semantics.

> **Rejected.** Creates ambiguity — for Assembly-owned mates, `occurrence_ref` resolves through `composed_of` (Float / Fixed / materialized), and the mate's own binding either duplicates or conflicts with that resolution. Codex1 §3 caught the load-bearing precedence gap.

**C2. Keep `mated_to.binding`; declare precedence with `composed_of` as authority; endpoint `revision_id` as cross-check.** Codex1's first proposed option.

> **Rejected.** The field has no independent semantic content for Assembly-owned mates (resolution is determined by `composed_of`); keeping it as a precedence-cross-check field adds complexity without benefit.

**C3. Drop `mated_to.binding` entirely; binding delegated to address mechanism.** *Chosen — see Decision §5.* Codex1's simpler alternative + Codex2's confirmation. Each endpoint's effective binding is determined by the address mechanism: occurrence-path resolution for Assembly-owned mates; the carrier Part's Revision for Part-owned within-Part mates. Endpoint `revision_id`, if present, is a cross-check (hard-fail on mismatch with occurrence-path resolution), never authority. This declares the **indirect-binding pattern** (companion to ADR/0009 / 0010's direct-binding pattern).

### Release rule for unsatisfied mates

**D1. All over-constraint as warning; not release-blocking.** Original Claude1 draft.

> **Rejected.** Conflates "redundant but satisfiable over-constraint" (warning OK) with "contradictory / unsatisfied mates" (canonical-truth violation). Caught by Codex1 §4. Solver inconsistency at release time is exactly the kind of silent canonical truth violation the architecture has been carefully avoiding.

**D2. Distinguish redundant-satisfiable (warning) from contradictory-unsatisfied (hard-fail release).** *Chosen — see Decision §8.* Released mates must evaluate true against the materialized occurrence transforms; contradictory mates hard-fail release unless `requires_validation` explicitly invoked. Cycle policy `undirected_constraint_graph` (closed loops permitted) is preserved.

### Endpoint identity (post-Claude2 absorption)

**E1. Endpoint-local annotations with positional addressing.** Claude2 absorption — endpoint array entries carry `fact_uncertainty`, `revision_id`, `selector` while position is non-semantic.

> **Rejected.** Collides with [S0 commitment 7](../TruthModelSchema.md#7-list-addressability-rule) list-addressability rule: list members that carry annotations / can be changed independently / can be reordered need a stable key or id. Caught by Codex2.

**E2. Atomic unordered endpoint pair; move all annotations relationship-level.** Codex2 Option B.

> **Rejected.** Loses endpoint-level diagnostic precision. A mate where one endpoint is clean `published_ref` and the other is raw imported selector should be able to mark the imported endpoint specifically as `requires_validation`, not the whole mate.

**E3. Endpoint stable local ids; endpoint order non-semantic; endpoint-local annotations addressable.** *Chosen — see Decision §3.* Codex2 Option A. Endpoint ids enable diagnostic precision, repair event targeting per [S3 commitment 14](../TruthModelSchema.md#14-ai-driven-repair-as-a-first-class-layer-3-obligation), S1 four-level walk addressability, and duplicate-mate detection (which ignores ids and compares normalized endpoint content). Declared as the **multi-endpoint stable-id pattern** (sixth seed catalogue pattern declaration).

## Decision

Eight decisions. Three load-bearing pattern declarations (undirected multi-endpoint serialization; indirect-binding; multi-endpoint stable ids); five inherit ADR/0009 / 0010 patterns plus geometric-relationship extensions.

### 1. Endpoint Type constraints, arity, source-anchoring — undirected multi-endpoint pattern

**Source-anchoring (storage):** record lives in the owning Assembly's `relationship:` namespace per [S3 commitment 3](../TruthModelSchema.md#3-relationships-are-source-anchored). For Part-owned within-Part mates (rare exception per [ADR/0005 §11](0005-object-type-part.md)), the Part is the storage carrier.

**Endpoint Type constraints (per-endpoint):** each endpoint targets a feature or `published_ref` on a Part or Assembly:

- For Assembly-owned mates (the common case): both endpoints carry `occurrence_ref` (per [ADR/0010 §3](0010-relationship-type-composed-of.md)) identifying which placed Part / Assembly instance, plus `fact_ref` (typically `published_ref:<id>`) OR `selector` (layered topological selector with `requires_validation`).
- For Part-owned within-Part mates (rare): endpoints reference features within the owning Part; no `occurrence_ref` (single-Object scope).

**Arity:** binary at the semantic layer. **Serialization: two-entry `endpoints` array — both endpoints explicit, neither semantically privileged.** This is the legitimate pattern break from ADR/0009 / 0010's source-anchored implicit-source pattern.

**Pattern declaration (new — undirected multi-endpoint serialization):**

> Undirected relationship types serialize all semantic endpoints explicitly. The owning Object is the storage carrier selected by the relationship type's ownership rule; it is not automatically a semantic endpoint.

ADR/0011's pattern is **undirected multi-endpoint serialization**. ADR/0009 / 0010's source-anchored implicit-source pattern remains the seed for asymmetric source-anchored binary relationships (`satisfies`, `composed_of`, future `derived_from`, `refines`, `allocates_to`). A future asymmetric multi-endpoint relationship (`parameter_expression`'s source-plus-many shape) will declare its own pattern.

### 2. Mate-type taxonomy — eight static mate types in seed

The seed `mated_to` schema discriminates by `mate_type` enum with eight static mechanical CAD mate types:

| `mate_type` | Semantics | Mate-type-specific properties |
|---|---|---|
| `coincident` | Two features (faces / axes / points / planes) coincide. | `aligned: bool` REQUIRED — orientation flag for axes / faces. |
| `concentric` | Two axes (or two circular features) share an axis. | `aligned: bool` REQUIRED — axes point the same way. |
| `parallel` | Two features (faces / axes / planes) are parallel. | `aligned: bool` REQUIRED — same-direction vs opposite-direction normals / axes. |
| `perpendicular` | Two features are perpendicular. | no extra properties. |
| `distance` | Fixed distance between two features. | `value_mm: number` REQUIRED (canonical millimeters per [ADR/0010 §2](0010-relationship-type-composed-of.md) pattern); finite, `>= 0`. `aligned: bool` REQUIRED — signed offset direction. |
| `angle` | Fixed angle between two features. | `value_deg: number` REQUIRED (canonical degrees); finite, `0 <= value_deg <= 180`. `aligned: bool` REQUIRED — angle direction sense. |
| `tangent` | Two features in tangent contact. | no extra properties. |
| `planar` | Two planes coplanar. | `aligned: bool` REQUIRED. |

**Excluded from seed** (deferred to future Schema Change Notes):

- **`lock`** — different endpoint model (occurrence-frame, not feature pair). Future Schema Change Note when endpoint shape is settled.
- **Kinematic mates** (`gear`, `path`, `cam`, `universal`, `screw`) — depend on simulation / motion semantics.
- **Less-universal mechanical mates** (`symmetric`, `width`, profile mates) — Schema Change Notes when concrete production use case surfaces.

**Per-mate-type schema variation:** the `relationship/mated_to.schema.json` uses JSON Schema's `oneOf` / discriminator pattern keyed on `mate_type`. Each mate type's required / optional properties are validated per its specific schema. The mate-type-specific property invariants (Decision §7's record properties table) are enforced at validation time.

### 3. Endpoint shape — `oneOf` (`fact_ref` OR `selector`); endpoint stable ids — multi-endpoint stable-id pattern

Each endpoint takes one of two forms; mutually exclusive (`oneOf` in schema). Both forms carry a stable local `id`.

**Form A — Published-ref endpoint** (preferred; release-capable):

| Field | Required | Notes |
|---|---|---|
| `id` | REQUIRED | Stable local id; format `^[a-z][a-z0-9_]*$`; not semantically privileged. Unique within this record's endpoints array. |
| `occurrence_ref` | REQUIRED for Assembly-owned; ABSENT for Part-owned within-Part | Per [ADR/0010 §3](0010-relationship-type-composed-of.md) syntax (prefix-free bare-id slash-separated; binding-aware resolution). |
| `fact_ref` | REQUIRED | S0 fact address per [S0 commitment 6](../TruthModelSchema.md#6-cross-object-references); seed-mandated value `published_ref:<id>` for release-bound cross-Object endpoints. |
| `revision_id` | optional cross-check | Cross-check against occurrence-path resolved terminal Revision per Decision §5; hard-fail on mismatch; not authority. |
| `fact_provenance`, `fact_uncertainty` | optional | S1 annotations addressable at `endpoints:<id>.<field>` per S1 four-level walk. |

**Form B — Inline-selector endpoint** (working / transitional):

| Field | Required | Notes |
|---|---|---|
| `id` | REQUIRED | Same format / role as Form A. |
| `occurrence_ref` | REQUIRED for Assembly-owned; ABSENT for Part-owned within-Part | Same as Form A. |
| `selector` | REQUIRED | S3 layered selector object per [S3 commitment 9](../TruthModelSchema.md#9-geometric--topological-endpoints-use-a-layered-selector). `selector_predicate` REQUIRED for AIADRA-authored references per S3 §9. |
| `fact_uncertainty` | REQUIRED with value `"requires_validation"` | Per S3 §11 narrow exception. |
| `fact_provenance` | optional | S1 annotation. |

**Mutual exclusion:** `fact_ref` and `selector` are mutually exclusive per JSON Schema `oneOf` discriminator. Schema rejects records carrying both or neither.

**Pattern declaration (new — multi-endpoint stable-id pattern):**

> Multi-endpoint relationships use endpoint stable ids. For relationship types where the `endpoints` array has two or more entries, each endpoint carries a stable local `id` per [S0 commitment 7](../TruthModelSchema.md#7-list-addressability-rule) list-addressability rule. Single-endpoint relationships (`satisfies`, `composed_of`) continue to use positional addressing (endpoints[0]) without ids — single-member lists collapse list-addressability into record-level addressability trivially.

Endpoint ids are storage / addressability labels, not source / target roles. The relationship remains undirected per Decision §1.

**S1 four-level walk addressability examples:**

| Address | Resolves to |
|---|---|
| `relationship:<rid>` | the whole mate record |
| `relationship:<rid>.endpoints:<eid>` | endpoint `<eid>` |
| `relationship:<rid>.endpoints:<eid>.fact_uncertainty` | endpoint-`<eid>` uncertainty (level-1 S1 override) |
| `relationship:<rid>.fact_uncertainty` | mate-level S1 default (level-3 fallback) |
| `object.fact_uncertainty` | envelope-level S1 default (level-4 fallback) |

**Within-Part mate scoping:**

> The published-ref release rule (Form A preference; release-time hard-fail on raw `selector` without `requires_validation`) applies to **cross-Object mates only** — per [S3 commitment 11](../TruthModelSchema.md#11-published-reference-ports-are-first-class-addressable-records-owned-by-objects)'s "release-bound cross-Object geometric relationships" wording. Within-Part mates (Part-owned per [ADR/0005 §11](0005-object-type-part.md); both endpoints reference features within the carrier Part) MAY use Form A or Form B at release without invoking the S3 §11 exception. The within-Part target is the same Object as the carrier; its Revision is the carrier's Revision.

### 4. Undirected serialization invariants

Per Decision §1, `mated_to` records serialize both endpoints explicitly. The owning Assembly stores the record (carrier role); neither endpoint is semantically privileged.

**Endpoint ordering:** the array is ordered for serialization purposes but **not semantically meaningful**. Adapters / Layer-2 validators MAY canonicalize ordering for normalization (e.g., sort by `(occurrence_ref, fact_ref)` lexicographically); mates do not change behavior under ordering changes. The schema does not enforce ordering.

**Duplicate-mate detection:**

> Two `mated_to` records with identical `mate_type` + normalized endpoint content (set of `(occurrence_ref, fact_ref OR selector_canonical_hash)` pairs, **ignoring endpoint ids and array order**) + identical mate-type-specific properties are duplicate. Layer-2 validator MAY emit a warning; NOT hard validation failure. Diagnostics SHOULD report both record-level ids AND the matched endpoint-content normalization, so a human can retire one deliberately.

Endpoint ids are storage / addressability labels, not semantic content; duplicate authoring using different endpoint id labels is still duplicate authoring.

### 5. Cycle policy, self-policy; binding dropped — indirect-binding pattern

**Cycle policy:** `undirected_constraint_graph`. Per [S3 commitment 13](../TruthModelSchema.md#13-per-type-cycle-and-graph-class-policy). **Closed loops are permitted** — three Parts mated in a triangle is a valid constraint pattern; the constraint solver determines whether the geometry is realizable, not the cycle gate. Over-constraint (the solver concern) is distinct from cycles; release-time handling per Decision §8.

**Self-policy:** `self_forbidden`. A feature cannot be mated to itself — two distinct `(occurrence_ref, fact_ref OR selector)` tuples in the endpoints array. Same-Object two-feature mates (a flexible Part's two ends pinned together) remain legitimate; the self-forbidden rule applies to identical-endpoint-tuple records, not same-Object records.

**Binding — DROPPED from seed schema:**

> `mated_to` does NOT carry a `binding` field. Each endpoint's effective binding is determined by the address mechanism:
> - **Assembly-owned mates:** the endpoint's `occurrence_ref` resolves through ADR/0010 §3's binding-aware algorithm. The `composed_of` segment's binding determines which Part / sub-Assembly Revision the endpoint is inside.
> - **Part-owned within-Part mates:** both endpoints reference features within the carrier Part; there is no separate target Revision. Binding is structurally undefined and need not be expressed.

> Endpoint `revision_id`, if present, is a **cross-check** against the occurrence-path's resolved terminal Revision; validation hard-fails on mismatch. Endpoint `revision_id` is never authority.

**Pattern declaration (new — indirect-binding):**

> Indirect-binding relationships delegate target-Revision binding to the address mechanism (e.g., `occurrence_ref` resolving through `composed_of`). The relationship type does NOT carry its own `binding` field; binding is inherited from the resolved address. Endpoint `revision_id`, if present, is a cross-check against the resolved address's terminal Revision (hard-fail on mismatch), never authority.

Contrasts with the **direct-binding** pattern (ADR/0009 / 0010) — `satisfies`, `composed_of` carry their own `binding` field (default Float; release materializes Fixed) because their endpoints reference whole Objects directly. `mated_to`'s endpoints reference features through occurrence paths or within-Part addresses; binding is meaningful only at the address-mechanism level.

### 6. Direct cross-project endpoint policy — NO (engineering-structure default)

Per [ADR/0008 §4](0008-cross-project-object-identity.md) engineering-structure default. `mated_to` endpoints target local Objects only. A consumer Assembly mating a catalog Part's feature MUST route through a local Component first; the mate references the Component's `published_ref`, not the catalog Part directly.

**Negative case explicit:**

> Direct cross-project `mated_to` endpoints are forbidden. Catalog-Part features used in consumer-Assembly mates flow through a local Component's `published_ref` namespace, never directly. This preserves local approval boundary, where-used locality, and procurement / supplier override capacity for catalog reuse.

Same engineering-structure exclusion as [ADR/0010 §4](0010-relationship-type-composed-of.md) `composed_of`. Contrast with [ADR/0009 §3](0009-relationship-type-satisfies.md) `satisfies`'s trace-relationship direct-external-endpoint opt-in.

### 7. Record properties

Relationship-level fields:

| Field | Required | Notes |
|---|---|---|
| `id` | REQUIRED | Stable local id per [S0 commitment 4](../TruthModelSchema.md#4-hybrid-within-artifact-addressing). |
| `name` | optional | Mutable human-readable label. |
| `type` | REQUIRED | Constant `"mated_to"`. |
| `mate_type` | REQUIRED | Enum per Decision §2: `coincident \| concentric \| parallel \| perpendicular \| distance \| angle \| tangent \| planar`. |
| `endpoints` | REQUIRED | Two-entry array per Decision §3 (each entry Form A or Form B with stable id). |
| `value_mm` | conditional | REQUIRED ⇔ `mate_type == "distance"`; FORBIDDEN otherwise. Finite; `>= 0`. |
| `value_deg` | conditional | REQUIRED ⇔ `mate_type == "angle"`; FORBIDDEN otherwise. Finite; `0 <= value_deg <= 180`. |
| `aligned` | conditional | REQUIRED on `coincident`, `concentric`, `parallel`, `distance`, `angle`, `planar`. FORBIDDEN on `perpendicular`, `tangent`. |
| `fact_provenance`, `fact_uncertainty` | optional | S1 annotations addressable at `relationship:<id>.<field>` per S1 four-level walk; level-3 fallback for endpoint-local fields. |

No `binding` field per Decision §5. No `solver_priority` / `tolerance` / `mate_properties:` sub-object — flat conditional fields per Codex1 §8. Mate-type-specific endpoint orientation overrides beyond `aligned` deferred to future Schema Change Notes.

### 8. Eventability, release materialization, bundle bump

**Eventability** per [S3 commitment 5](../TruthModelSchema.md#5-relationships-have-create--change--retire-events): `relationship_created`, `relationship_changed`, `relationship_retired`. `_changed` fires on:

- Endpoint rebind (different `occurrence_ref`, `fact_ref`, or `selector` on either endpoint). Event field target: `endpoints:<eid>.<field>`.
- `mate_type` change — **only when the authoring intent is reclassification of the same constraint** (e.g., a planar-coincident mate being relabeled as a `planar` mate when authoring tooling distinguishes). Semantic replacement (a coincident mate becoming a distance mate) should retire the old record and create a new one, mirroring [S3 commitment 14](../TruthModelSchema.md#14-ai-driven-repair-as-a-first-class-layer-3-obligation)'s topological-repair-vs-semantic-rebind distinction.
- Mate-type-specific property change (`value_mm`, `value_deg`, `aligned`).

No binding-switch event (no `binding` field per Decision §5). Release-time materialization is NOT a `_changed` event per [S3 commitment 12](../TruthModelSchema.md#12-float-vs-fixed-binding-mode-is-explicit-per-relationship). Retirement is tombstoning.

**Release-time materialization:**

- Every endpoint in a released Revision record carries `revision_id`, materialized from the occurrence path's resolved terminal Revision per [ADR/0010 §3](0010-relationship-type-composed-of.md).
- Cross-check rule: endpoint `revision_id` present in working state must match materialized Revision; hard-fail on mismatch.
- **Cross-Object release-bound endpoints use Form A** (`fact_ref: published_ref:<id>`); Form B (raw `selector`) hard-fails unless `requires_validation` per the narrow S3 §11 exception.
- **Within-Part released mates** may use Form A or Form B without invoking the exception per Decision §3 within-Part scoping.
- Occurrence-path validation per ADR/0010 §3 binding-aware algorithm: every segment resolves in the materialized Revision graph.
- **Mate-satisfaction validation:** every `mated_to` record's declared constraint must evaluate true against the materialized occurrence transforms. Categorization:

| Solver outcome | Working state | Release |
|---|---|---|
| Satisfiable + uniquely solved. | clean. | clean. |
| Over-constrained + still satisfiable (redundant constraints; all true). | warning. | warning, NOT blocking. |
| Under-constrained + deterministic placement. | warning. | warning, NOT blocking. |
| Unsatisfied / contradictory mates. | warning + diagnostic. | **HARD FAIL** unless `requires_validation` invoked. |
| Solver failure / inconsistent constraints. | warning + diagnostic. | **HARD FAIL** unless `requires_validation` invoked. |

The "released as clean engineering truth" gate is: every materialized `mated_to` evaluates true against the materialized occurrence transforms. Layer-2 validator performs this check at the release transaction per [S2 commitment 11](../TruthModelSchema.md#11-release-transactions-are-atomic-across-all-canonical-artifacts).

**Validation rules** (Layer 2 per [ADR/0001 §4](0001-storage-substrate.md) sidecar/event invariant):

- `type == "mated_to"`.
- `mate_type` ∈ seed enum values (8 types).
- `endpoints` is a two-entry array.
- Each endpoint carries stable local `id` matching `^[a-z][a-z0-9_]*$`; ids unique within the record's array.
- Two endpoints are distinct (`self_forbidden` per Decision §5).
- For Assembly-owned mates: each endpoint carries `occurrence_ref`; resolves per ADR/0010 §3 binding-aware algorithm.
- For Part-owned within-Part mates: endpoints carry no `occurrence_ref`; both endpoints reference features within the owning Part.
- Endpoint shape is Form A (`fact_ref`) OR Form B (`selector`); mutually exclusive.
- Form B endpoints carry `fact_uncertainty: "requires_validation"`.
- Mate-type-specific property invariants per Decision §7's table.
- Endpoint `revision_id`, if present, matches occurrence-path resolved terminal Revision (hard-fail on mismatch).
- Direct cross-project endpoints REJECTED per Decision §6.
- At release: cross-Object endpoints use Form A (`fact_ref: published_ref:<id>`) unless Form B carries `requires_validation`.
- At release: every mate's declared constraint evaluates true against materialized occurrence transforms; contradictory mates hard-fail.

**Bundle bump:** **v0.7.0 → v0.8.0**, MINOR additive per [ADR/0003 §11](0003-schema-governance.md). New `relationship/mated_to.schema.json`; third occupant of the `relationship/` directory (after [ADR/0009](0009-relationship-type-satisfies.md)'s `satisfies` and [ADR/0010](0010-relationship-type-composed-of.md)'s `composed_of`). No existing artifacts to break.

**ADR ceremony** per the [amended Promotion Rule commitment 6](../TruthModelSchema.md#6-promotion-ceremony) — first geometric / topological relationship-type ADR; first undirected multi-endpoint relationship; first indirect-binding pattern; first multi-endpoint stable-id pattern; first cycle-class `undirected_constraint_graph` activation; pins 8-mate seed taxonomy. Multiple substantial pattern-setting decisions qualify.

## Pattern declarations summary (seed catalogue, post-ADR/0011)

Eight seed patterns governing relationship-type schemas:

| Pattern | Declared by | Applies to |
|---|---|---|
| Source-anchored asymmetric binary serialization (implicit source + single serialized target) | ADR/0009 §1, ADR/0010 §1 | `satisfies`, `composed_of`; future `derived_from`, `refines`, `allocates_to` |
| Undirected multi-endpoint serialization (all semantic endpoints serialized; owning Object is storage carrier) | ADR/0011 §1 | `mated_to`; future undirected geometric relationships |
| Asymmetric multi-endpoint serialization | future ADR (`parameter_expression`) | `parameter_expression` |
| Direct-binding (relationship-level Float/Fixed; default Float; release materializes Fixed) | ADR/0009 §4, ADR/0010 §5 | `satisfies`, `composed_of`; future direct-binding relationships |
| Indirect-binding (no relationship-level binding; delegated to address mechanism; endpoint `revision_id` as cross-check) | ADR/0011 §5 | `mated_to`; future indirect-binding relationships (`parameter_expression` cross-Assembly likely) |
| Multi-endpoint relationships use endpoint stable ids | ADR/0011 §3 | `mated_to`; future multi-endpoint relationships |
| Engineering-structure direct-external-endpoint NO default | ADR/0008 §4 | `composed_of`, `mated_to`; future structural relationships |
| Trace-relationship direct-external-endpoint opt-in (with Float external semantics) | ADR/0009 §3 | `satisfies`; future trace relationships |

The catalogue is now broad enough to support the remaining seed relationship-type ADRs (`derived_from`, `refines`, `allocates_to`, `parameter_expression`, `derived_geometry_from`, `depicts`) without further substantial pattern additions.

## Worked sidecar example

```yaml
object:
  uuid: "0193abcd-1234-7890-..."
  type: "Assembly"
  number: "ASM-000042"
  lifecycle: "in_work"
  schema_version: "0.8.0"
  fact_provenance: { category: "human_input" }
  fact_uncertainty: "verified"

relationship:
  # composed_of records from ADR/0010 — omitted (rel_composed_plate, rel_composed_bolt_1..4, rel_composed_wrist)

  # Concentric mate, Form A endpoints, descriptive endpoint ids
  - id: "rel_mate_bolt_1_to_plate_NE"
    type: "mated_to"
    mate_type: "concentric"
    endpoints:
      - id: "bolt_side"
        occurrence_ref: "rel_composed_bolt_1"
        fact_ref: "published_ref:pub_bolt_axis"
      - id: "plate_side"
        occurrence_ref: "rel_composed_plate"
        fact_ref: "published_ref:pub_mounting_hole_axis_NE"
    aligned: true

  # Coincident mate, generic end_a / end_b labels
  - id: "rel_mate_bolt_1_head_to_plate_top"
    type: "mated_to"
    mate_type: "coincident"
    endpoints:
      - id: "end_a"
        occurrence_ref: "rel_composed_bolt_1"
        fact_ref: "published_ref:pub_bolt_head_under_face"
      - id: "end_b"
        occurrence_ref: "rel_composed_plate"
        fact_ref: "published_ref:pub_plate_top_face"
    aligned: true

  # Distance mate using nested occurrence path from ADR/0010 §3
  - id: "rel_mate_servo_gap"
    type: "mated_to"
    mate_type: "distance"
    endpoints:
      - id: "servo_face"
        occurrence_ref: "rel_composed_wrist/rel_composed_servo"
        fact_ref: "published_ref:pub_servo_mount_face"
      - id: "plate_face"
        occurrence_ref: "rel_composed_plate"
        fact_ref: "published_ref:pub_plate_boss_top_face"
    value_mm: 5.0
    aligned: true

  # Angle mate with endpoint revision_id cross-checks
  - id: "rel_mate_left_arm_angle"
    type: "mated_to"
    mate_type: "angle"
    endpoints:
      - id: "arm_pivot"
        occurrence_ref: "rel_composed_left_arm"
        fact_ref: "published_ref:pub_pivot_axis"
        revision_id: "B"                          # cross-check against composed_of resolved Revision
      - id: "base_ref"
        occurrence_ref: "rel_composed_base"
        fact_ref: "published_ref:pub_reference_axis"
        revision_id: "A"                          # cross-check
    value_deg: 45.0
    aligned: true

  # Form B (raw selector) endpoint with endpoint-local S1 level-1 uncertainty
  - id: "rel_mate_bolt_1_to_imported"
    type: "mated_to"
    mate_type: "concentric"
    endpoints:
      - id: "bolt_axis"
        occurrence_ref: "rel_composed_bolt_1"
        fact_ref: "published_ref:pub_bolt_axis"
        # endpoint inherits envelope-level fact_uncertainty ("verified") via S1 level 4
      - id: "imported_hole_axis"
        occurrence_ref: "rel_composed_imported_chassis"
        selector:                                  # raw S3 layered selector
          topology_ref_id: "toporef_chassis_mount_hole_axis_2"
          source_feature_id: "feature_imported_hole_2"
          encoded_history: "Face42;:M5;FUS;:T1:2:F"
          selector_predicate: "axis of imported chassis mounting hole 2"
        fact_uncertainty: "requires_validation"   # endpoint-level level-1 override
    aligned: true
```

Demonstrates:

- **Eight-mate seed taxonomy** illustrated across records (concentric, coincident, distance, angle shown; others analogous; no `lock`).
- **Endpoint stable ids** on every entry; descriptive labels where helpful, generic labels otherwise.
- **Form A endpoints** (preferred) on most mates.
- **Form B endpoint** with `requires_validation` on the imported-chassis case; `fact_uncertainty` at endpoint level demonstrates S1 four-level walk (endpoint-level level-1 override; other endpoint inherits envelope level-4 "verified").
- **No `binding` field** on `mated_to` records — endpoint binding inherited from `composed_of` per indirect-binding pattern.
- **Endpoint `revision_id` cross-checks** on the angle mate (validator hard-fails if `composed_of` resolution disagrees).
- **`aligned` REQUIRED** on all six orientation-meaningful mate types; absent on `perpendicular` / `tangent` (not shown but analogous).
- **Value ranges**: `value_mm: 5.0` (>= 0); `value_deg: 45.0` (in `[0, 180]`).
- **Nested occurrence path** `rel_composed_wrist/rel_composed_servo` per ADR/0010 §3 binding-aware resolution.

At release of this Assembly:

- Float bindings (from `composed_of` records) materialize: target endpoints gain `revision_id` from occurrence-path resolution.
- Form A endpoints: `fact_ref` validated as `published_ref:<id>`; cross-check rule applies.
- Form B endpoint with `requires_validation`: permitted under S3 §11 narrow exception.
- Every mate's declared constraint evaluated against materialized occurrence transforms; contradictory mates hard-fail.
- `undirected_constraint_graph` cycle policy: no cycle-failure regardless of mate topology (closed loops permitted).

## Consequences

- **Schema bundle bump.** Active bundle moves v0.7.0 → v0.8.0. New `relationship/mated_to.schema.json` lands in the `aiadra-core` bundle with discriminator-based per-mate-type validation, endpoint `oneOf` shape, endpoint stable id format constraint, mate-type-specific property invariants, value ranges (`value_mm >= 0`; `0 <= value_deg <= 180`), and `aligned` required-where-meaningful enforcement.
- **Glossary update.** [Glossary](../Glossary.md) bumps v0.11 → v0.12 with a new entry for *`mated_to`* citing this ADR; existing *Part* / *Assembly* entries already reference `mated_to` by name.
- **`undirected_constraint_graph` cycle policy operationally active.** Layer-2 validator implementation work to deliver mate-satisfaction validation per Decision §8's release rule. Solver-status categorization (warning vs hard-fail) belongs to Layer-2 implementation.
- **ADR/0010 §3 worked-example placeholder supersession.** ADR/0010's `mated_to` records in worked examples predate this ADR's schema; ADR/0011's endpoint shape (with endpoint stable ids, Form A / Form B split, no `binding` field) supersedes the placeholder shape. ADR/0010's accepted text remains historical record per ADRs-are-immutable-once-accepted convention; ADR/0011's supersession statement is the durable record. Same convention as ADR/0010's supersession of ADR/0007 §2's `relationship:` prefix form.
- **Three new pattern declarations.** Undirected multi-endpoint serialization (Decision §1); indirect-binding (Decision §5); multi-endpoint stable ids (Decision §3). Total of eight seed catalogue patterns; the catalogue is now broad enough for remaining seed relationship-type ADRs.
- **Pattern inheritance for subsequent relationship-type ADRs.** `derived_from`, `refines`, `allocates_to` (trace relationships, asymmetric binary) inherit ADR/0009 / 0010 source-anchored patterns; `parameter_expression` (asymmetric multi-endpoint with cross-Object parameter addresses) will inherit indirect-binding + multi-endpoint stable-id patterns from this ADR plus declare its own asymmetric multi-endpoint serialization; `derived_geometry_from` (likely Part feature → Part `published_ref`; binary directed) inherits direct-binding + source-anchored patterns; `depicts` (Drawing → Part / Assembly) inherits trace patterns when Drawing ADR lands.
- **`lock` deferred** to future Schema Change Note when its occurrence-frame endpoint shape (likely with `locked_transform` per ADR/0010's transform pattern) is concretely settled.
- **Kinematic mates deferred** to simulation / motion semantics layer when that work lands.
- **Less-universal mates (`symmetric`, `width`, profile mates) deferred** to Schema Change Notes when concrete production use case surfaces per [Promotion Rule commitment 9](../TruthModelSchema.md#9-catalogue-work-is-use-case-driven).
- **Solver implementation freedom.** Layer-2 validator implementation has freedom for over-constraint detection algorithms, duplicate-mate normalization, mate-satisfaction evaluation against materialized transforms. ADR/0011 commits to the invariants and release rules, not the algorithms.
- **AP242 / STEP round-trip** — `mated_to` maps to AP242 e3 's `Mate` / `Configuration_Item_Relationship` elements per [S3 commitment 7](../TruthModelSchema.md#7-relationship-types-are-schema-governed-under-adr0003)'s STEP-aware vocabulary. Domain Adapter implementation is Layer 5 work per [S3 commitment 15](../TruthModelSchema.md#15-ap242-external-element-references-round-trip-via-layer-5-domain-adapters-where-ap242-can-represent).
- **Cross-Assembly Binding Object Type for catalog Assembly mates** — same deferral as ADR/0010.
- **`relationship/mated_to.schema.json`** — lives in the `aiadra-core` schema bundle, not in this ADR. The ADR governs decisions; the schema implements them.

## References

- [Manifesto.md](../Manifesto.md) — P3 (UUID identity), P6 (Parameters first, raw geometry last — mates are structural authoring), P7 (provenance + uncertainty on relationship records and endpoints per S1), P9 (layered geometry access — mates compose geometric references at multiple selector layers), P11 (AIADRA Core hosts nothing — bounds direct-cross-project-endpoint NO default).
- [Glossary.md](../Glossary.md) — *Object*, *Part*, *Assembly*, *Revision*, *Released Truth*, *UUID*, *Number*, *`satisfies`*, *`composed_of`*, *`mated_to`* (new entry in Glossary v0.12).
- [TruthModelSchema.md](../TruthModelSchema.md) — S0 commitment 4 (hybrid within-artifact addressing), commitment 6 (cross-Object references), commitment 7 (list-addressability rule — basis for endpoint stable id requirement); S1 commitment 2 (four-level resolver walk — endpoint-local annotations); S2 commitment 8 (cross-Object references with `revision_id`); S3 commitment 2 (three relationship kinds; `mated_to` is geometric / topological), commitment 3 (source-anchored ownership), commitment 5 (relationship events), commitment 9 (layered topological selector — Form B endpoint shape), commitment 11 (published reference ports + release-bound published-ref rule with narrow exception), commitment 12 (Float / Fixed binding), commitment 13 (`undirected_constraint_graph` cycle policy), commitment 14 (AI-driven repair — endpoint targeting via stable ids), commitment 15 (AP242 round-trip).
- [ADR/0001](0001-storage-substrate.md) — Storage substrate. §3 (acceleration cache — reverse where-used; mate-resolution indexing), §4 (sidecar/event invariant — validation fires here), §6 (locality tier and staleness — Float endpoint resolution).
- [ADR/0002](0002-canonical-format.md) — Canonical format. AIADRA YAML Profile for relationship records with endpoint stable ids.
- [ADR/0003](0003-schema-governance.md) — Schema governance. §2 (discriminator — mate_type), §11 (bump ceremony — MINOR additive).
- [ADR/0005](0005-object-type-part.md) — Object Type: Part. §11 (Part is target endpoint via `published_ref` or feature addresses; within-Part constraints may be Part-owned).
- [ADR/0007](0007-object-type-assembly.md) — Object Type: Assembly. §2 (occurrence-qualified endpoint rule — basis for Assembly-owned mate endpoint structure), §11 (Assembly is source / owner for `mated_to`; cycle policy `undirected_constraint_graph`).
- [ADR/0008](0008-cross-project-object-identity.md) — Cross-project Object identity. §4 (engineering-structure direct-endpoint NO default — basis for Decision §6).
- [ADR/0009](0009-relationship-type-satisfies.md) — Relationship Type: `satisfies`. Pattern source for source-anchored asymmetric binary serialization, direct-binding, eventability; ADR/0011 inherits some patterns and legitimately breaks others (undirected multi-endpoint; indirect-binding).
- [ADR/0010](0010-relationship-type-composed-of.md) — Relationship Type: `composed_of`. §2 (transform shape — analogous to potential future `lock` endpoint), §3 (occurrence path syntax — basis for `occurrence_ref` in Assembly-owned mates; binding-aware resolution governs endpoint Revision selection); ADR/0011 supersedes ADR/0010 §3's worked-example placeholder `mated_to` records.
- [OpenQuestions.md](../OpenQuestions.md) — OQ-0007 (Wedge scope adequacy — ADR/0011 unblocks mate-bearing extended Wedge variant; basic Wedge does not strictly need mates).
- Discussion trail (git-ignored, local only): `Docs/Discussions/20260518-11/Claude1.md` → `Codex1.md` → `Claude2.md` → `Codex2.md` → `Claude3.md` → `Codex3.md` — full working-out across two substantive Codex rounds (four hard blockers + one schema-contract issue in absorption, all absorbed) plus a green-light third round.
