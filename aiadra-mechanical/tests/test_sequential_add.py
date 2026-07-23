"""M-add (arc 20260717-2, ADR/0038 A4.8) — the FIRST sequential extrudes:
a boss fused onto a face-bound sketch's support, through the public protocol.

The walk Petre steered the arc toward: base box → sketch ON its top cap →
add-extrude → the boss. Identity assertions ride every step: the body chain,
the projection-staged body record, the consumed sketch record's removal, the
complete post-fuse ledger, and the extraction (which consumes the ledger).
Refusals: cut-until-M-cut, datum-bound sequential sketches, double
consumption, and the A4.8 strict-interior boundary."""
from __future__ import annotations

import pytest

from aiadra_core.protocol import propose
from aiadra_core.transaction.boundary import TransactionError

from aiadra_mechanical import body_history, geometry, kernel, topology
from conftest import part_sidecar


def _build_base_box(ws) -> None:
    """P-000001: a 40×25 rectangle on xy extruded 10 (the plain-rectangle
    ledgered base — the hole/fillet-compatible surface)."""
    propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001",
        "primitives": [{"type": "rectangle", "x_mm": 0, "y_mm": 0,
                        "width_mm": 40.0, "height_mm": 25.0}],
    }).commit()
    propose(ws, kind="mechanical.add_extrude_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001",
        "depth_mm": 10.0, "direction": "normal+",
    }).commit()


def _cap_top(ws) -> str:
    features = part_sidecar(ws)["feature"]
    topo = topology.extract_part_topology(features)
    return next(f.face_id for f in topo.faces if f.face_id.endswith(":face:cap_top"))


def _add_face_sketch(ws, *, prims, face=None) -> None:
    propose(ws, kind="mechanical.add_sketch_feature", params={
        "part_number": "P-000001",
        "plane": {"kind": "face", "target_face_id": face or _cap_top(ws)},
        "primitives": prims,
    }).commit()


BOSS_RECT = [{"type": "rectangle", "x_mm": 15.0, "y_mm": 8.0,
              "width_mm": 10.0, "height_mm": 8.0}]


