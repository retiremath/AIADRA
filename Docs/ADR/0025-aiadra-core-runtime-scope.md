---
name: adr-0025-aiadra-core-runtime-scope
status: accepted
date: 2026-05-31
supersedes: none
superseded_by: none
resolves: []
---

# ADR/0025 — Production-grade `aiadra-core` runtime: scope, repo layout, posture

## Status

**Accepted** — 2026-05-31. Third code-producing-direction ADR after [ADR/0023](0023-wedge-spike-scope-and-runtime.md) (Wedge-001) and [ADR/0024](0024-wedge-002-spike-scope.md) (Wedge-002). Pins the **scope + runtime shape + repo layout + posture + friction-item absorption directions + implementation-arc sequencing** for the production-grade `aiadra-core` runtime, without writing any `aiadra-core/` code in this arc. Implementation lands in **five sequenced follow-up arcs** (skeleton → runtime-behavior+W1+W2 SCNs bundled → F1 SCN → W3 SCN → F2 SCN).

Builds on the [ADR/0023 + arc 20260530-1](../Discussions/20260530/20260530-1/CLOSED.md) + [ADR/0024 + arc 20260530-3](../Discussions/20260530/20260530-3/CLOSED.md) precedent: scope-first ADR → implementation arc → friction log → next scope-first ADR informed by friction. Combined Wedge-001 + Wedge-002 friction logs are the load-bearing input.

**Ten pinned decisions** (each is the recommended option from [Claude1](../Discussions/20260530/20260530-4/Claude1.md) / [Codex1](../Discussions/20260530/20260530-4/Codex1.md) / [Claude2 absorptions](../Discussions/20260530/20260530-4/Claude2.md) / [Codex2 signoff](../Discussions/20260530/20260530-4/Codex2.md)):

1. **Arc structure + implementation sequencing** — scope-first ADR; five sequenced follow-up arcs (Decision §1).
2. **Runtime shape** — Python 3.12+ library + thin CLI wrapper; synchronous; ruamel.yaml + jsonschema as load-bearing deps (Decision §2).
3. **Repo layout** — `aiadra-core/` at AIADRA repo root parallel to `spikes/`; spikes frozen as historical (Decision §3).
4. **F1 absorption** — extend `parameter_changed` event payload with optional `new_fact_provenance` (Decision §4).
5. **F2 absorption** — hybrid `threshold_expression` primitive on `acceptance_criterion`; numeric-only, opt-in, unit-REQUIRED, no free-text parsing (Decision §5).
6. **F3 absorption** — Draft-then-commit per state-changing CLI command; git commit IS the atomicity boundary (Decision §6).
7. **W1 absorption** — staged-release mechanism; each stage IS a canonical Release Manifest; final stage validates the full graph; explicit `final_stage: true|false` marker (Decision §7).
8. **W2 absorption** — attachments live in working sidecars from authoring time, mutated via canonical Transaction emitting `<type>_changed` event with `attachment_delta` payload (Decision §8).
9. **W3 absorption** — per-relationship-type schemas + bundle lookup namespace keyed by relationship `type`; no new field; no data migration (Decision §9).
10. **Out of scope** — Layer 3 AI Action Protocol, Layer 4 PR/merge, Layer 5 Domain Adapters, acceleration cache, token-stream Profile linter, concurrency, Tier-L scaling (Decision §10).

Plus a disposition table covering 13 non-absorbed friction-log items per [Codex1 N1](../Discussions/20260530/20260530-4/Codex1.md) (see §"Disposition of non-absorbed friction items").

**Three firsts** (each pattern-setting):

1. **First production-grade direction ADR** — pivots from spike-grade scope ADRs (ADR/0023, ADR/0024) into the production runtime. Pattern: combined-spike-friction-informs-production.
2. **First ADR informed by *combined* friction logs from two prior spikes** — Wedge-001 friction shaped ADR/0024's Decision §7 (carry forward); ADR/0025 absorbs friction from BOTH spikes as joint load-bearing input.
3. **First ADR to pin a multi-arc implementation sequencing roadmap** — five phases (skeleton; runtime-behavior+W1+W2 SCNs; F1 SCN; W3 SCN; F2 SCN); each phase opens after the prior closes; sequential per [PROTOCOL.md](../Discussions/Transfer/PROTOCOL.md) pipeline-cap discipline.

**No schema bundle bump.** ADR/0025 is a meta-decision (scope + posture + direction); does NOT modify any schema. Bundle stays v0.19.0 after this ADR. The five SCN follow-up arcs (F1, F2, W1, W2, W3) each carry their own bundle bumps when they land.

**Methodology flag: NO.** ADR/0025 does not reserve the pipeline (cap-of-1). Treat as a normal arc.

## Context

Discussion trail in [`Docs/Discussions/20260530/20260530-4/`](../Discussions/20260530/20260530-4/). [Codex1](../Discussions/20260530/20260530-4/Codex1.md) produced four blocking objections — B1 (Decision §8 missing canonical event), B2 (Decision §6 atomicity model conflicts with §8), B3 (Decision §7 stage artifact semantics blurry), B4 (Decision §9 discriminator overreach) — plus three non-blockers (N1 disposition table; N2 threshold scope tightening; N3 implementation sequencing clarity). [Claude2](../Discussions/20260530/20260530-4/Claude2.md) absorbed all seven; B1+B2 resolved jointly via the Draft-then-commit-per-CLI-command model. [Codex2](../Discussions/20260530/20260530-4/Codex2.md) signed off with three non-blocking wording repairs (avoid "relationship artifact_kind"; Layer-2 hard-fail for unit mismatch; explicit `final_stage` field) — all three applied below.

Two pressures converge on ADR/0025:

1. **Spec → code transition is complete for spike-grade.** Wedge-001 (basic loop) + Wedge-002 (V&V chain + Attachment-bearing + execution-instance + Vault) both implemented end-to-end per [arc 20260530-1](../Discussions/20260530/20260530-1/CLOSED.md) + [arc 20260530-3](../Discussions/20260530/20260530-3/CLOSED.md). [SystemState §1](../SystemState.md) names this ADR as the next likely arc. No further spike is needed to surface production-grade signal — Wedge-003 (Component + SoftwareModule + Drawing) would teach about additional Object Types in code, not about the runtime itself.

