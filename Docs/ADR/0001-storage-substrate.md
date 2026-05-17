---
name: adr-0001-storage-substrate
status: accepted
date: 2026-05-17
supersedes: none
superseded_by: none
resolves: [OQ-0001, OQ-0002, OQ-0014]
---

# ADR/0001 — Storage Substrate for the Product Truth Model

## Status

**Accepted** — 2026-05-17. This is the first ADR; its existence also establishes the ADR mechanism itself per the Manifesto and the resolution of OQ-0010.

## Context

The Product Truth Model — AIADRA's canonical, authoritative representation of a product as a graph of Objects, relationships, parameters, requirements, events, and history — must physically live somewhere. Where it lives, and what relationship that location has to AIADRA Core, the project's Git repo, the binary artifacts, and per-developer Workspaces, is the foundational decision the rest of the project rests on.

This decision is forced into the open by three Manifesto v0.3 commitments:

1. **Principle 11: AIADRA Core hosts nothing.** The substrate cannot be a service AIADRA operates. It must work on the project's own infrastructure, using only what the project already chose (a Git host, optionally a blob store, the developer's own machine).
2. **Principle 12: Three-tier separation, on Git.** Commonspace (shared official record), Vault (binary blobs), Workspace (per-developer local environment) must each have a concrete realization. The substrate decision *is* the concrete realization in storage terms.
3. **Principle 13: AI is Workspace-native.** AI reads from the local mirror of Commonspace and syncs when staleness is unacceptable; writes only via the change-order pipeline. The substrate must make those accesses cheap, the access boundary explicit, and the AI's view honest about what is local vs. remote.

Three open questions converge here and are resolved together:

- **OQ-0001** — What is the canonical store for the Product Truth Model?
- **OQ-0002** — Within a filesystem-canonical hybrid, what is the relationship between flat current-state files and the event log?
- **OQ-0014** — Does AIADRA Core require any live inter-Workspace coordination (locks, allocators, in-flight registries)?

The Manifesto's scale ceiling — Tier L: 50–500 contributors, 10⁴–10⁵ objects, open-source EV / robotic arm scale — bounds the compatibility envelope from day one. The decision must hold up at Tier L without forcing AIADRA Core to operate infrastructure.

## Alternatives Considered

### For OQ-0001 (canonical store)

**A1. DB-canonical.** An embedded database (SQLite, DuckDB, sled, etc.) is the source of truth; YAML/JSON sidecars are exports/projections regenerated for Git review.

> **Rejected.** If the canonical DB corrupts, truth is lost — there is no humanly inspectable fallback. A binary DB file diffs poorly, reviews opaquely, blames opaquely, and forces AIADRA tooling into the read path for every contributor's basic exploration of project state. This contradicts the spirit of Principle 11 (AIADRA Core stays out of the way) and the realization of Principle 12 (Commonspace = Git remote, not a DB). The "recoverability over decades" argument is decisive: multi-decade open-source hardware projects exist; truth must survive any specific tool, including AIADRA itself.

**A2. External AIADRA-operated service.** AIADRA-hosted registry / store reachable over the network.

> **Rejected.** Directly violates Principle 11. Recorded for completeness so future contributors see the rejection on the record rather than re-proposing it.

**A3. Filesystem-canonical, no event log.** Sidecars hold current state; history is recoverable only from `git log`.

> **Rejected.** `git log` records *file changes*, not *engineering decisions*. The two are not equivalent — a parameter change, an ECR approval, a release decision carry semantic structure (who, why, against which validation outcome, with what provenance) that does not survive being represented as "this YAML file changed." Principle 10 explicitly requires structured event history; this alternative cannot deliver it.

**A4. Filesystem-canonical hybrid.** *Chosen — see Decision.*

### For OQ-0002 (event-canonicity scope, given hybrid)

**B1. Full event sourcing.** Current state is always reconstructed from events; no flat current-state files.

