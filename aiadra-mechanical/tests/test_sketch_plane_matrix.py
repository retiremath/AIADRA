"""EP2 — the sketch-plane binding matrix (arc 20260714-2; Codex1 B2/B3 +
Codex2 build bars).

Covers: rectangle / rectangle+circle / contour × the three principal planes ×
both normal signs (solid orientation, roles, cylinder/cap correlation on the
new frames); per-plane identity stability (a value edit preserves roles +
signature); plane-change = skeleton; legacy-signature byte-identity; the
`normal±`/`z±` direction rules; exact named-sketch resolution + negatives;
and the revolve principal-xy guards.
"""
from __future__ import annotations

import pytest

from aiadra_core.transaction.boundary import TransactionError

from aiadra_mechanical.adapter_payload import build_extrude_payload, build_sketch_payload
from aiadra_mechanical.recipe import (
    PlaneFrame,
    effective_plane_frame,
    extrude_sign,
    resolve_consumed_sketch,
    validate_plane_record,
)
from aiadra_mechanical import display, topology

# ---------------------------------------------------------------------------
# Recipe helpers (engine-level, no workspace — the fast lane)
# ---------------------------------------------------------------------------

RECT = {"type": "rectangle", "x_mm": 0, "y_mm": 0, "width_mm": 40, "height_mm": 30}
CIRCLE = {"type": "circle", "cx_mm": 20, "cy_mm": 15, "radius_mm": 5}
L_VERTS = [(0, 0), (60, 0), (60, 20), (20, 20), (20, 50), (0, 50)]


def _contour(verts):
    n = len(verts)
    return {
        "type": "contour",
        "segments": [
            {"kind": "line", "x1_mm": verts[i][0], "y1_mm": verts[i][1],
             "x2_mm": verts[(i + 1) % n][0], "y2_mm": verts[(i + 1) % n][1]}
            for i in range(n)
        ],
    }


def _sketch(prims, plane=None, fid="feat_0001"):
    return {"id": fid, "feature_type": "sketch",
            "adapter_payload": build_sketch_payload(prims, plane)}


def _extrude(sketch_id="feat_0001", depth=10.0, direction="normal+", fid="feat_0002"):
    return {
        "id": fid, "feature_type": "extrude",
        "depends_on_feature_ids": [sketch_id],
        "parameters": [{"id": "featp_0001", "name": "depth_mm", "value": depth,
                        "datatype": "number", "unit": "mm"}],
        "adapter_payload": build_extrude_payload(
            sketch_feature_id=sketch_id, direction=direction,
            depth_parameter_id="featp_0001"),
    }


def _gen(feats):
    return display.generate_display_representation(
        feats, object_uuid="u-1", object_number="PRT-0001",
        geometry_ref="sha256:deadbeef", cache_key="ck")


def _faces(d):
    return {f["face_id"] for f in d["render"]["faces"]}


# The (u, v, n) → global-axis index for each principal plane.
_AXIS_INDEX = {"xy": (0, 1, 2), "yz": (1, 2, 0), "zx": (2, 0, 1)}


def _plane(ori):
    return {"kind": "principal", "orientation": ori}


# ---------------------------------------------------------------------------
# 1. The build matrix: profile × plane × sign
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ori", ["xy", "yz", "zx"])
@pytest.mark.parametrize("direction,sign", [("normal+", 1.0), ("normal-", -1.0)])
def test_rectangle_extrudes_on_every_plane_both_signs(ori, direction, sign):
    d = _gen([_sketch([RECT], _plane(ori)), _extrude(direction=direction)])
    ui, vi, ni = _AXIS_INDEX[ori]
    bmin, bmax = d["render"]["bbox_min"], d["render"]["bbox_max"]
    # In-plane extents = the profile; the sweep spans [0, sign·depth] on n.
    assert (bmin[ui], bmax[ui]) == pytest.approx((0.0, 40.0), abs=1e-6)
    assert (bmin[vi], bmax[vi]) == pytest.approx((0.0, 30.0), abs=1e-6)
    lo, hi = (0.0, 10.0) if sign > 0 else (-10.0, 0.0)
    assert (bmin[ni], bmax[ni]) == pytest.approx((lo, hi), abs=1e-6)
    faces = _faces(d)
    assert len(faces) == 6
    assert "feat_0002:face:cap_base" in faces and "feat_0002:face:cap_top" in faces
    assert sum(1 for f in faces if ":face:wall_" in f) == 4


@pytest.mark.parametrize("ori", ["xy", "yz", "zx"])
def test_rectangle_with_circle_hole_on_every_plane(ori):
    # Cylinder-axis/cap correlation on the new frames (Codex1 build bar).
    d = _gen([_sketch([RECT, CIRCLE], _plane(ori)), _extrude()])
    faces = _faces(d)
    assert len(faces) == 7
    assert "feat_0002/skp_0002:face:hole_wall" in faces
    kinds = d["counters"]["edge_count_by_kind"]
    assert kinds.get("seam") == 1  # the hole cylinder's seam, on every frame


