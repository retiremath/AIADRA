# ADR/0044 — The AIADRA Sketcher Paradigm

- **Status:** ACCEPTED (arc 20260715-2; Codex3 signoff)
- **Date:** 2026-07-15
- **Arc:** 20260715-2 (SK-A)
- **Relates to:** ADR/0027 (Native Engine posture), ADR/0029 (Part authoring SCN), ADR/0033 D1 (benchmark, never cloned), ADR/0034 (licensing & dependency policy), ADR/0035 (display identity, `skp_` anchors), ADR/0037 (modeling-paradigm benchmark + KB), ADR/0038 (persistent reference identity), ADR/0039 (the AIAD authoring model)

## Context

AIADRA's sketch today is a frozen coordinate literal: line-segment contours, rectangles, circles-as-holes, one outer profile, no dimensions, no constraints, no references. The established parametric-CAD benchmark's sketcher is the opposite pole and one of the most valuable toolboxes in any parametric CAD system: rough drawing, automatic constraint/dimension completion (weak dimensions), asserted intent (strong dimensions, explicit constraints), a deterministic 2D variational solver, references projected from existing 3D geometry, construction geometry, and a rich editing toolset. Petre has pinned the full benchmark sketcher as the strand's North Star, with OCCT as the kernel and FreeCAD as implementation research.

Two hard facts shape everything: **OCCT ships no 2D variational constraint solver**, and **determinism is a Truth requirement for AIADRA** — the same recipe must regenerate identical geometry everywhere, or the result is not data the platform can trust.

This ADR pins the paradigm. It ships no code; the strand roadmap (§Decision 9) realizes it across gated arcs.

## Decision

### D1 — A sketch is a CONSTRAINED MODEL; solved coordinates are DERIVED

A v2 sketch consists of four cooperating, id-addressed fact sets in the sketch feature's adapter payload (engine-internal, adapter-versioned):

- **Entities** — the canonical geometry the solver sees.
- **Constraints** — typed relations between entities/sub-entities.
- **Dimensions** — structural dimension records whose driving numeric values are first-class `feature.parameters[]` entries.
- **References** — projections/uses of existing 3D geometry (v1: same-Part only; cross-Part is Binding-Object territory and explicitly out of the strand).

The solver's OUTPUT (solved coordinates) is derived data — cacheable, regenerable, never Truth. This is the platform's recipe-vs-geometry split applied inside the sketch.

**Coexistence:** the v2 constrained payload is an EXPLICIT new, incompatible adapter series. v1 frozen sketches remain valid forever and never migrate; decoders are per-series.

### D2 — The entity ontology: solver entities ≠ tools ≠ modes

- **Canonical solver entities:** point, line, circle, arc, ellipse, conic, spline (control representation pinned in SK-C design). Each carries an engine-minted id extending the `skp_` discipline, plus a **closed per-type sub-entity endpoint vocabulary** (`.start`, `.end`, `.center`, `.major`, …) so constraints address endpoints stably.
- **Macros** (tools that CREATE entities+constraints and leave NO macro-record in Truth): rectangle (four lines + coincident corners + H/V), offset, import. The recipe stays solver-canonical; tool ergonomics live in the UX.
- **Modes:** `construction: true` on any entity (solver-visible, profile-invisible); centerlines are construction lines; sketch-local coordinate systems/axes are construction reference entities.

### D3 — Dimension axes: strength, role, and provenance are three ORTHOGONAL things

- **`strength: weak | strong`** — behavioral: may the system adjust/remove this to satisfy the scheme? Weak = the system's completion; strong = asserted intent. Promotion weak→strong is a state change recorded as an event.
- **`role: driving | reference`** — a driving dimension constrains; a **reference dimension is a parameter-free DERIVED MEASUREMENT** (it has no `parameters[]` entry and is never editable — `adjust_feature_parameter` cannot address it by construction).
- **Provenance** — the fact's ORIGIN, never rewritten; the event log is the HISTORY (the terms are reserved exactly so: `origin` = fact provenance, `history` = events). A human asserting an AI-proposed dimension changes `strength` — an event in the history — while the unchanged value's origin stays what it was.

**Per-dimension provenance (the named SK-C1 schema extension):** today's `feature.parameters[]` items carry no provenance, and feature-level provenance cannot represent dimensions added by different actors within one sketch. SK-C1 lands an **additive shared bundle/schema extension: per-feature-parameter fact provenance**. Structural dimension records reference their stable parameter ids; the extension is additive (existing parameters remain valid with feature-level provenance as the default reading).

