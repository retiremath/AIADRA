---
name: adr-0017-object-type-drawing
status: accepted
date: 2026-05-19
supersedes: none
superseded_by: none
resolves: []
---

# ADR/0017 — Object Type: Drawing

## Status

**Accepted** — 2026-05-19. Sixth Object Type after Part / Requirement / Assembly / Component / SoftwareModule. First **Attachment-bearing Object** operationalization of the named non-disqualifier pattern from [TruthModelSchema commitment 5 (line 852)](../TruthModelSchema.md). Counterpart to [ADR/0014](0014-object-type-component.md)'s first External pointer Object operationalization — the second of the Promotion Rule's two named non-disqualifier patterns is now operationalized. Introduces the new `attachment:` namespace as the template for subsequent Attachment-bearing Object Types (EvidenceArtifact and similar future Types inherit this shape). Carries additive endpoint Type union extension to `relationship/allocates_to.schema.json` — closing the Drawing deferral from [Glossary "Object (Managed Object)" candidate pool](../Glossary.md) Tier-2 Types.

The `depicts` relationship (pre-declared in [ADR/0005 §11 line 212](0005-object-type-part.md) and [ADR/0007 §11 line 242](0007-object-type-assembly.md) as `Drawing → Part/Assembly`, binary, `trace_graph`) is NOT in this bundle. The natural next arc lands `depicts` as a relationship-type ADR; ADR/0017 makes that arc actionable by establishing Drawing as a real Object Type.

## Context

[TruthModelSchema lines 842-852 + 926](../TruthModelSchema.md) names **Attachment-bearing Object** as the second of the Promotion Rule's named non-disqualifier patterns. Definition: *"AIADRA owns the engineering meaning; Vault holds byte payloads subordinate to that meaning. The Object owns its own (wrapper) lifecycle, fully. Examples: an EvidenceArtifact with a simulation output; a Drawing with a rendered PDF; future annotated-simulation candidates whose annotation layer is canonical. The bytes are subordinate to AIADRA truth."* Drawing is the canonical example.

Discussion trail in [`Docs/Discussions/20260519/20260519-7/`](../Discussions/20260519/20260519-7/). [Codex1](../Discussions/20260519/20260519-7/Codex1.md) produced two blockers and three non-blockers; the blockers were tightly connected (both about what makes a *canonical committed Drawing*). Both absorbed in [Claude2](../Discussions/20260519/20260519-7/Claude2.md):

1. **Promotion / D7-escape was aspirational, not structural.** Claude1's argument was that Drawing tips out of D7 because authored canonical content lives on the sidecar — but the seed schema only required `title` + a `rendered_primary` attachment. A valid released Drawing under Claude1 could be just a deterministic render + title, which IS the D7-derived-view case the Promotion Rule rejects. Repair: require a `source_authoring` attachment role at release; derived roles (`rendered_primary`, `derived_secondary`) carry explicit lineage back to the authored source.
2. **`content_hash` was both REQUIRED and "may be pending."** Schema contradiction in a pattern-setting namespace. Repair: `content_hash` unconditionally required on every committed `attachment:` record; async rendering happens pre-commit in Workspace cache / Transaction preview.

[Codex2](../Discussions/20260519/20260519-7/Codex2.md) sign-off with three implementation-precision notes carried forward.

Three pressures converge:

1. **First operationalization of Attachment-bearing Object pattern.** [ADR/0014](0014-object-type-component.md) operationalized the External pointer Object pattern (consumer Binds to external upstream). ADR/0017 operationalizes the counterpart: Object owns Vault-attached canonical bytes. Both invoke named non-disqualifier patterns from [Promotion Rule commitment 5](../TruthModelSchema.md); the Promotion Rule's two named patterns are now both operationalized.
2. **D7-escape must be structural.** The Promotion Rule's D7 disqualifier rejects "derived views." A Drawing that is purely a rendered output of a Part's CAD model + title block IS a derived view. What lifts Drawing out of D7 is the *authored canonical layer*. The schema must enforce that layer; it cannot be aspirational. Codex caught this; the repair is structural — `source_authoring` is the load-bearing role.
3. **`attachment:` namespace as a template.** Subsequent Attachment-bearing Types (EvidenceArtifact at minimum) will inherit ADR/0017's `attachment:` namespace pattern. The shape must be right at the seed because future Types will follow it.

