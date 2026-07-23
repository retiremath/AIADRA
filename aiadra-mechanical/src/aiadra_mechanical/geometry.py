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
from .arc_geometry import arc_geometry
from .profile_classify import classify_sketch, non_construction
from .recipe import (
    PlaneFrame,
    effective_plane_frame,
    extrude_sign,
    principal_frame,
    resolve_consumed_sketch,
)

from OCP.Bnd import Bnd_Box
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer, BRepFilletAPI_MakeFillet
from OCP.GC import GC_MakeArcOfCircle
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism, BRepPrimAPI_MakeRevol
from OCP.BRepTools import BRepTools_WireExplorer
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Cylinder, GeomAbs_Plane
from OCP.gp import gp_Ax1, gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Vec
from OCP.Precision import Precision
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_IN, TopAbs_SOLID
from OCP.TopExp import TopExp, TopExp_Explorer
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
    ledger: "FaceRoleLedger | None" = None


@dataclass(frozen=True)
class FaceRoleLedger:
    """ADR/0038 A4.1 (arc 20260717-2 M-identity) — the fold-wide role
    authority SCAFFOLD: `{body_head, faces, body_recipe_ids}` where every face
    of the final body carries EXACTLY ONE canonical recipe role, assigned by
    construction at the base and PROPAGATED through every mutation via OCCT
    history (A4.2 — transport evidence, never role authority).

    M-identity builds it ALONGSIDE the existing extraction for the
    by-construction paths (contour / circle-outer extrudes) and proves it
    where the final-shape hint model cannot go (stacked modifiers on hinted
    faces). M-add switches the extractor/resolvers to consume it. Rectangle
    and revolve bases stay outside the scaffold (ledger None) — the extractor
    remains their sole authority; both are outside the sequential-extrude v1
    domain (B2: a later revolve is unsupported in this slice).
    """

    body_head: str | None
    faces: tuple[tuple[TopoDS_Shape, str], ...]  # (face, canonical role)
    body_recipe_ids: tuple[str, ...]

    def roles(self) -> tuple[str, ...]:
        return tuple(role for _f, role in self.faces)


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
    from . import body_history
    # ADR/0044 A2.4/A2.6/A2.9 (Gate F2b): the evaluator's v2 lane — a 0.2.x
    # non-sketch refuses as out-of-family, a malformed v2 sketch refuses
    # specifically, and a VALID v2 sketch REGENERATES (read lifecycle:
    # solve from committed Truth, validate weak/witness agreement) and
    # contributes NO solid geometry (construction only).
    from .sketch_v2 import process_v2_at_evaluation

    process_v2_at_evaluation(features)

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
    # M-add (arc 20260717-2): SEQUENTIAL extrudes are legal — the body-chain
    # validation (`body_head`: one terminal head, linear, no incomparables) is
    # the authority a raw count check used to approximate. Revolve stays
    # single (a later revolve is unsupported in this slice, B2).
    n_revolves = sum(1 for f in features if f.get("feature_type") == "revolve")
    if n_revolves > 1:
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: a Part has {n_revolves} revolve base features; "
            f"v1 supports exactly one base creation per Part"
        )
    # ADR/0038 A4.6 (Codex5 B1): the BODY FOLD ORDER is the dependency graph —
    # derived ONCE here, validated (missing/cyclic/incomparable heads reject),
    # and used for every prefix below. Sidecar array position never orders the
    # fold; a legally permuted sidecar evaluates identically. For every recipe
    # the append-only handlers author, the projection equals the array order,
    # so all stored signatures stay byte-identical (the length-one reduction).
    head_id = body_history.body_head(features)
    fold_features: list[dict[str, Any]] = (
        list(body_history.project_body_recipe(features, head_id).features)
        if head_id is not None
        else []
    )
    # SK-C1.0 S2 (Codex1 B1.4) reframed by A4.6: EVERY face-bound sketch
    # resolves against its DEPENDENCY-CLOSED support context on EVERY
    # evaluation — the graph prefix, never an array slice (Codex5 B1). The
    # closure recursion terminates (Core + body_history reject cycles).
    for _feat in features:
        if _feat.get("feature_type") != "sketch":
            continue
        _plane = (_feat.get("adapter_payload") or {}).get("plane")
        if isinstance(_plane, dict) and _plane.get("kind") == "face":
            from . import face_frame as _face_frame

            _sketch_prefix = [
                f for f in body_history.project_body_recipe(
                    features, _feat["id"]
                ).features
                if f.get("id") != _feat.get("id")
            ]
            _face_frame.resolve_face_plane(_sketch_prefix, _plane)

    # M-add: the BASE is the FIRST body-mutating feature of the graph-ordered
    # projection; later extrudes are fold steps (never "the last extrude").
    body_steps = [f for f in fold_features if body_history.is_body_mutating(f)]
    later_extrudes = [f for f in body_steps[1:] if f.get("feature_type") == "extrude"]
    if body_steps:
        first = body_steps[0]
        if first.get("feature_type") == "extrude":
            extrude = first
        elif first.get("feature_type") == "revolve":
            revolve = first
    else:
        extrude = None
        revolve = None
    # B2: exactly-once profile consumption across ALL body features.
    _consumed: dict[str, str] = {}
    for f in body_steps:
        sid = (f.get("adapter_payload") or {}).get("sketch_feature_id")
        if isinstance(sid, str):
            if sid in _consumed:
                raise TransactionError(
                    f"{ENGINE_OP_PREFIX}: sketch {sid!r} is consumed by BOTH "
                    f"{_consumed[sid]!r} and {f.get('id')!r} — a committed profile "
                    f"is consumed by at most one solid feature"
                )
            _consumed[sid] = f.get("id")

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
    # SK-C1.0 S2: the ONE base's profile sketch cannot live on a face of the
    # solid it creates (the support would not exist before the base) — refuse
    # loudly; a face-bound sketch stays unconsumed until sequential extrudes.
    _sketch_plane = (sketch.get("adapter_payload") or {}).get("plane")
    if isinstance(_sketch_plane, dict) and _sketch_plane.get("kind") == "face":
        if base is not None:
            raise TransactionError(
                f"{ENGINE_OP_PREFIX}: the base feature consumes a FACE-BOUND sketch "
                f"{sketch.get('id')!r} — a base profile cannot lie on a face of the "
                f"solid it creates (sequential features arrive in a later arc)"
            )
        # Unconsumed face-bound preview: the binding was validated in the fold
        # loop above; the no-base display lane renders its wires from the
        # resolved frame (Display v1.2 `sketch_frames`) — no BREP here.
        return EvalResult(shape=TopoDS_Shape())
    # The effective plane frame (EP2) — validated on EVERY evaluation, so a
    # corrupt stored plane record fails loud at regeneration too.
    frame = effective_plane_frame(sketch)
    primitives = sketch.get("adapter_payload", {}).get("primitives", [])

    wall_hints: list[ProducedFaceHint] = []
    base_caps: tuple[TopoDS_Shape, TopoDS_Shape] | None = None
    try:
        if revolve is not None:
            # D-P4: v1 revolve is principal-xy-only (its axis vocabulary is the
            # global x/y in the sketch plane). Checked on the EXACT sketch.
            if frame.orientation != "xy":
                raise TransactionError(
                    f"{ENGINE_OP_PREFIX}: v1 revolve requires the sketch on the "
                    f"principal xy plane; the consumed sketch is on {frame.orientation!r}"
                )
            # SK-C0 D-C3: construction guides never participate in the profile.
            rectangle = require_simple_revolve_profile(non_construction(primitives))
            shape: TopoDS_Shape = _build_revolved_solid(rectangle, _revolve_axis(revolve))
        else:
            outer_kind, outer, circle = _outer_profile(primitives)
            if outer_kind == "none":
                if extrude is not None:
                    raise TransactionError(
                        f"{ENGINE_OP_PREFIX}: the consumed sketch has no profile "
                        f"geometry (a construction-only sketch cannot be extruded)"
                    )
                # SK-C0 D-C3: a sketch-only artifact (all-construction) — no
                # BREP; the display path renders the guides from the recipe on
                # the established no-base lane.
                return EvalResult(shape=TopoDS_Shape())
            if outer_kind == "contour":
                # arc 20260711-11 slice E: an arbitrary closed-ring profile.
                # Eval-time Class-1 re-check (Codex4 D-E3) so a stored/edited/
                # corrupt recipe fails loud before OCCT, on every regeneration.
                require_valid_contour(outer)
                if extrude is None:
                    shape = _contour_face(outer, frame)
                else:
                    depth_mm, sign = _extract_extrude(extrude, frame)
                    shape, wall_hints, base_caps = _build_contour_solid(
                        outer, depth_mm, sign, frame, wall_prefix=extrude["id"]
                    )
            elif outer_kind == "circle":
                # SK-C0 D-C2: circle-as-outer-profile — extrude → a cylinder.
                if extrude is None:
                    shape = _circle_outer_face(outer, frame)
                else:
                    depth_mm, sign = _extract_extrude(extrude, frame)
                    shape, wall_hints, base_caps = _build_circle_outer_solid(
                        outer, depth_mm, sign, frame, wall_prefix=extrude["id"]
                    )
            elif extrude is None:
                shape = _build_sketch_face(outer, circle, frame)
            else:
                depth_mm, sign = _extract_extrude(extrude, frame)
                # Codex5 B4.1: the rectangle base joins the ledger domain —
                # walls + caps by construction; a sketch-circle hole is a
                # boolean Cut whose roles PROPAGATE through the same A4.2
                # machinery the modifier fold uses (the supported modifier
                # surface lives on these bases — A4.1 forbids a fallback to a
                # separate final-shape authority).
                shape, wall_hints, base_caps = _build_rectangle_solid_ledgered(
                    outer, depth_mm, sign, frame, wall_prefix=extrude["id"]
                )
                if circle is not None:
                    shape, wall_hints, base_caps = _cut_sketch_circle_ledgered(
                        shape, wall_hints, base_caps, outer_rect=outer,
                        circle=circle, depth_mm=depth_mm, sign=sign,
                        frame=frame, extrude=extrude,
                    )
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
    # Base-wall by-construction hints (SK-C0 B2) ride the same claimed channel
    # as feature-produced faces — correlation claims them before any geometric rule.
    produced: list[ProducedFaceHint] = list(wall_hints)
    running = shape
    # A4.1 (M-identity scaffold): seed the ledger from the BY-CONSTRUCTION
    # base — every wall hint + both caps, exactly one role per face. Only the
    # by-construction paths (contour / circle-outer) carry a ledger; the
    # extractor stays the sole authority elsewhere (rectangle / revolve).
    ledger_faces: list[tuple[TopoDS_Shape, str]] | None = None
    if extrude is not None and base_caps is not None:
        ledger_faces = [
            (h.faces[0], f"{h.feature_id}:face:{h.role_base}") for h in wall_hints
        ]
        ledger_faces.append((base_caps[0], f"{extrude['id']}:face:cap_base"))
        ledger_faces.append((base_caps[1], f"{extrude['id']}:face:cap_top"))
    # Codex5 B1: the fold walks the GRAPH-NORMALIZED projection; each
    # modifier's parent prefix is the projection slice before it (identical
    # to the authoring-time closure for every append-authored recipe).
    for fold_idx, feat in enumerate(fold_features):
        ftype = feat.get("feature_type")
        if ftype == "extrude" and feat.get("id") != (extrude or {}).get("id"):
            # M-add/M-cut: a SEQUENTIAL extrude — fuse (add) or pocket (cut)
            # under the A4.8 within-face domain + each operation's own proof.
            if ledger_faces is None:
                raise TransactionError(
                    f"{ENGINE_OP_PREFIX}: a sequential extrude arrived on a body "
                    f"outside the ledger domain — unsupported (ADR/0038 A4.1)"
                )
            seq_operation = (feat.get("adapter_payload") or {}).get("operation", "add")
            if seq_operation not in ("add", "cut"):
                raise TransactionError(
                    f"{ENGINE_OP_PREFIX}: extrude operation must be 'add' or "
                    f"'cut', got {seq_operation!r}"
                )
            if seq_operation == "cut":
                running, ledger_faces, seq_hints = _apply_one_cut_extrude(
                    running, feat, features, ledger_faces
                )
            else:
                running, ledger_faces, seq_hints = _apply_one_add_extrude(
                    running, feat, features, ledger_faces
                )
            produced.extend(seq_hints)
            continue
        if ftype not in ("fillet", "chamfer", "hole"):
            continue
        if extrude is None:
            # v1 fold features (fillet/chamfer/hole) target the extrude box; they
            # are not supported on a revolve base yet (a v2 stacking concern).
            raise TransactionError(
                f"{ENGINE_OP_PREFIX}: a {ftype} requires an extruded solid (v1 does "
                f"not support {ftype} on a revolve)"
            )
        if ledger_faces is None:
            # Codex5 B4.1: a supported body mutation may NEVER proceed on a
            # ledgerless body (no silent fallback to a second authority).
            raise TransactionError(
                f"{ENGINE_OP_PREFIX}: a {ftype} arrived on a body outside the "
                f"ledger domain (rectangle+hole compound base) — unsupported "
                f"in this slice (ADR/0038 A4.1 fail-loud)"
            )
        prefix = fold_features[:fold_idx]
        if ftype == "fillet":
            running, hint, mk = _apply_one_fillet(running, prefix, feat, ledger_faces)
        elif ftype == "chamfer":
            running, hint, mk = _apply_one_chamfer(running, prefix, feat, ledger_faces)
        else:
            running, hint, mk = _apply_one_hole(running, prefix, feat, frame, ledger_faces)
        produced.append(hint)
        ledger_faces = _propagate_ledger(ledger_faces, mk, running, hint, feat)

    ledger: FaceRoleLedger | None = None
    if ledger_faces is not None:
        _validate_ledger_complete(ledger_faces, running)
        from . import body_history

        head_id = body_history.body_head(features)
        proj = (
            body_history.project_body_recipe(features, head_id)
            if head_id is not None
            else None
        )
        ledger = FaceRoleLedger(
            body_head=head_id,
            faces=tuple(ledger_faces),
            body_recipe_ids=proj.feature_ids if proj is not None else (),
        )
    return EvalResult(shape=running, produced_hints=tuple(produced), ledger=ledger)


