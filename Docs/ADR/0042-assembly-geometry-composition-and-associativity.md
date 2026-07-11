# ADR/0042 — Assembly Geometry Composition & Associativity (v1: positioned composition)

## Frontmatter

- **Status:** **Accepted** — 2026-07-11 (arc 20260711-9; two-round: Claude1+draft / Codex1 / Claude2 close. Codex1 verdict "strong consolidation, close-ready"; B1 scoped the D4 "iff" invariant (the aggregate identity also includes Assembly/display-version/geometry-source material, so the iff is stated for a *fixed* Assembly/source/contract-version — done). Confirmed: no-schema-change accurate; D2/D5/D6 faithful; the seven close-conditions belong here). Consolidates one fully-converged direction arc: **20260701-1** (Part↔Assembly document model, associativity & session/retrieval; Codex1 concur + B1 the aggregate display identity + B2 occurrence-identity-already-decided + N1–N4).
- **What it is:** the **scope ADR** for how an Assembly's 3D geometry **composes** from its components and stays **associative** to them — *"edit a Float Part → the Assembly updates."* It pins **v1 = positioned composition**, the **pull/lazy display-composition read primitive**, the **recursive aggregate display identity**, the **read-vs-write/release closure** distinction, and the **`derived_geometry_from` boundary** — plus the seven close-conditions the implementation arc must satisfy. It is the substrate the **`compose` sub-kind of configurators** ([ADR/0039 D4](0039-the-aiad-authoring-model.md)) depends on.
- **Macro direction:** Petre, 2026-07-01 — *"there is always a direct connection between the files — if we modify a part in part mode, the assembly containing that part will update with the modified part."*
- **Version impact:** **scope ADR — no code this arc.** **Consumes the existing `composed_of.occurrence.transform`** ([ADR/0007](0007-object-type-assembly.md) / [ADR/0010](0010-relationship-type-composed-of.md)) — **no Truth-Model schema change**. The aggregate display identity is a **derived acceleration artifact, not Product Truth** — **no bundle/schema/Glossary/Manifesto change**. A follow-up **build arc** implements the read primitive; a **Studio assembly / session-retrieval UX arc** consumes it.

## §0 — What this ADR does

An orientation pass over the ADRs (arc 20260701-1) found the "files + relationships + associativity + session/retrieval" model **~80% already decided**: the document model (Part [ADR/0005](0005-object-type-part.md), Assembly [ADR/0007](0007-object-type-assembly.md); `composed_of` [ADR/0010](0010-relationship-type-composed-of.md), `mated_to` [ADR/0011](0011-relationship-type-mated-to.md)); reference-level associativity (**Float/Fixed** bindings — Float auto-tracks a changed part); the geometry anchor (**`published_ref`** — anchor-preserving edits survive, anchor-removing edits fail loud); and session/retrieval (**no session server** — [Manifesto P11](../Manifesto.md); "session" = the git working tree + Vault blobs; **locality/staleness** — [ADR/0001 §6](0001-storage-substrate.md) / [ADR/0026 §4](0026-ai-action-protocol-scope.md)). **The one genuine gap:** assembly *geometry* associativity — geometry regenerated **per-Part only**; `derived_geometry_from` was **pre-declared** ([ADR/0005 §11](0005-object-type-part.md)) but never ADR'd. This ADR fills that gap for v1.

## Decisions

### D1. v1 = positioned composition (deliberately boring)
An **Assembly = a set of component occurrences**; each occurrence = a `composed_of` record carrying an **`occurrence.transform`** (`position_mm` + unit `quaternion_xyzw`). **Assembly geometry = each component's own evaluated recipe geometry, placed by its occurrence transform.** The Assembly owns **placements, not geometry edits**. This delivers Petre's "edit Part → Assembly updates" for the overwhelmingly common case on the existing Float/Fixed + `composed_of` + per-Part recipe-fold spine, without smuggling in the next three hard problems. **Deferred:** cross-part derived geometry / skeleton (top-down, D6); in-context assembly features; a mate solver (D7).

### D2. Occurrence identity + placement are ALREADY DECIDED — v1 consumes them, does not reopen them (arc 20260701-1 B2)
- [ADR/0007](0007-object-type-assembly.md) D1 rejected a parallel occurrence namespace: **each `composed_of` relationship record *is* the occurrence**.
- [ADR/0010](0010-relationship-type-composed-of.md) D1: the **record id is the occurrence id**.
- [ADR/0010](0010-relationship-type-composed-of.md) D2 pins **`occurrence.transform.position_mm` + `rotation.quaternion_xyzw`** (identity transforms explicit, no scale), mirrored in the Glossary `composed_of` entry.
v1 positioned composition **consumes this existing shape**; this ADR specifies the missing engine/core *read* behavior over it and **does not reopen** the location decision — no new `occurrence:` namespace, **no schema change**.

