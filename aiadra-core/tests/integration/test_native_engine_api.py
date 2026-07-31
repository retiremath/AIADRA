"""Native Engine API additions (arc 20260601-1; aiadra-core 0.10.0 → 0.11.0).

Per ADR/0028 D2 + D3 + D5 + D9 + D16 + Codex1 R1 absorptions:
- B1: NativeEngineRegistrar engine_id immutable from construction
- B2: NativeEngineContext.make_event / emit_event envelope helpers using
      draft-aware _next_event_id_in_draft (composability across modify())
- B3: validation/binding.py find_mutation_after_binding_violations_for_events
      includes part_changed
- B4: NativeEngineContext uses __slots__ (not dataclass); _draft hidden from
      dataclasses.fields()/repr
- N2: cross-engine kind collision check dropped (redundant once duplicate-
      engine_id rejection + namespace discipline enforced)
- N3: handler signature check is arity-only (accepts any param names)
"""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from aiadra_core import __version__ as aiadra_version
from aiadra_core.native_engine.discovery import (
    _CACHE,
    _discover_native_engines,
    get_native_engines,
    refresh_native_engines,
)
from aiadra_core.native_engine.registrar import _EngineRegistration
from aiadra_core.protocol import (
    EngineNotAvailableError,
    NativeEngineContext,
    NativeEngineKernelError,
    NativeEngineRegistrar,
    NativeEngineRegistrationError,
    TransactionDraft,
    TransactionError,
    commit,
    modify,
    modify_kinds,
    native_engine_status,
    propose,
    propose_kinds,
    refresh_native_engines as protocol_refresh,
)
from aiadra_core.protocol import _resolve_propose_handler
from aiadra_core.transaction.boundary import TransactionKind
from aiadra_core.validation.binding import (
    find_mutation_after_binding_violations_for_events,
)
from aiadra_core.validation.bundle_registry import BundleRegistry


# =============================================================================
# Helpers
# =============================================================================


def _init_workspace(tmp_path: Path, name: str = "ws") -> Path:
    ws = tmp_path / name
    ws.mkdir()
    propose(ws, kind="init", params={}).commit()
    return ws


def _bundle_latest():
    return BundleRegistry().latest()


@pytest.fixture(autouse=True)
def _reset_discovery_cache():
    """Clear discovery cache before AND after each test so per-test
    monkeypatch state doesn't leak."""
    refresh_native_engines()
    yield
    refresh_native_engines()


class _FakeEntryPoint:
    """Mock for importlib.metadata.EntryPoint."""

    def __init__(self, name: str, load_fn, dist_name: str = "fake-dist"):
        self.name = name
        self._load_fn = load_fn
        # Mimic the .dist.name attribute used by discovery.py.
        self.dist = type("FakeDist", (), {"name": dist_name})()

    def load(self):
        return self._load_fn


def _patch_entry_points(eps: list[_FakeEntryPoint]):
    """Patch importlib.metadata.entry_points to return the given list when
    queried for `group="aiadra.native_engines"`."""

    def fake_entry_points(*, group: str):
        if group == "aiadra.native_engines":
            return eps
        return []

    return patch(
        "aiadra_core.native_engine.discovery.entry_points",
        side_effect=fake_entry_points,
    )


# =============================================================================
# 1. Module surface + version
# =============================================================================


def test_native_engine_module_exports():
    """All 7 public symbols importable from aiadra_core.protocol."""
    from aiadra_core import protocol as p

    assert hasattr(p, "NativeEngineRegistrar")
    assert hasattr(p, "NativeEngineContext")
    assert hasattr(p, "NativeEngineRegistrationError")
    assert hasattr(p, "EngineNotAvailableError")
    assert hasattr(p, "NativeEngineKernelError")
    assert hasattr(p, "refresh_native_engines")
    assert hasattr(p, "native_engine_status")


def test_native_engine_api_in___all__():
    from aiadra_core import protocol as p

    for sym in (
        "NativeEngineRegistrar",
        "NativeEngineContext",
        "NativeEngineRegistrationError",
        "EngineNotAvailableError",
        "NativeEngineKernelError",
        "refresh_native_engines",
        "native_engine_status",
    ):
        assert sym in p.__all__


def test_aiadra_core_version_bumped_to_0_15_0():
    """Arc 20260716-2 SK-C1.0 S2 MINOR bump: Display Representation contract
    v1.2 — additive optional `surface_kind` per face + top-level
    `sketch_frames` (resolved face-bound sketch frames) with the full
    1.0/1.1/1.2 compatibility matrix and the standalone-HLR capable set
    {1.1, 1.2}. Additive public behavior → minor bump (prior: 0.14.0,
    arc 20260714-2 EP0 — the empty-Part display state)."""
    # 0.19.1: the W-3 log-advance guard — `TransactionDraft.commit()` /
    # `protocol.commit()` now refuse a serialized stale draft with a typed
    # CommitError before any write (arc 20260730-1 Codex14 B2; the
    # user-visible-edge-behavior PATCH precedent of arc 20260601-5).
    # 0.19.0: ADR/0044 A4 — Display contract v1.4 (`v2_profiles`) + the new
    # `protocol.preview_sketch_graph` read primitive (arc 20260730-1).
    # 0.18.0 was delete_object + bundle v0.30.0; 0.17.0 was contract v1.3.
    # Keep in lockstep with pyproject — the Studio engine badge reads THIS
    # constant.
    assert aiadra_version == "0.19.1"


