# Wedge-003 friction log

Primary deliverable per [ADR/0030 D11](../../Docs/ADR/0030-wedge-003-spike-scope.md).
Populated PROGRESSIVELY during the implementation arc (20260601-3), not just at end.
10-section structure per scope.

**Status as of 2026-06-01 (arc 20260601-3 R3 close):** 4 Native Engine handlers
written; toy synthetic kernel + adapter_payload helpers + demo + **23 tests
written** (13 happy-path + 9 negative-discipline + 1 demo-script smoke);
demo runs end-to-end (5-step Mode A authoring loop completes with depth_mm
adjusted 5 → 8 visible in Product Truth as a `feature.parameters[]` record with
canonical unit `mm`); **378/378 tests passing** (was 355 pre-arc; +23 Wedge-003;
+0 regressions after 2 aiadra-core test adaptations per §1 below).

**R3 absorption (Codex2 B1 + N1)**: B1 added the missing B6 binding-scan
INTEGRATION test (`test_b6_binding_scan_catches_mechanical_spike_mutation_against_unreleased_bound_revision`)
that creates a Part with features, a TestProcedure + TestExecution fixture, links
TEX `executed_on` Part with Fixed binding pinning Part's current unreleased
revision, then asserts `RevisionBindingError` at `draft.validate()` when
attempting `mechanical_spike.adjust_feature_parameter`. This proves the full
chain: `part_changed` correctly classifies as a mutation event in
`find_mutation_after_binding_violations_for_events` (arc 20260601-1 B3 R1 live
for Native Engine emissions); proposed-state dual-fold scan fires for Native
Engine ops (arc 9 Phase C Codex2 B1 R3 generalized); B6 rule blocks against
unreleased current_revision_id (per Phase 1 + Phase C reservation model).
**Codex2 N1 R3 absorption**: depth-domain validation added on
`adjust_feature_parameter` (rejects `new_value <= 0` for `*_mm` depth params)
with regression test `test_adjust_rejects_non_positive_new_value`. **Codex2 N2
R3 absorption**: README + test layout-table updated to reflect actual 23-test
count (13 + 9 + carries-over 12).

## 1. Build / install / discovery friction

**`pip install -e ./spikes/wedge-003` failed on first attempt with
"Could not find a version that satisfies the requirement aiadra-core>=0.11.0"**.
The spike's `pyproject.toml` originally declared `dependencies = ["aiadra-core>=0.11.0"]`
but `aiadra-core` is NOT published to PyPI — it's a local editable-install in the
same venv. pip's dependency resolver couldn't find it on PyPI even though it was
already installed locally.

**Fix**: dropped the explicit dependency declaration; added an inline comment
explaining the install-precondition pattern (spike assumes `aiadra-core` already
present in the venv). Re-install succeeded.

