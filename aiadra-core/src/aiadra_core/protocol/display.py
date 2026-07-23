"""The **Display Representation contract** — the versioned, read-only data
contract between a geometry producer (a Native Engine, or a future import
parser) and the AIADRA Studio viewport. ADR/0035 (arc 20260609-1) pinned v1.0;
arc 20260609-2 adds the view-dependent HLR payload → **contract v1.1**
(additive — the foundation's reserved `view_dependent` slot is populated, a
v1.0 package with a null slot stays valid, a v1.0 package with a POPULATED
slot stays rejected).

Kernel-neutral pure data — `aiadra-core` defines the *shape*; it imports no
geometry kernel. A Native Engine produces the payload (OCCT lives in the
engine, e.g. `aiadra-mechanical`); `display_representation()` /
`display_hlr()` in `aiadra_core.protocol` validate the engine's dict into
these frozen dataclasses. Studio mirrors this shape as a TypeScript type.

Design notes (arcs 20260609-1 + 20260609-2 Codex reviews):
- **`topology_signature`, not a counter** (20260609-1 B2): invalidation is
  keyed on a deterministic signature over the topology-affecting recipe
  skeleton. Parameter edits preserve it; add/remove changes it.
- **`view_dependent` (20260609-2)** holds a `ViewDependentPayload`: per-view
  classified HLR segments in an explicit, contract-complete 2D view frame
  (B2 — normalized `direction`/`up`/`right`, right-handed, mm units; the
  mapping is `u = (p - origin)·right`, `v = (p - origin)·up`; `direction` is
  the LOOK direction, eye → scene).
- **`identity_echo` (B3)** makes a standalone HLR overlay attachable only to
  the display package it was computed against — object/package identity, not
  just cache material. Inline payloads are cross-checked against the
  enclosing package identity at validation time.
- **Outline firewall (B5)**: silhouette segments carry
  `{kind: "outline", face_id, index}` — face-anchored, per-view ephemeral;
  never a display id, never pickable, never in `selection.names`.
- **Sliver accounting (B4)**: producers may drop sub-threshold uncorrelatable
  segments; the count surfaces in `counters.discarded_tolerance_segments` —
  never a silent discard.
"""
from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field
from typing import Any

# SK-C1.0 S2 (arc 20260716-2): contract v1.2 — additive optional
# `surface_kind` per face + top-level `sketch_frames` (the resolved frames of
# face-bound sketches, identity-bound by living INSIDE the package). The FULL
# compatibility matrix survives (Codex6 S2 boundary): display accepts
# 1.0/1.1/1.2; standalone HLR attaches for the HLR-CAPABLE set {1.1, 1.2}
# only (1.0 keeps its populated-slot rejection verbatim).
# v1.3 (Gate F2b, arc 20260717-2): additive `v2_construction` — the SOLVED
# construction geometry of v2 constrained sketches (the A2.9 read-lifecycle
# output; derived display data, never Truth). Same declared-shape amendment
# discipline as v1.1→v1.2: a pre-1.3 package carrying the field is a
# producer error, never an additive mutation.
DISPLAY_REPRESENTATION_VERSION = "1.3"
ACCEPTED_VERSIONS = ("1.0", "1.1", "1.2", "1.3")
HLR_CAPABLE_VERSIONS = ("1.1", "1.2", "1.3")

# sketch-frame numeric discipline (Codex2 B3.1.5)
_FRAME_TOL = 1e-9

_UNIT_TOL = 1e-6


class DisplayContractError(ValueError):
    """A producer returned a malformed / incompatible Display Representation.
    Fail-loud per Manifesto P5 — the viewport must never render guesswork."""


@dataclass(frozen=True)
class DisplayIdentity:
    object_uuid: str
    object_number: str
    geometry_ref: str          # the recipe-hash vault_ref (authoring identity)
    cache_key: str             # the engine's D8 freshness key for this package
    topology_signature: str    # deterministic; stable across parameter edits


