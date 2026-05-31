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
- [SystemState.md](Docs/SystemState.md) — v1 updated through arc 20260531-5 — curated navigation / cache layer; fifteen active patterns; ten Coherence Checklist items; **Spec → code transition COMPLETED; Wedge-001 + Wedge-002 implemented; ADR/0025 production-grade runtime scope COMPLETE — all six friction items (F1+F2+F3+W1+W2+W3) absorbed end-to-end across Phases 0-4 at [`aiadra-core/`](aiadra-core/)** (cumulative ~3,800 LOC new Python; **bundle progression v0.19.0 → v0.20.0 → v0.21.0 → v0.22.0 → v0.23.0**; 93 of 93 tests passing; aiadra version 0.5.0). Phase 4 F2 SCN (arc 20260531-5) implements `threshold_expression` canonical primitive on Requirement `acceptance_criterion` per [ADR/0025 §5](Docs/ADR/0025-aiadra-core-runtime-scope.md): new `_shared/acceptance_criterion_item.schema.json` (Codex1 N2 absorption — canonical criterion item shape with optional `threshold_expression: {parameter_ref, comparison_op, value, unit}` all REQUIRED inside; numeric-only); Requirement schema's `acceptance_criterion.items` `$ref`s the shared schema. New `event/requirement_changed.schema.json` — **added-only per Codex1 B1 preferred path** (`acceptance_criterion_delta.added` with `additionalProperties: false` rejecting `updated`/`removed`; `added.items` `$ref` the shared canonical criterion). Both fold paths (read-side `validation/fold.py` + proposed-state `transaction/boundary.py::_validate_proposed_fold`) append with duplicate-id rejection — matching Phase 2's dual-fold discipline. New `validate_final_stage_threshold_checks` in `validation/release.py` (~175 LOC) walks cumulative release graph; Layer-2 hard-fail at release on unit mismatch (Codex2 N2 from arc 20260530-4); FAIL outcome + claim (satisfies whole / verifies whole / verifies criterion-specific via `endpoints[0].fact_ref` per W3) → `ReleaseConsistencyError`. Hooked in `release()` `if final_stage:` parallel to vv_chain + cardinality. New `add_acceptance_criterion` Transaction op + `cmd_add_acceptance_criterion` CLI with threshold quartet gate. New `MigrationStep("0.22.0", "0.23.0", ...)` in `REGISTERED_STEPS`; CLI `migrate --to-bundle {0.20.0|0.21.0|0.22.0|0.23.0}`. 20 new Phase 4 F2 tests (+2 over D10 planned 18). **Two-round Phase 4 arc** (Codex2 signoff; matches Phase 2+3 cadence). §6 Recent Pattern Changes prepends arc 20260531-5 entry. Object Type catalogue still 9, named relationship-type catalogue still 14. **NO remaining SCN arcs from ADR/0025.** New-front candidates (user-prioritized): Wedge-003 scope ADR; `derived_geometry_from` (awaits FreeCAD Domain Adapter scope per [Manifesto P12](Docs/Manifesto.md)); Ring 2 AI Action Protocol; Ring 3 Domain Adapter contract; FreeCAD adapter implementation; migrator integration test follow-up (v0.19.0 → v0.20.0 gap); inherited stale-digest migrator CLI handling polish; SystemState Pattern Catalogue split-out.

## Planning framework (rings)

Planning happens in concentric rings around the Product Truth Model. See [Docs/ArchitectureOverview.md](Docs/ArchitectureOverview.md) for the current five-layer model (Truth Model → Validation → AI Action Protocol → Project Control → Domain Engines) and how the Ring 0 ADRs realize it. [Docs/Discussions/20260517/Claude1.md](Docs/Discussions/20260517/Claude1.md) §3 holds the original framework, refined by the Overview. Current ring is recorded in the latest snapshot.