**Implication for `aiadra-mechanical` v0.0.1**: when `aiadra-core` IS published
to PyPI, this issue goes away. Until then, ecosystem packages should either (a)
declare no aiadra-core dep + document install precondition (Wedge-003's path),
or (b) use `pip install --no-deps -e .` for editable spike installs.

**`refresh_native_engines()` + `native_engine_status()` worked first try** — the
two-pass discovery from arc 20260601-1 D5 picked up `mechanical_spike` correctly
against the REAL installed distribution; first time the discovery loop runs
end-to-end against a real entry-point (not monkeypatched). Big validation
moment: the boundary discipline holds.

**Pre-existing aiadra-core tests broke after spike install** (2 failures):
- `test_native_engine_status_empty_when_no_engines` assumed an empty status dict;
  with `mechanical_spike` installed it returned `{"mechanical_spike": ...}`.
- `test_phase_c_propose_kinds_catalogue` asserted `len(kinds) == 17`; with 4
  spike kinds added it became 21.
- Both fixed in arc 20260601-3 R2 (mark them as taking installed engines into
  account: monkeypatch empty entry-points OR filter to builtin-only kinds).
- **Lesson**: aiadra-core tests should NEVER assume "no Native Engines installed"
  — the dev venv reality is whatever's `pip install -e`'d. Future tests
  introducing engine-dependent assertions should explicitly control discovery
  state via monkeypatched entry-points (the pattern other tests in
  `test_native_engine_api.py` already follow).

## 2. Native Engine API ergonomics

**`NativeEngineContext` surface felt right** — 6 read properties + 4 read methods
+ 5 stage methods + `make_event` / `emit_event` envelope helpers + hook
registration. No missing helpers surfaced. Handler code is straightforward:

```python
entry = context.find_reservation_entry_by_number(part_number)  # 1 call
sidecar = context.load_sidecar(part_uuid)  # 1 call (draft-aware)
# ... build records ...
context.stage_vault_bytes(geom_bytes)  # 1 call
context.stage_sidecar(part_uuid, sidecar)  # 1 call
context.emit_event("part_changed", payload)  # 1 call
```

**`emit_event` vs `make_event` distinction**: per Codex2 N1 from arc 1 docstring
guidance, `emit_event` is the right default for single-event handlers. None of
the spike's handlers needed `make_event` separately. The risk Codex2 flagged
(two un-staged `make_event()` calls colliding on event_id) didn't surface
because the spike's pattern is one-event-per-handler. **Recommend**: for
production engines, `emit_event` should remain the path of least resistance;
`make_event` is for advanced cases (e.g., conditional staging).

**Hook adapter**: NOT EXERCISED by the spike (per ADR/0030 D7 deferral). Absence
felt fine — the spike's invariants are cleanly enforceable via schema + fold
without engine-side hook participation.

## 3. Schema ergonomics (v0.28.0)

**Atomic delta rules (ADR/0029 D3) felt right**: the spike's handlers stage
records that match the rules naturally (no intra-array duplicates; no cross-array
overlap; added MUST be fresh; updated/removed MUST exist). No friction. The
6 invariants didn't get in the way.

**DAG `depends_on_feature_ids` (ADR/0029 D9 + Codex1 B6 from arc 13) felt natural**:
the extrude handler declares `depends_on_feature_ids=[sketch_feature_id]`
explicitly. Kahn's algorithm acyclicity check fired silently in fold (no
spurious errors).

**Cascade rule (ADR/0029 D12) caught a real bug**: the cascade-rejection
negative test surfaced that removing `feat_0001` (sketch) while `feat_0002`
(extrude) still depends on it correctly raises `FoldInconsistencyError`
("depends_on_feature_ids ['feat_0001'] which do not exist on the Part") at
`draft.validate()`. The batched-remove test confirms that bundling all
dependent removals into one event succeeds. Cascade integrity holds.

**STRICT set-equality on geometry_ref provenance (ADR/0029 D6 + Codex2 B2 R3
from arc 13) worked transparently**: the spike's handlers construct
`derived_from_feature_ids` + `fact_provenance.derived_from` in lockstep. The
fold's strict equality check never fires for the spike's well-behaved
handlers; only fires for synthetic-misbehavior negative tests. **The
canonical-form discipline `feature:<feat_id>` is engine-trivially-correct** —
spike code just does `[f"feature:{feat_id}"]` once when building the
geometry_ref record.

**Codex1 B1 R1 absorption (extrude depth as `feature.parameters[]` record)
strengthened the spike significantly**: making depth_mm Product Truth (not
opaque payload) means `mechanical_spike.adjust_feature_parameter` is genuinely
visible at the AIADRA fold + canonicalization layer. `test_adjust_changes_parameter_value_and_geometry_hash`
proves the geometry hash genuinely changes when the parameter changes. This
is the canonical "parameter change → recompute → new geometry hash" loop that
real CAD systems need.

## 4. Composability (Mode A vs Mode B)

**Both modes work end-to-end**. Test count: 13 happy-path tests cover the
5-step loop in both modes + provenance + DAG + B1.

