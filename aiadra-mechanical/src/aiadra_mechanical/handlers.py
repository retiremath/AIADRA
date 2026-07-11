"""Native Engine authoring handlers for `aiadra-mechanical` v0.0.1 (ADR/0031 D5).

Mirrors the proven Wedge-003 handler flow against the production API, with
three production deltas:
  1. **Real OCCT validity gate** — each geometry-changing handler evaluates the
     current feature recipe through `cache.evaluate_with_cache` → OCCT. A
     recipe that cannot build a valid solid fails loudly (Class-1
     `TransactionError` for domain errors; Class-2 propagates from
     `geometry.py` and the dispatch adapter wraps it as
     `NativeEngineKernelError` — the engine never constructs that itself, per
     arc 20260602-1 Codex1 B1).
  2. **`kind` omitted** on `geometry_ref` records (ADR/0031 D6/B1): `vault_ref`
     addresses canonical *recipe* JSON bytes, not solid bytes, so v0.0.1 does
     not assert a `kind`.
  3. **Identity is recipe-hash** — the bytes staged into the Vault are the
     canonical recipe (`kernel.compute_recipe_bytes`), never the evaluated BREP.

Per ADR/0028 D8 provenance split: feature records carry actor-derived
`ai_proposal`/`human_input`; geometry_ref records carry `computed_result` +
`derived_from` in STRICT set-equality with `derived_from_feature_ids`.
"""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from aiadra_core.transaction.boundary import TransactionError

from . import cache
from .adapter_payload import (
    build_chamfer_payload,
    build_extrude_payload,
    build_fillet_payload,
    build_hole_payload,
    build_revolve_payload,
    build_sketch_payload,
    require_simple_cap_fit,
)
from .kernel import compute_recipe_bytes, vault_ref_for_bytes

if TYPE_CHECKING:
    from aiadra_core.native_engine.context import NativeEngineContext

ENGINE_ID = "mechanical"
# 0.1.5 (arc 20260622-4): adds the revolve feature — the first non-referencing
# CREATION feature since extrude (sketch → extrude XOR revolve); a revolve solid
# (tube/washer or solid cylinder) correlated recipe-first into outer/inner-wall +
# cap roles. No ADR/0038 reference machinery (revolve creates base geometry).
# 0.1.4 (arc 20260622-3): adds the chamfer feature (the fillet's edge-reference
# twin; shared `build_edge_reference_payload`; planar `…:face:chamfer` role, A3).
# 0.1.3 (arc 20260622-2): adds the hole feature + the `target_face` reference
# (ADR/0038 A1) + the generic produced-role vocabulary (`…:face:hole_wall`; A3).
# 0.1.2 (arc 20260621-2): adds the fillet feature + the engine-owned recipe-
# anchored `target_edge` reference (ADR/0038) + the `…:face:blend` role grammar.
# 0.1.1 (arc 20260609-1 Codex1 B2): sketch primitives carry engine-minted stable
# `skp_NNNN` ids — the primitive-level role anchor for Display topology identity.
ADAPTER_SCHEMA_VERSION = "0.1.6"


# =============================================================================
# Handler 1: add_sketch_feature
# =============================================================================


