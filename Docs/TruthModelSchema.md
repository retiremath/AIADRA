---
name: aiadra-truth-model-schema
status: draft
version: 0.7
last_updated: 2026-05-18
---

# AIADRA Truth Model Schema — Abstract Foundation

> The abstract, storage-independent foundation of the Product Truth Model: what an Object is, how its facts are addressed, how those facts are mutated, and how references compose across Objects. The synthesis layer for Ring 1's spine work; concrete per-Object schemas (Part, Requirement, Assembly, etc.) sit on top and are governed by their own ADRs.

## What this document is

[ADR/0001](ADR/0001-storage-substrate.md), [ADR/0002](ADR/0002-canonical-format.md), and [ADR/0003](ADR/0003-schema-governance.md) settled *where* the Truth Model lives, *what shape* it is written in, and *how that shape evolves*. They did not settle what an Object actually is in the abstract — what fields are universal, how facts inside an Object are named, how references between Objects compose. Those are Ring 1 questions, and this document is their synthesis.

Authority: ADRs own load-bearing decisions; the [Manifesto](Manifesto.md) owns principles. **When this document disagrees with either, this document is stale until updated.** Same authority status as [ArchitectureOverview.md](ArchitectureOverview.md) — synthesis, not source. The disagreement hierarchy remains: ADRs > Manifesto > ArchitectureOverview ≈ TruthModelSchema > ArchitectureGraph.

This document grows incrementally. Each Ring 1 spine question (S0, S1, S2, S2.5, S3) lands a section when it closes. The working-out — full alternatives, dialogue with Codex/GPT, and the rationale trail — lives in the git-ignored `Docs/Discussions/` files; what survives into git is the pinned position plus enough rationale to interpret it without those files.

## Spine status

| Question | Subject | Status |
|---|---|---|
| **S0** | Fact addressability and universal artifact envelope | **Pinned** ([Claude4.md](Discussions/20260518/Claude4.md), 2026-05-18) |
| **S1** | Provenance and uncertainty granularity | **Pinned** ([Claude6.md](Discussions/20260518/Claude6.md), 2026-05-18) |
| **S2** | Release binding and mutability model | **Pinned** ([Claude9.md](Discussions/20260518/Claude9.md), 2026-05-18) |
| **S2.5** | Object creation and Number-binding lifecycle | **Pinned** ([Claude11.md](Discussions/20260518/Claude11.md), 2026-05-18) |
| **S3** | Relationship modeling: inline / addressable records / Managed Objects | **Pinned** ([Claude14.md](Discussions/20260518/Claude14.md), 2026-05-18) |

**Spine complete.** Catalogue work opens next: promotion rule, seed Object Type list (Part, Requirement, Assembly first per [ADR/0003](ADR/0003-schema-governance.md)), concrete relationship type schemas, and first Revision / Manifest schema content. [OQ-0016](OpenQuestions.md) reopens before relationship taxonomy completes.

After S3 closes, catalogue work begins: promotion rule, then the seed Object type list (Part, Requirement, Assembly first, per [ADR/0003](ADR/0003-schema-governance.md)).

## S0 — Fact addressability and universal artifact envelope

S0 settles the abstract shape every Object shares and how facts inside an Object are stably named. Eight commitments, pinned 2026-05-18.

### 1. Compositional schema governance

Every Object schema is `BaseObject ⨁ TypeSpecific`, composed via JSON Schema 2020-12 (`allOf` / `$ref`). BaseObject defines the universal envelope; TypeSpecific defines the per-type payload. The composition is governed inside the schema bundle structure already settled in [ADR/0003 §2](ADR/0003-schema-governance.md); no new governance machinery is introduced.

A new envelope field added in a future MINOR bundle bump (per [ADR/0003 §4](ADR/0003-schema-governance.md)) propagates to every Object type automatically because the composition does the work.

### 2. Wrapped serialized envelope

Universal envelope fields live under `object.<field>` in the YAML. The discriminator for schema lookup stays at `object.type` per [ADR/0003 §2](ADR/0003-schema-governance.md). The payload's serialized layout — top-level sibling keys to `object`, or a structured wrapper — is type-specific and decided per-type during catalogue work; what is pinned now is only that the universal envelope is wrapped.

Reasons (recorded in [Claude4.md](Discussions/20260518/Claude4.md)):

- No amendment to [ADR/0003](ADR/0003-schema-governance.md) needed.
- The visible envelope boundary is a small but real diff-readability win.
- Namespace safety is structural rather than a discipline tax — TypeSpecific fields cannot accidentally collide with future envelope fields.

The compositional schema (commitment 1) is preserved either way; this is a serialized-form choice.

### 3. `schema_version` is governance, not engineering

`schema_version` is an artifact-envelope field governed by [ADR/0003 §11](ADR/0003-schema-governance.md)'s bump ceremony (PATCH = CHANGELOG; MINOR = Schema Change Note; MAJOR = its own ADR). It never appears as an Object event in the engineering event log. Schema migration emits an audit record to the operational audit log (named in the [Glossary](Glossary.md) entry for *Transaction*), not an `object_modified` or `schema_migration` event in the Product Truth event log.

This keeps schema governance and engineering provenance decoupled — bundle bumps do not pollute the engineering history, and parameter-change provenance does not become load-bearing on bundle-bump correctness.

### 4. Hybrid within-artifact addressing

Within-artifact addresses use two complementary forms:

- **Semantic / composite addresses** for schema-defined, non-renamable fields: `lifecycle.state`, `object.type`, `revision.current`, similar. Stable across schema migrations because the schema defines the address; if the schema renames a field, the bundle's alias table makes old addresses resolve at read time (commitment 5).
- **Stable local IDs** for user-authored, independently mutable, renameable records: parameters, relationship records, design-intent entries, tests, evidence, future similar categories. Each record carries an `id` field assigned at creation and never changing, plus a `name` field that may change without invalidating the record's address.

Within-artifact addresses then take the form `<namespace>:<local-id>` for record-typed facts (e.g., `parameter:param_plate_thickness`) and `<namespace>.<field>` for fixed schema fields (e.g., `lifecycle.state`). Collections compose naturally: the collection is named by its semantic namespace; the items are addressed by local id within it.

This is meaningfully better than either pure extreme (semantic-everywhere with alias chains, or stable-IDs-on-every-leaf). Verbosity stays bounded — only user-authored records carry id fields — and the facts most likely to be renamed have addresses that do not depend on alias resolution at all.

### 5. Events are immutable; address resolution is read-side

Historical events are never rewritten — per [ADR/0003 §5](ADR/0003-schema-governance.md), each event remains at its declared `schema_version` forever, and the registry retains every historical event schema. Sidecar migrators may rewrite sidecar addresses (because sidecars are migrated forward per [ADR/0003 §5](ADR/0003-schema-governance.md)), but events are not touched.

Address resolution for events therefore works read-side: each event target is resolved against the bundle named by the event's own `schema_version`, using that bundle's alias / crosswalk tables only as read-time resolution metadata. The active-authoring bundle is irrelevant to historical event resolution.

The practical implication: the sidecar/event invariant ([ADR/0001 §4](ADR/0001-storage-substrate.md)) is verified by folding events forward using each event's declared bundle for address resolution, not the project pin. The fold is deterministic across time because address rules are frozen alongside the event.

### 6. Cross-Object references

References across Objects use the base form:

```
(project_scope?, object_uuid, fact_ref?)
```

- **`project_scope`** is implicit/local for Ring 1. [OQ-0016](OpenQuestions.md) (cross-project Object identity, deferred to Ring 2) may make it explicit additively; Ring-1 references must round-trip through any Ring-2 extension without rewriting.
- **`object_uuid`** is the load-bearing identity. UUID, not Number — [Manifesto P3](Manifesto.md) and the [Glossary](Glossary.md) entry for *Number* both make Number presentation-only.
- **`fact_ref`** is optional. When present, it uses the within-artifact form from commitment 4. When absent, the reference targets the Object as a whole.

The UUID-keyed shape preserves the four-state locality distinction that Layer 3's API surface will need to expose ([ADR/0001 §6](ADR/0001-storage-substrate.md)): present-and-valid-locally, known-by-UUID-but-not-fetched, absent-because-stale, absent-because-invalid. A validator can answer locality questions from the UUID alone before reading the target.

### 7. List addressability rule

> If a list member can be independently referenced, changed, deleted, renamed, reordered, or carry provenance, it needs a stable key or id. If order itself is semantic, reorder must be an event. If the whole list is replaced atomically, position can remain internal and should not be an event target.

The rule is pinned at the spine level; catalogue work applies it per list type when concrete schemas are drafted.

### 8. Eventability sketches

Every address-touching mutation has a sketched event-fold shape. Concrete schemas come during catalogue work and the event taxonomy phase; the spine commits only to support these mutation kinds:

