"""The commit log-advance guard (W-3, arc 20260730-1).

Event and transaction ids are allocated at staging time against the event log
as it then stands. Before this guard, two drafts staged against the same log
could BOTH commit — the second appending duplicate event ids — after which
every fold replay refuses and the workspace stops accepting commits entirely
(observed in the wild: tx_0050 committed twice, evt_0051 duplicated, every
subsequent transaction refused). The guard refuses the second commit BEFORE
the first byte is written.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiadra_core.protocol import propose, rollback
from aiadra_core.transaction.boundary import CommitError
from aiadra_core.truth_model.event_log import event_log_path


def _init_workspace(tmp_path: Path, name: str = "ws") -> Path:
    workspace = tmp_path / name
    propose(workspace, kind="init", params={}).commit()
    return workspace


def _create_part_draft(workspace: Path, number: str):
    return propose(workspace, kind="create_part", params={"number": number, "name": "Bracket"})


def _event_ids(workspace: Path) -> list[str]:
    with event_log_path(workspace).open(encoding="utf-8") as f:
        return [json.loads(line)["event_id"] for line in f if line.strip()]


def test_second_draft_staged_against_same_log_is_refused(tmp_path: Path):
    """The exact wild scenario: two drafts staged before either commits.
    The first commits; the second must refuse with NOTHING written."""
    workspace = _init_workspace(tmp_path)
    a = _create_part_draft(workspace, "P-000001")
    b = _create_part_draft(workspace, "P-000002")  # staged against the SAME log

    a.commit()
    events_after_a = _event_ids(workspace)

    with pytest.raises(CommitError, match="event log advanced under this draft"):
        b.commit()

    # nothing was written: the log is exactly as commit A left it, no duplicates
    assert _event_ids(workspace) == events_after_a
    assert len(set(events_after_a)) == len(events_after_a)
    # the second Part's sidecar/reservation writes did not land either
    assert not any(
        p.name == "working.yaml" and "P-000002" in p.read_text(encoding="utf-8")
        for p in (workspace / "revisions").rglob("working.yaml")
    )


def test_refused_draft_stays_open_and_rolls_back_cleanly(tmp_path: Path):
    """The guard's refusal leaves the draft OPEN (not terminal), so the
    caller can roll it back — the bridge's fix/retry/cancel contract."""
    workspace = _init_workspace(tmp_path)
    a = _create_part_draft(workspace, "P-000001")
    b = _create_part_draft(workspace, "P-000002")
    a.commit()
    with pytest.raises(CommitError):
        b.commit()
    result = rollback(b, reason="log advanced; discarding")
    assert result.discarded_change_count > 0


def test_restaged_draft_after_refusal_commits_cleanly(tmp_path: Path):
    """The recovery path the refusal message names: re-stage against current
    state and commit — fresh ids, clean fold."""
    workspace = _init_workspace(tmp_path)
    a = _create_part_draft(workspace, "P-000001")
    b = _create_part_draft(workspace, "P-000002")
    a.commit()
    with pytest.raises(CommitError):
        b.commit()
    rollback(b, reason="log advanced")

    again = _create_part_draft(workspace, "P-000002")
    again.commit()
    ids = _event_ids(workspace)
    assert len(set(ids)) == len(ids)  # unique throughout


def test_sequential_commits_are_untouched_by_the_guard(tmp_path: Path):
    """The ordinary lifecycle — stage, commit, stage, commit — never trips
    the guard."""
    workspace = _init_workspace(tmp_path)
    _create_part_draft(workspace, "P-000001").commit()
    _create_part_draft(workspace, "P-000002").commit()
    ids = _event_ids(workspace)
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)
