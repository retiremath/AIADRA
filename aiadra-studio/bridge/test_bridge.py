"""Bridge endpoint regressions (Codex14 B1, arc 20260730-1).

The general authoring lane's terminal gate: `m_authoring_commit` VALIDATES
the draft immediately before `protocol.commit` — `protocol.commit` does not
self-validate, and an earlier `simulate` is a UX read on a separate IPC
call, not an atomic terminal gate (the delete endpoint learned this first).

Run with the aiadra-core venv (wired as `npm run test:bridge`):

    ../aiadra-core/.venv/Scripts/python -m pytest bridge/test_bridge.py -q

Note on the invalid draft: legal authoring ops are handler-validated at
staging, so an invalid PROPOSED FOLD is not constructible through the
public op surface — by design. The regression therefore injects the fold
inconsistency at the event level (the same class the W-3 incident wrote to
disk): the gate must refuse it AT COMMIT, leave the session recoverable,
and leave the canonical workspace byte-unchanged.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bridge  # noqa: E402  (the module under test)


def _init_workspace(tmp_path: Path) -> Path:
    from aiadra_core.protocol import propose

    workspace = tmp_path / "ws"
    propose(workspace, kind="init", params={}).commit()
    return workspace


def _read_events(workspace: Path) -> list[str]:
    p = workspace / "events.jsonl"
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return [json.loads(line)["event_id"] for line in f if line.strip()]


def _begin_create_part(workspace: Path, session_id: str, number: str) -> None:
    bridge.m_authoring_begin({
        "session_id": session_id,
        "workspace_path": str(workspace),
        "kind": "create_part",
        "op_params": {"number": number, "name": "Bracket"},
    })


@pytest.fixture(autouse=True)
def _clean_sessions():
    bridge._DRAFTS.clear()
    yield
    bridge._DRAFTS.clear()


def test_commit_validates_and_refuses_an_invalid_fold(tmp_path: Path):
    """The terminal gate: an invalid proposed fold is refused AT COMMIT with
    the session recoverable and the canonical workspace unchanged."""
    workspace = _init_workspace(tmp_path)
    events_before = _read_events(workspace)
    _begin_create_part(workspace, "s1", "P-000001")

    # Inject a fold inconsistency of the W-3 class: a part_changed for an
    # Object no part_created event introduces.
    draft = bridge._DRAFTS["s1"]
    draft.events.append({
        "event_id": f"evt_{9999:04d}",
        "event_type": "part_changed",
        "transaction_id": draft.transaction_id,
        "payload": {
            "object_uuid": "00000000-0000-0000-0000-000000000000",
            "feature_delta": {"added": [], "updated": [], "removed": []},
        },
    })

    with pytest.raises(Exception):
        bridge.m_authoring_commit({
            "session_id": "s1", "workspace_path": str(workspace),
        })

    # the session survives the refusal (fix/retry/cancel contract)…
    assert "s1" in bridge._DRAFTS
    # …and nothing reached the canonical workspace
    assert _read_events(workspace) == events_before
    assert not list((workspace / "revisions").rglob("working.yaml")) or all(
        "P-000001" not in p.read_text(encoding="utf-8")
        for p in (workspace / "revisions").rglob("working.yaml")
    )
    # rollback still closes it cleanly
    bridge.m_authoring_rollback({"session_id": "s1"})
    assert "s1" not in bridge._DRAFTS


def test_commit_of_a_valid_draft_still_lands(tmp_path: Path):
    """The gate must not over-refuse: the ordinary begin→commit path works
    and closes the session on success."""
    workspace = _init_workspace(tmp_path)
    _begin_create_part(workspace, "s2", "P-000002")
    out = bridge.m_authoring_commit({
        "session_id": "s2", "workspace_path": str(workspace),
    })
    assert out["commit"]["transaction_id"]
    assert "s2" not in bridge._DRAFTS
    assert any(
        "P-000002" in p.read_text(encoding="utf-8")
        for p in (workspace / "revisions").rglob("working.yaml")
    )
