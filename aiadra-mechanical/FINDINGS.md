# aiadra-mechanical v0.0.1 — findings

Primary deliverable of the implementation arc (20260602-1) per
[ADR/0031 D13](../Docs/ADR/0031-aiadra-mechanical-v0.0.1-scope.md). Surfaces the
[Wedge-003 FRICTION_LOG §10](../spikes/wedge-003/FRICTION_LOG.md) OCCT-class
items **for real** — packaging, BREP behavior, tolerance, recompute timing —
and seeds the v0.0.2 scope. Converges to ordinary release notes by `0.1.0`.

**Status (arc 20260602-1 R2):** package implemented end-to-end against a real
OCCT kernel; **30 aiadra-mechanical tests pass in 39.4s**; **full aiadra-core
suite 360 passed (0 regressions)** after 3 test-hygiene fixes (§1). The
5-step authoring loop (sketch → extrude → adjust 5→8mm → release) runs in both
Mode A (separate Transactions) and Mode B (composed via `modify`).

**Environment:** Windows-11 (10.0.26200) / CPython 3.12.4 / `cadquery-ocp`
**7.9.3.1.1** (OCCT 7.9.x), installed via prebuilt `win_amd64` wheel.

## 1. Build / install / discovery (§10 packaging — surfaced for real)

- **`cadquery-ocp==7.9.3.1.1` installed cleanly from a PyPI wheel** on
  win_amd64 / cp312 — **no build-from-source**, pulling `vtk`, `numpy`,
  `matplotlib`, etc. as wheels. This directly answers the FRICTION_LOG §10
  platform-packaging worry **for Windows**: the OCP wheel story holds. (The
  Linux/macOS legs are exercised by the cross-platform CI workflow at the repo
  root — `.github/workflows/aiadra-mechanical-ci.yml`; their results extend this
  section.)
- **Exact version selected + frozen during the smoke step** (ADR/0031 N2):
  `cadquery-ocp==7.9.3.1.1` pinned in `pyproject.toml`.
- **Install precondition** (ADR/0031 D11): `aiadra-core` is not on PyPI, so it is
  NOT a declared dependency; install it (editable) first, then
  `pip install -e ./aiadra-mechanical --no-deps`. Documented in README.
- **Discovery worked first try**: `refresh_native_engines()` +
  `native_engine_status()` load the `mechanical` engine with its 4 ops against
  the real installed distribution, coexisting with the still-installed
  `mechanical_spike` (Wedge-003) — the ADR/0028 D2 collision-free
  distinct-engine_id design holds with TWO real ecosystem packages installed.
- **3 pre-existing aiadra-core tests regressed on install — fixed (test-surface
  only; no core code change; no version bump).** The same friction class as arc
  20260601-3: tests that assumed engine_id `mechanical` would never be a real
  installed engine (`test_dispatch_raises_engine_not_available_when_engine_missing`,
  `test_refresh_native_engines_clears_cache`,
  `test_protocol_refresh_is_same_as_native_engine_refresh`). Fix: use a
  guaranteed-never-installed fake engine_id (`faketestengine`). **Lesson
  (extends the arc-5 README rule):** a test must not assume a *specific real
  engine_id is absent* from the dev venv — the venv now ships real
  `mechanical`. Candidate for the aiadra-core integration `README.md`
  test-hygiene doc.

## 2. Native Engine API ergonomics

The `NativeEngineContext` surface (`find_reservation_entry_by_number` /
`load_sidecar` / `stage_vault_bytes` / `stage_sidecar` / `emit_event` /
`event_log_last_event_id`) carried the production handlers with no missing
helpers — the handler flow is the same shape proven by Wedge-003, against a real
kernel. `emit_event` remained the right single-event default.

## 3. Schema ergonomics (v0.28.0)

Consumed unchanged — **no bundle bump**. Atomic delta rules, DAG
`depends_on_feature_ids`, STRICT geometry_ref provenance set-equality, and
canonical-unit `depth_mm` all held against real handler emissions. **`kind`
omitted** on `authoring_geometry` records (ADR/0031 D6/B1): the optional field
is simply absent, removing any "solid bytes at vault_ref" implication.

## 4. Composability (Mode A vs Mode B)

Both modes pass. Mode B (sketch propose + extrude modify + adjust modify → one
commit) produces 3 distinct `evt_NNNN` ids and the same final state as Mode A
(2 features, 1 geometry_ref). Draft-aware reads let the extrude/adjust handlers
see the staged sketch.

## 5. Geometry identity + validity gate (ADR/0031 D6 — the crux, validated)

