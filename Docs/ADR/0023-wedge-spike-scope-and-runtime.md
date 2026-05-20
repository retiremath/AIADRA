---
name: adr-0023-wedge-spike-scope-and-runtime
status: accepted
date: 2026-05-20
supersedes: none
superseded_by: none
resolves: []
---

# ADR/0023 — Wedge spike scope, runtime, and posture

## Status

**Accepted** — 2026-05-20. First code-producing-direction ADR — the meta-decision that pins **scope + runtime + posture + repo layout + fixture strategy + CI / packaging posture + deliverable shape** for the **Wedge-001 spike implementation**, without writing any spike code in this arc. The actual spike implementation lands in a separate follow-up arc that references ADR/0023's pinned scope.

After [ADR/0022](0022-test-execution-model.md), the spec-arc strand for Ring 1 catalogue work substantively closes (nine Object Types; fourteen named relationship types operationally complete except `derived_geometry_from`; V&V framework operationally executable end-to-end against schema). ADR/0023 is the natural close of the spec-arc strand and the entry into the spec → code transition Petre flagged at session open as "the bigger posture shift; worth a fresh discussion at session start."

**Six pinned decisions** (each is the recommended option from Claude1 / [Codex1 Requested Feedback agreement](../Discussions/20260520/20260520-2/Codex1.md) / [Codex2 sign-off](../Discussions/20260520/20260520-2/Codex2.md)):

1. **Arc structure** — scope-first ADR; spike code in follow-up arc (Decision §1).
2. **Wedge scope** — basic shape per ADRs [0005](0005-object-type-part.md) / [0006](0006-object-type-requirement.md) / [0009](0009-relationship-type-satisfies.md) (clarifies the old Glossary singular-count shorthand into the minimum coherent artifact set, without expanding scope ambition — still Tier-S; still one Part / one Requirement / one parameter / one Transaction) (Decision §2).
3. **Runtime** — Python 3.11+ for spike only; **not a production runtime commitment** (Decision §3).
4. **Posture** — explicit throwaway spike per [Glossary "Spike"](../Glossary.md) (Decision §4).
5. **Repo layout** — `spikes/wedge-001/` at AIADRA repo root; NOT git-ignored; in-repo (Decision §5).
6. **Fixture strategy** — reuse ADR worked-example UUIDs / Numbers as **spike-local demo records** for tight spec↔code anchor; Numbers are per-project namespaces per [ADR/0004](0004-number-allocation.md) so the reuse does not reserve those Numbers against future real project data (Decision §6).

Plus three auxiliary decisions: **no CI for spike** (Decision §7); **CLI + checked-in fixtures + ≤2-page friction log** as deliverable shape with the friction log as primary deliverable (Decision §8); **explicit deferrals** carry forward all the surface ADR/0023 deliberately does NOT exercise (V&V framework instrumentation; Component / SoftwareModule / Drawing; cross-project; Domain Engine; acceleration cache; production-grade `aiadra-core`; Vault Adapter; failed-transaction audit retention per [OQ-0003](../OpenQuestions.md)) (Decision §10).

**Partial clarification of [Glossary "Wedge"](../Glossary.md) entry's singular-count shorthand** ("one sidecar / one event-log entry") into the minimum coherent artifact set per ADRs 0005 / 0006 / 0009. Glossary v0.23 → v0.24. Manifesto framing of the Wedge stays unchanged.

**Reopens [OQ-0007](../OpenQuestions.md)** (Wedge scope adequacy) per its `accepted-as-unresolved` resurfacing rule ("re-open at end of Ring 4"). OQ-0007 status transitions to `under-investigation` on ADR/0023 acceptance; `resolved` waits until the spike has run and the friction log has been reviewed.

**No schema bundle bump.** ADR/0023 is a meta-decision (scope + posture); does NOT modify any schema. Bundle stays v0.19.0.

## Context

Discussion trail in [`Docs/Discussions/20260520/20260520-2/`](../Discussions/20260520/20260520-2/). [Codex1](../Discussions/20260520/20260520-2/Codex1.md) produced three blockers and three non-blockers; all three blockers tightly scoped (Release Manifest scope crosses ADR/0001 + ADR/0009 boundaries; rejected-transaction audit-log pre-empts OQ-0003; "basic Wedge verbatim" conflicts with the coherent artifact set requiring partial Glossary clarification) and structurally addressed in [Claude2](../Discussions/20260520/20260520-2/Claude2.md); [Codex2](../Discussions/20260520/20260520-2/Codex2.md) signed off without further objection. Codex1's eight feedback-requested decisions all converged on round 1; no model-level reopens.

Three pressures converge on the spec → code transition:

