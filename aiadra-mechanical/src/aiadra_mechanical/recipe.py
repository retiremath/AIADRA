"""Shared PURE recipe-resolution + sketch-plane frames (arc 20260714-2 EP2).

ONE implementation (Codex2 build bar 4) consumed by the handlers, the
evaluator, the topology extraction/correlation, and display code — no OCCT
imports, no circular imports:

- `effective_plane_frame()` — the discriminated sketch-plane record
  (`{"kind": "principal", "orientation": "xy"|"yz"|"zx"}`; absent ≡ principal
  xy for legacy recipes; `datum`/`offset` are RESERVED future kinds, fail loud)
  → the right-handed (u, v, n) frame:
      xy → u=+X, v=+Y, n=+Z    yz → u=+Y, v=+Z, n=+X    zx → u=+Z, v=+X, n=+Y
  Sketch coordinates (`x_mm`/`y_mm`) are the sketch-LOCAL (u, v) — they are
  not global-axis claims.
- `resolve_consumed_sketch()` — a base feature (extrude/revolve) consumes
  EXACTLY the sketch named by its `sketch_feature_id` (Codex1 B2): it must
  exist, precede the consumer, be a sketch, be unique, and agree with the
  declared dependency. The last-sketch shortcut is gone.
- `extrude_sign()` — the direction rule (Codex1 B3): `normal+`/`normal-` are
  canonical; legacy `z+`/`z-` are accepted ONLY on a principal-xy frame and
  never rewritten on disk; everything else fails Class-1.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiadra_core.transaction.boundary import TransactionError

PLANE_ORIENTATIONS = ("xy", "yz", "zx")

_FRAME_AXES: dict[str, tuple[tuple[float, float, float], ...]] = {
    "xy": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "yz": ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
    "zx": ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
}


@dataclass(frozen=True)
class PlaneFrame:
    """A principal sketch-plane frame: right-handed (u, v, n), through origin."""

    orientation: str
    u_axis: tuple[float, float, float]
    v_axis: tuple[float, float, float]
    normal: tuple[float, float, float]

    def to_3d(self, u: float, v: float, w: float = 0.0) -> tuple[float, float, float]:
        """Sketch-local (u, v) + normal offset w → global 3D."""
        return (
            u * self.u_axis[0] + v * self.v_axis[0] + w * self.normal[0],
            u * self.u_axis[1] + v * self.v_axis[1] + w * self.normal[1],
            u * self.u_axis[2] + v * self.v_axis[2] + w * self.normal[2],
        )

    def project_uv(self, p: tuple[float, float, float]) -> tuple[float, float]:
        """Global 3D → sketch-local (u, v)."""
        return (
            p[0] * self.u_axis[0] + p[1] * self.u_axis[1] + p[2] * self.u_axis[2],
            p[0] * self.v_axis[0] + p[1] * self.v_axis[1] + p[2] * self.v_axis[2],
        )

    def normal_coord(self, p: tuple[float, float, float]) -> float:
        """The signed coordinate of a global point along the plane normal."""
        return p[0] * self.normal[0] + p[1] * self.normal[1] + p[2] * self.normal[2]


def principal_frame(orientation: str) -> PlaneFrame:
    """The frame for a principal orientation (public — e.g. the revolve builder
    pins xy explicitly)."""
    if orientation not in PLANE_ORIENTATIONS:
        raise TransactionError(
            f"mechanical: unknown principal orientation {orientation!r}"
        )
    u, v, n = _FRAME_AXES[orientation]
    return PlaneFrame(orientation=orientation, u_axis=u, v_axis=v, normal=n)


_frame = principal_frame


def validate_plane_record(plane: Any, *, op_kind: str) -> str:
    """Validate the discriminated plane record EXACTLY (Codex1 B3: unknown
    kinds and extra keys fail loud; `datum`/`offset` are reserved). Returns the
    orientation."""
    if not isinstance(plane, dict):
        raise TransactionError(
            f"{op_kind}: 'plane' must be an object like "
            f"{{'kind': 'principal', 'orientation': 'xy'}}, got {type(plane).__name__}"
        )
    kind = plane.get("kind")
    if kind in ("datum", "offset"):
        raise TransactionError(
            f"{op_kind}: plane kind {kind!r} is RESERVED — datum-plane and offset "
            f"bindings arrive in a later slice; v1 supports kind 'principal'"
        )
    if kind != "principal":
        raise TransactionError(
            f"{op_kind}: unknown plane kind {kind!r}; v1 supports 'principal' "
            f"('datum'/'offset' reserved)"
        )
    orientation = plane.get("orientation")
    if orientation not in PLANE_ORIENTATIONS:
        raise TransactionError(
            f"{op_kind}: plane orientation must be one of {list(PLANE_ORIENTATIONS)}, "
            f"got {orientation!r}"
        )
    extra = set(plane) - {"kind", "orientation"}
    if extra:
        raise TransactionError(
            f"{op_kind}: plane record carries unsupported key(s) {sorted(extra)}; "
            f"v1 accepts exactly {{kind, orientation}}"
        )
    return orientation


def effective_plane_frame(sketch_feature: dict[str, Any]) -> PlaneFrame:
    """The sketch's effective plane frame. Absent `plane` ≡ principal xy
    (legacy recipes keep their meaning byte-for-byte); a present record is
    validated exactly — a corrupt stored plane fails loud at every consumer."""
    payload = sketch_feature.get("adapter_payload") or {}
    plane = payload.get("plane")
    if plane is None:
        return _frame("xy")
    orientation = validate_plane_record(plane, op_kind="mechanical.sketch-plane")
    return _frame(orientation)


def resolve_consumed_sketch(
    features: list[dict[str, Any]], base_feature: dict[str, Any]
) -> dict[str, Any]:
    """Resolve EXACTLY the sketch a base feature (extrude/revolve) names
    (Codex1 B2). Class-1 on: missing/absent id, not found, duplicate ids,
    wrong type, the sketch not PRECEDING the consumer, or disagreement with
    `depends_on_feature_ids`. Never 'the last sketch'."""
    base_type = base_feature.get("feature_type", "base")
    op = f"mechanical.{base_type}"
    sid = (base_feature.get("adapter_payload") or {}).get("sketch_feature_id")
    if not isinstance(sid, str) or not sid:
        raise TransactionError(
            f"{op}: base feature {base_feature.get('id')!r} names no "
            f"sketch_feature_id — a corrupt payload cannot resolve its profile"
        )
    deps = base_feature.get("depends_on_feature_ids")
    if deps is not None and sid not in deps:
        raise TransactionError(
            f"{op}: base feature {base_feature.get('id')!r} names sketch {sid!r} "
            f"but declares dependencies {deps!r} — the payload and the declared "
            f"dependency disagree"
        )
    matches = [f for f in features if f.get("id") == sid]
    if not matches:
        raise TransactionError(
            f"{op}: consumed sketch {sid!r} not found in the recipe"
        )
    if len(matches) > 1:
        raise TransactionError(
            f"{op}: consumed sketch id {sid!r} is DUPLICATED in the recipe "
            f"({len(matches)} features carry it)"
        )
    sketch = matches[0]
    if sketch.get("feature_type") != "sketch":
        raise TransactionError(
            f"{op}: consumed feature {sid!r} is a "
            f"{sketch.get('feature_type')!r}, not a sketch"
        )
    base_id = base_feature.get("id")
    ids = [f.get("id") for f in features]
    if base_id in ids and ids.index(sid) > ids.index(base_id):
        raise TransactionError(
            f"{op}: consumed sketch {sid!r} appears AFTER its consumer "
            f"{base_id!r} in the recipe — a profile must precede its base feature"
        )
    return sketch


EXTRUDE_DIRECTIONS = ("normal+", "normal-", "z+", "z-")


def extrude_sign(direction: Any, frame: PlaneFrame, *, op_kind: str) -> float:
    """Normalize a stored direction to the sweep sign along the frame normal.
    `normal±` is canonical; legacy `z±` is accepted ONLY on a principal-xy
    frame (where it means the same thing) and is never rewritten on disk."""
    if direction in ("normal+", "normal-"):
        return 1.0 if direction == "normal+" else -1.0
    if direction in ("z+", "z-"):
        if frame.orientation != "xy":
            raise TransactionError(
                f"{op_kind}: legacy direction {direction!r} is only valid on the "
                f"principal xy plane; this sketch is on {frame.orientation!r} — "
                f"use 'normal+'/'normal-'"
            )
        return 1.0 if direction == "z+" else -1.0
    raise TransactionError(
        f"{op_kind}: direction must be one of {list(EXTRUDE_DIRECTIONS)}, "
        f"got {direction!r}"
    )