class TestTheFirstBoss:
    def test_boss_on_the_top_cap(self, workspace_with_part):
        """THE WALK: base → face-bound sketch on cap_top → add-extrude →
        the boss. Chain, records, ledger, extraction — all asserted."""
        ws = workspace_with_part
        _build_base_box(ws)
        _add_face_sketch(ws, prims=BOSS_RECT)
        propose(ws, kind="mechanical.add_extrude_feature", params={
            "part_number": "P-000001", "sketch_feature_id": "feat_0003",
            "depth_mm": 6.0, "direction": "normal+", "operation": "add",
        }).commit()

        sidecar = part_sidecar(ws)
        features = sidecar["feature"]
        boss = next(f for f in features if f["id"] == "feat_0004")
        # the chain: consumed sketch + the prior body head
        assert boss["depends_on_feature_ids"] == ["feat_0003", "feat_0002"]
        assert body_history.body_predecessor(features, boss) == "feat_0002"
        assert body_history.body_head(features) == "feat_0004"

        # ONE body record at the new head; the consumed sketch record is GONE
        records = [g for g in sidecar["geometry_ref"] if g.get("role") == "authoring_geometry"]
        assert len(records) == 1
        body = records[0]
        assert body["derived_from_feature_ids"] == [
            "feat_0001", "feat_0002", "feat_0003", "feat_0004",
        ]
        proj = body_history.project_body_recipe(features, "feat_0004")
        expected = "sha256:" + __import__("hashlib").sha256(
            kernel.compute_recipe_bytes(list(proj.features))).hexdigest()
        assert body["vault_ref"] == expected

        # the LEDGER is complete through the fuse; extraction consumes it
        result = geometry.evaluate_part_with_provenance(features)
        assert result.ledger is not None
        roles = set(result.ledger.roles())
        # base roles survive (the support cap under its own role, RING-modified)
        assert "feat_0002:face:cap_top" in roles
        assert "feat_0002:face:cap_base" in roles
        # boss walls + top cap joined; its CONTACT cap lawfully deleted
        assert "feat_0004:face:cap_top" in roles
        assert "feat_0004:face:cap_base" not in roles
        assert any(r.startswith("feat_0004/") and r.endswith(":face:wall_x_min") for r in roles)
        topo = topology.extract_part_topology(features)
        assert roles == {f.face_id for f in topo.faces}
        # 6 base faces (cap_top ring-modified) + 5 boss faces
        assert len(roles) == 11

    def test_boss_rides_a_base_depth_edit(self, workspace_with_part):
        """Regeneration: editing the BASE depth re-evaluates the whole chain —
        the face-bound sketch re-resolves on the moved cap and the boss
        follows (the sequential ride, now an engine fact)."""
        ws = workspace_with_part
        _build_base_box(ws)
        _add_face_sketch(ws, prims=BOSS_RECT)
        propose(ws, kind="mechanical.add_extrude_feature", params={
            "part_number": "P-000001", "sketch_feature_id": "feat_0003",
            "depth_mm": 6.0, "direction": "normal+", "operation": "add",
        }).commit()
        propose(ws, kind="mechanical.adjust_feature_parameter", params={
            "part_number": "P-000001", "feature_id": "feat_0002",
            "parameter_name": "depth_mm", "new_value": 18.0,
        }).commit()
        features = part_sidecar(ws)["feature"]
        result = geometry.evaluate_part_with_provenance(features)
        assert result.ledger is not None
        # the boss cap now sits at base(18) + boss(6) = 24
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib
        top = next(f for f, r in result.ledger.faces if r == "feat_0004:face:cap_top")
        b = Bnd_Box()
        BRepBndLib.Add_s(top, b)
        assert abs(b.Get()[5] - 24.0) < 1e-6

    def test_modifier_on_the_boss(self, workspace_with_part):
        """The payoff of the whole identity arc: a fillet on an edge PRODUCED
        BY THE BOSS resolves mid-fold through the ledger and commits."""
        ws = workspace_with_part
        _build_base_box(ws)
        _add_face_sketch(ws, prims=BOSS_RECT)
        propose(ws, kind="mechanical.add_extrude_feature", params={
            "part_number": "P-000001", "sketch_feature_id": "feat_0003",
            "depth_mm": 6.0, "direction": "normal+", "operation": "add",
        }).commit()
        features = part_sidecar(ws)["feature"]
        topo = topology.extract_part_topology(features)
        boss_top_edges = [
            e for e in topo.edges
            if e.kind == "sharp" and "feat_0004:face:cap_top" in e.adjacent_face_ids
        ]
        assert boss_top_edges, "the boss's top edges must be addressable"
        propose(ws, kind="mechanical.add_fillet_feature", params={
            "part_number": "P-000001",
            "target_edge_id": sorted(e.edge_id for e in boss_top_edges)[0],
            "radius_mm": 1.5,
        }).commit()
        features = part_sidecar(ws)["feature"]
        fillet = next(f for f in features if f["feature_type"] == "fillet")
        # chain: the boss is the head; the boss also owns the referenced roles
        assert fillet["depends_on_feature_ids"] == ["feat_0004"]
        assert body_history.body_head(features) == "feat_0005"
        result = geometry.evaluate_part_with_provenance(features)
        assert "feat_0005:face:blend" in result.ledger.roles()


