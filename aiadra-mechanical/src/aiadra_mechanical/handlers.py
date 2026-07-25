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
from . import face_frame, topology
from .adapter_payload import (
    build_chamfer_payload,
    build_extrude_payload,
    build_fillet_payload,
    build_hole_payload,
    build_revolve_payload,
    build_sketch_payload,
    require_simple_cap_fit,
)
from . import body_history
from .kernel import compute_recipe_bytes, vault_ref_for_bytes
from .recipe import effective_plane_frame, extrude_sign

if TYPE_CHECKING:
    from aiadra_core.native_engine.context import NativeEngineContext

ENGINE_ID = "mechanical"
# 0.1.11 (arc 20260717-2 M-identity, ADR/0038 A4): the body-history chain +
#   graph-to-bytes normalization — geometry records stage the PROJECTION of
#   their head's dependency closure (never the whole sidecar list); the
#   canonical serializer includes sorted depends_on_feature_ids; extrude
#   gains structural `operation: add|cut` (absent legacy = add).
# 0.1.8 (arc 20260714-3 S2, Codex1 B3): the SAME-KIND one-base guards — a
# second extrude (or second revolve) is rejected at the handler AND the
# evaluator (a stored two-base recipe fails loud, never "last one wins").
# 0.1.7 (arc 20260714-2 EP2): the sketch-plane binding — sketches carry a
# discriminated `plane: {kind: "principal", orientation: xy|yz|zx}` (absent ≡
# xy; datum/offset reserved); base features resolve EXACTLY their named sketch
# (`recipe.resolve_consumed_sketch` — the last-sketch shortcut is gone); the
# extrude direction is canonically `normal±` (legacy `z±` accepted only on xy,
# never rewritten on disk); geometry/topology generalize over the (u,v,n) frame.
# 0.1.6 (arc 20260711-11 slice E): the `contour` outer profile — an arbitrary
# CLOSED RING of typed line segments with per-segment `skp` anchors.
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
ADAPTER_SCHEMA_VERSION = "0.1.11"


# =============================================================================
# Handler 1: add_sketch_feature
# =============================================================================