> **Rejected.** Schema migration becomes "rewrite history" — invasive, error-prone, scary over a multi-year project. Projection logic itself becomes load-bearing infrastructure that must be versioned, tested, and migration-safe. Storage grows monotonically. The cost-benefit is poor for engineering data: "what is the current value of `plate_thickness_mm`" should be answerable in one filesystem read, not by folding decades of events.

**B2. No event sourcing.** Events are audit trail only; flat sidecars hold current state with no enforced relationship between the two.

> **Rejected.** This is the easy path that loses everything important. Without an enforced relationship, the event log is documentation, not truth. Provenance becomes prose. AI agents cannot trust either view. The hybrid only earns its keep when the two views are forced into consistency.

**B3. Mixed with invariant.** *Chosen — see Decision.*

### For OQ-0014 (inter-Workspace coordination)

**C1. Live coordination service.** AIADRA Core operates (or requires the project to operate) a service that resolves Number allocations, advisory locks, in-flight-ECR visibility live.

> **Rejected on Principle 11 grounds.** Recorded explicitly so the rejection is on the record. The natural-sounding pull toward this option (the numbering case) is exactly the kind of quiet drift the principle guards against.

**C2. Git-host-native coordination as an *optional* UX layer.** AIADRA tools may consult the project's chosen Git host (GitHub, Gitea, etc.) for visibility into in-flight PRs as a UX nicety — but never for correctness.

> **Permitted, with constraint.** Allowed only as a non-load-bearing UX hint. The system's correctness must not depend on any host API being available, reachable, or honest. AIADRA Core ships no library that requires it.

**C3. Pure Git mechanics.** *Chosen — see Decision.*

## Decision

The Product Truth Model is realized as **filesystem-canonical artifacts in the project's Git repository, with binary blobs in a pluggable Vault and a per-clone derived acceleration cache.** Concretely:

### 1. Canonical text artifacts live in the Git repo (Commonspace)

Three classes, all plain text, all diff-able and review-able through standard Git tooling:

- **Sidecars** — hold the **current authoritative state** of each managed Object: UUID, Number, parameters, references, design intent, lifecycle state, provenance and uncertainty labels. Typically one sidecar per Object (the precise file layout / sharding strategy is deferred to OQ-0012 / Ring 1). On-disk format settled in **ADR/0002**.
- **Event log** — append-only record of *approved transitions and provenance*: object created, parameter changed, revision released, ECO approved, AI proposal accepted, validation failed. Each event carries provenance and links to the Transaction that produced it. On-disk format: **JSONL** (newline-delimited JSON), formally settled in ADR/0002. JSONL is chosen here because append-only line-mergeable text is the right shape for an event stream that lives in Git and must survive concurrent contribution.
- **Release manifests** — frozen, deterministic, content-hashable, signable records of each Release: every Object UUID and Revision in scope, every artifact hash, every validation outcome, every approval signature. On-disk format: **deterministic JSON** (sorted keys, canonical serialization), formally settled in ADR/0002. Determinism is required so the manifest itself is content-hashable and signable.

These three text layers are *Commonspace truth*. Lose them and the project is lost; corrupt them and validation surfaces the corruption immediately.

### 2. Binary blobs live in a pluggable Vault

The repository holds references **by content hash**; the Vault holds the bytes:

- **Default Vault**: **GitHub LFS**. Zero-infrastructure default; works on the free GitHub tier; sufficient for Tier S–M.
- **Pluggable alternatives** through the **Vault Adapter** contract: S3, MinIO, IPFS, NAS, project-local filesystem. Any project that outgrows LFS (Tier L; or has a self-hosted reason like compliance, internal-only) swaps the adapter without changing anything else.
- **The Vault holds blobs only.** No engineering decisions, no events, no metadata that belongs in the text layer. STEP exports, meshes, drawings, simulation outputs, renders — yes. Object definitions, requirements, change records — no.

### 3. A per-clone acceleration cache

A local derived index (default: **DuckDB**, with SQLite as a smaller-footprint alternative) supports parametric, graph, and where-used queries at interactive speed:

