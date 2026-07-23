"""Per-process evaluated-solid cache with the ADR/0031 D8 freshness key.

Per [ADR/0028 D6] Native Engine caches are advisory + per-process; before
reuse a handler must prove the cached inputs still match current Workspace
authority. The cache key (ADR/0031 D8 + arc 20260602-1 Codex1 N3) is:

    (recipe-hash, event_log_last_event_id, adapter_schema_version, OCP/OCCT version)

DE-EQUALIZATION (ADR/0038 A4.7, arc 20260717-2): the recipe-hash component is
the hash of the WHOLE current feature list — a display/evaluation STATE key.
It is deliberately NOT the body `geometry_ref.vault_ref`: since A4.7, geometry
records stage only the PROJECTION of their head's dependency closure, so a
Part carrying an independent unconsumed sketch has a whole-list cache hash
that differs from every stored record's ref. The former "coincides with
vault_ref" claim is retired (it was true only while every record staged the
whole list); the cache key is an explicit COMPOSITION — whole-recipe state
(covering the body projection AND every non-body display input) + the
event-log boundary + version material. `vault_ref` stays recipe-only per
ADR/0031 D6, and identity never derives FROM this key. Including the
OCP/OCCT version ensures a cached shape is never reused across a
kernel/binding upgrade.

For v0.0.1 the cache is primarily a PATTERN-EXERCISE — the toy-scale evaluation
is sub-millisecond — proving the D8 keying discipline is cheap to implement
(FINDINGS §6).
"""
from __future__ import annotations

import importlib.metadata
from typing import Any

from . import geometry
from .kernel import recipe_hash

_OCP_VERSION: str = importlib.metadata.version("cadquery-ocp")
# Stores the full EvalResult (shape + by-construction blend hints, ADR/0038 D6)
# so display/HLR extraction reuses the evaluated solid AND its construction
# provenance from one pass (preserves the arc 20260609-1 N4 cache-reuse).
_SOLID_CACHE: dict[str, "geometry.EvalResult"] = {}


def ocp_version() -> str:
    """The frozen OCP/OCCT binding version (cache-key + FINDINGS material)."""
    return _OCP_VERSION


def cache_key(
    features: list[dict[str, Any]],
    *,
    last_event_id: str | None,
    adapter_schema_version: str,
) -> str:
    return f"{recipe_hash(features)}|{last_event_id}|{adapter_schema_version}|{_OCP_VERSION}"


def evaluate_with_cache(
    features: list[dict[str, Any]],
    *,
    last_event_id: str | None,
    adapter_schema_version: str,
) -> Any:
    """Validity-gate the recipe through OCCT, reusing a per-process cached solid
    only when the full D8 freshness key matches. Returns the evaluated SHAPE
    (the gate's caller wants a solid). Propagates `TransactionError` (Class-1)
    and `MechanicalKernelEvaluationError` (Class-2)."""
    return evaluate_with_cache_provenance(
        features, last_event_id=last_event_id, adapter_schema_version=adapter_schema_version
    ).shape


def evaluate_with_cache_provenance(
    features: list[dict[str, Any]],
    *,
    last_event_id: str | None,
    adapter_schema_version: str,
) -> "geometry.EvalResult":
    """As `evaluate_with_cache`, but returns the full `EvalResult` (shape +
    by-construction blend hints, ADR/0038 D6) — the topology layer's authority
    for fillet-produced roles. Same cache + freshness key."""
    key = cache_key(
        features, last_event_id=last_event_id, adapter_schema_version=adapter_schema_version
    )
    if key in _SOLID_CACHE:
        return _SOLID_CACHE[key]
    result = geometry.evaluate_part_with_provenance(features)
    _SOLID_CACHE[key] = result
    return result


def clear() -> None:
    """Test hook: drop all cached solids."""
    _SOLID_CACHE.clear()


def size() -> int:
    return len(_SOLID_CACHE)