def _propagate_ledger(
    entries: list[tuple[TopoDS_Shape, str]],
    mk,
    result_shape: TopoDS_Shape,
    hint: "ProducedFaceHint | None",
    feat: dict[str, Any],
) -> list[tuple[TopoDS_Shape, str]]:
    """A4.2 — complete history propagation through ONE body mutation, with
    OCCT history as transport evidence only: per input face use `Modified()`
    when non-empty; else drop iff `IsDeleted()`; else RETAIN the unchanged
    face when it still occurs in the result; else fail loud. A one-to-many
    split and a multi-role collision REJECT in v1 (A4.3/A4.4 bounded domain).
    The mutation's produced faces then join under the hint's role."""
    result_faces = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(result_shape, TopAbs_FACE, result_faces)
    out: list[tuple[TopoDS_Shape, str]] = []
    claimed: dict[int, str] = {}

    def claim(face: TopoDS_Shape, role: str, provenance: str) -> None:
        idx = result_faces.FindIndex(face)
        if idx == 0:
            raise TransactionError(
                f"{ENGINE_OP_PREFIX}: ledger propagation through "
                f"{feat.get('feature_type')} {feat.get('id')!r} produced a face "
                f"({provenance} of role {role!r}) that is not in the result body "
                f"(ADR/0038 A4.2)"
            )
        if idx in claimed:
            raise TransactionError(
                f"{ENGINE_OP_PREFIX}: ledger propagation through "
                f"{feat.get('feature_type')} {feat.get('id')!r} claimed one result "
                f"face for two roles ({claimed[idx]!r} and {role!r}) — the v1 "
                f"domain rejects role collisions (ADR/0038 A4.3)"
            )
        claimed[idx] = role
        out.append((face, role))

    for face, role in entries:
        modified = [TopoDS.Face_s(m) for m in mk.Modified(face)]
        if modified:
            if len(modified) > 1:
                raise TransactionError(
                    f"{ENGINE_OP_PREFIX}: {feat.get('feature_type')} "
                    f"{feat.get('id')!r} SPLIT the face of role {role!r} into "
                    f"{len(modified)} faces — outside the v1 within-face domain "
                    f"(ADR/0038 A4.3/A4.4); deferred to a later slice"
                )
            claim(modified[0], role, "Modified image")
        elif mk.IsDeleted(face):
            continue  # a lawful deletion (e.g. the tool contact face)
        else:
            # unchanged — must still occur in the result to be retained
            if result_faces.FindIndex(face) == 0:
                raise TransactionError(
                    f"{ENGINE_OP_PREFIX}: ledger propagation through "
                    f"{feat.get('feature_type')} {feat.get('id')!r} lost the face "
                    f"of role {role!r} — not modified, not deleted, not in the "
                    f"result (ADR/0038 A4.2 fails loud)"
                )
            claim(face, role, "retained face")
    if hint is None:
        # M-add: a sequential fuse produces no NEW role via a hint — the
        # tool's by-construction faces ride the propagation as entries.
        return out
    if len(hint.faces) != 1:
        # A4.4 (Codex5 B4): split identity derives from the source role's
        # canonical local frame — that discriminator is not pinned yet, and
        # raw iteration order may NEVER mint identity. Reject until it lands.
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: {feat.get('feature_type')} {feat.get('id')!r} "
            f"produced {len(hint.faces)} faces for role base "
            f"{hint.role_base!r} — multi-face produced roles are outside the "
            f"v1 domain (ADR/0038 A4.4; no iteration-order identity)"
        )
    claim(hint.faces[0], f"{hint.feature_id}:face:{hint.role_base}", "produced face")
    return out


