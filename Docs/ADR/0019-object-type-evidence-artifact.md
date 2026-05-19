---
name: adr-0019-object-type-evidence-artifact
status: accepted
date: 2026-05-19
supersedes: none
superseded_by: none
resolves: []
---

# ADR/0019 — Object Type: EvidenceArtifact

## Status

**Accepted** — 2026-05-19. Seventh Object Type after Part / Requirement / Assembly / Component / SoftwareModule / Drawing. Second **Attachment-bearing Object** instance — first reuse of the [ADR/0017](0017-object-type-drawing.md) template, validating it for a non-Drawing Object Type. Inherits the `attachment:` namespace shape, structural D7-escape, algorithm-qualified hash discipline, and `derived_from_attachment_id` lineage rules verbatim, with **two EvidenceArtifact-specific specializations**: (1) `source_authoring` MUST be the canonical evidence payload (raw result / signed report / measurement log), not setup-only; (2) every `parameter:` record carries explicit lineage to supporting attachment(s) via `fact_provenance.derived_from`. **No relationship-type schema extensions in this bundle** — Requirement-to-EvidenceArtifact citation/verification is deliberately deferred to the future V&V relationship-type ADR, not modeled via `allocates_to`.

Closes the EvidenceArtifact deferral from [Glossary "Object (Managed Object)" candidate pool](../Glossary.md) Tier-2 Types and from [TruthModelSchema line 928](../TruthModelSchema.md). After ADR/0019, both Attachment-bearing Object Types from the Promotion Rule commitment-5 named-example list are operationalized; the V&V Object Type triad (TestProcedure + EvidenceArtifact + future `verifies`/`tested_against`/`cites` relationships) needs only TestProcedure to be complete.

## Context

Discussion trail in [`Docs/Discussions/20260519/20260519-9/`](../Discussions/20260519/20260519-9/). [Codex1](../Discussions/20260519/20260519-9/Codex1.md) produced two blockers and seven non-blockers; both blockers tightly scoped and structurally addressed in [Claude2](../Discussions/20260519/20260519-9/Claude2.md). Per the protocol's [one-more-round exception](../Discussions/Transfer/PROTOCOL.md), Petre authorized close-on-Claude2 due to Codex token availability constraints; convergence rests on Claude2 meeting Codex1's stated close conditions exactly:

1. EvidenceArtifact-specific canonical evidence-basis rule for `source_authoring` attachments + parameter lineage to supporting attachments — encoded in Decision §3 + §4 + §8 below.
2. Removal of `allocates_to` target extension; Requirement-to-EvidenceArtifact citation explicitly deferred to V&V relationship ADR — encoded in Decision §5 below.

Both repairs land per Codex1's specifications.

Two pressures converge:

1. **First reuse of ADR/0017's Attachment-bearing template.** The structural mechanics (`attachment:` namespace; required `source_authoring`; lineage chain; hash-as-authority) inherit verbatim. EvidenceArtifact validates the template's reusability without modification. The specialization is *semantic* (what counts as `source_authoring` for evidence) and *additive* (parameter lineage discipline), not structural.
2. **Canonical evidence record, not loose attachment container.** A released EvidenceArtifact must not be reconstructable as "input deck + hand-entered result values" without a canonical evidence output basis. The schema enforces this through (a) the inherited `source_authoring`-required-at-release invariant from ADR/0017 specialized in Decision §3, and (b) the new required `fact_provenance.derived_from` on every `parameter:` record pointing at supporting attachment(s).

## Promotion Rule walk — via Attachment-bearing Object pattern

Inherits from [ADR/0017 §"Promotion Rule walk"](0017-object-type-drawing.md). EvidenceArtifact passes the [Promotion Rule capability test](../TruthModelSchema.md) via the same **Attachment-bearing Object** named non-disqualifier pattern from [commitment 5](../TruthModelSchema.md):

