"""THE whole-list sketch classifier (SK-C0, arc 20260715-4, Codex1 B3).

ONE pure engine-owned interpretation of a sketch's primitive list, consumed by
payload validation, the evaluator, topology extraction, and the Hole/Revolve
guards — and mirrored fixture-for-fixture by Studio TS. Every unsupported
whole-list combination fails LOUD here; no consumer silently selects or
silently ignores primitives (the pre-C0 first-circle-wins and stray-content
holes are closed by construction).

The pinned matrix (each row a test):

  non-construction content                      -> result
  rectangle alone                               -> outer=rectangle
  rectangle + exactly one circle                -> outer=rectangle, hole=circle
  contour alone                                 -> outer=contour
  contour + any circle                          -> REJECT (v1 rule unchanged)
  exactly one circle, nothing else              -> outer=circle  (NEW in C0)
  two+ circles without a rectangle              -> REJECT loud
  two+ outer candidates (any mix)               -> REJECT loud
  nothing (empty or all-construction)           -> VALID sketch-only: outer=None
                                                   (no Extrude/Revolve eligibility)

Construction (D-C3): `construction` is TOP-LEVEL and atomic per primitive
(absent == False; non-boolean REJECTS; a contour SEGMENT carrying its own
`construction` key REJECTS — Codex2 clarification). Construction primitives are
filtered out of every profile decision, retained for display, and excluded from
the 3D topology-contributing set.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aiadra_core.transaction.boundary import TransactionError

_WHERE = "mechanical.add_sketch_feature"


@dataclass(frozen=True)
class SketchClassification:
    """outer_kind: 'rectangle' | 'contour' | 'circle' | 'none'."""

    outer_kind: str
    outer_index: int | None            # index into the primitives list
    hole_index: int | None             # non-construction circle inside a rectangle
    construction_indices: tuple[int, ...] = field(default=())
    topology_contributing: tuple[int, ...] = field(default=())  # outer + hole

    @property
    def is_sketch_only(self) -> bool:
        return self.outer_kind == "none"


def non_construction(primitives: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The primitives that participate in geometry/profile decisions — shared
    by every consumer so construction guides are excluded ONE way."""
    return [p for i, p in enumerate(primitives or []) if not _construction_flag(p, i)]


def _construction_flag(prim: dict[str, Any], i: int) -> bool:
    flag = prim.get("construction", False)
    if not isinstance(flag, bool):
        raise TransactionError(
            f"{_WHERE}: primitive[{i}] 'construction' must be a boolean "
            f"(absent means False), got {flag!r}"
        )
    if prim.get("type") == "contour":
        for k, seg in enumerate(prim.get("segments") or []):
            if isinstance(seg, dict) and "construction" in seg:
                raise TransactionError(
                    f"{_WHERE}: primitive[{i}] contour segment[{k}] carries its own "
                    f"'construction' key — construction is TOP-LEVEL and atomic for "
                    f"a contour (mark the whole contour, not segments)"
                )
    return flag


def classify_sketch(primitives: list[dict[str, Any]]) -> SketchClassification:
    """Classify the whole list. Raises TransactionError (Class-1) on every
    unsupported combination. Assumes per-primitive SHAPE validation (keys,
    domains, contour Class-1) happens in adapter_payload — this function owns
    the WHOLE-LIST semantics only, but is safe on unvalidated input."""
    construction: list[int] = []
    rects: list[int] = []
    contours: list[int] = []
    circles: list[int] = []
    for i, prim in enumerate(primitives or []):
        if not isinstance(prim, dict):
            raise TransactionError(f"{_WHERE}: primitive[{i}] must be an object")
        if _construction_flag(prim, i):
            construction.append(i)
            continue
        kind = prim.get("type")
        if kind == "rectangle":
            rects.append(i)
        elif kind == "contour":
            contours.append(i)
        elif kind == "circle":
            circles.append(i)
        elif kind == "line":
            # closes the pre-C0 silently-ignored hole: a standalone line is a
            # GUIDE, never profile geometry
            raise TransactionError(
                f"{_WHERE}: primitive[{i}] is a non-construction standalone line — "
                f"standalone lines are construction-only in v1 (set "
                f"construction:true for a guide; profile edges are contour segments)"
            )
        else:
            raise TransactionError(
                f"{_WHERE}: primitive[{i}] unknown type {kind!r}; expected one of "
                f"['circle', 'contour', 'line', 'rectangle']"
            )

    outer_candidates = len(rects) + len(contours)

    if outer_candidates == 0 and not circles:
        # empty or all-construction: a VALID sketch-only artifact (guides/layout);
        # Extrude/Revolve guards read outer_kind == 'none' and refuse.
        return SketchClassification(
            outer_kind="none", outer_index=None, hole_index=None,
            construction_indices=tuple(construction), topology_contributing=(),
        )

    if outer_candidates > 1:
        raise TransactionError(
            f"{_WHERE}: a sketch needs exactly one outer profile; got "
            f"{len(rects)} rectangle(s) + {len(contours)} contour(s)"
        )

    if contours:
        if circles:
            raise TransactionError(
                f"{_WHERE}: v1 does not support a circle with a contour outer "
                f"profile (contour = outer boundary only); use a rectangle "
                f"profile for a circular through-hole"
            )
        idx = contours[0]
        return SketchClassification(
            outer_kind="contour", outer_index=idx, hole_index=None,
            construction_indices=tuple(construction),
            topology_contributing=(idx,),
        )

    if rects:
        idx = rects[0]
        if len(circles) > 1:
            raise TransactionError(
                f"{_WHERE}: at most one non-construction circle hole is supported "
                f"with a rectangle profile; got {len(circles)} circles (nothing is "
                f"silently ignored)"
            )
        hole = circles[0] if circles else None
        contributing = (idx,) if hole is None else (idx, hole)
        return SketchClassification(
            outer_kind="rectangle", outer_index=idx, hole_index=hole,
            construction_indices=tuple(construction),
            topology_contributing=contributing,
        )

    # circles only (no rectangle, no contour)
    if len(circles) > 1:
        raise TransactionError(
            f"{_WHERE}: {len(circles)} non-construction circles without a "
            f"rectangle profile — exactly ONE circle may stand as the outer "
            f"profile (nothing is silently selected)"
        )
    idx = circles[0]
    return SketchClassification(
        outer_kind="circle", outer_index=idx, hole_index=None,
        construction_indices=tuple(construction),
        topology_contributing=(idx,),
    )