### D4 — The two-layer determinism commit invariant

A committed sketch recipe MUST regenerate identically, everywhere, forever. Two layers make that true by construction:

1. **Canonical weak completion** closes every CONTINUOUS degree of freedom: at commit, the strong-intent subset (which may be underconstrained on its own) is completed by canonical weak dimensions/constraints to a fully-determined system. "Underconstrained" is a description of the strong subset, never of what commits.
2. **A canonical branch seed/selector** chooses among DISCRETE nonlinear solution branches (mirror, intersection-side, tangency-side ambiguities) and is persisted with the recipe — unless SK-B evidences a closed deterministic replacement rule, in which case the ADR is amended.

The determinism envelope pinned for SK-B to prove: constraint ordering, branch selection, convergence tolerance, coordinate normalization, platform floating-point stability, and a persisted **solver contract version** (the semantic contract — distinct from the implementation build; an upgrade that would move committed geometry is a detectable, versioned event, never silent drift).

**"Identical" is defined:** regeneration reproduces the SAME branch/classification and normalized geometry within the solver contract's tolerance — bit-for-bit identity is claimed only where SK-B proves it. Tolerance is part of the solver contract version (D4's envelope), so "within tolerance" is itself versioned, never ambient.

**Diagnostics are typed and distinct:** solve-failure vs DoF-state (under/well/over-constrained, on the strong subset) are separate validation outcomes, and the failure taxonomy is enumerated — **redundant** (a constraint adds no information), **conflicting** (unsatisfiable set), **non-convergent** (the solver failed within contract bounds), **out-of-domain** (a configuration the contract does not cover). UI and AI lanes consume them differently.

### D5 — The solver decision is made ON EVIDENCE in SK-B (one decision arc, two gates, one baseline)

- **Candidate: PlaneGCS** (FreeCAD's solver) — LGPL-2.1+, policy-compatible as a LIBRARY (ADR/0034; the OCCT precedent), but it is embedded source in FreeCAD's tree, an extraction candidate, NOT a proven standalone library.
- **Gate 1 (capability):** extract/build standalone; drive the SK-C1 witness (the exact vertical-slice entity+constraint set); prove the D4 envelope — or fail it honestly.
- **Gate 2 (artifact compliance):** the ADR/0034 per-distribution-form treatment; attorney-list items appended as needed.
- **Baseline:** a bounded own deterministic solver over the v1 constraint set, spiked far enough to price honestly.
- **libslvs (SolveSpace) is DENIED**: GPLv3 — a GPL dependency destroys the ADR/0034 commercial-license lever categorically. Named here so it cannot resurface.
- The decision (PlaneGCS / own / hybrid) lands as an amendment to this ADR at SK-B close.

**Amendment A1 (arc 20260715-3 close, 2026-07-16) — THE DECISION: select the patched PlaneGCS extraction.** The v2 sketch solver is PlaneGCS extracted from FreeCAD commit `8d0078866c6fcefed3395d5d9fa36c683ea858ad` (subtree `src/Mod/Sketcher/App/planegcs`, byte-identical sources) plus **two AIADRA determinism patches** (published, upstream-contributable; they remove allocation-address ordering from solver-critical traversals — the causal seam, `SubSystem::redirectParams` last-writer-wins over reduction-aliased parameter slots, was A/B-proven), behind the AIADRA-owned `aiadra_solver` binding as a **separate replaceable LGPL DLL**. Selection evidence (arc 20260715-3): the `skb-1` executable 14-case gate with full signature coverage; Gate 1 passed by BOTH candidates (capability + exact diagnostics + literal persisted-replay P2/P4 + 100+10 byte-identical repeatability); Gate 2 package audit (independently rebuildable corresponding source, file-level SPDX, complete license set, locked third-party acquisition, retained rebuild→swap→retest identity chain). The pure-Python own baseline is retained permanently as the corpus reference candidate. **Measured paradigm consequence:** `coincident` + supporting-curve `tangent` at a joined tangent joint is Jacobian-singular — **endpoint tangency (`tangent_at`) joins the D2 public constraint vocabulary** (SK-C1). **The selection carries three conditions on its face:** `conditional pending clean-machine packaged-rebuild evidence` (release-gated by Petre's arbitration; the proven one-command test kit is staged in the arc), `conditional pending second-platform evidence` (Linux corpus run; D4's full envelope is claimed only for the evidenced Windows platform until then), and attorney review before any distribution (ADR/0034 list).

### D6 — The AI-native posture (beyond the benchmark's assistance)

The operator sketches roughly or asks in words; **AI proposes the constraint/dimension scheme**; the **deterministic solver validates solvability** (DoF accounting as typed validation outcomes); the **human asserts** (promotes to strong / approves). Auto-dimensioning = the system's canonical weak completion, provenance-tagged. Core ships zero AI (ADR/0026 §0 BYO-AI holds); the AI lane consumes the same Ring-2 contracts as the manual sketcher (ADR/0039's loop).