2. **Six production-grade decisions are ripe.** Three Wedge-001 load-bearing items (F1 `parameter_changed` event payload + `fact_provenance` mutation; F2 acceptance-criterion threshold-expression primitive; F3 cross-artifact atomicity strategy) plus three Wedge-002 moderate items (W1 `.rev-id-map` upfront predeclaration; W2 `.attachments-staging.yaml` staging file; W3 `relationship` namespace `oneOf` schema errors) all share a common posture-decision shape: each has 2-3 credible resolution paths, none has been picked. The ADR's job is **pick one direction per item with rationale; the schema-change-note follow-ups land separately**.

Following the [ADR/0024 §"Decision §7"](0024-wedge-002-spike-scope.md) precedent (carry-forward direction pinned in ADR; SCN itself a separate arc), this ADR sets *direction* for each friction item but does NOT author the schema diffs. Those land as independent SCN arcs once the direction is committed.

## Decision §1 — Arc structure + implementation sequencing

ADR/0025 is a **scope-first methodology ADR**. No `aiadra-core/` code in this arc. Implementation lands in **five sequenced follow-up arcs**:

1. **Skeleton arc (Phase 0):** `aiadra-core/` package layout + `pyproject.toml` + dependency declarations + empty module stubs + integration test fixture carryover from spikes + cross-cutting infrastructure already canonical (`atomic_write_bytes`; schema-validated load helpers; per-event-type schemas; UTF-8 stdout; workspace-rooted paths; `schema_version` placement convention; canonical-optionality REQUIRED fields). **No friction-item absorption beyond setup.**
2. **Runtime-behavior arc (Phase 1):** absorbs F3 atomicity (Draft-then-commit per CLI command per Decision §6) + W1 staged-release runtime (per Decision §7) + W2 attachment-via-Transaction runtime (per Decision §8). Includes the **W1 SCN** (manifest `prior_stage_manifest_ref` + `stage_number` + `final_stage` fields + `release_staged` event variant) AND the **W2 SCN** (`<type>_changed` event payload extension with `attachment_delta` for Attachment-bearing Object Types). Both SCNs MINOR; bundle bumps once at end of Phase 1.
3. **F1 SCN arc (Phase 2):** `parameter_changed` event payload extension with `new_fact_provenance`. MINOR bump.
4. **W3 SCN arc (Phase 3):** per-relationship-type schema split + bundle lookup namespace dispatch on existing `type` field. MINOR bump. Lands before F2 so the threshold validator builds on the cleaner per-relationship dispatch surface (per [Codex1 Q4 answer](../Discussions/20260530/20260530-4/Codex1.md)).
5. **F2 SCN arc (Phase 4):** `threshold_expression` primitive on `acceptance_criterion`. MINOR bump.

Each follow-up arc opens after the prior arc closes; sequential. Pipeline cap (3 in flight per [PROTOCOL.md](../Discussions/Transfer/PROTOCOL.md)) is not approached.

**Alternatives rejected.**
- **Single mega-arc** that lands all five phases: explodes scope; loses per-decision rationale.
- **Skipping the scope-first ADR** and going straight to skeleton: re-decides the six friction-item directions informally during implementation.
- **Splitting Phase 1 into 1a (runtime behavior) + 1b (W1/W2 SCNs)** per [Codex1 N3](../Discussions/20260530/20260530-4/Codex1.md) suggestion: rejected because the runtime behavior of W1 (staged release) and W2 (attachment-via-Transaction) is meaningless without the corresponding schema (manifest field for staging; event payload extension for attachment delta) — both must land together.

## Decision §2 — Runtime shape: library + thin CLI wrapper

`aiadra_core` is a **Python library** (importable from notebooks, IDEs, CI scripts, Domain Adapter prototypes) with a **thin CLI wrapper** (`aiadra` command) for shell-driven workflows. Both share the same Layer-1/Layer-2 code paths; CLI is a wrapper, not a parallel implementation.

- **Python 3.12+** — match spike runtime (Wedge-001 + Wedge-002 both ran on 3.12.4); type hints + ruamel.yaml 0.18 + jsonschema 4.x ecosystem is stable.
- **Dependency posture:** stdlib-only on Layer-1 read/write paths where feasible; `ruamel.yaml` REQUIRED for Profile-conformant emission with comment preservation; `jsonschema` REQUIRED for Draft 2020-12; `pyyaml` rejected (loses comments, no Profile control). Vault Adapter backends, format converters, and future Domain Adapter integrations are **optional extras** (`pip install aiadra-core[vault-s3]`, etc.).
- **No daemon, no service, no background process.** Every operation is a synchronous library call returning a result or raising; CLI is a one-shot process. Reinforces [Manifesto P11](../Manifesto.md).
- **Importable name:** `aiadra_core` (PEP 8). The `aiadra` namespace is reserved for future subpackages (e.g., `aiadra.adapters.freecad`).

**Alternatives rejected.** CLI-only (closes off Domain Adapter and notebook embedding); daemon/service (violates P11); async API (premature for I/O-bound Layer 1/2); stdlib-only Profile emission (multi-month detour reimplementing YAML 1.2 round-tripping).

## Decision §3 — Repo layout: `aiadra-core/` at AIADRA repo root parallel to `spikes/`

```
AIADRA/
├── aiadra-core/                 # NEW
│   ├── pyproject.toml
│   ├── src/
│   │   └── aiadra_core/
│   │       ├── __init__.py
│   │       ├── truth_model/     # Layer 1: sidecars, events, Revisions, Reservations, Manifest
│   │       ├── validation/      # Layer 2: schema + Profile linter + sidecar/event invariant + bundle digest
│   │       ├── transaction/     # Layer 3 partial: begin/commit/rollback (NOT the full AI Action Protocol)
│   │       ├── vault/           # Vault Adapter interface + local-FS reference implementation
│   │       ├── cli/             # Thin wrappers around library; one module per command
│   │       └── schemas/         # Bundled schemas; per-bundle-version subdir
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/         # End-to-end against fixture projects
│   │   └── fixtures/            # Including Wedge-001 / Wedge-002 carry-overs as integration baselines
│   └── README.md
├── spikes/
│   ├── wedge-001/               # Frozen as historical
│   └── wedge-002/               # Frozen as historical
└── Docs/                        # Unchanged
```

