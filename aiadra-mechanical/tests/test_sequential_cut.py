"""M-cut (arc 20260717-2, ADR/0038 A4.8's CUT half) — the first pockets:
a blind cut into a face-bound sketch's support, through the public protocol.

The cut-specific proof (Codex11's inheritance boundary; spike-pinned): only
the support is modified (1:1), the contact deletes exactly, every other body
face is RETAINED IDENTICALLY, the pocket walls + bottom survive, one
non-empty solid remains, and the volume DECREASES by exactly the tool volume
(blind containment proven post-hoc). Plus the marquee three-boolean walk:
base -> boss -> pocket."""
from __future__ import annotations

import pytest

from aiadra_core.protocol import propose
from aiadra_core.transaction.boundary import TransactionError

from aiadra_mechanical import body_history, geometry, topology
from conftest import part_sidecar

from test_sequential_add import (  # the shared walk helpers
    BOSS_RECT, _add_face_sketch, _build_base_box, _cap_top,
)

POCKET_RECT = [{"type": "rectangle", "x_mm": 4.0, "y_mm": 4.0,
                "width_mm": 8.0, "height_mm": 6.0}]


def _commit_cut(ws, sketch_id, depth=4.0):
    propose(ws, kind="mechanical.add_extrude_feature", params={
        "part_number": "P-000001", "sketch_feature_id": sketch_id,
        "depth_mm": depth, "direction": "normal-", "operation": "cut",
    }).commit()


