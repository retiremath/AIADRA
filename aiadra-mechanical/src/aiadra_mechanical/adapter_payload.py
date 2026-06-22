"""Engine-opaque `adapter_payload` shapes for mechanical features.

Per ADR/0029 D7 sketch primitives + extrude op-data stay OPAQUE to
aiadra-core (the bundle schema only checks `adapter_payload` IS an object).
This module pins the payload format (`adapter_schema_version = 0.1.1` since arc
20260609-1 added engine-minted `skp_` primitive ids — see `build_sketch_payload`)
and performs **domain/payload validation** — Class-1 failures per ADR/0031
D6/B2: malformed or out-of-domain inputs raise `TransactionError` (a
passthrough exception) BEFORE the kernel is touched, so they are never
laundered as kernel instability.

Per ADR/0031 D6 + Wedge-003 Codex1 B1: extrude `depth_mm` is NOT in the
payload — it lives in `feature.parameters[]` as a first-class
canonical-unit-bearing Product-Truth record. The payload references the
parameter id so the kernel can correlate it during evaluation.
"""
from __future__ import annotations

from typing import Any

from aiadra_core.transaction.boundary import TransactionError

# Sketch primitive shapes carried in feature.adapter_payload["primitives"]:
#   {"type": "rectangle", "x_mm": float, "y_mm": float, "width_mm": float, "height_mm": float}
#   {"type": "circle", "cx_mm": float, "cy_mm": float, "radius_mm": float}
#   {"type": "line", "x1_mm": float, "y1_mm": float, "x2_mm": float, "y2_mm": float}

_SKETCH_PRIMITIVE_REQUIRED_KEYS = {
    "rectangle": {"type", "x_mm", "y_mm", "width_mm", "height_mm"},
    "circle": {"type", "cx_mm", "cy_mm", "radius_mm"},
    "line": {"type", "x1_mm", "y1_mm", "x2_mm", "y2_mm"},
}


def build_sketch_payload(primitives: list[dict[str, Any]]) -> dict[str, Any]:
    """Build (and domain-validate) the adapter_payload for a sketch feature.

    Per arc 20260609-1 Codex1 B2: each primitive is assigned a **stable,
    engine-minted `skp_NNNN` id** at authoring time. This is the
    primitive-level role anchor the Display Representation topology-identity
    scheme (ADR/0035) needs — face/edge display IDs derive from a primitive's
    `skp_` id, NOT from its position in the list (which is not stable once a
    sketch carries multiple same-type primitives). The id is engine-opaque to
    `aiadra-core` (the bundle schema only checks `adapter_payload` IS an
    object). It IS part of the canonical recipe → it participates in
    `vault_ref` identity (intentional: the primitive anchor is geometry
    identity, not incidental metadata). Bumps `adapter_schema_version` 0.1.0
    → 0.1.1.
    """
    _validate_sketch_primitives(primitives)
    out: list[dict[str, Any]] = []
    for i, p in enumerate(primitives, start=1):
        prim = dict(p)
        # Engine-minted stable id; a caller-supplied id is rejected so the
        # engine remains the sole minter (no spoofed anchors).
        if "id" in prim:
            raise TransactionError(
                f"mechanical.add_sketch_feature: primitive[{i - 1}] must not "
                f"carry a caller-supplied 'id'; the engine mints skp_ ids"
            )
        prim["id"] = f"skp_{i:04d}"
        out.append(prim)
    return {"primitives": out}


def build_extrude_payload(
    *, sketch_feature_id: str, direction: str, depth_parameter_id: str
) -> dict[str, Any]:
    """Build (and domain-validate) the adapter_payload for an extrude feature.

    `depth_mm` lives in `feature.parameters[]`; this payload references the
    parameter id so the kernel can correlate it.
    """
    if direction not in ("z+", "z-"):
        raise TransactionError(
            f"mechanical.add_extrude_feature: direction must be 'z+' or 'z-', got {direction!r}"
        )
    if not depth_parameter_id.startswith("featp_"):
        raise TransactionError(
            f"mechanical.add_extrude_feature: depth_parameter_id must match featp_NNNN, "
            f"got {depth_parameter_id!r}"
        )
    if not sketch_feature_id.startswith("feat_"):
        raise TransactionError(
            f"mechanical.add_extrude_feature: sketch_feature_id must match feat_NNNN, "
            f"got {sketch_feature_id!r}"
        )
    return {
        "sketch_feature_id": sketch_feature_id,
        "direction": direction,
        "depth_parameter_id": depth_parameter_id,
    }


