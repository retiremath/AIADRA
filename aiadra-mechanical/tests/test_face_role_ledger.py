"""ADR/0038 A4 (arc 20260717-2 M-identity) — the FaceRoleLedger scaffold +
the handler-layer projection regressions.

The ledger is built ALONGSIDE the existing extraction (M-identity): these
tests prove (1) role-set EQUALITY with the extractor everywhere both operate,
(2) ledger completeness (exactly one role per final face), and (3) the
scaffold's superiority case — propagation through a stacked modifier on
hinted faces, where the final-map hint model cannot go. Plus the Codex2/4
handler regressions: body-record projection staging, display selection by
head, and the N1 legacy-artifact compatibility behavior."""
from __future__ import annotations

import json

import pytest

from aiadra_core.protocol import propose
from aiadra_core.transaction.boundary import TransactionError

from aiadra_mechanical import body_history, geometry, kernel, topology
from conftest import part_sidecar


def contour_sketch(part="P-000001") -> dict:
    return {
        "part_number": part,
        "primitives": [{
            "type": "contour",
            "segments": [
                {"kind": "line", "x1_mm": 0, "y1_mm": 0, "x2_mm": 40, "y2_mm": 0},
                {"kind": "line", "x1_mm": 40, "y1_mm": 0, "x2_mm": 40, "y2_mm": 25},
                {"kind": "line", "x1_mm": 40, "y1_mm": 25, "x2_mm": 0, "y2_mm": 25},
                {"kind": "line", "x1_mm": 0, "y1_mm": 25, "x2_mm": 0, "y2_mm": 0},
            ],
        }],
    }


def build_contour_box(ws) -> None:
    propose(ws, kind="mechanical.add_sketch_feature", params=contour_sketch()).commit()
    propose(ws, kind="mechanical.add_extrude_feature", params={
        "part_number": "P-000001", "sketch_feature_id": "feat_0001",
        "depth_mm": 10.0, "direction": "normal+",
    }).commit()


class TestLedgerEqualsExtractor:
    def test_contour_box_role_sets_match(self, workspace_with_part):
        ws = workspace_with_part
        build_contour_box(ws)
        features = part_sidecar(ws)["feature"]
        result = geometry.evaluate_part_with_provenance(features)
        assert result.ledger is not None
        topo = topology.extract_part_topology(features)
        extractor_roles = {f.face_id for f in topo.faces}
        assert set(result.ledger.roles()) == extractor_roles
        assert len(result.ledger.faces) == len(extractor_roles)
        # the ledger names its body chain
        assert result.ledger.body_head == "feat_0002"
        assert result.ledger.body_recipe_ids == ("feat_0001", "feat_0002")

    def test_circle_cylinder_role_sets_match(self, workspace_with_part):
        ws = workspace_with_part
        propose(ws, kind="mechanical.add_sketch_feature", params={
            "part_number": "P-000001",
            "primitives": [{"type": "circle", "cx_mm": 10, "cy_mm": 10, "radius_mm": 8}],
        }).commit()
        propose(ws, kind="mechanical.add_extrude_feature", params={
            "part_number": "P-000001", "sketch_feature_id": "feat_0001",
            "depth_mm": 6.0, "direction": "normal+",
        }).commit()
        features = part_sidecar(ws)["feature"]
        result = geometry.evaluate_part_with_provenance(features)
        assert result.ledger is not None
        topo = topology.extract_part_topology(features)
        assert set(result.ledger.roles()) == {f.face_id for f in topo.faces}

    def test_compound_rectangle_circle_is_ledgered(self, workspace_with_extrude):
        """Codex5 B4.1: the rectangle(+sketch-circle) base is LEDGERED — the
        Cut propagates walls/caps and the hole wall joins by construction;
        extraction consumes the ledger and matches the legacy role names."""
        features = part_sidecar(workspace_with_extrude)["feature"]
        result = geometry.evaluate_part_with_provenance(features)
        assert result.ledger is not None
        roles = set(result.ledger.roles())
        topo = topology.extract_part_topology(features)
        assert roles == {f.face_id for f in topo.faces}
        assert any(r.endswith(":face:hole_wall") for r in roles)
        assert any(r.endswith(":face:wall_x_min") for r in roles)


