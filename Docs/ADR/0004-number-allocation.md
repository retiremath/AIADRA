---
name: adr-0004-number-allocation
status: accepted
date: 2026-05-18
supersedes: none
superseded_by: none
resolves: [OQ-0015]
---

# ADR/0004 — Number Allocation: Reservation File Shape

## Status

**Accepted** — 2026-05-18. Fills the long-reserved ADR/0004 slot (targeted at Ring 0 close 2026-05-17, deferred until Ring 1 settled what the Reservation file needed to contain). Resolves [OQ-0015](../OpenQuestions.md). Adds `reservation` as the fifth artifact kind under [ADR/0003 §2](0003-schema-governance.md)'s extensible artifact-kind taxonomy.

## Context

[S2.5](../TruthModelSchema.md#s25--object-creation-and-number-binding-lifecycle) settled the Number-binding *lifecycle*:

- Number required at Object creation (commitment 1).
- Allocation atomic with `object_created` (commitment 2); writes to the Reservation file in the same atomic commit.
- Conflicts resolve pre-merge through Git rebase (commitment 3).
- Pre-merge branch history may be rewritten; merged history immutable (commitment 4).
- Numbers stable after merge by default (commitment 5).
- `number_rebound` exists for rare ceremony-heavy renumbering (commitment 6); retires old Number as permanently retired alias (commitment 7).
- Released Revision records keep their release-time Number (commitment 8).
- Number format / Type → prefix mapping per-project policy (commitment 10).
- `object.number` is governed identity metadata, not provenance-bearing (commitment 11).

S2.5 also handed off seven explicit acceptance criteria for the Reservation file shape:

> The file must support: current Number → Object UUID binding; retired Number alias → Object UUID binding; rejection of reuse for both current and retired Numbers; atomic create allocation with `object_created`; atomic rebind allocation with `number_rebound` (old Number to retired); merge-conflict detection on the Number key; history sufficient to explain why a Number is retired.

The seed catalogue has now declared its Number prefixes:

- Part `P-NNNNNN` ([ADR/0005 §2](0005-object-type-part.md))
- Requirement `REQ-NNNNNN` ([ADR/0006 §2](0006-object-type-requirement.md))
- Assembly `ASM-NNNNNN` ([ADR/0007 §10](0007-object-type-assembly.md))

What was missing: the actual file structure that allocations write to. ADR/0004 fills that gap.

The discussion trail in [`Docs/Discussions/20260518-8/`](../Discussions/20260518-8/) carries the full alternatives reasoning. Codex1 produced two hard blockers (YAML mapping key vs list-of-records shape; cross-artifact commit-level invariant strength) plus several refinements; all corrections accepted. Codex2 green-lit with two non-blocking polish notes (duplicate-key rejection layer; Glossary generalization timing), both absorbed.

## Alternatives Considered

The four options from [OQ-0015](../OpenQuestions.md), evaluated against current spine maturity:

### A1. Per-Type Reservation files

One file per Number prefix. Merge-conflict granularity per Type.

> **Chosen — see Decision §1.** Confirmed by current spine. Aligns with S2.5's per-Type semantic (each prefix has its own allocation policy); aligns with `number_rebound`'s retire-one-alias semantics within a Type's file.

### A2. Single project Reservation file

One file covering all Types' allocations.

> **Rejected.** Coarser merge granularity. Two contributors authoring different Object Types collide on the same file. Per-Type's finer granularity is strictly better at Tier-L scale.

### A3. No Reservation file; PR-merge counter

Numbers assigned at PR-merge time from monotonic counter; not stable until merged.

> **Rejected.** [S2.5 commitment 5](../TruthModelSchema.md#5-numbers-are-stable-after-merge-by-default) requires Numbers stable after merge, but allocation must happen pre-merge — events reference Numbers and need to exist on the working branch. PR-merge-counter assignment means events reference a Number that doesn't exist until merge, breaking the event log's consistency.

### A4. Block allocation per Workspace

Pre-reserve a block (e.g., `P-001000` through `P-001099`) per Workspace at first use. Fewer conflicts at high contributor counts.

> **Deferred.** Held in reserve for Tier-L scale per [OQ-0015](../OpenQuestions.md) current instinct. Option 1 is sufficient for Tier-S / Tier-M (Wedge era through most open-source hardware projects). When Tier-L (50K+ Objects, 50+ contributors) surfaces unacceptable merge churn, a future Schema Change Note adds block allocation additively (a `block_reservations:` mapping alongside `reservations:` with the existing entries recording concrete allocations within those blocks).

## Decision

Ten commitments.

### 1. Per-prefix Reservation artifact at `Docs/Reservations/<TypePrefix>.yaml`

One Reservation artifact per Number prefix. Path: `Docs/Reservations/P.yaml`, `Docs/Reservations/REQ.yaml`, `Docs/Reservations/ASM.yaml`, etc.

Path matches where canonical engineering artifacts live (`Docs/` per [ADR/0001](0001-storage-substrate.md)) — Reservation files are canonical truth, not project / infrastructure config.

**Consolidated Reservation artifacts** (one file covering multiple prefixes) are **NOT permitted under this ADR.** They have a different schema, different conflict behavior, and different validation. A future Schema Change Note or ADR may introduce a `consolidated_reservation` artifact kind with its own discriminator and validation story.

### 2. Reservation as the fifth artifact kind

`reservation` joins the artifact-kind set under [ADR/0003 §2](0003-schema-governance.md)'s `(bundle_version, artifact_kind, discriminator) → schema` lookup. Existing kinds are `sidecar`, `event`, `manifest`; [S2 commitment 1](../TruthModelSchema.md#1-revisions-are-separate-immutable-schema-governed-artifacts) committed `revision` as the fourth. ADR/0004 commits `reservation` as the fifth.

The discriminator is the Number prefix. Schema lookup: `(bundle_version, "reservation", "P") → reservation/P.schema.json`.

Bundle bump: **MINOR additive** per [ADR/0003 §11](0003-schema-governance.md). Existing artifact-kind values' lookup unchanged; the new kind adds a new entry without breaking anything. Bundle v0.4.0 → v0.5.0.

ADR ceremony required per the [amended Promotion Rule commitment 6](../TruthModelSchema.md#6-promotion-ceremony) — adding a new artifact kind is "introducing or changing a reusable modeling pattern" and a "new convention expected to constrain later Type ADRs." Same level of decision as S2 commitment 1.

### 3. Artifact header + `reservations:` mapping (Number is the mapping key)

```yaml
---
name: aiadra-reservation-P
status: active
schema_version: "0.5.0"
artifact_kind: "reservation"
discriminator: "P"
---

# Number Reservation artifact for Object Type with prefix P-
# One artifact per Number prefix. Entries are keyed by Number.
# Append-mostly; entries mutate status from "current" to "retired" only via
# number_rebound (Transaction-atomic per Decision §6).
# Canonical ordering: ascending by Number.

reservations:
  "P-000001":
    object_uuid: "0193abcd-1234-..."
    status: "current"
    allocated_at: "2026-05-18T10:00:00Z"
    allocated_by_transaction: "txn_2026_05_18_001"

  "P-000007":
    object_uuid: "0193ffff-5678-..."
    status: "retired"
    allocated_at: "2026-05-18T10:05:00Z"
    allocated_by_transaction: "txn_2026_05_18_003"
    retired_at: "2026-06-15T14:30:00Z"
    retired_by_transaction: "txn_2026_06_15_017"
    retirement_reason: "Renumbered to P-000123 per ECO-007"

  "P-000123":
    object_uuid: "0193ffff-5678-..."   # same UUID as P-000007 — alias history
    status: "current"
    allocated_at: "2026-06-15T14:30:00Z"
    allocated_by_transaction: "txn_2026_06_15_017"
```

**The Number is the YAML mapping key**, not a field inside a value object. The key carries identity; the value carries binding plus audit metadata.

Each value object's fields:

- **`object_uuid`** — REQUIRED. The Object the Number binds to. A single Object may appear in multiple entries (one `current` plus N `retired` aliases per S2.5 commitment 7).
- **`status`** — REQUIRED. `current` or `retired`.
- **`allocated_at`** — REQUIRED. ISO 8601 timestamp.
- **`allocated_by_transaction`** — REQUIRED. Reference to the Transaction (`object_created` or `number_rebound`) that allocated this Number.
- **`retired_at`** — REQUIRED when `status: retired`; FORBIDDEN when `status: current`.
- **`retired_by_transaction`** — REQUIRED when retired. Reference to the `number_rebound` Transaction.
- **`retirement_reason`** — REQUIRED when retired. Human-readable justification per [S2.5 commitment 6](../TruthModelSchema.md#6-number_rebound-exists-for-rare-ceremony-heavy-renumbering). **Stronger approval ceremony itself lives in the Transaction / Layer 4 record**, not in the free-text field alone; this field is for legibility, not approval.

The Number is NOT duplicated inside the value object as a self-check field — the mapping key carries it once.

**Canonical ordering: entries appear in ascending Number order.** Deterministic ordering keeps diffs stable and review friction predictable.

### 4. AIADRA YAML Profile compliance, cardinality scoped per artifact kind

Reservation artifacts follow the [AIADRA YAML Profile](0002-canonical-format.md): strict YAML 1.2, all ambiguous scalars (Numbers, UUIDs, timestamps) quoted, no anchors / aliases / merge keys / custom tags, **duplicate-key rejection**, JSON Schema validation at every read.

The Profile's cardinality phrase ("one managed Object per file" in the Glossary entry pre-this-ADR) is **sidecar-specific**. Reservation artifacts have their own cardinality: **one Reservation artifact per file, scoped to one Number prefix.** The prefix in the artifact header's `discriminator` field matches the Number-key regex enforced by the per-prefix schema.

The Glossary's *AIADRA YAML Profile* entry is generalized in v0.9 (landing with this ADR) to reflect cardinality per artifact kind: sidecar = one Object; Revision = one frozen Object snapshot; Reservation = one Number prefix's allocations.

The duplicate-key rejection is now **directly load-bearing**: two branches both adding the same Number as a mapping key produce a duplicate-key file after merge, caught by the Profile parser BEFORE semantic validation runs.

### 5. Schema factoring — `_base` + per-prefix wrappers

The schema bundle ships:

- **`reservation/_base.schema.json`** — common value shape (`object_uuid`, `status`, `allocated_at`, `allocated_by_transaction`, optional retirement metadata). Status-dependent requirements: retirement metadata REQUIRED when `status: retired`; FORBIDDEN when `status: current`.
- **Per-prefix wrapper schemas** — `reservation/P.schema.json`, `reservation/REQ.schema.json`, `reservation/ASM.schema.json`, etc. Each is a tiny wrapper that sets the prefix-specific Number-key regex via `patternProperties` and `additionalProperties: false`, then `$ref`s the shared `_base.schema.json` for value shapes.

Sketch of `reservation/P.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "reservations": {
      "type": "object",
      "patternProperties": {
        "^P-[0-9]{6}$": { "$ref": "_base.schema.json#/$defs/reservationValue" }
      },
      "additionalProperties": false
    }
  },
  "required": ["reservations"]
}
```

The [ADR/0003 §2](0003-schema-governance.md) lookup `(bundle_version, "reservation", "P") → reservation/P.schema.json` resolves to the wrapper; the wrapper enforces the prefix-specific Number regex and inherits the shared value shape.

**Layer separation:**

- **AIADRA YAML Profile parser** enforces duplicate-mapping-key rejection (the load-bearing protection against branch conflicts).
- **Schema validator** enforces prefix / key shape (regex) and value shape (object_uuid, status, audit fields, status-dependent requirements). **Schema validation does not enforce key uniqueness** — that is the parser's responsibility.

### 6. Transaction-atomic cross-artifact invariant

A commit that creates or modifies a Reservation entry MUST contain all coherent parts of the Transaction. The Layer-2 validator hard-rejects any commit that touches a Reservation entry without the full coherent set. This is the Reservation-file version of the sidecar/event invariant ([ADR/0001 §4](0001-storage-substrate.md)).

**For `object_created`** — same Git commit MUST contain:

- (a) The new sidecar with matching `object.uuid` and `object.number`.
- (b) The `object_created` event with matching payload (`uuid`, `number`, `transaction_id`).
- (c) The Reservation entry under the matching Number mapping key with matching `object_uuid` and `allocated_by_transaction`.

All four references must agree: `sidecar.object.uuid` == event payload `uuid` == Reservation entry's `object_uuid`; `sidecar.object.number` == event payload `number` == Reservation entry's mapping key; event payload `transaction_id` == Reservation entry's `allocated_by_transaction`.

**For `number_rebound`** — same Git commit MUST contain:

- (a) The sidecar's `object.number` updated to the new value.
- (b) The `number_rebound` event with matching payload (`object_uuid`, `old_number`, `new_number`, `transaction_id`, `justification`).
- (c) The old Reservation entry mutated from `status: current` to `status: retired`, with matching `retired_by_transaction` (= the rebound transaction id) and matching `retirement_reason` (= the rebound event's `justification`).
- (d) The new Reservation entry added under the new Number mapping key with matching `object_uuid` and matching `allocated_by_transaction` (= the rebound transaction id).

All five references must agree across sidecar, event, retired entry, and new current entry. The Transaction referenced by `allocated_by_transaction` / `retired_by_transaction` is not merely required to exist — it must be the Transaction whose event payload authorizes that specific allocation or retirement.

**Partial commits cannot land.** A Reservation entry without the matching sidecar + event is a hard reject. A sidecar + event without the Reservation entry is a hard reject. A `number_rebound` triple missing any of the four pieces is a hard reject.

No live-coordination violation per [Manifesto P11](../Manifesto.md) / [ADR/0001 §5](0001-storage-substrate.md): the validator checks a local Git commit before it becomes canonical truth. No server is consulted; no remote allocator is required.

### 7. Conflict resolution via Git rebase per S2.5

Two contributors authoring new Objects in parallel branches may pick the same Number. The conflict is detected at parse time:

- **Duplicate mapping keys are rejected by the YAML Profile parser** (per [ADR/0002 §1](0002-canonical-format.md)). Two branches both adding `"P-000042":` as a mapping key produce a duplicate-key file after Git's textual merge; the Profile parser fails the merged file before any semantic validator runs.
- Schema validation enforces prefix / key shape (regex), not duplicates — duplicate-key rejection is the parser's responsibility.

Resolution flow per [S2.5 commitment 3](../TruthModelSchema.md#3-reservation-conflicts-resolve-pre-merge-through-git-rebase):

1. One PR merges first; its allocation wins.
2. The second contributor rebases. Local tooling picks a new Number; the local `object_created` event's `number` field is rewritten on the unmerged branch (allowed pre-merge per [S2.5 commitment 4](../TruthModelSchema.md#4-merged-event-history-is-immutable-pre-merge-branch-history-may-be-rewritten)); the local Reservation entry's mapping key is updated; the sidecar's `object.number` is updated; the branch is force-pushed.
3. Re-attempt the PR with the new Number.

The Transaction-atomic invariant from Decision §6 means the rebase must atomically update all three artifacts (sidecar, event, Reservation entry) on the rebased branch — partial rewrites cannot land.

### 8. Status transitions are monotonic forward

A Reservation entry's `status` transitions only `current → retired`, never backwards. The reverse ("un-retire") is forbidden — [S2.5 commitment 7](../TruthModelSchema.md#7-number_rebound-retires-the-old-number-as-an-alias) makes retired aliases permanent, never reassignable.

A retired entry cannot be deleted. The mapping key remains forever; the entry's `status: retired` plus retirement metadata preserve the binding history.

**Cross-prefix uniqueness is not enforced** at the Reservation-file level — `P-000001` and `REQ-000001` coexist by design across different prefix files. Number prefixes namespace the Number space; the same numeric sequence can appear under multiple prefixes. Project policy may enforce global Number uniqueness if needed, outside the seed schema.

### 9. Block allocation (Option 4) deferred to future Schema Change Note

Per [OQ-0015](../OpenQuestions.md) current instinct, block allocation per Workspace is held in reserve for Tier-L scale. ADR/0004 commits to Option 1 (per-Type Reservation files) and explicitly defers Option 4.

The seed schema supports the additive extension when needed: a future Schema Change Note adds a `block_reservations:` mapping alongside `reservations:` describing pre-reserved blocks. Existing `reservations:` entries continue to record concrete allocations within those blocks.

For Tier-S / Tier-M projects (Wedge era through most open-source hardware projects), Option 1 with rebase-on-conflict is sufficient. Tier-L (50K+ Objects, 50+ contributors with frequent allocation) is where block allocation earns its keep.

### 10. The Reservation artifact has no formal Revisions

Reservation artifacts are project-state, not Object-state. They evolve continuously through transactions; **no formal Revisions on the artifact itself**. Like sidecars, a snapshot at any commit captures the project's current allocations.

Release Manifests (per [ADR/0002](0002-canonical-format.md)) may reference Reservation artifact state at release time as part of the reconstructable baseline.

When the project's schema bundle bumps (per ADR/0003), each Reservation artifact's `schema_version` updates per [S0 commitment 3](../TruthModelSchema.md#3-schema_version-is-governance-not-engineering): the bump emits an audit record to the operational audit log, NOT an event in the engineering event log.

## Worked example — multi-Object allocation with one renumbering

A consumer project's `Docs/Reservations/P.yaml` after a few Parts allocated and one renumbered:

```yaml
---
name: aiadra-reservation-P
status: active
schema_version: "0.5.0"
artifact_kind: "reservation"
discriminator: "P"
---

reservations:
  "P-000001":
    object_uuid: "0193abcd-1234-..."
    status: "current"
    allocated_at: "2026-05-18T10:00:00Z"
    allocated_by_transaction: "txn_2026_05_18_001"

  "P-000002":
    object_uuid: "0193bbbb-bolt-..."
    status: "current"
    allocated_at: "2026-05-18T10:01:00Z"
    allocated_by_transaction: "txn_2026_05_18_002"

  "P-000007":
    object_uuid: "0193ffff-5678-..."
    status: "retired"
    allocated_at: "2026-05-18T10:05:00Z"
    allocated_by_transaction: "txn_2026_05_18_003"
    retired_at: "2026-06-15T14:30:00Z"
    retired_by_transaction: "txn_2026_06_15_017"
    retirement_reason: "Renumbered to P-000123 per ECO-007 (consistency with chassis-mount numbering range P-000100–P-000200). Stronger approval recorded in transaction txn_2026_06_15_017 / ECO record ECO-007."

  "P-000123":
    object_uuid: "0193ffff-5678-..."
    status: "current"
    allocated_at: "2026-06-15T14:30:00Z"
    allocated_by_transaction: "txn_2026_06_15_017"
```

The Git commit `txn_2026_06_15_017` touched (per Decision §6):

- The sidecar for Object `0193ffff-5678` — `object.number` field updated from `P-000007` to `P-000123`.
- The event log — `number_rebound` event appended with `object_uuid: 0193ffff-5678`, `old_number: P-000007`, `new_number: P-000123`, `transaction_id: txn_2026_06_15_017`, `justification: "Renumbered per ECO-007..."`.
- This Reservation file — `P-000007` entry mutated `current → retired` with matching transaction id and retirement reason; `P-000123` entry added as `current` with matching transaction id.

All four references agree. The Layer-2 validator confirmed coherence before the commit landed.

Queries against this file:

- "Current Number for `0193ffff-5678`?" → `P-000123` (one `current` entry per UUID).
- "Number history for `0193ffff-5678`?" → `P-000007` (retired, renumbered per ECO-007) → `P-000123` (current).
- "What Object has Number `P-000007`?" → `0193ffff-5678` (retired alias; still resolves).
- "What Object has Number `P-000999`?" → unknown; not allocated.

## Consequences

- **Schema bundle bump v0.4.0 → v0.5.0.** `reservation` joins the artifact-kind set. `reservation/_base.schema.json` plus per-prefix wrapper schemas (`reservation/P.schema.json`, `reservation/REQ.schema.json`, `reservation/ASM.schema.json`) land in the `aiadra-core` bundle.
- **Glossary v0.8 → v0.9.** *Reservation file* entry rewritten with the now-pinned shape and references to this ADR. *AIADRA YAML Profile* entry generalized: cardinality clarified per artifact kind (sidecar = one Object; Revision = one frozen Object snapshot; Reservation = one Number prefix's allocations).
- **OpenQuestions v0.5 → v0.6.** OQ-0015 status moves to `resolved`; entry restructured with concise Resolution block at top plus preserved four-option historical trail (mirror of the OQ-0016 restructure pattern from ADR/0008).
- **Per-Type ADRs' Number prefixes are now usable.** Part / Requirement / Assembly can allocate Numbers concretely via their respective Reservation files. Future Component / SoftwareModule per-Type ADRs declare their prefixes (`C-NNNNNN`, `SW-NNNNNN`, or similar) and inherit the same allocation mechanics.
- **The Wedge is now allocation-capable.** The Wedge's one Part can allocate `P-000001` via `Docs/Reservations/P.yaml`; its one Requirement can allocate `REQ-000001` via `Docs/Reservations/REQ.yaml`. Combined with `satisfies` (the next relationship-type ADR to land), the Wedge's Requirement-Part-satisfies-validation-Release loop becomes operational.
- **Layer-2 validator gains the cross-artifact Reservation invariant.** Implementation belongs to validator work; this ADR pins the rule.
- **Cross-project Reservation interactions deferred.** A consumer project binding to a catalog Part doesn't allocate a catalog Number locally — Component (subsequent per-Type ADR) carries the cross-project binding per [ADR/0008](0008-cross-project-object-identity.md). Reservation files stay within-project.
- **Pre-existing-Number migration** (a project adopting AIADRA with legacy Numbers from Excel BOMs etc.) is not addressed here. A future ADR or per-project tooling can specify bulk-allocation flow; the seed Reservation file accepts any valid initial state.

## References

- [Manifesto.md](../Manifesto.md) — P3 (UUID is identity, Number is presentation), P5 (every AI action is a Transaction — relevant for atomicity), P10 (event-based history with sidecars holding current state; Reservation files extend this pattern to project-level allocation state), P11 (AIADRA Core hosts nothing — no live allocator; conflict resolution via Git rebase).
- [Glossary.md](../Glossary.md) — *Reservation file* (rewritten in v0.9 to cite this ADR), *AIADRA YAML Profile* (generalized in v0.9), *Number*, *UUID*, *Transaction*, *Lifecycle State*, *Released Truth*.
- [TruthModelSchema.md](../TruthModelSchema.md) — S0 commitment 3 (schema_version governance, audit log connection), S0 commitment 4 (record addressing — Reservation entries follow related patterns), S2.5 (Number-binding lifecycle — provides the seven acceptance criteria for the file shape).
- [ADR/0001](0001-storage-substrate.md) — Storage substrate. §3 (acceleration cache — supports cross-file validator queries for Transaction references), §4 (sidecar/event invariant — Reservation-file invariant is the parallel), §5 (no live coordination — bounds allocation to local-with-merge-conflict-resolution), §6 (locality tier — Reservation validation requires fetched local state, no remote consultation).
- [ADR/0002](0002-canonical-format.md) — Canonical format. AIADRA YAML Profile (parser-level rules Reservation files inherit, including duplicate-key rejection that catches branch conflicts at parse time).
- [ADR/0003](0003-schema-governance.md) — Schema governance. §2 (artifact-kind taxonomy — extended here to include `reservation`), §11 (bump ceremony — MINOR additive for this ADR).
- [ADR/0005](0005-object-type-part.md), [ADR/0006](0006-object-type-requirement.md), [ADR/0007](0007-object-type-assembly.md) — Seed Object Type ADRs that declared their Number prefixes pending this ADR's allocation mechanics.
- [ADR/0008](0008-cross-project-object-identity.md) — Cross-project Object identity. Reservation files stay within-project; cross-project bindings live in Component / SoftwareModule per-Type ADRs.
- [OpenQuestions.md](../OpenQuestions.md) — OQ-0015 (resolved by this ADR), OQ-0014 (resolved earlier, related — no live coordination), OQ-0012 (scale-sensitive structural commitments; Tier-L escape hatch for block allocation flagged but deferred).
- Discussion trail (git-ignored, local only): `Docs/Discussions/20260518-8/Claude1.md` → `Codex1.md` → `Claude2.md` → `Codex2.md` — full working-out across one substantive Codex round (two hard blockers caught and absorbed) plus a green-light second round with two non-blocking polish notes absorbed.

---

## SCN 2026-07-28 — terminal `deleted` lifecycle status (arc 20260728-3; bundle v0.29.0 → v0.30.0)

The Reservation entry lifecycle grows one terminal state:

```
current → retired          (renumbering; unchanged)
current → deleted          (NEW: Object deletion — TERMINAL)
```

Rules (all pinned by the arc-20260728-3 converged design; Codex2 SIGNOFF):

1. **`deleted` is terminal.** No transition leaves it. The Number and `object_uuid`
   remain permanently reserved and historically resolvable — deletion never frees a
   Number for reuse (S2.5 commitment: Numbers are forever).
2. **Tombstone shape.** When `status: deleted`, the entry REQUIRES `deleted_at`
   (UTC ISO), `deleted_by_transaction` (`tx_NNNN`), and `deletion_reason`
   (non-empty), and FORBIDS `current_revision_id` (a deleted Object has no current
   revision by rule). Under the v1 delete gate, `released_revision_ids` must
   already be `[]` — an Object with released history cannot be deleted.
3. **Atomic identity transition.** The Reservation tombstone, the `object_deleted`
   event, and the working-sidecar REMOVAL are one Transaction and one Git commit.
   Mechanical equality (Codex2 N2): the event payload and the tombstone MUST agree
   on UUID, Number, transaction id, deletion reason, and deletion time, with the
   working sidecar absent post-commit. Tests hard-fail on any disagreement.
4. **Lookup distinguishes deleted from unknown.** Resolving a deleted Number/UUID
   raises the typed `ObjectDeletedError` (carrying the tombstone metadata), never
   `ObjectNotFoundError`. Queries over working state exclude deleted Objects
   naturally (no sidecar exists).
5. **Schema consequence.** Bundle v0.30.0: all five reservation schemas gain
   `deleted` in the status enum + the three tombstone fields + the conditional
   requirement/forbid branch; new `event/object_deleted.schema.json`. Additive
   MINOR per ADR/0003 §11.

Discussion trail (git-ignored, local only): `Docs/Discussions/20260728/20260728-3/`
(Claude1 → Codex1 → Claude2 → Codex2 SIGNOFF).
