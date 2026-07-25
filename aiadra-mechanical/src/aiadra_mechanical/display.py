"""Engine-side **Display Representation** generation for `aiadra-mechanical`
(ADR/0035; arc 20260609-1; refactored over the shared topology layer in arc
20260609-2 Codex1 B1). The read-only counterpart to the authoring handlers:
it evaluates a Part's feature recipe to a real OCCT solid (through the
validity-gate cache — arc 20260609-1 Codex2 N4 absorbed in 20260609-2), then
produces the kernel-neutral display package the AIADRA Studio viewport
consumes — face-grouped tessellation with true surface normals, true model
edges with kind classification (sharp / tangent / seam), and **engine-minted,
feature-anchored topology IDs**.

Identity derivation lives in `topology.py` (the B1 shared layer) — this module
consumes `PartTopology` records; it derives NO ids of its own. `hlr.py`
consumes the SAME records, so base display and HLR can never drift apart.

OCCT lives here, not in `aiadra-core` (kernel-neutral). This module returns a
plain dict; `aiadra_core.protocol.display_representation` validates it into the
frozen `DisplayRepresentation` contract.
"""
from __future__ import annotations

import math
from typing import Any

from aiadra_core.transaction.boundary import TransactionError

from OCP.TopExp import TopExp
from OCP.TopAbs import TopAbs_VERTEX, TopAbs_FACE, TopAbs_REVERSED
from OCP.TopoDS import TopoDS
from OCP.TopLoc import TopLoc_Location
from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
from OCP.BRep import BRep_Tool
from OCP.GeomLProp import GeomLProp_SLProps

from . import cache, topology
from .handlers import ADAPTER_SCHEMA_VERSION
from .topology import (  # re-exported for compatibility (tests import from here)
    DEFAULT_ANGULAR_DEFLECTION_RAD,
    DEFAULT_LINEAR_DEFLECTION_MM,
    compute_topology_signature,
)

# SK-C1.0 S2: v1.2 — additive `surface_kind` per face + top-level
# `sketch_frames` (the resolved frames of face-bound sketches). The HLR
# producer echoes THIS constant too (Codex2 B3.1: one version authority).
# v1.3 (Gate F2b, arc 20260717-2): additive `v2_construction` — the solved
# construction geometry of v2 sketches (A2.9 read-lifecycle output).
DISPLAY_REPRESENTATION_VERSION = "1.3"


# ---------------------------------------------------------------------------
# Read handler (registered as the `mechanical.display_representation` READ op).
# Receives a NativeEngineReadContext (committed reads only — no staging).
# ---------------------------------------------------------------------------


def handle_display_representation(context, params: dict[str, Any]) -> dict[str, Any]:
    """Generate the Display Representation for a Part from committed state.

    `params` is supplied by `aiadra_core.protocol.display_representation`:
    `object_uuid` (required), `object_number` (optional), `tolerance`
    (optional `{linear_deflection_mm, angular_deflection_rad}`).
    """
    material = load_display_material(context, params)
    return generate_display_representation(
        material["features"],
        object_uuid=material["object_uuid"],
        object_number=material["object_number"],
        geometry_ref=material["geometry_ref"],
        cache_key=material["cache_key"],
        linear_deflection_mm=material["linear_deflection_mm"],
        angular_deflection_rad=material["angular_deflection_rad"],
        cache_material=material["cache_material"],
    )