def handle_add_sketch_feature(context: "NativeEngineContext", params: dict[str, Any]) -> None:
    part_number = _require_param(params, "part_number", str, "mechanical.add_sketch_feature")
    primitives = _require_param(params, "primitives", list, "mechanical.add_sketch_feature")
    # The sketch-plane binding (arc 20260714-2 EP2): optional discriminated
    # record; absent ≡ principal xy. Validated exactly in build_sketch_payload.
    plane = params.get("plane")

    part_uuid, sidecar = _resolve_part_sidecar(context, part_number)

    # SK-C1.0 S2 (adapter 0.1.10; Codex1 B1.3): the FACE-plane input — the
    # caller sends the DISPLAY face id (input vocabulary only, ADR/0038); the
    # handler resolves it against a FRESH extraction of the current prefix
    # (the hole pattern), mints the engine-owned structured reference, and
    # records the DIRECT PRODUCER in depends_on_feature_ids (the canonical
    # cascade edge). The display string is never parsed-and-trusted.
    sketch_depends_on: list[str] = []
    if isinstance(plane, dict) and plane.get("kind") == "face":
        if set(plane.keys()) != {"kind", "target_face_id"}:
            raise TransactionError(
                "mechanical.add_sketch_feature: a face-plane INPUT carries exactly "
                "{'kind': 'face', 'target_face_id': <display face id>}; the engine "
                "mints the stored reference itself"
            )
        target_face_id = _require_param(
            plane, "target_face_id", str, "mechanical.add_sketch_feature"
        )
        # A4.6/A4.7 (Codex5 B1): the support context is the BODY HEAD's
        # dependency-closed projection — the stored signature and the
        # resolution both use it (independent sketches never enter it).
        _all = list(sidecar.get("feature", []))
        _head = body_history.body_head(_all)
        prefix = (
            list(body_history.project_body_recipe(_all, _head).features)
            if _head is not None
            else _all
        )
        fresh = topology.extract_part_topology(prefix)
        stored_plane = {
            "kind": "face",
            "face_role": target_face_id,
            "resolved_against_topology_signature": fresh.topology_signature,
        }
        # ONE refusal authority: the resolver runs the full typed set
        # (missing / ambiguous / non-planar; the signature matches trivially).
        face_frame.resolve_face_plane(prefix, stored_plane)
        producer = topology.producing_feature_id(target_face_id)
        if producer not in {f.get("id") for f in prefix}:
            raise TransactionError(
                f"mechanical.add_sketch_feature: the support face {target_face_id!r} "
                f"names producer {producer!r}, which is not a committed feature of "
                f"Part {part_number}"
            )
        sketch_depends_on = [producer]
        # A4.6: the sketch records enough context to reconstruct the body
        # state its support was resolved against — when the producer is not
        # the CURRENT body head, the head is recorded too.
        current_head = body_history.body_head(prefix)
        if current_head is not None and current_head != producer:
            sketch_depends_on.append(current_head)
        plane = stored_plane

    feature_id = _next_id(sidecar.get("feature", []), prefix="feat_")
    geom_id = _next_id(sidecar.get("geometry_ref", []), prefix="geom_")

    feature_record = {
        "id": feature_id,
        "name": f"sketch_{feature_id}",
        "feature_type": "sketch",
        "engine": ENGINE_ID,
        "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
        "adapter_payload": build_sketch_payload(primitives, plane),
        "fact_provenance": {"category": _provenance_category_for_actor(context.actor)},
    }
    if sketch_depends_on:
        feature_record["depends_on_feature_ids"] = sketch_depends_on
    sidecar = copy.deepcopy(sidecar)
    sidecar.setdefault("feature", []).append(copy.deepcopy(feature_record))

    # Real OCCT validity gate (also exercises the D8 cache key).
    _gate_validity(context, sidecar["feature"])

    # Recipe-hash identity (ADR/0031 D6 + ADR/0038 A4.7): stage the canonical
    # PROJECTION of the sketch's own dependency closure — a principal sketch
    # stages itself alone; a face-bound sketch stages its support chain too.
    vault_ref, proj = _project_and_stage(context, sidecar["feature"], feature_id)

    geom_record = {
        "id": geom_id,
        "role": "authoring_geometry",
        # NB: `kind` omitted per ADR/0031 D6/B1.
        **_geom_fields_from_projection(vault_ref, proj),
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
# Handler 1b: add_reference_sketch (Gate F2b — the FIRST v2 writer)
# =============================================================================


def handle_add_reference_sketch(context: "NativeEngineContext", params: dict[str, Any]) -> None:
    """ADR/0044 A2 (arc 20260717-2, Gate F2b): the slice-1 REFERENCES sketch —
    the first authorized v2 (adapter 0.2.0) write. The A2.9 authoring
    transaction runs whole inside `sketch_v2.author_reference_sketch`
    (preview solve → verbatim skb-0 weak completion → empty exact witness
    set → validation); this handler stages the ONE resulting record
    atomically. Solved coordinates are derived display data and are never
    persisted anywhere in this path."""
    part_number = _require_param(params, "part_number", str, "mechanical.add_reference_sketch")
    axes = params.get("axes", "xy")
    x_axis_mm = params.get("x_axis_mm", 20.0)
    y_axis_mm = params.get("y_axis_mm", 20.0)

    # ADR/0044 A3.6.1 (pass sketch-place-1): the EXPLICIT version
    # discriminator — presence of `placement` selects the 0.2.1 writer;
    # absence (incl. the historical `plane` input and bare {part_number})
    # is the LEGACY lane and writes byte-identical 0.2.0 forever. Mixing
    # the two vocabularies refuses; nothing dispatches on silent omission.
    has_placement = "placement" in params
    if has_placement and "plane" in params:
        raise TransactionError(
            "mechanical.add_reference_sketch: `plane` (the legacy 0.2.0 "
            "lane) and `placement` (the 0.2.1 lane) are mutually exclusive "
            "— one explicit lane per call (A3.6.1)"
        )

    part_uuid, sidecar = _resolve_part_sidecar(context, part_number)

    feature_id = _next_id(sidecar.get("feature", []), prefix="feat_")
    geom_id = _next_id(sidecar.get("geometry_ref", []), prefix="geom_")

    provenance = {"category": _provenance_category_for_actor(context.actor)}
    if has_placement:
        from .sketch_v2 import author_reference_sketch_placed

        feature_record = author_reference_sketch_placed(
            feature_id=feature_id,
            name=f"references_{feature_id}",
            placement_input=params["placement"],
            axes=axes,
            x_axis_mm=x_axis_mm,
            y_axis_mm=y_axis_mm,
            fact_provenance=provenance,
        )
    else:
        plane = params.get("plane", {"kind": "principal", "orientation": "xy"})

        from .sketch_v2 import author_reference_sketch

        feature_record = author_reference_sketch(
            feature_id=feature_id,
            name=f"references_{feature_id}",
            plane=plane,
            axes=axes,
            x_axis_mm=x_axis_mm,
            y_axis_mm=y_axis_mm,
            fact_provenance=provenance,
        )

    sidecar = copy.deepcopy(sidecar)
    sidecar.setdefault("feature", []).append(copy.deepcopy(feature_record))

    # The evaluation gate now runs the v2 READ lifecycle over the staged
    # list (regeneration validates the committed record end-to-end).
    _gate_validity(context, sidecar["feature"])

    vault_ref, proj = _project_and_stage(context, sidecar["feature"], feature_id)
    geom_record = {
        "id": geom_id,
        "role": "authoring_geometry",
        **_geom_fields_from_projection(vault_ref, proj),
    }
    sidecar.setdefault("geometry_ref", []).append(copy.deepcopy(geom_record))

    context.stage_sidecar(part_uuid, sidecar)
    context.emit_event("part_changed", {
        "object_uuid": part_uuid,
        "rationale": f"add v2 reference sketch {feature_id} (shape axes={axes})",
        "feature_delta": {"added": [copy.deepcopy(feature_record)]},
        "geometry_ref_delta": {"added": [copy.deepcopy(geom_record)]},
    })


def handle_redefine_sketch_placement(context: "NativeEngineContext", params: dict[str, Any]) -> None:
    """ADR/0044 A3.6.2 (pass sketch-place-1; Petre's SP-06 ruling): re-place
    an EXISTING 0.2.1 sketch — the strict minimal-delta transaction.

    Omitted placement members KEEP their current persisted values (edit
    semantics, deliberately distinct from creation's defaults). Every
    non-placement field is preserved byte-for-byte; the frame-only invariant
    holds (the re-solve's weak completion must EQUAL the committed set); an
    effective no-op refuses BEFORE staging; failure leaves no delta.
    """
    _op = "mechanical.redefine_sketch_placement"
    part_number = _require_param(params, "part_number", str, _op)
    sketch_feature_id = _require_param(params, "sketch_feature_id", str, _op)

    part_uuid, sidecar = _resolve_part_sidecar(context, part_number)

    # A3.6.2 step 1 — target resolution FIRST; every wrong-target case
    # refuses before any solver invocation.
    matches = [i for i, f in enumerate(sidecar.get("feature", []))
               if f.get("id") == sketch_feature_id]
    if len(matches) != 1:
        raise TransactionError(
            f"{_op}: feature {sketch_feature_id!r} "
            f"{'not found' if not matches else 'is ambiguous'} on Part {part_number}"
        )
    target = sidecar["feature"][matches[0]]
    asv = target.get("adapter_schema_version")
    if target.get("feature_type") != "sketch" or target.get("engine") != "mechanical":
        raise TransactionError(
            f"{_op}: feature {sketch_feature_id!r} is not a mechanical sketch"
        )
    from .sketch_v2 import SKETCH_V21_ADAPTER_VERSION, regenerate_v2_sketch

    if asv == "0.2.0":
        raise TransactionError(
            f"{_op}: sketch-placement-redefine-v020 — feature "
            f"{sketch_feature_id!r} is a 0.2.0 record; its frame is immortal "
            "history (A3.1). Redefine applies to 0.2.1 placed sketches only; "
            "a cross-version rewrite is deliberately not opened in BS-1"
        )
    if asv != SKETCH_V21_ADAPTER_VERSION:
        raise TransactionError(
            f"{_op}: feature {sketch_feature_id!r} carries adapter version "
            f"{asv!r}; redefine targets literal {SKETCH_V21_ADAPTER_VERSION!r} only"
        )

    # A3.6.2 step 2 — overlay the provided members on the CURRENT placement
    # (omission keeps; explicit null/malformed refuses via validation).
    current = dict(target["adapter_payload"]["placement"])
    candidate = copy.deepcopy(current)
    provided = False
    for member in ("support", "orientation_ref", "orientation", "normal_side"):
        if member in params:
            candidate[member] = copy.deepcopy(params[member])
            provided = True

    from .sketch_placement import derive_frame, validate_placement_record

    def _pfail(reason: str) -> None:
        raise TransactionError(f"{_op}: {reason}")

    validate_placement_record(candidate, _pfail)
    derive_frame(candidate, _pfail)

    # A3.6.2 step 6 — the effective no-change case refuses BEFORE staging:
    # nothing is ever minted for a no-op.
    if not provided or candidate == current:
        raise TransactionError(
            f"{_op}: sketch-placement-unchanged — the "
            f"{'request names no members' if not provided else 'provided members equal the current placement'}; "
            "no recipe, event, or geometry projection is minted for a no-op"
        )

    # A3.6.2 steps 3+4 — the minimal delta: ONLY placement changes; the
    # frame-only invariant runs through the read lifecycle (regeneration
    # validates the committed weak completion EQUALS the derivation — a
    # placement edit can never alter local graph semantics). Original
    # fact_provenance is preserved (step 5): old geometry is never
    # relabeled; the redefine actor rides the EVENT.
    updated_feature = copy.deepcopy(target)
    updated_feature["adapter_payload"]["placement"] = copy.deepcopy(candidate)
    regenerate_v2_sketch(updated_feature)

    sidecar = copy.deepcopy(sidecar)
    sidecar["feature"][matches[0]] = copy.deepcopy(updated_feature)

    _gate_validity(context, sidecar["feature"])

    # A4.7 discipline: re-stage every authoring_geometry output whose head
    # closure contains the redefined feature (the construction sketch's own
    # projection re-derives in the new frame).
    updated_geoms: list[dict[str, Any]] = []
    for i, g in enumerate(sidecar.get("geometry_ref", [])):
        if g.get("role") != "authoring_geometry":
            continue
        head = _geom_head(g)
        if head is None:
            continue
        closure = body_history.dependency_closure(sidecar["feature"], head)
        if sketch_feature_id not in closure:
            continue
        new_ref, proj = _project_and_stage(context, sidecar["feature"], head)
        updated = copy.deepcopy(g)
        updated.update(_geom_fields_from_projection(new_ref, proj))
        sidecar["geometry_ref"][i] = copy.deepcopy(updated)
        updated_geoms.append(updated)
    if not updated_geoms:
        raise TransactionError(
            f"{_op}: no authoring_geometry geom_ref found depending on "
            f"feature {sketch_feature_id!r} on Part {part_number}"
        )

    context.stage_sidecar(part_uuid, sidecar)
    context.emit_event("part_changed", {
        "object_uuid": part_uuid,
        "rationale": f"redefine placement of {sketch_feature_id}",
        # A3.6.2 step 5 — the NEW placement facts' provenance rides the
        # event; the feature's original provenance/history is untouched.
        "placement_provenance": {"category": _provenance_category_for_actor(context.actor)},
        "feature_delta": {"updated": [{"id": sketch_feature_id,
                                       "new_record": copy.deepcopy(updated_feature)}]},
        "geometry_ref_delta": {"updated": [copy.deepcopy(g) for g in updated_geoms]},
    })


# =============================================================================
# Handler 2: add_extrude_feature
# =============================================================================


def handle_add_extrude_feature(context: "NativeEngineContext", params: dict[str, Any]) -> None:
    part_number = _require_param(params, "part_number", str, "mechanical.add_extrude_feature")
    # ADR/0038 A4 (arc 20260717-2): the structural operation — add fuses, cut
    # removes. Absent = add (legacy parity). Independent of `direction` (B2).
    operation = params.get("operation", "add")
    if operation not in ("add", "cut"):
        raise TransactionError(
            f"mechanical.add_extrude_feature: operation must be 'add' or 'cut', "
            f"got {operation!r}"
        )
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
    # ADR/0044 A2.4 (Gate F2a): a v2 constrained sketch is not a consumable
    # profile — extruding one is F2b+ territory. Codex23 B3: shared policy
    # VALIDATION runs first, so a malformed v2 record keeps its specific
    # refusal at the handler surface; only a VALID v2 sketch gets the named
    # consume refusal.
    _asv = sketch_feature.get("adapter_schema_version")
    if isinstance(_asv, str) and _asv.startswith("0.2.") \
            and sketch_feature.get("engine") == "mechanical":
        from .sketch_v2 import validate_v2_sketch_record

        validate_v2_sketch_record(sketch_feature)
        raise TransactionError(
            f"mechanical.add_extrude_feature: sketch {sketch_feature_id!r} is a "
            f"v2 constrained sketch (adapter {_asv}) — construction-only in "
            "this slice (skb-b0 admits reference frames, no profile "
            "geometry); it is not a consumable extrusion profile"
        )
    # Codex1 B3 (arc 20260622-4): extrude XOR revolve, enforced symmetrically —
    # a Part with a revolve base cannot also take an extrude (one base creation
    # per Part in v1). The mirror guard lives on add_revolve_feature.
    if any(f.get("feature_type") == "revolve" for f in sidecar.get("feature", [])):
        raise TransactionError(
            f"mechanical.add_extrude_feature: Part {part_number} already has a revolve "
            f"base feature; v1 supports exactly one base creation per Part (extrude XOR revolve)"
        )
    # M-add (arc 20260717-2, ADR/0038 A4): SEQUENTIAL extrudes — the one-
    # extrude guard is lifted. The base is the first body feature; every later
    # extrude ADVANCES the body chain and fuses (add) onto the current body.
    all_features = list(sidecar.get("feature", []))
    prior_head = body_history.body_head(all_features)
    sketch_plane = (sketch_feature.get("adapter_payload") or {}).get("plane")
    sketch_is_face_bound = isinstance(sketch_plane, dict) and sketch_plane.get("kind") == "face"

    if prior_head is None:
        # THE BASE. B2 first-add: nothing to cut from.
        if operation == "cut":
            raise TransactionError(
                "mechanical.add_extrude_feature: operation 'cut' requires an existing "
                "body — the first body feature must be 'add' (nothing to cut from)"
            )
    else:
        # A LATER extrude (the sequential slice) — add (boss) or cut (pocket).
        # v1 domain pin (A4.8): a sequential extrude consumes a FACE-BOUND
        # sketch — its support face IS the A4.8 within-face domain anchor.
        # Datum-plane sequential extrudes are a later slice.
        if not sketch_is_face_bound:
            raise TransactionError(
                f"mechanical.add_extrude_feature: a sequential extrude consumes a "
                f"FACE-BOUND sketch (its support face anchors the within-face "
                f"domain); sketch {sketch_feature_id!r} is datum-bound — "
                f"datum-plane sequential extrudes are a later slice"
            )
        # exactly-once consumption (B2): no two body features share a profile.
        for f in all_features:
            if not body_history.is_body_mutating(f):
                continue
            consumed = (f.get("adapter_payload") or {}).get("sketch_feature_id")
            if consumed == sketch_feature_id:
                raise TransactionError(
                    f"mechanical.add_extrude_feature: sketch {sketch_feature_id!r} is "
                    f"already consumed by {f.get('id')!r} — a committed profile is "
                    f"consumed by at most one solid feature"
                )

    # EP2 direction rule (Codex1 B3): the handler holds the resolved sketch, so
    # the write-time gate lives here — legacy `z±` is valid ONLY on a
    # principal-xy sketch, and NEW writes always store canonical `normal±`.
    # M-add: a FACE-BOUND sketch's frame comes from the ledger-aware resolver
    # against its dependency-closed support prefix (`effective_plane_frame`
    # deliberately refuses face records — the verified S2 boundary).
    if sketch_is_face_bound:
        _sk_prefix = [
            f for f in body_history.project_body_recipe(
                all_features, sketch_feature_id
            ).features
            if f.get("id") != sketch_feature_id
        ]
        frame = face_frame.resolve_face_plane(_sk_prefix, sketch_plane)
    else:
        frame = effective_plane_frame(sketch_feature)
    extrude_sign(direction, frame, op_kind="mechanical.add_extrude_feature")
    if direction in ("z+", "z-"):
        direction = "normal+" if direction == "z+" else "normal-"

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
        # A4.6: the consumed sketch (operand) + the immediately-preceding
        # body head (the chain edge) when a body already exists.
        "depends_on_feature_ids": (
            [sketch_feature_id] if prior_head is None
            else [sketch_feature_id, prior_head]
        ),
        "parameters": [depth_param_record],
        "adapter_payload": build_extrude_payload(
            sketch_feature_id=sketch_feature_id,
            direction=direction,
            depth_parameter_id=depth_param_id,
            operation=operation,
        ),
        "fact_provenance": {"category": _provenance_category_for_actor(context.actor)},
    }
    sidecar = copy.deepcopy(sidecar)
    sidecar.setdefault("feature", []).append(copy.deepcopy(feature_record))

    _gate_validity(context, sidecar["feature"])
    # A4.7: the new extrude is the new body head — stage ITS closure
    # projection, never the whole list.
    vault_ref, proj = _project_and_stage(context, sidecar["feature"], feature_id)

    # Subtree-output (ADR/0030 D4 step 3 + A4.7):
    #  - the BASE transitions the consumed sketch's record INTO the body record;
    #  - a SEQUENTIAL extrude advances the EXISTING body record and REMOVES the
    #    consumed sketch's record (`geometry_ref_delta.removed` — never two
    #    competing body roots).
    removed_geom_ids: list[str] = []
    if prior_head is None:
        existing_geom = _find_geom_by_head(sidecar, sketch_feature_id)
    else:
        existing_geom = _body_geom_record(sidecar, "mechanical.add_extrude_feature")
        consumed_rec = _find_geom_by_head(sidecar, sketch_feature_id)
        if consumed_rec is not None:
            removed_geom_ids.append(consumed_rec["id"])
            sidecar["geometry_ref"] = [
                g for g in sidecar.get("geometry_ref", [])
                if g.get("id") != consumed_rec["id"]
            ]
    new_geom_record = {
        "id": existing_geom["id"] if existing_geom else _next_id(sidecar.get("geometry_ref", []), prefix="geom_"),
        "role": "authoring_geometry",
        # `kind` omitted per ADR/0031 D6/B1.
        **_geom_fields_from_projection(vault_ref, proj),
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
    if removed_geom_ids:
        geometry_delta["removed"] = removed_geom_ids

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
    # S2 (arc 20260714-3 Codex1 B3): the same-kind half — a second revolve too.
    if any(f.get("feature_type") == "revolve" for f in features):
        raise TransactionError(
            f"mechanical.add_revolve_feature: Part {part_number} already has a revolve "
            f"base feature; v1 supports exactly one base creation per Part"
        )
    # EP2 (Codex1 D-P4): revolve is principal-xy-only in v1 — its axis
    # vocabulary is the global x/y in the sketch plane. Enforced on the EXACT
    # consumed sketch here and re-checked in the evaluator.
    if effective_plane_frame(sketch_feature).orientation != "xy":
        raise TransactionError(
            f"mechanical.add_revolve_feature: v1 revolve requires the sketch on "
            f"the principal xy plane; sketch {sketch_feature_id!r} is on "
            f"{effective_plane_frame(sketch_feature).orientation!r}"
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
    # A4.7: the revolve is the new body head — stage its closure projection.
    vault_ref, proj = _project_and_stage(context, sidecar["feature"], feature_id)

    # Like the extrude, the revolve REPLACES the consumed sketch's
    # authoring_geometry (found BY HEAD) with the body record.
    existing_geom = _find_geom_by_head(sidecar, sketch_feature_id)
    new_geom_record = {
        "id": existing_geom["id"] if existing_geom else _next_id(sidecar.get("geometry_ref", []), prefix="geom_"),
        "role": "authoring_geometry",
        # `kind` omitted per ADR/0031 D6/B1.
        **_geom_fields_from_projection(vault_ref, proj),
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
    # A4.6 (Codex5 B2): the mutation advances from the CURRENT graph-derived
    # body head — never "the last extrude by array scan". The v1 fold still
    # requires an extrude-based body (revolve modifiers refuse in the fold).
    body_head_id = body_history.body_head(features)
    extrude = next(
        (f for f in features
         if f.get("feature_type") == "extrude"), None
    )
    if body_head_id is None or extrude is None:
        raise TransactionError(
            f"mechanical.add_fillet_feature: Part {part_number} has no extruded solid to round"
        )

    # ADR/0038 D1: the display `edge_id` is an INPUT SELECTOR only. Resolve it
    # against a FRESH parent-prefix extraction and persist the structured recipe
    # anchor read from THAT extraction — never parse-and-trust the display string
    # into Product Truth. (The current features ARE the parent prefix; the fillet
    # is appended after.)
    from . import topology

    # A4.7 (Codex5 B2): the reference resolves against — and its stored
    # signature is computed over — the body head's dependency-closed
    # projection, never the raw sidecar array.
    _proj_features = list(
        body_history.project_body_recipe(features, body_head_id).features
    )
    topo = topology.extract_part_topology(_proj_features)
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
        # ADR/0038 D5 + A4.6 (Codex6 B3): the CURRENT body head + the DIRECT
        # referenced role owners (each validated as the head or its ancestor).
        "depends_on_feature_ids": _mutation_dependencies(
            features, body_head_id, list(match.adjacent_face_ids),
            "mechanical.add_fillet_feature",
        ),
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
    # A4.7: the fillet advances the body head — the ONE body record (found by
    # head, never list position) re-stages from the fillet's closure projection.
    vault_ref, proj = _project_and_stage(context, sidecar["feature"], feature_id)
    existing_geom = _body_geom_record(sidecar, "mechanical.add_fillet_feature")
    updated_geom = copy.deepcopy(existing_geom)
    updated_geom.update(_geom_fields_from_projection(vault_ref, proj))
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
    # A4.6 (Codex5 B2): the mutation advances from the CURRENT graph-derived
    # body head — never "the last extrude by array scan". The v1 fold still
    # requires an extrude-based body (revolve modifiers refuse in the fold).
    body_head_id = body_history.body_head(features)
    extrude = next(
        (f for f in features
         if f.get("feature_type") == "extrude"), None
    )
    if body_head_id is None or extrude is None:
        raise TransactionError(
            f"mechanical.add_chamfer_feature: Part {part_number} has no extruded solid to bevel"
        )

    # ADR/0038 D1: the display `edge_id` is an INPUT SELECTOR only. Resolve it
    # against a FRESH extraction; persist the structured recipe anchor from THAT.
    from . import topology

    # A4.7 (Codex5 B2): the reference resolves against — and its stored
    # signature is computed over — the body head's dependency-closed
    # projection, never the raw sidecar array.
    _proj_features = list(
        body_history.project_body_recipe(features, body_head_id).features
    )
    topo = topology.extract_part_topology(_proj_features)
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
        # ADR/0038 D5 + A4.6 (Codex6 B3): the CURRENT body head + the DIRECT
        # referenced role owners (each validated as the head or its ancestor).
        "depends_on_feature_ids": _mutation_dependencies(
            features, body_head_id, list(match.adjacent_face_ids),
            "mechanical.add_chamfer_feature",
        ),
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
    # A4.7: the chamfer advances the body head — one body record, projection-staged.
    vault_ref, proj = _project_and_stage(context, sidecar["feature"], feature_id)

    existing_geom = _body_geom_record(sidecar, "mechanical.add_chamfer_feature")
    updated_geom = copy.deepcopy(existing_geom)
    updated_geom.update(_geom_fields_from_projection(vault_ref, proj))
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
    # A4.6 (Codex5 B2): the mutation advances from the CURRENT graph-derived
    # body head — never "the last extrude by array scan".
    body_head_id = body_history.body_head(features)
    extrude = next(
        (f for f in features if f.get("feature_type") == "extrude"), None
    )
    if body_head_id is None or extrude is None:
        raise TransactionError(
            f"mechanical.add_hole_feature: Part {part_number} has no extruded solid"
        )

    # ADR/0038 D1/A1: resolve the display `face_id` SELECTOR against a fresh
    # extraction; persist the structured recipe anchor read from THAT extraction.
    from . import topology

    # A4.7 (Codex5 B2): the reference resolves against — and its stored
    # signature is computed over — the body head's dependency-closed
    # projection, never the raw sidecar array.
    _proj_features = list(
        body_history.project_body_recipe(features, body_head_id).features
    )
    topo = topology.extract_part_topology(_proj_features)
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
    # Codex6 B1: the domain check reads the BODY closure — an independent
    # sketch earlier in the array must never drive the cap-fit contract.
    require_simple_cap_fit(_proj_features, float(center_x_mm), float(center_y_mm), diameter_mm / 2.0)

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
        # ADR/0038 D5 + A4.6 (Codex6 B3): the CURRENT body head + the DIRECT
        # target face-role owner (validated as the head or its ancestor).
        "depends_on_feature_ids": _mutation_dependencies(
            features, body_head_id, [match.face_id],
            "mechanical.add_hole_feature",
        ),
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
    # A4.7: the hole advances the body head — one body record, projection-staged.
    vault_ref, proj = _project_and_stage(context, sidecar["feature"], feature_id)

    existing_geom = _body_geom_record(sidecar, "mechanical.add_hole_feature")
    updated_geom = copy.deepcopy(existing_geom)
    updated_geom.update(_geom_fields_from_projection(vault_ref, proj))
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
    # ADR/0044 A2.4 (Gate F2a): a v2 record has no adjustable-parameter
    # semantics yet. Codex23 B3: shared validation first (malformed keeps
    # its specific refusal), then the named refusal for valid records.
    _asv = target_feature.get("adapter_schema_version")
    if isinstance(_asv, str) and _asv.startswith("0.2.") \
            and target_feature.get("engine") == "mechanical":
        from .sketch_v2 import validate_v2_sketch_record

        validate_v2_sketch_record(target_feature)
        raise TransactionError(
            f"mechanical.adjust_feature_parameter: feature {feature_id!r} is a "
            f"v2 record (adapter {_asv}); v2 facts are edited only through "
            "the A2.9 atomic authoring transaction (no per-parameter edit "
            "lane exists for the references slice) — refuse"
        )
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

    # A4.7 (Codex2): the affected outputs are found by DEPENDENCY CLOSURE —
    # every authoring_geometry record whose head closure contains the
    # adjusted feature re-stages from ITS OWN projection (the body record,
    # and any face-bound sketch record riding the adjusted support chain).
    updated_geoms: list[dict[str, Any]] = []
    for i, g in enumerate(sidecar.get("geometry_ref", [])):
        if g.get("role") != "authoring_geometry":
            continue
        head = _geom_head(g)
        if head is None:
            continue
        closure = body_history.dependency_closure(sidecar["feature"], head)
        if feature_id not in closure:
            continue
        new_ref, proj = _project_and_stage(context, sidecar["feature"], head)
        updated = copy.deepcopy(g)
        updated.update(_geom_fields_from_projection(new_ref, proj))
        sidecar["geometry_ref"][i] = copy.deepcopy(updated)
        updated_geoms.append(updated)
    if not updated_geoms:
        raise TransactionError(
            f"mechanical.adjust_feature_parameter: no authoring_geometry geom_ref found "
            f"depending on feature {feature_id!r} on Part {part_number}"
        )

    context.stage_sidecar(part_uuid, sidecar)
    context.emit_event("part_changed", {
        "object_uuid": part_uuid,
        "rationale": f"adjust {feature_id}.{parameter_name} = {new_value}",
        "feature_delta": {"updated": [{"id": feature_id, "new_record": copy.deepcopy(updated_feature)}]},
        "geometry_ref_delta": {"updated": [
            {"id": g["id"], "new_record": copy.deepcopy(g)} for g in updated_geoms
        ]},
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

    # Codex23 B3 → F2b: the shared v2 preflight is now VALIDATE-only — a
    # valid v2 sketch is a legal resident (the staging re-evaluation runs
    # its read lifecycle); a malformed v2 record keeps its specific refusal
    # here, before any mutation is staged.
    from .sketch_v2 import validate_v2_records

    validate_v2_records(sidecar.get("feature", []))

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
    pre_removal_features = list(sidecar.get("feature", []))
    # Codex7 B1: SNAPSHOT the original geometry records BEFORE any explicit
    # `geometry_ref_ids` filtering — classification must see the live body
    # record even when the request names it for deletion.
    pre_removal_geometry = list(sidecar.get("geometry_ref", []) or [])
    remaining = [f for f in pre_removal_features if f["id"] not in set(feature_ids)]
    sidecar["feature"] = remaining

    # A4.7 (Codex5 B3, classification Codex6 B2, ordering Codex7 B1): the
    # affected geometry output follows the SURVIVING dependency graph — and
    # ONLY the OLD BODY RECORD may ever retarget. Classify from the ORIGINAL
    # graph AND the ORIGINAL geometry snapshot, BEFORE honoring any explicit
    # deletion; removed sketch/subtree records are REMOVED, never promoted to
    # body authority. Core's dangling-dependency protection (ADR/0029 D12)
    # still guards remaining FEATURES; this closes the same law for geometry
    # records.
    old_head = body_history.body_head(pre_removal_features)
    old_body_record_id: str | None = None
    if old_head is not None:
        old_body = [
            g for g in pre_removal_geometry
            if g.get("role") == "authoring_geometry" and _geom_head(g) == old_head
        ]
        if len(old_body) == 1:
            old_body_record_id = old_body[0]["id"]
    surviving_head = body_history.body_head(remaining)
    if (
        old_body_record_id is not None
        and old_body_record_id in set(geometry_ref_ids)
        and surviving_head is not None
    ):
        # BEFORE staging any sidecar or recipe bytes: deleting the body's one
        # geometry authority while its body survives would leave Display /
        # cache / HLR with nothing to resolve (A4.7 recoverability).
        raise TransactionError(
            f"mechanical.remove_feature: the request removes the body "
            f"authoring_geometry record {old_body_record_id!r} while a body "
            f"survives (head {surviving_head!r}) — contradictory; remove the "
            f"body features too, or keep the record"
        )
    if geometry_ref_ids:
        sidecar["geometry_ref"] = [g for g in sidecar.get("geometry_ref", []) if g["id"] not in set(geometry_ref_ids)]
    remaining_ids = {f["id"] for f in remaining}
    updated_records: list[dict[str, Any]] = []
    removed_records: list[str] = []
    kept: list[dict[str, Any]] = []
    for g in sidecar.get("geometry_ref", []) or []:
        if g.get("role") != "authoring_geometry":
            kept.append(g)
            continue
        head = _geom_head(g)
        if head in remaining_ids:
            kept.append(g)  # its head survives — untouched
            continue
        # headless record: ONLY the old body record may retarget (to the
        # surviving head's projection); every other headless record dangles
        # and is removed — a deleted sketch record is never promoted.
        if g["id"] == old_body_record_id and surviving_head is not None:
            new_ref, proj = _project_and_stage(context, remaining, surviving_head)
            updated = copy.deepcopy(g)
            updated.update(_geom_fields_from_projection(new_ref, proj))
            kept.append(updated)
            updated_records.append(updated)
        else:
            removed_records.append(g["id"])
    sidecar["geometry_ref"] = kept

    context.stage_sidecar(part_uuid, sidecar)
    payload: dict[str, Any] = {
        "object_uuid": part_uuid,
        "rationale": f"remove feature(s) {feature_ids}"
        + (f" + geometry_ref(s) {geometry_ref_ids}" if geometry_ref_ids else ""),
        "feature_delta": {"removed": list(feature_ids)},
    }
    all_removed = list(geometry_ref_ids) + removed_records
    geometry_delta: dict[str, Any] = {}
    if all_removed:
        geometry_delta["removed"] = all_removed
    if updated_records:
        geometry_delta["updated"] = [
            {"id": g["id"], "new_record": copy.deepcopy(g)} for g in updated_records
        ]
    if geometry_delta:
        payload["geometry_ref_delta"] = geometry_delta
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


# --- The body-authority helpers (ADR/0038 A4.6/A4.7, arc 20260717-2) --------
# ONE projection object supplies the staged bytes, the ordered
# derived_from_feature_ids, and fact_provenance.derived_from (A4.7.3).
# Convention: a geometry record's HEAD is the TERMINAL element of its ordered
# `derived_from_feature_ids` (the projection puts dependencies first) — true
# for every record this adapter has ever written ([sketch], [sketch, extrude],
# [sketch, extrude, fillet], ...), so legacy 0.1.10 records resolve too.


def _geom_head(geom: dict[str, Any]) -> str | None:
    derived = geom.get("derived_from_feature_ids") or []
    return derived[-1] if derived else None


def _find_geom_by_head(sidecar: dict[str, Any], head_id: str) -> dict[str, Any] | None:
    for g in sidecar.get("geometry_ref", []) or []:
        if g.get("role") == "authoring_geometry" and _geom_head(g) == head_id:
            return g
    return None


def _body_geom_record(
    sidecar: dict[str, Any], op_kind: str
) -> dict[str, Any]:
    """The ONE active body authoring_geometry record: head is body-mutating
    (A4.7 — resolved by head, NEVER by list position). Fail loud when a body
    is expected and no unique record exists."""
    matches = [
        g for g in sidecar.get("geometry_ref", []) or []
        if g.get("role") == "authoring_geometry"
        and (head := _geom_head(g)) is not None
        and any(
            f.get("id") == head and body_history.is_body_mutating(f)
            for f in sidecar.get("feature", []) or []
        )
    ]
    if len(matches) != 1:
        raise TransactionError(
            f"{op_kind}: expected exactly one body authoring_geometry record, "
            f"found {len(matches)}"
        )
    return matches[0]


def _project_and_stage(
    context: "NativeEngineContext",
    features: list[dict[str, Any]],
    head_id: str,
) -> tuple[str, "body_history.BodyProjection"]:
    """A4.7: stage the canonical ordered PROJECTION of the head's dependency
    closure — never the whole sidecar list."""
    proj = body_history.project_body_recipe(features, head_id)
    vault_ref = _stage_recipe(context, list(proj.features))
    return vault_ref, proj


def _geom_fields_from_projection(
    vault_ref: str, proj: "body_history.BodyProjection"
) -> dict[str, Any]:
    """Derived ids + provenance from the SAME projection object (A4.7.3)."""
    ids = list(proj.feature_ids)
    return {
        "vault_ref": vault_ref,
        "derived_from_feature_ids": ids,
        "fact_provenance": {
            "category": "computed_result",
            "derived_from": [f"feature:{fid}" for fid in ids],
        },
    }


def _mutation_dependencies(
    features: list[dict[str, Any]],
    body_head_id: str,
    referenced_roles,
    op_kind: str,
) -> list[str]:
    """A4.6 + ADR/0038 D5 (Codex6 B3): a reference-bearing mutation declares
    the CURRENT body head AND its direct referenced role owners — the head
    stays the unique maximal element because every owner must be its ancestor
    (validated here, fail loud). Deterministic order: head first, then the
    remaining owners sorted."""
    from . import topology

    owners: set[str] = set()
    for role in referenced_roles:
        owners.add(topology.producing_feature_id(role))
    head_closure = body_history.dependency_closure(features, body_head_id)
    for owner in owners:
        if owner != body_head_id and owner not in head_closure:
            raise TransactionError(
                f"{op_kind}: referenced role owner {owner!r} is neither the "
                f"current body head {body_head_id!r} nor its ancestor — the "
                f"reference crosses the body history (ADR/0038 A4.6)"
            )
    return [body_head_id] + sorted(owners - {body_head_id})


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
