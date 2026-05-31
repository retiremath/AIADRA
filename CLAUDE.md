# AIADRA

> Open-source AI-native platform for product engineering. See [Manifesto](Docs/Manifesto.md).

## At session start

1. **Read the most recent file in [Docs/Snapshots/](Docs/Snapshots/)** — it contains current state, in-flight work, and the immediate next step. Snapshots are git-ignored; if the folder doesn't exist on a fresh clone, the project is at v0 with no session-passed state.
2. **Read [Docs/SystemState.md](Docs/SystemState.md)** — curated whole-system navigation / cache layer; ~one page; surfaces the current front, active patterns, Coherence Checklist, load-bearing-now, deferred items, and recent pattern changes. NOT an authority layer (decisions live in ADRs); the cache that prevents zooming-into-one-arc-and-losing-the-big-picture.
3. **Read [Docs/Discussions/Transfer/PROTOCOL.md](Docs/Discussions/Transfer/PROTOCOL.md)** if present — Claude↔Codex coordination protocol established in arc 20260519-1. Defines arc-state-from-file-presence, INBOX regeneration discipline, dispute path, and the Codex write boundary. Git-ignored / local-only; if absent on a fresh clone, the project predates the protocol (treat as v0 coordination — Petre relays manually). Codex extension reads this same file at its session-start tick.
4. **Skim [Docs/Manifesto.md](Docs/Manifesto.md) and [Docs/Glossary.md](Docs/Glossary.md)** if any term in the snapshot or SystemState is unfamiliar.
5. **The auto-memory index** at `~/.claude/projects/d--VSCode-Work/memory/MEMORY.md` is loaded automatically and contains cross-session preferences, ownership rules, and working style — see those memories for the durable rules below in long form.

## Per-arc ritual

Adopted in arc 12. Three checkpoints to maintain whole-system coherence as the front widens:

- **Arc open** (before drafting Claude1): read [SystemState.md](Docs/SystemState.md). ~2 min.
- **Codex review**: Codex explicitly walks the local proposal against SystemState's [Coherence Checklist](Docs/SystemState.md#3-coherence-checklist). ~2 min Codex-side.
- **Arc close** (before commit): ask "Does SystemState need an update?" Update if a pattern, invariant, current front, or deferred item changed. ~5 min if yes; 30 sec if no.

Pattern-setting ADRs usually need an update; small refinements often don't.

## What this project is

AIADRA is an open-source platform where AI agents help design and engineer real products against a single deterministic source of truth. Probabilistic AI proposes and explains; the deterministic core validates and records; humans approve. See [Manifesto.md](Docs/Manifesto.md) for principles and non-goals.

This is a **long, deliberate** project. Years, not weeks. Quality, stability, and architectural coherence beat velocity.

## Working style (short)

Discuss → brainstorm → organize → plan → architect → code. No production code until the design is settled enough for the bit being coded; **spike code is allowed in parallel with design** to stress-test assumptions; production code waits. When in doubt, surface the trade-off and ask — don't barrel ahead on assumptions. (Full rule: `aiadra-working-style` memory.)

## Ownership (short)

Claude is the lead on strategy, planning, and implementation. Other AIs (Codex/ChatGPT) review and advise via files in [Docs/Discussions/](Docs/Discussions/), but Claude owns the synthesis and the rationale — engage seriously, take what improves the project, push back on what doesn't, never rubber-stamp. (Full rule: `aiadra-ownership` memory.)

## Repo layout

```
AIADRA/
├── CLAUDE.md                      # This file — session-start orientation
├── README.md
├── .gitignore
└── Docs/
    ├── Manifesto.md               # Durable project thesis + principles + non-goals (in git)
    ├── Glossary.md                # Pinned term definitions (in git)
    ├── ArchitectureOverview.md    # Layer model (in git)
    ├── TruthModelSchema.md        # Ring 1 abstract Truth Model Schema spine (S0–S3) + Promotion Rule for first-class Object Types (in git)
    ├── ArchitectureGraph.json     # On-demand visualization snapshot of the Overview (in git)
    ├── OpenQuestions.md           # Register of unresolved questions (in git)
    ├── SystemState.md             # Curated navigation / cache layer; read at arc open (in git)
    ├── ADR/                       # Architecture Decision Records (in git)
    ├── Discussions/               # Inter-AI dialogue, dated subfolders (GIT-IGNORED)
    └── Snapshots/                 # Session-end state for handoff (GIT-IGNORED)
```

## Discussion folder convention

`Docs/Discussions/YYYYMMDD/<Source><N>.md` — e.g., `Docs/Discussions/20260517/Claude2.md`, `GPT1.md`. Each session-day gets its own folder; each AI's contributions are numbered sequentially. Git-ignored — local-only.

## Snapshot folder convention

`Docs/Snapshots/YYYY-MM-DD-NN.md` — written by Claude at end of session or after milestones. Captures: status, done this session, in flight, immediate next step, open threads. Git-ignored — local-only. Schema is established in the first snapshot.

## Active document versions

Update this list when versions change.