## Promotion Rule walk — via Attachment-bearing Object pattern

Drawing passes the Promotion Rule capability test via the **Attachment-bearing Object** named non-disqualifier pattern from [TruthModelSchema commitment 5](../TruthModelSchema.md):

- **C1 — Independent identity.** A Drawing `DWG-000017` has stable local UUID + Number identifying *the engineering drawing artifact* — independent of any Part it depicts, of the Vault content hash of any specific render, and of the rendering tool used to produce a PDF. The same drawing can be re-rendered (tool upgrade, format change) without changing its identity.
- **C2 — Independent lifecycle.** Drawing has its own release cadence (drawing rev A, B, C) distinct from the depicted Part's revisions. A Part may release without releasing a corresponding drawing; a drawing rev B may depict Part v3 *or* Part v4 depending on which Part Revision the drawing was authored against.
- **C3 — Independent referenceability.** Referenced by UUID from `depicts` records (the natural next arc) and from `allocates_to` (a Requirement may be allocated to a drawing deliverable, e.g., *"document mounting interface in DWG-000023"*).
- **C4 — Independent provenance / approval.** Drawing approval is its own engineering decision — typically drafting-checker + engineering-manager sign-off, distinct from Part design approval.

**D1–D7 disqualifier walk:**

- **D7 (Derived view)** — N/A *because* the schema requires a `source_authoring` attachment at release per Decision §2. The Drawing carries an authored canonical payload (the DWG file, the source LaTeX, the InDesign file, etc.); any rendered or derived attachments are explicit derivatives that must point back to the source via `derived_from_attachment_id`. D7 rejects "derived views" — Drawing is *not* a derived view because the schema enforces an authored layer. This argument is now **structural**, not aspirational; the Promotion Rule's commitment-5 named-non-disqualifier shield is properly earned.
- **D1–D6** — N/A or trivially pass.

Conclusion: **Drawing is a first-class Object Type via the Attachment-bearing Object pattern.** First operationalization of this pattern; sets the template for future Attachment-bearing Types.

## Alternatives Considered

### Attachment storage shape

**A1. Extend `geometry_ref` namespace with a `drawing_export` / `rendered_artifact` role.**

> **Rejected.** Conflates kernel-geometry pattern with canonical-attachment pattern. Subsequent Attachment-bearing Types (EvidenceArtifact) would inherit geometry-namespace-pretending-to-be-attachment shape. Cleaner break with a dedicated namespace.

**A2. New `attachment:` namespace; template for Attachment-bearing Object Types.** *Chosen — see Decision §2.*

### Authored canonical layer requirement (D7-escape rigor)

**B1. Schema requires only `rendered_primary` at release; authored layer is aspirational reference.** Claude1's original proposal.

> **Rejected.** Per Codex1 Blocker 1 — the Promotion Rule's D7-escape requires a structural authored layer, not an argument about what *could* be there. A schema enforcing only rendered output is a D7-derived-view, full stop.

**B2. Require `source_authoring` role at release; derived roles carry `derived_from_attachment_id` lineage.** *Chosen — see Decision §2.*

### `content_hash` resolution discipline

**C1. Allow `content_hash` pending in working state; resolved only at release.** Claude1's contradictory shape.

> **Rejected.** Per Codex1 Blocker 2 — committed sidecar attachments cannot be half-resolved without an explicit state shape; the seed shouldn't introduce that complexity. Async rendering belongs pre-commit (Workspace cache, Transaction preview); committed sidecars carry only resolved-bytes state.

**C2. `content_hash` unconditionally required on every committed `attachment:` record.** *Chosen — see Decision §2.*

### Number prefix + Type name

**D1. `D-NNNNNN` (Drawing prefix, short form).**

> **Rejected.** `D-` alone risks confusion with future Drawing-adjacent Types. `DWG` is engineering convention.

**D2. `DWG-NNNNNN` (chosen).** Six-digit zero-padded sequential allocation per [ADR/0004](0004-number-allocation.md).