### D7 — Identity and the write path extend existing law

Engine-owned identity throughout: entities, sub-entity endpoints, constraints, and dimension records are engine-minted (the S2 staged-identity handshake extends — the renderer never predicts ids). References use ADR/0038 persistent-reference machinery (display ids are input vocabulary only). Display anchoring extends ADR/0035's `skp_` scheme.

### D8 — Hard lines

The benchmark is followed, never cloned (ADR/0033 D1, ADR/0037 D1); PTC materials stay behind the D3 research firewall; public language is original. FreeCAD: architecture = open design research; its CODE enters only through the license's own front door — a **properly-licensed library dependency, including licensed extraction/forking of PlaneGCS under its LGPL terms with attribution and compliance per ADR/0034** (that IS licensed use, not copying). What stays prohibited: unlicensed copying, license-incompatible embedding, and wrapping FreeCAD-the-application (ADR/0027). Import provenance: imported geometry (sketch/DXF/DWG) carries import-origin facts. DWG licensing is an SK-H research item.

### D9 — The strand roadmap (each arc Codex-gated, independently shippable)

SK-A this ADR → **SK-B** the solver decision arc (D5) → **SK-C0** frozen-palette growth (arc, circle-as-outer-profile, construction flags on the CURRENT v1 model — durable, may run parallel to SK-B) → **SK-C1** the constrained vertical slice (line/circle/arc + the bounded constraint set + weak/strong dims + the per-parameter provenance extension, end-to-end on one walkable flow) → **SK-C2** robustness + diagnostics → **SK-D** sketcher UX v1 (draw-rough + live solve, constraint glyphs, dimension edit-in-place, construction toggle, orient-into-plane, pan/zoom, snap-to-geometry) → **SK-E** references (same-Part) → **SK-F** editing tools (trim, divide, extend, mirror, offset) → **SK-G** the palette completed (ellipse, conic, spline, points, centerlines, sketch csys) → **SK-H** import (sketch, DXF; DWG pending research).

## Consequences

- The Truth model gains its first constraint-solving surface; determinism obligations extend to an iterative numeric domain (D4 is the contract that keeps that safe).
- A new incompatible adapter series will coexist with v1 permanently; every decoder is per-series (the R-arc guard discipline generalizes).
- The `feature.parameters[]` schema gains additive per-parameter provenance in SK-C1 (a shared-bundle extension, named here per Codex2 B2).
- SK-B may add attorney-review items (PlaneGCS artifact compliance) to ADR/0034's list.
- The AI scheme-proposal lane gets its substrate; no core AI machinery is added.

## Alternatives considered

- **Growing the frozen-coordinate model indefinitely** (more primitives, no constraints): rejected — it builds UX debt against a different final model; retained only as SK-C0's bounded, durable palette step.
- **libslvs**: rejected on license (D5).
- **Solver-first without the paradigm ADR**: rejected — the solver choice depends on the determinism contract (D4) and the ontology (D2), not vice versa.

## Amendment A2 (arc 20260717-2, Gate F2a; Codex22 signoff of the design) — the production solver foundation and the v2 series contract

*Version impact: adapter series 0.2.x opens (first writer `0.2.0`); no v1 record or hash changes; the shared schema gains the additive D3 per-parameter provenance extension; `aiadra-solver/` becomes the production artifact home.*

**A2.1 — The production artifact home and boundary.** The selected solver artifact (A1) lives at top-level `aiadra-solver/` — the ORGANIZATIONAL expression of an ARTIFACT-level seam: the loadable `planegcs.dll`, its corresponding source + the two determinism patches, notices/license texts, the locked rebuild material (vendored Eigen/pybind11 as exact manifested bytes; Boost by locked acquisition), and the replacement procedure (`src/BUILD.md` + the frozen `testkit/run_gate2.py`) together establish the seam. `aiadra-mechanical` never compiles it — it LOADS the replaceable binary behind the AIADRA-owned typed API (`aiadra_mechanical.solver`). The built DLL/PYD pair does not enter git; binary distribution in any form first requires the ADR/0034 artifact-compliance inventory entry and the A1 attorney gate. Binary digests are provenance evidence, never runtime compatibility authority.