class TestSequentialRefusals:
    def test_cut_with_outward_direction_refuses(self, workspace_with_part):
        """M-cut era: a sequential CUT is legal — but it removes material
        INTO the body (normal-); an outward cut refuses on the
        operation-never-inferred-from-direction rule."""
        ws = workspace_with_part
        _build_base_box(ws)
        _add_face_sketch(ws, prims=BOSS_RECT)
        with pytest.raises(TransactionError, match="INTO the body"):
            propose(ws, kind="mechanical.add_extrude_feature", params={
                "part_number": "P-000001", "sketch_feature_id": "feat_0003",
                "depth_mm": 4.0, "direction": "normal+", "operation": "cut",
            }).commit()

    def test_datum_bound_sequential_sketch_refuses(self, workspace_with_part):
        ws = workspace_with_part
        _build_base_box(ws)
        propose(ws, kind="mechanical.add_sketch_feature", params={
            "part_number": "P-000001",
            "primitives": [{"type": "rectangle", "x_mm": 2, "y_mm": 2,
                            "width_mm": 5.0, "height_mm": 5.0}],
        }).commit()
        with pytest.raises(TransactionError, match="FACE-BOUND"):
            propose(ws, kind="mechanical.add_extrude_feature", params={
                "part_number": "P-000001", "sketch_feature_id": "feat_0003",
                "depth_mm": 4.0, "direction": "normal+", "operation": "add",
            }).commit()

    def test_double_consumption_refuses(self, workspace_with_part):
        """A face-bound sketch already consumed by one boss cannot feed a
        second extrude (the datum-bound base sketch refuses earlier, on the
        face-bound rule — this pins the consumption check specifically)."""
        ws = workspace_with_part
        _build_base_box(ws)
        _add_face_sketch(ws, prims=BOSS_RECT)
        propose(ws, kind="mechanical.add_extrude_feature", params={
            "part_number": "P-000001", "sketch_feature_id": "feat_0003",
            "depth_mm": 6.0, "direction": "normal+", "operation": "add",
        }).commit()
        with pytest.raises(TransactionError, match="already consumed"):
            propose(ws, kind="mechanical.add_extrude_feature", params={
                "part_number": "P-000001", "sketch_feature_id": "feat_0003",
                "depth_mm": 4.0, "direction": "normal+", "operation": "add",
            }).commit()

    def test_boundary_straddling_boss_refuses_strict_interior(self, workspace_with_part):
        """A4.8: a footprint reaching the support boundary refuses loudly
        (strict-interior clearance / history proof) — deferred, not guessed."""
        ws = workspace_with_part
        _build_base_box(ws)
        # footprint 0..40 = the full cap width — ON the boundary
        _add_face_sketch(ws, prims=[{"type": "rectangle", "x_mm": 0.0, "y_mm": 8.0,
                                     "width_mm": 40.0, "height_mm": 8.0}])
        with pytest.raises(TransactionError, match="strict|interior|boundary|A4.8"):
            propose(ws, kind="mechanical.add_extrude_feature", params={
                "part_number": "P-000001", "sketch_feature_id": "feat_0003",
                "depth_mm": 4.0, "direction": "normal+", "operation": "add",
            }).commit()

    def test_add_into_the_body_refuses_direction(self, workspace_with_part):
        ws = workspace_with_part
        _build_base_box(ws)
        _add_face_sketch(ws, prims=BOSS_RECT)
        with pytest.raises(TransactionError, match="AWAY from the body|sweeps"):
            propose(ws, kind="mechanical.add_extrude_feature", params={
                "part_number": "P-000001", "sketch_feature_id": "feat_0003",
                "depth_mm": 4.0, "direction": "normal-", "operation": "add",
            }).commit()