_EDGE_KINDS = {"sharp", "tangent", "seam", "boundary", "free"}


def build_fillet_payload(
    *,
    adjacent_face_roles: list[str],
    edge_kind: str,
    resolved_against_topology_signature: str,
) -> dict[str, Any]:
    """Build (and domain-validate) the fillet `adapter_payload` — the engine-owned,
    recipe-anchored **`target_edge` reference** (ADR/0038 D2). The persisted
    reference is structured recipe roles + edge kind + the parent-prefix topology
    signature it resolved against — NEVER the read-side Display Representation
    `edge_id` string (ADR/0038 D1: display ids are input vocabulary, not Truth).
    `radius_mm` is NOT here — it lives in `feature.parameters[]` as a first-class
    canonical-unit record, like extrude `depth_mm`.
    """
    if not isinstance(adjacent_face_roles, list) or len(adjacent_face_roles) != 2:
        raise TransactionError(
            f"mechanical.add_fillet_feature: target_edge needs exactly two adjacent "
            f"face roles (v1 single sharp edge), got {adjacent_face_roles!r}"
        )
    if not all(isinstance(r, str) and r for r in adjacent_face_roles):
        raise TransactionError(
            "mechanical.add_fillet_feature: adjacent_face_roles must be non-empty strings"
        )
    if edge_kind not in _EDGE_KINDS:
        raise TransactionError(
            f"mechanical.add_fillet_feature: edge_kind must be one of "
            f"{sorted(_EDGE_KINDS)}, got {edge_kind!r}"
        )
    if (
        not isinstance(resolved_against_topology_signature, str)
        or not resolved_against_topology_signature.startswith("topo_")
    ):
        raise TransactionError(
            f"mechanical.add_fillet_feature: resolved_against_topology_signature must be a "
            f"'topo_' signature, got {resolved_against_topology_signature!r}"
        )
    return {
        "target_edge": {
            # Codex1 N2 (arc 20260621-2): sort at write time so the stored order
            # is deterministic + the reference compares stably across regenerate.
            "adjacent_face_roles": sorted(adjacent_face_roles),
            "edge_kind": edge_kind,
            "resolved_against_topology_signature": resolved_against_topology_signature,
        }
    }


def _validate_sketch_primitives(primitives: list[dict[str, Any]]) -> None:
    if not primitives:
        raise TransactionError(
            "mechanical.add_sketch_feature: primitives list cannot be empty"
        )
    has_rectangle = False
    for i, prim in enumerate(primitives):
        kind = prim.get("type")
        if kind not in _SKETCH_PRIMITIVE_REQUIRED_KEYS:
            raise TransactionError(
                f"mechanical.add_sketch_feature: primitive[{i}] unknown type {kind!r}; "
                f"expected one of {sorted(_SKETCH_PRIMITIVE_REQUIRED_KEYS)}"
            )
        missing = _SKETCH_PRIMITIVE_REQUIRED_KEYS[kind] - set(prim)
        if missing:
            raise TransactionError(
                f"mechanical.add_sketch_feature: primitive[{i}] type={kind!r} "
                f"missing keys: {sorted(missing)}"
            )
        if kind == "rectangle":
            has_rectangle = True
            if prim["width_mm"] <= 0 or prim["height_mm"] <= 0:
                raise TransactionError(
                    f"mechanical.add_sketch_feature: primitive[{i}] rectangle "
                    f"width_mm/height_mm must be positive, got "
                    f"width={prim['width_mm']!r} height={prim['height_mm']!r}"
                )
        elif kind == "circle":
            if prim["radius_mm"] <= 0:
                raise TransactionError(
                    f"mechanical.add_sketch_feature: primitive[{i}] circle "
                    f"radius_mm must be positive, got {prim['radius_mm']!r}"
                )
    # v0.0.1 builds a planar face from a rectangle outer profile; require one.
    if not has_rectangle:
        raise TransactionError(
            "mechanical.add_sketch_feature: v0.0.1 requires exactly one rectangle "
            "primitive as the outer profile (circles are interpreted as holes)"
        )
