---
name: adr-0002-canonical-format
status: accepted
date: 2026-05-17
supersedes: none
superseded_by: none
resolves: [OQ-0011]
---

# ADR/0002 — Canonical On-Disk Format

## Status

**Accepted** — 2026-05-17. Sibling decision to [ADR/0001](0001-storage-substrate.md), which settled the substrate; this one settles the format used by that substrate's three text-artifact classes.

## Context

[ADR/0001](0001-storage-substrate.md) committed the Product Truth Model to filesystem-canonical text artifacts in the project's Git repo, with three classes — **sidecars** (current authoritative Object state), **event log** (approved transitions and provenance), **release manifests** (frozen, signable Release records). Of these, two were incidentally pinned in ADR/0001: **JSONL** for events and **deterministic JSON** for manifests. ADR/0002's job is to formally record those choices and settle the remaining open question — **sidecar format** — recorded as [OQ-0011](../OpenQuestions.md).

Sidecars are the format that contributors interact with directly. They are read more often than written, edited by humans and AI, reviewed in PRs, merged across branches, parsed by validators on every commit, and expected to survive multi-decade open-source projects. Format choice for sidecars is therefore the most user-visible of the three, and the one most exposed to long-term maintenance risk.

Per the Manifesto Scale Targets framing, format is *scale-sensitive* (parse cost at 100k objects, merge-conflict shape, schema-migration ergonomics, AI parsing cost), so it falls in the *decide-early-and-probe* bucket: settle the choice now, stress-test against synthetic Tier-M / Tier-L data in Ring 1, revisit if the test surfaces unacceptable churn.