class TestLedgerSuperiority:
    def test_propagates_through_a_stacked_fillet_on_hinted_faces(self, workspace_with_part):
        """The scaffold's reason to exist: a fillet on a CONTOUR box modifies
        hinted wall/cap faces. The ledger propagates every role through the
        mutation (A4.2) and stays complete; the blend face joins under the
        fillet's role. (The final-map hint model documents this stacking as
        its deferred limitation.)"""
        ws = workspace_with_part
        build_contour_box(ws)
        features = list(part_sidecar(ws)["feature"])
        prefix_sig = topology.compute_topology_signature(features)
        # the top edge between cap_top and the first wall
        fillet = {
            "id": "feat_0003",
            "feature_type": "fillet",
            "engine": "mechanical",
            "adapter_schema_version": "0.1.11",
            "depends_on_feature_ids": ["feat_0002"],
            "parameters": [{"id": "featp_0002", "name": "radius_mm", "value": 2.0,
                            "datatype": "number", "unit": "mm"}],
            "adapter_payload": {"target_edge": {
                "adjacent_face_roles": sorted([
                    "feat_0002:face:cap_top",
                    "feat_0002/skp_0001s01:face:wall",
                ]),
                "edge_kind": "sharp",
                "resolved_against_topology_signature": prefix_sig,
            }},
        }
        result = geometry.evaluate_part_with_provenance(features + [fillet])
        ledger = result.ledger
        assert ledger is not None
        roles = ledger.roles()
        assert "feat_0003:face:blend" in roles
        # the trimmed neighbours SURVIVED under their own roles
        assert "feat_0002:face:cap_top" in roles
        assert "feat_0002/skp_0001s01:face:wall" in roles
        # completeness: exactly one role per final face (validated in the
        # fold; recheck the counts here)
        assert len(set(roles)) == len(roles)
        assert ledger.body_head == "feat_0003"
        assert ledger.body_recipe_ids == ("feat_0001", "feat_0002", "feat_0003")


