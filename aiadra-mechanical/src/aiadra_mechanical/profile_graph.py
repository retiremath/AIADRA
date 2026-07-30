"""`compile_profile_graph` — THE ONE semantic path for v2 profile sketches.

Authority: ADR/0044 A4 (arc 20260730-1). Codex3 B1 pinned preview honesty as
a build floor: `preview_sketch_graph`, `author_profile_sketch`, and
`replace_sketch_graph` must all reach geometry through THIS function. A
second compiler — even a "small" preview-only one — would be a parallel
semantic authority and exactly the drift ADR/0045 D6 forbids.

The compiler is PURE and namespace-agnostic: it neither mints ids nor
touches disk. Callers hand it entities/constraints already carrying whatever
identifiers they own (engine-minted `skp_NNNN` for committed graphs, caller
keys for an uncommitted preview), and it returns the same namespace back.
Id minting, persistence, and the survival law belong to the operations.

Pipeline (A2.9 lifecycle 1, unchanged in structure):
    preview solve -> exact canonical skb-0 completion -> skb-b1 admission
    -> empty-witness validation -> derived annotations + glyphs
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from aiadra_core.transaction.boundary import TransactionError

from .annotation_basis import build_annotation_basis, build_constraint_glyphs
from .solver import branch_policy_b1

_OP = "mechanical.profile_graph"


def _fail(reason: str) -> None:
    raise TransactionError(f"{_OP}: {reason}")


def _renominalize(entities: Sequence[Mapping[str, Any]],
                  cfg: Mapping[str, float]) -> list:
    """An IN-MEMORY copy of the graph whose nominals are the feasible
    configuration. Used ONLY as a solve input so `skb-0` completion evaluates
    its rank test where the constraints actually hold. It is never persisted:
    the authored nominals stay exactly as drawn (Petre's ruling 2026-07-30)."""
    out = []
    for e in entities:
        e2 = dict(e)
        if e["type"] == "point":
            e2["nominal"] = {"x": cfg.get(f"{e['id']}.x", e["nominal"]["x"]),
                             "y": cfg.get(f"{e['id']}.y", e["nominal"]["y"])}
        elif e["type"] == "circle":
            e2["nominal"] = {
                "radius": cfg.get(f"{e['id']}.radius", e["nominal"]["radius"])}
        out.append(e2)
    return out


def frame_from_placement(placement: Mapping[str, Any]) -> dict[str, Any]:
    """The engine-resolved sketch frame for a placement record. `sketch_placement`
    stays THE frame authority (A3.5/A3.7); this only shapes it for the wire."""
    from .sketch_placement import derive_frame

    u, v, n = derive_frame(placement, _fail)
    return {"origin_mm": [0.0, 0.0, 0.0],
            "u_axis": list(u), "v_axis": list(v), "normal": list(n)}


def world_point(frame: Mapping[str, Any], x: float, y: float) -> list:
    """Sketch-local (mm) -> world. The ENGINE owns this mapping; Studio never
    re-derives a sketch plane (Codex3 B3)."""
    o = frame["origin_mm"]
    u = frame["u_axis"]
    v = frame["v_axis"]
    return [o[i] + u[i] * x + v[i] * y for i in range(3)]


@dataclass(frozen=True)
class CompiledGraph:
    """The complete derived result for one profile graph. Everything a
    caller needs to commit it, preview it, or display it."""

    entities: tuple
    constraints: tuple
    weak_completion: tuple
    admission: Any
    solved: Mapping[str, float]      # <entity>.<parameter> -> mm/deg
    annotations: tuple
    glyphs: tuple


def compile_profile_graph(*, case_id: str,
                          entities: Sequence[Mapping[str, Any]],
                          constraints: Sequence[Mapping[str, Any]]) -> CompiledGraph:
    """Solve, complete, admit, and derive — or refuse typed, having written
    nothing. `case_id` labels the solve only; it need not be a feature id."""
    from .solver import solve, solve_feasible
    from .sketch_v2 import _corpus_case

    # PHASE 1 — the feasible solution of the STRONG system, nearest the
    # drawn nominals. This is where snapping physically happens.
    feasible = solve_feasible(_corpus_case(case_id, entities, constraints))
    if feasible is None:
        _fail(
            "the strong constraints of this profile graph have no feasible "
            "solution near the drawn geometry — nothing was authored"
        )

    # PHASE 2 — the canonical skb-0 completion runs AT the feasible solution
    # (defect D-1, Petre's ruling 2026-07-30). The re-nominalized case is an
    # IN-MEMORY solve input only; the caller keeps the drawn nominals as the
    # authored ones, because committing solved output would be an implicit
    # rebaseline and A2.5/A2.9 require a rebaseline to be explicit.
    feasible_entities = _renominalize(entities, feasible)
    result = solve(_corpus_case(case_id, feasible_entities, constraints))
    # A profile graph always carries free scalars before completion, so the
    # solver classification is `under` for every admitted member.
    if result.classification != "under" or result.diagnostics \
            or result.solved_coordinates is None:
        diags = [d.kind for d in result.diagnostics]
        _fail(
            f"the preview solve refused this profile graph: classification "
            f"{result.classification!r} (expected 'under'), diagnostics "
            f"{diags} — nothing was authored"
        )

    weak = [w.to_record() for w in result.weak_completion]

    try:
        admission = branch_policy_b1.admit_graph(entities, constraints, [], weak)
        branch_policy_b1.validate_witness_set([], admission)
    except branch_policy_b1.OutOfDomain as exc:
        _fail(str(exc))

    profile_entities = [dict(e) for e in entities if e.get("construction") is False]
    segment_ids = [e["id"] for e in profile_entities if e["type"] == "line"]
    annotations = build_annotation_basis(
        entities=profile_entities,
        classes=admission.classes,
        solved=result.solved_coordinates,
    )
    glyphs = build_constraint_glyphs(constraints, segment_ids)

    return CompiledGraph(
        entities=tuple(dict(e) for e in entities),
        constraints=tuple(dict(c) for c in constraints),
        weak_completion=tuple(weak),
        admission=admission,
        solved=dict(result.solved_coordinates),
        annotations=annotations,
        glyphs=glyphs,
    )


def profile_preview_payload(compiled: CompiledGraph,
                            frame: Mapping[str, Any],
                            owner: Mapping[str, str]) -> dict[str, Any]:
    """The `ProfileGraphPreview` envelope (Codex4 B2).

    Deliberately NOT a committed Display `v2_profiles[]` entry: a create
    preview runs before any feature exists, so it carries a caller-scoped
    `candidate_key` owner and the engine-resolved frame INLINE (there is no
    `sketch_frames[]` entry to join yet). Inventing a `sketch_feature_id`
    here would be exactly the fake identity this project refuses everywhere
    else. Parity with committed Display is evaluated AFTER the declared
    key->id and owner/frame substitution, never as literal equality.
    """
    if set(owner.keys()) not in ({"feature_id"}, {"candidate_key"}):
        _fail("preview owner must be exactly {feature_id} or {candidate_key}")
    return {
        "owner": dict(owner),
        "frame": dict(frame),
        **profile_geometry_payload(compiled, frame),
    }


def profile_geometry_payload(compiled: CompiledGraph,
                             frame: Mapping[str, Any]) -> dict[str, Any]:
    """The shared geometry/annotation/glyph content, in WORLD space.

    The engine owns world mapping (Codex3 B3): Studio renders what it is
    given and never re-derives a sketch plane. Annotation VALUES stay
    sketch-local scalars with their schema-fixed units; every drawable
    anchor is world.
    """
    solved = compiled.solved
    by_id = {e["id"]: e for e in compiled.entities}
    profile = [e for e in compiled.entities if e.get("construction") is False]

    def w(x: float, y: float) -> list:
        return world_point(frame, float(x), float(y))

    points = []
    for e in sorted((e for e in profile if e["type"] == "point"),
                    key=lambda e: e["id"]):
        px = solved[f"{e['id']}.x"]
        py = solved[f"{e['id']}.y"]
        points.append({"id": e["id"], "world": w(px, py)})

    segments = [
        {"id": e["id"], "start": e["start"], "end": e["end"]}
        for e in sorted((e for e in profile if e["type"] == "line"),
                        key=lambda e: e["id"])
    ]

    circles = []
    for e in sorted((e for e in profile if e["type"] == "circle"),
                    key=lambda e: e["id"]):
        circles.append({
            "id": e["id"], "center": e["center"],
            "radius_mm": float(solved[f"{e['id']}.radius"]),
        })

    annotations = [
        {"id": a.id, "kind": a.kind, "value": float(a.value), "unit": a.unit,
         "entities": list(a.entities),
         "anchors": [w(ax, ay) for ax, ay in a.anchors]}
        for a in compiled.annotations
    ]

    glyphs = []
    for g in compiled.glyphs:
        seg = by_id[g["target"]]
        sx = solved[f"{seg['start']}.x"]
        sy = solved[f"{seg['start']}.y"]
        ex = solved[f"{seg['end']}.x"]
        ey = solved[f"{seg['end']}.y"]
        glyphs.append({**g, "anchor": w((sx + ex) / 2.0, (sy + ey) / 2.0)})

    return {"points": points, "segments": segments, "circles": circles,
            "annotations": annotations, "constraint_glyphs": glyphs}