def handle_add_sketch_feature(context: "NativeEngineContext", params: dict[str, Any]) -> None:
    part_number = _require_param(params, "part_number", str, "mechanical.add_sketch_feature")
    primitives = _require_param(params, "primitives", list, "mechanical.add_sketch_feature")

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
        "fact_provenance": {"category": _provenance_category_for_actor(context.actor)},
    }
    sidecar = copy.deepcopy(sidecar)
    sidecar.setdefault("feature", []).append(copy.deepcopy(feature_record))

    # Real OCCT validity gate (also exercises the D8 cache key).
    _gate_validity(context, sidecar["feature"])

    # Recipe-hash identity (ADR/0031 D6): stage the canonical RECIPE bytes.
    vault_ref = _stage_recipe(context, sidecar["feature"])

    geom_record = {
        "id": geom_id,
        "role": "authoring_geometry",
        "vault_ref": vault_ref,  # NB: `kind` omitted per ADR/0031 D6/B1.
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
# Handler 2: add_extrude_feature
# =============================================================================


def handle_add_extrude_feature(context: "NativeEngineContext", params: dict[str, Any]) -> None:
    part_number = _require_param(params, "part_number", str, "mechanical.add_extrude_feature")
    sketch_feature_id = _require_param(params, "sketch_feature_id", str, "mechanical.add_extrude_feature")
    depth_mm = _require_param(params, "depth_mm", (int, float), "mechanical.add_extrude_feature")
    direction = _require_param(params, "direction", str, "mechanical.add_extrude_feature")

    if depth_mm <= 0:
        raise TransactionError(
            f"mechanical.add_extrude_feature: depth_mm must be positive, got {depth_mm!r}"
        )

    part_uuid, sidecar = _resolve_part_sidecar(context, part_number)

    sketch_feature = next(
        (f for f in sidecar.get("feature", [])
         if f.get("id") == sketch_feature_id and f.get("feature_type") == "sketch"),
        None,
    )
    if sketch_feature is None:
        raise TransactionError(
            f"mechanical.add_extrude_feature: sketch feature {sketch_feature_id!r} "
            f"not found on Part {part_number}"
        )
    # Codex1 B3 (arc 20260622-4): extrude XOR revolve, enforced symmetrically —
    # a Part with a revolve base cannot also take an extrude (one base creation
    # per Part in v1). The mirror guard lives on add_revolve_feature.
    if any(f.get("feature_type") == "revolve" for f in sidecar.get("feature", [])):
        raise TransactionError(
            f"mechanical.add_extrude_feature: Part {part_number} already has a revolve "
            f"base feature; v1 supports exactly one base creation per Part (extrude XOR revolve)"
        )

    feature_id = _next_id(sidecar.get("feature", []), prefix="feat_")
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
        "parameters": [depth_param_record],
        "adapter_payload": build_extrude_payload(
            sketch_feature_id=sketch_feature_id,
            direction=direction,
            depth_parameter_id=depth_param_id,
        ),
        "fact_provenance": {"category": _provenance_category_for_actor(context.actor)},
    }
    sidecar = copy.deepcopy(sidecar)
    sidecar.setdefault("feature", []).append(copy.deepcopy(feature_record))

    _gate_validity(context, sidecar["feature"])
    vault_ref = _stage_recipe(context, sidecar["feature"])

    # Subtree-output (ADR/0030 D4 step 3): the extrude REPLACES the sketch's
    # authoring_geometry with one derived from BOTH features.
    existing_geom = next(
        (g for g in sidecar.get("geometry_ref", [])
         if g.get("role") == "authoring_geometry"
         and sketch_feature_id in g.get("derived_from_feature_ids", [])),
        None,
    )
    new_geom_record = {
        "id": existing_geom["id"] if existing_geom else _next_id(sidecar.get("geometry_ref", []), prefix="geom_"),
        "role": "authoring_geometry",
        "vault_ref": vault_ref,  # `kind` omitted per ADR/0031 D6/B1.
        "derived_from_feature_ids": [sketch_feature_id, feature_id],
        "fact_provenance": {
            "category": "computed_result",
            "derived_from": [f"feature:{sketch_feature_id}", f"feature:{feature_id}"],
        },
    }
    if existing_geom is not None:
        for i, g in enumerate(sidecar["geometry_ref"]):
            if g.get("id") == new_geom_record["id"]:
                sidecar["geometry_ref"][i] = copy.deepcopy(new_geom_record)
                break
        geometry_delta = {"updated": [{"id": new_geom_record["id"], "new_record": copy.deepcopy(new_geom_record)}]}
    else:
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
# Handler: add_revolve_feature (ADR/0037 D8; a creation feature; arc 20260622-4)
# =============================================================================