@dataclass(frozen=True)
class FaceBuffer:
    face_id: str
    positions: tuple[float, ...]   # flat (x,y,z) triples, this face's nodes
    normals: tuple[float, ...]     # flat (x,y,z) triples, true surface normals
    triangles: tuple[int, ...]     # flat (i,j,k) index triples into this face's nodes
    appearance_slot: str = "default"
    # v1.2 (SK-C1.0 S2): engine-classified surface kind — 'plane' | 'other'.
    # OPTIONAL/None on pre-1.2 payloads; consumers treat absent as unknown and
    # FAIL CLOSED (no planar-pick eligibility), never guess.
    surface_kind: str | None = None


@dataclass(frozen=True)
class EdgePolyline:
    edge_id: str
    kind: str                      # sharp | tangent | seam | boundary
    polyline: tuple[float, ...]    # flat (x,y,z), true curve discretization
    faces: tuple[str, ...]         # adjacent face_ids (≤2)


@dataclass(frozen=True)
class VertexMarker:
    vertex_id: str
    position: tuple[float, float, float]


@dataclass(frozen=True)
class RenderPayload:
    faces: tuple[FaceBuffer, ...]
    edges: tuple[EdgePolyline, ...]
    vertices: tuple[VertexMarker, ...]
    bbox_min: tuple[float, float, float]
    bbox_max: tuple[float, float, float]
    linear_deflection_mm: float
    angular_deflection_rad: float
    buffer_encoding: str = "json_arrays"


@dataclass(frozen=True)
class SelectionPayload:
    id_space: str                  # "canonical" (Workspace) | "ephemeral" (imports)
    pickable_kinds: tuple[str, ...]
    names: dict[str, str] = field(default_factory=dict)  # display_id -> human name


@dataclass(frozen=True)
class DisplayInvalidation:
    stale_when: tuple[str, ...]
    selection_invalid_when: str


@dataclass(frozen=True)
class DisplayCounters:
    face_count: int
    edge_count_by_kind: dict[str, int]
    triangle_count: int
    vertex_count: int
    generation_ms: float | None = None
    package_bytes: int | None = None


# ---------------------------------------------------------------------------
# View-dependent HLR payload (contract v1.1; arc 20260609-2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HlrProjector:
    """The contract-complete view frame (Codex1 B2). `direction` is the unit
    LOOK direction (eye → scene); `up`/`right` are the orthonormalized screen
    axes; (right, up, -direction) is right-handed. View-plane mapping:
    `u = (p - origin) · right`, `v = (p - origin) · up`, in `units`."""

    projection: str                                  # "orthographic" (v1.1)
    origin: tuple[float, float, float]
    direction: tuple[float, float, float]
    up: tuple[float, float, float]
    right: tuple[float, float, float]
    units: str = "mm"


@dataclass(frozen=True)
class HlrSegmentSource:
    """Strict union (Codex1 B5): `model_edge` carries ONLY `edge_id` (a stable
    canonical display id); `outline` carries ONLY `face_id` + per-view ordinal
    `index` (ephemeral — silhouettes move with the camera and are never
    pickable or nameable)."""

    kind: str                      # "model_edge" | "outline"
    edge_id: str | None = None
    face_id: str | None = None
    index: int | None = None


@dataclass(frozen=True)
class HlrSegment:
    polyline_2d: tuple[float, ...]  # flat (u,v) pairs in the view plane
    visibility: str                 # "visible" | "hidden"
    edge_class: str                 # sharp | smooth | sewn | outline (OCCT HLR vocab)
    source: HlrSegmentSource


@dataclass(frozen=True)
class HlrViewCounters:
    visible_segments: int
    hidden_segments: int
    outline_segments: int
    discarded_tolerance_segments: int  # B4 — dropped slivers are COUNTED
    generation_ms: float | None = None


@dataclass(frozen=True)
class HlrView:
    view_id: str
    projector: HlrProjector
    algorithm: str                  # "exact" | "poly"
    coordinate_space: str           # "view_plane_2d" (v1.1)
    correlation_min_length_mm: float
    segments: tuple[HlrSegment, ...]
    counters: HlrViewCounters


@dataclass(frozen=True)
class ViewIdentityEcho:
    """What the overlay was computed against (Codex1 B3). Studio must attach a
    standalone HLR payload only when ALL fields match the held package."""

    object_uuid: str
    object_number: str
    geometry_ref: str
    display_representation_version: str
    cache_key: str
    topology_signature: str


