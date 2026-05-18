---
name: aiadra-glossary
status: draft
version: 0.8
last_updated: 2026-05-18
---

# AIADRA Glossary

Definitions of terms that recur in AIADRA discussions, specs, and code. The point is to stop re-litigating terminology in every conversation. Where a term's meaning is still open, the entry says so.

This is a **working document**. Entries are expected to gain precision over time. When a term's meaning is later pinned by an ADR, this glossary should be updated to match.

---

## Core concepts

**AIADRA** — The project itself. Treat as a brand name; pronounced /ai-AH-dra/. The original acronym AIAD (AI-Augmented Design) is the project's intellectual lineage but no longer fits the scope (which is product engineering, not only design). AIADRA stands on its own.

**AIADRA Core** — The library, CLI, and tooling that we maintain under the AIADRA project. Distinguished from any future ecosystem projects (registries, hosted validators, shared part libraries) that may consume AIADRA but are not part of the core. Per Manifesto Principle 11, AIADRA Core hosts nothing.

**Product Truth Model** — The canonical, authoritative representation of a product as a graph of engineering Objects, relationships, parameters, requirements, events, and history. Everything else — files, exports, drawings, dashboards, AI views — is a projection of this model. Current architectural instinct (open until `ADR/0001`): the Truth Model is realized as canonical text artifacts (sidecars + event log + manifests) in the project's Git repo, with binary artifacts in a pluggable Vault and a local derived acceleration cache.

**Object (Managed Object)** — An engineering entity tracked as a first-class managed artifact in the Product Truth Model, with stable UUID identity, Number, Type, and metadata. The Promotion Rule in [TruthModelSchema.md](TruthModelSchema.md) determines which entities qualify. Current catalogue (as of TruthModelSchema v0.6):

- **Seed Object Types** (pinned by [ADR/0003 §1 / §2](ADR/0003-schema-governance.md) named examples): Part, Requirement, Assembly.
- **Tier-2 Object Types** (cleared the rule; per-Type ADRs follow as the Wedge surfaces need): Drawing, TestProcedure, EvidenceArtifact.
- **Candidate pool, deferred** (pass the capability test plausibly; deferred until concrete use case or [OQ-0016](OpenQuestions.md) reopening): Supplier, Component (purchased item), Software module, Electrical component.
- **Recognized non-Objects** (handled by other spine artifact kinds): Feature (CAD construction-history) as records under parent Part; Test execution / Evidence citation / measurement as records under their parent; Release as Release Manifest + release transaction + events (optional derived Release index for query ergonomics); ECR / ECO as externally governed workflow artifact in the Git host, referenced via PR URL / commit hash; AI Decision as event payload (reopenable through [OQ-0003](OpenQuestions.md)); BOM and similar derived reports (where-used, dashboards, trace matrices, validation summaries, impact-analysis reports, generated exports) as D7-disqualified derived views.

**Domain Engine** — An external tool that authors data in a specific domain: FreeCAD/OpenCascade for mechanical geometry, KiCad (planned) for electrical, Git for software source, etc. AIADRA modifies these tools where necessary so they expose kernel-level access and synchronize natively with the Product Truth Model.

**Domain Adapter** — The bridge between a Domain Engine and the Product Truth Model. Translates between the tool's native representation and AIADRA's canonical objects/events. Implements a common contract so adding a new domain is a known shape of work.

**AI Action Protocol** — The set of stable structured contracts through which AI agents (and other automation) interact with AIADRA: `inspect`, `query`, `propose`, `modify`, `simulate/check`, `validate`, `explain`, `commit/rollback`, `release`. AI never reaches around these contracts to touch raw files or kernels directly.

---

## Three-tier architecture

AIADRA inherits Windchill's Commonspace / Vault / Workspace separation, realized on top of Git and a pluggable blob store (Manifesto Principle 12).

**Commonspace** — The project's shared, official, governed record. Realized as the Git remote — `origin/main`, protected branches, signed tags, the change-order pipeline gating writes. Holds canonical text artifacts (sidecars, event log, release manifests) and references (by content hash) to Vault blobs. Released revisions live here. Every Workspace clone contains a local mirror of Commonspace within its fetched scope.

