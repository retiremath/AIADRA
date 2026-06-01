# ADR/0028 — Native Engine Implementation contract

## Frontmatter

- **Status:** Accepted — 2026-05-31 (arc 20260531-12; three-round convergence Claude1 + Codex1 / Claude2 + Codex2 / Claude3 + Codex3).
- **Operationalizes:** [ADR/0027 D6 + D10 + D11 + D17 + D18](0027-aiad-positioning-and-native-engine-posture.md) — Native Engine posture pinned by ADR/0027; this ADR pins the Python API + lifecycle contract.
- **Sequencing per ADR/0027 D10**: this ADR is step (a). Next: (b) Part authoring SCN ADR/0029 — `part_changed` event with `feature_delta` + `geometry_ref_delta`; bundle v0.27.0 → v0.28.0 MINOR additive; **PRE-CONDITION for `aiadra-mechanical` Wedge-003 implementation**. Then (c) Wedge-003 scope ADR. Then (d) `aiadra-mechanical` ecosystem-package implementation.
- **No schema bundle bump.** Bundle stays v0.27.0. This ADR is positioning-adjacent — pins the contract; concrete API surface additions land via the `aiadra-core 0.9.0 → 0.10.0` arc that lands alongside or before the first `aiadra-mechanical` slice.
- **No `aiadra-core` version bump in this arc** (positioning-adjacent ADR).
- **Compatibility**: D16 operation identity generalization (`TransactionDraft.kind: str`) is a minimal change to the Phase-1 boundary — `TransactionKind` enum stays as a namespace of built-in kind constants (already inherits from `str`); existing built-in handlers + audit + tests unaffected.

## §0 — Position in the layer model

Native Engines are the implementation of Layer 5 per [ArchitectureOverview.md v0.2](../ArchitectureOverview.md) + [ADR/0027 D5](0027-aiad-positioning-and-native-engine-posture.md). They:
- Are AIADRA-implemented authoring runtimes per domain (mechanical, electrical, ...).
- Use third-party kernel libraries (OCCT, KiCad libs, etc.) as DEPENDENCIES.
- Do NOT wrap third-party applications (FreeCAD-the-app, KiCad-the-app, etc. are research material per ADR/0027 D4).
- Ship as ecosystem packages outside `aiadra-core` per ADR/0027 D11.
- Register with `aiadra-core`'s Ring 2 dispatch table via Python entry points per D2 below.
- Emit canonical sidecars + events + Vault blobs that validate against the canonical bundle (NEVER engine-side schemas — D10 below).