### D3. Pull/lazy regeneration — no stored Assembly BREP
**Float** components resolve to current working/released state **on read** → edit a Float Part, its recipe re-evaluates, the Assembly display recomposes. **No persisted composed Assembly BREP** for v1: **`display_representation(assembly)` recomposes from the resolved `composed_of` closure on read** (recipe-hash identity, [ADR/0031](0031-aiadra-mechanical-v0.0.1-scope.md); P11-clean — nothing new persisted as Truth). A cache **may** exist, but only as a **derived acceleration artifact keyed on the D4 aggregate identity**.

### D4. The recursive aggregate display identity (arc 20260701-1 B1)
Lazy assembly display is only safe with a **deterministic identity/cache key over the resolved composition closure** — otherwise a Float child can change while the Assembly sidecar stays byte-identical, and a cache could legally serve stale composed display, breaking the arc's central promise. (Same lesson as the HLR full-identity cache key, [ADR/0036](0036-view-dependent-hlr-contract-v1-1.md): *a valid read that returns a stale display is still a broken contract.*)

The aggregate display identity of an Assembly is a hash, defined **recursively**, over:
- the Assembly's own object identity + **display-contract version** + selected `geometry_ref`;
- for each resolved `composed_of` occurrence — **canonically ordered by occurrence id** (determinism): the **occurrence id**, its **`occurrence.transform`** (`position_mm` + `quaternion_xyzw`), its **binding mode + resolved target** (revision id for Fixed / working-state identity for Float), **and the child's own display identity** — where for a child **Part** that is its display `cache_key` / `topology_signature` / `geometry_ref` / display-version, and for a child **Assembly** it is *that Assembly's* aggregate display identity **computed by this same function** (a **sub-Assembly participates in its parent exactly as a Part does** — nesting is not a special case);
- cycle / closure-resolution failures are **LOUD** (never a partial hash).