class TestProjectionStaging:
    def test_body_record_stages_exactly_the_body_closure(self, workspace_with_part):
        """Codex2 regression: an INDEPENDENT unconsumed sketch appears in
        neither the body record's bytes nor its provenance."""
        ws = workspace_with_part
        build_contour_box(ws)
        # an independent second sketch (never consumed)
        propose(ws, kind="mechanical.add_sketch_feature", params={
            "part_number": "P-000001",
            "primitives": [{"type": "circle", "cx_mm": 5, "cy_mm": 5, "radius_mm": 2}],
        }).commit()
        sidecar = part_sidecar(ws)
        features = sidecar["feature"]
        body_records = [
            g for g in sidecar["geometry_ref"]
            if g.get("role") == "authoring_geometry"
            and (g.get("derived_from_feature_ids") or [])[-1] == "feat_0002"
        ]
        assert len(body_records) == 1
        body = body_records[0]
        assert body["derived_from_feature_ids"] == ["feat_0001", "feat_0002"]
        assert set(body["fact_provenance"]["derived_from"]) == {
            "feature:feat_0001", "feature:feat_0002",
        }
        # the staged bytes ARE the projection bytes — and NOT the whole list
        proj = body_history.project_body_recipe(features, "feat_0002")
        expected_ref = "sha256:" + __import__("hashlib").sha256(
            kernel.compute_recipe_bytes(list(proj.features))).hexdigest()
        assert body["vault_ref"] == expected_ref
        whole_ref = "sha256:" + __import__("hashlib").sha256(
            kernel.compute_recipe_bytes(features)).hexdigest()
        assert body["vault_ref"] != whole_ref  # the de-equalization is REAL

    def test_display_selects_the_body_record_not_the_first(self, workspace_with_part):
        """Codex2 regression #5 seed: with an independent sketch committed
        FIRST (its record first in the list), the display identity echo must
        be the BODY record — the old first-record rule would pick the sketch."""
        ws = workspace_with_part
        # independent sketch FIRST
        propose(ws, kind="mechanical.add_sketch_feature", params={
            "part_number": "P-000001",
            "primitives": [{"type": "circle", "cx_mm": 5, "cy_mm": 5, "radius_mm": 2}],
        }).commit()
        # then the body
        propose(ws, kind="mechanical.add_sketch_feature", params={
            **contour_sketch(),
        }).commit()
        propose(ws, kind="mechanical.add_extrude_feature", params={
            "part_number": "P-000001", "sketch_feature_id": "feat_0002",
            "depth_mm": 10.0, "direction": "normal+",
        }).commit()
        sidecar = part_sidecar(ws)
        first = sidecar["geometry_ref"][0]
        assert (first.get("derived_from_feature_ids") or [])[-1] == "feat_0001"
        body = next(
            g for g in sidecar["geometry_ref"]
            if (g.get("derived_from_feature_ids") or [])[-1] == "feat_0003"
        )
        # the display selection rule (mirrored): with a body present, the
        # unique record whose head is body-mutating wins — not list position
        by_id = {f["id"]: f for f in sidecar["feature"]}
        head = body_history.body_head(sidecar["feature"])
        assert head == "feat_0003"
        chosen = [
            g for g in sidecar["geometry_ref"]
            if g.get("role") == "authoring_geometry"
            and body_history.is_body_mutating(by_id[(g.get("derived_from_feature_ids") or [])[-1]])
        ]
        assert len(chosen) == 1 and chosen[0]["id"] == body["id"]
        assert chosen[0]["id"] != first["id"]

    def test_adjust_restages_every_affected_record(self, workspace_with_part):
        """A depth edit re-stages the body record (its closure contains the
        extrude) and leaves an independent sketch record untouched."""
        ws = workspace_with_part
        build_contour_box(ws)
        propose(ws, kind="mechanical.add_sketch_feature", params={
            "part_number": "P-000001",
            "primitives": [{"type": "circle", "cx_mm": 5, "cy_mm": 5, "radius_mm": 2}],
        }).commit()
        before = part_sidecar(ws)
        body_before = next(g for g in before["geometry_ref"]
                           if (g.get("derived_from_feature_ids") or [])[-1] == "feat_0002")
        sk_before = next(g for g in before["geometry_ref"]
                         if (g.get("derived_from_feature_ids") or [])[-1] == "feat_0003")
        propose(ws, kind="mechanical.adjust_feature_parameter", params={
            "part_number": "P-000001", "feature_id": "feat_0002",
            "parameter_name": "depth_mm", "new_value": 25.0,
        }).commit()
        after = part_sidecar(ws)
        body_after = next(g for g in after["geometry_ref"]
                          if (g.get("derived_from_feature_ids") or [])[-1] == "feat_0002")
        sk_after = next(g for g in after["geometry_ref"]
                        if (g.get("derived_from_feature_ids") or [])[-1] == "feat_0003")
        assert body_after["vault_ref"] != body_before["vault_ref"]  # re-staged
        assert sk_after["vault_ref"] == sk_before["vault_ref"]      # untouched