1. **The spec needs to meet reality.** Twelve spec arcs (`20260518-12` + `20260519-{1..11}` + `20260520-1`) since 2026-05-18 land elegant invariants — sidecar/event invariant, attachment lineage chains, criterion-level addressing, execution-instance binding semantics — but no line of code yet implements them. Per [OQ-0007](../OpenQuestions.md) current instinct (*"Build it, evaluate, expand if necessary"*), the Wedge is the first real friction-finder. Until it runs, every invariant is hypothetical.
2. **The Wedge scope was pinned at Manifesto v0.3 (2026-05-17), pre-dating the V&V framework.** The basic Wedge shape (Part + parameter + Requirement + sidecar + event + Transaction + validation + Release Manifest) was correct for the substrate-and-format-only world of [ADR/0001](0001-storage-substrate.md) + [ADR/0002](0002-canonical-format.md) + [ADR/0003](0003-schema-governance.md). The V&V framework (TestProcedure / EvidenceArtifact / TestExecution + nine V&V-family relationship types) lands a much larger surface that COULD be Wedge-exercised. Pressure: should the Wedge expand to instrument what was spent two days building? Alternatives §A walks the cut.
3. **First code-producing arc sets precedent.** Whatever runtime, repo layout, posture, and CI we pick will anchor subsequent spike / implementation arcs unless reopened. Methodology-arc-scale. The Manifesto framing of "Spike" (per [Glossary "Spike"](../Glossary.md) — *"Throwaway prototype code written to test a design assumption. Allowed in any Ring; explicitly not the same as production implementation."*) is a strong prior; this arc operationalizes it for the first time.

