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
per ADR/0029 D4), the engine-opaque `adapter_payload`, and — since adapter
0.1.11 (ADR/0038 A4.7.2, arc 20260717-2) — the feature's normalized
`depends_on_feature_ids` as a SORTED stable-id list: A4.6 makes those edges
geometry-order authority, so two recipes with identical payloads but different
body chains are different models and MUST hash differently. It EXCLUDES
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
                # ADR/0038 A4.7.2: dependency edges are geometry-order
                # authority — they participate in identity, sorted (stable
                # ids), so a dependency-only model change changes vault_ref.
                "depends": sorted(f.get("depends_on_feature_ids", [])),
                "parameters": _canonical_parameters(f.get("parameters", [])),
                "payload": _canonical_payload(f.get("adapter_payload", {})),
            }
            for f in features
        ],
        sort_keys=True,
    )


def _canonical_payload(payload: Any) -> Any:
    """ADR/0044 A2.7 (Codex23 B1): ONE identity for ONE graph.

    The v2 sketch policy declares entity/constraint (and dimension/reference)
    array order NON-semantic — admission matches by structure. Identity must
    agree: for a v2 payload (`sketch_model == 2`) the four unordered
    id-addressed collections are sorted by their `id` before hashing, so
    every legal permutation of the same graph yields the same recipe bytes.
    The weak-completion and witness arrays keep their POLICY-defined
    canonical order (skb-b0 §5.1/§3.1) and are hashed verbatim. v1 payloads
    (no `sketch_model`) pass through byte-identically — no v1 hash moves.
    """
    if not (isinstance(payload, dict) and payload.get("sketch_model") == 2):
        return payload
    out = dict(payload)
    for name in ("entities", "constraints", "dimensions", "references"):
        coll = out.get(name)
        if isinstance(coll, list):
            out[name] = sorted(
                coll, key=lambda r: str(r.get("id", "")) if isinstance(r, dict) else ""
            )
    return out


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