- [Manifesto.md](Docs/Manifesto.md) — v0.3
- [Glossary.md](Docs/Glossary.md) — v0.24 (Wedge entry singular-count shorthand clarified per ADR/0023 into the minimum coherent artifact set per ADRs 0005 / 0006 / 0009, without expanding scope ambition — still Tier-S; still one Part / one Requirement / one parameter / one Transaction. Continues from v0.23 changes: new `TestExecution` Object Type entry per ADR/0022; three new execution-instance relationship-type entries `executes` / `executed_on` / `produces`; small updates to `EvidenceArtifact` / `tested_against` / `cites` framing.)
- [ArchitectureOverview.md](Docs/ArchitectureOverview.md) — v0.1
- [TruthModelSchema.md](Docs/TruthModelSchema.md) — v0.8 (Ring 1 abstract spine **complete** with S0+S1+S2+S2.5+S3 pinned; Promotion Rule for first-class Object Types pinned with 12 commitments including amended commitment 6; **S0 commitment 6 amended per ADR/0008 with cross-project identity tuple, identity-locator split, revision content hash for fixed cross-project bindings, and direct-endpoint policy**; same stale-when-overridden authority as ArchitectureOverview)
- [ArchitectureGraph.json](Docs/ArchitectureGraph.json) — v0.1 (on-demand visualization snapshot; prose Overview is master, graph drifts between refreshes)
- [OpenQuestions.md](Docs/OpenQuestions.md) — v0.8 (OQ-0007 `under-investigation` → `resolved` per arc 20260530-1: Wedge-001 spike ran end-to-end clean and friction log confirms basic Wedge architecture survived contact with reality cleanly. Continues from v0.7: OQ-0007 transitioned `accepted-as-unresolved` → `under-investigation` per ADR/0023; OQ-0016 resolved by ADR/0008 — cross-project Object identity; OQ-0015 resolved by ADR/0004 — Reservation file shape.)
- [SystemState.md](Docs/SystemState.md) — v1 updated through arc 20260531-8 — curated navigation / cache layer; fifteen active patterns; ten Coherence Checklist items; **Spec → code transition COMPLETED; Wedge-001 + Wedge-002 implemented; ADR/0025 production-grade runtime scope COMPLETE; ADR/0026 Ring 2 scope landed; Phase A + Phase B Ring 2 implementations landed** at [`aiadra-core/`](aiadra-core/) v0.7.0 + bundle v0.25.0 + 156 of 156 tests passing. Phase B (arc 20260531-8) lands `query(workspace, *, kind, filter, locality, staleness) → list[ObjectView]` covering cumulative release graph + working set per Codex1 B1 (ObjectView extended with source/revision_id/release_label defaulted fields preserving Phase A backward-compat); locality/staleness matrix per ADR/0001 §6 + ADR/0026 §4 (remote_only/must_sync always fetch; fresh_within_<N><unit> fetches if FETCH_HEAD missing/stale; local_if_fetched does "one fetch otherwise" per ADR/0001); `_run_git_fetch` bounded 30s timeout with subprocess errors all → `NetworkUnreachableError(ConnectionError)` per Codex1 B3; `FetchTooStaleError` dropped per Codex1 Q11; `_check_locality_staleness` split into `_validate`/`_enforce`; `_object_view_from_sidecar` helper per Codex1 N2; predicate-rebind avoids shadowing builtin per N1; deterministic ordering per N3. **Codex2 B1 fail-loud absorption (R3)**: removed all silent skip-on-invalid catches; corrupt working sidecars / Release Manifests / released Revisions propagate raise; defensive `continue` on missing manifest revision fields → explicit `SchemaValidationError`. `query` is AI read primitive over Product Truth NOT best-effort search index — agents need to know when substrate is corrupt; aligned with Manifesto P5 + ADR/0002 reject-loudly. **Three-round arc** (matches arc 20260531-6's cadence — both where API contract tightened across rounds). 35 new Phase B tests + 2 net Phase A test splits → 156/156. No new Pattern Catalogue row; no new Coherence Checklist item ("AIADRA Core hosts nothing" load-bearing — git fetch hits project's own origin remote; agent-initiated network only). Phase A (arc 20260531-7) lands `aiadra_core/protocol/__init__.py` (~360 LOC) as canonical Ring 2 agent-facing surface: 5 operations (inspect / validate / commit / rollback / release) + 6 type shapes (ObjectView frozen+sidecar deep-copy; ValidationReport frozen+tuple outcomes; RollbackResult frozen; CommitResult + ValidationOutcome + TransactionDraft re-exported) + 2 new exceptions (ObjectNotFoundError, ProjectPinError wrapping Phase 1 pin exceptions with `__cause__`). CLI delegation scope-limited per Codex1 B1 (cli/inspect.py 89→30 LOC; cli/validate.py 193→55 LOC with logic moved INTO protocol.validate per Codex1 N2; cmd_release + _run_draft commit through protocol.*; create/change/link/attach/add-criterion stay on transaction.operations.* until Phase C propose/modify). Locality/staleness API value classes distinguished per Codex1 B2 (invalid → ValueError; recognized non-default → NotImplementedError "Phase B"). New TransactionDraft.rollback(*, reason) clears 11 staged collections per Codex1 Q5+N5; Phase A discard-only (Phase D adds audit per ADR/0026 §9). Bundle v0.24.0 pin-only (byte-identical to v0.23.0 except _index.json+_digest.json); new MigrationStep chain entry. 26 new tests covering: module exports + negative future-op stubs guard; UUID-or-Number inspect; sidecar deep-copy independence; 5 locality/staleness value-class tests; pin-error wrapping with __cause__; sentinel commit-wrapper; rollback-clears-all-collections; CLI thin-wrapper unchanged-behavior; chain v0.19.0→v0.24.0 migration. **Two-round arc** (Codex2 signoff with one-line release_label default polish). No new Pattern Catalogue row; no new Coherence Checklist item (existing "AIADRA Core hosts nothing" load-bearing — Phase A is Python API + light CLI refactor; BYO-AI posture preserved per ADR/0026 §0). Ring 2 scope ADR (arc 20260531-6, [ADR/0026](Docs/ADR/0026-ai-action-protocol-scope.md)) — **first forward-look ADR after ADR/0025's production-arc strand closed**; scope-first ADR (no code in this arc) per ADR/0023/24/25 precedent; pins agent-facing 9-operation contract surface (inspect / query / propose / modify / simulate / validate / explain / commit-rollback / release) + 5-phase implementation roadmap (Phases A-D core + optional Phase E ecosystem RPC package OUTSIDE core per Manifesto P11) + **§0 BYO-AI posture** (AIADRA Core ships zero AI model code; Tier-1 Python + Tier-2 CLI vendor-neutral; cloud LLMs / local LLMs / deterministic scripts all call same contracts) + **mutation granularity intentionally OPEN** in Decision §2 (preserves future Ring 3 kernel-level operations + future CAD-model DSL per Petre's framing) + Phase 1 Draft-then-commit formalized as Layer 3 Transaction contract (Codex2 N1: only `commit` writes; `simulate`+`validate` are no-write functionally-identical operations differing in lifecycle position) + locality+staleness as Phase A defaulted no-op kwargs (Phase B implements non-default) + provenance enum reconciled to v0.23.0 implemented `{human_input, ai_proposal, computed_result, measured}` + transport tiering (Tier-1 Python + Tier-2 CLI in core, Tier-3 RPC like `aiadra-mcp` as SEPARATE ecosystem package) + no hosted service / no live coordination / multi-agent contention deferred + **OQ-0003 resolved** (bounded audit log at `.aiadra/audit/YYYY-MM-DD/tx_NNNN-failed-*.jsonl`; `audit-config.yaml` at `.aiadra/` ROOT remains guarded; carve-out scoped to `.aiadra/audit/` subdirectory prefix only per Codex2 B1; diagnostic-only NOT truth; default git-tracked) + **Knowledge Base / RAG explicitly DEFERRED** to future scope ADR (no `knowledge:kb_*` URI reservation today since `fact_provenance.derived_from[]` is already unconstrained array of string). **Three-round arc** (R1 design + Codex1 B1+B2+N1+N2+brainstorm; R2 ADR draft + Codex2 B1 path contradiction + N1 lifecycle wording; R3 patches + Codex3 signoff). **First arc with explicit user-led discussion turn** (`Claude1_brainstorm.md` per Petre BYO-AI / RAG / kernel-level questions before Codex review). §6 prepends arc 20260531-6 entry. No schema bundle bump (meta-decision; bundle stays v0.23.0; aiadra stays 0.5.0). No new Pattern Catalogue row; no new Coherence Checklist item ("AIADRA Core hosts nothing" is load-bearing for this ADR). Object Type catalogue still 9, named relationship-type catalogue still 14. **Next likely arc per ADR/0026 §"Sequencing"**: **Phase C** — `propose`/`modify` as first-class API entities (bundle v0.25.0 → v0.26.0; aiadra 0.7.0 → 0.8.0; estimated 3-5 rounds — biggest Ring 2 phase since it lifts `TransactionDraft` to first-class Ring 2 entity). Alternative palate-cleansers: Wedge-003 scope ADR; `derived_geometry_from` (blocked on FreeCAD Domain Adapter scope per [Manifesto P12](Docs/Manifesto.md)); Ring 3 Domain Adapter scope ADR (parallel forward-look to ADR/0026); FreeCAD adapter implementation (blocked on Ring 3); Knowledge Base / Ring 6 scope ADR (would pin the design Petre raised); housekeeping bundle (migrator integration test v0.19.0→v0.20.0 gap + stale-digest CLI handling polish + SystemState Pattern Catalogue split-out).

## Planning framework (rings)

Planning happens in concentric rings around the Product Truth Model. See [Docs/ArchitectureOverview.md](Docs/ArchitectureOverview.md) for the current five-layer model (Truth Model → Validation → AI Action Protocol → Project Control → Domain Engines) and how the Ring 0 ADRs realize it. [Docs/Discussions/20260517/Claude1.md](Docs/Discussions/20260517/Claude1.md) §3 holds the original framework, refined by the Overview. Current ring is recorded in the latest snapshot.
