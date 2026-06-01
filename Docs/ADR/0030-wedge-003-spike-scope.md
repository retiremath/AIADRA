# ADR/0030 — Wedge-003 (Native-Engine-instrumented Wedge) spike scope

## Frontmatter

- **Status:** Accepted — 2026-06-01 (arc 20260601-2; two-round convergence Claude1 + Codex1 / Claude2 + Codex2).
- **Operationalizes:** [ADR/0027 D17](0027-aiad-positioning-and-native-engine-posture.md) Wedge-003 gating + [ADR/0028 D14 step 4](0028-native-engine-implementation-contract.md) sequencing. Pins scope for the **Native-Engine-instrumented Wedge spike** — first arc to design real AIADRA-native mechanical authoring work, even at spike scale.
- **Sequencing per renumbered [ADR/0028 D14](0028-native-engine-implementation-contract.md)**: (a) ADR/0028 ✓; (b) ADR/0029 ✓; (c) `aiadra-core 0.10.0 → 0.11.0` arc 20260601-1 ✓; **(d) this ADR — Wedge-003 scope ✓**; (e) Wedge-003 impl arc (next; would be `20260601-3`); (f) friction-log review arc (small); (g) `aiadra-mechanical` v0.0.1 scope ADR + impl.
- **No schema bundle bump.** Bundle stays v0.28.0. This ADR is scope-only (matches ADR/0023 + ADR/0024 precedent); implementation arc writes spike code + tests + friction log.
- **No `aiadra-core` version bump in this arc** (positioning-only scope ADR). The Wedge-003 impl arc may bump aiadra-core ONLY if the spike surfaces friction requiring a core-side fix (per ADR/0024 §7 precedent — Wedge-001's friction log produced no core changes; Wedge-002's surfaced bundle changes that landed in subsequent SCN arcs).

## §0 — What this ADR does

Wedge-003 is the **inflection-point spike**: first time AIADRA's design composes into real mechanical authoring work. The schema surface ([ADR/0029](0029-part-authoring-scn.md) + v0.28.0 bundle) and the Python API surface ([arc 20260601-1](../Discussions/20260601/20260601-1/CLOSED.md) + `aiadra-core` 0.11.0) are both landed. Wedge-003 is the proof those surfaces compose into a real loop.

This ADR pins WHAT the spike does, WHERE it lives, WHAT kernel it uses, WHAT it explicitly does NOT cover. The implementation arc (next) writes the code + runs it end-to-end + populates the friction log.

**Three Wedge-001/002 precedents preserved**:
- Spike directory at `spikes/wedge-NNN/` (top-level AIADRA repo, not nested under `aiadra-core/`).
- Throwaway-spike posture per [ADR/0023 §4](0023-wedge-spike-scope-and-runtime.md) — spike code is exploratory; production gets a clean slate.
- Scope-first ADR → impl-in-next-arc → friction log → close cadence per [ADR/0024](0024-wedge-002-spike-scope.md).

**One ecosystem-package first**: Wedge-003 is the FIRST AIADRA spike to install as an entry-point-declaring distribution discovered by `aiadra-core` at runtime. Per ADR/0028 D11 + arc 20260601-1 D5 two-pass discovery, this is the first time the boundary is exercised against a REAL installed package (not monkeypatched tests).

## Decisions

### D1. Scope-only ADR; implementation in separate follow-up arc

Per [ADR/0023 §1](0023-wedge-spike-scope-and-runtime.md) + [ADR/0024 Decision §1](0024-wedge-002-spike-scope.md) precedent. ADR/0030 pins scope; implementation arc (next) writes:
- `spikes/wedge-003/` directory per D2
- 4 Native Engine handlers per D5
- Toy deterministic synthetic kernel per D3
- ~20 integration tests per D12
- Friction log per D11

Codex review of scope BEFORE code surfaces scope errors cheaply; friction log informs subsequent refinement ADRs + the first `aiadra-mechanical` production-package arc.

### D2. Location — `spikes/wedge-003/`; engine_id `mechanical_spike` (Codex1 B2 R1 absorption)

Spike directory: `d:\VSCode-Work\AIADRA\spikes\wedge-003\` per Wedge-001 + Wedge-002 precedent. Own `pyproject.toml`; installable via `pip install -e ./spikes/wedge-003/` into the AIADRA venv that has `aiadra-core` installed.

**Codex1 B2 R1 absorption** (arc 20260601-2): engine_id is **`mechanical_spike`**, NOT `mechanical`. Operation kinds use the `mechanical_spike.*` namespace. Rationale:
- Per ADR/0028 D2 invariant #5 + arc 20260601-1 two-pass discovery: duplicate engine_id across distributions REJECTS ALL colliding engines.
- If Wedge-003's spike package declared engine_id `mechanical` AND the future production `aiadra-mechanical` package also declares engine_id `mechanical`, a developer who leaves the spike installed when the production package arrives would make BOTH unavailable — silent footgun in the exact boundary this spike validates.
- Using `mechanical_spike` keeps the production `mechanical.*` namespace clean for the future `aiadra-mechanical` package; spike + production can coexist in the same venv without colliding.

```toml
# spikes/wedge-003/pyproject.toml
[project]
name = "aiadra-mechanical-spike"
version = "0.0.1"
dependencies = ["aiadra-core>=0.11.0"]

