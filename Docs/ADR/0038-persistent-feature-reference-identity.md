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

## References
- [ADR/0035](0035-display-representation-contract-and-topology-identity.md) — read-only Display Representation identity (the read-side sibling); D2 the role grammar reused here; D3 the value-independent `topology_signature`; D5 no-placeholder/fail-loud.
- [ADR/0036](0036-view-dependent-hlr-contract-v1-1.md) — the single-extractor invariant (Codex1 B1) D6 preserves.
- [ADR/0037 D8](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md) — the feature-taxonomy roadmap; this ADR is the reference-identity spine its referencing features inherit.
- [ADR/0031](0031-aiadra-mechanical-scope.md) — recipe-hash identity; the engine-opaque `adapter_payload`.
- Arc `Docs/Discussions/20260621/20260621-2/` — Claude1 (design + spike) / Codex1 (converge + B1 + Q1–Q4) / Claude2 (this ADR + build); direction arc `20260621-1/`.
