---
name: aiadra-open-questions
status: draft
version: 0.8
last_updated: 2026-05-30
---

# AIADRA Open Questions Register

The living list of unresolved architectural and scoping questions. Every load-bearing decision that has not yet been made (or has been consciously deferred) lives here until it is closed.

This register exists so that open questions are **visible** rather than implicit. An implicit question gets answered silently by whoever writes the next line of code or doc; an explicit question gets answered with reasoning, alternatives, and accountability.

## Statuses

| Status | Meaning |
|---|---|
| `under-investigation` | Active work to resolve; expect an ADR or follow-up entry soon. |
| `deferred-to-ring-X` | Postponed until a specific later Ring; rationale stated. |
| `accepted-as-unresolved` | Acknowledged, not blocking, no current plan to resolve. |
| `resolved` | An ADR (or other artifact) has settled it; link provided. |

## How to use

- **Adding a question:** assign the next sequential ID (`OQ-NNNN`), pick the most accurate status, fill in the schema, link the discussion or doc where it was surfaced.
- **Promoting to ADR:** when a question moves to `under-investigation` and an ADR is being written, add a forward-reference (`see ADR/NNNN`). When the ADR is signed, change status to `resolved` and link the ADR.
- **Not removing:** resolved questions stay in the register with their resolution. The history is part of the foundation.

Entry schema:

```
### OQ-NNNN: Short title

- **Status:** ...
- **Surfaced in:** [link]
- **Affects:** which Layers, which deliverables

**Context.** What the question is and why it matters.

**Options:** (when alternatives are known)
1. ...
2. ...

**Current instinct:** (when there is one)
```

---

## Entries

### OQ-0001: Storage substrate for the Product Truth Model