**Vault** — Pluggable storage for large binary artifacts: STEP exports, mesh files, drawings, PDFs, simulation outputs, renders. The repository holds references and hashes; the Vault holds the bytes. Default Vault implementation is GitHub LFS; pluggable alternatives include S3 / MinIO, IPFS, NAS, project-local filesystem, via the Vault Adapter contract. The Vault is blob storage only — it holds no engineering decisions, no events, no metadata that belongs in the Commonspace text record.

**Vault Adapter** — The contract any blob backend must implement to serve as a Vault: content-addressable read/write by hash, presence-check, fetch, garbage collection cooperation. AIADRA Core ships at least one default adapter (GitHub LFS) and project maintainers may configure others. The adapter is the only place Vault choice leaks into the rest of the system.

**Workspace** — A developer's local environment: the Git clone + working tree + live Domain Engine sessions (FreeCAD, KiCad, etc.) currently open. Per-developer, high-bandwidth, where work-in-progress and AI activity live. The Workspace is the natural operating context for AI agents (Manifesto Principle 13).

**Workspace Browser** — The UI through which a human (and AI) inspects and manipulates the Workspace. Primary Workspace Browser is VSCode + the AIADRA extension; Domain Engines (FreeCAD, KiCad) act as tool-specific sub-browsers that present authoring surfaces over the same Workspace state.

---

## Locality and synchronization

**Locality tier** — Where data physically resides relative to a given Workspace. Three tiers:
- **Always-local.** Text artifacts in the current checkout (working tree). Free, instant.
- **Local-if-fetched.** Other branches, LFS pointer-resolved blobs, history beyond shallow-clone depth. Free if already pulled; one fetch otherwise.
- **Remote-only.** Untracked branches, never-fetched blobs, refs not yet pulled. Requires a `git fetch` or `git lfs pull`.

AI queries and AIADRA Core APIs declare what locality they require; the system reports what is already local and what would need to be fetched.

**Staleness tolerance** — A property of a read operation: is it correct to answer from the Workspace's local mirror of Commonspace (possibly out of date), or must the local mirror first be synchronized? Most queries tolerate staleness (looking up the prior parameter value, the release history, the where-used graph). A few do not (generating a release manifest against the *current* released revisions). AIADRA Core exposes this distinction at the API surface so callers choose deliberately.

**Reservation file** — A Git-tracked file (or set of files) recording locally-claimed allocations that must be unique project-wide — most prominently human-readable **Numbers**. Allocations are made locally and resolved through Git's normal merge mechanics: two developers claiming the same Number in parallel branches produce a merge conflict at PR time, and the second one rebases. AIADRA Core never requires or provides a live allocator. Exact file shape is open until `ADR/0004` (see OQ-0015).

---

## Identity and lifecycle

**UUID** — Globally unique, opaque, stable identifier for an Object. Assigned at creation, never reused, never changes. Filenames, Numbers, and storage paths can change; UUID does not.

**Number** — Human-readable identifier (e.g., `P-000123`, `REQ-0014`, `DV-0007`). Stable within a project, intended for humans (UUID serves the system). Allocated through a Reservation file merged via Git; conflicts resolve at PR time. The Number is presentation, not truth.

**Revision** — A formally released state of an Object (e.g., Rev A, Rev B). Released revisions are immutable. New work happens on the next revision.

**Iteration** — A working version of an Object between releases. Mutable; not yet committed to a Revision baseline.

**Lifecycle State** — Where an Object is in its life: `in_work`, `under_review`, `released`, `superseded`, `obsolete`. State transitions follow deterministic rules.

**Released Truth** — Data belonging to a Released Revision. Immutable. Modifying it requires creating a new Revision through a controlled Change process (ECR/ECO).

---

## Engineering data

