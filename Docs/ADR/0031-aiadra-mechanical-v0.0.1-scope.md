# ADR/0031 — `aiadra-mechanical` v0.0.1 scope

## Frontmatter

- **Status:** Accepted — 2026-06-02 (arc 20260601-6; two-round convergence Claude1 + Codex1 / Claude2, Codex1 conditional signoff on B1+B2 absorption with binding unchanged + public pip-installability not a v0.0.1 gate).
- **Operationalizes:** [ADR/0028 D14 step 5](0028-native-engine-implementation-contract.md) (`aiadra-mechanical` ecosystem-package implementation) + [ADR/0030 D15 step 5](0030-wedge-003-spike-scope.md) (`aiadra-mechanical` v0.0.1 scope ADR). Pins scope for the **first SHIPPABLE Native Engine** — the destination of the Wedge spike series.
- **Resolves:** [ADR/0028 D15 item 1](0028-native-engine-implementation-contract.md) — the OCCT Python binding choice deferred to "the `aiadra-mechanical` implementation arc" is committed here: **OCP (`cadquery-ocp`)**.
- **No schema bundle bump.** Bundle stays v0.28.0. This ADR is scope-only (matches [ADR/0023](0023-wedge-spike-scope-and-runtime.md) + [ADR/0024](0024-wedge-002-spike-scope.md) + [ADR/0030](0030-wedge-003-spike-scope.md) precedent); the implementation arc writes the package + tests + findings doc.
- **No `aiadra-core` version bump in this arc** (scope-only). The implementation arc may bump `aiadra-core` ONLY if real-OCCT integration surfaces friction requiring a core-side fix (per [ADR/0030](0030-wedge-003-spike-scope.md) consequences precedent — Wedge-001 produced no core change; Wedge-002's surfaced bundle changes in later SCN arcs).

## §0 — What this ADR does

The Wedge spike series proved the AIADRA loop end-to-end with a toy kernel ([ADR/0030](0030-wedge-003-spike-scope.md) / arc 20260601-3): real Product Truth, real `part_changed` events, real provenance discipline, real discovery + dispatch + binding-scan + cascade integrity + release — all against a deterministic synthetic kernel. `aiadra-mechanical` v0.0.1 is the **next, narrower proof**: that the SAME loop integrates a REAL OCCT kernel cleanly, packages cross-platform, and surfaces the [Wedge-003 FRICTION_LOG §10](../../spikes/wedge-003/FRICTION_LOG.md) OCCT-class friction **for real** rather than by omission.

The discipline that keeps this a *small* arc is restraint: **v0.0.1 changes the kernel and the packaging, and nothing else in the Truth-Model surface.** Same v0.28.0 schema, same events, same provenance, same namespaces — so the package is a pure consumer of the canonical bundle ([ADR/0028 D10](0028-native-engine-implementation-contract.md)).

This ADR pins WHAT v0.0.1 does, WHERE it lives, WHICH kernel + binding, and WHAT it explicitly does NOT cover. The implementation arc (next) writes the code, runs it across a cross-platform CI matrix, and populates the v0.0.1 FINDINGS doc.

**Three precedents preserved:**
- Ecosystem package lives OUTSIDE `aiadra-core` per [ADR/0027 D11](0027-aiad-positioning-and-native-engine-posture.md) + [Manifesto P11](../Manifesto.md).
- Clean-slate code per [ADR/0023 §4](0023-wedge-spike-scope-and-runtime.md) — production is re-written from the contract, NOT carried over from the throwaway spike.
- Scope-first ADR → impl-in-next-arc → findings doc → close cadence per [ADR/0024](0024-wedge-002-spike-scope.md) + [ADR/0030](0030-wedge-003-spike-scope.md).

## Decisions

### D1. Scope-only ADR; implementation in a separate next arc

Per the [ADR/0023](0023-wedge-spike-scope-and-runtime.md) + [ADR/0024](0024-wedge-002-spike-scope.md) + [ADR/0030](0030-wedge-003-spike-scope.md) precedent. ADR/0031 pins scope; the implementation arc writes:
- the top-level `aiadra-mechanical/` package per D3
- 4 Native Engine handlers driving real OCCT per D5
- `cadquery-ocp` kernel integration + recipe-hash identity per D4 + D6
- the cross-platform test surface per D12
- the v0.0.1 FINDINGS doc per D13

Codex review of scope before real-kernel code is written catches scope errors cheaply — and the stakes are higher than the spike: this is the first SHIPPABLE package, so a scope error becomes production baseline.

### D2. Package identity — `aiadra-mechanical`, engine_id `mechanical`, clean-slate

- **Distribution name** `aiadra-mechanical` (NOT `aiadra-mechanical-spike`). The spike deliberately kept this namespace clean by using `mechanical_spike` ([ADR/0030 D2](0030-wedge-003-spike-scope.md) Codex1 B2 absorption); spike + production coexist collision-free, and the spike may be uninstalled once v0.0.1 supersedes it.
- **`engine_id` = `mechanical`** — entry point `mechanical = "aiadra_mechanical:register"` in the `aiadra.native_engines` group per [ADR/0028 D2](0028-native-engine-implementation-contract.md). Operation kinds: `mechanical.add_sketch_feature` / `.add_extrude_feature` / `.adjust_feature_parameter` / `.remove_feature`.
- **Version 0.0.1** — `0.0.x` signals pre-stability; the API + op catalogue may change before `0.1.0`. Honors [ADR/0027 D17](0027-aiad-positioning-and-native-engine-posture.md) years-horizon framing.
- **Clean-slate code** per [ADR/0023 §4](0023-wedge-spike-scope-and-runtime.md) — v0.0.1 is re-written from the contract, NOT copied from `spikes/wedge-003/`. The spike's handler shapes, adapter_payload format, and test layout are *reference*, not carry-over, so the toy-kernel shortcuts never become the production baseline.

```toml
# aiadra-mechanical/pyproject.toml (sketch; exact cadquery-ocp version selected + frozen during impl smoke test per D11/N2)
[project]
name = "aiadra-mechanical"
version = "0.0.1"
dependencies = ["cadquery-ocp"]   # exact == pin frozen during the first smoke-test step
# aiadra-core is an install-precondition (not pip-resolvable until published) — see D11

[project.entry-points."aiadra.native_engines"]
mechanical = "aiadra_mechanical:register"
```

### D3. Location — top-level `aiadra-mechanical/`

Mirrors `aiadra-core/` as a sibling top-level package in the AIADRA repo (alongside `aiadra-core/` and `spikes/`). Ecosystem packages live OUTSIDE `aiadra-core` per [ADR/0027 D11](0027-aiad-positioning-and-native-engine-posture.md) + [Manifesto P11](../Manifesto.md); a top-level sibling is the most consistent expression of that boundary.

```
aiadra-mechanical/
├── pyproject.toml                 # name=aiadra-mechanical; entry-point mechanical; dep cadquery-ocp
├── README.md                      # documents the aiadra-core install-precondition prominently (D11)
├── FINDINGS.md                    # v0.0.1 findings doc (D13); populated during impl arc
├── src/aiadra_mechanical/
│   ├── __init__.py                # def register(registrar): ...
│   ├── handlers.py                # 4 Native Engine handlers
│   ├── kernel.py                  # cadquery-ocp evaluation + recipe canonicalization
│   ├── geometry.py                # recipe → OCCT solid; validity gating; tolerance config
│   └── adapter_payload.py         # sketch primitive + extrude payload shapes (adapter_schema_version)
├── tests/
│   ├── test_authoring_loop.py     # 5-step loop Mode A + Mode B, real kernel
│   ├── test_validity_gating.py    # domain-invalid (Class 1) + kernel-invalid (Class 2) per D6/B2
│   ├── test_recipe_hash_stability.py  # cross-platform/-version identity stability
│   ├── test_negative_discipline.py    # provenance / cascade / B6 / cross-object-address (carry-over)
│   └── test_packaging_smoke.py    # cadquery-ocp imports + builds a trivial solid (runs first)
└── (CI workflow — cross-platform matrix per D11)
```

A `packages/aiadra-mechanical/` regroup is deferred until a second ecosystem package (`aiadra-electrical/` etc.) exists; eventual own-repo split is deferred to ≥ `0.1.0` (decision dispositions Q1, Q9).

### D4. Kernel — real OCCT via OCP (`cadquery-ocp`)

Resolves [ADR/0028 D15 item 1](0028-native-engine-implementation-contract.md).

- **Binding:** `cadquery-ocp` (the pybind11 OCP binding distributed on PyPI with prebuilt wheels). Declared as a real, version-pinned dependency (unlike the spike, which declared no kernel dep).
- **Why OCP over pythonocc-core:** PyPI wheels for manylinux / macOS / Windows × supported CPython give a pure-`pip install` story that directly answers the [FRICTION_LOG §10](../../spikes/wedge-003/FRICTION_LOG.md) platform-packaging lesson; ecosystem alignment with CadQuery/build123d provides a deep well of OCCT-via-OCP examples. pythonocc-core's larger API surface is not needed for the v0.0.1 op set (rectangle/circle sketch → prism extrude).
- **OCCT usage in v0.0.1 is deliberately shallow:** build a planar sketch wire/face from the rectangle + circle primitives; a prism (`BRepPrimAPI_MakePrism`-class) for the extrude; that is the whole kernel footprint. No fillets, no booleans beyond the implicit profile, no STEP/IGES I/O (out of scope per D14).
- **Version-pinned** so BREP/tolerance behavior is reproducible within a v0.0.1 line; an OCCT/OCP bump is a deliberate, tested change (relevant to D6 + D9).
- **Fallback route (Codex1 N1):** if a CI-matrix platform lacks usable OCP wheels, the impl arc records it as v0.0.1 packaging friction and either narrows supported platforms for v0.0.1 OR routes a fallback-binding decision to a follow-up ADR — **never a silent mid-implementation swap to pythonocc-core** (Alternatives (i)).

### D5. v0.0.1 scope — minimal real-kernel mirror of the Wedge-003 loop

Identical authoring loop + op catalogue to [ADR/0030 D4 + D5](0030-wedge-003-spike-scope.md), kernel swapped toy → real:

1. **Create Part** — BUILT-IN `propose(kind="create_part", ...)`; the Native Engine is not involved at Part creation ([ADR/0027 D5](0027-aiad-positioning-and-native-engine-posture.md)).
2. **`mechanical.add_sketch_feature`** — rectangle + circle primitives → OCCT planar face; allocates `feat_0001`; geometry_ref `geom_0001`.
3. **`mechanical.add_extrude_feature`** — consumes `feat_0001` (DAG `depends_on_feature_ids=["feat_0001"]`); OCCT prism; subtree-output **replaces** `geom_0001` (per [ADR/0030 D4 step 3](0030-wedge-003-spike-scope.md) subtree-output decision).
4. **`mechanical.adjust_feature_parameter`** — `depth_mm` 5 → 8; real OCCT recompute; SINGLE `part_changed` with `feature_delta.updated` + `geometry_ref_delta.updated`. The canonical parameter-change → recompute loop.
5. **Release Part** — BUILT-IN `propose(kind="release", params={"object_numbers": ["P-000001"], "final_stage": True})`.

**Two modes** (Mode A separate Transactions; Mode B composed via `modify`) per [ADR/0030 D4](0030-wedge-003-spike-scope.md) — Mode B remains the composability proof.

**4-op catalogue** (sketch / extrude / adjust / remove) per [ADR/0030 D5](0030-wedge-003-spike-scope.md); `remove_feature` enables the cascade-rejection test; `recompute_geometry` stays dropped (recompute folds into adjust).

The *only* deltas from the spike are: real kernel (D4), real geometry-identity semantics (D6), real packaging (D11), production code quality, and a real findings doc (D13). The Truth-Model surface — schema, events, provenance, namespaces — is identical to the spike's emissions, so v0.0.1 consumes bundle v0.28.0 unchanged (D7).

### D6. Geometry identity — recipe-hash authoritative; OCCT as validity gate  **(CRUX)**

The [FRICTION_LOG §10](../../spikes/wedge-003/FRICTION_LOG.md) core warning: real OCCT BREP serialization is **not** byte-stable across OCCT minor versions or platforms for identical input. If `geometry_ref.vault_ref = sha256(BREP bytes)`, the same feature recipe evaluated on two machines yields different content hashes → false "geometry changed" signals → broken content-addressed Vault determinism ([ADR/0001 §3](0001-storage-substrate.md)) and a non-reproducible `computed_result`.

**Resolution — two-layer identity:**

1. **Authoritative `vault_ref` = `sha256` of the canonical, kernel-independent feature recipe** (the deterministic JSON serialization the spike already used). Stable by construction across platforms/OCCT versions. This is what release integrity, dedup, and cross-reference resolution depend on. Continuous with Wedge-003 — zero schema change.
2. **OCCT's role is a VALIDITY GATE, not an identity source.** The kernel evaluates the recipe to a real solid; a recipe that fails to build a valid solid → loud failure (see "failure classes" below). This is the real value over the toy kernel, which accepts geometric garbage.
3. **The evaluated solid is NOT a canonical Truth-Model artifact in v0.0.1.** It may be held as a per-process cache (D8) for recompute speed but is not persisted as authoritative Vault bytes.

**Principled basis:** in a parametric system the *feature recipe is the authoritative geometric definition*; the evaluated solid is a *computed materialization*. Hashing the recipe for identity is therefore the correct Truth-Model placement, not a cop-out — it keeps kernel-byte-instability strictly off the identity path while v0.0.1 still gains validity-gating + real packaging/tolerance/recompute friction.

#### What `vault_ref` addresses in v0.0.1 (Codex1 B1 absorption)

The v0.28.0 `geometry_ref` schema carries `role ∈ {authoring_geometry, derived_export}`, REQUIRED `vault_ref` (the canonical Vault anchor), and an OPTIONAL `kind ∈ {solid, surface, wireframe, mesh, point_cloud}` ("engines may set or omit"). To prevent a reader from inferring "`vault_ref` names solid kernel bytes":

- v0.0.1 stages the **canonical recipe JSON bytes** into the Vault; `sha256:` of those bytes IS `geometry_ref.vault_ref`.
- The v0.0.1 `authoring_geometry` Vault artifact is a **canonical parametric recipe artifact** — NOT BREP / STEP / mesh / renderable kernel bytes.
- v0.0.1 **OMITS the optional `kind`** on the authoring_geometry record — `kind` is optional precisely so an engine that does not persist evaluated bytes need not assert a byte semantics. (When evaluated-artifact persistence lands, `kind` becomes meaningful on the persisted record.)
- Consumers needing display / export in v0.0.1 **re-evaluate the recipe** through the installed engine; persisted evaluated artifacts are deferred.
- **Schema home for the deferred path:** the existing `derived_export` role ("STEP / IGES / mesh / render retained as a Part-bound reference," with `derived_from` lineage citing the authoring_geometry id) is the natural slot for a persisted evaluated artifact. The deferred v0.0.2 work is therefore "emit a `derived_export` geometry_ref for the evaluated artifact + resolve cross-version byte stability for ITS `vault_ref`" — **possibly schema-clean** (a behavior + stability change, bundle bump only if a new field proves necessary). This refines the earlier "BREP-persistence SCN" framing.

#### Validity-gate failure classes (Codex1 B2 absorption)

[ADR/0028 D9](0028-native-engine-implementation-contract.md) reserves `NativeEngineKernelError` for true kernel-execution failures with preserved `__cause__`. v0.0.1 splits validity-gate failures into two classes so user-invalid input is never laundered as kernel instability:

- **Class 1 — domain / payload validation failure** → the existing transaction/domain error path (`TransactionError`). The handler rejects loudly **before or around** kernel invocation with a clear message. Examples: `depth_mm <= 0` (Wedge-003 already absorbed this domain check — [FRICTION_LOG R3 N1](../../spikes/wedge-003/FRICTION_LOG.md)); a malformed sketch-primitive payload (engine-owned payload validation).
- **Class 2 — kernel execution failure** → OCCT/OCP raises, or returns a null/invalid shape, while evaluating a *plausible* recipe → the adapter wraps as `NativeEngineKernelError(engine_id, operation_kind, __cause__)` per [ADR/0028 D9](0028-native-engine-implementation-contract.md). Examples: OCCT cannot build a valid face/solid from a geometrically degenerate-but-plausible profile.

The split keeps the v0.0.1 FINDINGS doc's OCCT-class evidence uncontaminated by user error.

### D7. Provenance + schema discipline — identical to the spike; consumes v0.28.0; no bundle bump

Per [ADR/0028 D8](0028-native-engine-implementation-contract.md) + [ADR/0029 D6](0029-part-authoring-scn.md):
- **feature records** carry `fact_provenance.category` from `context.actor` (`ai_proposal` for agent / `human_input` for human); the handler MUST NOT self-attest `human_input` when `actor == "agent"`.
- **geometry_ref records** carry `category="computed_result"` + `derived_from=["feature:<id>", ...]` in STRICT set-equality with `derived_from_feature_ids`.

The negative-discipline surface (engine emits wrong category / extra-or-missing `derived_from` / cross-Object address form `<uuid>:feature:<id>`) carries over from [ADR/0030 D6 + D8](0030-wedge-003-spike-scope.md), now proven against a real-kernel handler. **No schema change → no bundle bump.** v0.0.1 is a pure consumer of canonical bundle v0.28.0 per [ADR/0028 D10](0028-native-engine-implementation-contract.md).

### D8. Cache-keying discipline — recipe-hash + event-log boundary + kernel/config version material

[FRICTION_LOG §6](../../spikes/wedge-003/FRICTION_LOG.md) flagged that the spike's module-level `_GEOMETRY_CACHE` is not a general solution; real engines need workspace + event-log-boundary evidence before reuse per [ADR/0028 D6](0028-native-engine-implementation-contract.md).

v0.0.1 uses the D6(a) keying path. The in-memory evaluated-solid cache key is:

```
(canonical-recipe-hash, context.event_log_last_event_id(), adapter_schema_version, OCP/OCCT version)   # Codex1 N3
```

Before reusing a cached solid the handler verifies the key still matches the proposed-Workspace state (after any `existing_draft` mutations); stale/unverifiable entries are discarded and rebuilt. Including the adapter-schema + OCP/OCCT version (N3) ensures a cached shape is never reused across kernel/config changes. The **`vault_ref` identity stays recipe-only** (D6) — the version material guards the cache, not the identity. This keying is now trivially available since arc 20260601-5 locked `event_log_last_event_id()` proposed-workspace semantics + fail-loud-on-corruption under conformance tests. FINDINGS (D13) records whether the keying feels right for OCCT-class engines.

### D9. Kernel tolerance — pinned documented defaults; identity-independent

Per the [FRICTION_LOG §10](../../spikes/wedge-003/FRICTION_LOG.md) tolerance lesson. v0.0.1 pins explicit, documented OCCT tolerance constants (e.g., `Precision::Confusion` usage at the documented default) in `geometry.py`; they are engine configuration, recorded via `adapter_schema_version` lineage. **Because identity is recipe-hash (D6), tolerance does NOT affect `vault_ref`** — it affects only whether OCCT successfully builds the solid (the Class-2 validity gate). This decouples the most platform-sensitive kernel behavior from Truth-Model identity. FINDINGS records observed tolerance behavior on the v0.0.1 shapes as a baseline for v0.0.2.

### D10. Long-running recompute / cancellation — OUT of scope; record timing baseline

Per the [FRICTION_LOG §10](../../spikes/wedge-003/FRICTION_LOG.md) recompute-cancellation lesson. v0.0.1's shapes (single rectangle+circle sketch → single prism → depth adjust) evaluate in milliseconds even in real OCCT, so cancellation is not meaningfully exercisable. **Explicitly out of scope for v0.0.1.** But the impl arc MUST record actual OCCT call timing as a baseline in FINDINGS, and this ADR NAMES cancellation/timeout/progress as a known v0.0.2+ open question (the `add_pre_validate_hook` surface has no cancellation token today — [ADR/0028 D3](0028-native-engine-implementation-contract.md)). Designing the cancellation surface against a real long-running op is a future arc; v0.0.1 produces the timing evidence that arc will need.

### D11. Packaging / dependencies — `cadquery-ocp` wheels; cross-platform CI; aiadra-core install-precondition

- **`cadquery-ocp` declared + version-pinned** in `pyproject.toml`; pip resolves prebuilt wheels on manylinux / macOS / Windows. The impl arc's **first action is a cross-platform install + build-a-trivial-solid smoke test** (`test_packaging_smoke`, D12) BEFORE writing handlers — spike-in-parallel-with-design, so a wheel/platform surprise is caught cheaply. The **exact OCP version is selected during that smoke step and frozen** in `pyproject.toml` (Codex1 N2); the selected version becomes part of v0.0.1 FINDINGS (no literal placeholder pinned here).
- **`aiadra-core` dependency — install-precondition pattern** per [FRICTION_LOG §1](../../spikes/wedge-003/FRICTION_LOG.md): `aiadra-core` is not yet on PyPI, so pip cannot resolve it as a declared dep. v0.0.1 documents the precondition prominently (README + a clear import-time error if `aiadra-core` is absent) rather than declaring an unresolvable dep. **Publishing `aiadra-core` to PyPI is a separate prerequisite** for a *publicly* `pip install aiadra-mechanical`-able release — it does NOT block v0.0.1 development or a git/editable-install workflow, and public pip-installability is explicitly NOT a v0.0.1 gate.
- **CI matrix** = {Linux, macOS, Windows} × {supported CPython} — the first cross-platform CI in the AIADRA repo; its results feed v0.0.2. Platform-specific OCP-wheel gaps follow the D4 fallback route (N1).

### D12. Test surface — mirror the spike + real-kernel additions

Carries over the [ADR/0030 D12](0030-wedge-003-spike-scope.md) ~20-test surface (loop Mode A/B; event-id distinctness; envelope conformance; namespace-no-colons; DAG acyclicity; provenance STRICT set-equality; cascade reject/accept; B6 binding scan against UNRELEASED current revision; cross-object-address rejection; canonical-unit; release-with-features; status reflection), now run against a real kernel. **New real-kernel tests:**

- `test_packaging_smoke` — `cadquery-ocp` imports + builds a trivial prism (the install-precondition gate; runs first).
- `test_validity_gating` — per D6/B2, **both** a Class-1 domain-invalid case (e.g., `depth_mm <= 0` → `TransactionError`) **and** a Class-2 true-kernel-invalid case (degenerate-but-plausible profile → `NativeEngineKernelError`), with a synthetic kernel-fault-injection fallback (ADR/0030 D9 precedent) if the v0.0.1 shape set is too simple to trigger a genuine OCCT failure — documented in FINDINGS.
- `test_recipe_hash_stability` — the same recipe yields the same `vault_ref` independent of kernel state (the D6 stability guarantee made executable).
- recompute-timing capture (assertion-light; emits a baseline number into FINDINGS per D10).

The carry-over negatives (cascade / B6 / provenance / cross-object-address) MUST fire against a REAL-kernel handler (the engine emits the wrong record through the real code path), proving the boundary discipline holds for production emissions, not just the toy handler.

### D13. Findings doc — `aiadra-mechanical/FINDINGS.md`

v0.0.1 is production, but the spike → production pattern still produces a findings doc — now surfacing the §10 OCCT-class friction **for real**: observed BREP behavior; tolerance behavior on real shapes; recompute timing baseline; cadquery-ocp packaging/wheel reality across the CI matrix; whether D6 two-layer identity held; whether D8 cache-keying felt right; the OCP version selected + frozen (N2). This doc is the load-bearing input to the **v0.0.2 scope ADR** (likely the evaluated-artifact persistence via `derived_export` + cancellation surface + derived properties). Per [ADR/0024 §9](0024-wedge-002-spike-scope.md) cross-artifact friction-comparison, it also compares v0.0.1's real-kernel friction against the spike's §10 by-omission predictions — closing the loop the spike opened. By `0.1.0` it converges to ordinary release notes.

### D14. Explicit out of scope

1. **Evaluated-artifact (BREP/STEP/mesh) persistence as canonical Truth** — deferred per D6 (via the `derived_export` role; possibly schema-clean). The headline deferral.
2. **STEP / IGES / STL Data Adapters** — a future `aiadra.data_adapters` entry-point surface per [ADR/0028 D7 + D11](0028-native-engine-implementation-contract.md); not v0.0.1.
3. **Cancellation / timeout / progress** — per D10; v0.0.2+.
4. **Features beyond sketch + extrude** (fillet / hole / revolve / boolean / pattern) — the catalogue grows in later releases.
5. **Constraint solving** — sketches stay opaque per [ADR/0029 D7](0029-part-authoring-scn.md).
6. **Multi-Part assemblies / `mated_to` / `composed_of`** — single-Part authoring depth only.
7. **`derived_geometry_from`** — last unfilled relationship type ([ADR/0009 §3](0009-relationship-type-satisfies.md)); awaits multi-Part Native Engine work.
8. **Derived geometric properties** (mass / volume / centroid; `bounding_box_mm` IS schema-available in v0.28.0) emitted as Truth — deferred for v0.0.1 identity-cleanliness; a low-friction v0.0.2 candidate noted in FINDINGS.
9. **Validation hooks** — per [ADR/0030 D7](0030-wedge-003-spike-scope.md); defer.
10. **Authoring UI / viewport** — per [ADR/0028 D13](0028-native-engine-implementation-contract.md).
11. **Multi-process / parallel engine instances** — per [ADR/0028 D6 + D15](0028-native-engine-implementation-contract.md).
12. **`aiadra-electrical` / KiCad** — a separate strand.
13. **Publishing `aiadra-core` to PyPI** — prerequisite for public pip-install (D11); a separate arc, not gated by v0.0.1.

### D15. Sequencing after this scope ADR

1. **This ADR/0031 (landed at arc-close)** — `aiadra-mechanical` v0.0.1 scope.
2. **`aiadra-mechanical` v0.0.1 implementation arc** (next; would be `20260601-7`) — cross-platform install smoke FIRST; then 4 real-OCCT handlers + recipe-hash identity + cache-keying; the test surface across the CI matrix; FINDINGS.md.
3. **Findings review** (small, per the [Wedge-003 friction-log-review precedent arc 20260601-4](../Discussions/20260601/20260601-4/CLOSED.md)) — surface refinement ADRs / the v0.0.2 list.
4. **v0.0.2 scope ADR** — likely evaluated-artifact persistence (via `derived_export`) + cancellation surface + derived properties, informed by v0.0.1 FINDINGS.
5. **`aiadra-mechanical` later releases** — multi-arc strand; horizon = years per [ADR/0027 D17](0027-aiad-positioning-and-native-engine-posture.md).

Parallel-eligible: per-engine research arcs (Solvespace / OpenSCAD / Onshape / KiCad) per [ADR/0028 D14](0028-native-engine-implementation-contract.md); the carried housekeeping items.

### D16. Coherence Checklist walk

11 items:

| Item | Verdict | Note |
|---|---|---|
| List-addressability | PASS | feature + geometry_ref carry stable ids per ADR/0029 D2; sketch primitives opaque in adapter_payload per ADR/0029 D7 (no core enforcement). |
| Released cross-Object geometry | N/A | Single-Part v0.0.1; no cross-Object geometric refs. |
| Engineering-structure cross-project | N/A | No `composed_of` / `mated_to`. |
| Binding ownership | PASS | B6 binding-scan negative test carries over from ADR/0030 D9 (bind CURRENT UNRELEASED revision); real-kernel `part_changed` participates in the scan. |
| Identity cross-check | N/A | No endpoint `revision_id` cross-check change. |
| Released geometric satisfaction | N/A | No `mated_to`. |
| **Canonical units at fact level** | PASS — LOAD-BEARING | feature.parameters[].unit uses canonical_unit enum per ADR/0029 D10; sketch primitives use `_mm`/`_deg` suffix. Real OCCT consumes the SAME canonical units (no kernel-native unit drift). |
| Quaternion normalization | N/A (deferred) | No first-class transforms in v0.28.0 per ADR/0029 D11. |
| **AIADRA Core hosts nothing** | PASS — TIGHTENED | First SHIPPABLE ecosystem package; the real `cadquery-ocp` dependency lives entirely in `aiadra-mechanical`; `aiadra-core` never imports it and remains schema/protocol authority only. No service. |
| Execution-record cardinality invariants | N/A | B6 negative-test fixture creates TestExecution/TestProcedure to exercise the scan, not cardinality (per ADR/0030 D16). |
| **Native engine boundary** | PASS — TIGHTENED | The boundary under REAL kernel pressure: OCCT-as-library (never wrapping an app per ADR/0027 D4); the engine emits `part_changed` via the envelope; provenance/cascade/DAG enforced at the boundary; identity stays on the stable recipe hash (D6). Codex1 B1 tightens it further — evaluated BREP stays OUT of canonical truth until an explicit follow-up. First time the boundary holds with a real C++ kernel behind it. |

No new Coherence Checklist item. No new Pattern Catalogue row (Codex1 N4) — "recipe-anchored identity, evaluated artifact deferred" earns pattern status only after v0.0.1 FINDINGS confirm it holds under real OCCT friction.

### Decision dispositions (open questions Q1–Q9)

- **Q1 Location:** top-level `aiadra-mechanical/`; `packages/` regroup only once a second package exists.
- **Q2 Geometry identity (CRUX):** recipe-hash authoritative + OCCT validity-gate + B1 byte-format clarification.
- **Q3 BREP cache-only:** accepted; persisted evaluated artifacts deferred (via `derived_export`).
- **Q4 Validity-gate failure mode:** two-class split per B2 (Class 1 `TransactionError` / Class 2 `NativeEngineKernelError`).
- **Q5 Version pin granularity:** exact `==` pin, selected + frozen during the first smoke-test step.
- **Q6 Pattern Catalogue row:** deferred (N4).
- **Q7 Derived properties:** deferred (D14 item 8).
- **Q8 aiadra-core PyPI publish:** install-precondition for v0.0.1 dev; public pip-installability waits for publication and is NOT a v0.0.1 gate.
- **Q9 Own-repo split:** deferred to ≥ `0.1.0`.

## Supersession + amendment register

**No supersessions.** [ADR/0023](0023-wedge-spike-scope-and-runtime.md) + [ADR/0024](0024-wedge-002-spike-scope.md) + [ADR/0030](0030-wedge-003-spike-scope.md) conventions preserved. [ADR/0028 D14 step 5](0028-native-engine-implementation-contract.md) sequencing operationalized; [ADR/0028 D15 item 1](0028-native-engine-implementation-contract.md) OCCT-binding deferral RESOLVED (OCP).

**No multi-document amendments.** Manifesto / ArchitectureOverview / TruthModelSchema / Glossary unchanged. Glossary may gain entries for `aiadra-mechanical` + the `mechanical` engine in a future polish/housekeeping arc — flagged, not blocking.

## Consequences

- **No bundle bump** (consumes v0.28.0). **No `aiadra-core` version bump in this arc** (the impl arc may bump only if real-OCCT friction requires a core-side fix).
- **First SHIPPABLE Native Engine scoped.** The Wedge spike series' destination; the first time AIADRA designs production authoring code against a real C++ kernel.
- **OCCT binding committed (OCP / `cadquery-ocp`)** — resolves the [ADR/0028 D15 item 1](0028-native-engine-implementation-contract.md) deferral; chosen for its cross-platform PyPI-wheel packaging story and CadQuery/build123d ecosystem alignment.
- **Geometry identity is recipe-anchored** (D6) — kernel-byte-instability is kept off the Truth-Model identity path; OCCT is a validity gate; evaluated-artifact persistence is a named, possibly-schema-clean v0.0.2 path (via `derived_export`).
- **Validity-gate failures are two-class** (D6/D9/D12, Codex1 B2) — domain/payload errors (`TransactionError`) vs true kernel failures (`NativeEngineKernelError`); keeps the FINDINGS doc's OCCT-class evidence uncontaminated.
- **`vault_ref` byte semantics pinned** (D6, Codex1 B1) — v0.0.1 stages canonical recipe JSON bytes; the `authoring_geometry` artifact is a parametric recipe artifact, not kernel bytes; `kind` omitted.
- **First cross-platform CI in the AIADRA repo** (D11) — its wheel/packaging results feed v0.0.2; OCP-wheel gaps follow the fallback route, never a silent binding swap.
- **FINDINGS doc is the load-bearing output** (D13) — surfaces the §10 OCCT-class friction for real and seeds the v0.0.2 scope ADR.

## Alternatives rejected

- **(i) Silent fallback to pythonocc-core** if OCP wheels fail on a platform. Rejected per Codex1 N1 — a binding swap is an ADR-level decision; v0.0.1 records the gap as friction and narrows platforms or routes a follow-up ADR.
- **(ii) BREP-byte identity** (`vault_ref = sha256(BREP)`). Rejected per D6 — kernel-byte instability across OCCT versions/platforms breaks Vault determinism + reproducible `computed_result`.
- **(iii) All validity-gate failures as `NativeEngineKernelError`** (Claude1 Q4 first pass). Rejected per Codex1 B2 — over-broadens ADR/0028 D9; launders user-invalid input as kernel instability.
- **(iv) Persist evaluated BREP as canonical Truth in v0.0.1.** Rejected per D6/Q3 — spreads the first real-kernel package across too many axes; deferred to v0.0.2 via `derived_export`.
- **(v) Broader v0.0.1** (fillet/hole/revolve and/or STEP Data Adapter). Rejected per D5 — minimal real-kernel mirror proves kernel-integration + packaging + validity-gating fundamentals before breadth.
- **(vi) `aiadra-mechanical-spike` production name / carry-over spike code.** Rejected per D2 + [ADR/0023 §4](0023-wedge-spike-scope-and-runtime.md) — clean-slate production avoids spike shortcuts becoming baseline.
- **(vii) Co-landed scope + impl in one arc.** Rejected per D1 + [ADR/0024](0024-wedge-002-spike-scope.md) precedent — scope-first surfaces errors cheaply and isolates findings-doc production.
- **(viii) Public pip-installability as a v0.0.1 gate** (block on `aiadra-core` PyPI publication). Rejected per D11 — shippable-quality code ≠ published; the install-precondition + a separate PyPI-publish arc decouple the two.

## References

- [ADR/0030 — Wedge-003 spike scope](0030-wedge-003-spike-scope.md) — the loop + op catalogue + provenance discipline v0.0.1 mirrors with a real kernel; D15 step 5 names this ADR.
- [`spikes/wedge-003/FRICTION_LOG.md`](../../spikes/wedge-003/FRICTION_LOG.md) — the load-bearing input; §1 install-precondition, §6 cache-keying, §10 lessons-by-omission (BREP/tolerance/recompute/packaging).
- [ADR/0028 — Native Engine Implementation contract](0028-native-engine-implementation-contract.md) — D2 entry-point; D6 cache-freshness; D8 provenance split; D9 `NativeEngineKernelError`; D10 canonical-bundle-only; D11 ecosystem boundary; D14 step 5 sequencing; D15 item 1 binding deferral (resolved here).
- [ADR/0027 — AIAD positioning + Native Engine posture](0027-aiad-positioning-and-native-engine-posture.md) — D4 never-wrap-apps; D5 Part-as-Object vs in-Part; D6 cache freshness; D11 ecosystem packages outside core; D17 years horizon; D18 adapter-shell wire names.
- [ADR/0029 — Part authoring SCN](0029-part-authoring-scn.md) — `part_changed` + feature/geometry_ref namespaces + STRICT set-equality + DAG + cascade; the v0.28.0 surface v0.0.1 consumes unchanged.
- [ADR/0005 §9 + D7 + D9](0005-object-type-part.md) — geometry_ref role enum + required vault_ref + adapter shell.
- [ADR/0001 §3](0001-storage-substrate.md) — content-addressed Vault determinism (drives D6).
- [ADR/0023 §4 + §6](0023-wedge-spike-scope-and-runtime.md) — throwaway-spike posture + repo layout; [ADR/0024 §9](0024-wedge-002-spike-scope.md) — scope-first-ADR + friction-comparison pattern.
- [Manifesto P5 + P11](../Manifesto.md) — reject-loudly; Core hosts nothing.