- **Object creation** — `object_created` produces the envelope (`uuid`, `type`, optional `number`, `lifecycle: in_work`, `schema_version`, audit fields). Fold target: the new sidecar's `object` block.
- **Record creation** — `<namespace>_created` adds a user-authored record at the declared local id. Fold target: append to the Object's `<namespace>` collection.
- **Field change** — `<namespace>_changed` updates a named field on a resolved target. Fold target: resolve by id (for record-typed namespaces) or by semantic path (for fixed-field namespaces), then update the named field.
- **Rename** — `<namespace>_renamed` changes a record's `name` (human-readable label) without changing its `id` (durable address). Fold target: the record's `name` field. Addresses stay stable; downstream events keep targeting the same id.
- **Retirement / tombstone** — `<namespace>_retired` marks a record as retired with a timestamp and reason; records are not deleted. Where-used queries skip retired endpoints by default; historical events targeting the retired id still resolve correctly.
- **List reorder** — `<namespace>_reordered` rewrites a collection's order; emitted only when order is semantic.
- **Address / id stability validation** — *not an event*, but a commit-time validator invariant: every id ever introduced into a sidecar must continue to resolve (alive or retired) on every subsequent commit; every event target must resolve under its declared bundle.

Schema migration is **explicitly excluded** from the engineering event log per commitment 3. Audit records for migrations live in the operational audit log, not here.

## S1 — Provenance and uncertainty granularity

S1 settles how the universal commitment from [Manifesto P7](Manifesto.md) — *every fact carries provenance and uncertainty* — is realized concretely under S0's address model. Nine commitments, pinned 2026-05-18.

### 1. Every addressable fact has effective provenance and effective uncertainty

For every address an Object's schema permits to hold a value, there is an effective `provenance` and an effective `uncertainty`. The resolver (commitment 2) guarantees a definite answer for every address; there is no "unknown" default and no implicit fallback to silence.

### 2. Deterministic four-level resolver walk

Effective provenance (resp. uncertainty) at an address A in Object O is the first explicit annotation found walking:

1. **A itself,** if A carries an explicit annotation.
2. **The record that contains A,** if A is inside a user-authored record that carries a record-level annotation.
3. **The namespace default on the envelope,** if O's envelope declares a default for A's namespace.
4. **The envelope default,** set at `object_created` and updatable via envelope-targeting events.

If no annotation is found at any level, the validator hard-rejects the artifact at commit time. There is no implicit "unknown" default; the schema or the data must produce a resolvable effective annotation.

The walk is deterministic, schema-validatable, and O(depth)-bounded per address.

### 3. No canonical project-level defaults