# =============================================================================
# 2. D16 TransactionDraft.kind: str generalization
# =============================================================================


def test_d16_kind_accepts_namespaced_string(tmp_path: Path):
    """ADR/0028 D16: TransactionDraft.kind accepts plain string like
    'mechanical.adjust_parameter'."""
    bundle = _bundle_latest()
    draft = TransactionDraft(
        workspace=tmp_path,
        bundle=bundle,
        kind="mechanical.adjust_parameter",
        transaction_id="tx_0001",
    )
    assert draft.kind == "mechanical.adjust_parameter"
    assert isinstance(draft.kind, str)


def test_d16_kind_normalizes_transaction_kind_enum_member(tmp_path: Path):
    """ADR/0028 D16 __post_init__: TransactionKind enum members get extracted
    to plain str so audit/commit serialization no longer needs .value."""
    bundle = _bundle_latest()
    draft = TransactionDraft(
        workspace=tmp_path,
        bundle=bundle,
        kind=TransactionKind.CHANGE_PARAMETER,
        transaction_id="tx_0002",
    )
    assert draft.kind == "change_parameter"
    assert type(draft.kind) is str
    assert not isinstance(draft.kind, TransactionKind)


def test_d16_kind_str_interpolates_cleanly_in_commit_message(tmp_path: Path):
    """ADR/0028 D16: f-string interpolation on `self.kind` produces the
    bare string value (no 'TransactionKind.X' prefix)."""
    bundle = _bundle_latest()
    draft = TransactionDraft(
        workspace=tmp_path,
        bundle=bundle,
        kind=TransactionKind.INIT,
        transaction_id="tx_0003",
    )
    msg = f"aiadra: {draft.kind} {draft.transaction_id}"
    assert msg == "aiadra: init tx_0003"


# =============================================================================
# 3. NativeEngineRegistrar per-call invariants (B1 + N3)
# =============================================================================


def test_registrar_engine_id_immutable_from_construction():
    """Codex1 B1 R1: engine_id cannot be reassigned, even during register()
    (before _frozen_view is called)."""
    reg = NativeEngineRegistrar(engine_id="mechanical")
    assert reg.engine_id == "mechanical"
    with pytest.raises(NativeEngineRegistrationError, match="immutable"):
        reg.engine_id = "evil"
    assert reg.engine_id == "mechanical"  # unchanged


def test_registrar_other_attributes_also_immutable():
    """B1 extends to ALL attributes — engine code cannot poke any registrar field."""
    reg = NativeEngineRegistrar(engine_id="mechanical")
    with pytest.raises(NativeEngineRegistrationError):
        reg._engine_id = "evil"
    with pytest.raises(NativeEngineRegistrationError):
        reg._frozen = True
    with pytest.raises(NativeEngineRegistrationError):
        reg._operations = {}


def test_registrar_rejects_kind_outside_namespace():
    """ADR/0028 D2 invariant #2."""
    reg = NativeEngineRegistrar(engine_id="mechanical")
    with pytest.raises(NativeEngineRegistrationError, match="outside its namespace"):
        reg.add_operation(
            "electrical.foo", lambda ctx, params: None  # not mechanical.*
        )


def test_registrar_rejects_builtin_overwrite(monkeypatch):
    """ADR/0028 D2 invariant #3. Defense-in-depth: under normal operation,
    invariant #2 (namespace discipline — engine kinds must have a dot, built-in
    kinds don't) makes invariant #3 unreachable. To test it directly, inject a
    fake dotted built-in into _PROPOSE_DISPATCH and try to register the same
    kind from an engine that satisfies the namespace prefix.
    """
    from aiadra_core.protocol import _PROPOSE_DISPATCH

    # Inject a fake dotted built-in (synthetic — would never exist normally).
    monkeypatch.setitem(_PROPOSE_DISPATCH, "mechanical.builtin_synthetic",
                        lambda *a, **kw: None)
    reg = NativeEngineRegistrar(engine_id="mechanical")
    # Namespace check #2 passes (kind starts with "mechanical."); built-in
    # check #3 catches the collision.
    with pytest.raises(NativeEngineRegistrationError, match="overwrite built-in"):
        reg.add_operation("mechanical.builtin_synthetic", lambda c, p: None)


def test_registrar_rejects_duplicate_within_engine():
    """Duplicate kind in the same register() call."""
    reg = NativeEngineRegistrar(engine_id="mechanical")
    reg.add_operation("mechanical.foo", lambda ctx, params: None)
    with pytest.raises(NativeEngineRegistrationError, match="duplicate registration"):
        reg.add_operation("mechanical.foo", lambda ctx, params: None)


def test_registrar_arity_check_accepts_any_param_names():
    """Codex1 N3 R1: arity-only signature check. Param names can be anything."""
    reg = NativeEngineRegistrar(engine_id="mechanical")
    # Both shapes accepted:
    reg.add_operation("mechanical.foo", lambda ctx, params: None)
    reg.add_operation("mechanical.bar", lambda c, p: None)
    reg.add_operation("mechanical.baz", lambda context, kwargs_dict: None)


