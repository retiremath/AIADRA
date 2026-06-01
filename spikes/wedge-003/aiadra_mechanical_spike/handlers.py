"""4 Native Engine handlers per ADR/0030 D5 (Codex1 N3 R1 absorption from
arc 20260601-2: `mechanical_spike.recompute_geometry` dropped from catalog).

Each handler follows the canonical shape:
    1. Parse `params` dict (handler-specific keys)
    2. Resolve Part UUID via `context.find_reservation_entry_by_number`
    3. Read current Part sidecar via `context.load_sidecar` (draft-aware)
    4. Allocate feat_NNNN / featp_NNNN / geom_NNNN id (next-available)
    5. Build feature_record / geometry_ref_record per ADR/0029 schemas
    6. Compute geometry via toy kernel (for handlers that touch geometry)
    7. Stage Vault bytes via `context.stage_vault_bytes` → vault_ref
    8. Stage updated Part sidecar via `context.stage_sidecar`
    9. Emit `part_changed` event via `context.emit_event` envelope

Per Codex1 B1 R1 absorption (arc 20260601-3): extrude depth is a
first-class `feature.parameters[]` record per ADR/0029 D4 with canonical
unit `mm`. `adjust_feature_parameter` updates that parameter record;
canonicalization includes parameters; geometry hash changes when
parameter value changes.

Per Codex1 N2 R1 absorption (arc 20260601-3): bad operation inputs raise
`TransactionError` (NOT bare `ValueError`) so the native dispatch adapter
keeps domain errors distinct from kernel failures.

Per Codex1 N4 R1 absorption (arc 20260601-3): records built once then
deep-copied into sidecar + event payload to avoid shared-mutable-object
aliasing.
"""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from aiadra_core.transaction.boundary import TransactionError

from .adapter_payload import build_extrude_payload, build_sketch_payload
from .kernel import compute_geometry, vault_ref_for_bytes

if TYPE_CHECKING:
    from aiadra_core.native_engine.context import NativeEngineContext


ADAPTER_SCHEMA_VERSION = "0.1.0"
ENGINE_ID = "mechanical_spike"


# =============================================================================
# Handler 1: add_sketch_feature
# =============================================================================


def handle_add_sketch_feature(context: "NativeEngineContext", params: dict[str, Any]) -> None:
    """ADR/0030 D4 step 2: add sketch feature with primitives.

    params:
        part_number: str — Part Number (e.g., "P-000001")
        primitives: list[dict] — sketch primitives per build_sketch_payload
    """
    part_number = _require_param(params, "part_number", str, "mechanical_spike.add_sketch_feature")
    primitives = _require_param(params, "primitives", list, "mechanical_spike.add_sketch_feature")

    part_uuid, sidecar = _resolve_part_sidecar(context, part_number)

    feature_id = _next_id(sidecar.get("feature", []), prefix="feat_")
    geom_id = _next_id(sidecar.get("geometry_ref", []), prefix="geom_")

    feature_record = {
        "id": feature_id,
        "name": f"sketch_{feature_id}",
        "feature_type": "sketch",
        "engine": ENGINE_ID,
        "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
        "adapter_payload": build_sketch_payload(primitives),
        "fact_provenance": {
            "category": _provenance_category_for_actor(context.actor),
        },
    }
    # Per Codex1 N4 R1: deep-copy into sidecar so later mutations don't alias.
    sidecar = copy.deepcopy(sidecar)
    sidecar.setdefault("feature", []).append(copy.deepcopy(feature_record))

    # Compute geometry via toy kernel.
    geom_bytes = compute_geometry(sidecar["feature"])
    vault_ref, _vault_path = context.stage_vault_bytes(geom_bytes)

    geom_record = {
        "id": geom_id,
        "role": "authoring_geometry",
        "vault_ref": vault_ref,
        "kind": "wireframe",  # sketches are 2D wireframes
        "derived_from_feature_ids": [feature_id],
        "fact_provenance": {
            "category": "computed_result",
            "derived_from": [f"feature:{feature_id}"],
        },
    }
    sidecar.setdefault("geometry_ref", []).append(copy.deepcopy(geom_record))

    context.stage_sidecar(part_uuid, sidecar)
    context.emit_event("part_changed", {
        "object_uuid": part_uuid,
        "rationale": f"add sketch feature {feature_id} with {len(primitives)} primitive(s)",
        "feature_delta": {"added": [copy.deepcopy(feature_record)]},
        "geometry_ref_delta": {"added": [copy.deepcopy(geom_record)]},
    })


