"""Read-only Native Engine operation lane (arc 20260609-1 Codex1 B1).

Proves the read path is a GENUINE read-only boundary, not the mutation adapter
with discipline-by-convention:
  - read ops live in a separate registry lane (`read_operations`), never in
    `propose_kinds()` / `modify_kinds()`; visible in `native_engine_status`.
  - read handlers receive `NativeEngineReadContext` — NO `stage_*`,
    `emit_event`, `make_event`, validation hooks, or `transaction_id`.
  - dispatching a read creates NO TransactionDraft and writes nothing.
  - `display_representation` engine-resolution fails loud on the B1 cases.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from aiadra_core.native_engine.discovery import refresh_native_engines
from aiadra_core.native_engine.read_context import NativeEngineReadContext
from aiadra_core.protocol import (
    EngineNotAvailableError,
    NativeEngineRegistrar,
    NativeEngineRegistrationError,
    ObjectNotFoundError,
    TransactionError,
    modify_kinds,
    native_engine_status,
    propose,
    propose_kinds,
    read_kinds,
)
from aiadra_core.protocol import (
    _dispatch_read,
    _resolve_producing_engine,
    _resolve_read_handler,
)
from aiadra_core.validation.bundle_registry import BundleRegistry


# ----------------------------------------------------------------------------
# Fake engine scaffolding (no OCCT)
# ----------------------------------------------------------------------------


class _FakeEntryPoint:
    def __init__(self, name, load_fn, dist_name="fake-dist"):
        self.name = name
        self._load_fn = load_fn
        self.dist = type("FakeDist", (), {"name": dist_name})()

    def load(self):
        return self._load_fn


def _patch_entry_points(eps):
    def fake_entry_points(*, group):
        return eps if group == "aiadra.native_engines" else []

    return patch(
        "aiadra_core.native_engine.discovery.entry_points",
        side_effect=fake_entry_points,
    )


def _mut_handler(context, params):  # arity-2 mutation handler (no-op)
    return None


_CAPTURED: dict = {}


def _read_handler(context, params):
    """A read handler that records the context it was handed + returns a
    minimal-but-valid display dict."""
    _CAPTURED["context"] = context
    _CAPTURED["params"] = params
    return {
        "display_representation_version": "1.0",
        "identity": {"object_uuid": "u", "object_number": "N",
                     "geometry_ref": "sha256:x", "cache_key": "ck",
                     "topology_signature": "topo_x"},
        "render": {"faces": [], "edges": [], "vertices": [],
                   "bbox_min": [0, 0, 0], "bbox_max": [0, 0, 0],
                   "linear_deflection_mm": 0.1, "angular_deflection_rad": 0.5},
        "selection": {"id_space": "canonical", "pickable_kinds": [], "names": {}},
        "view_dependent": None,
        "invalidation": {"stale_when": [], "selection_invalid_when": "x"},
        "counters": {"face_count": 0, "edge_count_by_kind": {},
                     "triangle_count": 0, "vertex_count": 0},
    }


def _register_fake(registrar):
    registrar.add_operation("fakeeng.mutate", _mut_handler)
    registrar.add_read_operation("fakeeng.read_thing", _read_handler)


@pytest.fixture(autouse=True)
def _reset_cache():
    refresh_native_engines()
    _CAPTURED.clear()
    yield
    refresh_native_engines()


def _init_ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    propose(ws, kind="init", params={}).commit()
    return ws


# ----------------------------------------------------------------------------
# 1. Registry lane separation
# ----------------------------------------------------------------------------


def test_read_op_not_in_propose_or_modify_kinds():
    ep = _FakeEntryPoint("fakeeng", _register_fake)
    with _patch_entry_points([ep]):
        refresh_native_engines()
        assert "fakeeng.read_thing" in read_kinds()
        assert "fakeeng.read_thing" not in propose_kinds()
        assert "fakeeng.read_thing" not in modify_kinds()
        # The mutation op stays where it belongs.
        assert "fakeeng.mutate" in propose_kinds()
        assert "fakeeng.mutate" not in read_kinds()


def test_native_engine_status_shows_read_ops_distinctly():
    ep = _FakeEntryPoint("fakeeng", _register_fake)
    with _patch_entry_points([ep]):
        refresh_native_engines()
        status = native_engine_status()["fakeeng"]
        assert status["status"] == "loaded"
        assert status["operations"] == ["fakeeng.mutate"]
        assert status["read_operations"] == ["fakeeng.read_thing"]


# ----------------------------------------------------------------------------
# 2. The read context is genuinely non-mutating
# ----------------------------------------------------------------------------


def test_read_context_has_no_staging_surface(tmp_path: Path):
    bundle = BundleRegistry().latest()
    ctx = NativeEngineReadContext(
        workspace=tmp_path, bundle=bundle, actor="agent",
        operation_kind="fakeeng.read_thing", engine_id="fakeeng",
    )
    for forbidden in (
        "stage_sidecar", "stage_event", "stage_vault_bytes", "stage_reservation",
        "stage_revision", "stage_project_pin", "emit_event", "make_event",
        "add_pre_validate_hook", "add_post_validate_hook", "transaction_id",
        "_draft",
    ):
        assert not hasattr(ctx, forbidden), f"read context must not expose {forbidden}"
    # ... but it DOES expose the committed-read surface.
    for allowed in (
        "workspace", "bundle", "actor", "engine_id", "operation_kind",
        "load_sidecar", "load_reservation", "find_reservation_entry_by_number",
        "event_log_last_event_id",
    ):
        assert hasattr(ctx, allowed), f"read context must expose {allowed}"


def test_dispatch_read_hands_read_only_context(tmp_path: Path):
    ws = _init_ws(tmp_path)
    bundle = BundleRegistry().bundle_for_pin(ws)
    ep = _FakeEntryPoint("fakeeng", _register_fake)
    with _patch_entry_points([ep]):
        refresh_native_engines()
        result = _dispatch_read(
            "fakeeng", "fakeeng.read_thing", ws, bundle,
            {"object_uuid": "u"}, "agent",
        )
    assert result["display_representation_version"] == "1.0"
    ctx = _CAPTURED["context"]
    assert isinstance(ctx, NativeEngineReadContext)
    assert not hasattr(ctx, "stage_sidecar")


# ----------------------------------------------------------------------------
# 3. A read writes nothing (no draft, no events, no files)
# ----------------------------------------------------------------------------


def _snapshot(ws: Path) -> set[str]:
    return {str(p.relative_to(ws)) for p in ws.rglob("*") if p.is_file()
            and ".git" not in p.parts}


def test_read_dispatch_writes_nothing(tmp_path: Path):
    ws = _init_ws(tmp_path)
    bundle = BundleRegistry().bundle_for_pin(ws)
    before = _snapshot(ws)
    ep = _FakeEntryPoint("fakeeng", _register_fake)
    with _patch_entry_points([ep]):
        refresh_native_engines()
        _dispatch_read("fakeeng", "fakeeng.read_thing", ws, bundle,
                       {"object_uuid": "u"}, "agent")
        # propose/modify catalogues unchanged by a read.
        assert "fakeeng.read_thing" not in propose_kinds()
    after = _snapshot(ws)
    assert before == after, "a read operation must not write any workspace file"


# ----------------------------------------------------------------------------
# 4. display_representation engine-resolution fail-loud (B1 close conditions)
# ----------------------------------------------------------------------------


def _sidecar(geometry_refs, features):
    return {
        "object": {"uuid": "u-1", "number": "PRT-0001", "type": "Part"},
        "geometry_ref": geometry_refs,
        "feature": features,
    }


def test_resolve_engine_no_authoring_geometry():
    sc = _sidecar([], [])
    with pytest.raises(ObjectNotFoundError, match="no authoring_geometry"):
        _resolve_producing_engine(sc, "PRT-0001")


def test_resolve_engine_no_engine_discriminator():
    sc = _sidecar(
        [{"role": "authoring_geometry", "derived_from_feature_ids": ["feat_0001"]}],
        [{"id": "feat_0001", "feature_type": "sketch"}],  # no `engine`
    )
    with pytest.raises(ObjectNotFoundError, match="no feature carries an `engine`"):
        _resolve_producing_engine(sc, "PRT-0001")


def test_resolve_engine_multiple_engines_rejected():
    sc = _sidecar(
        [{"role": "authoring_geometry",
          "derived_from_feature_ids": ["feat_0001", "feat_0002"]}],
        [{"id": "feat_0001", "feature_type": "sketch", "engine": "mechanical"},
         {"id": "feat_0002", "feature_type": "sketch", "engine": "electrical"}],
    )
    with pytest.raises(TransactionError, match="multiple engines"):
        _resolve_producing_engine(sc, "PRT-0001")


def test_resolve_engine_single():
    sc = _sidecar(
        [{"role": "authoring_geometry", "derived_from_feature_ids": ["feat_0001"]}],
        [{"id": "feat_0001", "feature_type": "sketch", "engine": "mechanical"}],
    )
    assert _resolve_producing_engine(sc, "PRT-0001") == "mechanical"


def test_resolve_read_handler_engine_not_installed():
    with _patch_entry_points([]):
        refresh_native_engines()
        with pytest.raises(EngineNotAvailableError, match="not installed"):
            _resolve_read_handler("ghost", "ghost.display_representation")


# ----------------------------------------------------------------------------
# 5. add_read_operation invariants
# ----------------------------------------------------------------------------


def test_add_read_operation_namespace_discipline():
    reg = NativeEngineRegistrar(engine_id="fakeeng")
    with pytest.raises(NativeEngineRegistrationError, match="outside its namespace"):
        reg.add_read_operation("other.read", _read_handler)


def test_kind_cannot_be_both_mutation_and_read():
    reg = NativeEngineRegistrar(engine_id="fakeeng")
    reg.add_operation("fakeeng.x", _mut_handler)
    with pytest.raises(NativeEngineRegistrationError, match="duplicate"):
        reg.add_read_operation("fakeeng.x", _read_handler)


def test_read_op_arity_checked():
    reg = NativeEngineRegistrar(engine_id="fakeeng")
    with pytest.raises(NativeEngineRegistrationError, match="arity"):
        reg.add_read_operation("fakeeng.bad", lambda context: None)