**Mode B (composed via `modify`) specifically verified**:
- `test_mode_b_event_ids_distinct` — 3 composed engine ops produce 3
  distinct `evt_NNNN` ids via draft-aware `_next_event_id_in_draft` per
  arc 1 Codex1 B2 R1.
- Draft-aware reads work transparently — extrude handler reads the sketch
  feature from the staged sidecar (not stale disk) per arc 9 Phase C
  Codex1 B1.

**`emit_event` was the right choice for the spike's pattern**: all 4 handlers
emit a single `part_changed` event each via `emit_event`. The Codex2 N1
docstring guidance (steer toward `emit_event` for multi-event handlers)
matched the spike's actual usage.

## 5. Vault Adapter ergonomics

**`context.stage_vault_bytes(data)` returns `(vault_ref, vault_path)`** — clean
API. Spike just uses `vault_ref` (the canonical sha256-prefixed content hash);
`vault_path` ignored. Aiadra-core handles the Vault writes during commit. Spike
inherits the spike-grade Vault Adapter from `aiadra-core` (vs Wedge-002 which
had its own).

**No friction**. The Vault abstraction holds at this layer.

## 6. Cache freshness implementation cost

**Toy kernel uses module-level `_GEOMETRY_CACHE`** keyed by
`sha256(canonical_json(features))`. ~20 LOC including the cache lookup +
populate logic. Pure-function cache: only Product Truth inputs affect the
key.

**Per Codex1 N3 R1 absorption from arc 20260601-3**: this is NOT a general
cache-freshness solution. Real engines need workspace + bundle + event-log
boundary evidence before reuse per ADR/0027 D6. The toy cache only proves
the PATTERN is implementable in <30 LOC; production OCCT-class engines need
more.

**For `aiadra-mechanical` v0.0.1**: cache keying must include either
(a) sidecar content hashes / event-log boundary explicitly, or
(b) `context.event_log_last_event_id()` snapshots invalidating cache
entries that pre-date them.

## 7. Provenance discipline burden

**Every feature record carries `fact_provenance.category`**. Spike code does
this via `_provenance_category_for_actor(context.actor)` helper (returns
`"ai_proposal"` for agent, `"human_input"` for human). 2 LOC per record
build site. Not burdensome.

**Geometry_ref records carry `category="computed_result"` + `derived_from=["feature:<id>", ...]`**.
Spike code constructs both in lockstep, ~3 LOC. Not burdensome.

**The STRICT set-equality check (ADR/0029 D6 R3) is the right rigor level**:
catches engine bugs (e.g., declaring dependency on a feature without listing
it in provenance, or attesting a feature in provenance without declaring
dependency). Spike caught no such bugs because handlers are well-behaved,
but the negative tests confirm the boundary holds.

## 8. Release graph interactions

**`propose(kind="release", params={"object_numbers": ["P-000001"], "final_stage": True})`
succeeds on a Part with features + geometry_refs**. No new release-time
validators fire on featureful Parts (no `mated_to` interactions; no
`derived_geometry_from` cross-Part claims).

**Released revision_id appears in Reservation's `released_revision_ids[]`**;
the working sidecar still reflects the working state (new `current_revision_id`
allocated for next mutation). This is the standard Phase 1 + Phase C release
model — Codex1 B1 R1 absorption from arc 2 made this explicit in ADR/0030 D9.

**No friction**. Featureful Parts release cleanly.

## 9. Cross-spike friction comparison

