"""Canonical recipe serialization → content-addressed `vault_ref`.

**This module owns geometry IDENTITY, not geometry evaluation.** Per
[ADR/0031 D6] the authoritative `geometry_ref.vault_ref` is the sha256 of the
canonical, kernel-independent feature *recipe* — NOT the evaluated OCCT BREP.
The recipe is stable across OCCT versions/platforms, so it keeps kernel-byte
instability ([Wedge-003 FRICTION_LOG §10]) off the Truth-Model identity path.

The bytes staged into the Vault for an `authoring_geometry` record are the
canonical recipe JSON bytes produced here — a **parametric recipe artifact**,
not BREP / STEP / mesh / renderable kernel bytes (ADR/0031 D6 / Codex1 B1 of
arc 20260601-6). The evaluated solid (see `geometry.py`) is a per-process
materialization used to GATE VALIDITY and is never persisted in v0.0.1.

Canonicalization includes the Product-Truth geometry inputs only — feature
`id`, `feature_type`, first-class `parameters[]` (id/name/value/datatype/unit
per ADR/0029 D4), and the engine-opaque `adapter_payload`. It EXCLUDES
`fact_provenance`, `adapter_schema_version`, and any cache/version material
(Codex1 N4 of arc 20260602-1: irrelevant metadata must not affect `vault_ref`;
actual feature parameters must).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def compute_recipe_bytes(features: list[dict[str, Any]]) -> bytes:
    """Canonical recipe bytes for the current feature list.

    Deterministic across machines + runs (pure canonical-JSON sort + UTF-8
    encode). `sha256(compute_recipe_bytes(...))` is the authoritative
    `geometry_ref.vault_ref` per ADR/0031 D6.
    """
    return _canonicalize(features).encode("utf-8")


def recipe_hash(features: list[dict[str, Any]]) -> str:
    """Hex sha256 of the canonical recipe — the cache-key identity component
    (D8) and the value behind `vault_ref_for_bytes`."""
    return hashlib.sha256(compute_recipe_bytes(features)).hexdigest()


def vault_ref_for_bytes(data: bytes) -> str:
    """Canonical algorithm-qualified Vault content-hash per ADR/0005 D7 +
    ADR/0016 convention."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonicalize(features: list[dict[str, Any]]) -> str:
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
    """Only the Product-Truth fields (id+name+value+datatype+unit), sorted by
    id. `fact_provenance` is excluded per ADR/0028 D8 (provenance is distinct
    from the value)."""
    return sorted(
        (
            {
                "id": p["id"],
                "name": p["name"],
                "value": p["value"],
                "datatype": p["datatype"],
                "unit": p["unit"],
            }
            for p in parameters
        ),
        key=lambda p: p["id"],
    )
