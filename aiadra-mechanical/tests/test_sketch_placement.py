"""The BS-1 placement floors (ADR/0044 Amendment A3; pass `sketch-place-1`).

Floors 1–5 of the ledger, engine side:
  1. LITERAL 0.2.0 compatibility — the checked-in pre-BS-1 oracle (captured
     from commit c779fa4 and verified byte-identical against it) decodes,
     regenerates, canonicalizes to the OLD hash, and displays the OLD world
     construction after 0.2.1 landed. The new code never regenerates its
     own oracle.
  2. The derivation matrix — all 48 admitted support/ref/orientation/side
     combinations against LITERAL expected axes; parallel refs refuse.
  3. The closed-shape/refusal matrix at the codec + handler surfaces.
  4. Identity — every placement fact changes canonical identity AND the
     topology skeleton; derived axes never persist.
  5. World mapping — v2_construction through the derived frame, both sides.
Plus the A3.6.1 operation-trace floor (legacy inputs → literal 0.2.0;
`placement` → 0.2.1; mixed refuses) and the A3.6.2 redefine floor
(minimal delta, provenance, no-change refusal, failure atomicity).
"""
from __future__ import annotations

import copy
import hashlib
import json
import types
from pathlib import Path

import pytest

from aiadra_core.transaction.boundary import TransactionError
from aiadra_mechanical import handlers, sketch_placement, sketch_v2
from aiadra_mechanical import display as display_mod
from aiadra_mechanical.kernel import _canonical_payload

DATA = Path(__file__).parent / "data"
ORACLE = json.loads((DATA / "oracle_v020_zx_g2.json").read_text())
MATRIX = [json.loads(line) for line in
          (DATA / "placement_matrix.jsonl").read_text().splitlines() if line]


