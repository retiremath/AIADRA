"""Real OCCT evaluation of a Part's feature recipe — the v0.0.1 VALIDITY GATE.

Per [ADR/0031 D6] OCCT is used as a *validity gate*, not an identity source:
the kernel evaluates the feature recipe to a real solid and rejects geometric
garbage that the Wedge-003 toy kernel accepted. The evaluated shape is a
per-process materialization (cached in `cache.py`); it is NEVER persisted as
Truth — identity stays on the recipe hash (`kernel.py`).

**Failure classes (ADR/0031 D6/B2 + arc 20260602-1 Codex1 B1):**
- *Class 1 — domain/payload*: deterministic, caught before/around the kernel,
  raised as `TransactionError` (a dispatch-adapter PASSTHROUGH exception) with
  a clear message. e.g. a circle that does not fit inside the rectangle.
- *Class 2 — kernel execution*: OCP raises, or produces a null / invalid shape,
  while evaluating a *plausible* recipe. This module raises a package-local
  `MechanicalKernelEvaluationError` (a non-passthrough exception). **The engine
  NEVER constructs `NativeEngineKernelError`** — the aiadra-core dispatch
  adapter owns that wrapping + the failure audit (Codex1 B1). Callers observe
  `NativeEngineKernelError`; the engine raises the raw/kernel-local failure.

OCCT tolerance is pinned + documented here (ADR/0031 D9). Because identity is
recipe-hash, tolerance does NOT affect `vault_ref` — it only gates validity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aiadra_core.transaction.boundary import TransactionError

from OCP.Bnd import Bnd_Box
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer, BRepFilletAPI_MakeFillet
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Vec
from OCP.Precision import Precision
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS, TopoDS_Shape
from OCP.TopTools import TopTools_IndexedMapOfShape

# ADR/0031 D9 — pinned tolerance default (OCCT confusion tolerance). Identity is
# recipe-hash so this does not affect `vault_ref`; it gates validity only.
CONFUSION_TOLERANCE_MM: float = Precision.Confusion_s()

ENGINE_OP_PREFIX = "mechanical"


class MechanicalKernelEvaluationError(RuntimeError):
    """Class-2 (kernel execution) failure sentinel. NON-passthrough: the
    aiadra-core dispatch adapter wraps this as `NativeEngineKernelError` with
    `__cause__` + a failure audit (ADR/0028 D9 + arc 20260602-1 Codex1 B1).
    The engine never constructs `NativeEngineKernelError` itself."""


@dataclass(frozen=True)
class ProducedFaceHint:
    """By-construction role authority for feature-produced topology (ADR/0038 D6
    + the arc 20260622-2 A3 amendment). `faces` are the live faces the producing
    OCCT operation reported (a fillet blend via `MakeFillet.Generated(edge)`; a
    hole wall via `Cut.Modified(cutter_lateral)`). The single topology extractor
    consumes these as recipe authority for the `feat_N:face:<role_base>` role and
    enforces the MANDATORY claim invariant — NEVER re-guessing a produced face
    from surface geometry. `role_base` is feature-kind-owned (`blend`,
    `hole_wall`, …), not always `blend`."""

    feature_id: str
    role_base: str
    faces: tuple[Any, ...]                # live TopoDS_Face handles in `.shape`


@dataclass(frozen=True)
class EvalResult:
    """The evaluated solid plus the construction provenance the topology layer
    needs (ADR/0038 D6). `evaluate_part` returns `.shape` for the validity gate;
    `extract_part_topology` consumes the whole result so display/HLR identity is
    assigned recipe-first, by construction."""

    shape: TopoDS_Shape
    produced_hints: tuple[ProducedFaceHint, ...] = field(default_factory=tuple)


def evaluate_part(features: list[dict[str, Any]]) -> TopoDS_Shape:
    """Evaluate the current feature recipe to a validated OCCT shape (the
    validity gate). Returns the shape only; raises `TransactionError` (Class-1
    domain) / `MechanicalKernelEvaluationError` (Class-2 kernel)."""
    return _evaluate(features).shape


def evaluate_part_with_provenance(features: list[dict[str, Any]]) -> EvalResult:
    """As `evaluate_part`, but also returns the by-construction `blend_hints`
    (ADR/0038 D6) — the topology layer's authority for fillet-produced roles."""
    return _evaluate(features)