**Same-repo posture:** `aiadra-core/` lives in the AIADRA repo for v0 — no spin-out. If/when the runtime is consumed by external projects via `pip install`, repo-split is a future arc. The shared-repo move keeps ADRs / schemas / runtime co-versioned and lets the runtime read its own schemas from `aiadra-core/src/aiadra_core/schemas/<bundle-version>/` without cross-repo plumbing.

**Spike preservation:** Both Wedge spikes stay at `spikes/wedge-001/` and `spikes/wedge-002/` as **frozen historical artifacts** (per [ADR/0023 §6](0023-wedge-spike-scope-and-runtime.md) throwaway posture). Their friction logs remain the audit trail for ADR/0025's decisions. Not migrated, not refactored.

**Alternatives rejected.** Separate `aiadra-core` repo (premature; co-versioning is the highest-value invariant); folding into `Docs/` (runtime code belongs at repo root); using `spikes/wedge-002/` as production starting point (violates throwaway posture per ADR/0023/0024).

## Decision §4 — F1 absorption: extend `parameter_changed` event payload with `new_fact_provenance`

**Friction recap.** Wedge-001 `transaction.change_parameter` mutated `parameter.fact_provenance.category` (`human_input` → `ai_proposal`) but the `parameter_changed` event carried only `{old_value, new_value, rationale}`. Fold check failed: the event log couldn't derive the mutation. Spike workaround: don't mutate `fact_provenance` (sidecar stays `human_input` even after AI-proposed change).

**Decision.** Extend `parameter_changed` event payload with optional `new_fact_provenance` field carrying the new provenance dict. Fold rule: if `new_fact_provenance` present, apply it; if absent, `fact_provenance` unchanged.

**Alternatives rejected.**
- **Define normative fold rule "`parameter_changed` ⇒ `fact_provenance.category = 'ai_proposal'`":** assumes AI Action Protocol is the ONLY shape producing `parameter_changed`. False — a human-driven parameter change also produces `parameter_changed` and should stay `human_input`. The fold rule misclassifies provenance.
- **Separate `parameter_provenance_changed` event in addition to `parameter_changed`:** doubles event volume for a logically atomic change; violates [ADR/0001 §4](0001-storage-substrate.md) "atomic transition = single event" framing.

**SCN follow-up (Phase 2).** Additive optional field on existing event payload; MINOR bump per [ADR/0003 §11](0003-schema-governance.md) ceremony; migrator is a no-op (old events without the field are still valid; new events optionally carry it).

## Decision §5 — F2 absorption: hybrid canonical threshold primitive (numeric-only, opt-in, unit-REQUIRED)

**Friction recap.** Wedge needs deterministic `plate_thickness_mm >= 5` check. Requirement schema carries `criterion: {text, language, format}` + optional `references[]` — no structured threshold. Spike-local: CLI parses `--acceptance-criterion ac_id:param>=value` and synthesizes criterion text; spike validator regex-parses to extract `(param, threshold)`. Brittle.

**Decision.** Extend `acceptance_criterion` schema with optional `threshold_expression` structured primitive:

```yaml
threshold_expression:
  parameter_ref: "<object_uuid>:parameter:<id>"   # fact-level reference per ADR/0015 addressing
  comparison_op: ">=" | "<=" | "==" | "!=" | ">" | "<"   # numeric comparison only
  value: <number>                                  # numeric value only
  unit: "<unit-string>"                            # REQUIRED; must match the referenced parameter's unit
```

**Tight scope.**

- **Numeric comparisons only.** No boolean combinators, no set membership, no regex, no statistical distributions. If a criterion requires non-numeric or compound logic, it stays in free-text `criterion.text`.
- **Explicit unit compatibility.** `threshold_expression.unit` MUST be present (JSON Schema enforces presence). Unit-equality against the referenced parameter's unit at release is **Layer-2 hard-fail at release** (cross-record check; JSON Schema cannot perform). No silent unit conversion.
- **Fact-level `parameter_ref`** per [ADR/0015](0015-relationship-type-parameter-expression.md) addressing — `<object_uuid>:parameter:<id>`.
- **No free-text parsing.** Core does NOT parse `criterion.text` for threshold expressions. If `threshold_expression` is absent, the criterion is tooling-aided-only per the [ADR/0021 §7](0021-relationship-types-v-and-v.md) verification-method-consistency-as-tooling-aided posture. **Core MUST NOT infer PASS from prose.**

**If `threshold_expression` present:** at release, the Layer-2 validator structurally checks the referenced parameter's value against the comparison_op + value + unit, and emits a `threshold_check(<criterion_id>)` validation_outcome (PASS / FAIL). FAIL is a hard-fail at release if a `satisfies` or `verifies` relationship claims the criterion.

**If `threshold_expression` absent:** free-text `criterion.text` remains. Satisfaction is a tooling-aided diagnostic claim; Core does not structurally evaluate.

**Alternatives rejected.**
- **Option (i) structured threshold REQUIRED:** breaks non-numeric requirements (e.g., "shall comply with FCC Part 15"); backward-compat incompatible; clashes with [ADR/0021 §7](0021-relationship-types-v-and-v.md) posture.
- **Option (ii) tooling-aided only:** loses structural enforcement at release; leaves spike-grade regex-parsing as the only mechanism.
- **Option (iii) hybrid CHOSEN, now tightly scoped per [Codex1 N2](../Discussions/20260530/20260530-4/Codex1.md):** numeric-only, opt-in, unit-REQUIRED, no free-text parsing.

**Pattern Catalogue impact:** none added. The opt-in primitive pattern is consistent with the per-relationship-schema opt-in discipline from [ADR/0021 §"Decision §6"](0021-relationship-types-v-and-v.md).

