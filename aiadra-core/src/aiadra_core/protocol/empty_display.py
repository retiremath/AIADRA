"""The kernel-neutral EMPTY-Part display branch (arc 20260714-2 EP0; ADR/0035
Amendment A4).

A just-committed Part with NO features and NO authoring geometry has no
producing Native Engine — engine resolution cannot (and must not) run. Core
owns the display of mathematical emptiness: this module builds the empty
Display Representation / HLR payloads locally, with ONE precisely defined
empty-state identity. It imports no kernel and no engine ("AIADRA Core hosts
nothing" — Core describes emptiness, it does not acquire kernel behavior).

The empty-state identity (A4):
- ``geometry_ref``:  the reserved value ``"empty:v1"`` — NOT a vault ref; a
  Part carries it iff it has no authoring geometry. Committing the first
  feature replaces it with the recipe-hash vault ref (the ADR/0035 promise for
  non-empty state is unchanged).
- ``topology_signature``: the deterministic hash of the EMPTY topology
  skeleton — ``"topo_" + sha256(b"[]")[:16]``. This is byte-equivalent to the
  engine-side ``compute_topology_signature([])`` (whose canonical bytes for an
  empty skeleton are exactly ``json.dumps([], sort_keys=True) == "[]"``)
  WITHOUT importing the engine (Codex2 build bar 1). Committing the first
  sketch changes it exactly like any skeleton change.
- ``cache_key``: ``"empty:v1|<object_uuid>|<display contract version>"``.
- Invalidation is machine-readable (Codex2 build bar 2): the standard identity
  predicates, so Studio's existing gates work unchanged.
"""
from __future__ import annotations

import hashlib
from typing import Any

from aiadra_core.transaction.boundary import TransactionError

from .display import DISPLAY_REPRESENTATION_VERSION

#: The reserved empty-state geometry_ref (ADR/0035 A4). Never a vault ref.
EMPTY_GEOMETRY_REF = "empty:v1"

#: The canonical bytes of the empty topology skeleton: json.dumps([], sort_keys=True).
_EMPTY_SKELETON_BYTES = b"[]"


def empty_topology_signature() -> str:
    """The deterministic empty-skeleton signature (byte-equivalent to the
    engine's signature function applied to zero features; computed Core-locally
    — no engine import)."""
    return "topo_" + hashlib.sha256(_EMPTY_SKELETON_BYTES).hexdigest()[:16]


def empty_cache_key(object_uuid: str) -> str:
    return f"{EMPTY_GEOMETRY_REF}|{object_uuid}|{DISPLAY_REPRESENTATION_VERSION}"


def _is_part(sidecar: dict[str, Any]) -> bool:
    return (sidecar.get("object") or {}).get("type") == "Part"


def is_empty_part(sidecar: dict[str, Any]) -> bool:
    """The EXACT empty state (Codex2 build bar 3 + Codex3 B1): the Object IS a
    **Part** (A4's iff-domain — a featureless Requirement is NOT CAD emptiness
    and must keep the normal fail-loud no-display path), with NO features AND
    NO active authoring geometry. Mixed states are NOT empty — callers must let
    them fail loud through the normal engine-resolution path or
    `require_consistent`."""
    if not _is_part(sidecar):
        return False  # A4 is Part-only — never broaden the reserved identity
    features = sidecar.get("feature", []) or []
    authoring = [
        g for g in (sidecar.get("geometry_ref", []) or [])
        if g.get("role") == "authoring_geometry"
    ]
    return not features and not authoring


def require_consistent_for_display(sidecar: dict[str, Any], object_ref: str) -> None:
    """Fail loud on the features-without-geometry mixed state (Codex2 build bar
    3) — an inconsistent PART sidecar must never masquerade as empty NOR yield
    the generic no-geometry error. Part-only (Codex3 B1): non-Part Objects keep
    their normal no-display path. (The inverse mix — authoring geometry without
    features — already fails loud inside engine resolution.)"""
    if not _is_part(sidecar):
        return
    features = sidecar.get("feature", []) or []
    authoring = [
        g for g in (sidecar.get("geometry_ref", []) or [])
        if g.get("role") == "authoring_geometry"
    ]
    if features and not authoring:
        raise TransactionError(
            f"{object_ref}: INCONSISTENT sidecar — {len(features)} feature(s) "
            f"present but no authoring_geometry; refusing to display this Part "
            f"as empty (a feature commit must produce authoring geometry)"
        )


