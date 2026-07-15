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