[project.entry-points."aiadra.native_engines"]
mechanical_spike = "aiadra_mechanical_spike:register"
```

Directory layout (matches Wedge-001 + 002 + the entry-point structure):
```
spikes/wedge-003/
├── pyproject.toml                          # declares aiadra.native_engines entry-point mechanical_spike
├── README.md
├── FRICTION_LOG.md                         # populated during impl arc
├── aiadra_mechanical_spike/
│   ├── __init__.py                         # def register(registrar): ...
│   ├── handlers.py                         # 4 Native Engine handlers
│   ├── kernel.py                           # toy deterministic geometry kernel
│   └── adapter_payload.py                  # sketch primitive + extrude payload shapes
├── fixtures/                               # AIADRA workspace fixtures (carry-over pattern)
├── outputs/                                # workspace + vault outputs at runtime
├── run_demo.sh
├── test_wedge_003_end_to_end.py            # ~12 tests
├── test_wedge_003_negative_discipline.py   # ~8 negative tests
└── test_profile_negative.py                # carries forward Wedge-001 pattern
```

The package name `aiadra-mechanical-spike` (distinct from future production `aiadra-mechanical`) reinforces the throwaway-spike posture per ADR/0023 §4. Naming distinctness across BOTH `[project] name` AND entry-point `engine_id` makes the boundary collision-proof.

### D3. Kernel — toy deterministic synthetic kernel (real OCCT deferred)

Per [ADR/0028 D15 item 1](0028-native-engine-implementation-contract.md): specific Python binding choice for OCCT (pythonocc-core vs OCP) is deferred to the first `aiadra-mechanical` production-package arc. For Wedge-003 (the SPIKE), the kernel choice should isolate the test scope to the AIADRA boundary — NOT the kernel-integration boundary.

```python
# spikes/wedge-003/aiadra_mechanical_spike/kernel.py
import json

def compute_geometry(features: list[dict]) -> bytes:
    """Deterministic synthetic geometry generator.

    Takes a list of feature records; produces a reproducible byte blob
    representing 'this combination of features evaluated together'. sha256
    of bytes becomes the vault_ref per ADR/0005 D7.

    Reproducible across machines + runs because it's a pure
    canonical-JSON-sort + UTF-8 encode. No floating-point or kernel-state
    nondeterminism. For the spike, the 'geometry' is just the serialized
    recipe — there is no BREP / mesh / surface to render.

    This is fine: Wedge-003's purpose is to validate the AIADRA loop
    (schema + events + provenance + discovery + dispatch + binding scan
    + cascade integrity + release), NOT to validate OCCT bindings or
    BREP semantics.
    """
    canonical = json.dumps(
        [{"id": f["id"], "type": f["feature_type"], "payload": f["adapter_payload"]}
         for f in features],
        sort_keys=True,
    )
    return canonical.encode("utf-8")
