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

import math
from dataclasses import dataclass, field
from typing import Any

from aiadra_core.transaction.boundary import TransactionError

from .adapter_payload import require_valid_contour
from .recipe import (
    PlaneFrame,
    effective_plane_frame,
    extrude_sign,
    principal_frame,
    resolve_consumed_sketch,
)

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
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism, BRepPrimAPI_MakeRevol
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.gp import gp_Ax1, gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Vec
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
    extrude = _last_feature_of_type(features, "extrude")
    revolve = _last_feature_of_type(features, "revolve")
    # Codex1 B3 (evaluator side): extrude XOR revolve — a single base-creation
    # authority. A stored/corrupt recipe with both fails loud rather than letting
    # "last base wins" make recipe identity disagree with feature history.
    if extrude is not None and revolve is not None:
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: a Part has BOTH an extrude and a revolve base feature; "
            f"v1 supports exactly one base creation per Part"
        )
    base = extrude if extrude is not None else revolve
    if base is not None:
        # EP2 (arc 20260714-2, Codex1 B2): the base feature consumes EXACTLY the
        # sketch it names — never "the last sketch".
        sketch = resolve_consumed_sketch(features, base)
    else:
        # No base feature: preview the (last) unconsumed sketch, if any.
        sketch = _last_feature_of_type(features, "sketch")
        if sketch is None:
            # Nothing geometric to evaluate yet (e.g. an empty Part). No-op gate.
            return EvalResult(shape=TopoDS_Shape())
    # The effective plane frame (EP2) — validated on EVERY evaluation, so a
    # corrupt stored plane record fails loud at regeneration too.
    frame = effective_plane_frame(sketch)
    primitives = sketch.get("adapter_payload", {}).get("primitives", [])

    try:
        if revolve is not None:
            # D-P4: v1 revolve is principal-xy-only (its axis vocabulary is the
            # global x/y in the sketch plane). Checked on the EXACT sketch.
            if frame.orientation != "xy":
                raise TransactionError(
                    f"{ENGINE_OP_PREFIX}: v1 revolve requires the sketch on the "
                    f"principal xy plane; the consumed sketch is on {frame.orientation!r}"
                )
            rectangle = require_simple_revolve_profile(primitives)  # Codex1 B2
            shape: TopoDS_Shape = _build_revolved_solid(rectangle, _revolve_axis(revolve))
        else:
            outer_kind, outer, circle = _outer_profile(primitives)
            if outer_kind == "contour":
                # arc 20260711-11 slice E: an arbitrary closed-ring profile.
                # Eval-time Class-1 re-check (Codex4 D-E3) so a stored/edited/
                # corrupt recipe fails loud before OCCT, on every regeneration.
                require_valid_contour(outer)
                if extrude is None:
                    shape = _contour_face(outer, frame)
                else:
                    depth_mm, sign = _extract_extrude(extrude, frame)
                    shape = _build_contour_solid(outer, depth_mm, sign, frame)
            elif extrude is None:
                shape = _build_sketch_face(outer, circle, frame)
            else:
                depth_mm, sign = _extract_extrude(extrude, frame)
                shape = _build_extruded_solid(outer, circle, depth_mm, sign, frame)
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
            # v1 fold features (fillet/chamfer/hole) target the extrude box; they
            # are not supported on a revolve base yet (a v2 stacking concern).
            raise TransactionError(
                f"{ENGINE_OP_PREFIX}: a {ftype} requires an extruded solid (v1 does "
                f"not support {ftype} on a revolve)"
            )
        prefix = features[:idx]
        if ftype == "fillet":
            running, hint = _apply_one_fillet(running, prefix, feat)
        elif ftype == "chamfer":
            running, hint = _apply_one_chamfer(running, prefix, feat)
        else:
            running, hint = _apply_one_hole(running, prefix, feat, frame)
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


def _apply_one_hole(running, prefix, hole, frame: PlaneFrame):
    """Cut one circular through-hole on a cap face (ADR/0038 D2/D3 + A1). The
    face is resolved on the running instance; the wall is captured BY
    CONSTRUCTION from the boolean cut (A3). Hole centres are sketch-local
    (u, v); the cut runs along the sketch plane's normal (EP2)."""
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
    holed, wall = _cut_through_hole(running, cx, cy, face, diameter, hole.get("id"), frame)
    return holed, ProducedFaceHint(feature_id=hole["id"], role_base="hole_wall", faces=wall)