@pytest.mark.parametrize("ori", ["xy", "yz", "zx"])
def test_contour_extrudes_on_every_plane(ori):
    d = _gen([_sketch([_contour(L_VERTS)], _plane(ori)), _extrude()])
    faces = _faces(d)
    assert len(faces) == 8  # 6 segment walls + 2 caps
    assert sum(1 for f in faces if f.endswith(":face:wall")) == 6


# ---------------------------------------------------------------------------
# 2. Identity per plane: value edit vs skeleton change (ADR/0035/0038)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ori", ["yz", "zx"])
def test_value_edit_on_a_non_default_plane_preserves_roles_and_signature(ori):
    a = [_sketch([RECT], _plane(ori)), _extrude()]
    wider = dict(RECT, width_mm=55)
    b = [_sketch([wider], _plane(ori)), _extrude()]
    assert _faces(_gen(a)) == _faces(_gen(b))
    assert topology.compute_topology_signature(a) == topology.compute_topology_signature(b)


def test_plane_change_is_skeleton_and_does_not_rename_roles():
    xy = [_sketch([RECT], _plane("xy")), _extrude()]
    yz = [_sketch([RECT], _plane("yz")), _extrude()]
    # The signature CHANGES (dependent references invalidate)…
    assert topology.compute_topology_signature(xy) != topology.compute_topology_signature(yz)
    # …but role NAMES are stable (the signature carries the invalidation).
    assert _faces(_gen(xy)) == _faces(_gen(yz))


def test_legacy_and_explicit_xy_signatures_are_byte_identical():
    legacy = [_sketch([RECT]), _extrude(direction="z+")]
    explicit = [_sketch([RECT], _plane("xy")), _extrude(direction="normal+")]
    assert topology.compute_topology_signature(legacy) == topology.compute_topology_signature(explicit)


def test_signature_rejects_a_malformed_plane_record_codex3_b2():
    """The signature consumer uses the SAME exact validator — a malformed plane
    can never mint an authoritative signature evaluation would reject."""
    extra_key = _sketch([RECT], _plane("yz"))
    extra_key["adapter_payload"]["plane"]["offset_mm"] = 5  # illegal extra key
    with pytest.raises(TransactionError, match="unsupported key"):
        topology.compute_topology_signature([extra_key, _extrude()])
    bad_kind = _sketch([RECT])
    bad_kind["adapter_payload"]["plane"] = {"kind": "datum", "orientation": "xy"}
    with pytest.raises(TransactionError, match="RESERVED"):
        topology.compute_topology_signature([bad_kind, _extrude()])


def test_signature_enforces_the_exact_consumed_sketch_codex3_b2():
    """Extrude AND revolve resolution violations fail Class-1 in the signature
    consumer too — never `mode='invalid'`-swallowed, never skipped."""
    # extrude naming a missing sketch
    with pytest.raises(TransactionError, match="not found"):
        topology.compute_topology_signature([_sketch([RECT]), _extrude(sketch_id="feat_0009")])
    # extrude whose payload and declared dependency disagree
    mismatched = _extrude(sketch_id="feat_0001")
    mismatched["depends_on_feature_ids"] = ["feat_0007"]
    with pytest.raises(TransactionError, match="disagree"):
        topology.compute_topology_signature([_sketch([RECT]), mismatched])
    # revolve resolver violations PROPAGATE (only crossing-axis keeps 'invalid')
    revolve = {
        "id": "feat_0002", "feature_type": "revolve",
        "depends_on_feature_ids": ["feat_0009"],
        "adapter_payload": {"sketch_feature_id": "feat_0009", "axis": "x"},
    }
    with pytest.raises(TransactionError, match="not found"):
        topology.compute_topology_signature([_sketch([RECT]), revolve])


# ---------------------------------------------------------------------------
# 3. The direction rules (Codex1 B3)
# ---------------------------------------------------------------------------


def test_legacy_z_direction_works_on_xy_and_matches_normal():
    legacy = _gen([_sketch([RECT]), _extrude(direction="z+")])
    canonical = _gen([_sketch([RECT], _plane("xy")), _extrude(direction="normal+")])
    assert legacy["render"]["bbox_max"] == canonical["render"]["bbox_max"]


def test_legacy_z_direction_rejected_on_non_xy_at_regeneration():
    with pytest.raises(TransactionError, match="only valid on the principal xy"):
        _gen([_sketch([RECT], _plane("yz")), _extrude(direction="z+")])


