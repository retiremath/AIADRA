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

from typing import Any

from aiadra_core.transaction.boundary import TransactionError

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Vec
from OCP.Precision import Precision
from OCP.TopoDS import TopoDS_Shape

# ADR/0031 D9 — pinned tolerance default (OCCT confusion tolerance). Identity is
# recipe-hash so this does not affect `vault_ref`; it gates validity only.
CONFUSION_TOLERANCE_MM: float = Precision.Confusion_s()

ENGINE_OP_PREFIX = "mechanical"


class MechanicalKernelEvaluationError(RuntimeError):
    """Class-2 (kernel execution) failure sentinel. NON-passthrough: the
    aiadra-core dispatch adapter wraps this as `NativeEngineKernelError` with
    `__cause__` + a failure audit (ADR/0028 D9 + arc 20260602-1 Codex1 B1).
    The engine never constructs `NativeEngineKernelError` itself."""


def evaluate_part(features: list[dict[str, Any]]) -> TopoDS_Shape:
    """Evaluate the current feature recipe to a validated OCCT shape.

    Returns the evaluated shape (cache-only; not persisted). Raises
    `TransactionError` for Class-1 domain failures and
    `MechanicalKernelEvaluationError` for Class-2 kernel failures.
    """
    sketch = _last_feature_of_type(features, "sketch")
    if sketch is None:
        # Nothing geometric to evaluate yet (e.g. an empty Part). No-op gate.
        return TopoDS_Shape()
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

    if shape is None or shape.IsNull():
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: OCCT evaluation produced a null shape"
        )
    if not BRepCheck_Analyzer(shape).IsValid():
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: OCCT evaluation produced an invalid shape "
            f"(BRepCheck_Analyzer rejected it)"
        )
    return shape


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
