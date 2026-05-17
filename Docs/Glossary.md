---
name: aiadra-glossary
status: draft
version: 0.2
last_updated: 2026-05-17
---

# AIADRA Glossary

Definitions of terms that recur in AIADRA discussions, specs, and code. The point is to stop re-litigating terminology in every conversation. Where a term's meaning is still open, the entry says so.

This is a **working document**. Entries are expected to gain precision over time. When a term's meaning is later pinned by an ADR, this glossary should be updated to match.

---

## Core concepts

**AIADRA** — The project itself. Treat as a brand name; pronounced /ai-AH-dra/. The original acronym AIAD (AI-Augmented Design) is the project's intellectual lineage but no longer fits the scope (which is product engineering, not only design). AIADRA stands on its own.

**Product Truth Model** — The canonical, authoritative representation of a product as a graph of engineering Objects, relationships, parameters, requirements, events, and history. Everything else — files, exports, drawings, dashboards, AI views — is a projection of this model. The *storage substrate* of the model (filesystem-canonical with sidecars and event logs vs. database-canonical with file projections) is an open ADR; current instinct is filesystem-canonical, but this is recorded as a question, not a decision.

**Object (Managed Object)** — Any engineering entity tracked in the Product Truth Model: parts, assemblies, features, requirements, electrical components, software modules, purchased items, suppliers, drawings, tests, evidence, releases, ECOs, AI decisions. Every Object has a stable UUID, a human-readable Number, a Type, and metadata.

**Domain Engine** — An external tool that authors data in a specific domain: FreeCAD/OpenCascade for mechanical geometry, KiCad (planned) for electrical, Git for software source, etc. AIADRA modifies these tools where necessary so they expose kernel-level access and synchronize natively with the Product Truth Model.

**Domain Adapter** — The bridge between a Domain Engine and the Product Truth Model. Translates between the tool's native representation and AIADRA's canonical objects/events. Implements a common contract so adding a new domain is a known shape of work.

**AI Action Protocol** — The set of stable structured contracts through which AI agents (and other automation) interact with AIADRA: `inspect`, `query`, `propose`, `modify`, `simulate/check`, `validate`, `explain`, `commit/rollback`, `release`. AI never reaches around these contracts to touch raw files or kernels directly.

---

## Identity and lifecycle

**UUID** — Globally unique, opaque, stable identifier for an Object. Assigned at creation, never reused, never changes. Filenames, Numbers, and storage paths can change; UUID does not.

**Number** — Human-readable identifier (e.g., `P-000123`, `REQ-0014`, `DV-0007`). Stable within a project. Distinct from UUID — Number serves humans, UUID serves the system.

**Revision** — A formally released state of an Object (e.g., Rev A, Rev B). Released revisions are immutable. New work happens on the next revision.

**Iteration** — A working version of an Object between releases. Mutable; not yet committed to a Revision baseline.

**Lifecycle State** — Where an Object is in its life: `in_work`, `under_review`, `released`, `superseded`, `obsolete`. State transitions follow deterministic rules.

**Released Truth** — Data belonging to a Released Revision. Immutable. Modifying it requires creating a new Revision through a controlled Change process (ECR/ECO).

---

## Engineering data

**Requirement** — A statement of what the product must do, constrain, or guarantee, recorded as a first-class Object. Verified by one or more DV tests. Linked to the parts, components, or software that implement it.

**Design Intent** — The "why" behind a feature: purpose, role, what it depends on, what depends on it, what must not change without review. Stored on the feature as structured data, not only in human memory. Example: a hole is not just a circular cut — it is `M8 clearance for MTR-0007 mounting per REQ-014`.

**Parameter** — A named, typed input that defines an aspect of an Object (e.g., `plate_thickness_mm = 6`). The preferred surface for AI modification: same value in, same downstream effect out.

**Provenance** — For every fact in the system: where did it come from? Categories include `released_fact`, `computed_result`, `imported_supplier_data`, `human_input`, `ai_inference`, `ai_proposal`. The AI is required to distinguish these.

**Uncertainty Label** — A confidence/maturity tag on a fact: `verified`, `computed`, `estimate`, `requires_validation`, `stale`. Lets consumers (humans and AI alike) know what trust level applies.