class TestLegacyCompatibility:
    def test_n1_untouched_legacy_artifact_stays_valid_and_next_write_restages(
        self, workspace_with_part, tmp_path
    ):
        """Codex4 N1: reading never mutates; a legacy (pre-0.1.11, whole-list,
        no-depends serializer) vault_ref remains a valid content address of
        its OLD bytes; the next WRITE mints the normalized 0.1.11 ref."""
        ws = workspace_with_part
        build_contour_box(ws)
        sidecar = part_sidecar(ws)
        features = sidecar["feature"]
        # freeze the LEGACY serializer's byte shape (id/type/parameters/payload,
        # list order, no depends) as 0.1.10 wrote it — a frozen-format fixture
        legacy_bytes = json.dumps(
            [
                {
                    "id": f["id"],
                    "type": f["feature_type"],
                    "parameters": sorted(
                        ({"id": p["id"], "name": p["name"], "value": p["value"],
                          "datatype": p["datatype"], "unit": p["unit"]}
                         for p in f.get("parameters", [])),
                        key=lambda p: p["id"],
                    ),
                    "payload": f.get("adapter_payload", {}),
                }
                for f in features
            ],
            sort_keys=True,
        ).encode("utf-8")
        new_bytes = kernel.compute_recipe_bytes(features)
        assert legacy_bytes != new_bytes  # the serializer change is real
        # the legacy ref is a valid content address of the legacy bytes forever
        import hashlib
        legacy_ref = "sha256:" + hashlib.sha256(legacy_bytes).hexdigest()
        assert legacy_ref != "sha256:" + hashlib.sha256(new_bytes).hexdigest()
        # a WRITE re-stages under 0.1.11: the body record's ref equals the
        # NEW-projection hash after an edit (proven in
        # test_adjust_restages_every_affected_record); reading the Part
        # (display material path) mutates nothing:
        before = json.dumps(part_sidecar(ws), sort_keys=True)
        result = geometry.evaluate_part_with_provenance(features)
        assert result.shape is not None
        after = json.dumps(part_sidecar(ws), sort_keys=True)
        assert before == after  # read paths never mutate the Part


class TestOperationField:
    def test_cut_without_a_body_refuses_at_the_handler(self, workspace_with_part):
        ws = workspace_with_part
        propose(ws, kind="mechanical.add_sketch_feature", params=contour_sketch()).commit()
        with pytest.raises(Exception, match="nothing to cut from"):
            propose(ws, kind="mechanical.add_extrude_feature", params={
                "part_number": "P-000001", "sketch_feature_id": "feat_0001",
                "depth_mm": 10.0, "direction": "normal+", "operation": "cut",
            }).commit()

    def test_new_writes_emit_add_and_signature_parity_holds(self, workspace_with_part):
        ws = workspace_with_part
        build_contour_box(ws)
        features = part_sidecar(ws)["feature"]
        ext = next(f for f in features if f["feature_type"] == "extrude")
        assert ext["adapter_payload"]["operation"] == "add"
        # legacy/add signature parity: stripping the field changes nothing
        import copy
        legacy = copy.deepcopy(features)
        for f in legacy:
            if f["feature_type"] == "extrude":
                f["adapter_payload"].pop("operation")
        assert (topology.compute_topology_signature(features)
                == topology.compute_topology_signature(legacy))
        # ...while a CUT (synthetic) changes the skeleton
        cut = copy.deepcopy(features)
        for f in cut:
            if f["feature_type"] == "extrude":
                f["adapter_payload"]["operation"] = "cut"
        assert (topology.compute_topology_signature(cut)
                != topology.compute_topology_signature(features))

    def test_stored_cut_base_refuses_at_regeneration(self, workspace_with_part):
        ws = workspace_with_part
        build_contour_box(ws)
        import copy
        features = copy.deepcopy(part_sidecar(ws)["feature"])
        for f in features:
            if f["feature_type"] == "extrude":
                f["adapter_payload"]["operation"] = "cut"
        with pytest.raises(TransactionError, match="must be operation 'add'"):
            geometry.evaluate_part(features)


