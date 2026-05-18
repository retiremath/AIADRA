---
name: adr-0008-cross-project-object-identity
status: accepted
date: 2026-05-18
supersedes: none
superseded_by: none
resolves: [OQ-0016]
---

# ADR/0008 — Cross-Project Object Identity

## Status

**Accepted** — 2026-05-18. Resolves [OQ-0016](../OpenQuestions.md) (cross-project Object identity and reuse semantics), deferred from Ring 0 closure (2026-05-17) and reopened now that the seed catalogue ([Part](0005-object-type-part.md) + [Requirement](0006-object-type-requirement.md) + [Assembly](0007-object-type-assembly.md)) is complete. Lands before the relationship-type ADRs (`composed_of`, `mated_to`, `satisfies`, etc.) per the [Promotion Rule's verdict table](../TruthModelSchema.md#verdict-summary) instruction: "OQ-0016 reopens before relationship taxonomy enumeration completes." Unblocks Component, SoftwareModule, and other candidate-pool Types whose promotion depended on cross-project semantics.

## Context

[Manifesto P3](../Manifesto.md) — "Identity is UUID. Filenames are storage, not truth." — is silent on the cross-project case. Within a project, the UUID is unambiguous identity. Across projects, when Project B reuses a Part originally authored in Project A (a standard M8 bolt, a motor, a board module), what is the identity relationship between the two? [OQ-0016](../OpenQuestions.md) surfaced this gap and deferred resolution until Ring 1's single-project identity model settled.

Ring 1 is now settled. The cumulative context that makes OQ-0016's answer legible:

1. **[S0 commitment 6](../TruthModelSchema.md#6-cross-object-references)** committed cross-Object references to `(project_scope?, object_uuid, fact_ref?)` with `project_scope` as the explicit slot OQ-0016 fills.
2. **[S2 commitment 8](../TruthModelSchema.md#8-cross-object-references-may-include-revision_id-required-in-released-revision-records)** extended that to `(project_scope?, object_uuid, revision_id?, fact_ref?)` for release-bound references.
3. **[Promotion Rule commitment 5](../TruthModelSchema.md#5-two-named-non-disqualifier-patterns)** named two patterns for Objects whose payload or upstream truth lives outside the sidecar:
   - **Attachment-bearing Object** — AIADRA owns meaning; Vault holds bytes.
   - **External pointer Object** — AIADRA owns wrapper or binding; another system owns upstream truth. Explicitly includes Binding lifecycle: "AIADRA owns the lifecycle of the project's adoption of an upstream entity."
4. **Candidate-pool deferrals** — Component, SoftwareModule, Electrical component — all named by the [Promotion Rule's verdict table](../TruthModelSchema.md#verdict-summary) as blocked on OQ-0016.

The Promotion Rule's External pointer Object pattern (Binding lifecycle) IS the catalog-binding shape this ADR needs. The remaining work is to operationalize it: pin the cross-project identity tuple, structure `project_scope`, require integrity for fixed cross-project bindings, and bound the policy so engineering relationships flow through Binding Objects rather than bypass them.

The discussion trail in [`Docs/Discussions/20260518-7/`](../Discussions/20260518-7/) carries the full alternatives reasoning. Codex1 produced twelve findings, all accepted (five load-bearing; seven refinements/confirmations); Codex2 green-lit Claude2's absorption with one wording polish on Decision §4. This ADR pins the result.

## Alternatives Considered

The four options from [OQ-0016](../OpenQuestions.md), re-evaluated against current spine maturity:

### A1. Project-scoped UUIDs, no cross-project link

Reused parts re-authored in each project. No identity relationship between Project A's M8 bolt and Project B's M8 bolt.

> **Rejected.** AIADRA's audience includes the open-source hardware ecosystem ([Manifesto](../Manifesto.md) audience). Ecosystem reuse requires traceability with some form of cross-project link; total re-authoring fragments the ecosystem and discards information engineering teams already produce. Loses ecosystem-level "where else is this M8 bolt used."

### A2. Project-scoped UUIDs + `derived_from` relationship

Each project owns its UUID; `derived_from` relationship carries `(source_project, source_uuid, source_revision)`.

> **Rejected.** Federated-query problem at scale (every consumer must be queried for ecosystem-level where-used). Semantic ambiguity — `derived_from` confuses "we copied this design and evolved it independently" (genuine derivation) with "we pinned to this version" (binding). The two cases need different semantics.

### A3. Global UUID namespace + per-project revision binding

UUID shared across projects; v4-random avoids live coordination.

> **Rejected.** Violates the spirit of "each project owns its truth" ([Manifesto P11](../Manifesto.md)). Global namespace creates implicit ownership questions: who "owns" a globally-identified Object? What if v4 random generation collides (improbable but non-zero across decades)? Cross-project semantic contracts become silent — changing the upstream Object affects all consumers without explicit binding lifecycle.

### A4. Catalog Objects as a separate class

Originally framed as "Catalog Objects" — a distinct Object Type for standard parts in shared library projects.

> **Adopted, with reframing.** Under current spine + Promotion Rule, "Catalog Objects as a separate class" reads as **"catalog projects"** — regular AIADRA projects designated as publishers — not a new Object Type. Consumer projects reference catalog Objects via the [External pointer Object pattern (Binding lifecycle)](../TruthModelSchema.md#5-two-named-non-disqualifier-patterns); the consumer-side Binding Object is a domain-specific Type (Component for physical/procurement; SoftwareModule for software; etc.). No Catalog Object Type is needed in the seed.

The reframing matters: catalog projects are composable (a project can simultaneously be catalog + consumer + product). A separate Catalog Object Type would encode project role as Object-level data, which is the wrong layer. Catalog publication is a project's intent, not a property of any single Object inside the project.

## Decision

Eight commitments.

### 1. Project-scoped identity tuple

**Across project boundaries, canonical Object identity is `(project_id, object_uuid)`**, not global UUID alone. Within-project identity remains just `object_uuid` per [Manifesto P3](../Manifesto.md); the cross-project case composes `project_id` with the UUID without changing P3.

`revision_id` selects a frozen Revision within the target project. `revision_content_hash` proves the fetched content matches what the consumer approved (Decision §6).

### 2. Catalog projects, not Catalog Object Type

A **catalog project is a regular AIADRA project** that publishes reusable Objects (Parts, Assemblies, Software modules — eventually). The "catalog" designation is project-level (the project's intent), not Object-level. Catalog projects own their Objects' lifecycles, Revisions, releases, and provenance — same as any AIADRA project.

Composability: a project can simultaneously be:
- A catalog (publishing reusable Objects).
- A consumer (binding to other catalogs).
- A regular product project (authoring for its own use).

No project-level discriminator; the relationships determine the role at any moment.

**Reserved for future** (not landed here): a catalog index / publication manifest — a governance artifact, project config, or derived index naming the catalog project's intended-for-consumption surface ("here are the released catalog Objects we expect consumers to use," "here are recommended replacements / deprecations"). This is **Manifest-shaped or project-config-shaped, not Object-Type-shaped**. Likely lands as per-catalog-project policy or a future ADR. Out of scope here.

### 3. Consumer-side Binding Object Types via External pointer pattern

Consumer projects reference upstream reusable Objects through **local Binding Object Types** using the [External pointer Object pattern (Binding lifecycle)](../TruthModelSchema.md#5-two-named-non-disqualifier-patterns) from Promotion Rule commitment 5.

**Component** is the canonical Binding Type for **physical / procurement catalog items** — standard parts, off-the-shelf components, supplier-cataloged items. Component as a full Object Type is the subject of a subsequent per-Type ADR.

**Other domains define their own Binding Types** using the same pattern:

- **SoftwareModule** — Binding to Git-backed software releases. Subsequent per-Type ADR.
- **MaterialSpec** (potential future) — Binding to material standard catalogs.
- **StandardClause** (potential future) — Binding to regulatory / engineering standards published as catalog projects.

The **shared abstraction is the pattern**, not a generic Binding Object Type. Generic `Binding` or `ExternalReference` Types would be meta-Objects with no engineering semantics — explicitly rejected (Codex1 §7 confirmation, Claude2 absorption).

No `binds_to` relationship type is introduced. Each Binding Object's TypeSpecific payload carries the upstream reference directly; local product relationships target the Binding Object's UUID.

### 4. Direct external endpoint policy

**Product-structure and engineering relationships in a consumer project MUST target local Binding Objects** (Component, SoftwareModule, etc.) **unless the relationship-type schema explicitly permits direct external endpoints.**

Direct cross-project endpoints are reserved for:

- The Binding Object's own upstream reference payload (e.g., Component's `upstream_ref` field carrying the catalog binding).
- Provenance / source records (e.g., a `source:` namespace record on a Requirement citing a catalog regulatory clause; see [ADR/0006 §9](0006-object-type-requirement.md)).
- Relationship types whose schema explicitly permits direct external endpoints (per-relationship-type ADR opt-in).

**Without this policy, S0 commitment 6's structured `project_scope` could allow any cross-Object reference to bypass the Binding Object pattern.** A local Assembly could `composed_of` a catalog Part directly — defeating the binding lifecycle, local approval boundary, stable local target for drawings / BOMs / where-used queries, and procurement / supplier overrides.

Practical effect on the seed catalogue's declared relationships:

- **Engineering structure** (`composed_of`, `mated_to`, `parameter_expression`, `derived_geometry_from`) — target local Binding Objects only. No exception.
- **Trace relationships** (`satisfies`, `derived_from`, `refines`, `allocates_to`) — relationship-type ADRs decide per-type whether to permit direct external endpoints. Legitimate trace use cases (e.g., "consumer Requirement derives from a catalog regulatory clause") may warrant the exception; the relationship-type ADR carries the rationale.

The default is "go through Binding Objects." Exceptions are explicit, per-type, and documented in their relationship-type ADRs.

### 5. `project_scope` identity/locator split

`project_scope` carries two conceptually distinct components:

- **`project_id`** — **stable project identity**. Ideally produced by a future project identity artifact; survives Git remote URL changes, repo migrations, mirrors, forks.
- **`locator_hint`** — **non-authoritative transport/discovery hint**. Optional Git URL / local remote / registry pointer. Workspaces may resolve through different locators without affecting identity.

```yaml
project_scope:
  project_id: "..."       # stable identity
  locator_hint: "..."     # optional; transport/discovery; non-authoritative
```

**Exact field names, the format of `project_id`, and the future project identity artifact's design defer to subsequent ADRs.** Component's per-Type ADR settles the usage pattern; a separate ADR may design the project identity artifact itself. The commitment here is the **identity-locator split**, not the field syntax.

A Git remote URL is not stable identity — repos move, mirrors exist, forks share history. Locking URL identity into canonical references would fight [Manifesto P11](../Manifesto.md) (AIADRA Core hosts nothing — but canonical truth must be portable, not transport-dependent) and long-term reconstructability. The split prevents Component's ADR from accidentally making URL identity canonical.

### 6. Revision integrity for fixed cross-project bindings

**A fixed cross-project binding MUST include or resolve to the catalog Object's `revision_content_hash`** per [S2 commitment 2](../TruthModelSchema.md#2-revision-identity-is-object_uuid-revision_id-with-content-hash-as-integrity) (content hash is integrity, not identity).

Endpoint shape for fixed cross-project bindings (concrete fields TBD in Component ADR):

```yaml
project_scope:
  project_id: "..."
  locator_hint: "..."
object_uuid: "catalog-object-uuid"
revision_id: "A"
revision_content_hash: "sha256:..."
```

The hash placement (alongside `revision_id` at endpoint level, or inside a `binding_integrity` sub-object) defers to Component's per-Type ADR. The **requirement that the hash be present or resolvable for fixed bindings** is committed here.

Without the integrity anchor, "catalog project P, object X, revision A" is nominal — the consumer cannot prove they are using the exact frozen artifact they approved, even if fetched later from a mirror or archive. With the hash, the consumer's Release Manifest can cryptographically bind to the exact upstream Revision content. This mirrors S2's own principle.

**For Float cross-project bindings** (where the consumer's binding resolves to "current catalog state at read time"): integrity-anchor semantics defer to Component's per-Type ADR. What "current" means cross-project — current as of last fetch? Current as of catalog's working state? — needs concrete design that belongs in Component, not at the framework level.

### 7. Backward compatibility — Ring 1 references round-trip

Per S0 commitment 6's existing language: "Ring-1 references must round-trip through any Ring-2 extension without rewriting." This resolution preserves it.

**Within-project references stay unchanged.** `project_scope` is null / omitted; the existing single-project model is the default. Cross-project references are an additive extension that only matters when the consumer authors a Component, SoftwareModule, or other cross-project Binding.

No existing sidecars need migration. Existing ADRs (0001 – 0007) stay valid. Spine commitments stay valid.

### 8. Transport, discovery, federation — out of scope

The following are **explicitly out of scope** for AIADRA Core's Layer 1:

- **Transport mechanism.** How a consumer's tooling actually fetches catalog data — Git submodules, subtrees, external fetch, vendoring — is Layer 4 / project-control concern.
- **Catalog discovery / registry.** How consumers find catalog projects — directories, search indexes, federation services — is ecosystem-level, per [Manifesto P11](../Manifesto.md): "AIADRA Core hosts nothing. Future hosted services (registries, validators, shared libraries) belong to separate ecosystem projects, not to the core."
- **Cross-project where-used at scale.** Catalog projects with many consumers require federated where-used queries. Practical solution at scale is an ecosystem-level catalog-of-catalogs or search index, outside AIADRA Core. This ADR preserves local traceability in each consumer and makes ecosystem traceability *possible*, but global "where used across all projects" still requires federation outside core.
- **Catalog publication conventions.** Per-catalog-project policy. How a catalog organizes its repo, names its Releases, manages its public surface is its own concern.
- **Catalog-project ADRs.** A catalog project uses the same spine + Promotion Rule that any AIADRA project uses; its own ADRs / Revisions / Releases follow standard AIADRA. No special "catalog ADR" mechanism is introduced.

## Worked example sketch

A consumer project's Component sidecar binding to a catalog Part (exact Component schema in subsequent ADR; this shows the framework):

```yaml
object:
  uuid: "0193dddd-consumer-component-..."   # consumer's local Object UUID
  type: "Component"
  number: "C-000017"                         # consumer's local Number; prefix in Component ADR
  lifecycle: "in_work"
  schema_version: "0.5.0"
  fact_provenance: { category: "human_input" }

component:                                   # Component's TypeSpecific (full schema in Component ADR)
  source_kind: "aiadra_catalog"
  upstream_ref:
    project_scope:
      project_id: "aiadra:standard-fasteners:abc123def"
      locator_hint: "https://github.com/aiadra-catalog/standard-fasteners.git"
    object_uuid: "0193aaaa-catalog-m8-bolt-..."
    revision_id: "A"
    revision_content_hash: "sha256:e7f9..."

# Local product relationships target THIS Component (local UUID),
# not the catalog Part directly:
relationship:
  - id: "rel_satisfies_req14"
    type: "satisfies"
    binding: "float"
    endpoints:
      - object_uuid: "0193ffff-req14-..."     # local Requirement, same project
```

A parent Assembly in the same consumer project composing this Component:

```yaml
# Inside the consumer's Assembly sidecar:
relationship:
  - id: "rel_composed_bolt_1"
    type: "composed_of"
    binding: "float"
    endpoints:
      - object_uuid: "0193dddd-consumer-component-..."   # LOCAL Component, not catalog Part
        # no project_scope — within-project reference
    occurrence:
      instance_name: "bolt_mounting_NE"
      transform: { ... }
```

The Assembly's `composed_of` targets the local Component. The Component's `upstream_ref` carries the catalog binding (with identity-locator split + integrity hash). Local relationships stay local; cross-project semantics live inside the Binding Object's TypeSpecific payload per Decision §4.

## Consequences

- **TruthModelSchema bump v0.7 → v0.8.** S0 commitment 6 amended to reflect cross-project shape, identity-locator split, revision integrity for fixed bindings, and direct-endpoint policy. Pointer to this ADR for the full framework.
- **OpenQuestions bump v0.4 → v0.5.** OQ-0016 status moves to `resolved`; entry restructured with concise Resolution block at top plus preserved four-option historical trail.
- **Component per-Type ADR unblocked.** Likely ADR/0009 — authors Component's full schema, including exact `project_scope` field names and the sourcing discriminator (`aiadra_catalog | supplier_datasheet | custom`).
- **SoftwareModule per-Type ADR unblocked.** Subsequent ADR; same pattern as Component but Git-source-of-truth.
- **Electrical component candidate** remains deferred per [OQ-0006](../OpenQuestions.md). Its promotion (or collapse into Part as specialization) is a separate question.
- **Manifesto P3 unchanged.** Cross-project identity tuple lives in this ADR + S0 commitment 6; Manifesto stays short.
- **Project identity artifact deferred.** Decision §5 commits to the identity-locator split without designing the artifact. A future ADR or Manifesto extension may design the project identity artifact (likely `.aiadra/project-identity.yaml` or similar with a UUID-shaped `project_id`); not in scope here.
- **Catalog index / publication manifest reserved as future governance artifact.** Manifest-shaped or project-config-shaped, not Object-Type-shaped. Likely lands as per-catalog-project policy or a future ADR.
- **Ecosystem-level concerns out of scope.** Catalog discovery, registry, federation, search indexes — all ecosystem projects per Manifesto P11.
- **Relationship-type ADRs proceed next.** With OQ-0016 resolved, relationship-type ADRs (`composed_of`, `mated_to`, `satisfies`, `derived_from`, `refines`, `allocates_to`, `parameter_expression`, `derived_geometry_from`) can author concrete schemas. Each declares whether it permits direct external endpoints per Decision §4.
- **The Wedge** needs the `satisfies` relationship-type schema at minimum but doesn't strictly need cross-project semantics. The Wedge's Parts and Requirements are within-project; cross-project binding through Component would be tested by a subsequent multi-project Wedge variant.

## References

- [Manifesto.md](../Manifesto.md) — P3 (UUID identity; extended cross-project by this ADR without amendment), P11 (AIADRA Core hosts nothing — bounds transport/discovery/federation out of scope).
- [Glossary.md](../Glossary.md) — *Object*, *UUID*, *Number*, *Revision* (Decision §6 integrity anchor), *Released Truth*.
- [TruthModelSchema.md](../TruthModelSchema.md) — S0 commitment 6 (amended in v0.8 to carry cross-project shape per this ADR), S2 commitment 2 (revision content hash is integrity not identity — basis for Decision §6), S2 commitment 8 (cross-Object references with `revision_id` — cross-project case adds `revision_content_hash` per this ADR), [Promotion Rule commitment 5](../TruthModelSchema.md#5-two-named-non-disqualifier-patterns) (External pointer Object pattern with Binding lifecycle — pattern used by all consumer-side Binding Types under this ADR).
- [ADR/0001](0001-storage-substrate.md) — Storage substrate. §5 (no live coordination — bounds catalog discovery as out of scope).
- [ADR/0002](0002-canonical-format.md) — Canonical format.
- [ADR/0003](0003-schema-governance.md) — Schema governance.
- [ADR/0005](0005-object-type-part.md) — Object Type: Part. Pattern source for adapter shell, geometry roles, governance ceremony.
- [ADR/0006](0006-object-type-requirement.md) — Object Type: Requirement. Source for the `source:` namespace pattern that may carry catalog regulatory citations under this ADR's Decision §4 exception.
- [ADR/0007](0007-object-type-assembly.md) — Object Type: Assembly. Occurrence-qualified endpoints + composition cycle validation establish the within-project relationship semantics that this ADR extends across project boundaries.
- [OpenQuestions.md](../OpenQuestions.md) — OQ-0016 (resolved by this ADR), OQ-0006 (multi-tool sequencing; affects Electrical component candidate verdict), OQ-0015 (Reservation file shape; downstream of `C-NNNNNN` Number prefix when Component ADR lands).
- Discussion trail (git-ignored, local only): `Docs/Discussions/20260518-7/Claude1.md` → `Codex1.md` → `Claude2.md` → `Codex2.md` — full working-out across one substantive Codex round (twelve findings, zero rejected; five load-bearing) plus a green-light second round.