def test_registrar_rejects_wrong_arity():
    """ADR/0028 D2 invariant #6: handler must accept exactly 2 positional params."""
    reg = NativeEngineRegistrar(engine_id="mechanical")
    with pytest.raises(NativeEngineRegistrationError, match="wrong arity"):
        reg.add_operation("mechanical.foo", lambda ctx: None)  # 1 arg
    reg2 = NativeEngineRegistrar(engine_id="mechanical")
    with pytest.raises(NativeEngineRegistrationError, match="wrong arity"):
        reg2.add_operation("mechanical.bar", lambda a, b, c: None)  # 3 args
    reg3 = NativeEngineRegistrar(engine_id="mechanical")
    with pytest.raises(NativeEngineRegistrationError, match="wrong arity"):
        reg3.add_operation("mechanical.qux", lambda: None)  # 0 args


def test_registrar_rejects_non_callable():
    reg = NativeEngineRegistrar(engine_id="mechanical")
    with pytest.raises(NativeEngineRegistrationError, match="not callable"):
        reg.add_operation("mechanical.foo", "not_a_function")  # type: ignore[arg-type]


def test_registrar_rejects_add_after_frozen_view():
    reg = NativeEngineRegistrar(engine_id="mechanical")
    reg.add_operation("mechanical.foo", lambda c, p: None)
    reg._frozen_view()
    with pytest.raises(NativeEngineRegistrationError, match="frozen"):
        reg.add_operation("mechanical.bar", lambda c, p: None)


def test_registrar_frozen_view_returns_sorted_operations():
    """Deterministic order per ADR/0028 D2 invariant #7."""
    reg = NativeEngineRegistrar(engine_id="mechanical")
    reg.add_operation("mechanical.zebra", lambda c, p: None)
    reg.add_operation("mechanical.alpha", lambda c, p: None)
    reg.add_operation("mechanical.beta", lambda c, p: None)
    frozen = reg._frozen_view()
    kinds = [k for k, _h in frozen.operations]
    assert kinds == ["mechanical.alpha", "mechanical.beta", "mechanical.zebra"]


# =============================================================================
# 4. Two-pass discovery (B1 R3 from arc 12 — duplicate engine_id rejection)
# =============================================================================


def _make_register_fn(operations: list[tuple[str, Any]]):
    """Build a register(registrar) fn that adds the given operations."""

    def register(registrar: NativeEngineRegistrar) -> None:
        for kind, handler in operations:
            registrar.add_operation(kind, handler)

    return register


def test_discovery_loads_single_engine_happy_path():
    register_fn = _make_register_fn(
        [("mechanical.foo", lambda c, p: None), ("mechanical.bar", lambda c, p: None)]
    )
    ep = _FakeEntryPoint("mechanical", register_fn, dist_name="aiadra-mechanical")
    with _patch_entry_points([ep]):
        loaded, failures = _discover_native_engines()
    assert "mechanical" in loaded
    assert failures == {}
    assert [k for k, _ in loaded["mechanical"].operations] == [
        "mechanical.bar",
        "mechanical.foo",
    ]


def test_discovery_rejects_duplicate_engine_id_across_distributions():
    """Codex2 B1 R3 from arc 20260531-12: two distributions claiming
    `engine_id='mechanical'` are BOTH rejected before any load."""
    register_fn = _make_register_fn([("mechanical.foo", lambda c, p: None)])
    ep_a = _FakeEntryPoint("mechanical", register_fn, dist_name="aiadra-mechanical-a")
    ep_b = _FakeEntryPoint("mechanical", register_fn, dist_name="aiadra-mechanical-b")
    with _patch_entry_points([ep_a, ep_b]):
        loaded, failures = _discover_native_engines()
    assert "mechanical" not in loaded
    assert "mechanical" in failures
    assert "duplicate engine_id" in str(failures["mechanical"])
    assert "aiadra-mechanical-a" in str(failures["mechanical"])
    assert "aiadra-mechanical-b" in str(failures["mechanical"])


def test_discovery_isolates_engine_load_failures():
    """A broken engine in `register()` doesn't poison built-in dispatch or
    sibling engines (per-engine isolation per ADR/0028 D5 pass 2)."""

    def broken_register(registrar):
        raise RuntimeError("OCCT not installed")

    good_fn = _make_register_fn([("electrical.foo", lambda c, p: None)])
    ep_bad = _FakeEntryPoint("mechanical", broken_register)
    ep_good = _FakeEntryPoint("electrical", good_fn)
    with _patch_entry_points([ep_bad, ep_good]):
        loaded, failures = _discover_native_engines()
    assert "mechanical" in failures
    assert "electrical" in loaded  # sibling unaffected
    assert isinstance(failures["mechanical"], RuntimeError)


def test_discovery_preserves_cause_on_engine_load_failure():
    """ADR/0028 D5 case 3: `__cause__` preservation for diagnostics."""

    def broken_register(registrar):
        try:
            raise ImportError("OCCT missing")
        except ImportError as e:
            raise RuntimeError("engine init failed") from e

    ep = _FakeEntryPoint("mechanical", broken_register)
    with _patch_entry_points([ep]):
        loaded, failures = _discover_native_engines()
    err = failures["mechanical"]
    assert isinstance(err.__cause__, ImportError)


# =============================================================================
# 5. Dispatch lookup four-case discipline (ADR/0028 D5)
# =============================================================================