def _cut_through_hole(running, cx, cy, face, diameter, hole_id, frame: PlaneFrame):
    """Cut a Ø`diameter` through-hole at sketch-local (`cx`,`cy`) through a cap
    face. Cap = planar, normal ∥ the sketch plane's normal (EP2); the cylinder
    spans the solid's full extent along that normal so the cut is direction-
    agnostic for cap_top and cap_base. The wall is captured by construction via
    `Cut.Modified(cylinder_lateral)`."""
    surf = BRepAdaptor_Surface(face)
    if surf.GetType() != GeomAbs_Plane:
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: hole {hole_id!r} target face is not planar"
        )
    n = surf.Plane().Position().Direction()
    fn = frame.normal
    if abs(n.X() * fn[0] + n.Y() * fn[1] + n.Z() * fn[2]) < 0.999:
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: hole {hole_id!r} target face is not a cap "
            f"(normal not parallel to the extrude axis)"
        )
    bbox = Bnd_Box()
    BRepBndLib.Add_s(running, bbox)
    corner_min, corner_max = bbox.Get()[:3], bbox.Get()[3:]
    wmin = min(
        corner_min[0] * fn[0] + corner_min[1] * fn[1] + corner_min[2] * fn[2],
        corner_max[0] * fn[0] + corner_max[1] * fn[1] + corner_max[2] * fn[2],
    )
    wmax = max(
        corner_min[0] * fn[0] + corner_min[1] * fn[1] + corner_min[2] * fn[2],
        corner_max[0] * fn[0] + corner_max[1] * fn[1] + corner_max[2] * fn[2],
    )
    margin = 1.0
    try:
        axis = gp_Ax2(gp_Pnt(*frame.to_3d(cx, cy, wmin - margin)), gp_Dir(*fn))
        cyl = BRepPrimAPI_MakeCylinder(axis, diameter / 2.0, (wmax - wmin) + 2 * margin).Shape()
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
# Revolve (a non-referencing creation feature; arc 20260622-4)
# ---------------------------------------------------------------------------


def revolve_radial_mode(rectangle: dict[str, Any], axis: str) -> str:
    """The derived radial MODE of a revolve (Codex1 B1) — `solid` if the profile
    touches the revolve axis (min radius 0), `tube` if it is offset. A profile
    that CROSSES the axis is an invalid v1 revolve (self-intersecting) → Class-1.

    The mode is topology SKELETON (it adds/removes the `inner_wall` role), so it
    enters `compute_topology_signature`; the radii/positions are VALUES within a
    mode (ADR/0038 A2 spirit). Shared by the evaluator, the signature, and the
    correlation so all three agree."""
    if axis == "x":
        lo = float(rectangle["y_mm"])
        hi = lo + float(rectangle["height_mm"])
    elif axis == "y":
        lo = float(rectangle["x_mm"])
        hi = lo + float(rectangle["width_mm"])
    else:
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: revolve axis must be 'x' or 'y', got {axis!r}"
        )
    if lo < -1e-9 and hi > 1e-9:  # straddles the axis
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: revolve profile crosses the {axis}-axis (a "
            f"self-intersecting v1 revolve); offset the profile to one side of the axis"
        )
    min_radius = min(abs(lo), abs(hi))
    return "solid" if min_radius <= 1e-9 else "tube"


def require_simple_revolve_profile(primitives: list[dict[str, Any]]) -> dict[str, Any]:
    """Codex1 B2: a v1 revolve profile is EXACTLY one rectangle — no circles,
    lines, or extra rectangles silently ignored (which would make Truth claim a
    revolve of more than the engine actually revolved). Shared by the handler
    (early error) and the evaluator (direct/corrupt-recipe path)."""
    rects = [p for p in primitives if p.get("type") == "rectangle"]
    others = [p for p in primitives if p.get("type") != "rectangle"]
    if len(rects) != 1 or others:
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: v1 revolve requires a SIMPLE profile of exactly one "
            f"rectangle (no circles, lines, or extra rectangles); got primitive types "
            f"{[p.get('type') for p in primitives]}"
        )
    return rects[0]