**A2.2 — THREE immutable contract ids.** Every v2 sketch record persists three canonical ids, each an immutable frozen authority whose ANY semantic change is a NEW id (a detectable versioned event per D4, never an edit):

- `solver_contract: "skb-c0"` — the numeric contract (residual blocks + per-block tolerance, rank tolerance, normalization, update-step semantics, default iteration cap, the skb-canon-1 serializer);
- `weak_policy: "skb-0"` — the canonical weak-completion enumeration;
- `branch_policy: "skb-b0"` — the branch-identity contract (A2.6): the closed local signature table, the total whole-fact-graph admission predicate, the length-guard constants, the id/reference/uniqueness and canonical array-order rules, and the machine-checkable coverage catalog. A policy whose catalog derives a NON-empty witness set for any admitted graph MUST additionally freeze its witness-kind schemas (canonical normalized measures with total, SCALE-AWARE domains) and its degeneracy threshold, each with executable golden vectors proven against that domain; a policy whose catalog is EMPTY everywhere — `skb-b0` — normatively contains NONE of those, because an empty catalog freezes no measure (Codex24 B1). Witness semantics are NOT part of `skb-c0` and are never silently folded into it.

Each id has exactly ONE durable tracked normative source (A2.10); production code implements it and parity tests enforce the correspondence — no two independently editable authorities.

**A2.3 — The DLL handshake and origin protocol.** The replaceable DLL itself exports `aiadra_planegcs_handshake()` returning `aiadra-planegcs-abi:<N>;solver-contract:<id>` — a conforming replacement declares truthfully what it executes (a build without the determinism patches does not satisfy `skb-c0` and must not claim it). The loader protocol is fail-closed and typed: explicit artifact-location resolution (never `PATH`/process state), interpreter-ABI precheck, import from the explicit path only, binding-identity verification, DLL handshake verification, and ORIGIN verification — the loaded module's reported absolute path (`GetModuleFileNameW` on the handshake `HMODULE`) must be the selected artifact file, canonically compared; a conforming same-named module from another origin is refused.

**A2.4 — The v2 series is adapter 0.2.x; the first writer stamps `"0.2.0"`.** Constrained sketches (D1) are an explicit new, incompatible adapter series; records carry the CONCRETE version, never a wildcard. v1 0.1.x records remain first-class and decodable forever; nothing migrates. Versioning splits per RECORD FAMILY: the sketch family admits {0.1.x, 0.2.x}; every other family admits only its defined series; a 0.2.x record for any feature type without defined 0.2 semantics refuses in the handler AND the evaluator AND the Studio decoder. Mixed v1/v2 Parts are supported. `sketch_model: 2` is carried redundantly inside the payload — the series is the compatibility authority; the payload discriminator is what participates in canonical identity (A2.7).

**A2.5 — The persisted v2 sketch contract.** A v2 sketch record persists, id-addressed throughout: **entities** (with AUTHORED nominal parameters — A2.6), **constraints**, **dimensions** (driving values as `feature.parameters[]` entries with per-parameter fact provenance via the D3 additive extension), **references**, the **weak completion** (the skb-0 `fix_param` records verbatim — full records, validated field-by-field including magnitude, deeply immutable), the **branch-selector witness set** (A2.6, each witness carrying its explicit nested `origin`), and the three contract ids + `sketch_model: 2`. **Solved coordinates are NEVER persisted** — not as a field, not renamed, not as a seed. Implementation build/compiler/platform/binary digests are evidence/telemetry, never payload.

**A2.6 — Branch identity under `branch_policy`: authored nominals seed; the witness set is a BRANCH FIREWALL; disagreement refuses.**