def handle_add_revolve_feature(context: "NativeEngineContext", params: dict[str, Any]) -> None:
    part_number = _require_param(params, "part_number", str, "mechanical.add_revolve_feature")
    sketch_feature_id = _require_param(params, "sketch_feature_id", str, "mechanical.add_revolve_feature")
    axis = _require_param(params, "axis", str, "mechanical.add_revolve_feature")

    part_uuid, sidecar = _resolve_part_sidecar(context, part_number)
    features = sidecar.get("feature", [])

    sketch_feature = next(
        (f for f in features
         if f.get("id") == sketch_feature_id and f.get("feature_type") == "sketch"),
        None,
    )
    if sketch_feature is None:
        raise TransactionError(
            f"mechanical.add_revolve_feature: sketch feature {sketch_feature_id!r} "
            f"not found on Part {part_number}"
        )
    # Codex1 B3 (symmetric XOR): a Part with an extrude base cannot also revolve.
    if any(f.get("feature_type") == "extrude" for f in features):
        raise TransactionError(
            f"mechanical.add_revolve_feature: Part {part_number} already has an extrude "
            f"base feature; v1 supports exactly one base creation per Part (extrude XOR revolve)"
        )
    # Codex1 B2 (early-error path): exactly one rectangle, no circles/lines/extras.
    # The SAME check runs inside the evaluator fold (geometry._evaluate), so a
    # direct/corrupt recipe is rejected there too.
    from . import geometry

    primitives = sketch_feature.get("adapter_payload", {}).get("primitives", [])
    rectangle = geometry.require_simple_revolve_profile(primitives)
    # Crossing-axis is also caught at the gate below (evaluator path, Codex1 B1),
    # but check here for the clearest early error.
    geometry.revolve_radial_mode(rectangle, axis)

    feature_id = _next_id(features, prefix="feat_")
    feature_record = {
        "id": feature_id,
        "name": f"revolve_{feature_id}",
        "feature_type": "revolve",
        "engine": ENGINE_ID,
        "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
        "depends_on_feature_ids": [sketch_feature_id],
        # v1 has no numeric parameter (360° fixed; axis is structural payload).
        "adapter_payload": build_revolve_payload(
            sketch_feature_id=sketch_feature_id, axis=axis
        ),
        "fact_provenance": {"category": _provenance_category_for_actor(context.actor)},
    }
    sidecar = copy.deepcopy(sidecar)
    sidecar.setdefault("feature", []).append(copy.deepcopy(feature_record))

    _gate_validity(context, sidecar["feature"])  # builds the revolve through real OCCT
    vault_ref = _stage_recipe(context, sidecar["feature"])

    # Like the extrude, the revolve REPLACES the sketch's authoring_geometry with
    # one derived from BOTH features (the sketch profile + the revolve).
    existing_geom = next(
        (g for g in sidecar.get("geometry_ref", [])
         if g.get("role") == "authoring_geometry"
         and sketch_feature_id in g.get("derived_from_feature_ids", [])),
        None,
    )
    new_geom_record = {
        "id": existing_geom["id"] if existing_geom else _next_id(sidecar.get("geometry_ref", []), prefix="geom_"),
        "role": "authoring_geometry",
        "vault_ref": vault_ref,  # `kind` omitted per ADR/0031 D6/B1.
        "derived_from_feature_ids": [sketch_feature_id, feature_id],
        "fact_provenance": {
            "category": "computed_result",
            "derived_from": [f"feature:{sketch_feature_id}", f"feature:{feature_id}"],
        },
    }
    if existing_geom is not None:
        for i, g in enumerate(sidecar["geometry_ref"]):
            if g.get("id") == new_geom_record["id"]:
                sidecar["geometry_ref"][i] = copy.deepcopy(new_geom_record)
                break
        geometry_delta = {"updated": [{"id": new_geom_record["id"], "new_record": copy.deepcopy(new_geom_record)}]}
    else:
        sidecar.setdefault("geometry_ref", []).append(copy.deepcopy(new_geom_record))
        geometry_delta = {"added": [copy.deepcopy(new_geom_record)]}

    context.stage_sidecar(part_uuid, sidecar)
    context.emit_event("part_changed", {
        "object_uuid": part_uuid,
        "rationale": (
            f"add revolve feature {feature_id} consuming sketch {sketch_feature_id} "
            f"(360° around the {axis}-axis)"
        ),
        "feature_delta": {"added": [copy.deepcopy(feature_record)]},
        "geometry_ref_delta": geometry_delta,
    })


# =============================================================================
# Handler 3: add_fillet_feature (ADR/0037 D8 step 1; ADR/0038; arc 20260621-2)
# =============================================================================