- **Derived** — rebuilt deterministically from the canonical text layer. The text layer is the input; the cache is the output.
- **Local** — never shared, never networked, never canonical. Each clone has its own.
- **Optional** — every operation must remain possible (if slower) by direct reading of the text layer. The cache exists for performance, not correctness. AIADRA Core must function with the cache disabled or absent.
- **Garbage-collectable** — `aiadra cache rebuild` (or equivalent) must always be safe at any time without data loss.

### 4. The sidecar / event invariant is load-bearing

Sidecars hold current authoritative state. Events record approved transitions and provenance. **If they disagree, validation fails — neither silently wins.**

The invariant is enforced at commit time by AIADRA Core's validator: folding the relevant events forward from the prior known-consistent baseline must yield a state consistent with the current sidecars. Divergence is a **hard validation error** — not silent reconciliation in either direction, not a "the event log is the source" tiebreaker, not a "the sidecar is the source" tiebreaker. Either the data is consistent or the commit is refused.

This invariant is what makes the hybrid actually defensible. Without it, the two views drift and the question "which is authoritative?" gets answered situationally by whoever writes the next line of code. With it, divergence is loud and immediate, and AI agents can rely on either view because they are forced to agree.

### 5. AIADRA Core operates no shared services

No live coordination, no central allocator, no in-flight registry, no AIADRA-operated network endpoint of any kind. All inter-Workspace coordination resolves through:

- **Git's normal mechanics** — merge conflicts on overlapping changes, rebases, PR queues.
- **The project's chosen Git host** — branch protection, PR review, signed tags. AIADRA does not provide this; the project's host does.
- **The change-order pipeline** — promoting a Workspace branch to Commonspace requires opening a PR (the ECR), attaching validation results and impact analysis, and obtaining maintainer approval (the ECO).
- **Reservation files** for project-wide unique allocations (most prominently human-readable Numbers — see OQ-0015 / future ADR/0004). Allocations are local-then-merged; conflicts resolve at PR time.

This is recorded as a *load-bearing non-decision*: we considered locks, registries, allocators (alternative C1), and rejected them. Future contributors who propose adding such mechanisms should consult this ADR before doing so.

### 6. AI access is locality-tier-aware

AI agents read against the three-tier locality hierarchy:

| Tier | Cost | Examples |
|---|---|---|
| Always-local | Free, instant | Working-tree text artifacts |
| Local-if-fetched | Free if pulled; one fetch otherwise | Other branches; LFS pointer-resolved blobs |
| Remote-only | Requires `git fetch` / `git lfs pull` | Untracked branches; never-fetched blobs |

The AI Action Protocol surface (specified in detail in Ring 2) exposes **staleness tolerance** as an explicit property of each read operation: callers declare whether stale local-mirror data is acceptable, or whether the local mirror must be synced first. Most queries tolerate staleness; a few (release manifest generation, namespace coordination) require a fresh sync. Making this distinction explicit at the API surface is required.

## Rationale

- **Recoverability.** If the cache corrupts, run `aiadra cache rebuild`. If the substrate corrupts, the project is gone. The right tradeoff is to make canonical storage a thing humans and Git already understand — plain text files in a versioned repository — and treat any acceleration layer as a derivative that can always be regenerated. Truth must survive any specific tool, including AIADRA itself.
- **GitHub-native review.** Sidecars and events in Git mean every change is visible in a PR diff, reviewable by humans without specialized tooling, blameable, signable, revertible. A binary DB makes none of this possible without parallel infrastructure that AIADRA would then have to provide.
- **No-HQ alignment.** Each of items 1 through 5 is a direct expression of Principle 11. AIADRA Core ships libraries and tools that operate on the project's own repo. The project owns its infrastructure, identity, access control, Git host, Vault backend, and compute. AIADRA Core touches none of these.
- **Three-tier alignment.** The text layer is Commonspace. The Vault is Vault. The local clone + Domain Engine sessions + cache is Workspace. The substrate decision is the realization of Principle 12 in concrete storage terms.
- **Invariant safety.** The "neither silently wins" rule is what makes the hybrid actually defensible against time and concurrency. Without it, the two views drift; with it, drift is impossible to land.
- **No coordination matches the OSS model.** Open-source hardware projects already operate through Git merge mechanics + PR review. Adding live coordination would violate Principle 11, introduce single points of failure AIADRA must operate, and fight the social model contributors already understand. Do less, not more.
- **Scale compatibility.** At Tier L the substrate remains viable: text artifacts are Git-friendly (with directory sharding, OQ-0012); blobs go via LFS or a self-hosted S3 (Vault Adapter); the cache handles query performance locally; merge mechanics scale with PR review, which projects of this size already have in place. The substrate does not preclude any of the Tier-L refinements deferred to Ring 1.

