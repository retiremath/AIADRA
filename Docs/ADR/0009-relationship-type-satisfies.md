---
name: adr-0009-relationship-type-satisfies
status: accepted
date: 2026-05-18
supersedes: none
superseded_by: none
resolves: []
---

# ADR/0009 — Relationship Type: `satisfies`

## Status

**Accepted** — 2026-05-18. First relationship-type ADR; instantiates the `relationship/<type>.schema.json` mechanism pre-authorized by [S3 commitment 7](../TruthModelSchema.md#7-relationship-types-are-schema-governed-under-adr0003). Sets thirteen reusable relationship-type pattern fields that subsequent relationship-type ADRs (`composed_of`, `mated_to`, `derived_from`, `refines`, `allocates_to`, `parameter_expression`, `derived_geometry_from`, `depicts`) will inherit. Unblocks the Wedge's end-to-end loop — a Part can now satisfy a Requirement with a schema-governed relationship record, a `relationship_created` event, validation, and release-time materialization into a Revision record.

## Context

The seed catalogue ([Part](0005-object-type-part.md), [Requirement](0006-object-type-requirement.md), [Assembly](0007-object-type-assembly.md)) declared `satisfies` endpoint participation pending the relationship-type ADR; the cross-project framework ([ADR/0008](0008-cross-project-object-identity.md)) reserved per-relationship-type opt-in for direct external endpoints on trace relationships; Number allocation ([ADR/0004](0004-number-allocation.md)) closed the last Ring-1 framework gap. `satisfies` is the smallest first relationship-type ADR — engineering-graph trace semantics, asymmetric Type endpoints (Part / Assembly → Requirement), and direct relevance to the Wedge.

Three pressures converge here:

1. **Pattern-setting.** ADR/0009 is the first concrete relationship-type schema. Decisions made here — source-anchoring serialization, direct-external-endpoint policy declaration, whole-Object endpoint shape, default binding, cycle / self policies, minimal seed properties, release-time materialization — become the precedent the next eight relationship-type ADRs follow. The deliberate-narrow seed reflects that.
2. **Cross-project policy contact.** [ADR/0008 §4](0008-cross-project-object-identity.md) made direct cross-project endpoints per-relationship-type opt-in for trace relationships. `satisfies` is the first opt-in decision. Float external semantics had to land here because the direct-endpoint exception bypasses Component (the otherwise-natural owner of cross-project semantics).
3. **Wedge readiness.** The Wedge — one Part + one Requirement + one `satisfies` record + one `relationship_created` event + one validation + one Release Manifest — is the end-to-end loop this ADR makes operational. Over-engineering (criterion-level `fact_ref`, coverage properties) blocks the Wedge; under-engineering (Fixed-only external bindings) front-loads ceremony onto every regulatory-trace claim.

The discussion trail in [`Docs/Discussions/20260518-9/`](../Discussions/20260518-9/) carries the full alternatives reasoning. Codex1 produced two hard blockers (cross-project Float semantics ownership; source endpoint serialization) and three refinements (direct-external wording sharpening; whole-Requirement normative meaning; pattern-setting completeness); all absorbed. Codex2 green-lit Claude2's absorption with one wording polish on the "current released Revision" boundary, folded into Decision §3.

## Alternatives Considered

### Endpoint shape

**A1. Criterion-level `fact_ref` on target in the seed.** Optional `fact_ref: "acceptance_criterion:<id>"` on the Requirement endpoint to express partial / per-criterion satisfaction.

> **Rejected.** Pre-commits criterion-level semantics before TestProcedure / EvidenceArtifact ADRs and the verification taxonomy land. Partial-coverage roll-up rules, multi-criterion satisfaction aggregation, and how `verifies` relationships address criteria belong with V&V ADRs, not with the first relationship-type ADR.

**A2. Whole-Object endpoints only; criterion-level deferred.** *Chosen — see Decision §2.* Matches [S3 commitment 2](../TruthModelSchema.md#2-three-kinds-of-relationships-are-explicitly-recognized) (engineering-graph endpoints are whole-Object). Whole-Requirement satisfaction is normatively defined as "all acceptance criteria present in that Revision are in scope." Future Schema Change Note may add optional criterion-level `fact_ref` when verification taxonomy hardens.

### Cross-project endpoint policy

**B1. Require local Binding-Object Requirement that mirrors any external Requirement.** Consumer's Part / Assembly satisfies the local mirror; the local mirror binds to the external clause.

> **Rejected.** Forces every consumer to author a local mirror Requirement for every external trace claim (FCC clauses, CE clauses, ISO clauses). High authoring overhead with low engineering payoff — the consumer has no design control over a regulation, only a satisfaction claim. The local-Binding-Object pattern protects local approval boundary / where-used / consumer overrides, none of which apply to a satisfaction claim against an upstream Requirement.

**B2. Permit direct external Requirement endpoints with integrity anchoring.** *Chosen — see Decision §3.* Per [ADR/0008 §4](0008-cross-project-object-identity.md)'s per-type opt-in for trace relationships. Cross-project Fixed endpoints carry `revision_id` + `revision_content_hash` per [ADR/0008 §6](0008-cross-project-object-identity.md). Cross-project Float endpoints resolve to the external Requirement's current released Revision; release materialization is staleness-intolerant.

### Float external `satisfies` semantics

**C1. Defer to Component's per-Type ADR.** Per [ADR/0008 §6](0008-cross-project-object-identity.md)'s deferral of Float cross-project semantics to the Component ADR.

> **Rejected.** ADR/0009's direct-endpoint exception explicitly bypasses Component; deferring to Component leaves Float external `satisfies` ownerless. "Allowed-but-deferred-elsewhere" is the unsafe middle.

**C2. Disallow Float external `satisfies` in seed; Fixed-only.**

> **Rejected.** Front-loads pinning ceremony onto every regulatory-trace claim. A consumer should be able to declare "satisfies the current external FCC §15.247" during working iteration without committing to a specific Revision until release.

**C3. Define Float external semantics in ADR/0009.** *Chosen — see Decision §3.* Float resolves to the external Requirement's current released Revision, never to working sidecar payload. Release materialization is staleness-intolerant: resolves, validates `object.type == "Requirement"`, pins `revision_id` + `revision_content_hash`. The asymmetry with within-project Float (which per [S3 commitment 12](../TruthModelSchema.md#12-float-vs-fixed-binding-mode-is-explicit-per-relationship) may see working state) is principled — a consumer project has no business reading another project's working sidecar.

### Source endpoint serialization

**D1. Explicit source endpoint in the `endpoints` array.** Both source and target serialized.

> **Rejected.** Duplicates the owning sidecar's identity inside the record; creates a drift case (record lives on Part `P1`; explicit source says Assembly `A1`; validator must reject / repair / treat-as-authoritative). The seed catalogue's existing worked examples ([ADR/0005 §11](0005-object-type-part.md), [ADR/0007 §11](0007-object-type-assembly.md)) already serialize only the target; explicit source contradicts established practice.

**D2. Source is implicit (owning Object by storage location); `endpoints` lists target(s) only.** *Chosen — see Decision §1.* Source-anchored binary relationships serialize only the target endpoint. Arity is binary at the semantic layer: implicit source + serialized target. Pattern declaration for `composed_of`, `derived_from`, `refines`, `allocates_to` to inherit; multi-endpoint or symmetric relationships (`mated_to`, `parameter_expression`) will serialize multiple entries explicitly per their own ADRs.

### Optional record properties

**E1. Include `coverage` / `satisfaction_extent` / `evidence_ref` / `verification_state` / `notes` in seed.**

> **Rejected.** Each pre-commits semantics that belong elsewhere: `coverage` / `satisfaction_extent` presume the criterion-level shape Decision §2 defers; `evidence_ref` / `verification_state` belong with `verifies` (TestProcedure → Requirement); `notes` invites the structured-free-text failure mode [ADR/0005 §5](0005-object-type-part.md)'s anchors-or-object-level guardrail forbids.

**E2. Minimal seed properties; standard relationship-record fields only.** *Chosen — see Decision §5.* `id`, `name?`, `type`, `binding`, `endpoints`, S1 annotations. Source's `design_intent:` records can anchor to a relationship by id when rationale is needed.

## Decision

### 1. Endpoint Type constraints, arity, source-anchoring

**Source endpoint Type constraint:** `Part | Assembly`. Per [ADR/0005 §11](0005-object-type-part.md) and [ADR/0007 §11](0007-object-type-assembly.md). Extensible by future Schema Change Note (Component is the most plausible near-term addition per [ADR/0008 §3](0008-cross-project-object-identity.md); deferred to Component's per-Type ADR or its Schema Change Note).

**Target endpoint Type constraint:** `Requirement`. Per [ADR/0006 §12](0006-object-type-requirement.md). For cross-project endpoints, the target Type is validated against the resolved external Object's `object.type` per Decision §3.

**Arity:** binary at the semantic layer. **Serialization: source is implicit (the owning sidecar Object, by storage location per [S3 commitment 3](../TruthModelSchema.md#3-relationships-are-source-anchored)); the `endpoints` array contains exactly one entry — the target.** This pattern (implicit source + serialized target) is the seed declaration for all source-anchored binary relationship types; subsequent relationship-type ADRs inherit it unless their semantics genuinely require explicit multi-endpoint serialization (`mated_to`, `parameter_expression`).

**Source-anchoring:** record lives in the source's `relationship:` namespace per [S3 commitment 3](../TruthModelSchema.md#3-relationships-are-source-anchored). Reverse direction ("what Parts / Assemblies satisfy this Requirement?") is acceleration-cache-derived per [ADR/0001 §3](0001-storage-substrate.md), never stored.

### 2. Whole-Object endpoint shape in seed; criterion-level deferred

Per [S3 commitment 2](../TruthModelSchema.md#2-three-kinds-of-relationships-are-explicitly-recognized) — engineering-graph endpoints are whole-Object. `satisfies` is engineering-graph trace; both semantic endpoints are whole-Object. No `fact_ref` into target namespaces in the seed. No `fact_ref` on the source endpoint either (source isn't serialized per Decision §1; source-side fact addresses are expressible via the source's `design_intent:` records anchoring to the relationship id).

**Normative whole-Requirement semantics:**

> A whole-Requirement `satisfies` claim means the source claims satisfaction of the Requirement as a whole, including all acceptance criteria present in that Requirement Revision. Partial or criterion-scoped satisfaction is not representable in the seed schema.

Future criterion-level Schema Change Note will land additive optional `fact_ref: "acceptance_criterion:<id>"` on the target endpoint when TestProcedure / EvidenceArtifact ADRs and the verification taxonomy harden.

### 3. Direct cross-project endpoint policy — permit, with Float semantics owned here

Per [ADR/0008 §4](0008-cross-project-object-identity.md)'s per-type opt-in for trace relationships, this ADR opts in: **`satisfies` endpoints may target external Requirements (Requirements whose project identity is carried by `project_scope`) directly, without routing through a local Binding Object.**

Rationale:

- Regulatory / standards reuse is the load-bearing use case. Forcing every consumer to author a local Binding-Object Requirement mirroring every external regulatory clause is high authoring overhead with low engineering payoff.
- `satisfies` is a trace claim, not product-structure or procurement binding. The Binding Object pattern protects local approval boundary / where-used / consumer overrides — none of which apply to a satisfaction claim against an external Requirement.

**Negative case (explicit):**

> This exception does not generalize to product-structure relationships. `composed_of`, `mated_to`, `derived_geometry_from`, `parameter_expression`, and similar engineering-structure relationships still target local Binding Objects unless their own ADRs prove otherwise. The trace-relationship exception is per-type opt-in, not a general weakening of ADR/0008's local-Binding-Object default.

**Endpoint schema for external endpoints** (when `endpoints[0].project_scope` is populated):

- `project_scope.project_id` — REQUIRED. Stable external-project identity per [ADR/0008 §5](0008-cross-project-object-identity.md).
- `project_scope.locator_hint` — OPTIONAL. Non-authoritative transport / discovery hint.
- `object_uuid` — REQUIRED. External Requirement's UUID within its project.
- `revision_id` — REQUIRED for Fixed; absent for Float.
- `revision_content_hash` — REQUIRED for Fixed per [ADR/0008 §6](0008-cross-project-object-identity.md); absent for Float (release materialization pins it).

**Float external `satisfies` semantics:**

> A Float cross-project `satisfies` endpoint resolves to the external Requirement's **current released Revision** — the Revision designated as current by the external project's release machinery — never to the external project's working sidecar payload.

This asymmetry with within-project Float (which per [S3 commitment 12](../TruthModelSchema.md#12-float-vs-fixed-binding-mode-is-explicit-per-relationship) may see working state) is principled: cross-project semantics flow only through released artifacts; a consumer project has no business depending on another project's unreleased work. The validator may read external release metadata while refusing to consume the external working payload.

Operational behavior:

- **Working reads** under the locality-tier model per [ADR/0001 §6](0001-storage-substrate.md). Stale-tolerant tiers may report `UNRESOLVED` or stale-cached state with diagnostics; fresh-required tiers must fetch and resolve the external Requirement's current released Revision before the read succeeds. Locality primitives are inherited; this ADR does not invent new ones.
- **Release materialization is staleness-intolerant.** The release transaction MUST resolve the external Requirement to its current released Revision, validate `object.type == "Requirement"`, materialize the resolved `revision_id` and `revision_content_hash` into the source's released Revision record, and hard-fail validation if any step cannot complete. Matches [S3 commitment 16](../TruthModelSchema.md#16-domain-adapter-graceful-degradation-rule-with-a-release-time-threshold)'s "in_work tolerates partial; release demands resolved" pattern.
- **Type validation.** The external endpoint's target Object must validate as `object.type == "Requirement"`. A Float external endpoint pointing at a non-Requirement Object is a hard validation failure at fetch time (working) and at release time (materialization).
- **Fetch failure on Float external endpoints.** Locality-tier-appropriate response in working state per [ADR/0001 §6](0001-storage-substrate.md); hard validation failure at release.

**Inheritance for subsequent trace-relationship ADRs.** `derived_from`, `refines`, `allocates_to` will likely opt into the same direct-external-endpoint pattern when their ADRs land. The Float-external semantics in this section are the seed; subsequent trace-relationship ADRs can reuse or refine them.

### 4. Binding, cycle policy, self-policy

**Default binding mode:** `float`. Per [S3 commitment 12](../TruthModelSchema.md#12-float-vs-fixed-binding-mode-is-explicit-per-relationship). A Part / Assembly claiming to satisfy a Requirement tracks the Requirement's current state by default; `fixed` is available for "satisfies a specific past Revision" semantics. Allowed values: `"float" | "fixed"`.

**Cycle policy:** `trace_graph`. Cycles permitted per the graph class declaration per [S3 commitment 13](../TruthModelSchema.md#13-per-type-cycle-and-graph-class-policy). Structurally cycles cannot form via `satisfies` alone today (Part / Assembly → Requirement is asymmetric across Types); the class is declared for consistency with the policy enumeration and for forward compatibility.

**Self-policy:** `self_forbidden`. Structurally impossible today (cross-Type source / target); declared explicitly for class consistency with the per-type policy enumeration.

### 5. Optional record properties — minimal in seed

Each `satisfies` record carries:

| Field | Required | Notes |
|---|---|---|
| `id` | REQUIRED | Stable local id per [S0 commitment 4](../TruthModelSchema.md#4-hybrid-within-artifact-addressing). |
| `name` | optional | Mutable human-readable label. |
| `type` | REQUIRED | Constant `"satisfies"`. |
| `binding` | REQUIRED | `"float"` \| `"fixed"`. Default Float per Decision §4. |
| `endpoints` | REQUIRED | Single-entry array: the target endpoint only. Source is implicit (the owning Object) per Decision §1. |
| `fact_provenance`, `fact_uncertainty` | optional | S1 annotations per [S3 commitment 4](../TruthModelSchema.md#4-relationship-properties-follow-s1-annotation-rules). Inherits from container per S1 walk. |

No `coverage` / `satisfaction_extent` / `evidence_ref` / `verification_state` / `notes` in seed (rationale in Alternatives §E). Source's `design_intent:` records anchor to the relationship by id when rationale is needed.

### 6. Eventability, release materialization, bundle bump

**Eventability** per [S3 commitment 5](../TruthModelSchema.md#5-relationships-have-create--change--retire-events): `relationship_created`, `relationship_changed`, `relationship_retired`. `_changed` fires only on author intent change (Float ↔ Fixed switch, endpoint rebind, binding semantics change). Release-time materialization is NOT a `_changed` event per [S3 commitment 12](../TruthModelSchema.md#12-float-vs-fixed-binding-mode-is-explicit-per-relationship). Retirement is tombstoning, not deletion.

**Release-time materialization:**

- Every endpoint in a released source (Part / Assembly) Revision record carries `revision_id` per [S2 commitment 8](../TruthModelSchema.md#8-cross-object-references-may-include-revision_id-required-in-released-revision-records).
- Cross-project endpoints additionally carry `revision_content_hash` per Decision §3 and [ADR/0008 §6](0008-cross-project-object-identity.md).
- Float bindings (within-project AND cross-project) materialize to Fixed at release; working sidecar preserves authoring intent per [S3 commitment 12](../TruthModelSchema.md#12-float-vs-fixed-binding-mode-is-explicit-per-relationship).
- For Float external endpoints, release materialization resolves to the external Requirement's current released Revision, validates `object.type == "Requirement"`, and pins `revision_id` + `revision_content_hash` atomically per [S2 commitment 11](../TruthModelSchema.md#11-release-transactions-are-atomic-across-all-canonical-artifacts). Staleness-intolerant per Decision §3.

**Validation rules** (Layer 2 per [ADR/0001 §4](0001-storage-substrate.md) sidecar/event invariant):

- Source Object Type ∈ {Part, Assembly}.
- Target Object Type == Requirement (within-project: validated against the local Object's `object.type`; cross-project: validated against the resolved external Object at fetch / release time).
- Endpoint UUID resolves (within-project: local sidecar exists; cross-project: external project locator + UUID resolves per ADR/0008's identity-locator split).
- For Fixed within-project bindings: `revision_id` REQUIRED on target endpoint.
- For Fixed cross-project bindings: `revision_id` + `revision_content_hash` REQUIRED.
- For Float cross-project bindings: locality-tier-appropriate behavior in working state; hard validation failure at release.
- In released Revision records: every endpoint carries `revision_id`; cross-project endpoints also carry `revision_content_hash`.

**Bundle bump:** **v0.5.0 → v0.6.0**, MINOR additive per [ADR/0003 §11](0003-schema-governance.md). Adds new `relationship/satisfies.schema.json` to the bundle. First occupant of the `relationship/` directory in the bundle structure (pre-authorized by [S3 commitment 7](../TruthModelSchema.md#7-relationship-types-are-schema-governed-under-adr0003)). No existing artifacts to break.

**ADR ceremony** per the [amended Promotion Rule commitment 6](../TruthModelSchema.md#6-promotion-ceremony) — first relationship-type ADR; sets thirteen pattern-setting fields (Decision §1's source-anchoring serialization, Decision §2's whole-Object endpoint shape, Decision §3's direct-external-endpoint policy + Float external semantics + negative case, Decision §4's binding / cycle / self declarations, Decision §5's minimal seed properties, Decision §6's eventability and release materialization rules) that subsequent relationship-type ADRs inherit.

## Worked sidecar example

A Part sidecar with three `satisfies` records: within-project Float, cross-project Fixed, cross-project Float. All three follow the implicit-source pattern (the owning Part is the source; `endpoints` lists only the target).

```yaml
object:
  uuid: "0193abcd-1234-7890-..."
  type: "Part"
  number: "P-000017"
  lifecycle: "in_work"
  schema_version: "0.6.0"
  fact_provenance: { category: "human_input" }
  fact_uncertainty: "verified"

# (other Part namespaces — parameter, feature, geometry_ref, material, design_intent, published_ref — omitted)

relationship:
  # Within-project — Float, no project_scope, source implicit (this Part)
  - id: "rel_satisfies_req14"
    name: "Satisfies operating temperature range Requirement"
    type: "satisfies"
    binding: "float"
    endpoints:
      - object_uuid: "0193ffff-req14-..."     # local Requirement; single endpoint = target
    fact_provenance: { category: "human_input" }
    fact_uncertainty: "verified"

  # Cross-project — Fixed, external Requirement, integrity-anchored
  - id: "rel_satisfies_fcc_15247"
    name: "Satisfies FCC Part 15 §15.247 external Requirement"
    type: "satisfies"
    binding: "fixed"
    endpoints:
      - project_scope:
          project_id: "aiadra:regulations-fcc:abc123def"
          locator_hint: "https://github.com/aiadra-catalog/regulations-fcc.git"
        object_uuid: "0193eeee-fcc-15247-..."
        revision_id: "A"
        revision_content_hash: "sha256:7f9e..."
    fact_provenance: { category: "human_input" }
    fact_uncertainty: "requires_validation"   # awaiting compliance test

  # Cross-project — Float, external Requirement, release-time-materialization-pinned
  - id: "rel_satisfies_iec_60601"
    name: "Satisfies IEC 60601 (current released Revision)"
    type: "satisfies"
    binding: "float"
    endpoints:
      - project_scope:
          project_id: "aiadra:regulations-iec:xyz789"
        object_uuid: "0193dddd-iec-60601-..."
        # no revision_id / revision_content_hash in working state — pinned at release
    fact_provenance: { category: "human_input" }
    fact_uncertainty: "requires_validation"

design_intent:
  - id: "di_fcc_compliance_path"
    name: "FCC §15.247 compliance approach"
    purpose: "Operating power and spurious emissions are bounded by RF shielding and antenna selection per design notes 2026-04."
    anchors:
      - "relationship:rel_satisfies_fcc_15247"
    scope: "object"
```

Effective S1 annotations under this sidecar:

- `relationship:rel_satisfies_req14.binding` → `human_input` / `verified` (inherits envelope default).
- `relationship:rel_satisfies_fcc_15247.binding` → `human_input` / `requires_validation` (record-level uncertainty override; provenance inherited).
- `relationship:rel_satisfies_iec_60601.binding` → `human_input` / `requires_validation` (record-level uncertainty override).

At release of this Part:

- `rel_satisfies_req14` Float → Fixed materialization: target endpoint gains `revision_id` of the local Requirement's released Revision at release time.
- `rel_satisfies_fcc_15247` already Fixed: target endpoint copied verbatim into the Revision record.
- `rel_satisfies_iec_60601` Float external → Fixed materialization: external IEC 60601's current released Revision is resolved, `object.type == "Requirement"` validated, `revision_id` + `revision_content_hash` pinned into the Revision record. The working sidecar's Float binding stays Float for the next iteration's authoring intent per [S3 commitment 12](../TruthModelSchema.md#12-float-vs-fixed-binding-mode-is-explicit-per-relationship).

## Consequences

- **Schema bundle bump.** Active bundle moves v0.5.0 → v0.6.0. New `sidecar` schemas for Part / Assembly accept `relationship:` records with `type: "satisfies"`; the new `relationship/satisfies.schema.json` declares endpoint Type constraints, arity, binding mode, cycle policy, self policy, and the cross-project endpoint shape. The `relationship/` directory in the bundle structure is now occupied (first relationship-type schema).
- **Glossary update.** [Glossary](../Glossary.md) bumps v0.9 → v0.10 with a new entry for *`satisfies`* citing this ADR; existing entries for *Part*, *Requirement*, *Assembly* unchanged in content (their relationship-endpoint references to `satisfies` were already present).
- **The Wedge becomes operational.** One Part + one local Requirement + one `satisfies` record + one `relationship_created` event + one Layer-2 validation + one release-time materialization into a Revision record is now a schema-supported round-trip. Cross-project satisfaction is not strictly needed for the Wedge.
- **Pattern inheritance for subsequent relationship-type ADRs.** `composed_of`, `mated_to`, `derived_from`, `refines`, `allocates_to`, `parameter_expression`, `derived_geometry_from`, `depicts` inherit the thirteen pattern-setting fields. The implicit-source / serialized-target shape inherits to all source-anchored binary relationships; multi-endpoint and symmetric relationships override at their own ADRs. The direct-external-endpoint opt-in pattern inherits to other trace relationships (`derived_from`, `refines`, `allocates_to`) likely adopting analogous Float external semantics. `composed_of` will declare NO direct-external endpoint per [ADR/0008 §4](0008-cross-project-object-identity.md) engineering-structure default.
- **Float external `satisfies` semantics are the seed for trace-relationship cross-project semantics.** Future trace-relationship ADRs can reuse the "current released Revision; staleness-intolerant release materialization" pattern verbatim or refine it.
- **Cycle / self policies declared even when structurally moot.** The uniform declaration across all relationship-type ADRs is the pattern; subsequent ADRs (`composed_of` with `acyclic_dependency`, `mated_to` with `undirected_constraint_graph`) inherit the declaration practice.
- **Criterion-level `fact_ref` deferred** to future Schema Change Note when TestProcedure / EvidenceArtifact / `verifies` taxonomy hardens.
- **`coverage` / `satisfaction_extent` / `evidence_ref` / `verification_state` properties deferred** to Schema Change Notes when concrete V&V use cases surface.
- **Component as source Type deferred** to Component's per-Type ADR or its Schema Change Note.
- **AP242 / SysML v2 round-trip.** `satisfies` maps to SysML v2 `Satisfy` and AP242 e3 `Satisfy` elements per [S3 commitment 7](../TruthModelSchema.md#7-relationship-types-are-schema-governed-under-adr0003)'s SysML-baseline. Domain Adapter implementation is Layer 5 work per [S3 commitment 15](../TruthModelSchema.md#15-ap242-external-element-references-round-trip-via-layer-5-domain-adapters-where-ap242-can-represent).
- **`relationship/satisfies.schema.json`** — lives in the `aiadra-core` schema bundle, not in this ADR. The ADR governs decisions; the schema implements them.

## References

- [Manifesto.md](../Manifesto.md) — P3 (UUID identity; extended cross-project by ADR/0008), P7 (provenance + uncertainty on relationship records per S1), P11 (AIADRA Core hosts nothing — bounds the "current released Revision" boundary in Decision §3 — release metadata may be read; working payload may not be consumed cross-project).
- [Glossary.md](../Glossary.md) — *Object (Managed Object)*, *Part*, *Requirement*, *Assembly*, *Revision*, *Released Truth*, *`satisfies`* (new entry in Glossary v0.10).
- [TruthModelSchema.md](../TruthModelSchema.md) — S0 (compositional schema; cross-Object references; hybrid within-artifact addressing), S1 (provenance / uncertainty four-level walk; relationship-record container defaults), S2 (release / Revision; revision_content_hash integrity; release transaction atomicity; revision snapshot boundary), S3 (relationship records as first-class addressable; engineering-graph endpoints whole-Object; source-anchored ownership; binary default arity; relationship-type schema mechanism; engineering-graph endpoint form; Float / Fixed binding; per-type cycle / graph class policy; release-time threshold; AP242 round-trip).
- [ADR/0001](0001-storage-substrate.md) — Storage substrate. §3 (acceleration cache — reverse-direction where-used derivation), §4 (sidecar/event invariant — relationship-record validation fires here), §6 (locality tier and staleness — Float external endpoint fetch semantics in working state).
- [ADR/0002](0002-canonical-format.md) — Canonical format. AIADRA YAML Profile for sidecar relationship records.
- [ADR/0003](0003-schema-governance.md) — Schema governance. §2 (discriminator — relationship-type schemas keyed by `type` field), §11 (bump ceremony — MINOR additive for first relationship-type schema).
- [ADR/0005](0005-object-type-part.md) — Object Type: Part. §11 (Part is source for `satisfies`).
- [ADR/0006](0006-object-type-requirement.md) — Object Type: Requirement. §12 (Requirement is target for `satisfies`).
- [ADR/0007](0007-object-type-assembly.md) — Object Type: Assembly. §11 (Assembly is source for `satisfies`); §2 (occurrence-qualified endpoints — pattern subsequent multi-endpoint relationship-type ADRs will reuse, distinct from `satisfies`'s implicit-source single-target shape).
- [ADR/0008](0008-cross-project-object-identity.md) — Cross-project Object identity. §3 (Binding Object Types), §4 (per-type opt-in for direct cross-project endpoints on trace relationships — basis for Decision §3), §5 (`project_scope` identity-locator split), §6 (`revision_content_hash` integrity for Fixed cross-project bindings).
- [OpenQuestions.md](../OpenQuestions.md) — OQ-0003 (failed-transaction audit-log scope — relationship-create / change / retire transactions participate when audit log shape lands), OQ-0007 (Wedge scope adequacy — ADR/0009 unblocks the Wedge's local `satisfies` round-trip; cross-project satisfaction not strictly needed for the Wedge).
- Discussion trail (git-ignored, local only): `Docs/Discussions/20260518-9/Claude1.md` → `Codex1.md` → `Claude2.md` → `Codex2.md` — full working-out across one substantive Codex round (two hard blockers, three refinements, all absorbed) plus a green-light second round.