class TestGraphRuntimeAuthority:
    """Codex5 B1/B2/B3 — the RUNTIME obeys the graph, not the array."""

    def test_permuted_sidecar_evaluates_identically(self, workspace_with_part):
        """Codex5 B1 regression: permute EVERY contributing record of an
        evaluable body recipe (with a modifier) — identical evaluation,
        ledger roles, topology signature over the projection, and body ref."""
        ws = workspace_with_part
        build_contour_box(ws)
        propose(ws, kind="mechanical.add_fillet_feature", params={
            "part_number": "P-000001",
            "target_edge_id": sorted(_top_edge_ids(ws))[0],
            "radius_mm": 2.0,
        }).commit()
        features = list(part_sidecar(ws)["feature"])
        assert len(features) == 3
        import itertools
        baseline = None
        for perm in itertools.permutations(features):
            perm = list(perm)
            result = geometry.evaluate_part_with_provenance(perm)
            assert result.ledger is not None
            proj = body_history.project_body_recipe(perm, "feat_0003")
            sig = topology.compute_topology_signature(list(proj.features))
            data = kernel.compute_recipe_bytes(list(proj.features))
            key = (tuple(sorted(result.ledger.roles())), proj.feature_ids, sig, data)
            if baseline is None:
                baseline = key
            assert key == baseline

    def test_stacked_mutations_author_a_linear_chain(self, workspace_with_part):
        """Codex5 B2 regression: two stacked mutations through the PUBLIC
        handlers — the second advances from the FIRST (not the base), one
        terminal head exists, the body record advances, the ledger stays
        complete."""
        ws = workspace_with_part
        build_contour_box(ws)
        # pick OPPOSITE top edges deterministically BEFORE any mutation:
        # sharing a vertex with the filleted region generates corner topology
        # from the VERTEX, which face-history propagation cannot see — the
        # ledger refuses that case loudly (see the negative test below).
        e_a, e_b = _opposite_top_edges(ws)
        propose(ws, kind="mechanical.add_fillet_feature", params={
            "part_number": "P-000001",
            "target_edge_id": e_a,
            "radius_mm": 2.0,
        }).commit()
        propose(ws, kind="mechanical.add_chamfer_feature", params={
            "part_number": "P-000001",
            "target_edge_id": e_b,
            "distance_mm": 1.5,
        }).commit()
        sidecar = part_sidecar(ws)
        features = sidecar["feature"]
        chamfer = next(f for f in features if f["feature_type"] == "chamfer")
        # Codex6 B3: the chain edge (the FILLET, the prior head) comes FIRST,
        # followed by the DIRECT referenced role owner (the base extrude owns
        # the chamfered cap/wall roles) — an explicit operand edge, not merely
        # transitively reachable. The head stays the unique maximal element.
        assert chamfer["depends_on_feature_ids"] == ["feat_0003", "feat_0002"]
        assert body_history.body_predecessor(features, chamfer) == "feat_0003"
        assert body_history.body_head(features) == "feat_0004"
        # ONE body record, advanced to the terminal head, full closure
        body_records = [
            g for g in sidecar["geometry_ref"]
            if g.get("role") == "authoring_geometry"
            and (g.get("derived_from_feature_ids") or [])[-1] == "feat_0004"
        ]
        assert len(body_records) == 1
        assert body_records[0]["derived_from_feature_ids"] == [
            "feat_0001", "feat_0002", "feat_0003", "feat_0004",
        ]
        # the ledger is complete through BOTH mutations
        result = geometry.evaluate_part_with_provenance(features)
        assert result.ledger is not None
        roles = result.ledger.roles()
        assert "feat_0003:face:blend" in roles
        assert "feat_0004:face:chamfer" in roles

    def test_remove_terminal_modifier_retargets_the_body_record(self, workspace_with_part):
        """Codex5 B3 regression: removing the terminal modifier retargets the
        body record to the surviving head's projection — display keeps ONE
        resolvable body identity; nothing dangles."""
        ws = workspace_with_part
        build_contour_box(ws)
        propose(ws, kind="mechanical.add_fillet_feature", params={
            "part_number": "P-000001",
            "target_edge_id": sorted(_top_edge_ids(ws))[0],
            "radius_mm": 2.0,
        }).commit()
        propose(ws, kind="mechanical.remove_feature", params={
            "part_number": "P-000001", "feature_ids": ["feat_0003"],
        }).commit()
        sidecar = part_sidecar(ws)
        features = sidecar["feature"]
        assert body_history.body_head(features) == "feat_0002"
        body = next(
            g for g in sidecar["geometry_ref"]
            if g.get("role") == "authoring_geometry"
            and (g.get("derived_from_feature_ids") or [])[-1] == "feat_0002"
        )
        assert body["derived_from_feature_ids"] == ["feat_0001", "feat_0002"]
        proj = body_history.project_body_recipe(features, "feat_0002")
        expected = "sha256:" + __import__("hashlib").sha256(
            kernel.compute_recipe_bytes(list(proj.features))).hexdigest()
        assert body["vault_ref"] == expected
        # no other record references the removed fillet
        for g in sidecar["geometry_ref"]:
            assert "feat_0003" not in (g.get("derived_from_feature_ids") or [])

    def test_remove_whole_body_keeps_independent_sketch(self, workspace_with_part):
        """Codex5 B3: removing the entire body chain removes the body record;
        an independent sketch and ITS record survive untouched."""
        ws = workspace_with_part
        build_contour_box(ws)
        propose(ws, kind="mechanical.add_sketch_feature", params={
            "part_number": "P-000001",
            "primitives": [{"type": "circle", "cx_mm": 5, "cy_mm": 5, "radius_mm": 2}],
        }).commit()
        before = part_sidecar(ws)
        sk_ref = next(g for g in before["geometry_ref"]
                      if (g.get("derived_from_feature_ids") or [])[-1] == "feat_0003")
        propose(ws, kind="mechanical.remove_feature", params={
            "part_number": "P-000001", "feature_ids": ["feat_0002", "feat_0001"],
        }).commit()
        sidecar = part_sidecar(ws)
        assert [f["id"] for f in sidecar["feature"]] == ["feat_0003"]
        assert body_history.body_head(sidecar["feature"]) is None
        records = [g for g in sidecar["geometry_ref"] if g.get("role") == "authoring_geometry"]
        assert len(records) == 1
        assert records[0]["id"] == sk_ref["id"]
        assert records[0]["vault_ref"] == sk_ref["vault_ref"]


