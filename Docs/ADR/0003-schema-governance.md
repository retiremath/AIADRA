---
name: adr-0003-schema-governance
status: accepted
date: 2026-05-17
supersedes: none
superseded_by: none
resolves: [OQ-0013]
---

# ADR/0003 — Schema Governance

## Status

**Accepted** — 2026-05-17. Third of the Ring 0 ADRs, completing the substrate / format / governance triad. [ADR/0001](0001-storage-substrate.md) settled where canonical truth lives; [ADR/0002](0002-canonical-format.md) settled the shape it is written in; this ADR settles how that shape evolves across the project's lifetime.

## Context

[ADR/0002 §1](0002-canonical-format.md) committed AIADRA to **JSON Schema validation at every read** for every sidecar, event, and release manifest. It also made **`schema_version` mandatory on every artifact**. Neither of those commitments is realisable without the governance machinery this ADR defines: a registry of schemas, a versioning model, migration rules, validator behavior, and a process for changing schemas without breaking the multi-decade reconstructability commitment.

The decision is forced into the open by three factors converging here:

1. **ADR/0002 hard-depends on it.** The AIADRA YAML Profile only earns its keep if there is a JSON Schema registry behind it. Without ADR/0003, ADR/0002 names a `schema_version` field without specifying what the version *means*.
2. **AIADRA's reconstructability commitment.** Releases must remain readable years later. A naive deprecation model that hard-rejects old artifacts would make old Release tags unreadable. Governance must reconcile "evolve the schema" with "never lose access to the past."
3. **Tier-L scale ([OQ-0012](../OpenQuestions.md))** — *"ADR/0003 must support schema evolution across millions of historical records"*. The chosen model must hold up when the event log has accumulated decades of entries against many schema generations.

[OQ-0013](../OpenQuestions.md) named the question; [Claude6.md](../Discussions/20260517/Claude6.md) walked the design surface; [GPT6.md](../Discussions/20260517/GPT6.md) green-lit the framing with five tightenings; [Claude7.md](../Discussions/20260517/Claude7.md) accepted them. This ADR folds the resulting design in.

## Alternatives Considered

### Description language

**A1. JSON Schema Draft 2020-12.** *Chosen — see Decision §1.*

**A2. JSON Schema Draft 7 or earlier drafts.**

> **Rejected.** Older drafts lack `$dynamicRef`, unified annotation handling, and the cleaner `$defs` / `$ref` semantics 2020-12 introduces. Tooling for 2020-12 is mature enough to use today; locking the project into a pre-2020 draft trades long-term flexibility for short-term ecosystem comfort.

**A3. RELAX-NG, custom DSL, schema-by-example.**

> **Rejected.** RELAX-NG has thin ecosystem support outside XML; a custom DSL multiplies AIADRA's surface area for zero clear gain; schema-by-example is fundamentally unsuited to load-bearing validation. JSON Schema is the lingua franca for validating JSON-shaped data, which is what the AIADRA YAML Profile produces post-parse.

### Schema location

**B1. AIADRA Core source control.** *Chosen — see Decision §1.*

**B2. In-project schemas.**

> **Rejected.** Each project would carry its own copy of the schemas, drifting from every other project, defeating the cross-project interoperability that makes AIADRA worth running. Schemas are part of the *AIADRA contract*, not part of the project's product truth.

**B3. Self-describing artifacts** (each sidecar carries its own schema definition).

> **Rejected.** Heavy on every read; provides no cross-artifact consistency guarantee (each artifact could legally invent its own shape); makes schema evolution unmanageable. The savings (no central registry) are illusory — the registry has to exist *somewhere*; better in AIADRA Core where it is reviewable than scattered across millions of artifacts.

### Versioning granularity

**C1. Bundle versioning** — one version for the entire schema set, every artifact references the bundle version it was authored against. *Chosen — see Decision §2.*

**C2. Per-schema versioning** — every artifact-class schema has its own SemVer line; artifacts reference both schema name and version.

> **Rejected.** More precise, more flexible, more cognitive load. Cross-references between sidecars and events make per-schema version skew within a single project a genuine consistency hazard. The "version churn without real change" cost of bundling is small compared to the operational simplicity of one version pin per project.

**C3. No versioning** — parsers handle all known shapes implicitly.