@dataclass(frozen=True)
class ViewDependentPayload:
    """The value of the `view_dependent` slot — inline in a v1.1
    `DisplayRepresentation`, or standalone from `display_hlr()`."""

    identity_echo: ViewIdentityEcho
    views: tuple[HlrView, ...]

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_engine_dict(cls, d: dict[str, Any]) -> "ViewDependentPayload":
        """Validate a standalone engine payload (fail-loud)."""
        if not isinstance(d, dict):
            raise DisplayContractError(
                f"view-dependent payload is not a dict: {type(d).__name__}"
            )
        try:
            payload = _parse_view_dependent(d)
        except (KeyError, TypeError, ValueError) as e:
            if isinstance(e, DisplayContractError):
                raise
            raise DisplayContractError(
                f"malformed view-dependent payload from producer: {e!r}"
            ) from e
        echoed = payload.identity_echo.display_representation_version
        if echoed not in HLR_CAPABLE_VERSIONS:
            raise DisplayContractError(
                f"view-dependent payload requires an HLR-capable contract version "
                f"{HLR_CAPABLE_VERSIONS!r}; producer echoed {echoed!r}"
            )
        return payload


@dataclass(frozen=True)
class SketchFrame:
    """v1.2: the RESOLVED plane frame of one face-bound sketch — derived
    display data (never Truth), identity-bound to THIS package by containment
    (it inherits object_uuid/geometry_ref/cache_key/topology_signature/version
    from the package it rides in — Codex2 B3.1)."""

    sketch_feature_id: str
    origin_mm: tuple[float, float, float]
    u_axis: tuple[float, float, float]
    v_axis: tuple[float, float, float]
    normal: tuple[float, float, float]


@dataclass(frozen=True)
class V2ConstructionPoint:
    """One solved construction point (world mm)."""

    id: str
    at: tuple[float, float, float]


@dataclass(frozen=True)
class V2ConstructionLine:
    """One solved construction line (world mm endpoints)."""

    id: str
    a: tuple[float, float, float]
    b: tuple[float, float, float]


@dataclass(frozen=True)
class V2ConstructionSketch:
    """v1.3 (Gate F2b): the SOLVED construction geometry of one v2
    constrained sketch — the engine's A2.9 read-lifecycle output. Derived
    display data (never Truth), identity-bound to THIS package by
    containment, exactly like `SketchFrame`. Codex26 B2: the THREE surfaces
    (engine, this validator, Studio) recite ONE exact member set — the
    bridge's `to_dict()` output is the contract Studio consumes, so every
    declared field survives the wire."""

    sketch_feature_id: str
    shape: str
    construction: bool
    points: tuple[V2ConstructionPoint, ...]
    lines: tuple[V2ConstructionLine, ...]


def _finite3(v: Any, label: str) -> tuple[float, float, float]:
    if not (isinstance(v, (list, tuple)) and len(v) == 3
            and all(isinstance(c, (int, float)) and not isinstance(c, bool)
                    and math.isfinite(c) for c in v)):
        raise DisplayContractError(f"{label} must be a finite 3-vector, got {v!r}")
    return (float(v[0]), float(v[1]), float(v[2]))