class TestFailClosedProofEdges:
    """Codex9 B1/B2 — adverse/incomplete OCCT history evidence REFUSES."""

    def test_incomplete_clearance_query_fails_closed(self, workspace_with_part, monkeypatch):
        """B1: a distance query that cannot complete refuses the transaction —
        never silently skips the pinned clearance."""
        ws = workspace_with_part
        _build_base_box(ws)
        _add_face_sketch(ws, prims=BOSS_RECT)
        propose(ws, kind="mechanical.add_extrude_feature", params={
            "part_number": "P-000001", "sketch_feature_id": "feat_0003",
            "depth_mm": 6.0, "direction": "normal+", "operation": "add",
        }).commit()
        features = part_sidecar(ws)["feature"]

        class _NeverDone:
            def __init__(self, *a, **k): pass
            def IsDone(self): return False
            def Value(self):  # pragma: no cover — must never be read
                raise AssertionError("Value() read before IsDone check")

        monkeypatch.setattr(geometry, "BRepExtrema_DistShapeShape", _NeverDone)
        from aiadra_mechanical import cache
        cache.clear()  # force a real re-evaluation through the patched query
        with pytest.raises(TransactionError, match="did not complete"):
            geometry.evaluate_part_with_provenance(features)

    def _survival_fixture(self, ws):
        """A committed boss; returns (fuse-stub inputs) captured from a real
        evaluation via a recording wrapper around the real Fuse."""
        _build_base_box(ws)
        _add_face_sketch(ws, prims=BOSS_RECT)
        propose(ws, kind="mechanical.add_extrude_feature", params={
            "part_number": "P-000001", "sketch_feature_id": "feat_0003",
            "depth_mm": 6.0, "direction": "normal+", "operation": "add",
        }).commit()
        return part_sidecar(ws)["feature"]

    @staticmethod
    def _lying_fuse_class(real_cls, lie):
        """Wrap the real Fuse; `lie(real, method, face)` may override."""
        class _Lying:
            def __init__(self, a, b):
                self._real = real_cls(a, b)
                self._tool = b
            def Shape(self):
                return self._real.Shape()
            def Modified(self, f):
                out = lie(self._real, "Modified", f)
                return self._real.Modified(f) if out is None else out
            def IsDeleted(self, f):
                out = lie(self._real, "IsDeleted", f)
                return self._real.IsDeleted(f) if out is None else out
        return _Lying

    def _expect_refusal(self, features, monkeypatch, lie, match):
        from aiadra_mechanical import cache
        real = geometry.BRepAlgoAPI_Fuse
        monkeypatch.setattr(
            geometry, "BRepAlgoAPI_Fuse", self._lying_fuse_class(real, lie)
        )
        cache.clear()
        with pytest.raises(TransactionError, match=match):
            geometry.evaluate_part_with_provenance(features)

    def test_unexpected_body_face_deletion_refuses(self, workspace_with_part, monkeypatch):
        """B2: the fuse claiming to have deleted a prior owned body face —
        outside the within-face domain, refused (never a smaller 'complete'
        ledger)."""
        features = self._survival_fixture(workspace_with_part)

        def lie(real, method, f):
            if method == "IsDeleted" and not real.IsDeleted(f) and not real.Modified(f):
                # the first RETAINED face queried — an owned body face
                return True
            return None

        self._expect_refusal(features, monkeypatch, lie, "DELETED owned body face|DELETED intended tool|far cap")

    def test_contradictory_contact_history_refuses(self, workspace_with_part, monkeypatch):
        """B2: the contact face reporting Modified images WHILE IsDeleted —
        contradictory evidence rejects at the A4.8 boundary."""
        features = self._survival_fixture(workspace_with_part)

        def lie(real, method, f):
            if method == "Modified" and real.IsDeleted(f):
                # the deleted contact face suddenly claims an image
                return [real.Shape()]  # any non-empty list
            return None

        self._expect_refusal(features, monkeypatch, lie, "CONTRADICTORY")

    # Codex10 B1: the tool-wall / far-cap survival branches are proven
    # DIRECTLY on `_assert_add_survival` with sentinel source faces and a
    # deterministic fake history — the arming-lie variant reached the body-
    # face guard first (checked earlier in the function) and never exercised
    # these branches. The diagnostics are NARROW: the owned-body-face message
    # may not satisfy either case.

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
    def _sentinel_setup():
        from aiadra_mechanical.geometry import ProducedFaceHint
        contact, far_cap = object(), object()
        body_a, body_b = object(), object()
        wall = object()
        ledger = [(body_a, "feat_0002:face:cap_top"), (body_b, "feat_0002:face:cap_base")]
        hints = [ProducedFaceHint(feature_id="feat_0004/skp_0001", role_base="wall_x_min", faces=(wall,))]
        return contact, far_cap, ledger, hints, wall

    def test_deleted_tool_wall_refuses_on_its_own_branch(self):
        contact, far_cap, ledger, hints, wall = self._sentinel_setup()
        fake = self._fake_history(deleted=(contact, wall))
        with pytest.raises(TransactionError, match="DELETED intended tool face"):
            geometry._assert_add_survival(fake, ledger, hints, (contact, far_cap), ledger[0][0], "feat_0004")

    def test_deleted_far_cap_refuses_on_its_own_branch(self):
        contact, far_cap, ledger, hints, _wall = self._sentinel_setup()
        fake = self._fake_history(deleted=(contact, far_cap))
        with pytest.raises(TransactionError, match="far cap"):
            geometry._assert_add_survival(fake, ledger, hints, (contact, far_cap), ledger[0][0], "feat_0004")

    def test_survival_happy_path_passes(self):
        contact, far_cap, ledger, hints, _wall = self._sentinel_setup()
        fake = self._fake_history(deleted=(contact,))
        geometry._assert_add_survival(fake, ledger, hints, (contact, far_cap), ledger[0][0], "feat_0004")  # no raise
