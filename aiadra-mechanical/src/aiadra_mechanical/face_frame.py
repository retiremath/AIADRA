"""The OCCT-aware face-plane resolver (SK-C1.0 S2; arc 20260716-2 Codex1 B1.2).

The SECOND layer of the two-layer face-binding architecture: `recipe.py` owns
the PURE record structure and the skeleton (signature) — THIS module owns the
kernel-aware resolution. `resolve_face_plane` receives the exact parent
PREFIX (the features strictly before the face-bound sketch in the fold),
validates the stored parent-prefix topology signature, resolves EXACTLY one
face by its recipe-anchored role, checks planarity, and returns an
origin-aware `PlaneFrame`.

THE NUMERICAL RULE, pinned completely (Codex1 B1.7 / Claude2 B1.6):

- the oriented outward normal is the adapted plane normal, FLIPPED when the
  face is `TopAbs_REVERSED` (the standard OCCT orientation rule);
- `origin_mm` (millimetres by schema) is the orthogonal projection of the
  GLOBAL ORIGIN onto the face plane;
- `u_axis` is the first global axis in the FIXED order X → Y → Z whose
  in-plane projection magnitude exceeds `PLANE_AXIS_PROJECTION_TOL`
  (dimensionless — the operands are unit vectors), projected and normalized;
  exhaustion is impossible for a unit normal and refuses loudly regardless
  (never a silent fallback);
- `v_axis = normal × u_axis`; orthonormality is asserted to
  `FRAME_ORTHONORMAL_TOL`.

EDIT-STABILITY (narrowed per Codex1 B1.7): the frame is stable exactly when
the same structured face resolves to the same ORIENTED plane; an orientation
flip re-derives from the flipped normal (v mirrors) — that boundary is a
topology-level change the signature discipline already surfaces, never a
silent remap.

The signature path NEVER calls this module (Codex1 B1.5 — no recursion).
"""
from __future__ import annotations

import math
from typing import Any

from aiadra_core.transaction.boundary import TransactionError

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane
from OCP.TopAbs import TopAbs_REVERSED

from .recipe import PlaneFrame

ENGINE_OP_PREFIX = "mechanical"

PLANE_AXIS_PROJECTION_TOL = 1e-6
FRAME_ORTHONORMAL_TOL = 1e-9

_GLOBAL_AXES = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def _dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(a) -> float:
    return math.sqrt(_dot(a, a))


def resolve_face_plane(
    prefix_features: list[dict[str, Any]],
    plane_record: dict[str, Any],
    *,
    op_kind: str = "mechanical.sketch-plane",
) -> PlaneFrame:
    """Resolve a `{kind:'face'}` plane record against the parent prefix.

    Typed refusals (three DISTINCT recovery paths — Codex1 non-blocker 3):
    stale parent signature ("parent topology changed"), missing/ambiguous
    face ("stale selection"), and non-planar ("not planar").
    """
    from . import topology  # local import — topology imports recipe; no cycle

    stored_sig = plane_record.get("resolved_against_topology_signature")
    current_sig = topology.compute_topology_signature(prefix_features)
    if stored_sig != current_sig:
        raise TransactionError(
            f"{op_kind}: the sketch's face binding is STALE — the parent topology "
            f"skeleton changed since the face was picked (stored {stored_sig!r}, "
            f"current {current_sig!r}). Re-pick the sketch plane."
        )

    topo = topology.extract_part_topology(prefix_features)
    role = plane_record["face_role"]
    matches = [f for f in topo.faces if f.face_id == role]
    if not matches:
        raise TransactionError(
            f"{op_kind}: the sketch's support face {role!r} no longer exists on the "
            f"parent solid (stale selection — the producing feature was removed or "
            f"no longer yields this role). Re-pick the sketch plane."
        )
    if len(matches) > 1:
        raise TransactionError(
            f"{op_kind}: the sketch's support face role {role!r} is AMBIGUOUS on the "
            f"parent solid ({len(matches)} faces) — refusing to guess."
        )
    match = matches[0]
    if match.surface_kind != "plane":
        raise TransactionError(
            f"{op_kind}: the sketch's support face {role!r} is NOT PLANAR "
            f"({match.surface_kind}) — a sketch lies on a flat face; pick a "
            f"planar face or a datum plane."
        )

    surf = BRepAdaptor_Surface(match.face)
    # Codex7 B2: the resolver INDEPENDENTLY establishes exact OCCT planarity —
    # never trusting only the transported classification (fail closed).
    if surf.GetType() != GeomAbs_Plane:
        raise TransactionError(
            f"{op_kind}: the sketch's support face {role!r} is NOT PLANAR "
            f"(kernel surface type {int(surf.GetType())}) — a sketch lies on a "
            f"flat face; pick a planar face or a datum plane."
        )
    pln = surf.Plane()
    ax = pln.Axis().Direction()
    n = (ax.X(), ax.Y(), ax.Z())
    if match.face.Orientation() == TopAbs_REVERSED:
        n = (-n[0], -n[1], -n[2])

    u_axis: tuple[float, float, float] | None = None
    for g in _GLOBAL_AXES:
        gn = _dot(g, n)
        proj = (g[0] - gn * n[0], g[1] - gn * n[1], g[2] - gn * n[2])
        m = _norm(proj)
        if m > PLANE_AXIS_PROJECTION_TOL:
            u_axis = (proj[0] / m, proj[1] / m, proj[2] / m)
            break
    if u_axis is None:  # impossible for a unit normal — loud, never a fallback
        raise TransactionError(
            f"{op_kind}: no global axis projects onto the face plane above "
            f"{PLANE_AXIS_PROJECTION_TOL} — the resolved normal {n!r} is degenerate"
        )
    v_axis = _cross(n, u_axis)

    loc = pln.Location()
    d = _dot((loc.X(), loc.Y(), loc.Z()), n)
    origin_mm = (d * n[0], d * n[1], d * n[2])

    for name, val in (
        ("|u|", abs(_norm(u_axis) - 1.0)),
        ("|v|", abs(_norm(v_axis) - 1.0)),
        ("u·v", abs(_dot(u_axis, v_axis))),
        ("u·n", abs(_dot(u_axis, n))),
        ("v·n", abs(_dot(v_axis, n))),
    ):
        if val > FRAME_ORTHONORMAL_TOL:
            raise TransactionError(
                f"{op_kind}: resolved face frame fails orthonormality ({name} off by "
                f"{val:.3e} > {FRAME_ORTHONORMAL_TOL})"
            )

    return PlaneFrame(
        orientation="face", u_axis=u_axis, v_axis=v_axis, normal=n, origin_mm=origin_mm
    )
