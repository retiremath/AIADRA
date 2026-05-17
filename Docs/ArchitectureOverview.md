---
name: aiadra-architecture-overview
status: draft
version: 0.1
last_updated: 2026-05-17
---

# AIADRA Architecture Overview

> A map of how AIADRA is structured: the five layers it is built in, how they fit together, and which ADRs realize each part. The map, not the derivation — the ADRs carry the reasoning.

## What this document is

The [Manifesto](Manifesto.md) says *what* AIADRA is and *why* it must look the way it does. The ADRs settle *how* specific load-bearing pieces work. This Overview is the **map between the two**: it names the five layers AIADRA is built in, points at the ADRs that realize each, and shows the throughlines that cross them all.

ADRs own architectural decisions; the Manifesto owns principles. When this Overview disagrees with either, the Overview is stale until updated.

The five-layer framing refines the original sketch in [Discussions/20260517/Claude1.md §3](Discussions/20260517/Claude1.md): Validation is now a distinct layer (promoted by the weight Ring 0 placed on it); the original "AI Agent Infrastructure" became "AI Action Protocol & Transactions"; Domain Engines moved to the outer ring; Human UX dropped because it emerges from the other layers rather than constituting its own architectural concern.

## The five layers

AIADRA is structured as five concentric layers around the Product Truth Model. Layer 1 is the keystone — every other layer is defined in terms of what it does to, with, or for it. Layers 1 and 2 are the deterministic core; Layer 3 is how probabilistic AI interacts with that core; Layer 4 is how change promotes through it; Layer 5 is where domain-specific authoring lives.

| Layer | What it holds | Realized by |
|---|---|---|
| **1. Product Truth Model** | Canonical state: Objects, parameters, requirements, events, history, releases | [ADR/0001](ADR/0001-storage-substrate.md), [ADR/0002](ADR/0002-canonical-format.md), [ADR/0003](ADR/0003-schema-governance.md) |
| **2. Validation & Constraints** | Rule-based deterministic checks: schema, YAML Profile, sidecar/event invariant, bundle digest | [ADR/0001 §4](ADR/0001-storage-substrate.md), [ADR/0002 §1](ADR/0002-canonical-format.md), [ADR/0003 §§2,7,9](ADR/0003-schema-governance.md) |
| **3. AI Action Protocol & Transactions** | Stable structured contracts for `inspect` / `query` / `propose` / `modify` / `validate` / `commit` / `release` | Ring 2 (deferred) |
| **4. Project Control & Change-Order Pipeline** | The path Workspace → Commonspace: PRs as ECR/ECO, branch protection, signed releases, bundle governance | [ADR/0001 §5](ADR/0001-storage-substrate.md), [ADR/0003 §11](ADR/0003-schema-governance.md) |
| **5. Domain Engines** | FreeCAD/OCCT, KiCad (planned), Git, procurement, DV — modified to expose kernels natively via the Domain Adapter contract | Ring 3 (Domain Adapter contract, deferred) |

Three cross-cutting structures bind the layers together: the **three-tier Commonspace / Vault / Workspace separation** (Principle 12), the **locality-tier hierarchy for AI reads** ([ADR/0001 §6](ADR/0001-storage-substrate.md)), and **schema bundle governance** ([ADR/0003](ADR/0003-schema-governance.md)).

## Layer 1 — Product Truth Model

The keystone. The single source of truth for every product fact: Objects (parts, requirements, assemblies, releases, ECOs, AI decisions), their parameters, their relationships, their lifecycle states, their provenance.

**Responsibilities.**
- Carry the canonical state of every managed Object.
- Survive any specific tool, including AIADRA Core itself.
- Be readable, diffable, blameable, signable through standard Git tooling — no specialized infrastructure required.

**Realization.**
- *Where it lives.* Filesystem-canonical text artifacts in the project's Git repo + binary blobs in a pluggable Vault + a per-clone derived acceleration cache. ([ADR/0001](ADR/0001-storage-substrate.md))
- *What shape it is written in.* Sidecars in the AIADRA YAML Profile; events as JSONL; release manifests as deterministic JSON. ([ADR/0002](ADR/0002-canonical-format.md))
- *How that shape evolves.* JSON Schema 2020-12; schemas bundled and versioned in AIADRA Core; active-authoring vs archival mode; three-way migration asymmetry across sidecars / events / manifests. ([ADR/0003](ADR/0003-schema-governance.md))

