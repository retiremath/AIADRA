"""Shared **topology extraction layer** for `aiadra-mechanical` display reads
(arc 20260609-2 Codex1 B1; refactored out of `display.py`).

One extraction, two consumers: `display.generate_display_representation()`
(the base Display Representation package) and `hlr.generate_hlr()` (the
view-dependent HLR overlay) BOTH consume the records produced here. Identity
is derived ONCE — recipe-first, geometry-second (ADR/0035 D2) — so HLR
correlation inherits the foundation invariant instead of cloning it. No
parallel edge-id derivation exists anywhere (the B1 hard stop).

The records carry the live OCCT handles (face/edge) alongside the canonical
ids and model-space sampled curves, which is exactly what view-dependent
correlation needs and what the v1 payload-building code threw away.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any

from aiadra_core.transaction.boundary import TransactionError

from OCP.TopExp import TopExp
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_REVERSED
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

from . import cache, geometry, profile_classify
from .arc_geometry import arc_geometry, point_on_arc_span
from .recipe import (
    PlaneFrame,
    effective_plane_frame,
    plane_skeleton,
    extrude_sign,
    resolve_consumed_sketch,
)

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


def require_skp_id(primitive: dict[str, Any], label: str) -> str:
    pid = primitive.get("id")
    if not isinstance(pid, str) or not _SKP_ID_RE.match(pid):
        raise TransactionError(
            f"mechanical.display: {label} primitive lacks a valid "
            f"engine-minted id (expected ^skp_NNNN$, got {pid!r}); a corrupt or "
            f"pre-0.1.1 payload cannot anchor stable display identity — failing "
            f"loud rather than minting a placeholder id"
        )
    return pid


# ---------------------------------------------------------------------------
# Records — the one identity source both display and HLR consume (B1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FaceRecord:
    face_id: str               # canonical recipe-anchored role id
    occt_index: int            # 1-based index into `PartTopology.face_map`
    surface_kind: str          # "plane" | "cylinder" | "other" (exact; Codex7 B2)
    face: Any                  # live TopoDS_Face handle (NEVER identity)


@dataclass(frozen=True)
class EdgeRecord:
    edge_id: str               # canonical id derived from adjacent face roles
    kind: str                  # sharp | tangent | seam | boundary | free
    occt_index: int            # 1-based index into the edge→faces ancestor map
    edge: Any                  # live TopoDS_Edge handle (NEVER identity)
    adjacent_face_ids: tuple[str, ...]
    polyline_mm: tuple[float, ...]  # model-space sampled true curve (flat xyz)


@dataclass(frozen=True)
class PartTopology:
    """Everything identity-bearing about one evaluated Part, extracted once."""

    shape: Any                 # the evaluated TopoDS_Shape (meshed)
    face_map: Any              # TopTools_IndexedMapOfShape over FACEs
    faces: tuple[FaceRecord, ...]
    edges: tuple[EdgeRecord, ...]
    topology_signature: str
    linear_deflection_mm: float
    angular_deflection_rad: float
    # identity-echo material (ADR/0035 D1 identity + arc 20260609-2 B3)
    object_uuid: str = ""
    object_number: str = ""
    geometry_ref: str = ""
    cache_key: str = ""

    def face_id_by_index(self) -> dict[int, str]:
        return {f.occt_index: f.face_id for f in self.faces}

    def edge_ids(self) -> tuple[str, ...]:
        return tuple(e.edge_id for e in self.edges)


# ---------------------------------------------------------------------------
# Extraction — the single entry point (B1)
# ---------------------------------------------------------------------------


def producing_feature_id(face_id: str) -> str:
    """The DIRECT producing feature of a canonical face id — the ONE tested
    grammar authority (ADR/0035: '<feature>[/<primitive>]:<kind>:<role>'; a
    wall id like 'feat_0002/skp_0001:face:wall_y_min' is produced by
    'feat_0002'). Used AFTER exact fresh-topology matching confirms the id
    exists — this extracts ownership, never existence (Codex7 B1)."""
    if ":face:" not in face_id:
        raise TransactionError(
            f"mechanical: {face_id!r} is not a canonical face id "
            f"('<feature>[/<primitive>]:face:<role>')"
        )
    anchor = face_id.split(":", 1)[0]
    return anchor.split("/", 1)[0]


def extract_part_topology(
    features: list[dict[str, Any]],
    *,
    object_uuid: str = "",
    object_number: str = "",
    geometry_ref: str = "",
    cache_key: str = "",
    linear_deflection_mm: float = DEFAULT_LINEAR_DEFLECTION_MM,
    angular_deflection_rad: float = DEFAULT_ANGULAR_DEFLECTION_RAD,
    cache_material: dict[str, Any] | None = None,
) -> PartTopology:
    """Evaluate the recipe, mesh, and derive the canonical identity records.

    `cache_material` (`{"last_event_id": ..., "adapter_schema_version": ...}`)
    routes the solid through `cache.evaluate_with_cache` (the D8 freshness key)
    — the read-handler path. Without it (engine-level tests) the recipe is
    evaluated directly. Either way the SAME records come out (arc 20260609-1
    Codex2 N4 absorption: display generation reuses the evaluated-solid cache).
    """
    if cache_material is not None:
        result = cache.evaluate_with_cache_provenance(
            features,
            last_event_id=cache_material.get("last_event_id"),
            adapter_schema_version=cache_material["adapter_schema_version"],
        )
    else:
        result = geometry.evaluate_part_with_provenance(features)
    shape = result.shape
    if shape is None or shape.IsNull():
        raise TransactionError(
            "mechanical.display: Part has no evaluable geometry "
            "(no sketch/extrude features) — nothing to display"
        )

    face_map, faces, edges = correlate_shape(
        shape, features,
        produced_hints=result.produced_hints,
        ledger=result.ledger,
        linear_deflection_mm=linear_deflection_mm,
        angular_deflection_rad=angular_deflection_rad,
    )

    return PartTopology(
        shape=shape,
        face_map=face_map,
        faces=faces,
        edges=edges,
        topology_signature=compute_topology_signature(features),
        linear_deflection_mm=linear_deflection_mm,
        angular_deflection_rad=angular_deflection_rad,
        object_uuid=object_uuid,
        object_number=object_number,
        geometry_ref=geometry_ref,
        cache_key=cache_key,
    )


def correlate_shape(
    shape,
    features: list[dict[str, Any]],
    *,
    produced_hints: tuple = (),
    ledger=None,
    linear_deflection_mm: float = DEFAULT_LINEAR_DEFLECTION_MM,
    angular_deflection_rad: float = DEFAULT_ANGULAR_DEFLECTION_RAD,
):
    """Mesh + correlate a PREBUILT solid to recipe-anchored face/edge records.
    Split out of `extract_part_topology` (arc 20260621-2) so a fold can resolve a
    target edge/face on the SAME running instance it mutates (ADR/0038 D3).
    `produced_hints` carry by-construction roles for feature-produced faces
    (fillet blends, hole walls — ADR/0038 D6 + A3); they are claimed BEFORE the
    geometric plane/cylinder rule so a produced face is never re-guessed.

    Returns `(face_map, faces, edges)`.
    """
    BRepMesh_IncrementalMesh(
        shape, linear_deflection_mm, False, angular_deflection_rad, True
    )
    face_map = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, TopAbs_FACE, face_map)
    if ledger is not None:
        # ADR/0038 A4.1/A4.5 (Codex5 B4 — THE EXTRACTOR SWITCH): when the
        # fold produced a complete ledger, IT is the role authority — no
        # hint claims, no geometric re-correlation. Fail loud on any
        # disagreement between ledger and final shape (never silently fall
        # back to the geometric lane).
        role_by_face_index = {}
        for lface, role in ledger.faces:
            idx = face_map.FindIndex(lface)
            if idx == 0:
                raise TransactionError(
                    f"mechanical.display: ledger face of role {role!r} is not in "
                    f"the final shape (ADR/0038 A4.1 fail-loud)"
                )
            if idx in role_by_face_index:
                raise TransactionError(
                    f"mechanical.display: final face carries two ledger roles "
                    f"({role_by_face_index[idx]!r} and {role!r}) — A4.3 rejects"
                )
            role_by_face_index[idx] = role
        if len(role_by_face_index) != face_map.Extent():
            raise TransactionError(
                f"mechanical.display: the ledger covers {len(role_by_face_index)} "
                f"of {face_map.Extent()} final faces (ADR/0038 A4.1 fail-loud)"
            )
    else:
        recipe = _extract_recipe_geometry(features)
        claimed = _claimed_produced_roles(face_map, produced_hints)
        role_by_face_index = _correlate_faces(face_map, recipe, claimed)

    faces: list[FaceRecord] = []
    for i in range(1, face_map.Extent() + 1):
        face = TopoDS.Face_s(face_map.FindKey(i))
        stype = BRepAdaptor_Surface(face).GetType()
        # SK-C1.0 S2 Codex7 B2: EXACT classification — planarity is a safety
        # boundary (face-sketch eligibility); every non-plane/non-cylinder or
        # unknown surface is 'other', never assumed planar.
        if stype == GeomAbs_Plane:
            surface_kind = "plane"
        elif stype == GeomAbs_Cylinder:
            surface_kind = "cylinder"
        else:
            surface_kind = "other"
        faces.append(FaceRecord(
            face_id=role_by_face_index[i],
            occt_index=i,
            surface_kind=surface_kind,
            face=face,
        ))

    edges = _build_edge_records(
        shape, face_map, role_by_face_index,
        linear_deflection_mm, angular_deflection_rad,
    )
    return face_map, tuple(faces), edges


def _claimed_produced_roles(face_map, produced_hints) -> dict[int, str]:
    """Map face_map index → produced role from the evaluator's construction hints
    (ADR/0038 D6 + the A3 mandatory-claim invariant, Codex1 B2 of arc 20260622-2).
    The claim is MANDATORY, not best-effort:
      - a produced role with ZERO faces fails loud;
      - a hinted face NOT FOUND in the final face_map fails loud (never skipped);
      - multi-face roles get a DETERMINISTIC `#k` suffix from the sorted face_map
        index — never raw Modified()/Generated() iteration order.
    Geometry may later verify a claimed face's surface kind; it may never invent
    or substitute the role."""
    claimed: dict[int, str] = {}
    for hint in produced_hints:
        faces = hint.faces
        base = f"{hint.feature_id}:face:{hint.role_base}"
        if not faces:
            raise TransactionError(
                f"mechanical.display: produced role {base!r} has zero faces — the "
                f"by-construction claim failed (ADR/0038 D6/A3)"
            )
        indices: list[int] = []
        for face in faces:
            idx = face_map.FindIndex(face)
            if idx == 0:
                raise TransactionError(
                    f"mechanical.display: a produced face for {base!r} is not present "
                    f"in the final shape — the by-construction claim failed (ADR/0038 "
                    f"D6/A3); refusing to silently skip it"
                )
            indices.append(idx)
        indices.sort()  # deterministic #k ordering, stable across runs
        single = len(indices) == 1
        for k, idx in enumerate(indices):
            claimed[idx] = base if single else f"{base}#{k}"
    return claimed


def resolve_face_on_shape(
    shape,
    features: list[dict[str, Any]],
    face_role: str,
    *,
    ledger_entries=None,
):
    """Resolve a persisted face reference (ADR/0038 A1) to EXACTLY ONE live face
    on `shape`, recipe-first. Zero matches (missing role / topology change) or
    many matches (ambiguous) → fail loud (Class-1 `TransactionError`); never a
    nearest-geometry guess (ADR/0038 D4).

    A4.5 (Codex5 B4): with `ledger_entries` (the live fold ledger describing
    `shape` at this body-history position), the LEDGER is the authority — no
    geometric re-correlation runs. The correlate path remains for ledgerless
    callers (handler-side input validation on legacy/rectangle+hole shapes)."""
    if ledger_entries is not None:
        lmatches = [f for f, role in ledger_entries if role == face_role]
        if not lmatches:
            raise TransactionError(
                f"mechanical: face reference {face_role!r} resolves to NO face on the "
                f"parent topology — a missing role or a topology change. Re-pick the "
                f"face (ADR/0038 D4)."
            )
        if len(lmatches) > 1:
            raise TransactionError(
                f"mechanical: face reference {face_role!r} is AMBIGUOUS — resolves to "
                f"{len(lmatches)} faces. Refusing to guess (ADR/0038 D4)."
            )
        return lmatches[0]
    _face_map, faces, _edges = correlate_shape(shape, features)
    matches = [f for f in faces if f.face_id == face_role]
    if not matches:
        raise TransactionError(
            f"mechanical: face reference {face_role!r} resolves to NO face on the "
            f"parent topology — a missing role or a topology change. Re-pick the "
            f"face (ADR/0038 D4)."
        )
    if len(matches) > 1:
        raise TransactionError(
            f"mechanical: face reference {face_role!r} is AMBIGUOUS — resolves to "
            f"{len(matches)} faces. Refusing to guess (ADR/0038 D4)."
        )
    return matches[0].face


def resolve_edge_on_shape(
    shape,
    features: list[dict[str, Any]],
    adjacent_face_roles,
    edge_kind: str,
    *,
    ledger_entries=None,
):
    """Resolve a persisted edge reference (ADR/0038 D2/D3) to EXACTLY ONE live
    edge on `shape`, recipe-first. Zero matches (missing role / topology change)
    or many matches (ambiguous) → fail loud (Class-1 `TransactionError`); never
    a nearest-geometry guess (ADR/0038 D4).

    A4.5 (Codex5 B4): with `ledger_entries`, edges derive from the LEDGER —
    adjacency via `MapShapesAndAncestors` over `shape`, roles from the ledger
    map, kind from the same classifier as extraction. No re-correlation."""
    if ledger_entries is not None:
        matches_l = _ledger_edges_matching(
            shape, ledger_entries, tuple(sorted(adjacent_face_roles)), edge_kind
        )
        if not matches_l:
            raise TransactionError(
                f"mechanical: edge reference {tuple(sorted(adjacent_face_roles))} "
                f"(kind={edge_kind!r}) resolves to NO edge on the parent topology — "
                f"a missing role or a topology change. Re-pick the edge (ADR/0038 D4)."
            )
        if len(matches_l) > 1:
            raise TransactionError(
                f"mechanical: edge reference {tuple(sorted(adjacent_face_roles))} "
                f"(kind={edge_kind!r}) is AMBIGUOUS — resolves to {len(matches_l)} "
                f"edges. Refusing to guess (ADR/0038 D4)."
            )
        return matches_l[0]
    _face_map, _faces, edges = correlate_shape(shape, features)
    want = tuple(sorted(adjacent_face_roles))
    matches = [e for e in edges if e.adjacent_face_ids == want and e.kind == edge_kind]
    if not matches:
        raise TransactionError(
            f"mechanical: edge reference {want} (kind={edge_kind!r}) resolves to NO "
            f"edge on the parent topology — a missing role or a topology change. "
            f"Re-pick the edge (ADR/0038 D4)."
        )
    if len(matches) > 1:
        raise TransactionError(
            f"mechanical: edge reference {want} (kind={edge_kind!r}) is AMBIGUOUS — "
            f"resolves to {len(matches)} edges. Refusing to guess (ADR/0038 D4)."
        )
    return matches[0].edge


def _ledger_edges_matching(shape, ledger_entries, want_roles, want_kind):
    """A4.5: enumerate `shape`'s edges with their LEDGER-derived adjacent role
    pairs + classifier kind; return those matching the persisted reference."""
    face_roles = TopTools_IndexedMapOfShape()
    roles_by_idx: dict[int, str] = {}
    for f, role in ledger_entries:
        idx = face_roles.Add(f)
        roles_by_idx[idx] = role
    edge_face_map = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, edge_face_map)
    out = []
    for i in range(1, edge_face_map.Extent() + 1):
        edge = TopoDS.Edge_s(edge_face_map.FindKey(i))
        adj = [TopoDS.Face_s(f) for f in edge_face_map.FindFromIndex(i)]
        adj_roles = []
        ok = True
        for f in adj:
            fidx = face_roles.FindIndex(f)
            if fidx == 0:
                ok = False  # a face outside the ledger (never for a complete ledger)
                break
            adj_roles.append(roles_by_idx[fidx])
        if not ok or len(adj) != 2:
            continue
        if tuple(sorted(adj_roles)) != want_roles:
            continue
        if _edge_kind(edge, adj) != want_kind:
            continue
        out.append(edge)
    return out


# ---------------------------------------------------------------------------
# Topology signature (ADR/0035 D3) — recipe-derived, value-independent
# ---------------------------------------------------------------------------


def compute_topology_signature(features: list[dict[str, Any]]) -> str:
    """A deterministic hash over the **topology skeleton** — feature types +
    sketch primitive (id, type) lists — EXCLUDING parameter values (depth,
    dimensions, positions, direction). Stable across parameter edits; changes
    when a feature or primitive is added/removed. NOT a stored counter."""
    # ADR/0038 A4.6 (Codex6 B1): the signature NORMALIZES its input at the
    # public boundary — a Kahn order over the dependency graph with stable-id
    # tie-break, so sidecar array position is non-semantic HERE too and no
    # caller needs a pre-normalization ritual. Append-authored recipes are
    # already in this order (byte-identical signatures; golden-tested).
    from . import body_history as _body_history
    # ADR/0044 A2.4 (Gate F2b): STRUCTURAL v2 validation only — the
    # signature is pure/value-independent and must never run the native
    # solver. Non-sketch/malformed 0.2.x refuse; a valid v2 sketch gets a
    # skeleton entry below.
    from .sketch_v2 import validate_v2_records as _validate_v2

    _validate_v2(features)

    features = _body_history.normalize_feature_order(list(features))
    skeleton: list[dict[str, Any]] = []
    for f in features:
        ftype = f.get("feature_type")
        entry: dict[str, Any] = {"feature": ftype}
        _asv = f.get("adapter_schema_version")
        if ftype == "sketch" and isinstance(_asv, str) and _asv.startswith("0.2."):
            # Gate F2b: a v2 CONSTRAINED sketch is construction-only in this
            # slice — it contributes NO 3D topology. Its skeleton entry is
            # the admitted shape + plane orientation (value-independent;
            # nominals/weak magnitudes are values and stay out); presence/
            # removal changes the signature like any feature.
            from .sketch_v2 import decode_v2_sketch as _decode_v2

            decoded = _decode_v2(f)
            entry["sketch_model"] = 2
            entry["v2_shape"] = decoded["shape"]
            payload = f.get("adapter_payload", {})
            if "placement" in payload:
                # ADR/0044 A3.4: the COMPLETE placement record is topology
                # skeleton — changing support/orientation_ref/orientation/
                # normal_side changes world placement and must invalidate
                # held selection + derived display state.
                pl = payload["placement"]
                entry["placement"] = {
                    "support": dict(pl["support"]),
                    "orientation_ref": dict(pl["orientation_ref"]),
                    "orientation": pl["orientation"],
                    "normal_side": pl["normal_side"],
                }
            else:
                plane_sk = plane_skeleton(f)
                if plane_sk is not None:
                    entry["plane"] = plane_sk
            skeleton.append(entry)
            continue
        if ftype == "sketch":
            all_prims = f.get("adapter_payload", {}).get("primitives", [])
            # SK-C0 B4: only TOPOLOGY-CONTRIBUTING primitives enter the 3D
            # skeleton (the classifier's outer+hole set). Editing/adding/removing
            # a pure construction guide changes recipe/vault identity but NEVER
            # the 3D signature — canonical selections and parent-prefix
            # references survive. Toggling a primitive into/out of profile
            # participation DOES change the signature (the set changes, and the
            # BREP with it). Legacy no-construction recipes: contributing == the
            # full list → signatures byte-identical (golden-tested).
            cls = profile_classify.classify_sketch(all_prims)
            contributing = set(cls.topology_contributing)
            prims = [p for i, p in enumerate(all_prims) if i in contributing]
            entry["primitives"] = sorted(
                (p.get("id", ""), p.get("type")) for p in prims
            )
            # arc 20260711-11 slice E (Codex4 D-E2): a contour's ordered segment
            # (id, kind) list is SKELETON — an insert/delete or line→arc changes
            # topology; the vertex COORDINATES stay values (excluded). Added under
            # a separate key ONLY when a contour is present, so existing
            # rectangle/circle signatures are byte-identical (no migration).
            contour_segments = {
                p.get("id", ""): [
                    (s.get("id", ""), s.get("kind")) for s in p.get("segments", [])
                ]
                for p in prims
                if p.get("type") == "contour"
            }
            if contour_segments:
                entry["contour_segments"] = {
                    k: contour_segments[k] for k in sorted(contour_segments)
                }
            # EP2 (Codex1 B3 → Codex3 B2): the plane ORIENTATION is skeleton —
            # derived through the SAME exact validator every consumer uses
            # (`effective_plane_frame`), so a malformed/reserved/extra-key
            # record fails Class-1 HERE too and can never mint an authoritative
            # signature that evaluation would reject. Included ONLY when
            # non-default, so absent-plane and explicit principal-xy recipes
            # keep byte-identical signatures. The direction SIGN stays out (an
            # orientation value, not a role-set change).
            plane_sk = plane_skeleton(f)
            if plane_sk is not None:
                entry["plane"] = plane_sk
        elif ftype == "extrude":
            # Codex3 B2: the signature consumer enforces the exact-sketch
            # discipline too — a missing/mismatched/duplicate consumed sketch
            # fails Class-1 here, never minting a signature evaluation would
            # reject. Adds NOTHING to the skeleton bytes (the dependency is
            # validated, not encoded — valid-recipe signatures are unchanged).
            resolve_consumed_sketch(features, f)
            # ADR/0038 A4 (arc 20260717-2): the OPERATION is structural — an
            # add and a cut over the same profile are different topologies.
            # Encoded ONLY when it differs from the legacy default ("add"),
            # so every legacy/add signature stays byte-identical (B2 parity).
            operation = (f.get("adapter_payload") or {}).get("operation", "add")
            if operation != "add":
                entry["operation"] = operation
        elif ftype in ("fillet", "chamfer"):
            # An edge-referencing feature IS a topology change; retargeting it
            # changes topology too (ADR/0038 D4) — so the target ANCHOR is part of
            # the skeleton, but the radius/distance VALUE is not (ADR/0038 A2).
            tgt = (f.get("adapter_payload") or {}).get("target_edge", {})
            entry["target"] = [
                sorted(tgt.get("adjacent_face_roles", [])),
                tgt.get("edge_kind"),
            ]
        elif ftype == "hole":
            # ADR/0038 A2 (Codex1 B1, arc 20260622-2): the target_face ROLE is
            # skeleton (retargeting changes topology); the diameter/centre VALUES
            # are NOT — moving/resizing a hole within the same face is a parameter
            # edit, exactly like a sketch circle's position/radius.
            tgt = (f.get("adapter_payload") or {}).get("target_face", {})
            entry["target"] = tgt.get("face_role")
        elif ftype == "revolve":
            # Codex1 B1 (arc 20260622-4): the axis AND the derived radial mode
            # (tube vs solid) are skeleton — tube↔solid adds/removes the
            # `inner_wall` role, a topology change, not a value edit. The radii
            # (the profile dimensions, already excluded with every sketch dim)
            # stay out within a mode.
            axis = (f.get("adapter_payload") or {}).get("axis")
            # EP2 (Codex1 B2 → Codex3 B2): resolver violations PROPAGATE — the
            # signature consumer provides the same Class-1 exact-sketch
            # discipline as every other consumer. Only the radial-mode
            # computation keeps the legacy `mode="invalid"` (a crossing-axis
            # PROFILE is a value-domain rejection, not a resolution failure).
            sk = resolve_consumed_sketch(features, f)
            prims = sk.get("adapter_payload", {}).get("primitives", [])
            rect = next((p for p in prims if p.get("type") == "rectangle"), None)
            try:
                mode = geometry.revolve_radial_mode(rect, axis) if rect is not None else None
            except TransactionError:
                mode = "invalid"  # a crossing-axis profile; the evaluator rejects it separately
            entry["axis"] = axis
            entry["mode"] = mode
        skeleton.append(entry)
    raw = json.dumps(skeleton, sort_keys=True).encode("utf-8")
    return "topo_" + hashlib.sha256(raw).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Recipe geometry extraction (the stable anchor source)
# ---------------------------------------------------------------------------


def _extract_recipe_geometry(features: list[dict[str, Any]]) -> dict[str, Any]:
    """Pull the stable, recipe-derived anchors used for role correlation:
    the CONSUMED sketch (EP2, Codex1 B2 — resolved by the base feature's
    `sketch_feature_id`, never "the last sketch") + its plane frame, the
    profile primitive ids & geometry, and the base feature id + direction."""
    extrude = _last(features, "extrude")
    revolve = _last(features, "revolve")
    base = extrude if extrude is not None else revolve
    if base is not None:
        sketch = resolve_consumed_sketch(features, base)
    else:
        sketch = _last(features, "sketch")
        if sketch is None:
            raise TransactionError(
                "mechanical.display: recipe has no sketch feature"
            )
    frame = effective_plane_frame(sketch)
    sketch_id = sketch["id"]
    prims = sketch.get("adapter_payload", {}).get("primitives", [])
    # SK-C0 B3: THE classifier is the single interpretation authority here too —
    # construction guides never reach correlation; circle-as-outer dispatches.
    cls = profile_classify.classify_sketch(prims)
    rectangle = prims[cls.outer_index] if cls.outer_kind == "rectangle" else None
    contour = prims[cls.outer_index] if cls.outer_kind == "contour" else None
    outer_circle = prims[cls.outer_index] if cls.outer_kind == "circle" else None
    circle = prims[cls.hole_index] if cls.hole_index is not None else None
    if cls.outer_kind == "none":
        raise TransactionError(
            "mechanical.display: sketch has no profile geometry (construction-only)"
        )

    # Revolve base (arc 20260622-4): a different topology family than the extrude
    # box, so the recipe carries its base kind and the correlation dispatches.
    if revolve is not None:
        if frame.orientation != "xy":
            raise TransactionError(
                "mechanical.display: v1 revolve requires the consumed sketch on "
                f"the principal xy plane; it is on {frame.orientation!r}"
            )
        if rectangle is None:
            raise TransactionError(
                "mechanical.display: revolve v1 requires a rectangle profile "
                "(a contour revolve is unsupported)"
            )
        axis = (revolve.get("adapter_payload") or {}).get("axis")
        return {
            "base": "revolve",
            "sketch_id": sketch_id,
            "revolve_id": revolve["id"],
            "rectangle": rectangle,
            "axis": axis,
            "mode": geometry.revolve_radial_mode(rectangle, axis),
            "frame": frame,
        }

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
    common = {
        "base": "extrude",
        "sketch_id": sketch_id,
        "extrude_id": extrude_id,
        "direction": direction,
        "depth": depth,
        # EP2: the sign normalizes normal±/legacy-z± against THIS frame — the
        # same rule the evaluator applies (one implementation, recipe.py).
        "sign": extrude_sign(direction, frame, op_kind="mechanical.display")
        if extrude is not None
        else 1.0,
        "frame": frame,
    }
    # arc 20260711-11 slice E: a contour outer profile is a different (N-side)
    # topology family; the recipe carries the kind so correlation dispatches.
    if contour is not None:
        return {**common, "outer_kind": "contour", "contour": contour, "circle": None}
    # SK-C0 D-C2: circle-as-outer — a cylinder family. Correlation dispatches
    # from THIS classification; the outer wall never enters the hole_wall path.
    if outer_circle is not None:
        return {**common, "outer_kind": "circle_outer", "outer_circle": outer_circle, "circle": None}
    return {**common, "outer_kind": "rectangle", "rectangle": rectangle, "circle": circle}


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


def _correlate_faces(
    face_map, recipe: dict[str, Any], claimed: dict[int, str] | None = None
) -> dict[int, str]:
    """Assign every OCCT face a recipe-anchored role id. Faces `claimed` by
    construction (fillet blends, ADR/0038 D6) take their hinted role and skip
    the geometric rule — so a blend cylinder is never mislabeled as a hole wall.
    Raises if an unclaimed face cannot be mapped (fail-loud: a correlation gap is
    a real bug, not a silent fallback to traversal order)."""
    claimed = claimed or {}
    if recipe.get("base") == "revolve":
        return _correlate_revolve_faces(face_map, recipe, claimed)
    if recipe.get("outer_kind") == "contour":
        return _correlate_contour_faces(face_map, recipe, claimed)
    if recipe.get("outer_kind") == "circle_outer":
        return _correlate_circle_outer_faces(face_map, recipe, claimed)
    sketch_id = recipe["sketch_id"]
    extrude_id = recipe["extrude_id"]
    rect = recipe["rectangle"]
    circle = recipe["circle"]
    frame: PlaneFrame = recipe["frame"]  # EP2 — the consumed sketch's frame
    # Codex2 B1 (arc 20260609-1): the display id source MUST be a real
    # engine-minted anchor, never a placeholder — fail loud before any id mints.
    rect_skp = require_skp_id(rect, "rectangle")
    circle_skp = require_skp_id(circle, "circle") if circle else None
    feat_prefix = extrude_id if extrude_id is not None else sketch_id
    rect_edges = _rect_edges(rect)

    roles: dict[int, str] = {}
    used_wall_suffixes: set[str] = set()
    for i in range(1, face_map.Extent() + 1):
        if i in claimed:
            roles[i] = claimed[i]  # by-construction blend role (ADR/0038 D6)
            continue
        face = TopoDS.Face_s(face_map.FindKey(i))
        surf = BRepAdaptor_Surface(face)
        stype = surf.GetType()
        centroid, normal = _face_centroid_normal(face)

        if stype == GeomAbs_Cylinder:
            # Codex2 B2: an UNCLAIMED cylinder is a hole wall ONLY if the recipe
            # actually has a circle primitive. With no circle, the only cylinder
            # source is a fillet blend — which must have been CLAIMED by
            # construction (ADR/0038 D6) above. Reaching here means a missed
            # blend hint; fail loud rather than mint a placeholder
            # `…/None:face:hole_wall` anchor (ADR/0035 no-placeholder).
            if circle_skp is None:
                raise TransactionError(
                    f"mechanical.display: face {i} is an unclaimed cylinder but the "
                    f"recipe has no circle primitive — a produced face (fillet blend / "
                    f"hole wall) must be claimed by construction (ADR/0038 D6/A3). "
                    f"Refusing to mint a placeholder hole_wall role (ADR/0035 no-placeholder)."
                )
            roles[i] = f"{feat_prefix}/{circle_skp}:face:hole_wall"
            continue

        if stype == GeomAbs_Plane and abs(_dot3(normal, frame.normal)) >= _AXIS_DOT:
            # A cap: base (the sketch plane, normal-coordinate ≈ 0) vs top (the
            # swept end — either sign of the sweep).
            if abs(frame.normal_coord(centroid)) <= 1e-6:
                roles[i] = f"{feat_prefix}:face:cap_base"
            else:
                roles[i] = f"{feat_prefix}:face:cap_top"
            continue

        if stype == GeomAbs_Plane:
            # A side wall — correlate to the originating sketch edge by the
            # closest rectangle-edge midpoint IN THE SKETCH PLANE (u, v).
            suffix = _nearest_wall(frame.project_uv(centroid), rect_edges)
            if suffix is None or suffix in used_wall_suffixes:
                raise TransactionError(
                    f"mechanical.display: could not uniquely "
                    f"correlate side face {i} to a rectangle edge "
                    f"(centroid={centroid}); recipe/topology mismatch"
                )
            used_wall_suffixes.add(suffix)
            roles[i] = f"{feat_prefix}/{rect_skp}:face:wall_{suffix}"
            continue

        raise TransactionError(
            f"mechanical.display: unexpected surface type "
            f"{stype} on face {i}; v0.0.1 supports plane + cylinder only"
        )
    return roles


def _dot3(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _correlate_revolve_faces(
    face_map, recipe: dict[str, Any], claimed: dict[int, str]
) -> dict[int, str]:
    """Recipe-anchored roles for a revolve solid (arc 20260622-4). The recipe's
    radial mode + axis enumerate the expected roles; geometry ORDERS the faces
    into them — `outer_wall`/`inner_wall` by absolute radius, `cap_lo`/`cap_hi`
    by axis coordinate (Codex1 Q2). v1 surfaces are plane + cylinder only; any
    other surface, a cap whose normal is not the axis, or a face-count mismatch
    against the mode fails loud (the same no-silent-fallback discipline as the
    box correlation)."""
    feat = recipe["revolve_id"]
    axis = recipe["axis"]
    mode = recipe["mode"]
    axis_idx = {"x": 0, "y": 1}[axis]

    roles: dict[int, str] = {}
    cylinders: list[tuple[int, float]] = []   # (face index, radius)
    caps: list[tuple[int, float]] = []        # (face index, axis coordinate)
    for i in range(1, face_map.Extent() + 1):
        if i in claimed:  # forward-compat: a stacked produced face (none in v1)
            roles[i] = claimed[i]
            continue
        face = TopoDS.Face_s(face_map.FindKey(i))
        surf = BRepAdaptor_Surface(face)
        stype = surf.GetType()
        if stype == GeomAbs_Cylinder:
            cylinders.append((i, surf.Cylinder().Radius()))
            continue
        if stype == GeomAbs_Plane:
            n = surf.Plane().Position().Direction()
            if abs((n.X(), n.Y(), n.Z())[axis_idx]) < _AXIS_DOT:
                raise TransactionError(
                    f"mechanical.display: revolve face {i} is a plane whose normal is "
                    f"not the {axis}-axis (an unexpected revolve cap); recipe/topology mismatch"
                )
            loc = surf.Plane().Position().Location()
            caps.append((i, (loc.X(), loc.Y(), loc.Z())[axis_idx]))
            continue
        raise TransactionError(
            f"mechanical.display: revolve face {i} has unexpected surface type "
            f"{stype}; a v1 (rectangle-profile) revolve is plane + cylinder only "
            f"(cones/tori are a richer-profile v2)"
        )

    expected_cyl = 1 if mode == "solid" else 2
    if len(cylinders) != expected_cyl or len(caps) != 2:
        raise TransactionError(
            f"mechanical.display: revolve face-count mismatch for {mode!r} mode — "
            f"expected {expected_cyl} cylinder(s) + 2 cap(s), got {len(cylinders)} "
            f"cylinder(s) + {len(caps)} cap(s); recipe/topology mismatch"
        )

    cylinders.sort(key=lambda c: c[1])  # ascending radius
    if mode == "solid":
        roles[cylinders[0][0]] = f"{feat}:face:outer_wall"
    else:
        roles[cylinders[0][0]] = f"{feat}:face:inner_wall"   # smaller radius
        roles[cylinders[1][0]] = f"{feat}:face:outer_wall"   # larger radius
    caps.sort(key=lambda c: c[1])  # ascending axis coordinate
    roles[caps[0][0]] = f"{feat}:face:cap_lo"
    roles[caps[1][0]] = f"{feat}:face:cap_hi"
    return roles


def _correlate_contour_faces(
    face_map, recipe: dict[str, Any], claimed: dict[int, str]
) -> dict[int, str]:
    """Assign roles for an extruded CLOSED-RING contour (arc 20260711-11 slice E;
    Codex4 D-E2). Caps by axis-parallel normal (`cap_base` at the sketch plane
    z≈0, `cap_top` at the swept end). Each side wall is anchored to its
    originating contour SEGMENT id — so a vertex move (a value edit) preserves
    every wall role, while a segment insert/delete (a skeleton change) changes
    them. Fail-loud on an unmatched/duplicated wall (no positional fallback)."""
    contour = recipe["contour"]
    frame: PlaneFrame = recipe["frame"]  # EP2 — the consumed sketch's frame
    feat_prefix = recipe["extrude_id"] if recipe.get("extrude_id") is not None else recipe["sketch_id"]
    line_mids, arc_segs = _contour_segment_geometry(contour)
    roles: dict[int, str] = {}
    used_segments: set[str] = set()
    # SK-C0 B2: by-construction wall claims (Generated(edge) hints from the
    # evaluator) are AUTHORITY — count their segments toward the bijection.
    wall_re = re.compile(re.escape(feat_prefix) + r"/([^:]+):face:wall$")
    for role in claimed.values():
        m = wall_re.search(role)
        if m:
            used_segments.add(m.group(1))
    for i in range(1, face_map.Extent() + 1):
        if i in claimed:
            roles[i] = claimed[i]
            continue
        face = TopoDS.Face_s(face_map.FindKey(i))
        stype = BRepAdaptor_Surface(face).GetType()
        centroid, normal = _face_centroid_normal(face)
        if stype == GeomAbs_Plane and abs(_dot3(normal, frame.normal)) >= _AXIS_DOT:
            roles[i] = (
                f"{feat_prefix}:face:cap_base"
                if abs(frame.normal_coord(centroid)) <= 1e-6
                else f"{feat_prefix}:face:cap_top"
            )
            continue
        if stype == GeomAbs_Plane:
            seg_id = _nearest_segment(frame.project_uv(centroid), line_mids)
            if seg_id is None or seg_id in used_segments:
                raise TransactionError(
                    f"mechanical.display: could not uniquely correlate side face {i} "
                    f"to a contour segment (centroid={centroid}); recipe/topology mismatch"
                )
            used_segments.add(seg_id)
            roles[i] = f"{feat_prefix}/{seg_id}:face:wall"
            continue
        if stype == GeomAbs_Cylinder:
            # SK-C0 B2 EXPLICIT FALLBACK (hint-less re-correlation lane only):
            # the injective geometric key — cylinder axis point + radius +
            # the wall centroid within the segment's angular span. Same-support
            # split arcs stay distinguishable via the span; exactly-one-or-loud.
            seg_id = _match_arc_wall(face, frame, arc_segs, used_segments)
            if seg_id is None:
                raise TransactionError(
                    f"mechanical.display: could not uniquely correlate cylindrical "
                    f"face {i} to an arc contour segment; recipe/topology mismatch"
                )
            used_segments.add(seg_id)
            roles[i] = f"{feat_prefix}/{seg_id}:face:wall"
            continue
        raise TransactionError(
            f"mechanical.display: unexpected surface type {stype} on face {i}; "
            f"a contour extrude produces planar and cylindrical faces only"
        )
    # Codex5 B1: the segment↔wall map must be a bijection — every declared segment
    # produces exactly one wall. The in-loop guard rejects a duplicate; this guards
    # the OTHER direction (a missing wall, e.g. a coplanar merge emitting fewer side
    # faces than segments), fail loud rather than returning silently-incomplete
    # identity (ADR/0035 no-placeholder / no-silent-gap).
    declared = {sid for sid, _, _ in line_mids} | {sid for sid, _ in arc_segs}
    if used_segments != declared:
        missing = sorted(declared - used_segments)
        raise TransactionError(
            f"mechanical.display: contour correlation did not map every segment to its "
            f"own wall (no wall for {missing}); a coplanar merge or face-count mismatch "
            f"broke one-segment-one-wall identity"
        )
    return roles


def _correlate_circle_outer_faces(
    face_map, recipe: dict[str, Any], claimed: dict[int, str]
) -> dict[int, str]:
    """Assign roles for a circle-as-outer-profile extrude (SK-C0 D-C2): the
    lateral wall is `<prefix>/<circle-skp>:face:outer_wall` (normally claimed by
    construction; verified here on the fallback lane), caps by normal coordinate.
    Dispatch comes from CLASSIFICATION — this wall never enters the hole_wall path."""
    circle = recipe["outer_circle"]
    frame: PlaneFrame = recipe["frame"]
    feat_prefix = recipe["extrude_id"] if recipe.get("extrude_id") is not None else recipe["sketch_id"]
    circle_skp = require_skp_id(circle, "circle")
    roles: dict[int, str] = {}
    wall_seen = False
    for i in range(1, face_map.Extent() + 1):
        if i in claimed:
            roles[i] = claimed[i]
            wall_seen = wall_seen or claimed[i].endswith(":face:outer_wall")
            continue
        face = TopoDS.Face_s(face_map.FindKey(i))
        stype = BRepAdaptor_Surface(face).GetType()
        centroid, normal = _face_centroid_normal(face)
        if stype == GeomAbs_Plane and abs(_dot3(normal, frame.normal)) >= _AXIS_DOT:
            roles[i] = (
                f"{feat_prefix}:face:cap_base"
                if abs(frame.normal_coord(centroid)) <= 1e-6
                else f"{feat_prefix}:face:cap_top"
            )
            continue
        if stype == GeomAbs_Cylinder and not wall_seen:
            r = BRepAdaptor_Surface(face).Cylinder().Radius()
            if abs(r - float(circle["radius_mm"])) > 1e-6:
                raise TransactionError(
                    f"mechanical.display: cylinder face {i} radius {r} does not "
                    f"verify against the circle outer profile"
                )
            roles[i] = f"{feat_prefix}/{circle_skp}:face:outer_wall"
            wall_seen = True
            continue
        raise TransactionError(
            f"mechanical.display: unexpected face {i} (surface type {stype}) on a "
            f"circle-outer extrude (one wall + two caps expected)"
        )
    if not wall_seen:
        raise TransactionError(
            "mechanical.display: circle-outer correlation found no lateral wall"
        )
    return roles


def _contour_segment_geometry(contour: dict[str, Any]):
    """Split the contour's segments for correlation: LINE segments as
    (id, chord-midpoint-x, chord-midpoint-y) for the planar matcher; ARC
    segments as (id, ArcGeometry) for the cylindrical matcher. Fail loud on a
    missing engine-minted anchor (no placeholder)."""
    line_mids: list[tuple[str, float, float]] = []
    arc_segs: list[tuple[str, Any]] = []
    for seg in contour.get("segments", []):
        sid = seg.get("id")
        if not isinstance(sid, str) or not sid:
            raise TransactionError(
                "mechanical.display: contour segment lacks an engine-minted id — a "
                "corrupt/pre-slice-E payload cannot anchor stable wall identity "
                "(failing loud rather than minting a placeholder, ADR/0035)"
            )
        if seg.get("kind") == "arc":
            arc_segs.append((sid, arc_geometry(
                float(seg["x1_mm"]), float(seg["y1_mm"]),
                float(seg["x2_mm"]), float(seg["y2_mm"]), float(seg["bulge"]),
            )))
        else:
            mx = 0.5 * (float(seg["x1_mm"]) + float(seg["x2_mm"]))
            my = 0.5 * (float(seg["y1_mm"]) + float(seg["y2_mm"]))
            line_mids.append((sid, mx, my))
    return line_mids, arc_segs


def _match_arc_wall(face, frame, arc_segs, used_segments) -> str | None:
    """The EXPLICIT injective fallback key (SK-C0 B2, hint-less lane): the
    wall's cylinder must match a declared arc segment's center+radius, and the
    wall centroid (projected to sketch UV) must fall INSIDE that segment's
    angular span — same-support split arcs stay distinct. Exactly one match or
    None (the caller fails loud)."""
    surf = BRepAdaptor_Surface(face)
    cyl = surf.Cylinder()
    r = cyl.Radius()
    loc = cyl.Axis().Location()
    cu, cv = frame.project_uv((loc.X(), loc.Y(), loc.Z()))
    centroid, _ = _face_centroid_normal(face)
    pu, pv = frame.project_uv(centroid)
    matches = []
    for sid, g in arc_segs:
        if sid in used_segments:
            continue
        if abs(r - g.radius) > 1e-6:
            continue
        if math.hypot(cu - g.center[0], cv - g.center[1]) > 1e-6:
            continue
        if point_on_arc_span(g, pu, pv, 1e-6):
            matches.append(sid)
    return matches[0] if len(matches) == 1 else None


def _nearest_segment(centroid_uv, seg_mids) -> str | None:
    """Nearest contour-segment midpoint in the SKETCH PLANE (u, v)."""
    best = None
    best_d = None
    for sid, mx, my in seg_mids:
        d = math.hypot(centroid_uv[0] - mx, centroid_uv[1] - my)
        if best_d is None or d < best_d:
            best_d = d
            best = sid
    return best


def _nearest_wall(centroid_uv, rect_edges) -> str | None:
    """Nearest rectangle-edge midpoint in the SKETCH PLANE (u, v). The wall
    suffixes (`x_min`… — historically named) are sketch-LOCAL edge anchors,
    not global-axis claims (EP2)."""
    best = None
    best_d = None
    for suffix, mx, my in rect_edges:
        d = math.hypot(centroid_uv[0] - mx, centroid_uv[1] - my)
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
            "mechanical.display: face has no triangulation"
        )
    sx = sy = sz = 0.0
    n = tri.NbNodes()
    for k in range(1, n + 1):
        p = tri.Node(k).Transformed(trsf)
        sx += p.X(); sy += p.Y(); sz += p.Z()
    centroid = (sx / n, sy / n, sz / n)
    normal = surface_normal(face, tri)
    return centroid, normal


def surface_normal(face, tri) -> tuple[float, float, float]:
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
# Edge records — id + kind + handle + model-space curve, derived ONCE (B1)
# ---------------------------------------------------------------------------


def _build_edge_records(
    shape, face_map, role_by_index,
    linear_deflection, angular_deflection,
) -> tuple[EdgeRecord, ...]:
    edge_faces = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, edge_faces)
    out: list[EdgeRecord] = []
    role_pair_seen: dict[str, int] = {}
    for i in range(1, edge_faces.Extent() + 1):
        edge = TopoDS.Edge_s(edge_faces.FindKey(i))
        adj = [TopoDS.Face_s(f) for f in edge_faces.FindFromIndex(i)]
        adj_roles = [role_by_index[face_map.FindIndex(f)] for f in adj]
        kind = _edge_kind(edge, adj)
        edge_id = _edge_id(adj_roles, kind, role_pair_seen)
        polyline = discretize_edge(edge, linear_deflection, angular_deflection)
        out.append(EdgeRecord(
            edge_id=edge_id,
            kind=kind,
            occt_index=i,
            edge=edge,
            adjacent_face_ids=tuple(sorted(set(adj_roles))),
            polyline_mm=tuple(polyline),
        ))
    return tuple(out)


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


def discretize_edge(edge, linear_deflection, angular_deflection) -> list[float]:
    curve = BRepAdaptor_Curve(edge)
    disc = GCPnts_TangentialDeflection(curve, linear_deflection, angular_deflection)
    pts: list[float] = []
    for k in range(1, disc.NbPoints() + 1):
        p = disc.Value(k)
        pts.extend((p.X(), p.Y(), p.Z()))
    return pts


def _last(features: list[dict[str, Any]], ftype: str) -> dict[str, Any] | None:
    chosen = None
    for f in features:
        if f.get("feature_type") == ftype:
            chosen = f
    return chosen