def handle_add_fillet_feature(context: "NativeEngineContext", params: dict[str, Any]) -> None:
    part_number = _require_param(params, "part_number", str, "mechanical.add_fillet_feature")
    target_edge_id = _require_param(params, "target_edge_id", str, "mechanical.add_fillet_feature")
    radius_mm = _require_param(params, "radius_mm", (int, float), "mechanical.add_fillet_feature")
    if radius_mm <= 0:
        raise TransactionError(
            f"mechanical.add_fillet_feature: radius_mm must be positive, got {radius_mm!r}"
        )

    part_uuid, sidecar = _resolve_part_sidecar(context, part_number)
    features = sidecar.get("feature", [])
    extrude = next(
        (f for f in reversed(features) if f.get("feature_type") == "extrude"), None
    )
    if extrude is None:
        raise TransactionError(
            f"mechanical.add_fillet_feature: Part {part_number} has no extruded solid to round"
        )

    # ADR/0038 D1: the display `edge_id` is an INPUT SELECTOR only. Resolve it
    # against a FRESH parent-prefix extraction and persist the structured recipe
    # anchor read from THAT extraction — never parse-and-trust the display string
    # into Product Truth. (The current features ARE the parent prefix; the fillet
    # is appended after.)
    from . import topology

    topo = topology.extract_part_topology(list(features))
    match = next((e for e in topo.edges if e.edge_id == target_edge_id), None)
    if match is None:
        raise TransactionError(
            f"mechanical.add_fillet_feature: target_edge_id {target_edge_id!r} not found on "
            f"Part {part_number} (available: {sorted(e.edge_id for e in topo.edges)})"
        )
    # Codex2 B1: the v1 fillet rounds a SHARP edge only. Reject any other edge
    # kind as Class-1 BEFORE staging — unsupported topology must never reach
    # Product Truth, and the user gets a clear "unsupported target kind" error
    # rather than a Class-2 kernel rejection. (The general ADR/0038 reference
    # shape accepts any kind; the v1 fillet OPERATION constrains to sharp.)
    if match.kind != "sharp":
        raise TransactionError(
            f"mechanical.add_fillet_feature: v1 rounds a SHARP edge only; target "
            f"{target_edge_id!r} is kind {match.kind!r} (tangent / seam / boundary / "
            f"free are not supported). Pick a sharp model edge."
        )

    feature_id = _next_id(features, prefix="feat_")
    radius_param_id = _next_id_within_parameters(features, prefix="featp_")
    radius_param_record = {
        "id": radius_param_id,
        "name": "radius_mm",
        "value": float(radius_mm),
        "datatype": "number",
        "unit": "mm",
    }
    feature_record = {
        "id": feature_id,
        "name": f"fillet_{feature_id}",
        "feature_type": "fillet",
        "engine": ENGINE_ID,
        "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
        "depends_on_feature_ids": [extrude["id"]],  # ADR/0038 D5 dependency
        "parameters": [radius_param_record],
        "adapter_payload": build_fillet_payload(
            adjacent_face_roles=list(match.adjacent_face_ids),
            edge_kind=match.kind,
            resolved_against_topology_signature=topo.topology_signature,
        ),
        "fact_provenance": {"category": _provenance_category_for_actor(context.actor)},
    }
    sidecar = copy.deepcopy(sidecar)
    sidecar.setdefault("feature", []).append(copy.deepcopy(feature_record))

    # Folds the fillet through real OCCT (resolves the persisted reference on the
    # running solid, applies the round) — a too-large radius surfaces here as a
    # Class-2 kernel rejection (Codex1 Q3).
    _gate_validity(context, sidecar["feature"])
    vault_ref = _stage_recipe(context, sidecar["feature"])

    # The fillet extends the existing authoring_geometry (sketch+extrude) to also
    # derive from the fillet feature.
    existing_geom = next(
        (g for g in sidecar.get("geometry_ref", [])
         if g.get("role") == "authoring_geometry"
         and extrude["id"] in g.get("derived_from_feature_ids", [])),
        None,
    )
    if existing_geom is None:
        raise TransactionError(
            f"mechanical.add_fillet_feature: no authoring_geometry derived from the extrude "
            f"on Part {part_number}"
        )
    derived = list(existing_geom.get("derived_from_feature_ids", [])) + [feature_id]
    updated_geom = copy.deepcopy(existing_geom)
    updated_geom["vault_ref"] = vault_ref
    updated_geom["derived_from_feature_ids"] = derived
    updated_geom["fact_provenance"] = {
        "category": "computed_result",
        "derived_from": [f"feature:{fid}" for fid in derived],
    }
    for i, g in enumerate(sidecar["geometry_ref"]):
        if g.get("id") == updated_geom["id"]:
            sidecar["geometry_ref"][i] = copy.deepcopy(updated_geom)
            break

    context.stage_sidecar(part_uuid, sidecar)
    context.emit_event("part_changed", {
        "object_uuid": part_uuid,
        "rationale": (
            f"add fillet feature {feature_id} (radius={radius_mm}mm) on edge {target_edge_id}"
        ),
        "feature_delta": {"added": [copy.deepcopy(feature_record)]},
        "geometry_ref_delta": {"updated": [{"id": updated_geom["id"], "new_record": copy.deepcopy(updated_geom)}]},
    })


# =============================================================================
# Handler 4: add_chamfer_feature (ADR/0037 D8; ADR/0038; arc 20260622-3)
# =============================================================================