**Inherited principles.** P1 (truth lives here, not in tools), P3 (UUID identity), P4 (design intent first-class), P7 (provenance and uncertainty), P8 (released truth immutable), P10 (history event-based, current state flat), P11 (AIADRA Core hosts nothing), P12 (three-tier on Git).

**Boundary.** Layer 1 stores facts. It does not decide whether they are consistent (Layer 2), how AI agents read or modify them (Layer 3), how they promote from Workspace to Commonspace (Layer 4), or how they are authored in domain-specific tools (Layer 5).

## Layer 2 — Validation & Constraints

Rule-based deterministic checking of the Product Truth Model. Engineering discipline, not AI opinion.

**Responsibilities.**
- Verify every artifact conforms to its declared schema.
- Enforce the AIADRA YAML Profile at the token level (the rule JSON Schema cannot enforce post-parse).
- Enforce the sidecar/event invariant at commit time.
- Verify the project-pinned schema bundle's digest matches the on-disk bundle at startup and before every write.
- Reject loudly on any failure — no best-effort parsing, no silent default substitution.

**Realization.** Concrete across the three Ring 0 ADRs:
- *Schema validation.* Every read uses the bundle named by the artifact's own `schema_version`, with the schema looked up as `(bundle_version, artifact_kind, discriminator) → schema`. ([ADR/0003 §2](ADR/0003-schema-governance.md))
- *Profile linter.* Token-level quoting check; rejection of anchors / aliases / merge keys / custom tags; duplicate-key rejection. ([ADR/0002 §1](ADR/0002-canonical-format.md))
- *Sidecar/event invariant.* Folding events forward from the prior known-consistent baseline must yield a state consistent with current sidecars; divergence is a hard error at commit time. ([ADR/0001 §4](ADR/0001-storage-substrate.md))
- *Bundle digest verification.* The project pin (`.aiadra/schemas.yaml`) carries a `sha256` over canonical serialization of the bundle's normative files (schemas + linter rules + migrators). AIADRA Core verifies the pinned bundle against the digest at startup and before every write; read-path validation resolves the bundle named by each artifact's own `schema_version`, not the project pin. ([ADR/0003 §9](ADR/0003-schema-governance.md))
- *Validator behavior taxonomy.* Four hard-reject classes on read (unknown bundle, schema fail, profile fail, digest mismatch), one hard-reject class on write (past the deprecation horizon), one warn-on-read class (within the grace period). ([ADR/0003 §7](ADR/0003-schema-governance.md))

**Inherited principles.** P2 (AI proposes; deterministic core decides), P5 (validate before commit), P7 (provenance discipline), P10 (sidecar/event invariant), P11 (validation runs locally, not as a service).

**Boundary.** Layer 2 says "yes, the data is consistent" or "no, here is what failed, where, and why." It does not produce the data (Layer 1 / Layer 5), approve it for promotion (Layer 4), or explain the failure conversationally to a human (Layer 3, when surfaced through the AI).

## Layer 3 — AI Action Protocol & Transactions

The stable structured contracts through which AI agents (and other automation) interact with the Product Truth Model.

**Responsibilities.**
- Expose the canonical operations as a typed API: `inspect`, `query`, `propose`, `modify`, `simulate / check`, `validate`, `explain`, `commit / rollback`, `release`.
- Bracket every AI-driven change in a Transaction: `begin → modify → recompute → validate → compare → human approval → commit-or-rollback`. Failed Transactions leave no trace on canonical truth.
- Expose locality tier and staleness tolerance as explicit properties of every read.
- Distinguish provenance — `released_fact`, `computed_result`, `human_input`, `ai_inference`, `ai_proposal` — at the API surface; never let the AI launder its outputs as released facts.

**Realization status.** **Deferred to Ring 2.** Ring 0 set the foundation Ring 2 will sit on:
- [ADR/0001 §6](ADR/0001-storage-substrate.md) commits the API surface to making locality tier and staleness tolerance first-class.
- [ADR/0001 §4](ADR/0001-storage-substrate.md) makes the sidecar/event invariant the gate every Transaction must clear at commit time.
- [ADR/0002](ADR/0002-canonical-format.md) and [ADR/0003](ADR/0003-schema-governance.md) ensure every read and write goes through validation; Transactions cannot smuggle bad data past Layer 2.

**Inherited principles.** P2 (probabilistic AI, deterministic core), P5 (every AI action is a transaction), P6 (parameters first, raw geometry last), P7 (provenance), P9 (layered geometry access), P13 (AI is Workspace-native).

