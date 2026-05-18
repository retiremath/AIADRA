---
name: adr-0010-relationship-type-composed-of
status: accepted
date: 2026-05-18
supersedes: none
superseded_by: none
resolves: []
---

# ADR/0010 — Relationship Type: `composed_of`

## Status

**Accepted** — 2026-05-18. Second relationship-type ADR; first structural / assembly-context relationship ADR. Pins three new pattern declarations on top of ADR/0009's thirteen: transform shape (position + unit quaternion), canonical units at the fact level (schema-fixed millimeters for `composed_of`), and binding-aware nested occurrence path resolution. Activates [ADR/0007 §5](0007-object-type-assembly.md)'s `acyclic_dependency` write-validation closure rule at runtime — `composed_of` is the first relationship type to engage the cycle gate. Supersedes [ADR/0007 §2](0007-object-type-assembly.md)'s worked-example `occurrence_ref: "relationship:<id>"` form with prefix-free `occurrence_ref: "<id>"` syntax (ADR/0007's accepted text remains as historical record per ADRs-are-immutable-once-accepted convention).

## Context

The seed catalogue ([Part](0005-object-type-part.md), [Requirement](0006-object-type-requirement.md), [Assembly](0007-object-type-assembly.md)) declared `composed_of` endpoint participation pending the relationship-type ADR; the first relationship-type ADR ([ADR/0009](0009-relationship-type-satisfies.md)) set thirteen pattern fields for subsequent relationship-type ADRs to inherit; ADR/0007 §2 deferred occurrence path serialization syntax to this ADR.

Three pressures converge here:

