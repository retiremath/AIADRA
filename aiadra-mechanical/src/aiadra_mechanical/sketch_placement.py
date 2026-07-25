"""Sketch placement law (ADR/0044 Amendment A3; arc 20260725-2, pass
`sketch-place-1`).

The `0.2.1` placement record makes the sketch's frame Product Truth:

    placement: {support, orientation_ref, orientation, normal_side}

Both plane records are closed principal-plane vocabulary; `orientation`
names which screen edge the reference faces; `normal_side` is the SIGNED
support normal (Petre's Flip experiment: a positive-depth downstream
feature grows to the other side — model semantics, never camera state).

This module is PURE math + validation — the single frame authority (A3.7:
centralized dispatch; no other surface derives placement axes). The codec
(`sketch_v2`), handlers, display, and signature all consume it.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

Vec3 = tuple[float, float, float]

PRINCIPALS: tuple[str, ...] = ("xy", "yz", "zx")
ORIENTATIONS: tuple[str, ...] = ("right", "top", "left", "bottom")
NORMAL_SIDES: tuple[str, ...] = ("positive", "negative")

#: The canonical principal-plane normals (the engine table; A3.5 step 1).
CANONICAL_NORMALS: Mapping[str, Vec3] = {
    "xy": (0.0, 0.0, 1.0),
    "yz": (1.0, 0.0, 0.0),
    "zx": (0.0, 1.0, 0.0),
}

#: A3.3 — ONE canonical default per support; reproduces the 0.2.0
#: `_FRAME_AXES` frames exactly (tolerance-free; parity-tested).
DEFAULT_ORIENTATION_REF: Mapping[str, str] = {"xy": "yz", "yz": "zx", "zx": "xy"}

_PLACEMENT_KEYS = frozenset({"support", "orientation_ref", "orientation", "normal_side"})
_PLANE_KEYS = frozenset({"kind", "orientation"})


def default_placement(support_orientation: str) -> dict[str, Any]:
    """The complete A3.3 canonical default record for a support plane."""
    if support_orientation not in PRINCIPALS:
        raise ValueError(f"unknown principal orientation {support_orientation!r}")
    return {
        "support": {"kind": "principal", "orientation": support_orientation},
        "orientation_ref": {
            "kind": "principal",
            "orientation": DEFAULT_ORIENTATION_REF[support_orientation],
        },
        "orientation": "right",
        "normal_side": "positive",
    }


def _validate_principal(rec: Any, label: str, fail: Callable[[str], None]) -> str:
    if not isinstance(rec, Mapping):
        fail(f"placement {label} must be an object, got {type(rec).__name__}")
    keys = set(rec.keys())
    if keys != set(_PLANE_KEYS):
        fail(
            f"placement {label} must be exactly {{kind, orientation}} — "
            f"got keys {sorted(keys)} (the record is closed; A3.2)"
        )
    if rec["kind"] != "principal":
        fail(
            f"placement {label} kind must be 'principal' in BS-1 "
            f"(face/surface/edge references are later passes), got {rec['kind']!r}"
        )
    if rec["orientation"] not in PRINCIPALS:
        fail(
            f"placement {label} orientation must be one of {list(PRINCIPALS)}, "
            f"got {rec['orientation']!r}"
        )
    return str(rec["orientation"])


def validate_placement_record(placement: Any, fail: Callable[[str], None]) -> None:
    """Validate one COMPLETE persisted placement record (A3.2) — closed
    4-member shape, principal-only, support ≠ orientation_ref."""
    if not isinstance(placement, Mapping):
        fail(f"placement must be an object, got {type(placement).__name__}")
    keys = set(placement.keys())
    if keys != set(_PLACEMENT_KEYS):
        missing = set(_PLACEMENT_KEYS) - keys
        extra = keys - set(_PLACEMENT_KEYS)
        fail(
            f"placement key set mismatch — missing {sorted(missing)}, "
            f"unknown {sorted(extra)} (all four members are REQUIRED; A3.2)"
        )
    support = _validate_principal(placement["support"], "support", fail)
    ref = _validate_principal(placement["orientation_ref"], "orientation_ref", fail)
    if support == ref:
        fail(
            f"placement orientation_ref must differ from support (both are "
            f"{support!r}) — a parallel reference has no castable direction; "
            "refused before any solver invocation (A3.5)"
        )
    if placement["orientation"] not in ORIENTATIONS:
        fail(
            f"placement orientation must be one of {list(ORIENTATIONS)}, "
            f"got {placement['orientation']!r}"
        )
    if placement["normal_side"] not in NORMAL_SIDES:
        fail(
            f"placement normal_side must be one of {list(NORMAL_SIDES)}, "
            f"got {placement['normal_side']!r}"
        )


def complete_placement(placement_input: Any, fail: Callable[[str], None]) -> dict[str, Any]:
    """The authoring-lane overlay (A3.6.1): `support` is REQUIRED inside an
    explicitly provided `placement` input; omitted nested members take the
    A3.3 defaults; unknown/extra members refuse. Returns the COMPLETE
    canonical record (the engine mints it; callers never persist partials)."""
    if not isinstance(placement_input, Mapping):
        fail(f"placement must be an object, got {type(placement_input).__name__}")
    keys = set(placement_input.keys())
    unknown = keys - set(_PLACEMENT_KEYS)
    if unknown:
        fail(f"placement carries unknown members {sorted(unknown)} (A3.2 is closed)")
    if "support" not in keys:
        fail("placement requires 'support' (the version-selecting input names "
             "its plane; only NESTED omissions take defaults — A3.6.1)")
    support = _validate_principal(placement_input["support"], "support", fail)
    defaults = default_placement(support)
    record = {
        "support": {"kind": "principal", "orientation": support},
        "orientation_ref": placement_input.get("orientation_ref", defaults["orientation_ref"]),
        "orientation": placement_input.get("orientation", defaults["orientation"]),
        "normal_side": placement_input.get("normal_side", defaults["normal_side"]),
    }
    # deep-copy the ref if caller-provided (never alias caller objects)
    if isinstance(record["orientation_ref"], Mapping):
        record["orientation_ref"] = dict(record["orientation_ref"])
    validate_placement_record(record, fail)
    return record


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _scale(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def derive_frame(placement: Mapping[str, Any],
                 fail: Callable[[str], None]) -> tuple[Vec3, Vec3, Vec3]:
    """A3.5 — the exact derivation. Returns (u, v, n) unit vectors.

    Order is LAW: the SIGNED normal is selected first (Petre's Flip ruling),
    then the reference normal is projected into the support plane, then the
    four-edge mapping applies. Right-handed (v = n × u) on BOTH sides.
    """
    validate_placement_record(placement, fail)
    n0 = CANONICAL_NORMALS[placement["support"]["orientation"]]
    n = n0 if placement["normal_side"] == "positive" else _scale(n0, -1.0)

    p0 = CANONICAL_NORMALS[placement["orientation_ref"]["orientation"]]
    p = _sub(p0, _scale(n, _dot(p0, n)))  # project into the support plane
    norm = _dot(p, p) ** 0.5
    if norm < 1e-12:  # impossible in the principal domain (defensive law)
        fail("placement orientation_ref projects to zero in the support "
             "plane — parallel references refuse (A3.5)")
    p = _scale(p, 1.0 / norm)

    orientation = placement["orientation"]
    if orientation == "right":
        u = p
        v = _cross(n, u)
    elif orientation == "left":
        u = _scale(p, -1.0)
        v = _cross(n, u)
    elif orientation == "top":
        v = p
        u = _cross(v, n)
    else:  # bottom
        v = _scale(p, -1.0)
        u = _cross(v, n)

    # the A3.5 step-5 proof: finite, unit, orthogonal, right-handed
    for vec in (u, v, n):
        mag = _dot(vec, vec)
        assert abs(mag - 1.0) < 1e-12, f"non-unit frame vector {vec!r}"
    assert abs(_dot(u, v)) < 1e-12 and abs(_dot(u, n)) < 1e-12 \
        and abs(_dot(v, n)) < 1e-12, "non-orthogonal frame"
    assert all(abs(a - b) < 1e-12 for a, b in zip(_cross(n, u), v)), \
        "left-handed frame (v != n × u)"
    return u, v, n