- **Status:** `resolved` — see [ADR/0001](ADR/0001-storage-substrate.md)
- **Surfaced in:** [Claude1.md §2 tension #1](Discussions/20260517/Claude1.md), refined in [GPT1.md](Discussions/20260517/GPT1.md), [Claude2.md](Discussions/20260517/Claude2.md), [Claude3.md](Discussions/20260517/Claude3.md), [GPT3.md](Discussions/20260517/GPT3.md), [Claude4.md](Discussions/20260517/Claude4.md), [GPT4.md](Discussions/20260517/GPT4.md)
- **Affects:** Layer 1 (Product Truth Model), Layer 4 (Project Control / OpenPLM), every downstream design that touches persistence

**Context.** AIADRA's Product Truth Model is the canonical, authoritative representation of a product. The brainstorm and subsequent discussions reference three potential substrates: an in-memory or database object graph; OpenPLM-style YAML sidecar files in a Git repo; the native files of Domain Engines (FreeCAD, KiCad). The substrate decision is now bounded by three commitments landed in Manifesto v0.3: **AIADRA Core hosts nothing** (Principle 11), **three-tier Commonspace / Vault / Workspace separation on Git** (Principle 12), and **AI is Workspace-native** (Principle 13). The substrate must work per-project on the user's own infrastructure with no AIADRA-operated service, must split canonical text from binary blobs, and must allow the AI to operate against a Workspace-local mirror.

**Options:**
1. **Filesystem-canonical.** YAML/JSON sidecars + event log + manifests in the Git repo are truth; SQLite/DuckDB exists only as a rebuildable acceleration cache.
2. **DB-canonical.** A database (likely embedded) is truth; sidecars are exports/projections generated for Git review and diff.
3. **Hybrid (filesystem-canonical overall).** Current parameter values live in flat sidecars (canonical). Decisions and lifecycle transitions live in an event log (canonical). Large binary artifacts live in a pluggable Vault (LFS default; S3 / MinIO / IPFS via Vault Adapter). The acceleration cache (DuckDB) is per-clone derived. The sidecar/event invariant — *if they disagree, validation fails; neither silently wins* — is enforced at commit time.

**Current instinct.** Option 3. Alignment across the full discussion thread. Core argument: if a derived cache breaks, truth survives; if a DB is canonical and corrupts, truth is lost. Matches the no-HQ commitment and the GitHub-native philosophy. ADR/0001 will spell out the rejected alternatives, the locality-tier semantics for AI reads, the staleness-tolerance API, and the specific scaling/concurrency trade-offs accepted. ADR/0001 will also resolve OQ-0002 and OQ-0014 in the same document.

---

### OQ-0002: Event-canonicity scope (child of OQ-0001)

- **Status:** `resolved` — see [ADR/0001](ADR/0001-storage-substrate.md) §4 (the sidecar/event invariant)
- **Surfaced in:** [Claude2.md §"On the storage substrate" point 2](Discussions/20260517/Claude2.md), refined by [GPT3.md](Discussions/20260517/GPT3.md) and [Claude4.md](Discussions/20260517/Claude4.md)
- **Affects:** Layer 1 (Product Truth Model), Layer 3 (Transaction model), Principle 10

**Context.** Within a filesystem-canonical hybrid (per OQ-0001's instinct), the question becomes: *how much* of the model is event-sourced? Event sourcing (current state = fold over events) is elegant and aligns with Principle 10, but has real costs: schema migration becomes "rewrite history," storage grows monotonically, and projection logic itself becomes load-bearing.

**Options:**
1. **Full event sourcing.** Current state is always reconstructed from events. No flat current-state files.
2. **No event sourcing.** Events are an audit trail only; flat sidecars hold current state.
3. **Mixed, with invariant.** Sidecars hold current authoritative object state. Events record approved transitions and provenance (ECR opened, parameter changed, release approved). If they disagree, validation fails — neither silently wins. The invariant is enforced at commit time: folding the event log must produce a state consistent with the sidecars.

**Current instinct.** Option 3, with the "neither silently wins" invariant as a load-bearing rule. Matches Manifesto Principle 10 v0.3 wording and Glossary v0.3 Sidecar / Event / Sidecar-event-invariant entries. The invariant is what makes the hybrid safe: it prevents silent drift between the two views, and it makes validation a genuine consistency gate rather than a syntactic check.

---

### OQ-0003: Audit log scope for failed transactions

- **Status:** `deferred-to-ring-2`
- **Surfaced in:** [GPT2.md §"Third Fix"](Discussions/20260517/GPT2.md); Glossary v0.2 Transaction entry
- **Affects:** Layer 3 (AI Action Protocol & transactions)

**Context.** Failed Transactions never reach canonical product truth, but they carry useful information (what the AI proposed, what validation failed, why). Retaining this is valuable for traceability and AI-behavior review. The question is *what gets retained, where, with what retention policy* — and that question only becomes concrete once the Transaction contract is being designed in detail.

**Options (sketched):**
1. **No retention.** Failed transactions vanish.
2. **Full retention.** Audit log retains proposed changes + validation outcomes indefinitely.
3. **Bounded retention.** Audit log retains summary records under a policy (last N per object, last N per AI agent, time window, etc.).

**Current instinct.** Not yet. Capture options properly when designing the Transaction contract in Ring 2.

---

### OQ-0004: Fork trigger — when does external work become a FreeCAD fork?

- **Status:** `deferred-to-ring-3`
- **Surfaced in:** [Claude1.md §2 tension #2](Discussions/20260517/Claude1.md)
- **Affects:** Domain Engine strategy (Layer 3), governance, long-term maintenance burden

**Context.** The plan sequence is: start as external workbench/plugin → patch FreeCAD where necessary → fork only when blocked. The criterion for "blocked" — *"when access paths aren't enough"* — is not operationalized. Without an explicit trigger we will drift toward fork-by-frustration, exactly what the brainstorm warned against (RealThunder/LinkStage as cautionary).

**Options to define:**
1. **Functional criteria.** Fork only when specific access requirements cannot be satisfied as a plugin (e.g., needed event hooks not exposed; required transaction guarantees not available).
2. **Project-readiness criteria.** Fork only when the project has the maintainer capacity, test models, and CI to carry the fork.
3. **Both.**

**Current instinct.** Defer until Ring 3 (when the Domain Adapter contract is being designed) and until the Wedge in Ring 4 surfaces actual friction. The trigger will be much easier to define once we know which FreeCAD APIs we've actually had to fight.

---

### OQ-0005: Upstream FreeCAD cooperation strategy

- **Status:** `deferred-to-ring-3`
- **Surfaced in:** [Claude1.md §2 tension #5](Discussions/20260517/Claude1.md)
- **Affects:** Domain Engine strategy, public positioning, community formation

**Context.** Modifying FreeCAD deeply enough to expose kernel-level access for AI agents is, in practice, a fork unless upstream cooperates. LGPL-2.1 permits it; the cooperation strategy with FreeCAD's existing community is undefined. The Manifesto's tone toward FreeCAD is respectful but the operational strategy is unstated.

**Options:**
1. **Cooperative.** Contribute changes upstream, work within FreeCAD governance, accept their pace.
2. **Friendly fork.** Maintain a divergent branch; upstream where mutually beneficial; do not block on upstream pace.
3. **Hard fork.** Independent project; ignore upstream direction; accept full maintenance burden.

**Current instinct.** Progression: 1 → 2 if upstream pace blocks the mission. Closely related to OQ-0004; defer commitment until then.

---

### OQ-0006: Multi-tool integration sequencing and asymmetry

- **Status:** `deferred-to-ring-5`
- **Surfaced in:** [Claude1.md §2 tension #7](Discussions/20260517/Claude1.md)
- **Affects:** Roadmap, scope of each phase

**Context.** The brainstorm and the converged plan have rich detail on the mechanical path (FreeCAD/OCCT) but only sketches for electrical (KiCad), software (Git), procurement, and DV adapters. Each of these is a multi-year project on its own. The order of attack is undefined.

**Current instinct.** Mechanical first (the Wedge is mechanical). Electrical second (procurement and DV both need component identity to anchor to). Software adapter and DV adapter later. Procurement may be earliest of the data-only adapters because it has the simplest data model and immediate engineering value. Capture in Ring 5 roadmap once the Wedge is proven.

---

### OQ-0007: Wedge scope adequacy

- **Status:** `resolved` — see [arc 20260530-1](Discussions/20260530/20260530-1/) ([Claude4](Discussions/20260530/20260530-1/Claude4.md) + [Codex4](Discussions/20260530/20260530-1/Codex4.md) signoff) and [`spikes/wedge-001/FRICTION_LOG.md`](../spikes/wedge-001/FRICTION_LOG.md). Wedge-001 ran end-to-end clean per [ADR/0023 §"Worked invocation"](ADR/0023-wedge-spike-scope-and-runtime.md); the friction log confirms basic Wedge scope is adequate as a validating slice — *"the basic Wedge architecture — sidecars + events + Revisions + Manifest + cross-artifact invariant — survived contact with reality cleanly. The friction is in field-level details, not architectural shape."* V&V-instrumented Wedge-002 is the natural follow-up but is NOT a scope-adequacy gap; it's an additive expansion per the build-it-evaluate-expand pattern.
- **Surfaced in:** [Claude1.md §2 tension #6](Discussions/20260517/Claude1.md); scope refined in [Claude2.md](Discussions/20260517/Claude2.md) with [GPT2.md](Discussions/20260517/GPT2.md) acceptance; reopened in [ADR/0023](ADR/0023-wedge-spike-scope-and-runtime.md) per the `accepted-as-unresolved` resurfacing rule; resolved by [arc 20260530-1](Discussions/20260530/20260530-1/) after a four-round Claude↔Codex spike-writing arc that ran the spike end-to-end and reviewed the friction log.
- **Affects:** Ring 4 deliverable (now satisfied)

**Resolution.** Wedge-001 implemented as a Python 3.11+ spike at [`spikes/wedge-001/`](../spikes/wedge-001/) per ADR/0023. Four-round Claude↔Codex arc: Codex1 caught four schema-shape blockers (B1 satisfies record shape; B2 Requirement canonical shape; B3 mandatory `schema_version` on events; B4 bundle `revision` lookup + manifest `manifest_type`); Codex2 caught three implementation-faithfulness blockers (Profile quoting on dump; Windows-newline-driven hash mismatch; schema validation not at every read); Codex3 caught one narrow remaining blocker (event sequencing read events unvalidated); Codex4 signoff. Final spike: 6 CLI commands matching ADR/0023 worked invocation; 8 JSON Schemas; 12 negative Profile fixtures all rejected; manifest content-hashable + pins verifiable against on-disk bytes. Friction log surfaces three load-bearing production-grade signals (`parameter_changed` event payload cannot derive `fact_provenance` mutation; acceptance-criterion threshold-expression has no canonical primitive; cross-artifact atomicity gap awaits write-ahead-log / git-commit-as-atomic-boundary) plus several minor items — all are field-level Schema Change Notes, not architectural reopens.

**Current instinct (carried forward, now confirmed).** Build it, evaluate, expand if necessary. Build-it: done. Evaluation: passed at architectural level; friction at field level becomes future Schema Change Notes. Expand: Wedge-002 (V&V-instrumented) is the obvious next spike per ADR/0023 §10 deferral list; production-grade `aiadra-core` runtime ADR is the obvious next spec arc, informed by FRICTION_LOG.md.

---

### OQ-0008: Contributor and sustainability model

- **Status:** `accepted-as-unresolved`
- **Surfaced in:** [Claude1.md §2 tension #4](Discussions/20260517/Claude1.md)
- **Affects:** Long-term viability; does not block Ring 0–4

**Context.** AIADRA's eventual scope (multi-domain, multi-engine, AI-native) plausibly requires 4–8 talented contributors over many years. The project is currently solo (Petre as workflow architect, Claude as implementer). Open-source community formation is itself a multi-year project, distinct from the technical work.

**Current instinct.** Not a Ring 0 blocker. Defer explicit strategy until the Wedge is built and there is *something concrete to recruit around*. The Manifesto and README should signal that this is an evolving open-source project; do not invent governance ahead of need.

---

### OQ-0009: AIAD acronym vs project scope

- **Status:** `accepted-as-unresolved` — operationally closed by naming convention
- **Surfaced in:** [Claude1.md §2 tension #3](Discussions/20260517/Claude1.md)
- **Affects:** Public positioning only; does not affect any technical decision

**Context.** "AIAD" (AI-Augmented Design) doesn't capture the project's actual scope, which is product engineering (mechanical + electrical + software + procurement + DV + documentation + release), not only design. AIADRA has been adopted as a brand name; the original acronym is preserved as etymology in Glossary v0.2.

**Current instinct.** Accept as resolved by convention. No technical action required. Revisit only if the project is later renamed.

---

### OQ-0010: Decision points vs principles — structural separation

- **Status:** `resolved` — this register is the resolution
- **Surfaced in:** [Claude1.md §2 tension #8](Discussions/20260517/Claude1.md)
- **Affects:** Process

**Context.** The original strategic plan in the brainstorm mixed load-bearing decisions (what we must decide now) with principles (what guides decisions later). Without separation, the roadmap obscured which items were blocking and which were aspirational.

**Resolution.** Three documents now hold these concerns separately:
- **Principles** live in [Manifesto.md](Manifesto.md).
- **Open decisions** live in this register (OpenQuestions.md).
- **Resolved decisions** live in `ADR/NNNN-*.md` files (folder to be created with the first ADR).

This separation is structural going forward.

---

### OQ-0011: Canonical on-disk format

- **Status:** `resolved` — see [ADR/0002](ADR/0002-canonical-format.md). Decision: the **AIADRA YAML Profile** for sidecars; JSONL for events; deterministic JSON for release manifests. S-expressions held as recorded fallback if Ring 1 stress tests reveal unacceptable YAML merge churn.
- **Surfaced in:** [Claude3.md §6](Discussions/20260517/Claude3.md), refined in [GPT3.md](Discussions/20260517/GPT3.md) and [Claude4.md](Discussions/20260517/Claude4.md)
- **Affects:** Layer 1 (Product Truth Model), tooling parsers, AI token cost, merge ergonomics, schema migration

**Context.** Substrate (OQ-0001) settles *where* truth lives; format settles *what shape it is written in*. Format is a sibling decision, separable enough to deserve its own ADR. Format choice splits by artifact class — human-edited sidecars, append-only event log, machine-generated release manifests have different needs. Format is also scale-sensitive (parse cost at 100k objects, merge-conflict shape, schema-migration ergonomics, AI parsing cost), so the decision falls in the *decide-early-and-probe* bucket: settle the choice in Ring 0, validate against synthetic Tier-M / Tier-L data before committing in production.

**Options:**

*Sidecars (human-edited current state):*
1. **YAML** — OpenPLM precedent, comment-friendly, readable. Spec ambiguity (1.1 vs 1.2, type coercion). Merge fragility increases with nesting depth.
2. **KiCad-style S-expressions** — actual precedent in this exact space; mergeable; parseable. Less familiar to non-EDA engineers.
3. **TOML** — clean for flat config; weak for deeply nested list-of-object data (which is exactly the shape of product data).
4. **JSON5 / HJSON** — JSON with comments; less ecosystem support.
5. **Markdown + YAML front-matter** — best for narrative design-intent; parser surface grows.

*Event log:*
1. **JSONL (newline-delimited JSON)** — append-only, line-mergeable, ubiquitous tooling, no spec ambiguity.
2. Other (YAML stream, NDJSON variants).

*Release manifests:*
1. **Deterministic JSON** (sorted keys, canonical serialization) — content-hashable, signable, machine-generated.
2. Other (CBOR, protobuf — gain determinism but lose readability).

**Current instinct.** JSONL for events; deterministic JSON for manifests. Sidecars: YAML for parity with OpenPLM and broad familiarity, but **run a spike comparing YAML against KiCad-style S-expressions on a representative sidecar** before committing. Schema-versioning discipline (OQ-0013) applies uniformly across all three.

---

### OQ-0012: Scale-sensitive structural commitments

- **Status:** `deferred-to-ring-1` — revisit at Ring 1 entry, when the Truth Model Schema is drafted
- **Surfaced in:** [Claude3.md §4](Discussions/20260517/Claude3.md), promoted from `accepted-as-unresolved` per [GPT3.md](Discussions/20260517/GPT3.md)
- **Affects:** Layer 1 (Product Truth Model directory layout, event-log organization, cache structure), Layer 4 (role-based change-order gating)

**Context.** Manifesto v0.3 commits AIADRA Core to being architecturally compatible with Tier L (50–500 contributors, tens of thousands of parts) from day one and operationally smooth at Tier M. Several structural decisions are scale-sensitive enough that we cannot leave them undefined past Ring 1, because they shape the Truth Model Schema directly. They are not blockers for Ring 0 ADRs (substrate, format, schema governance), but they must be addressed before the Ring 1 schema work hardens.

**Items in scope:**
1. **Directory layout for sidecars** — flat vs. UUID-prefix sharded vs. Type-then-shard. At 100k objects, flat directories degrade Git tree handling.
2. **Event-log organization** — single file vs. monthly/yearly shards vs. per-stream shards.
3. **Acceleration cache structure** — index strategy for parametric queries, where-used graph traversal, full-text search.
4. **Role-based change-order gating** — committer / reviewer / release-manager roles enforced through the Git host's branch protection + AIADRA validation. The mechanism is host-native (GitHub teams, Gitea collaborators, etc.); the AIADRA-side rule must encode role expectations explicitly.

**Current instinct.** Defer concrete decisions to Ring 1, with the constraint that Ring 0 ADRs must not preclude any of these refinements. Specifically: ADR/0001 must accept content-addressable file paths (so sharding is added without breaking references); ADR/0002 must pick a format that scales (so YAML's merge fragility is a real data point); ADR/0003 must support schema evolution across millions of historical records.

---

### OQ-0013: Schema governance and versioning

- **Status:** `resolved` — see [ADR/0003](ADR/0003-schema-governance.md). Decision: JSON Schema Draft 2020-12; schemas bundled and versioned in AIADRA Core; per-artifact `schema_version` selects a bundle, plus an artifact-kind discriminator (`object.type` / `event_type` / `manifest_type`) selects the schema within it; per-event-type schemas with a shared `_base.schema.json`; SemVer taxonomy with breaking changes always MAJOR even pre-1.0; three-way migration asymmetry (sidecars migrate forward via `aiadra migrate`, events immortal at declared version, manifests frozen); active-authoring vs archival mode split (read path validates against any historical bundle forever, write path enforces deprecation horizon); project pin file with bundle version + digest covering schemas, linter rules, and migrators; migrator constraints (deterministic, dry-run, idempotent, no-network, fixture-tested, human-readable diffs); governance ceremony scaled by bump class (PATCH/MINOR by PR + changelog/note, MAJOR by ADR); default deprecation horizon of two MAJOR bumps.
- **Surfaced in:** [Claude3.md §6](Discussions/20260517/Claude3.md), endorsed in [GPT3.md](Discussions/20260517/GPT3.md) and [Claude4.md](Discussions/20260517/Claude4.md); designed in [Claude6.md](Discussions/20260517/Claude6.md) → [GPT6.md](Discussions/20260517/GPT6.md) → [Claude7.md](Discussions/20260517/Claude7.md); ADR draft reviewed in GPT8 with four corrections folded in before landing.
- **Affects:** Every canonical artifact (sidecar, event, manifest), every migration, every validator, AI parsing

**Context.** Whatever on-disk format ADR/0002 picks, the more load-bearing discipline is schema governance: every artifact declares a `schema_version`; schemas are themselves versioned; migrations have explicit forward paths; the AIADRA Core validator rejects unrecognized or stale schemas loudly. Without this, format choice rots into a thousand bespoke variants and AI agents cannot trust the structure of what they read.

**Options:**
1. **Inline schema_version per artifact** + central registry of schemas (versioned in the AIADRA Core repo) + explicit migrators (one per version bump). Validators consult the registry on every read.
2. **Schema embedded in artifact** — every sidecar carries its own schema definition. Self-describing; heavy.
3. **Implicit / convention-based** — no version field, parser handles all known shapes. Fragile.

**Current instinct.** Option 1. Schemas live under `aiadra-core` source control, versioned independently of the Product Truth Model itself; every artifact carries `schema_version`; a migrator is required for any schema change that is not strictly additive. Schema changes are themselves ADRs (or short addenda) so the history is recorded.

---

### OQ-0014: Inter-Workspace coordination semantics

- **Status:** `resolved` — see [ADR/0001](ADR/0001-storage-substrate.md) §5 (no live coordination; pure Git mechanics)
- **Surfaced in:** [Claude3.md §3](Discussions/20260517/Claude3.md), debated through [GPT3.md](Discussions/20260517/GPT3.md), [Claude4.md](Discussions/20260517/Claude4.md), [GPT4.md](Discussions/20260517/GPT4.md)
- **Affects:** AI behavior on read paths, conflict handling, the no-live-coordination posture, OQ-0015 (Number allocation)

**Context.** Workspaces are per-developer Git clones. When two contributors are working on overlapping parts of the model — same Object, same Number namespace, overlapping requirements — they may collide at PR/merge time. The question is whether AIADRA Core should introduce *any* live coordination signal (advisory locks, in-flight ECR registry, central allocator) or rely entirely on Git's merge mechanics plus the change-order pipeline. This question is forced into the open by the numbering case (OQ-0015) where the natural-sounding answer ("just check the project for the next available Number") would re-introduce a centralized live service exactly contrary to Principle 11.

**Options:**
1. **Live coordination service** — AIADRA Core operates or requires a service that resolves Number allocations, advisory locks, in-flight-ECR visibility live. Rejected on Principle 11 grounds (AIADRA Core hosts nothing).
2. **Git-host-native coordination** — use Git host APIs (GitHub teams, PR queries) for visibility; no AIADRA-operated service, but AI agents may query the host for in-flight PR state as a UX nicety.
3. **Pure Git mechanics** — no live coordination of any kind. All conflicts resolve at merge time via Git's normal mechanisms. Number allocation uses a Reservation file merged through Git (see OQ-0015). AI surface explains the model to users.

**Current instinct.** Option 3, with Option 2 permitted as an *optional UX layer* — never load-bearing for correctness. The conclusion follows directly from Principles 11 and 13: if AIADRA Core hosts nothing and AI is Workspace-native, there is nowhere coordination could live without violating both. ADR/0001 will record this as a load-bearing non-decision (we considered locks/registries/allocators, rejected them, here is why) so future contributors do not relitigate it implicitly.

---

### OQ-0015: Human-readable Number allocation strategy

- **Status:** `resolved` — see [ADR/0004](ADR/0004-number-allocation.md)
- **Surfaced in:** [GPT3.md](Discussions/20260517/GPT3.md) §"Important Corrections", elaborated in [Claude4.md](Discussions/20260517/Claude4.md)
- **Affects:** Identity scheme (Principle 3), every Object's lifecycle, AI behavior on Object creation, OQ-0014

**Resolution** ([ADR/0004](ADR/0004-number-allocation.md), 2026-05-18). **Option 1: per-prefix Reservation artifacts** at `Docs/Reservations/<TypePrefix>.yaml`, with the Number as the YAML mapping key (so duplicate claims collide at parse time via the AIADRA YAML Profile's duplicate-key rejection). `reservation` joins the artifact-kind set as the fifth kind under [ADR/0003 §2](ADR/0003-schema-governance.md). Allocation is Transaction-atomic across sidecar + event + Reservation per ADR/0004 §6 — the Layer-2 validator hard-rejects commits touching a Reservation entry without the full coherent set. Status transitions are monotonic forward (`current → retired` only; retired aliases permanent per S2.5 commitment 7). Conflict resolution at PR time via Git rebase per S2.5 commitment 3. Block allocation (Option 4) deferred to future Schema Change Note for Tier-L scale.

**Context.** UUIDs are easy: locally generated, collision-resistant, never coordinated. Human-readable Numbers (`P-000123`, `REQ-0014`) are not — they imply stability and uniqueness within a project, and they are surfaces humans grow attached to. The naive solution ("check the project for the next free Number, claim it") would require live Commonspace coordination and violate Principle 11. The right model is **allocation through a Git-tracked Reservation file** with conflicts resolved at PR time.

**Options (historical, evaluated and resolved in [ADR/0004](ADR/0004-number-allocation.md)):**
1. **Per-Type Reservation file** — `Docs/Reservations/P.yaml`, `REQ.yaml`, etc., each recording claimed Numbers and the UUID they bind to. Conflicts produce merge conflicts on the relevant file. ***Adopted, with Number as YAML mapping key (not list-of-records) so duplicate claims collide at parse time — see [ADR/0004](ADR/0004-number-allocation.md).***
2. **Single project Reservation file** — one file per project; coarser merge granularity. *Rejected — different artifact shape; would require separate schema and validation. Consolidated Reservation artifacts may land in a future Schema Change Note with their own discriminator.*
3. **No Reservation file** — Numbers are assigned at PR-merge time from the merge commit's monotonic counter. Numbers are not stable until merged. *Rejected — S2.5 commitment 5 requires Numbers stable after merge, and events on the working branch reference Numbers that must exist pre-merge.*
4. **Block-allocation per Workspace** — each Workspace pre-reserves a block (`P-001000` through `P-001099`) at first use. Reduces conflict surface but introduces sparse Number sequences. *Deferred to future Schema Change Note for Tier-L scale (50K+ Objects, 50+ contributors with frequent allocation) when Option 1's merge churn becomes unacceptable.*

**Original deferral rationale (preserved for context).** "Option 1 is the current instinct, with the file format defined by Ring 1's Truth Model Schema work. UUID remains underlying truth; the Number is presentation. Rebase-and-retry semantics for merge conflicts." Ring 1's S2.5 settled the Number-binding lifecycle and handed off seven explicit acceptance criteria to ADR/0004 (current + retired binding, reuse rejection, atomic create / rebind, merge-conflict detection on the Number key, retirement history). ADR/0004 satisfies all seven.

---

### OQ-0016: Cross-project Object identity and reuse semantics

- **Status:** `resolved` — see [ADR/0008](ADR/0008-cross-project-object-identity.md)
- **Surfaced in:** [Snapshot 2026-05-17-03](Snapshots/2026-05-17-03.md) "Open threads" — surfaced by Petre as the "file management as afterthought" inversion concern
- **Affects:** Layer 1 (Product Truth Model identity scheme — Principle 3), Layer 4 (Project Control across project boundaries), shared-library / part-catalog ecosystem (out-of-core, but constrained by the answer here)

**Resolution** ([ADR/0008](ADR/0008-cross-project-object-identity.md), 2026-05-18). Option 4 reframed: **catalog projects** (regular AIADRA projects publishing reusable Objects; no Catalog Object Type) + **consumer-side Binding Object Types** (Component for physical / procurement; SoftwareModule for software; other domains may define their own) via the [External pointer Object pattern](TruthModelSchema.md#5-two-named-non-disqualifier-patterns) (Binding lifecycle). Cross-project canonical identity is `(project_id, object_uuid)`; `revision_content_hash` proves integrity for fixed bindings; `project_scope` splits stable `project_id` from non-authoritative `locator_hint`. Engineering relationships in consumer projects target local Binding Objects unless the relationship-type schema explicitly permits direct external endpoints. Transport / discovery / federation are out of scope for AIADRA Core (per Manifesto P11).

**Context.** Principle 3 establishes UUID as identity *within a project*. The cross-project case was unstated. When Project B reuses a part (e.g., a standard M8 bolt, a motor, a board module) originally authored in Project A, what is the identity relationship between the two? The naive answers each had real costs:

- *Same UUID across projects* — preserves identity perfectly but requires global UUID coordination (which Principle 11 forbids as a live service) and means a Project A revision change quietly affects Project B's snapshot of "the same Object."
- *Different UUID with a "derived-from" link* — preserves no-HQ posture but breaks "what depends on this part?" queries at the ecosystem level; the same physical fastener now has N identities.
- *Shared library substrate* — a third class of Object (catalog entry) with its own identity, referenced by per-project Objects that bind to a specific revision. Cleanest but introduces new infrastructure.

Largely covered by existing principles for the *within-project* case (Principle 3 UUID, Principle 1 tools-sync-to-truth, ADR/0001's acceleration cache for where-used). The gap was the *across-project* case, which Ring 1's Truth Model Schema could not avoid: the relationship taxonomy needed the answer.

**Options (historical, evaluated and resolved in [ADR/0008](ADR/0008-cross-project-object-identity.md)):**
1. **Project-scoped UUIDs, no cross-project link.** Reused parts are re-authored in each project. Simple; loses ecosystem-level traceability entirely. *Rejected — too lossy for AIADRA's open-source-hardware-ecosystem positioning.*
2. **Project-scoped UUIDs + `derived-from` relationship.** Each project owns its own UUID; the relationship carries (source_project, source_uuid, source_revision). Cross-project where-used is a federated query. *Rejected — semantic ambiguity (binding vs genuine derivation) plus federated-query cost.*
3. **Global UUID namespace + per-project revision binding.** UUID is shared; each project pins a specific revision of the upstream Object. Requires only naming convention (no live coordination if UUID generation remains v4-random), but creates a strong implicit contract on upstream stability. *Rejected — violates the spirit of "each project owns its truth" per Manifesto P11; implicit cross-project ownership questions.*
4. **Catalog Objects as a separate class.** Standard parts, common modules, and reusable assets live as Catalog Objects in shared library projects; consumer projects reference them by (catalog_uuid, revision). Closest to existing component-library practice. ***Adopted, reframed as catalog projects (regular AIADRA projects publishing reusable Objects, not a distinct Object Type) + consumer-side Binding Object Types — see [ADR/0008](ADR/0008-cross-project-object-identity.md).***

**Original deferral rationale (preserved for context).** "Ring 1's basic identity model (single-project) must settle before this question's answer becomes legible. Resurfacing rule: when Ring 2 begins designing the relationship taxonomy, this question must be reopened before relationship-class enumeration is finalized, because the answer materially shapes that enumeration." This reopening happened on 2026-05-18 after the seed catalogue (Part / Requirement / Assembly) was complete and before the relationship-type ADRs.
