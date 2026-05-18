---
name: adr-0007-object-type-assembly
status: accepted
date: 2026-05-18
supersedes: none
superseded_by: none
resolves: []
---

# ADR/0007 — Object Type: Assembly

## Status

**Accepted** — 2026-05-18. Third and final seed Object Type per [ADR/0003 §1 / §2](0003-schema-governance.md) named examples and the [Promotion Rule's commitment 8](../TruthModelSchema.md#8-seed-catalogue-is-grandfathered). Completes the seed catalogue (Part / Requirement / Assembly). Establishes three patterns subsequent ADRs will rely on: occurrence-qualified endpoints for assembly-context relationships, write-validation closure for cycle policy enforcement, and the per-instance addressability invariant for any future pattern primitive.

## Context

[ADR/0005 (Part)](0005-object-type-part.md) and [ADR/0006 (Requirement)](0006-object-type-requirement.md) pinned the first two seed Types. Assembly is the third — the *structural* Type, where Parts compose into larger units and assembly-context relationships (mates, spanning parametric expressions, in-context features) live.

Three pressures converge here:

1. **Composition with occurrence identity.** A single Part may appear multiple times in one Assembly (four M8 bolts at four mounting holes, eight identical brackets). Each occurrence has its own position and orientation but shares Part identity. The seed Assembly schema must answer how occurrences are modeled — and the answer propagates into every assembly-context relationship that needs to address a specific placed instance versus the reusable Part definition.
2. **Assembly-context relationship ownership.** Per [ADR/0005 §11](0005-object-type-part.md) and the Codex pushback in the Part arc, Assembly owns most `mated_to` records (the mate exists in assembly context, not on either participating Part) and the broader class of assembly-spanning relationships. Assembly is the Type where that ownership becomes operational.
3. **First cycle-policy-enforcing Type.** `composed_of` is `acyclic_dependency` per [S3 commitment 13](../TruthModelSchema.md#13-per-type-cycle-and-graph-class-policy). Parts have no `composed_of` records; Requirements have no composition relationship. Assembly is the first Type where the cycle gate fires, and the seed Assembly ADR must answer how cycle detection works at write time across the project.

The discussion trail in [`Docs/Discussions/20260518-6/`](../Discussions/20260518-6/) carries the full alternatives reasoning. Codex1 produced twelve findings (one load-bearing — occurrence-qualified endpoints — plus eleven refinements); all twelve accepted. Codex2 green-lit Claude2's twelve absorptions with one tiny non-blocking polish note on the worked example. This ADR pins the result.

## Alternatives Considered

### Occurrence representation

**A1. Position as property of `composed_of` record; record IS the occurrence.** *Chosen — see Decision §1.*

**A2. Separate `occurrence:` namespace with records that reference Parts plus carry position.** Each occurrence has its own id; `composed_of` records target the occurrence.

> **Rejected.** Adds a parallel addressable namespace (`occurrence:<id>` alongside `relationship:rel_composed_<id>`) for content that's logically the same — "this is one realization of this Part in this Assembly at this place." The relationship record naturally IS the occurrence; introducing a second namespace would duplicate identity and create synchronization hazards. Relationship records already support properties per [S3 commitment 4](../TruthModelSchema.md#4-relationship-properties-follow-s1-annotation-rules) with S1 annotations, addressable per [S0 commitment 4](../TruthModelSchema.md#4-hybrid-within-artifact-addressing).

**A3. BOM-line aggregate — one `composed_of` per unique Part + count + transform list.** Quantity is a property of the relationship; positions are an array.

> **Rejected.** Conflates instance identity with aggregate count. Loses per-occurrence addressability — a mate cannot target "the third bolt" if all four share one BOM-line record. BOMs are *derived* from the per-instance composition records, not the canonical structure.

### Assembly-context endpoint shape

**B1. Endpoints reference Part / sub-Assembly only via `object_uuid` + `fact_ref`.** The original Claude1 shape.

> **Rejected.** Ambiguous the moment the same Part appears multiple times in one Assembly. Four bolts all expose `published_ref:pub_bolt_axis`; an endpoint with only `object_uuid: "bolt-part-uuid"` + `fact_ref: "published_ref:pub_bolt_axis"` cannot identify which bolt occurrence is mated. Caught by Codex1 §1.

**B2. Endpoints carry `occurrence_ref` (the `composed_of` record id) + `fact_ref`.** *Chosen — see Decision §2.* The validator resolves `occurrence_ref` → `composed_of` record → target Object/Revision → `fact_ref` within that. Object-only references (no `occurrence_ref`) explicitly mean "the reusable Object definition," not one placed instance.

### Cycle policy enforcement

**C1. Invariant only; soft enforcement based on fetched locality.** Validator detects cycles within whatever's fetched; unresolved targets emit warnings.

> **Rejected.** Composition cycle bugs corrupt product structure and propagate silently. A stale Workspace could approve a cycle it cannot see. Soft warnings on high-stakes operations is exactly the failure mode [ADR/0001 §6](0001-storage-substrate.md)'s staleness posture guards against.

**C2. Invariant plus hard write-validation closure rule.** *Chosen — see Decision §5.* Commits that touch `composed_of` cannot pass validation unless transitive composition closure can be resolved. Unfetched targets are hard validation failures, not warnings.

### Configuration / variants

**D1. Add a `configuration:` namespace or property to `composed_of` in the seed.**

> **Rejected.** Multi-configuration assemblies are real but raise many load-bearing questions (alternate constituent sets, suppressed/optional occurrences, parameter variants, product options, release rules per configuration, BOM derivation per configuration). Each is substantial. Pre-committing a shape would silently lock in one model.

**D2. Explicitly defer with explicit future-options framing.** *Chosen — see Decision §7.* Seed represents one canonical assembly structure per Assembly Object. Future configuration / variant support requires a dedicated ADR or substantial Schema Change Note.

### Pattern semantics

**E1. Compact pattern primitive in seed (one record with `pattern: {type, count, parameters}`).**

> **Rejected.** Each occurrence type would need to handle pattern-resolution semantics; mates and other relationships targeting individual instances inside a pattern would require pattern-expansion logic at every consumer. Premature for the Wedge.

**E2. Individual `composed_of` per occurrence; defer pattern semantics with binding future invariant.** *Chosen — see Decision §8.* Any future pattern representation must preserve per-occurrence addressability.

## Decision

### 1. Occurrence semantics — position on `composed_of`, record id IS the occurrence id

Each occurrence of a constituent Part or sub-Assembly is a separate `composed_of` relationship record in the Assembly's `relationship:` namespace. The record IS the occurrence; no parallel `occurrence:` namespace.

```yaml
relationship:
  - id: "rel_composed_bolt_1"
    type: "composed_of"
    binding: "float"
    endpoints:
      - project_scope: null
        object_uuid: "0193bbbb-bolt-..."
    occurrence:
      instance_name: "bolt_mounting_NE"
      transform: { ... }
    fact_provenance: { category: "human_input" }
```

Per-instance addressability: each `composed_of` record carries a stable `id` plus an optional `instance_name`. These ids are the occurrence identifiers used by assembly-context relationships per Decision §2. The `occurrence` sub-object carries position / orientation; the exact transform representation is settled in the `composed_of` relationship-type ADR.

### 2. Occurrence-qualified endpoint rule

**Assembly-context relationships that target constituent geometry, parameters, or features MUST carry `occurrence_ref` identifying which placed instance the endpoint refers to, in addition to the `fact_ref`.** Object-only references (no `occurrence_ref`) explicitly mean "the reusable Object definition," not one placed instance.

Endpoint shape:

```yaml
relationship:
  - id: "rel_mate_bolt_1_to_plate"
    type: "mated_to"
    endpoints:
      - occurrence_ref: "relationship:rel_composed_bolt_1"
        fact_ref: "published_ref:pub_bolt_axis"
      - occurrence_ref: "relationship:rel_composed_plate"
        fact_ref: "published_ref:pub_mounting_hole_axis_NE"
    fact_provenance: { category: "human_input" }
```

The validator resolves `occurrence_ref` → `composed_of` record → target Object/Revision binding → `fact_ref` within that.

**Where the rule applies:**

- `mated_to` endpoints — always occurrence-qualified when targeting placed Parts.
- `parameter_expression` endpoints — occurrence-qualified when the expression targets parameters of placed instances. Object-level parameter references without `occurrence_ref` mean "the reusable Object's parameter definition" (e.g., a class-level constant).
- In-context `feature:` records — when an Assembly-level feature references constituent geometry, each reference is occurrence-qualified.
- Future relationship types (Drawing `depicts` of a specific occurrence, EvidenceArtifact citations of placed instances) — occurrence-qualified per the same rule.

**Endpoint shape choice for the seed.** The slimmer form (`occurrence_ref` + `fact_ref`; no separate `object_uuid` field on the endpoint) is the proposed shape; the validator resolves `object_uuid` through the occurrence. Relationship-type ADRs may add redundant `object_uuid` for cross-check robustness when authoring those schemas.

**Nested occurrence paths.** Parent Assemblies need to reference occurrences inside sub-Assemblies (`top_assembly.left_arm.bolt_1` vs `top_assembly.right_arm.bolt_1`). The Assembly model supports occurrence paths; **exact serialization is deferred to the `composed_of` relationship-type ADR**. The seed commits to the concept ("a placed instance is identified by an occurrence id within its owning Assembly; nested placed instances are identified by an occurrence path") without pinning the path syntax.

### 3. `feature:` namespace with assembly-level guardrail

Assembly `feature:` records are for **assembly-level authored features whose meaning is owned by the Assembly context**:

- Welds, brazed / soldered / bonded joints.
- In-context drilling — holes passing through multiple Parts when the Assembly is on the fixture.
- Assembly-level machining operations applied after composition.
- Datum features at the assembly level (assembly origin, mounting reference plane).
- Surface finishes / coatings applied to the assembled product.

Assembly `feature:` records are **NOT** a second place to copy or duplicate constituent Part features. Each Part owns its own construction-history features in its own `feature:` namespace; Assembly's `feature:` records reference into constituent Parts via occurrence-qualified endpoints (Decision §2) when needed.

Same generic `feature_type` discriminator pattern as Part's `feature:` per [ADR/0005 §6](0005-object-type-part.md). Per-feature taxonomy deferred to Domain Adapter ADR.

Optional namespace; many Assemblies have no in-context features.

### 4. `geometry_ref:` with derived_export sharpening

Assembly `geometry_ref:` allows both `authoring_geometry` and `derived_export` roles per Part's role enum, with a sharper rule for `derived_export`:

> Assembly `geometry_ref:` may carry `derived_export` records only when the export is intentionally retained as a canonical reference or release artifact, with `derived_from` lineage to the composition / source Parts. Ordinary cached / generated views remain outside the sidecar (in the acceleration cache per [ADR/0001 §3](0001-storage-substrate.md), adapter-local cache, or Workspace-local files) or in the Release Manifest. Generated STEP / mesh / render artifacts are not authored Assembly state by default; they enter the sidecar only when there is a specific Assembly-bound reason.

`authoring_geometry` records remain allowed for assembly-level kernel-modified geometry (the assembled BRep after weldments, in-context drilling, surface finishes).

Cached visualizations live outside the sidecar entirely, same as Part.

### 5. Cycle policy enforcement with write-validation closure

`composed_of` is `acyclic_dependency` per [S3 commitment 13](../TruthModelSchema.md#13-per-type-cycle-and-graph-class-policy). Assembly is the first Type to activate this gate.

**The invariant:** an Assembly cannot transitively contain itself via any chain of `composed_of` records, traversing through Parts and sub-Assemblies.

**Where the check fires:** at commit time on the merged sidecar / event state. The Layer-2 validator (per [ADR/0001 §4](0001-storage-substrate.md)'s sidecar/event invariant) traverses the `composed_of` graph rooted at every Assembly in scope.

**Write-validation closure rule.** A commit that creates or modifies `composed_of` records cannot pass validation unless the validator can resolve the transitive composition closure required for cycle detection. **Unknown or not-fetched composition targets are a hard validation failure for that write**, not a warning.

This matches [ADR/0001 §6](0001-storage-substrate.md)'s staleness posture: read paths can tolerate stale data, but write paths affecting composition must operate on resolved state. The AI Action Protocol exposes this through the locality tier; composition-touching commits request remote-only fetches before commit.

**Cross-Object scope.** The cycle gate is global across Objects in the project, not local to one sidecar.

**Implementation flexibility flagged.** Efficient cycle detection at Tier-L scale (50K Objects, deep composition trees) is non-trivial. The Layer-2 validator implementation has freedom — graph algorithms, incremental detection on the diff, acceleration-cache-backed indexing per [ADR/0001 §3](0001-storage-substrate.md). The ADR commits to the invariant and the write-validation closure rule, not the algorithm.

### 6. Float / Fixed binding for `composed_of`

Per [S3 commitment 12](../TruthModelSchema.md#12-float-vs-fixed-binding-mode-is-explicit-per-relationship) and [S2 commitment 8](../TruthModelSchema.md#8-cross-object-references-may-include-revision_id-required-in-released-revision-records):

- **In working sidecars,** `composed_of` records may be Float (no `revision_id` on endpoints — resolves to constituent's current Revision at read time) or Fixed (`revision_id` pinned). Default is Float for working sidecars per S3 commitment 12; per-occurrence Fixed for "derived from a specific past Revision" semantics.
- **In released Assembly Revision records,** every managed-Object endpoint in `composed_of` is materialized with `revision_id` per S2 commitment 8. The release transaction (S2 commitment 11) resolves Float bindings to specific Revision ids at materialization without rewriting the working sidecar's authoring intent.
- **Occurrence identity is stable across materialization.** The `composed_of` record's `id` stays the same in the working sidecar (with potentially Float binding) and in the released Revision record (with Fixed `revision_id`). Only the target revision binding resolves.

### 7. Configuration / variants explicitly deferred

Multi-configuration assemblies are a real engineering pattern (110V / 220V variants of an appliance; left-hand-drive / right-hand-drive variants; size-graded variants of a fixture). Configuration support is **out of scope for the seed Assembly Type.**

The seed Assembly represents one canonical assembly structure per Assembly Object at a time. Multi-variant support raises load-bearing questions:

- Are variants separate Assembly Objects (each with its own UUID, lifecycle, Revisions), or are they records inside one Assembly?
- How are alternate constituent sets represented?
- What does "suppressed" or "optional" mean for an occurrence?
- How do parameter variants interact with Revision content boundaries?
- How does the release rule work — release one configuration or all together?
- How does BOM derivation per configuration interact with the Promotion Rule's BOM-as-D7-derived-view?

Pre-committing a shape via "just add optional properties to `composed_of` records" would silently lock in one model without working through the alternatives.

**Future configuration / variant support will require a dedicated ADR or substantial Schema Change Note** defining whether variants are separate Assemblies, records under a `configuration:` namespace, or project-control / product-line constructs. A future `Configuration` Object Type could even be promoted through the Promotion Rule's candidate-pool process if variants become first-class Objects.

For Wedge-era projects (one canonical configuration per Assembly), this deferral has no cost.

### 8. Pattern semantics deferred with expansion invariant

Linear / circular / rectangular patterns (one master instance with N derived instances controlled by pattern parameters) are **not introduced in the seed Assembly schema.** Each occurrence is an individual `composed_of` record. For typical Wedge-era projects this is sufficient.

**Future invariant (binding on any future pattern primitive):**

> Any compact pattern representation introduced later — whether a single `composed_of` record with `pattern: {type, count, parameters}` properties, a separate `pattern:` namespace, or any other shape — must either materialize stable per-occurrence identities at commit time OR provide deterministic virtual occurrence ids that mates, callouts, and assembly-context relationships can target individually.

This follows from Decision §2's occurrence-qualified endpoint rule. A pattern primitive that prevents addressing individual instances would break mates, in-context features, parameter expressions, and Drawing callouts on those instances.

### 9. TypeSpecific shape — six namespaces, no singletons

Following Part's pattern, not Requirement's. Assembly has no "primary canonical fact" demanding an envelope-style singleton. All canonical content lives in record collections.

1. **`parameter:`** — Assembly-level parameters (envelope dimensions, aggregate computed properties with `derived_from` lineage per [S1 commitment 5](../TruthModelSchema.md#5-computed-facts-carry-derived_from-inside-fact-provenance), user-authored Assembly parameters). Same shape as Part's `parameter:`.
2. **`design_intent:`** — rationale with anchors-or-object-level guardrail per [ADR/0005 §5](0005-object-type-part.md).
3. **`feature:`** — assembly-level authored features per Decision §3.
4. **`relationship:`** — composition (`composed_of` per Decision §1), mates (`mated_to` with occurrence-qualified endpoints per Decision §2), Assembly-spanning parameter expressions (`parameter_expression` per Decision §2), and other relationships sourced on Assembly. Same source-anchored shape per [S3 commitment 3](../TruthModelSchema.md#3-relationships-are-source-anchored).
5. **`published_ref:`** — published reference ports for parent-Assembly consumption. Same shape as Part's `published_ref:` per [S3 commitment 11](../TruthModelSchema.md#11-published-reference-ports-are-first-class-addressable-records-owned-by-objects).
6. **`geometry_ref:`** — assembly geometry per Decision §4.

Not present:

- **No `material:`.** Welded / coated / composite Assemblies have material at the feature level (weld filler material on a weld feature, coating material on a coating feature). Assembly-level `material:` can be added additively via Schema Change Note if use case arises.
- **No TypeSpecific singletons under an `assembly:` wrapper block.** Following Part's pattern.
- **No `acceptance_criterion:` or `source:`.** Requirement-specific patterns.

### 10. Number prefix mapping

`ASM-NNNNNN` — three-letter prefix, six-digit zero-padded sequential. AIADRA Core default; per-project override per [S2.5 commitment 10](../TruthModelSchema.md#10-number-format-and-type--prefix-mapping-are-per-project-policy). Three-letter prefix is unambiguous in running text (single-letter `A-` could clash with abbreviations); six digits matches Part / Requirement for Tier-L headroom.

Alternatives `ASY-` (Onshape default), `SA-` (some Windchill projects) acceptable as per-project overrides. Exhaustion mechanics belong to OQ-0015 / ADR/0004.

### 11. Revision schema, relationship endpoint participation, bundle bump

**Revision schema.** Same as Part / Requirement per [S2 commitment 1](../TruthModelSchema.md#1-revisions-are-separate-immutable-schema-governed-artifacts). Full reconstructable release-time snapshot per [S2 commitment 13](../TruthModelSchema.md#13-revision-snapshot-boundary). Every `composed_of` endpoint materialized with `revision_id` per Decision §6 and S2 commitment 8. Canonical path: `revisions/<object-uuid>/<revision-id>.yaml`.

**Relationship endpoint participation:**

| Relationship | Direction | Arity | Cycle policy | Notes |
|---|---|---|---|---|
| `composed_of` | Assembly → Part / Assembly | binary | `acyclic_dependency` | Assembly is source / owner. Occurrence position on the record. Write-validation requires resolved transitive composition closure (Decision §5) |
| `mated_to` | feature ↔ feature | binary | `undirected_constraint_graph` | Assembly is source / owner. Endpoints **occurrence-qualified** per Decision §2 |
| `parameter_expression` | Parameter → Parameter(s) | source + many | `acyclic_dependency` | Assembly is source when expression spans constituent occurrences. Endpoints **occurrence-qualified** unless intentionally targeting reusable Object definitions per Decision §2 |
| `satisfies` | Assembly → Requirement | binary | `trace_graph` | Assembly is source (an Assembly can satisfy system-level Requirements) |
| `allocates_to` | Requirement → Assembly | binary | `trace_graph` | Assembly is target |
| `depicts` | Drawing → Assembly | binary | `trace_graph` | Assembly is target |
| `derived_geometry_from` | Assembly in-context feature → constituent occurrence `published_ref` | binary | `acyclic_dependency` | Likely participation; in-context features derive geometry from constituent occurrence published refs. Occurrence-qualified per Decision §2. Full schema in future relationship-type ADR |

Future endpoint participations: `verified_by` / `tested_against` (Assembly → TestProcedure / EvidenceArtifact when those Types land).

**Bundle bump:** MINOR / additive per [ADR/0003 §11](0003-schema-governance.md). Bundle bumps v0.3.0 → v0.4.0. New `object.type = "Assembly"` discriminator value, new `sidecar/Assembly.schema.json`. No existing artifacts to break.

**ADR ceremony** per the [amended Promotion Rule commitment 6](../TruthModelSchema.md#6-promotion-ceremony) — third seed Type completing the catalogue; introduces occurrence-qualified endpoint pattern (multi-Type pattern-setting); introduces assembly-context relationship ownership operationalization; first Type to activate cycle-policy enforcement with write-validation closure rule; introduces configuration-deferral and pattern-deferral invariants. Multiple substantial pattern-setting decisions.

## Worked sidecar example

S1-valid with envelope-level default and one computed-result override. Demonstrates occurrence-qualified mate endpoints across four bolt instances of the same Part. Adapter shells show `engine_artifact_ref` consistently across the assembly-level feature and the assembly-level authoring geometry, so the `stable_engine_object_id` anchors resolve cleanly within a known artifact.

```yaml
object:
  uuid: "0193abcd-1234-7890-..."
  type: "Assembly"
  number: "ASM-000042"
  lifecycle: "in_work"
  schema_version: "0.4.0"
  fact_provenance: { category: "human_input" }
  fact_uncertainty: "verified"

parameter:
  - id: "param_total_mass"
    name: "total_mass_g"
    value: 234.7
    datatype: "number"
    unit: "g"
    fact_provenance:
      category: "computed_result"
      derived_from:
        - "relationship:rel_composed_plate"
        - "relationship:rel_composed_bolt_1"
        - "relationship:rel_composed_bolt_2"
        - "relationship:rel_composed_bolt_3"
        - "relationship:rel_composed_bolt_4"

design_intent:
  - id: "di_assembly_purpose"
    name: "Mounting bracket assembly purpose"
    purpose: "Bolts the motor MTR-0007 to the chassis at four mounting points per REQ-014."
    scope: "object"

feature:
  - id: "feat_assy_datum_a"
    name: "Datum A — base mounting plane"
    feature_type: "datum_plane"
    adapter_payload:
      engine: "freecad"
      adapter_schema_version: "0.1.0"
      engine_artifact_ref: "sha256:freecad_assy_doc_hash..."   # same artifact as geo_assy_modified_brep
      stable_engine_object_id: "Datum001"                       # resolves inside the FreeCAD doc above

relationship:
  - id: "rel_composed_plate"
    type: "composed_of"
    binding: "float"
    endpoints:
      - object_uuid: "0193cccc-plate-..."
    occurrence:
      instance_name: "mounting_plate"
      transform: { ... }

  - id: "rel_composed_bolt_1"
    type: "composed_of"
    binding: "float"
    endpoints:
      - object_uuid: "0193bbbb-bolt-..."
    occurrence:
      instance_name: "bolt_mounting_NE"
      transform: { ... }

  - id: "rel_composed_bolt_2"
    type: "composed_of"
    binding: "float"
    endpoints:
      - object_uuid: "0193bbbb-bolt-..."        # SAME Part UUID as bolt_1
    occurrence:
      instance_name: "bolt_mounting_NW"
      transform: { ... }

  # rel_composed_bolt_3 (SE), rel_composed_bolt_4 (SW) — same Part UUID, different occurrence ids

  - id: "rel_mate_bolt_1_to_plate"
    type: "mated_to"
    endpoints:
      - occurrence_ref: "relationship:rel_composed_bolt_1"      # occurrence-qualified
        fact_ref: "published_ref:pub_bolt_axis"
      - occurrence_ref: "relationship:rel_composed_plate"
        fact_ref: "published_ref:pub_mounting_hole_axis_NE"

  # rel_mate_bolt_2_to_plate, rel_mate_bolt_3_to_plate, rel_mate_bolt_4_to_plate — analogous, occurrence-qualified

  - id: "rel_satisfies_req14"
    type: "satisfies"
    binding: "float"
    endpoints:
      - object_uuid: "0193ffff-req14-..."

published_ref:
  - id: "pub_overall_envelope"
    name: "overall_envelope"
    kind: "bounding_box"
    selector:
      topology_ref_id: "toporef_assembly_envelope"
      selector_predicate: "outer envelope of the assembled bracket plus four bolts"
      encoded_history: "ASSY:CompoundShape;:E:1"

geometry_ref:
  - id: "geo_assy_modified_brep"
    role: "authoring_geometry"
    kind: "brep"
    vault_ref: "sha256:assy_brep_hash..."
    adapter_ref:
      engine: "freecad"
      adapter_schema_version: "0.1.0"
      engine_artifact_ref: "sha256:freecad_assy_doc_hash..."   # same artifact referenced by feat_assy_datum_a
      stable_engine_object_id: "AssyBody001"
```

The example demonstrates:

- **Computed `total_mass_g`** with `derived_from` lineage to constituent occurrence records.
- **Four occurrences of the same bolt Part**, each with its own `composed_of` record and stable id.
- **Mate records using `occurrence_ref`** to identify which bolt occurrence is mated to which mounting hole.
- **One Assembly-level `published_ref:`** (overall envelope) for parent-Assembly consumption.
- **`authoring_geometry`** `geometry_ref:` record for the assembly's post-composition BRep.
- **Adapter shell consistency** — the in-context feature and the assembly's authoring geometry share `engine_artifact_ref`, so `stable_engine_object_id` anchors resolve inside a known FreeCAD document.
- **Float binding on `composed_of`** — working sidecar. Release would materialize to Fixed per Decision §6.

Effective S1 annotations:

- `relationship:rel_composed_bolt_1.occurrence.instance_name` → `human_input` / `verified` (inherits envelope default).
- `parameter:param_total_mass.value` → `computed_result` / `verified` (explicit level-1 override on the record).
- `feature:feat_assy_datum_a.feature_type` → `human_input` / `verified` (inherits envelope default).

Every concrete address resolves to effective provenance and uncertainty.

## Consequences

- **Schema bundle bump.** Active bundle moves v0.3.0 → v0.4.0. New `sidecar/Assembly.schema.json` lands in the `aiadra-core` bundle. Number prefix mapping for `Assembly → ASM-NNNNNN` declared.
- **Glossary update.** [Glossary](../Glossary.md) bumps v0.7 → v0.8 with a new entry for *Assembly* citing this ADR.
- **Seed catalogue complete.** Part / Requirement / Assembly all pinned. The Promotion Rule's grandfathered seed is fully realized.
- **Relationship-type ADRs become the next phase.** `composed_of`, `mated_to`, `satisfies`, `derived_from`, `refines`, `allocates_to`, `parameter_expression`, `derived_geometry_from`. The `composed_of` ADR will pin the position / orientation representation and the occurrence path syntax flagged in Decision §2.
- **OQ-0016 reopens.** Per the [Promotion Rule's verdict table](../TruthModelSchema.md#verdict-summary), OQ-0016 (cross-project Object identity) reopens before relationship taxonomy enumeration completes. The reopening lands between Assembly's ADR and the first relationship-type ADR.
- **Cycle detection in the validator.** Layer-2 must implement the `acyclic_dependency` invariant on `composed_of` with the write-validation closure rule from Decision §5. Algorithm flexibility flagged; concrete implementation belongs to Layer-2 work.
- **Configuration / variants formally out of scope** until a dedicated ADR. The seed represents one canonical assembly structure per Assembly Object.
- **Pattern future invariant binding.** Any future pattern primitive must preserve per-occurrence addressability per Decision §8.
- **Wedge readiness.** The Wedge — one Part + one Parameter + one Requirement + one sidecar + one event + one AI Transaction + one validation + one Release Manifest — does not strictly need Assembly. But the Wedge's eventual "real product" extension does, and the Assembly schema is now ready for it.
- **`sidecar/Assembly.schema.json`** — lives in the `aiadra-core` schema bundle, not in this ADR.

## References

- [Manifesto.md](../Manifesto.md) — P3 (UUID identity), P4 (Design Intent first-class), P6 (Parameters first, raw geometry last — Assembly-level parameters and computed aggregates), P7 (provenance + uncertainty), P9 (layered geometry access — Assembly's geometry typically derived from composition), P11 (AIADRA Core hosts nothing — bounds adapter shell portability).
- [Glossary.md](../Glossary.md) — *Object (Managed Object)* (catalogue verdicts including Assembly as seed), *Assembly* (new entry in Glossary v0.8 citing this ADR), *Revision*, *Released Truth*, *UUID*, *Number*.
- [TruthModelSchema.md](../TruthModelSchema.md) — S0 (compositional schema; addressing; hybrid within-artifact addressing), S1 (provenance / uncertainty four-level walk), S2 (release / Revision; Float/Fixed materialization; revision snapshot boundary), S2.5 (Number-binding lifecycle), S3 (relationships, source-anchored ownership, published reference ports, cycle policies including `acyclic_dependency`), Promotion Rule (C1–C4, D1–D7, two patterns, amended commitment 6 governance-vs-schema decoupling).
- [ADR/0001](0001-storage-substrate.md) — Storage substrate. §3 (acceleration cache — where cached visualizations live; cycle-detection indexing implementation freedom), §4 (sidecar/event invariant — composition cycle validation fires here), §6 (locality tier and staleness — write-validation closure rule's basis).
- [ADR/0002](0002-canonical-format.md) — Canonical format.
- [ADR/0003](0003-schema-governance.md) — Schema governance. §2 (discriminator), §11 (bump ceremony — MINOR additive for Assembly).
- [ADR/0005](0005-object-type-part.md) — Object Type: Part. Pattern source for `parameter:`, `design_intent:`, `feature:` discriminator, `published_ref:`, `geometry_ref:` role enum, governed adapter shell, Number prefix conventions, governance ceremony.
- [ADR/0006](0006-object-type-requirement.md) — Object Type: Requirement. Demonstrated the "template, not quota" namespace selectivity that Assembly inherits (no `material:` for Assembly, no `acceptance_criterion:` or `source:`).
- [OpenQuestions.md](../OpenQuestions.md) — OQ-0003 (failed-transaction audit-log scope), OQ-0006 (multi-tool sequencing; affects future Electrical/PCB Assembly variants), OQ-0015 (Reservation file shape, downstream of `ASM-NNNNNN` Number prefix decision), OQ-0016 (cross-project Object identity — reopens after this ADR and before relationship-type ADRs).
- Discussion trail (git-ignored, local only): `Docs/Discussions/20260518-6/Claude1.md` → `Codex1.md` → `Claude2.md` → `Codex2.md` — full working-out across one substantive Codex round (twelve findings, zero rejected) plus a green-light second round.