# =============================================================================
# Handler 2: add_extrude_feature (B1: depth_mm as first-class parameter)
# =============================================================================


def handle_add_extrude_feature(context: "NativeEngineContext", params: dict[str, Any]) -> None:
    """ADR/0030 D4 step 3: add extrude feature consuming a sketch.

    Per Codex1 B1 R1 absorption (arc 20260601-3): depth_mm is a first-class
    `feature.parameters[]` record per ADR/0029 D4 + D10 (canonical unit `mm`).
    The adapter_payload references the parameter id; kernel canonicalization
    includes parameters so changing depth changes the geometry hash.

    Per Q9 from arc 20260601-2 ack: subtree-output — the existing
    `authoring_geometry` geom_ref derived from the sketch is REPLACED by
    the new authoring_geometry derived from BOTH features (extrude
    subsumes the sketch's geometric output).

    params:
        part_number: str — Part Number
        sketch_feature_id: str — feat_NNNN id of the sketch this extrude consumes
        depth_mm: float — extrude depth (becomes a feature.parameters[] record)
        direction: str — "z+" or "z-"
    """
    part_number = _require_param(params, "part_number", str, "mechanical_spike.add_extrude_feature")
    sketch_feature_id = _require_param(params, "sketch_feature_id", str, "mechanical_spike.add_extrude_feature")
    depth_mm = _require_param(params, "depth_mm", (int, float), "mechanical_spike.add_extrude_feature")
    direction = _require_param(params, "direction", str, "mechanical_spike.add_extrude_feature")

    if depth_mm <= 0:
        raise TransactionError(
            f"mechanical_spike.add_extrude_feature: depth_mm must be positive, got {depth_mm!r}"
        )

    part_uuid, sidecar = _resolve_part_sidecar(context, part_number)

    # Verify sketch feature exists on this Part.
    sketch_feature = None
    for f in sidecar.get("feature", []):
        if f.get("id") == sketch_feature_id and f.get("feature_type") == "sketch":
            sketch_feature = f
            break
    if sketch_feature is None:
        raise TransactionError(
            f"mechanical_spike.add_extrude_feature: sketch feature {sketch_feature_id!r} not found on Part {part_number}"
        )

    feature_id = _next_id(sidecar.get("feature", []), prefix="feat_")
    # Per Codex1 B1 R1: depth as first-class parameter
    depth_param_id = _next_id_within_parameters(sidecar.get("feature", []), prefix="featp_")
    depth_param_record = {
        "id": depth_param_id,
        "name": "depth_mm",
        "value": float(depth_mm),
        "datatype": "number",
        "unit": "mm",
    }

    feature_record = {
        "id": feature_id,
        "name": f"extrude_{feature_id}",
        "feature_type": "extrude",
        "engine": ENGINE_ID,
        "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
        "depends_on_feature_ids": [sketch_feature_id],
        "parameters": [depth_param_record],  # B1: first-class
        "adapter_payload": build_extrude_payload(
            sketch_feature_id=sketch_feature_id,
            direction=direction,
            depth_parameter_id=depth_param_id,
        ),
        "fact_provenance": {
            "category": _provenance_category_for_actor(context.actor),
        },
    }
    sidecar = copy.deepcopy(sidecar)
    sidecar.setdefault("feature", []).append(copy.deepcopy(feature_record))

    # Per Q9: REPLACE the sketch's authoring_geometry geom_ref with one
    # derived from BOTH features. Find the existing geom_ref pointing to
    # the sketch.
    existing_geom = None
    for g in sidecar.get("geometry_ref", []):
        if g.get("role") == "authoring_geometry" and sketch_feature_id in g.get("derived_from_feature_ids", []):
            existing_geom = g
            break

    # Compute new geometry from BOTH features (sketch + extrude).
    geom_bytes = compute_geometry(sidecar["feature"])
    vault_ref, _vault_path = context.stage_vault_bytes(geom_bytes)

    if existing_geom is not None:
        # REPLACE existing geom_ref with extrude-subtree output.
        geom_id = existing_geom["id"]
        new_geom_record = {
            "id": geom_id,
            "role": "authoring_geometry",
            "vault_ref": vault_ref,
            "kind": "solid",  # extrude produces a 3D solid
            "derived_from_feature_ids": [sketch_feature_id, feature_id],
            "fact_provenance": {
                "category": "computed_result",
                "derived_from": [f"feature:{sketch_feature_id}", f"feature:{feature_id}"],
            },
        }
        # Update sidecar's geom_ref in place.
        for i, g in enumerate(sidecar["geometry_ref"]):
            if g.get("id") == geom_id:
                sidecar["geometry_ref"][i] = copy.deepcopy(new_geom_record)
                break
        geometry_delta = {"updated": [{"id": geom_id, "new_record": copy.deepcopy(new_geom_record)}]}
    else:
        # No prior geom_ref — add fresh one (this is the Mode B fast-path
        # where extrude is added before sketch's geom_ref was committed).
        geom_id = _next_id(sidecar.get("geometry_ref", []), prefix="geom_")
        new_geom_record = {
            "id": geom_id,
            "role": "authoring_geometry",
            "vault_ref": vault_ref,
            "kind": "solid",
            "derived_from_feature_ids": [sketch_feature_id, feature_id],
            "fact_provenance": {
                "category": "computed_result",
                "derived_from": [f"feature:{sketch_feature_id}", f"feature:{feature_id}"],
            },
        }
        sidecar.setdefault("geometry_ref", []).append(copy.deepcopy(new_geom_record))
        geometry_delta = {"added": [copy.deepcopy(new_geom_record)]}

    context.stage_sidecar(part_uuid, sidecar)
    context.emit_event("part_changed", {
        "object_uuid": part_uuid,
        "rationale": f"add extrude feature {feature_id} consuming sketch {sketch_feature_id} (depth={depth_mm}mm)",
        "feature_delta": {"added": [copy.deepcopy(feature_record)]},
        "geometry_ref_delta": geometry_delta,
    })