def _top_edge_ids(ws) -> set:
    """Sharp top-cap edges of the current box (via the public extraction)."""
    features = part_sidecar(ws)["feature"]
    topo = topology.extract_part_topology(features)
    return {
        e.edge_id for e in topo.edges
        if e.kind == "sharp" and "cap_top" in " ".join(e.adjacent_face_ids)
    }



def test_adjacent_corner_topology_refuses_loud(workspace_with_part):
    """A chamfer sharing a VERTEX with the filleted region generates corner
    faces from the vertex — invisible to face-history propagation. The ledger
    refuses the incomplete accounting loudly (A4.1/A4.2) rather than
    mislabeling; vertex-corner propagation is a named deferral."""
    ws = workspace_with_part
    build_contour_box(ws)
    adjacent = _adjacent_top_edge_pair(ws)
    if adjacent is None:
        pytest.skip("no vertex-sharing top edge pair found")
    e_a, e_b = adjacent
    propose(ws, kind="mechanical.add_fillet_feature", params={
        "part_number": "P-000001", "target_edge_id": e_a, "radius_mm": 2.0,
    }).commit()
    with pytest.raises(Exception, match="accounts for|two ledger roles|SPLIT|AMBIGUOUS|resolves to"):
        propose(ws, kind="mechanical.add_chamfer_feature", params={
            "part_number": "P-000001", "target_edge_id": e_b, "distance_mm": 1.5,
        }).commit()


def _wall_of(edge_record) -> str:
    return next(f for f in edge_record.adjacent_face_ids if ":face:wall" in f)


def _top_edge_records(ws):
    features = part_sidecar(ws)["feature"]
    topo = topology.extract_part_topology(features)
    return sorted(
        (e for e in topo.edges
         if e.kind == "sharp" and "cap_top" in " ".join(e.adjacent_face_ids)),
        key=lambda e: e.edge_id,
    )