**The load-bearing invariant (scoped — arc 20260711-9 B1):** the aggregate display identity is a pure function of *all* the inputs above. **For a fixed Assembly object, selected geometry source, and display-contract version, it changes iff** a resolved child's display identity changes, an occurrence's placement or binding-resolution input changes, or the resolved occurrence set changes. (The broader inputs — a display-contract-version bump, a selected-geometry-source change, or the Assembly's own object identity — of course also change the aggregate identity; they are held fixed only to state the child/placement cascade precisely.) Because a child's own display `cache_key` already encodes its geometry state, a Float child recompute flips the child key → flips the aggregate → invalidates the composed display. **The child/placement cascade is automatic** and needs no cross-object change-notification machinery. This aggregate `cache_key`/`topology_signature` is a **derived acceleration artifact, not Product Truth** (it joins AIADRA's content-addressed-identity family — recipe-hash, `topology_signature`).

### D5. Read closure vs write/release closure (arc 20260701-1 N4)
- **Reads** may use explicit **locality/staleness** policy — a display read can be **lazy/partial** ([ADR/0001 §6](0001-storage-substrate.md) / [ADR/0026 §4](0026-ai-action-protocol-scope.md)).
- **Writes** touching composition, and **release materialization**, must **resolve the full required closure or fail loud** (matching the [ADR/0007](0007-object-type-assembly.md) / [ADR/0010](0010-relationship-type-composed-of.md) write-validation closure rule).
- **Release materializes Fixed** into the frozen snapshot; the **working Float intent stays distinct** and is never overwritten.

### D6. The `derived_geometry_from` gateway — the explicit v1 boundary (arc 20260701-1 N3)
The moment a feature in Object A **consumes Object B's `published_ref`**, it has **left positioned composition** and become **cross-Object derived geometry** — which requires the separate **`derived_geometry_from` ADR** + cascade semantics (pre-declared [ADR/0005 §11](0005-object-type-part.md); never ADR'd; **deferred**, the last named-but-open item in the [ADR/0009 §3](0009-relationship-type-satisfies.md) relationship-type catalogue). v1 names this boundary explicitly so the deferral is a **named edge, not a silent gap**.

### D7. No mate solver in v1 (arc 20260701-1 N2)
**Explicit occurrence transforms only.** `mated_to` remains **validation/diagnostic truth** over materialized transforms ([ADR/0011](0011-relationship-type-mated-to.md) D8 — mates are *evaluated at release, not solved*). A future **mate solver** proposes transform changes *through Transactions* ([ADR/0026](0026-ai-action-protocol-scope.md)); it is **never implied** by v1 display composition.

### D8. Cross-project + catalog routing (arc 20260701-1 Q5)
Direct cross-project product-structure endpoints remain **forbidden**; external catalog / product reuse routes through **local Component/Binding Objects** ([ADR/0008](0008-cross-project-object-identity.md); consistent with the `select`-configurator routing of [ADR/0039 D4](0039-the-aiad-authoring-model.md)). A `composed_of` occurrence targets a local Object, not a remote catalog endpoint.

## §1 — The seven close-conditions for the implementation arc

The follow-up **build arc** ("Assembly geometry composition, v1") must pin, as its acceptance criteria:
1. **Assembly display-composition read primitive** behavior — recompose from the resolved `composed_of` closure; the Native-Engine/core read path, no renderer/kernel back channel.
2. **The recursive aggregate display identity / cache** (D4) — closure hash; canonical ordering; the iff-invariant; derived-not-Truth; loud on cycle/closure failure.
3. **Closure resolution + locality/staleness**, with **read closure vs write/release closure** distinguished (D5).
4. **Consumes the existing `composed_of.occurrence.transform`** (D2) — no reopened occurrence/placement location; any schema touch is confirmation only.
5. **The `derived_geometry_from` gateway named** as the explicit v1 boundary (D6), staged out.
6. **Release materialization** kept distinct from working Float intent (D5).
7. Direct cross-project product-structure endpoints remain **forbidden**; catalog/reuse via local Component/Binding (D8).

## Consequences

- **Positive:** delivers "edit Part → Assembly updates" for the common case on the existing spine; deterministic, P11-clean (no stored BREP, no session server); the recursive aggregate identity makes the cascade automatic with no change-notification machinery; nesting is uniform (a sub-Assembly is a Part-like participant); it is the substrate `compose`-configurators need ([ADR/0039 D4](0039-the-aiad-authoring-model.md)).
- **Deferred (named, not foreclosed):** cross-part `derived_geometry_from` / skeleton (top-down) (D6); in-context assembly features; a mate solver (D7).
- **Watches:** stable ids/digests for occurrences + aggregate identity material; Float/Fixed status surfaced in the assembly tree / PDM UI ([ADR/0040 D7](0040-studio-application-ai-pdm-ux.md)); canonical `_mm`/unit quaternion invariants preserved ([ADR/0010](0010-relationship-type-composed-of.md) D2); released-revision identity mismatches surfaced when Fixed.

## §2 — Relationship to other work

- **[ADR/0039](0039-the-aiad-authoring-model.md) (the AIAD authoring model):** the **`compose` sub-kind of configurators** is built directly on this positioned-composition + occurrence-transform substrate — this scope ADR is its **prerequisite**.
- **[ADR/0040](0040-studio-application-ai-pdm-ux.md) (Studio app/AI/PDM UX):** the **assembly navigation tree** + per-object status/locality + the `listObjects`/`listAssemblies` surface (arc 20260701-1 N1 — *not* an overload of `list_parts`) are the **Studio consumer arc** that follows this ADR's build arc.
- **Next artifacts (deferred, staged):** (1) the **build arc** implementing the seven close-conditions; (2) the **Studio assembly / session-retrieval UX** consumer arc; (3) the **`derived_geometry_from`** ADR (skeleton/top-down), when a skeleton-first workflow needs it.

## Alternatives considered

- **Derived geometry / skeleton (top-down) in v1** — deferred (D1/D6): powerful (Creo top-down) but needs the cross-part cascade built; the `published_ref` + Float spine supports it later. v1 stays positioned-composition.
- **In-context assembly features** (the Assembly owns features that cut/modify constituent geometry post-composition) — deferred (D1).
- **A materialized/cached Assembly BREP** — rejected for v1 (D3): pull/lazy recompose keyed on the aggregate identity is P11-clean and reuses the per-Part fold; a cache is a derived artifact only.
- **A new `occurrence:` namespace / placement record** — rejected (D2): [ADR/0007](0007-object-type-assembly.md)/[ADR/0010](0010-relationship-type-composed-of.md) already decided the occurrence *is* the `composed_of` record.
- **A mate solver as the placement mechanism** — deferred (D7): v1 uses explicit transforms; a solver is a later Transaction-proposing concern.