def handle_add_chamfer_feature(context: "NativeEngineContext", params: dict[str, Any]) -> None:
    part_number = _require_param(params, "part_number", str, "mechanical.add_chamfer_feature")
    target_edge_id = _require_param(params, "target_edge_id", str, "mechanical.add_chamfer_feature")
    distance_mm = _require_param(params, "distance_mm", (int, float), "mechanical.add_chamfer_feature")
    if distance_mm <= 0:
        raise TransactionError(
            f"mechanical.add_chamfer_feature: distance_mm must be positive, got {distance_mm!r}"
        )

    part_uuid, sidecar = _resolve_part_sidecar(context, part_number)
    features = sidecar.get("feature", [])
    extrude = next(
        (f for f in reversed(features) if f.get("feature_type") == "extrude"), None
    )
    if extrude is None:
        raise TransactionError(
            f"mechanical.add_chamfer_feature: Part {part_number} has no extruded solid to bevel"
        )

    # ADR/0038 D1: the display `edge_id` is an INPUT SELECTOR only. Resolve it
    # against a FRESH extraction; persist the structured recipe anchor from THAT.
    from . import topology

    topo = topology.extract_part_topology(list(features))
    match = next((e for e in topo.edges if e.edge_id == target_edge_id), None)
    if match is None:
        raise TransactionError(
            f"mechanical.add_chamfer_feature: target_edge_id {target_edge_id!r} not found on "
            f"Part {part_number} (available: {sorted(e.edge_id for e in topo.edges)})"
        )
    # v1 bevels a SHARP edge only (the same operation-scope guard as fillet).
    if match.kind != "sharp":
        raise TransactionError(
            f"mechanical.add_chamfer_feature: v1 bevels a SHARP edge only; target "
            f"{target_edge_id!r} is kind {match.kind!r} (tangent / seam / boundary / "
            f"free are not supported). Pick a sharp model edge."
        )

    feature_id = _next_id(features, prefix="feat_")
    distance_param_id = _next_id_within_parameters(features, prefix="featp_")
    distance_param_record = {
        "id": distance_param_id,
        "name": "distance_mm",
        "value": float(distance_mm),
        "datatype": "number",
        "unit": "mm",
    }
    feature_record = {
        "id": feature_id,
        "name": f"chamfer_{feature_id}",
        "feature_type": "chamfer",
        "engine": ENGINE_ID,
        "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
        "depends_on_feature_ids": [extrude["id"]],  # ADR/0038 D5 dependency
        "parameters": [distance_param_record],
        "adapter_payload": build_chamfer_payload(
            adjacent_face_roles=list(match.adjacent_face_ids),
            edge_kind=match.kind,
            resolved_against_topology_signature=topo.topology_signature,
        ),
        "fact_provenance": {"category": _provenance_category_for_actor(context.actor)},
    }
    sidecar = copy.deepcopy(sidecar)
    sidecar.setdefault("feature", []).append(copy.deepcopy(feature_record))

    # Folds the chamfer through real OCCT — a too-large distance surfaces here as
    # a Class-2 kernel rejection (mirrors the fillet's oversize radius).
    _gate_validity(context, sidecar["feature"])
    vault_ref = _stage_recipe(context, sidecar["feature"])

    existing_geom = next(
        (g for g in sidecar.get("geometry_ref", [])
         if g.get("role") == "authoring_geometry"
         and extrude["id"] in g.get("derived_from_feature_ids", [])),
        None,
    )
    if existing_geom is None:
        raise TransactionError(
            f"mechanical.add_chamfer_feature: no authoring_geometry derived from the extrude "
            f"on Part {part_number}"
        )
    derived = list(existing_geom.get("derived_from_feature_ids", [])) + [feature_id]
    updated_geom = copy.deepcopy(existing_geom)
    updated_geom["vault_ref"] = vault_ref
    updated_geom["derived_from_feature_ids"] = derived
    updated_geom["fact_provenance"] = {
        "category": "computed_result",
        "derived_from": [f"feature:{fid}" for fid in derived],
    }
    for i, g in enumerate(sidecar["geometry_ref"]):
        if g.get("id") == updated_geom["id"]:
            sidecar["geometry_ref"][i] = copy.deepcopy(updated_geom)
            break

    context.stage_sidecar(part_uuid, sidecar)
    context.emit_event("part_changed", {
        "object_uuid": part_uuid,
        "rationale": (
            f"add chamfer feature {feature_id} (distance={distance_mm}mm) on edge {target_edge_id}"
        ),
        "feature_delta": {"added": [copy.deepcopy(feature_record)]},
        "geometry_ref_delta": {"updated": [{"id": updated_geom["id"], "new_record": copy.deepcopy(updated_geom)}]},
    })


# =============================================================================
# Handler 5: add_hole_feature (ADR/0037 D8; ADR/0038 A1-A3; arc 20260622-2)
# =============================================================================


