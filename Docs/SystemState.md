# SystemState

> Curated navigation / cache layer for AIADRA's working method.
> **Not an authority layer.** Decisions live in ADRs; this document points to them and asks the right questions at arc time.
> Authority hierarchy: ADRs > Manifesto > TruthModelSchema / ArchitectureOverview > SystemState.
> Anti-goals: second TruthModelSchema; decisions not backed by ADRs; >140 lines; narrative recap; ceremonial-but-unread.
> Last updated: arc 20260519-2 ([ADR/0012](ADR/0012-relationship-types-derived-from-and-refines.md)) at 2026-05-19.

## 1. Current Front

**Ring 1 catalogue work — framework complete + five relationship-type ADRs landed (across four decisions).**

- Spine + Promotion Rule + amended commitment 6 + seed catalogue (Part / Requirement / Assembly) + cross-project framework (ADR/0008) + Number allocation (ADR/0004) all pinned.
- Relationship-type ADRs landed: [`satisfies`](ADR/0009-relationship-type-satisfies.md) (trace), [`composed_of`](ADR/0010-relationship-type-composed-of.md) (structural), [`mated_to`](ADR/0011-relationship-type-mated-to.md) (geometric / topological), [`derived_from` and `refines`](ADR/0012-relationship-types-derived-from-and-refines.md) (intra-Requirement trace, combined ADR; partial supersession of [ADR/0006 §"Decision 12"](ADR/0006-object-type-requirement.md) cycle-class rows).
- All three S3 cycle classes operationally active: `trace_graph` (exercised by `satisfies`, `derived_from`, `refines`), `acyclic_dependency` (exercised by `composed_of`), `undirected_constraint_graph` (exercised by `mated_to`).
- First arc end-to-end on the Claude↔Codex coordination protocol from arc 20260519-1; protocol caught a real Claude miss on round 1.