1. **The regeneration seed is the AUTHORED nominal geometry** — input intent written ONLY by authoring gestures (drawing, dragging, an explicit human-accepted rebaseline), each an event with its actor. The system never writes solved output into nominals. Nominal authorship provenance = the feature-level provenance plus the event history; dimension values additionally carry the D3 per-parameter fact provenance.
2. **Witness facts are typed, id-addressed, deeply immutable discrete records** minted at commit from the accepted solution: `{id, kind, of: [ordered operands], sign: +1|-1, origin: {category: "computed_result", policy: <branch_policy>, solver_contract: <solver_contract>}}` — acceptance lives in the actor-carrying commit event, exactly as for weak facts. A witness carries no coordinates. **The mechanism is precisely this: nominals seed the NUMERICAL solve; the committed witnesses VALIDATE the converged branch after the fact.** The solver does not consume witnesses; they are a firewall, not active selection.
3. **Admission is graph-level, or nothing.** A branch policy admits complete fact GRAPHS, never isolated signatures — per-kind branch annotations cannot prove a composed system single-rooted (the governing rule: *a list of safe equations is not yet a safe system*). A policy's normative source carries a closed local signature table AND a total machine-checkable whole-graph predicate; every admitted graph shape carries either a single-root proof or required witness coverage; every other graph refuses as typed out-of-domain at all five enforcement surfaces (encode, decode, handler, evaluator, Studio decoder). Under `skb-b0` the admitted universe is exactly the three reference-sketch shapes G0/G1/G2 (fixed construction origin; plus directed construction axes with signed non-collapse guards and their exact skb-0 weak completions), each proven single-root — deriving the exact EMPTY witness set.
4. **The catalog derives an EXACT set; zero is never assigned a sign.** Catalog evaluation is a total function from the admitted fact graph to the exact canonically-ordered witness-descriptor set; decode and commit reject missing, duplicate, AND extra witnesses. Minting REFUSES an undefined, non-finite, or within-ε measure (commit refuses a covered configuration it cannot witness unambiguously). Regeneration distinguishes two typed refusals — **`branch-mismatch`** (defined measure, opposite sign) and **`branch-degenerate`** (undefined measure or |measure| ≤ ε) — both joining the D4 diagnostic taxonomy; neither ever silently re-solves, re-seeds, remints, or re-picks.
5. **Widening is a new policy id.** Catalog, vocabulary, or admission changes are Codex-gated and require a NEW branch-policy id; committed records remain governed forever by the id they stamp.

**A2.7 — v2 identity.** The canonical recipe bytes of a v2 sketch record cover the full constrained payload of A2.5 — including `sketch_model: 2`, ALL THREE contract ids, the weak facts, and the witness set. `adapter_schema_version` remains excluded from canonical bytes (the standing rule; the payload carries every semantic discriminator). v1 recipe hashes remain byte-identical. Recipe-identity regressions are mandatory before the first v2 Truth commit: v2 identity moves with every semantic fact and contract id and does not move with solved output or telemetry.

**A2.8 — Typed fact shapes before persistence.** Weak-completion and witness facts are DEEPLY immutable typed records — including nested operand/reference lists and `origin` blocks — schema-validated at encode and decode; malformed records refuse loudly. Encode AND decode cross-check every nested `origin` against the record's top-level ids: weak-fact `origin.policy`/`origin.solver_contract` must equal `weak_policy`/`solver_contract`; witness `origin.policy`/`origin.solver_contract` must equal `branch_policy`/`solver_contract`; any mismatch refuses — a contradiction never becomes identity-bearing.

**A2.9 — The two lifecycles are disjoint by construction.**

1. **The authoring transaction** (draw / drag / driving-dimension edit / constraint change / explicit rebaseline): solve a preview from the working nominals → compute or SUPERSEDE the complete canonical weak completion → mint the COMPLETE witness set under the branch policy → validate coverage and non-degeneracy → obtain human/AI acceptance → **atomically commit** nominals + strong facts + weak facts + witnesses + the three contract ids. No committed state ever holds a stale weak fact, a stale witness, or a partial witness set.
2. **Regeneration (read)**: solve from committed nominals and facts only; validate EVERY committed witness; derive display geometry or refuse. Regeneration never remints witnesses, never rebases nominals, never changes weak completion, never writes recovered state. Recovery from any refusal is a NEW accepted authoring transaction, recorded as events.

**A2.10 — Normative sources.** `skb-c0` and `skb-0`: the frozen SK-B `SCHEMA.md` (§2b residual blocks, §4 completion, §5 serialization) as adopted at `aiadra-solver/testkit/corpus/SCHEMA.md`, implemented by the production contract module, digest/parity-tested. `skb-b0`: [`Docs/SolverContracts/skb-b0.md`](../SolverContracts/skb-b0.md) (immutable-by-id; a semantic change is a new file `skb-b1.md`), implemented by the production branch-policy module, parity-tested over its COMPLETE machine-readable content (constants, the local table, the whole graph predicate, the array-order rules). Golden-vector parity attaches to the first policy with a non-empty catalog; the draft measure schemas live in [`witness-kinds-draft.md`](../SolverContracts/witness-kinds-draft.md) (explicitly informative, production-unconsumed). One durable tracked source per id; production implements; tests enforce.