def handle_add_hole_feature(context: "NativeEngineContext", params: dict[str, Any]) -> None:
    part_number = _require_param(params, "part_number", str, "mechanical.add_hole_feature")
    target_face_id = _require_param(params, "target_face_id", str, "mechanical.add_hole_feature")
    diameter_mm = _require_param(params, "diameter_mm", (int, float), "mechanical.add_hole_feature")
    center_x_mm = _require_param(params, "center_x_mm", (int, float), "mechanical.add_hole_feature")
    center_y_mm = _require_param(params, "center_y_mm", (int, float), "mechanical.add_hole_feature")
    if diameter_mm <= 0:
        raise TransactionError(
            f"mechanical.add_hole_feature: diameter_mm must be positive, got {diameter_mm!r}"
        )

    part_uuid, sidecar = _resolve_part_sidecar(context, part_number)
    features = sidecar.get("feature", [])
    extrude = next(
        (f for f in reversed(features) if f.get("feature_type") == "extrude"), None
    )
    if extrude is None:
        raise TransactionError(
            f"mechanical.add_hole_feature: Part {part_number} has no extruded solid"
        )

    # ADR/0038 D1/A1: resolve the display `face_id` SELECTOR against a fresh
    # extraction; persist the structured recipe anchor read from THAT extraction.
    from . import topology

    topo = topology.extract_part_topology(list(features))
    match = next((f for f in topo.faces if f.face_id == target_face_id), None)
    if match is None:
        raise TransactionError(
            f"mechanical.add_hole_feature: target_face_id {target_face_id!r} not found on "
            f"Part {part_number} (available: {sorted(f.face_id for f in topo.faces)})"
        )
    # Operation-scope guard (the face analog of fillet's sharp-only B1): v1 places
    # a hole on a CAP face only (cap_top / cap_base). Class-1, before staging.
    if not (match.face_id.endswith(":face:cap_top") or match.face_id.endswith(":face:cap_base")):
        raise TransactionError(
            f"mechanical.add_hole_feature: v1 places a hole on a cap face only "
            f"(cap_top / cap_base); target {target_face_id!r} is not a cap. Pick a cap face."
        )

    # Simple-cap + fit-within-face (Codex1 B3): Class-1 domain, before staging.
    # The SAME `require_simple_cap_fit` is re-run inside the evaluator fold
    # (Codex2 B1), so every later parameter-edit / regeneration path enforces it
    # too — this handler call is the early-error path. `features` here is the
    # parent prefix (the new hole is not appended yet).
    require_simple_cap_fit(features, float(center_x_mm), float(center_y_mm), diameter_mm / 2.0)

    feature_id = _next_id(features, prefix="feat_")
    base = int(_next_id_within_parameters(features, prefix="featp_")[len("featp_"):])
    params_records = [
        {"id": f"featp_{base:04d}", "name": "diameter_mm", "value": float(diameter_mm),
         "datatype": "number", "unit": "mm"},
        {"id": f"featp_{base + 1:04d}", "name": "center_x_mm", "value": float(center_x_mm),
         "datatype": "number", "unit": "mm"},
        {"id": f"featp_{base + 2:04d}", "name": "center_y_mm", "value": float(center_y_mm),
         "datatype": "number", "unit": "mm"},
    ]
    feature_record = {
        "id": feature_id,
        "name": f"hole_{feature_id}",
        "feature_type": "hole",
        "engine": ENGINE_ID,
        "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
        "depends_on_feature_ids": [extrude["id"]],  # ADR/0038 D5 dependency
        "parameters": params_records,
        "adapter_payload": build_hole_payload(
            face_role=match.face_id,
            resolved_against_topology_signature=topo.topology_signature,
        ),
        "fact_provenance": {"category": _provenance_category_for_actor(context.actor)},
    }
    sidecar = copy.deepcopy(sidecar)
    sidecar.setdefault("feature", []).append(copy.deepcopy(feature_record))

    _gate_validity(context, sidecar["feature"])  # folds the hole through real OCCT
    vault_ref = _stage_recipe(context, sidecar["feature"])

    existing_geom = next(
        (g for g in sidecar.get("geometry_ref", [])
         if g.get("role") == "authoring_geometry"
         and extrude["id"] in g.get("derived_from_feature_ids", [])),
        None,
    )
    if existing_geom is None:
        raise TransactionError(
            f"mechanical.add_hole_feature: no authoring_geometry derived from the extrude "
            f"on Part {part_number}"
        )
    derived = list(existing_geom.get("derived_from_feature_ids", [])) + [feature_id]
    updated_geom = copy.deepcopy(existing_geom)
    updated_geom["vault_ref"] = vault_ref
    updated_geom["derived_from_feature_ids"] = derived
    updated_geom["fact_provenance"] = {
        "category": "computed_result",
        "derived_from": [f"feature:{fid}" for fid in derived],
    }
    for i, g in enumerate(sidecar["geometry_ref"]):
        if g.get("id") == updated_geom["id"]:
            sidecar["geometry_ref"][i] = copy.deepcopy(updated_geom)
            break

    context.stage_sidecar(part_uuid, sidecar)
    context.emit_event("part_changed", {
        "object_uuid": part_uuid,
        "rationale": (
            f"add hole feature {feature_id} (Ø{diameter_mm}mm at "
            f"({center_x_mm},{center_y_mm})) on face {target_face_id}"
        ),
        "feature_delta": {"added": [copy.deepcopy(feature_record)]},
        "geometry_ref_delta": {"updated": [{"id": updated_geom["id"], "new_record": copy.deepcopy(updated_geom)}]},
    })