def _evaluate(features: list[dict[str, Any]]) -> EvalResult:
    sketch = _last_feature_of_type(features, "sketch")
    if sketch is None:
        # Nothing geometric to evaluate yet (e.g. an empty Part). No-op gate.
        return EvalResult(shape=TopoDS_Shape())
    primitives = sketch.get("adapter_payload", {}).get("primitives", [])
    rectangle, circle = _split_primitives(primitives)

    extrude = _last_feature_of_type(features, "extrude")
    try:
        if extrude is None:
            shape: TopoDS_Shape = _build_sketch_face(rectangle, circle)
        else:
            depth_mm, direction = _extract_extrude(extrude)
            shape = _build_extruded_solid(rectangle, circle, depth_mm, direction)
    except (TransactionError, MechanicalKernelEvaluationError):
        raise
    except Exception as exc:  # raw OCP / OCCT failure on a plausible recipe
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: OCCT evaluation raised {exc!r}"
        ) from exc

    _assert_valid(shape, "base solid")

    # Sequential fold (ADR/0038 D3): fold each post-base feature onto the running
    # solid, in recipe order. v0.1.2 added the fillet; v0.1.3 adds the hole. Each
    # produced feature emits a ProducedFaceHint (A3) for by-construction roles.
    # (v1 scope: a single produced feature on a plain extrude — resolving a
    # second produced feature's reference against a shape that already carries
    # prior produced faces is deferred, and fails loud rather than mislabel.)
    produced: list[ProducedFaceHint] = []
    running = shape
    for idx, feat in enumerate(features):
        ftype = feat.get("feature_type")
        if ftype not in ("fillet", "chamfer", "hole"):
            continue
        if extrude is None:
            raise TransactionError(
                f"{ENGINE_OP_PREFIX}: a {ftype} requires an extruded solid"
            )
        prefix = features[:idx]
        if ftype == "fillet":
            running, hint = _apply_one_fillet(running, prefix, feat)
        elif ftype == "chamfer":
            running, hint = _apply_one_chamfer(running, prefix, feat)
        else:
            running, hint = _apply_one_hole(running, prefix, feat)
        produced.append(hint)

    return EvalResult(shape=running, produced_hints=tuple(produced))


def _check_reference_staleness(prefix, tgt, feature, what: str) -> None:
    """ADR/0038 D4: the persisted reference resolves against the parent-prefix
    skeleton it was authored against. A skeleton change (a topology edit, NOT a
    parameter edit) fails loud."""
    from . import topology

    stored_sig = tgt.get("resolved_against_topology_signature")
    current_sig = topology.compute_topology_signature(prefix)
    if stored_sig != current_sig:
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: {feature.get('feature_type')} {feature.get('id')!r} "
            f"{what} is STALE — the parent topology skeleton changed since it was "
            f"authored (resolved_against={stored_sig!r}, current={current_sig!r}). "
            f"A parameter edit preserves the reference; a topology edit requires re-picking."
        )


def _apply_one_fillet(running, prefix, fillet):
    """Round one sharp edge (ADR/0038 D2/D3). The edge is resolved on the SAME
    running instance it is filleted (the spike's same-instance rule)."""
    from . import topology  # lazy: topology imports geometry at module top

    tgt = (fillet.get("adapter_payload") or {}).get("target_edge")
    if not isinstance(tgt, dict):
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: fillet {fillet.get('id')!r} has no target_edge reference"
        )
    _check_reference_staleness(prefix, tgt, fillet, "target edge")
    roles = tuple(tgt.get("adjacent_face_roles", ()))
    kind = tgt.get("edge_kind")
    edge = topology.resolve_edge_on_shape(running, prefix, roles, kind)
    radius = _fillet_radius(fillet)
    try:
        mk = BRepFilletAPI_MakeFillet(running)
        mk.Add(radius, edge)
        filleted = mk.Shape()
        generated = tuple(TopoDS.Face_s(s) for s in mk.Generated(edge))
    except (TransactionError, MechanicalKernelEvaluationError):
        raise
    except Exception as exc:  # plausible reference, unbuildable radius/blend
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: fillet {fillet.get('id')!r} (radius={radius}) "
            f"could not be built by OCCT: {exc!r}"
        ) from exc
    _assert_valid(filleted, f"fillet {fillet.get('id')!r}")
    if not generated:
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: fillet {fillet.get('id')!r} built a solid but OCCT "
            f"reported no generated blend face (ADR/0038 D6)"
        )
    return filleted, ProducedFaceHint(feature_id=fillet["id"], role_base="blend", faces=generated)