def load_display_material(context, params: dict[str, Any]) -> dict[str, Any]:
    """Resolve the committed-state inputs both display read handlers share:
    the feature recipe, identity material, the D8 cache key, and tolerances.
    (`handle_display_representation` and `hlr.handle_display_hlr` both call
    this — one resolution path, B1 discipline at the handler level too.)"""
    part_uuid = params.get("object_uuid")
    if not part_uuid:
        raise TransactionError(
            f"mechanical.{context.operation_kind}: missing object_uuid"
        )
    sidecar = context.load_sidecar(part_uuid)
    features = sidecar.get("feature", []) or []

    # ADR/0038 A4.7 (arc 20260717-2): with a body present, the identity echo
    # is the UNIQUE body record — resolved by its HEAD (the terminal element
    # of the ordered derived_from list, body-mutating), NEVER by list
    # position. The no-body branch keeps the existing live sketch-recipe
    # identity behavior (the first authoring record).
    from . import body_history

    records = [
        g for g in sidecar.get("geometry_ref", []) or []
        if g.get("role") == "authoring_geometry"
    ]
    head_id = body_history.body_head(features)
    if head_id is not None:
        by_id = {f.get("id"): f for f in features}
        body_records = [
            g for g in records
            if (derived := g.get("derived_from_feature_ids") or [])
            and derived[-1] in by_id
            and body_history.is_body_mutating(by_id[derived[-1]])
        ]
        if len(body_records) != 1:
            raise TransactionError(
                f"mechanical.{context.operation_kind}: expected exactly one body "
                f"authoring_geometry record, found {len(body_records)}"
            )
        authoring = body_records[0]
    else:
        authoring = records[0] if records else None
    if authoring is None:
        raise TransactionError(
            f"mechanical.{context.operation_kind}: Part has no authoring_geometry"
        )
    geometry_ref = authoring.get("vault_ref", "")
    object_number = params.get("object_number") or sidecar.get("object", {}).get("number", "")

    last_event_id = context.event_log_last_event_id()
    ck = cache.cache_key(
        features,
        last_event_id=last_event_id,
        adapter_schema_version=ADAPTER_SCHEMA_VERSION,
    )
    tol = params.get("tolerance") or {}
    return {
        "features": features,
        "object_uuid": part_uuid,
        "object_number": object_number,
        "geometry_ref": geometry_ref,
        "cache_key": ck,
        "linear_deflection_mm": float(
            tol.get("linear_deflection_mm", DEFAULT_LINEAR_DEFLECTION_MM)),
        "angular_deflection_rad": float(
            tol.get("angular_deflection_rad", DEFAULT_ANGULAR_DEFLECTION_RAD)),
        "cache_material": {
            "last_event_id": last_event_id,
            "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
        },
    }


# ---------------------------------------------------------------------------
# Public entry: recipe → display package dict
# ---------------------------------------------------------------------------