def _revolve_axis(revolve: dict[str, Any]) -> str:
    axis = (revolve.get("adapter_payload") or {}).get("axis")
    if axis not in ("x", "y"):
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: revolve feature {revolve.get('id')!r} has invalid "
            f"axis {axis!r} (expected 'x' or 'y')"
        )
    return axis


def _build_revolved_solid(rectangle: dict[str, Any], axis: str) -> TopoDS_Shape:
    """Revolve the XY rectangle profile 360° around the global X or Y axis →
    a tube/washer (offset profile) or a solid cylinder (touching). The
    crossing-axis guard runs here too (the direct/evaluator path), not only the
    handler."""
    revolve_radial_mode(rectangle, axis)  # crossing-axis guard (Class-1)
    # v1 revolve is principal-xy-only (guarded upstream at the handler AND the
    # evaluator), so the profile builds on the xy frame explicitly.
    face = _rectangle_face(rectangle, principal_frame("xy"))
    direction = gp_Dir(1.0, 0.0, 0.0) if axis == "x" else gp_Dir(0.0, 1.0, 0.0)
    gp_axis = gp_Ax1(gp_Pnt(0.0, 0.0, 0.0), direction)
    return BRepPrimAPI_MakeRevol(face, gp_axis, 2.0 * math.pi).Shape()


# ---------------------------------------------------------------------------
# Construction helpers
# ---------------------------------------------------------------------------


def _build_sketch_face(
    rectangle: dict[str, Any], circle: dict[str, Any] | None, frame: PlaneFrame
) -> TopoDS_Shape:
    """Planar rectangle face on the sketch plane (w=0 in the frame). The circle,
    if present, is validated as a constructible hole-profile (Class-1 domain
    check) but the 2D face is the rectangle outline — the hole is cut at extrude
    time as a real boolean."""
    face = _rectangle_face(rectangle, frame)
    if circle is not None:
        _require_circle_inside_rectangle(rectangle, circle)
        # Validate the circle is itself a constructible wire.
        _circle_wire(circle, frame)
    return face


def _build_extruded_solid(
    rectangle: dict[str, Any],
    circle: dict[str, Any] | None,
    depth_mm: float,
    sign: float,
    frame: PlaneFrame,
) -> TopoDS_Shape:
    """Prism the rectangle face into a box along the sketch plane's ±normal
    (EP2); if a circle is present, cut a real cylindrical through-hole (genuine
    OCCT boolean)."""
    sweep = _normal_vec(frame, sign * depth_mm)
    box = BRepPrimAPI_MakePrism(_rectangle_face(rectangle, frame), sweep).Shape()
    if circle is None:
        return box
    _require_circle_inside_rectangle(rectangle, circle)
    # Cylinder spans beyond both faces of the box for a clean through-cut.
    margin = max(1.0, depth_mm)
    cyl_face = BRepBuilderAPI_MakeFace(_circle_wire(circle, frame, w=-sign * margin)).Face()
    cylinder = BRepPrimAPI_MakePrism(
        cyl_face, _normal_vec(frame, sign * (depth_mm + 2.0 * margin))
    ).Shape()
    return BRepAlgoAPI_Cut(box, cylinder).Shape()


def _normal_vec(frame: PlaneFrame, length: float) -> gp_Vec:
    n = frame.normal
    return gp_Vec(n[0] * length, n[1] * length, n[2] * length)


def _outer_profile(
    primitives: list[dict[str, Any]],
) -> tuple[str, dict[str, Any], dict[str, Any] | None]:
    """The single outer profile of a sketch + an optional circle hole. arc
    20260711-11 slice E: the outer profile is a rectangle OR a contour (Codex4
    D-E4 — a contour is an outer boundary only, so no circle rides with it)."""
    contour = next((p for p in primitives if p.get("type") == "contour"), None)
    if contour is not None:
        return "contour", contour, None
    rectangle = next((p for p in primitives if p.get("type") == "rectangle"), None)
    circle = next((p for p in primitives if p.get("type") == "circle"), None)
    if rectangle is None:
        raise TransactionError(
            "mechanical: sketch has no rectangle or contour outer profile to evaluate"
        )
    return "rectangle", rectangle, circle