---

## Records and storage

**Sidecar** — A structured, human-readable, machine-validatable metadata file (YAML or JSON, schema-validated) associated with a managed artifact. Diffable in Git, reviewable in pull requests, readable by AI agents without opening heavy binary files. Whether sidecars are *canonical truth* or *projections of canonical truth* is the open storage-substrate ADR.

**Event** — A structured, append-only record of something that happened to the model: object created, parameter changed, revision released, ECO approved, AI proposal accepted, validation failed. Events carry provenance and link to the Transaction that produced them. Whether events are *canonical* (current state = fold over events) or *audit trail alongside flat current-state sidecars* is an open ADR. Current instinct: events canonical for *decisions and lifecycle transitions*; flat sidecars for *current parameter values*; hybrid overall.

**Vault** — Storage for large binary artifacts (CAD files, STEP, STL, PDFs, simulation outputs). Git LFS at first; S3-compatible object storage later. The repository holds references and hashes; the vault holds the bytes.

**Sidecar Projection** — A sidecar file generated from the Product Truth Model. If the storage-substrate ADR resolves to "DB-canonical," sidecars are projections; if "filesystem-canonical," sidecars are the source and the model is loaded from them.

---

## Change and release

**Transaction** — A bracketed, atomic, reversible unit of change. Lifecycle: `begin → modify → recompute → validate → compare → human approval → commit-or-rollback`. Every AI-driven change happens inside a Transaction. Failed Transactions leave no trace on canonical product truth, but may be recorded in an operational audit log along with their proposed changes and validation results.

**Validation** — Rule-based, deterministic checking of the model against constraints: required metadata present, all references resolve, BOM is fresh, released objects unmodified, requirement-test traceability complete, artifact hashes match, etc. Validation is engineering discipline, not AI opinion.

**Where-Used** — A query returning every Object that depends on a given Object. Generated deterministically from the dependency graph. Essential AI infrastructure: "what breaks if I change this?"

**ECR (Engineering Change Request)** — A proposal that something needs to change, with rationale. In the GitHub-native PLM layer, typically captured as a GitHub Issue. Does not by itself modify anything.

**ECO (Engineering Change Order)** — An approved, scoped change carrying the actual modifications, impact analysis, validation results, and approvals. In the GitHub-native PLM layer, typically captured as a Pull Request.

**Release** — A formally controlled engineering baseline: a frozen, reproducible snapshot of object revisions, vault artifact hashes, BOMs, drawings, exports, software versions, electrical files, DV evidence, known issues, and approval records. More than a tag — a Release is reconstructable years later.

**Release Manifest** — The structured document defining a Release: every Object UUID and Revision in scope, every artifact hash, every validation outcome, every approval signature.

**BOM (Bill of Materials)** — Generated, not authored. The list of purchased and made items required to build a product (or sub-assembly), derived from the Product Truth Model at a given Revision or Release.

---

## Planning and process

**Ring** — A unit of planning work, organized concentrically around the Product Truth Model. Ring 0 = foundation docs (Manifesto, Glossary, Architecture, ADR log, Open Questions). Ring 1 = core design specs. Ring 2 = interface contracts. Ring 3 = control layer. Ring 4 = the wedge. Ring 5 = implementation roadmap. See [Discussions/20260517/Claude1.md](Discussions/20260517/Claude1.md).

**Wedge** — The smallest end-to-end vertical slice that exercises all architectural layers. Used to stress-test the architecture by building the minimum viable end-to-end loop. Current scope: *one part + one named parameter + one requirement + one sidecar + one event-log entry + one AI transaction modifying the parameter + one deterministic validation against the requirement + one release manifest*.

**ADR (Architecture Decision Record)** — A short document recording a single load-bearing architectural decision: context, alternatives considered, decision, rationale, consequences. ADRs are the canonical record when they conflict with the Manifesto or design docs.

**Spike** — Throwaway prototype code written to test a design assumption. Allowed in any Ring; explicitly not the same as production implementation. Spikes are how design choices meet reality before getting baked in.

**Open Questions Register** — The living list of unresolved architectural and scoping questions. Each entry has a status: `resolved` (with link to ADR), `deferred-to-ring-X`, or `accepted-as-unresolved`.