def test_dispatch_builtin_kind_unaffected_by_engine_load_state(tmp_path: Path):
    """Built-in `change_parameter` works whether engines are loaded or not."""
    # No engines registered (default empty).
    workspace = _init_workspace(tmp_path)
    # Confirm change_parameter dispatch works — uses _resolve_propose_handler
    # which returns the built-in directly from _PROPOSE_DISPATCH.
    handler = _resolve_propose_handler("change_parameter")
    assert handler is not None


def test_dispatch_raises_engine_not_available_when_engine_missing():
    """ADR/0028 D5 case 4: engine_id not installed.

    Uses a guaranteed-never-installed engine_id. Friction surfaced by the
    aiadra-mechanical install (arc 20260602-1): `mechanical` is now a REAL
    installed engine_id, so a test asserting it is "not installed" must use a
    fake id that no real package declares (extends the arc 20260601-3 / arc-5
    README rule "no test may assume a specific real engine_id is absent")."""
    with pytest.raises(EngineNotAvailableError, match="not installed"):
        _resolve_propose_handler("faketestengine.adjust_parameter")


def test_dispatch_raises_engine_not_available_when_engine_failed():
    """ADR/0028 D5 case 3: engine_id failed to load."""

    def broken_register(registrar):
        raise RuntimeError("OCCT init failed")

    ep = _FakeEntryPoint("mechanical", broken_register)
    with _patch_entry_points([ep]):
        refresh_native_engines()
        with pytest.raises(EngineNotAvailableError, match="failed to load") as excinfo:
            _resolve_propose_handler("mechanical.adjust_parameter")
        assert isinstance(excinfo.value.__cause__, RuntimeError)


def test_dispatch_raises_engine_not_available_when_kind_unknown_to_loaded_engine():
    """Fifth case (added arc 20260601-1): engine loaded but doesn't register
    this specific kind."""
    register_fn = _make_register_fn([("mechanical.foo", lambda c, p: None)])
    ep = _FakeEntryPoint("mechanical", register_fn)
    with _patch_entry_points([ep]):
        refresh_native_engines()
        with pytest.raises(EngineNotAvailableError, match="does not register kind"):
            _resolve_propose_handler("mechanical.adjust_parameter")


def test_dispatch_raises_value_error_on_kind_without_dot():
    """Not built-in + not namespaced → ValueError (NOT EngineNotAvailableError)."""
    with pytest.raises(ValueError, match="Unknown kind"):
        _resolve_propose_handler("totally_made_up")


def test_dispatch_loaded_engine_kind_returns_adapter():
    register_fn = _make_register_fn(
        [("mechanical.foo", lambda ctx, params: ctx.stage_event({"x": 1}))]
    )
    ep = _FakeEntryPoint("mechanical", register_fn)
    with _patch_entry_points([ep]):
        refresh_native_engines()
        handler = _resolve_propose_handler("mechanical.foo")
        assert callable(handler)


# =============================================================================
# 6. propose_kinds() + modify_kinds() return combined built-in + engine kinds
# =============================================================================


def test_propose_kinds_includes_loaded_engine_kinds():
    register_fn = _make_register_fn(
        [("mechanical.adjust_parameter", lambda c, p: None),
         ("mechanical.add_extrude", lambda c, p: None)]
    )
    ep = _FakeEntryPoint("mechanical", register_fn)
    with _patch_entry_points([ep]):
        refresh_native_engines()
        kinds = propose_kinds()
        assert "mechanical.adjust_parameter" in kinds
        assert "mechanical.add_extrude" in kinds
        # Built-ins still present:
        assert "change_parameter" in kinds


def test_modify_kinds_excludes_init_and_release_even_with_engines():
    register_fn = _make_register_fn([("mechanical.foo", lambda c, p: None)])
    ep = _FakeEntryPoint("mechanical", register_fn)
    with _patch_entry_points([ep]):
        refresh_native_engines()
        kinds = modify_kinds()
        assert "init" not in kinds
        assert "release" not in kinds
        assert "mechanical.foo" in kinds


def test_propose_kinds_excludes_failed_engines():
    def broken_register(registrar):
        raise RuntimeError("init failed")

    ep = _FakeEntryPoint("mechanical", broken_register)
    with _patch_entry_points([ep]):
        refresh_native_engines()
        kinds = propose_kinds()
        # mechanical.* not present because engine failed
        assert not any(k.startswith("mechanical.") for k in kinds)


# =============================================================================
# 7. NativeEngineContext surface (B4 R1 absorption)
# =============================================================================


def _make_context(workspace, bundle, *, actor="agent", operation_kind="mechanical.foo",
                  engine_id="mechanical"):
    draft = TransactionDraft(
        workspace=workspace,
        bundle=bundle,
        kind=operation_kind,
        transaction_id="tx_0001",
    )
    return NativeEngineContext(
        draft=draft,
        workspace=workspace,
        bundle=bundle,
        actor=actor,
        operation_kind=operation_kind,
        engine_id=engine_id,
    )


def test_context_protocol_version_is_1_0(tmp_path: Path):
    ctx = _make_context(tmp_path, _bundle_latest())
    assert ctx.protocol_version == "1.0"