- **C1 — Independent identity.** EvidenceArtifact `EVD-000043` has stable local UUID + Number — the engineering evidence record persists independent of any specific simulation rerun, test reproduction, or attachment re-export.
- **C2 — Independent lifecycle.** Evidence has its own release cadence — `in_work` while authoring; `released` when sealed as an evidence record (often tied to a Test execution closure); `retired` if superseded by re-execution.
- **C3 — Independent referenceability.** Cited by multiple Tests, Requirements, Releases (per [TruthModelSchema line 928](../TruthModelSchema.md)); future `verified_by` / `tested_against` / `cites` relationships will populate the citation graph.
- **C4 — Independent provenance / approval.** Evidence approval is its own decision — typically test engineer + technical reviewer sign-off.

**D1–D7 disqualifier walk:**

- **D7 (Derived view)** — N/A *because* the schema requires `source_authoring` attachment at release per inherited [ADR/0017 §2](0017-object-type-drawing.md), specialized in Decision §3 to be the canonical evidence payload (not setup-only). The authored canonical layer is structural; D7 is excluded.
- **D1–D6** — N/A or trivially pass.

Conclusion: **EvidenceArtifact is a first-class Object Type via the Attachment-bearing Object pattern.** Seventh Object Type; second Attachment-bearing instance.

## Alternatives Considered

### `source_authoring` semantic for evidence

**A1. Inherit ADR/0017's generic `source_authoring` (any authored canonical payload).** Claude1's original proposal.

> **Rejected (Codex1 Blocker 1).** Generic `source_authoring` permits "input deck only" as the canonical layer for an EvidenceArtifact — but an input deck is method/setup, not evidence. A released EvidenceArtifact under that interpretation could be reconstructable as "we had a method to collect evidence, plus some hand-entered values" — which is not evidence.

**A2. EvidenceArtifact-specific specialization: `source_authoring` must include canonical evidence payload (result / report / log), not setup-only.** *Chosen — see Decision §3.*

### Parameter inclusion and lineage

**B1. Exclude `parameter:` from EvidenceArtifact seed (parity with Drawing).**

> **Rejected.** Burying measured / simulated / analyzed values in attachment payload makes them non-diffable, non-queryable, non-unit-anchored. Canonical engineering facts belong on the sidecar.

**B2. Include `parameter:` without lineage discipline (any free-floating evidence value).**

> **Rejected (Codex1 Blocker 1).** Lets parameters drift from the attachment that supports them; "hand-entered result values" pathology Codex named.

**B3. Include `parameter:` with required `fact_provenance.derived_from` referencing supporting attachment(s).** *Chosen — see Decision §4 + §8.* Reuses S1's existing `fact_provenance.derived_from` field; no new schema machinery; full chain enforceable.

### Requirement-to-EvidenceArtifact citation

**C1. Extend `allocates_to` target Type union to include EvidenceArtifact ("Requirement allocated to evidence record"). **Claude1's original proposal.

> **Rejected (Codex1 Blocker 2).** Crosses a semantic wire. `allocates_to` is responsibility-assignment (Requirement → deliverable Object responsible for fulfilling it). EvidenceArtifact is not responsible for fulfilling a product Requirement; it records what was observed. The relationship saying "this evidence verifies / supports this Requirement" is the V&V relationship family ([ADR/0009 Alternatives §E](0009-relationship-type-satisfies.md)) deferred until TestProcedure + `verifies` taxonomy lands. Extending `allocates_to` now would canonicalize a wrong-verb trace.

**C2. Defer Requirement-to-EvidenceArtifact citation to V&V relationship-type ADR; no seed relationship-type schema extension.** *Chosen — see Decision §5.*

### Number prefix

**D1. `EA-NNNNNN`.**

> **Rejected.** Ambiguous (could read as "Electrical Assembly" or similar).

**D2. `EVD-NNNNNN`.** *Chosen — see Decision §1.* Established engineering convention for "evidence."

### `outcome` field on EvidenceArtifact

**E1. Include `outcome: passed | failed | inconclusive | n/a` on the sidecar.**

> **Rejected.** Outcome is a V&V judgment relative to a specific Requirement / acceptance criterion; the same evidence can pass one criterion and fail another. Belongs in the V&V relationship, not on the evidence record. Defer to V&V ADR.