# =============================================================================
# Handler 3: adjust_feature_parameter (B1: updates parameters[] record)
# =============================================================================


def handle_adjust_feature_parameter(context: "NativeEngineContext", params: dict[str, Any]) -> None:
    """ADR/0030 D4 step 4: adjust a parameter on an existing feature.

    Per Codex1 B1 R1 absorption (arc 20260601-3): updates a first-class
    `feature.parameters[]` record per ADR/0029 D4. Kernel canonicalization
    includes parameters; sha256 changes; vault_ref changes; geometry is
    GENUINELY recomputed (not just metadata-changed).

    Emits single `part_changed` event with BOTH `feature_delta.updated`
    AND `geometry_ref_delta.updated` in one Transaction per ADR/0030 D4
    step 4.

    params:
        part_number: str
        feature_id: str — feat_NNNN id
        parameter_name: str — e.g., "depth_mm"
        new_value: float
    """
    part_number = _require_param(params, "part_number", str, "mechanical_spike.adjust_feature_parameter")
    feature_id = _require_param(params, "feature_id", str, "mechanical_spike.adjust_feature_parameter")
    parameter_name = _require_param(params, "parameter_name", str, "mechanical_spike.adjust_feature_parameter")
    new_value = _require_param(params, "new_value", (int, float), "mechanical_spike.adjust_feature_parameter")

    # Codex2 N1 R3 absorption (arc 20260601-3): depth-domain validation on
    # adjust mirrors the same check on add_extrude. Spike-grade: assumes
    # any parameter named "depth_mm" (or any *_mm depth parameter) must be
    # positive. Production engines would have richer parameter-specific
    # validation (e.g., fillet radius must be < adjacent edge length, etc.).
    if parameter_name.endswith("depth_mm") and new_value <= 0:
        raise TransactionError(
            f"mechanical_spike.adjust_feature_parameter: {parameter_name} must be positive, "
            f"got {new_value!r}"
        )

    part_uuid, sidecar = _resolve_part_sidecar(context, part_number)

    # Find the target feature.
    target_feature = None
    target_idx = None
    for i, f in enumerate(sidecar.get("feature", [])):
        if f.get("id") == feature_id:
            target_feature = f
            target_idx = i
            break
    if target_feature is None:
        raise TransactionError(
            f"mechanical_spike.adjust_feature_parameter: feature {feature_id!r} not found on Part {part_number}"
        )

    # Find the target parameter within the feature's parameters[].
    target_param_idx = None
    for i, p in enumerate(target_feature.get("parameters", [])):
        if p.get("name") == parameter_name:
            target_param_idx = i
            break
    if target_param_idx is None:
        raise TransactionError(
            f"mechanical_spike.adjust_feature_parameter: parameter {parameter_name!r} not found "
            f"on feature {feature_id!r} (available: {[p.get('name') for p in target_feature.get('parameters', [])]})"
        )

    # Build updated feature record (B1: parameter value updated; provenance refreshed for actor).
    sidecar = copy.deepcopy(sidecar)
    updated_feature = copy.deepcopy(target_feature)
    updated_feature["parameters"][target_param_idx]["value"] = float(new_value)
    updated_feature["fact_provenance"] = {
        "category": _provenance_category_for_actor(context.actor),
    }
    sidecar["feature"][target_idx] = copy.deepcopy(updated_feature)

    # Recompute geometry — canonical includes parameters per kernel.py.
    geom_bytes = compute_geometry(sidecar["feature"])
    vault_ref, _vault_path = context.stage_vault_bytes(geom_bytes)

    # Find the geometry_ref that depends on this feature.
    target_geom = None
    target_geom_idx = None
    for i, g in enumerate(sidecar.get("geometry_ref", [])):
        if g.get("role") == "authoring_geometry" and feature_id in g.get("derived_from_feature_ids", []):
            target_geom = g
            target_geom_idx = i
            break
    if target_geom is None:
        raise TransactionError(
            f"mechanical_spike.adjust_feature_parameter: no authoring_geometry geom_ref found "
            f"depending on feature {feature_id!r} on Part {part_number}"
        )

    updated_geom = copy.deepcopy(target_geom)
    updated_geom["vault_ref"] = vault_ref
    sidecar["geometry_ref"][target_geom_idx] = copy.deepcopy(updated_geom)

    context.stage_sidecar(part_uuid, sidecar)
    context.emit_event("part_changed", {
        "object_uuid": part_uuid,
        "rationale": f"adjust {feature_id}.{parameter_name} = {new_value}",
        "feature_delta": {"updated": [{"id": feature_id, "new_record": copy.deepcopy(updated_feature)}]},
        "geometry_ref_delta": {"updated": [{"id": target_geom["id"], "new_record": copy.deepcopy(updated_geom)}]},
    })