> **Rejected.** Fragile, untraceable, makes migration impossible to verify. Already pre-emptively rejected by OQ-0013.

### Event-schema structure

**D1. Per-event-type schemas with shared `_base.schema.json`.** *Chosen — see Decision §3.*

**D2. Polymorphic single schema** with a discriminator (`event_type`) and `oneOf` per-type sub-schemas in one file.

> **Rejected after review.** `oneOf` failures over discriminated unions produce notoriously poor error messages — validators report "matched zero or more than one branch" instead of "the field you got wrong was `parameter_value`." For events, which the AI Action Protocol will surface to AI agents and humans, error legibility matters. Per-type evolution (bumping one event type's schema without touching others) is also genuinely easier when types live in separate files. The cross-event invariants story still works: a shared base schema captures `event_id`, `timestamp`, `actor`, `transaction_id`, `schema_version` and is `$ref`'d from every per-type schema.

### Migration model

**E1. Forward-only migration via explicit tool for sidecars; immortal at declared version for events; frozen for manifests.** *Chosen — see Decision §5 and §6.*

**E2. On-read migration** — validator silently rewrites the on-disk file when an older `schema_version` is encountered.

> **Rejected.** Silent file mutation on read poisons the review process — the diff appears in a PR by surprise, the contributor who triggered it may not be the contributor who reviews it, and the audit trail loses precision. Migration must be an explicit, reviewable commit.

**E3. Eager on-commit migration** — every commit auto-migrates every encountered artifact to the current version.

> **Rejected.** Same surprise-mutation problem at a different time. Also expensive: a commit touching one parameter would migrate every nearby artifact incidentally, polluting diffs.

**E4. Hard-reject old artifacts past a deprecation horizon, regardless of read or write.**

> **Rejected.** This was the original Claude6 model. GPT6 surfaced that it breaks reconstructability: a 2030 contributor checking out a 2026 Release tag would find its sidecars rejected by the current validator. Splitting into active-authoring and archival modes (Decision §6) preserves both forward pressure (write path enforces the horizon) and reconstructability (read path validates any historical version forever).

## Decision

### 1. JSON Schema Draft 2020-12, schemas in AIADRA Core source, bundled

The description language for every artifact-class schema is **JSON Schema Draft 2020-12** — the current latest JSON Schema meta-schema (per https://json-schema.org/specification). The same draft applies uniformly to sidecars, events, and release manifests.

All schemas live under AIADRA Core source control, in a folder rooted at `aiadra-core/schemas/`. They are versioned independently of any specific Product Truth Model and shipped as **bundles** — versioned collections containing every schema, every linter rule, and every migrator AIADRA Core ships at that point in time.

The project pin (§9) names the **active authoring target** — the bundle that new and modified artifacts must conform to. Validation, however, may load **any historical bundle** named by an individual artifact's `schema_version`, because archival mode (§6) requires that artifacts at any past bundle version remain readable forever. AIADRA Core verifies the on-disk pinned bundle matches the project's pinned digest at startup and before any write; read-path validation resolves the bundle named by the artifact itself, not the project pin.

### 2. Bundle versioning; schema lookup via (bundle_version, artifact_kind, discriminator)

Every artifact carries a `schema_version` field whose value is a bundle SemVer string (e.g., `"0.3.0"`). That value alone does not pick a schema — the validator combines it with the artifact's *kind* and a *discriminator* field internal to the artifact:

| Artifact kind | Discriminator field | Source |
|---|---|---|
| Sidecar | `object.type` | Already present in ADR/0002's worked example. |
| Event | `event_type` | Required on every event line. |
| Manifest | `manifest_type` | Currently only `release` exists; the field is forward-compatible. |

**The schema lookup formula:**

> **(bundle_version, artifact_kind, discriminator) → schema**

The validator reads `schema_version` (identifies the bundle), identifies the artifact kind from the file path or wrapping context, reads the discriminator, and resolves to a single schema file inside the bundle. Validation proceeds against that schema only.

### 3. Per-event-type schemas with a shared `_base.schema.json`

Events do *not* use a polymorphic `oneOf` schema. Each event type has its own schema file; cross-event invariants (event ID, timestamp, actor identity, transaction ID, `schema_version`) live in `_base.schema.json` and are `$ref`'d from every per-type schema.

Layout fragment:

```
schemas/v0.1.0/event/
  _base.schema.json
  object_created.schema.json
  parameter_changed.schema.json
  release_approved.schema.json
  ...
```

New event types are added by dropping new per-type schemas into the bundle — a MINOR bump (additive) if the type is genuinely new, a MAJOR bump only if it changes shared base contracts.

### 4. SemVer taxonomy for schema changes

Every schema change classifies into exactly one of three bump categories:

| Bump | What it covers | Effect on existing artifacts |
|---|---|---|
| **PATCH** (0.1.0 → 0.1.1) | Documentation, clarifications, error-message wording. No shape change. | None — old artifacts validate against new schema unchanged. |
| **MINOR** (0.1.0 → 0.2.0) | New *optional* field. New permitted enum value. Relaxation of an over-strict rule. New event type. | Old artifacts validate against new schema unchanged. |
| **MAJOR** (0.1.0 → 1.0.0) | New *required* field (even with a default). Field removal. Field rename. Type narrowing. Validation-rule tightening. Enum value removal. Semantic redefinition of an existing field. | Old artifacts do *not* validate against new schema; migration required. |

Subtleties pinned by this ADR:

- **Adding a required field is MAJOR even if a default exists.** The on-disk artifact lacks the field; the file stays honest about what it contains. No silent default-substitution at read time. Migration writes the default into the file explicitly.
- **Tightening a validation rule is MAJOR.** Even if no current artifact would fail, a contributor pinned to the old version could later write artifacts the new validator rejects.
- **Pre-1.0 SemVer is stricter than the spec.** While the bundle is on `0.x.y`, the project signals instability — but AIADRA still uses MAJOR for breaking changes (`0.x → X.0`, where X starts at 1). The artifact format is too load-bearing for the pre-1.0 escape hatch.

### 5. Three-way migration asymmetry across artifact classes

| Class | Migration behavior |
|---|---|
| **Sidecars** | Forward-migration via explicit `aiadra migrate` command. No on-read mutation. Migration is a normal commit, reviewed in a PR. |
| **Events** | Never migrated. Each event remains at its declared `schema_version` forever; the registry holds every historical event schema. New events use the current bundle's event schemas; old events keep theirs. |
| **Manifests** | Frozen. A signed manifest is a content-hashed fingerprint of a Release; re-rendering at a new schema would invalidate the signature. New schema → new manifest, not migrated old one. |

This asymmetry is intentional and is what makes schema governance more than a generic concern.

### 6. Active authoring mode vs. archival mode

The validator operates in two distinct modes with different policy responses to old `schema_version` values:

- **Active authoring mode (write path).** Deprecation policy applies to writes:
  - *Within the grace period:* new artifacts at the deprecated version are **hard-refused**. Modifying an existing artifact at the deprecated version is **hard-refused** unless the same commit migrates the artifact to a supported version, or the user invokes an explicit `--legacy-edit` escape hatch (reserved for emergency fixes that genuinely cannot be migrated). Reads warn.
  - *Past the deprecation horizon (§11):* all writes against the version are hard-refused, including modifications. The only path forward is `aiadra migrate`. The `--legacy-edit` escape hatch is not available past the horizon.
- **Archival mode (read/validate path).** *Every* `schema_version` that the registry has ever known continues to validate forever. The bundle registry retains all historical schemas for all three artifact classes — sidecars, events, manifests — and never deletes them. Read never hard-rejects on age alone, regardless of how many MAJOR bumps have passed.

The practical consequence: a 2030 contributor checking out a 2026 Release tag will still find every sidecar, event, and manifest in that tag readable and validatable by current AIADRA Core. The deprecation horizon governs write-path behavior only.

Bundle folders accumulate forever. Cost is small — JSON Schemas are tiny text — and pays for a guarantee that matters across decades.

### 7. Validator behavior taxonomy

The validator's response to each condition:

| Condition | Behavior |
|---|---|
| `schema_version` not in registry (unknown bundle) | **Hard reject.** No best-effort parsing. |
| `schema_version` recognized, currently supported | Validate normally. |
| `schema_version` recognized, deprecated, within grace period | Validate normally on read with a **warning**. New artifacts at this version: **hard-refused**. Modifications to existing artifacts at this version: **hard-refused** unless the same commit migrates the artifact (or `--legacy-edit` is set for an emergency fix). |
| `schema_version` recognized, past deprecation horizon | Validate normally on read (archival mode is permanent). **All writes hard-refused**, including modifications; only `aiadra migrate` can advance the artifact. |
| JSON Schema validation fails on a recognized version | **Hard reject.** No partial reads. |
| AIADRA YAML Profile rule fails (token-level linter, per ADR/0002 §1) | **Hard reject.** Sibling failure mode. |
| Sidecar/event invariant fails (per ADR/0001 §4) | **Hard reject** at commit time. Not strictly schema governance, but the same validator owns the check. |
| Bundle digest in project pin does not match on-disk bundle | **Hard reject** before any artifact is read. |

Four hard-reject classes for reads (unknown version, schema fail, profile fail, digest mismatch), one hard-reject class for commits past the horizon, one warn-on-read class within the grace period.

### 8. Registry file layout

The bundle registry is self-contained per version:

```
aiadra-core/
  schemas/
    v0.1.0/
      bundle.json                         # manifest: every schema, deprecation status, supported versions
      CHANGELOG.md                        # cumulative + this-version notes
      sidecar/
        part.schema.json
        requirement.schema.json
        ...
      event/
        _base.schema.json
        object_created.schema.json
        parameter_changed.schema.json
        ...
      manifest/
        release.schema.json
      yaml-profile/
        rules.json                        # token-level linter rules, versioned with the bundle
      migrations/
        from-v0.0.x/                      # only present for bundles that ship migrators
          sidecar.py                      # implementation language deferred
          ...
      notes/                              # Schema Change Notes for MINOR bumps
        ...
    v0.2.0/
      ...
```

Key properties:

- **Each bundle version is self-contained.** No reaching across versions for schemas. Old bundles remain on disk forever for archival-mode reads.
- **Migrations co-located with the destination version.** `v0.2.0/migrations/from-v0.1.0/` contains the code that brings v0.1.0 artifacts to v0.2.0. Bidirectional reasoning is trivial.
- **The bundle manifest** lists every schema, every deprecation status, every supported `schema_version` value. The validator loads it once at startup.
- **YAML Profile token-level linter rules** are part of the bundle. Profile evolution = bundle bump. This is the correct coupling: a Profile change is a schema-set change.

### 9. Project pin file with bundle version and digest

Every AIADRA project carries a pin file at `.aiadra/schemas.yaml`:

```yaml
bundle_version: "0.3.0"
bundle_digest: "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
```

- **`bundle_version`** names the **active authoring target** — the bundle that new and modified artifacts must conform to.
- **`bundle_digest`** is the SHA-256 of a canonical serialization of every **normative** file in the bundle: the `bundle.json` manifest, all schema files, all linter-rule files, and all migrators, in deterministic ordering. Non-normative files (the `CHANGELOG.md` and Schema Change Notes in `notes/`) are excluded because they are documentation, not code that runs against canonical truth. The digest therefore covers everything that affects either validation behavior *or* migration behavior; reproducibility for both paths is anchored to the same hash.

AIADRA Core computes the digest at bundle-publish time; the project records it; AIADRA Core verifies the on-disk pinned bundle matches the digest at startup and before any write.

The pin is the **active authoring target**; per-artifact `schema_version` is the **bundle the artifact was authored against**. The two need not match — many artifacts will be at older bundle versions, especially after a project's bundle pin has advanced. **Read-path validation always uses the artifact's own `schema_version` to select a bundle from the registry**, not the project pin. Write-path policy (§7) requires new and modified artifacts to target the pinned bundle unless `aiadra migrate` is being run to advance them.

Migration via `aiadra migrate` updates the pin to the new bundle version (and digest) atomically with the artifact rewrites.

### 10. Migrator constraints

Migrator implementation language is deferred (likely Python, decided when AIADRA Core's stack is settled). Regardless of language, every migrator MUST satisfy:

- **Deterministic output.** Same input artifact, same migrator, byte-identical output. Reproducibility under review.
- **Dry-run mode.** `aiadra migrate --dry-run` produces the proposed diff without writing. Reviewers see what would change before they accept.
- **Idempotent.** Running a migrator twice on the same artifact is a no-op the second time.
- **No network.** Migrators run offline. No external services, no live registry calls. Fits Principle 11 (AIADRA Core hosts nothing) and makes them reproducible for the lifetime of the project.
- **Fixture tests.** Every migrator ships with paired (input, expected output) fixtures covering the cases it claims to handle. Tests run in AIADRA Core CI.
- **Human-readable diffs.** Migrator output is reviewable as a normal Git diff. No binary blobs, no opaque transformations.

A migrator that fails any of these is not eligible for inclusion in a bundle.

### 11. Governance ceremony and deprecation horizon

**Per-bump ceremony:**

| Bump | Required artifacts |
|---|---|
| **PATCH** | PR + reviewer + entry in the bundle's `CHANGELOG.md`. No ADR. |
| **MINOR** | PR + reviewer + `CHANGELOG.md` entry + a short **Schema Change Note** in `notes/` describing what was added and why. No full ADR. |
| **MAJOR** | **Full ADR** — `ADR/NNNN-schema-bump-vX.0.0.md`. Migration plan, deprecation timeline, rationale, old-version retention notes. |

The Schema Change Note for MINOR bumps is a lower-ceremony artifact than an ADR but higher than a CHANGELOG line — it captures the *why* for additive changes that would otherwise rot into commit messages.

**Deprecation horizon (default policy):**

- The deprecation horizon is **two MAJOR bumps behind the current bundle**. Example, when bundle v3.0.0 is current:
  - **v2.x.y and v3.x.y** — fully supported.
  - **v1.x.y** — in deprecation grace. Reads validate with a warning. New artifacts at this version are refused; modifications require concurrent migration or the `--legacy-edit` escape hatch (per §6).
  - **v0.x.y** — past the horizon. Reads still validate (archival mode is permanent). Writes are hard-refused in all forms except `aiadra migrate`.
- The horizon is bundle-relative, not calendar-time-based, so slow-moving projects are not punished by elapsed time.
- This default is **revisable without a new ADR** — the policy can be tightened or loosened by amending this ADR's §11 directly, provided the change is recorded in the AIADRA Core changelog.
- **Archival mode is never affected by the horizon.** Read-path validation against historical schemas continues forever regardless of how many MAJOR bumps have passed.

## Rationale

- **JSON Schema 2020-12 is gravity.** Every reasonable ecosystem has libraries for it; the spec is stable and broadly understood; the features AIADRA cares about (`$dynamicRef`, `$defs`, unified annotations) are exactly what 2020-12 added over earlier drafts. Picking it costs almost nothing and buys decades of tooling compatibility.
- **Bundling beats per-schema versioning at this stage.** One version pin per project is a smaller surface to reason about than N independent version lines. Cross-artifact consistency (sidecars referencing events, events referencing sidecars) becomes trivial when both move together. The reversibility argument: a future bundle MAJOR can introduce per-schema versioning if the constraint genuinely bites, but starting with per-schema versioning would be much harder to retreat from.
- **The active/archival split is what makes governance compatible with multi-decade reconstructability.** Without it, the deprecation horizon would silently invalidate old Releases — a quiet disaster the project would only notice when someone tried to rebuild a 2026 design in 2032. Forward pressure on writes; permanence on reads. Both are required.
- **Per-event-type schemas with shared base prioritize error legibility.** AI agents and humans will both consume validation errors on events through the AI Action Protocol surface. Specific errors against specific schemas beat `oneOf` failures.
- **Migrator constraints reflect that migrators touch canonical truth.** A buggy migrator is worse than a buggy validator because a migrator's bugs are *committed*. Determinism, dry-run, idempotence, no-network, and fixture tests are not luxuries; they are the minimum bar for code that modifies the Product Truth Model.
- **Bundle digest is the no-HQ proof of identity.** Without a digest, "this project uses schema bundle 0.3.0" is a nominal claim. With a digest, a future AIADRA Core can prove it is validating against the *exact same schemas* the project was authored against — even if AIADRA Core's own source has moved on. Principle 11 (AIADRA Core hosts nothing) plus content-addressable verification = projects survive AIADRA Core's evolution.
- **Two-MAJOR-bumps as deprecation default is a guess, and is recorded as such.** No data exists yet on how often AIADRA Core will MAJOR-bump. The horizon is calibrated to be lenient enough for slow-moving projects and forward-pressure enough that active projects stay current. It is revisable.

## Consequences

### Enables

- **JSON Schema validation at every read becomes operational.** ADR/0002's commitment is now executable: the validator knows which schema to load for any given artifact.
- **Schema evolution is safe and traceable.** Every change is classified (PATCH/MINOR/MAJOR), reviewed at the appropriate ceremony level, and recorded in a per-bundle CHANGELOG plus optional Schema Change Notes.
- **Cross-project compatibility.** Two projects on the same bundle version use the same schemas, validated the same way. The schemas are part of the AIADRA contract, not project-specific.
- **Reconstructability across decades.** Old Releases remain readable forever. A 2030 contributor reading a 2026 design gets the same validation guarantees the 2026 author had.
- **Migrator review is a normal Git workflow.** Migrators ship with fixtures, run with `--dry-run`, produce reviewable diffs. No special tooling, no special process.
- **The AIADRA YAML Profile evolves cleanly.** Profile changes are bundle changes. Token-level linter rules are versioned alongside the schemas they sit beside.

### Costs / accepted tradeoffs

- **The bundle registry grows monotonically.** Historical bundles are never deleted. Tractable — JSON Schemas are small — but it is a real space cost over decades.
- **AIADRA Core must maintain a digest computation and verification path.** Canonical bundle serialization, hash, validation. Not free; it is the price of reproducibility.
- **A single bundle version pin can produce false coupling.** A PATCH on a sidecar schema bumps the bundle, which means every other artifact class incidentally moves to a new bundle version. Most schema changes are coordinated anyway (a parameter-model change touches sidecar and event schemas simultaneously), but the friction is real.
- **MAJOR bumps require ADRs.** This is intentional ceremony — MAJOR bumps must be deliberated — but it raises the cost of any breaking change. The hope is that schema design lands well enough early that MAJOR bumps are genuinely rare.
- **Migrator authoring is real work.** Determinism, idempotence, fixtures, no-network discipline impose real constraints. Migrators are not afternoon scripts.

### Defers

- **Ring 1 — Actual schemas for each Object type.** Part, Requirement, Assembly, etc. ADR/0003 settles the *governance*; Ring 1 settles the *content*. The Wedge will exercise the first real schemas.
- **Ring 1 — First concrete migrator implementations.** No migrators exist yet because no bumps have occurred. The first migrator lands when the first MAJOR bump does.
- **Ring 1 — Event-log sharding interaction** (cross-references OQ-0012). When events are sharded by time period, the registry's historical-schema lookup must remain efficient.
- **Ring 2 — Validator performance characteristics.** Throughput, memory, the interaction with the acceleration cache (ADR/0001 §3) for repeated validations.
- **Future ADRs — Every MAJOR bump.** Each future MAJOR bump gets its own `ADR/NNNN-schema-bump-vX.0.0.md`.
- **Migrator implementation language.** Probably Python; decided when AIADRA Core's stack is settled.

### Resolves

- **OQ-0013** — Schema governance and versioning.

## References

- [Manifesto](../Manifesto.md) — Principle 10 (event-based history, flat current state), Principle 11 (AIADRA Core hosts nothing — drives no-network migrator constraint and content-addressable bundle digest), Scale Targets section.
- [Glossary](../Glossary.md) — Sidecar, Event, Release Manifest, AIADRA YAML Profile, Sidecar/event invariant, Acceleration Cache.
- [ADR/0001](0001-storage-substrate.md) — Storage substrate (sidecar/event invariant in §4; the validator that owns this ADR's checks also owns that invariant).
- [ADR/0002](0002-canonical-format.md) — Canonical on-disk format (AIADRA YAML Profile; JSONL events; deterministic JSON manifests; `schema_version` mandatory on every artifact).
- [OpenQuestions](../OpenQuestions.md) — OQ-0013 (resolved here); OQ-0012 (Ring 1 scale-sensitive structural commitments).
- JSON Schema specification — https://json-schema.org/specification
- Discussion thread (git-ignored, local-only): `Docs/Discussions/20260517/Claude6.md`, `GPT6.md`, `Claude7.md`.