class TestTheFirstPocket:
    def test_pocket_in_the_top_cap(self, workspace_with_part):
        """THE POCKET: base -> face-bound sketch on cap_top -> cut -> the
        blind pocket. Chain, records, ledger, extraction, volume."""
        ws = workspace_with_part
        _build_base_box(ws)
        _add_face_sketch(ws, prims=POCKET_RECT)
        _commit_cut(ws, "feat_0003", depth=4.0)

        sidecar = part_sidecar(ws)
        features = sidecar["feature"]
        pocket = next(f for f in features if f["id"] == "feat_0004")
        assert pocket["depends_on_feature_ids"] == ["feat_0003", "feat_0002"]
        assert pocket["adapter_payload"]["operation"] == "cut"
        assert body_history.body_head(features) == "feat_0004"

        records = [g for g in sidecar["geometry_ref"] if g.get("role") == "authoring_geometry"]
        assert len(records) == 1
        assert records[0]["derived_from_feature_ids"] == [
            "feat_0001", "feat_0002", "feat_0003", "feat_0004",
        ]

        result = geometry.evaluate_part_with_provenance(features)
        assert result.ledger is not None
        roles = set(result.ledger.roles())
        # the base survives whole (the support ring-modified under its role)
        assert "feat_0002:face:cap_top" in roles
        assert "feat_0002:face:cap_base" in roles
        # pocket walls + BOTTOM joined; the opening (contact) lawfully gone
        assert "feat_0004:face:cap_top" in roles      # the pocket bottom (swept end)
        assert "feat_0004:face:cap_base" not in roles  # the opening
        assert any(r.startswith("feat_0004/") and ":face:wall_" in r for r in roles)
        topo = topology.extract_part_topology(features)
        assert roles == {f.face_id for f in topo.faces}
        assert len(roles) == 11  # 6 base + 4 pocket walls + the bottom
        # the volume: 40*25*10 - 8*6*4 = 10000 - 192
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(result.shape, props)
        assert abs(props.Mass() - (10000.0 - 192.0)) < 1e-3

    def test_pocket_rides_a_base_depth_edit(self, workspace_with_part):
        """The base grows 10 -> 18: the pocket bottom follows its support to
        18 - 4 = 14 (the cut re-resolves on the moved cap)."""
        ws = workspace_with_part
        _build_base_box(ws)
        _add_face_sketch(ws, prims=POCKET_RECT)
        _commit_cut(ws, "feat_0003", depth=4.0)
        propose(ws, kind="mechanical.adjust_feature_parameter", params={
            "part_number": "P-000001", "feature_id": "feat_0002",
            "parameter_name": "depth_mm", "new_value": 18.0,
        }).commit()
        features = part_sidecar(ws)["feature"]
        result = geometry.evaluate_part_with_provenance(features)
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib
        bottom = next(f for f, r in result.ledger.faces if r == "feat_0004:face:cap_top")
        b = Bnd_Box()
        BRepBndLib.Add_s(bottom, b)
        assert abs(b.Get()[5] - 14.0) < 1e-6

    def test_base_boss_pocket_three_booleans_deep(self, workspace_with_part):
        """THE MARQUEE WALK: base -> boss (Fuse) -> pocket (Cut), each on a
        face-bound sketch, the ledger complete through BOTH booleans — the
        arc's whole purpose in one Part."""
        ws = workspace_with_part
        _build_base_box(ws)
        _add_face_sketch(ws, prims=BOSS_RECT)          # feat_0003 on cap_top
        propose(ws, kind="mechanical.add_extrude_feature", params={
            "part_number": "P-000001", "sketch_feature_id": "feat_0003",
            "depth_mm": 6.0, "direction": "normal+", "operation": "add",
        }).commit()                                     # feat_0004 the boss
        # the pocket sketch on the SUPPORT RING (the base cap, now with the
        # boss opening as an inner boundary) — footprint clear of BOTH edges
        _add_face_sketch(ws, prims=[{"type": "rectangle", "x_mm": 2.0, "y_mm": 2.0,
                                     "width_mm": 6.0, "height_mm": 4.0}],
                         face="feat_0002:face:cap_top")  # feat_0005
        _commit_cut(ws, "feat_0005", depth=3.0)          # feat_0006 the pocket

        features = part_sidecar(ws)["feature"]
        assert body_history.body_head(features) == "feat_0006"
        pocket = next(f for f in features if f["id"] == "feat_0006")
        # chain: consumed sketch + the BOSS (the prior head)
        assert pocket["depends_on_feature_ids"] == ["feat_0005", "feat_0004"]
        result = geometry.evaluate_part_with_provenance(features)
        roles = set(result.ledger.roles())
        # 6 base + 5 boss + 5 pocket = 16 faces, every role exactly once
        assert len(roles) == 16
        assert "feat_0004:face:cap_top" in roles   # the boss top
        assert "feat_0006:face:cap_top" in roles   # the pocket bottom
        topo = topology.extract_part_topology(features)
        assert roles == {f.face_id for f in topo.faces}


class TestCutRefusals:
    def test_through_cut_refuses(self, workspace_with_part):
        """depth 20 through a 10-thick base: the far cap would be modified and
        the removed volume would mismatch — refused (blind pockets only)."""
        ws = workspace_with_part
        _build_base_box(ws)
        _add_face_sketch(ws, prims=POCKET_RECT)
        with pytest.raises(TransactionError, match="blind|only its support|BLIND"):
            _commit_cut(ws, "feat_0003", depth=20.0)

    def test_cut_on_the_base_still_refuses(self, workspace_with_part):
        ws = workspace_with_part
        propose(ws, kind="mechanical.add_sketch_feature", params={
            "part_number": "P-000001",
            "primitives": [{"type": "rectangle", "x_mm": 0, "y_mm": 0,
                            "width_mm": 40.0, "height_mm": 25.0}],
        }).commit()
        with pytest.raises(TransactionError, match="nothing to cut from"):
            propose(ws, kind="mechanical.add_extrude_feature", params={
                "part_number": "P-000001", "sketch_feature_id": "feat_0001",
                "depth_mm": 10.0, "direction": "normal-", "operation": "cut",
            }).commit()


