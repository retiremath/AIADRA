# ADR/0027 — AIAD positioning + Native Engine posture

## Frontmatter

- **Status:** Accepted — 2026-05-31 (arc 20260531-11; three-round convergence Claude1 + Codex1 / Claude2 + Codex2 / Claude3 + Codex3).
- **Supersedes:** [OQ-0004](../OpenQuestions.md#oq-0004) (FreeCAD fork trigger); [OQ-0005](../OpenQuestions.md#oq-0005) (FreeCAD upstream cooperation).
- **Reframes:** [OQ-0006](../OpenQuestions.md#oq-0006) (multi-tool sequencing) — sequencing posture retained; per-domain shape pivots from "wrap external tools" to "AIADRA-native engines using third-party libraries."
- **Amends:** [Manifesto.md](../Manifesto.md) (v0.3 → v0.4: §"What AIADRA is" + P12 + non-goal at the "integration wrapper" line + About-this-document terms list); [ArchitectureOverview.md](../ArchitectureOverview.md) (v0.1 → v0.2: Layer 5 row + Layer 5 § + Ring 3 framing + five-layer historical-framing intro + Commonspace/Vault/Workspace bullet); [Glossary.md](../Glossary.md) (v0.24 → v0.25: AIADRA entry reframed to AIAD platform + new "AIAD" entry; drop "Domain Adapter" entry; add "Native Engine" + "Data Adapter" entries; reword "Workspace" + "Workspace Browser").
- **Retrofits (terminological + structural-shell):** see Decisions §D13 + §D18 + §Supersession register.
- **No schema bundle bump.** Bundle stays v0.27.0.
- **No `aiadra-core` version bump.** aiadra stays 0.9.0.

## §0 — AIAD positioning

**AIADRA is not a CAD platform; it is an AIAD platform.**

**AIAD = AI-Augmented Design.** AIAD systems are a distinct category from CAD systems:
- In **CAD** (Computer-Aided Design), the computer aids the human. The computer is a *tool*.
- In **AIAD** (AI-Augmented Design), the AI is a structural engineering participant. The AI *proposes*; the deterministic core *validates*; the human *approves* ([Manifesto P2 + P5](../Manifesto.md)).

"Design" in AIAD is category-language for the **whole product-engineering authoring loop** (mechanical / electrical / software / procurement / DV / requirements / V&V) — not a retreat to CAD/drawing-only scope. AIADRA is an AIAD platform across all five Layers of [ArchitectureOverview.md](../ArchitectureOverview.md); the AIAD framing characterizes the **system category**, not a specific Layer.

This positioning is compatible with — and reinforced by — the [ADR/0026 §0 BYO-AI posture](0026-ai-action-protocol-scope.md). BYO-AI is about *which* AI agent calls Ring 2's contracts; AIAD is about *what kind of platform* AIADRA is. The two compose: a BYO-AI agent (cloud LLM, local LLM, deterministic script) calls AIADRA's Ring 2 contracts to author content via AIADRA-native engines.

## §1 — Native Engine posture (implementation strategy)

AIADRA implements its own authoring runtimes per domain. These are **Native Engines** — AIADRA-implemented, AIAD-native, kernel-using-but-not-kernel-replacing software.

- **Third-party kernels and libraries are dependencies, allowed and encouraged.** OCCT (OpenCascade) for mechanical geometry kernel. KiCad's reusable libraries (libcommon, eeschema, pcbnew engines) for electrical. Library dependency is bounded by: (a) clean public API; (b) usable statelessly / per-Transaction; (c) doesn't impose its own truth-ownership model.
- **Third-party applications are research material, NEVER dependencies.** FreeCAD-the-application, KiCad-the-application, Solvespace-the-application, etc. are studied for their solved problems (parametric graph; sketch solver integration; constraint propagation; feature recomputation invalidation; history graph editing; multi-body operations; assembly mating constraint solver). AIADRA reads their source, reads their friction logs (years of issue trackers), learns what works and what doesn't, and re-implements the AIADRA-native equivalent on top of OCCT (or equivalent library kernel).

**No fork. No wrap. No plugin. No workbench.** Inspiration, not derivation.

## §2 — Why this posture, why now

[Ring 2 implementation strand closed in arc 20260531-10](0026-ai-action-protocol-scope.md) (Phases A-D shipped Layers 1-3 end-to-end). The natural next question is: what's the relationship between AIADRA and existing engineering tools? The pre-ADR/0027 answer assumed wrap-or-modify-or-fork:

> [Manifesto §"What AIADRA is" pre-v0.4](../Manifesto.md): "AIADRA does not wrap these tools loosely. It modifies them so they expose their kernels natively..."
> [Manifesto non-goal pre-v0.4](../Manifesto.md): "Not an integration wrapper around unmodified tools. Tools are modified to expose their kernels."

That progression — start as workbench → patch FreeCAD where insufficient → fork only when blocked — assumes the impedance mismatch with FreeCAD-the-application is local. It is not. Five structural reasons:

1. **Truth ownership is inverted.** Manifesto P1 says the Product Truth Model owns truth and tools synchronize. FreeCAD's FCStd format IS the project — the document is the truth. Bidirectional sync between two sources of truth is famously dishonest.
2. **Event-sourced vs state-based.** AIADRA's correctness model is events + sidecars + Revisions with cross-artifact invariants. FreeCAD's document model is a state graph with an undo stack. Intercepting every FreeCAD mutation and translating it to canonical AIADRA events without losing semantics is exactly the kind of "fight upstream forever" path [OQ-0004](../OpenQuestions.md#oq-0004) was worried about.
3. **Design-intent first vs geometry first.** [P4](../Manifesto.md): "Not 'hole removed from cylinder' but 'M8 clearance for MTR-0007 per REQ-014.'" FreeCAD's feature tree is geometry-first; intent lives in property annotations. Inverting that priority is foundational, not a plugin.
4. **AI-first surfaces don't exist in FreeCAD.** Stable parameter IDs that survive geometry edits, sketch constraints addressable as facts, parametric features that survive mate re-evaluation — none of FreeCAD's surfaces are designed to be the *target* of structured AI proposals. They're designed for a human dragging in the viewport.
5. **The cautionary tale.** [OQ-0004](../OpenQuestions.md#oq-0004) cited RealThunder/LinkStage as the friendly-fork-fighting-upstream-forever path. Starting on FreeCAD and only forking "when blocked" almost guarantees ending up there.

**The sharpening that matters: keep the kernel, replace the application.** OpenCascade (OCCT) is 1.5M+ LOC of production geometric kernel — replicating it is decades, not years. The [Manifesto opening at L17](../Manifesto.md) already cites "FreeCAD/OpenCascade" as substrate; the v0.4 wording (per §D9 below) makes the relationship precise: OCCT is a library AIADRA depends on; FreeCAD-the-application is not.

## Decisions

### D1. ADR scope — meta-positioning + Layer 5 posture, co-landed

Both halves (AIAD framing + Native Engine implementation strategy) ship in ONE ADR because they're coupled. NO concrete Ring 3 mechanical-engine scope in this ADR — that's a separate future ADR (working number 0028) downstream. Multi-document amendments (Manifesto + ArchitectureOverview + Glossary + OpenQuestions) co-land here.

### D2. AIAD as system category

Pin **AIAD = AI-Augmented Design** as a named system category. Glossary entry added per Q10 + Glossary v0.24 → v0.25 diff. Codex Q1 clarification incorporated: "Design" is category-language for the whole product-engineering authoring loop, not CAD-only.

### D3. Third-party kernels = library dependency

OCCT (canonical example). KiCad's libcommon / EDA engines (electrical). Existing geometric / constraint-solving / kernel-grade work is not in scope to replicate. Library dependency bounded by clean API + stateless usability + no truth-ownership imposition.

### D4. Third-party applications = research material, NEVER dependency

FreeCAD-the-application, KiCad-the-application, Solvespace-the-application, etc. AIADRA reads their source, reads their friction logs, learns, **re-implements** the AIADRA-native equivalent on top of OCCT. No fork; no wrap; no plugin; no workbench.

Per Codex1 Q4: Same posture applies to KiCad. Reusable KiCad libraries are plausible dependencies; KiCad-the-app is research material.

### D5. Layer 5 reframing — "Domain Engine" → "Native Engine"

[ArchitectureOverview.md Layer 5](../ArchitectureOverview.md) reworded (v0.1 → v0.2). [Glossary "Domain Engine" L31](../Glossary.md) reworded as "Native Engine." Rename applies in this ADR (not deferred to ADR/0028) per Codex1 Q2.

### D6. Ring 3 reshape — "Domain Adapter contract" → "Native Engine Implementation contract"

Ring 3's job changes from "specify how AIADRA wraps external tools" to "specify what a Native Engine offers AIADRA + how it emits events + how its parametric surface maps to Ring 2 `propose(kind=...)` operations." Concrete shape pinned in ADR/0028. ADR/0027 pins the *direction* and the *naming*.

### D7. OQ-0004 + OQ-0005 SUPERSEDED

Both questions presuppose AIADRA runs on FreeCAD. Under the Native Engine posture, AIADRA does not run on FreeCAD — there's no fork to trigger and no cooperation strategy to define beyond "study their solutions; cite their friction." Status: `superseded-by-adr/0027`. Historical question text preserved in OpenQuestions for archaeology.

### D8. OQ-0006 REFRAMED, not superseded

Multi-tool sequencing (mechanical first → electrical → data-only) still applies; semantics shift:
- "Mechanical first" = build AIADRA-native mechanical engine first (using OCCT as library).
- "Electrical second" = build AIADRA-native electrical engine (likely using KiCad's reusable libraries).
- "Data-only" (procurement, DV) = Data Adapters per D12, not Native Engines.

Status remains `deferred-to-ring-5` for the cross-domain sequencing decision; per-domain shape pivots.

### D9. Manifesto amendments

Concrete edits (Manifesto v0.3 → v0.4):

- **Line 17** ("AIADRA does not wrap these tools loosely. It modifies them so they expose their kernels natively and synchronize with AIADRA's Product Truth Model.") → REPLACE with:

  > "AIADRA implements its own AIAD-native authoring engines per domain. These Native Engines use third-party kernels and libraries (OCCT for mechanical, etc.) as dependencies, but never wrap third-party applications. The Product Truth Model owns truth; Native Engines produce content against it."

- **Line 64 non-goal** ("Not an integration wrapper around unmodified tools. Tools are modified to expose their kernels.") → REPLACE with:

  > "Not a wrapper around any third-party application (modified or unmodified). AIADRA implements its own authoring runtimes; third-party engineering applications are research material, not implementation dependencies."

- Active-versions line in Manifesto frontmatter: v0.3 → v0.4.

### D10. Sequencing — what comes after this arc

Four downstream arcs implied (revised per Codex1 B2 absorption to include the Part authoring SCN dependency):

- **(a) Ring 3 scope ADR** (working ADR/0028) — concrete shape of Native Engine Implementation contract + Native Engine handler-registration mechanism.
- **(b) Part authoring SCN** (working ADR/0029) — new `part_changed` event with `feature_delta` + `geometry_ref_delta`; bundle v0.27.0 → v0.28.0 MINOR additive. **Pre-condition for (d) per D17 revision.**
- **(c) Wedge-003 scope ADR** — analogous to ADR/0023 / ADR/0024 precedent.
- **(d) `aiadra-mechanical` ecosystem-package implementation** — first concrete Native Engine slice per D17.

Plus optional parallel:
- **(e) Per-engine research arcs** — informal study + writeup of FreeCAD / KiCad / Solvespace / OpenSCAD / Onshape solutions to mechanical authoring sub-problems. Could be `Docs/Research/` notes rather than ADRs.

Recommendation: (a) → (b) → (c) → (d). (e) runs in parallel and feeds (c) + (d).

### D11. Native Engines as ecosystem packages — NOT in `aiadra-core`

Per [Manifesto P11](../Manifesto.md) modularity + the [ADR/0026 Decision §6 Tier-3 RPC precedent](0026-ai-action-protocol-scope.md) ("Tier-3 RPC adapters live in SEPARATE ecosystem packages"), each Native Engine ships as its own package:

- `aiadra-core` — Layers 1-3 + Vault Adapter abstract + CLI. Kernel-free. Truth-Model-focused. STAYS as-is.
- `aiadra-mechanical` (ecosystem package, future) — mechanical Native Engine. Depends on OCCT (or its Python bindings).
- `aiadra-electrical` (ecosystem package, future) — electrical Native Engine. Depends on KiCad's reusable libraries.
- `aiadra-mcp` (ecosystem package, future) — Tier-3 RPC binding for MCP per ADR/0026.

Native Engine packages register their `propose(kind="mechanical.<op>", ...)` handlers with Ring 2's dispatch table at import time (entry-point or explicit `register_handler()` call — mechanism per ADR/0028). This preserves "core stays small + auditable" + keeps OCCT off `aiadra-core`'s dependency tree.

### D12. Layer 5 has TWO categories — Native Engines AND Data Adapters

- **Native Engine** — domain with a *parametric authoring surface*. Implements AIADRA-native authoring runtime, using third-party kernel libraries. Emits canonical content (sidecars + events + Vault blobs) directly. Ecosystem packages. Examples: `aiadra-mechanical`, `aiadra-electrical`.
- **Data Adapter** — domain that is *pure data flow* (no parametric authoring). Lighter-weight: format converters, external-tool data ingestion, BOM exports, instrument-data importers, requirements-management bridges (DOORS / Polarion / ReqIF per [ADR/0006 L404](0006-object-type-requirement.md)). May be ecosystem packages OR optional core extras. Examples: `aiadra-bom-export`, `aiadra-doors-ingestion`, `aiadra-instron-csv-ingestion`.
- **Software source (Git) is a special case** — Git IS the substrate per [Manifesto P12](../Manifesto.md); no separate Native Engine or Data Adapter needed. Direct Git interaction via standard tooling.
- **DV / TestExecution** — primarily Data Adapter territory (ingesting test results, signing reports). TestProcedure authoring is document authoring, not parametric — also Data Adapter scope.

Implementation cost differs by an order of magnitude: mechanical Native Engine is years; CSV Data Adapter is days.

### D13. Uniform terminological retrofit clause

The number of references to "Domain Engine" / "Domain Adapter" / "FreeCAD Domain Adapter scope" across prior ADRs + TruthModelSchema + Glossary is substantial. Editing each downstream location is high-churn + dilutes ADR/0027's load-bearing role.

**Instead, ADR/0027 declares this uniform retrofit:**

> All prior references to "Domain Engine" are read as "Native Engine" per D5.
>
> All prior references to "Domain Adapter" are read as either "Native Engine" (if the referenced work is parametric authoring per D12) or "Data Adapter" (if pure data flow). The Glossary "Domain Adapter" entry itself is DROPPED per Q10 / D5; the structural shell that this entry abstracted is preserved per D18.
>
> All prior references to "awaits FreeCAD Domain Adapter scope" (notably the `derived_geometry_from` blocker citation across ADR/0015, ADR/0018, ADR/0021, ADR/0022, ADR/0025, ADR/0026) are read as "awaits AIADRA-native mechanical engine scope (Ring 3 / ADR/0028)."
>
> Sidecar examples in ADR/0005 §7 and ADR/0007 L294 that cite FreeCAD `.FCStd` documents as `engine_artifact_ref` values or `stable_engine_object_id` resolvers are read as **illustrative-only** — the schema fields themselves are kernel-agnostic; per D18, those fields' role is reframed as the Native Engine / Data Adapter payload shell. Concrete Native Engine surfaces per ADR/0028.

The retrofit clause is auditable: the supersession register below lists every affected location. Future-archaeology readers find both the original wording AND the retrofit reading by following the register's entries.

### D14. File format interop is LOAD-BEARING for the mechanical Native Engine

Per Codex1 N1 absorption (wording softened from Claude1):

Without STEP import/export, the mechanical Native Engine is unusable in any real engineering environment (every existing CAD-emitted part / supplier-provided model / standards-pinned geometry arrives as STEP). Concrete minimum scope for mechanical Native Engine v1:

- **STEP AP203/AP214 import** — read part bodies + basic assembly structure; named parameters where present (best-effort, importer-specific — neutral STEP does NOT reliably reconstruct AIADRA-native feature/parameter history; parametric round-trip is a future SCN at most).
- **STEP AP203/AP214 export** — emit AIADRA-native parts as STEP for downstream tools (verification, supplier transfer, archival).
- **IGES** — secondary; some legacy ecosystems need it.
- **STL** — for 3D-printing pipeline and visualization.
- **STEP AP242 (PMI)** — secondary; for PMI / GD&T round-trip; under the D13 retrofit, the [ADR/0011 §"AP242 / STEP round-trip" commitment](0011-relationship-type-mated-to.md) is now Native Engine import/export scope.
- **OCCT-native BREP** — internal; for Vault canonical storage option.

Adds substantive but bounded scope to the mechanical engine arc. Honest call-out: this work is not optional and represents months of engineering by itself. D14 is a **scope register**, not an implementation commitment in this ADR; concrete priority + sequencing lives in ADR/0028.

### D15. OCCT licensing posture (LGPL 2.1) + Python binding choice

Per Codex1 N2 absorption (softened from Claude1):

- OCCT is LGPL 2.1. Dynamic linking is permitted for any project license; static linking has share-modifications-upstream restrictions. AIADRA-native engines that depend on OCCT link it **dynamically**.
- AIADRA Core's current license is `TBD` per [`aiadra-core/pyproject.toml`](../../aiadra-core/pyproject.toml). Explicit license review required before the mechanical engine package lands; specific compatible-license decision deferred to that review.
- Python binding to OCCT: two plausible upstreams — **pythonocc-core** (mature; LGPL 2.1) or **OCP** (newer; Apache 2.0; uses CadQuery's binding generator). Specific binding choice deferred to ADR/0028 per Codex1 Q9.

### D16. P2 ("AI proposes; deterministic core decides") boundary preserved

Native Engines are part of the **deterministic core**, not the AI side. The boundary holds end-to-end under the new posture:

```
Agent proposes:    propose(kind="mechanical.adjust_extrude_depth", params={...})
                        ↓                                  (AI side — probabilistic)
Ring 2 dispatch → Native Engine handler                    (deterministic boundary crossed)
                        ↓                                  (Native Engine side — deterministic)
Native Engine computes new geometry via OCCT               (OCCT is deterministic given same inputs)
                        ↓
Native Engine emits new sidecar + event + Vault blob       (deterministic emission)
                        ↓
Ring 2 validates                                           (deterministic Layer 2)
                        ↓
Human approves                                             (gate per P5)
                        ↓
commit() writes                                            (deterministic atomic write)
```

Native Engines DO NOT propose — they compute on demand. The agent proposes the operation kind + params; the Native Engine deterministically realizes it. This preserves [Manifesto P2 + P5](../Manifesto.md) wholesale; no weakening.

### D17. Wedge-003 concrete shape — gated on Part authoring SCN

Per Codex1 B2 absorption — REVISED FROM CLAUDE1.

**Pre-condition:** the v0.27.0 event surface has `parameter_changed` (scalar value mutations only) but **no `part_changed` event with feature / geometry / vault deltas**. Native Engine geometry writes cannot fold against the sidecar/event invariant without a new event type. Therefore Wedge-003 (and any subsequent Native-Engine-authored Object Type) is GATED on a focused **Part authoring SCN** that lands a new event surface before Wedge-003 implementation. (Sequencing per D10: (a) Ring 3 scope ADR/0028 → (b) Part authoring SCN ADR/0029 → (c) Wedge-003 scope ADR → (d) `aiadra-mechanical` implementation.)

**Candidate Part authoring SCN scope** (settled in the Wedge-003 scope ADR or in ADR/0029, NOT in ADR/0027):
- New `part_changed` event with `feature_delta` (add / remove / update feature records) + `geometry_ref_delta` (add / remove / replace geometry_ref records with their associated `vault_ref` content hashes)
- Sidecar/event fold + proposed-state validation extensions in `aiadra-core` for the new event in both read-side fold and Draft-then-commit boundary
- Native Engine handler registration mechanism per D11 (also ADR/0028 scope) so `propose(kind="mechanical.<op>", ...)` dispatches correctly

**Concrete Wedge-003 authoring loop** (assuming the Part authoring SCN has landed):
- **One** extruded rectangular sketch with **one** named parameter (e.g., `param_thickness_mm`).
- Backed by OCCT via the Python binding chosen per Q9 + D15.
- Editable via Ring 2: `propose(kind="mechanical.adjust_parameter", params={"obj_number": "P-000001", "parameter_id": "param_thickness_mm", "new_value": 8.0})`.
- Native Engine recomputes the extrusion via OCCT.
- Emits sidecar (P-000001 with new parameter value + updated `geometry_ref.vault_ref` after SCN lands) + events (`parameter_changed` for the scalar + `part_changed` for the `geometry_ref_delta`; possibly composed in a single Transaction via Phase C `propose`+`modify`) + Vault blob (canonical geometry format TBD: OCCT BREP or AIADRA-native serialization).
- Round-trip verification: export to STEP; re-import via OCCT; geometric identity check.

**Explicitly NOT in Wedge-003 scope:** assembly authoring; mating constraints; sketch solver UI; multiple features beyond the single extrusion; feature-tree manipulation; viewport (JSON-only authoring + STEP-export validation is sufficient for the loop).

This scope is meaningfully smaller than the prior FreeCAD-round-trip Wedge-003 sketch from [ADR/0023 §A4](0023-wedge-spike-scope-and-runtime.md) — it's not fighting an external application's document model; it's the smallest authoring loop that exercises the full Ring 1 → Ring 2 → Native Engine → Vault path.

### D18. Adapter shell compatibility — wire names preserved, semantic role reframed

Per Codex1 B1 absorption — NEW IN ROUND 2.

[ADR/0005 §9](0005-object-type-part.md) defines a governed adapter shell with required outer fields `engine` + `adapter_schema_version`, optional `engine_artifact_ref` + `stable_engine_object_id`. The shell appears in `feature:adapter_payload` and `geometry_ref:adapter_ref`. AIADRA Core uses it for dispatch, validation, and reference integrity. This is **structural**, not just terminology — the shell defines wire-format field names that AIADRA Core dispatches through.

**Decision: preserve wire names; reframe semantic role.**

- Wire-format field names survive verbatim. `engine` (e.g., `"freecad"`, `"kicad"`) → now reads `"mechanical-native"`, `"electrical-native"`, etc. as the canonical Native Engine discriminator values; legacy `"freecad"` / `"kicad"` are read-compatible identifiers for historical artifacts only. **No bundle bump; no Part / Drawing / TestProcedure / EvidenceArtifact schema change.**
- Semantic role: "AIADRA Core uses the shell for dispatch (`engine` → Domain Adapter)" reads as "AIADRA Core uses the shell for dispatch (`engine` → Native Engine handler registered via D11 ecosystem-package entry point)."
- "Promotion to a named cross-cutting spine pattern in TruthModelSchema waits on recurrence confirmation by a second Type ADR" ([ADR/0005 §9 last paragraph](0005-object-type-part.md)) still applies; recurrence already confirmed by Drawing / TestProcedure / EvidenceArtifact reuse, so the future spine promotion can happen but is not gated by ADR/0027.
- The shell's role as the **Native Engine / Data Adapter dispatch contract** is canonicalized by ADR/0027; concrete Native Engine handler-registration mechanism (entry-point name, registration call signature, dispatch table semantics) is ADR/0028's responsibility.

Alternative considered (mark shell as future SCN migration target with the old fields intentionally not changed by ADR/0027): rejected because path-1 (preserve + reframe) achieves the same outcome with zero schema churn and zero migration debt.

## Supersession + amendment register

29 affected locations covering primary edits + downstream retrofit + structural shell + TruthModelSchema:

### Primary line-precise edits

| Target | Current state | New state | Note |
|---|---|---|---|
| [Manifesto.md L17](../Manifesto.md#L17) | "modifies them so they expose their kernels" | D9 wording (Native Engines) | Manifesto v0.3 → v0.4 |
| [Manifesto.md L40](../Manifesto.md#L40) (Principle 12) | "the developer's local clone plus live Domain Engine sessions form the Workspace" | "live Native Engine sessions and Data Adapter processes form the Workspace" (Codex2 R3 absorption) | Same bump |
| [Manifesto.md L64](../Manifesto.md#L64) (non-goal) | "Not an integration wrapper around unmodified tools..." | D9 wording (no wrappers, any modification) | Manifesto v0.3 → v0.4 |
| [Manifesto.md L73](../Manifesto.md#L73) (About-this-document terms list) | "Terms in this document (UUID, Released Truth, Domain Engine, Commonspace, Vault, Workspace, etc.)" | "(UUID, Released Truth, AIAD, Native Engine, Data Adapter, Commonspace, Vault, Workspace, etc.)" (Codex2 R3 absorption) | Same bump |
| [ArchitectureOverview.md L18](../ArchitectureOverview.md#L18) (five-layer historical framing) | "Domain Engines moved to the outer ring" | "Native Engines + Data Adapters (called 'Domain Engines' in the original sketch, per ADR/0027 terminology pivot) moved to the outer ring" (Codex2 R3 absorption) | ArchitectureOverview v0.1 → v0.2 |
| [ArchitectureOverview.md L30](../ArchitectureOverview.md#L30) (Layer 5 row) | "FreeCAD/OCCT... modified to expose kernels... Domain Adapter contract" | D5 + D12 wording | Same bump |
| [ArchitectureOverview.md L113-128](../ArchitectureOverview.md#L113) (Layer 5 §) | "modified... wrapped external silos... Domain Adapter contract" | D5 + D6 + D12 wording | Same bump |
| [ArchitectureOverview.md L151](../ArchitectureOverview.md#L151) (Commonspace/Vault/Workspace bullet) | "live Domain Engine sessions" | "live Native Engine sessions / Data Adapter processes" (Codex2 R3 absorption) | Same bump |
| [ArchitectureOverview.md L177](../ArchitectureOverview.md#L177) | "Ring 3 will specify Layer 5's Domain Adapter bridge" | "Ring 3 will specify Native Engine Implementation contract + Data Adapter integration pattern" | Same bump |
| [Glossary "Domain Engine" L31](../Glossary.md#L31) | "External tool... AIADRA modifies these tools..." | "Native Engine — AIADRA-implemented authoring runtime per domain..." | Glossary v0.24 → v0.25 |
| [Glossary "Domain Adapter" L33](../Glossary.md#L33) | "The bridge between a Domain Engine and the Product Truth Model..." | **DROPPED** (per Q10); add "Data Adapter" entry per D12 | Same bump |
| [Glossary "Workspace" L49](../Glossary.md#L49) | "live Domain Engine sessions (FreeCAD, KiCad, etc.) currently open" | "live Native Engine sessions / Data Adapter processes currently active" | Same bump |
| [Glossary "Workspace Browser" L51](../Glossary.md#L51) | "Domain Engines (FreeCAD, KiCad) act as tool-specific sub-browsers" | "Native Engines act as domain-specific sub-browsers" | Same bump |
| [OQ-0004](../OpenQuestions.md#oq-0004) | `deferred-to-ring-3` | `superseded-by-adr/0027` | No fork to trigger |
| [OQ-0005](../OpenQuestions.md#oq-0005) | `deferred-to-ring-3` | `superseded-by-adr/0027` | No upstream-cooperation to define |
| [OQ-0006](../OpenQuestions.md#oq-0006) | `deferred-to-ring-5` | unchanged status; D8 reframing note appended | Sequencing still applies, semantics changes |

### Downstream ADR references — D13 uniform retrofit + D18 structural shell

| ADR / Doc | Reference | Retrofit reading |
|---|---|---|
| [ADR/0001 L143](0001-storage-substrate.md#L143) | "Domain Engine sessions" | "Native Engine sessions" |
| [ADR/0005 §7](0005-object-type-part.md) `engine_artifact_ref` "(e.g., FreeCAD `.FCStd`)" + `stable_engine_object_id` "(e.g., named object in FreeCAD document)" | Schema fields are kernel-agnostic; examples are illustrative-only; per D18 shell preserved verbatim |
| [ADR/0005 §9](0005-object-type-part.md) — adapter shell (entire section) | **D18 governs**: wire names preserved (`engine`, `adapter_schema_version`, etc.); semantic role reframed as Native Engine / Data Adapter dispatch contract; no bundle bump; concrete handler-registration mechanism per ADR/0028 |
| [ADR/0005 §229](0005-object-type-part.md#L229) ("Adapter contract... the first concrete adapter (FreeCAD for the Wedge)") | Per D18: "the first concrete Native Engine (`aiadra-mechanical` per D11) lands per ADR/0028 + the Part authoring SCN per D17" |
| [ADR/0005 §148, §159, §161](0005-object-type-part.md) ("per-feature schema taxonomy is deferred entirely to a future Domain Adapter ADR"; "the Domain Adapter's local cache"; "extensible by future Domain Adapter ADRs") | Read under D13: "future Native Engine Implementation ADR (ADR/0028)" |
| [ADR/0006 L404](0006-object-type-requirement.md#L404) | "full adapter contract awaits Domain Adapter ADR" (DOORS / Polarion / ReqIF) | "full Data Adapter contract awaits ADR/0028" (these are Data Adapters per D12) |
| [ADR/0007 L139, L149, L294, L370](0007-object-type-assembly.md) | `stable_engine_object_id: "Datum001"` "resolves inside the FreeCAD doc"; "Domain Adapter ADR" | Same as ADR/0005: illustrative-only retrofit + D18 shell preserved |
| [ADR/0009 L267](0009-relationship-type-satisfies.md#L267) | "Domain Adapter implementation is Layer 5 work per S3 commitment 15" | "Native Engine implementation is Layer 5 work per S3 commitment 15 (commitment also retrofitted below)" |
| [ADR/0010 L22, L38, L48, L54, L142, L251](0010-relationship-type-composed-of.md) | FreeCAD-influenced quaternion convention; "Domain Adapters that author or read assembly placements" | Technical interop choice STAYS valid (FreeCAD convention is good for STEP/glTF/OCCT compat per D14); "Domain Adapters" → "Native Engines" |
| [ADR/0011 L22, L426](0011-relationship-type-mated-to.md) | Mate-type taxonomy from "SolidWorks / Creo / Onshape / FreeCAD"; "AP242 / STEP round-trip ... Domain Adapter implementation is Layer 5 work" | Research material STAYS valid; AP242 round-trip becomes Native Engine import/export scope per D14 |
| [ADR/0014 L169](0014-object-type-component.md#L169) | Component `geometry_ref` `derived_export` only; "does not author canonical kernel geometry" | Compatible with new posture (Component is a Binding Object; Part authors via Native Engine; Component imports) |
| [ADR/0015 L65, L365](0015-relationship-type-parameter-expression.md) | "Different Domain Engines... native expression languages"; "`derived_geometry_from` awaits FreeCAD Domain Adapter scope" | "Different Native Engines... native expression languages"; "`derived_geometry_from` awaits AIADRA-native mechanical engine scope (Ring 3 / ADR/0028)" |
| [ADR/0016 L436](0016-object-type-software-module.md#L436) | "Awaits KiCad Domain Engine ADR" | "Awaits AIADRA-native electrical engine scope" |
| [ADR/0017 L215](0017-object-type-drawing.md#L215) | "Domain Adapter / Domain Engine concern (FreeCAD, custom drafting tools)" | "Native Engine concern (`aiadra-mechanical` for drawing generation; custom drafting tools as Data Adapters)" |
| [ADR/0018 L14, L357, L365](0018-relationship-type-depicts.md) | "`derived_geometry_from` awaits FreeCAD Domain Adapter scope" | Same uniform retrofit as ADR/0015 |
| [ADR/0019 L200, L257](0019-object-type-evidence-artifact.md) | "Domain Adapter / Domain Engine concerns"; worked example "FreeCAD FEM + CalculiX" in `collection_context` | "Data Adapter concerns" (DV is Data Adapter per D12); worked example becomes illustrative ("e.g., FEM solver output") |
| [ADR/0020 L245](0020-object-type-test-procedure.md#L245) | "all Domain Adapter / Domain Engine concerns" | "all Data Adapter concerns" (per D12 — DV is Data Adapter, not Native Engine) |
| [ADR/0021 L16, L140, L441](0021-relationship-types-v-and-v.md) | "`derived_geometry_from` awaits FreeCAD Domain Adapter scope" | Same uniform retrofit |
| [ADR/0022 L25, L565, L582](0022-test-execution-model.md) | "`derived_geometry_from` awaits FreeCAD Domain Adapter scope" | Same uniform retrofit |
| [ADR/0023 L27, L68, L78-80, L182, L300](0023-wedge-spike-scope-and-runtime.md) | "Domain Engine" in deferrals + non-scope language; §A4 alternative rejected "Domain-Engine-touched Wedge — FreeCAD Adapter sketch" | "Native Engine" in deferrals; Wedge-003-FreeCAD-Adapter scope SUPERSEDED — Wedge-003 takes the D17-revised shape (AIADRA-native authoring loop gated on Part authoring SCN) |
| [ADR/0024 L382](0024-wedge-002-spike-scope.md#L382) | "Domain Engine (FreeCAD Adapter) — Ring 3 / Ring 4; out of Wedge spike series" | Same as ADR/0023: Wedge-003+ takes D17 shape |
| [ADR/0025 L29, L74, L81, L301](0025-aiadra-core-runtime-scope.md) | "Layer 5 Domain Adapters" / "Domain Adapter integrations" as future extension points | Read under D13; D11 confirms Native Engines live as ecosystem packages — matches ADR/0025 §2's `pip install aiadra-core[vault-s3]` extras pattern |
| [ADR/0026 L98, L244, L294-296](0026-ai-action-protocol-scope.md) | "Ring 3 Domain Adapter contract's ability to expose kernel-level operations" | Read under D13; the `propose(kind="<domain-specific-op>", ...)` futureproofing carries through verbatim — Native Engine ops slot in via the same mechanism |
| [TruthModelSchema.md L335](../TruthModelSchema.md#L335) | "Layer 5 (Domain Adapter). Domain Engines must distinguish editing a working sidecar from viewing a frozen Revision" | "Layer 5 (Native Engine + Data Adapter). Native Engines must distinguish editing a working sidecar from viewing a frozen Revision" |
| [TruthModelSchema.md §S3 commitment 15](../TruthModelSchema.md) | "AP242 external element references round-trip via Layer 5 Domain Adapters, where AP242 can represent" | "AP242 external element references round-trip via Layer 5 Native Engine import/export per D14, where AP242 can represent" |
| [TruthModelSchema.md §S3 commitment 16](../TruthModelSchema.md) | "Domain Adapter graceful-degradation rule, with a release-time threshold" | "Native Engine graceful-degradation rule, with a release-time threshold" |

### TruthModelSchema research-material references — NOT retrofitted

| Location | Reference | Why keep |
|---|---|---|
| [TruthModelSchema.md L527](../TruthModelSchema.md#L527) | "research surveyed how production CAD systems (SolidWorks / Creo / NX / CATIA / FreeCAD / Onshape) handle topological identity" | EXACTLY the "study + inspire" research material the new posture endorses |
| [TruthModelSchema.md L589](../TruthModelSchema.md#L589) | "FreeCAD 1.0 / RealThunder-style encoded names at the resolver layer" | Technical inspiration adopted into AIADRA-native schema; what D4 names as "every trick FreeCAD resolved through friction" |

ADR/0023 + ADR/0024 are NOT content-superseded — their Wedge-001 / Wedge-002 scope ran clean and the friction logs remain load-bearing for production runtime. Only the *aspirational Wedge-003-with-FreeCAD-Adapter* paragraph from ADR/0023 §A4 is superseded by D17's reshape.

## Research register — mechanical domain (D4 / Q8 absorption)

Brief register of FreeCAD / Solvespace / OpenSCAD / Onshape / KiCad mechanical sub-problems worth studying as research material before implementing the AIADRA-native mechanical engine. Not a roadmap; not a commitment to study any specific one. ADR/0028 + per-engine implementation arcs grow their own concrete research lists.

- **Parametric graph implementation** — feature dependency tracking; topological-sort recomputation; cycle detection; invalidation propagation. FreeCAD's `App.Document` graph; Onshape's parametric model (public docs); RealThunder/LinkStage's topological-naming improvements over FreeCAD's master branch.
- **Sketch solver integration** — constraint propagation; under-/over-constrained detection; degenerate-case handling. FreeCAD's PlanetCNC integration; Solvespace's solver (used standalone and embeddable).
- **Topological identity persistence** — feature recomputation invariant id stability. Bidarra & Bronsvoort persistent naming; FreeCAD's encoded names; RealThunder's "Toponaming" improvements; OCCT's BRep persistent id work.
- **Feature recomputation invalidation** — incremental rebuild vs full rebuild; sketch-driven cascades. FreeCAD's recompute strategy; OpenSCAD's text-driven recompute model (instructive even if different paradigm).
- **History graph editing** — feature insertion/reorder; mid-history edits; rollback semantics. FreeCAD's history list; Onshape's feature list (public docs).
- **Multi-body operations + assembly mating constraint solver** — body-pair operations; assembly placement constraint propagation; mate-type taxonomy from [ADR/0011](0011-relationship-type-mated-to.md) (already research-material-sourced).

Plus ADR/0017 + ADR/0019 + ADR/0020 + ADR/0022 already cite specific Attachment-bearing Object Type research material (Drawing rendering pipelines; evidence collection; test procedure authoring; test execution recording) — those registers stay as documented in their respective ADRs.

## Consequences

- **Multi-document amendment co-landing.** Manifesto v0.3 → v0.4; ArchitectureOverview v0.1 → v0.2; Glossary v0.24 → v0.25; OpenQuestions OQ-0004 + OQ-0005 + OQ-0006 status updates. All applied in arc 20260531-11 round 2 alongside this ADR.
- **No schema bundle bump.** Bundle stays v0.27.0. D18 wire-name preservation means zero schema bytes change. Concrete schema additions (the `part_changed` event per D17 pre-condition) land in the future Part authoring SCN (working ADR/0029; bundle v0.27.0 → v0.28.0 MINOR additive).
- **No `aiadra-core` version bump.** aiadra-core stays 0.9.0 — no code changes in this arc.
- **OQ-0004 + OQ-0005 archived** as `superseded-by-adr/0027`. Historical question text preserved for archaeology.
- **OQ-0006 reframed**: per-domain implementation shape pivots from "wrap external tools" to "AIADRA-native engines using third-party libraries." Cross-domain sequencing still `deferred-to-ring-5`.
- **`derived_geometry_from` blocker citation retrofitted** uniformly across ADRs 0015, 0018, 0021, 0022, 0025, 0026: was "awaits FreeCAD Domain Adapter scope per Manifesto P12"; now reads "awaits AIADRA-native mechanical engine scope (Ring 3 / ADR/0028)" per D13.
- **ADR/0005 §9 adapter shell preserved** with wire names verbatim per D18. The shell's role as the Native Engine / Data Adapter dispatch contract is canonicalized by ADR/0027; concrete handler-registration mechanism deferred to ADR/0028.
- **Sequencing for the post-Ring-2 era**: (a) Ring 3 scope ADR/0028 → (b) Part authoring SCN ADR/0029 (`part_changed` event) → (c) Wedge-003 scope ADR → (d) `aiadra-mechanical` ecosystem-package implementation. Per-engine research arcs (FreeCAD / Solvespace / OpenSCAD / KiCad / Onshape) can run in parallel and feed (c) + (d). Estimated horizon: multi-year. Bounded by OCCT-as-library (no kernel replication).
- **AIADRA Core hosts nothing preserved** (Manifesto P11) — Native Engines run locally as part of the developer's Workspace, packaged as ecosystem extras (per D11). No hosted Native Engine service. No cross-Workspace coordination.
- **BYO-AI posture preserved** ([ADR/0026 §0](0026-ai-action-protocol-scope.md)) — AIAD framing characterizes the platform; BYO-AI characterizes which agent calls Ring 2. The two compose: a BYO-AI agent calls AIADRA's Ring 2 contracts to author content via AIADRA-native engines.
- **P2 + P5 boundary preserved** — Native Engines are part of the deterministic core (OCCT computes deterministically; Native Engines compute on demand; humans approve via P5 gate). See D16.
- **New Coherence Checklist item** (earned via Codex1 B1 absorption — the ADR/0005 adapter-shell near-miss):

  > **Native engine boundary**: Does this proposal wrap a third-party application, or does it use an AIADRA Native Engine with third-party libraries only? If the former, push back hard. ([ADR/0027](0027-aiad-positioning-and-native-engine-posture.md); earned via Codex1 B1 absorption arc 20260531-11.)

  Lands in SystemState §3 at arc close. Proactively-watched as Ring 3 / mechanical-engine / electrical-engine arcs approach.

- **No new Pattern Catalogue row.** Meta-positioning ADR; no new schema patterns introduced.
- **D14 file format interop register** documents the load-bearing cost honestly. Codex1 N1 wording softened ("named parameters where present" is best-effort/importer-specific, not v1 guarantee). Concrete priority + sequencing deferred to ADR/0028.
- **D15 license posture** documents OCCT LGPL 2.1 dynamic-linking + flags AIADRA Core license review as required before mechanical engine package lands. No premature license commitment.

## Alternatives rejected

- **(i) Continue with "modify FreeCAD" non-goal language.** Rejected: structural impedance with FreeCAD-the-application is not addressable by modification (see §2).
- **(ii) Fork FreeCAD as "AIADRA FreeCAD."** Rejected: per [OQ-0004](../OpenQuestions.md#oq-0004) cautionary tale (RealThunder/LinkStage); fights upstream pace forever; doesn't actually solve the truth-ownership inversion or event-sourced-vs-state-based mismatch.
- **(iii) Wrap FreeCAD as a Domain Adapter (Ring 3 original framing).** Rejected: bidirectional sync between two sources of truth is dishonest; AI-targeted surfaces don't exist in FreeCAD; perpetually-translating layer is a maintenance burden indistinguishable from the fork case.
- **(iv) Replicate OCCT from scratch.** Rejected: 1.5M+ LOC of production geometric kernel; decades of work; not in AIADRA's scope. OCCT is a library AIADRA depends on.
- **(v) Single ADR covering AIAD positioning + Ring 3 mechanical-engine scope + Wedge-003 scope together.** Rejected: too many concerns; each deserves its own ADR. ADR/0027 (positioning + posture only) → ADR/0028 (Ring 3 scope) → ADR/0029 (Part authoring SCN) → Wedge-003 scope ADR.
- **(vi) Edit each downstream ADR in place to swap "Domain Adapter" / "Domain Engine" wording.** Rejected: high-churn (29+ locations); dilutes ADR/0027's load-bearing role. D13 uniform retrofit clause is the cleaner mechanism. (Codex1 B7 self-test acknowledged this is an unconventional precedent; the retrofit is specifically scoped to terminology + structural-shell preservation + `derived_geometry_from` blocker citation; does NOT change schema bytes or decision semantics.)
- **(vii) Mark ADR/0005 §9 adapter shell as future SCN migration target.** Rejected: D18 path-1 (preserve wire names + reframe semantic role) achieves the same outcome with zero schema churn and zero migration debt.

## References

- [Manifesto.md](../Manifesto.md) v0.4 (amended by this ADR)
- [ArchitectureOverview.md](../ArchitectureOverview.md) v0.2 (amended by this ADR)
- [Glossary.md](../Glossary.md) v0.25 (amended by this ADR)
- [OpenQuestions.md](../OpenQuestions.md) OQ-0004 + OQ-0005 + OQ-0006 (status-updated by this ADR)
- [ADR/0001](0001-storage-substrate.md) (D13 retrofit target)
- [ADR/0005](0005-object-type-part.md) §7 + §9 + §229 (D13 + D18 retrofit targets)
- [ADR/0006](0006-object-type-requirement.md) L404 (D13 retrofit target)
- [ADR/0007](0007-object-type-assembly.md) §139, §149, §294, §370 (D13 retrofit targets)
- [ADR/0009](0009-relationship-type-satisfies.md) L267 (D13 retrofit target)
- [ADR/0010](0010-relationship-type-composed-of.md) (D13 retrofit target; FreeCAD quaternion convention research material)
- [ADR/0011](0011-relationship-type-mated-to.md) §"AP242 / STEP round-trip" (D14 file-format scope register)
- [ADR/0014](0014-object-type-component.md) L169 (compatibility note)
- [ADR/0015 / 0018 / 0021 / 0022](0015-relationship-type-parameter-expression.md) (`derived_geometry_from` uniform retrofit)
- [ADR/0016](0016-object-type-software-module.md) L436 (D13 retrofit target)
- [ADR/0017](0017-object-type-drawing.md) L215 (D13 retrofit target)
- [ADR/0019](0019-object-type-evidence-artifact.md) L200, L257 (D13 retrofit targets)
- [ADR/0020](0020-object-type-test-procedure.md) L245 (D13 retrofit target)
- [ADR/0023](0023-wedge-spike-scope-and-runtime.md) §A4 + L27 / L68 / L182 / L300 (Wedge-003-FreeCAD-Adapter scope superseded by D17)
- [ADR/0024](0024-wedge-002-spike-scope.md) L382 (D13 retrofit target)
- [ADR/0025](0025-aiadra-core-runtime-scope.md) §10 + ecosystem-package extras pattern (D11 precedent)
- [ADR/0026](0026-ai-action-protocol-scope.md) §0 BYO-AI (positioning precedent) + §6 Tier-3 RPC ecosystem-package precedent (D11 precedent) + §10 item 3 kernel-level futureproofing (Decision §2 intentional openness)
- [TruthModelSchema.md L335 + §S3 commitment 15 + §S3 commitment 16](../TruthModelSchema.md) (D13 retrofit targets); L527 + L589 (research-material; NOT retrofitted)
- [OQ-0007](../OpenQuestions.md#oq-0007) Wedge scope adequacy (resolved by Wedge-001; D17 builds on the Wedge series precedent)
- Petre direct framing (arc 20260531-11 conversation): "This is not another CAD system. This is an AIAD system. We will use the OpenCascade kernel AND every trick FreeCAD resolved through friction. However, we will re-write the CAD layer to fit our new philosophy."