def test_context_introspection_properties(tmp_path: Path):
    ctx = _make_context(tmp_path, _bundle_latest(), actor="human")
    assert ctx.workspace == tmp_path
    assert ctx.actor == "human"
    assert ctx.operation_kind == "mechanical.foo"
    assert ctx.engine_id == "mechanical"
    assert ctx.transaction_id == "tx_0001"


def test_context_b4_not_a_dataclass(tmp_path: Path):
    """Codex1 B4 R1: NativeEngineContext is NOT a dataclass — _draft does not
    appear in dataclasses.fields()."""
    ctx = _make_context(tmp_path, _bundle_latest())
    assert not dataclasses.is_dataclass(ctx)
    with pytest.raises(TypeError):
        dataclasses.fields(ctx)


def test_context_b4_uses_slots(tmp_path: Path):
    """Codex1 B4 R1: __slots__ prevents arbitrary attribute injection."""
    ctx = _make_context(tmp_path, _bundle_latest())
    assert hasattr(NativeEngineContext, "__slots__")
    with pytest.raises(AttributeError):
        ctx.some_random_attr = "evil"  # type: ignore[attr-defined]


def test_context_b4_repr_does_not_expose_draft(tmp_path: Path):
    """Codex1 B4 R1: custom __repr__ shows context surface, NOT raw draft state."""
    ctx = _make_context(tmp_path, _bundle_latest())
    r = repr(ctx)
    assert "engine_id='mechanical'" in r
    assert "TransactionDraft" not in r
    assert "sidecar_writes" not in r


def test_context_stage_sidecar_proxies_to_draft(tmp_path: Path):
    ctx = _make_context(tmp_path, _bundle_latest())
    ctx.stage_sidecar("uuid-1", {"object": {"uuid": "uuid-1"}})
    assert "uuid-1" in ctx._draft.sidecar_writes


def test_context_stage_event_proxies_to_draft(tmp_path: Path):
    ctx = _make_context(tmp_path, _bundle_latest())
    ctx.stage_event({"event_id": "evt_0001", "event_type": "test"})
    assert len(ctx._draft.events) == 1


# =============================================================================
# 8. B2: make_event + emit_event envelope helpers (draft-aware event-id)
# =============================================================================


def test_context_make_event_builds_canonical_envelope(tmp_path: Path):
    """Codex1 B2 R1: make_event populates schema_version + event_id +
    event_type + timestamp + transaction_id + actor + payload."""
    workspace = _init_workspace(tmp_path)
    bundle = _bundle_latest()
    ctx = _make_context(workspace, bundle, actor="agent",
                        operation_kind="mechanical.foo")
    ev = ctx.make_event("part_changed", {"object_uuid": "xxx", "feature_delta": {"added": []}})
    assert ev["event_type"] == "part_changed"
    assert ev["schema_version"] == bundle.bundle_version
    assert ev["event_id"].startswith("evt_")
    assert ev["transaction_id"] == ctx.transaction_id
    assert ev["actor"] == "agent"
    assert ev["payload"]["object_uuid"] == "xxx"
    assert "timestamp" in ev


def test_context_make_event_allocates_distinct_ids_across_calls(tmp_path: Path):
    """Codex1 B2 R1: two composed operations in one draft do not collide on event_id."""
    workspace = _init_workspace(tmp_path)
    bundle = _bundle_latest()
    ctx = _make_context(workspace, bundle)
    ev1 = ctx.make_event("part_changed", {"object_uuid": "x"})
    ctx.stage_event(ev1)  # adds to draft.events
    ev2 = ctx.make_event("part_changed", {"object_uuid": "y"})
    assert ev1["event_id"] != ev2["event_id"]


def test_context_emit_event_makes_and_stages(tmp_path: Path):
    """emit_event = make_event + stage_event in one call."""
    workspace = _init_workspace(tmp_path)
    ctx = _make_context(workspace, _bundle_latest())
    before = len(ctx._draft.events)
    ev = ctx.emit_event("part_changed", {"object_uuid": "z"})
    assert len(ctx._draft.events) == before + 1
    assert ctx._draft.events[-1] is ev


def test_context_make_event_actor_override(tmp_path: Path):
    """actor= kwarg overrides context.actor for a specific event."""
    ctx = _make_context(tmp_path, _bundle_latest(), actor="agent")
    ev = ctx.make_event("test", {}, actor="human")
    assert ev["actor"] == "human"


# =============================================================================
# 8b. event_log_last_event_id() conformance (arc 20260601-5 Action A)
# =============================================================================
# Per arc 20260601-4 Codex1 B1 R1 + arc 20260601-5 Codex1 absorption:
# the helper at native_engine/context.py:148-170 returns the highest event_id
# known to the workspace (committed + staged in this draft), or None if no
# events exist anywhere. ADR/0028 D6 names it as a cache-freshness primitive.
# Tests below lock the four documented semantic cases + one fail-loud
# regression (was: silent default to evt_0001 on corrupt event log; arc
# 20260601-5 removed the broad except guard).


def test_event_log_last_event_id_returns_none_for_empty_workspace(tmp_path: Path):
    """Arc 20260601-5 Action A case 1 (per arc-4 Codex1 B1 R1 spec):
    truly empty workspace (no committed events, no staged events) → None."""
    ws = tmp_path / "ws"
    ws.mkdir()  # No init; no events.jsonl exists yet
    ctx = _make_context(ws, _bundle_latest())
    assert ctx.event_log_last_event_id() is None


