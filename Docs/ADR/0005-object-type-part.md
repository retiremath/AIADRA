---
name: adr-0005-object-type-part
status: accepted
date: 2026-05-18
supersedes: none
superseded_by: none
resolves: []
---

# ADR/0005 — Object Type: Part

## Status

**Accepted** — 2026-05-18. First per-Type Object catalogue ADR; opens the seed (Part, Requirement, Assembly per the [Promotion Rule's grandfathering](../TruthModelSchema.md#8-seed-catalogue-is-grandfathered)). Sets patterns that subsequent per-Type ADRs follow: TypeSpecific namespace shape, adapter shell governance, role-discriminated geometry, anchors guardrail for cross-cutting records, and governance-vs-schema decoupling for bundle bumps.

## Context

The [Promotion Rule](../TruthModelSchema.md#promotion-rule-for-first-class-object-types) (TruthModelSchema v0.6, pinned 2026-05-18) governs which entities become first-class Object Types. Part is the first seed Type per [ADR/0003 §1 / §2](0003-schema-governance.md) named examples and [Promotion Rule commitment 8](../TruthModelSchema.md#8-seed-catalogue-is-grandfathered). Its *promotion* is grandfathered; what this ADR settles is the **Type-specific schema content**: what fields and namespaces Part carries beyond the [BaseObject envelope](../TruthModelSchema.md#1-compositional-schema-governance), how it threads through S0–S3 and S2.5, and how it satisfies [Manifesto P3 / P4 / P6 / P7 / P9](../Manifesto.md).

Three pressures converge here:

1. **Pattern-setting.** Part is the first concrete Object Type. Every decision in this ADR — the namespace count, the governed adapter shell, the role-discriminated geometry, the cross-cutting record guardrails — will be the precedent Requirement and Assembly ADRs follow, and (in turn) Drawing / TestProcedure / EvidenceArtifact when their per-Type ADRs land.
2. **Catalogue rule contact.** The Promotion Rule's commitment 6 wording ("ADR if MAJOR; Schema Change Note if MINOR") contradicts the load-bearing reality of Part: this is a MINOR bundle bump (additive) requiring ADR ceremony (first concrete Object Type, sets patterns). The commitment 12 governance-vs-schema decoupling is the operative principle; commitment 6 needs amendment in a follow-up arc.
3. **Wedge readiness.** Part's schema must round-trip through all five layers in the Wedge ([Manifesto](../Manifesto.md), [Glossary: Wedge](../Glossary.md)). The schema in this ADR is what the Wedge will exercise; over-engineering it (e.g., pinning a CAD-feature taxonomy ahead of Domain Adapter work) blocks the Wedge, under-engineering (e.g., omitting material) ships an incomplete mechanical Part.

The discussion trail in [`Docs/Discussions/20260518-3/`](../Discussions/20260518-3/) carries the full alternatives reasoning across two Codex review rounds (Claude1 → Codex1 → Claude2 → Codex2 → Claude3); thirteen findings across both rounds, all accepted, zero rejected. This ADR pins the resulting twelve decisions.

## Alternatives Considered

### Geometry representation

**A1. Single envelope field `object.geometry`.** Each Part has one canonical geometry; raw BRep referenced via Vault hash.

> **Rejected.** [Manifesto P9](../Manifesto.md) layered geometry access implies coexisting representations at different layers (parametric features, raw BRep, derived STEP, visualization). A single field forces a choice or smuggles multi-representation into Vault-side semantics. Independent S1 annotation per representation is also lost.

**A2. Namespace `geometry_ref:` with mixed canonical-and-derived peer records.** Original Claude1 draft.

> **Rejected.** Blurs the [Promotion Rule's D7 boundary](../TruthModelSchema.md#3-disqualifier-test--seven-negative-criteria) — derived exports (STEP, mesh, render) are D7-derived and should not be peer canonical state with the authoring model. Caught by Codex1 §1.

**A3. Namespace `geometry_ref:` with `role:` discriminator.** *Chosen — see Decision §7.* Roles separate canonical authoring geometry from D7-derived exports retained as Part-bound references; cached visualizations are excluded from the sidecar entirely (Codex2 blocking edit).

### Design intent location

**B1. Embedded fields on each parameter / feature record.** Intent lives next to what it governs.

> **Rejected.** Design intent often spans multiple parameters and features ("M8 clearance for MTR-0007 mounting per REQ-014" governs a hole feature AND its diameter parameter AND its position parameter). Embedded fields force duplication or arbitrary anchor choice. Object-level intent ("Part purpose") has no natural single embed location.

**B2. Separate `design_intent:` namespace with anchors.** *Chosen — see Decision §5.* Records declare cross-cutting `anchors:` OR `scope: "object"` (Codex1 §7 anchors-or-object-level guardrail). Prevents the namespace from becoming structured free-text.

### CAD feature taxonomy

**C1. Pin a seed feature taxonomy in this ADR.** Define `sketch`, `extrusion`, `hole`, `fillet`, `datum` with minimal sub-schemas.

> **Rejected.** Feature semantics are deeply Domain-Adapter-specific (FreeCAD's notion of "hole" vs Creo's vs OCCT primitive structure vs SolidWorks). Pinning ahead of Domain Adapter work in Ring 3 risks baking a CAD-kernel-specific taxonomy into the canonical schema. Codex1 §5 flagged the self-contradiction in Claude1 (claimed sub-schemas while deferring taxonomy).

**C2. Generic `feature:` records with `feature_type` string discriminator; no sub-schemas.** *Chosen — see Decision §6.* Per-feature taxonomy deferred to Domain Adapter ADR. The Wedge can use a single placeholder `feature_type` value.

### Material representation

**D1. Material as parameters under `parameter:`.** A `material_name` parameter, a `density` parameter, etc.

> **Rejected.** Loses material as a coherent engineering concept. Mass-from-volume-and-density computations have no canonical density source; "stainless steel only" requirements have no structured target; material substitution decisions disappear into a flat parameter list. Codex1 §3 flagged this as the biggest missing namespace.

**D2. Material as `design_intent:` records.** Anchored to whatever parameters the material affects.

> **Rejected.** Material isn't intent; it's authored engineering data with structured fields (standard reference, density, finish, heat treatment, compliance). Forcing it into `design_intent:` overloads that namespace.

**D3. Material as a separate `material:` namespace, collection of records.** *Chosen — see Decision §8.* Collection accommodates multi-material Parts (welded, composite). In-Part only for now; future MaterialSpec catalog reuse is additive via the External pointer Object pattern under OQ-0016.

### Mate ownership

**E1. Part owns `mated_to` records when its features participate.** Each Part's sidecar lists its mates to other Parts.

> **Rejected.** A mate is assembly-context-specific — "in Assembly X, Part A's hole axis mates to Part B's boss axis." Part A doesn't intrinsically know about Part B; the assembly context does. Codex1 §4 caught the right ownership boundary.

**E2. Assembly owns most mate records; Part is target endpoint.** *Chosen — see Decision §11.* Part is a valid endpoint for `mated_to` via `published_ref` or feature addresses; Assembly carries the mate record. Within-Part constraints (a rare exception) may be Part-owned.

### Adapter metadata governance

**F1. Fully opaque `domain_engine_metadata` blob.** AIADRA Core treats it as bytes; adapter understands.

> **Rejected.** Workspace-local paths and arbitrary opaque blobs in canonical truth violate [Manifesto P11](../Manifesto.md) (AIADRA Core hosts nothing — but canonical truth must be portable, not local) and [ADR/0001 §2](0001-storage-substrate.md) (Workspace is local; Commonspace is canonical and portable). A FreeCAD document path in one clone is meaningless in another. Caught by Codex1 §2.

**F2. Governed adapter shell with opaque inner payload.** *Chosen — see Decision §9.* Outer fields (`engine`, `adapter_schema_version`) are required; resolution anchor (`engine_artifact_ref` Vault hash, or `stable_engine_object_id` resolved within a referenced artifact, or the parent record's `vault_ref`) must always exist; workspace-local paths are forbidden. Inner `adapter_payload` is adapter-defined and opaque to AIADRA Core.

### Cached visualization placement

**G1. `cached_visualization` role in `geometry_ref:`.** Original Claude2 draft.

> **Rejected.** Self-contradiction — the sidecar IS canonical current state; a record described as "not canonical" cannot live there. Codex2 blocking edit.

**G2. Cached visualizations live outside the sidecar.** *Chosen — see Decision §7.* Acceleration cache per [ADR/0001 §3](0001-storage-substrate.md); adapter-local cache; Workspace-local files. Never as sidecar records.

### Bundle bump class

**H1. MAJOR for first concrete Object Type.** Procedurally v0.1.0 → v0.2.0 pre-v1.0.

> **Rejected.** Conflates "first" with "breaking." Adding a new `object.type = "Part"` discriminator value and `sidecar/Part.schema.json` is purely additive — no existing artifacts to break; the lookup for existing discriminator values is unchanged. [ADR/0003 §11](0003-schema-governance.md)'s MAJOR class is for tightening validation or breaking existing artifacts. Caught by Codex1 §6.

**H2. MINOR / additive, with ADR ceremony.** *Chosen — see Decision §12.* Bundle bumps v0.1.0 → v0.2.0 as a MINOR. ADR ceremony applies separately because the promotion sets patterns (first concrete Object Type, novel adapter shell, etc.) — this is governance ceremony per [Promotion Rule commitment 12](../TruthModelSchema.md#12-rule-evolution-is-governance-tier-decoupled-from-schema-bundle-bumps), decoupled from the additive schema ceremony.

## Decision

### 1. Promotion

Part passes the [Promotion Rule's](../TruthModelSchema.md#promotion-rule-for-first-class-object-types) capability test:

- **C1 — Independent identity.** A Part `P-000123` is the same Part regardless of which Assembly contains it.
- **C2 — Independent lifecycle.** Progresses through `in_work → under_review → released → superseded → obsolete` on its own cadence.
- **C3 — Independent referenceability.** Referenced by UUID from Assemblies (`composed_of`), Requirements (`satisfies`), Drawings (`depicts`), other Parts (`derived_geometry_from`, `parameter_expression`, `mated_to`).
- **C4 — Independent provenance / approval.** Released on its own approval, distinct from any Assembly or Release that includes it.

No D1–D7 disqualifier applies. Grandfathered as seed per ADR/0003 §1 / §2 named examples and Promotion Rule commitment 8.

### 2. Number prefix

`P-NNNNNN` — six-digit zero-padded sequential allocation from the Reservation file. AIADRA Core default; per-project override per [S2.5 commitment 10](../TruthModelSchema.md#10-number-format-and-type--prefix-mapping-are-per-project-policy). Exhaustion mechanics belong to OQ-0015 / ADR/0004, not here.

### 3. Seven TypeSpecific namespaces

Part is composed `BaseObject ⨁ PartSpecific` per [S0 commitment 1](../TruthModelSchema.md#1-compositional-schema-governance). PartSpecific carries seven user-authored record collections under named namespaces ([S0 commitment 4](../TruthModelSchema.md#4-hybrid-within-artifact-addressing)):

1. `parameter:` — named typed engineering parameters (Decision §4).
2. `design_intent:` — first-class design intent records (Decision §5).
3. `feature:` — CAD construction-history features (Decision §6).
4. `relationship:` — first-class relationship records ([S3](../TruthModelSchema.md#s3--relationship-modeling)).
5. `published_ref:` — published reference ports ([S3 commitment 11](../TruthModelSchema.md#11-published-reference-ports-are-first-class-addressable-records-owned-by-objects)).
6. `geometry_ref:` — kernel geometry attachments (Decision §7).
7. `material:` — material specification records (Decision §8).

Each record carries a stable local `id`, optional `name` (mutable label), record-specific content, and S1 fact provenance / uncertainty annotations.

### 4. `parameter:` carries computed properties

Mass, volume, surface area, center of gravity, bounding box live in `parameter:` records with `fact_provenance.category: computed_result` and `derived_from` lineage per [S1 commitment 5](../TruthModelSchema.md#5-computed-facts-carry-derived_from-inside-fact-provenance). No separate namespaces for these. A Part schema does not pre-declare which computed parameters must exist; computation is a per-project / per-Domain-Adapter concern.

### 5. `design_intent:` anchors-or-object-level guardrail

Each `design_intent:` record MUST declare either:

- `anchors:` — one or more addresses inside this Part (`parameter:<id>`, `feature:<id>`, `published_ref:<id>`, `relationship:<id>`), OR
- `scope: "object"` — explicit object-level intent with no anchors required.

Records carrying neither are validation errors. This prevents the namespace from accreting as structured free-text notes; intent must either point at what it governs or explicitly declare object-level scope.

### 6. `feature:` is a generic record; per-feature taxonomy deferred

`feature_type` is a string discriminator. No sub-schemas are claimed by this ADR. Per-feature schema taxonomy is **deferred entirely to a future Domain Adapter ADR** (Ring 3).

Each `feature:` record requires `id`, `name`, `feature_type`, plus optional `parameters_ref` (links to driving parameters in this Part), optional governed `adapter_payload` (Decision §9 shell), S1 annotations. For the Wedge, a single placeholder `feature_type` value suffices.

### 7. `geometry_ref:` split by role; two values

Roles:

- **`authoring_geometry`** — canonical Part state. The kernel geometry blob referenced via `vault_ref`.
- **`derived_export`** — D7-derived artifact (generated STEP, IGES, mesh, render) retained on the sidecar only when needed as a Part-bound reference (e.g., a release-signed export). Each derived record carries `derived_from` lineage citing the authoring geometry it was generated from.

**Cached visualizations are not a role.** They live outside the sidecar entirely: in the acceleration cache per [ADR/0001 §3](0001-storage-substrate.md), in the Domain Adapter's local cache, or in Workspace-local files. Never as canonical sidecar records.

`vault_ref` (content hash) is REQUIRED on every `geometry_ref:` record. The role enum is extensible by future Domain Adapter ADRs, but only with canonical roles (e.g., signed release exports retained on the sidecar).

### 8. `material:` as a collection of records

Most Parts have one material; welded / composite / multi-material Parts may have multiple records. Each record requires at minimum: `id`, `material_name`, `fact_provenance`. Other fields (`standard_ref`, `density`, `finish`, `heat_treatment`, etc.) are optional in the seed schema; per-project or per-Domain ADRs may tighten requirements.

In-Part records only for now. Future cross-Part material catalog reuse goes via the [External pointer Object pattern](../TruthModelSchema.md#5-two-named-non-disqualifier-patterns) under [OQ-0016](../OpenQuestions.md), with a future MaterialSpec Object Type promoted per the candidate-pool process. The eventual promotion is additive — a `material:` record gains an optional cross-Object reference shape — and this ADR does not pre-commit it.

### 9. Adapter shell — governed outer, opaque inner

Adapter metadata appears in `feature:adapter_payload` and `geometry_ref:adapter_ref`. The outer shell is schema-governed by AIADRA Core; the inner `adapter_payload` is adapter-defined and opaque to AIADRA Core.

Required outer fields:

- `engine` — discriminator (e.g., `"freecad"`, `"kicad"`).
- `adapter_schema_version` — adapter contract version (so adapter contract evolution is governed per [ADR/0003](0003-schema-governance.md)).

Optional outer fields:

- `engine_artifact_ref` — content-addressable Vault hash of the adapter's representation of the artifact (e.g., a FreeCAD `.FCStd` document hash).
- `stable_engine_object_id` — adapter-defined stable id portable across Workspaces (e.g., a named object inside a FreeCAD document).

**Anchor requirement.** Every adapter reference must resolve deterministically across Workspaces. On `geometry_ref:`, the record's required `vault_ref` satisfies this on its own. On `feature:`, where the record has no `vault_ref`, `stable_engine_object_id` is acceptable when it resolves within a referenced geometry/adapter artifact (whose own `vault_ref` provides the canonical anchor).

**Forbidden in canonical truth:**

- Workspace-local filesystem paths (e.g., `document_path: "C:/Users/.../doc.FCStd"`).
- Local-only identifiers that don't survive clone migration.
- Any field whose meaning depends on a single Workspace's filesystem state.

AIADRA Core uses the shell for dispatch (`engine` → Domain Adapter), validation (`adapter_schema_version` against adapter registry), and reference integrity. The inner `adapter_payload` is the adapter's responsibility.

The shell is Part-ADR-defined. Drawing / TestProcedure / EvidenceArtifact ADRs will reuse it. Promotion to a named cross-cutting spine pattern in [TruthModelSchema.md](../TruthModelSchema.md) waits on recurrence confirmation by a second Type ADR (flagged as a follow-up).

### 10. Revision schema

Part participates in formal release per [S2 commitment 1](../TruthModelSchema.md#1-revisions-are-separate-immutable-schema-governed-artifacts). Each Revision record carries the full reconstructable release-time snapshot per [S2 commitment 13](../TruthModelSchema.md#13-revision-snapshot-boundary) — all seven namespaces frozen at release time, with `revision_id` pinned on every release-bound managed-Object reference per [S2 commitment 8](../TruthModelSchema.md#8-cross-object-references-may-include-revision_id-required-in-released-revision-records).

Canonical path: `revisions/<object-uuid>/<revision-id>.yaml`.

### 11. Relationship endpoint participation

Part is a valid endpoint for the following relationship types (initial seed; expanded by future relationship-type ADRs):

| Relationship | Direction | Arity | Cycle policy | Notes |
|---|---|---|---|---|
| `satisfies` | Part → Requirement | binary | `trace_graph` | Part is source |
| `composed_of` | Assembly → Part | binary | `acyclic_dependency` | Part is target |
| `mated_to` | feature ↔ feature | binary | `undirected_constraint_graph` | **Assembly owns** most mate records; Part is a target endpoint via `published_ref` or feature addresses. Within-Part constraints (rare) may be Part-owned |
| `derived_geometry_from` | Part feature → Part `published_ref` | binary | `acyclic_dependency` | Part is source and target |
| `parameter_expression` | Parameter → Parameter(s) | source + many | `acyclic_dependency` | Part parameters as endpoints |
| `depicts` | Drawing → Part | binary | `trace_graph` | Part is target |

Future endpoint participations (flagged, out of scope): `verified_by` / `tested_against` when TestProcedure / EvidenceArtifact ADRs land; `supplied_by` only if Component / Supplier promotion makes it relevant.

These constraints take effect in the corresponding relationship-type schemas when those ADRs are written.

### 12. Bundle bump MINOR; ADR/0005 carries architectural ceremony

Bundle bumps **v0.1.0 → v0.2.0** per [ADR/0003 §11](0003-schema-governance.md). The change is additive: new `object.type = "Part"` discriminator value, new `sidecar/Part.schema.json`, new endpoint constraints on relationship-type schemas (when those land). No existing artifacts to break.

ADR ceremony applies separately because Part is the first concrete Object Type — it sets patterns (adapter shell, role-discriminated geometry, anchors guardrail, seven-namespace shape) that subsequent per-Type ADRs follow. This is governance ceremony per [Promotion Rule commitment 12](../TruthModelSchema.md#12-rule-evolution-is-governance-tier-decoupled-from-schema-bundle-bumps), decoupled from schema ceremony.

## Consequences

- **Schema bundle bump.** Active bundle moves v0.1.0 → v0.2.0. New `sidecar/Part.schema.json` lands in the `aiadra-core` bundle when authored. Number prefix mapping for `Part → P-NNNNNN` declared at the bundle.
- **Glossary update.** [Glossary](../Glossary.md) bumps v0.5 → v0.6 with a new entry for *Part* citing this ADR.
- **Forward references in relationship-type schemas.** The relationship endpoint constraints in Decision §11 take effect when relationship-type ADRs are written (next catalogue phase after the seed Types). Until then, the constraints are documentation-only; no relationship type schema currently enforces them because no relationship type schema exists.
- **Adapter contract.** The governed adapter shell (Decision §9) becomes the contract Domain Adapters implement. The first concrete adapter (FreeCAD for the Wedge) lands per Ring 3 / OQ-0004 / OQ-0005 work; this ADR's shell binds it.
- **Promotion Rule commitment 6 amendment.** Commitment 6's strict "ADR if MAJOR; Schema Change Note if MINOR" wording is contradicted by Part's case (MINOR bump + ADR ceremony required). Flagged for a follow-up TruthModelSchema bump (v0.6 → v0.7) addressed as its own short arc. Not blocking this ADR.
- **Cached visualization implementation.** Cached visualizations live in the acceleration cache, adapter-local cache, or Workspace-local files per Decision §7. Implementation details belong to the Domain Adapter contract and ADR/0001's acceleration cache; this ADR forbids them from the sidecar but does not specify where they are written.
- **Next catalogue ADRs.** Requirement and Assembly per-Type ADRs follow per the [Promotion Rule's seed catalogue order](../TruthModelSchema.md#verdict-summary). They cite this ADR's patterns (seven-namespace shape, adapter shell, anchors guardrail, MINOR-bump-with-ADR-ceremony) and adapt them to their respective Types.

## References

- [Manifesto.md](../Manifesto.md) — P3 (UUID identity), P4 (Design Intent first-class), P6 (Parameters first, raw geometry last), P7 (provenance + uncertainty), P9 (layered geometry access), P11 (AIADRA Core hosts nothing — bounds the adapter shell's portability rules).
- [Glossary.md](../Glossary.md) — *Object (Managed Object)* (carries the catalogue verdicts including Part as seed), *UUID*, *Number*, *Sidecar*, *Revision*, *Vault*, *Wedge*.
- [TruthModelSchema.md](../TruthModelSchema.md) — S0 (compositional schema; addressing), S1 (provenance / uncertainty), S2 (release / Revision), S2.5 (Number-binding lifecycle), S3 (relationships, published refs), Promotion Rule (C1–C4, D1–D7, two patterns, ceremony).
- [ADR/0001](0001-storage-substrate.md) — Storage substrate. §3 acceleration cache (where cached visualizations live).
- [ADR/0002](0002-canonical-format.md) — Canonical format. AIADRA YAML Profile; mandatory `schema_version`; deterministic JSON for manifests.
- [ADR/0003](0003-schema-governance.md) — Schema governance. §2 (discriminator), §5 (event immutability), §11 (bump ceremony — relevant for the MINOR-vs-MAJOR call in Decision §12).
- [OpenQuestions.md](../OpenQuestions.md) — OQ-0004 / OQ-0005 (Domain Adapter / FreeCAD, downstream of this ADR's adapter shell), OQ-0006 (multi-tool sequencing, affects future per-Type ADRs in the catalogue pool), OQ-0015 (Reservation file shape, downstream of the Number prefix decision), OQ-0016 (cross-project identity, downstream of future MaterialSpec promotion).
- Discussion trail (git-ignored, local only): `Docs/Discussions/20260518-3/Claude1.md` → `Codex1.md` → `Claude2.md` → `Codex2.md` → `Claude3.md` — full working-out of the twelve decisions across two Codex review rounds.