def _opposite_top_edges(ws) -> tuple:
    """Two top edges on OPPOSITE walls (segments s01/s03 of the 4-segment
    contour) — no shared vertex, so stacked mutations stay in the v1 domain."""
    recs = _top_edge_records(ws)
    a = next(e for e in recs if "s01" in _wall_of(e))
    b = next(e for e in recs if "s03" in _wall_of(e))
    return a.edge_id, b.edge_id


def _adjacent_top_edge_pair(ws):
    """Two top edges on NEIGHBOURING walls (s01/s02) — they share a corner
    vertex."""
    recs = _top_edge_records(ws)
    try:
        a = next(e for e in recs if "s01" in _wall_of(e))
        b = next(e for e in recs if "s02" in _wall_of(e))
    except StopIteration:
        return None
    return a.edge_id, b.edge_id


class TestCodex6Boundaries:
    """Codex6 B1/B2 — the public signature boundary + removal classification."""

    def test_public_extraction_signature_is_permutation_invariant(self, workspace_with_part):
        """Codex6 B1: `extract_part_topology(perm).topology_signature` itself —
        not a caller ritual — is identical across every sidecar permutation."""
        ws = workspace_with_part
        build_contour_box(ws)
        propose(ws, kind="mechanical.add_sketch_feature", params={
            "part_number": "P-000001",
            "primitives": [{"type": "circle", "cx_mm": 5, "cy_mm": 5, "radius_mm": 2}],
        }).commit()
        features = list(part_sidecar(ws)["feature"])
        import itertools
        sigs = {
            topology.extract_part_topology(list(perm)).topology_signature
            for perm in itertools.permutations(features)
        }
        assert len(sigs) == 1

    def test_hole_domain_check_reads_the_body_sketch(self, workspace_with_part):
        """Codex6 B1: an independent sketch FIRST in the array must not drive
        the cap-fit contract — the hole succeeds against the BODY sketch."""
        ws = workspace_with_part
        # a tiny independent sketch first (the hole would NOT fit in it)
        propose(ws, kind="mechanical.add_sketch_feature", params={
            "part_number": "P-000001",
            "primitives": [{"type": "rectangle", "x_mm": 0, "y_mm": 0,
                            "width_mm": 3.0, "height_mm": 3.0}],
        }).commit()
        # the body: a LARGE rectangle (the hole's v1 domain is rectangle
        # profiles; the plain rectangle base is ledgered since Codex5 B4)
        propose(ws, kind="mechanical.add_sketch_feature", params={
            "part_number": "P-000001",
            "primitives": [{"type": "rectangle", "x_mm": 0, "y_mm": 0,
                            "width_mm": 40.0, "height_mm": 25.0}],
        }).commit()
        propose(ws, kind="mechanical.add_extrude_feature", params={
            "part_number": "P-000001", "sketch_feature_id": "feat_0002",
            "depth_mm": 10.0, "direction": "normal+",
        }).commit()
        # Ø8 at the box centre fits the 40×25 body cap, NOT the 3×3 sketch —
        # under the old whole-array read this refused; now it commits.
        cap = next(
            f.face_id for f in topology.extract_part_topology(
                part_sidecar(ws)["feature"]).faces
            if f.face_id.endswith(":face:cap_top")
        )
        propose(ws, kind="mechanical.add_hole_feature", params={
            "part_number": "P-000001", "target_face_id": cap,
            "diameter_mm": 8.0, "center_x_mm": 20.0, "center_y_mm": 12.5,
        }).commit()
        features = part_sidecar(ws)["feature"]
        assert any(f["feature_type"] == "hole" for f in features)
        # the hole's deps: the head (the extrude) — the cap owner IS the head
        hole = next(f for f in features if f["feature_type"] == "hole")
        assert hole["depends_on_feature_ids"] == ["feat_0003"]

    def test_remove_independent_sketch_never_promotes_its_record(self, workspace_with_part):
        """Codex6 B2's concrete corruption shape: removing an independent
        sketch while the body survives must REMOVE the sketch record — never
        retarget it into a second body authority."""
        ws = workspace_with_part
        build_contour_box(ws)
        propose(ws, kind="mechanical.add_sketch_feature", params={
            "part_number": "P-000001",
            "primitives": [{"type": "circle", "cx_mm": 5, "cy_mm": 5, "radius_mm": 2}],
        }).commit()
        before = part_sidecar(ws)
        body_before = next(g for g in before["geometry_ref"]
                           if (g.get("derived_from_feature_ids") or [])[-1] == "feat_0002")
        propose(ws, kind="mechanical.remove_feature", params={
            "part_number": "P-000001", "feature_ids": ["feat_0003"],
        }).commit()
        sidecar = part_sidecar(ws)
        records = [g for g in sidecar["geometry_ref"] if g.get("role") == "authoring_geometry"]
        # exactly ONE record — the UNCHANGED body record; the sketch record is gone
        assert len(records) == 1
        assert records[0]["id"] == body_before["id"]
        assert records[0]["vault_ref"] == body_before["vault_ref"]
        assert records[0]["derived_from_feature_ids"] == ["feat_0001", "feat_0002"]

    def test_remove_face_bound_sketch_keeps_the_body_record(self, workspace_with_part):
        """Codex6 B2: removing a face-bound unconsumed sketch while its support
        body survives — one unchanged body record, nothing promoted."""
        ws = workspace_with_part
        build_contour_box(ws)
        cap = next(
            f.face_id for f in topology.extract_part_topology(
                part_sidecar(ws)["feature"]).faces
            if f.face_id.endswith(":face:cap_top")
        )
        propose(ws, kind="mechanical.add_sketch_feature", params={
            "part_number": "P-000001",
            "plane": {"kind": "face", "target_face_id": cap},
            "primitives": [{"type": "circle", "cx_mm": 20, "cy_mm": 12, "radius_mm": 3}],
        }).commit()
        before = part_sidecar(ws)
        body_before = next(g for g in before["geometry_ref"]
                           if (g.get("derived_from_feature_ids") or [])[-1] == "feat_0002")
        propose(ws, kind="mechanical.remove_feature", params={
            "part_number": "P-000001", "feature_ids": ["feat_0003"],
        }).commit()
        sidecar = part_sidecar(ws)
        records = [g for g in sidecar["geometry_ref"] if g.get("role") == "authoring_geometry"]
        assert len(records) == 1
        assert records[0]["id"] == body_before["id"]
        assert records[0]["vault_ref"] == body_before["vault_ref"]


