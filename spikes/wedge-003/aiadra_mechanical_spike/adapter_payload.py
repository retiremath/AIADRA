"""Schema sketches for engine-opaque adapter_payload structures.

Per ADR/0029 D7: sketch primitives + extrude geometric-op data stay OPAQUE
to aiadra-core. This module documents the spike's payload shapes for
handler clarity. NOT consumed by aiadra-core schema validation; the bundle
schema only checks `adapter_payload` IS an object.

Per Codex1 B1 R1 absorption (arc 20260601-3): extrude depth_mm is NOT in
adapter_payload — it lives in feature.parameters[] as a first-class
Product Truth record per ADR/0029 D4 + D10 (canonical units at fact
level). The adapter_payload references the parameter id so the engine can
correlate during geometry computation. This makes
`mechanical_spike.adjust_feature_parameter` updates visible at the AIADRA
fold level (canonicalization includes parameters per kernel.py).

Per Codex1 N2 R1 absorption (arc 20260601-3): validation raises
`TransactionError` for bad operation inputs (NOT bare `ValueError`) so the
native dispatch adapter doesn't wrap them as kernel failures.
"""
from __future__ import annotations

from typing import Any

from aiadra_core.transaction.boundary import TransactionError


# Sketch primitive shapes carried in feature.adapter_payload["primitives"]:
#   {"type": "rectangle", "x_mm": float, "y_mm": float, "width_mm": float, "height_mm": float}
#   {"type": "circle", "cx_mm": float, "cy_mm": float, "radius_mm": float}
#   {"type": "line", "x1_mm": float, "y1_mm": float, "x2_mm": float, "y2_mm": float}


def build_sketch_payload(primitives: list[dict[str, Any]]) -> dict[str, Any]:
    """Build adapter_payload for a sketch feature.

    Spike validation: checks each primitive has the required keys for its
    type. Production engines would do real geometric validity (closed
    contours, self-intersection detection, etc.) — out of scope for spike
    per ADR/0030 D3.
    """
    _validate_sketch_primitives(primitives)
    return {"primitives": list(primitives)}


def build_extrude_payload(*, sketch_feature_id: str, direction: str, depth_parameter_id: str) -> dict[str, Any]:
    """Build adapter_payload for an extrude feature.

    Per Codex1 B1 R1 absorption (arc 20260601-3): depth_mm is NOT in this
    payload. It lives in feature.parameters[] as a first-class
    canonical-unit-bearing Product Truth record. The payload references
    the parameter id (`depth_parameter_id`) so the engine + kernel can
    correlate during geometry computation.

    Spike validation: valid direction enum + parameter id format.
    """
    if direction not in ("z+", "z-"):
        raise TransactionError(
            f"mechanical_spike.add_extrude_feature: direction must be 'z+' or 'z-', got {direction!r}"
        )
    if not depth_parameter_id.startswith("featp_"):
        raise TransactionError(
            f"mechanical_spike.add_extrude_feature: depth_parameter_id must match featp_NNNN, got {depth_parameter_id!r}"
        )
    if not sketch_feature_id.startswith("feat_"):
        raise TransactionError(
            f"mechanical_spike.add_extrude_feature: sketch_feature_id must match feat_NNNN, got {sketch_feature_id!r}"
        )
    return {
        "sketch_feature_id": sketch_feature_id,
        "direction": direction,
        "depth_parameter_id": depth_parameter_id,
    }


_SKETCH_PRIMITIVE_REQUIRED_KEYS = {
    "rectangle": {"type", "x_mm", "y_mm", "width_mm", "height_mm"},
    "circle": {"type", "cx_mm", "cy_mm", "radius_mm"},
    "line": {"type", "x1_mm", "y1_mm", "x2_mm", "y2_mm"},
}


def _validate_sketch_primitives(primitives: list[dict[str, Any]]) -> None:
    if not primitives:
        raise TransactionError(
            "mechanical_spike.add_sketch_feature: primitives list cannot be empty"
        )
    for i, prim in enumerate(primitives):
        kind = prim.get("type")
        if kind not in _SKETCH_PRIMITIVE_REQUIRED_KEYS:
            raise TransactionError(
                f"mechanical_spike.add_sketch_feature: primitive[{i}] unknown type {kind!r}; "
                f"expected one of {sorted(_SKETCH_PRIMITIVE_REQUIRED_KEYS)}"
            )
        required = _SKETCH_PRIMITIVE_REQUIRED_KEYS[kind]
        missing = required - set(prim)
        if missing:
            raise TransactionError(
                f"mechanical_spike.add_sketch_feature: primitive[{i}] type={kind!r} missing keys: {sorted(missing)}"
            )