# =============================================================================
# Handler 4: remove_feature (enables cascade-rejection negative test)
# =============================================================================


def handle_remove_feature(context: "NativeEngineContext", params: dict[str, Any]) -> None:
    """ADR/0030 D4 step 5 / D8: remove one or more features (batched-cascade
    capable). Engine emits `part_changed` with `feature_delta.removed` +
    (if requested) `geometry_ref_delta.removed` for dependent geometry.

    Per ADR/0030 D8 + ADR/0029 D12: fold cascade-rejects if surviving
    records still reference removed ids; caller must batch dependent
    removals into the same event for cascade-accept.

    params:
        part_number: str
        feature_ids: list[str] — feat_NNNN ids to remove
        geometry_ref_ids: list[str] | None (optional) — geom_NNNN ids to remove
            in same Transaction (for batched-cascade-accept)
    """
    part_number = _require_param(params, "part_number", str, "mechanical_spike.remove_feature")
    feature_ids = _require_param(params, "feature_ids", list, "mechanical_spike.remove_feature")
    geometry_ref_ids = params.get("geometry_ref_ids") or []
    if not isinstance(geometry_ref_ids, list):
        raise TransactionError(
            f"mechanical_spike.remove_feature: geometry_ref_ids must be a list, got {type(geometry_ref_ids).__name__}"
        )

    part_uuid, sidecar = _resolve_part_sidecar(context, part_number)

    # Verify all feature_ids exist on the Part.
    existing_feature_ids = {f["id"] for f in sidecar.get("feature", [])}
    missing = set(feature_ids) - existing_feature_ids
    if missing:
        raise TransactionError(
            f"mechanical_spike.remove_feature: feature(s) {sorted(missing)} not present on Part {part_number}"
        )
    existing_geom_ids = {g["id"] for g in sidecar.get("geometry_ref", [])}
    missing_geoms = set(geometry_ref_ids) - existing_geom_ids
    if missing_geoms:
        raise TransactionError(
            f"mechanical_spike.remove_feature: geometry_ref(s) {sorted(missing_geoms)} not present on Part {part_number}"
        )

    # Apply removals to sidecar.
    sidecar = copy.deepcopy(sidecar)
    sidecar["feature"] = [f for f in sidecar.get("feature", []) if f["id"] not in set(feature_ids)]
    if geometry_ref_ids:
        sidecar["geometry_ref"] = [g for g in sidecar.get("geometry_ref", []) if g["id"] not in set(geometry_ref_ids)]

    context.stage_sidecar(part_uuid, sidecar)
    payload: dict[str, Any] = {
        "object_uuid": part_uuid,
        "rationale": f"remove feature(s) {feature_ids}" + (f" + geometry_ref(s) {geometry_ref_ids}" if geometry_ref_ids else ""),
        "feature_delta": {"removed": list(feature_ids)},
    }
    if geometry_ref_ids:
        payload["geometry_ref_delta"] = {"removed": list(geometry_ref_ids)}
    context.emit_event("part_changed", payload)