def generate_display_representation(
    features: list[dict[str, Any]],
    *,
    object_uuid: str,
    object_number: str,
    geometry_ref: str,
    cache_key: str,
    linear_deflection_mm: float = DEFAULT_LINEAR_DEFLECTION_MM,
    angular_deflection_rad: float = DEFAULT_ANGULAR_DEFLECTION_RAD,
    cache_material: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the Display Representation dict for the current recipe."""
    # S2 (arc 20260714-3, the stepwise paradigm): a recipe with NO base
    # creation feature — e.g. a committed-but-unconsumed sketch — has no solid
    # B-REP yet. Its honest display is ZERO faces/edges under the Part's REAL
    # identity (geometry_ref/cache_key/topology_signature all live, so the
    # invalidation contract works unchanged); the sketch itself is visible via
    # Studio's recipe-derived wire overlay (D-S2 — noncanonical, no contract
    # amendment). Solid correlation vocabularies (one-wall-per-segment etc.)
    # only apply once a base feature exists.
    has_base = any(
        f.get("feature_type") in ("extrude", "revolve") for f in features
    )
    if features and not has_base:
        return _no_solid_display(
            features,
            object_uuid=object_uuid,
            object_number=object_number,
            geometry_ref=geometry_ref,
            cache_key=cache_key,
            linear_deflection_mm=linear_deflection_mm,
            angular_deflection_rad=angular_deflection_rad,
        )
    topo = topology.extract_part_topology(
        features,
        object_uuid=object_uuid,
        object_number=object_number,
        geometry_ref=geometry_ref,
        cache_key=cache_key,
        linear_deflection_mm=linear_deflection_mm,
        angular_deflection_rad=angular_deflection_rad,
        cache_material=cache_material,
    )
    return build_display_payload(
        topo,
        sketch_frames=build_sketch_frames(features),
        v2_construction=build_v2_construction(features),
    )


def _no_solid_display(
    features: list[dict[str, Any]],
    *,
    object_uuid: str,
    object_number: str,
    geometry_ref: str,
    cache_key: str,
    linear_deflection_mm: float,
    angular_deflection_rad: float,
) -> dict[str, Any]:
    """The display of a Part whose recipe has features but NO base creation
    yet (S2 stepwise): zero render payload, full live identity."""
    return {
        "display_representation_version": DISPLAY_REPRESENTATION_VERSION,
        "identity": {
            "object_uuid": object_uuid,
            "object_number": object_number,
            "geometry_ref": geometry_ref,
            "cache_key": cache_key,
            "topology_signature": topology.compute_topology_signature(features),
        },
        "render": {
            "faces": [],
            "edges": [],
            "vertices": [],
            "bbox_min": [0.0, 0.0, 0.0],
            "bbox_max": [0.0, 0.0, 0.0],
            "linear_deflection_mm": linear_deflection_mm,
            "angular_deflection_rad": angular_deflection_rad,
            "buffer_encoding": "json_arrays",
        },
        "selection": {
            "id_space": "canonical",
            # Codex3 N1: capability metadata stays LITERAL — zero topology
            # means nothing is pickable (matches the featureless empty branch).
            "pickable_kinds": [],
            "names": {},
        },
        "sketch_frames": [],
        "v2_construction": build_v2_construction(features),
        "view_dependent": None,
        "invalidation": {
            "stale_when": ["geometry_ref_changed", "cache_key_changed"],
            "selection_invalid_when": "topology_signature_changed",
        },
        "counters": {
            "face_count": 0,
            "edge_count_by_kind": {},
            "triangle_count": 0,
            "vertex_count": 0,
        },
    }


def build_v2_construction(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Display v1.3 (Gate F2b): the SOLVED construction geometry of every
    valid v2 sketch — the A2.9 READ lifecycle's derived output, mapped from
    sketch-plane (u, v) mm to world via the sketch's principal frame.
    Derived display data, never Truth; a malformed record or a refused
    regeneration fails the display loud, exactly like evaluation."""
    from .recipe import principal_frame
    from .sketch_v2 import is_v2_series, regenerate_v2_sketch

    out: list[dict[str, Any]] = []
    for f in features:
        if not (f.get("feature_type") == "sketch"
                and is_v2_series(f.get("adapter_schema_version"))
                and f.get("engine") == "mechanical"):
            continue
        solved = regenerate_v2_sketch(f)
        payload = f.get("adapter_payload", {})
        if "placement" in payload:
            # 0.2.1 (ADR/0044 A3): the frame is DERIVED from the persisted
            # placement facts — sketch_placement is the one frame authority.
            from .sketch_placement import derive_frame as _derive_frame

            def _dfail(reason: str) -> None:
                raise ValueError(f"display: {reason}")

            u_vec, v_vec, _n = _derive_frame(payload["placement"], _dfail)

            def to_world(u: float, v: float) -> list[float]:
                return [u_vec[i] * u + v_vec[i] * v for i in range(3)]
        else:
            plane = payload.get("plane", {})
            frame = principal_frame(plane.get("orientation", "xy"))

            def to_world(u: float, v: float) -> list[float]:
                return list(frame.to_3d(u, v))

        points: list[dict[str, Any]] = []
        lines: list[dict[str, Any]] = []
        pt_world: dict[str, list[float]] = {}
        for e in payload.get("entities", []):
            if e.get("type") == "point":
                w = to_world(solved[f"{e['id']}.x"], solved[f"{e['id']}.y"])
                pt_world[e["id"]] = w
                points.append({"id": e["id"], "at": w})
        for e in payload.get("entities", []):
            if e.get("type") == "line":
                lines.append({
                    "id": e["id"],
                    "a": pt_world[e["start"]],
                    "b": pt_world[e["end"]],
                })
        from .sketch_v2 import decode_v2_sketch

        out.append({
            "sketch_feature_id": f.get("id"),
            "shape": decode_v2_sketch(f)["shape"],
            "construction": True,
            "points": points,
            "lines": lines,
        })
    return out


def build_sketch_frames(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Display v1.2 `sketch_frames`: the RESOLVED frame of every face-bound
    sketch (derived display data, never Truth). Resolution runs the full typed
    refusal set at the sketch's fold position — a display of a Part with a
    stale/broken binding fails loud, exactly like regeneration."""
    from . import face_frame

    frames: list[dict[str, Any]] = []
    for idx, feat in enumerate(features):
        if feat.get("feature_type") != "sketch":
            continue
        plane = (feat.get("adapter_payload") or {}).get("plane")
        if not (isinstance(plane, dict) and plane.get("kind") == "face"):
            continue
        frame = face_frame.resolve_face_plane(features[:idx], plane)
        frames.append({
            "sketch_feature_id": feat.get("id"),
            "origin_mm": list(frame.origin_mm),
            "u_axis": list(frame.u_axis),
            "v_axis": list(frame.v_axis),
            "normal": list(frame.normal),
        })
    return frames


def build_display_payload(
    topo: "topology.PartTopology",
    sketch_frames: list[dict[str, Any]] | None = None,
    v2_construction: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble the contract dict from extracted topology records (B1: ids come
    from the records, never derived here)."""
    role_by_index = topo.face_id_by_index()

    faces_payload, triangle_count = _build_faces(topo.face_map, role_by_index)
    # v1.2: additive engine-classified surface kind per face (the pick filter's
    # planarity authority — absent means unknown, consumers fail closed).
    kind_by_id = {f.face_id: f.surface_kind for f in topo.faces}
    for fp in faces_payload:
        sk = kind_by_id.get(fp.get("face_id"))
        fp["surface_kind"] = "plane" if sk == "plane" else "other"

    edges_payload = [
        {
            "edge_id": e.edge_id,
            "kind": e.kind,
            "polyline": list(e.polyline_mm),
            "faces": list(e.adjacent_face_ids),
        }
        for e in topo.edges
    ]

    vertices_payload = _build_vertices(topo.shape, topo.face_map, role_by_index)

    bbox_min, bbox_max = _bbox(faces_payload)

    edge_kind_counts: dict[str, int] = {}
    for e in edges_payload:
        edge_kind_counts[e["kind"]] = edge_kind_counts.get(e["kind"], 0) + 1

    names = {f.face_id: _human_name(f.face_id) for f in topo.faces}

    return {
        "display_representation_version": DISPLAY_REPRESENTATION_VERSION,
        "identity": {
            "object_uuid": topo.object_uuid,
            "object_number": topo.object_number,
            "geometry_ref": topo.geometry_ref,
            "cache_key": topo.cache_key,
            "topology_signature": topo.topology_signature,
        },
        "render": {
            "faces": faces_payload,
            "edges": edges_payload,
            "vertices": vertices_payload,
            "bbox_min": bbox_min,
            "bbox_max": bbox_max,
            "linear_deflection_mm": topo.linear_deflection_mm,
            "angular_deflection_rad": topo.angular_deflection_rad,
            "buffer_encoding": "json_arrays",
        },
        "selection": {
            "id_space": "canonical",
            "pickable_kinds": ["face", "edge", "vertex"],
            "names": names,
        },
        "sketch_frames": list(sketch_frames or []),
        # v1.3 (Gate F2b): SOLVED-derived v2 construction geometry (A2.9 read
        # lifecycle output) — derived display data, never Truth.
        "v2_construction": list(v2_construction or []),
        "view_dependent": None,  # populated only by the HLR read lane (hlr.py)
        "invalidation": {
            "stale_when": ["geometry_ref_changed", "cache_key_changed"],
            "selection_invalid_when": "topology_signature_changed",
        },
        "counters": {
            "face_count": len(faces_payload),
            "edge_count_by_kind": edge_kind_counts,
            "triangle_count": triangle_count,
            "vertex_count": len(vertices_payload),
        },
    }


# ---------------------------------------------------------------------------
# Buffers: faces / vertices (render-payload concerns; identity-free)
# ---------------------------------------------------------------------------


def _build_faces(face_map, role_by_index) -> tuple[list[dict[str, Any]], int]:
    out: list[dict[str, Any]] = []
    total_tris = 0
    for i in range(1, face_map.Extent() + 1):
        face = TopoDS.Face_s(face_map.FindKey(i))
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is None:
            continue
        trsf = loc.Transformation()
        reversed_face = face.Orientation() == TopAbs_REVERSED
        positions: list[float] = []
        normals: list[float] = []
        for k in range(1, tri.NbNodes() + 1):
            p = tri.Node(k).Transformed(trsf)
            positions.extend((p.X(), p.Y(), p.Z()))
        node_normals = _per_node_normals(face, tri, reversed_face)
        normals.extend(node_normals)
        triangles: list[int] = []
        for t in range(1, tri.NbTriangles() + 1):
            a, b, c = tri.Triangle(t).Get()
            # 1-indexed → 0-indexed; flip winding on REVERSED faces so all
            # triangles wind CCW about the outward normal.
            if reversed_face:
                triangles.extend((a - 1, c - 1, b - 1))
            else:
                triangles.extend((a - 1, b - 1, c - 1))
        total_tris += tri.NbTriangles()
        out.append({
            "face_id": role_by_index[i],
            "positions": positions,
            "normals": normals,
            "triangles": triangles,
            "appearance_slot": "default",
        })
    return out, total_tris


def _per_node_normals(face, tri, reversed_face) -> list[float]:
    """True per-node surface normals from UV params (flipped for REVERSED)."""
    if not tri.HasUVNodes():
        # Fallback: zero normals (renderer can derive flat normals).
        return [0.0] * (3 * tri.NbNodes())
    surf = BRep_Tool.Surface_s(face)
    out: list[float] = []
    for k in range(1, tri.NbNodes() + 1):
        uv = tri.UVNode(k)
        props = GeomLProp_SLProps(surf, uv.X(), uv.Y(), 1, 1e-6)
        if props.IsNormalDefined():
            d = props.Normal()
            nx, ny, nz = d.X(), d.Y(), d.Z()
            if reversed_face:
                nx, ny, nz = -nx, -ny, -nz
        else:
            nx, ny, nz = 0.0, 0.0, 0.0
        out.extend((nx, ny, nz))
    return out


def _build_vertices(shape, face_map, role_by_index) -> list[dict[str, Any]]:
    vert_faces = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_VERTEX, TopAbs_FACE, vert_faces)
    out: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for i in range(1, vert_faces.Extent() + 1):
        vtx = TopoDS.Vertex_s(vert_faces.FindKey(i))
        pnt = BRep_Tool.Pnt_s(vtx)
        roles = sorted({role_by_index[face_map.FindIndex(f)]
                        for f in vert_faces.FindFromIndex(i)})
        base = "vertex:" + "~".join(roles)
        n = seen.get(base, 0)
        seen[base] = n + 1
        vid = base if n == 0 else f"{base}#{n}"
        out.append({"vertex_id": vid, "position": [pnt.X(), pnt.Y(), pnt.Z()]})
    return out


def _bbox(faces_payload) -> tuple[list[float], list[float]]:
    lo = [math.inf, math.inf, math.inf]
    hi = [-math.inf, -math.inf, -math.inf]
    for f in faces_payload:
        pos = f["positions"]
        for j in range(0, len(pos), 3):
            for axis in range(3):
                v = pos[j + axis]
                lo[axis] = min(lo[axis], v)
                hi[axis] = max(hi[axis], v)
    if lo[0] == math.inf:
        lo = [0.0, 0.0, 0.0]; hi = [0.0, 0.0, 0.0]
    return lo, hi


def _human_name(role: str) -> str:
    """A short Creo-style human label for a role id (e.g.
    `feat_0002:face:cap_top` → `CAP_TOP`). Theme-/UI-agnostic."""
    tail = role.split(":")[-1]
    return tail.upper()