Layer 5 has TWO categories per ADR/0027 D12 — **Native Engines** (parametric authoring; this ADR's primary focus) and **Data Adapters** (pure data flow; D11 pins shape, mechanism deferred). Software source (Git) is the irregular case — Git IS the substrate per Manifesto P12.

## §1 — What this ADR pins

The 16 decisions below pin the Python API + lifecycle contract that a Native Engine package must satisfy to integrate with `aiadra-core`. Specifically:

- **Registration mechanism** (D2 — guarded `NativeEngineRegistrar` API via Python entry points)
- **Handler signature** (D3 — `NativeEngineContext` wrapper; not raw `TransactionDraft` exposure)
- **Kind namespace convention** (D4 — `<engine_id>.<op>`)
- **Discovery + missing-engine semantics** (D5 — lazy + per-engine isolated; `EngineNotAvailableError` covers missing + installed-but-unloadable)
- **State model + cache freshness invariant** (D6)
- **Native Engine vs Data Adapter boundary** (D7)
- **Provenance discipline split** (D8 — caller-supplied vs engine-computed)
- **Failure mode mapping** (D9 — `NativeEngineKernelError`)
- **Per-engine schema-additions governance** (D10 — canonical bundle only)
- **Data Adapter contract shape** (D11 — pinned shape, mechanism deferred)
- **Cross-engine references** (D12 — use existing relationship graph)
- **UI scope discipline** (D13 — per-engine; not pinned here)
- **Sequencing** (D14)
- **Out of scope** (D15)
- **Operation identity model** (D16 — `TransactionDraft.kind: str` generalized + `operation_kind` semantics)

## Decisions

### D1. ADR scope — Native Engine contract canonical; Data Adapter shape secondary

Both halves land here per [ADR/0027 D12 two-category Layer 5](0027-aiad-positioning-and-native-engine-posture.md) but Native Engine is the canonical contract; Data Adapter shape is pinned (D11) with concrete contract deferred to a future small ADR if/when the first Data Adapter ships. Co-landed because the two categories share the same Layer 5 boundary semantics + entry-point machinery; splitting would create symmetric-by-name asymmetric-in-content arcs.

### D2. Registration mechanism — Python entry-point group `aiadra.native_engines` + guarded `NativeEngineRegistrar` API

**Codex1 B2 absorption (arc 20260531-12).**

Each Native Engine package declares an entry point in its `pyproject.toml`:

```toml
[project.entry-points."aiadra.native_engines"]
mechanical = "aiadra_mechanical:register"
```

`aiadra-core` discovers entry points via [`importlib.metadata.entry_points()`](https://docs.python.org/3/library/importlib.metadata.html#entry-points) lazily on first `propose()` / `propose_kinds()` / `modify_kinds()` call (per D5).

Each engine's `register(registrar)` function receives a **`NativeEngineRegistrar`** (NOT the raw `_PROPOSE_DISPATCH` dict). The registrar enforces seven invariants:

1. **`engine_id` provenance**: the registrar's `engine_id` field is set by `aiadra-core` from the entry-point name (`"mechanical"` from `mechanical = "aiadra_mechanical:register"`); engine code cannot override it.
2. **Namespace discipline**: every `kind` passed to `add_operation()` MUST satisfy `kind.startswith(f"{engine_id}.")`. The registrar raises `NativeEngineRegistrationError` (new exception class) otherwise.
3. **No built-in overwrite**: `kind` MUST NOT be a key in built-in `_PROPOSE_DISPATCH` (init / create_part / change_parameter / etc.). The registrar raises `NativeEngineRegistrationError` on conflict.
4. **No cross-engine kind collision**: `kind` MUST NOT be registered by another engine. If two engines (via two entry-point packages) collide on the same kind, BOTH engines' registrations are REJECTED (not silently last-wins); both engine_ids become unavailable for the process lifetime; the collision is recorded in the discovery failure map per D5.
5. **No duplicate engine_id across distributions** (Codex2 B1 absorption, arc 20260531-12): if two or more installed distributions declare the SAME `engine_id` (same entry-point name in the `aiadra.native_engines` group) — REGARDLESS of whether their registered kinds collide — ALL distributions sharing that engine_id are REJECTED. The shared engine_id enters the failures map per D5 with a duplicate-engine-id diagnostic listing all colliding distributions; no handler from any of them is loaded; `propose(kind=f"{engine_id}.*")` raises `EngineNotAvailableError` per D5. This closes the nondeterminism gap where two packages each claiming `mechanical` (one registering `mechanical.adjust_parameter`, another registering `mechanical.add_hole`) would otherwise non-deterministically merge or shadow depending on entry-point iteration order.
6. **Handler signature check**: handler MUST be callable matching the D3 signature `(context: NativeEngineContext, params: dict) -> None`. The registrar does best-effort `inspect.signature` validation at registration time.
7. **Deterministic order**: the registrar collects ALL valid registrations first; merges into a single combined dispatch dict in a single atomic step; order of entry-point iteration MUST NOT affect outcome.

Sketch (`aiadra-core` internal — implementation lands in the `aiadra-core 0.9.0 → 0.10.0` arc):

```python
@dataclass
class NativeEngineRegistrar:
    engine_id: str  # set by aiadra-core; frozen via __setattr__ guard

    def __post_init__(self):
        object.__setattr__(self, "_operations", {})

    def add_operation(self, kind: str, handler: Callable) -> None:
        if not kind.startswith(f"{self.engine_id}."):
            raise NativeEngineRegistrationError(
                f"engine '{self.engine_id}' attempted to register kind {kind!r} "
                f"outside its namespace (must start with '{self.engine_id}.')"
            )
        if kind in _PROPOSE_DISPATCH:
            raise NativeEngineRegistrationError(
                f"engine '{self.engine_id}' attempted to overwrite built-in kind {kind!r}"
            )
        if kind in self._operations:
            raise NativeEngineRegistrationError(
                f"engine '{self.engine_id}' attempted duplicate registration of {kind!r}"
            )
        # Best-effort signature check
        sig = inspect.signature(handler)
        if list(sig.parameters) != ["context", "params"]:
            raise NativeEngineRegistrationError(
                f"engine '{self.engine_id}' handler for {kind!r} has wrong signature; "
                f"expected (context, params), got {list(sig.parameters)}"
            )
        self._operations[kind] = handler

    def frozen(self) -> _EngineRegistration:
        return _EngineRegistration(engine_id=self.engine_id, operations=tuple(self._operations.items()))
```

### D3. Handler signature — `NativeEngineContext` wrapper, NOT raw `TransactionDraft` exposure

**Codex1 N1 absorption (arc 20260531-12).**

Handler signature:

```python
def handle(context: NativeEngineContext, params: dict[str, Any]) -> None:
    """Native Engine operation handler. Mutates the context (stage_* calls)
    to express the operation's effect. Does not return a draft; aiadra-core
    builds the TransactionDraft from the context's accumulated stage calls.
    """
    ...
```

`NativeEngineContext` exposes a stable, versionable API surface:

**Read APIs (draft-aware per arc 20260531-9 Codex1 B1)** — operations that participate in `modify` MUST resolve state from the draft's staged writes FIRST, then fall back to disk:
- `context.find_reservation_entry_by_number(number) -> tuple[str, dict] | None`
- `context.load_sidecar(obj_uuid) -> dict`
- `context.load_reservation(prefix) -> dict`
- `context.load_revision(obj_uuid, rev_id) -> dict`
- `context.event_log_last_event_id() -> str | None`
- (additional read helpers added as Native Engines need them; versioned)

**Stage APIs (emission)** — mirror `TransactionDraft.stage_*` methods:
- `context.stage_sidecar(obj_uuid, sidecar) -> None`
- `context.stage_event(event) -> None`
- `context.stage_vault_bytes(data) -> tuple[content_hash, vault_path]`
- `context.stage_reservation(prefix, reservation) -> None`
- `context.stage_revision(obj_uuid, rev_id, content) -> None`

**Validation hook APIs** (Codex2 B2 absorption, arc 20260531-12 — hook callbacks MUST NOT receive raw `TransactionDraft` since that would re-expose the internals D3 explicitly hides):
- `context.add_pre_validate_hook(hook: Callable[[NativeEngineContext], None]) -> None`
- `context.add_post_validate_hook(hook: Callable[[NativeEngineContext], None]) -> None`

The hook callable receives the SAME `NativeEngineContext` that the handler received — the wrapper remains valid throughout validation. Engines that need to inspect proposed staged state during validation use the same `context.load_sidecar()` / `context.event_log_last_event_id()` / etc. methods exposed for handler use; those methods already read draft-aware per D3. Engines that need no context arg may register `Callable[[], None]` lambdas with captured context — `aiadra-core` accepts both 0-arg and 1-arg callables via `inspect.signature` adapter.

`aiadra-core` internally adapts these hooks to its existing `TransactionDraft.pre_validate_hooks` / `post_validate_hooks` mechanism (which currently passes the raw draft) — the adapter constructs a closure `lambda draft: hook(context)` or `lambda draft: hook()` per registered hook's arity. This preserves the existing internal hook plumbing while keeping `TransactionDraft` out of the Native Engine API surface.

**Context introspection** (read-only properties):
- `context.workspace -> Path`
- `context.bundle -> BundleHandle`
- `context.actor -> str` — `"agent" | "human"` per ADR/0026 §5 + D8 below
- `context.operation_kind -> str` — e.g., `"mechanical.adjust_parameter"`
- `context.transaction_id -> str`
- `context.protocol_version -> str` — currently `"1.0"`; bumped on breaking changes

**NOT exposed**:
- Direct `TransactionDraft` access (caller cannot circumvent the wrapper).
- `_PROPOSE_DISPATCH` access (engines don't dispatch to each other directly; cross-engine effects flow through the relationship graph per D12).
- `_lifecycle_state` access (managed by Ring 2 commit/rollback per Phase C arc 20260531-9 Codex1 B3).
- `pre_validate_hooks` / `post_validate_hooks` lists (only `add_*` accessors).

`NativeEngineContext` is **versioned** via the `protocol_version` property. Breaking changes to the context API bump the version + require Native Engine packages to declare compatibility in their entry-point metadata (mechanism deferred to the `aiadra-core 0.10.0` arc).

This decouples the engine API from `TransactionDraft`'s internal evolution. The 4 draft-aware-read helpers from arc 20260531-9 Codex1 B1 absorption (currently private `_find_reservation_entry_by_number_with_draft` / `_load_sidecar_with_draft` / `_load_reservation_with_draft` / `_begin_or_extend_draft` in `transaction/operations.py`) become methods on `NativeEngineContext` — minimal stable exposure.

### D4. Kind namespace convention — `<engine_id>.<op>`

Built-in kinds keep their existing names (`init`, `create_part`, `change_parameter`, `link_satisfies`, etc.). Native-Engine-registered kinds use the `.`-prefixed namespace: `mechanical.adjust_parameter`, `mechanical.add_extrude_feature`, `electrical.add_net`, `electrical.place_component`.

The `engine_id` is sourced from the entry-point name per D2 — engine code cannot override it. This makes engine origin syntactically visible + enables `propose_kinds()` filtering (e.g., "all mechanical operations" = `[k for k in propose_kinds() if k.startswith("mechanical.")]`).

Operations within an engine are engine-defined. No central catalogue of valid mechanical ops; each Native Engine documents its own kind catalogue in its package + per-engine ADR (e.g., a future `aiadra-mechanical` operation-catalogue ADR).

`propose_kinds()` + `modify_kinds()` return the COMBINED set (built-in + Native-Engine-registered) sorted; dynamic per the entry-point discovery (D5).

### D5. Engine discovery — lazy + per-engine isolated

**Codex1 B3 absorption (arc 20260531-12).**

Discovery is lazy on first `propose()` / `propose_kinds()` / `modify_kinds()` call; cached for process lifetime. An explicit `protocol.refresh_native_engines()` escape hatch (per Codex Q6) re-runs discovery for tests + embedding scenarios.

Each engine's load is **isolated** — a failure in one engine package does NOT prevent other engines or built-in operations from working:

```python
def _discover_native_engines() -> tuple[
    dict[str, _EngineRegistration],
    dict[str, Exception],
]:
    """Returns (loaded, failures). load_failures don't pollute the loaded set.

    Two-pass discovery:
      Pass 1 — group entry points by name (engine_id). If any engine_id has
               more than one entry point across installed distributions, the
               entire group is rejected per D2 invariant #5; the engine_id
               enters `failures` with a NativeEngineRegistrationError listing
               the colliding distributions. No load attempt is made.
      Pass 2 — for each unique-named entry point, attempt isolated load;
               any exception goes to `failures` per per-engine isolation.
    """
    loaded, failures = {}, {}

    # Pass 1: group by entry-point name to detect duplicate engine_ids.
    groups: dict[str, list] = {}
    for ep in entry_points(group="aiadra.native_engines"):
        groups.setdefault(ep.name, []).append(ep)

    for engine_id, eps in groups.items():
        if len(eps) > 1:
            distributions = sorted({ep.dist.name for ep in eps if ep.dist})
            failures[engine_id] = NativeEngineRegistrationError(
                f"duplicate engine_id {engine_id!r} declared by multiple "
                f"installed distributions: {distributions}; ALL rejected per "
                f"ADR/0028 D2 invariant #5. Resolve by uninstalling all but one."
            )
            continue

        # Pass 2: isolated load.
        ep = eps[0]
        try:
            register_fn = ep.load()
            registrar = NativeEngineRegistrar(engine_id=engine_id)
            register_fn(registrar)
            loaded[engine_id] = registrar.frozen()
        except Exception as e:
            failures[engine_id] = e
            # Continue — other engines + built-ins still loadable.

    return loaded, failures
```

**Dispatch lookup semantics**:
- `propose(kind="change_parameter")` (built-in): unaffected by Native Engine load state. Built-in `_PROPOSE_DISPATCH` is never polluted by engine failures.
- `propose(kind="mechanical.adjust_parameter")` (Native Engine):
  1. Parse `engine_id = kind.split(".", 1)[0]`.
  2. If `engine_id` in loaded engines: dispatch via the loaded handler.
  3. If `engine_id` in failed engines: raise `EngineNotAvailableError(f"engine {engine_id!r} failed to load: {failure!r}")` with `__cause__ = failure`. This case covers BOTH per-engine load failures (broken import, `register()` raised, etc.) AND duplicate-engine_id rejections per D2 invariant #5 (the `NativeEngineRegistrationError` raised in pass 1 is preserved as `__cause__`; its message identifies the colliding distributions).
  4. If `engine_id` neither loaded nor failed: raise `EngineNotAvailableError(f"engine {engine_id!r} not installed; try: pip install aiadra-{engine_id}")` (no `__cause__`).
- `propose_kinds()` / `modify_kinds()`: return the combined set of built-in kinds + LOADED engine kinds. Failed engines contribute zero kinds.

`EngineNotAvailableError(ValueError)` is a new exception class (per Codex Q8 + D9 below) covering all four unavailability cases (missing / per-engine load failure / duplicate-engine_id rejection / cross-engine-kind-collision rejection). The message distinguishes the case for human + agent diagnostics.

Read-only operations (`inspect` / `query` / `validate` / `explain` / `explain_failure`) work without any Native Engine installed — reading mechanical sidecars + Vault blobs requires no engine, since schemas are in the canonical bundle (per D10).

### D6. Native Engine state model — opaque cache + freshness invariant

**Codex1 B5 absorption (arc 20260531-12).**

- Native Engines MAY hold per-Workspace cache state between calls (e.g., loaded OCCT BREP instances, sketch solver intermediate solutions, feature-tree caches).
- State is OPAQUE to `aiadra-core` and to other Native Engines. `aiadra-core` does not introspect, validate, persist, or coordinate engine state.
- Canonical truth lives in the Workspace per [Manifesto P1](../Manifesto.md). Engine state is per-process + rebuildable from sidecars + Vault on demand (per [Manifesto P10](../Manifesto.md) history-is-event-based / current-state-is-flat).
- Engine restart MUST NOT lose data — anything not in sidecars + events + Vault is invalidatable cache.
- Multi-process / parallel Native Engine instances are out of scope per D15.

**Cache freshness invariant** (Codex1 B5 verbatim):

> Native Engine caches are advisory only and per-process. Before emitting sidecars / events / Vault blobs from any cached computation, a handler MUST prove its cached inputs still match current Workspace authority by:
>
> - **(a) keying cache entries** to current sidecar content hashes / event-log boundary (last event_id) / relevant Vault content hashes / current `revision_id` of relevant Reservations, AND verifying the keys still match before emission; OR
> - **(b) reloading inputs** from canonical Workspace artifacts (sidecars + events + Vault) and recomputing.
>
> Stale or unverifiable cache entries MUST be discarded and rebuilt. `aiadra-core` does NOT introspect engine cache; the engine is responsible for the freshness check. The check MUST happen on the proposed-Workspace state (after applying any `existing_draft` mutations) — caches that read pre-draft state are stale relative to the in-flight Transaction.

This rule + the existing Phase D `_validate_proposed_b6_scan` (arc 20260531-9 Codex2 B1) + the proposed-state fold check (arc 20260531-2 Phase 1 B9) together close the cache-vs-canonical-state gap for Native Engine operations.

`NativeEngineContext` exposes the keying primitives Native Engines need (`context.load_sidecar(uuid)` returns the current draft-aware state; `context.event_log_last_event_id()` returns the current boundary; etc.) so engines can implement (a) ergonomically.

### D7. Native Engine vs Data Adapter boundary

(Tightened from [ADR/0027 D12](0027-aiad-positioning-and-native-engine-posture.md).)

| Aspect | Native Engine | Data Adapter |
|---|---|---|
| **Purpose** | Parametric authoring surface for a domain | Pure data flow: ingest external format → AIADRA, OR export AIADRA → external format |
| **Emits** | Sidecars + events + Vault blobs (canonical Truth Model artifacts) | Sidecars + events from ingest; external format files from export |
| **Kernel dependency** | Third-party kernel library (OCCT, KiCad libs, etc.) | None required (may use parsing libraries; no parametric kernel) |
| **Registration entry-point group** | `aiadra.native_engines` per D2 | `aiadra.data_adapters` per D11 (mechanism deferred) |
| **Kind namespace** | `<engine_id>.<op>` per D4 (registered into `_PROPOSE_DISPATCH`) | NOT in `_PROPOSE_DISPATCH`; separate ingest/export entry-point functions per D11 |
| **State model** | Opaque per-process cache + freshness invariant per D6 | Stateless per call (typical) |
| **Provenance category** (D8) | Split: caller-supplied facts preserve caller provenance; engine-computed facts use `computed_result` | `measured` / `human_input` / `ai_proposal` per source category — Data Adapter usually preserves whatever the source data attests |
| **Examples** | `aiadra-mechanical` (OCCT), `aiadra-electrical` (KiCad libs) | `aiadra-bom-export`; `aiadra-doors-ingestion`; `aiadra-instron-csv-ingestion`; STEP/IGES/STL ingest within `aiadra-mechanical` (per Q5 + N2: same package can ship both contract categories under different entry-point groups) |

**Software source (Git) is the irregular case** — Git IS the substrate per Manifesto P12. No Native Engine, no Data Adapter; standard Git tooling.

**DV (Design Verification)** sits in Data Adapter territory: ingesting test results, signing reports. Authoring of test procedures themselves ([TestProcedure Object Type per ADR/0020](0020-object-type-test-procedure.md)) is document authoring, not parametric — Data Adapter scope.

**Per Codex1 N2 + Q5**: entry-point group, NOT package name, determines contract semantics. A package like `aiadra-mechanical` MAY register operations under both `aiadra.native_engines` (mechanical authoring ops) AND `aiadra.data_adapters` (STEP/IGES/STL ingest+export). Both surfaces ship in the same pip package but expose different contracts.

### D8. Provenance discipline — split caller-supplied vs engine-computed

**Codex1 B4 absorption (arc 20260531-12).**

Native Engine handlers emit two distinct classes of facts; each takes a different provenance category:

**Caller-supplied design-intent facts** — preserve caller provenance:
- The parameter value the agent/human is setting (e.g., `new_value=8.0` in `mechanical.adjust_parameter`)
- New named parameters introduced by an operation (e.g., a new sketch dimension)
- New constraint specifications (mate distances, angles, threshold values)
- New feature parameter inputs (extrude depth, fillet radius, etc.)
- Anything the caller's `params` dict named that becomes a `parameter` record value

For these, the Native Engine handler MUST set `fact_provenance.category` based on `context.actor`:
- `"ai_proposal"` if `context.actor == "agent"`
- `"human_input"` if `context.actor == "human"`

The handler MUST NOT self-attest `human_input` when `actor == "agent"` (raises `TransactionError` per [ADR/0026 §5 + Codex1 B4 absorption arc 20260531-9](0026-ai-action-protocol-scope.md)). This discipline is identical to the built-in `change_parameter` operation; Native Engine handlers follow the same rule.

**Engine-computed derivative facts** — `computed_result + derived_from`:
- Recomputed geometry (`geometry_ref` records emitted from OCCT BREP ops; their `vault_ref` content hashes)
- Derived measurements (mass, volume, centroid, surface area)
- Solver outputs (constraint solver intermediate values; sketch-solver-derived constraint satisfactions)
- Cached computational artifacts (mesh, render preview, STEP export blob hashes)
- Anything the engine COMPUTES from the caller's input + existing canonical state

For these, the handler MUST set:
- `fact_provenance.category = "computed_result"`
- `fact_provenance.derived_from = [<caller-supplied-input-fact-refs>, <other-dependency-fact-refs>]` per [S1](../TruthModelSchema.md) fact-provenance shape. The `derived_from` list MUST be non-empty when category is `computed_result`.

**`context.actor` is NOT informational** — it's the SOLE source of truth for the caller-supplied vs computed distinction. Native Engine handlers consume `context.actor` directly to set provenance.

This split prevents the laundering risk Codex flagged: a Native Engine handler that blanket-set `computed_result` for everything would erase the agent's (or human's) authorship of the design intent, breaking the audit trail and the [Manifesto P7](../Manifesto.md) "every fact carries provenance" discipline.

### D9. Failure mode mapping

Native Engine failures map to two new exception classes (plus the existing Ring 2 exceptions):

**`EngineNotAvailableError(ValueError)`** — new in `aiadra_core.protocol`. Raised when:
- Engine_id is parsed from `kind` but the engine is not installed (pip install missing)
- Engine is installed but failed to load during discovery (broken import, `register()` raised, etc.) — `__cause__` preserves the load exception with full traceback
- Engine is installed + loaded but collided with another engine during D2 enforcement — both engines are in failures map; same error path

All three subcases preserve `engine_id` + `operation_kind` (full `<engine_id>.<op>`) in the message for diagnostics.

**`NativeEngineKernelError(RuntimeError)`** — new in `aiadra_core.protocol`. Raised by Native Engine handlers when:
- OCCT (or equivalent kernel) raises an exception during BREP / sketch-solver / feature-recompute operations
- The handler encounters an unrecoverable kernel-level state inconsistency
- The handler's freshness check (D6 (a) keying or (b) reload) fails irrecoverably

`NativeEngineKernelError` carries:
- `engine_id`: the engine that raised
- `operation_kind`: the full namespaced kind (e.g., `"mechanical.adjust_parameter"`)
- The underlying kernel exception preserved as `__cause__`

**Existing Ring 2 exceptions still apply** for user-facing failures:
- `TransactionError` — invalid params, no such Object, invalid operation for engine state
- `SchemaValidationError` — emitted artifacts fail schema validation
- `RevisionBindingError` — B6 mutation-prohibition violation
- `ProfileViolationError` — emitted artifacts fail Profile lint
- All caught by Ring 2 dispatch + included in `simulate()` collect-mode FAIL outcomes per Phase D arc 20260531-10

Native Engine handlers MUST NOT swallow exceptions silently. Validation rejects MUST raise per the existing fail-loud discipline ([Manifesto P5](../Manifesto.md) + [ADR/0002 reject-loudly](0002-canonical-format.md)).

### D10. Per-engine schema additions — canonical bundle authority only

When a Native Engine introduces new Object Types, relationship types, event types, or sidecar namespaces, those land via per-engine SCN ADRs that bump the canonical schema bundle (same governance as [ADR/0017 Drawing](0017-object-type-drawing.md), [ADR/0019 EvidenceArtifact](0019-object-type-evidence-artifact.md), [ADR/0020 TestProcedure](0020-object-type-test-procedure.md), [ADR/0022 TestExecution](0022-test-execution-model.md)).

Specifically: the **Part authoring SCN ADR/0029** (working number; gates Wedge-003 per [ADR/0027 D17](0027-aiad-positioning-and-native-engine-posture.md)) lands the new `part_changed` event + `feature_delta` + `geometry_ref_delta` shape; bundle v0.27.0 → v0.28.0 MINOR additive. `aiadra-mechanical` then READS the bundle to discover its own schemas — the bundle stays canonical; the engine is a consumer.

**Schema authority is `aiadra-core/src/aiadra_core/schemas/v*/` per [ADR/0003](0003-schema-governance.md)** — Native Engines are NEVER the authority. Alternative (engine-side schemas) was rejected per Q4: it would fracture validation (would force `aiadra-core` to consult engine packages for schema lookup), would break cross-engine references (each engine's schemas would only validate within its own namespace), and would invert the [ADR/0027 D6](0027-aiad-positioning-and-native-engine-posture.md) reframing of Ring 3 as the "Native Engine Implementation contract" not "Native Engine schema definition surface."

Engines can iterate freely on opaque-state caches + handler implementations + operation catalogues. Only schema additions need SCN ADRs.

### D11. Data Adapter contract — pinned shape, deferred mechanism

(Per ADR/0027 D12 + Codex1 Q5 + N2 absorption.)

Probable shape (NON-binding pinning — concrete contract deferred to a future small ADR if/when first Data Adapter ships):

```python
# Ingest pattern (external format → AIADRA workspace):
def ingest(workspace: Path, source_path: Path, params: dict | None = None) -> TransactionDraft:
    """Read external format at source_path; build a draft that creates
    corresponding AIADRA Objects + events. Returns a draft for the caller
    to validate + commit (or rollback)."""
    ...

# Export pattern (AIADRA workspace → external format):
def export(workspace: Path, query: dict | None, dest_path: Path) -> None:
    """Export Workspace state matching query as external format at dest_path.
    Read-only against the Workspace; emits no events or sidecars."""
    ...
```

**Registration**: separate entry-point group `aiadra.data_adapters`. Same package may declare entry points in BOTH `aiadra.native_engines` AND `aiadra.data_adapters` (per Q5 + N2 — e.g., `aiadra-mechanical` ships mechanical Native Engine + STEP/IGES/STL Data Adapters).

**Concrete contract deferred** because the variety in Data Adapter shape (ingest vs export, one-shot vs streaming, full-workspace vs filter, sync vs async, transactional vs side-effecting, etc.) makes premature pinning likely to constrain badly. Better to let the first 1-2 concrete cases (probably a BOM export + a STEP importer for `aiadra-mechanical`) inform the contract.

The future Data Adapter contract ADR (when it lands) will likely pin:
- Callable name + signature precision
- Error model (Data Adapter exception class?)
- Transactional semantics for ingest (draft-build + caller validate-commit, similar to Native Engine handlers)
- Streaming + cancellation surface (if needed)
- Provenance category defaults for ingested facts

### D12. Cross-engine references — handled by existing AIADRA relationship graph

When a mechanical Part is `depicts`-ed by an electrical Drawing (hypothetical), the cross-engine reference is just a regular `relationship` record on the source Object — no special engine-to-engine dispatch needed. AIADRA's existing per-relationship-type schemas + bundle lookup machinery (per [W3 / ADR/0025 §9](0025-aiadra-core-runtime-scope.md)) handle the validation.

Native Engines see other engines' Objects as normal sidecars when reading via `context.load_sidecar()` or via `aiadra_core.protocol.inspect()` / `query()`; no special "this is a mechanical Object" vs "this is an electrical Object" engine-side discrimination beyond `object.type` discriminator already in the sidecar.

`_PROPOSE_DISPATCH` access is NOT exposed to Native Engines per D3 — engines don't dispatch to each other directly. Cross-engine effects flow through the relationship graph + the standard `propose` / `modify` Ring 2 contracts.

### D13. UI scope — per-engine; NOT pinned here

`aiadra explain` + `aiadra inspect` already work for read-side surfaces in any domain (the structured `ExplanationTree` from arc 20260531-10 Phase D is domain-agnostic). No new UI scope in this ADR.

Authoring UI is per-engine, decoupled from this ADR. Each Native Engine MAY ship its own viewport (web-based via VSCode extension; native; etc.). The canonical Workspace Browser per [Glossary v0.25](../Glossary.md) is VSCode + AIADRA extension; Native Engines integrate there via standard VSCode extension mechanisms.

This ADR pins NO UI commitment. Per [ADR/0027 Q5 + Codex1 acceptance](0027-aiad-positioning-and-native-engine-posture.md): defer to per-engine UI scope ADRs.

### D14. Sequencing per ADR/0027 D10 (operationalized here)

1. **This ADR/0028 (now)** — Native Engine Implementation contract.
2. **Part authoring SCN ADR/0029** — new `part_changed` event with `feature_delta` + `geometry_ref_delta` per [ADR/0027 D17](0027-aiad-positioning-and-native-engine-posture.md); bundle v0.27.0 → v0.28.0 MINOR additive. **PRE-CONDITION for `aiadra-mechanical` Wedge-003 implementation** since Native Engine geometry writes need the new event shape.
3. **`aiadra-core 0.9.0 → 0.10.0` arc** (small) — implements the API additions ADR/0028 pins: `NativeEngineRegistrar` + `NativeEngineContext` + `EngineNotAvailableError` + `NativeEngineKernelError` + `D16` operation-identity generalization + entry-point discovery + dispatch lookup semantics + `protocol.refresh_native_engines()`. Can land before or after step 2; both must land before step 4. Bumps aiadra-core 0.9.0 → 0.10.0 (MINOR additive). May not bump bundle.
4. **Wedge-003 scope ADR** — smallest viable AIADRA-native mechanical authoring loop per [ADR/0027 D17](0027-aiad-positioning-and-native-engine-posture.md) concrete shape sketch.
5. **`aiadra-mechanical` ecosystem-package implementation** — first concrete Native Engine slice. Multi-arc work; horizon = years per [ADR/0027 D14 + D17](0027-aiad-positioning-and-native-engine-posture.md) scope register.

Plus optional parallel:
- **Per-engine research arcs** (FreeCAD / Solvespace / OpenSCAD / KiCad / Onshape) — informal study + writeup; could be `Docs/Research/` notes rather than ADRs; feeds (4) + (5).

### D15. Out of scope (explicit deferrals)

1. **Specific Python binding choice** for OCCT (pythonocc-core vs OCP) per [ADR/0027 Q9](0027-aiad-positioning-and-native-engine-posture.md). Decided by `aiadra-mechanical` implementation arc.
2. **Concrete Wedge-003 implementation scope** — separate Wedge-003 scope ADR per D14.
3. **Part authoring SCN event surface** — separate ADR/0029 per D14 + D10.
4. **`aiadra-mechanical` package implementation** — multi-arc series; first slice per Wedge-003.
5. **KiCad / electrical engine specifics** — future per-engine ADR.
6. **DV / procurement Data Adapter specifics** — future per-adapter ADR (probably first one with BOM export).
7. **Native Engine subprocess / multi-language story** — Native Engines MUST be Python-callable (entry-point + Python import) per D2. Subprocess IPC or non-Python engines deferred until a concrete case demands it; Python-wrapping-C++ via bindings (pythonocc-core, etc.) is sufficient.
8. **Native Engine sandboxing / trust model** — Native Engines are trusted code installed via `pip` (same trust model as any Python dependency). Sandboxing deferred until a concrete threat model demands it.
9. **Multi-process / parallel Native Engine instances** — single-process operation only per D6. Tier-L scaling concern per [Manifesto Scale Targets](../Manifesto.md).
10. **Hosted Native Engine service** — explicitly REJECTED per [Manifesto P11](../Manifesto.md). Native Engines run locally per D11 (ADR/0027).
11. **Engine diagnostics introspection helper** (`native_engine_status()` / `engine_diagnostics()`) — useful per Codex1 N3 but not contract-critical; lands in `aiadra-core 0.10.0` arc or first `aiadra-mechanical` arc.
12. **Engine version compatibility declaration** — `NativeEngineContext.protocol_version` per D3 is "1.0" at the start; mechanism for engines to declare compatibility deferred to the `aiadra-core 0.10.0` arc.

### D16. Operation identity model — `TransactionDraft.kind: str` generalized

**Codex1 B1 absorption (arc 20260531-12).**

Current Phase-1 boundary types cannot honestly represent Native Engine operation kinds like `"mechanical.adjust_parameter"` — `TransactionDraft.kind: TransactionKind` is an enum; audit serialization writes `kind=self.kind.value`. Without changes, Native Engine kinds would have to lie as an existing enum member or wedge into a generic "NATIVE_ENGINE_OPERATION" member that loses the specific identifier.

**Verification**: `class TransactionKind(str, Enum)` already inherits from `str`. `TransactionKind.CHANGE_PARAMETER == "change_parameter"` is True. Audit + explain + failure surfaces already consume the string value. Generalization is a minimal change.

**Decision**:

1. **`TransactionDraft.kind: str`** — generalized from `TransactionKind` enum to plain string. The Phase-1 boundary type stays backward-compatible because `TransactionKind` inherits from `str`; existing callers passing `TransactionKind.CHANGE_PARAMETER` continue to work (the enum member's str value is `"change_parameter"`).

2. **`TransactionKind` enum stays** as a namespace of **built-in kind constants**:
   ```python
   class TransactionKind(str, Enum):
       INIT = "init"
       CREATE_OBJECT = "create_object"
       CHANGE_PARAMETER = "change_parameter"
       # ... etc., unchanged
   ```
   Built-in handlers use the enum members (no code change). Native Engine handlers pass the full namespaced string directly (`kind="mechanical.adjust_parameter"`).

3. **`_begin_or_extend_draft(kind: str, ...)`** — accepts the string. Internal `TransactionKind | str` compatibility is automatic via inheritance.

4. **Audit serialization** — drops the redundant `.value` access (was `kind=self.kind.value`; becomes `kind=self.kind`). Native Engine kinds round-trip as strings without information loss.

5. **`propose_kinds()` + `modify_kinds()`** — return the COMBINED set (built-in + Native-Engine-registered) as sorted tuples per D4 + D5. Dynamic per the entry-point discovery.

6. **Failure trees** (per ADR/0026 Phase D `ExplanationNode` shape from arc 20260531-10) — preserve the full namespaced kind via the existing `details` dict.

7. **`EngineNotAvailableError` + `NativeEngineKernelError`** — both carry the full namespaced kind in their messages + as attribute `operation_kind`.

8. **Lifecycle errors** (`_assert_open` messages, etc.) — use the full string kind unchanged.

The generalization lands in the `aiadra-core 0.9.0 → 0.10.0` arc per D14 step 3. NOT this ADR — this ADR pins the contract only.

## Supersession + amendment register

**No supersessions.** ADR/0027 already pinned the Native Engine posture + Ring 3 reshape; this ADR operationalizes them without changing prior decisions.

**No multi-document amendments.** Manifesto / ArchitectureOverview / Glossary unchanged. Glossary may gain a brief entry for `NativeEngineRegistrar` + `NativeEngineContext` + `aiadra.native_engines` entry-point group when the `aiadra-core 0.10.0` arc lands — captured as future polish, not blocking this ADR.

**`aiadra-core` API additions** (deferred to `aiadra-core 0.9.0 → 0.10.0` arc per D14 step 3, NOT this ADR):

- `aiadra_core.protocol.EngineNotAvailableError(ValueError)` — D5 + D9
- `aiadra_core.protocol.NativeEngineKernelError(RuntimeError)` — D9
- `aiadra_core.protocol.NativeEngineRegistrationError(ValueError)` — D2
- `aiadra_core.protocol.NativeEngineRegistrar` — D2
- `aiadra_core.protocol.NativeEngineContext` — D3
- `aiadra_core.protocol.refresh_native_engines()` — D5 + Codex Q6 explicit escape hatch
- `aiadra_core.protocol.propose_kinds()` / `modify_kinds()` — already exist; become dynamic per D4 + D5
- `TransactionDraft.kind: str` generalization — D16

**Coherence Checklist**: the "Native engine boundary" item earned in arc 20260531-11 + landed at arc-11 close (SystemState §3 count 10 → 11). This ADR is the first to be walked against it; PASS per the self-check below. No new Checklist item proposed.

## Consequences

- **No bundle bump.** Bundle stays v0.27.0; this ADR is positioning-adjacent.
- **No `aiadra-core` version bump in this arc.** The API additions land in the future `aiadra-core 0.9.0 → 0.10.0` arc per D14 step 3.
- **Native Engine + Data Adapter framework is now operational at the contract level** — concrete Native Engine implementation can proceed once steps 2 (Part authoring SCN) + 3 (aiadra-core 0.10.0) + 4 (Wedge-003 scope) land.
- **First arc to be walked against the new "Native engine boundary" Coherence Checklist item** (earned arc 20260531-11). PASS — this ADR specifically enforces the boundary via D2 entry-point + D7 boundary table + D15 explicit "no wrap of third-party application."
- **Per-engine schemas remain canonical to `aiadra-core` bundle** (D10). Engine packages are consumers, not schema authorities. Trade-off: every Native Engine schema addition requires AIADRA SCN governance ceremony.
- **Native Engine vs Data Adapter is a per-entry-point-group distinction**, not per-package. The same package may ship both.
- **Provenance discipline is operationalized at the Native Engine boundary** (D8) — handlers MUST split caller-supplied design intent (preserve `actor` provenance) from engine-computed derivatives (use `computed_result + derived_from`). Native Engines that violate this discipline launder authorship + break the audit trail.
- **Cache freshness is an engine-side invariant** (D6) — `aiadra-core` does not introspect; engines are responsible.
- **Engine failures are isolated** (D5 + D9) — a broken `aiadra-mechanical` install does not break `propose(kind="change_parameter")` or any other built-in / unrelated engine kind.
- **Duplicate `engine_id` across distributions is deterministic-failure** (D2 invariant #5 + D5 pass-1 grouping per Codex2 B1 absorption) — two installed distributions declaring the same `engine_id` cannot non-deterministically merge or shadow; both are rejected before any load attempt; `propose(kind=f"{engine_id}.*")` raises `EngineNotAvailableError` with a duplicate-engine-id diagnostic listing the colliding distributions.
- **Validation hooks never receive raw `TransactionDraft`** (D3 per Codex2 B2 absorption) — hook callbacks receive the same `NativeEngineContext` the handler received (or `Callable[[], None]` with captured context); `aiadra-core` adapts internally to its existing `TransactionDraft.pre_validate_hooks` mechanism via a closure adapter. Native Engine API surface contains zero references to `TransactionDraft`.

## Alternatives rejected

- **(i) Raw dispatch-table mutation** (`register(dispatch)` exposing `_PROPOSE_DISPATCH` directly). Rejected per Codex1 B2: allows accidental overwrite of built-ins, cross-engine collisions, namespace violations. D2 guarded `NativeEngineRegistrar` is the chosen path.
- **(ii) Symmetric-with-built-in handler signature** (handler receives `workspace, bundle, params, actor, existing_draft` like `transaction.operations.*` functions). Rejected per Codex1 N1: exposes `TransactionDraft.pre_validate_hooks` + private operations helpers as stable ecosystem API. D3 `NativeEngineContext` wrapper is the chosen path.
- **(iii) Eager all-engine discovery at first import**. Rejected per Codex1 B3: one broken engine poisons all subsequent dispatch. D5 per-engine isolated discovery is the chosen path.
- **(iv) Blanket `computed_result` for all Native-Engine-emitted facts**. Rejected per Codex1 B4: launders agent / human authorship of design intent. D8 split (caller-supplied vs engine-computed) is the chosen path.
- **(v) Opaque cache without freshness invariant**. Rejected per Codex1 B5: stale cache reads can emit canonical artifacts derived from outdated state. D6 freshness rule is the chosen path.
- **(vi) Engine-side schema authority**. Rejected per Q4: fractures validation; breaks cross-engine references; inverts ADR/0027 D6 reframing. D10 canonical-bundle-only is the chosen path.
- **(vii) Subprocess IPC for Native Engines**. Rejected for v1 per D15 item 7: Python-wrapping-C++ via bindings (pythonocc-core etc.) is sufficient for the mechanical engine's OCCT dependency; subprocess IPC adds complexity for marginal isolation benefit.
- **(viii) `TransactionDraft.kind` as enum-only with a generic `NATIVE_ENGINE_OPERATION` member + separate `operation_kind: str` field**. Rejected per Codex1 B1: the generalization to plain `str` (D16) is cleaner because `TransactionKind` already inherits from `str` — no dual-field bookkeeping needed; existing call sites unaffected.
- **(ix) Last-wins or merge on duplicate `engine_id` across distributions**. Rejected per Codex2 B1: would reintroduce nondeterminism dependent on entry-point iteration order; would let an installed package silently shadow another. D2 invariant #5 reject-both is the chosen path; users resolve by uninstalling all but one of the colliding distributions.
- **(x) Validation hooks receiving raw `TransactionDraft`**. Rejected per Codex2 B2: defeats the D3 wrapper boundary by exposing `TransactionDraft.sidecar_writes` / `_lifecycle_state` / `pre_validate_hooks` list to engine code after explicitly hiding them; would make those internals part of the stable engine API through the back door. D3 hook signatures `Callable[[NativeEngineContext], None]` (or 0-arg with captured context) is the chosen path; `aiadra-core` adapts internally.

## References

- [ADR/0027 — AIAD positioning + Native Engine posture](0027-aiad-positioning-and-native-engine-posture.md) — direct parent; this ADR operationalizes its D6 + D10 + D11 + D17 + D18.
- [ADR/0026 — AI Action Protocol scope](0026-ai-action-protocol-scope.md) — §2 9-of-9 contract surface (`propose` / `modify` are the entry points Native Engines plug into); §5 provenance discipline; §6 Tier-3 ecosystem-package precedent (D11 precedent).
- [ADR/0025 — `aiadra-core` runtime scope](0025-aiadra-core-runtime-scope.md) — §9 W3 bundle lookup namespace; per-engine SCN precedent.
- [ADR/0017 / 0019 / 0020 / 0022 — per-Object-Type ADRs](0017-object-type-drawing.md) — per-engine SCN governance pattern (D10).
- [ADR/0005 §9 — adapter shell](0005-object-type-part.md) — preserved per ADR/0027 D18; wire-format field names this contract dispatches through.
- [ADR/0003 — Schema governance](0003-schema-governance.md) — schema authority lives in `aiadra-core` bundle (D10).
- [Manifesto.md v0.4](../Manifesto.md) — P1 (tools sync to truth); P5 (transactional approval); P11 (Core hosts nothing); P12 (three-tier on Git).
- [ArchitectureOverview.md v0.2](../ArchitectureOverview.md) — Layer 5 (Native Engines + Data Adapters).
- [Glossary.md v0.25](../Glossary.md) — Native Engine + Data Adapter + AIAD entries.
- Phase C arc 20260531-9 Codex1 B1 absorption — draft-aware reads pattern (`_find_reservation_entry_by_number_with_draft` etc.); D3 `NativeEngineContext` methods.
- Phase C arc 20260531-9 Codex1 B3 absorption — `TransactionDraft._lifecycle_state` terminal-state guard; D3 + D16 lifecycle awareness.
- Phase D arc 20260531-10 Codex1 B1 absorption — structured `ExplanationNode` failure trees; D16 failure surfaces.