# =============================================================================
# Shared helpers
# =============================================================================


def _require_param(
    params: dict[str, Any],
    name: str,
    type_: type | tuple[type, ...],
    op_kind: str,
) -> Any:
    """Per Codex1 N2 R1 absorption (arc 20260601-3): raise TransactionError
    for missing or wrong-type params so the dispatch adapter keeps domain
    errors distinct from kernel failures."""
    if name not in params:
        raise TransactionError(f"{op_kind}: missing required param {name!r}")
    value = params[name]
    if not isinstance(value, type_):
        expected = type_.__name__ if isinstance(type_, type) else " | ".join(t.__name__ for t in type_)
        raise TransactionError(
            f"{op_kind}: param {name!r} must be {expected}, got {type(value).__name__}"
        )
    return value


def _resolve_part_sidecar(context: "NativeEngineContext", part_number: str) -> tuple[str, dict[str, Any]]:
    """Lookup Part UUID via Reservation; return (uuid, draft-aware sidecar)."""
    entry = context.find_reservation_entry_by_number(part_number)
    if entry is None:
        raise TransactionError(
            f"Part {part_number!r} not found in workspace reservations"
        )
    _prefix, res_entry = entry
    part_uuid = res_entry["object_uuid"]
    sidecar = context.load_sidecar(part_uuid)
    return part_uuid, sidecar


def _next_id(records: list[dict], *, prefix: str) -> str:
    """Allocate next feat_NNNN / geom_NNNN id; 4-digit zero-padded."""
    existing_nums = {
        int(r["id"][len(prefix):])
        for r in records
        if isinstance(r, dict) and r.get("id", "").startswith(prefix)
    }
    n = max(existing_nums, default=0) + 1
    return f"{prefix}{n:04d}"


def _next_id_within_parameters(features: list[dict], *, prefix: str) -> str:
    """Allocate next featp_NNNN id across ALL features' parameters[]."""
    existing_nums: set[int] = set()
    for f in features:
        for p in f.get("parameters", []) or []:
            pid = p.get("id", "")
            if pid.startswith(prefix):
                try:
                    existing_nums.add(int(pid[len(prefix):]))
                except ValueError:
                    pass
    n = max(existing_nums, default=0) + 1
    return f"{prefix}{n:04d}"


def _provenance_category_for_actor(actor: str) -> str:
    """Per ADR/0029 D6 + ADR/0028 D8: features carry actor-derived provenance."""
    if actor == "agent":
        return "ai_proposal"
    if actor == "human":
        return "human_input"
    raise TransactionError(
        f"mechanical_spike: unsupported actor {actor!r}; expected 'agent' or 'human'"
    )