def _validate_ledger_complete(
    entries: list[tuple[TopoDS_Shape, str]], shape: TopoDS_Shape
) -> None:
    """A4.1/A4.2 — every face of the final body carries exactly one canonical
    role; every ledger face is in the body; no face is unaccounted for."""
    fm = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, TopAbs_FACE, fm)
    seen: dict[int, str] = {}
    for face, role in entries:
        idx = fm.FindIndex(face)
        if idx == 0:
            raise TransactionError(
                f"{ENGINE_OP_PREFIX}: ledger face of role {role!r} is not a face "
                f"of the final body (ADR/0038 A4.1)"
            )
        if idx in seen:
            raise TransactionError(
                f"{ENGINE_OP_PREFIX}: final body face carries two ledger roles "
                f"({seen[idx]!r} and {role!r}) — ADR/0038 A4.3 rejects collisions"
            )
        seen[idx] = role
    if len(seen) != fm.Extent():
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: the ledger accounts for {len(seen)} of "
            f"{fm.Extent()} final body faces — every face needs exactly one "
            f"canonical role (ADR/0038 A4.1 fails loud)"
        )


def _volume(shape: TopoDS_Shape) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return props.Mass()


# A4.8 (arc 20260717-2 M-add): the PINNED scale-aware strict-interior
# clearance — the absolute floor plus a fraction of the support's diagonal.
STRICT_INTERIOR_FLOOR_MM = 1e-4
STRICT_INTERIOR_DIAG_FRACTION = 1e-5


def _require_strict_interior(contact_face, support_face, ext_id: str) -> None:
    """A4.8 pre-check: the tool footprint lies STRICTLY INTERIOR to the one
    planar support face — its centroid classifies IN, and its distance to
    every boundary edge of the support meets the pinned scale-aware
    clearance. (The post-boolean history proof remains the authority — this
    precheck cannot predict every collision along the extrusion path.)"""
    bbox = Bnd_Box()
    BRepBndLib.Add_s(support_face, bbox)
    v = bbox.Get()
    diag = math.sqrt((v[3] - v[0]) ** 2 + (v[4] - v[1]) ** 2 + (v[5] - v[2]) ** 2)
    clearance = max(STRICT_INTERIOR_FLOOR_MM, STRICT_INTERIOR_DIAG_FRACTION * diag)
    # centroid classification (fail closed on anything but IN)
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(contact_face, props)
    centroid = props.CentreOfMass()
    classifier = BRepClass_FaceClassifier()
    classifier.Perform(TopoDS.Face_s(support_face), centroid, CONFUSION_TOLERANCE_MM)
    if classifier.State() != TopAbs_IN:
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: sequential extrude {ext_id!r} — the tool "
            f"footprint is not strictly interior to its support face "
            f"(ADR/0038 A4.8; the within-face v1 domain)"
        )
    # boundary clearance
    edge_exp = TopExp_Explorer(support_face, TopAbs_EDGE)
    while edge_exp.More():
        dist = BRepExtrema_DistShapeShape(contact_face, edge_exp.Current())
        # Codex9 B1: an INCOMPLETE distance query fails CLOSED — this is the
        # only check enforcing the pinned positive clearance, and the
        # post-boolean proof cannot reconstruct a missed metric distance.
        if not dist.IsDone():
            raise TransactionError(
                f"{ENGINE_OP_PREFIX}: sequential extrude {ext_id!r} — a support-"
                f"boundary clearance query did not complete; refusing rather "
                f"than skipping the pinned A4.8 strict-interior check"
            )
        if dist.Value() < clearance:
            raise TransactionError(
                f"{ENGINE_OP_PREFIX}: sequential extrude {ext_id!r} — the tool "
                f"footprint comes within {dist.Value():.6f}mm of the support "
                f"boundary (clearance {clearance:.6f}mm; ADR/0038 A4.8 strict "
                f"interior). Faces that touch or straddle the boundary are a "
                f"later slice."
            )
        edge_exp.Next()