class TestCutFailClosedBranches:
    """The cut survival proof's branch witnesses (the Codex10 discipline,
    applied preemptively): sentinels + a deterministic fake history."""

    @staticmethod
    def _fake_history(deleted=(), modified=None):
        deleted_ids = {id(f) for f in deleted}
        modified = modified or {}

        class _Fake:
            def Modified(self, f):
                return modified.get(id(f), [])
            def IsDeleted(self, f):
                return id(f) in deleted_ids
        return _Fake()

    @staticmethod
    def _sentinels():
        from aiadra_mechanical.geometry import ProducedFaceHint
        contact, bottom = object(), object()
        support, other_body = object(), object()
        wall = object()
        ledger = [(support, "feat_0002:face:cap_top"), (other_body, "feat_0002:face:cap_base")]
        hints = [ProducedFaceHint(feature_id="feat_0006/skp_0001", role_base="wall_x_min", faces=(wall,))]
        return contact, bottom, support, other_body, wall, ledger, hints

    def test_modified_body_face_refuses(self):
        """The CUT-specific strictness: a non-support body face reporting a
        Modified image refuses (through/overshoot evidence)."""
        contact, bottom, support, other_body, wall, ledger, hints = self._sentinels()
        fake = self._fake_history(deleted=(contact,), modified={id(other_body): [object()]})
        with pytest.raises(TransactionError, match="MODIFIED owned body face"):
            geometry._assert_cut_survival(fake, ledger, hints, (contact, bottom), support, "feat_0006")

    def test_deleted_body_face_refuses(self):
        contact, bottom, support, other_body, wall, ledger, hints = self._sentinels()
        fake = self._fake_history(deleted=(contact, other_body))
        with pytest.raises(TransactionError, match="DELETED owned body face"):
            geometry._assert_cut_survival(fake, ledger, hints, (contact, bottom), support, "feat_0006")

    def test_deleted_pocket_wall_refuses(self):
        contact, bottom, support, other_body, wall, ledger, hints = self._sentinels()
        fake = self._fake_history(deleted=(contact, wall))
        with pytest.raises(TransactionError, match="DELETED intended pocket wall"):
            geometry._assert_cut_survival(fake, ledger, hints, (contact, bottom), support, "feat_0006")

    def test_deleted_pocket_bottom_refuses(self):
        contact, bottom, support, other_body, wall, ledger, hints = self._sentinels()
        fake = self._fake_history(deleted=(contact, bottom))
        with pytest.raises(TransactionError, match="pocket bottom"):
            geometry._assert_cut_survival(fake, ledger, hints, (contact, bottom), support, "feat_0006")

    def test_contradictory_support_history_refuses(self):
        """Codex12 B1: the support reporting one Modified image AND
        IsDeleted simultaneously is contradictory evidence — refused with a
        dedicated diagnostic (the support is exempt only from the
        Modified-must-be-empty rule, never from deletion evidence)."""
        contact, bottom, support, other_body, wall, ledger, hints = self._sentinels()
        fake = self._fake_history(
            deleted=(contact, support),
            modified={id(support): [object()]},
        )
        with pytest.raises(TransactionError, match="CONTRADICTORY.*support|support.*CONTRADICTORY"):
            geometry._assert_cut_survival(fake, ledger, hints, (contact, bottom), support, "feat_0006")

    def test_contradictory_contact_refuses(self):
        contact, bottom, support, other_body, wall, ledger, hints = self._sentinels()
        fake = self._fake_history(deleted=(contact,), modified={id(contact): [object()]})
        with pytest.raises(TransactionError, match="CONTRADICTORY"):
            geometry._assert_cut_survival(fake, ledger, hints, (contact, bottom), support, "feat_0006")

    def test_happy_path_passes(self):
        contact, bottom, support, other_body, wall, ledger, hints = self._sentinels()
        fake = self._fake_history(deleted=(contact,))
        geometry._assert_cut_survival(fake, ledger, hints, (contact, bottom), support, "feat_0006")