- **Identity is recipe-hash.** `vault_ref = sha256(canonical recipe JSON)`. Two
  independent Parts with identical primitives get an **identical** `vault_ref`;
  `fact_provenance` changes do NOT affect it; a `depth_mm` change DOES
  (`test_recipe_hash_stability`, Codex1 N4 golden).
- **OCCT is a real validity gate.** `geometry.evaluate_part` builds a genuine
  box-with-cylindrical-hole **solid** via an OCCT boolean `Cut` and validates it
  with `BRepCheck_Analyzer`. Volume checks out:
  `20×10×5 − π·2²·5 ≈ 937.168 mm³`. The toy kernel could not have done this.
- **Failure split (Codex1 B1) verified end-to-end:** domain errors →
  `TransactionError` (passthrough); engine-local `MechanicalKernelEvaluationError`
  (or a raw OCP exception) → the **aiadra-core dispatch adapter** wraps it as
  `NativeEngineKernelError` with `engine_id` / `operation_kind` / `__cause__`.
  The engine never constructs `NativeEngineKernelError`. Forcing a genuine
  OCCT-internal failure on the trivial v0.0.1 shapes proved impractical, so the
  Class-2 wrapping path is covered by fault injection on `evaluate_part`
  (ADR/0031 D12 fallback) — an honest gap noted for richer shapes in v0.0.2.

## 6. Cache freshness (ADR/0031 D8 / Codex1 N3)

The evaluated-solid cache key is
`(recipe-hash, event_log_last_event_id(), adapter_schema_version, OCP/OCCT version)`.
The recipe-hash component coincides with `vault_ref` identity; the event-log +
version material guard the cache without touching identity. Implementing the
D6(a) keying was ~30 LOC. At v0.0.1 scale it is a **pattern-exercise** (eval is
~5 ms; see §10) — but it demonstrates the freshness key is cheap, and the
version material means a kernel/binding upgrade never reuses a stale solid.

## 7. Provenance discipline burden

~2 LOC per record build-site, as in the spike. Feature records carry
actor-derived `ai_proposal`/`human_input`; geometry_ref records carry
`computed_result` + `derived_from=["feature:<id>", …]` in lockstep. Negative
tests confirm cross-Object address forms and category mismatches are rejected
against REAL handler emissions.

## 8. Release graph interactions

Releasing a featureful Part (2 features + 1 geometry_ref) succeeds; the released
revision lands in the Reservation's `released_revision_ids[]`. No unexpected
release-time validators fire (no `mated_to`, no cross-Part derivation).

## 9. Cross-package effect (ecosystem packages get smaller as core grows)

`aiadra-mechanical` v0.0.1 is **~600 LOC of source** (6 modules) + ~300 LOC of
tests — smaller than Wedge-003's ~1,500 because it consumes the production
`aiadra-core` API fully. The novel surface is concentrated in `geometry.py`
(real OCCT) and `cache.py` (D8 keying); `kernel.py` / `adapter_payload.py` /
`handlers.py` are structural re-writes of the proven spike shapes.

## 10. The §10 OCCT-class items — now measured

- **BREP serialization:** identity is recipe-hash, so cross-version BREP-byte
  stability is OFF the Truth-Model path in v0.0.1 (the D6 decision validated).
  When v0.0.2 persists an evaluated artifact (via `derived_export`), THAT
  artifact's `vault_ref` reopens the byte-stability question — to be resolved
  with OCCT-version pinning there.
- **Tolerance:** `Precision::Confusion = 1e-07` (pinned, documented in
  `geometry.py`). Identity-independent; gates validity only. No tolerance
  surprises on the v0.0.1 shapes.
- **Recompute / cancellation:** `evaluate_part` (box + real cylindrical-hole
  boolean + `BRepCheck_Analyzer`) measured at **~4.9 ms/call** (200-call mean,
  Windows/cp312/OCCT 7.9.3.1.1). Milliseconds — **cancellation is moot at
  v0.0.1 size** (ADR/0031 D10). This is the baseline the v0.0.2 cancellation
  design will need once features get expensive.
- **Platform packaging:** Windows wheel install clean (§1). Linux/macOS via the
  CI matrix; gaps follow the D4 fallback route.

**For v0.0.2:** evaluated-artifact persistence via `derived_export` (+ that
artifact's cross-version byte-stability); a real Class-2 OCCT-failure case on a
richer shape; cancellation/timeout surface once a recompute is expensive;
derived geometric properties (`bounding_box_mm` is already schema-available).