# =============================================================================
# Handler 6: adjust_feature_parameter
# =============================================================================


def handle_adjust_feature_parameter(context: "NativeEngineContext", params: dict[str, Any]) -> None:
    part_number = _require_param(params, "part_number", str, "mechanical.adjust_feature_parameter")
    feature_id = _require_param(params, "feature_id", str, "mechanical.adjust_feature_parameter")
    parameter_name = _require_param(params, "parameter_name", str, "mechanical.adjust_feature_parameter")
    new_value = _require_param(params, "new_value", (int, float), "mechanical.adjust_feature_parameter")

    if parameter_name.endswith("depth_mm") and new_value <= 0:
        raise TransactionError(
            f"mechanical.adjust_feature_parameter: {parameter_name} must be positive, got {new_value!r}"
        )

    part_uuid, sidecar = _resolve_part_sidecar(context, part_number)

    target_idx = next(
        (i for i, f in enumerate(sidecar.get("feature", [])) if f.get("id") == feature_id), None
    )
    if target_idx is None:
        raise TransactionError(
            f"mechanical.adjust_feature_parameter: feature {feature_id!r} not found on Part {part_number}"
        )
    target_feature = sidecar["feature"][target_idx]
    param_idx = next(
        (i for i, p in enumerate(target_feature.get("parameters", []))
         if p.get("name") == parameter_name),
        None,
    )
    if param_idx is None:
        raise TransactionError(
            f"mechanical.adjust_feature_parameter: parameter {parameter_name!r} not found on "
            f"feature {feature_id!r} (available: "
            f"{[p.get('name') for p in target_feature.get('parameters', [])]})"
        )

    sidecar = copy.deepcopy(sidecar)
    updated_feature = copy.deepcopy(target_feature)
    updated_feature["parameters"][param_idx]["value"] = float(new_value)
    updated_feature["fact_provenance"] = {"category": _provenance_category_for_actor(context.actor)}
    sidecar["feature"][target_idx] = copy.deepcopy(updated_feature)

    _gate_validity(context, sidecar["feature"])
    vault_ref = _stage_recipe(context, sidecar["feature"])

    geom_idx = next(
        (i for i, g in enumerate(sidecar.get("geometry_ref", []))
         if g.get("role") == "authoring_geometry"
         and feature_id in g.get("derived_from_feature_ids", [])),
        None,
    )
    if geom_idx is None:
        raise TransactionError(
            f"mechanical.adjust_feature_parameter: no authoring_geometry geom_ref found "
            f"depending on feature {feature_id!r} on Part {part_number}"
        )
    updated_geom = copy.deepcopy(sidecar["geometry_ref"][geom_idx])
    updated_geom["vault_ref"] = vault_ref
    sidecar["geometry_ref"][geom_idx] = copy.deepcopy(updated_geom)

    context.stage_sidecar(part_uuid, sidecar)
    context.emit_event("part_changed", {
        "object_uuid": part_uuid,
        "rationale": f"adjust {feature_id}.{parameter_name} = {new_value}",
        "feature_delta": {"updated": [{"id": feature_id, "new_record": copy.deepcopy(updated_feature)}]},
        "geometry_ref_delta": {"updated": [{"id": updated_geom["id"], "new_record": copy.deepcopy(updated_geom)}]},
    })


# =============================================================================
# Handler 7: remove_feature
# =============================================================================