**Part** — A managed Object Type representing a physical, internally-designed engineering component (mechanical, electrical, or other domain). First concrete Object Type in the seed catalogue per [ADR/0005](ADR/0005-object-type-part.md). Number prefix `P-NNNNNN` by default. Carries seven TypeSpecific namespaces: `parameter:`, `design_intent:`, `feature:`, `relationship:`, `published_ref:`, `geometry_ref:` (role-discriminated: `authoring_geometry` for canonical kernel geometry, `derived_export` for D7-derived release artifacts retained on the sidecar), and `material:`. Distinguished from Component (purchased / sourced item, deferred per the [Promotion Rule's verdict table](TruthModelSchema.md#verdict-summary)) by being internally designed — a sourcing discriminator on Part may carry both for the Wedge era.

**Assembly** — A managed Object Type representing a composition of Parts and / or sub-Assemblies as a single engineering unit. Third seed Object Type per [ADR/0007](ADR/0007-object-type-assembly.md), completing the seed catalogue. Number prefix `ASM-NNNNNN` by default. Six TypeSpecific namespaces (`parameter:`, `design_intent:`, `feature:` for assembly-level authored features only, `relationship:` for composition / mate / Assembly-spanning parameter expression records, `published_ref:`, `geometry_ref:`); no `material:` (deferred). Each occurrence of a constituent Part or sub-Assembly is a separate `composed_of` relationship record with position / orientation properties; the record id IS the occurrence id. Assembly-context relationships (`mated_to`, `parameter_expression`, in-context features) carry **occurrence-qualified endpoints** (`occurrence_ref` identifying which placed instance) — Object-only references without `occurrence_ref` mean the reusable Object definition, not one placed instance. First Type to activate the `composed_of` `acyclic_dependency` cycle policy with a write-validation closure rule (commits touching composition hard-fail if transitive closure can't be resolved). Configuration / variant semantics and compact pattern primitives are explicitly deferred to future ADRs / Schema Change Notes.

**Requirement** — A managed Object Type representing a statement of what the product must do, constrain, or guarantee. Second concrete Object Type in the seed catalogue per [ADR/0006](ADR/0006-object-type-requirement.md); first non-physical Type. Number prefix `REQ-NNNNNN` by default. Three TypeSpecific singletons under the `requirement:` block (`statement`, `category`, `default_verification_method`) plus five namespaces (`parameter:`, `acceptance_criterion:`, `design_intent:`, `relationship:`, `source:`). Category enum: `functional | performance | non_functional | interface | design_constraint | regulatory`. Default verification methods: `test | analysis | inspection | demonstration`. Verified by Tests (when TestProcedure Type lands); linked to Parts via `satisfies` and to other Requirements via `derived_from` / `refines`. The seven-namespace shape established by [Part](ADR/0005-object-type-part.md) is a template, not a quota — Requirement demonstrates selective namespace adoption (no `feature:` / `geometry_ref:` / `material:` / `published_ref:` / adapter shell).

**Design Intent** — The "why" behind a feature: purpose, role, what it depends on, what depends on it, what must not change without review. Stored on the feature as structured data, not only in human memory. Example: a hole is not just a circular cut — it is `M8 clearance for MTR-0007 mounting per REQ-014`.

**Parameter** — A named, typed input that defines an aspect of an Object (e.g., `plate_thickness_mm = 6`). The preferred surface for AI modification: same value in, same downstream effect out.

**Provenance** — For every fact in the system: where did it come from? Categories include `released_fact`, `computed_result`, `imported_supplier_data`, `human_input`, `ai_inference`, `ai_proposal`. The AI is required to distinguish these.

**Uncertainty Label** — A confidence/maturity tag on a fact: `verified`, `computed`, `estimate`, `requires_validation`, `stale`. Lets consumers (humans and AI alike) know what trust level applies.

---

## Records and storage

**Sidecar** — A structured, human-readable, machine-validatable metadata file (format: the AIADRA YAML Profile, settled in [ADR/0002](ADR/0002-canonical-format.md)) associated with a managed artifact. Holds the **current authoritative state** of the Object. Diffable in Git, reviewable in pull requests, readable by AI agents without opening heavy binary files.

**AIADRA YAML Profile** — The strict YAML 1.2 dialect AIADRA Core's parser enforces on every sidecar: YAML 1.2 only; one managed Object per file; all ambiguous scalars (UUIDs, Numbers, version strings, anything coercible to bool) quoted; no anchors, aliases, merge keys, or custom tags; duplicate keys rejected; JSON Schema validation at every read. Enforcement is split between AIADRA Core's parser (structural rules) and a token-level linter (the quoting rule, which JSON Schema cannot catch post-parse, since the parser has already resolved the scalar). Settled in [ADR/0002](ADR/0002-canonical-format.md).

**Event** — A structured, append-only record of approved transitions: object created, parameter changed, revision released, ECO approved, AI proposal accepted, validation failed. Events carry provenance and link to the Transaction that produced them. Stored as JSONL, one event per line (settled in [ADR/0002](ADR/0002-canonical-format.md)).

**Sidecar / event invariant** — Sidecars hold current authoritative object state; events record approved transitions and provenance. If they disagree, validation fails — neither silently wins. The invariant is enforced at commit time: folding the event log must produce a state consistent with the sidecars (Manifesto Principle 10).

**Acceleration Cache** — A local derived index (DuckDB or SQLite) that supports parametric, graph, and where-used queries at interactive speed. Per-clone, rebuildable from canonical text artifacts, never canonical, never shared, never networked.

**Release Manifest** — The structured document defining a Release: every Object UUID and Revision in scope, every artifact hash, every validation outcome, every approval signature. Stored as deterministic JSON — sorted keys, canonical numeric serialization, normalized whitespace — so manifests are content-hashable and signable (settled in [ADR/0002](ADR/0002-canonical-format.md)).

---

## Change and release

**Transaction** — A bracketed, atomic, reversible unit of change. Lifecycle: `begin → modify → recompute → validate → compare → human approval → commit-or-rollback`. Every AI-driven change happens inside a Transaction. Failed Transactions leave no trace on canonical product truth, but may be recorded in an operational audit log along with their proposed changes and validation results.

**Validation** — Rule-based, deterministic checking of the model against constraints: required metadata present, all references resolve, BOM is fresh, released objects unmodified, requirement-test traceability complete, artifact hashes match, **sidecar/event invariant holds**. Validation is engineering discipline, not AI opinion.

**Where-Used** — A query returning every Object that depends on a given Object. Generated deterministically from the dependency graph. Essential AI infrastructure: "what breaks if I change this?"

**Change-order pipeline** — The mechanism by which writes promote from Workspace to Commonspace: a branch is pushed, a Pull Request opened (the ECR/ECO), impact analysis and validation results attached, maintainers review, the PR merges into a protected branch. Same machinery for AI-authored and human-authored changes (Manifesto Principles 5, 8, 13).

**ECR (Engineering Change Request)** — A proposal that something needs to change, with rationale. Captured as a Pull Request (or Issue, when earlier-stage) in the Git host's interface. Does not by itself modify Commonspace.

**ECO (Engineering Change Order)** — An approved, scoped change carrying the actual modifications, impact analysis, validation results, and approvals. Captured as a Pull Request that has cleared the change-order pipeline.

**Release** — A formally controlled engineering baseline: a frozen, reproducible snapshot of object revisions, vault artifact hashes, BOMs, drawings, exports, software versions, electrical files, DV evidence, known issues, and approval records. More than a tag — a Release is reconstructable years later.

**BOM (Bill of Materials)** — Generated, not authored. The list of purchased and made items required to build a product (or sub-assembly), derived from the Product Truth Model at a given Revision or Release.

---

## Planning and process

**Ring** — A unit of planning work, organized concentrically around the Product Truth Model. Ring 0 = foundation docs (Manifesto, Glossary, Architecture, ADR log, Open Questions). Ring 1 = core design specs. Ring 2 = interface contracts. Ring 3 = control layer. Ring 4 = the Wedge. Ring 5 = implementation roadmap. See [Discussions/20260517/Claude1.md](Discussions/20260517/Claude1.md).

**Wedge** — The smallest end-to-end vertical slice that exercises all architectural layers. Used to stress-test the architecture by building the minimum viable end-to-end loop. Current scope: *one part + one named parameter + one requirement + one sidecar + one event-log entry + one AI transaction modifying the parameter + one deterministic validation against the requirement + one release manifest*.

**ADR (Architecture Decision Record)** — A short document recording a single load-bearing architectural decision: context, alternatives considered, decision, rationale, consequences. ADRs are the canonical record when they conflict with the Manifesto or design docs.

**Spike** — Throwaway prototype code written to test a design assumption. Allowed in any Ring; explicitly not the same as production implementation. Spikes are how design choices meet reality before getting baked in.

**Open Questions Register** — The living list of unresolved architectural and scoping questions. Each entry has a status: `under-investigation`, `deferred-to-ring-X`, `accepted-as-unresolved`, or `resolved` (with link to ADR).

**Scale targets** — The S / M / L / XL tier ladder defined in the Manifesto. AIADRA Core is architecturally compatible with Tier L from day one, operationally smooth at Tier M, with the Wedge at Tier S; Tier XL (enterprise PLM) is out of scope. Scale-sensitive decisions are bucketed as *decide-early-and-probe*, *design-with-scale-in-mind*, or *defer-with-acknowledgement*.