### Combined Drawing + `depicts` ADR

**E1. Land both in one ADR.**

> **Rejected.** `depicts` has substantial decisions (target Type union; occurrence-qualification rules per [ADR/0007 §2](0007-object-type-assembly.md); binding defaults; partial-Drawing-of-partial-Object case) that warrant their own arc. Same posture as the trace family being sequenced rather than combined.

### `title_block_fields` shape

**F1. Free-form key-value map.** Claude1's proposal.

> **Rejected for unguarded form (Codex Non-blocker 3).** Adopted with explicit guardrail (Decision §3): `title_block_fields` may mirror canonical Object metadata for rendering but is NOT a second source of truth. Canonical metadata wins on mismatch.

**F2. Free-form key-value map with explicit canonical-metadata-wins guardrail.** *Chosen — see Decision §3.*

## Decision

### 1. Number prefix + Type name

**Type name:** `Drawing` (PascalCase; matches Part / Requirement / Assembly / Component / SoftwareModule).

**TypeSpecific block:** `drawing:` (snake_case singleton).

**Number prefix:** `DWG-NNNNNN`. Six-digit zero-padded sequential allocation from the Reservation file per [ADR/0004](0004-number-allocation.md). Matches other Types' six-digit width.

### 2. `attachment:` namespace — the load-bearing decision

New namespace template for Attachment-bearing Object Types. Subsequent Attachment-bearing Type ADRs (EvidenceArtifact, future annotated-simulation candidates) inherit this shape.

**Per-record fields:**

```yaml
attachment:
  - id: "string"                       # REQUIRED — stable local id per S0 commitment 7
    role: "source_authoring | rendered_primary | derived_secondary"   # REQUIRED enum
    media_type: "string"               # REQUIRED — IANA media type (e.g., "application/pdf", "application/dwg")
    vault_path: "string"               # REQUIRED — Vault Adapter-resolved path; non-authoritative locator
    content_hash: "string"             # REQUIRED — algorithm-qualified per ADR/0016 convention (e.g., "sha256:...")
    derived_from_attachment_id: "string"  # REQUIRED for rendered_primary | derived_secondary; FORBIDDEN for source_authoring
    page_count: integer                # OPTIONAL — for multi-page media (PDF, multi-sheet DWG)
    fact_provenance: { ... }           # OPTIONAL — S1 annotations
    fact_uncertainty: "..."            # OPTIONAL — S1 annotations
```

**`role` enum semantics:**

- **`source_authoring`** — the canonical authored payload. The Drawing's authored content; not derived. May be the editable source format (DWG, source LaTeX, InDesign file) OR — in the edge case where a project authors directly in the final rendered form — the final form itself (a directly-authored PDF has `role: source_authoring`, not `role: rendered_primary`). A Drawing MAY have one `source_authoring` record (typical) or, in unusual cases, more than one (e.g., multi-file source like DWG + linked XREFs). At minimum one MUST be present at release.
- **`rendered_primary`** — release-facing rendered representation derived from `source_authoring`. Typical case: DWG (`source_authoring`) renders to PDF (`rendered_primary`). MUST carry `derived_from_attachment_id` pointing at the source `attachment.id` it was derived from. Optional in a Drawing — if the source IS the rendered form (PDF-only authored case), there's no separate `rendered_primary`.
- **`derived_secondary`** — additional derived forms (DXF for laser-cut, thumbnail PNG, etc.). MUST carry `derived_from_attachment_id` pointing at the source `attachment.id` (either `source_authoring` directly or `rendered_primary`). Optional.

**Hash discipline:**

`content_hash` is the **stable authority** for the attachment's integrity. Algorithm-qualified per [ADR/0016](0016-object-type-software-module.md) convention — `"sha256:..."` is the default; the prefix vocabulary is consumer-policy-extensible. `vault_path` is the Vault-Adapter-resolved locator hint — analogous to `git_url` and `locator_hint` in prior ADRs, **non-authoritative** per [Manifesto P11](../Manifesto.md). Hash-against-retrieved-bytes mismatch at fetch / release is a hard validation failure.

**Resolution discipline:**

