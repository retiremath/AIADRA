---
name: adr-0014-object-type-component
status: accepted
date: 2026-05-19
supersedes: none
superseded_by: none
resolves: []
---

# ADR/0014 — Object Type: Component

## Status

**Accepted** — 2026-05-19. Fourth Object Type after Part / Requirement / Assembly; first **External pointer Object** (Binding lifecycle) operationalization of the pattern named in [TruthModelSchema commitment 5](../TruthModelSchema.md) and framed in [ADR/0008 §3](0008-cross-project-object-identity.md). First arc to exercise the [SystemState §3 "AIADRA Core hosts nothing"](../SystemState.md#3-coherence-checklist) Coherence Checklist item as a load-bearing proactive check. Sets the namespace adoption template for future Binding Object Types (SoftwareModule, Electrical component, MaterialSpec-like). Also carries additive relationship endpoint Type extensions: `composed_of`, `mated_to`, and `allocates_to` now accept Component as target — closing deferrals from [ADR/0010 §1](0010-relationship-type-composed-of.md), [ADR/0011 §1](0011-relationship-type-mated-to.md), and [ADR/0013 §4](0013-relationship-type-allocates-to.md) respectively.

## Context

[ADR/0008 §3 line 90](0008-cross-project-object-identity.md) explicitly named Component as a future per-Type ADR: *"Component is the canonical Binding Type for physical / procurement catalog items — standard parts, off-the-shelf components, supplier-cataloged items. Component as a full Object Type is the subject of a subsequent per-Type ADR."* That subsequent ADR is this one. The previous three arcs (20260519-2/3 — `derived_from`/`refines`, `allocates_to`) progressively narrowed the deferral set; ADR/0014 closes the load-bearing Component-as-Binding-Object case.

Discussion trail in [`Docs/Discussions/20260519/20260519-4/`](../Discussions/20260519/20260519-4/). [Codex1](../Discussions/20260519/20260519-4/Codex1.md) produced four blockers — (a) target-artifact scope incomplete (relationship endpoint extensions needed in this bundle bump, not deferred); (b) `upstream_ref` overloaded across discriminator cases, risking pseudo-canonical supplier identity in `project_scope`; (c) missing release semantics for Component-owned `published_ref` mirroring; (d) invalid `satisfies` target direction — and five non-blocking refinements. All absorbed in [Claude2](../Discussions/20260519/20260519-4/Claude2.md). [Codex2](../Discussions/20260519/20260519-4/Codex2.md) sign-off with no further findings.

Three pressures converge:

1. **First External pointer Object operationalization.** The Promotion Rule's [commitment 5 named non-disqualifier pattern](../TruthModelSchema.md) — *External pointer Object (Binding lifecycle)* — is realized concretely here. Subsequent Binding Object Types (SoftwareModule, Electrical component) inherit this ADR's template for namespace adoption, discriminator-specific upstream binding shape, and release-integrity discipline.
2. **AIADRA Core hosts nothing — first real test.** [Manifesto P11](../Manifesto.md): AIADRA Core operates no hosted registry, no live coordination, no federation. Component is the natural temptation to violate this: a cross-project catalog binding could be designed as "Core hosts the catalog index." This ADR explicitly resists that. The local Component IS the registry from the consumer's perspective; upstream resolution is project-local transport (`locator_hint`, `datasheet_url`), never Core-mediated.
3. **Boundary precision over symmetry.** Codex's review forced sharp boundaries — `project_scope` is `aiadra_catalog`-only (not retrofitted onto supplier identities); `published_ref` mirroring carries explicit `upstream_fact_ref` with release-time chain validation; `satisfies` source/target direction respects [ADR/0009 §1](0009-relationship-type-satisfies.md) without backdoor target expansion. Boundary precision is the load-bearing trait for a first-of-its-kind Binding Type.

## Promotion Rule walk

Component passes the [Promotion Rule capability test](../TruthModelSchema.md) via the **External pointer Object (Binding lifecycle)** named non-disqualifier pattern from [commitment 5](../TruthModelSchema.md):

- **C1 — Independent identity.** The consumer project's Component `C-000017` has a *local* UUID + Number stable across its lifetime in this project. Upstream re-numbering, supersession, or even disappearance does not invalidate the consumer's Component identity.
- **C2 — Independent lifecycle.** Component progresses on its own lifecycle (`in_work` → `released` → `retired`) independent of the upstream Object's lifecycle. The consumer decides when to release a Component (commit to using this catalog item) and when to retire it (cease using). Upstream lifecycle changes surface as Float-binding staleness signals, not as automatic Component state changes.
- **C3 — Independent referenceability.** Local relationships (`composed_of` target, `mated_to` endpoint, `allocates_to` target) point at the *local* Component UUID. Component is the addressable local proxy for cross-project use.
- **C4 — Independent provenance / approval.** Component carries its own adoption / approval decision in the consumer project — typically a procurement / engineering-review sign-off, distinct from upstream authoring approval.

D1–D7 disqualifier walk:

- **D1 (Derived-from-another-Object).** N/A — Component *references* an external Object via a Binding pointer; not *derived from* a local Object. The Promotion Rule's commitment 5 explicitly named the External pointer pattern as a non-disqualifier.
- **D2–D6.** Not applicable to Binding Objects.
- **D7 (Derived view).** N/A — Component is the authoritative consumer-side record of an adoption decision, not a generated report.

Conclusion: **Component is a first-class Object Type via the External pointer Object pattern.**

## Alternatives Considered

### Endpoint patterns (Binding shape)

**A1. Single overloaded `upstream_ref` block carrying both AIADRA-project and supplier identity.** Claude1's original proposal.

> **Rejected.** `project_scope.project_id` is AIADRA-catalog-specific stable identity per [ADR/0008 §5](0008-cross-project-object-identity.md). Forcing supplier/custom upstreams through `project_scope` would make URL/vendor identity pseudo-canonical AIADRA project identity — exactly what ADR/0008's identity-locator split prevented. The single-block shape made non-AIADRA upstreams look like degraded AIADRA projects.

**A2. Discriminator-specific top-level blocks (`catalog_ref` / `supplier_ref` / `custom_ref`); `oneOf` schema constraint.** *Chosen — see Decision §3.* Each binding shape is a distinct schema; the discriminator selects which is present. `project_scope` is `aiadra_catalog`-only; supplier identity is its own tuple.

### Component as relationship `satisfies` target

**B1. Permit Component as `satisfies` target.** Claude1's misstatement.

> **Rejected.** `satisfies` per [ADR/0009 §1](0009-relationship-type-satisfies.md) has target Type `Requirement`. Component cannot be a `satisfies` target without superseding ADR/0009's endpoint constraint, which has no Wedge justification.

**B2. Defer Component as `satisfies` source.** *Chosen.* Component as `satisfies` source (a catalog item claiming it satisfies a Requirement) is plausible but requires explicit ADR/0009 endpoint-constraint extension. Deferred to a future Schema Change Note when production case surfaces.

### Component `published_ref` shape

**C1. Local stable id only; no upstream pointer.**

> **Rejected.** Without upstream mapping, a Component `published_ref` becomes a free-floating local fact whose authority cannot be validated. Mates targeting this `published_ref` cannot validate at release.

**C2. Local stable id + `upstream_fact_ref` + release-time chain validation.** *Chosen — see Decision §5.* Component `published_ref` records are *local stable aliases* with explicit upstream mapping. Release materializes the upstream binding, then validates each local `published_ref`'s `upstream_fact_ref` against the materialized upstream Revision.

### Float vs Fixed default for supplier / custom

**D1. Float-by-default for all discriminator cases, with content-hash resolver required at release.** *Chosen — see Decision §3.*

**D2. Fixed-only seed for `supplier_datasheet` / `custom`.**

> **Rejected.** Float-default matches the broader binding pattern; release-time integrity is preserved by requiring a content-hash resolver in project policy. Forcing Fixed-only in seed would push authoring-time friction onto common cases (a consumer wants to track "supplier's current datasheet of record" during evaluation; pinning a specific datasheet hash is what release time is for).

### Scope: bundle bump granularity

**E1. ADR/0014 lands `Component.schema.json` only; defers `composed_of` / `mated_to` / `allocates_to` endpoint extensions to follow-up Schema Change Notes.**

> **Rejected.** Codex's argument lands: Component existing but unable to be targeted by product-structure relationships defeats the entire point. Same arc, same bundle bump.

**E2. ADR/0014 owns all four schema changes in the same bundle bump.** *Chosen.* `Component.schema.json` (new) + endpoint Type union extensions in `composed_of`, `mated_to`, `allocates_to` (additive). Single MINOR additive bump.

### Hosted-federation hooks

**F1. Add optional `registry_url` / `federation_hint` fields to permit Core-hosted federation later.**

> **Rejected.** Violates [Manifesto P11](../Manifesto.md). Federation lives in consuming projects; AIADRA Core ships the pattern, not the infrastructure. `locator_hint` (catalog) and `datasheet_url` (supplier) are non-authoritative transport hints — never canonical identity — and explicitly not coordinated by Core.

## Decision

### 1. Promotion

Component is a first-class Object Type via the External pointer Object (Binding lifecycle) named non-disqualifier pattern, per the Promotion Rule walk above. Inherits seed-Type ceremony per the [amended Promotion Rule commitment 6](../TruthModelSchema.md).

### 2. Number prefix

`C-NNNNNN` — six-digit zero-padded sequential allocation from the Reservation file per [ADR/0004](0004-number-allocation.md). AIADRA Core default; per-project override allowed per [S2.5 commitment 10](../TruthModelSchema.md). Six-digit width matches Part / Requirement / Assembly for consistency.

### 3. TypeSpecific `component:` block — discriminator-specific upstream binding shapes

Singleton TypeSpecific block (Requirement's singleton precedent per [ADR/0006](0006-object-type-requirement.md)). The `sourcing_discriminator` field selects which sub-shape is present; the schema enforces a `oneOf` constraint on the binding block.

**Top-level fields:**

```yaml
component:
  sourcing_discriminator: "aiadra_catalog | supplier_datasheet | custom"   # REQUIRED enum
  binding_mode: "float | fixed"                                            # REQUIRED; default "float"
  # Exactly one of catalog_ref | supplier_ref | custom_ref, per discriminator
```

**`aiadra_catalog`** sub-shape:

```yaml
catalog_ref:
  project_scope:
    project_id: "string"           # REQUIRED — stable AIADRA project identity per ADR/0008 §5
    locator_hint: "string"         # OPTIONAL — non-authoritative transport / discovery hint
  object_uuid: "string"            # REQUIRED — upstream Object UUID within its project
  revision_id: "string"            # REQUIRED for Fixed; absent for working Float; pinned at release
  revision_content_hash: "string"  # REQUIRED for Fixed per ADR/0008 §6; pinned at release for materialized Float
```

**`supplier_datasheet`** sub-shape:

```yaml
supplier_ref:
  manufacturer: "string"             # REQUIRED — supplier identity
  part_number: "string"              # REQUIRED — supplier's catalog identifier
  datasheet_url: "string"            # OPTIONAL — non-authoritative transport hint; never canonical identity
  datasheet_content_hash: "string"   # REQUIRED for Fixed; pinned at release for materialized Float
```

**`custom`** sub-shape:

```yaml
custom_ref:
  descriptor: "string"      # REQUIRED — opaque, project-policy-driven identifier
  content_hash: "string"    # REQUIRED for Fixed; pinned at release for materialized Float
```

**Critical boundaries:**

- `project_scope` is **`aiadra_catalog`-only**. Supplier and custom upstreams never use `project_scope` — preserving [ADR/0008 §5](0008-cross-project-object-identity.md)'s identity-locator split.
- `locator_hint` and `datasheet_url` are explicitly **non-authoritative transport / discovery hints**. AIADRA Core does not resolve either; resolution is consumer-project-local per [Manifesto P11](../Manifesto.md).
- The discriminator drives a hard schema `oneOf`: the binding sub-block must match the discriminator value; mismatches hard-fail at write validation.

**Float binding semantics, per discriminator:**

- **`aiadra_catalog` Float:** resolves to the upstream Object's *current released Revision*. Release materialization is staleness-intolerant per [ADR/0009 §3](0009-relationship-type-satisfies.md#3-direct-cross-project-endpoint-policy--permit-with-float-semantics-owned-here) pattern — resolve, validate `object.type`, pin `revision_id` + `revision_content_hash`, hard-fail otherwise.
- **`supplier_datasheet` Float:** allowed *only if* the consumer project defines a deterministic resolver that produces a `datasheet_content_hash` at release. Release hard-fails if Float resolves to no hash. Practical implication: a consumer wanting "current datasheet of record" must wire a fetch + hash policy; without one, use Fixed.
- **`custom` Float:** allowed *only if* the consumer project defines a `content_hash` resolver. Same release hard-fail discipline. Opaque `descriptor` semantics stay project-local; the integrity anchor is uniform across discriminators.

### 4. Namespace set — five of Part's seven plus singleton `component:`

Component selectively adopts Part's seven-namespace template ([ADR/0005](0005-object-type-part.md)). Selective-adoption precedent per [ADR/0006](0006-object-type-requirement.md) (Requirement carries five of seven).

| Namespace | In Component seed? | Notes |
|---|---|---|
| `parameter:` | YES | Datasheet parameters (e.g., `voltage_v`, `current_a`, `length_mm`). Canonical-units-at-field-name discipline per [ADR/0010 §2](0010-relationship-type-composed-of.md). |
| `design_intent:` | YES | *Why* this Component was chosen; substitution constraints; anchors by id to records in this Component's `relationship:` namespace. |
| `feature:` | NO | Component is not internally designed. Features belong to the upstream Object. |
| `relationship:` | YES | Component participates as target (predominant) per Decision §6. Component as relationship source: permitted but rare. |
| `published_ref:` | YES | Local stable aliases mirroring upstream published_ref records; carries `upstream_fact_ref`; release-time chain validation per Decision §5. |
| `geometry_ref:` | YES, with `derived_export` role only | Derived geometry (mesh / STEP / preview) carried locally for visualization. No `authoring_geometry` role — Component does not author canonical kernel geometry. |
| `material:` | NO | Supplier-declared materials belong upstream. Consumer-side material overrides deferred to Schema Change Note when production case surfaces. |

Plus the new singleton `component:` block (Decision §3). **Five of seven namespaces + one new singleton.**

The `source:` namespace is *not* adopted — `source:` is Requirement-specific per [ADR/0006](0006-object-type-requirement.md). Component's "where this data comes from" is captured by `sourcing_discriminator` + the discriminator-specific `*_ref` block.

### 5. Component `published_ref` mirroring + release semantics

Component-owned `published_ref` records are **local stable aliases with explicit upstream mapping**:

```yaml
published_ref:
  - id: "pr_mount_face_a"           # REQUIRED — local stable id per S0 commitment 7
    name: "Mounting face A"         # optional
    upstream_fact_ref: "published_ref:upstream_pr_id"  # REQUIRED — points into upstream Object's published_ref namespace
    # S1 annotations (fact_provenance, fact_uncertainty) per usual
```

The `upstream_fact_ref` field is new with this ADR. Format: `"published_ref:<upstream-stable-id>"` — referencing an id inside the resolved upstream Object's `published_ref` namespace.

**Release invariants** (added to validation rules in Decision §9):

1. **Upstream binding must be Fixed or successfully materialized** in the Component's released Revision record before any mate targeting that Component's local `published_ref` can validate.
2. **Every Component-published_ref `upstream_fact_ref` must resolve** to an existing `published_ref` id in the materialized upstream Revision. Hard-fail at release if mapping fails.
3. **Released mate targeting a Component-owned `published_ref`** validates the chain: mate endpoint → Component local `published_ref` id → Component's pinned upstream Revision → upstream `published_ref` id existence. Any broken link is a release hard-fail.
4. **Working-state Float Component**: locality-tier-appropriate per [ADR/0001 §6](0001-storage-substrate.md); mate validation may report stale-cached or UNRESOLVED diagnostics; never hard-fails until release.
5. **Released Component Revision stores**: the local `published_ref` records (with `upstream_fact_ref` values) AND the materialized upstream binding (Fixed `*_ref` with `revision_id` + `revision_content_hash` or `*_content_hash`). Future reads reconstruct the full chain.

This is the Component-specific application of [SystemState §3 "Released cross-Object geometry"](../SystemState.md#3-coherence-checklist) — the local Component cannot become a stable-looking wrapper around an unstable upstream geometry surface.

### 6. Relationship participation + endpoint-schema extensions

Component participates per the [ADR/0008 §4](0008-cross-project-object-identity.md) Binding-Object-as-target rule:

| Relationship | Component participation | Schema change in this bundle |
|---|---|---|
| `composed_of` | **target** — an Assembly may compose a Component (closes [ADR/0010 §1](0010-relationship-type-composed-of.md) deferral) | `relationship/composed_of.schema.json` target Type union: `Part \| Assembly` → `Part \| Assembly \| Component` (additive) |
| `mated_to` | **endpoint** — mate endpoints may resolve to Component-owned `published_ref` records (closes [ADR/0011 §1](0011-relationship-type-mated-to.md) deferral) | `relationship/mated_to.schema.json` endpoint Type union extended to allow Component-owned occurrence published_ref endpoints (additive) |
| `allocates_to` | **target** — a Requirement may be allocated to a Component (closes [ADR/0013 §4](0013-relationship-type-allocates-to.md) cross-project allocation deferral via local Binding) | `relationship/allocates_to.schema.json` target Type union: `Part \| Assembly` → `Part \| Assembly \| Component` (additive) |
| `satisfies` | **NOT in seed** | No change. Component as `satisfies` source deferred to future Schema Change Note. |
| `derived_from` / `refines` | **NOT in seed** | No change. Requirement → Requirement only per [ADR/0012](0012-relationship-types-derived-from-and-refines.md). |

All schema changes are MINOR additive: existing records continue to validate; new records gain Component-target capability.

Component as relationship *source*: permitted but unusual at seed scale. A Component authoring its own `composed_of` (a sub-Component) is a forward-looking case for hierarchical catalog items; allowed by schema, rare in practice.

### 7. AIADRA Core hosts nothing — explicit constraint walk

[Manifesto P11](../Manifesto.md) — load-bearing for this ADR, first arc to exercise the [Coherence Checklist "AIADRA Core hosts nothing"](../SystemState.md#3-coherence-checklist) item proactively.

- **No central catalog registry.** Component does not require a Core-hosted catalog index. Each consumer project resolves upstream independently.
- **No hosted resolution service.** Cross-project resolution is filesystem / Git / HTTP / VCS-mediated by consumer tooling. AIADRA Core ships Vault Adapter–style local-resolution scaffolding ([Glossary "Vault Adapter"](../Glossary.md)) but does NOT host the resolution service.
- **No live coordination.** Components do not subscribe to upstream change feeds. Staleness is detected at fetch (locality-tier-appropriate) and at release (staleness-intolerant). No long-lived coordination handles.
- **No hosted approval / governance.** Component adoption / approval is consumer-project governance (PR review, ECO, signed tag) — not Core-operated.
- **No registry-shaped fields in schema.** `locator_hint` (catalog) and `datasheet_url` (supplier) are non-authoritative transport hints, explicitly marked as such. No `registry_url`, `federation_hint`, or similar shapes (Alternative F1 rejected above).

The temptation to violate P11 here is real and was explicitly resisted at multiple decision points. If federation infrastructure is later wanted, it lives as a separate *project consuming AIADRA*, not inside AIADRA Core.

### 8. Lifecycle, eventability, Revision schema, bundle bump

**Lifecycle** independent per Promotion C2. States: `in_work` → `released` → `retired`. The consumer project owns each transition. Release materializes any Float binding to Fixed atomically per [S2 commitment 11](../TruthModelSchema.md).

**Eventability** per [S3 commitment 5](../TruthModelSchema.md): `component_created`, `component_changed`, `component_released`, `component_retired`. `_changed` fires on author intent change (binding_mode flip, upstream re-target, descriptor edit, namespace record add/remove/edit). Release materialization is NOT a `_changed` event per the broader [S3 commitment 12](../TruthModelSchema.md) pattern. Retirement is tombstoning.

**Revision schema** per [S2 commitment 1](../TruthModelSchema.md). Each Component Revision is a separate immutable artifact at canonical path `revisions/<object-uuid>/<revision-id>.yaml`, carrying the full reconstructable release-time snapshot per [S2 commitment 13](../TruthModelSchema.md) — singleton `component:` + five namespaces frozen at release. The release-time `*_ref` (whichever discriminator) is materialized to its Fixed form with all integrity-anchor fields present.

**Bundle bump:** **v0.10.0 → v0.11.0**, MINOR additive per [ADR/0003 §11](0003-schema-governance.md). Changes in this bump:

- NEW: `sidecar/Component.schema.json` (new Object Type sidecar schema).
- NEW: `object.type = "Component"` discriminator value at the bundle level.
- NEW: `C-NNNNNN` Number prefix mapping at the bundle level per [S2.5 commitment 10](../TruthModelSchema.md).
- ADDITIVE: `relationship/composed_of.schema.json` target Type union extension (Component added).
- ADDITIVE: `relationship/mated_to.schema.json` endpoint Type union extension (Component-owned published_ref endpoints permitted).
- ADDITIVE: `relationship/allocates_to.schema.json` target Type union extension (Component added).

No existing artifacts break. Existing records remain valid against the bumped bundle.

**ADR ceremony** per the [amended Promotion Rule commitment 6](../TruthModelSchema.md) — substantial new pattern declarations (the External pointer Object pattern operationalized; discriminator-specific upstream binding shape; mirrored `published_ref` with release-time chain validation; AIADRA Core hosts nothing proactively walked). Pattern-setting at the Object Type level.

### 9. Validation rules (Layer 2)

- `object.type == "Component"`.
- `component:` singleton block present; matches schema.
- `component.sourcing_discriminator` ∈ {`aiadra_catalog`, `supplier_datasheet`, `custom`}.
- Exactly one of `component.catalog_ref` / `component.supplier_ref` / `component.custom_ref` present, matching the discriminator value.
- `component.binding_mode` ∈ {`float`, `fixed`}; default `float`.
- For `catalog_ref` Fixed: `revision_id` + `revision_content_hash` REQUIRED.
- For `supplier_ref` Fixed: `datasheet_content_hash` REQUIRED.
- For `custom_ref` Fixed: `content_hash` REQUIRED.
- For Float (any discriminator): working-state behavior locality-tier-appropriate per [ADR/0001 §6](0001-storage-substrate.md); release MUST materialize to the Fixed-equivalent integrity anchors (resolve + pin); hard-fail at release if no resolver / no hash producible.
- Each `published_ref` record has `id` + `upstream_fact_ref`.
- Released Component Revision: every endpoint of every relationship targeting this Component (composed_of, mated_to, allocates_to) carries `revision_id` resolving to this Component Revision per [S2 commitment 8](../TruthModelSchema.md).
- Released Component Revision: upstream binding is Fixed (materialized) with all integrity-anchor fields present per discriminator.
- Released Component Revision: every local `published_ref.upstream_fact_ref` resolves to an existing `published_ref` id in the materialized upstream Revision. Hard-fail at release if any mapping breaks.

## Worked sidecar example

A `Component` sidecar for a motor sourced from an internal AIADRA catalog project, with one local `published_ref` mirror and a few datasheet parameters. (Other discriminators differ in the `*_ref` block; namespaces shape unchanged.)

```yaml
object:
  uuid: "0193abcd-cccc-7000-9999-eeeeeeeeeeee"
  type: "Component"
  number: "C-000017"
  lifecycle: "in_work"
  schema_version: "0.11.0"
  fact_provenance: { category: "human_input" }
  fact_uncertainty: "verified"

component:
  sourcing_discriminator: "aiadra_catalog"
  binding_mode: "float"
  catalog_ref:
    project_scope:
      project_id: "aiadra-catalog:internal-motors-v3"
      locator_hint: "git@github.internal:motors/catalog.git"   # non-authoritative
    object_uuid: "0193mnop-aaaa-7bcd-8000-111111111111"
    # No revision_id / revision_content_hash — Float in working state; pinned at release.

parameter:
  - id: "param_continuous_torque"
    name: "Continuous torque rating"
    value_nm: 12.0
    fact_provenance: { category: "supplier_datasheet_or_catalog" }
    fact_uncertainty: "verified"
  - id: "param_rated_voltage"
    name: "Rated voltage"
    value_v: 24.0
    fact_provenance: { category: "supplier_datasheet_or_catalog" }
    fact_uncertainty: "verified"

design_intent:
  - id: "di_substitution_constraint"
    statement: "Substitutable only with motors providing continuous_torque >= 12 Nm at <= 24 V; consult ME team before swap."
    anchors: ["component"]

published_ref:
  # Local stable alias for the upstream's mounting-face published_ref.
  - id: "pr_mount_face_a"
    name: "Mounting face A"
    upstream_fact_ref: "published_ref:mount_face_a_upstream"
    fact_provenance: { category: "external_release" }
    fact_uncertainty: "verified"

geometry_ref:
  - id: "gr_preview_mesh"
    role: "derived_export"
    path: "vault:motor_preview_mesh_v3.obj"
    content_hash: "sha256:b0c1d2e3f4a5..."
    derived_from_object: "external"   # upstream binding owns the source
    fact_provenance: { category: "derived_for_preview" }

relationship:
  # Component may carry its own relationships, though typically targets in the seed.
  # Example: this Component is empty here; it's referenced FROM Assemblies via composed_of and
  # FROM Requirements via allocates_to, which live on the source sidecars per source-anchoring.
```

A parent Assembly composing this Component would carry the `composed_of` record (per [ADR/0010](0010-relationship-type-composed-of.md)):

```yaml
# In ASM-000007 (drive assembly):
relationship:
  - id: "rel_composed_motor"
    type: "composed_of"
    binding: "float"
    occurrence:
      instance_name: "primary_drive_motor"
      transform:
        position_mm: [0, 0, 50]
        quaternion_xyzw: [0, 0, 0, 1]
    endpoints:
      - object_uuid: "0193abcd-cccc-7000-9999-eeeeeeeeeeee"   # LOCAL Component C-000017
```

A consumer Requirement allocated to this Component carries the `allocates_to` record (per [ADR/0013](0013-relationship-type-allocates-to.md)):

```yaml
# In REQ-000058 (drive torque requirement):
relationship:
  - id: "rel_alloc_to_motor_component"
    type: "allocates_to"
    binding: "float"
    endpoints:
      - object_uuid: "0193abcd-cccc-7000-9999-eeeeeeeeeeee"   # LOCAL Component C-000017
```

Both the Assembly's `composed_of` and the Requirement's `allocates_to` target the *local* Component UUID. The Component's `catalog_ref` carries the upstream binding. Local relationships stay local; cross-project semantics live entirely inside the Component's TypeSpecific payload per the [ADR/0008 §4](0008-cross-project-object-identity.md) Binding-Object-as-target rule.

A `supplier_datasheet` variant differs only in the `component:` block:

```yaml
component:
  sourcing_discriminator: "supplier_datasheet"
  binding_mode: "fixed"
  supplier_ref:
    manufacturer: "Acme Motors Inc"
    part_number: "AM-24-12NM-001"
    datasheet_url: "https://acme.example/datasheets/AM-24-12NM-001-rev3.pdf"  # non-authoritative
    datasheet_content_hash: "sha256:7d2c..."
```

A `custom` variant:

```yaml
component:
  sourcing_discriminator: "custom"
  binding_mode: "fixed"
  custom_ref:
    descriptor: "internal-prototype-2026-batch-A"
    content_hash: "sha256:9a1b..."
```

## Consequences

- **First External pointer Object Type lands.** ADR/0014 operationalizes the [Promotion Rule commitment 5](../TruthModelSchema.md) named non-disqualifier pattern for the first time. Sets the template for future Binding Object Types (SoftwareModule, Electrical component, MaterialSpec-like).
- **Three relationship endpoint deferrals closed.** [ADR/0010 §1](0010-relationship-type-composed-of.md) (`composed_of` Component target), [ADR/0011 §1](0011-relationship-type-mated-to.md) (`mated_to` Component endpoint), [ADR/0013 §4](0013-relationship-type-allocates-to.md) (cross-project `allocates_to` via Component) are all unblocked by the additive schema extensions in this bundle bump. Those ADRs' overall status remains `accepted`; the additive extensions don't supersede their decisions.
- **AIADRA Core hosts nothing — proactive Coherence Checklist exercise.** First arc to exercise this item load-bearingly; the design walks past several P11-violation temptations explicitly (Alternative F1 rejected; `locator_hint` / `datasheet_url` explicitly non-authoritative; no registry-shaped fields).
- **Schema bundle bump.** Active bundle moves v0.10.0 → v0.11.0. NEW `sidecar/Component.schema.json` + `C-NNNNNN` prefix mapping. ADDITIVE extensions to three existing `relationship/*.schema.json` files. No existing artifacts break.
- **Glossary additions.** [Glossary.md](../Glossary.md) v0.15: new `Component` entry; small update to the existing `Part` entry's "Distinguished from Component (purchased / sourced item, *deferred*)" wording — Component is no longer deferred.
- **SystemState additions.** One new Pattern Catalogue row (*External pointer Object pattern operationalized*); Recent Pattern Changes entry; Current Front advances (seed catalogue grows from three to four — Part, Requirement, Assembly, Component).
- **Component as `satisfies` source deferred.** A future Schema Change Note (or ADR/0009 endpoint-constraint extension) can land Component as `satisfies` source if production case surfaces. Not in this bundle.
- **Wedge readiness for catalog adoption.** Cross-project responsibility-assignment is now schema-supported via the Component target. The basic Wedge (one Part → one Requirement) does not exercise this; an extended Wedge with one catalog Component plus a Requirement allocated to it is now schema-feasible.
- **Future Binding Object Types template.** SoftwareModule's per-Type ADR can largely follow ADR/0014's shape, with discriminator-specific shapes adapted to Git-source-of-truth semantics (commit-hash binding instead of upstream Revision UUID).