def _assert_add_survival(
    fuse,
    ledger_entries: list[tuple[TopoDS_Shape, str]],
    tool_hints: list["ProducedFaceHint"],
    tool_caps: tuple[TopoDS_Shape, TopoDS_Shape],
    support_face: TopoDS_Shape,
    ext_id,
) -> None:
    """Codex9 B2 — the A4.8 ADD-specific survival proof, STRICTER than the
    generic A4.2 transport (which lawfully drops any IsDeleted face):

      - the tool CONTACT cap must report `IsDeleted` AND ZERO `Modified`
        images (contradictory history evidence rejects);
      - EVERY prior owned body face must be non-deleted (the support's
        exactly-one-image rule is asserted separately);
      - EVERY intended tool wall and the far cap must be non-deleted.

    `_propagate_ledger` remains the one transport loop for splits,
    collisions, result membership, and completeness — this is an
    add-specific pre/postcondition over the same faces."""
    contact = tool_caps[0]
    if list(fuse.Modified(contact)):
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: sequential extrude {ext_id!r} — CONTRADICTORY "
            f"history: the tool contact face reports Modified images while it "
            f"must delete (ADR/0038 A4.8)"
        )
    if not fuse.IsDeleted(contact):
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: sequential extrude {ext_id!r} — the tool "
            f"contact face did not delete (the footprint is not flush-interior "
            f"on the support; ADR/0038 A4.8)"
        )
    for face, role in ledger_entries:
        if fuse.IsDeleted(face):
            raise TransactionError(
                f"{ENGINE_OP_PREFIX}: sequential extrude {ext_id!r} — the fuse "
                f"DELETED owned body face {role!r}; an accepted within-face add "
                f"preserves every prior owned face (ADR/0038 A4.8)"
            )
    for h in tool_hints:
        if fuse.IsDeleted(h.faces[0]):
            raise TransactionError(
                f"{ENGINE_OP_PREFIX}: sequential extrude {ext_id!r} — the fuse "
                f"DELETED intended tool face {h.feature_id}:face:{h.role_base}; "
                f"every tool wall must survive (ADR/0038 A4.8)"
            )
    if fuse.IsDeleted(tool_caps[1]):
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: sequential extrude {ext_id!r} — the fuse "
            f"DELETED the tool's far cap; it must survive (ADR/0038 A4.8)"
        )


def _assert_cut_survival(
    cut,
    ledger_entries: list[tuple[TopoDS_Shape, str]],
    tool_hints: list["ProducedFaceHint"],
    tool_caps: tuple[TopoDS_Shape, TopoDS_Shape],
    support_face: TopoDS_Shape,
    ext_id,
) -> None:
    """M-cut (ADR/0038 A4.8, the CUT half — spike-pinned): the blind pocket's
    survival proof, STRICTER than add's on the body side:

      - the tool CONTACT cap (the opening) must report `IsDeleted` AND ZERO
        `Modified` images;
      - EVERY prior owned body face EXCEPT the support must be RETAINED
        IDENTICALLY — neither deleted NOR modified (a blind pocket touches
        only its support face; a through-cut or overshoot modifies the far
        side and refuses HERE);
      - every intended tool wall (the pocket walls) and the far cap (the
        pocket bottom) must be non-deleted.

    `_propagate_ledger` remains the one transport loop."""
    contact = tool_caps[0]
    if list(cut.Modified(contact)):
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: sequential cut {ext_id!r} — CONTRADICTORY "
            f"history: the tool contact face reports Modified images while it "
            f"must delete (ADR/0038 A4.8)"
        )
    if not cut.IsDeleted(contact):
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: sequential cut {ext_id!r} — the tool contact "
            f"face did not delete (the pocket opening is not flush-interior on "
            f"the support; ADR/0038 A4.8)"
        )
    for face, role in ledger_entries:
        if face is support_face:
            # Codex12 B1: the support is exempt ONLY from the Modified-must-
            # be-empty rule (its exactly-one-image count is asserted at the
            # call site) — its DELETION evidence is still checked: one
            # Modified image AND IsDeleted is contradictory history, and the
            # Modified-first generic transport must never decide this proof.
            if cut.IsDeleted(face):
                raise TransactionError(
                    f"{ENGINE_OP_PREFIX}: sequential cut {ext_id!r} — "
                    f"CONTRADICTORY history: the support face {role!r} reports "
                    f"a Modified image while ALSO reporting deleted "
                    f"(ADR/0038 A4.8 exact one-to-one evidence)"
                )
            continue
        if cut.IsDeleted(face):
            raise TransactionError(
                f"{ENGINE_OP_PREFIX}: sequential cut {ext_id!r} — the cut "
                f"DELETED owned body face {role!r}; a blind pocket touches only "
                f"its support face (ADR/0038 A4.8)"
            )
        if list(cut.Modified(face)):
            raise TransactionError(
                f"{ENGINE_OP_PREFIX}: sequential cut {ext_id!r} — the cut "
                f"MODIFIED owned body face {role!r}; a blind pocket touches only "
                f"its support face (a through-cut or overshoot; deeper cuts are "
                f"a later slice — ADR/0038 A4.8)"
            )
    for h in tool_hints:
        if cut.IsDeleted(h.faces[0]):
            raise TransactionError(
                f"{ENGINE_OP_PREFIX}: sequential cut {ext_id!r} — the cut "
                f"DELETED intended pocket wall {h.feature_id}:face:{h.role_base}; "
                f"every pocket wall must survive (ADR/0038 A4.8)"
            )
    if cut.IsDeleted(tool_caps[1]):
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: sequential cut {ext_id!r} — the cut DELETED "
            f"the pocket bottom; it must survive (a blind pocket ends inside "
            f"the material — ADR/0038 A4.8)"
        )


def _resolve_sequential_tool(
    ext: dict[str, Any],
    features: list[dict[str, Any]],
    ledger_entries: list[tuple[TopoDS_Shape, str]],
    *,
    sign: float,
    expect_direction: str,
    wrong_direction_msg: str,
) -> tuple[TopoDS_Shape, list["ProducedFaceHint"], tuple[TopoDS_Shape, TopoDS_Shape], TopoDS_Shape]:
    """The SHARED sequential-tool resolution (M-add extracted for M-cut): the
    face-bound consumed sketch, the frame from its dependency closure, the
    tool from the same by-construction builders (`sign` orients the sweep),
    the support from the LIVE ledger, and the A4.8 strict-interior precheck.
    The operation-specific PROOFS stay with each caller."""
    from . import body_history, face_frame

    ext_id = ext.get("id")
    sketch = resolve_consumed_sketch(features, ext)
    plane = (sketch.get("adapter_payload") or {}).get("plane")
    if not (isinstance(plane, dict) and plane.get("kind") == "face"):
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: sequential extrude {ext_id!r} consumes a "
            f"datum-bound sketch — v1 sequential extrudes consume a FACE-BOUND "
            f"sketch (the support anchors the within-face domain); datum-plane "
            f"sequential extrudes are a later slice"
        )
    payload = ext.get("adapter_payload") or {}
    direction = payload.get("direction", "normal+")
    if direction not in ("normal+", "normal-"):
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: sequential extrude {ext_id!r} direction must be "
            f"canonical normal± (legacy z± is principal-xy-only), got {direction!r}"
        )
    if direction != expect_direction:
        raise TransactionError(wrong_direction_msg)
    depth_mm: float | None = None
    for param in ext.get("parameters", []):
        if param.get("name") == "depth_mm":
            depth_mm = float(param["value"])
            break
    if depth_mm is None or depth_mm <= 0:
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: sequential extrude {ext_id!r} needs a positive "
            f"'depth_mm' parameter, got {depth_mm!r}"
        )

    # the frame from the sketch's dependency-closed support prefix (A4.5)
    sk_prefix = [
        f for f in body_history.project_body_recipe(features, sketch["id"]).features
        if f.get("id") != sketch.get("id")
    ]
    frame = face_frame.resolve_face_plane(sk_prefix, plane)

    # the tool solid — the SAME by-construction builders as a base
    primitives = (sketch.get("adapter_payload") or {}).get("primitives", [])
    outer_kind, outer, circle = _outer_profile(non_construction(primitives))
    if outer_kind == "none":
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: sequential extrude {ext_id!r} — the consumed "
            f"sketch has no profile geometry (a construction-only sketch cannot "
            f"be extruded)"
        )
    if outer_kind == "contour":
        require_valid_contour(outer)
        tool, tool_hints, tool_caps = _build_contour_solid(
            outer, depth_mm, sign, frame, wall_prefix=ext_id
        )
    elif outer_kind == "circle":
        tool, tool_hints, tool_caps = _build_circle_outer_solid(
            outer, depth_mm, sign, frame, wall_prefix=ext_id
        )
    else:
        if circle is not None:
            raise TransactionError(
                f"{ENGINE_OP_PREFIX}: sequential extrude {ext_id!r} — a "
                f"rectangle+circle compound profile is not a supported tool "
                f"(draw the hole as a later cut)"
            )
        tool, tool_hints, tool_caps = _build_rectangle_solid_ledgered(
            outer, depth_mm, sign, frame, wall_prefix=ext_id
        )

    # the support face from the LIVE ledger (A4.5 — never re-correlation)
    support_role = plane["face_role"]
    support = [f for f, r in ledger_entries if r == support_role]
    if len(support) != 1:
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: sequential extrude {ext_id!r} — support face "
            f"{support_role!r} resolves to {len(support)} ledger faces "
            f"(exactly-one-or-loud, ADR/0038 D4)"
        )

    # A4.8 pre-check (each caller's history proof remains the authority)
    _require_strict_interior(tool_caps[0], support[0], ext_id)
    return tool, tool_hints, tool_caps, support[0]


