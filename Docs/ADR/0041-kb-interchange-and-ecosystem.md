# ADR/0041 — KB Interchange & Ecosystem (import / export / packs)

## Frontmatter

- **Status:** **Accepted** — 2026-07-11 (arc 20260711-8; two-round: Claude1+draft / Codex1 / Claude2 close. Codex1 verdict "strong consolidation, contractual"; B1 co-land the ADR/0034 attorney item (done — [ADR/0034 Attorney-review #6](0034-licensing-and-third-party-kernel-compliance.md) added in the same commit); D4 wording softened to "intended/expected not to conflict, subject to attorney review"). Consolidates one fully-converged discussion arc: **20260711-5** (KB interchange & ecosystem; Codex1 accept-premise + B1 license-state-separate-from-lineage + B2 data-only/prompt-injection-hardened trust boundary + Q1–Q7 + blind spots).
- **What it is:** the ADR that makes the two-tier KB ([ADR/0039 D9/D10](0039-the-aiad-authoring-model.md); [ADR/0037 Amendment A1](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md)) **shareable and tradeable** — the community / ecosystem layer. It pins the **KB pack** format, **import-as-a-digest-locked source tier**, the **two-group import lock** (content lineage + license/import state), the **data-only, prompt-injection-hardened trust boundary**, and the **ecosystem-not-Core marketplace posture**. Written **contractually** (Codex: *"a KB pack is a mounted, read-only, digest-locked data source with explicit license/import state — not code, not a plugin, not a hosted-service dependency, not a way for third-party content to acquire privileged authority"*).
- **Macro direction:** Petre, 2026-07-11 — *"a local/custom KB should be easily importable and exportable. This will be the mechanism to have people building on each other's knowledge and build a strong community. It will also open the option for some people to build stores of KBs and monetize some of their work."*
- **Version impact:** vision/scope ADR — no code this arc. Fills the **[ADR/0037 A1.7](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md) `pack:` deferral** (a one-line pointer co-lands in ADR/0037 A1.7). References [ADR/0039](0039-the-aiad-authoring-model.md) (two-tier KB), [ADR/0037](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md) (KB architecture + A1), [ADR/0034](0034-licensing-and-third-party-kernel-compliance.md) (licensing). The **[ADR/0034](0034-licensing-and-third-party-kernel-compliance.md) attorney list grows by one** (commercial-pack distribution — D4). No bundle/schema/Glossary/Manifesto change.

## §0 — What this ADR does

The two-tier KB ([ADR/0039](0039-the-aiad-authoring-model.md)) made configurators durable, git-tracked, digest-locked assets. **Interchange makes them shareable and tradeable** — turning "AIADRA grows a KB as a by-product" into "AIADRA grows a **KB economy**." The load-bearing good news: this **reuses the two-tier machinery almost entirely** — a shared or sold KB is just *another source tier* with the same digest-lock, `override`/`origin` lineage, and acceptance-bundle discipline. The genuinely new pieces are the **pack format**, the **license/import-state lock**, the **trust boundary**, and the **marketplace posture** — the four things this ADR pins contractually.

## Decisions

### D1. The interchange unit — a KB pack (Q1)
The portable unit is a **KB pack**: a self-contained bundle of one or more configurators + their acceptance bundles ([ADR/0039 D7](0039-the-aiad-authoring-model.md)) + a **`pack.yaml`** manifest (pack id/version, publisher identity, **license**, engine/adapter compatibility reusing the `compatible:` block, the `pack:<publisher>/<name>:` namespace it claims, content digests). **Transport-agnostic:** a git repo *or* a tarball, **normalized to ONE canonical mounted tree digest** — the canonical-digest rules of D5 make transport, tar ordering, and path normalization irrelevant to meaning.

### D2. Import = mount a pack as a READ-ONLY, digest-locked `pack:` source tier (Q1)
Import mounts a pack as a new **read-only, digest-locked source** under its `pack:<publisher>/<name>:` namespace — **architecturally identical** to how a core-KB source is mounted ([ADR/0039 D9/D10](0039-the-aiad-authoring-model.md); [ADR/0037 A1](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md)). It participates in the merged retrieval view exactly like `core:` and `project:`. **Fork-to-customize** into the project KB records a **digest-backed `origin`** ([ADR/0039 D10](0039-the-aiad-authoring-model.md)); a pack is never edited in place. **Export** bundles a project-KB subset into a pack (manifest + license + provenance + acceptance bundles). This **fills the [ADR/0037 A1.7](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md) `pack:` deferral**.

### D3. The import lock records TWO SEPARATE groups — content lineage AND license/import state (B1)
`origin` + `source_context` prove *where* content came from; they do **not** prove license acceptance, attribution preservation, commercial rights, or re-export permission. The import lock therefore records **two distinct groups**:
1. **Content lineage** — pack id, publisher id, version, namespace, canonical **tree digest**, per-artifact digests, and the digest-backed `origin` on any fork.
2. **License / import state (SEPARATE)** — license id + **license text digest** (or immutable license-URL digest); `accepted_by` + `accepted_at` (local import); **attribution requirements** (surfaced to export/report generation); **re-export + derivative permissions** as machine-readable policy; an optional **entitlement reference** for paid packs — *kept out of Core if it implies accounts, payment, or hosted services*; and **pack-upgrade + license-change behavior with no silent mutation** of an existing lock.

### D4. Licensing — a KB pack is DATA with its own license; directional, not a legal conclusion (B1 / ADR/0034 honesty)
A KB pack is **data consumed by the AGPL engine, not linked program code** — like a font or a document — so it **carries its own license** (`pack.yaml`): CC-BY / CC0 / a commercial or proprietary EULA / AGPL, at the author's choice. A commercial/proprietary pack license **is intended/expected not to conflict with AIADRA's AGPL** ([ADR/0034](0034-licensing-and-third-party-kernel-compliance.md)) — because the engine *reads* the data rather than linking it — the legal basis for monetization, **subject to attorney review** (this is directional, not a legal conclusion; arc 20260711-8 note). This is **directional, stated but not overstated**: the ADR makes **no final legal conclusion**; **executable pack contents are out of data-only scope** (→ [ADR/0034](0034-licensing-and-third-party-kernel-compliance.md) dependency-policy review); and **commercial-distribution claims need attorney review** (a new item on the ADR/0034 attorney list). Import **surfaces the license**; re-export/fork respects it (the D3 lineage + attribution/re-export policy make derivation visible).

### D5. The trust boundary — data-only, prompt-injection-hardened (B2)
Imported pack content is read by deterministic code **and surfaced to BYO-AI workflows**, so "data not code" is only airtight with explicit rules. The ADR requires:
- **Strict schema validation** for `pack.yaml` and every mounted KB artifact.
- **No executable content of any kind** — no hooks, scripts, macros, dynamic imports, shell commands, Python/JS, or plugin loading. (Executable content moves the pack out of data-only scope → D4.)
- **Pack prose is untrusted content, never instructions** — pack-authored prompts, question text, descriptions, examples, and tags are treated as untrusted *content*; **AI retrieval wrappers quote/delimit** pack text so it cannot override AIADRA operating rules (the **prompt-injection defense**).
- **Overrides are namespace-scoped by default** — a pack's `overrides:` can only affect its own `pack:` namespace; **suppressing core or project KB requires explicit project-level opt-in**, never semantic shadowing (this *hardens* [ADR/0039 D10](0039-the-aiad-authoring-model.md) / arc 20260711-2 B2).
- **Canonical archive/tree digest rules** — tar ordering, path normalization, symlink handling, and case collisions **cannot alter meaning** (defeats path-traversal / symlink / case-collision archive attacks; normalizes git-repo and tarball transport to one digest, D1).
- **Signatures optional, digest locks minimum** — signature verification is an available provenance feature; a digest lock is the floor.
- **The malicious-pack story:** *a pack can propose bad **data**, but it cannot execute code, hide its origin, silently override higher-trust sources, or commit geometry without the normal acceptance bundle and human-approval path* ([ADR/0039 D3](0039-the-aiad-authoring-model.md) three-state model applies to imported candidates unchanged).

### D6. Canonical units in the pack schema (Codex checklist watch)
Parameter and elicitation schemas in an imported pack carry **unit-bearing or schema-fixed `_mm`/`_deg` fields** — no implicit unit assumptions ever cross a pack boundary (consistent with [ADR/0037 A1.6](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md) / [ADR/0039 D13](0039-the-aiad-authoring-model.md)).

### D7. The marketplace posture — ECOSYSTEM, never Core (P11; Q5)
[Manifesto P11](../Manifesto.md): **AIADRA Core hosts no store.**
- **Core-compatible:** local import/export, local pack listing, manifest validation, provenance/license surfacing, and BYO-configured source discovery (the static local KB-source discovery helper of [ADR/0039 D10](0039-the-aiad-authoring-model.md) — enumerate roots / list manifests / return digests; no ranking, no hosting).
- **NOT Core (a separate ecosystem product, later, if ever):** a ranked registry, a hosted marketplace, payments, telemetry, centralized trust scoring, or a first-party commercial pack store.
AIADRA ships the **interchange format + import/export + provenance/lineage + license surfacing**; the stores and registries are third-party/BYO (a git host, a published pack file, an npm-like registry, or a dedicated marketplace someone builds on top). The value accrues to publishers; AIADRA benefits from the network effect **without hosting it or sitting in the rent-seeking middle**.

### D8. Named blind spots the interchange implementation must handle (Q7)
The implementation arc must address, and the pack format must not preclude: **pack upgrade semantics**; **namespace collision + publisher identity**; **offline import**; **signature/key rotation**; **revocation behavior**; **license-text immutability**; **symlink/path traversal**; **case-sensitive path collisions**; and **fork-and-re-export**. (Named here so none is a silent gap; specifics land with the implementation arc.)

## Consequences

- **Positive:** the community/monetization vision Petre wants is enabled with **~90% reuse** of the two-tier KB machinery; provenance/lineage makes "building on each other's work" auditable; licensing works because a pack is data (its own license, no AGPL conflict, directionally); the trust boundary is airtight by construction (no code execution + human-approval-to-commit + prompt-injection quoting); P11 stays clean (interchange is Core, the store is ecosystem).
- **Deferred / out of scope:** executable packs (→ dependency-policy review); a first-party marketplace/registry/payments (ecosystem product); the D8 blind-spot mechanics (implementation arc).
- **Watches:** stable ids + digests at artifact level; `select`-configurator catalog content still routes through local Component/Binding, not direct catalog endpoints; no hosted catalog/registry dependency; the ADR/0034 attorney item (commercial-pack distribution) is a **release-prerequisite confirmation**, not a build blocker.

## Alternatives considered

- **Origin lineage carries licensing too** — rejected (D3): provenance ≠ entitlement; license/import state is a separate, explicit lock group.
- **Concluding "all commercial packs are AGPL-conflict-free"** — rejected (D4): stated as directional; attorney review gates commercial-distribution claims; executable packs are out of data-only scope.
- **"Data, not code" as sufficient for safety** — rejected (D5): pack text reaches BYO-AI workflows, so prompt-injection hardening (quote/delimit; overrides namespace-scoped) + canonical-archive rules are required.
- **A first-party AIADRA marketplace as the mechanism** — rejected (D7): violates P11; interchange + provenance is Core, the store is a separate ecosystem product.
- **Folding interchange into ADR/0037 or ADR/0034** — rejected (Q6): it is its own boundary (format + source-tier mounting + license state + ecosystem posture); those ADRs are references, not the home.