def _validate_v2_construction(raw: Any, version: str) -> tuple[V2ConstructionSketch, ...]:
    """v1.3 validator: unique sketch ids; every point/line id-addressed with
    finite world coordinates. Empty/absent is valid; a populated list on a
    pre-1.3 version is a producer error (the declared-shape amendment
    discipline, verbatim from sketch_frames)."""
    if raw in (None, []):
        return ()
    if version not in ("1.3",):
        raise DisplayContractError(
            f"v2_construction requires contract v1.3; producer declared {version!r}"
        )
    if not isinstance(raw, list):
        raise DisplayContractError("v2_construction must be a list")
    out: list[V2ConstructionSketch] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise DisplayContractError("v2_construction entries must be objects")
        sid = item.get("sketch_feature_id")
        if not isinstance(sid, str) or not sid or sid in seen:
            raise DisplayContractError(
                "v2_construction entries need unique non-empty sketch_feature_id"
            )
        seen.add(sid)
        # Codex26 B2: the shape is CLOSED (the skb-b0 admitted universe),
        # `construction` is a REQUIRED literal true, and the arrays are
        # required MEMBERS — absence never defaults to empty.
        shape = item.get("shape")
        if shape not in ("G0", "G1", "G2"):
            raise DisplayContractError(
                f"v2_construction {sid!r} shape must be G0|G1|G2, got {shape!r}"
            )
        if item.get("construction") is not True:
            raise DisplayContractError(
                f"v2_construction {sid!r} requires literal construction: true"
            )
        if not (isinstance(item.get("points"), list) and isinstance(item.get("lines"), list)):
            raise DisplayContractError(
                f"v2_construction {sid!r} requires points[] and lines[] members"
            )
        points = []
        pt_ids: set[str] = set()
        for p in item.get("points", []):
            if not (isinstance(p, dict) and isinstance(p.get("id"), str)
                    and p["id"] and p["id"] not in pt_ids):
                raise DisplayContractError(
                    f"v2_construction {sid!r} points need unique string ids"
                )
            pt_ids.add(p["id"])
            points.append(V2ConstructionPoint(
                id=p["id"], at=_finite3(p.get("at"), f"point {p['id']!r} at")))
        lines = []
        ln_ids: set[str] = set()
        for ln in item.get("lines", []):
            if not (isinstance(ln, dict) and isinstance(ln.get("id"), str)
                    and ln["id"] and ln["id"] not in ln_ids):
                raise DisplayContractError(
                    f"v2_construction {sid!r} lines need unique string ids"
                )
            ln_ids.add(ln["id"])
            lines.append(V2ConstructionLine(
                id=ln["id"],
                a=_finite3(ln.get("a"), f"line {ln['id']!r} a"),
                b=_finite3(ln.get("b"), f"line {ln['id']!r} b")))
        out.append(V2ConstructionSketch(
            sketch_feature_id=sid, shape=shape, construction=True,
            points=tuple(points), lines=tuple(lines)))
    return tuple(out)


def _validate_sketch_frames(raw: Any, version: str) -> tuple[SketchFrame, ...]:
    """The B3.1.5 validator: unique ids, finite 3-vectors, unit + orthogonal
    axes, right-handed v = normal × u. Empty/absent is valid; a populated list
    on a pre-1.2 version is a producer error."""
    if raw in (None, []):
        return ()
    if version not in ("1.2", "1.3"):
        raise DisplayContractError(
            f"sketch_frames requires contract v1.2+; producer declared {version!r}"
        )
    if not isinstance(raw, list):
        raise DisplayContractError("sketch_frames must be a list")
    frames: list[SketchFrame] = []
    seen: set[str] = set()
    for i, f in enumerate(raw):
        if not isinstance(f, dict):
            raise DisplayContractError(f"sketch_frames[{i}] must be an object")
        sid = f.get("sketch_feature_id")
        if not isinstance(sid, str) or not sid:
            raise DisplayContractError(f"sketch_frames[{i}] lacks sketch_feature_id")
        if sid in seen:
            raise DisplayContractError(f"sketch_frames duplicates {sid!r}")
        seen.add(sid)
        vecs: dict[str, tuple[float, float, float]] = {}
        for key in ("origin_mm", "u_axis", "v_axis", "normal"):
            v = f.get(key)
            if not (isinstance(v, (list, tuple)) and len(v) == 3):
                raise DisplayContractError(f"sketch_frames[{i}].{key} must be a 3-vector")
            vec = tuple(float(x) for x in v)
            if not all(math.isfinite(x) for x in vec):
                raise DisplayContractError(f"sketch_frames[{i}].{key} must be finite")
            vecs[key] = vec  # type: ignore[assignment]
        u, vv, n = vecs["u_axis"], vecs["v_axis"], vecs["normal"]
        dot = lambda a, b: a[0] * b[0] + a[1] * b[1] + a[2] * b[2]  # noqa: E731
        for name, val in (
            ("|u|", abs(math.sqrt(dot(u, u)) - 1.0)),
            ("|v|", abs(math.sqrt(dot(vv, vv)) - 1.0)),
            ("|n|", abs(math.sqrt(dot(n, n)) - 1.0)),
            ("u·v", abs(dot(u, vv))),
            ("u·n", abs(dot(u, n))),
            ("v·n", abs(dot(vv, n))),
        ):
            if val > _FRAME_TOL:
                raise DisplayContractError(
                    f"sketch_frames[{i}] fails orthonormality ({name} off by {val:.3e})"
                )
        cross = (
            n[1] * u[2] - n[2] * u[1],
            n[2] * u[0] - n[0] * u[2],
            n[0] * u[1] - n[1] * u[0],
        )
        if max(abs(cross[k] - vv[k]) for k in range(3)) > _FRAME_TOL:
            raise DisplayContractError(
                f"sketch_frames[{i}] is not right-handed (v != normal × u)"
            )
        frames.append(SketchFrame(
            sketch_feature_id=sid,
            origin_mm=vecs["origin_mm"],  # type: ignore[arg-type]
            u_axis=u, v_axis=vv, normal=n,  # type: ignore[arg-type]
        ))
    return tuple(frames)