**Next likely arc:** `allocates_to` ADR — last remaining trace relationship named in [ADR/0009 §3](ADR/0009-relationship-type-satisfies.md#3-direct-cross-project-endpoint-policy--permit-with-float-semantics-owned-here). Cross-Type (Requirement → Part / Assembly), unlike ADR/0012's intra-Type shape; needs its own endpoint Type constraints. Alternative: Component per-Type ADR (Track B from snapshot 2026-05-18-12) — first concrete exercise of External pointer Object pattern from [ADR/0008 §3](ADR/0008-cross-project-object-identity.md); the [Coherence Checklist](#3-coherence-checklist) "AIADRA Core hosts nothing" item will be load-bearing.

## 2. Active Pattern Catalogue

| Pattern | Declared by | Applies to | Watch-out |
|---|---|---|---|
| Source-anchored asymmetric binary serialization (implicit source + single serialized target) | [ADR/0009 §1](ADR/0009-relationship-type-satisfies.md), [ADR/0010 §1](ADR/0010-relationship-type-composed-of.md) | `satisfies`, `composed_of`; future `derived_from`, `refines`, `allocates_to` | Legitimate break for symmetric / multi-endpoint relationships per [ADR/0011 §1](ADR/0011-relationship-type-mated-to.md) |
| Undirected multi-endpoint serialization (all semantic endpoints serialized; owning Object is storage carrier) | [ADR/0011 §1](ADR/0011-relationship-type-mated-to.md) | `mated_to`; future undirected geometric | Owning Object is carrier, not semantic endpoint |
| Asymmetric multi-endpoint serialization | future ADR (`parameter_expression`) | `parameter_expression` | TBD when ADR lands |
| Direct-binding (relationship-level Float / Fixed; default Float; release materializes Fixed) | [ADR/0009 §4](ADR/0009-relationship-type-satisfies.md), [ADR/0010 §5](ADR/0010-relationship-type-composed-of.md) | `satisfies`, `composed_of`; future direct-binding | Legitimate break for indirect-binding relationships per [ADR/0011 §5](ADR/0011-relationship-type-mated-to.md) |
| Indirect-binding (no relationship-level binding; delegated to address mechanism; endpoint `revision_id` as cross-check) | [ADR/0011 §5](ADR/0011-relationship-type-mated-to.md) | `mated_to`; future indirect-binding (`parameter_expression` cross-Assembly likely) | Endpoint `revision_id` is never authority; hard-fail on mismatch with occurrence-path resolution |
| Multi-endpoint stable ids (endpoints with n≥2 carry stable local id per S0 commitment 7) | [ADR/0011 §3](ADR/0011-relationship-type-mated-to.md) | `mated_to`; future multi-endpoint | Single-endpoint relationships don't need ids (positional addressing OK) |
| Engineering-structure direct-external-endpoint NO default | [ADR/0008 §4](ADR/0008-cross-project-object-identity.md) | `composed_of`, `mated_to`; future structural | Catalog reuse routes through local Binding Objects |
| Trace-relationship direct-external-endpoint opt-in (with Float external semantics) | [ADR/0009 §3](ADR/0009-relationship-type-satisfies.md) | `satisfies`, `derived_from`, `refines`; future trace relationships likely | Float external resolves to current released Revision; never working sidecar |
| Requirement-to-Requirement trace relationships (`trace_graph` cycle class; partial supersession of [ADR/0006 §"Decision 12"](ADR/0006-object-type-requirement.md) `acyclic_dependency`) | [ADR/0012](ADR/0012-relationship-types-derived-from-and-refines.md) | `derived_from`, `refines` | Cycles are graph-class-valid but semantically suspicious; tooling may warn, schema does not hard-fail |

## 3. Coherence Checklist

Operational yes/no questions for arc-time review (Codex walks these against each proposal). Items earn their place either by (a) catching / nearly-catching an actual issue, or (b) being a load-bearing invariant the current work front will exercise repeatedly.

- **List-addressability:** Does any independently mutable list item carry annotations or need stable identity? If yes, does it have a stable `id`? ([S0 commitment 7](TruthModelSchema.md#7-list-addressability-rule); near-miss caught in [ADR/0011 Codex2](Discussions/20260518-11/Codex2.md).)
- **Released cross-Object geometry:** Does every released cross-Object geometric reference use `published_ref:<id>` unless `requires_validation` is explicitly invoked per the narrow exception? ([S3 commitment 11](TruthModelSchema.md#11-published-reference-ports-are-first-class-addressable-records-owned-by-objects).)
- **Engineering-structure cross-project:** Does the engineering-structure relationship target local Binding Objects unless [ADR/0008 §4](ADR/0008-cross-project-object-identity.md) narrow exception invoked? Catalog Part used as `composed_of` / `mated_to` endpoint must route through local Component. ([ADR/0010 §4](ADR/0010-relationship-type-composed-of.md), [ADR/0011 §6](ADR/0011-relationship-type-mated-to.md).)
- **Binding ownership:** Does Float / Fixed resolution have an explicit owner — relationship-level (direct-binding) or address-mechanism (indirect-binding)? Avoid ambiguous middles. ([ADR/0011 §5](ADR/0011-relationship-type-mated-to.md).)
- **Identity cross-check:** When endpoint `revision_id` is present alongside an address-resolved binding, does it match the resolved terminal Revision? Hard-fail on mismatch. ([ADR/0010 §3](ADR/0010-relationship-type-composed-of.md), [ADR/0011 §3](ADR/0011-relationship-type-mated-to.md).)
- **Released geometric satisfaction:** Does every released `mated_to` evaluate true against materialized occurrence transforms? Contradictory mates hard-fail. ([ADR/0011 §8](ADR/0011-relationship-type-mated-to.md).)
- **Canonical units at fact level:** Does every numeric engineering fact carry its unit at the field-name level (`_mm`, `_deg`) or schema-fixed canonical? No deferring units to "project policy" or "adapter convention." ([ADR/0010 §2](ADR/0010-relationship-type-composed-of.md), [ADR/0011 §2](ADR/0011-relationship-type-mated-to.md).)
- **Quaternion normalization:** Does every quaternion satisfy `|q|² ∈ [1 - 1e-6, 1 + 1e-6]`? No silent renormalize-on-read by adapters. ([ADR/0010 §2](ADR/0010-relationship-type-composed-of.md).)
- **AIADRA Core hosts nothing:** Does the proposal introduce any AIADRA-Core-operated service, live coordination, registry, or hosted federation? If yes, push back hard — this violates [Manifesto P11](Manifesto.md). Proactively-watched as cross-project / catalog / registry arcs approach. ([Manifesto P11](Manifesto.md); proactive per [Codex2 §2 meta-rule](Discussions/20260518-12/Codex2.md).)

## 4. Load-Bearing Now

- `undirected_constraint_graph` cycle policy operationally active ([ADR/0011](ADR/0011-relationship-type-mated-to.md)) — Layer-2 validator implementation will need mate-satisfaction evaluation at release.
- `acyclic_dependency` write-validation closure rule active ([ADR/0007 §5](ADR/0007-object-type-assembly.md), exercised by [ADR/0010](ADR/0010-relationship-type-composed-of.md)) — composition cycle check fires at commit AND release.
- Three serialization patterns coexist (source-anchored asymmetric binary; undirected multi-endpoint; pending asymmetric multi-endpoint). Next multi-endpoint ADR (`parameter_expression`) declares the fourth.
- Eight Codex-walkable invariants in the Coherence Checklist. Adding items follows the meta-rule.
- The Wedge becomes operationally accessible end-to-end after all framework + first three relationship-type ADRs ([ADR/0009](ADR/0009-relationship-type-satisfies.md), [ADR/0010](ADR/0010-relationship-type-composed-of.md), [ADR/0011](ADR/0011-relationship-type-mated-to.md)). Basic Wedge needs only `satisfies`; extended Wedge needs composition + mates.

## 5. Deferred / Do Not Accidentally Solve

- **Configuration / variants** — substantial future ADR. ([ADR/0007 §7](ADR/0007-object-type-assembly.md).)
- **Pattern primitives** (linear / circular / rectangular patterns) — future invariant binding any pattern primitive to per-occurrence addressability. ([ADR/0007 §8](ADR/0007-object-type-assembly.md).)
- **`lock` mate** — endpoint shape differs from feature-pair model; future Schema Change Note. ([ADR/0011 §2 / A1](ADR/0011-relationship-type-mated-to.md).)
- **Kinematic mates** (`gear`, `path`, `cam`, `universal`, `screw`) — future simulation / motion semantics layer. ([ADR/0011 §2 / A3](ADR/0011-relationship-type-mated-to.md).)
- **Criterion-level satisfaction** (`fact_ref` into Requirement `acceptance_criterion:`) — future Schema Change Note when verification taxonomy lands. ([ADR/0009 §2](ADR/0009-relationship-type-satisfies.md).)
- **Component target Type** for `composed_of` / `mated_to` — Component per-Type ADR or Schema Change Note. ([ADR/0010 §1](ADR/0010-relationship-type-composed-of.md), [ADR/0011 §1](ADR/0011-relationship-type-mated-to.md).)
- **Block allocation per Workspace** (Number Reservation Option 4) — Tier-L scale Schema Change Note. ([ADR/0004 §9](ADR/0004-number-allocation.md).)
- **Less-universal mates** (`symmetric`, `width`, profile mates) — Schema Change Notes when concrete production case surfaces.
- **Scale on `composed_of` occurrence** — future Schema Change Note if production case surfaces. ([ADR/0010 §2 / F1](ADR/0010-relationship-type-composed-of.md).)
- **Audit log shape** (failed-transaction retention) — [OQ-0003](OpenQuestions.md), deferred to Ring 2.
- **Project identity artifact** (the future `.aiadra/project-identity.yaml`-or-similar) — flagged but not designed. ([ADR/0008 §5](ADR/0008-cross-project-object-identity.md).)

## 6. Recent Pattern Changes

Rolling log; last 3-5 arcs; newest first.

- **Arc 20260519-2 ([ADR/0012](ADR/0012-relationship-types-derived-from-and-refines.md)):** Declared `derived_from` and `refines` as intra-Requirement trace relationships in a combined ADR; inherited [ADR/0009](ADR/0009-relationship-type-satisfies.md)'s thirteen base trace-relationship pattern fields; no new pattern fields. Partial supersession of [ADR/0006 §"Decision 12"](ADR/0006-object-type-requirement.md) cycle-class rows (`acyclic_dependency` → `trace_graph` for these two relationships only). Pattern Catalogue gained one row (Requirement-to-Requirement trace relationships). First arc to run end-to-end on the Claude↔Codex coordination protocol from arc 20260519-1.
- **Arc 11 ([ADR/0011](ADR/0011-relationship-type-mated-to.md)):** Declared undirected multi-endpoint serialization, indirect-binding, multi-endpoint stable-ids patterns. Activated `undirected_constraint_graph` cycle policy. Superseded [ADR/0010 §3](ADR/0010-relationship-type-composed-of.md) worked-example placeholder `mated_to` shape.
- **Arc 10 ([ADR/0010](ADR/0010-relationship-type-composed-of.md)):** Declared transform shape (position + unit quaternion); canonical units at fact level (`position_mm`); binding-aware nested occurrence path resolution. Activated `acyclic_dependency` cycle policy. Superseded [ADR/0007 §2](ADR/0007-object-type-assembly.md) `relationship:<id>` prefix form.
- **Arc 9 ([ADR/0009](ADR/0009-relationship-type-satisfies.md)):** Declared first relationship-type schema with thirteen base pattern fields; trace-relationship direct-external-endpoint opt-in with Float external semantics.
