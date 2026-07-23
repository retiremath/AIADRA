# ADR/0038 — Persistent feature-reference identity

## Frontmatter

- **Status:** **Accepted** — 2026-06-21 (arc 20260621-2; design-first, two-round convergence: Claude1 design + spike → Codex1 converge with one blocker (land this ADR before production code) + Q1–Q4 answers → Claude2 ADR + build. Direction set by the closed direction arc 20260621-1.)
- **What it is:** the **write-side sibling to [ADR/0035](0035-display-representation-contract-and-topology-identity.md)**. ADR/0035 pins *read-only Display Representation* topology identity; this ADR pins how a **feature persistently references existing topology in Product Truth** — the first such reference being the fillet's target edge ([arc 20260621-2](../Discussions/20260621/20260621-2/Claude1.md)), but the rule is **pattern-setting** for every future referencing feature: holes-on-faces, datum references, patterns, and the eventual general parent/child regeneration semantics ([ADR/0037 D8](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md)).
- **Why an ADR and not engine comments (Codex1 B1):** this is the first Product-Truth topology reference. It will be copied across the feature taxonomy. It must be a durable canonical decision artifact with full authority, not a convention buried in `Claude1.md` + code comments. It is the *write-side* boundary, so it is its own ADR rather than an ADR/0035 addendum (ADR/0035 is explicitly the read DTO).
- **Version impact:** no `aiadra-core`/bundle/schema/Glossary/Manifesto change — the reference lives inside the engine-opaque `feature.adapter_payload` (`aiadra-core` only checks it IS an object, per [ADR/0029 D7](0029-part-authoring-scn.md)). `aiadra-mechanical` `adapter_schema_version` 0.1.1 → 0.1.2 (the first referencing feature realizes this ADR in the same arc).

## §0 — Context

AIADRA models a Part as a feature recipe ([ADR/0031 D6](0031-aiadra-mechanical-scope.md) recipe-hash identity). Until now every feature was *self-contained* (a sketch carries its primitives; an extrude names a sketch feature **id**, which is a recipe id, not a topology reference). The fillet is the first feature that references a piece of **derived topology** — an *edge produced by evaluating a prior feature* — and must keep referencing it as the recipe regenerates. ADR/0035 already gives derived topology a recipe-anchored identity for *display*; the open question this ADR closes is what a *committed feature* may persist to name that topology, and how it resolves across regeneration. The wrong answer (persisting the read-only display id, an OCCT handle, or a traversal index) would either couple Product Truth to a read DTO or make identity non-deterministic.

## Decisions

### D1. Display IDs are selection/input vocabulary — never persisted authority
A feature operation MAY accept a Display Representation `edge_id`/`face_id` ([ADR/0035](0035-display-representation-contract-and-topology-identity.md)) as an **input selector** (it is how a UI pick or a golden recipe says *which* entity). The handler MUST resolve that selector against a **fresh engine extraction** and persist the structured reference derived from *that* extraction. The display id string is **never parsed-and-trusted into Product Truth**. (Display data is a read-only projection of recipe identity; it is not Truth — [ADR/0035 D1/§0](0035-display-representation-contract-and-topology-identity.md).)

### D2. Persisted references are engine-owned, recipe-anchored adapter-payload records
A persisted topology reference lives in the referencing `feature.adapter_payload` and is expressed in **recipe-anchored role vocabulary** — the same `<feature>[/<primitive>]:<kind>:<role>` grammar ADR/0035 D2 derives, owned by the engine. It carries enough to re-resolve deterministically and to detect staleness. For an **edge reference** (the v1 shape):
- `adjacent_face_roles` — the sorted pair of recipe-anchored face roles whose intersection IS the edge (this is exactly what `topology._edge_id` is computed from);
- `edge_kind` — `sharp | tangent | seam | boundary | free`;
- `resolved_against_topology_signature` — the **parent-prefix** topology signature (D4) the reference was resolved against, as staleness evidence.