@dataclass(frozen=True)
class DisplayRepresentation:
    """The full read-only display package for one Object, version-stamped."""

    identity: DisplayIdentity
    render: RenderPayload
    selection: SelectionPayload
    invalidation: DisplayInvalidation
    counters: DisplayCounters
    view_dependent: ViewDependentPayload | None = None
    sketch_frames: tuple[SketchFrame, ...] = ()
    # v1.3 (Gate F2b): solved v2 construction geometry (derived, never Truth).
    v2_construction: tuple[V2ConstructionSketch, ...] = ()
    display_representation_version: str = DISPLAY_REPRESENTATION_VERSION

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable dict (tuples → lists). The bridge ships this."""
        return dataclasses.asdict(self)

    # ------------------------------------------------------------------
    # Construction from an engine's plain-dict output (fail-loud)
    # ------------------------------------------------------------------

    @classmethod
    def from_engine_dict(cls, d: dict[str, Any]) -> "DisplayRepresentation":
        if not isinstance(d, dict):
            raise DisplayContractError(
                f"engine display output is not a dict: {type(d).__name__}"
            )
        version = d.get("display_representation_version")
        if version not in ACCEPTED_VERSIONS:
            raise DisplayContractError(
                f"unsupported display_representation_version {version!r}; "
                f"this core understands {ACCEPTED_VERSIONS!r}"
            )
        try:
            identity = DisplayIdentity(**_req(d, "identity"))
            r = _req(d, "render")
            render = RenderPayload(
                faces=tuple(
                    FaceBuffer(
                        face_id=f["face_id"],
                        positions=tuple(float(x) for x in f["positions"]),
                        normals=tuple(float(x) for x in f["normals"]),
                        triangles=tuple(int(i) for i in f["triangles"]),
                        appearance_slot=f.get("appearance_slot", "default"),
                        surface_kind=_surface_kind(f, version),
                    )
                    for f in r["faces"]
                ),
                edges=tuple(
                    EdgePolyline(
                        edge_id=e["edge_id"],
                        kind=e["kind"],
                        polyline=tuple(float(x) for x in e["polyline"]),
                        faces=tuple(e["faces"]),
                    )
                    for e in r["edges"]
                ),
                vertices=tuple(
                    VertexMarker(
                        vertex_id=v["vertex_id"],
                        position=tuple(float(x) for x in v["position"]),  # type: ignore[arg-type]
                    )
                    for v in r["vertices"]
                ),
                bbox_min=tuple(float(x) for x in r["bbox_min"]),  # type: ignore[assignment]
                bbox_max=tuple(float(x) for x in r["bbox_max"]),  # type: ignore[assignment]
                linear_deflection_mm=float(r["linear_deflection_mm"]),
                angular_deflection_rad=float(r["angular_deflection_rad"]),
                buffer_encoding=r.get("buffer_encoding", "json_arrays"),
            )
            sel = _req(d, "selection")
            selection = SelectionPayload(
                id_space=sel["id_space"],
                pickable_kinds=tuple(sel["pickable_kinds"]),
                names=dict(sel.get("names", {})),
            )
            inv = _req(d, "invalidation")
            invalidation = DisplayInvalidation(
                stale_when=tuple(inv["stale_when"]),
                selection_invalid_when=inv["selection_invalid_when"],
            )
            c = _req(d, "counters")
            counters = DisplayCounters(
                face_count=int(c["face_count"]),
                edge_count_by_kind=dict(c["edge_count_by_kind"]),
                triangle_count=int(c["triangle_count"]),
                vertex_count=int(c["vertex_count"]),
                generation_ms=c.get("generation_ms"),
                package_bytes=c.get("package_bytes"),
            )
        except (KeyError, TypeError, ValueError) as e:
            raise DisplayContractError(
                f"malformed Display Representation from producer: {e!r}"
            ) from e

        vd_raw = d.get("view_dependent")
        view_dependent: ViewDependentPayload | None = None
        if vd_raw is not None:
            if version == "1.0":
                # The v1.0 rule survives verbatim (Codex1 Q7).
                raise DisplayContractError(
                    "view_dependent must be null in contract v1.0 (HLR "
                    "requires contract v1.1)"
                )
            try:
                view_dependent = _parse_view_dependent(vd_raw)
            except (KeyError, TypeError, ValueError) as e:
                if isinstance(e, DisplayContractError):
                    raise
                raise DisplayContractError(
                    f"malformed inline view_dependent payload: {e!r}"
                ) from e
            _check_echo_matches_identity(
                view_dependent.identity_echo, identity, version)
        sketch_frames = _validate_sketch_frames(d.get("sketch_frames"), version)
        v2_construction = _validate_v2_construction(d.get("v2_construction"), version)

        return cls(
            identity=identity,
            render=render,
            selection=selection,
            invalidation=invalidation,
            counters=counters,
            view_dependent=view_dependent,
            sketch_frames=sketch_frames,
            v2_construction=v2_construction,
            display_representation_version=version,
        )


# ---------------------------------------------------------------------------
# View-dependent parsing + validation helpers
# ---------------------------------------------------------------------------


def _parse_view_dependent(d: dict[str, Any]) -> ViewDependentPayload:
    if not isinstance(d, dict):
        raise DisplayContractError(
            f"view_dependent must be an object, got {type(d).__name__}"
        )
    echo_raw = _req(d, "identity_echo")
    echo = ViewIdentityEcho(
        object_uuid=str(echo_raw["object_uuid"]),
        object_number=str(echo_raw["object_number"]),
        geometry_ref=str(echo_raw["geometry_ref"]),
        display_representation_version=str(
            echo_raw["display_representation_version"]),
        cache_key=str(echo_raw["cache_key"]),
        topology_signature=str(echo_raw["topology_signature"]),
    )
    views_raw = d.get("views")
    if not isinstance(views_raw, (list, tuple)) or not views_raw:
        raise DisplayContractError(
            "view_dependent.views must be a non-empty list"
        )
    return ViewDependentPayload(
        identity_echo=echo,
        views=tuple(_parse_view(v) for v in views_raw),
    )


def _parse_view(v: dict[str, Any]) -> HlrView:
    view_id = v.get("view_id")
    if not isinstance(view_id, str) or not view_id:
        raise DisplayContractError("each view requires a non-empty 'view_id'")

    coordinate_space = v.get("coordinate_space")
    if coordinate_space != "view_plane_2d":
        raise DisplayContractError(
            f"view {view_id!r}: unknown coordinate_space "
            f"{coordinate_space!r} (contract v1.1 = 'view_plane_2d')"
        )
    algorithm = v.get("algorithm")
    if algorithm not in ("exact", "poly"):
        raise DisplayContractError(
            f"view {view_id!r}: unknown algorithm {algorithm!r} "
            f"(expected 'exact' or 'poly')"
        )
    min_len = v.get("correlation_min_length_mm")
    if not isinstance(min_len, (int, float)) or min_len < 0:
        raise DisplayContractError(
            f"view {view_id!r}: correlation_min_length_mm must be a "
            f"non-negative number"
        )

    projector = _parse_projector(_req(v, "projector"), view_id)

    segs_raw = v.get("segments")
    if not isinstance(segs_raw, (list, tuple)):
        raise DisplayContractError(
            f"view {view_id!r}: 'segments' must be a list"
        )
    segments = tuple(_parse_segment(s, view_id) for s in segs_raw)

    c = _req(v, "counters")
    counters = HlrViewCounters(
        visible_segments=int(c["visible_segments"]),
        hidden_segments=int(c["hidden_segments"]),
        outline_segments=int(c["outline_segments"]),
        discarded_tolerance_segments=int(c["discarded_tolerance_segments"]),
        generation_ms=c.get("generation_ms"),
    )
    # Counter consistency — the acceptance baseline must be trustworthy.
    vis = sum(1 for s in segments if s.visibility == "visible")
    hid = sum(1 for s in segments if s.visibility == "hidden")
    out = sum(1 for s in segments if s.edge_class == "outline")
    if (counters.visible_segments, counters.hidden_segments,
            counters.outline_segments) != (vis, hid, out):
        raise DisplayContractError(
            f"view {view_id!r}: counters disagree with segments "
            f"(claimed {counters.visible_segments}/{counters.hidden_segments}"
            f"/{counters.outline_segments}, actual {vis}/{hid}/{out})"
        )

    return HlrView(
        view_id=view_id,
        projector=projector,
        algorithm=algorithm,
        coordinate_space=coordinate_space,
        correlation_min_length_mm=float(min_len),
        segments=segments,
        counters=counters,
    )


def _parse_projector(p: dict[str, Any], view_id: str) -> HlrProjector:
    projection = p.get("projection")
    if projection != "orthographic":
        raise DisplayContractError(
            f"view {view_id!r}: projection {projection!r} unsupported "
            f"(contract v1.1 = 'orthographic' only; perspective is reserved)"
        )
    units = p.get("units")
    if units != "mm":
        raise DisplayContractError(
            f"view {view_id!r}: projector units must be 'mm', got {units!r}"
        )
    origin = _vec3(p.get("origin"), view_id, "origin")
    direction = _unit_vec3(p.get("direction"), view_id, "direction")
    up = _unit_vec3(p.get("up"), view_id, "up")
    right = _unit_vec3(p.get("right"), view_id, "right")

    # B2: the basis must be exactly the pinned construction —
    # right == direction × up (orthonormal, right-handed (right, up, -direction)).
    expected_right = _cross(direction, up)
    if _dist3(right, expected_right) > 1e-5:
        raise DisplayContractError(
            f"view {view_id!r}: 'right' must equal direction × up "
            f"(got {right}, expected {expected_right}) — the view basis is "
            f"contract-pinned, not producer-specific"
        )
    if abs(_dot3(direction, up)) > 1e-5:
        raise DisplayContractError(
            f"view {view_id!r}: 'up' must be orthogonal to 'direction' "
            f"(the producer echoes the ORTHONORMALIZED up)"
        )
    return HlrProjector(
        projection=projection, origin=origin, direction=direction,
        up=up, right=right, units=units,
    )


def _parse_segment(s: dict[str, Any], view_id: str) -> HlrSegment:
    visibility = s.get("visibility")
    if visibility not in ("visible", "hidden"):
        raise DisplayContractError(
            f"view {view_id!r}: segment visibility {visibility!r} invalid"
        )
    edge_class = s.get("edge_class")
    if edge_class not in ("sharp", "smooth", "sewn", "outline"):
        raise DisplayContractError(
            f"view {view_id!r}: segment edge_class {edge_class!r} invalid"
        )
    poly = s.get("polyline_2d")
    if (not isinstance(poly, (list, tuple)) or len(poly) < 4
            or len(poly) % 2 != 0
            or not all(isinstance(x, (int, float)) and math.isfinite(x)
                       for x in poly)):
        raise DisplayContractError(
            f"view {view_id!r}: segment polyline_2d must be a flat, finite "
            f"(u,v) list with >= 2 points"
        )
    source = _parse_source(s.get("source"), view_id, edge_class)
    return HlrSegment(
        polyline_2d=tuple(float(x) for x in poly),
        visibility=visibility,
        edge_class=edge_class,
        source=source,
    )


def _parse_source(src: Any, view_id: str, edge_class: str) -> HlrSegmentSource:
    if not isinstance(src, dict):
        raise DisplayContractError(
            f"view {view_id!r}: segment source must be an object"
        )
    kind = src.get("kind")
    if kind == "model_edge":
        if edge_class == "outline":
            raise DisplayContractError(
                f"view {view_id!r}: an outline segment cannot carry a "
                f"model_edge source (B5 firewall)"
            )
        edge_id = src.get("edge_id")
        if not isinstance(edge_id, str) or not edge_id:
            raise DisplayContractError(
                f"view {view_id!r}: model_edge source requires 'edge_id'"
            )
        if src.get("face_id") is not None or src.get("index") is not None:
            raise DisplayContractError(
                f"view {view_id!r}: model_edge source must not carry "
                f"'face_id'/'index' (strict union, B5)"
            )
        return HlrSegmentSource(kind="model_edge", edge_id=edge_id)
    if kind == "outline":
        if edge_class != "outline":
            raise DisplayContractError(
                f"view {view_id!r}: only outline segments may carry an "
                f"outline source (B5 firewall)"
            )
        face_id = src.get("face_id")
        index = src.get("index")
        if not isinstance(face_id, str) or not face_id:
            raise DisplayContractError(
                f"view {view_id!r}: outline source requires 'face_id'"
            )
        if not isinstance(index, int) or index < 0:
            raise DisplayContractError(
                f"view {view_id!r}: outline source requires a non-negative "
                f"integer 'index' (per-view ordinal)"
            )
        if src.get("edge_id") is not None:
            raise DisplayContractError(
                f"view {view_id!r}: outline source must not carry 'edge_id' "
                f"(strict union, B5 — silhouettes are never display ids)"
            )
        return HlrSegmentSource(kind="outline", face_id=face_id, index=index)
    raise DisplayContractError(
        f"view {view_id!r}: unknown segment source kind {kind!r} "
        f"(expected 'model_edge' or 'outline')"
    )


def _check_echo_matches_identity(
    echo: ViewIdentityEcho, identity: DisplayIdentity, package_version: str
) -> None:
    """All SIX echo fields must agree (Codex2 B2 added the version: an inline
    echo must carry the enclosing package's contract version — which the
    enclosing-version gate already constrains to '1.1' for populated slots —
    matching the standalone rule and the Studio attach check)."""
    mismatches = [
        name for name, a, b in (
            ("object_uuid", echo.object_uuid, identity.object_uuid),
            ("object_number", echo.object_number, identity.object_number),
            ("geometry_ref", echo.geometry_ref, identity.geometry_ref),
            ("cache_key", echo.cache_key, identity.cache_key),
            ("topology_signature", echo.topology_signature,
             identity.topology_signature),
            ("display_representation_version",
             echo.display_representation_version, package_version),
        ) if a != b
    ]
    if mismatches:
        raise DisplayContractError(
            f"inline view_dependent identity_echo disagrees with the package "
            f"identity on: {', '.join(mismatches)} — an overlay must never "
            f"attach to the wrong package (B3)"
        )


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _surface_kind(f: dict, version: str) -> str | None:
    sk = f.get("surface_kind")
    if sk is None:
        return None
    # Codex7 B3: v1.1 -> v1.2 is a DECLARED-shape amendment — a legacy
    # package carrying the new field is a producer error, exactly like
    # populated sketch_frames (never an additive mutation of v1.1).
    if version not in ("1.2", "1.3"):
        raise DisplayContractError(
            f"face {f.get('face_id')!r} carries surface_kind under contract "
            f"{version!r}; the field requires v1.2+"
        )
    if sk not in ("plane", "other"):
        raise DisplayContractError(
            f"face {f.get('face_id')!r} surface_kind must be 'plane'|'other', got {sk!r}"
        )
    return sk


def _req(d: dict[str, Any], key: str) -> dict[str, Any]:
    v = d.get(key)
    if not isinstance(v, dict):
        raise DisplayContractError(f"display package missing required object section {key!r}")
    return v


def _vec3(v: Any, view_id: str, label: str) -> tuple[float, float, float]:
    if (not isinstance(v, (list, tuple)) or len(v) != 3
            or not all(isinstance(c, (int, float)) and math.isfinite(c)
                       for c in v)):
        raise DisplayContractError(
            f"view {view_id!r}: projector {label!r} must be a finite "
            f"3-component vector"
        )
    return (float(v[0]), float(v[1]), float(v[2]))


def _unit_vec3(v: Any, view_id: str, label: str) -> tuple[float, float, float]:
    vec = _vec3(v, view_id, label)
    n = math.sqrt(_dot3(vec, vec))
    if abs(n - 1.0) > _UNIT_TOL:
        raise DisplayContractError(
            f"view {view_id!r}: projector {label!r} must be a unit vector "
            f"(|v| = {n:.9f})"
        )
    return vec


def _dot3(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b) -> tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dist3(a, b) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)