The resolver stops at the Object envelope. Project-level defaults would make effective annotation depend on **mutable project configuration**, breaking the self-contained-sidecar property and complicating archival reads, release reconstruction, branch review, and schema migration ([ADR/0003 §6](ADR/0003-schema-governance.md)'s archival mode is designed to avoid exactly this).

Project templates may pre-fill envelope defaults at creation time — that is authoring-time convenience without canonical context dependence. **Namespace defaults, when used, live as explicit Object data on the envelope**, not as schema magic. The schema may require or permit them; the actual values used for resolution are stored in the sidecar.

### 4. Provenance and uncertainty are independent fields

The [Glossary](Glossary.md) defines distinct value sets for the two — provenance categories (`released_fact`, `computed_result`, `imported_supplier_data`, `human_input`, `ai_inference`, `ai_proposal`) and uncertainty labels (`verified`, `computed`, `estimate`, `requires_validation`, `stale`) — and they evolve independently. They travel together in storage (often adjacent in the YAML) and are resolved by the same walk, but the schema does not bundle them into a single trust envelope.

Validators may later warn on suspicious combinations (e.g., `ai_inference + verified` with no validation/approval path in the transaction history). This is a downstream validator opportunity, not an S1 commitment.

### 5. Computed facts carry `derived_from` inside fact provenance

A `computed_result` fact's provenance may carry structured input references — for example:

```yaml
fact_provenance:
  category: computed_result
  derived_from:
    - "parameter:param_volume"
    - "parameter:param_density"
```

This is **computation lineage**, not the design dependency graph. Examples that belong: `mass_g` computed from `volume_mm3` and `density_g_per_mm3`; a validation result from a test output and a requirement threshold; a generated BOM quantity from assembly composition. Examples that do not belong (these are relationships, S3 territory): Part satisfies Requirement, Assembly contains Part, Supplier provides Component.

The same graph engine may index both for query purposes; the model keeps them distinct.

### 6. AI-originated values preserve AI origin after human approval

When an AI proposes a value and a human approves it without editing, the committed fact's provenance stays `ai_proposal` (or `ai_inference` when the AI computed rather than guessed). The human approver's identity lives in the transaction record, not in the fact provenance.

Reasons: keeps "where did the value come from?" and "who approved committing it?" as orthogonal facts; preserves the AI's contribution in the engineering record across the lifetime of the project; symmetric with the AI/human authoring distinction the [Glossary](Glossary.md) already establishes; consistent with [Manifesto P2](Manifesto.md) — probabilistic AI and deterministic core do not silently mix at approval time either.

### 7. Envelope identity fields exempt; Lifecycle State provenance-bearing

The envelope splits into two groups under S1:

- **Exempt from fact provenance** — `object.uuid`, `object.type`, `object.created_at`, `object.schema_version`. Identity and artifact governance, not engineering facts in the Manifesto P7 sense. The envelope's *own* identity fields are not provenance-bearing addresses; they are the artifact's identity.
- **Provenance-bearing** — `object.lifecycle.state`. A current governed fact about the Object; changes through deterministic transitions, carries actor and justification, directly controls operation legality. Its effective uncertainty is usually `verified` once committed, because the state is determined by the accepted lifecycle transition event rather than inferred.

The envelope's `object.provenance` / `object.uncertainty` defaults apply to addresses *below* the envelope — they are level-4 fallbacks in the resolver walk, not annotations on the envelope's own identity fields.

### 8. Fact provenance is distinct from event provenance

Two layers of provenance:

- **Fact provenance** lives on addresses, resolved by the walk. Answers: where did the value come from? Stored on the sidecar; mutated by events that carry `fact_provenance` (and `fact_uncertainty`) in their payload.
- **Event provenance** lives in the event base schema ([ADR/0003 §3](ADR/0003-schema-governance.md)'s `_base.schema.json`) and the transaction reference. Answers: where did the transition record come from, under what transaction, with what approval? Carries `event_id`, `actor`, `timestamp`, `transaction_id`, and approval details via the transaction.

Event payload fields for fact-level deltas are named `fact_provenance` and `fact_uncertainty` to keep the two layers visibly distinct. Overloading the single word "provenance" across both layers was the trap S1 explicitly avoided.

### 9. Release semantics are out of scope for provenance

**`released_fact` is origin/source, not mutability.** A value can be `released_fact` if it originated from an already released source or baseline (a supplier datasheet, another project's released Revision, a prior Release of the same Object). The current Object's mutability is governed by S2's release binding model, not by rewriting provenance.

Specifically:

- A supplier datum imported from a released supplier datasheet may be `released_fact` even while the local Object is `in_work`.
- A locally authored parameter stays `human_input` after the Object is released; release controls mutability via S2.
- A computed value in a released Revision stays `computed_result`; release freezes it, but does not change where it came from.

This boundary is what lets S2 work cleanly on release/mutability without dragging fact provenance into the question.

### Annotation validation rules

Per the eventability gate, S1 commits the validator to enforce at commit time:

- Every address the schema permits and that holds a value must produce an effective annotation under the four-level walk. **Hard-reject** otherwise.
- Annotation events must target stable S0 addresses (semantic path or `<namespace>:<local-id>`). No YAML-position targets.
- Unsetting an explicit annotation is allowed only when a lower level still produces an effective annotation. **Hard-reject** otherwise, with a diagnostic naming the address.
- Retired records retain their historical annotations. New annotation changes against retired records are refused by default; a future lifecycle rule may relax this for specific retired-state operations.

### S1 eventability sketches

Value-changing events and annotation events have established shapes (concrete schemas come during catalogue / event-taxonomy work).

**Atomic value + annotation update.** The common case. When a value changes and its annotation must also change atomically (recomputation, AI-proposed commit), one event carries both deltas:

```
parameter_changed {
  target: { object_uuid, namespace: "parameter", id },
  field: "value",
  from, to,
  fact_provenance?: { category, derived_from?, ai_agent_ref?, ... },
  fact_uncertainty?: <label>
}
```

**Standalone annotation change.** Annotation-only mutations, when no value changes (e.g., a `requires_validation` parameter upgraded to `verified` after a test passes):

```
annotation_changed {
  target: { object_uuid, address, kind: "provenance" | "uncertainty" },
  from: <old value or null>,
  to: <new value or null>,
  reason
}
```

`to: null` removes the explicit annotation and restores inheritance from the next-lower level.

**Envelope default change.** Inheritance shifts apply to every address that resolves through the default:

```
envelope_default_changed {
  target: { object_uuid, kind: "provenance" | "uncertainty", scope: "object" | "namespace:<ns>" },
  from, to,
  reason
}
```

## S2 — Release binding and mutability model

S2 settles how the immutable Revision relates to the mutable sidecar, what state crosses the release boundary, and how cross-Object references resolve across that boundary. The boundary established by [S1 commitment 9](#9-release-semantics-are-out-of-scope-for-provenance) is the foundation: release controls mutability; provenance owns origin. Thirteen commitments, pinned 2026-05-18.

### 1. Revisions are separate immutable schema-governed artifacts

Each released Revision is its own immutable artifact stored at a canonical path (likely `revisions/<object-uuid>/<revision-id>.yaml`; precise layout decided in catalogue work). Revision becomes a **fourth artifact kind** under [ADR/0003 §2](ADR/0003-schema-governance.md)'s `(bundle_version, artifact_kind, discriminator) → schema` framework, alongside Sidecar, Event, Manifest. Discriminator most likely `object.type` — a Revision of a Part has the same shape as a Part sidecar, frozen.

Revision records carry `schema_version`; are validated under their declared historical bundle; readable forever via archival mode ([ADR/0003 §6](ADR/0003-schema-governance.md)); explicitly immutable after creation. The formal extension of ADR/0003 §2's artifact-kind table waits for the first Revision-schema ADR during catalogue work.

### 2. Revision identity is `(object_uuid, revision_id)` with content hash as integrity

Canonical Revision identity is the tuple `(object_uuid, revision_id)`. `revision_id` is a stable local sequence — alphabetical or numeric, bikeshedding for catalogue work. The Revision record's `revision_content_hash` is computed over the canonical serialization of the record, **including `schema_version` and every field required to validate under its declared bundle**. The hash is the integrity proof, not the identity. Presentation forms ("Rev A") map to the canonical tuple.

This is the same principle as [ADR/0003 §9](ADR/0003-schema-governance.md)'s bundle digest: the hash must prove the exact frozen artifact under its declared validation rules, not a loose payload.

### 3. Sidecar is the current working state

The sidecar continues to be mutable across release boundaries. [Manifesto P8](Manifesto.md)'s "Released truth is immutable" applies to the Revision record, not to the sidecar. The [Glossary](Glossary.md) entry for *Sidecar* ("Holds the current authoritative state of the Object") is taken at its word — sidecar = current iteration, always.

### 4. Sidecar carries explicit revision metadata

The envelope's `object.revision` block makes the lifecycle baseline and the fold baseline both discoverable from canonical state. Required fields:

- `object.revision.current` — latest released Revision id (`null` before first release).
- `object.revision.working.base_revision` — the Revision the working state began from (`null` when no Revision has been released yet).
- `object.revision.working.status` — `in_work`, `under_review`, or absent when no working changes exist.

Without an explicit baseline pointer, [ADR/0001 §4](ADR/0001-storage-substrate.md)'s "fold from a prior known-consistent baseline" becomes ambiguous under branches, parallel change orders, or stale workspaces.

### 5. Released-truth immutability applies to Revision records, not to the sidecar

[Manifesto P8](Manifesto.md) governs the Revision record. The sidecar continues as the working state for the next iteration; the prior Revision record sits frozen alongside as its own artifact, with its `revision_content_hash` proving it has not been mutated.

### 6. Object lifecycle is monotonic forward; iteration state lives in the working frame

`object.lifecycle.state` never slips backward. Once `released`, stays `released` (until eventually advancing to `superseded` or `obsolete`). Working iteration state lives in the `object.revision.working` frame, **not** in `lifecycle.state`. The Glossary's existing five-value enumeration (`in_work`, `under_review`, `released`, `superseded`, `obsolete`) stays valid: pre-first-release lifecycle states (`in_work`, `under_review`) live on the Object; post-first-release iteration states live in the working frame.

Coexistence is the point. An Object with Rev A released and work toward Rev B in progress carries `object.lifecycle.state = "released"` and `object.revision.working = {base_revision: "A", status: "in_work"}` simultaneously. Both facts visible; neither overwriting the other.

No Glossary change required.

### 7. Release Manifest entries carry `(object_uuid, revision_id, revision_content_hash)`

Per Revision in scope of a Release. The triple is what the manifest signs and what archival reads use to verify the bound Revision record's integrity. The manifest is the **product-level** cryptographic baseline; commitment 8 keeps Revision records readable on their own.

### 8. Cross-Object references may include `revision_id`; required in released Revision records

The S0 cross-Object form extends additively:

```text
(project_scope?, object_uuid, revision_id?, fact_ref?)
```

- **Current sidecars** may omit `revision_id`. Absent means "current working state" — the reference resolves to whatever Revision is currently authoritative at the target Object.
- **Released Revision records** require `revision_id` for managed-Object references that are part of the released meaning. The validator hard-rejects a Revision record whose release-bound reference to a managed Object omits `revision_id`.
- **Release Manifest's signed baseline** is a *reinforcing* source of truth — it cross-checks and signs the product baseline — but is **not** a fallback for ordinary Revision reference resolution. A Revision record reads correctly in isolation.

This makes Revisions self-describing for archival reads, single-Object reuse, partial releases, impact analysis, and (downstream of [OQ-0016](OpenQuestions.md)) cross-project references.

### 9. Revision records serve as fold baselines

For the [ADR/0001 §4](ADR/0001-storage-substrate.md) sidecar/event invariant. The sidecar's `object.revision.working.base_revision` names the baseline explicitly; validators do not guess. Folding events forward from the named baseline must produce the current sidecar's state; divergence is a hard error at commit time. The first Revision's baseline is the empty Object; each subsequent Revision rebaselines on its predecessor's state plus the events accumulated since.

### 10. `revision_amended` is rejected

Released Revision records are immutable. Corrections require either a **new Revision** (canonical path) or a separate **non-mutating erratum/correction record** that does not modify the frozen snapshot. The shape of the erratum record is not pinned in S2 — that is catalogue work. What S2 pins is the **non-mutating behavior**: no operation on a released Revision record ever rewrites or replaces it.

### 11. Release transactions are atomic across all canonical artifacts

A release transaction atomically commits four things:

1. The Revision record file at its canonical path (content per commitment 13).
2. The `revision_released` event appended to the event log.
3. Sidecar `object.revision` metadata update.
4. Lifecycle / iteration state update if the transition triggers one.

The transaction is the unit that writes; the event is the unit that records the transition; folding reads events but never creates files. This matches the [Glossary](Glossary.md)'s *Transaction* shape (`begin → modify → recompute → validate → compare → human approval → commit-or-rollback`).

### 12. Layer 4 and Layer 5 couplings acknowledged

- **Layer 4 (change-order pipeline).** Revision creation is gated by the change-order pipeline — approval, validation, impact analysis, ECR / ECO flow. S2 commits to the gate's existence; concrete mechanics defer to Layer 4 work.
- **Layer 5 (Domain Adapter).** Domain Engines must distinguish editing a working sidecar from viewing a frozen Revision. The AI Action Protocol API ([Layer 3](ArchitectureOverview.md), Ring 2) exposes baseline Revision and working iteration status so adapters never accidentally mutate released snapshots. Concrete API surface defers to Ring 2.

### 13. Revision snapshot boundary

A Revision record carries the **full reconstructable release-time Object state**:

- Envelope identity — UUID, Type, Number, audit fields, `schema_version`.
- Lifecycle-at-release (the Object's `lifecycle.state` at the moment of release; typically `released`).
- Revision metadata — `revision_id`, release timestamp, approval / transaction refs.
- The engineering payload — parameters, design intent, type-specific fields.
- Relationships, with `revision_id` pinned on every release-bound managed-Object reference per commitment 8.
- Fact provenance and uncertainty per [S1](#s1--provenance-and-uncertainty-granularity) commitments.
- Release / transaction refs.

The Revision record does **not** carry the mutable `object.revision.working` frame. That frame is about the *next* iteration and belongs to the sidecar after release. A Revision is a self-contained, reconstructable, frozen snapshot of what was released; nothing about future work appears inside it.

### S2 eventability sketches

**Revision released (transaction-atomic per commitment 11).**

```
revision_released {
  target: { object_uuid },
  revision_id: <stable-local-sequence>,
  revision_content_hash: <sha256-of-canonical-serialized-revision-record>,
  released_at: <timestamp>,
  manifest_ref?: <release-manifest-id-or-hash>,
  approval_ref: <transaction's-approval-record>
}
```

The release transaction writes the Revision record file (content per commitment 13), appends this event, updates the sidecar's `object.revision.current` to the new id, and advances `object.lifecycle.state` if it was not already `released`. Folding the event updates the sidecar's metadata; folding does not create files.

**Working iteration started.**

```
working_revision_started {
  target: { object_uuid },
  base_revision: <revision-id-or-null>,
  initiated_by: <transaction-or-ai-or-human-ref>,
  fact_provenance: { category: "human_input" | "ai_proposal" }
}
```

Fold target: sets `object.revision.working` block — `base_revision` to the named baseline (or `null` for first iteration), `status` to `in_work`. **Object's `lifecycle.state` is unchanged** under commitment 6.

**Working iteration submitted for review.**

```
working_revision_submitted {
  target: { object_uuid },
  base_revision: <revision-id-or-null>,
  reviewers?: [<ref>...],
  fact_provenance
}
```

Fold target: `object.revision.working.status` transitions to `under_review`. Lifecycle.state unchanged.

**Object-level lifecycle advances.**

```
object_superseded {
  target: { object_uuid, address: "object.lifecycle.state" },
  from: "released",
  to: "superseded",
  superseded_by?: <other-object-uuid>,
  justification,
  fact_provenance, transaction
}

object_obsoleted {
  target: { object_uuid, address: "object.lifecycle.state" },
  from: <prior-state>,
  to: "obsolete",
  justification,
  fact_provenance, transaction
}
```

Both follow [S1](#s1--provenance-and-uncertainty-granularity)'s atomic-value-plus-annotation pattern. Object-level lifecycle transitions; Revision records stay exactly as they were minted.

**Reference resolution inside a Revision record (commitment 8 effect).** The validator hard-rejects any Revision record whose release-bound reference to a managed Object omits `revision_id`. References to non-managed-Object scalars (a unit string, an enum value) do not carry `revision_id` and are unaffected.

## S2.5 — Object creation and Number-binding lifecycle

S2.5 settles when an Object acquires its Number and what states the Number occupies through creation, reservation, merge, and stability. The framework is already pinned by Ring 0 (UUID + Reservation file mechanics in the [Glossary](Glossary.md); Git rebase as the conflict-resolution path in [ADR/0001 §5](ADR/0001-storage-substrate.md); event immutability after merge in [ADR/0003 §5](ADR/0003-schema-governance.md)); S2.5 is small because most of the question is already answered. Eleven commitments, pinned 2026-05-18.

### 1. Number is required at Object creation

Every `object_created` event carries a `number` field; every sidecar has `object.number` set from day 1. UUID-only canonical Objects are not valid. Exploration without a canonical Number happens in [Transaction](Glossary.md)-preview state per the Glossary's failed-Transaction rule (no trace on canonical truth).

### 2. Object creation Transaction allocates UUID and Number atomically

The Transaction that emits `object_created` also writes to the Reservation file in the same atomic commit. UUID is assigned; Number is allocated; both land together. There is no canonical state in which the Object exists but the Reservation file does not record its Number.

### 3. Reservation conflicts resolve pre-merge through Git rebase

When Alice and Bob both pick the same Number in parallel branches, the conflict is detected at PR time on the Reservation file. One PR merges; the other rebases — Bob picks a new Number, which **rewrites his local `object_created` event's `number` field** before re-push. This is standard Git rebase mechanics per [ADR/0001 §5](ADR/0001-storage-substrate.md).

### 4. Merged event history is immutable; pre-merge branch history may be rewritten

The boundary for [ADR/0003 §5](ADR/0003-schema-governance.md)'s "events never migrated" rule is **merge into protected Commonspace**, not push. A PR branch may be force-pushed during rebase-driven conflict resolution before it lands in main. Once merged, the events in main are immutable forever.

### 5. Numbers are stable after merge by default

Routine Object edits never change the Number. The Number is identity-display; the Object's UUID is what other Objects reference (per [S0 commitment 6](#6-cross-object-references)).

### 6. `number_rebound` exists for rare, ceremony-heavy renumbering

A dedicated event type carries renumbering with mandatory justification and stronger approval than ordinary Object edits (per Layer 4 handoff). Expected to be rare across a project's lifetime. The event type's existence is itself a discouragement — renumbering is not a routine operation, and the required justification makes that explicit.

### 7. `number_rebound` retires the old Number as an alias

The old Number becomes a **permanently retired alias** of the same Object. It does not return to the Reservation file's available pool; it cannot be assigned to any other Object, ever. A Number history per Object accumulates over the project's lifetime:

```text
P-000123 -> object_uuid (retired alias)
P-000124 -> object_uuid (current)
```

This preserves the meaning of every historical reference (old issues, PRs, drawings, commit messages, emails) to the prior Number. Reusing a retired Number for a different Object would make historical references ambiguous; AIADRA does not permit it.

### 8. Released Revision records keep their release-time Number

Per [S2 commitment 13](#13-revision-snapshot-boundary), the Revision record's snapshot is frozen at release time, including the Number-at-release. After a `number_rebound`, the current sidecar and future Revisions use the new Number; historical Revision records continue to show the original Number. Reading Rev A of an Object that was later renumbered shows the release-time Number; reading the current sidecar shows the current Number. Both are correct in their contexts.

### 9. Initial `object.lifecycle.state` at creation

Defaults to `in_work`. `under_review` is allowed at creation when the Transaction includes review or import rationale (e.g., for imported Objects already reviewed externally). Higher states (`released`, `superseded`, `obsolete`) require the prior states' work and are not valid at creation.

### 10. Number format and Type → prefix mapping are per-project policy

S2.5 does **not** pin the string format of Numbers (`P-000123`, `REQ-0014`, etc.) or the mapping from Object Type to Number prefix. These are per-project policy under the Reservation file's governance, decided in ADR/0004 / [OQ-0015](OpenQuestions.md) or per-project configuration. S2.5 commits only that the Number field exists, is allocated through the Reservation file, and follows the lifecycle above.

### 11. `object.number` is governed identity metadata, not provenance-bearing

`object.number` joins [S1 commitment 7](#7-envelope-identity-fields-exempt-lifecycle-state-provenance-bearing)'s exempt list alongside `object.uuid`, `object.type`, `object.created_at`, `object.schema_version`. It does not carry `fact_provenance` / `fact_uncertainty`. `number_rebound` carries event-level rationale per [S1 commitment 8](#8-fact-provenance-is-distinct-from-event-provenance)'s event-provenance layer — justification, approver, transaction reference — not fact-level annotations.

This is consistent with the [Glossary](Glossary.md)'s framing of Number as presentation rather than truth. The event log records *who changed the Number and why*; it does not pretend the Number has engineering-origin categories like `computed_result` or `ai_inference`.

### Handoffs

S2.5 produces explicit downstream constraints:

**To ADR/0004 / [OQ-0015](OpenQuestions.md) (Reservation file shape).** The file must support: current Number → Object UUID binding; retired Number alias → Object UUID binding; rejection of reuse for both current and retired Numbers; atomic create allocation with `object_created`; atomic rebind allocation with `number_rebound` (old Number to retired); merge-conflict detection on the Number key; history sufficient to explain why a Number is retired.

**To Layer 4 (change-order pipeline).** `number_rebound` requires stronger approval than ordinary Object edits. Concrete approval mechanics defer to Layer 4; the policy is flagged here.

**To Layer 3 / Ring 2 (AI Action Protocol API).** Current Number lookup and historical Number lookup are both first-class. Searching `P-000123` after a renumbering lands on the same Object and surfaces the renumbering ("now P-000124"). API surface defers to Ring 2; the obligation is flagged here.

### S2.5 eventability sketches

**`object_created`** (extends S0's sketch with required Number per commitment 1):

```
object_created {
  envelope: {
    uuid,
    type,
    number,                                  // REQUIRED per commitment 1
    lifecycle_state: "in_work" | "under_review",   // optional; defaults in_work
    schema_version,
    created_at,
    created_by_transaction
  },
  initial_review_rationale?: <text>,         // REQUIRED when lifecycle_state = "under_review"
  fact_provenance: { category: "human_input" | "ai_proposal", ... },
  transaction
}
```

Fold target: the new sidecar's `object` block. The Transaction also writes to the Reservation file in the same atomic commit per commitment 2.

**`number_rebound`** (per commitments 6, 7, 11):

```
number_rebound {
  target: { object_uuid, address: "object.number" },
  from: <old-number>,
  to: <new-number>,
  justification                              // REQUIRED — ceremony-heavy
  // Event base carries: event_id, actor, timestamp, transaction_id.
  // Transaction record carries approver (stronger approval per Layer 4 handoff).
  // No fact_provenance / fact_uncertainty — Number is identity metadata per commitment 11.
}
```

Fold target: `object.number` on the current sidecar updates to `<new-number>`. The Reservation file is updated atomically: new Number allocated; old Number retired as alias per commitment 7. Released Revision records are unaffected per commitment 8.

## S3 — Relationship modeling

S3 settles how connections between Objects (Part `satisfies` Requirement, Assembly `composed_of` Part, mate referencing a face, parametric expressions across part/assembly/global levels, drawings derived from models) are modeled in the abstract. This was the largest spine question by surface — the framing was expanded after research surveyed how production CAD systems (SolidWorks / Creo / NX / CATIA / FreeCAD / Onshape) handle topological identity, how PLM systems (Aras / Windchill / Teamcenter / OpenBOM / OpenPLM) model engineering relationships, and how academic / standard work (Bidarra & Bronsvoort persistent naming, SysML v2, STEP AP242 e3, OSLC, SIGGRAPH 2023 B-rep matching) approaches the problem. Seventeen commitments, pinned 2026-05-18 ([Claude14.md](Discussions/20260518/Claude14.md)).

Grouped into five sections for readability.

### A. Relationship records — the spine pattern

#### 1. Relationships are first-class addressable records

Not inline fields, not full Managed Objects. Stored under the `relationship:` namespace per [S0 commitment 4](#4-hybrid-within-artifact-addressing). Each carries stable local id, type, endpoint(s), optional properties, fact provenance / uncertainty per [S1](#s1--provenance-and-uncertainty-granularity).

#### 2. Three kinds of relationships are explicitly recognized

- **Engineering-graph** — whole-Object endpoints, traceability semantics (`satisfies`, `composed_of`, `derived_from`, `supersedes`, `allocates_to`).
- **Geometric / topological** — entity-within-Object endpoints, recipe-based selectors (`mated_to`, `derived_geometry_from`, drawing dimension attachments).
- **Parametric** — parameter-to-parameter endpoints, expression-based linkage (`parameter_expression`, interpart constraints, skeleton-driven values).

First-class-record shape is uniform across all three; content and resolution semantics differ.

#### 3. Relationships are source-anchored

Stored on the source endpoint Object as declared by the relationship type's schema. Reverse direction (where-used) is derived from the acceleration cache per [ADR/0001 §3](ADR/0001-storage-substrate.md). For symmetric relationships (rare), the type schema declares a tie-breaking rule; validators detect double-storage.

#### 4. Relationship properties follow S1 annotation rules

Per-fact provenance / uncertainty with container defaults. The relationship record is the container; its properties inherit unless overridden, per the S1 resolver walk.

#### 5. Relationships have create / change / retire events

`relationship_created`, `relationship_changed`, `relationship_retired`. Retirement is S0 tombstoning; relationships are never deleted from history. Where-used queries skip retired endpoints by default; historical events targeting retired relationships still resolve correctly.

#### 6. Relationship type schemas declare arity

Binary is the default. Types may declare `source + many targets` (e.g., a parametric expression with multiple input parameters) or `multi-endpoint` (e.g., a CAD constraint over three coplanar entities) when domain semantics require it. The first-class-record model scales to all arities; only the schema changes.

#### 7. Relationship types are schema-governed under ADR/0003

A `relationship/<type>.schema.json` directory joins `sidecar/`, `event/`, `manifest/`, `revision/` in the bundle structure. Each type schema declares: endpoint Object Type constraints, directionality, arity, optional properties, the `fact_ref` form it uses, default binding mode.

**SysML v2's vocabulary** (`satisfy`, `derive`, `verify`, `refine`, `allocate`, `trace`) is the **baseline taxonomy for engineering-graph traceability relationships only.** CAD, assembly, procurement, geometric relationships use domain-native vocabularies aligned with STEP / AP242 / PLM standards as appropriate (`composed_of`, `mated_to`, `derived_geometry_from`, `parameter_expression`, `supplied_by`, `tested_against`, etc.).

### B. Endpoint forms

#### 8. Engineering-graph endpoints use the cross-Object form

`(project_scope?, object_uuid, revision_id?, fact_ref?)` per [S2 commitment 8](#8-cross-object-references-may-include-revision_id-required-in-released-revision-records), with `fact_ref` resolving to a semantic address inside the target Object.

#### 9. Geometric / topological endpoints use a layered selector

```yaml
selector:
  topology_ref_id: "toporef_mounting_bore_axis"     # stable anchor id; durable addressable reference identity
  source_feature_id: "feature_m8_mounting_hole"     # optional context (the feature that produced the anchor)
  encoded_history: "Face6;:M2;FUS;:T1:5:F"          # recipe at the B-rep resolver layer (RealThunder-style)
  selector_predicate: "axis of the M8 mounting hole bore"   # human-readable intent
  repair_hint?: { ... }                             # optional metadata for AI-driven repair
```

- `topology_ref_id` is the durable identity; one feature can expose multiple addressable anchors (a hole feature exposes axis, face, circular edge — each gets its own `topology_ref_id`).
- `encoded_history` is the resolver input; survives regeneration when the operation graph stays well-formed.
- `selector_predicate` is **required for AIADRA-authored references and published refs**; absent allowed only for imported / bulk geometry with explicit `requires_validation` uncertainty.
- `repair_hint` is optional metadata for AI-driven repair (commitment 14).

Background: layered identity follows the Bidarra & Bronsvoort 2005 dual-representation pattern (parametric definition layer + B-rep result layer), extended with FreeCAD 1.0 / RealThunder-style encoded names at the resolver layer.

#### 10. Parametric endpoints link parameter addresses via expressions

Endpoints are parameter addresses (`<object_uuid>:parameter:<id>`); the relationship's properties carry the expression. Skeleton-model patterns build on this — a master Object's parameters propagate to downstream Objects via `parameter_expression` relationships.

#### 11. Published reference ports are first-class addressable records owned by Objects

Stored under the `published_ref:` namespace alongside `relationship:`. Each published ref owns a layered topological selector. A target Object's owner controls what is publicly referenceable; consumers depend only on the stable published surface.

```yaml
published_refs:
  - id: "pub_motor_bore_axis"
    name: "motor_bore_axis"
    kind: "axis"
    selector:
      topology_ref_id: "toporef_motor_bore_axis"
      source_feature_id: "feature_m8_mounting_hole"
      encoded_history: "..."
      selector_predicate: "axis of the M8 motor mounting bore"
```

**Release-bound cross-Object geometric relationships MUST target a `published_ref`**, unless the relationship type explicitly declares a narrow exception (for import / transitional / private adapter cases) and the resulting reference carries `requires_validation` with diagnostics. **The default production rule is published interface only.**

Raw topological selectors remain valid for: within-Object references; unpublished bulk-imported geometry; private / internal adapter state; transitional repair workflows. But not for release-bound cross-Object geometric references by default. This is the discipline that makes the published-ref mechanism load-bearing for cross-Object reference durability — exactly the CATIA Publications / Creo Copy-Geom / NX WAVE / Onshape Derived lesson.

### C. Binding, release, and graph invariants

#### 12. Float vs Fixed binding mode is explicit per-relationship

In the authoring sidecar:

- **Float** — endpoint reference resolves to the target's current Revision / current working state at read time.
- **Fixed** — pinned to a specific `revision_id`; never re-resolves.

Default is Float for working sidecars; per-relationship Fixed for "derived from a specific past Revision" semantics. **Release materializes Fixed bindings into the Revision record snapshot** per [S2 commitment 13](#13-revision-snapshot-boundary) without rewriting the working sidecar's authoring binding. The sidecar's Float relationship stays Float for the next iteration's authoring intent; the Revision record carries the resolved Fixed reference as part of the frozen snapshot.

A sidecar `relationship_changed` event is emitted **only** when the author's intent itself changes. Release-time materialization happens inside the `revision_released` transaction per [S2 commitment 11](#11-release-transactions-are-atomic-across-all-canonical-artifacts), not as a separate sidecar event.

#### 13. Per-type cycle and graph-class policy

Each relationship type's schema declares its graph class. Initial enumeration (**extensible by catalogue schemas** under ADR/0003 governance):

- `acyclic_dependency` — validator hard-rejects cycles at commit time. Applies to dependency-semantic types (`composed_of`, `derived_geometry_from`, `parameter_expression` with directional inputs).
- `undirected_constraint_graph` — closed loops permitted (CAD constraint networks, `mated_to`). Over-constraint is a separate solver concern, not a cycle violation.
- `trace_graph` — cycles permitted; traceability semantics are not computational dependencies (`satisfy`, `verify`, `trace`, `allocate`, `refine`).
- `self_allowed` / `self_forbidden` — declared per type for self-relationships.

The spine commits to cycle validation as a Truth Model invariant; per-type schemas declare what valid means. The enumeration above is the initial set; catalogue work may add new policy classes through ADR/0003 bundle bumps when new relationship-domain semantics require them.

### D. Layer 3 / Layer 5 obligations

#### 14. AI-driven repair as a first-class Layer 3 obligation

When `encoded_history` fails to resolve, the AI Action Protocol surface (Ring 2 / Layer 3) supports a `propose-repair` operation. The agent examines `selector_predicate`, `repair_hint`, current geometry, and the Object's feature history to propose a rebind. Human approves through Transaction per [Manifesto P5](Manifesto.md).

**Repair updates `encoded_history` and `repair_hint` only.** `topology_ref_id` and `selector_predicate` remain unchanged — the intended reference is the same anchor; the recipe rebinds.

**Semantic rebind** (changing what's being referenced — different `topology_ref_id` or `selector_predicate`) is not repair; it requires `relationship_retired` + `relationship_created`, or an explicit `relationship_changed` event targeting the endpoint as a whole. The validator enforces this boundary at commit time. Unresolved references produce validation diagnostics, never silent canonical mutation.

The frontier (Jones et al., SIGGRAPH 2023) shows learning-based B-rep matching as the algorithmic substrate; AIADRA's AI-native posture treats it as a first-class operation rather than an emergency repair tool.

#### 15. AP242 external element references round-trip via Layer 5 Domain Adapters, where AP242 can represent

Cross-file relationships and published refs that have a clean AP242 e3 mapping round-trip. Relationships, selector layers, or extensions that AP242 cannot represent are **preserved as AIADRA-native metadata with diagnostics or documented degradation**. Silent lossy export is forbidden; named lossy export is acceptable.

This is consistent with [ADR/0003 §6](ADR/0003-schema-governance.md)'s archival-mode discipline — lossy interop must be named and diagnostic, not silent.

#### 16. Domain Adapter graceful-degradation rule, with a release-time threshold

Domain Adapters must populate the strongest selector layers they can. The threshold is state-dependent:

- **In `in_work` / bulk-import states**, a selector with only `topology_ref_id` + `selector_predicate` (no usable `encoded_history`) is acceptable with `requires_validation` uncertainty. Bulk imports land before recipes are generated; engineers may publish anchors before defining them fully.
- **At release**, every release-bound geometric reference must have a resolver-capable selector — `encoded_history` strong enough to bind, or a deterministic alternative — or the release transaction **hard-fails validation**. A released named anchor that cannot actually resolve is not permitted.

Silent breakage is forbidden at any stage; partial information surfaces as `requires_validation` per [S1](#s1--provenance-and-uncertainty-granularity) in working states and as hard validation failure at release.

### E. Organizational patterns

#### 17. Skeleton model as a recognized organizational pattern

Not a new Object kind or relationship type — a documented topology where a "skeleton" or "master" Object owns parametric variables and high-level geometry, with downstream Objects pulling copies via `derived_geometry_from` (Fixed binding, typically) and referencing parameters via `parameter_expression`. **The published reference port mechanism (commitment 11) is the durable surface for skeleton-published geometry**, and the production rule for release-bound use applies.

The dependency graph rooted at the skeleton becomes a tree, not a mesh — matching Creo / NX / CATIA top-down practice. AIADRA does not enforce skeleton-model use; the spine accommodates it as a first-class pattern.

### Hidden couplings — pinned

- **S0 / S1 governance.** Published refs and relationship records are user-authored mutable records under [S0 commitment 4](#4-hybrid-within-artifact-addressing). Stable local ids; retirement via tombstone, never delete; S1 annotations with container defaults; address stability across schema migrations.
- **S2 snapshot boundary, including published refs.** Revision records capture **published refs and relationships** alongside payload — they're first-class addressable records on the Object, so they freeze with the released Revision per [S2 commitment 13](#13-revision-snapshot-boundary). The working sidecar can evolve its published refs independently for the next iteration; the prior Revision's published refs stay frozen.
- **S2 release materialization.** Float / Fixed resolution is snapshot-aware: Revision record stores resolved Fixed references; sidecar preserves authoring intent unless explicitly changed. Release transaction handles materialization atomically per [S2 commitment 11](#11-release-transactions-are-atomic-across-all-canonical-artifacts).
- **S2.5 Number identity.** Cross-Object endpoints reference Objects by UUID, never by Number, per [S0 commitment 6](#6-cross-object-references) + [S2.5 commitment 11](#11-objectnumber-is-governed-identity-metadata-not-provenance-bearing).

### OQ-0016 reopens

Per the [Architecture Overview](ArchitectureOverview.md)'s Ring 2 deferral note, [OQ-0016](OpenQuestions.md) (cross-project Object identity and reuse semantics) reopens before Ring 2's relationship taxonomy is enumerated. S3's relationship model is compatible with all four OQ-0016 options (project-scoped no-link / project-scoped + `derived_from` / global UUID + per-project revision binding / Catalog Objects as separate class) — the endpoint form's optional `project_scope` field accommodates additive resolution. Catalogue and Ring 2 work picks among A/B/C/D before relationship taxonomy enumeration completes.

### S3 eventability sketches

**Relationship created.**

```
relationship_created {
  target: { object_uuid, namespace: "relationship", id: "<local-id>" },
  type, binding: "float" | "fixed", arity,
  endpoint(s): [
    { project_scope?, object_uuid, revision_id?, fact_ref? }
  ],
  properties?, fact_provenance, fact_uncertainty?
}
```

**Relationship changed** (authoring intent change in sidecar).

```
relationship_changed {
  target, field, from, to,
  fact_provenance?, fact_uncertainty?
}
```

Emitted only when authoring intent changes — release-time Float→Fixed materialization is NOT a sidecar event (handled inside `revision_released`).

**AI-driven topological repair** (per commitment 14).

```
relationship_changed {
  target,
  field: "endpoint.fact_ref.encoded_history",   // and optionally .repair_hint
  from, to,
  fact_provenance: { category: "ai_proposal", ai_agent_ref }
  // topology_ref_id and selector_predicate UNCHANGED — validator enforces
}
```

**Semantic rebind** (heavier ceremony — not repair).

Either `relationship_retired` + `relationship_created`, or `relationship_changed` targeting the whole endpoint with required justification.

**Published ref events.**

```
published_ref_created {
  target: { object_uuid, namespace: "published_ref", id },
  name, kind,
  selector: { topology_ref_id, source_feature_id?, encoded_history, selector_predicate, repair_hint? },
  fact_provenance, fact_uncertainty?
}

published_ref_changed { target, field, from, to, fact_provenance?, fact_uncertainty? }

published_ref_retired { target, reason }
// Validator enforces: a published_ref cannot be retired while live release-bound relationships reference it.
```

**Release-time validation** (per commitments 12 and 16). The `revision_released` transaction additionally:
- Resolves every Float relationship against current target Revisions; materializes Fixed bindings in the Revision record.
- Validates every release-bound geometric reference for resolver-capability; hard-fails the release if any reference would freeze unresolvable.
- Validates every release-bound cross-Object geometric reference targets a `published_ref` or carries an explicit type-declared exception with diagnostics.

## A worked example

A small illustrative Part sidecar (concrete schemas TBD during catalogue work; this only shows the address structure that commitments 1–8 establish):

```yaml
object:
  uuid: "0193abcd-1234-7890-..."
  type: "Part"
  number: "P-000123"
  lifecycle: "in_work"
  schema_version: "0.1.0"

parameters:
  - id: "param_plate_thickness"
    name: "plate_thickness_mm"
    value: 6.0
    unit: "mm"

  - id: "param_mass"
    name: "mass_g"
    value: 47.3
    unit: "g"

relationships:
  - id: "rel_satisfies_req14"
    kind: "satisfies"
    target_object_uuid: "0193ffff-5678-..."
```

Addresses produced by this sidecar:

- `object.uuid`, `object.type`, `object.lifecycle` — schema-defined envelope fields (commitment 4, semantic form).
- `parameter:param_plate_thickness` — user-authored record at its stable local id (commitment 4, record form).
- `parameter:param_plate_thickness.value` — a field within that record.
- `parameter:param_mass` — second parameter record, addressed independently of the first.
- `relationship:rel_satisfies_req14` — user-authored relationship record.
- Cross-Object reference embedded in `rel_satisfies_req14`: `(implicit-local, "0193ffff-5678-...", null)` per commitment 6.

If `plate_thickness_mm` is later renamed to `mat_thickness_mm`, only `parameter:param_plate_thickness.name` changes; the address `parameter:param_plate_thickness` is unchanged, and every event ever targeting it remains valid.

## Spine complete — catalogue work opens next

With S0, S1, S2, S2.5, and S3 all pinned, the Ring 1 abstract Truth Model Schema spine is complete. The foundation now in place:

- **Addresses and envelopes** (S0) — every fact has a stable address; every Object has a wrapped envelope with universal identity fields; events are immutable; cross-Object references are UUID-keyed.
- **Provenance and uncertainty** (S1) — every fact carries effective provenance + uncertainty via a deterministic four-level resolver walk; fact-vs-event provenance kept distinct; release semantics out of scope for provenance.
- **Release and Revision** (S2) — Revision records as separate immutable schema-governed artifacts; sidecar stays current working state; Object lifecycle monotonic forward with iteration in the working frame; Revision snapshot boundary explicit.
- **Number-binding lifecycle** (S2.5) — Number required at creation; allocated via Reservation file; stable after merge; retired-alias semantics for `number_rebound`; Number is identity metadata, not provenance-bearing.
- **Relationships** (S3) — first-class addressable records; three kinds explicitly recognized (engineering-graph, geometric, parametric); published reference ports as required interfaces for release-bound cross-Object geometry; Float / Fixed binding explicit; per-type cycle policy; AI repair as Layer 3 obligation; AP242 round-trip and Domain Adapter graceful-degradation pinned.

**Catalogue work opens next.** Per [ADR/0003](ADR/0003-schema-governance.md) and the [Architecture Overview](ArchitectureOverview.md):

1. **Promotion rule** — **pinned 2026-05-18**, see the [Promotion rule for first-class Object Types](#promotion-rule-for-first-class-object-types) section below. Twelve commitments establish the criterion for first-class Object Type promotion, the two non-disqualifier patterns (Attachment-bearing Object, External pointer Object), and the four-tier deprecation ceremony.
2. **Seed Object Type catalogue** — Part, Requirement, Assembly first per ADR/0003's named examples.
3. **Concrete relationship types** — first wave of `satisfy`, `composed_of`, `derived_from`, `mated_to`, `derived_geometry_from`, `parameter_expression` schemas drawing on S3's type-schema framework.
4. **First Revision schema and Manifest schema concrete content** — drawing on S2 commitment 1's artifact-kind framework.
5. **[OQ-0016](OpenQuestions.md) reopened** — cross-project Object identity, before relationship taxonomy completes (per S3 and [ArchitectureOverview.md](ArchitectureOverview.md)).
6. **Per-type Reservation file shape and [OQ-0015](OpenQuestions.md) / ADR/0004** — closes out S2.5's downstream constraints.

## Promotion rule for first-class Object Types

The spine settles the abstract shape every Object shares. It does not settle which entities become first-class Object Types in the first place. Catalogue work answers that question per-Type, and the Promotion Rule is the criterion each catalogue decision follows.

Same authority status as the rest of this document — stale when overridden by ADRs or the Manifesto. Twelve commitments, pinned 2026-05-18. Full reasoning trail in the discussion folder.

### Pinned core

> A first-class Object Type is justified only when the entity needs AIADRA-owned UUID identity, lifecycle, referenceability, and approval / provenance independent of any parent Object, and when no existing artifact kind — record, event, Revision, Manifest, Vault blob, external workflow reference, or derived projection — already carries the semantics.

C1–C4 unpack the affirmative criteria. D1–D7 enumerate the existing artifact kinds and the rule for each. Commitment 5 names the two non-disqualifier patterns for Objects whose payload or upstream truth lives outside the sidecar.

### 1. Default is record; promotion is the exception

The compositional schema ([S0 commitment 1](#1-compositional-schema-governance)) and the namespace + local-id record model ([S0 commitment 4](#4-hybrid-within-artifact-addressing)) handle the common case. Promotion to first-class Object Type is justified explicitly per the criteria below, not by default.

### 2. Capability test — four affirmative criteria

An entity is a candidate for first-class Object Type only if all four hold:

- **C1 — Independent identity.** Identity meaningful outside any one parent context. A Part `P-000123` is the same Part regardless of which Assembly contains it. A parameter `param_plate_thickness` is meaningful only inside its Part.
- **C2 — Independent lifecycle.** Progresses through `in_work → under_review → released → superseded → obsolete` on its own cadence, not derivatively from a parent. For External pointer Objects (commitment 5), the lifecycle may be a binding lifecycle rather than a wrapper lifecycle — both satisfy C2.
- **C3 — Independent referenceability.** Referenced by UUID, not through a parent. If every reference targets it as "the Nth record of parent X," it is a record.
- **C4 — Independent provenance / approval.** Commit-time approval distinct from any parent's.

### 3. Disqualifier test — seven negative criteria

A candidate that passes the capability test is still not promoted if any disqualifier holds:

- **D1 — Wholly contained.** Every fact about the entity is meaningful only inside one parent Object. Parameters, relationships, published refs, design-intent entries, test execution records, evidence citations, measurement records.
- **D2 — Append-only / transition-only.** Content is a record of a state change, not state itself. Events.
- **D3 — Frozen snapshot of another Object.** Bound to a parent Object UUID, immutable, governed by [S2 commitment 1](#1-revisions-are-separate-immutable-schema-governed-artifacts). Revisions.
- **D4 — Governance artifact, not engineering fact.** Records a release event or policy decision rather than an engineering property. Manifests.
- **D5 — Externally governed workflow artifact.** Lifecycle and approval live in an external workflow system; AIADRA only needs immutable references to its outcome. ECR / ECO and Git-host-side PR state. **Does not include** the AIADRA-owned attachment-bearing or external pointer Object patterns (commitment 5).
- **D6 — Opaque bytes.** Engineering meaning is just "this hash." Vault blobs *standing alone*. An Object Type that owns a Vault attachment as part of its payload is not D6-disqualified — see the Attachment-bearing Object pattern in commitment 5.
- **D7 — Derived projection / cache / view.** Deterministically generated from canonical Objects, Revisions, Events, Manifests, or Vault hashes. Stored as derived cache, export, report, or manifest content; not promoted as authored Object Type. BOMs, where-used reports, release dashboards, validation summaries, trace matrices, impact-analysis reports, generated exports. **Partially-derived test:** a partially-derived artifact is not D7-disqualified only when its authored layer contains canonical facts that cannot be deterministically reconstructed from existing Truth Model state, AND that authored layer independently passes C1–C4. A Drawing's authored annotations / dimensions / design-intent text tip it out of D7; a generated STEP export does not; an annotated simulation packet is a candidate only if its annotation layer itself passes C1–C4.

### 4. Both tests must pass

Capability all-affirmative AND disqualifiers all-negative. A candidate failing either is not promoted; the spine has a non-Object-Type kind for it.

### 5. Two named non-disqualifier patterns

When an Object's content, payload, or upstream truth lives partly outside the sidecar, the rule recognizes two patterns. Both are explicit non-disqualifiers under D5 and D6; both require AIADRA-owned UUID identity, relationship endpoint surface, and approval boundary on the local Object. They differ in authority direction.

**Attachment-bearing Object.** AIADRA owns the engineering meaning; Vault holds byte payloads subordinate to that meaning. The Object owns its own (wrapper) lifecycle, fully. Examples: an EvidenceArtifact with a simulation output; a Drawing with a rendered PDF; future annotated-simulation candidates whose annotation layer is canonical. The bytes are subordinate to AIADRA truth.

**External pointer Object.** Another system owns some upstream truth (a supplier datasheet, an external Git repo, a catalog project's Object); AIADRA owns the local wrapper or binding. The wrapper-vs-binding distinction is load-bearing:

- *Wrapper lifecycle* — AIADRA owns the lifecycle of the represented thing locally. Example: a Supplier Object whose existence and lifecycle are project-local even though the underlying real-world supplier is external. The pointer Object passes C2 with an independent lifecycle.
- *Binding lifecycle* — AIADRA owns the lifecycle of the project's adoption of an upstream entity. Example: "we pinned to upstream Component v1.2 in Q2; we superseded our binding to v1.4 in Q3." The upstream entity's lifecycle stays externally owned; the binding's lifecycle is AIADRA-local. This is what makes catalog-project / consumer-project patterns viable under [OQ-0016](OpenQuestions.md).

If neither wrapper lifecycle nor binding lifecycle exists, it is not an Object Type — it is just an external reference field or record on some other Object.

Per-Type ADRs using either pattern must explicitly state which pattern applies; for External pointer, whether the lifecycle is wrapper or binding; what AIADRA owns; and what AIADRA merely points at.

### 6. Promotion ceremony

Adding an Object Type to the catalogue requires:

- New `sidecar/<Type>.schema.json` in the active bundle, composed `BaseObject ⨁ TypeSpecific` per [S0 commitment 1](#1-compositional-schema-governance).
- Number prefix mapping declared at promotion per [S2.5 commitment 10](#10-number-format-and-type--prefix-mapping-are-per-project-policy).
- Optional Revision schema if the Type participates in formal release per [S2 commitment 1](#1-revisions-are-separate-immutable-schema-governed-artifacts).
- Relationship endpoint constraint table updates in every relationship type schema where the new Type is a valid endpoint per [S3 commitment 7](#7-relationship-types-are-schema-governed-under-adr0003).
- Bundle bump per [ADR/0003 §11](ADR/0003-schema-governance.md): MAJOR if the promotion breaks existing endpoint constraints or tightens validation; MINOR if purely additive.
- For Types using commitment 5 patterns: an explicit "what AIADRA owns vs what it points at" section in the per-Type ADR, naming the pattern (Attachment-bearing vs External pointer) and, for External pointer, the lifecycle kind (wrapper vs binding).

**Governance ceremony is decoupled from bundle bump class** per [commitment 12](#12-rule-evolution-is-governance-tier-decoupled-from-schema-bundle-bumps). Bundle bump class is determined by [ADR/0003](ADR/0003-schema-governance.md); governance ceremony is determined by whether the promotion carries load-bearing architectural decisions.

- **ADR required.** Promotions that introduce or change a reusable modeling pattern, namespace shape, lifecycle semantics, reference form, adapter contract, relationship ownership rule, release / revision behavior, or any other convention expected to constrain later Type ADRs. The first concrete Object Type and any Type that sets a new catalogue pattern require an ADR.
- **Schema Change Note sufficient.** Promotions that add a Type following established patterns already documented in this document or accepted per-Type ADRs, with no novel architectural commitments.
- **Tie-breaker.** When in doubt, prefer ADR. Schema Change Note is the lighter path for clearly additive, follow-the-template Type additions.

### 7. Demotion is deprecation-first, four-tier ceremony

A promoted Type that proves unnecessary follows this path:

- Historical artifacts of the Type remain readable forever under their declared bundle, per [ADR/0003 §6](ADR/0003-schema-governance.md) archival mode.
- The Type may be marked deprecated under one of four enforcement levels, each with a distinct bump class:
  - **Documentation-only deprecation** ("discouraged; do not use for new designs") — PATCH or docs-only bump. No schema or validator change.
  - **Schema-annotation deprecation, warning only** — MINOR bump. Schema carries a `deprecated: true` annotation; validator emits diagnostic on read or write; no hard rejection.
  - **Hard-refusal of new authoring** — MAJOR bump. Validator rejects new instances at write time. Read path / archival mode preserves access to existing data. This is a validation-rule tightening per [ADR/0003 §11](ADR/0003-schema-governance.md)'s MAJOR criteria — even though no existing artifact fails, the *authoring path* tightens, and standard schema-SemVer treats that as a breaking change.
  - **Historical migration of instances to records** — MAJOR bump with migrators per [ADR/0003 §5](ADR/0003-schema-governance.md). Allowed only when every instance has a unique containment owner AND every UUID reference to instances has a deterministic replacement address. Otherwise the deprecated Type remains archival and read-only, never forcibly demoted.
- Events targeting deprecated-Type UUID-keyed addresses must continue to resolve under their declared bundle per [S0 commitment 5](#5-events-are-immutable-address-resolution-is-read-side).

The four-tier ladder lets us deprecate without forcing migration, while pricing each enforcement level honestly.

### 8. Seed catalogue is grandfathered

Part, Requirement, Assembly are taken as passing the test by precedent (per [ADR/0003](ADR/0003-schema-governance.md) named examples). Each Type's ADR cites which criteria (C1–C4) justify the promotion so the rule lands in the corpus by example, not just by definition.

### 9. Catalogue work is use-case driven

Promotion requires near-term Wedge or current-catalogue need, not Glossary listing. Speculative promotion bloats the schema bundle and pre-commits relationship endpoint constraints without need. The candidate pool (commitment 10) holds plausible future Types in deferred status.

### 10. The Glossary's list is candidates, not commitments

The [Glossary](Glossary.md) *Object (Managed Object)* entry carries the catalogue's current verdicts: seed, Tier-2 promoted, candidate pool deferred, and spine-kind dispositions for non-Objects. The Glossary updates as the catalogue evolves.

### 11. The rule is itself stale-when-overridden

Same authority status as the rest of this document. Disagreement hierarchy: ADRs > Manifesto > ArchitectureOverview ≈ TruthModelSchema > ArchitectureGraph.

### 12. Rule evolution is governance-tier, decoupled from schema bundle bumps

Amendments to the rule are TruthModelSchema-tier governance: recorded as TruthModelSchema version bumps. A rule amendment triggers schema-bundle ceremony per [ADR/0003 §11](ADR/0003-schema-governance.md) **only when the amendment changes concrete schemas, endpoint constraints, or per-Type verdicts.** Adding a disqualifier that does not retro-disqualify any existing Type is a documentation change. Changing the four capability criteria, or retro-disqualifying an existing promoted Type, requires schema-side changes and therefore a bundle bump under the normal ceremony.

This keeps governance ceremony (TruthModelSchema version, per-Type ADRs) and schema ceremony (bundle bumps) decoupled, consistent with how they are decoupled elsewhere in [ADR/0003 §11](ADR/0003-schema-governance.md).

### Verdict summary

The Promotion Rule applied to the [Glossary](Glossary.md)'s candidate pool gives the following catalogue.

**Seed Object Types** (pinned by [ADR/0003 §1 / §2](ADR/0003-schema-governance.md) named examples):

- **Part**, **Requirement**, **Assembly** — per-Type ADRs follow.

**Tier-2 Object Types** (cleared the rule; per-Type ADRs follow as the Wedge surfaces need):

- **Drawing** — Attachment-bearing Object pattern (Vault holds rendered PDF; authored annotations / dimensions / design-intent are canonical and tip Drawing out of D7's partially-derived disqualifier).
- **TestProcedure** (a.k.a. DV Procedure) — reusable across Objects, independently approved, traceable to Requirements.
- **EvidenceArtifact** — Attachment-bearing Object pattern (Vault holds simulation outputs, reports); citeable by multiple Tests, Requirements, Releases.

**Candidate pool, deferred** (pass capability test plausibly; deferred until concrete use case or [OQ-0016](OpenQuestions.md) reopening):

- **Supplier** — likely External pointer Object (Wrapper lifecycle).
- **Component** (purchased item) — likely External pointer Object (Wrapper or Binding lifecycle depending on sourcing). Sourcing discriminator on Part is enough for the Wedge era; split fires when endpoint constraints, lifecycle, Revision semantics, or required fields diverge, or when OQ-0016 chooses a cross-project identity model that forces the split.
- **Software module** — likely External pointer Object (Binding lifecycle pinning project to upstream Git source's version).
- **Electrical component** — may collapse into Part as specialization per [OQ-0006](OpenQuestions.md) sequencing.

**Recognized non-Objects** (handled by other spine artifact kinds):

- **Release** — Release Manifest + release transaction + events. Optional derived Release index for query ergonomics. Reopenable only if Release must participate in relationships as a revisioned engineering Object, with the recursion rule defined first.
- **ECR / ECO** — externally governed workflow artifact in the Git host; referenced via PR URL / commit hash in events (D5).
- **AI Decision** — event payload (proposal carries AI provenance; Transaction record carries approval). Recognized candidate explicitly rejected under current rule; reopenable through [OQ-0003](OpenQuestions.md) failed-transaction audit-log work (D2).
- **Feature** (CAD construction-history: sketch, extrusion, fillet) — `feature:` namespace records under parent Part (D1).
- **Test execution / result / Evidence citation / measurement** — records under parent Test or Evidence (D1).
- **BOM, where-used reports, dashboards, trace matrices, validation summaries, impact-analysis reports, generated exports** — derived views over Truth Model state (D7).

## References

- [Manifesto.md](Manifesto.md) — P3 (UUID identity), P4 (Design Intent first-class), P7 (provenance + uncertainty universal), P10 (event-based history, flat current state), P11 (AIADRA Core hosts nothing — bounds the External pointer Object pattern).
- [Glossary.md](Glossary.md) — *Object (Managed Object)* carries the Promotion Rule's current catalogue verdicts; plus *UUID*, *Number*, *Sidecar*, *Event*, *Sidecar/event invariant*, *Transaction*, *Provenance*, *Uncertainty Label*, *Lifecycle State*, *Revision*, *Iteration*, *AIADRA YAML Profile*.
- [ArchitectureOverview.md](ArchitectureOverview.md) — Layer 1 (Truth Model) and Layer 2 (Validation) framing; this document specifies Layer 1's abstract shape and catalogue criterion.
- [ADR/0001](ADR/0001-storage-substrate.md) — Storage substrate. Provides the sidecar/event/manifest substrate this document's address model runs on top of.
- [ADR/0002](ADR/0002-canonical-format.md) — Canonical format. AIADRA YAML Profile; mandatory `schema_version`; deterministic JSON for manifests.
- [ADR/0003](ADR/0003-schema-governance.md) — Schema governance. Bundle structure, `(bundle_version, artifact_kind, discriminator) → schema` lookup, three-way migration asymmetry, active/archival modes. Several spine commitments and the Promotion Rule's ceremony rules thread directly through ADR/0003 — §2 (discriminator), §5 (event immutability and sidecar migration), §6 (archival mode), §7 (validator behavior taxonomy), §11 (governance ceremony, PATCH/MINOR/MAJOR bump rules).
- [OpenQuestions.md](OpenQuestions.md) — OQ-0003 (failed-transaction audit-log scope; AI Decision reopen channel under the Promotion Rule), OQ-0006 (multi-tool sequencing; affects Electrical component candidate verdict), OQ-0015 (Reservation file shape, downstream of S2.5), OQ-0016 (cross-project Object identity, downstream of S3 and the Promotion Rule's External pointer Object pattern).
- Discussion trail (git-ignored, local only): `Docs/Discussions/20260518-1/` (Ring 1 spine S0–S3 close, paired Claude / Codex files), `Docs/Discussions/20260518-2/` (Promotion Rule close: Claude1 / Codex1 / Claude2 / Codex2 / Claude3) — full working-out for Ring 1 spine + catalogue rule.
