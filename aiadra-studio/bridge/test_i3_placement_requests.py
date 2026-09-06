"""The connected I3 evidence (arc 20260905-1, Codex3 B5): the EXACT requests the
Studio pipeline produces — `src/authoring/i3PlacementRequests.test.ts` drives
the real dialog stores, the real accept, pointer rays through the flipped
frame, the real proposal builder, the production `commitIntent`, and the exact
main validator, then pins its output as `fixtures/i3-placement-requests.json` —
carried here through the REAL engine over the bridge: preview (the candidate,
a read), begin + commit (the acceptance), and the reopened display.

Run with the aiadra-core venv (wired as `npm run test:bridge`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bridge  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "i3-placement-requests.json"
PART = "P-000001"
SCENARIO = {
    "support": {"kind": "principal", "orientation": "xy"},
    "orientation_ref": {"kind": "principal", "orientation": "zx"},
    "orientation": "top",
    "normal_side": "negative",
}


@pytest.fixture(autouse=True)
def _clean_sessions():
    bridge._DRAFTS.clear()
    yield
    bridge._DRAFTS.clear()


@pytest.fixture(scope="module", autouse=True)
def _require_artifact():
    from aiadra_mechanical.solver import SolverArtifactMissingError, load_solver

    try:
        load_solver()
    except SolverArtifactMissingError as exc:
        pytest.skip(f"native solver artifact not built locally: {exc}")


def _workspace_with_part(tmp_path: Path) -> Path:
    from aiadra_core.protocol import propose

    ws = tmp_path / "ws"
    propose(ws, kind="init", params={}).commit()
    bridge.m_authoring_begin({
        "session_id": "part", "workspace_path": str(ws),
        "kind": "create_part", "op_params": {"number": PART, "name": "Bracket"},
    })
    bridge.m_authoring_commit({"session_id": "part", "workspace_path": str(ws)})
    return ws


def _near(vec, expected, eps=1e-9):
    return all(abs(a - b) <= eps for a, b in zip(vec, expected))


def test_the_fixture_is_the_studio_pipelines_output_shape():
    requests = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert [r["label"] for r in requests] == ["near-horizontal", "near-vertical"]
    for r in requests:
        assert r["kind"] == "mechanical.author_profile_sketch"
        assert r["params"]["part_number"] == PART
        assert r["params"]["placement"] == SCENARIO  # the dialog's four facts, verbatim


def test_the_studio_requests_preview_commit_and_reopen_through_the_real_engine(tmp_path: Path):
    from aiadra_core.protocol import display_representation, inspect

    requests = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ws = _workspace_with_part(tmp_path)
    committed: dict[str, str] = {}
    previews: dict[str, dict] = {}
    for r in requests:
        params = r["params"]
        # the candidate FIRST — a public read, nothing written
        pv = bridge.m_preview_sketch_graph({
            "workspace_path": str(ws), "object_ref": PART, "engine_id": "mechanical",
            "profile": params["profile"], "placement": params["placement"],
            "candidate_key": r["label"],
        })
        assert pv["refusal"] is None, pv["refusal"]
        previews[r["label"]] = pv["preview"]
        # the acceptance: the SAME request over the bridge's begin -> commit
        sid = f"i3-{r['label']}"
        out = bridge.m_authoring_begin({
            "session_id": sid, "workspace_path": str(ws), "kind": r["kind"], "op_params": params,
        })
        assert len(out["created_feature_ids"]) == 1
        committed[r["label"]] = out["created_feature_ids"][0]
        bridge.m_authoring_commit({"session_id": sid, "workspace_path": str(ws)})
        assert sid not in bridge._DRAFTS

    # the reopen: Truth + the display any later reader sees
    records = {f["id"]: f for f in inspect(ws, PART).sidecar["feature"]}
    pkg = display_representation(ws, PART)
    frames = {f.sketch_feature_id: f for f in pkg.sketch_frames}
    entries = {e.sketch_feature_id: e for e in pkg.v2_profiles}
    expected_fact = {"near-horizontal": "horizontal", "near-vertical": "vertical"}
    for r in requests:
        fid = committed[r["label"]]
        rec = records[fid]
        payload = rec["adapter_payload"]
        # the four persisted placement facts, the version/policy pairing
        assert rec["adapter_schema_version"] == "0.2.2"
        assert payload["branch_policy"] == "skb-b1"
        assert payload["placement"] == SCENARIO
        # the PROPOSED fact (Studio's snap under the flipped frame) is on the record
        assert any(c["kind"] == expected_fact[r["label"]] for c in payload["constraints"])
        # the frame the reader sees
        assert _near(frames[fid].u_axis, (-1.0, 0.0, 0.0))
        assert _near(frames[fid].v_axis, (0.0, 1.0, 0.0))
        assert _near(frames[fid].normal, (0.0, 0.0, -1.0))
        # solved local geometry + world mapping through THIS frame
        a, b = entries[fid].points[0].world, entries[fid].points[1].world
        if r["label"] == "near-horizontal":
            assert a[1] == pytest.approx(b[1], abs=1e-9)   # equal v -> equal world Y
            assert b[0] == pytest.approx(-20.0, abs=1e-9)  # sketch +u is world -X
        else:
            assert a[0] == pytest.approx(b[0], abs=1e-9)   # equal u -> equal world X
            assert b[1] == pytest.approx(15.0, abs=1e-9)   # sketch +v is world +Y
        # the candidate and the acceptance agree point for point
        assert [p["world"] for p in previews[r["label"]]["points"]] == \
            [list(p.world) for p in entries[fid].points]