[OQ-0007's resurfacing rule applies](../OpenQuestions.md): *"Build it, evaluate, expand if necessary. No early decision required. Re-open this entry at end of Ring 4."* The Ring 4 boundary is reached; OQ-0007 is reopening here.

## Pre-declared constraints honored

| Constraint | Source | Disposition |
|---|---|---|
| Wedge scope adequacy resurfacing at end of Ring 4 | [OQ-0007](../OpenQuestions.md) | Honored — OQ-0007 status transitions to `under-investigation` per Consequences. |
| Manifesto framing of the Wedge (smallest end-to-end vertical slice; exercises all architectural layers; Tier-S validation) | [Manifesto §"Scale targets"](../Manifesto.md) + [Manifesto P1-13](../Manifesto.md) | Honored — ADR/0023 implements the Manifesto framing in code via spike. No Manifesto edits. |
| Glossary "Wedge" entry's singular-count shorthand ("one sidecar / one event-log entry") | [Glossary "Wedge"](../Glossary.md) | **Partial clarification.** The singular-count shorthand predated ADRs [0005](0005-object-type-part.md) / [0006](0006-object-type-requirement.md) / [0009](0009-relationship-type-satisfies.md) pinning the concrete artifact mechanics. ADR/0023 clarifies the shorthand into the minimum coherent artifact set (two sidecars at working state — Part + Requirement; five distinct event types — `part_created` / `requirement_created` / `relationship_created` / `parameter_changed` / `*_released`; immutable Revision copies at release; one Release Manifest) without expanding scope ambition. Glossary v0.23 → v0.24 carries the edit. |
| Acceleration cache is derived / local / rebuildable / **never canonical** | [ADR/0001 §3](0001-storage-substrate.md) | Honored — Wedge-001 Release Manifest explicitly does NOT pin acceleration-cache state per Decision §2 (per [Codex1 B1 absorption](../Discussions/20260520/20260520-2/Claude2.md)). |
| `satisfies` source-anchored on Part-side `relationship:` namespace; release materialization happens INSIDE the source Object's Revision record | [ADR/0009 §5 + §"Eventability"](0009-relationship-type-satisfies.md) | Honored — Wedge-001 Release Manifest pins the materialized `satisfies` record INSIDE the Part Revision; does NOT pin a standalone relationship-Revision artifact (no such artifact exists for `satisfies`) per Decision §2 (per [Codex1 B1 absorption](../Discussions/20260520/20260520-2/Claude2.md)). |
| Failed-transaction audit retention `deferred-to-ring-2` | [OQ-0003](../OpenQuestions.md) | Honored — Wedge-001 rejected transactions produce NO canonical Product Truth artifact AND NO checked-in audit-log artifact; validation failure prints to stdout only; explicit deferral entry in Decision §10 (per [Codex1 B2 absorption](../Discussions/20260520/20260520-2/Claude2.md)). |
| AIADRA YAML Profile strict subset rules (YAML 1.2 only; no anchors / aliases / merge keys / custom tags; duplicate-key rejection; quoted ambiguous scalars; JSON Schema validation at every read; token-level linting where schema cannot catch post-parse) | [ADR/0002 §"AIADRA YAML Profile"](0002-canonical-format.md) | Honored — Wedge-001 acceptance criteria explicitly name the AIADRA YAML Profile checks per Decision §3 (per [Codex1 N1 absorption](../Discussions/20260520/20260520-2/Claude2.md)). `ruamel.yaml` is a tool, not the Profile; the Profile checks are implemented at spike grade on top. |
| Number allocation per-project per Reservation file | [ADR/0004 §6](0004-number-allocation.md) | Honored — Wedge-001 reused fixture identities (`P-000058`, `REQ-000058`) are **spike-local demo records** in the spike's Reservation files; per ADR/0004 Numbers are per-project namespaces, so the reuse does NOT reserve those Numbers against any future real project's data (per [Codex1 N3 absorption](../Discussions/20260520/20260520-2/Claude2.md)). |
| AIADRA Core hosts nothing | [Manifesto P11](../Manifesto.md) | Honored — Wedge-001 runs locally only; no CI; no published packages; no registry / instrument coordinator / hosted federation introduced. The deferred audit-log subsystem (OQ-0003) is explicitly NOT introduced. |
| Transaction-atomicity per ADR/0004 §6 (sidecar + event + Reservation as one coherent commit) | [ADR/0004 §6](0004-number-allocation.md) | Honored — Wedge-001's `create-part` / `create-requirement` commands implement the Transaction-atomic coherent commit per Decision §2 / §10 acceptance criteria. |

## Alternatives Considered

### A. Wedge scope (load-bearing)

**A1. Basic Wedge — minimum coherent artifact set per ADRs 0005 / 0006 / 0009, clarifying the Glossary Wedge shorthand.** *Chosen — Decision §2.*

> Exercises Layers 1 (Truth Model — Part sidecar + Requirement sidecar + event log) + 2 (Validation — schema + sidecar/event invariant + satisfies-check) + 3 (AI Action Protocol — one Transaction lifecycle: begin → modify → validate → commit) + 4 (Project Control — Release Manifest). Does NOT exercise V&V framework, Domain Engines, cross-project, or Component / SoftwareModule / Drawing surface. **Argument for:** smallest validating slice; matches Glossary definition (with the singular-count shorthand clarified per Decision §2 + Consequences); [OQ-0007](../OpenQuestions.md)'s *"build it, evaluate, expand if necessary"* framing is satisfied by basic scope; friction found in basic shape is friction that ALL future Wedges inherit. [Codex1 agreed](../Discussions/20260520/20260520-2/Codex1.md): "*V&V-instrumented Wedge should be Wedge-002 after the basic loop exposes substrate friction.*"

**A2. V&V-instrumented Wedge — basic + TestProcedure + TestExecution + EvidenceArtifact + V&V relationships exercised end-to-end.**

> **Rejected for seed.** Would validate the full ADR/0019-22 surface in a single spike. **Argument against:** substantially larger spike (5+ Object Type sidecars vs 2; 6+ relationship types vs 1; full chain *Part `tested_against` TestProcedure ←`executes`← TestExecution →`produces`→ EvidenceArtifact + `verifies` + `cites`* must round-trip). Friction discovery is dominated by basic-shape issues; V&V wiring is layered on top once basic round-trips successfully. Defer to Wedge-002 if basic surfaces interesting friction patterns first.

**A3. Micro-Wedge — Part sidecar + event + validation only; no Requirement, no satisfies, no Release Manifest.**

> **Rejected.** Skips Layer 3 (AI Action Protocol — no Transaction) and Layer 4 (Project Control — no Release Manifest). Does not validate the sidecar/event invariant under release-time materialization. Wedge-001 must include a release event because [Manifesto P10](../Manifesto.md) (*"if they disagree, validation fails"*) is exercised only at release-time materialization for the basic shape. Going smaller eliminates the load-bearing invariant test.

**A4. Domain-Engine-touched Wedge — basic + FreeCAD Domain Adapter sketch + STEP export.**

> **Rejected.** Crosses into Ring 3 (Domain Adapter contract) and Ring 4 (Domain Engine modifications), neither of which has any landed ADR yet. Out of scope per [Manifesto P12](../Manifesto.md) if it requires FreeCAD modifications (which the Adapter does per [OQ-0004 / OQ-0005](../OpenQuestions.md)). Defer to a Wedge-003+ once basic round-trips and the Adapter contract is settled.

### B. Runtime / language for the spike

**B1. Python (3.11+).** *Chosen — Decision §3.*

> Spike velocity is the dominant constraint. Python has mature YAML tooling (`ruamel.yaml` — known good for round-tripping comments + key order, which the AIADRA YAML Profile requires per [ADR/0002](0002-canonical-format.md)); mature JSON Schema tooling (`jsonschema` 4.x, Draft 2020-12 per [ADR/0003](0003-schema-governance.md)); minimal ceremony to a runnable CLI; nearly every developer has a 3.11 interpreter installed. **Throwaway-friendly:** if friction surfaces that demands a different runtime for production, the spike's Python implementation is sacrificed without regret. **Production posture:** spike does NOT lock the production runtime; production-grade `aiadra-core` may be Rust / TS / Go per separate ADR after Wedge-001 finds friction. [Codex1 agreed](../Discussions/20260520/20260520-2/Codex1.md): "*Python is the right spike runtime ... This should not constrain production runtime.*"

**B2. Rust.**

> **Rejected for spike.** Matches Tier-L scale ambitions per Manifesto §"Scale targets"; native binary deploy; strong type system. **Argument against:** higher spike-velocity cost; YAML tooling less mature for the AIADRA YAML Profile's strict subset; higher learning curve. Spike posture (throwaway) does not benefit from Rust's correctness guarantees — the goal is finding friction in the SPEC, not in the implementation. Reopen the runtime question for production after Wedge-001 evaluates.

**B3. TypeScript / Node.**

> **Rejected for spike.** Matches the VSCode extension surface per [Manifesto P13](../Manifesto.md); JSON Schema tooling extremely mature (ajv). **Argument against:** YAML tooling less reliable on strict subsets; JS/TS engineers may not be the AIADRA contributor demographic (mechanical / hardware engineers more often Python-fluent). Reopen for VSCode extension specifically when that arc lands.

**B4. Go.**

> **Rejected for spike.** Mid-tier velocity; good CLI ergonomics but less expressive type system than Rust / TS. No strong differentiator for spike scope.

**B5. Defer the runtime question — open Wedge-001 with no language commitment.**

> **Rejected.** The scope-first ADR exists precisely to pre-pin these decisions.

### C. Spike-vs-production posture

**C1. Throwaway spike — explicit `spikes/wedge-001/` location, no expectation of survival, friction log as primary deliverable.** *Chosen — Decision §4.*

> Per [Glossary "Spike"](../Glossary.md): *"Throwaway prototype code written to test a design assumption."* Spike's job is to find friction in the SPEC, not produce durable code. **Argument for:** clear posture removes test-discipline / type-discipline / CI-overhead from spike scope; faster iteration; friction-log artifact is the durable output even if code is sacrificed. **Counter to "rewrite overhead":** even if Wedge-001 surfaces zero friction (unlikely), the rewrite forces a clean production-grade design informed by spike learning. [Codex1 agreed](../Discussions/20260520/20260520-2/Codex1.md): "*Hybrid-in-production-location is correctly rejected.*"

**C2. Production-grade first-cut.**

> **Rejected for Wedge-001.** Crosses two postures simultaneously: spike-velocity testing of assumptions AND production-grade code discipline. The latter slows the former without compensating benefit at this stage. Reopen the production-code posture decision after Wedge-001 friction is logged.

**C3. Hybrid — spike-velocity but in production location; refactor toward production grade as patterns stabilize.**

> **Rejected.** Hybrid is the worst-of-both: throwaway code in production location confuses future contributors; "we'll refactor to production grade later" is the recipe for never-quite-finished-but-already-shipped code.

### D. Spike repo layout

**D1. `spikes/wedge-001/` under AIADRA repo root.** *Chosen — Decision §5.*

> Co-located with Docs/; visible to spec readers; spike code AND ADRs in one history. Spike output is NOT git-ignored because the code IS the friction-discovery artifact and must be reviewable / re-runnable. Subdirectory makes the throwaway-posture visible.

**D2. Separate `aiadra-wedge-001` repo.**

> **Rejected.** Separates spike code from spec; cross-references become brittle; the spec ↔ code anchor breaks.

### E. Fixture data — reuse ADR worked examples

**E1. Reuse worked-example UUIDs / Numbers from ADRs 0005-0022 as spike-local demo records.** *Chosen — Decision §6.*

> Tight spec↔code anchor — every fixture is traceable to an ADR worked example; spec readers can match spike outputs against ADR sections. **Explicit spike-local ownership** (per [Codex1 N3](../Discussions/20260520/20260520-2/Codex1.md)): the reused identities are spike-local demo records, NOT Number reservations against future real projects' data. Numbers are per-project namespaces per [ADR/0004 §6](0004-number-allocation.md); subsequent real projects allocate from their own Reservation files and may freely use `P-000058` / `REQ-000058` (or any other Number) in their own scope.

**E2. Fresh fixtures unrelated to ADR examples.**

> **Rejected.** Loses the spec↔code anchor.

### F. CI / packaging

**F1. No CI for spike; runs locally only; no published artifacts.** *Chosen — Decision §7.*

> Spike-posture: throwaway. CI overhead is production-posture concern. Spike runs are documented in friction-log; output fixtures checked in; reproducibility is "clone + python -m wedge" not GitHub Actions.

**F2. Light CI — GitHub Actions runs the spike on push.**

> **Rejected.** CI scaffolding is meaningful overhead for ~hundreds of lines of throwaway Python.

### G. Deliverable shape

**G1. Runnable CLI script + checked-in input/output fixtures + one-page friction log.** *Chosen — Decision §8.*

> CLI invocation pattern: `python -m wedge create-part ...`, `python -m wedge propose-parameter-change ...`, `python -m wedge release ...`. Output fixtures (sidecars / events / manifests) checked in alongside spike code. Friction log (Markdown, ≤2 pages) is the **primary deliverable** from a spec-validation perspective.

**G2. Library + tests.**

> **Rejected (for spike).** Library posture implies surviving API; rejected per C1 throwaway choice.

**G3. Test fixtures only — no CLI.**

> **Rejected.** Misses Layer 3 (AI Action Protocol — Transaction lifecycle); fixtures alone cannot exercise begin → modify → validate → commit.

## Decision

### 1. Arc-structure: scope-first ADR; spike code lands in follow-up arc

**This arc (20260520-2) lands ADR/0023.** No spike code is written in this arc. The follow-up arc (proposed `20260520-3` or later) references ADR/0023's pinned scope and writes the spike. Matches AIADRA working style (*discuss → plan → architect → code*) and avoids overloading a single arc with both scope and implementation.

### 2. Wedge scope: basic shape per ADRs 0005 / 0006 / 0009 (clarifies Glossary Wedge shorthand)

Wedge-001 implements the minimum coherent basic-Wedge artifact set. The Manifesto framing (Tier-S validation; exercises all architectural layers) stays as written; ADR/0023 partially clarifies the [Glossary "Wedge"](../Glossary.md) entry's old singular-count shorthand ("one sidecar / one event-log entry") into the concrete coherent set without expanding scope ambition:

- **One Part** (PascalCase Object Type per [ADR/0005](0005-object-type-part.md)) — `P-000058` drive bracket, reusing the worked-example UUID / Number as a spike-local demo record per Decision §6.
- **One named parameter** — `plate_thickness_mm` on the Part (field-name-encoded unit per [ADR/0010 §2](0010-relationship-type-composed-of.md) canonical-unit discipline).
- **One Requirement** (per [ADR/0006](0006-object-type-requirement.md)) — `REQ-000058` minimum-thickness Requirement.
- **One `satisfies` relationship** (per [ADR/0009](0009-relationship-type-satisfies.md)) — `P-000058 →satisfies→ REQ-000058` authored on Part-side `relationship:` namespace.
- **Sidecars** — two at working state (Part + Requirement) per AIADRA YAML Profile per [ADR/0002](0002-canonical-format.md).
- **Events** — five distinct types (`part_created`, `requirement_created`, `relationship_created`, `parameter_changed`, `part_released` / `requirement_released`) emitted at state transitions, append-only JSONL per [ADR/0002](0002-canonical-format.md).
- **One AI Transaction** — propose-parameter-change lifecycle: begin → modify (`plate_thickness_mm: 6 → 7`) → recompute (re-validate) → validate (satisfies-check against Requirement) → human approval (CLI prompt) → commit (write sidecar + event) OR rollback.
- **One deterministic validation** — `plate_thickness_mm` satisfies REQ-000058's `min_thickness_mm` acceptance criterion; pass / fail.
- **One Release Manifest** (deterministic JSON per [ADR/0002](0002-canonical-format.md)) — pins **Part Revision** + **Requirement Revision** + **materialized `satisfies` record inside the Part Revision** (per [ADR/0009 §5](0009-relationship-type-satisfies.md), `satisfies` materializes inside the source Object's Revision record, not as a parallel relationship-Revision artifact) + **validation outcomes** (the deterministic Layer-2 satisfies-check pass result) + **event-log boundary** (event ids / hashes of the events that produced this release). **Does NOT pin** acceleration-cache state (derived / local / never-canonical per [ADR/0001 §3](0001-storage-substrate.md)) or any standalone relationship-Revision artifact (no such artifact exists for `satisfies`). If a fold-consistency check is wanted, it is a validation output captured inside the manifest, not a cache-state pin.

**Explicit non-scope:** no V&V framework (TestProcedure / TestExecution / EvidenceArtifact / verifies / tested_against / cites / executes / executed_on / produces); no Assembly / Component / SoftwareModule / Drawing; no `composed_of` / `mated_to` / `parameter_expression`; no cross-project; no Domain Engine. **All these are landed in spec but deferred to Wedge-002+ per the [OQ-0007](../OpenQuestions.md) build-it-evaluate-expand pattern.**

### 3. Runtime: Python 3.11+ (spike-only; not a production runtime commitment)

Spike uses Python 3.11 or later. Dependencies (minimum set):

- `ruamel.yaml` (≥0.18) — round-trippable YAML with comment preservation + token-level access; needed for the AIADRA YAML Profile per [ADR/0002](0002-canonical-format.md).
- `jsonschema` (≥4.0) — Draft 2020-12 validation per [ADR/0003](0003-schema-governance.md).
- `click` (≥8.0) OR `argparse` (stdlib) — CLI argument parsing.
- `pytest` (≥7.0) — for spike-internal regression checks (NOT production tests; spike-grade only).

NO additional dependencies in seed spike. Reopen the runtime question for production after Wedge-001 friction is logged.

**AIADRA YAML Profile compliance (Wedge-001 acceptance criterion):** Wedge-001's YAML I/O implements the [ADR/0002](0002-canonical-format.md) AIADRA YAML Profile strict checks at spike grade:

- YAML 1.2 only (not 1.1).
- No anchors / aliases / merge keys / custom tags — parser rejects.
- Duplicate-key rejection — parser hard-fails on duplicate keys at the same level (load-bearing for [ADR/0004 §7](0004-number-allocation.md) Reservation conflict detection).
- Quoted ambiguous scalars — UUIDs, Numbers, version strings, any string coercible to bool, all quoted. Implemented via a token-level lint pass (regex / `ruamel.yaml` tokenizer; JSON Schema cannot catch post-parse since the parser has already resolved the scalar).
- JSON Schema (Draft 2020-12) validation at every read using the Wedge-001 schema subset (`object_part.schema.json`, `object_requirement.schema.json`, `relationship_satisfies.schema.json`, `event.schema.json`).

Spike-grade means implementations may be straightforward (e.g., a regex-based ambiguous-scalar check rather than a full token-stream linter) but the rules MUST be enforced — a Wedge-001 sidecar that violates the Profile MUST be rejected at read time, not silently accepted. The friction log captures any Profile rule that proved hard to enforce at spike grade and surfaces it for the production-runtime arc.

**Production runtime is explicitly NOT decided by ADR/0023.** Choosing Python here is a spike-velocity decision; production-grade `aiadra-core` runtime / repo-layout / posture is a separate future arc informed by the friction log.

### 4. Posture: throwaway spike

Wedge-001 is explicitly throwaway per [Glossary "Spike"](../Glossary.md). No expectation of code survival. Primary deliverable is the **friction log** documenting assumptions validated and friction encountered; secondary deliverable is the runnable CLI + checked-in fixtures. Production-grade `aiadra-core` is a separate future arc informed by the friction log.

### 5. Repo layout

Spike code lands under `spikes/wedge-001/` at the AIADRA repo root, with this expected structure:

```
spikes/wedge-001/
├── README.md                    # one-page spike framing + how to run
├── pyproject.toml               # minimal — name, deps, entry point
├── wedge/                       # Python package
│   ├── __init__.py
│   ├── __main__.py              # `python -m wedge` entry
│   ├── cli.py                   # CLI commands (create / propose / approve / release)
│   ├── sidecar.py               # YAML I/O + sidecar/event invariant + AIADRA YAML Profile checks
│   ├── event_log.py             # JSONL append-only
│   ├── manifest.py              # deterministic JSON release manifest
│   ├── transaction.py           # AI-Transaction lifecycle
│   ├── validate.py              # Layer-2 validator subset
│   └── schemas/                 # JSON Schemas needed for the basic Wedge subset
│       ├── _bundle_v0.19.0.json
│       ├── object_part.schema.json
│       ├── object_requirement.schema.json
│       ├── relationship_satisfies.schema.json
│       └── event.schema.json
├── fixtures/                    # seed Reservation files + initial sidecars
│   ├── Reservations/
│   │   ├── P.yaml
│   │   └── REQ.yaml
│   └── workspace/               # initial state (empty sidecars, etc.)
├── outputs/                     # spike-produced sidecars / events / manifests (checked in)
│   ├── revisions/
│   ├── events.jsonl
│   └── manifest.json
└── FRICTION_LOG.md              # primary deliverable
```

`spikes/wedge-001/` is NOT git-ignored. `spikes/` is a top-level directory at the AIADRA root; subsequent spikes (`wedge-002/`, etc.) sibling under it. Spike Python code uses local imports only; no `pip install -e` discipline required for throwaway.

### 6. Fixture data

Spike reuses the worked-example identities from ADRs as **spike-local demo records**:

- `P-000058` — drive bracket Part (from [ADR/0019 §"Worked sidecar example"](0019-object-type-evidence-artifact.md), [ADR/0022 §"Worked sidecar example"](0022-test-execution-model.md), etc.).
- `REQ-000058` — drive bracket structural Requirement (from [ADR/0021 §"Worked sidecar examples"](0021-relationship-types-v-and-v.md)).
- UUID values from ADR worked examples reused verbatim.
- Parameter `plate_thickness_mm` is a Wedge-specific addition (not in ADR worked examples) — Wedge-001 introduces it as a simple satisfies-checkable scalar.

Tight spec↔code anchor: every fixture identity is traceable to an ADR worked example; spec readers can match spike outputs against ADR sections.

**Spike-local ownership** (per [Codex1 N3](../Discussions/20260520/20260520-2/Codex1.md)): the reused identities are **spike-local demo records** for the Wedge-001 fixture. They do NOT reserve those Numbers for any future real project's data; subsequent real projects allocate Numbers from their own per-project Reservation files per [ADR/0004 §6](0004-number-allocation.md) and may freely use `P-000058` / `REQ-000058` (or any other Number) in their own scope. Spike fixtures and real project data live in separate Number namespaces because Number allocation is per-project per ADR/0004; the shared identifier text is a coincidence-by-design at the SPEC level, not a cross-project reservation.

### 7. CI / packaging

No CI for Wedge-001. No GitHub Actions, no published packages, no tagged releases of the spike. Spike runs locally only:

```bash
cd spikes/wedge-001
python -m wedge --help
```

Reproducibility documented in `spikes/wedge-001/README.md`. Spike output fixtures checked into `outputs/` so reviewers can see the result without running.

### 8. Deliverable shape

Three artifacts:

1. **Runnable Python CLI** at `spikes/wedge-001/wedge/` — implements the basic Wedge transaction lifecycle end-to-end.
2. **Checked-in input/output fixtures** at `spikes/wedge-001/fixtures/` (inputs) and `spikes/wedge-001/outputs/` (outputs) — reviewable without execution.
3. **Friction log** at `spikes/wedge-001/FRICTION_LOG.md` — Markdown, ≤2 pages, structured: (a) assumptions validated; (b) friction encountered with ADR / spec reference; (c) proposed clarifications / corrections / Schema Change Notes for follow-up arcs.

The friction log is the PRIMARY deliverable from a spec-validation perspective. The CLI + fixtures are how the friction log gets generated.

### 9. .gitignore additions (anticipated for spike-writing arc)

When the spike-writing arc lands, add to `.gitignore`:

```
# Python (spike + future implementation)
.pytest_cache/
*.egg-info/
.coverage
```

(Some Python entries are already in `.gitignore` lines 27-30 — `__pycache__/`, `*.pyc`, `.venv/`, `venv/`. The above extends the list. Code-arc to confirm exact set.)

### 10. Explicit deferrals (out of Wedge-001 scope)

- **V&V framework instrumentation** — Wedge-002 (`spikes/wedge-002/` or extends `wedge-001/` with V&V branch). Lifts the seven-record V&V chain end-to-end against schema.
- **Component / SoftwareModule / Drawing exercise** — Wedge-003+ once basic and V&V Wedges round-trip.
- **Cross-project (consumer adopts catalog Part)** — separate later spike; cross-project surface needs at least a two-project test bed.
- **Domain Engine (FreeCAD Adapter sketch)** — Ring 3 / Ring 4 arc; out of Wedge spike series until Domain Adapter contract is settled per [OQ-0004 / OQ-0005](../OpenQuestions.md).
- **Production-grade `aiadra-core` runtime + repo layout decision** — separate arc after Wedge-001 friction is logged. Spike's Python is NOT a production commitment.
- **Acceleration cache (DuckDB / SQLite per [ADR/0001 §3](0001-storage-substrate.md))** — out of Wedge-001. The basic Wedge does not need where-used queries; defer cache implementation to a later spike that exercises query semantics.
- **Schema bundle migrators per [ADR/0003](0003-schema-governance.md)** — out of Wedge-001. Spike runs at exactly one schema bundle version (v0.19.0); migration is a future spike concern.
- **Vault Adapter / LFS** — out of Wedge-001 (basic Wedge has no attachments). Vault exercised in Wedge-002 when Drawing / EvidenceArtifact land.
- **Failed-transaction audit retention** — deferred per [OQ-0003](../OpenQuestions.md) (Ring 2). Wedge-001 does NOT implement a checked-in audit-log shape for rejected transactions; validation failure prints to stdout; no canonical Product Truth artifact and no checked-in audit-log artifact is produced. The friction log captures the spike's experience with rejected transactions but does NOT propose an audit-log schema (that is Ring 2's concern per OQ-0003). If a local ephemeral debug trace is useful during spike development, it is explicitly non-canonical and excluded from `outputs/`.

## Worked invocation (target spike behavior, not implementation)

This is the target behavior Wedge-001 should produce; sketched here to anchor the scope, NOT a code design.

```bash
# Initialize an empty project workspace
$ python -m wedge init --project-id "wedge-001-demo"
✓ Created Docs/Reservations/P.yaml (empty)
✓ Created Docs/Reservations/REQ.yaml (empty)
✓ Created events.jsonl (empty)

# Author a Part sidecar in working state
$ python -m wedge create-part \
    --number P-000058 \
    --name "Drive bracket" \
    --parameter plate_thickness_mm=6
✓ Allocated P-000058 in Docs/Reservations/P.yaml
✓ Wrote revisions/0193abcd-1234-7890-abcd-111111111111/working.yaml
✓ Appended part_created event to events.jsonl
✓ Sidecar/event invariant: PASS

# Author a Requirement sidecar in working state
$ python -m wedge create-requirement \
    --number REQ-000058 \
    --statement "Drive bracket plate thickness >= 5mm" \
    --acceptance-criterion ac_min_thickness:plate_thickness_mm>=5
✓ Allocated REQ-000058 in Docs/Reservations/REQ.yaml
✓ Wrote revisions/0193abcd-1234-7890-abcd-222222222222/working.yaml
✓ Appended requirement_created event to events.jsonl

# Author a satisfies relationship on Part side
$ python -m wedge link-satisfies \
    --source P-000058 \
    --target REQ-000058
✓ Updated revisions/<part-uuid>/working.yaml relationship: namespace
✓ Appended relationship_created event to events.jsonl

# Propose a parameter change as an AI Transaction — REJECTED case
$ python -m wedge propose-parameter-change \
    --object P-000058 \
    --parameter plate_thickness_mm \
    --new-value 4 \
    --rationale "AI proposal: thinner for weight target"
✓ Transaction tx_0001 begun (in-memory; not committed)
✓ Modify: plate_thickness_mm: 6 → 4
✓ Validate: REQ-000058 acceptance criterion ac_min_thickness FAILS (4 < 5)
✗ Transaction REJECTED — rollback applied; no state change committed
  Note: failed-transaction retention remains deferred by OQ-0003 — no audit artifact written.

# Retry with a valid change — APPROVED case
$ python -m wedge propose-parameter-change \
    --object P-000058 \
    --parameter plate_thickness_mm \
    --new-value 7 \
    --rationale "AI proposal: stronger for safety margin"
✓ Transaction tx_0002 begun
✓ Modify: plate_thickness_mm: 6 → 7
✓ Validate: REQ-000058 acceptance criterion ac_min_thickness PASSES (7 >= 5)
? Human approval required: [y/N] y
✓ Commit: revisions/<part-uuid>/working.yaml updated
✓ Appended parameter_changed event to events.jsonl
✓ Sidecar/event invariant: PASS

# Release both Objects
$ python -m wedge release --objects P-000058,REQ-000058 --label "rev-A"
✓ Materialized Fixed bindings on satisfies inside Part Revision (endpoint.revision_id pinned to Requirement rev-A per ADR/0009 §5)
✓ Wrote revisions/<part-uuid>/rev_a.yaml (immutable copy — includes materialized satisfies record)
✓ Wrote revisions/<req-uuid>/rev_a.yaml (immutable copy)
✓ Appended part_released, requirement_released events
✓ Wrote Releases/rev-A/manifest.json (deterministic JSON, content-hashable; pins Part rev-A + Requirement rev-A + validation outcomes + event-log boundary; does NOT pin acceleration-cache state per ADR/0001 §3)
✓ Release manifest hash: sha256:abc123...
```

Wedge-001 succeeds if every line above runs cleanly with no manual fixup, and the resulting sidecars / events / manifest fold-consistency check passes.

## Consequences

- **First code-producing-direction ADR lands.** ADR/0023 pins scope + runtime + posture for the Wedge spike series; subsequent spike arcs reference these pins.
- **Partial clarification of [Glossary "Wedge"](../Glossary.md) entry's singular-count shorthand.** The old wording (*"one sidecar / one event-log entry"*) predated ADRs 0005 / 0006 / 0009 pinning concrete artifact mechanics; ADR/0023 clarifies it into the minimum coherent artifact set without expanding the Wedge's scope ambition (still Tier-S; still one Part / one Requirement / one parameter / one Transaction). [Manifesto §"Scale targets"](../Manifesto.md) framing of the Wedge stays unchanged. Glossary v0.23 → v0.24 carries the edit.
- **[OQ-0007](../OpenQuestions.md) partially advanced.** Status `accepted-as-unresolved` → `under-investigation`; pointer added to ADR/0023. Resolution waits for the running spike and friction-log review.
- **Python pinned as spike-only runtime.** Production-grade `aiadra-core` runtime / repo-layout decision is a separate future arc; NOT pre-empted by this ADR. The .gitignore Python entries that land with the spike-writing arc are spike-scope, not production-scope.
- **Spike code lives in-repo at `spikes/wedge-001/`.** Not git-ignored. Friction log + checked-in fixtures form the durable record.
- **Throwaway posture explicit.** Spike code is NOT a production commitment. Production posture decisions wait for Wedge-001 friction-log review.
- **AIADRA YAML Profile spike-grade acceptance criterion** explicitly named per Decision §3 (no anchors / aliases / merge keys / custom tags; duplicate-key rejection; quoted ambiguous scalars via token-level lint; JSON Schema validation at every read; spike-grade enforcement is normative, not optional). [Codex1 N1 absorption](../Discussions/20260520/20260520-2/Claude2.md).
- **Spike-local fixture ownership** clarified per Decision §6. Reused ADR worked-example identities are spike-local demo records; do not reserve Numbers against future real project data. [Codex1 N3 absorption](../Discussions/20260520/20260520-2/Claude2.md).
- **Failed-transaction audit retention** stays deferred per [OQ-0003](../OpenQuestions.md). Wedge-001 produces no audit-log artifact for rejected transactions; that decision is Ring 2's. [Codex1 B2 absorption](../Discussions/20260520/20260520-2/Claude2.md).
- **Wedge-002 (V&V-instrumented) is the natural follow-up** — once basic Wedge-001 round-trips, V&V framework exercise is the obvious next spike per [OQ-0007](../OpenQuestions.md)'s build-it-evaluate-expand pattern.
- **No SystemState Pattern Catalogue rows added.** ADR/0023 is a meta-decision; does not introduce schema patterns. SystemState Current Front + Recent Pattern Changes updated; Pattern Catalogue and Coherence Checklist unchanged.
- **No schema bundle bump.** ADR/0023 is a meta-decision (scope + posture); does NOT modify any schema. Schema bundle stays v0.19.0 after this ADR.
- **Glossary additions / edits.** [Glossary.md](../Glossary.md) v0.24: Wedge entry clarification per B3 (singular-count shorthand → minimum coherent artifact set, without expanding scope ambition); Manifesto framing unchanged.
- **SystemState updates.** §1 Current Front advances from "Ring 1 catalogue work substantively complete + named relationship-type catalogue operationally complete except `derived_geometry_from`" to "Wedge spike scope pinned (ADR/0023); spike-writing arc is next natural step." §5 Deferred refresh (Failed-transaction audit retention per OQ-0003 carries forward unchanged; Wedge-002 / production-runtime / Vault Adapter / acceleration cache / schema bundle migrators listed). §6 Recent Pattern Changes entry for ADR/0023.
- **OpenQuestions update.** OQ-0007 status `accepted-as-unresolved` → `under-investigation`; pointer to ADR/0023.
- **Methodology arc flag** carried per Codex2 sign-off — first code-producing direction; coherent as one methodology arc.

## Codex2 sign-off summary

[Codex2](../Discussions/20260520/20260520-2/Codex2.md) signed off without further objection. All three Codex1 blockers retracted after the Claude2 absorptions; all three non-blockers accepted. The agreed direction (scope-first ADR, basic Wedge-001, Python 3.11+ as spike-only runtime, throwaway posture under `spikes/wedge-001/`, methodology-arc treatment) is unchanged from Claude1; ADR/0023 lands the converged form.