def _apply_one_chamfer(running, prefix, chamfer):
    """Bevel one sharp edge (ADR/0038 D2/D3) — the fillet's edge-reference twin.
    The bevel face is a PLANE (not a cylinder), claimed BY CONSTRUCTION via
    `MakeChamfer.Generated(edge)` (ADR/0038 A3, the planar produced-face case)."""
    from . import topology  # lazy: topology imports geometry at module top

    tgt = (chamfer.get("adapter_payload") or {}).get("target_edge")
    if not isinstance(tgt, dict):
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: chamfer {chamfer.get('id')!r} has no target_edge reference"
        )
    _check_reference_staleness(prefix, tgt, chamfer, "target edge")
    roles = tuple(tgt.get("adjacent_face_roles", ()))
    kind = tgt.get("edge_kind")
    edge = topology.resolve_edge_on_shape(running, prefix, roles, kind)
    distance = _chamfer_distance(chamfer)
    try:
        mk = BRepFilletAPI_MakeChamfer(running)
        mk.Add(distance, edge)
        chamfered = mk.Shape()
        generated = tuple(TopoDS.Face_s(s) for s in mk.Generated(edge))
    except (TransactionError, MechanicalKernelEvaluationError):
        raise
    except Exception as exc:  # plausible reference, unbuildable distance/bevel
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: chamfer {chamfer.get('id')!r} (distance={distance}) "
            f"could not be built by OCCT: {exc!r}"
        ) from exc
    _assert_valid(chamfered, f"chamfer {chamfer.get('id')!r}")
    if not generated:
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: chamfer {chamfer.get('id')!r} built a solid but OCCT "
            f"reported no generated bevel face (ADR/0038 D6/A3)"
        )
    return chamfered, ProducedFaceHint(feature_id=chamfer["id"], role_base="chamfer", faces=generated)


def _chamfer_distance(chamfer: dict[str, Any]) -> float:
    for p in chamfer.get("parameters", []):
        if p.get("name") == "distance_mm":
            d = float(p["value"])
            if d <= 0:
                raise TransactionError(
                    f"{ENGINE_OP_PREFIX}: chamfer distance_mm must be positive, got {d!r}"
                )
            return d
    raise TransactionError(
        f"{ENGINE_OP_PREFIX}: chamfer feature {chamfer.get('id')!r} missing a "
        f"'distance_mm' parameter record"
    )


def _apply_one_hole(running, prefix, hole):
    """Cut one circular through-hole on a cap face (ADR/0038 D2/D3 + A1). The
    face is resolved on the running instance; the wall is captured BY
    CONSTRUCTION from the boolean cut (A3)."""
    from . import topology

    tgt = (hole.get("adapter_payload") or {}).get("target_face")
    if not isinstance(tgt, dict):
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: hole {hole.get('id')!r} has no target_face reference"
        )
    _check_reference_staleness(prefix, tgt, hole, "target face")
    role = tgt.get("face_role")
    face = topology.resolve_face_on_shape(running, prefix, role)
    diameter = _hole_param(hole, "diameter_mm", positive=True)
    cx = _hole_param(hole, "center_x_mm")
    cy = _hole_param(hole, "center_y_mm")
    # Codex2 B1: enforce the v1 simple-cap + fit-within-face DOMAIN contract on
    # EVERY regeneration / parameter-edit path (not only the handler's initial
    # add), so an edited centre/diameter that breaches the cap fails Class-1
    # before the kernel — never a side-breaching cut or a Class-2 surprise.
    from .adapter_payload import require_simple_cap_fit

    require_simple_cap_fit(prefix, cx, cy, diameter / 2.0)
    holed, wall = _cut_through_hole(running, cx, cy, face, diameter, hole.get("id"))
    return holed, ProducedFaceHint(feature_id=hole["id"], role_base="hole_wall", faces=wall)


