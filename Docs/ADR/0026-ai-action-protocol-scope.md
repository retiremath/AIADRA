---
adr: 0026
title: Ring 2 AI Action Protocol — scope, posture, contract surface, sequencing
status: accepted
date: 2026-05-31
supersedes: []
partial-supersedes: []
authors:
  - Claude (lead synthesis)
  - Codex (review)
arc: 20260531-6
---

# ADR/0026 — Ring 2 AI Action Protocol: scope, posture, contract surface, sequencing

## Status

Accepted (arc 20260531-6). First forward-look ADR after [ADR/0025](0025-aiadra-core-runtime-scope.md)'s production-arc strand closed end-to-end across Phases 0-4 today. First ADR to pin the agent-facing contract surface — Ring 2's bootstrap.

**Companion to ADR/0025.** ADR/0025 pinned the production-grade runtime scope (Layer 1+2 + partial Layer 3); ADR/0026 pins the full Layer 3 contract surface (the AI Action Protocol) + sequenced implementation roadmap. Together they define what `aiadra-core` IS as a vendor-neutral agent-facing runtime.

**No production code in this ADR.** Follow-up Phase A-D arcs land each implementation phase against the pinned scope. Optional Phase E (ecosystem RPC package) lives outside `aiadra-core`.

**No schema bundle bump.** ADR/0026 is a meta-decision; bundle stays v0.23.0. Implementation phases carry their own bundle bumps when they land.

**Three firsts** — each pattern-setting:
1. First forward-look ADR after the ADR/0025 production-arc strand closed.
2. First explicit **BYO-AI** posture as ADR-level §0.
3. First ADR to pin contract surface for AI agents.

## Posture (§0) — AIADRA is BYO-AI

**Load-bearing for everything that follows.**

AIADRA Core ships **zero AI model code**. No bundled embeddings; no bundled LLM; no bundled retrieval. The Tier-1 Python API (`aiadra_core.protocol.*`) + Tier-2 thin CLI wrapper (`aiadra <op>`) are **vendor-neutral by design**.

Any agent calls the same contracts and gets the same answers:

| Agent class | How it consumes Ring 2 | Examples |
|---|---|---|
| **Cloud LLM with tool-use** | RPC transport (Tier-3 ecosystem package, e.g. `aiadra-mcp`) wraps Tier-1 | Claude (Anthropic API), GPT-4 / GPT-5 (OpenAI API), Gemini (Google API) |
| **Local LLM with tool-use** | Same Tier-3 RPC transport OR direct Tier-1 via Python embedding | Ollama, llama.cpp, MLX, transformers, vLLM |
| **Deterministic script** | Direct Tier-1 Python import OR Tier-2 CLI invocation | Make targets, CI, data-driven generators, classical solvers |
| **IDE / editor / human-in-the-loop** | Tier-2 CLI OR Tier-3 transport-bridge | Cursor / Claude Code / VS Code extensions, Jupyter, command line |

The core is the **deterministic gatekeeper**. AI is **interchangeable** on the other side. The core never makes outbound calls to "the AI"; the AI calls in. This is the inverse of "AI in CAD" tools that lock users to vendor APIs.

This posture is directly downstream of [Manifesto P2](../Manifesto.md) ("AI proposes; deterministic core decides") + [P11](../Manifesto.md) ("AIADRA Core hosts nothing"). It is recorded here as ADR-level posture so future Ring 2 SCNs cannot accidentally regress it.

## Context

Ring 2 was deferred in three places in Ring 0 / production scope:

- [ArchitectureOverview §Layer 3](../ArchitectureOverview.md) — "Realization status: Deferred to Ring 2."
- [ADR/0025 §10](0025-aiadra-core-runtime-scope.md) "Out of scope" item 1 — "Layer 3 AI Action Protocol".
- [ADR/0025 §"Layer 3 partial materialization"](0025-aiadra-core-runtime-scope.md) — ADR/0025 lands the `transaction/` package as a partial Layer 3 (begin/commit/rollback boundary only); the full AI surface waits.