def _canon_sha(record: dict) -> str:
    canon = json.dumps(_canonical_payload(record.get("adapter_payload", {})),
                       sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


def _fail(reason: str) -> None:
    raise AssertionError(reason)


def _author_placed(placement_input=None, axes="xy"):
    return sketch_v2.author_reference_sketch_placed(
        feature_id="feat_0001", name="references_feat_0001",
        placement_input=placement_input if placement_input is not None
        else {"support": {"kind": "principal", "orientation": "xy"}},
        axes=axes, x_axis_mm=20.0, y_axis_mm=20.0,
        fact_provenance={"category": "human_input"},
    )


class TestLiteralV020Floor:
    """Floor 1 — the pre-BS-1 oracle is LAW; new code cannot re-derive it."""

    def test_the_literal_record_still_decodes_and_regenerates(self):
        rec = ORACLE["record"]
        decoded = sketch_v2.decode_v2_sketch(rec)
        assert decoded["shape"] == "G2"
        solved = sketch_v2.regenerate_v2_sketch(rec)
        assert solved["skp_0002.x"] == 20.0 and solved["skp_0003.y"] == 20.0

    def test_the_literal_canonical_hash_is_unchanged(self):
        assert _canon_sha(ORACLE["record"]) == ORACLE["canonical_sha256"]
        # the oracle itself is a literal, not a derivation
        assert ORACLE["canonical_sha256"] == (
            "b986415ecc21aa12665e29561291b84fb6188f5e178a69d03422f5442aeb37d8")

    def test_the_literal_world_construction_is_unchanged(self):
        assert display_mod.build_v2_construction([ORACLE["record"]]) \
            == ORACLE["v2_construction"]


class TestDerivationMatrix:
    """Floor 2 — 48 literal-expected frames; refusals before any solver."""

    @pytest.mark.parametrize("support,ref,orientation,side,u,v,n", MATRIX)
    def test_exact_axes(self, support, ref, orientation, side, u, v, n):
        got_u, got_v, got_n = sketch_placement.derive_frame({
            "support": {"kind": "principal", "orientation": support},
            "orientation_ref": {"kind": "principal", "orientation": ref},
            "orientation": orientation,
            "normal_side": side,
        }, _fail)
        assert list(got_u) == pytest.approx(u, abs=0.0)
        assert list(got_v) == pytest.approx(v, abs=0.0)
        assert list(got_n) == pytest.approx(n, abs=0.0)

    def test_the_default_table_reproduces_the_legacy_frames_exactly(self):
        # A3.3: (xy→yz,right,+) = u+X v+Y · (yz→zx,right,+) = u+Y v+Z ·
        # (zx→xy,right,+) = u+Z v+X — the _FRAME_AXES parity, tolerance-free.
        want = {"xy": ((1, 0, 0), (0, 1, 0)), "yz": ((0, 1, 0), (0, 0, 1)),
                "zx": ((0, 0, 1), (1, 0, 0))}
        for support, (wu, wv) in want.items():
            u, v, _n = sketch_placement.derive_frame(
                sketch_placement.default_placement(support), _fail)
            assert u == tuple(float(x) for x in wu)
            assert v == tuple(float(x) for x in wv)

    def test_parallel_reference_refuses(self):
        with pytest.raises(AssertionError, match="differ from support"):
            sketch_placement.validate_placement_record({
                "support": {"kind": "principal", "orientation": "xy"},
                "orientation_ref": {"kind": "principal", "orientation": "xy"},
                "orientation": "right", "normal_side": "positive",
            }, _fail)


class TestClosedShapeRefusals:
    """Floor 3 — the codec + completion refusal matrix (engine semantics)."""

    def _placed_record(self):
        return _author_placed()

    @pytest.mark.parametrize("mutate,match", [
        (lambda p: p.pop("normal_side"), "missing.*normal_side"),
        (lambda p: p.update(extra=1), "unknown.*extra"),
        (lambda p: p.update(orientation="diagonal"), "orientation must be one of"),
        (lambda p: p.update(normal_side="up"), "normal_side must be one of"),
        (lambda p: p.update(support={"kind": "principal", "orientation": "xy", "x": 1}),
         "exactly"),
        (lambda p: p.update(support={"kind": "face", "orientation": "xy"}),
         "must be 'principal'"),
        (lambda p: p.update(support={"kind": "face", "target_face_id": "f"}),
         "exactly"),
        (lambda p: p.update(orientation_ref={"kind": "principal", "orientation": "zx"}),
         None),  # valid change — control row
    ])
    def test_placement_record_shapes(self, mutate, match):
        rec = self._placed_record()
        placement = dict(rec["adapter_payload"]["placement"])
        placement["support"] = dict(placement["support"])
        mutate(placement)
        rec2 = copy.deepcopy(rec)
        rec2["adapter_payload"]["placement"] = placement
        if match is None:
            sketch_v2.validate_v2_sketch_record(rec2)
        else:
            with pytest.raises(TransactionError, match=match):
                sketch_v2.validate_v2_sketch_record(rec2)

    def test_021_payload_with_plane_key_refuses(self):
        rec = self._placed_record()
        rec2 = copy.deepcopy(rec)
        rec2["adapter_payload"]["plane"] = {"kind": "principal", "orientation": "xy"}
        with pytest.raises(TransactionError, match="unknown.*plane"):
            sketch_v2.validate_v2_sketch_record(rec2)

    def test_020_payload_with_placement_key_refuses(self):
        rec = copy.deepcopy(ORACLE["record"])
        rec["adapter_payload"]["placement"] = \
            sketch_placement.default_placement("xy")
        with pytest.raises(TransactionError, match="unknown.*placement"):
            sketch_v2.validate_v2_sketch_record(rec)

    def test_unknown_02x_minor_still_refuses(self):
        rec = copy.deepcopy(ORACLE["record"])
        rec["adapter_schema_version"] = "0.2.3"  # 0.2.2 became DEFINED (A4)
        with pytest.raises(TransactionError, match="unknown 0.2.x minor"):
            sketch_v2.validate_v2_sketch_record(rec)

    def test_0_2_2_stamped_with_the_older_policy_refuses(self):
        """ADR/0044 A4: the version x policy matrix is CLOSED in both
        directions — a 0.2.2 record carrying skb-b0 never resolves."""
        rec = copy.deepcopy(_author_placed())     # a real 0.2.1 record ...
        rec["adapter_schema_version"] = "0.2.2"   # ... still stamped skb-b0
        with pytest.raises(TransactionError, match="matrix is closed"):
            sketch_v2.validate_v2_sketch_record(rec)

    def test_completion_requires_support(self):
        with pytest.raises(AssertionError, match="requires 'support'"):
            sketch_placement.complete_placement({"orientation": "right"}, _fail)

    def test_completion_refuses_unknown_members(self):
        with pytest.raises(AssertionError, match="unknown members"):
            sketch_placement.complete_placement(
                {"support": {"kind": "principal", "orientation": "xy"},
                 "flip": True}, _fail)


class TestIdentityFloor:
    """Floor 4 — each placement fact is identity-bearing; the skeleton
    carries the COMPLETE record; derived axes never persist."""

    def test_each_fact_changes_canonical_identity(self):
        base = _author_placed()
        base_sha = _canon_sha(base)
        variants = [
            {"support": {"kind": "principal", "orientation": "yz"}},
            {"orientation_ref": {"kind": "principal", "orientation": "zx"}},
            {"orientation": "top"},
            {"normal_side": "negative"},
        ]
        for over in variants:
            rec = copy.deepcopy(base)
            rec["adapter_payload"]["placement"].update(copy.deepcopy(over))
            # keep the record valid (support change may collide with ref)
            pl = rec["adapter_payload"]["placement"]
            if pl["support"]["orientation"] == pl["orientation_ref"]["orientation"]:
                pl["orientation_ref"] = {"kind": "principal", "orientation": "zx"}
            sketch_v2.validate_v2_sketch_record(rec)
            assert _canon_sha(rec) != base_sha, f"{over} did not change identity"

    def test_the_signature_carries_the_complete_placement(self):
        from aiadra_mechanical.topology import compute_topology_signature
        a = _author_placed({"support": {"kind": "principal", "orientation": "xy"}})
        b = copy.deepcopy(a)
        b["adapter_payload"]["placement"]["orientation"] = "top"
        # a placement fact changes the SIGNATURE (held selection invalidates)
        assert compute_topology_signature([a]) != compute_topology_signature([b])
        # ...but axis LENGTHS are values, not skeleton — same placement,
        # different lengths keeps the signature (value-independence)
        c = sketch_v2.author_reference_sketch_placed(
            feature_id="feat_0001", name="references_feat_0001",
            placement_input={"support": {"kind": "principal", "orientation": "xy"}},
            axes="xy", x_axis_mm=35.0, y_axis_mm=15.0,
            fact_provenance={"category": "human_input"})
        assert compute_topology_signature([a]) == compute_topology_signature([c])

    def test_no_derived_axes_in_the_persisted_record(self):
        rec = _author_placed()
        flat = json.dumps(rec)
        assert "u_vec" not in flat and "v_vec" not in flat


class TestWorldMappingFloor:
    """Floor 5 — v2_construction maps through the DERIVED frame, both sides."""

    def test_default_placement_matches_the_legacy_world_mapping(self):
        placed = _author_placed(
            {"support": {"kind": "principal", "orientation": "zx"}})
        legacy_world = ORACLE["v2_construction"][0]
        placed_world = display_mod.build_v2_construction([placed])[0]
        assert placed_world["points"] == legacy_world["points"]
        assert placed_world["lines"] == legacy_world["lines"]

    def test_negative_side_mirrors_the_v_axis(self):
        placed = _author_placed(
            {"support": {"kind": "principal", "orientation": "xy"},
             "normal_side": "negative"})
        pts = {p["id"]: p["at"] for p in
               display_mod.build_v2_construction([placed])[0]["points"]}
        # u stays +X; v = n×u with n=−Z → −Y: the sketch mirrors, exactly
        # the Petre-experiment semantics (the extrusion side flips with it)
        assert pts["skp_0002"] == [20.0, 0.0, 0.0]
        assert pts["skp_0003"] == [0.0, -20.0, 0.0]


class _HandlerHarness:
    def _ctx(self, monkeypatch, features=None, geoms=None):
        sidecar = {"feature": list(features or []),
                   "geometry_ref": list(geoms or [])}
        staged = {}
        events = []
        monkeypatch.setattr(handlers, "_resolve_part_sidecar",
                            lambda _c, _n: ("uuid-1", sidecar))
        monkeypatch.setattr(handlers, "_gate_validity", lambda _c, _f: None)
        ctx = types.SimpleNamespace(
            actor="human",
            stage_sidecar=lambda uuid, sc: staged.update({uuid: sc}),
            emit_event=lambda kind, payload: events.append((kind, payload)),
            stage_vault_bytes=lambda data: (
                handlers.vault_ref_for_bytes(data), "vault/x"),
        )
        return ctx, staged, events


class TestOperationTraceFloor(_HandlerHarness):
    """A3.6.1 — old operation inputs replay to literal 0.2.0; only the
    explicit `placement` member selects 0.2.1; mixing refuses."""

    def test_bare_part_number_still_writes_literal_020(self, monkeypatch):
        ctx, staged, _ = self._ctx(monkeypatch)
        handlers.handle_add_reference_sketch(ctx, {"part_number": "P-1"})
        rec = staged["uuid-1"]["feature"][0]
        assert rec["adapter_schema_version"] == "0.2.0"
        assert set(rec["adapter_payload"].keys()) == sketch_v2._PAYLOAD_KEYS

    def test_the_historical_plane_input_still_writes_the_oracle_bytes(self, monkeypatch):
        ctx, staged, _ = self._ctx(monkeypatch)
        handlers.handle_add_reference_sketch(
            ctx, {"part_number": "P-1",
                  "plane": {"kind": "principal", "orientation": "zx"}})
        rec = staged["uuid-1"]["feature"][0]
        assert rec == ORACLE["record"]  # the FULL literal, not just the hash
        assert _canon_sha(rec) == ORACLE["canonical_sha256"]

    def test_placement_selects_the_021_writer(self, monkeypatch):
        ctx, staged, _ = self._ctx(monkeypatch)
        handlers.handle_add_reference_sketch(
            ctx, {"part_number": "P-1",
                  "placement": {"support": {"kind": "principal",
                                            "orientation": "xy"}}})
        rec = staged["uuid-1"]["feature"][0]
        assert rec["adapter_schema_version"] == "0.2.1"
        assert rec["adapter_payload"]["placement"] == \
            sketch_placement.default_placement("xy")

    def test_mixed_vocabularies_refuse(self, monkeypatch):
        ctx, staged, events = self._ctx(monkeypatch)
        with pytest.raises(TransactionError, match="mutually exclusive"):
            handlers.handle_add_reference_sketch(
                ctx, {"part_number": "P-1",
                      "plane": {"kind": "principal", "orientation": "xy"},
                      "placement": {"support": {"kind": "principal",
                                                "orientation": "xy"}}})
        assert staged == {} and events == []


class TestRedefineFloor(_HandlerHarness):
    """A3.6.2 — minimal delta, provenance, no-change refusal, atomicity."""

    def _seed(self, monkeypatch):
        placed = _author_placed(
            {"support": {"kind": "principal", "orientation": "xy"}})
        geom = {"id": "geom_0001", "role": "authoring_geometry",
                "derived_from_feature_ids": [placed["id"]],
                "vault_ref": "sha256:" + "0" * 64}
        return self._ctx(monkeypatch, features=[placed], geoms=[geom]), placed

    def test_minimal_delta_and_event_provenance(self, monkeypatch):
        (ctx, staged, events), placed = self._seed(monkeypatch)
        handlers.handle_redefine_sketch_placement(
            ctx, {"part_number": "P-1", "sketch_feature_id": placed["id"],
                  "orientation": "top"})
        new = staged["uuid-1"]["feature"][0]
        assert new["adapter_payload"]["placement"]["orientation"] == "top"
        # omission KEPT everything else
        assert new["adapter_payload"]["placement"]["support"] == \
            placed["adapter_payload"]["placement"]["support"]
        # the minimal delta: records equal with placement removed
        a, b = copy.deepcopy(placed), copy.deepcopy(new)
        a["adapter_payload"].pop("placement")
        b["adapter_payload"].pop("placement")
        assert a == b  # incl. fact_provenance — old geometry not relabeled
        (kind, payload), = events
        assert payload["placement_provenance"] == {"category": "human_input"}

    def test_no_change_refuses_before_staging(self, monkeypatch):
        (ctx, staged, events), placed = self._seed(monkeypatch)
        with pytest.raises(TransactionError, match="sketch-placement-unchanged"):
            handlers.handle_redefine_sketch_placement(
                ctx, {"part_number": "P-1", "sketch_feature_id": placed["id"]})
        with pytest.raises(TransactionError, match="sketch-placement-unchanged"):
            handlers.handle_redefine_sketch_placement(
                ctx, {"part_number": "P-1", "sketch_feature_id": placed["id"],
                      "orientation": "right"})  # equals current
        assert staged == {} and events == []

    def test_a_020_record_refuses_with_the_named_copy(self, monkeypatch):
        ctx, staged, events = self._ctx(
            monkeypatch, features=[copy.deepcopy(ORACLE["record"])])
        with pytest.raises(TransactionError,
                           match="sketch-placement-redefine-v020"):
            handlers.handle_redefine_sketch_placement(
                ctx, {"part_number": "P-1", "sketch_feature_id": "feat_0001",
                      "orientation": "top"})
        assert staged == {} and events == []

    def test_wrong_targets_refuse_before_solving(self, monkeypatch):
        ctx, staged, events = self._ctx(monkeypatch, features=[])
        with pytest.raises(TransactionError, match="not found"):
            handlers.handle_redefine_sketch_placement(
                ctx, {"part_number": "P-1", "sketch_feature_id": "feat_0009",
                      "orientation": "top"})
        assert staged == {} and events == []

    def test_invalid_member_fails_atomically(self, monkeypatch):
        (ctx, staged, events), placed = self._seed(monkeypatch)
        with pytest.raises(TransactionError, match="normal_side must be one of"):
            handlers.handle_redefine_sketch_placement(
                ctx, {"part_number": "P-1", "sketch_feature_id": placed["id"],
                      "normal_side": "up"})
        assert staged == {} and events == []

    def test_the_op_is_registered(self):
        import aiadra_mechanical

        seen = {}
        registrar = types.SimpleNamespace(
            add_operation=lambda k, h: seen.update({k: h}),
            add_read_operation=lambda *a, **kw: None,
        )
        aiadra_mechanical.register(registrar)
        assert seen["mechanical.redefine_sketch_placement"] is \
            handlers.handle_redefine_sketch_placement