def _cut_through_hole(running, cx, cy, face, diameter, hole_id):
    """Cut a Ø`diameter` through-hole at sketch-XY (`cx`,`cy`) through a cap face.
    Cap = planar, normal ∥ the extrude axis (Z); the cylinder spans the solid's
    full Z-extent so the cut is direction-agnostic for cap_top and cap_base. The
    wall is captured by construction via `Cut.Modified(cylinder_lateral)`."""
    surf = BRepAdaptor_Surface(face)
    if surf.GetType() != GeomAbs_Plane:
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: hole {hole_id!r} target face is not planar"
        )
    n = surf.Plane().Position().Direction()
    if abs(n.Z()) < 0.999:
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: hole {hole_id!r} target face is not a cap "
            f"(normal not parallel to the extrude axis)"
        )
    bbox = Bnd_Box()
    BRepBndLib.Add_s(running, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    margin = 1.0
    try:
        axis = gp_Ax2(gp_Pnt(cx, cy, zmin - margin), gp_Dir(0.0, 0.0, 1.0))
        cyl = BRepPrimAPI_MakeCylinder(axis, diameter / 2.0, (zmax - zmin) + 2 * margin).Shape()
        cut = BRepAlgoAPI_Cut(running, cyl)
        holed = cut.Shape()
        wall = tuple(TopoDS.Face_s(s) for s in cut.Modified(_cylinder_lateral_face(cyl)))
    except (TransactionError, MechanicalKernelEvaluationError):
        raise
    except Exception as exc:
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: hole {hole_id!r} (Ø{diameter}) could not be built by OCCT: {exc!r}"
        ) from exc
    _assert_valid(holed, f"hole {hole_id!r}")
    if not wall:
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: hole {hole_id!r} produced no wall face by construction (ADR/0038 D6)"
        )
    return holed, wall


def _cylinder_lateral_face(cyl):
    fm = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(cyl, TopAbs_FACE, fm)
    for i in range(1, fm.Extent() + 1):
        f = TopoDS.Face_s(fm.FindKey(i))
        if BRepAdaptor_Surface(f).GetType() == GeomAbs_Cylinder:
            return f
    raise MechanicalKernelEvaluationError(
        f"{ENGINE_OP_PREFIX}: hole cutting cylinder has no lateral face"
    )


def _hole_param(hole: dict[str, Any], name: str, *, positive: bool = False) -> float:
    for p in hole.get("parameters", []):
        if p.get("name") == name:
            v = float(p["value"])
            if positive and v <= 0:
                raise TransactionError(
                    f"{ENGINE_OP_PREFIX}: hole {name} must be positive, got {v!r}"
                )
            return v
    raise TransactionError(
        f"{ENGINE_OP_PREFIX}: hole feature {hole.get('id')!r} missing a {name!r} parameter record"
    )


def _assert_valid(shape: TopoDS_Shape, label: str) -> None:
    if shape is None or shape.IsNull():
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: OCCT evaluation produced a null shape ({label})"
        )
    if not BRepCheck_Analyzer(shape).IsValid():
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: OCCT evaluation produced an invalid shape "
            f"({label}; BRepCheck_Analyzer rejected it)"
        )


def _fillet_radius(fillet: dict[str, Any]) -> float:
    for p in fillet.get("parameters", []):
        if p.get("name") == "radius_mm":
            r = float(p["value"])
            if r <= 0:
                raise TransactionError(
                    f"{ENGINE_OP_PREFIX}: fillet radius_mm must be positive, got {r!r}"
                )
            return r
    raise TransactionError(
        f"{ENGINE_OP_PREFIX}: fillet feature {fillet.get('id')!r} missing a "
        f"'radius_mm' parameter record"
    )


# ---------------------------------------------------------------------------
# Construction helpers
# ---------------------------------------------------------------------------


def _build_sketch_face(rectangle: dict[str, Any], circle: dict[str, Any] | None) -> TopoDS_Shape:
    """Planar rectangle face (z=0). The circle, if present, is validated as a
    constructible hole-profile (Class-1 domain check) but the 2D face is the
    rectangle outline — the hole is cut at extrude time as a real boolean."""
    face = _rectangle_face(rectangle)
    if circle is not None:
        _require_circle_inside_rectangle(rectangle, circle)
        # Validate the circle is itself a constructible wire.
        _circle_wire(circle)
    return face


def _build_extruded_solid(
    rectangle: dict[str, Any],
    circle: dict[str, Any] | None,
    depth_mm: float,
    direction: str,
) -> TopoDS_Shape:
    """Prism the rectangle face into a box; if a circle is present, cut a real
    cylindrical through-hole (genuine OCCT boolean)."""
    sign = 1.0 if direction == "z+" else -1.0
    box = BRepPrimAPI_MakePrism(
        _rectangle_face(rectangle), gp_Vec(0.0, 0.0, sign * depth_mm)
    ).Shape()
    if circle is None:
        return box
    _require_circle_inside_rectangle(rectangle, circle)
    # Cylinder spans beyond both faces of the box for a clean through-cut.
    margin = max(1.0, depth_mm)
    cyl_face = BRepBuilderAPI_MakeFace(_circle_wire(circle, z=-sign * margin)).Face()
    cylinder = BRepPrimAPI_MakePrism(
        cyl_face, gp_Vec(0.0, 0.0, sign * (depth_mm + 2.0 * margin))
    ).Shape()
    return BRepAlgoAPI_Cut(box, cylinder).Shape()