Plus one Ring-2-captured open question:

- [OQ-0003](../OpenQuestions.md) — audit log scope for failed transactions, status `deferred-to-ring-2`. This ADR resolves it (Decision §9).

The production-arc strand for ADR/0025 just COMPLETED. The Wedge spike series (Wedge-001 + Wedge-002) is structurally answered in production-grade runtime. The natural next surface is Ring 2 — the API contracts AI agents use to interact with the now-complete Layer 1+2+partial-3 runtime.

The existing `aiadra-core` CLI (v0.5.0, bundle v0.23.0, 93/93 tests) is **already a partial Ring 2 surface**: 15+ state-changing commands wired through `TransactionDraft` (begin/validate/commit/rollback boundary per [ADR/0025 §6](0025-aiadra-core-runtime-scope.md) F3 absorption). ADR/0026 is therefore **partly retroactive** (formalize what exists) + **partly forward** (the missing `query` / `propose-as-first-class-entity` / `simulate-distinct-from-validate` / `explain` / locality+staleness / audit-log surfaces).

## Decision §1 — Arc structure + implementation sequencing

ADR/0026 is a **scope-first ADR** following [ADR/0023](0023-wedge-spike-scope-and-runtime.md) / [ADR/0024](0024-wedge-002-spike-scope.md) / [ADR/0025](0025-aiadra-core-runtime-scope.md) precedent. The ADR pins the abstract contract surface + posture + boundary with Layer 2 below and Layer 4 above + out-of-scope deferrals + 5-phase implementation sequencing roadmap. Follow-up arcs land each phase. **No production code in this ADR.**

Implementation sequencing:

1. **Phase A — Formalize existing surface as `aiadra_core.protocol`.** Mostly documentation + light refactor. CLI becomes a thin wrapper over `aiadra_core.protocol`. Locality + staleness kwargs land as defaulted no-op (per Decision §4 + B2 absorption). Rollback as explicit terminal contract per N2. MINOR bump v0.23.0 → v0.24.0; estimated 2-3 rounds.
2. **Phase B — `query` cross-Object + non-default locality/staleness behavior.** First new operation. Implements `query(kind, filter, locality, staleness)` over cumulative release graph + working set; `must_sync` calls git fetch. MINOR bump v0.24.0 → v0.25.0; estimated 3-4 rounds.
3. **Phase C — `propose` + `modify` as first-class API entities.** Lifts `TransactionDraft` from internal-only to first-class Ring 2 entity. Composable `modify` calls; `simulate` runs validate-phase hooks without commit. MINOR bump v0.25.0 → v0.26.0; estimated 3-5 rounds.
4. **Phase D — `explain` + audit log (OQ-0003 resolution).** Structured validation-error tree replaces stringly-typed errors. Failed-Transaction audit writes to `.aiadra/audit/`. Audit carve-out from dirty-worktree guard lands here. MINOR bump v0.26.0 → v0.27.0; estimated 2-3 rounds.
5. **Phase E (optional, ecosystem) — `aiadra-mcp` separate package.** Stdio JSON-RPC server (MCP or other) for AI agents. **Lives outside `aiadra-core`** per Decision §6 + §7. Not required by core; depends on whether a concrete agent-use case surfaces. Estimated 5-8 rounds standalone.

Total: **4 core phases (A-D) + 1 optional ecosystem phase.** Smaller than ADR/0025's 5-phase scope because much already exists.

## Decision §2 — Contract surface: 9 named operations

Pin the contract surface from the original [Discussions/20260517/Claude1.md §3](../Discussions/20260517/Claude1.md) + [ArchitectureOverview §Layer 3](../ArchitectureOverview.md):