**SCN follow-up (Phase 4).** Schema addition to `acceptance_criterion` (optional structured field). MINOR bump. Migrator no-op. Lands AFTER W3 so threshold validator builds on cleaner per-relationship dispatch.

## Decision §6 — F3 absorption: Draft-then-commit per state-changing CLI command; git commit as atomicity boundary

**Friction recap.** Wedge spikes use per-artifact temp-file-then-rename (`os.replace`); a crash between sidecar write and event append within a single CLI command leaves the sidecar/event invariant violated. [ADR/0004 §6](0004-number-allocation.md) already commits to "Same Git commit MUST contain..." — but spike implementations don't enforce.

**Decision.** Every state-changing AIADRA CLI command is a **Transaction**. Each Transaction follows the Draft-then-commit cycle:

1. **Draft phase (in-memory only):** compute the full coherent set of file changes — sidecar updates, event log appends, Reservation entries, Revision materializations (release-time), manifest updates (release-time), Vault byte writes. NO files written to the working tree yet. NO git operations yet.
2. **Validate phase (in-memory):** run all checks against the proposed-but-not-written state — schema (per [ADR/0003 §2](0003-schema-governance.md)), AIADRA YAML Profile lint, sidecar/event invariant (fold over event log including the proposed event must reproduce the proposed sidecar state per [ADR/0001 §4](0001-storage-substrate.md)), bundle digest match (per [ADR/0003 §9](0003-schema-governance.md)), and release-time Layer-2 invariants when applicable. Failure here aborts: no files touched, no commit, working tree byte-identical to pre-command state.
3. **Commit phase:** write all files via `atomic_write_bytes` (carrying forward [Wedge-001 round-2 B2 absorption](../../spikes/wedge-001/FRICTION_LOG.md)); write Vault bytes (idempotent — content-addressed); `git add` the touched files; `git commit -m "<aiadra-generated message with object refs and transaction kind>"`. The git commit IS the atomicity boundary.

**Failure semantics.** Draft-phase failure (in-memory): no side effects whatsoever. Commit-phase failure between `atomic_write_bytes` and `git commit`: the runtime SHOULD restore the working tree from `HEAD` before exiting; if the runtime itself crashes here, the user runs `git restore -- .` (or `aiadra recover`) to restore. The contract is **no Transaction half-applies to git history**.

**Boundary clarification.** The user does NOT call `git commit` manually with AIADRA-managed state. AIADRA Core's commit operation IS the git commit. Git plumbing operations the user IS expected to use: `git status`, `git log`, `git diff`, `git push`, `git pull`, branch operations, rebase. Mixing manual `git add`/`git commit` with AIADRA-managed paths is unsupported; the runtime detects this on next AIADRA command (working tree dirty for AIADRA paths) and refuses to proceed until reconciled.

**Read operations are not Transactions.** `aiadra inspect`, `aiadra query`, `aiadra validate` (read-only checks) do not write or commit. Only state-changing operations follow Draft-then-commit.

**Rationale for per-CLI-command granularity** (not per-Workspace-session): sessions lack natural start/end markers; long-running edit sessions would accumulate uncommitted state that re-introduces sidecar/event drift. Per-command granularity keeps every commit small + reviewable + reproducible, matches the typed-API granularity Ring 2's AI Action Protocol will eventually expose, and keeps the AI agent's mental model simple ("each tool call commits or aborts").

**Alternatives rejected.**
- **Coherent-working-tree model** (allows uncommitted but internally coherent working tree): adds operational state the runtime must reconcile on every command.
- **Git-plumbing model** (temp index/worktree + `git commit-tree` + ref update): bypasses the working tree; harder to debug; user's `git status` shows nothing mid-Transaction.
- **Write-ahead log:** adds operational state (`.aiadra/wal/`); complexity-creep for a problem git already solves.
- **Transaction-manager wrapping the writes:** introduces runtime coordination; clashes with synchronous-library-call shape per Decision §2.

**SCN follow-up:** none — runtime-shape change, not schema change. Lands in Phase 1.

## Decision §7 — W1 absorption: staged-release mechanism; each stage IS a canonical Release Manifest

**Friction recap.** Wedge-002 execution-instance authoring needs Revision UUIDs that don't exist until release. Spike workaround: `--rev-id` flags at `init` predeclare future UUIDs; `.rev-id-map` file persists them. Works but requires users to know future UUIDs at workspace init — unrealistic for production.

**Decision.** A release can occur in one or more **stages**. Each stage is a complete, canonical, content-hashable Release Manifest with `manifest_type: release` per existing [ADR/0001 §3](0001-storage-substrate.md) semantics. Stages chain via an optional `prior_stage_manifest_ref: {manifest_hash, stage_number}` field on the manifest. The final stage is the release-of-record for the complete release graph; intermediate stages are themselves releases-of-record for their respective subsets.

**Explicit `final_stage: true|false` field** (per [Codex2 N3](../Discussions/20260530/20260530-4/Codex2.md)). A manifest carrying `final_stage: true` MUST include final cross-graph checks; intermediate manifests MUST carry `final_stage: false`. Absence-of-subsequent-stage cannot be known from a single manifest at creation time; the explicit field eliminates the ambiguity.

**Stage dependency closure** (per [Codex1 Q2 answer](../Discussions/20260530/20260530-4/Codex1.md)). A stage's release set must satisfy the closure rule — for every Object in the stage's release set and every relationship of that Object, the endpoint Object must either (a) already be released in a prior stage of the same chain (Fixed endpoint resolves to prior-stage Revision UUID), or (b) be in the same stage's release set (Float endpoint materializes; Fixed endpoint resolves to same-stage Revision). Stages are NOT pinned to Object Type taxonomy — any subset whose dependency closure resolves is a valid stage.

**Per-stage validation.**