def test_event_log_last_event_id_returns_last_committed_when_no_staged(tmp_path: Path):
    """Arc 20260601-5 Action A case 2: workspace with N committed events +
    fresh context with no staged events → returns evt_{N:04d}.

    Uses `create_part` (number + name) per arc-5 Codex1 B1 absorption.
    Note: `_init_workspace` itself commits NO events to events.jsonl
    (only stages the project pin); the first event appears here as
    evt_0001 from the part_created commit. Verified against
    transaction/operations.py::init_workspace (no event_log writes)."""
    ws = _init_workspace(tmp_path)  # commits NO events
    propose(ws, kind="create_part", params={
        "number": "P-000001",
        "name": "Test part",
    }).commit()  # commits evt_0001 (part_created)
    ctx = _make_context(ws, _bundle_latest())  # no staged events in this draft
    assert ctx.event_log_last_event_id() == "evt_0001"


def test_event_log_last_event_id_returns_highest_staged_in_composed_draft(tmp_path: Path):
    """Arc 20260601-5 Action A case 3: workspace with 1 committed event +
    draft staging K engine events (evt_0002, evt_0003, evt_0004) → helper
    returns evt_0004, NOT evt_0001. Proves proposed-workspace semantics
    per ADR/0028 D6 (committed + staged max), not committed-only-at-
    construction."""
    ws = _init_workspace(tmp_path)  # commits NO events
    propose(ws, kind="create_part", params={
        "number": "P-000001",
        "name": "Test part",
    }).commit()  # commits evt_0001 (part_created)
    ctx = _make_context(ws, _bundle_latest())
    # Stage 3 engine events via emit_event (mirrors nearby valid-ish
    # part_changed payload shape per arc-5 Codex1 N2 absorption)
    ev1 = ctx.emit_event("part_changed", {"object_uuid": "u1", "feature_delta": {"added": []}})
    ev2 = ctx.emit_event("part_changed", {"object_uuid": "u2", "feature_delta": {"added": []}})
    ev3 = ctx.emit_event("part_changed", {"object_uuid": "u3", "feature_delta": {"added": []}})
    assert ev1["event_id"] == "evt_0002"
    assert ev2["event_id"] == "evt_0003"
    assert ev3["event_id"] == "evt_0004"
    assert ctx.event_log_last_event_id() == "evt_0004"


def test_event_log_last_event_id_reads_current_draft_state_not_snapshot(tmp_path: Path):
    """Arc 20260601-5 Action A case 4 (edge case per Claude2 absorption +
    Codex1 Q6): helper reads CURRENT draft.events at call time, not a
    snapshot at context construction. Test by calling before + after
    staging one event in the same context."""
    ws = _init_workspace(tmp_path)  # commits NO events
    propose(ws, kind="create_part", params={
        "number": "P-000001",
        "name": "Test part",
    }).commit()  # commits evt_0001 (part_created)
    ctx = _make_context(ws, _bundle_latest())
    assert ctx.event_log_last_event_id() == "evt_0001"  # only committed
    ctx.emit_event("part_changed", {"object_uuid": "u1", "feature_delta": {"added": []}})
    assert ctx.event_log_last_event_id() == "evt_0002"  # updated read


def test_event_log_last_event_id_propagates_corrupt_event_log_failure(tmp_path: Path):
    """Arc 20260601-5 Action A regression (per Codex2 arc-4 non-blocking
    note + arc-5 Codex1 N1): the broad `except Exception:` guard at
    context.py:156-159 silently defaulted to evt_0001 on
    SchemaValidationError; per arc 20260531-8 Phase B Codex2 B1 R3 fail-
    loud discipline, corrupt event log MUST propagate so engines + AI
    agents know substrate is bad, not silently treat as empty.

    Arc 20260601-5 removed the broad guard; this test locks the new
    behavior."""
    from aiadra_core.validation.schema import SchemaValidationError

    ws = _init_workspace(tmp_path)  # creates valid events.jsonl with evt_0001
    # Append a line missing required event-envelope fields (event_type,
    # schema_version, etc.). Per the base event schema this will reject.
    bad_line = '{"event_id": "evt_9999"}\n'
    (ws / "events.jsonl").open("a", encoding="utf-8").write(bad_line)
    ctx = _make_context(ws, _bundle_latest())
    with pytest.raises(SchemaValidationError):
        ctx.event_log_last_event_id()


# =============================================================================
# 9. Hook adapter (Codex2 R3 from arc 12 + Codex3 N1 reject-loudly)
# =============================================================================


def test_hook_adapter_accepts_zero_arg_callable(tmp_path: Path):
    """0-arg hook (closure captures context)."""
    ctx = _make_context(tmp_path, _bundle_latest())
    called = []
    ctx.add_pre_validate_hook(lambda: called.append("pre"))
    # Simulate hook invocation as boundary.py does it:
    for hook in ctx._draft.pre_validate_hooks:
        hook(ctx._draft)
    assert called == ["pre"]


def test_hook_adapter_accepts_one_arg_callable_passes_context_not_draft(tmp_path: Path):
    """1-arg hook receives NativeEngineContext, NOT raw TransactionDraft."""
    ctx = _make_context(tmp_path, _bundle_latest())
    received = []
    ctx.add_pre_validate_hook(lambda received_ctx: received.append(received_ctx))
    for hook in ctx._draft.pre_validate_hooks:
        hook(ctx._draft)
    assert len(received) == 1
    assert received[0] is ctx  # the SAME context, not the raw draft
    assert isinstance(received[0], NativeEngineContext)