| Operation | What it does | Existing implementation | Phase |
|---|---|---|---|
| `inspect(workspace, object_ref, *, locality, staleness) → ObjectView` | Single-Object current sidecar read | `aiadra inspect` CLI + `load_sidecar_validated` | A |
| `query(workspace, *, kind, filter, locality, staleness) → list[ObjectView]` | Cross-Object query | (new) | B |
| `propose(workspace, kind, ...) → TransactionDraft` | Build a Transaction draft (in-memory) | `change_parameter()` / `link_relationship()` / etc. return drafts but only via library calls | C |
| `modify(draft, mutation_spec) → TransactionDraft` | Extend a draft with additional staged mutations | Phase 1 supports `stage_sidecar` / `stage_event` on TransactionDraft; not exposed as composable API | C |
| `simulate(draft) → SimulationReport` | Run validate-phase hooks without commit | `TransactionDraft.validate()` returns outcomes — same pipeline, always-coupled with commit today | D |
| `validate(workspace) → ValidationReport` | Read-only workspace integrity check | `aiadra validate` CLI | A |
| `explain(failure, *, depth) → ExplanationTree` | Structured why-this-failed text | Stringly-typed `*Error.args[0]` today | D |
| `commit(draft) → CommitResult` / `rollback(draft) → RollbackResult` | Atomic commit + git commit OR discard draft (with optional audit entry) | `TransactionDraft.commit()` exists; explicit `rollback` is Phase D | A (commit) / D (rollback) |
| `release(workspace, object_numbers, ...) → TransactionDraft` | Multi-Object release Transaction | `release()` library + `aiadra release` CLI | A |

Rationale: even where the operation already exists, naming + documenting it as a Ring 2 contract makes the surface stable + agent-recognizable. `commit / rollback` is named as **one terminal family** (per N2 absorption + ArchitectureOverview phrasing) — `commit` is the atomic-write terminal; `rollback` is the discard terminal. Phase D's audit-log work makes `rollback` an explicit emitter; v1 is effectively "let TransactionDraft fall out of scope."