**Forbidden as persisted identity:** raw OCCT subshape handles, `face_map`/traversal indices, mesh ranges, the Display Representation id string, and any placeholder/minted-on-miss identity. (Mirrors ADR/0035 D2/D5's "no placeholder anchors — fail loud".)

### D3. References resolve against the parent-prefix recipe skeleton, with exactly-one resolution required before kernel mutation
A reference names topology of its **parent sub-recipe** — the solid built from the recipe features *before* the referencing feature. Resolution:
1. Evaluate the recipe **prefix up to (not including)** the referencing feature; extract its topology (recipe-first, the single ADR/0035/0036 extractor).
2. Match the stored reference (e.g. `adjacent_face_roles` + `edge_kind`) to **exactly one** topology entity.
3. The kernel mutation (e.g. the fillet) is applied on **that same evaluated solid instance** — an edge handle from a different instance is not a valid OCCT fillet input (proven in the arc spike).

**Exactly-one is mandatory before any kernel mutation.** Zero matches, more than one match, or a parent-prefix signature mismatch is a failure (D4), never a guess.

### D4. Survival vs. failure is decided by the parent-prefix topology signature — fail loud, no heuristics
The reference **survives** a parent **parameter** edit (a dimension/value change) because such an edit preserves the topology skeleton: `compute_topology_signature(prefix)` is unchanged ([ADR/0035 D3](0035-display-representation-contract-and-topology-identity.md), value-independent), so the recipe-anchored roles still resolve. The reference **fails loud, before commit**, on any of:
- parent-prefix topology-skeleton change (`compute_topology_signature(prefix)` ≠ the stored `resolved_against_topology_signature`);
- the role pair resolving to **zero** entities (missing role / removed geometry);
- the role pair resolving to **more than one** entity (ambiguous);
- a **removed or missing parent** feature.

The failure is a Class-1 domain `TransactionError` naming the unresolved reference and the repair path (re-pick the entity / restore the parent). **No nearest-geometry reattachment, no traversal-order fallback, no "same-looking entity" guess.** Deterministic-first; reattachment/repair UX is a deferred future concern, not a v1 behavior. *(This is intentionally stricter than a human CAD system's best-effort reattach — the correct seed behavior for a deterministic-truth platform.)*

### D5. Reference-bearing features declare dependency + cascade behavior
A referencing feature records its parent via `depends_on_feature_ids` (already the extrude→sketch pattern). Removing/altering a parent while a dependent reference exists must **cascade-reject** (or require explicit removal/repair of the dependent first) — never silently orphan a reference. The dependent-guard is part of every reference-bearing feature's contract.

### D6. By-construction role assignment for produced topology (Codex1 Q1)
When a feature *produces* new topology (the fillet's blend face + tangent edges), the role is assigned **by construction**: the sequential evaluator emits **role/provenance hints** for the topology it created, and the single topology extractor consumes those hints **as recipe authority** — it does not re-guess from surface geometry. Post-hoc geometric inspection is permitted **only as a strict assertion/check** on the hinted result, never as the authority source. This preserves ADR/0035's recipe-first principle (geometry maps roles to shapes; geometry does not invent roles) and the single-extractor invariant ([ADR/0036 Codex1 B1](0036-view-dependent-hlr-contract-v1-1.md)) — no second parallel id-derivation path.

## Consequences
- Every future referencing feature (hole-on-face, pattern seed, datum-on-face, the regeneration endgame) inherits D1–D6: recipe-anchored persisted reference, parent-prefix resolution, fail-loud staleness, dependency/cascade, by-construction produced-topology roles.
- The Truth/display authority boundary is explicit and durable: ADR/0035 owns the read projection; ADR/0038 owns the write-side reference. The display id never becomes Truth.
- AIADRA's regeneration semantics begin **deterministic and strict** — parameter edits survive, topology edits demand explicit repair — with reattachment UX deferred to a future arc, not retrofitted into the identity rule.
- The general persistent-naming problem ([ADR/0035 D5](0035-display-representation-contract-and-topology-identity.md) deferral) is now being met incrementally, smallest-scale-first, exactly as [ADR/0037 D8](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md) intended — not pinned in one upfront vision.

## Alternatives rejected
- **Persist the Display Representation `edge_id` string as the reference** — couples Product Truth to a read-only DTO; rejected (D1), the load-bearing correction from arc 20260621-1.
- **Persist an OCCT handle / traversal index / mesh range** — non-deterministic across regeneration and kernel/process boundaries; rejected (D2), consistent with ADR/0035 D5.
- **Best-effort geometric reattachment on a topology change** — non-deterministic; contradicts Manifesto P5 reject-loudly; rejected (D4). Repair UX is a future, explicit, human-or-agent-approved step.
- **Fold the rule into ADR/0035** — blurs the read/write authority boundary this ADR exists to make explicit; rejected (frontmatter; Codex1 Q2).
- **Per-parent-subtree signature granularity now** — speculative for a linear v1 recipe; parent-prefix is sufficient and matches the same-instance evaluation requirement (Codex1 Q4). Revisit when references target nested/generated entities or features can be reordered.

## Amendment — arc 20260622-2 (hole-as-feature: the first FACE reference)

The second referencing feature (hole-as-feature, [ADR/0037 D8](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md)) generalizes this ADR beyond its first (edge-reference) shape. Three additions, kept at the **invariant level** — not hole-specific (Codex 20260622-1 Q2; 20260622-2 Codex1):

### A1. `target_face` reference shape (extends D2)
A persisted reference may name a **face** as well as an edge. A `target_face` carries a recipe-anchored **face role** (the ADR/0035 D2 `<feature>[/<primitive>]:face:<role>` grammar) + the parent-prefix `resolved_against_topology_signature`. The same discipline as `target_edge` applies verbatim: the display `face_id` is **input vocabulary only** (D1); resolve against the parent-prefix skeleton **exactly-one-or-fail** before any kernel mutation (D3); skeleton-change / missing / ambiguous / removed-parent **fail loud** (D4). The reference shape itself stores **only** the role + signature; surface-kind constraints (e.g. a v1 "cap-only" guard) are **operation-scope** guards at the handler, not part of the general reference shape (Codex1 N1) — mirroring the fillet's sharp-only guard.

### A2. Produced-feature parameter values are NOT topology skeleton (sharpens D3/D4; Codex1 B1)
A referencing feature's **value parameters** (a hole's `diameter_mm` / `center_x_mm` / `center_y_mm`, a fillet's `radius_mm`) are **excluded from `topology_signature`** — exactly like a sketch circle's position/radius or an extrude's depth. Only the **feature type + the reference's role(s)** are skeleton. Consequences:
- Moving/resizing a hole **within the same target face** (no breach/collision — a Class-1 domain check enforces that) is a *parameter edit*: generated roles stay stable, the recipe hash / `vault_ref` changes. A downstream feature referencing the hole wall does **not** go stale because the diameter changed.
- **Retargeting** (changing `target_face` / `target_edge` to a different entity) **is** a skeleton change.

### A3. Produced-topology roles are a MANDATORY by-construction claim (sharpens D6; Codex1 B2)
D6 ("produced roles by construction, fail loud on a missed hint") is made an explicit, mandatory claim invariant — not merely a downstream geometric guard (which only happened to catch the fillet's *cylindrical* blend; a *planar* produced face could fall through as a cap/wall). The evaluator emits a generic produced-face hint `(feature_id, role_base, faces)` for every produced role it intends to claim, and the single topology extractor enforces:
- a produced role with **zero** faces → **fail loud**;
- a hinted face **not found** in the final `face_map` → **fail loud** (never silently skipped);
- multi-face roles get a **deterministic** `#k` suffix from a stable final-shape ordering (sorted `face_map` index), **not** raw `Modified()`/`Generated()` iteration order;
- geometry may **verify** a claimed face's surface kind but may **never invent or substitute** the role.
Produced roles are **feature-kind-owned** recipe roles — `feat_N:face:hole_wall`, `feat_N:face:blend`, … — a vocabulary, not always `:face:blend`. The fillet's `BlendHint` generalizes to this `ProducedFaceHint`; its by-construction source generalizes from `BRepFilletAPI_MakeFillet.Generated(edge)` to any operation's produced faces (a boolean cut's wall via `BRepAlgoAPI_Cut.Modified(cutter_lateral)`).

*(Version impact of the amendment: `aiadra-mechanical` `adapter_schema_version` 0.1.2 → 0.1.3. No `aiadra-core`/bundle/schema/Glossary change.)*

## Amendment — arc 20260717-2 (sequential extrudes: the first recipe with more than one body mutation)

Sequential add/cut extrudes ([ADR/0037 D8](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md)) make a Part hold **more than one body-producing/mutating feature**. That breaks two assumptions A1–A3 could hold while the recipe had exactly one base: (a) that a produced role can be looked up in **one final** `face_map` (A3), and (b) that "parent prefix" and body order can come from **sidecar array position**. Both silently become identity-bearing the moment a second body feature exists. A4 generalizes the reference-identity spine to an ordered **body history**; A3 is its length-one special case. A4 governs any recipe whose body chain has length > 1 and reduces to A3's behavior at length 1. It is **mandatory before any boolean lands** (arc sub-slice `M-identity`).

### A4.1. The `FaceRoleLedger` is the fold-wide role authority (generalizes D6/A3)
Role identity is **recipe-owned**, carried across the whole fold by a live ledger, not recovered from the final shape. Ledger state at each step is `{body_head, shape, face_roles, body_recipe_ids}`. **Before every body mutation**: every face of the current body already carries **exactly one** canonical role, and every face of the freshly built tool solid receives its `feature[/primitive]:face:<role>` role **before** the boolean. A3's `ProducedFaceHint` looked up in one final `face_map` is replaced by ledger membership; A3's post-hoc geometric check survives only as a strict assertion (D6), never the authority.

### A4.2. OCCT boolean history is transport evidence, not role authority (sharpens A3)
`BRepAlgoAPI` `Modified()`/`Generated()`/`IsDeleted()` answer only "which result shapes descend from this operand shape". They do **not** decide AIADRA roles. Propagation is **complete and explicit**, per input face of each operand: use its `Modified()` faces when non-empty; else drop it iff `IsDeleted()`; else **retain** the unchanged face if it still occurs in the result. Every final face must end carrying **exactly one** canonical role or evaluation **fails loud** (Class-1). A legitimately deleted tool contact face is a valid outcome, not a lost role.

### A4.3. Deletion / split / merge / collision are distinct; v1 rejects ambiguity
A one input face → several result faces (**split**), several input faces → one same-domain result face (**merge**), and one result face reachable from **both** operands (**collision**) are different events. v1 rule: a result face claimed by two **distinct** canonical roles is **rejected** (never last-wins); ambiguous same-domain merges are **rejected**. No same-domain simplification (`SimplifyResult`) runs in v1 — it needs an ownership policy first.

### A4.4. Split identity is derived in the source role's canonical local frame (supersedes A3's `#k`)
A3's multi-face `#k` from **sorted final-`face_map` index** is too weak once booleans reorder the map. When one source role legitimately splits, child ordering is derived from **stable geometric discriminators in the source role's canonical local frame** (the frame the ledger already holds for that role), **fail-on-tie**, tolerance pinned scale-aware. General curved-split identity stays deferred; v1's bounded planar domain (A4.8) needs only this.

### A4.5. Every mid-fold reference resolver consumes the live ledger (closes the stacked-reference gap)
`resolve_face_on_shape`, `resolve_edge_on_shape`, and `face_frame.resolve_face_plane` resolve against the ledger **at the referenced feature's body-history position** — never against a final-shape correlator that reconstructs "the one original base". This is the fix for the named stacked-reference gap: a fillet/hole/chamfer/face-bound-sketch on a face **produced by a prior extrusion** resolves correctly, for all modifiers, not just the new extrude.

### A4.6. Body order is the feature dependency graph, not sidecar array position (Codex2; predecessor rule Codex3)
[ADR/0029 D9](0029-part-authoring-scn.md) makes `depends_on_feature_ids` the authoritative graph and disclaims canonical array order. A **body-mutating feature records the immediately-preceding body head** in `depends_on_feature_ids`, in addition to its direct operands: the base extrude depends on its sketch; a later extrude on its consumed sketch **and** the current body head; every fillet/chamfer/hole/future mutation advances from **exactly one** body head. A face-bound sketch records enough context to reconstruct the body state its support was resolved against (its producing feature for role ownership, **plus** the body head when that producer is not itself the head). "Parent prefix" (D3) is redefined as the referenced feature's **dependency-closed body history**, not "array elements before this index". **No new Core schema field** — `depends_on_feature_ids` carries the chain; a duplicate engine-only head field would create a second authority requiring a forever-equality rule.

**The predecessor-extraction rule (Codex3 — executable, no second field).** The body predecessor of a non-base mutation is derived from the graph: among its **direct body-mutating dependencies**, the **unique dependency maximal under graph reachability** is the immediately-preceding body head; every other direct body-mutating dependency (e.g. a referenced role owner) must be an **ancestor of that head**. Zero or multiple **incomparable** maxima → **Class-1**. The base mutation has no prior body head and exactly one consumed base-profile root. The evaluator derives the fold from this rule and rejects **missing / cyclic / incomparable-head** branches in the v1 single-body model; raw sidecar order is serialization convenience only and is never a semantic tie-break.

### A4.7. The active body geometry artifact projects the body head's dependency closure (Codex2; normalization pinned Codex3; sharpens ADR/0030 + ADR/0031)
There is **one** active body-producing `authoring_geometry` record. It stages the **canonical ordered projection of the body head's dependency closure** (base sketch + base feature, consumed later sketches, every body mutation) — **not** `_stage_recipe(sidecar["feature"])` over the whole Part.

**The graph-to-bytes normalization (Codex3 — the algorithm, not just the property).** The projection is produced by ONE pinned rule so that any two evaluators derive byte-identical recipes from the same closure:
1. **Ordering**: a Kahn topological sort of the body head's dependency closure with **stable feature-id ordering among simultaneously-ready vertices**. Body-chain edges force mutations into fold order; operand edges force sketches/reference inputs before their consumers; the stable-id tie-break makes any remaining concurrency byte-deterministic. Sidecar array position never participates — an implementation that merely filters the sidecar array in place does NOT satisfy this rule.
2. **Dependency bytes**: normalized `depends_on_feature_ids` **participates in the canonical recipe bytes**, serialized per feature as a **sorted stable-id list**. Rationale: A4.6 makes those edges geometry-order authority — two closures with identical payloads but different body chains are different models and MUST hash differently; the serializer's previous silent omission of the edges is superseded. (`fact_provenance` and `adapter_schema_version` stay excluded as before.)
3. **One projection object**: `body_recipe_ids`, `derived_from_feature_ids`, and `fact_provenance.derived_from` are all derived **from the same ordered projection object** — never from parallel traversals that could disagree.

Consequences, all enforced/tested:
- `derived_from_feature_ids` and `fact_provenance.derived_from` equal **exactly** the body projection's feature-id set; the bytes at `vault_ref` encode that same projection; unrelated unconsumed sketch roots appear in **neither**.
- Consuming a sketch **removes** its former sketch-only geometry record via `geometry_ref_delta.removed` (there is no "retire" lifecycle state). An unconsumed sketch keeps its own subtree record.
- With a body present, display / HLR / cache resolve the **unique body record by the body head/closure**, never by first-list position; the no-body branch keeps its existing live sketch-recipe identity.
- The cache must **stop asserting** unconditional equality between a whole-Part feature-list hash and the body `geometry_ref` ([cache.py](../../aiadra-mechanical/src/aiadra_mechanical/cache.py) doc) once it mixes independent sketch/display state: key solid evaluation from the body projection and sketch-frame/overlay derivation separately, or make the combined display-cache key an explicit **composition** — never a preserved false equality.
- Parameter adjustment and feature removal find the affected output by **dependency closure**; the existing modifier handlers' "find the geometry containing the base extrude" convention converges on the **same body-authority helper**.

### A4.8. The within-face v1 acceptance domain (bounded by construction AND by history)
v1 accepts a sequential add/cut whose tool footprint lies **strictly interior** to a single planar face of the current body (the support face) — by one pinned scale-aware clearance, **no** footprint point/edge coincident with the support boundary; a blind pocket's terminal cap also stays inside material for the first cut slice. Eligibility is **not** granted by the geometric precheck alone: the **post-boolean history must prove** the support maps exactly one-to-one, the expected tool contact face deletes, every intended tool wall/cap survives under one role, no other owned face splits/merges/collides, and the result is **one** valid non-empty solid (`add` increases material; `cut` removes it; scale-aware volume + solid-count checks). Otherwise **fail loud (Class-1)**. Faces that would split/merge owned roles or straddle an edge are deferred to a later slice.

*(Version impact of the amendment: `aiadra-mechanical` `adapter_schema_version` 0.1.10 → 0.1.11 — extrude gains a structural `operation: add|cut` (absent legacy = `add`; add/cut differ in the topology skeleton), and the canonical recipe serializer gains per-feature sorted `depends_on_feature_ids` (A4.7.2) — an identity-affecting serializer change carried by the same version bump: existing stored `vault_ref`s stay valid content addresses of their staged bytes; the next write of any Part re-stages under the new rule and legitimately produces a new ref. No `aiadra-core` / Display-contract / bundle / schema / Glossary change: v1 keeps exactly one canonical `face_id` per result face — no multi-role alias lane, so [Display v1.2](0036-view-dependent-hlr-contract-v1-1.md) is sufficient.)*

## References
- [ADR/0035](0035-display-representation-contract-and-topology-identity.md) — read-only Display Representation identity (the read-side sibling); D2 the role grammar reused here; D3 the value-independent `topology_signature`; D5 no-placeholder/fail-loud.
- [ADR/0036](0036-view-dependent-hlr-contract-v1-1.md) — the single-extractor invariant (Codex1 B1) D6 preserves.
- [ADR/0037 D8](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md) — the feature-taxonomy roadmap; this ADR is the reference-identity spine its referencing features inherit.
- [ADR/0031](0031-aiadra-mechanical-scope.md) — recipe-hash identity; the engine-opaque `adapter_payload`.
- Arc `Docs/Discussions/20260621/20260621-2/` — Claude1 (design + spike) / Codex1 (converge + B1 + Q1–Q4) / Claude2 (this ADR + build); direction arc `20260621-1/`.
- Arc `Docs/Discussions/20260622/20260622-2/` — the hole-as-feature build that lands the A1–A3 amendment; direction arc `20260622-1/`.
