# AIADRA

> Open-source AI-native platform for product engineering. See [Manifesto](Docs/Manifesto.md).

## At session start

1. **Read the most recent file in [Docs/Snapshots/](Docs/Snapshots/)** — it contains current state, in-flight work, and the immediate next step. Snapshots are git-ignored; if the folder doesn't exist on a fresh clone, the project is at v0 with no session-passed state.
2. **Skim [Docs/Manifesto.md](Docs/Manifesto.md) and [Docs/Glossary.md](Docs/Glossary.md)** if any term in the snapshot is unfamiliar.
3. **The auto-memory index** at `~/.claude/projects/d--VSCode-Work/memory/MEMORY.md` is loaded automatically and contains cross-session preferences, ownership rules, and working style — see those memories for the durable rules below in long form.

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
- [Glossary.md](Docs/Glossary.md) — v0.7 (Promotion Rule catalogue verdicts in *Object*; *Part* entry per ADR/0005; *Requirement* entry per ADR/0006)
- [ArchitectureOverview.md](Docs/ArchitectureOverview.md) — v0.1
- [TruthModelSchema.md](Docs/TruthModelSchema.md) — v0.7 (Ring 1 abstract spine **complete** with S0+S1+S2+S2.5+S3 pinned; Promotion Rule for first-class Object Types pinned 2026-05-18 with 12 commitments; **commitment 6 amended to decouple governance ceremony from bundle bump class**; catalogue work continues with Requirement next; same stale-when-overridden authority as ArchitectureOverview)
- [ArchitectureGraph.json](Docs/ArchitectureGraph.json) — v0.1 (on-demand visualization snapshot; prose Overview is master, graph drifts between refreshes)
- [OpenQuestions.md](Docs/OpenQuestions.md) — v0.4

## Planning framework (rings)

Planning happens in concentric rings around the Product Truth Model. See [Docs/ArchitectureOverview.md](Docs/ArchitectureOverview.md) for the current five-layer model (Truth Model → Validation → AI Action Protocol → Project Control → Domain Engines) and how the Ring 0 ADRs realize it. [Docs/Discussions/20260517/Claude1.md](Docs/Discussions/20260517/Claude1.md) §3 holds the original framework, refined by the Overview. Current ring is recorded in the latest snapshot.
