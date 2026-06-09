"""Engine-side **Display Representation** generation for `aiadra-mechanical`
(ADR/0035; arc 20260609-1). The read-only counterpart to the authoring
handlers: it evaluates a Part's feature recipe to a real OCCT solid (reusing
the validity-gate cache), then produces the kernel-neutral display package the
AIADRA Studio viewport consumes — face-grouped tessellation with true surface
normals, true model edges with kind classification (sharp / tangent / seam),
and **engine-minted, feature-anchored topology IDs**.

Topology identity (the D5 crux; arc 20260609-1 Codex1 B2):
  - IDs are derived from the **stable recipe structure FIRST** — the feature
    ids + the engine-minted `skp_` primitive ids + a semantic role — and only
    THEN correlated to OCCT subshapes by geometry. Geometry is the *mapper*
    (role → subshape), never the identity source. Symmetric faces are
    disambiguated by the originating sketch edge (its midpoint), not by
    centroid magnitude or traversal order.
  - Invalidation is keyed on a deterministic `topology_signature` over the
    topology-affecting recipe skeleton (feature types + primitive ids/types),
    NOT a stored counter (a read op writes no Truth). Parameter edits (depth,
    dimensions, hole position) preserve every ID and the signature; adding /
    removing the hole or the extrude changes the signature and the ID set.

OCCT lives here, not in `aiadra-core` (kernel-neutral). This module returns a
plain dict; `aiadra_core.protocol.display_representation` validates it into the
frozen `DisplayRepresentation` contract.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

from aiadra_core.transaction.boundary import TransactionError

from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX, TopAbs_REVERSED
from OCP.TopoDS import TopoDS
from OCP.TopLoc import TopLoc_Location
from OCP.TopTools import (
    TopTools_IndexedMapOfShape,
    TopTools_IndexedDataMapOfShapeListOfShape,
)
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
from OCP.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_C0
from OCP.GeomLProp import GeomLProp_SLProps
from OCP.GCPnts import GCPnts_TangentialDeflection

from . import cache, geometry
from .handlers import ADAPTER_SCHEMA_VERSION
from .kernel import recipe_hash, vault_ref_for_bytes, compute_recipe_bytes

DISPLAY_REPRESENTATION_VERSION = "1.0"
DEFAULT_LINEAR_DEFLECTION_MM = 0.1
DEFAULT_ANGULAR_DEFLECTION_RAD = 0.5

# Geometric tolerance for role correlation (mm). Generous vs the kernel
# confusion tolerance — we are matching face centroids to sketch-edge
# midpoints, not asserting kernel-grade coincidence.
_CORRELATE_TOL_MM = 1e-6
_AXIS_DOT = 0.99  # |n·z| above this ⇒ a cap (normal parallel to the extrude axis)

# A topology-contributing primitive MUST carry an engine-minted anchor of this
# exact form (arc 20260609-1 Codex2 B1). NO placeholder fallback — a missing or
# malformed id means a corrupt/legacy payload, and minting a placeholder display
# id would fake a stable anchor that does not exist.
_SKP_ID_RE = re.compile(r"^skp_[0-9]{4}$")


def _require_skp_id(primitive: dict[str, Any], label: str) -> str:
    pid = primitive.get("id")
    if not isinstance(pid, str) or not _SKP_ID_RE.match(pid):
        raise TransactionError(
            f"mechanical.display_representation: {label} primitive lacks a valid "
            f"engine-minted id (expected ^skp_NNNN$, got {pid!r}); a corrupt or "
            f"pre-0.1.1 payload cannot anchor stable display identity — failing "
            f"loud rather than minting a placeholder id"
        )
    return pid


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
    part_uuid = params.get("object_uuid")
    if not part_uuid:
        raise TransactionError(
            "mechanical.display_representation: missing object_uuid"
        )
    sidecar = context.load_sidecar(part_uuid)
    features = sidecar.get("feature", []) or []

    authoring = next(
        (g for g in sidecar.get("geometry_ref", []) or []
         if g.get("role") == "authoring_geometry"),
        None,
    )
    if authoring is None:
        raise TransactionError(
            "mechanical.display_representation: Part has no authoring_geometry"
        )
    geometry_ref = authoring.get("vault_ref", "")
    object_number = params.get("object_number") or sidecar.get("object", {}).get("number", "")

    ck = cache.cache_key(
        features,
        last_event_id=context.event_log_last_event_id(),
        adapter_schema_version=ADAPTER_SCHEMA_VERSION,
    )
    tol = params.get("tolerance") or {}
    lin = float(tol.get("linear_deflection_mm", DEFAULT_LINEAR_DEFLECTION_MM))
    ang = float(tol.get("angular_deflection_rad", DEFAULT_ANGULAR_DEFLECTION_RAD))

    return generate_display_representation(
        features,
        object_uuid=part_uuid,
        object_number=object_number,
        geometry_ref=geometry_ref,
        cache_key=ck,
        linear_deflection_mm=lin,
        angular_deflection_rad=ang,
    )


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
) -> dict[str, Any]:
    """Build the Display Representation dict for the current recipe."""
    # N4 (Codex2): display intentionally re-evaluates the recipe rather than
    # reusing `cache.evaluate_with_cache`. The validity-gate cache stores the
    # solid keyed by the D8 freshness key, but a display read may run with a
    # different in-process cache population than the authoring path; for the
    # toy part the ~28 ms evaluation is cheap. Wiring display through the
    # evaluated-solid cache is a deferred optimization (arc 20260609-1 Codex2
    # N4) to revisit before larger parts / repeated display calls matter.
    shape = geometry.evaluate_part(features)
    if shape is None or shape.IsNull():
        raise TransactionError(
            "mechanical.display_representation: Part has no evaluable geometry "
            "(no sketch/extrude features) — nothing to display"
        )

    recipe = _extract_recipe_geometry(features)

    BRepMesh_IncrementalMesh(
        shape, linear_deflection_mm, False, angular_deflection_rad, True
    )

    # 1. Index faces; assign each a recipe-anchored role (correlation = mapper).
    face_map = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, TopAbs_FACE, face_map)
    role_by_face_index = _correlate_faces(face_map, recipe)

    # 2. Per-face tessellation buffers (grouped by face_id = role).
    faces_payload, triangle_count = _build_faces(face_map, role_by_face_index)

    # 3. True edges with kind + adjacent face roles.
    edges_payload = _build_edges(shape, face_map, role_by_face_index,
                                 linear_deflection_mm, angular_deflection_rad)

    # 4. Vertices, anchored by incident face roles.
    vertices_payload = _build_vertices(shape, face_map, role_by_face_index)

    # 5. bbox over the tessellated nodes.
    bbox_min, bbox_max = _bbox(faces_payload)

    # 6. Deterministic topology signature (B2) + counters (N5).
    topo_sig = compute_topology_signature(features)
    edge_kind_counts: dict[str, int] = {}
    for e in edges_payload:
        edge_kind_counts[e["kind"]] = edge_kind_counts.get(e["kind"], 0) + 1

    names = {role: _human_name(role) for role in role_by_face_index.values()}

    return {
        "display_representation_version": DISPLAY_REPRESENTATION_VERSION,
        "identity": {
            "object_uuid": object_uuid,
            "object_number": object_number,
            "geometry_ref": geometry_ref,
            "cache_key": cache_key,
            "topology_signature": topo_sig,
        },
        "render": {
            "faces": faces_payload,
            "edges": edges_payload,
            "vertices": vertices_payload,
            "bbox_min": bbox_min,
            "bbox_max": bbox_max,
            "linear_deflection_mm": linear_deflection_mm,
            "angular_deflection_rad": angular_deflection_rad,
            "buffer_encoding": "json_arrays",
        },
        "selection": {
            "id_space": "canonical",
            "pickable_kinds": ["face", "edge", "vertex"],
            "names": names,
        },
        "view_dependent": None,  # HLR slot — reserved (next arc)
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
# Topology signature (B2) — recipe-derived, value-independent
# ---------------------------------------------------------------------------


def compute_topology_signature(features: list[dict[str, Any]]) -> str:
    """A deterministic hash over the **topology skeleton** — feature types +
    sketch primitive (id, type) lists — EXCLUDING parameter values (depth,
    dimensions, positions, direction). Stable across parameter edits; changes
    when a feature or primitive is added/removed. NOT a stored counter."""
    skeleton: list[dict[str, Any]] = []
    for f in features:
        entry: dict[str, Any] = {"feature": f.get("feature_type")}
        if f.get("feature_type") == "sketch":
            prims = f.get("adapter_payload", {}).get("primitives", [])
            entry["primitives"] = sorted(
                (p.get("id", ""), p.get("type")) for p in prims
            )
        skeleton.append(entry)
    raw = json.dumps(skeleton, sort_keys=True).encode("utf-8")
    return "topo_" + hashlib.sha256(raw).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Recipe geometry extraction (the stable anchor source)
# ---------------------------------------------------------------------------


def _extract_recipe_geometry(features: list[dict[str, Any]]) -> dict[str, Any]:
    """Pull the stable, recipe-derived anchors used for role correlation:
    the sketch feature id + rectangle/circle primitive ids & geometry, and the
    extrude feature id + direction (+ resolved depth)."""
    sketch = _last(features, "sketch")
    if sketch is None:
        raise TransactionError(
            "mechanical.display_representation: recipe has no sketch feature"
        )
    sketch_id = sketch["id"]
    prims = sketch.get("adapter_payload", {}).get("primitives", [])
    rectangle = next((p for p in prims if p.get("type") == "rectangle"), None)
    circle = next((p for p in prims if p.get("type") == "circle"), None)
    if rectangle is None:
        raise TransactionError(
            "mechanical.display_representation: sketch has no rectangle profile"
        )

    extrude = _last(features, "extrude")
    direction = "z+"
    depth = None
    extrude_id = None
    if extrude is not None:
        extrude_id = extrude["id"]
        direction = extrude.get("adapter_payload", {}).get("direction", "z+")
        for p in extrude.get("parameters", []):
            if p.get("name") == "depth_mm":
                depth = float(p["value"])
                break
    return {
        "sketch_id": sketch_id,
        "extrude_id": extrude_id,
        "rectangle": rectangle,
        "circle": circle,
        "direction": direction,
        "depth": depth,
        "sign": 1.0 if direction == "z+" else -1.0,
    }


def _rect_edges(rect: dict[str, Any]) -> list[tuple[str, float, float]]:
    """The 4 rectangle edges as (role_suffix, midpoint_x, midpoint_y). The
    suffix is the stable sketch-edge anchor; the midpoint disambiguates walls
    even when dimensions are symmetric (a square prism)."""
    x = float(rect["x_mm"]); y = float(rect["y_mm"])
    w = float(rect["width_mm"]); h = float(rect["height_mm"])
    return [
        ("y_min", x + w / 2, y),          # bottom edge (outward -y)
        ("x_max", x + w, y + h / 2),       # right edge  (outward +x)
        ("y_max", x + w / 2, y + h),       # top edge    (outward +y)
        ("x_min", x, y + h / 2),           # left edge   (outward -x)
    ]


# ---------------------------------------------------------------------------
# Face correlation — recipe role → OCCT face index (the mapper)
# ---------------------------------------------------------------------------


def _correlate_faces(face_map, recipe: dict[str, Any]) -> dict[int, str]:
    """Assign every OCCT face a recipe-anchored role id. Raises if a face
    cannot be mapped (fail-loud: a correlation gap is a real bug, not a
    silent fallback to traversal order)."""
    sketch_id = recipe["sketch_id"]
    extrude_id = recipe["extrude_id"]
    rect = recipe["rectangle"]
    circle = recipe["circle"]
    # B1 (Codex2): the display id source MUST be a real engine-minted anchor,
    # never a placeholder — fail loud before any id is minted.
    rect_skp = _require_skp_id(rect, "rectangle")
    circle_skp = _require_skp_id(circle, "circle") if circle else None
    feat_prefix = extrude_id if extrude_id is not None else sketch_id
    rect_edges = _rect_edges(rect)

    roles: dict[int, str] = {}
    used_wall_suffixes: set[str] = set()
    for i in range(1, face_map.Extent() + 1):
        face = TopoDS.Face_s(face_map.FindKey(i))
        surf = BRepAdaptor_Surface(face)
        stype = surf.GetType()
        centroid, normal = _face_centroid_normal(face)

        if stype == GeomAbs_Cylinder:
            roles[i] = f"{feat_prefix}/{circle_skp}:face:hole_wall"
            continue

        if stype == GeomAbs_Plane and abs(normal[2]) >= _AXIS_DOT:
            # A cap: distinguish base (sketch plane, z≈0) vs top (swept end).
            if abs(centroid[2]) <= 1e-6:
                roles[i] = f"{feat_prefix}:face:cap_base"
            else:
                roles[i] = f"{feat_prefix}:face:cap_top"
            continue

        if stype == GeomAbs_Plane:
            # A side wall — correlate to the originating sketch edge by the
            # closest rectangle-edge midpoint (the sketch-edge anchor).
            suffix = _nearest_wall(centroid, rect_edges)
            if suffix is None or suffix in used_wall_suffixes:
                raise TransactionError(
                    f"mechanical.display_representation: could not uniquely "
                    f"correlate side face {i} to a rectangle edge "
                    f"(centroid={centroid}); recipe/topology mismatch"
                )
            used_wall_suffixes.add(suffix)
            roles[i] = f"{feat_prefix}/{rect_skp}:face:wall_{suffix}"
            continue

        raise TransactionError(
            f"mechanical.display_representation: unexpected surface type "
            f"{stype} on face {i}; v0.0.1 supports plane + cylinder only"
        )
    return roles


def _nearest_wall(centroid, rect_edges) -> str | None:
    best = None
    best_d = None
    for suffix, mx, my in rect_edges:
        d = math.hypot(centroid[0] - mx, centroid[1] - my)
        if best_d is None or d < best_d:
            best_d = d
            best = suffix
    return best


def _face_centroid_normal(face):
    """Representative centroid (node average) + outward normal (true surface
    normal at the first UV node, flipped for a REVERSED face)."""
    loc = TopLoc_Location()
    tri = BRep_Tool.Triangulation_s(face, loc)
    trsf = loc.Transformation()
    if tri is None or tri.NbNodes() == 0:
        raise TransactionError(
            "mechanical.display_representation: face has no triangulation"
        )
    sx = sy = sz = 0.0
    n = tri.NbNodes()
    for k in range(1, n + 1):
        p = tri.Node(k).Transformed(trsf)
        sx += p.X(); sy += p.Y(); sz += p.Z()
    centroid = (sx / n, sy / n, sz / n)
    normal = _surface_normal(face, tri)
    return centroid, normal


def _surface_normal(face, tri) -> tuple[float, float, float]:
    if not tri.HasUVNodes():
        return (0.0, 0.0, 0.0)
    surf = BRep_Tool.Surface_s(face)
    uv = tri.UVNode(1)
    props = GeomLProp_SLProps(surf, uv.X(), uv.Y(), 1, 1e-6)
    if not props.IsNormalDefined():
        return (0.0, 0.0, 0.0)
    d = props.Normal()
    nx, ny, nz = d.X(), d.Y(), d.Z()
    if face.Orientation() == TopAbs_REVERSED:
        nx, ny, nz = -nx, -ny, -nz
    return (nx, ny, nz)


# ---------------------------------------------------------------------------
# Buffers: faces / edges / vertices
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


def _build_edges(shape, face_map, role_by_index,
                 linear_deflection, angular_deflection) -> list[dict[str, Any]]:
    edge_faces = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, edge_faces)
    out: list[dict[str, Any]] = []
    role_pair_seen: dict[str, int] = {}
    for i in range(1, edge_faces.Extent() + 1):
        edge = TopoDS.Edge_s(edge_faces.FindKey(i))
        adj = [TopoDS.Face_s(f) for f in edge_faces.FindFromIndex(i)]
        adj_roles = [role_by_index[face_map.FindIndex(f)] for f in adj]
        kind = _edge_kind(edge, adj)
        edge_id = _edge_id(adj_roles, kind, role_pair_seen)
        polyline = _discretize_edge(edge, linear_deflection, angular_deflection)
        out.append({
            "edge_id": edge_id,
            "kind": kind,
            "polyline": polyline,
            "faces": sorted(set(adj_roles)),
        })
    return out


def _edge_kind(edge, adj_faces) -> str:
    if len(adj_faces) == 2:
        if adj_faces[0].IsSame(adj_faces[1]):
            return "seam"
        cont = BRep_Tool.Continuity_s(edge, adj_faces[0], adj_faces[1])
        return "sharp" if cont == GeomAbs_C0 else "tangent"
    if len(adj_faces) == 1:
        return "seam" if BRep_Tool.IsClosed_s(edge, adj_faces[0]) else "boundary"
    return "free"


def _edge_id(adj_roles, kind, role_pair_seen) -> str:
    roles = sorted(set(adj_roles))
    if kind == "seam" and len(roles) == 1:
        base = f"edge:{roles[0]}~seam"
    else:
        base = "edge:" + "~".join(roles)
    # Defensive disambiguation if a role pair ever shares multiple edges
    # (richer topology than v0.0.1); keeps ids unique + deterministic.
    n = role_pair_seen.get(base, 0)
    role_pair_seen[base] = n + 1
    return base if n == 0 else f"{base}#{n}"


def _discretize_edge(edge, linear_deflection, angular_deflection) -> list[float]:
    curve = BRepAdaptor_Curve(edge)
    disc = GCPnts_TangentialDeflection(curve, linear_deflection, angular_deflection)
    pts: list[float] = []
    for k in range(1, disc.NbPoints() + 1):
        p = disc.Value(k)
        pts.extend((p.X(), p.Y(), p.Z()))
    return pts


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


def _last(features: list[dict[str, Any]], ftype: str) -> dict[str, Any] | None:
    chosen = None
    for f in features:
        if f.get("feature_type") == ftype:
            chosen = f
    return chosen
