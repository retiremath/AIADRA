---
name: adr-0016-object-type-software-module
status: accepted
date: 2026-05-19
supersedes: none
superseded_by: none
resolves: []
---

# ADR/0016 — Object Type: SoftwareModule

## Status

**Accepted** — 2026-05-19. Fifth Object Type after Part / Requirement / Assembly / Component. Second External pointer Object Type after Component — applies the [ADR/0014](0014-object-type-component.md) template to software dependencies with Git-source-of-truth discriminator shapes. Broader than a pure dependency wrapper: the `workspace_git` discriminator supports **first-party / in-Commonspace** software modules (firmware authored in the same product repo; in-repo Python control packages; etc.), invoking direct Promotion via the basic capability test rather than the External pointer Object named non-disqualifier pattern. The Type unifies both modes; the discriminator captures the source. Carries additive endpoint Type union extensions to `relationship/allocates_to.schema.json` and `relationship/parameter_expression.schema.json` — closing the SoftwareModule deferral from [Glossary "Object (Managed Object)" candidate pool](../Glossary.md) and the future-extension note in [ADR/0015 §"Decision §4"](0015-relationship-type-parameter-expression.md).

## Context

[ADR/0008 §3 line 233](0008-cross-project-object-identity.md) named SoftwareModule alongside Component as a future Binding Object Type: *"SoftwareModule per-Type ADR unblocked. Subsequent ADR; same pattern as Component but Git-source-of-truth."* [ADR/0014 §"Consequences"](0014-object-type-component.md) noted: *"SoftwareModule's per-Type ADR can largely follow ADR/0014's shape, with discriminator-specific shapes adapted to Git-source-of-truth semantics (commit-hash binding instead of upstream Revision UUID)."*

Discussion trail in [`Docs/Discussions/20260519/20260519-6/`](../Discussions/20260519/20260519-6/). [Codex1](../Discussions/20260519/20260519-6/Codex1.md) produced two blockers and three non-blocking refinements. Both blockers absorbed in [Claude2](../Discussions/20260519/20260519-6/Claude2.md):

1. SoftwareModule narrowed to a dependency wrapper in Claude1 — the four originally-proposed discriminators all assumed external upstream. The most basic embedded/mechatronic case is first-party firmware in the same Commonspace. Repair: add `workspace_git` discriminator; SoftwareModule now spans both modes; dual Promotion paths.
2. Release materialization fields overloaded authoring intent (`version_spec` ranges, mutable `ref` branches) with resolved-immutable release identity. Repair: separate fields for authoring intent vs released-resolved identity; algorithm-qualified hashes throughout.

[Codex2](../Discussions/20260519/20260519-6/Codex2.md) sign-off with two precision notes incorporated:

- Git-native hashes (SHA-1 by default in most repos, SHA-256 in newer repos) are distinct from AIADRA artifact-content hashes (SHA-256). Hash fields are *algorithm-qualified strings*; examples use `git-sha1:<oid>` / `git-sha256:<oid>` / `sha256:<artifact-bytes>` as appropriate.
- `workspace_ref.ref` is clearly authoring-intent-only; released Revisions reconstruct from commit/tree hash, not the branch/tag name.

Three pressures converge:

1. **Template re-use; honest Type name.** ADR/0014's External pointer Object template applies cleanly to four of five discriminator cases. The fifth (`workspace_git`) is in-Commonspace; pre-committing SoftwareModule as a Binding-only Type would either exclude the most basic use case or force creating a second software Type later. The dual-Promotion-path framing preserves the unified Type without compromising the Binding semantics where they apply.
2. **Reconstructable released truth.** The Claude1 shape blurred authoring vs released states; Codex correctly identified that `version_spec: "^2.5.0"` cannot simultaneously be authoring intent AND release identity. The repair is structural: distinct fields for distinct phases.
3. **AIADRA Core hosts nothing — tighter constraint at the Git boundary.** When the upstream is Git, the temptation to bake "the AIADRA-recommended Git host" or "Core-resolved Git registry" into the schema is real. Per [Manifesto P11](../Manifesto.md), `git_url` is a non-authoritative transport hint; resolution is consumer-project-local; no Core-hosted Git registry or resolver.

## Promotion Rule walk — dual paths

SoftwareModule passes Promotion two ways depending on `sourcing_discriminator`:

### Path 1: External pointer Object (Binding lifecycle)