def _apply_one_add_extrude(
    running: TopoDS_Shape,
    ext: dict[str, Any],
    features: list[dict[str, Any]],
    ledger_entries: list[tuple[TopoDS_Shape, str]],
) -> tuple[TopoDS_Shape, list[tuple[TopoDS_Shape, str]], list[ProducedFaceHint]]:
    """M-add (ADR/0038 A4.8): fuse one sequential ADD extrude onto the body.

    The consumed sketch must be FACE-BOUND (its support face anchors the
    within-face domain); the tool builds from the SAME by-construction
    builders as a base; the strict-interior precheck gates entry; the
    POST-BOOLEAN HISTORY PROOF is the authority (support 1:1, tool contact
    deleted, one solid, exactly-additive volume); the ledger propagates
    through the fuse via the one A4.2 loop."""
    from . import body_history, face_frame

    ext_id = ext.get("id")
    tool, tool_hints, tool_caps, support0 = _resolve_sequential_tool(
        ext, features, ledger_entries, sign=1.0,
        expect_direction="normal+",
        wrong_direction_msg=(
            f"{ENGINE_OP_PREFIX}: an ADD extrude sweeps AWAY from the body "
            f"(direction 'normal+' along the support's outward normal); "
            f"removing material is operation 'cut' — operation is never "
            f"inferred from direction"
        ),
    )
    support = [support0]

    before_vol = _volume(running)
    tool_vol = _volume(tool)
    try:
        fuse = BRepAlgoAPI_Fuse(running, tool)
        result = fuse.Shape()
    except (TransactionError, MechanicalKernelEvaluationError):
        raise
    except Exception as exc:
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: sequential extrude {ext_id!r} fuse failed: {exc!r}"
        ) from exc
    _assert_valid(result, f"sequential extrude {ext_id!r}")

    # ---- A4.8 POST-BOOLEAN HISTORY PROOF (the authority) ----
    support_mods = list(fuse.Modified(support[0]))
    if len(support_mods) != 1:
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: sequential extrude {ext_id!r} — the support "
            f"face mapped to {len(support_mods)} result faces (exactly one "
            f"required; ADR/0038 A4.8)"
        )
    # Codex9 B2: the ADD-specific survival proof (stricter than the generic
    # transport) — contact exact-deletion, no owned-face loss, all tool
    # walls + the far cap surviving.
    _assert_add_survival(fuse, ledger_entries, tool_hints, tool_caps, support[0], ext_id)
    n_solids = 0
    solid_exp = TopExp_Explorer(result, TopAbs_SOLID)
    while solid_exp.More():
        n_solids += 1
        solid_exp.Next()
    if n_solids != 1:
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: sequential extrude {ext_id!r} produced "
            f"{n_solids} solids — an add must end in exactly one connected "
            f"solid (ADR/0038 A4.8)"
        )
    result_vol = _volume(result)
    vol_tol = max(1e-6, 1e-6 * tool_vol)
    if abs(result_vol - (before_vol + tool_vol)) > vol_tol:
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: sequential extrude {ext_id!r} — the fused "
            f"volume {result_vol:.6f} is not exactly additive "
            f"({before_vol:.6f} + {tool_vol:.6f}; the strictly-interior outward "
            f"tool must add its own volume; ADR/0038 A4.8)"
        )

    # ---- the ledger rides the fuse (the ONE A4.2 loop) ----
    tool_entries: list[tuple[TopoDS_Shape, str]] = [
        (h.faces[0], f"{h.feature_id}:face:{h.role_base}") for h in tool_hints
    ]
    tool_entries.append((tool_caps[0], f"{ext_id}:face:cap_base"))
    tool_entries.append((tool_caps[1], f"{ext_id}:face:cap_top"))
    new_entries = _propagate_ledger(
        list(ledger_entries) + tool_entries, fuse, result, None, ext
    )
    return result, new_entries, list(tool_hints)


def _apply_one_cut_extrude(
    running: TopoDS_Shape,
    ext: dict[str, Any],
    features: list[dict[str, Any]],
    ledger_entries: list[tuple[TopoDS_Shape, str]],
) -> tuple[TopoDS_Shape, list[tuple[TopoDS_Shape, str]], list[ProducedFaceHint]]:
    """M-cut (ADR/0038 A4.8, the CUT half — spike-pinned): cut one sequential
    BLIND POCKET into the body. Shares the sequential-tool resolution with
    add (`sign=-1`: the tool sweeps INTO the body along −support-normal);
    defines its OWN proof (Codex11's inheritance boundary): only the support
    is modified (exactly 1:1), the contact deletes exactly, every other body
    face is RETAINED IDENTICALLY, the pocket walls + bottom survive, one
    non-empty solid remains, and the volume DECREASES by exactly the tool
    volume (blind containment proven post-hoc — a through-cut or overshoot
    violates both the retained rule and the volume identity)."""
    ext_id = ext.get("id")
    tool, tool_hints, tool_caps, support0 = _resolve_sequential_tool(
        ext, features, ledger_entries, sign=-1.0,
        expect_direction="normal-",
        wrong_direction_msg=(
            f"{ENGINE_OP_PREFIX}: a CUT extrude removes material INTO the body "
            f"(direction 'normal-' against the support's outward normal); "
            f"adding outward material is operation 'add' — operation is never "
            f"inferred from direction"
        ),
    )

    before_vol = _volume(running)
    tool_vol = _volume(tool)
    try:
        cut = BRepAlgoAPI_Cut(running, tool)
        result = cut.Shape()
    except (TransactionError, MechanicalKernelEvaluationError):
        raise
    except Exception as exc:
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: sequential cut {ext_id!r} failed: {exc!r}"
        ) from exc
    _assert_valid(result, f"sequential cut {ext_id!r}")

    # ---- the A4.8 CUT proof (the authority) ----
    support_mods = list(cut.Modified(support0))
    if len(support_mods) != 1:
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: sequential cut {ext_id!r} — the support face "
            f"mapped to {len(support_mods)} result faces (exactly one required; "
            f"ADR/0038 A4.8)"
        )
    _assert_cut_survival(cut, ledger_entries, tool_hints, tool_caps, support0, ext_id)
    n_solids = 0
    solid_exp = TopExp_Explorer(result, TopAbs_SOLID)
    while solid_exp.More():
        n_solids += 1
        solid_exp.Next()
    if n_solids != 1:
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: sequential cut {ext_id!r} produced "
            f"{n_solids} solids — a cut must leave exactly one non-empty solid "
            f"(ADR/0038 A4.8)"
        )
    result_vol = _volume(result)
    vol_tol = max(1e-6, 1e-6 * tool_vol)
    if abs((before_vol - result_vol) - tool_vol) > vol_tol:
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: sequential cut {ext_id!r} — the removed "
            f"volume {before_vol - result_vol:.6f} is not exactly the tool "
            f"volume {tool_vol:.6f}; the pocket must stay BLIND inside the "
            f"material (a through-cut or overshoot; deeper cuts are a later "
            f"slice — ADR/0038 A4.8)"
        )

    # ---- the ledger rides the cut (the ONE A4.2 loop) ----
    tool_entries: list[tuple[TopoDS_Shape, str]] = [
        (h.faces[0], f"{h.feature_id}:face:{h.role_base}") for h in tool_hints
    ]
    tool_entries.append((tool_caps[0], f"{ext_id}:face:cap_base"))
    tool_entries.append((tool_caps[1], f"{ext_id}:face:cap_top"))
    new_entries = _propagate_ledger(
        list(ledger_entries) + tool_entries, cut, result, None, ext
    )
    return result, new_entries, list(tool_hints)


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