Every committed `attachment:` record carries fully-resolved fields: `id`, `role`, `media_type`, `vault_path`, `content_hash`. No "pending" state; no half-resolved records. Asynchronous rendering (CAD-to-PDF, source-to-multiple-formats) happens *before* commit — in Workspace cache or Transaction preview, per [ADR/0001 §6 locality tiers](0001-storage-substrate.md). Only fully-resolved attachment records reach a committed sidecar.

**Working-state behavior:**

A Drawing in `lifecycle: in_work` MAY have zero attachments (drafting just started; rendering hasn't completed). The schema does NOT require attachments in working state. Release materialization is what enforces the "at least one `source_authoring` with `content_hash` resolved" invariant.

**Lineage discipline:**

`derived_from_attachment_id` is REQUIRED on every `rendered_primary` and `derived_secondary` record; FORBIDDEN on `source_authoring` records. The reference must resolve to another `attachment.id` *in the same Drawing*. Lineage chains must terminate at a `source_authoring` record — no cycles, no dangling references. Hard-fail at write validation.

### 3. Singleton `drawing:` block contents

Drawing-specific metadata. Conservative seed; only `title` REQUIRED.

```yaml
drawing:
  title: "string"                  # REQUIRED — drawing title (human-readable)
  sheet_size: "string"             # OPTIONAL — e.g., "A0", "A1", "A2", "A3", "A4", "ANSI-D"; not enum-bounded (regional/industry variance)
  scale: "string"                  # OPTIONAL — e.g., "1:1", "1:2", "1:10"; string convention; non-numeric
  projection_type: "first_angle | third_angle"   # OPTIONAL — enum-bounded; universal in engineering practice
  revision_block_format: "string"  # OPTIONAL — e.g., "ANSI", "ISO", project-specific
  title_block_fields:              # OPTIONAL — free-form key-value pairs for project-specific title-block metadata
    drafter: "..."
    checker: "..."
    department: "..."
```

**`title_block_fields` guardrail:**

`title_block_fields` MAY mirror canonical Object metadata (Object Number, Revision identifier, lifecycle state, approval signatures) for rendering convenience — drafters typically want title-block text to reflect committed metadata. However, the canonical sources of truth remain authoritative:

- `object.number` is the canonical Number.
- The Revision record itself is canonical for revision identity.
- The `object.lifecycle` field is canonical for lifecycle state.
- Release manifests + approval events are canonical for approvals.

**If a title-block value disagrees with canonical metadata, canonical metadata wins** and rendering / validation tooling should diagnose the mismatch. `title_block_fields` is a rendering convenience namespace, not a second source of truth. This guardrail prevents the title-block-as-shadow-spec failure mode.

### 4. Namespace set

Most selective namespace adoption in the catalogue to date. Drawing has no parameters, no features, no kernel geometry, no material, no source.

| Namespace | In Drawing seed? | Notes |
|---|---|---|
| `parameter:` | NO | Drawing's metadata lives in singleton `drawing:` block, not a parameter namespace. |
| `design_intent:` | YES | Rationale for callouts, dimension choices, drafting decisions; anchors by id to attachment records or future `depicts` relationships. |
| `feature:` | NO | Drawings have no engineering features in the CAD-construction-history sense. |
| `relationship:` | YES | Drawing participates as `depicts` source (when ADR for `depicts` lands); may participate as `allocates_to` target. |
| `published_ref:` | NO | Drawing has no published reference geometry. |
| `geometry_ref:` | NO | Drawing has no kernel geometry. Rendered representations live in `attachment:`. |
| `material:` | NO | N/A. |
| `source:` | NO | Requirement-specific. |
| **NEW: `attachment:`** | YES | Vault-attached canonical-bytes records per Decision §2. |

**Two of Part's seven namespaces** (`design_intent:`, `relationship:`) **plus the new `attachment:` namespace plus the singleton `drawing:` block**. Tightest namespace adoption in the catalogue.

### 5. Relationship participation + endpoint-schema extension

**In seed (this bundle):**

- **`allocates_to` target — YES.** Natural use case: a Requirement may be allocated to a drawing deliverable. Additive schema extension: `relationship/allocates_to.schema.json` target Type union extended from `Part | Assembly | Component | SoftwareModule` to `Part | Assembly | Component | SoftwareModule | Drawing`. Same posture as ADR/0014 / ADR/0016 endpoint extensions; ADR/0013's overall status remains `accepted` (additive extension, not supersession).

**Deferred (out of seed):**

- **`depicts` relationship type itself.** Pre-declared at `Drawing → Part | Assembly`, `trace_graph`, binary per [ADR/0005 §11](0005-object-type-part.md) and [ADR/0007 §11](0007-object-type-assembly.md); occurrence-qualified endpoints per [ADR/0007 §2](0007-object-type-assembly.md). Substantial decision space (target Type union; occurrence-qualification rules; binding defaults Float vs Fixed; partial-Drawing-of-partial-Object case) warrants its own ADR. ADR/0017's `relationship:` namespace exists; `depicts` records populate it when that ADR lands.
- **`composed_of` target — NOT applicable.** Drawings are documentation artifacts, not physical Assembly constituents. They're associated with Assemblies via `depicts`, not `composed_of`. Semantic non-fit; not a deferral.
- **`satisfies` source — deferred.** Plausible (a Drawing claiming it satisfies a documentation Requirement) but requires ADR/0009 endpoint extension. Same posture as Component / SoftwareModule.
- **`parameter_expression` endpoint — not in seed.** Plausible but uncommon enough to defer.

### 6. AIADRA Core hosts nothing — explicit walk

[Manifesto P11](../Manifesto.md). Walking the design:

- **No Core-hosted Drawing registry.** Per-project Drawing collections live in the project's own Git / Commonspace; no cross-project Drawing index hosted by AIADRA Core.
- **No Core-hosted Vault.** Per [Glossary "Vault Adapter"](../Glossary.md) and [Manifesto P12](../Manifesto.md), the Vault is consumer-project-policy (GitHub LFS default; S3 / MinIO / IPFS / NAS / project-local FS alternatives). AIADRA Core ships the default LFS adapter; never hosts.
- **No Core-mediated rendering service.** Generating the PDF from a Part's CAD model is a Domain Adapter / Domain Engine concern (FreeCAD, custom drafting tools); not Core.
- **No registry-shaped fields in the schema.** `vault_path` is a Vault-Adapter-resolved hint, non-authoritative; `content_hash` is the integrity anchor. Same posture as `git_url` (ADR/0016) and `locator_hint` (ADR/0014) — non-authoritative resolution hints throughout.

### 7. Lifecycle, eventability, Revisions, bundle bump

**Lifecycle** independent per Promotion C2. States: `in_work` → `released` → `retired`. Consumer project owns each transition.

**Eventability** per [S3 commitment 5](../TruthModelSchema.md): `drawing_created`, `drawing_changed`, `drawing_released`, `drawing_retired`. `_changed` fires on title-block edit, attachment add/remove/re-render, design-intent record edit, relationship-namespace edit.

**Revision schema** per [S2 commitment 1](../TruthModelSchema.md). Each Drawing Revision is a separate immutable artifact at canonical path `revisions/<object-uuid>/<revision-id>.yaml`. Released Drawing Revision MUST carry at least one `attachment:` record with `role: source_authoring` AND `content_hash` resolved.

**Bundle bump:** **v0.13.0 → v0.14.0**, MINOR additive per [ADR/0003 §11](0003-schema-governance.md). Changes:

- NEW: `sidecar/Drawing.schema.json` (new Object Type sidecar).
- NEW: `object.type = "Drawing"` discriminator value.
- NEW: `DWG-NNNNNN` Number prefix mapping at the bundle level.
- NEW: shared `attachment:` namespace schema (referenced from Drawing for now; available for future Attachment-bearing Object Types — EvidenceArtifact etc.).
- ADDITIVE: `relationship/allocates_to.schema.json` target Type union (Drawing added).

No existing artifacts break. All MINOR additive.

**ADR ceremony** per the [amended Promotion Rule commitment 6](../TruthModelSchema.md): pattern-setting (first Attachment-bearing Object operationalization; new `attachment:` namespace template; structural D7-escape via authored canonical layer).

### 8. Validation rules (Layer 2)

- `object.type == "Drawing"`.
- `drawing:` singleton block present with at least `title` (non-empty string).
- `drawing.projection_type` ∈ {`first_angle`, `third_angle`} if present.
- `attachment:` namespace is a list (may be empty in working state); each record has `id`, `role`, `media_type`, `vault_path`, `content_hash`.
- `attachment.role` ∈ {`source_authoring`, `rendered_primary`, `derived_secondary`}.
- `attachment.content_hash` is an algorithm-qualified string (non-empty; contains `:` separator between algorithm prefix and digest).
- `attachment.derived_from_attachment_id` REQUIRED for `role ∈ {rendered_primary, derived_secondary}`; FORBIDDEN for `role: source_authoring`.
- `attachment.derived_from_attachment_id` resolves to another `attachment.id` in the same Drawing (same record array). Hard-fail on dangling reference.
- Lineage chain: following `derived_from_attachment_id` from any derived record terminates at a `source_authoring` record. Hard-fail on cycle.
- **Released-state invariant:** at least one `attachment:` record with `role: source_authoring` AND `content_hash` resolved. Hard-fail at release if absent.
- **Hash integrity at fetch / release:** retrieved Vault bytes at `vault_path` must hash to the recorded `content_hash`. Hard-fail on mismatch.
- `title_block_fields` values that mirror canonical metadata are validated against canonical sources (Object Number, Revision identifier, lifecycle, approvals); mismatch is a validation diagnostic (not hard-fail) — canonical metadata wins.
- For released `allocates_to` records targeting this Drawing: per [ADR/0013](0013-relationship-type-allocates-to.md) validation; nothing Drawing-specific.

## Worked sidecar examples

### Example 1 — Typical DWG-authored Drawing with PDF render

A Drawing authored in DWG format, rendered to PDF for release-facing distribution, with an additional DXF derivative for downstream laser-cut tooling.

```yaml
object:
  uuid: "0193abcd-8888-7400-9ddd-bbbbbbbbbbbb"
  type: "Drawing"
  number: "DWG-000017"
  lifecycle: "in_work"
  schema_version: "0.14.0"

drawing:
  title: "Drive bracket — assembly drawing"
  sheet_size: "A3"
  scale: "1:2"
  projection_type: "third_angle"
  revision_block_format: "ISO"
  title_block_fields:
    drafter: "L. Chen"
    checker: "M. Park"
    department: "Mechanical"

attachment:
  - id: "att_source_dwg"
    role: "source_authoring"
    media_type: "image/vnd.dwg"
    vault_path: "vault:drawings/DWG-000017/source.dwg"
    content_hash: "sha256:a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2"
    fact_provenance: { category: "human_input" }
    fact_uncertainty: "verified"

  - id: "att_primary_pdf"
    role: "rendered_primary"
    media_type: "application/pdf"
    vault_path: "vault:drawings/DWG-000017/release.pdf"
    content_hash: "sha256:b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3"
    derived_from_attachment_id: "att_source_dwg"
    page_count: 2
    fact_provenance: { category: "derived_for_release" }
    fact_uncertainty: "computed"

  - id: "att_dxf_lasercut"
    role: "derived_secondary"
    media_type: "image/vnd.dxf"
    vault_path: "vault:drawings/DWG-000017/lasercut.dxf"
    content_hash: "sha256:c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4"
    derived_from_attachment_id: "att_source_dwg"
    fact_provenance: { category: "derived_for_release" }
    fact_uncertainty: "computed"

design_intent:
  - id: "di_section_view_choice"
    statement: "Section A-A cut at the mounting boss centerline (not at the hole pattern) to keep both wall thicknesses visible on a single sheet."
    anchors: ["drawing"]

# relationship: namespace empty here; Drawing will appear as depicts source when ADR for depicts lands,
# and may be the target of allocates_to from upstream Requirements.
```

### Example 2 — Directly-authored PDF (no separate source format)

A Drawing where the author edits the PDF directly (e.g., one-off informational drawing produced with a PDF editor; no separate authoring tool). The PDF IS the source.

```yaml
object:
  uuid: "0193abcd-9999-7500-9eee-cccccccccccc"
  type: "Drawing"
  number: "DWG-000019"
  lifecycle: "released"
  schema_version: "0.14.0"

drawing:
  title: "Cable routing diagram — wiring layout"
  sheet_size: "A4"
  scale: "NTS"          # not to scale
  projection_type: "third_angle"

attachment:
  - id: "att_pdf_authored"
    role: "source_authoring"     # PDF IS the source — no separate authoring format
    media_type: "application/pdf"
    vault_path: "vault:drawings/DWG-000019/source.pdf"
    content_hash: "sha256:d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5"
    fact_provenance: { category: "human_input" }
    fact_uncertainty: "verified"

  # No separate rendered_primary — the source IS the deliverable form.
  # If a thumbnail were generated for UI previews, it would be a derived_secondary
  # with derived_from_attachment_id: "att_pdf_authored".
```

## Consequences

- **Sixth Object Type lands.** Seed catalogue: Part, Requirement, Assembly, Component, SoftwareModule, Drawing.
- **First Attachment-bearing Object operationalization.** ADR/0017 operationalizes the [Promotion Rule commitment 5](../TruthModelSchema.md) Attachment-bearing Object named non-disqualifier pattern for the first time. Sets the template (`attachment:` namespace; `source_authoring` / `rendered_primary` / `derived_secondary` role enum; `derived_from_attachment_id` lineage; algorithm-qualified `content_hash` integrity discipline) for future Attachment-bearing Types — EvidenceArtifact, future annotated-simulation candidates.
- **Promotion Rule's two named non-disqualifier patterns both operationalized.** ADR/0014 (External pointer Object) + ADR/0017 (Attachment-bearing Object). The Promotion Rule's commitment-5 shield mechanism is now fully concrete.
- **`attachment:` namespace introduced.** New pattern template; available for inheritance by Attachment-bearing Type ADRs without re-derivation.
- **D7-escape made structural.** The Promotion walk's D7 argument is now schema-enforced: every released Drawing carries a `source_authoring` attachment; derived attachments carry explicit lineage. The "authored canonical layer" is required at release, not aspirational.
- **`content_hash` discipline universalized.** Algorithm-qualified hash convention from [ADR/0016](0016-object-type-software-module.md) extends to attachment integrity anchors. `vault_path` is non-authoritative locator; `content_hash` is authority.
- **`relationship/allocates_to.schema.json` endpoint Type union extended.** Drawing added to target Type union additively. [ADR/0013](0013-relationship-type-allocates-to.md)'s overall status remains `accepted` (additive extension, not supersession). Same posture as ADR/0014 / ADR/0016 extensions to multiple relationship schemas.
- **Schema bundle bump.** Active bundle moves v0.13.0 → v0.14.0.
- **Glossary additions.** [Glossary.md](../Glossary.md) v0.18: new `Drawing` entry; small update to the existing `allocates_to` entry's target Type scope wording (to include Drawing).
- **SystemState additions.** New Pattern Catalogue row ("Attachment-bearing Object pattern operationalized") — counterpart to ADR/0014's External pointer row. Recent Pattern Changes entry. Current Front advance (seed Object Type catalogue 5 → 6).
- **`depicts` relationship type is the natural immediate next arc.** Pre-declared shape in ADR/0005 §11 and ADR/0007 §11; substantial decision space (target Type union; occurrence-qualification; binding defaults; partial-Drawing-of-partial-Object). Drawing as Object Type is the unblocker.
- **EvidenceArtifact per-Type ADR remains as a future arc.** Second Attachment-bearing Object Type; inherits ADR/0017's `attachment:` namespace and pattern template.
- **TestProcedure per-Type ADR** — third Tier-2 Type from the candidate pool; possibly Attachment-bearing (carries a test method document) or possibly not (some test procedures are entirely sidecar-encoded). To be determined when its arc lands.
- **Drawing as `satisfies` source deferred** — Schema Change Note when production case surfaces (same posture as Component / SoftwareModule).
- **Wedge readiness for documentation artifacts.** A Wedge variant with `Part + Requirement + satisfies + Drawing + allocates_to(Requirement → Drawing)` is now schema-feasible. The basic Wedge does not exercise this; an enriched Wedge with documentation deliverables is.