A side-by-side spike comparing YAML 1.2 against KiCad-style S-expressions on a representative sidecar (the Wedge's Motor Mount Bracket Object) was conducted in [Claude5.md](../Discussions/20260517/Claude5.md); GPT5 reviewed it and returned the corrections this ADR incorporates.

## Alternatives Considered

### For sidecars

**A1. YAML 1.2, with the AIADRA YAML Profile.** *Chosen — see Decision.*

**A2. KiCad-style S-expressions.**

> **Held as recorded fallback, not chosen as default.** Wins on correctness-at-scale axes — explicit delimiters, no spec ambiguity, robust merging at high contributor counts, schema-migration cleanliness. Loses on adoption / readability / cross-domain neutrality axes — niche outside Lisp / KiCad / Racket worlds; the narrative fields (design-intent rationale, requirement statements) read awkwardly as concatenated string lists; KiCad's tooling isn't directly reusable. AIADRA's sidecars span every domain (mechanical, electrical, software, procurement, DV), not only EDA, so a domain-neutral format with broad familiarity wins on this generation of the project. The fallback record exists because the trade-off is genuine, not a clear-cut domination — if Ring 1 stress tests reveal that YAML merge churn at Tier L is unacceptable, S-expressions remain a viable migration target.

**A3. TOML.**

> **Rejected.** Strong for flat key-value config; weak for the deeply nested list-of-object structures that dominate product engineering data (parts containing parameters containing provenance containing event references). TOML forces awkward subscript-style nesting that defeats readability. The shape of the data fights the format.

**A4. JSON5 / HJSON.**

> **Rejected.** Variants of JSON that add comments. Comments were the main thing JSON lacked for human-edited data, but ecosystem support for these dialects is thin, IDE integration is inconsistent, and engineering tooling rarely speaks them natively. YAML solves the comment problem with broader support.

**A5. Markdown + YAML front-matter.**

> **Deferred, not rejected.** This format is plausibly attractive for narrative-heavy Objects in later Rings — long-form requirements documents, design-intent essays, ADRs themselves. But for general sidecars (parts, parameters, references, structured metadata) the structured-body parsing surface would grow, and the dual-format complexity would multiply schema-governance work. Reconsidered at the Ring at which narrative Objects gain weight.

**A6. Custom DSL.**

> **Rejected.** Parser maintenance burden, ecosystem of zero, no precedent for AIADRA-specific syntax to justify. The cost of inventing a format is paid every time a contributor opens a sidecar for the first time, and AIADRA's job is to lower that cost, not raise it.

**A7. Binary formats (protobuf, FlatBuffers, CBOR).**

> **Rejected.** Defeat human readability, the primary requirement for sidecars. Sidecars exist to be diff-able in Git, reviewable in PRs, hand-editable when necessary, and visually parseable by AI agents without specialized loaders. Binary formats invert all of these properties.

### For events

**B1. JSONL (newline-delimited JSON).** *Chosen — settled in [ADR/0001](0001-storage-substrate.md) §1 and re-confirmed here.* Append-only line-mergeable text is exactly what an event stream that lives in Git needs.

**B2. YAML stream / NDJSON variants.**

> **Rejected.** Less ecosystem support; YAML streams in particular invite the same ambiguity footguns YAML 1.1 introduces, which the AIADRA YAML Profile takes pains to neutralize for sidecars but isn't worth doing twice.

### For release manifests

**C1. Deterministic JSON.** *Chosen — settled in [ADR/0001](0001-storage-substrate.md) §1 and re-confirmed here.* Sorted keys, canonical numeric serialization, no whitespace variation across runs. Required because manifests must be content-hashable and signable.

**C2. CBOR / protobuf / binary canonical formats.**

> **Rejected.** Would gain a tighter canonical form but lose human readability. Manifests are reviewed by release managers; readability matters.

## Decision

### 1. Sidecars use the **AIADRA YAML Profile**

The AIADRA YAML Profile is a strict subset of YAML 1.2 with explicit constraints, enforced by AIADRA Core's own parser/validator at every read:

- **YAML 1.2 only.** No 1.1 fallback. A `%YAML 1.2` directive at the top of every sidecar serves as a machine-readable version label and a cheap tripwire — but it is documentation, not enforcement.
- **One managed Object per sidecar.** Features and inline children may be structured children of their parent Object's record (Ring 1 settles the exact shape). Unrelated managed Objects never share a file.
- **All ambiguous scalars must be quoted.** This includes UUIDs, Numbers, version strings (e.g., `"0.1.0"`), anything starting with `0`, and anything that could be interpreted as a YAML boolean under any reading (`yes`/`no`/`on`/`off`/`true`/`false`/`Y`/`N`). Enforcement is at the token level — JSON Schema alone runs post-parse and cannot tell whether a scalar was originally quoted, so the AIADRA YAML Profile requires a token-level linter check in addition to schema validation.
- **No anchors (`&name`), aliases (`*name`), merge keys (`<<:`), or custom tags (`!!...`).** Plain YAML only. Sidecars are boring, deterministic records, not a clever-YAML showcase.
- **Duplicate keys are rejected.** Not silently last-wins (which is the YAML default in many parsers); rejected with a hard validation error.
- **JSON Schema validation at every read.** Schemas live under AIADRA Core source control, versioned independently of the Product Truth Model. Schema governance details settled in ADR/0003.
- **AIADRA Core ships the strict YAML parser profile.** AIADRA does not rely on third-party YAML libraries' default behavior — too variable across versions and languages. Any conforming consumer (third-party tooling, alternative implementations) MUST use the AIADRA YAML Profile parser or a verified equivalent.

The one-line summary that codifies the Profile:

> **AIADRA YAML Profile** = YAML 1.2, one managed Object per file, quoted ambiguous scalars, no anchors / aliases / merge keys / custom tags, duplicate keys rejected, JSON Schema validation at every read.

A worked example — the Wedge's Motor Mount Bracket sidecar in conforming form:

```yaml
%YAML 1.2
---
schema_version: "0.1.0"
object:
  uuid: "0193f9a0-7e3c-7c6f-9d2a-1c84b54a92ee"
  number: "P-000001"
  type: part
  name: "Motor Mount Bracket"
  lifecycle:
    state: in_work
    iteration: 3
parameters:
  - name: plate_thickness_mm
    type: float
    value: 6.0
    unit: mm
    provenance: human_input
    uncertainty: verified
    last_changed_by_event: "e-0042"
  - name: hole_diameter_mm
    type: float
    value: 8.5
    unit: mm
    provenance: computed_result
    uncertainty: computed
    last_changed_by_event: "e-0039"
design_intent:
  role: "Mounting plate for motor MTR-0007"
  depends_on:
    - "REQ-0014"
  rationale: |
    Plate must clear the M8 mounting hardware while remaining
    rigid enough to transfer torque under load case LC-3.
references:
  requirements:
    - uuid: "49f01a40-2b1d-4e7e-bd49-1ce6d8efff9e"
      number: "REQ-0014"
      relation: satisfies
  parent_assembly:
    uuid: "c34f9120-b88a-4f73-be7b-22e9d6a01abc"
    number: "A-000003"
provenance:
  created_by_event: "e-0001"
  current_revision: A
```

### 2. Events use JSONL

One JSON object per line. Append-only. Each event carries its Transaction ID, ISO-8601 UTC timestamp, actor identity, provenance, schema_version, and a structured payload describing the transition. Lines are line-mergeable in Git; the event log file may be sharded by time period (Ring 1 settles the sharding strategy per [OQ-0012](../OpenQuestions.md)).

### 3. Release manifests use deterministic JSON

Sorted keys (lexicographic), canonical numeric serialization (no `1.0` vs `1` ambiguity), normalized whitespace. The manifest is content-hashable; the hash is what gets signed. Multiple AIADRA tools generating the manifest for the same Release MUST produce byte-identical output.

### 4. Schema versioning is mandatory on every artifact

Every sidecar, every event-log file header (or per-event when sharded), and every release manifest carries a `schema_version` field. AIADRA Core's validator refuses unrecognized versions and provides migration paths for recognized older versions. Schema governance — registry, migrators, version-bump policy — lives in ADR/0003.

### 5. S-expressions held as recorded fallback

The decision between YAML and KiCad-style S-expressions for sidecars was genuinely close. The AIADRA YAML Profile mitigates YAML's spec-ambiguity footguns, but it does not eliminate indentation-significance and its merge-conflict consequences. **Ring 1 stress tests MUST explicitly evaluate YAML merge churn under synthetic Tier-M and Tier-L workloads.** If the result is unacceptable — high false-positive conflict rate, frequent silently-valid-but-wrong merges, reviewer fatigue — a follow-up ADR will reopen this decision and consider migration to S-expressions. No numerical trigger threshold is invented now; the Ring 1 evaluation will define what "unacceptable" means in context.

## Rationale

- **Engineer familiarity is gravity.** Almost every engineer has read YAML. Few have read S-expressions outside Lisp / KiCad. AIADRA's Tier-M / Tier-L survival depends on contributors being productive on day one, not learning a new syntax. This argument is weighted more heavily by the project's stage (Ring 0, no contributors yet, Wedge ahead) than it might be later.
- **Readability dominates the lifecycle cost.** Sidecars are read 100x more than they are written. The `|` block scalar in YAML handles design-intent rationale, requirement statements, and audit-trail prose gracefully; S-expr string concatenation does not.
- **Cross-domain neutrality.** AIADRA sidecars carry primitives from every domain — mechanical, electrical, software, procurement, DV, documentation. A domain-neutral format with broad familiarity wins; a format tightly associated with EDA does not.
- **The AIADRA YAML Profile neutralizes most YAML footguns.** Strict 1.2 + quoting discipline + no clever features + duplicate-key rejection + JSON Schema validation + token-level linter = the parser-ambiguity argument loses most of its force. What remains (indentation-significance merge risk) is mitigated by one-Object-per-sidecar discipline and will be empirically evaluated in Ring 1.
- **JSONL for events because append-only line-mergeable is exactly what event logs need.** Every tool reads it; merges resolve per-line; no parser ambiguity. The right shape for the right job.
- **Deterministic JSON for manifests because they need to be content-hashable and signable.** Determinism beats readability when content is machine-generated and verified by hash.
- **The fallback record honors the genuine trade-off.** S-expr really does win on correctness-at-scale axes. If Ring 1 surfaces that the trade-off has tipped, the project should be free to migrate without feeling like ADR/0002 was a fixed permanent commitment.

## Consequences

### Enables

- Standard YAML tooling (every editor, every linter, every language binding) works on sidecars from day one.
- Schema validation via standard JSON Schema infrastructure.
- Merge review via standard Git diff tooling.
- AI parsing via every available YAML library — and via the strict AIADRA YAML parser for correctness-critical paths.
- Migration to a different format is preserved in principle: the AIADRA YAML Profile is strict enough that converting to S-expressions or another structured format would be largely mechanical, not a re-authoring effort.

### Costs / accepted tradeoffs

- **AIADRA Core must maintain a strict YAML parser profile.** Not free. Likely a thin wrapper over an existing library (PyYAML, ruamel.yaml, or equivalent in the chosen implementation language) plus a token-level linter for the quoting rule. The wrapper is a real piece of code that must be tested, versioned, and ported across language bindings.
- **A token-level linter is required in addition to JSON Schema.** Schema validation runs post-parse and cannot always tell whether a scalar was originally quoted (it sees the resolved value, not the input syntax). The linter closes this gap.
- **YAML's indentation-significance remains a latent merge-conflict risk at Tier L.** Mitigated by one-Object-per-sidecar discipline; not eliminated. Ring 1 stress tests must evaluate this; the fallback path exists for exactly this case.
- **Per-read validation has a performance cost.** The Acceleration Cache (ADR/0001 §3) must hold validated parsed structures so the cost is paid once per change-of-source, not once per query.
- **Schema governance becomes load-bearing immediately.** ADR/0003 cannot be deferred far past this one.

### Defers

- **ADR/0003 — Schema governance.** Schema registry, migration policy, JSON Schema authoring conventions, validator implementation. Cannot be deferred far — the AIADRA YAML Profile depends on it.
- **Ring 1** — explicit synthetic-scale stress tests of YAML merge churn at Tier-M and Tier-L; reopen this ADR if the result is unacceptable.
- **Markdown + YAML front-matter** — possibly used in later Rings for narrative-heavy Objects (long-form requirements, design-intent essays); not used for general sidecars.
- **Event-log and manifest schemas** — specific field shapes settled when Ring 1 defines the Truth Model Schema.

### Resolves

- **OQ-0011** — Canonical on-disk format.

## References

- [Manifesto](../Manifesto.md) — Principle 10 (history is event-based, current state is flat), Principle 12 (three-tier), Scale Targets section.
- [Glossary](../Glossary.md) — Sidecar, Event, Release Manifest, AIADRA YAML Profile, Sidecar/event invariant.
- [ADR/0001](0001-storage-substrate.md) — Storage substrate (JSONL events and deterministic-JSON manifests originally pinned there).
- [OpenQuestions](../OpenQuestions.md) — OQ-0011 (resolved here); OQ-0013 (schema governance, target ADR/0003).
- Discussion thread (git-ignored, local-only): `Docs/Discussions/20260517/Claude3.md` §6, `Claude4.md` §3, `Claude5.md` (spike), GPT5 review (2026-05-17).