**Boundary.** Layer 3 mediates. It does not decide whether a proposal is correct (Layer 2), whether it is merged (Layer 4), where the underlying fact came from (Layer 1's provenance metadata), or how a domain tool authored the change (Layer 5).

## Layer 4 — Project Control & Change-Order Pipeline

The path from Workspace to Commonspace. The mechanism that promotes work into the project's official record.

**Responsibilities.**
- Mediate every write to Commonspace through the change-order pipeline: branch → PR (the ECR / ECO) → impact analysis + validation results attached → maintainer approval → merge into the protected branch.
- Apply the same machinery to AI-authored and human-authored changes — no separate path for AI.
- Use the project's chosen Git host for branch protection, PR review, signed tags. Never an AIADRA-operated service.
- Govern schema bundle evolution through the same ceremony, scaled by bump class.

**Realization.**
- *Mechanism.* Git's normal mechanics — PRs, merge conflicts, rebases, branch protection. ([ADR/0001 §5](ADR/0001-storage-substrate.md))
- *Reservation file pattern* for project-wide unique allocations (Numbers; future allocation needs); conflicts resolve at PR time. ADR/0004 (deferred) will settle the file shape per [OQ-0015](OpenQuestions.md).
- *Bundle governance ceremony.* PATCH = PR + CHANGELOG entry. MINOR = PR + CHANGELOG + Schema Change Note. MAJOR = its own ADR. ([ADR/0003 §11](ADR/0003-schema-governance.md))
- *No live coordination.* AIADRA Core operates no service for locks, allocators, registries, or in-flight visibility. Git-host APIs may be consulted as optional UX hints — never for correctness. ([ADR/0001 §5](ADR/0001-storage-substrate.md), alternative C2)

**Inherited principles.** P5 (transactional approval), P8 (released truth immutable; changes require new revision + ECR + impact + approval), P11 (AIADRA Core hosts nothing), P12 (three-tier on Git).

**Boundary.** Layer 4 governs *promotion*. It does not author content (Layer 5, with Layer 3 as the AI-mediated path), define what counts as a valid artifact (Layer 2), or store the result (Layer 1).

## Layer 5 — Domain Engines

The authoring surfaces: FreeCAD/OCCT for mechanical, KiCad (planned) for electrical, Git for software source, procurement adapters, DV tools.

**Responsibilities.**
- Author domain-specific content (geometry, schematics, source, BOMs, evidence).
- Synchronize natively with the Product Truth Model — not as wrapped external silos, but as AIADRA-aware engines that expose their kernels and emit canonical Objects and Events through the Domain Adapter contract.

**Realization status.** **Deferred to Ring 3 (Domain Adapter contract) and Ring 4 (the Wedge — first mechanical adapter).** Ring 0 has bounded the work:
- The Wedge round-trips a single mechanical part through the full stack (see [Glossary: Wedge](Glossary.md)).
- [OQ-0004](OpenQuestions.md) (FreeCAD fork-trigger criteria) and [OQ-0005](OpenQuestions.md) (upstream cooperation strategy) are deferred to Ring 3 — neither can settle until the Wedge surfaces actual friction.
- [OQ-0006](OpenQuestions.md) (multi-tool sequencing) is deferred to Ring 5: mechanical first, then electrical, then data-only adapters.

**Inherited principles.** P1 (tools sync to truth), P6 (parameters first, raw geometry last), P9 (layered geometry access).

**Boundary.** Layer 5 produces content for Layer 1. It does not own truth, never bypasses Layers 2–4, and is replaceable in principle — a project that uses no domain engine still has a Product Truth Model.

## Cross-cutting structures

Three structures cross all five layers.

### Commonspace / Vault / Workspace

Manifesto Principle 12, realized concretely by [ADR/0001](ADR/0001-storage-substrate.md):

- **Commonspace** — the Git remote. Holds text artifacts (sidecars, events, manifests) and references-by-hash to Vault blobs. Layer 1 truth lives here; Layer 4 governs writes to here.
- **Vault** — pluggable blob storage (GitHub LFS default; S3 / MinIO / IPFS / NAS via Vault Adapter). Holds bytes only — no decisions, no events.
- **Workspace** — the developer's local clone + working tree + live Domain Engine sessions. AI's natural operating context (Principle 13).

### Locality tiers and staleness tolerance

AI reads against three locality tiers (always-local / local-if-fetched / remote-only) and declare staleness tolerance explicitly per read. ([ADR/0001 §6](ADR/0001-storage-substrate.md)) Layer 3's API surface exposes this distinction; Layer 4 operations that need fresh state (release manifest generation; Reservation-file conflict checks against the post-sync Git state, never against a live allocator) request a sync. Most reads tolerate staleness; a few do not. Making the choice explicit at the API surface keeps the AI honest about what it knows.

### Schema bundle governance

Every artifact carries a `schema_version`; the project carries a pin file at `.aiadra/schemas.yaml` with `bundle_version` + `bundle_digest`. The validator looks up schemas as `(bundle_version, artifact_kind, discriminator)`. Active authoring mode (write path) enforces the deprecation horizon; archival mode (read path) keeps every historical bundle readable forever. ([ADR/0003](ADR/0003-schema-governance.md)) This structure makes Layer 2 operational and gives Layer 1 a reconstructability guarantee across decades.

## A worked path through the layers

A typical AI-driven parameter change, end-to-end:

1. **AI inspects the model** (Layer 3 `inspect` / `query`, against Layer 1's acceleration cache, with explicit staleness tolerance).
2. **AI proposes a change** to a named Parameter (Layer 3 `propose`, returning a structured proposal with provenance `ai_proposal`).
3. **Validation runs against the proposal** (Layer 2: schema, profile, sidecar/event invariant simulation).
4. **Human reviews and approves** (Layer 3 `commit-or-rollback`, gated by human action).
5. **The Transaction commits to the Workspace** — sidecar updated, event appended, both consistent under the invariant.
6. **The contributor pushes and opens a PR** (Layer 4 — the ECR / ECO).
7. **The change-order pipeline validates in CI** (Layer 2 again, on the merge candidate; bundle digest verified).
8. **Maintainers approve and merge** to the protected branch (Layer 4 — promotion to Commonspace).
9. **Eventually, a Release manifest is generated** (Layer 4 output as deterministic JSON, content-hashed and signed) recording every Object UUID + Revision + artifact hash + validation outcome + approval signature.

Every step touches Layers 1 and 2. Every AI-mediated step touches Layer 3. Every Workspace → Commonspace promotion is a Layer 4 act. Layer 5 contributes when the change touches a domain tool's authoring surface (geometry, schematic, source).

## Open structure beyond Ring 0

Ring 1 (Truth Model Schema) inherits four explicit obligations from Ring 0:

1. **[OQ-0012](OpenQuestions.md)** — scale-sensitive structural commitments: directory sharding, event-log sharding, acceleration cache structure, role-based gating.
2. **[ADR/0002 §5](ADR/0002-canonical-format.md)** — synthetic Tier-M / Tier-L workloads must explicitly evaluate YAML merge churn; the format decision reopens if unacceptable.
3. **[ADR/0003](ADR/0003-schema-governance.md) schema content** — the actual JSON Schemas for Part, Requirement, Assembly, every event type, Release Manifest. The Wedge will exercise the first real schemas.
4. **[OQ-0015](OpenQuestions.md)** — Reservation file shape (target ADR/0004).

Plus one captured-for-Ring-2 question: **[OQ-0016](OpenQuestions.md)** — cross-project Object identity and reuse semantics — must be reopened before Ring 2's relationship taxonomy is enumerated, because the answer materially shapes it.

Ring 2 will specify Layer 3's contracts; Ring 3 will specify Layer 5's Domain Adapter bridge; Ring 4 (the Wedge) will round-trip one mechanical part through all five layers; Ring 5 (roadmap) sequences the multi-domain expansion.

## References

- [Manifesto.md](Manifesto.md) — Principles 1–13, Scale Targets, Non-goals.
- [Glossary.md](Glossary.md) — Every term used in this Overview.
- [OpenQuestions.md](OpenQuestions.md) — OQ-0001 through OQ-0016.
- [ADR/0001](ADR/0001-storage-substrate.md), [ADR/0002](ADR/0002-canonical-format.md), [ADR/0003](ADR/0003-schema-governance.md).
- [ArchitectureGraph.json](ArchitectureGraph.json) — On-demand visualization snapshot of this Overview (goals / users / surfaces / features / data / integrations / rules + edges). Buildpad-import compatible. Prose is the master; the graph is refreshed only when a visual rendering is wanted, and is expected to drift between refreshes.
- [Discussions/20260517/Claude1.md §3](Discussions/20260517/Claude1.md) — the original five-layer framework, refined here.