def build_empty_display(object_uuid: str, object_number: str) -> dict[str, Any]:
    """The empty Display Representation (current contract; v1.2 since SK-C1.0 S2) — validated by the
    caller through the standard `DisplayRepresentation.from_engine_dict`."""
    return {
        "display_representation_version": DISPLAY_REPRESENTATION_VERSION,
        "identity": {
            "object_uuid": object_uuid,
            "object_number": object_number,
            "geometry_ref": EMPTY_GEOMETRY_REF,
            "cache_key": empty_cache_key(object_uuid),
            "topology_signature": empty_topology_signature(),
        },
        "render": {
            "faces": [],
            "edges": [],
            "vertices": [],
            "bbox_min": [0.0, 0.0, 0.0],
            "bbox_max": [0.0, 0.0, 0.0],
            "linear_deflection_mm": 0.0,
            "angular_deflection_rad": 0.0,
            "buffer_encoding": "json_arrays",
        },
        # Nothing is pickable in the empty state (Codex2 build bar 2).
        "selection": {"id_space": "canonical", "pickable_kinds": [], "names": {}},
        "sketch_frames": [],
        "view_dependent": None,
        # Machine-readable, the SAME predicates the engine emits — Studio's
        # existing invalidation/attach gates work unchanged.
        "invalidation": {
            "stale_when": ["geometry_ref_changed", "cache_key_changed"],
            "selection_invalid_when": "topology_signature_changed",
        },
        "counters": {
            "face_count": 0,
            "edge_count_by_kind": {},
            "triangle_count": 0,
            "vertex_count": 0,
            "generation_ms": None,
            "package_bytes": None,
        },
    }


def build_empty_hlr(
    object_uuid: str,
    object_number: str,
    views: list[dict[str, Any]],
    algorithm: str,
) -> dict[str, Any]:
    """The empty HLR payload: the REQUESTED views, each with zero segments and
    zero counters, under the standard identity echo — Studio's attach gate
    works unchanged (Codex1 B1). View specs are validated structurally and the
    projector frame is orthonormalized Core-locally (pure math, no kernel)."""
    if not isinstance(views, list) or not views:
        raise TransactionError("display_hlr requires a non-empty list of views")
    if algorithm not in ("exact", "poly"):
        raise TransactionError(
            f"display_hlr algorithm must be 'exact' or 'poly', got {algorithm!r}"
        )
    out_views: list[dict[str, Any]] = []
    for v in views:
        out_views.append(_empty_view(v, algorithm))
    return {
        "identity_echo": {
            "object_uuid": object_uuid,
            "object_number": object_number,
            "geometry_ref": EMPTY_GEOMETRY_REF,
            "display_representation_version": DISPLAY_REPRESENTATION_VERSION,
            "cache_key": empty_cache_key(object_uuid),
            "topology_signature": empty_topology_signature(),
        },
        "views": out_views,
    }


def _empty_view(view: dict[str, Any], algorithm: str) -> dict[str, Any]:
    view_id = view.get("view_id")
    if not isinstance(view_id, str) or not view_id:
        raise TransactionError("each HLR view requires a non-empty 'view_id'")
    direction = _unit3(view.get("direction"), f"view '{view_id}' direction")
    up_raw = _vec3(view.get("up"), f"view '{view_id}' up")
    # Orthonormalize: u = normalize(up − (up·d)d); right = d × u (the engine's
    # projector convention — (right, up, −direction) right-handed).
    d = direction
    dot = up_raw[0] * d[0] + up_raw[1] * d[1] + up_raw[2] * d[2]
    u0 = (up_raw[0] - dot * d[0], up_raw[1] - dot * d[1], up_raw[2] - dot * d[2])
    n = (u0[0] ** 2 + u0[1] ** 2 + u0[2] ** 2) ** 0.5
    if n < 1e-9:
        raise TransactionError(
            f"view '{view_id}': 'up' must not be parallel to 'direction'"
        )
    u = (u0[0] / n, u0[1] / n, u0[2] / n)
    r = (
        d[1] * u[2] - d[2] * u[1],
        d[2] * u[0] - d[0] * u[2],
        d[0] * u[1] - d[1] * u[0],
    )
    origin = view.get("origin", [0.0, 0.0, 0.0])
    return {
        "view_id": view_id,
        "projector": {
            "projection": "orthographic",
            "origin": [float(x) for x in origin],
            "direction": list(d),
            "up": list(u),
            "right": list(r),
            "units": "mm",
        },
        "algorithm": algorithm,
        "coordinate_space": "view_plane_2d",
        "correlation_min_length_mm": 0.0,
        "segments": [],
        "counters": {
            "visible_segments": 0,
            "hidden_segments": 0,
            "outline_segments": 0,
            "discarded_tolerance_segments": 0,
            "generation_ms": None,
        },
    }


def _vec3(v: Any, label: str) -> tuple[float, float, float]:
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        raise TransactionError(f"{label} must be a 3-vector")
    try:
        return (float(v[0]), float(v[1]), float(v[2]))
    except (TypeError, ValueError) as e:
        raise TransactionError(f"{label} must be numeric: {e!r}") from e


def _unit3(v: Any, label: str) -> tuple[float, float, float]:
    x, y, z = _vec3(v, label)
    n = (x * x + y * y + z * z) ** 0.5
    if n < 1e-9:
        raise TransactionError(f"{label} must be non-zero")
    return (x / n, y / n, z / n)