**Items carried forward from Wedge-001/002 friction logs**:
- YAML Profile lint + 12 negative fixtures (verbatim from Wedge-002 — YAML
  Profile didn't change in v0.28.0)
- Spike-local UUIDs per ADR/0024 §5 (Part P-000001 UUID matches ADR/0029
  examples + arc 1 tests)
- `outputs/` checked in for review per Wedge-001/002 precedent

**Items NEW to Wedge-003 (not present in prior spikes)**:
- Entry-point installable spike (Wedge-001/002 were standalone `wedge/`
  packages; Wedge-003 IS discovered by `aiadra-core` at runtime)
- Native Engine API surface usage (Wedge-001/002 called `aiadra-core` APIs
  directly; Wedge-003 receives `NativeEngineContext` via dispatch adapter)
- `part_changed` event emission (Wedge-001/002 used `<type>_created` +
  `<type>_changed` only for attachment cases)
- Feature + geometry_ref namespaces (NEW in v0.28.0 per ADR/0029)
- DAG `depends_on_feature_ids` between features (NEW in v0.28.0)
- `feature.parameters[]` with canonical units (per ADR/0029 D10; Codex1 B1
  R1 from arc 20260601-3 forced first-class)

**Items from prior spikes that DID NOT recur (Wedge-003 design avoided them)**:
- Per-spike Vault Adapter reimplementation (Wedge-002 had its own; Wedge-003
  inherits from `aiadra-core`)
- Per-spike YAML Profile lint reimplementation (same; inherited)
- Per-spike CLI orchestrator (Wedge-001/002 had `cli.py` with multiple
  subcommands; Wedge-003 dispatches through Native Engine entry-point + has
  only `demo.py` for the worked invocation)
- Per-spike `transaction.py` / `manifest.py` / `validate.py` reimplementations

**Net effect**: Wedge-003 is ~1,500 LOC of new spike-specific code; Wedge-002
was ~2,400 LOC. The reduction is because Wedge-003 IS the first spike to
fully consume the production `aiadra-core` API surface rather than reimplement
spike-grade equivalents. **Pattern**: future ecosystem packages start much
smaller because the core has more.

## 10. Lessons by omission (Codex1 N1 R1 absorption from arc 20260601-2)

Per ADR/0030 D11 §10: explicitly name OCCT-class friction the toy kernel
CANNOT surface. These ARE the friction items the first `aiadra-mechanical`
v0.0.1 production-package arc will surface.

### BREP serialization quirks
The toy kernel produces synthetic byte blobs (canonical JSON-serialized
feature recipes). Real OCCT BREP serialization has format-version quirks,
endianness considerations, and shape-tessellation parameters that affect
byte-level reproducibility across machines. Likely friction:
- pythonocc-core vs OCP differ in BREP serialization output for identical input
- OCCT minor version upgrades break content-hash stability
- Cross-platform BREP byte equality is non-trivial

### Kernel tolerance behavior
The toy kernel has zero tolerance behavior (just JSON serialization). Real
kernels have:
- Floating-point comparison thresholds (e.g., for face/edge coincidence)
- Near-miss intersection cases that produce different results on different
  platforms
- Imprint-merge tolerance settings that affect feature-tree evaluation outcomes

### Long-running recompute / cancellation
Toy kernel returns synchronously in milliseconds. Real OCCT operations on
complex Parts can take minutes (or hang on degenerate input). Friction:
- What's the cancellation story? `context.add_pre_validate_hook` doesn't have
  a cancellation token; long compute would block the whole Transaction
- Should `mechanical.compute_geometry` accept a timeout? A progress callback?
- Bottoming-out behavior when OCCT exception is unrecoverable mid-recompute

### Platform-specific dependency packaging
Toy kernel has zero native dependencies. Real OCCT packaging:
- pythonocc-core ships pre-built wheels for some platform/Python combos
  only; missing combos require building OCCT from C++ source
- OCP uses py-bindgen and similar packaging challenges
- Cross-platform CI for `aiadra-mechanical` v0.0.1 needs a strategy: pinning
  wheel versions; fallback to conda-forge; or shipping our own wheels

**Recommendation for `aiadra-mechanical` v0.0.1 scope ADR**: surface these 4
friction items explicitly in the scope's "open questions" section. Don't
discover them mid-implementation.