def test_hook_adapter_rejects_two_arg_callable_loudly(tmp_path: Path):
    """Codex3 N1 from arc 12: reject 2+ arg hooks loudly with
    NativeEngineRegistrationError."""
    ctx = _make_context(tmp_path, _bundle_latest())
    with pytest.raises(NativeEngineRegistrationError, match="unsupported arity"):
        ctx.add_pre_validate_hook(lambda a, b: None)


def test_hook_adapter_rejects_non_callable(tmp_path: Path):
    ctx = _make_context(tmp_path, _bundle_latest())
    with pytest.raises(NativeEngineRegistrationError, match="not callable"):
        ctx.add_pre_validate_hook("not_a_function")  # type: ignore[arg-type]


def test_hook_adapter_post_validate_same_arity_rules(tmp_path: Path):
    ctx = _make_context(tmp_path, _bundle_latest())
    ctx.add_post_validate_hook(lambda: None)
    ctx.add_post_validate_hook(lambda c: None)
    with pytest.raises(NativeEngineRegistrationError, match="unsupported arity"):
        ctx.add_post_validate_hook(lambda a, b, c: None)


# =============================================================================
# 10. NativeEngineKernelError adapter behavior
# =============================================================================


def test_kernel_exception_wrapped_with_engine_id_and_operation_kind(tmp_path: Path):
    """Adapter wraps kernel exceptions as NativeEngineKernelError preserving
    engine_id + operation_kind."""
    workspace = _init_workspace(tmp_path)

    def kernel_failing_handler(ctx, params):
        raise ZeroDivisionError("kernel crashed")

    register_fn = _make_register_fn([("mechanical.crash", kernel_failing_handler)])
    ep = _FakeEntryPoint("mechanical", register_fn)
    with _patch_entry_points([ep]):
        refresh_native_engines()
        with pytest.raises(NativeEngineKernelError) as excinfo:
            propose(workspace, kind="mechanical.crash", params={})
        assert excinfo.value.engine_id == "mechanical"
        assert excinfo.value.operation_kind == "mechanical.crash"
        assert isinstance(excinfo.value.__cause__, ZeroDivisionError)


def test_kernel_passthrough_transaction_error_not_wrapped(tmp_path: Path):
    """Handler raising TransactionError propagates as-is (not wrapped as
    NativeEngineKernelError)."""
    workspace = _init_workspace(tmp_path)

    def handler(ctx, params):
        raise TransactionError("invalid params")

    register_fn = _make_register_fn([("mechanical.bad", handler)])
    ep = _FakeEntryPoint("mechanical", register_fn)
    with _patch_entry_points([ep]):
        refresh_native_engines()
        with pytest.raises(TransactionError, match="invalid params"):
            propose(workspace, kind="mechanical.bad", params={})


# =============================================================================
# 11. refresh_native_engines() escape hatch
# =============================================================================


def test_refresh_native_engines_clears_cache():
    # Uses a never-installed fake engine_id so the after-exit assertion holds
    # regardless of real engines in the venv (arc 20260602-1: `mechanical` is
    # now a REAL installed engine_id via aiadra-mechanical).
    register_fn = _make_register_fn([("faketestengine.foo", lambda c, p: None)])
    ep = _FakeEntryPoint("faketestengine", register_fn)
    with _patch_entry_points([ep]):
        refresh_native_engines()
        loaded, _ = get_native_engines()
        assert "faketestengine" in loaded
    # After exiting the patch, refresh + re-discover no longer sees the fake:
    refresh_native_engines()
    loaded, _ = get_native_engines()
    assert "faketestengine" not in loaded


def test_protocol_refresh_is_same_as_native_engine_refresh():
    """aiadra_core.protocol.refresh_native_engines is the re-export."""
    register_fn = _make_register_fn([("faketestengine.foo", lambda c, p: None)])
    ep = _FakeEntryPoint("faketestengine", register_fn)
    with _patch_entry_points([ep]):
        refresh_native_engines()
        get_native_engines()  # populate cache
    protocol_refresh()  # via protocol re-export
    loaded, _ = get_native_engines()
    assert "faketestengine" not in loaded


# =============================================================================
# 12. native_engine_status() diagnostic helper (D10)
# =============================================================================


def test_native_engine_status_empty_when_no_engines():
    """Friction surfaced by Wedge-003 install (arc 20260601-3): pre-existing
    tests that ASSUMED no engines installed broke when the spike package
    was added to the dev venv. Fix: use the same monkeypatched-empty
    entry-points pattern as the other tests in this file."""
    with _patch_entry_points([]):
        refresh_native_engines()
        assert native_engine_status() == {}


def test_native_engine_status_lists_loaded_engines_with_operations():
    register_fn = _make_register_fn(
        [("mechanical.foo", lambda c, p: None),
         ("mechanical.bar", lambda c, p: None)]
    )
    ep = _FakeEntryPoint("mechanical", register_fn)
    with _patch_entry_points([ep]):
        refresh_native_engines()
        status = native_engine_status()
    assert status["mechanical"]["status"] == "loaded"
    assert sorted(status["mechanical"]["operations"]) == [
        "mechanical.bar", "mechanical.foo"
    ]
    assert status["mechanical"]["error"] is None