**Mutation granularity is intentionally open.** The `kind` parameter on `propose` is an open string (not a closed enum); `mutation_spec` on `modify` is structured but open-shaped; composite Transactions (multiple events per Transaction) are first-class per [Phase 1's existing design](0025-aiadra-core-runtime-scope.md). This preserves the future Ring 3 Domain Adapter contract's ability to expose kernel-level operations (e.g., FreeCAD BRep ops, sketch primitives, KiCad net assignments) via `propose(kind="<domain-specific-op>", ...)` without re-opening Ring 2's contract surface.

## Decision §3 — Transaction lifecycle = Phase 1's Draft-then-commit, formalized

[Phase 1's F3 absorption](0025-aiadra-core-runtime-scope.md) (Draft-then-commit per state-changing CLI command; git commit as atomicity boundary) IS the Layer 3 Transaction contract. Ring 2 makes this explicit:

```
begin    →  build TransactionDraft (in-memory; no writes)
modify   →  stage additional sidecar / event / reservation deltas (in-memory; no writes)
simulate →  run validation hooks against the draft; no writes; returns
            SimulationReport for agent reasoning. Idempotent; may be called
            repeatedly during draft construction.
validate →  same hooks; no writes; called in commit-intent posture (this is
            the version the agent is about to commit). Functionally identical
            to simulate; the distinction is lifecycle position not write semantics.
compare  →  agent reasons about validation results; may iterate (modify + simulate again)
human    →  approval (out-of-band; surfaced through binding layer — CLI prompt, IDE UI, etc.)
         |
         +-- commit   →  atomic write + git commit (the ONLY step that mutates durable state)
         |
         +-- rollback →  discard draft; optional audit log entry per §9
```

**Only `commit` writes** (Codex2 N1 clarification arc 20260531-6). Every other step — including `validate` — is read-only against on-disk state. The `simulate` / `validate` split reflects intent + lifecycle position (iterative reasoning vs pre-commit gate), not posture. Phase 1's existing `TransactionDraft.validate()` is the single implementation today; Phase C may split into explicit `simulate` + `validate` callables if the agent ergonomics demand, but they share the same no-write semantics.

The "human approval" step is **out-of-band** per [Manifesto P5](../Manifesto.md) — Core doesn't host a UI; the binding layer (CLI today; future MCP/stdio later) collects approval and calls `commit`. For batch / scripted / CI use, an explicit `--no-prompt` flag bypasses approval — the responsibility shifts to the caller.

## Decision §4 — Locality + staleness as explicit read kwargs (Phase A surface; Phase B behavior)

Per [ADR/0001 §6](0001-storage-substrate.md) + [ArchitectureOverview §"Locality tiers and staleness tolerance"](../ArchitectureOverview.md). Every read API (`inspect`, `query`) carries:

```python
inspect(workspace, object_ref, *, locality="always_local", staleness="any")
query(workspace, ..., *, locality="always_local", staleness="any")
```

- `locality` ∈ `{"always_local", "local_if_fetched", "remote_only"}` — controls which tier is consulted.
- `staleness` ∈ `{"any", "fresh_within_<duration>", "must_sync"}` — controls whether to sync from origin first.

**Phase A** introduces the kwarg surface with **defaulted no-op behavior** (defaults preserve current Workspace-only semantics; agents that don't pass kwargs get today's behavior). **Phase B** implements non-default behavior (`must_sync` triggers `git fetch` before read; `remote_only` rejects when offline; etc.) alongside the `query` operation.

This pins the API contract from Phase A so agents that start depending on it don't see breaking changes in Phase B. **Per Codex1 B2 absorption (arc 20260531-6):** D4 / D10 / Q3 reconciled into this single coherent path.

## Decision §5 — Provenance carried in every fact returned (existing v0.23.0 enum)

Per [Manifesto P7](../Manifesto.md). Every `ObjectView` returned by `inspect` / `query` carries:

- Per parameter: `fact_provenance.category` ∈ `{human_input, ai_proposal, computed_result, measured}` — **the v0.23.0 implemented enum is canonical for Ring 2.**
- Per attachment / per relationship (where opt-in): same `fact_provenance.category` discipline.

**No new schema work** — the v0.23.0 bundle already carries this. Ring 2 makes the API contract that `inspect` / `query` return facts with provenance intact.

When the agent calls `propose` with a parameter change, the draft event payload's `new_fact_provenance` MUST carry `category: "ai_proposal"` (or agent-attestable `"computed_result"`); the agent MUST NOT claim `human_input`. Enforcement: a Ring 2 binding-layer check; not a schema-level constraint (the schema accepts any of the 4 enum values; the agent self-attests; humans audit via the released event log).

**Per Codex1 N1 absorption:** ArchitectureOverview §Layer 3's older wording (`released_fact, computed_result, human_input, ai_inference, ai_proposal`) is reconciled here:

- `released_fact` is NOT a provenance category — it is a derived property. Any fact in a released Revision IS a `released_fact` regardless of its `fact_provenance.category` (lifecycle + Revision lookup yields this).
- `ai_inference` from the original framework MAPS to either `ai_proposal` (agent proposing for human approval) or `computed_result` (agent deterministically computing a derived value). The split was intentional in Phase 0-4; ADR/0026 preserves it.

ArchitectureOverview may be updated in a small documentation arc later per its own "stale until updated" discipline; not blocking ADR/0026.

## Decision §6 — Transport tiering (Tier-1 Python; Tier-2 CLI; Tier-3 ecosystem RPC)

Three transport tiers, all [P11](../Manifesto.md)-compliant (no hosted service):

| Tier | Surface | Location | Status |
|---|---|---|---|
| **Tier 1** | In-process Python API (`aiadra_core.protocol.*`) | `aiadra-core` package | Phase A formalization of existing pieces |
| **Tier 2** | Thin CLI wrapper (`aiadra <op>`) | `aiadra-core` package | EXISTS today; refined in Phase A to match Ring 2 contracts 1:1 |
| **Tier 3** | Stdio JSON-RPC (e.g., `aiadra serve --stdio` via MCP, OpenAI tools, or LSP-style) | **Separate ecosystem package** (e.g., `aiadra-mcp`) — NOT in `aiadra-core` | DEFERRED to optional Phase E |

Rationale for Tier 3 as a **separate package** (not in core):

- [P11](../Manifesto.md) — a long-running stdio server is borderline "hosting." Keeping it outside core preserves the principle strictly.
- **Ecosystem play** — different AI vendors will want different transports (MCP for Claude Desktop; OpenAI's tools format; LSP-style for IDEs). Letting transports live as separate packages avoids picking a winner.
- **Core stays small + auditable.**

ADR/0026 does NOT commit to MCP (Model Context Protocol) as the only future transport. Per Codex1 Q4 + brainstorm B1: "Do not commit to MCP as the only future transport in ADR/0026." Other RPC choices (OpenAI tools shape; LSP-style; custom JSON-RPC; gRPC) remain on the table for ecosystem packages.

**Tier-1 package boundary:** `aiadra_core.protocol` sub-module within `aiadra-core` (per Codex1 Q5). Avoid premature split into a separate `aiadra-protocol` package; refactor when a second binding surface needs it.

## Decision §7 — No hosted service; no live coordination

Re-affirms [Manifesto P11](../Manifesto.md). Cross-cuts Decision §6: even the optional Tier-3 stdio server lives outside core. No registries, no shared state, no validators-as-a-service. Agents call core operations against their local Workspace clone only.

This is not new — same constraint Ring 0 + Wedge spikes + ADR/0025 honored. Recorded explicitly as a Ring 2 decision so it's load-bearing for ADR/0026 reviewers + future Ring 2 SCN authors.

## Decision §8 — Multi-agent contention: deferred to scaled-tier work

For ADR/0026 v1: assume **single AI session per workspace** (single Python process or single CLI invocation). Multi-agent contention (two agents on two clones of the same workspace concurrently building drafts that conflict) is a Tier-L scaling concern per [Manifesto Scale Targets §"Defer with acknowledgement"](../Manifesto.md).

Today's mitigations carry forward unchanged:

- **Same-clone race**: [Phase 1 dirty-worktree guard](0025-aiadra-core-runtime-scope.md) (`git_repo_dirty_for_aiadra_paths()`) catches.
- **Cross-clone conflict**: Layer 4's PR/merge ceremony catches at merge time.

Future Ring 2 SCN can add explicit multi-agent contention semantics when a concrete production case surfaces.

## Decision §9 — Audit log shape (resolves OQ-0003)

**Resolves [OQ-0003](../OpenQuestions.md) — "Audit log scope for failed transactions"** with **Option 3: bounded retention**.

Location:

```
.aiadra/
├── schemas.yaml                              # project pin (existing; guarded)
├── audit-config.yaml                         # project-configurable retention (NEW; guarded)
└── audit/                                    # diagnostic logs (NEW; dirty-guard EXCLUDED)
    └── YYYY-MM-DD/
        └── tx_NNNN-failed-<short-hash>.jsonl
```

**Path discipline (Codex2 B1 absorption arc 20260531-6):** `.aiadra/audit-config.yaml` lives at the `.aiadra/` root (alongside `schemas.yaml`), NOT inside `.aiadra/audit/`. The carve-out is precisely scoped to the `audit/` subdirectory; everything else under `.aiadra/` (including `audit-config.yaml`) remains dirty-guarded as managed configuration.

Each `tx_NNNN-failed-*.jsonl` carries:

- `transaction_id`, `attempted_at`, `agent_ref` (optional)
- **Proposed events** (the events that would have been appended if commit had succeeded)
- **Validation errors** (structured per Phase D's `ExplanationTree` shape — paves the way for `explain`)
- **Reason classification**: `schema_validation` / `profile_violation` / `fold_inconsistency` / `binding_violation` / `release_consistency` / `other`

**Retention policy** — project-configurable via `.aiadra/audit-config.yaml` (defaults: `max_entries_per_agent: 100`, `max_age_days: 30`, `max_total_mb: 50`). Cleanup runs on-demand via `aiadra audit-prune` (not automatic on each Transaction).

**CRITICAL: audit log is diagnostic, NOT truth.**

- Does NOT participate in the [sidecar/event fold invariant](0001-storage-substrate.md).
- Is NOT bundle-validated.
- Agents MUST NOT use audit content to reason about Truth Model state.

Exists for traceability + AI-behavior review per [Manifesto P7](../Manifesto.md). Failed Transactions never reach canonical product truth per the [Glossary "Transaction" entry](../Glossary.md); the audit log is the visible-side-channel that addresses OQ-0003's "this carries useful information for traceability and AI-behavior review."

**Per Codex1 B1 + Codex2 B1 absorption (arc 20260531-6) — dirty-worktree guard carve-out:**

> The `.aiadra/audit/` subdirectory is excluded from the [Phase 1 dirty-worktree guard](0025-aiadra-core-runtime-scope.md) (`git_repo_dirty_for_aiadra_paths()`). Audit files may be git-tracked per project policy (default: tracked, for PR visibility of AI behavior); **uncommitted audit files do NOT block canonical Transactions**. The `.aiadra/audit-config.yaml` file at the `.aiadra/` root (NOT inside the `audit/` subtree) remains managed configuration and stays guarded — same posture as `.aiadra/schemas.yaml`.

Implementation: at the `aiadra_managed_prefixes` check in `boundary.py::git_repo_dirty_for_aiadra_paths()`, add a sub-path exclusion for the `.aiadra/audit/` PREFIX specifically (everything else under `.aiadra/` — including `.aiadra/audit-config.yaml` at the root and `.aiadra/schemas.yaml` — remains guarded). Lands in Phase D when audit log goes live; ADR/0026 pins the contract.

Per Codex1 Q8: git-tracked-by-default is acceptable only because the B1 carve-out neutralizes the dirty-guard conflict. Project can `.gitignore .aiadra/audit/` for local-only retention if preferred.

## Decision §10 — Out of scope (explicit deferrals)

The following are **explicitly NOT** addressed by ADR/0026; each has its own future arc:

1. **Knowledge Base / accumulated design wisdom / RAG infrastructure** — Ring 2 defines how agents interact with Product Truth. A future scope ADR will decide whether project-local and cross-project Knowledge entries exist, how they are versioned, and how agents retrieve them. AIADRA Core will NOT host the knowledge service. Per Codex1 brainstorm B4: Knowledge Base is its own concern — not a Domain Adapter, not a Ring 2 sub-operation. Per brainstorm B5: project-local Knowledge first, cross-project later when the future ADR lands.
2. **`knowledge:kb_*` URI prefix reservation in `fact_provenance.derived_from`** — deferred. Current schema (v0.23.0) `fact_provenance.derived_from[]` is `array of string` with no URI-scheme constraint at the type level; future Knowledge Base URIs slot in without a bundle bump. Per Codex1 brainstorm B3: no reservation needed today.
3. **Kernel-level Ring 3 Domain Adapter operations** (e.g., FreeCAD BRep ops; KiCad net assignments) — Ring 3 territory. Ring 2 contracts are intentionally agnostic about mutation granularity / structure / domain semantics so Ring 3 can later extend the surface with kernel-level operations via `propose(kind="<domain-specific-op>", ...)` without re-opening Ring 2's contract surface. (Petre's framing: "AI shouldn't push CAD buttons; needs to interact at the internal model level in Python or possibly a CAD-specific DSL. Don't lock ourselves out.")
4. **CAD-model DSL** (a textual or graphical language compiled to AIADRA Transactions) — if ever designed, lives ABOVE Ring 2 and compiles to Ring 2 contract calls. The 9-operation surface is intentionally expressive enough that any future DSL just emits sequences of Ring 2 calls; ADR/0026 does not need to know the DSL exists to be compatible with it.
5. **Specific RPC/transport choice** (MCP, OpenAI tools, LSP-style, gRPC, etc.) — Tier-3 ecosystem packages are free to choose. ADR/0026 does NOT commit to MCP as the only future transport.
6. **Multi-agent live contention** — Tier-L scaling concern per Manifesto Scale Targets. Same-clone race handled by dirty-worktree guard; cross-clone conflict handled by Layer 4 PR/merge.
7. **Hosted AI inference; embedding indices; vector databases** — agent-side concerns. Per §0 BYO-AI posture: core ships zero AI code. Embedding indices live wherever the agent lives.
8. **New ring numbering** (e.g. "Ring 6: Knowledge & Learning") — discussion-time naming only; not committed by this ADR. The future Knowledge Base scope ADR can pin a ring or layer number if it wants one.
9. **ArchitectureOverview document update for the reconciled provenance enum** — small documentation arc; not blocking. ArchitectureOverview's "stale until updated" frontmatter discipline applies.

## Disposition of non-absorbed items from brainstorm + Codex review

Auditable per [ADR/0025 disposition-table pattern](0025-aiadra-core-runtime-scope.md):

| Item | Source | Disposition |
|---|---|---|
| BYO-AI as load-bearing ADR section | brainstorm B1 | Absorbed as §0 Posture (above Decision §1) |
| Knowledge Base / RAG scope | brainstorm B2 + Codex1 brainstorm response | Deferred to future scope ADR (§10 item 1) |
| `knowledge:kb_*` URI reservation | brainstorm B3 + Codex1 | NOT reserved today (§10 item 2) — current schema accommodates without action |
| Knowledge Base as Domain Adapter | brainstorm B4 + Codex1 | Rejected (§10 item 1) — Knowledge is meta-design memory, not engineering content sync |
| Project-local vs cross-project Knowledge sequencing | brainstorm B5 + Codex1 | Recorded as future-ADR sequencing hint (§10 item 1) |
| Kernel-level Ring 3 futureproofing | Petre direct framing | Absorbed as Decision §2 intentional-openness clause + §10 item 3 |
| CAD-model DSL futureproofing | Petre direct framing | Absorbed as §10 item 4 |
| Audit dirty-worktree carve-out | Codex1 B1 | Absorbed in Decision §9 |
| Locality / staleness phase placement | Codex1 B2 | Absorbed in Decision §4 (Phase A surface; Phase B behavior) |
| Provenance enum reconciliation | Codex1 N1 | Absorbed in Decision §5 |
| `rollback` explicit terminal | Codex1 N2 | Absorbed in Decision §2 ("commit / rollback" as one terminal family) |

## Alternatives rejected

- **(i) Build Ring 2 as a full code arc now, no scope ADR.** Pattern from ADR/0025: substantial design surfaces deserve scope-first ADRs that pin direction + sequencing before code. Skipping the scope ADR risks rework + scope creep in implementation rounds.
- **(ii) Make MCP the canonical Tier-3 transport in ADR/0026.** Picks a winner before the ecosystem speaks. Per Codex1 Q4: keep Tier-3 vendor-neutral; let ecosystem decide.
- **(iii) Fold Knowledge Base / RAG into Ring 2 as a `query_knowledge` 10th operation.** Significant scope creep on what is already a multi-arc scope ADR; couples Knowledge schema design (we haven't done) to Ring 2 contract design (we are doing).
- **(iv) Reserve `knowledge:kb_*` URI prefix preemptively.** Per Codex1 brainstorm B3: don't reserve in a vacuum. Current schema preserves optionality without reservation.
- **(v) Make `commit` and `rollback` two separate contract families.** Per Codex1 N2 preferred wording: one terminal family with two endpoints matches ArchitectureOverview phrasing + is cleaner mental model for agents.
- **(vi) Build hosted AI inference / shared embedding service as part of core.** Violates [Manifesto P11](../Manifesto.md). Agent-side concern; lives wherever the agent lives.
- **(vii) Track failed-Transaction events in canonical `events.jsonl` with `transaction_status: failed`.** Per Codex1 Q7: separate `.aiadra/audit/` keeps canonical event replay clean; audit is diagnostic not truth.

## Consequences

**For agents (cloud, local, deterministic):**

- Stable, vendor-neutral contract surface. Any agent that can call Python or spawn a CLI subprocess can drive AIADRA.
- Provenance discipline enforced at the binding layer — agents that claim `human_input` for AI-driven changes violate the contract.
- Locality + staleness are first-class read properties (Phase A surface; Phase B behavior).

**For ecosystem (Tier-3 RPC packages):**

- The door is open for MCP / OpenAI tools / LSP-style / custom RPC bindings as separate ecosystem packages.
- Each transport-binding package depends on `aiadra-core` and translates the chosen RPC to Tier-1 Python calls.
- Core stays small + auditable.

**For Ring 3 (Domain Adapter contract, future):**

- Ring 2 contracts are intentionally agnostic about mutation granularity, structure, and domain semantics. Ring 3's kernel-level operations slot in via `propose(kind="<domain-specific-op>", ...)` without re-opening Ring 2.
- Per Decision §2 intentional-openness clause: future BRep ops, sketch primitives, net assignments, etc., compose with the existing Transaction model.

**For ADR/0025 production-arc strand:**

- ADR/0026 carries the bundle progression forward: v0.23.0 → v0.24.0 (Phase A) → v0.25.0 (Phase B) → v0.26.0 (Phase C) → v0.27.0 (Phase D).
- aiadra version follows: 0.5.0 → 0.6.0 → 0.7.0 → 0.8.0 → 0.9.0 (or as Codex review per-phase recommends).
- 9-operation contract surface is stable across all four phases; only behavior + audit infrastructure grow per phase.

**For Knowledge Base (deferred):**

- No today-action. Current schema preserves optionality. Future scope ADR (call it ADR/0027 or "Ring 6 scope ADR") pins design when concrete agent-use cases surface.

## Sequencing

Phase A directly after ADR/0026 closes is the recommended natural next step (per Codex1 Q12). Alternative palate-cleanser arcs (Wedge-003 scope ADR; `derived_geometry_from` relationship type; housekeeping bundle — migrator integration test gap + stale-digest CLI polish + SystemState Pattern Catalogue split-out) remain plausible and require user prioritization.

Phase E (optional ecosystem RPC package) does NOT belong in the `aiadra-core` arc sequence — it lives in a separate package + repo per Decision §6 + §7. Triggered when a concrete agent-use case wants RPC.

## References

- [Manifesto](../Manifesto.md) — Principles P2, P5, P7, P11, P13.
- [ArchitectureOverview §Layer 3](../ArchitectureOverview.md) — original 9-contract surface; deferred-to-Ring-2 status.
- [ADR/0001 §6](0001-storage-substrate.md) — locality tiers and staleness tolerance.
- [ADR/0023](0023-wedge-spike-scope-and-runtime.md), [ADR/0024](0024-wedge-002-spike-scope.md), [ADR/0025](0025-aiadra-core-runtime-scope.md) — scope-first ADR precedents.
- [ADR/0025 §6 (F3 absorption)](0025-aiadra-core-runtime-scope.md) — Draft-then-commit; the existing partial Layer 3.
- [ADR/0025 §"Layer 3 partial materialization"](0025-aiadra-core-runtime-scope.md) — explicit hand-off to Ring 2.
- [Discussions/20260517/Claude1.md §3 Ring 2](../Discussions/20260517/Claude1.md) — original 9-contract framework.
- [OQ-0003](../OpenQuestions.md) — audit log scope, resolved by Decision §9.
- [arc 20260531-6](../Discussions/20260531/20260531-6/) — Claude1 proposal; Claude1_brainstorm Petre-initiated discussion; Codex1 review.
