---
name: adr-0015-relationship-type-parameter-expression
status: accepted
date: 2026-05-19
supersedes: none
superseded_by: none
resolves: []
---

# ADR/0015 — Relationship Type: `parameter_expression`

## Status

**Accepted** — 2026-05-19. Seventh relationship type after `satisfies`, `composed_of`, `mated_to`, `derived_from`, `refines`, `allocates_to`. Closes the [SystemState Pattern Catalogue](../SystemState.md#2-active-pattern-catalogue) "Asymmetric multi-endpoint serialization | TBD when ADR lands" placeholder open since [ADR/0011](0011-relationship-type-mated-to.md). Pattern-setting at the relationship-type level: declares the **asymmetric multi-endpoint serialization** seed (output_endpoint + input_endpoints) and pins the **fact-level endpoint addressing** mechanism (endpoints are parameter addresses, not Object addresses) for the first time. After this ADR, the named relationship-type catalogue from [ADR/0009 §3](0009-relationship-type-satisfies.md#3-direct-cross-project-endpoint-policy--permit-with-float-semantics-owned-here) is complete except for specialized future ones (`derived_geometry_from`, `depicts`).

## Context

Discussion trail in [`Docs/Discussions/20260519/20260519-5/`](../Discussions/20260519/20260519-5/). Substantial pre-declared constraints existed across the spine and earlier ADRs ([ADR/0005 §11](0005-object-type-part.md), [ADR/0007 §11](0007-object-type-assembly.md), [ADR/0010 §"Pattern inheritance"](0010-relationship-type-composed-of.md), [ADR/0011 §"Pattern declarations summary"](0011-relationship-type-mated-to.md), [TruthModelSchema lines 541 / 593 / 632 / 670](../TruthModelSchema.md)); the ADR's job was to honor those and crystallize the underspecified parts.

[Codex1](../Discussions/20260519/20260519-5/Codex1.md) produced two blockers and the proposal materially shifted in [Claude2](../Discussions/20260519/20260519-5/Claude2.md):

1. The opaque-`formula_string` shape proposed in Claude1 made the canonical `acyclic_dependency` dependency set semantically uncheckable — a record could silently reference a variable not in `input_endpoints` or carry unused endpoints. Repair: explicit `variables[]` symbol-to-endpoint map enforced at the schema level (no formula parsing required by AIADRA Core; language owner enforces the formula↔symbol binding).
2. The "smallest containing Assembly" source-anchoring rule proposed in Claude1 was both over-permissive (Assembly silently rewriting constituent Part definitions through `occurrence_ref` outputs; no occurrence-local parameter model exists) and over-restrictive (skeleton-driven propagation would have been blocked because the downstream Object pulling from a master Skeleton isn't necessarily inside a containing Assembly). Repair: output-owned source-anchoring uniformly; output endpoints schema-rejected if they carry `occurrence_ref`.

[Codex2](../Discussions/20260519/20260519-5/Codex2.md) sign-off with two wording-precision notes (bidirectional symbol↔text validation explicit; Component-output guardrail framed as authority-ownership not provenance-enum). Both incorporated.

Three pressures converge:

1. **Asymmetric multi-endpoint pattern.** [ADR/0011](0011-relationship-type-mated-to.md) declared the *undirected* (symmetric) multi-endpoint serialization for mates. `parameter_expression` is the *directional* counterpart — one parameter is the output (computed value), the rest are inputs (independent variables). Serialization must encode this asymmetry while preserving the multi-endpoint stable-id pattern for the input list.
2. **Fact-level endpoint addressing.** First relationship to use parameter addresses (`<object_uuid>:parameter:<id>`) rather than Object addresses. Establishes the precedent for future fact-level relationship types if any emerge.
3. **Canonical computation invariants.** As the canonical engineering computation linkage, `parameter_expression` must have an *enforceable* dependency contract — the dependency graph the cycle checker walks must be exactly what the record declares. Codex1 Blocker 1 was about this; Decision §2 addresses it.

## Pre-declared constraints honored

| Constraint | Source | Disposition |
|---|---|---|
| Endpoint Type: `Parameter → Parameter(s)` (fact-level) | [ADR/0005 §11](0005-object-type-part.md), [ADR/0007 §11](0007-object-type-assembly.md) | Inherited verbatim. |
| Endpoint address: `<object_uuid>:parameter:<id>` | [TruthModelSchema line 593](../TruthModelSchema.md) | Inherited; encoded as endpoint `object_uuid` + `fact_ref: "parameter:<id>"`. |
| Arity: source + many | [ADR/0005 §11](0005-object-type-part.md), [ADR/0007 §11](0007-object-type-assembly.md), [ADR/0011 §"Pattern declarations summary"](0011-relationship-type-mated-to.md) | Inherited; Decision §1 pins serialization shape. |
| Cycle policy: `acyclic_dependency` | [TruthModelSchema line 632](../TruthModelSchema.md), [ADR/0005 §11](0005-object-type-part.md), [ADR/0007 §11](0007-object-type-assembly.md) | Inherited; activates [ADR/0007 §5](0007-object-type-assembly.md) write-validation closure for `parameter_expression`. |
| Direct cross-project endpoint NO (engineering-structure default) | [ADR/0010 §"Pattern inheritance"](0010-relationship-type-composed-of.md) | Inherited; cross-project parameter use routes through local Component. |
| Indirect-binding (cross-Assembly) | [ADR/0011 §5 + Pattern Catalogue indirect-binding row](0011-relationship-type-mated-to.md) | Inherited; Decision §5. |
| Occurrence-qualified endpoints for placed instances | [ADR/0007 §2](0007-object-type-assembly.md) | Inherited; INPUT endpoints only (output endpoints rejected if they carry `occurrence_ref` — Decision §3). |
| Multi-endpoint stable-id pattern | [ADR/0011 §3](0011-relationship-type-mated-to.md), [S0 commitment 7](../TruthModelSchema.md) | Inherited; applies to `input_endpoints[].id`. Output is singleton; id not required. |
| Skeleton-model use case | [TruthModelSchema line 670](../TruthModelSchema.md) | Canonical use case; explicit in Decision §3. |

## Alternatives Considered

### Endpoint serialization shape

**A1. Unified `endpoints` list with `role: output | input` discriminator.**

> **Rejected.** Cardinality asymmetry (exactly one output vs one-or-more inputs) makes separate fields natural. "Exactly one output endpoint" is simpler to express with separate fields than with a role-discriminator exclusivity constraint.

**A2. Separate `output_endpoint` + `input_endpoints`.** *Chosen — see Decision §1.*

### Expression representation

**B1. Opaque `formula_string` with `input_endpoints[].id` as the variable namespace; dangling references are a tooling-layer warning.** Claude1's original proposal.

> **Rejected.** Cycle detection requires a canonical dependency set. Without a schema-enforceable variable→endpoint binding, a record can silently reference variables not in `input_endpoints`, carry unused inputs, or hide dependencies in unparsed text. Per [TruthModelSchema commitment 13](../TruthModelSchema.md), cycle validation is a Truth Model invariant, not an adapter nicety.

**B2. Pinned AIADRA seed dialect (`aiadra_formula_v0` with grammar).**

> **Rejected.** Different Domain Engines (FreeCAD, KiCad, custom solvers) have native expression languages. Pinning a single dialect either fights every engine or forces double-bookkeeping. Per [Manifesto P11](../Manifesto.md), AIADRA Core ships the pattern; the language is consumer/adapter policy.

**B3. Adapter / project dialect + explicit `variables[]` symbol map.** *Chosen — see Decision §2.* Schema enforces bijection between `input_endpoints[].id` and `variables[].input_endpoint_id` without parsing the formula. Language owner enforces formula↔symbol binding.

### Source-anchoring

**C1. Smallest Assembly containing both ends via composition.** Claude1's original proposal.

> **Rejected.** Created two unresolved cases: (a) Assembly-owned record with `occurrence_ref` output silently rewriting constituent Part definitions (no occurrence-local parameter model exists); (b) skeleton-driven propagation requiring an artificial containment Assembly. Both contradict canonical use cases.

**C2. Output-owned source-anchoring uniformly.** *Chosen — see Decision §3.* The record lives on the Object owning the *output parameter*; Assembly-aggregate cases work because the Assembly itself owns the aggregate parameter; skeleton cases work because downstream Object owns its derived parameter.

### Component participation

**D1. Component-as-input only; Component-as-output deferred.**

> **Rejected.** Component carries `parameter:` per [ADR/0014 §4](0014-object-type-component.md); Component-as-output is uncommon but not nonsensical (a Component's consumer-local computed parameter is plausible). The guardrail (Decision §4) handles the legitimate concern (don't compute datasheet-authoritative fields).

**D2. Component-as-input and Component-as-output with authority-ownership guardrail.** *Chosen — see Decision §4.*

### Cross-project endpoint policy

**E1. Opt in (symmetric with `satisfies` direct-external trace exception).**

> **Rejected.** `parameter_expression` is engineering-structure (per [ADR/0010 §"Pattern inheritance"](0010-relationship-type-composed-of.md)); the target-Type-governs precedent from [ADR/0013](0013-relationship-type-allocates-to.md) places engineering-structure relationships under the Binding-Object-as-target rule. Cross-project parameter references route through local Component.

**E2. Opt out (engineering-structure default).** *Chosen — see Decision §9.*

## Decision

### 1. Endpoint serialization shape

Separate `output_endpoint` (singleton) and `input_endpoints` (list with stable ids).

```yaml
relationship:
  - id: "<local-stable-id>"
    name: "<optional human label>"
    type: "parameter_expression"
    output_endpoint:
      object_uuid: "<output-owner's UUID>"
      fact_ref: "parameter:<output-param-id>"      # REQUIRED
      revision_id: "..."                            # cross-check; present in released records
      # NO occurrence_ref — Decision §3 forbids occurrence-qualified outputs.
    input_endpoints:
      - id: "<input-stable-local-id>"               # REQUIRED per S0 commitment 7
        object_uuid: "..."
        occurrence_ref: "..."                       # OPTIONAL — present when input is on a placed instance
        fact_ref: "parameter:<input-param-id>"
        revision_id: "..."                          # cross-check
      # ... one or more input endpoints
    expression:                                     # See Decision §2
      form: "formula_string"
      language: "..."
      value: "..."
      variables: [...]
```

Asymmetric multi-endpoint pattern: output is singleton (no list semantics); inputs are a list with stable-id discipline per [ADR/0011 §3](0011-relationship-type-mated-to.md). This is the seed declaration for *asymmetric* multi-endpoint serialization — counterpart to [ADR/0011](0011-relationship-type-mated-to.md)'s undirected/symmetric multi-endpoint shape.

### 2. Expression representation — `formula_string` form with explicit `variables[]` binding

The `expression` block uses a discriminator-driven `oneOf` payload. Seed enum: one value — `formula_string`. Future values (`structured_tree`, `external_computation`) deferred to Schema Change Notes.

```yaml
expression:
  form: "formula_string"                          # REQUIRED — discriminator
  language: "<adapter-or-project-policy id>"      # REQUIRED — e.g., "freecad_expression_v1", "aiadra_formula_v0"
  value: "a + b * 2"                              # REQUIRED — opaque string in the named language
  variables:                                      # REQUIRED — explicit symbol → input_endpoint binding
    - symbol: "a"
      input_endpoint_id: "<input-stable-local-id>"
    - symbol: "b"
      input_endpoint_id: "<input-stable-local-id>"
```

**Schema-enforced contract** (Layer 2; AIADRA Core does NOT parse `value`):

1. Every `variables[].input_endpoint_id` resolves to exactly one entry in `input_endpoints[].id`. Hard-fail on dangling reference.
2. Every entry in `input_endpoints[].id` appears as exactly one `variables[].input_endpoint_id`. Hard-fail on unused input. No `allow_unused` escape hatch in seed.
3. Every `variables[].symbol` is unique within the record. Hard-fail on duplicate.
4. `language` is a non-empty string; not enumerated by AIADRA Core (consumer/adapter policy per [Manifesto P11](../Manifesto.md)).

**Language-owner contract** (consumer responsibility, beyond Core's schema reach):

5. Every variable token in `expression.value` resolves to exactly one `variables[].symbol`. (Bidirectional: every symbol declared in `variables` is referenced by `value`; every variable token in `value` is declared in `variables`.)
6. Release-time materialization hard-fails if the named `language` has no project/adapter evaluator available when the output value must be materialized.

Together: AIADRA Core canonicalizes the dependency set (no dangling, no unused); the language owner canonicalizes the formula text. Cycle detection (Decision §6) can trust `input_endpoints` exactly.

### 3. Source-anchoring — output-owned uniformly

**The record lives in the Object owning the output parameter.** Source-anchored per [S3 commitment 3](../TruthModelSchema.md).

Applies uniformly across the use-case spectrum:

- **Within-Object expression** — output and inputs all on Part A → record on Part A.
- **Skeleton-driven propagation** — downstream Part B's `derived_diameter_mm` computed from master Skeleton's `bore_diameter_mm` → record on Part B (the output owner). No containing Assembly required. Canonical use case per [TruthModelSchema §"Skeleton model"](../TruthModelSchema.md).
- **Cross-Object input scattering** — Part A's `derived_param` from Part B's and Part C's parameters → record on Part A. Cross-Object inputs do not require composition between source and inputs.
- **Assembly-owned aggregate** — Assembly's own `total_mass_kg = sum(child.mass_kg)` → record on the Assembly. The Assembly is the output owner because the aggregate parameter is on the Assembly itself, not on a constituent. Inputs are occurrence-qualified refs into constituent Parts / sub-Assemblies / Components.

**What is NOT permitted:** an Assembly-owned `parameter_expression` whose output endpoint targets a *constituent* Object's parameter (e.g., `Part_X.parameter:diameter` via `occurrence_ref` from the Assembly).

- If the output is the reusable Part definition's parameter, the Assembly silently rewrites that Part for every other consumer (cross-context leak).
- If the output is an occurrence-local override of that parameter, that requires an occurrence-local parameter namespace — which does not exist in the seed. Pre-committing one is the configuration/variants case deferred per [ADR/0007 §7](0007-object-type-assembly.md).

Schema enforces this: **`output_endpoint.occurrence_ref` MUST be absent**. Output endpoints are always Object-level (no occurrence qualification); they target the output owner's reusable parameter definition. Input endpoints may carry `occurrence_ref` per [ADR/0007 §2](0007-object-type-assembly.md).

**Future occurrence-local parameter overrides** — Schema Change Note when the configuration/variants ADR lands and the occurrence-local parameter model is defined.

### 4. Component participation — input unrestricted; output authority-guarded

Component participates as both input and output endpoint:

- **Component-as-input:** unrestricted. Datasheet / catalog parameters are natural input endpoints (e.g., Assembly's `total_mass_kg` rolls up Part and Component masses).
- **Component-as-output:** the output parameter's authority MUST be local/consumer-authored on the Component sidecar — NOT a mirrored upstream/datasheet field whose authority lives upstream (per [ADR/0014 §3-4](0014-object-type-component.md)).

The invariant is **authority ownership**: a `parameter_expression` whose output endpoint targets a Component parameter is valid only if that parameter is consumer-authored on the Component (not authored from the upstream binding). Provenance categories on the output parameter (e.g., `human_input`, `derived_for_preview`) are the validation guidance — but the *invariant* is authority ownership, not the exact enum spelling (provenance categories may evolve via Schema Change Note without changing this rule).

Component-as-output is uncommon (most Component parameters are upstream-authored); the guardrail is a discipline anchor, not a usability hurdle.

### 5. Binding mode — indirect (no relationship-level binding)

Per [ADR/0011 §5](0011-relationship-type-mated-to.md) precedent for multi-endpoint cross-Object relationships: `parameter_expression` has **no relationship-level `binding` field**. Endpoint binding is inherited from address-mechanism resolution:

- Within-Object endpoints: container's Revision determines effective parameter value at read time.
- Cross-Object endpoints (Assembly-context with `occurrence_ref`): occurrence-path resolution per [ADR/0010 §3](0010-relationship-type-composed-of.md) determines effective parameter value.
- Cross-Object endpoints (output-owned without containing Assembly, e.g., skeleton case): the input Object's current Revision (Float) or pinned Revision (Fixed) per the input Object's own state.

Endpoint `revision_id` is a **cross-check, never authority**; hard-fail on mismatch between recorded `revision_id` and the value resolved via address mechanism. Matches [ADR/0011 §3](0011-relationship-type-mated-to.md) discipline.

### 6. Cycle policy — `acyclic_dependency` with output→input edge direction

Per pre-declared `acyclic_dependency` from [TruthModelSchema commitment 13](../TruthModelSchema.md). Each `parameter_expression` record contributes edges **`output_parameter → input_parameter`** (one edge per input endpoint) to the project-wide parameter dependency graph. The output parameter depends on each input parameter.

**Write-validation closure rule** per [ADR/0007 §5](0007-object-type-assembly.md):

- At commit, the validator walks the closure of `parameter_expression` records reachable from any changed parameter, following `output → input` edges.
- If the walk revisits a parameter already on the current path, commit hard-fails with the cycle path reported.
- The dependency set per record is canonical thanks to Decision §2's `input_endpoints[].id` ↔ `variables[].input_endpoint_id` bijection — the cycle checker can trust `input_endpoints` exactly.

**Cross-Object scope.** Closure traversal walks via `fact_ref` resolution, not bounded by `composed_of` ancestry. This means cycle detection is whole-project (within the project; cross-project endpoints are not permitted per Decision §9). Acceleration cache per [ADR/0001 §3](0001-storage-substrate.md) is the natural implementation-layer mitigation; ADR commits the rule.

### 7. Optional record properties — minimal seed

Minimal seed per the [ADR/0009 §5](0009-relationship-type-satisfies.md) discipline.

| Field | Required | Notes |
|---|---|---|
| `id` | REQUIRED | Stable local id per [S0 commitment 4](../TruthModelSchema.md). |
| `name` | optional | Mutable human-readable label. |
| `type` | REQUIRED | Constant `"parameter_expression"`. |
| `output_endpoint` | REQUIRED | Singleton; shape per Decision §1. No `occurrence_ref`. |
| `input_endpoints` | REQUIRED | List with one or more entries; each has stable `id`. |
| `expression` | REQUIRED | Discriminator-driven; shape per Decision §2. |
| `fact_provenance`, `fact_uncertainty` | optional | S1 annotations per [S3 commitment 4](../TruthModelSchema.md). |

No `evaluation_priority`, no `cache_policy`, no `expression_units` — all implementation-layer / D7-disqualified derived-view concerns.

### 8. Eventability, release materialization, bundle bump

**Eventability** inherited from [ADR/0009 §6](0009-relationship-type-satisfies.md): `relationship_created`, `relationship_changed`, `relationship_retired`. `_changed` fires on author intent change (expression text edit, language switch, variables map edit, input_endpoints add/remove/edit, output_endpoint re-target).

**Release materialization.** No relationship-level `binding` (Decision §5), so no Float→Fixed flip at the relationship level. Each endpoint's `revision_id` cross-check is pinned in released Revision records per [S2 commitment 8](../TruthModelSchema.md). The *evaluated value* of the output parameter at release lands in the output parameter's released Revision per the standard Revision materialization (no special `parameter_expression`-time rule); the value must be unit-consistent with the output parameter's canonical-unit field (Decision §9 hard-fail otherwise).

**Bundle bump:** **v0.11.0 → v0.12.0**, MINOR additive per [ADR/0003 §11](0003-schema-governance.md). New `relationship/parameter_expression.schema.json`. Seventh occupant of the `relationship/` directory.

**ADR ceremony** per the [amended Promotion Rule commitment 6](../TruthModelSchema.md) — pattern-setting at the relationship-type level. Declares:

- Asymmetric multi-endpoint serialization pattern (counterpart to ADR/0011's undirected/symmetric).
- Fact-level endpoint addressing (parameter addresses, first relationship to use them).
- Discriminator-driven expression payload with explicit binding map.
- Output-owned source-anchoring (uniform; resolves the prior under-specification across pre-declared participation tables).

### 9. Validation rules (Layer 2)

- `output_endpoint` present; `output_endpoint.object_uuid` + `output_endpoint.fact_ref` resolve to an existing parameter address.
- `output_endpoint.occurrence_ref` is ABSENT. Hard-fail at write if present.
- `input_endpoints` is a list of one or more entries. Each entry has stable `id`, `object_uuid`, `fact_ref` (resolving to an existing parameter address); `occurrence_ref` optional.
- `output_endpoint.object_uuid` ≠ any `input_endpoints[].object_uuid` + `fact_ref` combination (self-loop forbidden at the per-record level).
- **Source-anchoring closure:** the record's owning Object UUID equals `output_endpoint.object_uuid`. Hard-fail at write on mismatch.
- **Endpoint Type union:** output endpoint Object Type ∈ {Part, Requirement, Assembly, Component}; each input endpoint Object Type ∈ {Part, Requirement, Assembly, Component}.
- **Component-as-output authority guardrail (Decision §4):** if `output_endpoint` targets a Component sidecar, the targeted parameter's authority must be local/consumer-authored on that Component (not mirrored from upstream binding). Validation guidance: the targeted parameter's `fact_provenance.category` should reflect local authorship; provenance category names are not normatively pinned here.
- **Expression contract (Decision §2):**
  - `expression.form` ∈ {`formula_string`}.
  - `expression.language` is a non-empty string.
  - `expression.value` is a non-empty string.
  - `expression.variables` is a non-empty list. Each entry has `symbol` (non-empty string) + `input_endpoint_id`.
  - Bijection: each `variables[].input_endpoint_id` matches exactly one `input_endpoints[].id`; each `input_endpoints[].id` is referenced by exactly one `variables[].input_endpoint_id`. Hard-fail on dangling reference or unused input.
  - Symbol uniqueness: each `variables[].symbol` is unique within the record.
- **Cycle check (Decision §6):** closure over `parameter_expression` records following `output_parameter → input_parameter` edges is a DAG. Hard-fail at commit on cycle, with cycle path reported.
- **Cross-project endpoints: NONE permitted directly.** Schema rejects `project_scope` on any endpoint. Cross-project parameter references route through a local Component (per [ADR/0014](0014-object-type-component.md)).
- **Released Revisions:** every endpoint carries `revision_id`; the resolved value via address mechanism matches the recorded `revision_id` (hard-fail on mismatch).
- **Unit consistency at release:** the evaluated output value's unit must match the output parameter's canonical-unit field (e.g., `param_total_mass_kg` field must receive a kg value). Hard-fail at release on unit incompatibility — not deferred to adapter convention.
- **Release-time evaluator availability:** if `expression.language` has no project/adapter evaluator available at release, materialization hard-fails (Decision §2 language-owner contract).

## Worked sidecar examples

### Example 1 — Assembly-owned aggregate

An Assembly's `total_mass_kg` is computed as the sum of its constituent occurrences' masses. Output is on the Assembly itself; inputs are occurrence-qualified refs into the constituents.

```yaml
# In ASM-000007 (drive assembly)
object:
  uuid: "0193-ASM-007-..."
  type: "Assembly"
  number: "ASM-000007"
  lifecycle: "in_work"
  schema_version: "0.12.0"

parameter:
  - id: "param_total_mass_kg"
    name: "Total assembly mass"
    value_kg: 14.5                  # evaluated at write / release; consumer-policy when to recompute
    fact_provenance: { category: "computed_result" }
    fact_uncertainty: "computed"

relationship:
  - id: "rel_expr_total_mass"
    name: "Drive assembly total mass aggregate"
    type: "parameter_expression"
    output_endpoint:
      object_uuid: "0193-ASM-007-..."             # the Assembly itself
      fact_ref: "parameter:param_total_mass_kg"
    input_endpoints:
      - id: "ep_motor_mass"
        object_uuid: "0193-C-017-..."             # Component (the motor)
        occurrence_ref: "rel_composed_motor"
        fact_ref: "parameter:param_mass_kg"
      - id: "ep_bracket_mass"
        object_uuid: "0193-P-023-..."             # internal Part (bracket)
        occurrence_ref: "rel_composed_bracket"
        fact_ref: "parameter:param_mass_kg"
      - id: "ep_fasteners_mass"
        object_uuid: "0193-P-024-..."
        occurrence_ref: "rel_composed_fasteners"
        fact_ref: "parameter:param_mass_kg"
    expression:
      form: "formula_string"
      language: "aiadra_formula_v0"
      value: "motor + bracket + fasteners"
      variables:
        - symbol: "motor"
          input_endpoint_id: "ep_motor_mass"
        - symbol: "bracket"
          input_endpoint_id: "ep_bracket_mass"
        - symbol: "fasteners"
          input_endpoint_id: "ep_fasteners_mass"
```

### Example 2 — Skeleton-driven propagation

Downstream Part's `bore_diameter_mm` is driven by a master Skeleton's parameter. No containing Assembly required; record lives on the downstream Part (output owner).

```yaml
# In P-000049 (downstream housing part)
object:
  uuid: "0193-P-049-..."
  type: "Part"
  number: "P-000049"
  lifecycle: "in_work"
  schema_version: "0.12.0"

parameter:
  - id: "param_bore_diameter_mm"
    name: "Main bore diameter"
    value_mm: 25.0
    fact_provenance: { category: "computed_result" }
    fact_uncertainty: "computed"

relationship:
  - id: "rel_expr_bore_from_skeleton"
    name: "Bore diameter driven by master skeleton"
    type: "parameter_expression"
    output_endpoint:
      object_uuid: "0193-P-049-..."                # this Part itself
      fact_ref: "parameter:param_bore_diameter_mm"
    input_endpoints:
      - id: "ep_skeleton_bore"
        object_uuid: "0193-P-MASTER-001-..."       # master Skeleton Part
        # No occurrence_ref — referring to the reusable Part definition's parameter
        fact_ref: "parameter:param_master_bore_diameter_mm"
    expression:
      form: "formula_string"
      language: "aiadra_formula_v0"
      value: "skeleton_bore"
      variables:
        - symbol: "skeleton_bore"
          input_endpoint_id: "ep_skeleton_bore"
```

The expression is `skeleton_bore` (identity-propagation); a more elaborate downstream computation could be `skeleton_bore + 0.5` for clearance, etc.

## Consequences

- **Asymmetric multi-endpoint serialization pattern declared.** [SystemState §2 Pattern Catalogue](../SystemState.md#2-active-pattern-catalogue) row "Asymmetric multi-endpoint serialization | future ADR (`parameter_expression`) | TBD when ADR lands" closes — Applies-to advances to `parameter_expression`; watch-out can summarize the output_endpoint + input_endpoints shape + explicit variables map.
- **Indirect-binding row Applies-to extends** to include `parameter_expression`.
- **Engineering-structure direct-external-endpoint NO row Applies-to extends** to include `parameter_expression`.
- **Fact-level endpoint addressing precedent.** First relationship type to use parameter addresses (`<object_uuid>:parameter:<id>`) as endpoints. Future fact-level relationship types (none currently named) inherit this pattern.
- **Named relationship-type catalogue substantially complete.** After ADR/0015, the named relationship-type set from [ADR/0009 §3](0009-relationship-type-satisfies.md) is complete except for specialized future ones: `derived_geometry_from` (geometric derivation; awaits FreeCAD Domain Adapter scope) and `depicts` (Drawing → Part/Assembly; awaits Drawing Object Type ADR).
- **Schema bundle bump.** Active bundle moves v0.11.0 → v0.12.0. New `relationship/parameter_expression.schema.json`; seventh occupant of `relationship/`.
- **Glossary addition.** [Glossary.md](../Glossary.md) v0.16: new `parameter_expression` entry.
- **SystemState updates.** Three Pattern Catalogue row edits (Asymmetric multi-endpoint serialization Applies-to closes; Indirect-binding Applies-to extends; Engineering-structure direct-external-endpoint NO Applies-to extends). Recent Pattern Changes entry. Current Front advances.
- **No new Pattern Catalogue rows.** This ADR closes a placeholder; doesn't add patterns.
- **Cycle-detection scope.** Closure traversal now also walks `parameter_expression` records alongside `composed_of` and `derived_geometry_from` (when that lands). Implementation-layer cost; acceleration cache mitigation; not in scope for this ADR.
- **Wedge readiness for computed-parameter scenarios.** Skeleton-driven design, Assembly roll-ups, interpart constraints, Requirement-driven sizing are all now schema-supported. The Wedge basic loop (one Part + one Requirement + one `satisfies`) does not exercise this; an extended Wedge with computed parameters is now schema-feasible.
