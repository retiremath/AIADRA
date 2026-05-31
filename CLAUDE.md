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
- [SystemState.md](Docs/SystemState.md) — v1 updated through arc 20260531-1 — curated navigation / cache layer; fifteen active patterns; ten Coherence Checklist items; **Spec → code transition COMPLETED; Wedge-001 + Wedge-002 both implemented end-to-end; ADR/0025 production-grade runtime scope pinned; Phase 0 skeleton landed at [`aiadra-core/`](aiadra-core/)** (1,363 LOC Python + 33 schema files + 38 tests; library + thin CLI; `truth_model/` + `validation/` + `transaction/` STUB + `vault/` + `cli/` modules; read-only `aiadra validate` + `aiadra inspect` commands wired end-to-end; both verify `.aiadra/schemas.yaml` project pin before artifact reads; bidirectional sidecar/event fold invariant; per-event-type schemas with `allOf+$ref _base.schema.json` pattern via `referencing.Registry`). Three-round Claude↔Codex arc for Phase 0 skeleton (3+2+0 blockers; Codex3 signoff). §6 Recent Pattern Changes prepends arc 20260531-1 entry; Object Type catalogue still 9, named relationship-type catalogue still 14 (no spec change — Phase 0 carries existing canonical infrastructure). **No schema bundle bump** (Phase 0 materializes canonical v0.19.0 bundle; bundle stays v0.19.0; final digest `sha256:38596393b12253d19366b73322693a07f9873a84a24fe89d779dbb27e29e5111`; four SCN follow-up arcs remaining: Phase 1 W1+W2 bundled → Phase 2 F1 → Phase 3 W3 → Phase 4 F2; bumping v0.19.0 → v0.20.0 → v0.21.0 → v0.22.0 → v0.23.0). **Pattern-setting moves for future production-grade code arcs:** (a) `referencing.Registry` over `RefResolver` (no deprecation warning); (b) bidirectional sidecar/event fold invariant; (c) `verify_project_pin` BEFORE any artifact read across ALL CLI commands; (d) `allOf+$ref` + `unevaluatedProperties: false` as canonical per-event-type schema pattern; (e) schema bundle `$id` stripping. Next likely arc: Phase 1 runtime-behavior arc per ADR/0025 §1 — implements F3 atomicity (Draft-then-commit) + W1 staged-release + W2 attachment-via-Transaction; includes W1 + W2 SCNs bundled.

## Planning framework (rings)

Planning happens in concentric rings around the Product Truth Model. See [Docs/ArchitectureOverview.md](Docs/ArchitectureOverview.md) for the current five-layer model (Truth Model → Validation → AI Action Protocol → Project Control → Domain Engines) and how the Ring 0 ADRs realize it. [Docs/Discussions/20260517/Claude1.md](Docs/Discussions/20260517/Claude1.md) §3 holds the original framework, refined by the Overview. Current ring is recorded in the latest snapshot.