def test_extrude_sign_rules_are_exact():
    xy = effective_plane_frame(_sketch([RECT]))
    yz = effective_plane_frame(_sketch([RECT], _plane("yz")))
    assert extrude_sign("normal-", yz, op_kind="t") == -1.0
    assert extrude_sign("z+", xy, op_kind="t") == 1.0
    with pytest.raises(TransactionError):
        extrude_sign("z-", yz, op_kind="t")
    with pytest.raises(TransactionError):
        extrude_sign("up", xy, op_kind="t")


# ---------------------------------------------------------------------------
# 4. The discriminated plane record (Codex1 B3 — exact validation)
# ---------------------------------------------------------------------------


def test_plane_record_is_validated_exactly():
    assert validate_plane_record({"kind": "principal", "orientation": "zx"}, op_kind="t") == "zx"
    with pytest.raises(TransactionError, match="RESERVED"):
        validate_plane_record({"kind": "datum", "orientation": "xy"}, op_kind="t")
    with pytest.raises(TransactionError, match="unknown plane kind"):
        validate_plane_record({"kind": "weird", "orientation": "xy"}, op_kind="t")
    with pytest.raises(TransactionError, match="orientation"):
        validate_plane_record({"kind": "principal", "orientation": "ab"}, op_kind="t")
    with pytest.raises(TransactionError, match="unsupported key"):
        validate_plane_record(
            {"kind": "principal", "orientation": "xy", "offset_mm": 5}, op_kind="t")


def test_corrupt_stored_plane_fails_loud_at_evaluation():
    sk = _sketch([RECT])
    sk["adapter_payload"]["plane"] = {"kind": "principal", "orientation": "qq"}
    with pytest.raises(TransactionError):
        _gen([sk, _extrude()])


# ---------------------------------------------------------------------------
# 5. Exact named-sketch resolution (Codex1 B2) — the last-sketch shortcut is dead
# ---------------------------------------------------------------------------


def test_extrude_consumes_the_NAMED_sketch_not_the_last():
    # Two sketches on DIFFERENT planes; the extrude names the FIRST (xy).
    feats = [
        _sketch([RECT], _plane("xy"), fid="feat_0001"),
        _sketch([RECT], _plane("yz"), fid="feat_0003"),
        _extrude(sketch_id="feat_0001"),
    ]
    d = _gen(feats)
    # The solid sweeps along +Z (the xy frame) — NOT +X (the last sketch's).
    assert d["render"]["bbox_max"][2] == pytest.approx(10.0)
    assert d["render"]["bbox_max"][0] == pytest.approx(40.0)

    # Naming the SECOND flips the orientation.
    feats2 = [
        _sketch([RECT], _plane("xy"), fid="feat_0001"),
        _sketch([RECT], _plane("yz"), fid="feat_0003"),
        _extrude(sketch_id="feat_0003"),
    ]
    d2 = _gen(feats2)
    assert d2["render"]["bbox_max"][0] == pytest.approx(10.0)  # sweeps along +X


def test_resolution_negatives_fail_class1():
    sk = _sketch([RECT])
    # missing
    with pytest.raises(TransactionError, match="not found"):
        resolve_consumed_sketch([sk], _extrude(sketch_id="feat_0009"))
    # wrong type
    ex = _extrude(fid="feat_0002")
    with pytest.raises(TransactionError, match="not a sketch"):
        resolve_consumed_sketch([sk, ex], _extrude(sketch_id="feat_0002", fid="feat_0003"))
    # later-than-consumer
    consumer_first = [_extrude(fid="feat_0002"), _sketch([RECT], fid="feat_0001")]
    with pytest.raises(TransactionError, match="AFTER its consumer"):
        resolve_consumed_sketch(consumer_first, consumer_first[0])
    # dependency disagreement
    bad = _extrude(sketch_id="feat_0001")
    bad["depends_on_feature_ids"] = ["feat_0007"]
    with pytest.raises(TransactionError, match="disagree"):
        resolve_consumed_sketch([sk], bad)
    # duplicate sketch ids
    with pytest.raises(TransactionError, match="DUPLICATED"):
        resolve_consumed_sketch([sk, _sketch([RECT], fid="feat_0001")], _extrude())


# ---------------------------------------------------------------------------
# 6. Revolve stays principal-xy in v1 (D-P4)
# ---------------------------------------------------------------------------


def test_revolve_on_a_non_xy_sketch_fails_loud():
    revolve = {
        "id": "feat_0002", "feature_type": "revolve",
        "depends_on_feature_ids": ["feat_0001"],
        "adapter_payload": {"sketch_feature_id": "feat_0001", "axis": "x"},
    }
    offset_rect = {"type": "rectangle", "x_mm": 0, "y_mm": 2, "width_mm": 20, "height_mm": 3}
    with pytest.raises(TransactionError, match="principal xy"):
        _gen([_sketch([offset_rect], _plane("yz")), revolve])