def _contour_face(contour: dict[str, Any], frame: PlaneFrame) -> TopoDS_Shape:
    """A planar face from an explicit CLOSED RING of line segments (arc
    20260711-11 slice E), built on the sketch plane (EP2). The segments already
    close the ring (Codex4 B1 — no implicit closing edge); one OCCT edge per
    segment, in ring order. Segment coordinates are sketch-local (u, v)."""
    wire = BRepBuilderAPI_MakeWire()
    for seg in contour["segments"]:
        p1 = gp_Pnt(*frame.to_3d(float(seg["x1_mm"]), float(seg["y1_mm"])))
        p2 = gp_Pnt(*frame.to_3d(float(seg["x2_mm"]), float(seg["y2_mm"])))
        wire.Add(BRepBuilderAPI_MakeEdge(p1, p2).Edge())
    return BRepBuilderAPI_MakeFace(wire.Wire()).Face()


def _build_contour_solid(
    contour: dict[str, Any], depth_mm: float, sign: float, frame: PlaneFrame
) -> TopoDS_Shape:
    """Prism a contour face into a solid along ±normal (v1: outer boundary
    only, no hole)."""
    return BRepPrimAPI_MakePrism(
        _contour_face(contour, frame), _normal_vec(frame, sign * depth_mm)
    ).Shape()


def _rectangle_face(rectangle: dict[str, Any], frame: PlaneFrame) -> TopoDS_Shape:
    """The rectangle profile on the sketch plane. `x_mm`/`y_mm` are the
    sketch-LOCAL (u, v) — not global-axis claims (EP2)."""
    u = float(rectangle["x_mm"])
    v = float(rectangle["y_mm"])
    w = float(rectangle["width_mm"])
    h = float(rectangle["height_mm"])
    p1 = gp_Pnt(*frame.to_3d(u, v))
    p2 = gp_Pnt(*frame.to_3d(u + w, v))
    p3 = gp_Pnt(*frame.to_3d(u + w, v + h))
    p4 = gp_Pnt(*frame.to_3d(u, v + h))
    e1 = BRepBuilderAPI_MakeEdge(p1, p2).Edge()
    e2 = BRepBuilderAPI_MakeEdge(p2, p3).Edge()
    e3 = BRepBuilderAPI_MakeEdge(p3, p4).Edge()
    e4 = BRepBuilderAPI_MakeEdge(p4, p1).Edge()
    wire = BRepBuilderAPI_MakeWire(e1, e2, e3, e4).Wire()
    return BRepBuilderAPI_MakeFace(wire).Face()


def _circle_wire(circle: dict[str, Any], frame: PlaneFrame, *, w: float = 0.0):
    cx = float(circle["cx_mm"])
    cy = float(circle["cy_mm"])
    r = float(circle["radius_mm"])
    circ = gp_Circ(
        gp_Ax2(gp_Pnt(*frame.to_3d(cx, cy, w)), gp_Dir(*frame.normal)), r
    )
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


def _extract_extrude(extrude: dict[str, Any], frame: PlaneFrame) -> tuple[float, float]:
    """The extrude's (depth, sweep-sign) against the consumed sketch's frame.
    EP2 (Codex1 B3): `normal±` is canonical; legacy stored `z±` normalizes here
    on EVERY regeneration and is accepted only on a principal-xy frame — never
    rewritten on disk. A corrupt direction fails loud (arc 20260602-1 Codex2 N1;
    Manifesto P5)."""
    direction = extrude.get("adapter_payload", {}).get("direction", "z+")
    sign = extrude_sign(direction, frame, op_kind="mechanical.extrude")
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
    return depth_mm, sign


def _last_feature_of_type(features: list[dict[str, Any]], feature_type: str) -> dict[str, Any] | None:
    chosen: dict[str, Any] | None = None
    for f in features:
        if f.get("feature_type") == feature_type:
            chosen = f
    return chosen