def test_native_engine_status_lists_failed_engines_with_error_cause():
    def broken_register(registrar):
        try:
            raise ImportError("OCCT not found")
        except ImportError as e:
            raise RuntimeError("init failed") from e

    ep = _FakeEntryPoint("mechanical", broken_register)
    with _patch_entry_points([ep]):
        refresh_native_engines()
        status = native_engine_status()
    assert status["mechanical"]["status"] == "failed"
    assert status["mechanical"]["operations"] == []
    assert "RuntimeError" in status["mechanical"]["error"]
    assert "ImportError" in status["mechanical"]["error_cause"]


# =============================================================================
# 13. B3: part_changed in B6 mutation-after-binding scan
# =============================================================================


def test_part_changed_classified_as_mutation_event_for_b6_scan():
    """Codex1 B3 R1: part_changed is a mutation event that participates in
    the Fixed-binding-mutation-prohibition scan (was previously bypassed)."""
    events = [
        # Fixed binding at event 0 — Object UUID-X bound to revision rev-1
        {
            "event_id": "evt_0001",
            "event_type": "relationship_created",
            "payload": {
                "source_uuid": "src-uuid",
                "relationship_record": {
                    "id": "rel_0001",
                    "type": "executes",
                    "binding": "fixed",
                    "endpoints": [
                        {"object_uuid": "uuid-X", "revision_id": "rev-1"}
                    ],
                },
            },
        },
        # part_changed at event 1 — mutates UUID-X (was previously bypassed!)
        {
            "event_id": "evt_0002",
            "event_type": "part_changed",
            "actor": "agent",
            "payload": {
                "object_uuid": "uuid-X",
                "feature_delta": {"added": []},
            },
        },
    ]
    violations = find_mutation_after_binding_violations_for_events(events)
    assert violations, "part_changed should now be detected as a mutation event"
    assert "uuid-X" in violations[0]
    assert "part_changed" in violations[0]


def test_requirement_changed_also_classified_as_mutation_event_for_b6_scan():
    """Codex1 B3 R1 also added requirement_changed (was missing — bug spotted
    while extending classifier for part_changed)."""
    events = [
        {
            "event_id": "evt_0001",
            "event_type": "relationship_created",
            "payload": {
                "source_uuid": "src-uuid",
                "relationship_record": {
                    "id": "rel_0001",
                    "type": "executes",
                    "binding": "fixed",
                    "endpoints": [
                        {"object_uuid": "uuid-R", "revision_id": "rev-1"}
                    ],
                },
            },
        },
        {
            "event_id": "evt_0002",
            "event_type": "requirement_changed",
            "payload": {
                "object_uuid": "uuid-R",
                "acceptance_criterion_delta": {"added": []},
            },
        },
    ]
    violations = find_mutation_after_binding_violations_for_events(events)
    assert violations
    assert "uuid-R" in violations[0]


# =============================================================================
# 14. End-to-end propose+commit via fake engine
# =============================================================================


def test_native_engine_propose_then_commit_happy_path(tmp_path: Path):
    """Fake engine emits a part_changed event via emit_event; propose returns
    a draft; (skip commit since the fake event isn't schema-valid for v0.28.0
    against a real Part — but the dispatch + adapter + draft return all work)."""
    workspace = _init_workspace(tmp_path)

    def handler(ctx, params):
        # Use the envelope helper per B2 R1.
        ctx.emit_event("part_changed", {
            "object_uuid": params["object_uuid"],
            "feature_delta": {"added": []},
        })

    register_fn = _make_register_fn([("mechanical.adjust_parameter", handler)])
    ep = _FakeEntryPoint("mechanical", register_fn)
    with _patch_entry_points([ep]):
        refresh_native_engines()
        draft = propose(
            workspace,
            kind="mechanical.adjust_parameter",
            params={"object_uuid": "01934567-89ab-7def-8123-456789abcdef"},
        )
    assert draft.kind == "mechanical.adjust_parameter"
    assert len(draft.events) == 1
    assert draft.events[0]["event_type"] == "part_changed"
    assert draft.events[0]["actor"] == "agent"


def test_native_engine_modify_extends_existing_draft(tmp_path: Path):
    """modify(kind='mechanical.foo') extends the SAME draft (composability)."""
    workspace = _init_workspace(tmp_path)

    def handler(ctx, params):
        ctx.emit_event("part_changed", {
            "object_uuid": params["object_uuid"],
            "feature_delta": {"added": []},
        })

    register_fn = _make_register_fn([("mechanical.foo", handler)])
    ep = _FakeEntryPoint("mechanical", register_fn)
    with _patch_entry_points([ep]):
        refresh_native_engines()
        draft1 = propose(workspace, kind="mechanical.foo",
                         params={"object_uuid": "uuid-a"})
        draft2 = modify(draft1, kind="mechanical.foo",
                        params={"object_uuid": "uuid-b"})
    assert draft1 is draft2  # same instance
    assert len(draft1.events) == 2
    # Codex1 B2 R1: event ids must be distinct
    ids = [e["event_id"] for e in draft1.events]
    assert ids[0] != ids[1]