**E2. Defer to V&V relationships.** *Chosen.*

## Decision

### 1. Number prefix + Type name

**Type name:** `EvidenceArtifact` (PascalCase).
**TypeSpecific block:** `evidence:` (snake_case singleton; matches `requirement:`, `drawing:` pattern; per [ADR/0006 §"Consequences" line 396](0006-object-type-requirement.md) pre-declaration).
**Number prefix:** `EVD-NNNNNN`. Six-digit zero-padded sequential allocation from the Reservation file per [ADR/0004](0004-number-allocation.md).

### 2. TypeSpecific `evidence:` block

Singleton TypeSpecific block. Conservative seed; only `summary` and `evidence_kind` REQUIRED.

```yaml
evidence:
  summary: "string"               # REQUIRED — short textual canonical fact
  evidence_kind: "string"         # REQUIRED — enum (see below)
  collected_at: "string"          # OPTIONAL — ISO8601 timestamp when collected
  collection_context: "string"    # OPTIONAL — prose-only human-readable context (test stand identifier,
                                  #            simulation environment notes, inspection location, environmental conditions)
```

**`evidence_kind` enum (seed):**

- **`simulation`** — finite-element / CFD / kinematic / electrical / similar simulation output.
- **`test_report`** — physical test execution report (load test, vibration, EMC, etc.).
- **`measurement`** — direct quantitative measurement (dimensional inspection, weight, electrical parameter).
- **`inspection`** — qualitative inspection result (visual, NDT, surface finish).
- **`calibration_certificate`** — instrument calibration record.
- **`analysis`** — calculated / derived analysis (hand calc, spreadsheet, analytical method).
- **`other`** — escape hatch; descriptor lives in `collection_context`. Schema Change Note can extend the enum when recurring `other` patterns surface.

**`collection_context` guardrail:** prose-only human-readable summary. NOT a structured method/procedure linkage; structured TestProcedure citation lives in the future V&V relationship family. To prevent the field from becoming a junk drawer, the schema gives no field-shape; project policy may add structure but the seed treats `collection_context` as free-form text.

**`summary` is the textual canonical fact** per [ADR/0006 §"Consequences" line 397](0006-object-type-requirement.md) pattern (the structured-text content pattern for "textual canonical fact" pre-declared by Requirement). Short prose; not a full report (the report is in `attachment:`).

### 3. `attachment:` namespace — inherited from ADR/0017 with EvidenceArtifact-specific `source_authoring` semantic

Structural shape, role enum (`source_authoring` / `rendered_primary` / `derived_secondary`), required fields, `derived_from_attachment_id` lineage discipline, algorithm-qualified `content_hash`, `vault_path` non-authoritative, pre-commit resolution, release invariants — all inherited verbatim from [ADR/0017 §2](0017-object-type-drawing.md).

**EvidenceArtifact-specific specialization of `source_authoring` semantic:**

> For EvidenceArtifact, at least one released `source_authoring` attachment MUST be the **canonical evidence payload** — the raw measurement log, solver result package, signed test report, lab notebook export, calibration certificate, or equivalent canonical record of the evidence collected. Method / setup files (simulation input decks, fixture configurations, scripts, test procedures-as-files) MAY be present as additional `source_authoring` records as part of the canonical evidence package, but MUST NOT be the *only* `source_authoring` attachment. A released EvidenceArtifact must not be reconstructable as "input deck + hand-entered result values" without a canonical evidence output or result basis attached and named.

This is an EvidenceArtifact-specific specialization of the generic ADR/0017 `source_authoring` semantic. Drawing's `source_authoring` is the authored canonical drawing payload (DWG / source PDF); EvidenceArtifact's `source_authoring` must include the canonical evidence-result payload.

**Validation guidance** (not fully schema-enforceable; surfaced for review):

> Sidecar `parameter:` values are the queryable canonical extracted facts; `attachment:` payloads are the immutable supporting basis. Tooling may not parse every attachment kind. When a parser / checker exists and finds disagreement between an extracted sidecar parameter and the attachment it claims as basis, that is a hard validation failure at release (or at the specific extraction check). Authority on mismatch: canonical chain is parameter → `derived_from` → attachment → `content_hash` → Vault bytes — every link an authoritative anchor.