- **Always run** (per-stage): schema check; Profile lint; sidecar/event invariant; bundle digest; Revision hash verification for the stage's release set; attachment integrity + attachment lineage for the stage's released Attachment-bearing Objects (with `source_authoring` presence + chain termination checked within-stage; chain references to prior-stage attachments resolved via prior-stage manifest).
- **Always run** (final stage only, i.e., `final_stage: true`): execution-record cardinality invariants per [ADR/0022 §3-§5](0022-test-execution-model.md) (`executes==1`, `executed_on>=1`, status-sensitive `produces`) applied to the **complete release graph** across all stages, not to any single stage's subset; V&V chain integrity (graph traversal across the complete release graph); any other cross-Object Layer-2 invariant.
- **NOT run** at intermediate stages: any validation requiring the complete release graph. An intermediate stage CANNOT report PASS for such checks (validation_outcomes entry absent — not PASS, not FAIL).

**No new manifest_type.** All stage manifests carry `manifest_type: release`. The `prior_stage_manifest_ref` + `stage_number` + `final_stage` fields distinguish.

**Canonical and signed.** Intermediate stage manifests ARE canonical artifacts. They are git-committed, content-hashed, and (when project policy requires) signed. Released Revisions referenced by an intermediate stage manifest ARE released — citeable, immutable, terminal.

**Workflow shape.**