Applies when `sourcing_discriminator` ∈ {`git_module`, `package_registry`, `aiadra_catalog`, `custom`}. Same named non-disqualifier pattern as Component per [TruthModelSchema commitment 5](../TruthModelSchema.md). Capability test:

- **C1 — Independent identity.** Consumer project's SoftwareModule `SM-000017` has a *local* UUID + Number stable across its lifetime in this project. Even if upstream Git repo re-tags, re-bases, or moves to a different remote, the consumer's SoftwareModule identity persists.
- **C2 — Independent lifecycle.** Adoption / approval lifecycle is local: `in_work` while consumer evaluates the dependency; `released` when consumer commits to using it; `retired` when removed.
- **C3 — Independent referenceability.** Local relationships (`allocates_to` target; `parameter_expression` endpoint) point at the local SoftwareModule UUID, not the upstream commit / package.
- **C4 — Independent provenance / approval.** Adoption is consumer governance — typically a security / license / build-integration review distinct from upstream authoring.

D1–D7 disqualifiers: D1 (Derived-from-another-Object) N/A — Binding pointer is the named non-disqualifier pattern; D7 (Derived view) N/A — authoritative consumer-side adoption record.

### Path 2: Direct Promotion via basic capability test

Applies when `sourcing_discriminator == workspace_git`. SoftwareModule represents a first-party software module authored in the project's own Commonspace. No upstream; no Binding semantics; pure-Promotion. Capability test:

- **C1 — Independent identity.** Local UUID + Number stable across module evolution. Module re-paths within the repo do not invalidate identity.
- **C2 — Independent lifecycle.** Authoring lifecycle `in_work` → `released` → `retired`, independent of repo-level Git commits (a commit may touch many SoftwareModules; a SoftwareModule's release is its own decision).
- **C3 — Independent referenceability.** Same as Path 1.
- **C4 — Independent provenance / approval.** Standard authoring approval (PR review, ECO, signed tag), same as Part / Assembly.

D1–D7: D1 N/A (not derived from another Object); D2-D7 N/A or trivially pass.

Conclusion: **SoftwareModule is a first-class Object Type via dual Promotion paths.** The Type unifies first-party and externally-sourced software; the discriminator selects the path. Subsequent Binding Object Types may follow similar dual-path framing if they unify in-project and external-binding use cases.

## Alternatives Considered

### Type scope

**A1. Narrow SoftwareModule to dependency-wrapper semantics.** Externally-sourced only; first-party software modules deferred to a future Type ADR.

> **Rejected.** Would create a second near-identical software Type later. Type name is honest only if it covers both authoring modes. Per Codex1 Blocker 1.

**A2. SoftwareModule spans both modes with discriminator-driven Promotion paths.** *Chosen — see Promotion Rule walk above.*

### Number prefix + name

**B1. `SW-NNNNNN`.**

> **Rejected.** `SM` matches the camel-case-to-acronym convention better and aligns with the chosen Type name `SoftwareModule`.

**B2. `SM-NNNNNN` (chosen).** Six-digit zero-padded sequential allocation from the Reservation file per [ADR/0004](0004-number-allocation.md). Matches other seed Types' six-digit width.

### Discriminator enum

**C1. Three discriminators (`git_module`, `package_registry`, `custom`).** Claude1's initial proposal before the `aiadra_catalog` add.

> **Rejected.** `aiadra_catalog` belongs even though uncommon (consistency with ADR/0014 template; an AIADRA project may publish software modules).

**C2. Four discriminators (`git_module`, `package_registry`, `aiadra_catalog`, `custom`).** Claude1 final proposal.

> **Rejected (per Codex1 Blocker 1).** Missing first-party / in-Commonspace case.

**C3. Five discriminators (`workspace_git`, `git_module`, `package_registry`, `aiadra_catalog`, `custom`).** *Chosen — see Decision §3.*

### Release-materialization fields

**D1. Overload authoring fields with resolved identity at release (`version_spec` carries `^2.5.0` for Float and `2.5.3` for Fixed).**

> **Rejected.** Per Codex1 Blocker 2 — a released Revision cannot reliably reconstruct what was approved if the same field carries both authoring range and resolved version. Working sidecar and released Revision need distinct fields.

**D2. Separate authoring intent fields from resolved-immutable release fields per discriminator; algorithm-qualified hashes.** *Chosen — see Decision §3.*

### `composed_of` participation

**E1. Add SoftwareModule to `composed_of` target Type union by making `occurrence.transform` conditional on target Type.**

> **Rejected (per Codex1 Q1 answer).** Destabilizes [ADR/0010](0010-relationship-type-composed-of.md)'s framing that `composed_of` carries a universal transform payload. Software composition is real but is the natural fit for a future software-specific composition relationship type (`embeds` / `depends_on` / similar), not a conditional-shape `composed_of`.

**E2. Defer SoftwareModule from `composed_of` in seed; introduce a software-specific composition relationship later.** *Chosen — see Decision §6.*

### Seed namespace set

**F1. Include `published_ref:` for API surface mirroring.**

> **Rejected (for seed; Codex confirmed).** Premature without an API-reference relationship type. Schema Change Note when the use case surfaces.

**F2. Three of seven (`parameter:`, `design_intent:`, `relationship:`) plus singleton `software_module:` block.** *Chosen — see Decision §4.*

## Decision

### 1. Inherit ADR/0014 External pointer Object template (for Binding-mode discriminators)

For `sourcing_discriminator` ∈ {`git_module`, `package_registry`, `aiadra_catalog`, `custom`}: inherit verbatim from [ADR/0014](0014-object-type-component.md):

- Singleton TypeSpecific block (`software_module:` here).
- Discriminator-driven `oneOf` upstream binding.
- `binding_mode: float | fixed`, default Float.
- Float release materialization is staleness-intolerant; resolve + pin integrity anchors at release; release hard-fails without resolvable hash.
- Lifecycle independent of upstream; per-Object Revision schema.
- AIADRA Core hosts nothing — no hosted Git registry, no Core-mediated resolution.

For `sourcing_discriminator == workspace_git`: same Type-level structure (same singleton block, same `binding_mode` model) but the "upstream" is the project's own Commonspace; integrity anchors are repo-relative commit + tree hashes.

### 2. Number prefix + Type name

**Type name:** `SoftwareModule` (PascalCase).
**TypeSpecific block:** `software_module:` (snake_case singleton).
**Number prefix:** `SM-NNNNNN`.

### 3. TypeSpecific `software_module:` block — five discriminator-specific shapes

```yaml
software_module:
  sourcing_discriminator: "workspace_git | git_module | package_registry | aiadra_catalog | custom"  # REQUIRED
  binding_mode: "float | fixed"      # REQUIRED; default "float"
  # Exactly one of workspace_ref | git_ref | package_ref | catalog_ref | custom_ref, per discriminator
```

**`workspace_git`** (first-party / in-Commonspace):

```yaml
workspace_ref:
  module_path: "string"          # REQUIRED — repo-relative canonical path (e.g., "firmware/motor_controller")
  ref: "string"                  # OPTIONAL — authoring intent only (branch/tag); ignored at release; absent in released Revisions
  commit_hash: "string"          # REQUIRED for Fixed and released materialized Float; algorithm-qualified (e.g., "git-sha1:..." or "git-sha256:...")
  tree_hash: "string"            # REQUIRED for Fixed and released materialized Float; algorithm-qualified subtree hash at module_path
```

`workspace_ref.ref` is authoring-only — released Revisions do not need it to reconstruct the module. The `module_path` + `commit_hash` + `tree_hash` are the release-time integrity anchors.

**`git_module`** (external Git submodule, vendored Git tree, Git tag pin):

```yaml
git_ref:
  origin_id: "string"            # REQUIRED — stable upstream-project identity (consumer-policy stable identifier; NOT a URL)
  git_url: "string"              # OPTIONAL — non-authoritative transport hint (e.g., "https://github.com/...")
  ref: "string"                  # OPTIONAL — authoring intent for Float (branch/tag)
  module_path: "string"          # OPTIONAL — relative path inside upstream repo (when SoftwareModule represents a subtree)
  commit_hash: "string"          # REQUIRED for Fixed and released materialized Float; algorithm-qualified
  tree_hash: "string"            # REQUIRED if module_path is present (subtree pinning); OPTIONAL when the entire repo IS the module
```

`origin_id` is the stable identity (per [ADR/0008 §5](0008-cross-project-object-identity.md) identity-locator split — a Git remote URL is not stable identity; repos move, mirrors exist). Consumer-policy stable identifier (typically `<host-namespace>:<repo-path>` or an explicit project identifier the consumer maintains). `git_url` is the transport hint, non-authoritative.

**`package_registry`** (npm, PyPI, Maven, crates, etc.):

```yaml
package_ref:
  registry: "string"             # REQUIRED — registry identifier (consumer-policy; not Core-enumerated per Manifesto P11)
  package_name: "string"         # REQUIRED — registry's name for the package
  version_spec: "string"         # OPTIONAL — authoring intent; may be range (e.g., "^2.5.0", "~=2.5") or pin (e.g., "2.5.3"); preserved in released Revisions for traceability
  resolved_version: "string"     # REQUIRED for Fixed and released materialized Float; immutable pin (e.g., "2.5.3")
  artifact_hash: "string"        # REQUIRED for Fixed and released materialized Float; algorithm-qualified (e.g., "sha256:...")
```

`version_spec` (authoring range) and `resolved_version` (immutable pin) are distinct fields with distinct purposes. Working sidecar in Float carries `version_spec` (and may carry stale-cached `resolved_version` from last fetch); release materialization writes `resolved_version` + `artifact_hash` definitively.

**`aiadra_catalog`** (another AIADRA project publishing software modules):

```yaml
catalog_ref:
  project_scope:
    project_id: "string"          # REQUIRED — stable AIADRA project identity per ADR/0008 §5
    locator_hint: "string"        # OPTIONAL — non-authoritative transport hint
  object_uuid: "string"           # REQUIRED — upstream SoftwareModule's UUID within its project
  revision_id: "string"           # REQUIRED for Fixed; pinned at release
  revision_content_hash: "string" # REQUIRED for Fixed per ADR/0008 §6
```

Same shape as [ADR/0014 §3](0014-object-type-component.md). Uncommon for software upstream but kept for template consistency.

**`custom`** (escape hatch):

```yaml
custom_ref:
  descriptor: "string"           # REQUIRED — opaque, project-policy-driven identifier
  content_hash: "string"         # REQUIRED for Fixed and released materialized Float; algorithm-qualified
```

### Hash algorithm convention

All hash fields are **algorithm-qualified strings**. The invariant is reconstructable integrity, not a fixed algorithm. Hash values commonly seen:

- `git-sha1:<oid>` — Git's traditional SHA-1 object id (most repositories today).
- `git-sha256:<oid>` — Git's SHA-256 object id (newer repositories).
- `sha256:<hex>` — Plain SHA-256 of artifact bytes (package tarballs, custom-content hashes, AIADRA `revision_content_hash`).

Future Schema Change Note can extend the supported algorithm set when production case surfaces (e.g., `blake3:`, `git-sha384:`, custom). The seed pins the *prefix-qualified-string* convention; the prefix vocabulary is consumer-policy-extensible.

### Float binding semantics, per discriminator

Release materialization is **staleness-intolerant** uniformly. The released Revision MUST contain the resolved-immutable identity fields per the discriminator:

| Discriminator | Released-Revision REQUIRED fields |
|---|---|
| `workspace_git` | `commit_hash` + `tree_hash` |
| `git_module` | `commit_hash` (+ `tree_hash` if `module_path` is present) |
| `package_registry` | `resolved_version` + `artifact_hash` |
| `aiadra_catalog` | `revision_id` + `revision_content_hash` |
| `custom` | `content_hash` |

If a Float binding cannot be resolved at release (no resolver available, network unreachable, version range matches no artifact, branch/tag does not exist), release hard-fails. Working sidecar preserves authoring intent fields (`ref`, `version_spec`, etc.) for traceability.

### 4. Namespace set — three of Part's seven plus singleton

Tighter than Component's five-of-seven (software has no geometry, no mates, no features):

| Namespace | In SoftwareModule seed? | Notes |
|---|---|---|
| `parameter:` | YES | Software-relevant parameters (min language version, max memory, license identifier, build flags). Same canonical-units-at-field-name discipline ([ADR/0010 §2](0010-relationship-type-composed-of.md)); not all software parameters carry units (`max_memory_mb` does; `license_id` does not). |
| `design_intent:` | YES | *Why this module*; substitution constraints; security / license rationale; version-pinning rationale; anchored by id to participating relationships. |
| `feature:` | NO | Not internally designed (in the CAD sense). |
| `relationship:` | YES | Participates as target (predominant) per Decision §5; may source `parameter_expression`. |
| `published_ref:` | NO in seed | API surface mirroring deferred — future Schema Change Note when API-reference relationship type lands. |
| `geometry_ref:` | NO | N/A. |
| `material:` | NO | N/A. |

**Three of Part's seven** plus the new singleton `software_module:` block.

### 5. Relationship participation + endpoint-schema extensions

- **`allocates_to` target — YES.** Natural use case: a Requirement is allocated to a software module. Schema extension: `relationship/allocates_to.schema.json` target Type union extended from `Part | Assembly | Component` to `Part | Assembly | Component | SoftwareModule` (additive).
- **`parameter_expression` endpoint (output and input) — YES.** Cross-module version-parameter relationships (e.g., this module's required Python version expressed as a function of upstream dependency's required Python version). Schema extension: `relationship/parameter_expression.schema.json` endpoint Type union extended from `Part | Requirement | Assembly | Component` to `Part | Requirement | Assembly | Component | SoftwareModule` (additive). The SoftwareModule-as-output authority guardrail generalizes [ADR/0015 §4](0015-relationship-type-parameter-expression.md)'s Component-as-output rule: output parameter must be local/consumer-authored, not a mirrored upstream/registry field.
- **`composed_of` target — NOT in seed.** Per Decision §6 below.
- **`satisfies` source — NOT in seed.** Deferred to future Schema Change Note (same posture as ADR/0014 §4's Component-as-`satisfies`-source deferral).
- **`mated_to` — N/A.** No geometry.
- **`derived_from` / `refines` — NO.** Requirement → Requirement only per [ADR/0012](0012-relationship-types-derived-from-and-refines.md).

### 6. `composed_of` participation — DEFER

SoftwareModule does NOT participate in `composed_of` in this bundle. The Claude1 / Codex1 analysis: extending `composed_of` to support a target Type without transform requires destabilizing [ADR/0010 §2](0010-relationship-type-composed-of.md)'s universal-transform assumption. A future software-specific composition relationship type (`embeds`, `depends_on`, `bundles`, etc.) — when mechatronic / embedded composition emerges as a load-bearing case — can land cleanly without rewriting ADR/0010.

Consequence: mechatronic / embedded systems composition of SoftwareModule into a parent Assembly is not yet schema-supported. The Wedge basic loop does not need it; deferring is the lower-risk call.

### 7. Optional record properties — minimal seed

Inherited from [ADR/0014 §3](0014-object-type-component.md) plus the discriminator-specific shape above. No extra fields in seed.

| Field | Required | Notes |
|---|---|---|
| `software_module.sourcing_discriminator` | REQUIRED | Enum per Decision §3. |
| `software_module.binding_mode` | REQUIRED | Float | Fixed. Default Float. |
| `software_module.*_ref` (one per discriminator) | REQUIRED | Per-discriminator shape per Decision §3. |
| `parameter:`, `design_intent:`, `relationship:` namespace records | optional | Stable ids per [S0 commitment 7](../TruthModelSchema.md). |
| `fact_provenance`, `fact_uncertainty` | optional | S1 annotations per [S3 commitment 4](../TruthModelSchema.md). |

### 8. Lifecycle, eventability, Revision schema, bundle bump

**Lifecycle** independent per Promotion C2 (both paths). States: `in_work` → `released` → `retired`. The consumer project owns each transition.

**Eventability** per [S3 commitment 5](../TruthModelSchema.md): `software_module_created`, `software_module_changed`, `software_module_released`, `software_module_retired`. `_changed` fires on author intent change (discriminator switch, binding_mode flip, upstream re-target, descriptor edit, namespace edits). Release materialization is NOT a `_changed` event per the broader [S3 commitment 12](../TruthModelSchema.md) pattern. Retirement is tombstoning.

**Revision schema** per [S2 commitment 1](../TruthModelSchema.md). Same canonical path as other Object Types: `revisions/<object-uuid>/<revision-id>.yaml`. Released Revision contains the resolved-immutable upstream binding (per Decision §3 release-time required fields).

**Bundle bump:** **v0.12.0 → v0.13.0**, MINOR additive per [ADR/0003 §11](0003-schema-governance.md). Changes:

- NEW: `sidecar/SoftwareModule.schema.json`.
- NEW: `object.type = "SoftwareModule"` discriminator value.
- NEW: `SM-NNNNNN` Number prefix mapping at the bundle level.
- ADDITIVE: `relationship/allocates_to.schema.json` target Type union (SoftwareModule added).
- ADDITIVE: `relationship/parameter_expression.schema.json` endpoint Type union (SoftwareModule added to input and output unions).

No existing artifacts break. All MINOR additive.

### 9. Validation rules (Layer 2)

- `object.type == "SoftwareModule"`.
- `software_module:` singleton block present.
- `software_module.sourcing_discriminator` ∈ {`workspace_git`, `git_module`, `package_registry`, `aiadra_catalog`, `custom`}.
- Exactly one of `workspace_ref` / `git_ref` / `package_ref` / `catalog_ref` / `custom_ref` present, matching discriminator.
- `software_module.binding_mode` ∈ {`float`, `fixed`}; default `float`.
- Per-discriminator Fixed / released-materialized requirements per Decision §3 release-table.
- All hash fields are algorithm-qualified strings (non-empty; contains a `:` separator between algorithm prefix and digest).
- Float (any discriminator): release MUST materialize to Fixed-equivalent resolved-immutable identity; hard-fail at release if no resolver / no hash producible.
- Released SoftwareModule Revision: upstream binding materialized with all per-discriminator release-time required fields.
- For `parameter_expression` records targeting SoftwareModule as output: output parameter's authority MUST be local/consumer-authored (not mirrored from upstream binding) — same guardrail as [ADR/0015 §4](0015-relationship-type-parameter-expression.md) Component-as-output.
- For `workspace_git`: no `project_scope`; the "upstream" is the project's own Commonspace.

## Worked sidecar examples

### Example 1 — `workspace_git` (first-party firmware)

A first-party firmware module authored in the same product Commonspace. No external upstream; integrity anchor is repo-local commit + tree hashes.

```yaml
object:
  uuid: "0193abcd-5555-7100-9aaa-eeeeeeeeeeee"
  type: "SoftwareModule"
  number: "SM-000003"
  lifecycle: "in_work"
  schema_version: "0.13.0"

software_module:
  sourcing_discriminator: "workspace_git"
  binding_mode: "float"
  workspace_ref:
    module_path: "firmware/motor_controller"
    ref: "main"                              # authoring intent; absent in released Revisions
    # commit_hash + tree_hash absent in working Float; pinned at release.

parameter:
  - id: "param_target_mcu"
    name: "Target microcontroller"
    value: "STM32F407"
    fact_provenance: { category: "human_input" }
    fact_uncertainty: "verified"
  - id: "param_max_memory_kb"
    name: "Maximum RAM footprint"
    value_kb: 128
    fact_provenance: { category: "human_input" }
    fact_uncertainty: "verified"

design_intent:
  - id: "di_substitution_constraint"
    statement: "Motor controller firmware bound to this physical drive assembly's CAN bus protocol. Any substitution must support CAN-FD plus the bootloader contract recorded in di_bootloader_protocol."
    anchors: ["software_module"]

# relationship: namespace omitted; this module participates as target of allocates_to from upstream Requirements.
```

### Example 2 — `git_module` (external Git submodule, subpath)

An external Git module pinned at a specific commit, where SoftwareModule represents a subtree of the upstream repo.

```yaml
object:
  uuid: "0193abcd-6666-7200-9bbb-ffffffffffff"
  type: "SoftwareModule"
  number: "SM-000019"
  lifecycle: "in_work"
  schema_version: "0.13.0"

software_module:
  sourcing_discriminator: "git_module"
  binding_mode: "fixed"
  git_ref:
    origin_id: "github:foundation-cryptography/oss-tls-lib"
    git_url: "https://github.com/foundation-cryptography/oss-tls-lib.git"  # non-authoritative
    ref: "v3.2.1"                                                          # authoring intent (a tag)
    module_path: "src/handshake"                                            # subtree of the upstream repo
    commit_hash: "git-sha1:a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4"
    tree_hash: "git-sha1:f1e2d3c4b5a69788776655443322110099887766"          # the src/handshake subtree

parameter:
  - id: "param_protocol_version"
    name: "TLS protocol version supported"
    value: "1.3"
    fact_provenance: { category: "supplier_datasheet_or_catalog" }
    fact_uncertainty: "verified"

design_intent:
  - id: "di_license_constraint"
    statement: "Adopted as Apache-2.0; do not substitute with a copyleft alternative without legal review."
    anchors: ["software_module"]
```

### Example 3 — `package_registry` (Python package, Float in working state)

A Python package from PyPI pinned by version range in working state; release will materialize the resolved version + artifact hash.

```yaml
object:
  uuid: "0193abcd-7777-7300-9ccc-aaaaaaaaaaaa"
  type: "SoftwareModule"
  number: "SM-000031"
  lifecycle: "in_work"
  schema_version: "0.13.0"

software_module:
  sourcing_discriminator: "package_registry"
  binding_mode: "float"
  package_ref:
    registry: "pypi"
    package_name: "numpy"
    version_spec: "^1.26.0"     # authoring intent; range
    # resolved_version + artifact_hash absent in working Float; pinned at release.

parameter:
  - id: "param_min_python_version"
    name: "Minimum Python version"
    value: "3.10"
    fact_provenance: { category: "supplier_datasheet_or_catalog" }
    fact_uncertainty: "verified"

design_intent:
  - id: "di_pinning_rationale"
    statement: "Pinned to 1.26.x for SIMD-vectorized matmul compatibility with the control firmware's intermediate exports."
    anchors: ["software_module"]
```

When released, the working `package_ref` materializes to add `resolved_version: "1.26.4"` and `artifact_hash: "sha256:..."` to the released Revision record. The working sidecar retains `version_spec: "^1.26.0"` for traceability.

## Consequences

- **Fifth Object Type lands.** Seed catalogue: Part, Requirement, Assembly, Component, SoftwareModule.
- **Second External pointer Object Type.** Validates the [ADR/0014](0014-object-type-component.md) template with Git-flavored discriminator shapes. Pattern Catalogue's "External pointer Object pattern operationalized" row's Applies-to extends from `Component (future SoftwareModule, MaterialSpec-like, etc.)` to `Component, SoftwareModule (future MaterialSpec-like, etc.)`.
- **Dual Promotion paths precedent.** First Object Type to invoke two distinct Promotion paths depending on discriminator (External pointer named non-disqualifier for four cases; basic capability test for `workspace_git`). Future Binding Object Types unifying in-project and external-binding semantics may use the same dual-path framing.
- **Algorithm-qualified hash convention pinned normatively.** Prior ADRs used `sha256:` convention in examples; ADR/0016 makes it normative for SoftwareModule hash fields (`workspace_ref.commit_hash`, `git_ref.commit_hash`, `package_ref.artifact_hash`, etc.). Algorithm prefix vocabulary is consumer-policy-extensible. Future Schema Change Note can backfill the convention to other hash-bearing schemas if desired.
- **`relationship/allocates_to.schema.json` and `relationship/parameter_expression.schema.json` endpoint Type unions extended.** Additive; existing records continue to validate. ADR/0013 and ADR/0015's overall status remains `accepted` (additive extension by ADR/0016, not supersession). The "target artifacts travel with the bundle bump" discipline (same as ADR/0014's extension of ADR/0010 / ADR/0011 / ADR/0013) holds.
- **Glossary `parameter_expression` entry update.** "Cross-project parameter references route through local Component" wording generalizes to "route through local Binding Object such as Component or SoftwareModule." Same Binding Object discipline, broader applicability.
- **Schema bundle bump.** Active bundle moves v0.12.0 → v0.13.0.
- **Glossary additions.** [Glossary.md](../Glossary.md) v0.17: new `SoftwareModule` entry; update to `parameter_expression` entry's local-Binding-Object wording.
- **SystemState updates.** Pattern Catalogue External pointer Object row Applies-to edit; Recent Pattern Changes entry; Current Front advance.
- **`composed_of` participation deferred.** Future software-specific composition relationship type (e.g., `embeds` / `depends_on`) when mechatronic / embedded composition becomes load-bearing.
- **API surface mirroring deferred.** No `published_ref:` in SoftwareModule seed. Future Schema Change Note when an API-reference relationship type lands.
- **SoftwareModule as `satisfies` source deferred.** Future Schema Change Note (ADR/0009 endpoint extension).
- **Electrical component per-Type ADR remains separately deferred.** Awaits KiCad Domain Engine ADR per [Manifesto P12](../Manifesto.md).
- **Wedge readiness for software-bearing products.** Software dependencies allocatable; cross-module parameter constraints expressible via `parameter_expression`. The basic Wedge does not exercise this; a mechatronic Wedge variant is now schema-feasible end-to-end.