**Common shapes for EvidenceArtifact attachment sets:**

- Simulation: `source_authoring` = solver result package (the actual computed output); additional `source_authoring` = simulation input deck (method/setup, valid as additional source). `rendered_primary` = PDF report (derived from solver results). `derived_secondary` = visualization exports, plot images.
- Test report: `source_authoring` = signed test report + raw instrument log (canonical evidence). `rendered_primary` = the PDF for distribution. `derived_secondary` = instrument-specific exports.
- Measurement: `source_authoring` = CMM session file / measurement record file. No derivatives in simple cases.

### 4. Namespace set

Four of Part's seven plus the inherited `attachment:` plus singleton `evidence:`.

| Namespace | In EvidenceArtifact seed? | Notes |
|---|---|---|
| `parameter:` | YES | Canonical measured / simulated / analyzed values. Field-name-encoded units (`peak_stress_mpa`, `max_temperature_c`). **Each record carries `fact_provenance.derived_from` lineage to supporting attachment(s)** per Decision §4-lineage and §8 validation. |
| `design_intent:` | YES | Rationale for evidence collection; conditions under which it applies; substitution / re-execution constraints; anchors by id to attachment records or future citation relationships. |
| `feature:` | NO | Not internally designed. |
| `relationship:` | YES | Present for future V&V relationship participation (`verified_by` / `tested_against` / `cites`). NO seed schema extension to existing relationships per Decision §5. |
| `published_ref:` | NO | No geometric reference points. |
| `geometry_ref:` | NO | No kernel geometry. |
| `material:` | NO | N/A. |
| `source:` | NO | Requirement-specific. |
| **`attachment:`** (inherited from ADR/0017) | YES | Vault-attached canonical bytes per Decision §3 with EvidenceArtifact-specific `source_authoring` specialization. |

**Four of Part's seven** (`parameter:`, `design_intent:`, `relationship:`, plus inherited `attachment:` and singleton `evidence:`). The genuine namespace divergence from Drawing is the inclusion of `parameter:` for queryable canonical evidence values.

**Parameter lineage discipline** (EvidenceArtifact-specific):