## Consequences

### Enables

- Any project on any Git host (GitHub, Gitea, Forgejo, GitLab, self-hosted) is a valid AIADRA project. No AIADRA account, no registry, no service to sign up for.
- Any contributor with a clone has full local read access to canonical truth without network calls.
- Standard Git tooling — PRs, blame, bisect, diff — becomes AIADRA review tooling for free.
- AIADRA Core can ship as a library + CLI + IDE extension. Never a service.
- The acceleration cache is fully replaceable: DuckDB today, something else tomorrow, none of it affects truth.
- The Vault backend is fully replaceable: GitHub LFS today, MinIO tomorrow, none of it affects truth.

### Costs / accepted tradeoffs

- **Cache-invalidation discipline becomes load-bearing.** The cache must remain provably consistent with the text layer; tooling and tests must enforce this.
- **Invariant validation is real work.** Folding events forward from a known-consistent baseline to verify sidecar consistency is non-trivial; the implementation must remain efficient enough that commits stay interactive at Tier M and acceptable at Tier L.
- **LFS soft limits push Tier-L projects toward S3/MinIO sooner.** GitHub LFS is sufficient for Tier S and most of Tier M; Tier-L projects will frequently swap to a self-hosted Vault. Accepted — the Vault Adapter exists for exactly this case.
- **Text-format merge conflicts grow as contributor count grows.** Format choice (ADR/0002) and directory sharding (OQ-0012 → Ring 1) must mitigate this; the substrate alone cannot.
- **Some operations require a fresh sync.** Release-manifest generation, namespace coordination, and similar high-stakes operations require `git pull` before correctness can be claimed. The staleness-tolerance API must make this explicit so callers do not assume staleness silently.

### Defers

- **ADR/0002** — canonical on-disk format for sidecars (YAML vs. KiCad-style S-expressions, pending spike). JSONL for events and deterministic JSON for manifests are settled here but the formal record lives in ADR/0002.
- **ADR/0003** — schema governance, versioning, and migration policy.
- **ADR/0004** (future) — Reservation file mechanism for Number allocation (OQ-0015), once Ring 1's Truth Model Schema settles what the file should contain.
- **Ring 1** — Truth Model Schema; directory layout and sharding (OQ-0012); event-log sharding strategy.
- **Ring 2** — AI Action Protocol locality-tier and staleness-tolerance contract specifics.

### Resolves

- **OQ-0001** — Storage substrate. Resolved by sections 1–3.
- **OQ-0002** — Event-canonicity scope. Resolved by section 4.
- **OQ-0014** — Inter-Workspace coordination semantics. Resolved by section 5.

## References

- [Manifesto](../Manifesto.md) — Principles 1, 8, 10, 11, 12, 13; Scale Targets section.
- [Glossary](../Glossary.md) — Product Truth Model, Sidecar, Event, Sidecar/event invariant, Acceleration Cache, Vault, Vault Adapter, Commonspace, Workspace, Locality tier, Staleness tolerance, Reservation file.
- [OpenQuestions](../OpenQuestions.md) — OQ-0001, OQ-0002, OQ-0014 (resolved here); OQ-0011, OQ-0012, OQ-0013, OQ-0015 (deferred).
- Discussion thread (git-ignored, local-only): `Docs/Discussions/20260517/` — Claude1–4, GPT1–4.