def _apply_one_fillet(running, prefix, fillet, ledger_entries=None):
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
    edge = topology.resolve_edge_on_shape(
        running, prefix, roles, kind, ledger_entries=ledger_entries
    )
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
    return filleted, ProducedFaceHint(feature_id=fillet["id"], role_base="blend", faces=generated), mk


def _apply_one_chamfer(running, prefix, chamfer, ledger_entries=None):
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
    edge = topology.resolve_edge_on_shape(
        running, prefix, roles, kind, ledger_entries=ledger_entries
    )
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
    return chamfered, ProducedFaceHint(feature_id=chamfer["id"], role_base="chamfer", faces=generated), mk


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


def _apply_one_hole(running, prefix, hole, frame: PlaneFrame, ledger_entries=None):
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
    face = topology.resolve_face_on_shape(
        running, prefix, role, ledger_entries=ledger_entries
    )
    diameter = _hole_param(hole, "diameter_mm", positive=True)
    cx = _hole_param(hole, "center_x_mm")
    cy = _hole_param(hole, "center_y_mm")
    # Codex2 B1: enforce the v1 simple-cap + fit-within-face DOMAIN contract on
    # EVERY regeneration / parameter-edit path (not only the handler's initial
    # add), so an edited centre/diameter that breaches the cap fails Class-1
    # before the kernel — never a side-breaching cut or a Class-2 surprise.
    from .adapter_payload import require_simple_cap_fit

    require_simple_cap_fit(prefix, cx, cy, diameter / 2.0)
    holed, wall, mk = _cut_through_hole(running, cx, cy, face, diameter, hole.get("id"), frame)
    return holed, ProducedFaceHint(feature_id=hole["id"], role_base="hole_wall", faces=wall), mk


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
    return holed, wall, cut


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
    # SK-C0 Codex3 B2: THE classifier is the one whole-list authority.
    cls = classify_sketch(primitives)
    if cls.outer_kind != "rectangle" or cls.hole_index is not None:
        raise TransactionError(
            f"{ENGINE_OP_PREFIX}: v1 revolve requires a SIMPLE profile of exactly one "
            f"rectangle (no circles, lines, or extra rectangles); got outer "
            f"{cls.outer_kind!r}"
            + (" with a circle hole" if cls.hole_index is not None else "")
        )
    return primitives[cls.outer_index]


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


def _build_rectangle_solid_ledgered(
    rectangle: dict[str, Any], depth_mm: float, sign: float, frame: PlaneFrame,
    *, wall_prefix: str,
) -> tuple[TopoDS_Shape, list["ProducedFaceHint"], tuple[TopoDS_Shape, TopoDS_Shape]]:
    """Codex5 B4.1: the plain-rectangle base built WITH by-construction wall
    authority — each authored side edge maps to its wall via
    `MakePrism.Generated(edge)` and its side name comes from construction
    (p1→p2 = y_min, p2→p3 = x_max, p3→p4 = y_max, p4→p1 = x_min in sketch-
    local (u, v)), matching the extractor's geometric naming exactly. Caps by
    `FirstShape`/`LastShape` as in every ledgered path."""
    u = float(rectangle["x_mm"])
    v = float(rectangle["y_mm"])
    w = float(rectangle["width_mm"])
    h = float(rectangle["height_mm"])
    from . import topology  # lazy: topology imports geometry at module top

    rect_skp = topology.require_skp_id(rectangle, "rectangle")
    c1, c2, c3, c4 = (u, v), (u + w, v), (u + w, v + h), (u, v + h)
    side_by_corners = {
        frozenset((c1, c2)): "y_min",
        frozenset((c2, c3)): "x_max",
        frozenset((c3, c4)): "y_max",
        frozenset((c4, c1)): "x_min",
    }
    wire_mk = BRepBuilderAPI_MakeWire()
    for a, b in ((c1, c2), (c2, c3), (c3, c4), (c4, c1)):
        wire_mk.Add(BRepBuilderAPI_MakeEdge(
            gp_Pnt(*frame.to_3d(*a)), gp_Pnt(*frame.to_3d(*b))
        ).Edge())
    wire = wire_mk.Wire()
    face = BRepBuilderAPI_MakeFace(wire).Face()
    prism = BRepPrimAPI_MakePrism(face, _normal_vec(frame, sign * depth_mm))
    shape = prism.Shape()
    # MakeWire may re-orient/copy edges while chaining the ring (the contour
    # builder's documented behavior) — query Generated() with the WIRE'S OWN
    # edges and pair each back to its side by exact endpoints.
    hints: list[ProducedFaceHint] = []
    tol = 1e-6
    exp = BRepTools_WireExplorer(wire)
    seen_sides: set[str] = set()
    while exp.More():
        edge = TopoDS.Edge_s(exp.Current())
        exp.Next()
        va = BRep_Tool.Pnt_s(TopExp.FirstVertex_s(edge))
        vb = BRep_Tool.Pnt_s(TopExp.LastVertex_s(edge))
        a_uv = frame.project_uv((va.X(), va.Y(), va.Z()))
        b_uv = frame.project_uv((vb.X(), vb.Y(), vb.Z()))
        side = None
        for corners, name in side_by_corners.items():
            ca, cb = tuple(corners)
            fwd = (math.hypot(a_uv[0] - ca[0], a_uv[1] - ca[1]) <= tol
                   and math.hypot(b_uv[0] - cb[0], b_uv[1] - cb[1]) <= tol)
            rev = (math.hypot(a_uv[0] - cb[0], a_uv[1] - cb[1]) <= tol
                   and math.hypot(b_uv[0] - ca[0], b_uv[1] - ca[1]) <= tol)
            if fwd or rev:
                side = name
                break
        if side is None or side in seen_sides:
            raise MechanicalKernelEvaluationError(
                f"{ENGINE_OP_PREFIX}: rectangle wire edge could not be paired to "
                f"exactly one side (by-construction identity bookkeeping)"
            )
        seen_sides.add(side)
        gen = [TopoDS.Face_s(g) for g in prism.Generated(edge)]
        if len(gen) != 1:
            raise MechanicalKernelEvaluationError(
                f"{ENGINE_OP_PREFIX}: rectangle side {side} generated {len(gen)} "
                f"wall faces (expected exactly one; by-construction authority)"
            )
        hints.append(ProducedFaceHint(
            feature_id=f"{wall_prefix}/{rect_skp}", role_base=f"wall_{side}",
            faces=(gen[0],),
        ))
    if len(seen_sides) != 4:
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: rectangle produced {len(seen_sides)} of 4 walls "
            f"(by-construction authority)"
        )
    caps = (TopoDS.Face_s(prism.FirstShape()), TopoDS.Face_s(prism.LastShape()))
    return shape, hints, caps