Every `parameter:` record on an EvidenceArtifact sidecar MUST carry `fact_provenance.derived_from` (reusing the existing S1 lineage field per [TruthModelSchema §S1](../TruthModelSchema.md)). The list MUST contain at least one entry of the form `"attachment:<id>"` referencing an existing `attachment:` record in the same sidecar. Other lineage forms (e.g., references to other Objects' parameters) are permitted alongside but at minimum one MUST be an attachment reference.

```yaml
parameter:
  - id: "param_peak_stress_mpa"
    name: "Peak von Mises stress"
    value_mpa: 187
    fact_provenance:
      category: "computed_result"
      derived_from: ["attachment:att_solver_results"]   # REQUIRED on EvidenceArtifact
    fact_uncertainty: "computed"
```

The referenced attachment's own `derived_from_attachment_id` lineage chain (per inherited [ADR/0017 §2](0017-object-type-drawing.md)) terminates at a `source_authoring` record — so the parameter's full lineage chain reaches the canonical evidence payload.

### 5. Relationship participation — NO seed schema extension

**Deferred / NOT in seed:**

- **`allocates_to` target — NOT extended in this bundle.** Per Codex1 Blocker 2: `allocates_to` is responsibility-assignment; EvidenceArtifact is not responsible for fulfilling a product Requirement. The relationship saying "this evidence verifies / supports this Requirement" is the V&V relationship family deferred until TestProcedure + `verifies` taxonomy lands. Extending `allocates_to` now would canonicalize a wrong-verb trace.
- **`verified_by` / `tested_against` / `cites`** — future V&V relationships per [ADR/0005 §11 line 214](0005-object-type-part.md) and [ADR/0007 §11 line 245](0007-object-type-assembly.md). Their schema requires TestProcedure as a peer Object Type. Out of scope.
- **`composed_of` / `mated_to` / `parameter_expression` / `depicts`** — semantic non-fit.
- **`satisfies` source** — plausible but requires ADR/0009 endpoint extension. Defer.

**EvidenceArtifact's `relationship:` namespace exists in the seed schema** as an empty container for future V&V relationships to populate, but ADR/0019 introduces no relationship endpoint extensions. Requirement-to-EvidenceArtifact citation must wait for the V&V relationship-type ADR — this is a deliberate gap, not an oversight. Users SHOULD NOT use `allocates_to` as a temporary stand-in.

### 6. AIADRA Core hosts nothing — explicit walk

[Manifesto P11](../Manifesto.md). Inherited from ADR/0017's posture:

- No Core-hosted EvidenceArtifact registry. Per-project evidence records live in the project's own Git / Commonspace.
- No Core-hosted simulation runner / test instrument coordinator. Domain Adapter / Domain Engine concerns.
- No Core-hosted Vault. Vault Adapter pattern per [Glossary "Vault Adapter"](../Glossary.md); attachment bytes Vault-resident, `vault_path` locator-hint only.
- No registry-shaped fields. `vault_path` non-authoritative; `content_hash` authoritative.

### 7. Lifecycle, eventability, Revisions, bundle bump

**Lifecycle** independent per Promotion C2. States: `in_work` → `released` → `retired`.

**Eventability** per [S3 commitment 5](../TruthModelSchema.md): `evidence_artifact_created`, `evidence_artifact_changed`, `evidence_artifact_released`, `evidence_artifact_retired` (snake-cased per the convention used for `software_module_*` events in [ADR/0016 §8](0016-object-type-software-module.md)). `_changed` fires on `evidence:` block edit, attachment add/remove, parameter edit (including lineage edit), relationship-namespace edit.

**Revision schema** per [S2 commitment 1](../TruthModelSchema.md). Each EvidenceArtifact Revision is a separate immutable artifact at canonical path `revisions/<object-uuid>/<revision-id>.yaml`. Released EvidenceArtifact Revision MUST carry:

- At least one `attachment:` record with `role: source_authoring` AND `content_hash` resolved (per inherited [ADR/0017 §2](0017-object-type-drawing.md) invariant; specialized per Decision §3 to require canonical evidence payload).
- Every `parameter:` record carrying `fact_provenance.derived_from` with at least one valid `attachment:<id>` reference per Decision §4 lineage discipline.

**Bundle bump:** **v0.15.0 → v0.16.0**, MINOR additive per [ADR/0003 §11](0003-schema-governance.md). Changes:

- NEW: `sidecar/EvidenceArtifact.schema.json`.
- NEW: `object.type = "EvidenceArtifact"` discriminator value.
- NEW: `EVD-NNNNNN` Number prefix mapping.

**No relationship-type schema extensions in this bundle** (per Decision §5). Bundle bump scope is sidecar + discriminator + prefix only.

No existing artifacts break. All MINOR additive.

### 8. Validation rules (Layer 2)

- `object.type == "EvidenceArtifact"`.
- `evidence:` singleton block present with at least `summary` (non-empty string) and `evidence_kind`.
- `evidence.evidence_kind` ∈ {`simulation`, `test_report`, `measurement`, `inspection`, `calibration_certificate`, `analysis`, `other`}.
- `evidence.collected_at` (if present) is ISO8601 timestamp.
- `attachment:` namespace rules inherited from [ADR/0017 §"Decision §8"](0017-object-type-drawing.md): record shape; `derived_from_attachment_id` coupling; lineage chain discipline; `content_hash` unconditionally required on committed records; `vault_path` non-authoritative; **release-state invariant: at least one `source_authoring` record with resolved `content_hash`, which (per Decision §3) MUST be the canonical evidence payload** (semantic check; tooling-aided where parser available).
- **Parameter lineage discipline (EvidenceArtifact-specific):**
  - Every `parameter:` record carries `fact_provenance.derived_from`.
  - `fact_provenance.derived_from` is a non-empty list.
  - At least one entry in the list has the form `"attachment:<id>"` referencing an existing `attachment:` record in the same EvidenceArtifact sidecar.
  - Hard-fail at write on dangling `attachment:<id>` references.
  - The referenced attachment's `derived_from_attachment_id` lineage chain (when applicable) terminates at a `source_authoring` record (inherited from ADR/0017 lineage rules).
- `parameter:` namespace canonical-unit-at-field-name discipline inherited from Part (`_mm`, `_mpa`, `_n`, `_c`, etc. carry units in field name; no unqualified numeric facts).
- `relationship:` namespace exists; **no relationship-type-specific schema constraints in this bundle.**

## Worked sidecar example

A finite-element simulation evidence record for a drive bracket peak-stress analysis. Note: `source_authoring` includes the canonical evidence payload (solver result package) AND additional source files (input deck); each `parameter:` carries explicit lineage to its supporting attachment.

```yaml
object:
  uuid: "0193abcd-dddd-7a00-9ccc-444444444444"
  type: "EvidenceArtifact"
  number: "EVD-000043"
  lifecycle: "released"
  schema_version: "0.16.0"

evidence:
  summary: "FEA simulation of drive bracket under maximum operating load shows peak von Mises stress 187 MPa at mounting boss fillet — below 250 MPa yield threshold."
  evidence_kind: "simulation"
  collected_at: "2026-05-15T14:32:00Z"
  collection_context: "FreeCAD FEM + CalculiX solver on workstation WS-04; mesh density refined to 2mm at mounting boss; load case derived from REQ-000058 operating-load envelope plus 1.5x safety factor"

parameter:
  - id: "param_peak_stress_mpa"
    name: "Peak von Mises stress"
    value_mpa: 187
    fact_provenance:
      category: "computed_result"
      derived_from: ["attachment:att_solver_results"]   # canonical evidence payload reference
    fact_uncertainty: "computed"
  - id: "param_max_displacement_mm"
    name: "Maximum displacement under load"
    value_mm: 0.34
    fact_provenance:
      category: "computed_result"
      derived_from: ["attachment:att_solver_results"]
    fact_uncertainty: "computed"

attachment:
  # Canonical evidence payload — the solver result package. THIS is what makes the EvidenceArtifact reconstructable.
  - id: "att_solver_results"
    role: "source_authoring"
    media_type: "application/zip"
    vault_path: "vault:evidence/EVD-000043/solver_results.zip"
    content_hash: "sha256:e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2"
    fact_provenance: { category: "computed_result" }
    fact_uncertainty: "verified"

  # Additional source file — the input deck (method/setup), part of the canonical evidence package.
  - id: "att_source_input_deck"
    role: "source_authoring"
    media_type: "application/x-calculix-input"
    vault_path: "vault:evidence/EVD-000043/input.inp"
    content_hash: "sha256:d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3"
    fact_provenance: { category: "human_input" }
    fact_uncertainty: "verified"

  # Released-distribution rendered report, derived from the canonical solver results.
  - id: "att_primary_report"
    role: "rendered_primary"
    media_type: "application/pdf"
    vault_path: "vault:evidence/EVD-000043/report.pdf"
    content_hash: "sha256:f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3"
    derived_from_attachment_id: "att_solver_results"
    page_count: 8
    fact_provenance: { category: "derived_for_release" }
    fact_uncertainty: "computed"

  # Plot visualization derived from solver results.
  - id: "att_stress_visualization"
    role: "derived_secondary"
    media_type: "image/png"
    vault_path: "vault:evidence/EVD-000043/stress_contour.png"
    content_hash: "sha256:a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4"
    derived_from_attachment_id: "att_solver_results"
    fact_provenance: { category: "derived_for_release" }

design_intent:
  - id: "di_load_case_basis"
    statement: "Load case derived from REQ-000058 operating-load envelope plus 1.5x safety factor per project policy. Boundary conditions fixed at four mounting holes consistent with the production fixture interface. The 1.5x factor accounts for measurement uncertainty in the field-load survey."
    anchors: ["evidence"]

relationship:
  # Empty in seed. Future V&V relationships (`verified_by` / `tested_against` / `cites`) will
  # populate this namespace when the V&V relationship-type ADR lands. Requirement-to-EvidenceArtifact
  # linking is NOT modeled via `allocates_to` (per ADR/0019 §"Decision §5" — wrong verb).
```

**Lineage chain validation at release:**

- `param_peak_stress_mpa.fact_provenance.derived_from` → `attachment:att_solver_results` ✓
- `att_solver_results.role == "source_authoring"` and `content_hash` resolved ✓
- `att_primary_report.role == "rendered_primary"` with `derived_from_attachment_id: "att_solver_results"` ✓ (chain terminates at `att_solver_results` which is `source_authoring`)
- `att_stress_visualization.role == "derived_secondary"` with `derived_from_attachment_id: "att_solver_results"` ✓
- Canonical evidence payload (`att_solver_results`) is present as `source_authoring`; setup-only would have been only `att_source_input_deck` and would have failed Decision §3's semantic invariant.

## Consequences

- **Seventh Object Type lands.** Seed catalogue: Part, Requirement, Assembly, Component, SoftwareModule, Drawing, EvidenceArtifact.
- **First reuse of ADR/0017's Attachment-bearing Object template.** Validates template reusability — structural shape inherits verbatim; the divergences are *semantic* (`source_authoring` meaning specialized for evidence) and *additive* (parameter lineage discipline), not structural. Future Attachment-bearing Types (annotated-simulation candidates, possibly future TestProcedure depending on its design) can inherit the template the same way.
- **Pattern Catalogue Attachment-bearing Object row Applies-to extends** from `Drawing` to `Drawing, EvidenceArtifact (future annotated-simulation candidates, etc.)`.
- **EvidenceArtifact-specific `source_authoring` semantic established.** The Attachment-bearing template now has its first specialization — `source_authoring` for evidence must include the canonical evidence payload, not setup-only. Future evidence-adjacent Types (annotated simulations; possibly EvidenceArtifact-derived sub-Types) inherit this discipline.
- **Parameter lineage discipline introduced for evidence values.** Every `parameter:` on EvidenceArtifact carries `fact_provenance.derived_from` pointing at supporting `attachment:` records — the canonical chain `parameter → derived_from → attachment → content_hash → Vault bytes` is fully enforceable.
- **No relationship-type schema extensions in this bundle.** Requirement-to-EvidenceArtifact citation / verification is deliberately deferred to the future V&V relationship-type ADR (per Codex1 Blocker 2's clean deferral). `allocates_to` MUST NOT be used as a temporary stand-in; the deliberate gap is documented.
- **Bundle bump.** Active bundle moves v0.15.0 → v0.16.0. Scope: new sidecar schema + new discriminator + new Number prefix. No relationship-type extensions.
- **Glossary additions.** [Glossary.md](../Glossary.md) v0.20: new `EvidenceArtifact` entry.
- **SystemState updates.** Attachment-bearing Object row Applies-to extends. Recent Pattern Changes entry. Current Front advance.
- **TestProcedure per-Type ADR is the natural immediate next arc.** Closes the V&V Object Type triad and unblocks the V&V relationship-type ADR (`verifies` / `tested_against` / `cites`), which in turn lifts the deferral on Requirement-to-EvidenceArtifact citation.
- **EvidenceArtifact as `satisfies` source remains deferred** — Schema Change Note when production case surfaces (same posture as Component / SoftwareModule / Drawing).
- **Occurrence-qualified citations from EvidenceArtifact** (per [ADR/0007 §2 line 121](0007-object-type-assembly.md)) inherit the [ADR/0018](0018-relationship-type-depicts.md) `occurrence_context` shape when the citation relationship lands.
- **Wedge readiness for evidence-bearing scenarios.** A Wedge variant with `Part + Requirement + satisfies + EvidenceArtifact` is now schema-feasible. The basic Wedge does not exercise this; evidence-bearing variants need the V&V relationship-type ADR to fully connect evidence to Requirements.
