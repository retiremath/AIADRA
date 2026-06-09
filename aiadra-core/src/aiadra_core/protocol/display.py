"""The **Display Representation contract** — the versioned, read-only data
contract between a geometry producer (a Native Engine, or a future import
parser) and the AIADRA Studio viewport. ADR/0035 (arc 20260609-1); the central
deliverable of the rendering & topology foundation.

Kernel-neutral pure data — `aiadra-core` defines the *shape*; it imports no
geometry kernel. A Native Engine produces the payload (OCCT lives in the
engine, e.g. `aiadra-mechanical`); `display_representation()` in
`aiadra_core.protocol` validates the engine's dict into these frozen
dataclasses and returns them. Studio mirrors this shape as a TypeScript type.

Design notes (arc 20260609-1 Codex review):
- **B2 — `topology_signature`, not a counter.** A read-only operation has
  nowhere to persist a monotonic revision counter without writing Truth, so
  topology identity invalidation is keyed on a *deterministic signature* over
  the topology-affecting recipe skeleton. Parameter edits preserve it; adding
  / removing a feature or primitive changes it.
- **N4 — `buffer_encoding`** is a reserved field; v1 ships `"json_arrays"`.
- **N5 — `DisplayCounters`** carries the deterministic acceptance counters that
  become the baseline for the HLR / display-mode arcs.
- **D3/D6 — `view_dependent`** is a reserved slot (always `None` this arc);
  the HLR arc populates it additively (→ contract v1.1) without churn.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any

DISPLAY_REPRESENTATION_VERSION = "1.0"


class DisplayContractError(ValueError):
    """A producer returned a malformed / incompatible Display Representation.
    Fail-loud per Manifesto P5 — the viewport must never render guesswork."""


@dataclass(frozen=True)
class DisplayIdentity:
    object_uuid: str
    object_number: str
    geometry_ref: str          # the recipe-hash vault_ref (authoring identity)
    cache_key: str             # the engine's D8 freshness key for this package
    topology_signature: str    # B2: deterministic; stable across parameter edits


@dataclass(frozen=True)
class FaceBuffer:
    face_id: str
    positions: tuple[float, ...]   # flat (x,y,z) triples, this face's nodes
    normals: tuple[float, ...]     # flat (x,y,z) triples, true surface normals
    triangles: tuple[int, ...]     # flat (i,j,k) index triples into this face's nodes
    appearance_slot: str = "default"


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


@dataclass(frozen=True)
class DisplayRepresentation:
    """The full read-only display package for one Object, version-stamped."""

    identity: DisplayIdentity
    render: RenderPayload
    selection: SelectionPayload
    invalidation: DisplayInvalidation
    counters: DisplayCounters
    view_dependent: None = None  # HLR slot — reserved (populated by the HLR arc)
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
        if version != DISPLAY_REPRESENTATION_VERSION:
            raise DisplayContractError(
                f"unsupported display_representation_version {version!r}; "
                f"this core understands {DISPLAY_REPRESENTATION_VERSION!r}"
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
        if d.get("view_dependent") is not None:
            raise DisplayContractError(
                "view_dependent must be null in contract v1.0 (HLR is a later arc)"
            )
        return cls(
            identity=identity,
            render=render,
            selection=selection,
            invalidation=invalidation,
            counters=counters,
            view_dependent=None,
            display_representation_version=version,
        )


def _req(d: dict[str, Any], key: str) -> dict[str, Any]:
    v = d.get(key)
    if not isinstance(v, dict):
        raise DisplayContractError(f"display package missing required object section {key!r}")
    return v
