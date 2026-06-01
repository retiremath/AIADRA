"""Two-pass `_discover_native_engines()` per ADR/0028 D5 + Codex2 B1 R3
absorption arc 20260531-12. Module-level cache + `refresh_native_engines()`
escape hatch + `native_engine_status()` diagnostic helper.

Per Codex1 N2 R1 absorption arc 20260601-1: the explicit cross-engine
kind-collision check is DROPPED — once duplicate-engine_id rejection
(invariant #5, pass 1) and namespace discipline (invariant #2, per-call) are
enforced, two distinct engines CANNOT both register the same kind because
each kind must start with its own (unique) engine_id. The collision would
require both engines to share an engine_id, which pass 1 rejects.
"""
from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any

from .exceptions import NativeEngineRegistrationError
from .registrar import NativeEngineRegistrar, _EngineRegistration


ENTRY_POINT_GROUP = "aiadra.native_engines"


# Module-level cache. None = not yet discovered. Populated on first call to
# `get_native_engines()`; cleared by `refresh_native_engines()`.
_CACHE: tuple[dict[str, _EngineRegistration], dict[str, Exception]] | None = None


def _discover_native_engines() -> tuple[
    dict[str, _EngineRegistration], dict[str, Exception]
]:
    """Two-pass entry-point discovery per ADR/0028 D5 + Codex2 B1 R3 absorption
    arc 20260531-12.

    Pass 1: group entry-points by name. If any name has >1 distribution, reject
            the entire group upfront with `NativeEngineRegistrationError`
            listing the colliding distributions; no load attempt is made.
    Pass 2: per-engine isolated load. A broken engine cannot poison built-ins
            or other engines — exceptions land in the failures map with
            `__cause__` preserved.

    Returns:
        (loaded, failures) — both dicts keyed by engine_id (str).
            loaded[engine_id] = frozen `_EngineRegistration`
            failures[engine_id] = Exception (with __cause__ preserved when relevant)
    """
    loaded: dict[str, _EngineRegistration] = {}
    failures: dict[str, Exception] = {}

    # Pass 1: group by entry-point name (= engine_id).
    groups: dict[str, list] = {}
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        groups.setdefault(ep.name, []).append(ep)

    for engine_id, eps in groups.items():
        if len(eps) > 1:
            distributions = sorted(
                {ep.dist.name for ep in eps if ep.dist is not None}
            )
            failures[engine_id] = NativeEngineRegistrationError(
                f"duplicate engine_id {engine_id!r} declared by multiple "
                f"installed distributions: {distributions}; ALL rejected per "
                f"ADR/0028 D2 invariant #5 + Codex2 B1 R3 absorption arc "
                f"20260531-12. Resolve by uninstalling all but one of: "
                f"{distributions}"
            )
            continue

        # Pass 2: per-engine isolated load.
        ep = eps[0]
        try:
            register_fn = ep.load()
            registrar = NativeEngineRegistrar(engine_id=engine_id)
            register_fn(registrar)
            loaded[engine_id] = registrar._frozen_view()
        except Exception as e:
            failures[engine_id] = e

    return loaded, failures


def get_native_engines() -> tuple[
    dict[str, _EngineRegistration], dict[str, Exception]
]:
    """Lazy-cached discovery. First call populates the module cache; subsequent
    calls return the cached tuple. Use `refresh_native_engines()` to clear
    the cache (e.g., in tests after registering fake engines).
    """
    global _CACHE
    if _CACHE is None:
        _CACHE = _discover_native_engines()
    return _CACHE


def refresh_native_engines() -> None:
    """Force re-discovery on next `get_native_engines()` call. Per ADR/0028
    D5 + Codex Q6: explicit escape hatch for tests + embedding scenarios."""
    global _CACHE
    _CACHE = None


def native_engine_status() -> dict[str, dict[str, Any]]:
    """Diagnostic helper per ADR/0028 D15 item 11 + Codex1 N4 R1 acknowledgement
    arc 20260601-1.

    Returns a dict keyed by engine_id with:
        {
          "status": "loaded" | "failed",
          "operations": [kind, ...] | [],  # only populated for "loaded"
          "error": str | None,             # only populated for "failed"
          "error_cause": str | None,       # only populated when failure has __cause__
        }
    """
    loaded, failures = get_native_engines()
    out: dict[str, dict[str, Any]] = {}
    for engine_id, reg in loaded.items():
        out[engine_id] = {
            "status": "loaded",
            "operations": [kind for kind, _handler in reg.operations],
            "error": None,
            "error_cause": None,
        }
    for engine_id, err in failures.items():
        if engine_id in out:
            continue  # defensive — pass 1 + pass 2 should never both produce same id
        out[engine_id] = {
            "status": "failed",
            "operations": [],
            "error": f"{type(err).__name__}: {err}",
            "error_cause": repr(err.__cause__) if err.__cause__ else None,
        }
    return out