```

**Trade-offs honored**:
- ✅ No platform-specific deps (OCCT C++ libs + pythonocc-core/OCP binding system-install complexity all avoided)
- ✅ Deterministic content hashes across machines (essential for content-addressed Vault per ADR/0001 §3)
- ✅ Spike-appropriate fidelity — validates the loop, not the kernel
- ✅ Defers the Python-binding choice (pythonocc-core vs OCP) to `aiadra-mechanical` production arc per ADR/0028 D15 item 1
- ❌ Hides OCCT-class friction (BREP serialization, kernel tolerance, long-running recompute/cancellation, platform-specific packaging) — explicitly named in friction log's lessons-by-omission section per D11 (Codex1 N1 absorption)
- ❌ Doesn't crash like real OCCT can — synthetic kernel-failure path explicit in D9 + D12 test #17

### D4. The 5-step authoring loop (smallest viable)

Per ADR/0027 D17 candidate framing (7 steps), collapsed to 5 after consolidating "geometry recompute" into the parameter-adjust Transaction per Q8.

1. **Create Part** via BUILT-IN `propose(workspace, kind="create_part", params={"number": "P-000001", "name": "BracketSpike"})` — produces empty Part (no features / geometry_refs initially). Native Engine NOT involved at Part creation per ADR/0027 D5 (Part-as-an-Object is `aiadra-core` concern; what's IN a Part is Native Engine concern).

2. **Add sketch feature** via `propose(workspace, kind="mechanical_spike.add_sketch_feature", params={"part_number": "P-000001", "primitives": [{"type": "rectangle", "x_mm": 0, "y_mm": 0, "width_mm": 20, "height_mm": 10}, {"type": "circle", "cx_mm": 5, "cy_mm": 5, "radius_mm": 2}]})` — engine handler allocates `feat_0001`; builds feature_record (`feature_type="sketch"`, adapter_payload contains primitives, `fact_provenance.category="ai_proposal"` via actor=agent); computes geometry via toy kernel; stages Vault bytes via `context.stage_vault_bytes()`; builds geometry_ref_record (`geom_0001`, role=authoring_geometry, vault_ref=content_hash, derived_from_feature_ids=[`feat_0001`], fact_provenance.category="computed_result", derived_from=[`feature:feat_0001`] per ADR/0029 D6 STRICT set-equality); stages updated Part sidecar; emits `part_changed` via `context.emit_event("part_changed", payload={...})`.

3. **Add extrude feature consuming sketch** via `propose(workspace, kind="mechanical_spike.add_extrude_feature", params={"part_number": "P-000001", "sketch_feature_id": "feat_0001", "depth_mm": 5, "direction": "z+"})` — engine handler allocates `feat_0002`; builds feature_record (`feature_type="extrude"`, `depends_on_feature_ids=["feat_0001"]` per ADR/0029 D9 DAG, adapter_payload={depth_mm: 5, direction: "z+", sketch_ref: "feat_0001"}, fact_provenance.category="ai_proposal"); reads sketch via `context.load_sidecar(part_uuid)` (draft-aware); computes geometry via toy kernel; stages new Vault bytes; **REPLACES** `geom_0001` with new computed geometry (extruded body — supersedes sketch-only geometry; new derived_from_feature_ids=[`feat_0001`, `feat_0002`]) via `geometry_ref_delta.updated=[{id: "geom_0001", new_record: {...}}]` per Q9 subtree-output decision; emits `part_changed`.

4. **Adjust extrude depth parameter** via `propose(workspace, kind="mechanical_spike.adjust_feature_parameter", params={"part_number": "P-000001", "feature_id": "feat_0002", "parameter_name": "depth_mm", "new_value": 8})` — engine handler updates feat_0002 sidecar (draft-aware copy); recomputes geometry via toy kernel; stages new Vault bytes; emits SINGLE `part_changed` event with BOTH `feature_delta.updated=[{id: "feat_0002", new_record: <updated extrude>}]` AND `geometry_ref_delta.updated=[{id: "geom_0001", new_record: <updated authoring_geometry>}]`. This is the canonical "parameter change → geometry recompute" loop.

5. **Release Part as Revision** via `propose(workspace, kind="release", params={"object_numbers": ["P-000001"], "final_stage": True})` — Codex1 B3 R1 absorption: param name is `object_numbers` (matches `_propose_release` contract), NOT `objects`. Built-in path; freezes Part sidecar into Revision; emits `part_released`; updates Reservation `current_revision_id` + appends to `released_revision_ids[]`; validates final-stage release graph.

**Loop tested in TWO modes**:
- **Mode A** (separate Transactions): steps 1-5 each commit independently. Tests committed state composes correctly across Transactions.
- **Mode B** (composed via `modify`): step 1 commits; then step 2 propose + step 3 modify + step 4 modify all compose into ONE draft; single commit; then step 5 commit. Tests `_begin_or_extend_draft` + draft-aware reads end-to-end + `emit_event` event-id allocation across composed engine ops. **Mode B is non-decorative** (Codex1 N2 absorption arc 20260601-2): it's the only part of the scope that proves Native Engine handlers + draft-aware reads + staged sidecars + staged vault bytes + event_id allocation compose in one Transaction.

### D5. Feature catalog — 4 operations (Codex1 N3 R1 absorption: drop `recompute_geometry`)

```python
def register(registrar):
    registrar.add_operation("mechanical_spike.add_sketch_feature", _handle_add_sketch_feature)
    registrar.add_operation("mechanical_spike.add_extrude_feature", _handle_add_extrude_feature)
    registrar.add_operation("mechanical_spike.adjust_feature_parameter", _handle_adjust_feature_parameter)
    registrar.add_operation("mechanical_spike.remove_feature", _handle_remove_feature)