def _cut_sketch_circle_ledgered(
    box: TopoDS_Shape,
    wall_hints: list["ProducedFaceHint"],
    caps: tuple[TopoDS_Shape, TopoDS_Shape],
    *,
    outer_rect: dict[str, Any],
    circle: dict[str, Any],
    depth_mm: float,
    sign: float,
    frame: PlaneFrame,
    extrude: dict[str, Any],
) -> tuple[TopoDS_Shape, list["ProducedFaceHint"], tuple[TopoDS_Shape, TopoDS_Shape]]:
    """The sketch-circle through-hole as a LEDGERED boolean: the rectangle
    base's walls/caps propagate through the Cut via the same A4.2 loop the
    modifier fold uses; the hole wall joins by construction under the legacy
    role `<extrude>/<circle-skp>:face:hole_wall`."""
    from . import topology  # lazy

    circle_skp = topology.require_skp_id(circle, "circle")
    _require_circle_inside_rectangle(outer_rect, circle)
    margin = max(1.0, depth_mm)
    cyl_face = BRepBuilderAPI_MakeFace(_circle_wire(circle, frame, w=-sign * margin)).Face()
    cylinder = BRepPrimAPI_MakePrism(
        cyl_face, _normal_vec(frame, sign * (depth_mm + 2.0 * margin))
    ).Shape()
    cut = BRepAlgoAPI_Cut(box, cylinder)
    holed = cut.Shape()
    _assert_valid(holed, "rectangle+circle base")
    wall = tuple(TopoDS.Face_s(f) for f in cut.Modified(_cylinder_lateral_face(cylinder)))
    if len(wall) != 1:
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: sketch-circle hole produced {len(wall)} wall "
            f"faces by construction (expected exactly one)"
        )
    entries = [(h.faces[0], f"{h.feature_id}:face:{h.role_base}") for h in wall_hints]
    entries.append((caps[0], f"{extrude['id']}:face:cap_base"))
    entries.append((caps[1], f"{extrude['id']}:face:cap_top"))
    hint = ProducedFaceHint(
        feature_id=f"{extrude['id']}/{circle_skp}", role_base="hole_wall",
        faces=wall,
    )
    new_entries = _propagate_ledger(entries, cut, holed, hint, extrude)
    # re-derive the hint list + caps from the propagated entries so the
    # caller's seeding logic sees post-cut faces
    out_hints: list[ProducedFaceHint] = []
    cap_base = cap_top = None
    for face, role in new_entries:
        if role == f"{extrude['id']}:face:cap_base":
            cap_base = face
        elif role == f"{extrude['id']}:face:cap_top":
            cap_top = face
        else:
            fid, role_base = role.rsplit(":face:", 1)
            out_hints.append(ProducedFaceHint(feature_id=fid, role_base=role_base, faces=(face,)))
    if cap_base is None or cap_top is None:
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: the sketch-circle cut lost a cap role "
            f"(ADR/0038 A4.2 fails loud)"
        )
    return holed, out_hints, (cap_base, cap_top)


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
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    """THE classifier verdict, materialized for the evaluator (SK-C0 B3):
    `(outer_kind, outer_primitive, circle_hole)` with outer_kind in
    rectangle|contour|circle|none. Construction primitives are excluded by the
    classifier; every unsupported combination fails loud INSIDE it."""
    cls = classify_sketch(primitives)
    outer = primitives[cls.outer_index] if cls.outer_index is not None else None
    hole = primitives[cls.hole_index] if cls.hole_index is not None else None
    return cls.outer_kind, outer, hole


def _contour_wire(contour: dict[str, Any], frame: PlaneFrame):
    """(wire, [(segment_id, edge), ...]) — one OCCT edge per authored segment,
    in ring order, on the sketch plane (EP2). SK-C0 D-C1: arc segments become
    exact circular edges via 3-point construction (the bulge midpoint from the
    shared `arc_geometry` formulas — the same math Class-1 validated)."""
    mk = BRepBuilderAPI_MakeWire()
    seg_edges: list[tuple[str, Any]] = []
    for seg in contour["segments"]:
        x1, y1 = float(seg["x1_mm"]), float(seg["y1_mm"])
        x2, y2 = float(seg["x2_mm"]), float(seg["y2_mm"])
        p1 = gp_Pnt(*frame.to_3d(x1, y1))
        p2 = gp_Pnt(*frame.to_3d(x2, y2))
        if seg.get("kind") == "arc":
            g = arc_geometry(x1, y1, x2, y2, float(seg["bulge"]))
            mid_ang = g.start_angle + g.sweep / 2.0
            pm = gp_Pnt(*frame.to_3d(
                g.center[0] + g.radius * math.cos(mid_ang),
                g.center[1] + g.radius * math.sin(mid_ang),
            ))
            edge = BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(p1, pm, p2).Value()).Edge()
        else:
            edge = BRepBuilderAPI_MakeEdge(p1, p2).Edge()
        seg_edges.append((seg.get("id"), edge))
        mk.Add(edge)
    return mk.Wire(), seg_edges


def _contour_face(contour: dict[str, Any], frame: PlaneFrame) -> TopoDS_Shape:
    """A planar face from an explicit CLOSED RING of typed segments (line/arc).
    The segments already close the ring (Codex4 B1 — no implicit closing edge)."""
    return BRepBuilderAPI_MakeFace(_contour_wire(contour, frame)[0]).Face()


def _build_contour_solid(
    contour: dict[str, Any], depth_mm: float, sign: float, frame: PlaneFrame,
    *, wall_prefix: str,
) -> tuple[TopoDS_Shape, list["ProducedFaceHint"], tuple[TopoDS_Shape, TopoDS_Shape]]:
    """Prism a contour face into a solid + the BY-CONSTRUCTION wall authority
    (SK-C0 B2): the evaluator built each OCCT edge FROM its authored segment, so
    `MakePrism.Generated(edge)` IS the segment→wall mapping — exactly one face
    per segment or loud. Geometry then VERIFIES the surface family/radius (it
    never selects). Radius+axis matching is dead as a correlation key."""
    wire, _built_edges = _contour_wire(contour, frame)
    face = BRepBuilderAPI_MakeFace(wire).Face()
    prism = BRepPrimAPI_MakePrism(face, _normal_vec(frame, sign * depth_mm))
    shape = prism.Shape()
    # MakeWire may re-orient/copy edges while chaining the ring, so Generated()
    # must be queried with the WIRE'S OWN edges. Each wire edge is paired back
    # to its authored segment by EXACT endpoint (+kind) matching — unambiguous
    # for a valid Class-1 ring, and fail-loud otherwise (still by-construction:
    # the pairing is identity bookkeeping, never geometric guessing of ROLES).
    hints: list[ProducedFaceHint] = []
    matched: set[int] = set()
    exp = BRepTools_WireExplorer(wire)
    wire_edges = []
    while exp.More():
        wire_edges.append(TopoDS.Edge_s(exp.Current()))
        exp.Next()
    if len(wire_edges) != len(contour["segments"]):
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: contour wire has {len(wire_edges)} edges for "
            f"{len(contour['segments'])} segments (SK-C0 B2)"
        )
    for edge in wire_edges:
        sid, seg = _segment_for_edge(edge, contour["segments"], frame, matched)
        gen = [TopoDS.Face_s(s) for s in prism.Generated(edge)]
        if len(gen) != 1:
            raise MechanicalKernelEvaluationError(
                f"{ENGINE_OP_PREFIX}: contour segment {sid!r} generated "
                f"{len(gen)} wall faces (expected exactly one; SK-C0 B2 "
                f"by-construction wall authority)"
            )
        _verify_wall_family(gen[0], seg, sid)
        hints.append(ProducedFaceHint(
            feature_id=f"{wall_prefix}/{sid}", role_base="wall", faces=(gen[0],)
        ))
    # A4.1: the caps BY CONSTRUCTION — the profile face (FirstShape, on the
    # sketch plane, coordinate 0 = cap_base regardless of sweep sign) and the
    # swept face (LastShape = cap_top). Ledger material; the extractor's
    # geometric cap branch is untouched in M-identity.
    caps = (TopoDS.Face_s(prism.FirstShape()), TopoDS.Face_s(prism.LastShape()))
    return shape, hints, caps