def _rectangle_face(rectangle: dict[str, Any]) -> TopoDS_Shape:
    x = float(rectangle["x_mm"])
    y = float(rectangle["y_mm"])
    w = float(rectangle["width_mm"])
    h = float(rectangle["height_mm"])
    p1 = gp_Pnt(x, y, 0.0)
    p2 = gp_Pnt(x + w, y, 0.0)
    p3 = gp_Pnt(x + w, y + h, 0.0)
    p4 = gp_Pnt(x, y + h, 0.0)
    e1 = BRepBuilderAPI_MakeEdge(p1, p2).Edge()
    e2 = BRepBuilderAPI_MakeEdge(p2, p3).Edge()
    e3 = BRepBuilderAPI_MakeEdge(p3, p4).Edge()
    e4 = BRepBuilderAPI_MakeEdge(p4, p1).Edge()
    wire = BRepBuilderAPI_MakeWire(e1, e2, e3, e4).Wire()
    return BRepBuilderAPI_MakeFace(wire).Face()


def _circle_wire(circle: dict[str, Any], *, z: float = 0.0):
    cx = float(circle["cx_mm"])
    cy = float(circle["cy_mm"])
    r = float(circle["radius_mm"])
    circ = gp_Circ(gp_Ax2(gp_Pnt(cx, cy, z), gp_Dir(0.0, 0.0, 1.0)), r)
    edge = BRepBuilderAPI_MakeEdge(circ).Edge()
    return BRepBuilderAPI_MakeWire(edge).Wire()


# ---------------------------------------------------------------------------
# Domain (Class-1) checks + recipe extraction
# ---------------------------------------------------------------------------


def _require_circle_inside_rectangle(rectangle: dict[str, Any], circle: dict[str, Any]) -> None:
    """Class-1 domain check (ADR/0031 D6/B2; Codex1 N2 arc 20260602-1: a circle
    outside the rectangle is engine-domain, NOT a kernel failure)."""
    x = float(rectangle["x_mm"])
    y = float(rectangle["y_mm"])
    w = float(rectangle["width_mm"])
    h = float(rectangle["height_mm"])
    cx = float(circle["cx_mm"])
    cy = float(circle["cy_mm"])
    r = float(circle["radius_mm"])
    if (cx - r) < x or (cx + r) > (x + w) or (cy - r) < y or (cy + r) > (y + h):
        raise TransactionError(
            f"mechanical: circle (cx={cx}, cy={cy}, r={r}) must fit entirely inside "
            f"the rectangle [{x}..{x + w}] x [{y}..{y + h}] to form a valid hole"
        )


def _split_primitives(
    primitives: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    rectangle = next((p for p in primitives if p.get("type") == "rectangle"), None)
    circle = next((p for p in primitives if p.get("type") == "circle"), None)
    if rectangle is None:
        raise TransactionError(
            "mechanical: sketch has no rectangle outer profile to evaluate"
        )
    return rectangle, circle


def _extract_extrude(extrude: dict[str, Any]) -> tuple[float, str]:
    direction = extrude.get("adapter_payload", {}).get("direction", "z+")
    # Defensive (arc 20260602-1 Codex2 N1): reject a corrupt stored direction
    # rather than silently treating an unexpected value as 'z-'. Write-time
    # validation lives in adapter_payload.build_extrude_payload; a bad value
    # here means a corrupt adapter_payload — fail loud per Manifesto P5.
    if direction not in ("z+", "z-"):
        raise TransactionError(
            f"mechanical: extrude feature has invalid stored direction {direction!r} "
            f"(expected 'z+' or 'z-') — corrupt adapter_payload"
        )
    depth_mm: float | None = None
    for param in extrude.get("parameters", []):
        if param.get("name") == "depth_mm":
            depth_mm = float(param["value"])
            break
    if depth_mm is None:
        raise TransactionError(
            "mechanical: extrude feature missing a 'depth_mm' parameter record"
        )
    if depth_mm <= 0:
        raise TransactionError(
            f"mechanical: extrude depth_mm must be positive, got {depth_mm!r}"
        )
    return depth_mm, direction


def _last_feature_of_type(features: list[dict[str, Any]], feature_type: str) -> dict[str, Any] | None:
    chosen: dict[str, Any] | None = None
    for f in features:
        if f.get("feature_type") == feature_type:
            chosen = f
    return chosen