```

**Codex1 N3 R1 absorption** (arc 20260601-2): explicit `mechanical_spike.recompute_geometry` operation is DROPPED. Codex1 N3 noted it would need a crisp purpose if kept ("rebuild geometry from current feature records without changing feature records; event = `geometry_ref_delta.updated` only"). The spike's authoring loop doesn't need explicit recompute — every parameter-adjust automatically triggers recompute as part of the same Transaction (D4 step 4). If future production engines need explicit recompute semantics (e.g., kernel version upgrade triggering full-Part recompute), it lands in `aiadra-mechanical` v0.0.1+ with crisp semantics.

4 operations is the minimum:
- 2 add ops (sketch + extrude) exercise feature-type catalog + DAG dependency
- 1 adjust op exercises parameter-change + recompute loop (Codex1 B2 from arc 1 distinct event_ids across composed ops)
- 1 remove op enables cascade-rejection negative test (D8)

Sketch primitives schema in `adapter_payload` (opaque to aiadra-core per ADR/0029 D7):
```json
{
  "primitives": [
    {"type": "rectangle", "x_mm": ..., "y_mm": ..., "width_mm": ..., "height_mm": ...},
    {"type": "circle", "cx_mm": ..., "cy_mm": ..., "radius_mm": ...},
    {"type": "line", "x1_mm": ..., "y1_mm": ..., "x2_mm": ..., "y2_mm": ...}
  ]
}
```

`adapter_schema_version` per [ADR/0005 §9](0005-object-type-part.md) + [ADR/0027 D18](0027-aiad-positioning-and-native-engine-posture.md) starts at `"0.1.0"`.

### D6. Provenance discipline exercised end-to-end

Per ADR/0028 D8 + ADR/0029 D6:
- **Caller-supplied (feature records)**: every feature carries `fact_provenance.category = "ai_proposal"` (spike simulates AI agent via actor=agent at Ring 2 entry; `context.actor == "agent"` at handler level).
- **Engine-computed (geometry_ref records)**: every geometry_ref carries `fact_provenance.category = "computed_result"` + `derived_from = ["feature:<id>", ...]` STRICT set-equality with `derived_from_feature_ids` per ADR/0029 D6 R3 absorption from arc 13.

Negative tests exercising the boundary (D8 + D12):
- Engine emits feature with `category="computed_result"` → fold rejects (ADR/0029 schema-level enum `["ai_proposal", "human_input"]` on feature)
- Engine emits geometry_ref with `category="ai_proposal"` → fold rejects
- Engine emits geometry_ref with extras in `fact_provenance.derived_from` not in `derived_from_feature_ids` → fold rejects (ADR/0029 D6 STRICT set-equality)
- Engine emits geometry_ref with cross-Object form `<uuid>:feature:<id>` → fold rejects (ADR/0029 D14 item 6 + Codex2 B2 R3 from arc 13)

### D7. Validation hooks DEFERRED

Wedge-003 does NOT exercise `add_pre_validate_hook` / `add_post_validate_hook`. Hooks are an ADVANCED feature for engines that need cross-record invariants beyond what schema + fold can express. The smallest viable mechanical authoring loop doesn't need them. Absence noted in friction log per D11.

Hook surface itself is fully tested in arc 20260601-1's `test_native_engine_api.py` (arity adaptation + reject-loud + NativeEngineContext passing); Wedge-003 doesn't re-test the mechanism.

### D8. Cascade-rejection negative test

Per ADR/0029 D12 + Codex2 R3 from arc 13: removing a feature that's still referenced by a surviving record cascade-rejects unless the dependent removals are batched.

After Mode A step 3 (Part has feat_0001 + feat_0002 + geom_0001 where feat_0002 depends_on [feat_0001] AND geom_0001 derived_from_feature_ids=[feat_0001, feat_0002]):

- **Negative test**: `propose(workspace, kind="mechanical_spike.remove_feature", params={"part_number": "P-000001", "feature_ids": ["feat_0001"]})` → engine emits `part_changed.feature_delta.removed=["feat_0001"]`; fold cascade-rejects with `FoldInconsistencyError` because feat_0002 still has depends_on_feature_ids=[feat_0001] AND geom_0001 still has derived_from_feature_ids referencing feat_0001.
- **Happy test (batched-cascade)**: `propose(workspace, kind="mechanical_spike.remove_feature", params={"part_number": "P-000001", "feature_ids": ["feat_0001", "feat_0002"]})` → engine emits BOTH `feature_delta.removed=["feat_0001", "feat_0002"]` AND `geometry_ref_delta.removed=["geom_0001"]` in single `part_changed`; cascade-accepts because no surviving record references any removed id.

### D9. B6 binding-scan negative test (Codex1 B1 R1 absorption — bind UNRELEASED current revision)

**Codex1 B1 R1 absorption** (arc 20260601-2): the original D9 was technically wrong. Per Phase 1 release model + arc 9 Phase C reservation model: release writes the current revision as a frozen Revision, appends that id to `released_revision_ids[]`, AND allocates a fresh `current_revision_id` for the next mutable working state. The B6 rule deliberately ignores already-released fixed endpoints; it blocks mutations only when the Object's UNRELEASED `current_revision_id` is fixed-bound.

The correct negative test binds the CURRENT UNRELEASED revision, then attempts the mutation:

1. Create Part + featureful sidecar via Mode A steps 1-3 (creates Part P-000001 with current unreleased `current_revision_id = <fresh-uuid>`; no release yet).
2. Create the minimal TestExecution + TestProcedure fixture needed for `link_executed_on` (carry-over pattern from Wedge-002 fixtures per ADR/0024 §6).
3. Author `link_executed_on` with the target endpoint pinning the Part's CURRENT UNRELEASED revision_id (Fixed binding; ADR/0022 §6 execution-instance default).
4. Attempt `propose(workspace, kind="mechanical_spike.adjust_feature_parameter", ...)` → expect `RevisionBindingError` raised at the Draft boundary (Codex2 N1 R2 polish arc 20260601-2: `RevisionBindingError` fires at `draft.validate()` / `draft.commit()` per arc 9 Phase C Codex2 B1 R3 proposed-state B6 scan; `propose()` ALONE does not raise unless the Native Engine handler invokes validation explicitly via a `pre_validate_hook`. The negative test asserts the error at the validate/commit step where the dual-fold discipline fires).

This negative test confirms three things at once:
- Native Engine `mechanical_spike.adjust_feature_parameter` correctly emits `part_changed` (proving the schema integration in v0.28.0).
- `part_changed` correctly participates in the B6 mutation-after-binding scan (proving arc 20260601-1 B3 R1 absorption is live — the binding-classifier extension actually fires for Native Engine emissions).
- The mutation prohibition fires at the Draft boundary (BEFORE commit), not after (proving Phase C arc 9 R3 dual-fold discipline holds for Native Engine ops).

This negative test does NOT involve a release step at all. Skipping release simplifies the fixture machinery + accurately tests the B6 rule against unreleased state.

### D10. D16 string-kind dispatch exercised implicitly

Every `mechanical_spike.*` operation is a Native Engine kind that does NOT exist in `_PROPOSE_DISPATCH`. Dispatch goes through `_resolve_propose_handler` (per arc 20260601-1 D6) → engine discovery → `_native_engine_dispatch_adapter` → engine handler. This is the entire D16 path exercised end-to-end:
- `TransactionDraft.kind` accepts `"mechanical_spike.add_sketch_feature"` (str) via D16 generalization
- Audit + commit-message use `self.kind` directly without `.value`
- Failure trees preserve full namespaced kind via `details` dict

No special test required — every Mode A and Mode B step exercises this.

### D11. Friction log — `spikes/wedge-003/FRICTION_LOG.md`

First-class output of the impl arc per ADR/0023 + ADR/0024 precedent. Sections:
1. Build / install / discovery friction (does `pip install -e ./spikes/wedge-003/` + `refresh_native_engines()` + `native_engine_status()` work cleanly?)
2. Native Engine API ergonomics (NativeEngineRegistrar / NativeEngineContext — too verbose? missing helpers?)
3. Schema ergonomics (atomic delta rules / DAG / cascade / provenance set-equality — burdensome to engine implementer?)
4. Composability (Mode A vs Mode B — did `modify()` + draft-aware reads work as expected? `emit_event` vs `make_event` — was the docstring guidance per Codex2 N1 arc 20260601-1 sufficient?)
5. Vault Adapter ergonomics (Wedge-002 had spike-grade local-FS Vault; does Wedge-003 reuse or extend?)
6. Cache freshness implementation cost (does ADR/0027 D6 feel implementable; what keying choice did the spike make?)
7. Provenance discipline burden (every record needs `fact_provenance`; is that the right granularity?)
8. Release graph interactions (any unexpected release-time validators fire on featureful Parts?)
9. Cross-spike friction comparison vs Wedge-001 + Wedge-002 per ADR/0024 Decision §9 pattern
10. **Lessons by omission** (Codex1 N1 R1 absorption arc 20260601-2): explicitly name OCCT-class friction the toy kernel CANNOT surface:
    - BREP serialization quirks (CASCADE / OCCT-specific binary format gotchas)
    - Kernel tolerance behavior (floating-point comparison thresholds; near-miss intersection cases)
    - Long-running recompute / cancellation (real BREP ops on complex parts can take minutes; what's the cancellation story?)
    - Platform-specific dependency packaging (pythonocc-core + OCP both require system OCCT libs; cross-platform CI gets complicated)
    These ARE the friction items the first `aiadra-mechanical` production-package arc will surface. Documenting absence here flags them.

The friction log feeds:
- Follow-up refinement ADRs (if Codex review or implementation surface ergonomic problems)
- The FIRST `aiadra-mechanical` v0.0.1 scope ADR (which IS the next planning step after Wedge-003 lands)

### D12. End-to-end test surface — ~20 tests

| Test | Mode | Validates |
|---|---|---|
| `test_install_and_discover_via_entry_point` | one-time | `pip install -e ./spikes/wedge-003/` + `refresh_native_engines()` + `native_engine_status()` returns `mechanical_spike` loaded |
| `test_propose_kinds_includes_mechanical_spike_operations` | one-time | combined kind set includes all 4 |
| `test_modify_kinds_includes_mechanical_spike_operations` | one-time | excludes init/release |
| `test_5_step_authoring_loop_mode_a` | A | each step commits independently; final Part has 2 features + 1 geometry_ref + released revision |
| `test_5_step_authoring_loop_mode_b` | B | steps 2-4 composed via `modify()`; single commit; same final state as Mode A |
| `test_mode_b_event_ids_distinct` | B | Codex1 B2 from arc 1: 3 composed engine ops produce 3 distinct evt_NNNN ids (proves `emit_event` per Codex2 N1 from arc 1) |
| `test_part_changed_event_envelope_conforms_to_base_schema` | A | Codex1 B1 from arc 13: event_type + actor + timestamp + transaction_id + payload all per base schema |
| `test_part_sidecar_uses_feature_and_geometry_ref_namespaces_no_colons` | A | Codex1 B2 from arc 13: serialized keys are `feature` / `geometry_ref` (no colons) |
| `test_feature_dependency_dag_acyclicity_holds` | A | extrude.depends_on_feature_ids=[sketch.id]; Kahn's algorithm doesn't trigger cycle |
| `test_geometry_ref_provenance_strict_set_equality_holds` | A | geometry_ref.derived_from_feature_ids = parsed feature ids from fact_provenance.derived_from per ADR/0029 D6 R3 |
| `test_engine_computed_provenance_blocks_human_input_attestation` | A | NEGATIVE: synthetic handler emits feature with category="human_input" while actor=agent → fold rejects |
| `test_cascade_rejects_remove_with_dependent_feature` | A | NEGATIVE per D8: remove feat_0001 while feat_0002 depends on it → `FoldInconsistencyError` |
| `test_cascade_accepts_batched_dependent_remove` | A | D8 happy: remove feat_0001 + feat_0002 + geom_0001 batched → succeeds |
| `test_b6_binding_scan_catches_mechanical_spike_mutation_against_unreleased_bound_revision` | A | NEGATIVE per D9 + arc 1 B3 R1 + Codex1 B1 R1 arc 2 + Codex2 N1 R2 arc 2: bind UNRELEASED current_revision_id via execution-instance + adjust_feature_parameter; assert `RevisionBindingError` at `draft.validate()` / `draft.commit()` (NOT at `propose()` alone, per arc 9 Phase C Codex2 B1 R3 proposed-state B6 scan timing) |
| `test_provenance_blocks_cross_object_address_form` | A | NEGATIVE per ADR/0029 D6 + Codex2 R3 from arc 13: handler emits fact_provenance.derived_from=["<uuid>:feature:feat_0001"] → fold rejects |
| `test_canonical_unit_enforced_on_feature_parameters` | A | feature.parameters[].unit MUST be from canonical_unit enum (mm/m/deg/rad/...) per ADR/0029 D10 |
| `test_native_engine_kernel_error_wraps_kernel_exception` | A | synthetic handler raises ZeroDivisionError → adapter wraps as `NativeEngineKernelError` + emits audit per arc 1 Q3 |
| `test_engine_not_available_for_never_installed_engine_id` | one-time | **Codex1 N4 R1 absorption arc 20260601-2**: tests `propose(kind="totally_synthetic_engine_id.foo")` → `EngineNotAvailableError`; uses a NEVER-INSTALLED engine_id (NOT uninstall of the spike — preserves shared dev venv state) |
| `test_release_part_with_features_and_geometry_refs_succeeds` | A | step 5: Revision record includes feature + geometry_ref snapshots; manifest validates |
| `test_native_engine_status_reflects_loaded_state` | one-time | reflects loaded `mechanical_spike` engine with 4 operations |

20 tests covering all key paths. Plus `test_profile_negative.py` carried forward from Wedge-001/002 precedent.

### D13. Cache freshness — toy kernel uses content-hash-keyed cache; pattern documented in friction log

Per ADR/0027 D6 cache freshness invariant: toy kernel caches geometry computations keyed by `sha256(canonical_json(features))`. Before emitting a `geometry_ref`, the kernel verifies the cache key matches the current inputs; if mismatch, recompute.

This is over-engineered for a toy kernel (the kernel itself is deterministic so caching is a microoptimization), but the PATTERN-EXERCISE is the point — proves the cache freshness check is implementable in <30 LOC. Friction log section 6 documents whether the pattern feels right for real OCCT-class engines.

### D14. Explicit out of scope (carry forward + add)

1. **Real OCCT integration** — per ADR/0028 D15 item 1; defer to first `aiadra-mechanical` production-package arc.
2. **Multi-Part assemblies** — Wedge-001 had them; Wedge-003 focuses on single-Part authoring depth, not multi-Part composition.
3. **Constraint solving** — sketches stay opaque per ADR/0029 D7; no first-class constraint primitives.
4. **Mate satisfaction** — no `mated_to` in spike; deferred to future spike or production arc.
5. **Cross-Part geometry derivation** (`derived_geometry_from`) — last unfilled relationship type per ADR/0009 §3; awaits multi-Part Native Engine work.
6. **CLI for Native Engine operations** — per ADR/0028 D11 + arc 20260601-1 D11; engine packages ship their own CLI; spike runs via Python API.
7. **UI / viewport** — per ADR/0028 D13.
8. **Multi-process / parallel engine instances** — per ADR/0028 D6.
9. **KiCad / electrical engine specifics** — `aiadra-electrical` is a separate strand.
10. **DV / procurement Data Adapter specifics** — per ADR/0027 D12 Layer 5 Data Adapter category; future arc.
11. **Validation hooks** — per D7; defer to a future engine that needs them.
12. **`aiadra-mechanical` production package** — Wedge-003 spike is NOT the production package; it's the proof. Production package follows in a later arc informed by Wedge-003's friction log.
13. **Rollback path expanded testing** — kernel-failure audit emission is included per Codex Q5 R1 arc 20260601-2 ack (Codex1 N1+N2 from arc 1 satisfied), but explicit rollback() ergonomics exercise not in scope to avoid crowding the main loop.
14. **`mechanical_spike.recompute_geometry` operation** (Codex1 N3 R1 absorption arc 20260601-2): dropped from the 4-op catalog. If a future production engine needs explicit recompute semantics, it lands in `aiadra-mechanical` v0.0.1+ with crisp definition.
15. **Destructive package-uninstall test scenarios** (Codex1 N4 R1 absorption arc 20260601-2): never-installed engine_id pattern used instead per D12 test #18; preserves shared dev venv state.

### D15. Sequencing after Wedge-003 scope ADR

1. **This ADR/0030 (landed at arc-close)** — Wedge-003 scope.
2. **Wedge-003 implementation arc** (next; would be arc `20260601-3`) — writes the spike code; runs the 20-test surface; populates the friction log per D11.
3. **Friction-log review arc** (small) — Petre + Claude review the friction log; surface any refinement ADRs needed before `aiadra-mechanical` v0.0.1.
4. **(Optional) Refinement ADRs** — any per-issue ADRs surfacing from friction log review (e.g., NativeEngineContext ergonomics polish; new opt-in helpers).
5. **`aiadra-mechanical` v0.0.1 scope ADR** — clean-slate production package; first arc to write SHIPPABLE Native Engine code (vs throwaway spike).
6. **`aiadra-mechanical` v0.0.1 implementation arc** — same pattern as Wedge-001/002 ADR + impl arcs.
7. **`aiadra-mechanical` later releases** — multi-arc strand; horizon = years per ADR/0027 D17 framing.

### D16. Coherence Checklist walk

11 items:

| Item | Verdict | Note |
|---|---|---|
| List-addressability | PASS | Feature + geometry_ref records carry stable list-addressable ids (`feat_NNNN` / `geom_NNNN`) per ADR/0029 D2 + S0 commitment 7. Sketch primitives live inside opaque `adapter_payload` per ADR/0029 D7; aiadra-core does NOT enforce list-addressability on primitive records — engine internal concern (Codex2 N2 R2 polish arc 20260601-2). |
| Released cross-Object geometry | N/A | Single-Part spike; no cross-Object geometric refs. |
| Engineering-structure cross-project | N/A | No `composed_of` / `mated_to` change. |
| Binding ownership | PASS (with Codex1 B1 R1 absorption) | D9 negative test binds CURRENT UNRELEASED revision per the actual B6 rule; tests existing Fixed-execution-instance binding ownership doesn't catch released-only references. |
| Identity cross-check | N/A | No endpoint `revision_id` cross-check change. |
| Released geometric satisfaction | N/A | No `mated_to` in spike. |
| **Canonical units at fact level** | PASS — LOAD-BEARING | feature.parameters[].unit uses canonical_unit enum per ADR/0029 D10. Sketch primitives use `_mm` / `_deg` field-name suffix per D5. |
| Quaternion normalization | N/A (deferred) | Sketches + extrudes don't carry first-class transforms in v0.28.0; per ADR/0029 D11 deferred. |
| **AIADRA Core hosts nothing** | PASS — TIGHTENED | Spike IS the first ecosystem package living outside `aiadra-core` and discovered via entry-point. Codex1 B2 R1 absorption: engine_id `mechanical_spike` prevents future production collision; spike + production can coexist in same venv. No service introduced. |
| Execution-record cardinality invariants | N/A | The B6 negative-test fixture per D9 creates TestExecution + TestProcedure records but is testing the B6 scan, not execution cardinality. |
| **Native engine boundary** | PASS — TIGHTENED | Spike IS the boundary in action. Engine handlers stay in `aiadra-mechanical-spike` package; aiadra-core does not import them. Engine emits `part_changed` via `emit_event` envelope; provenance discipline + cascade + DAG all enforced at the boundary. |

No new Coherence Checklist item proposed.

## Supersession + amendment register

**No supersessions.** ADR/0023 + ADR/0024 Wedge scope-ADR conventions preserved verbatim. ADR/0027 D17 Wedge-003 gating clause fulfilled (both pre-conditions in place: ADR/0029 schema + arc 20260601-1 API). ADR/0028 D14 step 4 sequencing operationalized.

**No multi-document amendments.** Manifesto / ArchitectureOverview / Glossary unchanged. Glossary may gain entries for `mechanical_spike` engine + the spike package in a future polish arc — flagged for `aiadra-mechanical` v0.0.1 arc to take up.

## Consequences

- **No bundle bump.** Bundle stays v0.28.0; scope-only ADR.
- **No `aiadra-core` version bump in this arc.** The Wedge-003 impl arc may bump aiadra-core ONLY if the spike surfaces friction requiring a core-side fix.
- **First ecosystem package operationally tested end-to-end.** Wedge-003 is the first time `aiadra-core`'s entry-point discovery (arc 20260601-1 D5 two-pass) runs against a REAL installed distribution rather than monkeypatched tests. Surfaces real install / refresh / cross-distribution-collision friction.
- **Codex1 B1 R1 absorption** (arc 20260601-2): D9 B6 negative test correctly binds UNRELEASED current revision (was incorrectly described as "after release, bind the released revision" — wrong per Phase 1 release model). Tests existing B6 rule against the actual fixed-bound state it protects.
- **Codex1 B2 R1 absorption**: engine_id `mechanical_spike` (NOT `mechanical`) prevents future duplicate-engine_id collision with production `aiadra-mechanical` package. Spike + production can coexist in same venv. Boundary that this spike validates is itself collision-proof.
- **Codex1 B3 R1 absorption**: release example uses `params["object_numbers"]` (matches `_propose_release` contract), not the incorrect `params["objects"]`.
- **Codex1 N3 R1 absorption**: 4-op catalog (sketch + extrude + adjust + remove) without `recompute_geometry`. Simpler scope; if explicit recompute needed in production, lands with crisp semantics in `aiadra-mechanical` v0.0.1+.
- **Codex1 N4 R1 absorption**: missing-engine test uses never-installed engine_id (NOT destructive uninstall); preserves shared dev venv state.
- **Codex1 N1 R1 absorption**: friction log includes a "lessons by omission" section explicitly naming OCCT-class friction the toy kernel cannot surface — flagged for `aiadra-mechanical` v0.0.1 arc.
- **First arc that designs real mechanical authoring work** — even at spike scale. ADR/0027 + ADR/0028 + ADR/0029 + arc 20260601-1 are now load-bearing under real-engine pressure. If the loop works, the entire Ring 3 design holds; if it breaks, refinement ADRs land between Wedge-003 impl and `aiadra-mechanical` v0.0.1.
- **Friction log is the load-bearing output**. The impl arc produces code + tests + friction log; the friction log is the input to the next arc's planning. Per ADR/0024's first-scope-ADR-informed-by-prior-friction-log pattern: Wedge-003's friction log will inform `aiadra-mechanical` v0.0.1 scope.

## Alternatives rejected

- **(i) Real OCCT kernel in spike** (pythonocc-core or OCP). Rejected per D3 + Codex1 Q1 ack — isolates spike to AIADRA boundary; defers binding choice per ADR/0028 D15 item 1.
- **(ii) Wedge-003 inside `aiadra-core/spikes/`** (instead of top-level `spikes/wedge-003/`). Rejected per D2 + ADR/0023 §6 precedent — Wedge-001 + Wedge-002 live at `spikes/wedge-NNN/` (top-level AIADRA repo).
- **(iii) Engine_id `mechanical`** (matching production naming). Rejected per Codex1 B2 R1 — would create future duplicate-engine_id collision with production `aiadra-mechanical` package. `mechanical_spike` keeps the production namespace clean.
- **(iv) Package name `aiadra-mechanical` v0.0.1** (naming continuity). Rejected per D2 + Codex1 Q3 ack — throwaway-spike posture per ADR/0023 §4; production package gets a clean slate to avoid spike's compromises becoming production baseline.
- **(v) Co-landed scope + impl in single arc**. Rejected per D1 + ADR/0023 / ADR/0024 precedent — scope-first ADR + separate impl arc surfaces scope errors cheaply and isolates the friction-log production.
- **(vi) 5-op catalog including `recompute_geometry`**. Rejected per Codex1 N3 R1 — explicit recompute lacks crisp purpose in spike scope; 4 ops sufficient.
- **(vii) Destructive uninstall test for engine availability**. Rejected per Codex1 N4 R1 — never-installed engine_id pattern preserves shared dev venv state.
- **(viii) Original D9 B6 negative test** (bind released revision after release). Rejected per Codex1 B1 R1 — wrong revision state; B6 ignores released endpoints. Corrected to bind unreleased current revision.
- **(ix) `params["objects"]` for release**. Rejected per Codex1 B3 R1 — wrong contract; actual parameter name is `object_numbers`.
- **(x) Validation hooks in spike scope**. Rejected per D7 — advanced feature; smallest viable doesn't need; absence noted in friction log.
- **(xi) Mode A only** (skip composed-via-modify Mode B). Rejected per Codex1 N2 — Mode B is the only part of the scope that proves the composability surface end-to-end.
- **(xii) Subtree-output replacement** vs per-feature geometry_ref creation. Adopted per Q9 ack (subtree-output: extrude REPLACES sketch's geom_ref; matches real CAD where intermediate sketch is not rendered when extrude consumes it).

## References

- [ADR/0023 — Wedge spike scope + runtime](0023-wedge-spike-scope-and-runtime.md) — Wedge framework; throwaway posture; repo layout convention; deferral patterns.
- [ADR/0024 — Wedge-002 spike scope](0024-wedge-002-spike-scope.md) — scope-first ADR + impl-in-next-arc + friction log precedent; first scope ADR informed by prior friction log.
- [ADR/0027 D17](0027-aiad-positioning-and-native-engine-posture.md) — Wedge-003 gating + candidate authoring loop sketch.
- [ADR/0028 D11 + D13 + D14 step 4 + D15](0028-native-engine-implementation-contract.md) — ecosystem-package boundary; OCCT binding deferral; sequencing.
- [ADR/0029](0029-part-authoring-scn.md) — `part_changed` event + feature/geometry_ref namespaces + atomic delta rules + STRICT set-equality + canonical address form + DAG acyclicity + cascade integrity.
- [Arc 20260601-1](../Discussions/20260601/20260601-1/CLOSED.md) — Native Engine API surface (`NativeEngineRegistrar` + `NativeEngineContext` + 3 exception classes + D16 generalization + entry-point discovery + dispatch lookup); Codex2 N2 ("first real Native Engine arc should add a schema-valid end-to-end native operation that reaches `commit()`") is what Wedge-003 satisfies.
- [ADR/0005 §9](0005-object-type-part.md) — adapter shell (`engine` + `adapter_schema_version` + `engine_artifact_ref` + `stable_engine_object_id`) preserved per ADR/0027 D18; spike's adapter_payload + adapter_schema_version honor this.
- [ADR/0001 §3](0001-storage-substrate.md) — content-addressed Vault per ADR/0023 §10; spike inherits Wedge-002's spike-grade local-FS Vault Adapter pattern.
- [Manifesto P11](../Manifesto.md) — AIADRA Core hosts nothing; spike is local + package-based.
- [Glossary "Spike"](../Glossary.md) — throwaway-spike definition.