1. `aiadra release --stage 1 --objects P-000023,REQ-000007,TST-000017` — runs Draft-then-commit per Decision §6 on the release Transaction. Releases 3 Revisions. Writes 3 release events + 1 stage-1 manifest. Stage-1 manifest carries `stage_number: 1`, `final_stage: false`, no `prior_stage_manifest_ref`. validation_outcomes contains the per-stage checks; no V&V chain integrity outcome.
2. `aiadra link-executes TEX-000007 --procedure TST-000017@<stage-1-released-rev_id>` — authoring uses the stage-1 released rev_id (read from stage-1 manifest's pinned Revision). `endpoints[0].revision_id` set Fixed-at-authoring per [ADR/0022 §6](0022-test-execution-model.md). Same draft-then-commit cycle.
3. `aiadra release --stage 2 --final --objects TEX-000007,EVD-000043 --prior-stage <stage-1-manifest-hash>` — releases 2 more Revisions. Writes 2 release events + stage-2 manifest. Stage-2 manifest carries `stage_number: 2`, `final_stage: true`, `prior_stage_manifest_ref: {hash: <stage-1>, stage_number: 1}`. validation_outcomes contains per-stage checks PLUS final-stage cross-graph checks (V&V chain integrity over P + REQ + TST + TEX + EVD; execution cardinality over TEX).

**Single-stage release (Wedge-002 shape)** is the degenerate case: `aiadra release --objects <all>` defaults to `--stage 1 --final`, runs all per-stage AND final-stage validations against the full release set, produces a single manifest with `stage_number: 1`, `final_stage: true`, `prior_stage_manifest_ref: null`.

**Alternatives rejected.**
- Keep `.rev-id-map` upfront predeclaration as canonical: unrealistic for production.
- Transaction-preview: illusion of atomicity that breaks under Fixed-at-authoring semantics.
- Inline-author-and-release: loses authoring across multiple execution-instance relationships against same staged release.
- Stage granularity pinned to Object Type taxonomy: rejected per [Codex1 Q2 answer](../Discussions/20260530/20260530-4/Codex1.md); dependency closure is more flexible and equally enforceable.
- New `manifest_type: release_checkpoint`: rejected per [Codex1 B3](../Discussions/20260530/20260530-4/Codex1.md) absorption; intermediate stages are real releases-of-record for their subsets, not a separate artifact kind.

**SCN follow-up (Phase 1).** Extend manifest schema with optional `prior_stage_manifest_ref` + optional `stage_number` (default `1`) + optional `final_stage` (default `true` for backward-compat with single-stage manifests). New `release_staged` event variant (or extend `released` event with `stage_number`). MINOR bump (additive, backward-compatible). Migrator no-op (old manifests treated as single-stage final).

## Decision §8 — W2 absorption: attachments live in working sidecars; mutated via canonical Transaction

**Friction recap.** Wedge-002's `attach-file` → `create-*` workflow needs persistent `(att_id → content_hash + vault_path + role + media_type)` mapping. Spike persists in `outputs/.attachments-staging.yaml` (second non-canonical helper after `.rev-id-map`).

**Decision.** `aiadra attach-file <obj-num> <path> --role <role> [--id <att_id>]` is a **canonical Transaction** in the same sense as `change-parameter`, `link-*`, and `create-*`. It performs the full Draft-then-commit cycle per Decision §6:

1. **Draft** — compute attachment record (`content_hash`, `vault_path`, `role`, `media_type`); compute the proposed `attachment:` namespace delta against the current working sidecar; build the corresponding `<type>_changed` event payload with `attachment_delta`; reserve Vault bytes path.
2. **Validate** — schema-check the proposed sidecar state; Profile-lint; sidecar/event invariant simulation; bundle digest; attachment lineage rules per [ADR/0017 §2](0017-object-type-drawing.md) (source_authoring presence; derived-chain termination).
3. **Commit** — write attachment bytes to Vault; write updated sidecar; append event to event log; git add all touched files; git commit. All atomic under Decision §6.

**`attachment_delta` payload shape** (per [Codex2 answer](../Discussions/20260530/20260530-4/Codex2.md) — delta preferred over full-state):

```yaml
attachment_delta:
  operation: "add" | "update" | "remove"
  attachment_id: "<att_id>"
  # required for operation: "add" | "update"
  attachment_record:
    role: "source_authoring" | "rendered_primary" | "derived_secondary"
    content_hash: "sha256:<hex>"
    vault_path: "vault/<sha256-hex>"
    media_type: "<RFC-6838-media-type>"
    derived_from_attachment_id: "<att_id>"   # REQUIRED for derived roles per ADR/0017 §2
  # optional for operation: "remove"
  reason: "<human-readable rationale>"
```

Fold rule: `<type>_changed` events with `attachment_delta.operation: "add"` append the attachment record to the working sidecar's `attachment:` namespace; `"update"` replaces the record with matching `id`; `"remove"` removes the record.

**Initial Object creation (`<type>_created`)** continues to carry the initial `attachment:` namespace inside `initial_sidecar` (no separate delta needed).

**No standalone `attachment_*` event family** per [Codex1 B1 guidance](../Discussions/20260530/20260530-4/Codex1.md). The mutation rides the existing per-Object-Type event taxonomy. [ADR/0024](0024-wedge-002-spike-scope.md)'s scoped rejection of standalone attachment events stays intact.

**Authority model preserved.** Released Revisions still carry the full `attachment:` namespace; `attachment_integrity` and `attachment_lineage` validation outcomes still emit at release per ADR/0024. The change is in **how the working sidecar's attachment namespace is built up**, not in what the release manifest pins.

**Alternatives rejected.**
- **Compound CLI flag** (`--attachment att_id:role:media_type:file=path` on `create-*`): combines flag complexity with hidden state at create-time; no improvement over staging file.
- **Keep `.attachments-staging.yaml` canonical:** second non-canonical helper file; doubles the surface area to reason about; reflects spike-grade scope-boundedness.
- **Full-state `attachment_namespace` payload instead of delta:** larger payload; less legible audit diffs. Delta-shape is deterministic because prior state is known from earlier events.

**Working sidecar discipline.** The working sidecar is mutable at authoring (via Transactions); **only the released Revision is immutable** ([ADR/0001 §3](0001-storage-substrate.md) + [ADR/0017 §2](0017-object-type-drawing.md)). `attach-file` mutating the working sidecar (via Transaction) is no different from `change-parameter` mutating the working sidecar.

**SCN follow-up (Phase 1).** Extend `<type>_changed` event payload schemas for Attachment-bearing Object Types (Drawing, EvidenceArtifact, TestProcedure, TestExecution) with optional `attachment_delta` field. MINOR bump (additive). Migrator no-op. Bundles with the runtime-behavior arc per Decision §1.

## Decision §9 — W3 absorption: per-relationship-type schemas + bundle lookup namespace keyed by relationship `type`

**Friction recap.** Both Wedge-001 (Part `oneOf [satisfies, tested_against]`) and Wedge-002 (TestProcedure `oneOf [verifies]`, TestExecution `oneOf [executes, executed_on, produces]`) hit jsonschema's noisy "does not match any of the subschemas" error when a relationship record mismatches expected shape.

**Decision.** The bundle gains a **relationship schema-family / lookup namespace** keyed by relationship `type` (per [Codex2 N1 wording](../Discussions/20260530/20260530-4/Codex2.md)):

```
(bundle_version, lookup_namespace="relationship", discriminator=<type_value>) → schema_path
```

Per relationship type currently in the catalogue: `satisfies`, `composed_of`, `mated_to`, `derived_from`, `refines`, `allocates_to`, `parameter_expression`, `depicts`, `verifies`, `tested_against`, `cites`, `executes`, `executed_on`, `produces` (14 types). Plus a `_base.schema.json` capturing the thirteen base trace-relationship pattern fields per [ADR/0009](0009-relationship-type-satisfies.md) — analogous to per-event-type `_base.schema.json` per [ADR/0003 §"Decision §3"](0003-schema-governance.md).

Object schemas' `relationship:` namespace items reference the dispatch indirectly: each item validates against the schema looked up by `(lookup_namespace="relationship", discriminator=item.type)`. The Object schema no longer carries `oneOf [<list of relationship schemas>]`; it delegates to the bundle lookup-namespace dispatch. Schema errors then name the specific relationship type and field — e.g., `"Relationship of type 'verifies' at relationship[3]: missing required field 'endpoints[0].revision_id'"` rather than `"does not match any of the subschemas"`.

**No new artifact_kind** (per [Codex2 N1](../Discussions/20260530/20260530-4/Codex2.md)). Relationship records are schema-governed embedded records, not standalone artifacts like sidecars / revisions / events / manifests / reservations. [ADR/0009](0009-relationship-type-satisfies.md) already established the `relationship/<type>.schema.json` layout and keyed relationship schemas by `type`; the W3 SCN extends bundle-side organization to surface this as a lookup namespace, without amending [ADR/0003](0003-schema-governance.md)'s canonical artifact-kind set.

**No data shape change.** Existing sidecars + Revisions validate unchanged against the new bundle. Each relationship record still carries `type: <name>` field exactly as today. No migrator required at the data level; only the bundle's schema files reorganize.

**Bump.** MINOR per [Codex1 Q3 answer](../Discussions/20260530/20260530-4/Codex1.md). No artifact bytes change. Old artifacts validate unchanged.

**Alternatives rejected.**
- **Add new required `relationship_type` field:** Codex correctly catches this is a data-shape migration; MAJOR bump per [ADR/0003 §11](0003-schema-governance.md); unnecessary churn — existing `type` field carries the same semantic.
- **Better jsonschema error formatting:** fixes symptom not cause; per-event-type schemas already chosen for events at ADR/0023.
- **Keep `oneOf` aggregation, document the error pattern:** punts on the friction.

**SCN follow-up (Phase 3).** Bundle-organization-only schema refactor + lookup-namespace extension. MINOR bump. Migrator splits existing `oneOf` schemas into per-relationship-type files (already largely the case per ADR/0009); no data migration. Lands after F1 per Codex Q4 ordering.

## Decision §10 — Out of scope (explicit deferrals)

The following are **explicitly NOT** addressed by ADR/0025; each has its own future arc:

- **Layer 3 AI Action Protocol contract** — `propose` / `simulate` / `explain` typed APIs; remains Ring 2 work per [ArchitectureOverview §Layer 3](../ArchitectureOverview.md). ADR/0025 lands the `transaction/` package as a **partial** Layer 3 (begin/commit/rollback boundary only) sufficient for Layer 1/2 to be operational; the full AI surface waits.
- **Layer 4 PR/merge integration** — git-host-specific (GitHub Actions; gitea hooks; signed-tag verification); each host gets its own arc when concretely needed. ADR/0025 produces a runtime that's *compatible* with PR/merge workflow but doesn't author it.
- **Layer 5 Domain Engine adapters** — FreeCAD/OCCT, KiCad; remain Ring 3 work per [OQ-0004](../OpenQuestions.md) / [OQ-0005](../OpenQuestions.md).
- **Acceleration cache implementation** — DuckDB / SQLite index schema, query API surface, refresh semantics; per [ADR/0001 §3](0001-storage-substrate.md) the cache is "per-clone derived" and rebuildable from canonical truth.
- **Production-grade Profile linter (token-stream-based)** — per [ADR/0002 §1 Decision 1](0002-canonical-format.md). Wedge spikes used regex-over-text lint (FRICTION_LOG §2 acknowledges the false-positive case). Lands as its own arc.
- **Concurrency / multi-process safety** — git's own mechanics handle the PR-time case; in-Workspace concurrent processes operating on the same `.aiadra/` are not supported in v0 (single-CLI-process model).
- **Tier-L scaling decisions** per [OQ-0012](../OpenQuestions.md) — directory sharding, event-log sharding, role-based gating. ADR/0025 MUST NOT preclude these.
- **Migrators for the five SCNs** — each SCN arc authors its own migrator per [ADR/0003 §10](0003-schema-governance.md) constraints (deterministic, dry-run, idempotent, no-network, fixture-tested, human-readable diffs).
- **Pyramid testing strategy production-grade** — Wedge spikes used CLI-fixture pytest; production-grade likely wants unit + integration + fixture-based smoke + property-based for invariants. Lands in skeleton arc, not pinned at ADR level.

## Disposition of non-absorbed friction items

Per [Codex1 N1](../Discussions/20260530/20260530-4/Codex1.md), every friction-log item is dispositioned to make "anything missing" auditable.

| Item | Source | Disposition |
|---|---|---|
| Production-grade token-stream Profile linter | Wedge-001 §2 + §4 round-2 B1 | Already declared in [ADR/0002 §1 Decision 1](0002-canonical-format.md) as production requirement. Out of ADR/0025 scope per Decision §10; future focused arc. |
| Byte-mode canonical writes (`atomic_write_bytes`) | Wedge-001 §4 round-2 B2 | Skeleton-arc acceptance — carry the spike's `atomic_write_bytes` + hash-from-disk-bytes pattern forward into `aiadra-core/src/aiadra_core/truth_model/`. No further decision needed. |
| Schema validation at every read | Wedge-001 §4 round-2 B3 + §5 round-3 B1 | Skeleton-arc acceptance — carry the spike's validated load helpers + validated event iterator forward. Already aligns with [ADR/0003 §2](0003-schema-governance.md). Lazy-import code-smell becomes refactoring concern handled within the skeleton arc. |
| Per-event-type schemas | Wedge-001 §2 minor | Already declared in [ADR/0023 §5](0023-wedge-spike-scope-and-runtime.md) + [ADR/0003 §11](0003-schema-governance.md). Skeleton-arc acceptance — split existing `event.schema.json` `oneOf` into per-event-type files. No SCN needed. |
| `initial_sidecar` event payload heaviness | Wedge-001 §2 moderate | Future focused SCN at Tier-M+ scale. Out of ADR/0025 scope; deferred until production case where size cost matters. Carry spike pattern unchanged into skeleton. |
| Workspace vs repo path convention | Wedge-001 §2 + §3 | Skeleton-arc acceptance — production uses **workspace-rooted paths uniformly** (matches the spike-local convention generalized). |
| `schema_version` placement inconsistency across ADRs (0002 / 0004 / 0006 / 0009) | Wedge-001 §2 + §3 | **Pin in skeleton-arc** as per-artifact-kind convention: `object.schema_version` for sidecars/Revisions; top-level `schema_version` for events/manifest; YAML frontmatter `schema_version` for Reservations. No new ADR — matches spike's already-working convention. |
| `merge_key.yaml` negative fixture error message says "aliases" | Wedge-001 §2 minor | Handled by production-grade token-stream Profile linter (above row). No standalone SCN. |
| Windows console cp1252 unicode | Wedge-001 §2 minor | Skeleton-arc acceptance — carry `sys.stdout.reconfigure(encoding="utf-8")` from spike CLI entry. Production hardening: env var `PYTHONIOENCODING=utf-8` for CI. No SCN. |
| Spike-grade REQUIRED fields beyond canonical optionality | Wedge-001 §2 minor | Skeleton-arc acceptance — relax to canonical optionality per [ADR/0005](0005-object-type-part.md) / [ADR/0006](0006-object-type-requirement.md). No SCN. |
| Parameter shape hybrid (`{id, name, value, datatype, unit, fact_provenance}` vs `value_<unit>`) | Wedge-002 §2 minor + §3 | **Future focused SCN.** Canonical form choice deserves its own focused arc with full alternatives survey. Not absorbed into ADR/0025 because the decision shape doesn't fit the production-runtime ADR — it's a TruthModelSchema / canonical-shape decision. |
| No top-level `attachments` section in manifest | Wedge-002 §2 minor + §3 | **Future focused SCN if production query patterns require it.** Attachment hashes are transitively pinned via Revision content per ADR/0024. |
| V&V chain integrity single-instance only in basic Wedge-002 demo | Wedge-002 §2 minor + §3 | Skeleton-arc acceptance — algorithm generalizes naturally (nested-loop traversal). Production-grade `validate_v_and_v_chain_integrity` ports the spike's algorithm and exercises it against multi-instance fixtures in the integration test suite. No SCN. |

## Alternatives

Top-level alternatives considered and rejected for ADR/0025 itself:

- **Skip the scope-first ADR and go straight to skeleton implementation.** Rejected: would re-decide the six friction-item directions informally during implementation. Scope-first ADR is the pattern set by [ADR/0023](0023-wedge-spike-scope-and-runtime.md) + [ADR/0024](0024-wedge-002-spike-scope.md); breaking the pattern just for production-grade entry is unjustified.
- **Run a third Wedge spike before authoring ADR/0025.** Wedge-003 would teach about additional Object Types (Component / SoftwareModule / Drawing) in code, not about the runtime itself. Combined Wedge-001 + Wedge-002 friction is already sufficient for the runtime decisions.
- **Land all five SCNs as bundle v0.20.0 in one arc.** Each SCN is independently scoped + reviewable; bundling forces every Codex review to span all five concurrently. Sequential phases keep arcs reviewable.
- **Per-decision alternatives** are surveyed in-line in Decisions §4-§9 above.

## Consequences

**Layer 1 / Layer 2** — operationalized end-to-end in the skeleton + runtime-behavior arcs. ADR/0001 sidecar/event invariant becomes a runtime check in the validate phase of every Transaction; ADR/0002 Profile lint runs in validate phase; ADR/0003 bundle digest + schema validation runs in validate phase; ADR/0004 cross-artifact atomicity operationalized via Draft-then-commit per CLI command.

**Layer 3** — partial materialization (begin/commit/rollback boundary only); the full AI Action Protocol typed API remains Ring 2 work per [ArchitectureOverview §Layer 3](../ArchitectureOverview.md).

**Layer 4** — runtime is compatible with PR/merge workflow but ADR/0025 does not author the host-specific integration. The git-commit-as-atomicity-boundary in Decision §6 is the substrate Layer 4 will sit on; PR review of AIADRA-managed commits proceeds normally.

**Spike code** — Wedge-001 + Wedge-002 stay frozen at `spikes/wedge-001/` + `spikes/wedge-002/`. Their friction logs become the historical audit trail for ADR/0025's decisions. No migration; no refactoring.

**SCN sequence** — five MINOR-bump bundle updates land sequentially across Phases 1-4:
- Phase 1: W1 SCN (`prior_stage_manifest_ref` + `stage_number` + `final_stage` + `release_staged` event) + W2 SCN (`<type>_changed` event payload `attachment_delta` for Attachment-bearing Types). Bundle v0.19.0 → v0.20.0.
- Phase 2: F1 SCN (`parameter_changed.new_fact_provenance`). Bundle v0.20.0 → v0.21.0.
- Phase 3: W3 SCN (relationship lookup namespace + per-type schema split). Bundle v0.21.0 → v0.22.0.
- Phase 4: F2 SCN (`threshold_expression` on `acceptance_criterion`). Bundle v0.22.0 → v0.23.0.

**Pattern Catalogue** — no new row added by ADR/0025 itself. The opt-in primitive pattern (Decision §5 hybrid threshold) reuses the per-relationship-schema opt-in discipline from [ADR/0021](0021-relationship-types-v-and-v.md). Each SCN arc may add catalogue rows if its decisions warrant.

**Coherence Checklist** — no new item added by ADR/0025 itself. Codex2 walked all 10 items; B3 absorption explicitly addresses watch-flags on Binding ownership / Identity cross-check / Execution-record cardinality (final-stage cross-graph validation).

**Manifesto P11 (AIADRA Core hosts nothing)** — preserved across all six absorptions. Draft-then-commit is Workspace-local; staged release is Workspace-local; attachment Transactions are Workspace-local; relationship dispatch is bundle-local. No service, no central coordinator, no registry.

**Manifesto P12 (three-tier on Git)** + **P13 (AI Workspace-native)** — reinforced. Git commit IS the atomicity boundary; AI agents operate via the same Transaction surface as humans.

## References

- [Manifesto.md](../Manifesto.md) — P10, P11, P12, P13 (load-bearing).
- [ArchitectureOverview.md](../ArchitectureOverview.md) — five-layer model; §"Open structure beyond Ring 0" deferrals.
- [Glossary.md](../Glossary.md) — Wedge, Transaction, Reservation, Manifest, Attachment, Vault.
- [TruthModelSchema.md](../TruthModelSchema.md) — Ring 1 abstract spine.
- [ADR/0001](0001-storage-substrate.md) §3 (Release Manifest semantics) + §4 (sidecar/event invariant) + §5 (git mechanics) + §6 (locality tiers).
- [ADR/0002](0002-canonical-format.md) §1 (Profile + token-level linter declared as production requirement).
- [ADR/0003](0003-schema-governance.md) §2 (bundle index lookup) + §7 (validator behavior taxonomy) + §9 (digest verification) + §10 (migrator constraints) + §11 (governance ceremony).
- [ADR/0004](0004-number-allocation.md) §6 (atomicity claim — operationalized by Decision §6).
- [ADR/0009](0009-relationship-type-satisfies.md) — pre-existing `relationship/<type>.schema.json` layout (Decision §9 builds on).
- [ADR/0015](0015-relationship-type-parameter-expression.md) — fact-level addressing (Decision §5 builds on).
- [ADR/0017](0017-object-type-drawing.md) §2 — Attachment-bearing template (Decision §8 builds on).
- [ADR/0021](0021-relationship-types-v-and-v.md) §6 (per-relationship-schema opt-in pattern — Decision §5 reuses) + §7 (verification-method-consistency-as-tooling-aided posture).
- [ADR/0022](0022-test-execution-model.md) §3-§6 — execution-instance cardinality + Fixed-at-authoring (Decision §7 preserves cross-stage).
- [ADR/0023](0023-wedge-spike-scope-and-runtime.md) — first code-producing-direction ADR; precedent for scope-first ADR.
- [ADR/0024](0024-wedge-002-spike-scope.md) — second code-producing-direction ADR; precedent for friction-log-informed ADR.
- [`spikes/wedge-001/FRICTION_LOG.md`](../../spikes/wedge-001/FRICTION_LOG.md) — F1 / F2 / F3 + minor items.
- [`spikes/wedge-002/FRICTION_LOG.md`](../../spikes/wedge-002/FRICTION_LOG.md) — W1 / W2 / W3 + §4 cross-spike comparison.
- [OQ-0007](../OpenQuestions.md) — Wedge scope adequacy (resolved by arc 20260530-1; build-on framing exercised here).
- [OQ-0012](../OpenQuestions.md) — Tier-L scale-sensitive structural commitments (Decision §10 explicitly preserves).
- [PROTOCOL.md](../Discussions/Transfer/PROTOCOL.md) — pipeline-cap discipline (Decision §1 sequencing preserves).
- Arc 20260530-4 discussion: [Claude1](../Discussions/20260530/20260530-4/Claude1.md), [Codex1](../Discussions/20260530/20260530-4/Codex1.md), [Claude2](../Discussions/20260530/20260530-4/Claude2.md), [Codex2](../Discussions/20260530/20260530-4/Codex2.md).