1. **Structural payload beyond endpoints.** Unlike `satisfies` (engineering-graph trace; whole-Object endpoints; minimal seed properties), `composed_of` carries spatial / structural payload — each record IS an occurrence per [ADR/0007 §1](0007-object-type-assembly.md), with position + orientation as load-bearing record properties. The transform-representation choice (position + quaternion vs 4×4 matrix vs Euler) propagates to every Domain Adapter that authors or reads assembly placements.
2. **Canonical units at the fact level.** A position fact without a unit is genuinely ambiguous and fails the [S2 archival-readability principle](../TruthModelSchema.md#s2--release--revision) (Revision records must reconstruct correctly years later). Codex1 caught a gap in the original draft that deferred units to "per-project policy"; this ADR pins canonical millimeters with explicit `position_mm` field naming.
3. **Binding-aware path resolution.** Nested occurrence paths (`rel_composed_wrist/rel_composed_servo`) traverse cross-Revision graphs — each segment's `binding` mode determines which Revision state of the sub-Assembly to recurse into. Codex1 caught that the resolution algorithm in the original draft was binding-unaware; this ADR pins Fixed-segment-recurses-into-Revision and Float-segment-recurses-into-resolved-state, with release materialization resolving every Float segment to a concrete `revision_id` for storage in the released Revision record.

`composed_of` is also the survival case for ADR/0009's pattern declarations — the implicit-source + serialized-target shape, declared in ADR/0009 for source-anchored binary relationships, holds for `composed_of` with one structural extension: a relationship-record sub-object (`occurrence:`) carrying authored property content (transform). Codex1's retroactive clarification of ADR/0009's "minimal seed properties" framing — "schemas include semantic payload, not speculative convenience properties" — distinguishes the `occurrence:` sub-object (Type-design-mandated semantic payload) from speculative extras (the kind ADR/0009 §5 forbids).

The discussion trail in [`Docs/Discussions/20260518-10/`](../Discussions/20260518-10/) carries the full alternatives reasoning. Codex1 produced three hard blockers (canonical units; quaternion normalization invariant; binding-aware path resolution) plus four refinements (occurrence_ref-is-special-syntax scoping; ADR/0007 supersession framing; `name` vs `instance_name` guidance; ADR/0009 minimal-properties phrasing); all seven absorbed. Codex2 green-lit Claude2's absorption with no further blocker.

## Alternatives Considered

### Transform position units

**A1. Per-project policy with no schema-level unit.** Original Claude1 draft; cited [S1 commitment 3](../TruthModelSchema.md#3-no-canonical-project-level-defaults) ("no canonical project-level defaults").

> **Rejected.** S1 commitment 3 is about provenance / uncertainty resolution, not engineering units. A position fact without a unit attached to the fact (or schema-fixed) is genuinely ambiguous — the same numbers reconstruct different assemblies in different readers. Breaks archival readability per S2 (Revision records must reconstruct correctly years later) and surfaces as silent canonical mutation when adapters guess.

**A2. Schema-fixed millimeters with `position_mm` field name.** *Chosen — see Decision §2.* Simple; FreeCAD-friendly; matches mechanical CAD and modern PCB convention; field name encodes the unit unmissably; future Schema Change Note may add per-record `unit:` for multi-unit projects if a concrete case surfaces.

**A3. Per-record `unit:` field on the transform.** Generic `position: { value: [...], unit: "mm" }`.

> **Deferred fallback.** More flexible but noisier in the seed; allows multi-unit assemblies (an engineering anti-pattern in practice). Future Schema Change Note path if production cases require it.

### Transform rotation representation

**B1. 4×4 homogeneous transform matrix.** Single matrix encoding rotation + translation + (optionally) scale.

> **Rejected.** Universal kernel input but authoring-unfriendly (humans don't read matrices); non-trivial diff in Git review; 16 floats per occurrence vs 7 for position + quaternion; redundant (6 constraints on rotation block leave 3 DoF).

**B2. Position + Euler angles + order convention.** 3-vector position + 3-vector Euler + `order:` (XYZ / ZYX / intrinsic / extrinsic).

> **Rejected.** Maximally human-readable but suffers gimbal lock at 90° rotations; order convention ambiguity (XYZ vs ZYX vs intrinsic vs extrinsic) makes the same numbers read differently in different libraries; not robust under interpolation.

**B3. Position + unit quaternion `[x, y, z, w]`.** *Chosen — see Decision §2.* FreeCAD-native (matches `Placement.Rotation.Q`); glTF / OCCT / Three.js compatible; robust under interpolation; no gimbal lock; non-redundant; field name `quaternion_xyzw` encodes the component-order convention unmissably.

### Quaternion normalization enforcement

**C1. Warning + adapters renormalize on read.** Layer-2 validator surfaces denormalization as warning; adapters silently renormalize during read.

> **Rejected.** Silent canonical mutation — exactly the failure mode the architecture has avoided everywhere else. An adapter encountering a denormalized quaternion in committed truth would interpret canonical data without an event; that is silent canonical repair.

**C2. Hard validation invariant with deterministic schema-bundle tolerance.** *Chosen — see Decision §2.* `|q|² ∈ [1 - 1e-6, 1 + 1e-6]`; out-of-tolerance is hard validation failure; adapters may renormalize before commit (Transaction-mediated) but never silently on read. Tolerance is schema-bundle-versioned and may tighten in future MAJOR bumps.

### Occurrence path syntax

**D1. Namespace prefix per segment.** `relationship:rel_composed_left_arm/relationship:rel_composed_bolt_1`.

> **Rejected.** Verbose; redundant once the field name (`occurrence_ref`) tells the reader the segments are `composed_of` record ids; clashes with filesystem-path intuition.

**D2. Mixed-prefix (prefix only at top level).** ADR/0007 §2's worked-example form; `relationship:rel_composed_bolt_1` single-level; `relationship:rel_composed_left_arm/rel_composed_bolt_1` nested (prefix only on first segment).

> **Rejected.** Inconsistent shape across single-level and nested forms; the prefix becomes a quirk-of-history readers learn rather than a semantic distinction.

**D3. Bare slash-separated record ids, no prefix.** *Chosen — see Decision §3.* `rel_composed_bolt_1` single-level; `rel_composed_left_arm/rel_composed_bolt_1` nested; consistent shape; readable; matches filesystem-path intuition; supersedes ADR/0007 §2's worked-example form.

### Occurrence path resolution semantics

**E1. String-only walk; no binding-mode discrimination.** Resolver walks segments without addressing which Revision state of each sub-Assembly to use.

> **Rejected.** Underspecified across binding modes — a Float `rel_composed_wrist` could resolve to working state in one read and released state in another, producing different assemblies for the same path string. Caught by Codex1 §3.

**E2. Binding-aware per-segment resolution.** *Chosen — see Decision §3.* Fixed segments recurse into the named target Revision; Float segments in working sidecars recurse per within-project Float read semantics subject to staleness tolerance; Float segments in released parent Revisions resolve to the concrete `revision_id` materialized at release.

### Scale handling

**F1. Include scale field (`scale_factor` or `scale_xyz`).** Per-occurrence scale applied to the target Part.

> **Rejected.** Production engineering anti-pattern — scaling an occurrence usually means the target Object is not actually the same Part. Parametric variation belongs in the Part / Assembly definition or in a future configuration / variant model, not as an occurrence-scale convenience. Future Schema Change Note path if simulation / layout mockup cases require it.

**F2. No scale field; identity scale implicit.** *Chosen — see Decision §2.*

### Identity transform omission

**G1. Omit `transform` for identity placements; reader treats omission as identity.**

> **Rejected.** Invisible default; surfaces as implicit canonical assumption; complicates diffs and parser branches.

**G2. Require `transform` on every record; identity is `[0,0,0]` + `[0,0,0,1]` literal.** *Chosen — see Decision §2.* Predictable diffs; uniform validation; explicit-beats-clever for structural truth.

## Decision

Seven decisions. Two load-bearing pattern declarations (transform shape with canonical units + hard normalization; binding-aware occurrence path resolution). Five inherit ADR/0009 patterns plus structural extensions for assembly-context relationships.

### 1. Endpoint Type constraints, arity, source-anchoring

**Source endpoint Type:** `Assembly`. Per [ADR/0007 §11](0007-object-type-assembly.md).

**Target endpoint Type:** `Part | Assembly`. Per [ADR/0005 §11](0005-object-type-part.md) and [ADR/0007 §11](0007-object-type-assembly.md). **Component** is the most plausible near-term extension; deferred to Component's per-Type ADR or Schema Change Note per [Promotion Rule commitment 9](../TruthModelSchema.md#9-catalogue-work-is-use-case-driven). A future cross-Assembly Binding Object Type may also be added.

**Arity:** binary at the semantic layer. **Serialization: source implicit (the owning Assembly sidecar); `endpoints` array contains exactly one entry — the target.** Inherits ADR/0009 pattern.

**Source-anchoring:** record lives in the source Assembly's `relationship:` namespace per [S3 commitment 3](../TruthModelSchema.md#3-relationships-are-source-anchored). Reverse direction ("what Assemblies contain this Part?") is acceleration-cache-derived per [ADR/0001 §3](0001-storage-substrate.md), never stored.

**Record id IS the occurrence id.** Per [ADR/0007 §1](0007-object-type-assembly.md), each `composed_of` record is one occurrence of the target in the source. The record's stable `id` serves dual purpose: relationship-record identity + occurrence identity (the reference target for `occurrence_ref` on assembly-context relationships per Decision §3 and ADR/0007 §2). No parallel `occurrence:` namespace.

### 2. Transform representation — position + unit quaternion, canonical millimeters, hard normalization invariant

Each `composed_of` record's `occurrence.transform` carries:

```yaml
occurrence:
  instance_name: "bolt_mounting_NE"        # optional; mutable human-readable label
  transform:
    position_mm: [12.5, 8.0, 0.0]          # 3-vector; CANONICAL millimeters
    rotation:
      quaternion_xyzw: [0.0, 0.0, 0.0, 1.0]   # 4-vector; [x, y, z, w]; |q|=1 within tolerance
```

**Position (`position_mm`):**

- 3-vector of floats in **canonical millimeters**. Schema-fixed; no per-record unit.
- Field name encodes the unit unmissably (`_mm` suffix).
- Coordinate frame: target Object's local frame mapped into the source Assembly's local frame.
- Schema validates: array of exactly three numbers.
- The canonical-mm rule applies to `composed_of.occurrence.transform.position_mm` specifically. Other Object Types' `parameter:` records continue to declare per-record `unit:` per [ADR/0005 §4](0005-object-type-part.md) — this is a per-relationship-type unit convention, not a global Object-system unit policy.
- Future Schema Change Note may add per-record `unit:` for multi-unit assemblies (Option A3 fallback) if a concrete production case surfaces.

**Rotation (`quaternion_xyzw`):**

- 4-vector of floats in `[x, y, z, w]` convention (vector-then-scalar).
- Field name encodes the component-order convention unmissably.
- Matches FreeCAD's `Placement.Rotation.Q`, glTF rotation tuple, OCCT's `gp_Quaternion::Get`.
- Schema validates: array of exactly four numbers.

**Hard normalization invariant:**

> `quaternion_xyzw` MUST be unit length within deterministic tolerance. Tolerance for the seed: `|q|² ∈ [1 - 1e-6, 1 + 1e-6]` (squared-magnitude within 1e-6 of unity; equivalent to magnitude within ~5e-7 of unity). Values outside tolerance are a hard validation failure. Adapters MAY renormalize before proposing or committing a change (Transaction-mediated), but committed canonical truth MUST already satisfy the invariant.

The tolerance is declared in the schema bundle / validator rule, versioned with the schema bundle per [ADR/0003](0003-schema-governance.md). Future MAJOR bumps may tighten the tolerance; a permitted tightening path that adapters / projects can plan for.

This rules out silent canonical mutation. An adapter encountering a denormalized quaternion in committed truth surfaces a validation error to the user, who proposes a Transaction to renormalize. The renormalization is then a recorded event, not a phantom rename.

**No scale.** Assembly composition does not scale Parts. If a future use case surfaces, future Schema Change Note may add a scale field; the seed schema does not include one.

**No transform omission default.** Every `composed_of` record MUST carry a `transform`. Identity placement is `position_mm: [0, 0, 0]` + `quaternion_xyzw: [0, 0, 0, 1]` written explicitly.

### 3. Occurrence path serialization — slash-separated record ids, binding-aware resolution

The deferred-from-[ADR/0007 §2](0007-object-type-assembly.md) question: how is an occurrence inside a sub-Assembly referenced from a parent Assembly's assembly-context relationships?

**Decision: slash-separated chain of bare `composed_of` record ids.**

Single-level reference:

```yaml
occurrence_ref: "rel_composed_bolt_1"
```

Nested reference across a sub-Assembly boundary:

```yaml
occurrence_ref: "rel_composed_left_arm/rel_composed_bolt_1"
```

Three-level nesting:

```yaml
occurrence_ref: "rel_composed_left_arm/rel_composed_wrist/rel_composed_servo"
```

**`occurrence_ref` is relationship-type-specific occurrence path language, not a general S0 fact address.** Its segments are bare `composed_of` record ids resolved within successive Assembly states. `fact_ref` continues to use S0 commitment 4's namespace-prefixed format (`parameter:param_x`, `published_ref:pub_y`); `occurrence_ref` is a distinct syntax. This scoping prevents the slash-separated form from leaking into general address resolution.

**ADR/0007 supersession.** [ADR/0007 §2](0007-object-type-assembly.md)'s worked example used `occurrence_ref: "relationship:rel_composed_bolt_1"` with `relationship:` prefix. ADR/0010 supersedes that form with prefix-free `occurrence_ref: "rel_composed_bolt_1"`. ADR/0007's accepted text remains as historical record per ADRs-are-immutable-once-accepted convention; ADR/0010's supersession statement is the durable record.

**Regex constraint:**

> The `composed_of` relationship type constrains occurrence ids to lowercase snake case matching `^[a-z][a-z0-9_]*$`, per-segment in nested paths. This is a per-relationship-type schema constraint, not a general S0 rule.

**Binding-aware resolution algorithm:**

For each segment N of the occurrence path:

1. Look up the `composed_of` record by id in the current resolved Assembly state (working sidecar OR Revision record, depending on context).
2. Check segment N's `binding` mode:
   - **Fixed:** the segment's target endpoint carries `revision_id`. Recurse into the named target's Revision record.
   - **Float in working sidecar:** recurse according to within-project Float read semantics per [S3 commitment 12](../TruthModelSchema.md#12-float-vs-fixed-binding-mode-is-explicit-per-relationship), subject to the operation's staleness tolerance per [ADR/0001 §6](0001-storage-substrate.md).
   - **Float resolved in released parent Revision record:** every Float segment was resolved during release materialization to a concrete `revision_id`; recurse into that Revision record. The Revision record stores fully-resolved path targets.
3. Resolve segment N's endpoint:
   - Part + additional segments remain → **hard validation failure**.
   - Part + last segment → path terminates at this occurrence.
   - Assembly + additional segments remain → recurse to step 1 in the resolved sub-Assembly state.
   - Assembly + next segment absent in resolved sub-Assembly state → **hard validation failure**.

**Why binding-aware:** an occurrence path is not just a string — it's a cross-Revision graph traversal. A Float sub-Assembly may have added / removed occurrences between the parent's last release and current working state; release materialization needs to resolve to a single Revision graph where every path segment is valid. Without binding-aware semantics, the same occurrence path can point to different actual placed instances depending on whether the parent or child Assembly has moved from working state to release state.

### 4. Direct cross-project endpoint policy — NO

Per [ADR/0008 §4](0008-cross-project-object-identity.md) engineering-structure default. `composed_of` endpoints target local Objects only:

- A consumer Assembly composing a catalog Part MUST route through a local Component (the upstream binding per [ADR/0008 §3](0008-cross-project-object-identity.md)).
- A consumer Assembly composing a catalog sub-Assembly MUST route through a local Assembly Binding Object Type (mechanism deferred to subsequent ADR; future Type analogous to Component for procurement bindings).

**Negative case explicit:**

> Direct cross-project `composed_of` endpoints are forbidden. The catalog-Part-into-consumer-Assembly path goes through a local Component, never directly. This default preserves local approval boundary, local where-used queries, procurement / supplier override capacity, and the BOM-derived-from-local-state property of consumer projects.

This is the engineering-structure inverse of ADR/0009's `satisfies` direct-endpoint opt-in. The trace-relationship exception ([ADR/0009 §3](0009-relationship-type-satisfies.md)) does NOT propagate to structural relationships per [ADR/0008 §4](0008-cross-project-object-identity.md).

### 5. Binding, cycle policy, self-policy

**Default binding mode:** `float`. Per [S3 commitment 12](../TruthModelSchema.md#12-float-vs-fixed-binding-mode-is-explicit-per-relationship). An Assembly composing a Part by default tracks the Part's current Revision. `fixed` available for "composed of this Part at this specific Revision" semantics. Allowed values: `"float" | "fixed"`.

**Cycle policy:** `acyclic_dependency`. Per [S3 commitment 13](../TruthModelSchema.md#13-per-type-cycle-and-graph-class-policy). Activated by `composed_of` — first relationship type to engage the policy at runtime.

**Cycle enforcement** per [ADR/0007 §5](0007-object-type-assembly.md):

- The invariant: an Assembly cannot transitively contain itself via any chain of `composed_of` records.
- Check fires at commit time on the merged sidecar / event state.
- **Write-validation closure rule.** Commits creating or modifying `composed_of` records cannot pass validation unless the validator can resolve the transitive composition closure. Unknown / not-fetched composition targets are a **hard validation failure for that write**, not a warning.
- Cross-Object scope: global across Objects in the project, not local to one sidecar.
- Implementation flexibility flagged per ADR/0007 §5: efficient cycle detection at Tier-L scale is non-trivial; Layer-2 validator implementation has freedom (graph algorithms, incremental detection on diff, acceleration-cache-backed indexing per [ADR/0001 §3](0001-storage-substrate.md)). This ADR commits to the invariant and the write-validation closure rule, not the algorithm.

**Self-policy:** `self_forbidden`. An Assembly cannot directly compose itself. The trivially-detectable 1-cycle case of the cycle policy; full `acyclic_dependency` catches multi-step cycles via write-validation closure.

### 6. Record properties — endpoint + occurrence + standard fields

| Field | Required | Notes |
|---|---|---|
| `id` | REQUIRED | Stable local id per [S0 commitment 4](../TruthModelSchema.md#4-hybrid-within-artifact-addressing). **Also serves as the occurrence id** per [ADR/0007 §1](0007-object-type-assembly.md). Format per Decision §3 regex. |
| `name` | optional | Mutable human-readable label; record-level (vs occurrence-level `instance_name`). |
| `type` | REQUIRED | Constant `"composed_of"`. |
| `binding` | REQUIRED | `"float"` \| `"fixed"`. Default Float per Decision §5. |
| `endpoints` | REQUIRED | Single-entry array: the target Part or Assembly endpoint only. Source implicit per Decision §1. |
| `occurrence` | REQUIRED | Sub-object: `instance_name?` + `transform` per Decision §2. Required because every occurrence has a spatial placement; identity transform written explicitly. |
| `fact_provenance`, `fact_uncertainty` | optional | S1 annotations per [S3 commitment 4](../TruthModelSchema.md#4-relationship-properties-follow-s1-annotation-rules). |

**`name` vs `occurrence.instance_name` guidance:**

> `name` is the relationship-record label and `occurrence.instance_name` is the placed-instance label shown in assembly contexts. Projects SHOULD prefer `occurrence.instance_name` for human-visible instance naming and MAY omit `name` when it would duplicate the id or instance name.

This prevents `name` and `instance_name` from becoming two competing labels in Domain Adapter UIs.

**No `quantity` / `count` field.** Per [ADR/0007 §1](0007-object-type-assembly.md). Each occurrence is a separate record. BOM-line aggregation is derived (Layer 4 / project control concern), not authored.

**No `suppressed` / `optional` flag.** Configuration / variant deferral per [ADR/0007 §7](0007-object-type-assembly.md).

**No pattern primitive.** Deferral with future invariant per [ADR/0007 §8](0007-object-type-assembly.md).

### 7. Eventability, release materialization, bundle bump

**Eventability** per [S3 commitment 5](../TruthModelSchema.md#5-relationships-have-create--change--retire-events): `relationship_created`, `relationship_changed`, `relationship_retired`. `_changed` fires on:

- Binding switch (Float ↔ Fixed).
- Endpoint rebind (different target Part / Assembly UUID).
- `occurrence.transform` change (position or rotation).
- `occurrence.instance_name` change (label change).

`occurrence.instance_name` event-family scoping:

> `occurrence.instance_name` changes may use the same `relationship_changed` event family with field target `occurrence.instance_name`, or a future generic record-rename event if the event taxonomy distinguishes label changes. For the seed, `relationship_changed` covers all property changes including labels. The important invariant is that the record id / occurrence id does not change.

Release-time materialization is NOT a `_changed` event per [S3 commitment 12](../TruthModelSchema.md#12-float-vs-fixed-binding-mode-is-explicit-per-relationship). Retirement is tombstoning per [S3 commitment 5](../TruthModelSchema.md#5-relationships-have-create--change--retire-events).

**Release-time materialization:**

- Every endpoint in a released source Assembly's Revision record carries `revision_id` per [S2 commitment 8](../TruthModelSchema.md#8-cross-object-references-may-include-revision_id-required-in-released-revision-records).
- No cross-project endpoints per Decision §4; no `revision_content_hash` materialization.
- Float bindings materialize to Fixed at release; working sidecar preserves authoring intent per [S3 commitment 12](../TruthModelSchema.md#12-float-vs-fixed-binding-mode-is-explicit-per-relationship).
- **Composition cycle write-validation fires at release-time** per [ADR/0007 §5](0007-object-type-assembly.md); the release transaction's cycle check fires on the resolved materialized graph.
- **Nested occurrence path validation fires at release-time.** Every path segment must resolve in the materialized Revision graph per Decision §3; failure hard-fails the release.

**Validation rules** (Layer 2 per [ADR/0001 §4](0001-storage-substrate.md) sidecar/event invariant):

- Source Object Type == Assembly.
- Target Object Type ∈ {Part, Assembly}.
- Target endpoint has `project_scope == null` (within-project only per Decision §4).
- Endpoint UUID resolves to a local Object.
- For Fixed: `revision_id` REQUIRED.
- `occurrence.transform.position_mm` is a 3-vector of numbers.
- `occurrence.transform.rotation.quaternion_xyzw` is a 4-vector of numbers; `|q|² ∈ [1 - 1e-6, 1 + 1e-6]` per Decision §2 hard normalization invariant.
- `composed_of` write-validation closure: transitive composition closure resolves; no cycle; no self-composition per Decision §5.
- Occurrence path validation: every nested-path segment resolves per Decision §3's binding-aware algorithm.
- In released Revision records: every endpoint carries `revision_id`; every nested-path target resolves in the materialized graph.

**Bundle bump:** **v0.6.0 → v0.7.0**, MINOR additive per [ADR/0003 §11](0003-schema-governance.md). New `relationship/composed_of.schema.json`; second occupant of the `relationship/` directory (after [ADR/0009](0009-relationship-type-satisfies.md)'s `satisfies.schema.json`). No existing artifacts to break.

**ADR ceremony** per the [amended Promotion Rule commitment 6](../TruthModelSchema.md#6-promotion-ceremony) — first structural / assembly-context relationship-type ADR; pins three pattern-setting decisions on top of ADR/0009's thirteen (transform shape with canonical units + hard normalization invariant; occurrence path syntax + binding-aware resolution; engineering-structure direct-endpoint NO opt-in); activates ADR/0007 §5's write-validation closure rule at runtime; supersedes ADR/0007 §2's worked-example `occurrence_ref` prefix form. Multiple pattern-setting decisions qualify.

## Worked sidecar example

A mounting bracket Assembly with four bolt occurrences of one Part + one mounting plate + one sub-Assembly (the wrist sub-assembly with a servo two levels deep) demonstrating canonical mm units, explicit identity transform, single-level + nested occurrence paths with binding-aware resolution.

```yaml
object:
  uuid: "0193abcd-1234-7890-..."
  type: "Assembly"
  number: "ASM-000042"
  lifecycle: "in_work"
  schema_version: "0.7.0"
  fact_provenance: { category: "human_input" }
  fact_uncertainty: "verified"

relationship:
  # Single mounting plate at origin — identity transform written explicitly
  - id: "rel_composed_plate"
    type: "composed_of"
    binding: "float"
    endpoints:
      - object_uuid: "0193cccc-plate-..."
    occurrence:
      instance_name: "mounting_plate"
      transform:
        position_mm: [0.0, 0.0, 0.0]
        rotation:
          quaternion_xyzw: [0.0, 0.0, 0.0, 1.0]   # identity

  # Four bolts — same Part UUID, distinct occurrences with distinct transforms
  - id: "rel_composed_bolt_1"
    type: "composed_of"
    binding: "float"
    endpoints:
      - object_uuid: "0193bbbb-bolt-..."
    occurrence:
      instance_name: "bolt_NE"
      transform:
        position_mm: [12.5, 8.0, 0.0]
        rotation:
          quaternion_xyzw: [0.0, 0.0, 0.0, 1.0]

  - id: "rel_composed_bolt_2"
    type: "composed_of"
    binding: "float"
    endpoints:
      - object_uuid: "0193bbbb-bolt-..."     # SAME UUID
    occurrence:
      instance_name: "bolt_NW"
      transform:
        position_mm: [-12.5, 8.0, 0.0]
        rotation:
          quaternion_xyzw: [0.0, 0.0, 0.0, 1.0]

  # rel_composed_bolt_3 (SE), rel_composed_bolt_4 (SW) — analogous, omitted for brevity

  # Sub-Assembly (the wrist) — Fixed at a specific Revision
  - id: "rel_composed_wrist"
    type: "composed_of"
    binding: "fixed"
    endpoints:
      - object_uuid: "0193dddd-wrist-..."
        revision_id: "B"
    occurrence:
      instance_name: "wrist_assembly"
      transform:
        position_mm: [0.0, 15.0, 0.0]
        rotation:
          quaternion_xyzw: [0.0, 0.7071068, 0.0, 0.7071068]   # 90° about Y

  # Assembly-level weld referencing an occurrence inside the wrist sub-Assembly
  # (full mated_to schema in its own future ADR)
  - id: "rel_mate_weld_servo_bracket"
    type: "mated_to"
    endpoints:
      - occurrence_ref: "rel_composed_plate"                          # single-level
        fact_ref: "published_ref:pub_weld_edge_N"
      - occurrence_ref: "rel_composed_wrist/rel_composed_servo"       # nested; binding-aware resolution
        fact_ref: "published_ref:pub_servo_bracket_edge"
    fact_provenance: { category: "human_input" }

  # Satisfies (from ADR/0009) — coexists in same relationship namespace
  - id: "rel_satisfies_req14"
    type: "satisfies"
    binding: "float"
    endpoints:
      - object_uuid: "0193ffff-req14-..."
```

Demonstrates:

- **Canonical mm units** on every `position_mm` field; **explicit `quaternion_xyzw`** field name on every rotation.
- **Identity transform written explicitly** for `rel_composed_plate`.
- **Four occurrences of the same bolt Part UUID** with distinct `instance_name` labels and distinct positions.
- **Mixed Float / Fixed bindings**: plate / bolts Float (track current Revisions); wrist Fixed at Revision B.
- **Nested occurrence path** in `rel_mate_weld_servo_bracket`'s second endpoint: `rel_composed_wrist/rel_composed_servo` — binding-aware resolution per Decision §3: segment 1 (`rel_composed_wrist`) is Fixed at Revision B → recurse into wrist Revision B's record; segment 2 (`rel_composed_servo`) is looked up inside Revision B's resolved state.
- **`satisfies` record** from ADR/0009 unchanged — coexists cleanly with `composed_of` records in the same `relationship:` namespace.

At release of this Assembly:

- Float `composed_of` bindings materialize: `rel_composed_plate` / `rel_composed_bolt_1..4` target endpoints gain `revision_id` of the target Part's released Revision; `rel_satisfies_req14` gains `revision_id` per ADR/0009.
- `rel_composed_wrist` Fixed binding copied verbatim into the Revision record.
- Nested occurrence path on `rel_mate_weld_servo_bracket` validates against the materialized graph: wrist Revision B must contain a `rel_composed_servo` record; failure at this step hard-fails the release.
- Write-validation closure cycle check fires on the resolved composition graph: no Assembly contains itself transitively; release passes.

## Consequences

- **Schema bundle bump.** Active bundle moves v0.6.0 → v0.7.0. New `sidecar/Assembly.schema.json` (and related) accept `relationship:` records with `type: "composed_of"`; the new `relationship/composed_of.schema.json` declares endpoint Type constraints, arity, binding mode, cycle policy, self policy, occurrence sub-object shape, canonical mm units, hard quaternion normalization invariant with deterministic tolerance, and binding-aware occurrence path resolution semantics. Tolerance value `|q|² ∈ [1 - 1e-6, 1 + 1e-6]` versioned with the bundle; future MAJOR bumps may tighten.
- **Glossary update.** [Glossary](../Glossary.md) bumps v0.10 → v0.11 with a new entry for *`composed_of`* citing this ADR; existing *Assembly* entry already references `composed_of` by name.
- **The Wedge's Assembly extension is unblocked.** With ADR/0009 (`satisfies`) and ADR/0010 (`composed_of`) both pinned, the Wedge can extend from one-Part scope to Assembly-containing scope. The basic Wedge (one Part + one Requirement) doesn't need composition; the extended Wedge variant (Assembly + Parts + Requirement) does.
- **`acyclic_dependency` policy is operationally active.** First relationship type to engage [S3 commitment 13](../TruthModelSchema.md#13-per-type-cycle-and-graph-class-policy)'s cycle gate at runtime. Layer-2 validator implementation work to deliver the write-validation closure rule per [ADR/0007 §5](0007-object-type-assembly.md).
- **ADR/0007 §2 supersession.** The worked-example `occurrence_ref: "relationship:rel_composed_bolt_1"` form is superseded by prefix-free `occurrence_ref: "rel_composed_bolt_1"`. ADR/0007's accepted text remains historical record; readers consulting ADR/0007 §2 should be aware of this ADR's supersession. (ADR/0007 itself is unedited.)
- **Pattern inheritance for subsequent assembly-context relationship-type ADRs.** `mated_to`, `parameter_expression` with cross-Assembly spans, and future assembly-context relationships inherit:
  - Transform shape (position + quaternion) for any relationship needing spatial placement.
  - Canonical units at the fact level (per-relationship-type unit declaration as the pattern for any future unit-bearing relationship).
  - Binding-aware nested occurrence path resolution for any occurrence-path-bearing relationship.
  - Engineering-structure direct-endpoint NO default per ADR/0008 §4 — applies to `mated_to`, `derived_geometry_from`, `parameter_expression`.
- **ADR/0009 retroactive clarification (non-amendment).** Codex1 §12's sharpening of ADR/0009's "minimal seed properties" framing: "Relationship-type schemas include only properties required by that relationship type's semantics. Speculative convenience properties are deferred." For `composed_of`, `occurrence:` is semantic payload; for `satisfies`, no extras. The clarification is recorded here in ADR/0010 as a wording note for subsequent relationship-type ADRs to reference; ADR/0009's accepted text is unchanged.
- **Cross-Assembly Binding Object Type deferred.** A future Type analogous to Component but for catalog-Assembly composition is deferred until concrete cross-project Assembly reuse case surfaces.
- **Component target Type deferred.** Per Component's per-Type ADR or its Schema Change Note.
- **Scale field deferred.** Future Schema Change Note if production case surfaces.
- **Pattern primitives and configuration / variants deferred.** Per [ADR/0007 §7 / §8](0007-object-type-assembly.md).
- **Cycle-detection algorithm deferred.** Layer-2 validator implementation freedom per [ADR/0007 §5](0007-object-type-assembly.md).
- **Unit-policy multi-unit fallback deferred.** Future Schema Change Note adds per-record `unit:` (Option A3) if multi-unit production case surfaces; default mm remains.
- **Quaternion-normalization tolerance versioned with bundle.** Future MAJOR bumps may tighten; adapters / projects can plan for tightening through ADR/0003's bundle-bump governance path.
- **`relationship/composed_of.schema.json`** — lives in the `aiadra-core` schema bundle, not in this ADR. The ADR governs decisions; the schema implements them.

## References

- [Manifesto.md](../Manifesto.md) — P3 (UUID identity), P6 (Parameters first, raw geometry last — Assembly composition is structural authoring, not raw geometry), P7 (provenance + uncertainty on relationship records per S1), P11 (AIADRA Core hosts nothing — bounds direct-cross-project-endpoint NO default).
- [Glossary.md](../Glossary.md) — *Object (Managed Object)*, *Assembly*, *Part*, *Revision*, *Released Truth*, *UUID*, *Number*, *`satisfies`* (precedent first relationship-type entry), *`composed_of`* (new entry in Glossary v0.11).
- [TruthModelSchema.md](../TruthModelSchema.md) — S0 (compositional schema; cross-Object references; hybrid within-artifact addressing), S1 (provenance / uncertainty; computed facts with `derived_from`), S2 (release / Revision; revision snapshot boundary; release transaction atomicity), S3 (relationship records as first-class addressable; engineering-graph endpoints whole-Object; source-anchored ownership; binary default arity; relationship-type schema mechanism; engineering-graph endpoint form; Float / Fixed binding; per-type cycle / graph class policy with `acyclic_dependency`).
- [ADR/0001](0001-storage-substrate.md) — Storage substrate. §3 (acceleration cache — reverse where-used; cycle-detection indexing), §4 (sidecar/event invariant — write-validation fires here), §6 (locality tier and staleness — Float occurrence path resolution in working state).
- [ADR/0002](0002-canonical-format.md) — Canonical format. AIADRA YAML Profile for sidecar relationship records with `occurrence:` sub-object.
- [ADR/0003](0003-schema-governance.md) — Schema governance. §2 (discriminator), §11 (bump ceremony — MINOR additive for `composed_of` schema); bundle-versioned tolerance for hard normalization invariant.
- [ADR/0005](0005-object-type-part.md) — Object Type: Part. §11 (Part is target for `composed_of`); §4 (per-record `unit:` on `parameter:` — context for canonical-mm-only-on-composed_of scope).
- [ADR/0007](0007-object-type-assembly.md) — Object Type: Assembly. §1 (occurrence semantics — record id IS occurrence id; no parallel namespace), §2 (occurrence-qualified endpoint rule — ADR/0010 supersedes the prefix-bearing worked-example form), §5 (cycle policy enforcement with write-validation closure — ADR/0010 activates at runtime), §6 (Float / Fixed binding), §7 (configuration / variants deferred), §8 (pattern semantics deferred with per-occurrence-addressability future invariant), §11 (Assembly endpoint participation).
- [ADR/0008](0008-cross-project-object-identity.md) — Cross-project Object identity. §3 (Binding Object Types — Component for procurement; future cross-Assembly Binding Type for catalog Assembly reuse), §4 (engineering-structure direct-endpoint NO default — basis for Decision §4).
- [ADR/0009](0009-relationship-type-satisfies.md) — Relationship Type: `satisfies`. Pattern declarations 1–13 (source-anchoring serialization, implicit source + serialized target, whole-Object endpoint shape, binding / cycle / self policy declarations, release materialization, minimal seed properties); ADR/0010 inherits all thirteen and adds three structural-relationship-specific declarations (transform shape, canonical units, binding-aware path resolution).
- [OpenQuestions.md](../OpenQuestions.md) — OQ-0007 (Wedge scope adequacy — ADR/0010 unblocks the Wedge's Assembly extension; basic Wedge does not strictly need composition).
- Discussion trail (git-ignored, local only): `Docs/Discussions/20260518-10/Claude1.md` → `Codex1.md` → `Claude2.md` → `Codex2.md` — full working-out across one substantive Codex round (three hard blockers, four refinements, all absorbed) plus a green-light second round.