def handle_remove_feature(context: "NativeEngineContext", params: dict[str, Any]) -> None:
    part_number = _require_param(params, "part_number", str, "mechanical.remove_feature")
    feature_ids = _require_param(params, "feature_ids", list, "mechanical.remove_feature")
    geometry_ref_ids = params.get("geometry_ref_ids") or []
    if not isinstance(geometry_ref_ids, list):
        raise TransactionError(
            f"mechanical.remove_feature: geometry_ref_ids must be a list, "
            f"got {type(geometry_ref_ids).__name__}"
        )

    part_uuid, sidecar = _resolve_part_sidecar(context, part_number)

    existing_feature_ids = {f["id"] for f in sidecar.get("feature", [])}
    missing = set(feature_ids) - existing_feature_ids
    if missing:
        raise TransactionError(
            f"mechanical.remove_feature: feature(s) {sorted(missing)} not present on Part {part_number}"
        )
    existing_geom_ids = {g["id"] for g in sidecar.get("geometry_ref", [])}
    missing_geoms = set(geometry_ref_ids) - existing_geom_ids
    if missing_geoms:
        raise TransactionError(
            f"mechanical.remove_feature: geometry_ref(s) {sorted(missing_geoms)} not present on Part {part_number}"
        )

    # Dependent guard (ADR/0038 D5) is already enforced at the aiadra-core fold
    # layer (ADR/0029 D12): a remaining feature whose `depends_on_feature_ids`
    # dangle raises `FoldInconsistencyError` at validate/commit. The fillet
    # inherits that protection for free by declaring `depends_on_feature_ids:
    # [extrude]` — removing the parent solid while the fillet remains fails loud.
    # No redundant handler-level guard (it would preempt the core check + its
    # cascade-reject test).

    sidecar = copy.deepcopy(sidecar)
    sidecar["feature"] = [f for f in sidecar.get("feature", []) if f["id"] not in set(feature_ids)]
    if geometry_ref_ids:
        sidecar["geometry_ref"] = [g for g in sidecar.get("geometry_ref", []) if g["id"] not in set(geometry_ref_ids)]

    context.stage_sidecar(part_uuid, sidecar)
    payload: dict[str, Any] = {
        "object_uuid": part_uuid,
        "rationale": f"remove feature(s) {feature_ids}"
        + (f" + geometry_ref(s) {geometry_ref_ids}" if geometry_ref_ids else ""),
        "feature_delta": {"removed": list(feature_ids)},
    }
    if geometry_ref_ids:
        payload["geometry_ref_delta"] = {"removed": list(geometry_ref_ids)}
    context.emit_event("part_changed", payload)


# =============================================================================
# Shared helpers
# =============================================================================


def _gate_validity(context: "NativeEngineContext", features: list[dict[str, Any]]) -> None:
    """Evaluate the current recipe through OCCT (the v0.0.1 validity gate),
    keyed by the D8 cache. Raises Class-1 `TransactionError` / Class-2
    `MechanicalKernelEvaluationError`."""
    cache.evaluate_with_cache(
        features,
        last_event_id=context.event_log_last_event_id(),
        adapter_schema_version=ADAPTER_SCHEMA_VERSION,
    )


def _stage_recipe(context: "NativeEngineContext", features: list[dict[str, Any]]) -> str:
    """Stage the canonical RECIPE bytes (NOT BREP) into the Vault; return the
    recipe-hash `vault_ref` (ADR/0031 D6)."""
    recipe_bytes = compute_recipe_bytes(features)
    vault_ref, _vault_path = context.stage_vault_bytes(recipe_bytes)
    # Defensive: the staged ref must equal the canonical recipe hash.
    assert vault_ref == vault_ref_for_bytes(recipe_bytes)
    return vault_ref


def _require_param(params: dict[str, Any], name: str, type_: type | tuple[type, ...], op_kind: str) -> Any:
    if name not in params:
        raise TransactionError(f"{op_kind}: missing required param {name!r}")
    value = params[name]
    if not isinstance(value, type_):
        expected = type_.__name__ if isinstance(type_, type) else " | ".join(t.__name__ for t in type_)
        raise TransactionError(f"{op_kind}: param {name!r} must be {expected}, got {type(value).__name__}")
    return value


def _resolve_part_sidecar(context: "NativeEngineContext", part_number: str) -> tuple[str, dict[str, Any]]:
    entry = context.find_reservation_entry_by_number(part_number)
    if entry is None:
        raise TransactionError(f"Part {part_number!r} not found in workspace reservations")
    _prefix, res_entry = entry
    part_uuid = res_entry["object_uuid"]
    return part_uuid, context.load_sidecar(part_uuid)


def _next_id(records: list[dict], *, prefix: str) -> str:
    existing = {
        int(r["id"][len(prefix):])
        for r in records
        if isinstance(r, dict) and r.get("id", "").startswith(prefix)
    }
    return f"{prefix}{max(existing, default=0) + 1:04d}"


def _next_id_within_parameters(features: list[dict], *, prefix: str) -> str:
    existing: set[int] = set()
    for f in features:
        for p in f.get("parameters", []) or []:
            pid = p.get("id", "")
            if pid.startswith(prefix):
                try:
                    existing.add(int(pid[len(prefix):]))
                except ValueError:
                    pass
    return f"{prefix}{max(existing, default=0) + 1:04d}"


def _provenance_category_for_actor(actor: str) -> str:
    if actor == "agent":
        return "ai_proposal"
    if actor == "human":
        return "human_input"
    raise TransactionError(
        f"mechanical: unsupported actor {actor!r}; expected 'agent' or 'human'"
    )