def _segment_for_edge(edge, segments, frame: PlaneFrame, matched: set[int]):
    """Pair one wire edge back to its authored segment by exact endpoints
    (either direction) + curve kind. Exactly one unmatched candidate or loud."""
    v1 = BRep_Tool.Pnt_s(TopExp.FirstVertex_s(edge))
    v2 = BRep_Tool.Pnt_s(TopExp.LastVertex_s(edge))
    a = frame.project_uv((v1.X(), v1.Y(), v1.Z()))
    b = frame.project_uv((v2.X(), v2.Y(), v2.Z()))
    ekind = "arc" if BRepAdaptor_Curve(edge).GetType() == GeomAbs_Circle else "line"
    tol = 1e-6
    candidates = []
    for k, seg in enumerate(segments):
        if k in matched or seg.get("kind", "line") != ekind:
            continue
        s = (float(seg["x1_mm"]), float(seg["y1_mm"]))
        e = (float(seg["x2_mm"]), float(seg["y2_mm"]))
        fwd = math.hypot(a[0]-s[0], a[1]-s[1]) <= tol and math.hypot(b[0]-e[0], b[1]-e[1]) <= tol
        rev = math.hypot(a[0]-e[0], a[1]-e[1]) <= tol and math.hypot(b[0]-s[0], b[1]-s[1]) <= tol
        if fwd or rev:
            candidates.append(k)
    if len(candidates) != 1:
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: wire edge could not be paired to exactly one "
            f"contour segment (candidates={len(candidates)}); SK-C0 B2 identity "
            f"bookkeeping failed loud"
        )
    matched.add(candidates[0])
    seg = segments[candidates[0]]
    return seg.get("id"), seg


def _verify_wall_family(face, seg: dict[str, Any], sid) -> None:
    """By-construction VERIFICATION (never selection): a line segment's wall is
    a plane; an arc segment's wall is a cylinder with the segment's exact radius."""
    surf = BRepAdaptor_Surface(face)
    stype = surf.GetType()
    if seg.get("kind") == "arc":
        if stype != GeomAbs_Cylinder:
            raise MechanicalKernelEvaluationError(
                f"{ENGINE_OP_PREFIX}: contour arc segment {sid!r} produced a "
                f"non-cylindrical wall (surface type {stype}); by-construction "
                f"verification failed"
            )
        g = arc_geometry(
            float(seg["x1_mm"]), float(seg["y1_mm"]),
            float(seg["x2_mm"]), float(seg["y2_mm"]), float(seg["bulge"]),
        )
        r_occt = surf.Cylinder().Radius()
        if abs(r_occt - g.radius) > 1e-6:
            raise MechanicalKernelEvaluationError(
                f"{ENGINE_OP_PREFIX}: contour arc segment {sid!r} wall radius "
                f"{r_occt} does not verify against the recipe radius {g.radius}"
            )
    elif stype != GeomAbs_Plane:
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: contour line segment {sid!r} produced a "
            f"non-planar wall (surface type {stype}); by-construction "
            f"verification failed"
        )


def _circle_outer_face(circle: dict[str, Any], frame: PlaneFrame) -> TopoDS_Shape:
    """The full disk of a circle-as-outer-profile sketch (SK-C0 D-C2)."""
    return BRepBuilderAPI_MakeFace(_circle_wire(circle, frame)).Face()


def _build_circle_outer_solid(
    circle: dict[str, Any], depth_mm: float, sign: float, frame: PlaneFrame,
    *, wall_prefix: str,
) -> tuple[TopoDS_Shape, list["ProducedFaceHint"], tuple[TopoDS_Shape, TopoDS_Shape]]:
    """Prism a circle-outer disk into a cylinder (SK-C0 D-C2). The lateral wall
    is claimed BY CONSTRUCTION via `Generated(circle edge)` with the pinned role
    `<extrude>/<circle-skp>:face:outer_wall` — the outer wall NEVER enters the
    hole_wall path (correlation dispatches from classification, B2)."""
    from . import topology  # lazy: topology imports geometry at module top

    topology.require_skp_id(circle, "circle")
    cx, cy = float(circle["cx_mm"]), float(circle["cy_mm"])
    r = float(circle["radius_mm"])
    circ = gp_Circ(gp_Ax2(gp_Pnt(*frame.to_3d(cx, cy)), gp_Dir(*frame.normal)), r)
    edge = BRepBuilderAPI_MakeEdge(circ).Edge()
    face = BRepBuilderAPI_MakeFace(BRepBuilderAPI_MakeWire(edge).Wire()).Face()
    prism = BRepPrimAPI_MakePrism(face, _normal_vec(frame, sign * depth_mm))
    shape = prism.Shape()
    gen = [TopoDS.Face_s(s) for s in prism.Generated(edge)]
    if len(gen) != 1:
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: circle outer profile generated {len(gen)} wall "
            f"faces (expected exactly one; SK-C0 B2)"
        )
    surf = BRepAdaptor_Surface(gen[0])
    if surf.GetType() != GeomAbs_Cylinder or abs(surf.Cylinder().Radius() - r) > 1e-6:
        raise MechanicalKernelEvaluationError(
            f"{ENGINE_OP_PREFIX}: circle outer wall failed by-construction "
            f"verification (cylinder of radius {r} expected)"
        )
    hints = [ProducedFaceHint(
        feature_id=f"{wall_prefix}/{circle['id']}", role_base="outer_wall",
        faces=(gen[0],),
    )]
    caps = (TopoDS.Face_s(prism.FirstShape()), TopoDS.Face_s(prism.LastShape()))
    return shape, hints, caps


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
    # ADR/0038 A4 (arc 20260717-2): the structural operation — decoded on
    # EVERY regeneration (absent legacy = add). The v1 fold builds exactly one
    # body, so its one extrude is the BASE and must ADD (B2 first-add: there
    # is nothing to cut from); a stored/corrupt cut-base recipe fails Class-1
    # here, never reaching the kernel. M-add lifts one-base, not this rule.
    operation = extrude.get("adapter_payload", {}).get("operation", "add")
    if operation not in ("add", "cut"):
        raise TransactionError(
            f"mechanical: extrude operation must be 'add' or 'cut', got {operation!r}"
        )
    if operation == "cut":
        raise TransactionError(
            "mechanical: the BASE extrude must be operation 'add' — a cut "
            "requires an existing body (sequential extrudes arrive in M-add)"
        )
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