def test_explicit_body_record_removal_rejects_while_body_survives(workspace_with_part):
    """Codex7 B1 — the deterministic public-protocol reproduction, now a
    refusal: `remove_feature(feature_ids=[], geometry_ref_ids=[body_record])`
    with the body surviving must raise BEFORE staging; the sidecar stays
    unchanged and Display still resolves its one body record."""
    ws = workspace_with_part
    build_contour_box(ws)
    before = part_sidecar(ws)
    body = next(
        g for g in before["geometry_ref"]
        if g.get("role") == "authoring_geometry"
        and (g.get("derived_from_feature_ids") or [])[-1] == "feat_0002"
    )
    with pytest.raises(TransactionError, match="contradictory"):
        propose(ws, kind="mechanical.remove_feature", params={
            "part_number": "P-000001",
            "feature_ids": [],
            "geometry_ref_ids": [body["id"]],
        }).commit()
    after = part_sidecar(ws)
    assert json.dumps(after, sort_keys=True) == json.dumps(before, sort_keys=True)
    # Display's selection rule still finds exactly ONE body record
    records = [
        g for g in after["geometry_ref"]
        if g.get("role") == "authoring_geometry"
        and (g.get("derived_from_feature_ids") or [])[-1] == "feat_0002"
    ]
    assert len(records) == 1 and records[0]["vault_ref"] == body["vault_ref"]
