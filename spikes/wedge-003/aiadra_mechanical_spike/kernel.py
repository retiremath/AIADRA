"""Toy deterministic synthetic geometry kernel for Wedge-003.

NOT a real geometric kernel. Serializes features as canonical JSON; sha256
becomes vault_ref. Reproducible across machines (no floating-point /
kernel-state nondeterminism). Real OCCT integration deferred to first
`aiadra-mechanical` arc per ADR/0028 D15 item 1 + ADR/0030 D3.

The "geometry" produced by this kernel is THE RECIPE FOR THE GEOMETRY, not
the geometry itself. Sufficient to validate AIADRA's loop (schema + events
+ provenance + dispatch + binding scan + cascade integrity + release).

Per Codex1 N3 R1 absorption from arc 20260601-3: the module-level cache is
a PURE-FUNCTION SPIKE CACHE keyed by canonicalized Product Truth inputs.
It is NOT authoritative engine state and does NOT prove cache freshness
for real engines — real engine caches need workspace / bundle / event-log
boundary evidence before reuse (per ADR/0027 D6 cache freshness invariant).

Per Codex1 B1 R1 absorption from arc 20260601-3: canonicalization includes
`parameters` (first-class feature parameter records per ADR/0029 D4) in
addition to feature `id`, `feature_type`, and `adapter_payload`. This is
what makes `mechanical_spike.adjust_feature_parameter` actually change the
geometry hash — the depth_mm parameter is Product Truth, not opaque payload.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


_GEOMETRY_CACHE: dict[str, bytes] = {}


def compute_geometry(features: list[dict[str, Any]]) -> bytes:
    """Deterministic synthetic geometry generator.

    Per ADR/0030 D3 + Codex1 B1 R1 from arc 20260601-3: takes a list of
    feature records and produces a reproducible byte blob representing
    'this combination of features evaluated together'. sha256 of bytes
    becomes the vault_ref per ADR/0005 D7.

    Canonicalization includes feature `id`, `feature_type`, `parameters[]`
    (id + name + value + datatype + unit per ADR/0029 D4), and
    `adapter_payload`. Changing any parameter value changes the canonical
    JSON; sha256 changes; vault_ref changes; geometry is genuinely
    recomputed.

    Cache: pure-function spike cache keyed by canonical inputs. Per Codex1
    N3 R1: NOT a general cache-freshness solution; real engines need
    workspace / bundle / event-log boundary evidence per ADR/0027 D6.
    """
    cache_key = _cache_key_for(features)
    if cache_key in _GEOMETRY_CACHE:
        return _GEOMETRY_CACHE[cache_key]
    canonical = _canonicalize(features)
    bytes_out = canonical.encode("utf-8")
    _GEOMETRY_CACHE[cache_key] = bytes_out
    return bytes_out


def vault_ref_for_bytes(data: bytes) -> str:
    """Canonical sha256-prefixed vault_ref per ADR/0005 D7."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _cache_key_for(features: list[dict[str, Any]]) -> str:
    return hashlib.sha256(_canonicalize(features).encode("utf-8")).hexdigest()


def _canonicalize(features: list[dict[str, Any]]) -> str:
    """Canonical JSON serialization including first-class parameters per
    ADR/0029 D4 + Codex1 B1 R1. Excludes provenance + adapter_schema_version
    (not part of geometry inputs)."""
    return json.dumps(
        [
            {
                "id": f["id"],
                "type": f["feature_type"],
                "parameters": _canonical_parameters(f.get("parameters", [])),
                "payload": f.get("adapter_payload", {}),
            }
            for f in features
        ],
        sort_keys=True,
    )


def _canonical_parameters(parameters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort parameters by id for deterministic canonicalization. Only the
    Product-Truth fields (id + name + value + datatype + unit) are included
    — fact_provenance metadata is excluded per ADR/0028 D8 (provenance is
    distinct from the value itself)."""
    return sorted(
        [
            {
                "id": p["id"],
                "name": p["name"],
                "value": p["value"],
                "datatype": p["datatype"],
                "unit": p["unit"],
            }
            for p in parameters
        ],
        key=lambda p: p["id"],
    )


def simulate_kernel_failure(*, message: str = "synthetic kernel crash") -> None:
    """Test-only hook: raise a synthetic kernel-class exception to exercise
    the `NativeEngineKernelError` wrapping per arc 1 Q3 + ADR/0030 D9 +
    D12 test #17. Handlers SHOULD NOT call this; tests inject failure via
    monkeypatching the kernel module."""
    raise RuntimeError(message)


def clear_cache() -> None:
    """Test-only hook to clear the cache between tests for determinism."""
    _GEOMETRY_CACHE.clear()
