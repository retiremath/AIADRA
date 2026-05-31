"""Phase D tests — `simulate` + `explain` + `explain_failure` + audit log
emission per ADR/0026 §"Sequencing" Phase D + §9 (arc 20260531-10).

Covers Codex1 absorptions:
- B1 (simulate returns structured FAIL outcomes; no exceptions, no audit).
- B2 (explain workspace-ref AND explain_failure failure-tree — both exported).
- B3 (single-record audit emission via `_audit_emitted` flag).
- B4 (canonical per-kind ExplanationNode.details payloads).

Plus per-substream tests, dirty-guard carve-out, audit-config defaults, CLI
delegation, migrator chain.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from aiadra_core import protocol
from aiadra_core.audit import (
    AuditConfig,
    AuditRecord,
    apply_prune,
    audit_dir,
    audit_filename,
    compute_prune_set,
    compute_short_hash,
    list_audit_files,
    load_audit_config,
    write_audit_record,
)
from aiadra_core.explain import (
    ExplanationNode,
    ExplanationTree,
    KIND_OBJECT,
    KIND_RELATIONSHIP,
    KIND_VALIDATION_ERROR,
    REASON_CLASSIFICATIONS,
    classify_exception,
    event_node,
    object_node,
    relationship_node,
    tree_to_dict,
    validation_error_node,
)
from aiadra_core.protocol import (
    ExplanationTree as ProtocolExplanationTree,
    ObjectNotFoundError,
    ProjectPinError,
    TransactionDraft,
    TransactionError,
    ValidationOutcome,
    ValidationReport,
    commit,
    explain,
    explain_failure,
    propose,
    rollback,
    simulate,
)
from aiadra_core.transaction.boundary import git_repo_dirty_for_aiadra_paths
from aiadra_core.truth_model.reservation import find_reservation_entry_by_number
from aiadra_core.validation.binding import RevisionBindingError
from aiadra_core.validation.bundle_registry import BundleRegistry
from aiadra_core.validation.migration import REGISTERED_STEPS, apply_migration
from aiadra_core.validation.schema import SchemaValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_ws(tmp_path: Path, name: str = "ws") -> Path:
    workspace = tmp_path / name
    propose(workspace, kind="init", params={}).commit()
    return workspace


def _create_part(workspace: Path, number: str = "P-000001", with_param: bool = False) -> str:
    params: dict = {"number": number, "name": f"Part-{number}"}
    if with_param:
        params["extra_namespaces"] = {
            "parameter": [{
                "id": "param_thickness", "name": "plate_thickness_mm",
                "datatype": "number", "unit": "mm", "value": 7,
                "fact_provenance": {"category": "human_input"},
            }],
        }
    propose(workspace, kind="create_part", params=params).commit()
    _, entry = find_reservation_entry_by_number(workspace, number)
    return entry["object_uuid"]


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "aiadra_core.cli", *args],
        capture_output=True, text=True,
    )


# ---------------------------------------------------------------------------
# Module surface — closes 9-of-9 ADR/0026 §2 contracts
# ---------------------------------------------------------------------------


def test_phase_d_module_exports():
    """simulate + explain + explain_failure exported; ExplanationTree + Node re-exported."""
    assert callable(simulate)
    assert callable(explain)
    assert callable(explain_failure)
    assert ProtocolExplanationTree is ExplanationTree


def test_phase_d_closes_nine_of_nine_contracts():
    """All ADR/0026 §2 contracts now exist on protocol."""
    for name in ("inspect", "query", "propose", "modify", "simulate",
                 "validate", "explain", "commit", "rollback", "release"):
        assert hasattr(protocol, name), f"{name} missing"


def test_phase_d_explanation_tree_dataclass_frozen():
    """ExplanationNode + ExplanationTree are frozen dataclasses."""
    n = object_node(number="P-1", uuid="u", type="Part")
    with pytest.raises(Exception):
        n.kind = "other"  # frozen


# ---------------------------------------------------------------------------
# B4 — canonical per-kind ExplanationNode.details payloads
# ---------------------------------------------------------------------------


def test_codex1_b4_object_node_has_canonical_details():
    n = object_node(number="P-000001", uuid="0193abcd-1234-7890-abcd-444444444444", type="Part")
    assert n.kind == KIND_OBJECT
    for k in ("number", "uuid", "type", "source"):
        assert k in n.details
    assert n.details["source"] == "working"


def test_codex1_b4_object_node_rejects_invalid_source():
    with pytest.raises(ValueError, match="source"):
        object_node(number="P-1", uuid="u", type="Part", source="bogus")


def test_codex1_b4_relationship_node_has_canonical_details():
    n = relationship_node(
        source_uuid="src", relationship_id="rel_x", type="satisfies",
        endpoints=[{"object_uuid": "tgt"}],
    )
    assert n.kind == KIND_RELATIONSHIP
    for k in ("source_uuid", "relationship_id", "type", "endpoints"):
        assert k in n.details
    assert n.ref == "src:relationship:rel_x"


def test_codex1_b4_event_node_pulls_canonical_keys():
    ev = {"event_id": "evt_0001", "event_type": "part_created",
          "timestamp": "2026-05-31T12:00:00Z", "transaction_id": "tx_0001",
          "payload": {"uuid": "x"}}
    n = event_node(ev)
    for k in ("event_id", "event_type", "timestamp", "transaction_id"):
        assert k in n.details


def test_codex1_b4_validation_error_node_requires_known_classification():
    n = validation_error_node(
        error_type="SchemaValidationError",
        classification="schema_validation",
        check_name="schema(sidecar:foo)",
        message="bad shape",
    )
    assert n.kind == KIND_VALIDATION_ERROR
    for k in ("error_type", "classification", "check_name", "message"):
        assert k in n.details
    with pytest.raises(ValueError, match="classification"):
        validation_error_node(
            error_type="X", classification="bogus",
            check_name="c", message="m",
        )


def test_classify_exception_covers_known_exceptions():
    """The 6 enum values per ADR/0026 §9; unknown → other."""
    assert classify_exception(SchemaValidationError("x")) == "schema_validation"
    assert classify_exception(RevisionBindingError("x")) == "binding_violation"
    assert classify_exception(ValueError("x")) == "other"
    # Sanity: classification must be a valid enum member
    for cls_name in REASON_CLASSIFICATIONS:
        assert isinstance(cls_name, str)


# ---------------------------------------------------------------------------
# B1 — simulate returns structured FAIL outcomes (no exceptions, no audit)
# ---------------------------------------------------------------------------


def test_codex1_b1_simulate_passes_on_clean_draft(tmp_path: Path):
    """simulate on a clean draft returns ValidationReport with no failures."""
    workspace = _init_ws(tmp_path)
    _create_part(workspace, "P-000001")
    draft = propose(workspace, kind="create_part", params={"number": "P-000002", "name": "Plate"})
    report = simulate(draft)
    assert isinstance(report, ValidationReport)
    assert report.failures_count == 0
    assert all(o.result == "PASS" for o in report.outcomes)


def test_codex1_b1_simulate_collects_failures_without_raising(tmp_path: Path):
    """simulate MUST NOT raise on a known validation exception; instead
    appends a FAIL ValidationOutcome with `tree` populated."""
    workspace = _init_ws(tmp_path)
    _create_part(workspace, "P-000001", with_param=True)
    # Build a draft that link_executes between TST and an as-yet-uncreated TEX:
    # easier failure path — try a draft whose schema is invalid by injecting a
    # malformed staged sidecar after construction.
    draft = propose(workspace, kind="create_part", params={"number": "P-000002", "name": "Bracket"})
    # Mutate the staged sidecar to introduce a schema-invalid shape (missing
    # required object.lifecycle by clobbering it).
    obj_uuid = next(iter(draft.sidecar_writes))
    draft.sidecar_writes[obj_uuid]["object"].pop("lifecycle", None)
    report = simulate(draft)  # MUST NOT raise
    assert isinstance(report, ValidationReport)
    assert report.failures_count >= 1
    fail = next(o for o in report.outcomes if o.result == "FAIL")
    assert fail.tree is not None
    assert fail.tree.kind == KIND_VALIDATION_ERROR
    assert fail.tree.details["classification"] in REASON_CLASSIFICATIONS


def test_codex1_b1_simulate_emits_no_audit(tmp_path: Path):
    """simulate MUST NOT write a failed-Transaction audit record even when
    failures are present in the report."""
    workspace = _init_ws(tmp_path)
    draft = propose(workspace, kind="create_part", params={"number": "P-000001", "name": "X"})
    obj_uuid = next(iter(draft.sidecar_writes))
    draft.sidecar_writes[obj_uuid]["object"].pop("lifecycle", None)
    simulate(draft)
    assert list_audit_files(workspace) == []
    assert draft._audit_emitted is False


def test_codex1_b1_simulate_asserts_open(tmp_path: Path):
    """simulate on a closed (committed) draft raises TransactionError."""
    workspace = _init_ws(tmp_path)
    draft = propose(workspace, kind="create_part", params={"number": "P-000001", "name": "X"})
    draft.commit()
    with pytest.raises(TransactionError, match="committed"):
        simulate(draft)


def test_codex1_b1_validate_still_raises_on_first_fail(tmp_path: Path):
    """The commit-path `validate()` keeps raise-on-first-fail semantics."""
    workspace = _init_ws(tmp_path)
    draft = propose(workspace, kind="create_part", params={"number": "P-000001", "name": "X"})
    obj_uuid = next(iter(draft.sidecar_writes))
    draft.sidecar_writes[obj_uuid]["object"].pop("lifecycle", None)
    with pytest.raises(SchemaValidationError):
        draft.validate()  # commit-path: raises, doesn't collect


# ---------------------------------------------------------------------------
# B2 — explain workspace-ref AND explain_failure
# ---------------------------------------------------------------------------


def test_codex1_b2_explain_resolves_object_number(tmp_path: Path):
    workspace = _init_ws(tmp_path)
    uuid = _create_part(workspace, "P-000001")
    tree = explain(workspace, "P-000001", depth=0)
    assert isinstance(tree, ExplanationTree)
    assert tree.root.kind == KIND_OBJECT
    assert tree.root.details["uuid"] == uuid
    assert tree.root.details["number"] == "P-000001"
    assert tree.bundle_version  # non-empty


def test_codex1_b2_explain_resolves_object_uuid(tmp_path: Path):
    workspace = _init_ws(tmp_path)
    uuid = _create_part(workspace, "P-000001")
    tree = explain(workspace, uuid, depth=0)
    assert tree.root.details["uuid"] == uuid


def test_codex1_b2_explain_resolves_relationship_ref(tmp_path: Path):
    workspace = _init_ws(tmp_path)
    _create_part(workspace, "P-000001")
    propose(workspace, kind="create_requirement", params={
        "number": "REQ-000001", "name": "R",
        "extra_namespaces": {
            "requirement": {
                "statement": {"text": "shall do", "language": "en", "format": "freeform"},
                "category": "functional",
            },
        },
    }).commit()
    propose(workspace, kind="link_satisfies", params={
        "source_number": "P-000001", "target_number": "REQ-000001",
    }).commit()
    # Discover the relationship id from the part sidecar
    from aiadra_core.truth_model.sidecar import load_sidecar
    _, entry = find_reservation_entry_by_number(workspace, "P-000001")
    sc = load_sidecar(workspace, entry["object_uuid"])
    rel_id = sc["relationship"][0]["id"]
    ref = f"P-000001:relationship:{rel_id}"
    tree = explain(workspace, ref)
    assert tree.root.kind == KIND_RELATIONSHIP
    assert tree.root.details["relationship_id"] == rel_id


def test_codex1_b2_explain_includes_events_in_history(tmp_path: Path):
    workspace = _init_ws(tmp_path)
    _create_part(workspace, "P-000001")
    tree = explain(workspace, "P-000001", depth=0)
    # At least one event_node child for the part_created event
    event_children = [c for c in tree.root.children if c.kind == "event"]
    assert event_children, "expected at least one event in history"
    assert any(c.details["event_type"] == "part_created" for c in event_children)


def test_codex1_b2_explain_missing_ref_raises_object_not_found(tmp_path: Path):
    workspace = _init_ws(tmp_path)
    with pytest.raises(ObjectNotFoundError):
        explain(workspace, "P-999999")


def test_codex1_b2_explain_depth_traverses_related_objects(tmp_path: Path):
    """depth>0 walks ALL relationship types where this Object is source or target,
    capped at depth — per Codex Q3+N4."""
    workspace = _init_ws(tmp_path)
    _create_part(workspace, "P-000001")
    propose(workspace, kind="create_requirement", params={
        "number": "REQ-000001", "name": "R",
        "extra_namespaces": {
            "requirement": {
                "statement": {"text": "shall do", "language": "en", "format": "freeform"},
                "category": "functional",
            },
        },
    }).commit()
    propose(workspace, kind="link_satisfies", params={
        "source_number": "P-000001", "target_number": "REQ-000001",
    }).commit()
    tree = explain(workspace, "P-000001", depth=2)
    # At depth>0, related Object node(s) appear as children of the root
    related = [c for c in tree.root.children if c.kind == KIND_OBJECT]
    assert any(c.details["number"] == "REQ-000001" for c in related)


def test_codex1_b2_explain_no_pin_raises_project_pin_error(tmp_path: Path):
    workspace = tmp_path / "ws_no_pin"
    workspace.mkdir()
    with pytest.raises(ProjectPinError):
        explain(workspace, "P-000001")


def test_codex1_b2_explain_failure_from_validation_outcome(tmp_path: Path):
    """explain_failure accepts a ValidationOutcome with tree populated."""
    workspace = _init_ws(tmp_path)
    draft = propose(workspace, kind="create_part", params={"number": "P-000001", "name": "X"})
    obj_uuid = next(iter(draft.sidecar_writes))
    draft.sidecar_writes[obj_uuid]["object"].pop("lifecycle", None)
    report = simulate(draft)
    fail = next(o for o in report.outcomes if o.result == "FAIL")
    tree = explain_failure(fail, bundle_version=report.bundle_version)
    assert isinstance(tree, ExplanationTree)
    assert tree.root.kind == KIND_VALIDATION_ERROR


def test_codex1_b2_explain_failure_from_bare_explanation_node():
    n = validation_error_node(
        error_type="X", classification="other",
        check_name="c", message="m",
    )
    tree = explain_failure(n, bundle_version="0.27.0")
    assert tree.root is n
    assert tree.bundle_version == "0.27.0"


def test_codex1_b2_explain_failure_from_dict_audit_payload():
    """audit records carry validation_errors as dicts; explain_failure
    reconstructs ExplanationNode."""
    d = {
        "kind": "validation_error", "ref": "schema(sidecar:x)", "label": "SchemaValidationError",
        "details": {"error_type": "SchemaValidationError", "classification": "schema_validation",
                    "check_name": "schema(sidecar:x)", "message": "bad"},
        "children": [],
    }
    tree = explain_failure(d, bundle_version="0.27.0")
    assert tree.root.kind == KIND_VALIDATION_ERROR
    assert tree.root.details["classification"] == "schema_validation"


def test_codex1_b2_explain_failure_rejects_unknown_type():
    with pytest.raises(TypeError):
        explain_failure(12345, bundle_version="0.27.0")


# ---------------------------------------------------------------------------
# B3 — single-record audit emission via _audit_emitted flag
# ---------------------------------------------------------------------------


def test_codex1_b3_rollback_emits_audit_record(tmp_path: Path):
    workspace = _init_ws(tmp_path)
    draft = propose(workspace, kind="create_part", params={"number": "P-000001", "name": "X"})
    rollback(draft, reason="user cancelled")
    files = list_audit_files(workspace)
    assert len(files) == 1
    record = json.loads(files[0].read_text(encoding="utf-8"))
    assert record["transaction_id"] == draft.transaction_id
    assert record["reason_text"] == "user cancelled"
    assert record["reason_classification"] == "other"
    assert record["kind"] == "create_object"


def test_codex1_b3_rollback_no_audit_for_empty_draft(tmp_path: Path):
    """rollback() of an empty draft (no staged content) doesn't audit."""
    workspace = _init_ws(tmp_path)
    # Manually build a draft with no staged content via direct construction
    from aiadra_core.transaction.boundary import TransactionDraft, TransactionKind
    bundle = BundleRegistry().bundle_for_pin(workspace)
    empty = TransactionDraft(
        workspace=workspace, bundle=bundle, kind=TransactionKind.CREATE_OBJECT,
        transaction_id="tx_empty",
    )
    rollback(empty, reason="never staged")
    assert list_audit_files(workspace) == []


def test_codex1_b3_audit_failure_emits_then_rollback_skips(tmp_path: Path):
    """audit_failure() records the failure; subsequent rollback() must NOT
    double-emit (single-record semantics)."""
    workspace = _init_ws(tmp_path)
    draft = propose(workspace, kind="create_part", params={"number": "P-000001", "name": "X"})
    obj_uuid = next(iter(draft.sidecar_writes))
    draft.sidecar_writes[obj_uuid]["object"].pop("lifecycle", None)
    try:
        draft.validate()
    except SchemaValidationError as e:
        draft.audit_failure("validation raised", e)
    assert draft._audit_emitted is True
    files_after_audit = list_audit_files(workspace)
    assert len(files_after_audit) == 1
    # Now rollback — must NOT add a second file
    rollback(draft, reason="cleanup after fail")
    files_after_rollback = list_audit_files(workspace)
    assert len(files_after_rollback) == 1  # unchanged


def test_codex1_b3_classification_inferred_from_exception(tmp_path: Path):
    """audit_failure() classifies the exception when reason_classification
    is omitted."""
    workspace = _init_ws(tmp_path)
    draft = propose(workspace, kind="create_part", params={"number": "P-000001", "name": "X"})
    err = SchemaValidationError("bad")
    draft.audit_failure("manual", err)
    files = list_audit_files(workspace)
    record = json.loads(files[0].read_text(encoding="utf-8"))
    assert record["reason_classification"] == "schema_validation"


def test_codex1_b3_explicit_classification_overrides_inference(tmp_path: Path):
    workspace = _init_ws(tmp_path)
    draft = propose(workspace, kind="create_part", params={"number": "P-000001", "name": "X"})
    draft.audit_failure("manual", SchemaValidationError("x"), reason_classification="other")
    files = list_audit_files(workspace)
    record = json.loads(files[0].read_text(encoding="utf-8"))
    assert record["reason_classification"] == "other"


def test_codex1_b3_agent_ref_explicit_not_parsed(tmp_path: Path):
    """N1 absorption: agent_ref is explicit kwarg, NOT parsed from reason."""
    workspace = _init_ws(tmp_path)
    draft = propose(workspace, kind="create_part", params={"number": "P-000001", "name": "X"})
    rollback(draft, reason="cancelled", agent_ref="agent-alpha")
    record = json.loads(list_audit_files(workspace)[0].read_text(encoding="utf-8"))
    assert record["agent_ref"] == "agent-alpha"


def test_codex1_b3_audit_path_shape_per_adr(tmp_path: Path):
    """Path: .aiadra/audit/YYYY-MM-DD/tx_NNNN-failed-<short>.jsonl."""
    workspace = _init_ws(tmp_path)
    draft = propose(workspace, kind="create_part", params={"number": "P-000001", "name": "X"})
    rollback(draft, reason="r")
    files = list_audit_files(workspace)
    assert len(files) == 1
    p = files[0]
    parts = p.relative_to(workspace).parts
    assert parts[0] == ".aiadra"
    assert parts[1] == "audit"
    # date subdirectory
    assert len(parts[2]) == 10 and parts[2][4] == "-" and parts[2][7] == "-"
    # filename pattern
    assert parts[3].startswith(f"{draft.transaction_id}-failed-")
    assert parts[3].endswith(".jsonl")


def test_codex1_b3_collision_retry(tmp_path: Path):
    """If two records would land at the same path (rare hash collision),
    the second is suffixed `-1`."""
    workspace = _init_ws(tmp_path)
    workspace.mkdir(exist_ok=True)
    from aiadra_core.audit import _now_iso_utc
    ts = _now_iso_utc()
    r = AuditRecord(
        transaction_id="tx_clash", attempted_at=ts, kind="create_object",
        proposed_events=[], validation_errors=[],
        reason_classification="other", reason_text="r1",
    )
    p1 = write_audit_record(workspace, r)
    p2 = write_audit_record(workspace, r)  # same ts + tx => same hash, must retry
    assert p1 is not None and p2 is not None and p1 != p2


# ---------------------------------------------------------------------------
# AuditConfig + load defaults
# ---------------------------------------------------------------------------


def test_audit_config_defaults_when_missing(tmp_path: Path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    cfg = load_audit_config(workspace)
    assert cfg.max_entries_per_agent == 100
    assert cfg.max_age_days == 30
    assert cfg.max_total_mb == 50


def test_audit_config_loads_overrides(tmp_path: Path):
    workspace = tmp_path / "ws"
    (workspace / ".aiadra").mkdir(parents=True)
    (workspace / ".aiadra" / "audit-config.yaml").write_text(
        '"retention":\n  "max_age_days": 7\n  "max_total_mb": 5\n  "max_entries_per_agent": 50\n',
        encoding="utf-8",
    )
    cfg = load_audit_config(workspace)
    assert cfg.max_age_days == 7
    assert cfg.max_total_mb == 5
    assert cfg.max_entries_per_agent == 50


def test_audit_config_strict_raises_on_parse_error(tmp_path: Path):
    """N2 absorption: strict mode raises; non-strict (emission path) falls back to defaults."""
    workspace = tmp_path / "ws"
    (workspace / ".aiadra").mkdir(parents=True)
    (workspace / ".aiadra" / "audit-config.yaml").write_text(
        "this is: not\n  valid\n yaml: ::: :", encoding="utf-8",
    )
    # Non-strict falls back without raise
    cfg = load_audit_config(workspace, strict=False)
    assert cfg.max_age_days == 30
    # Strict raises
    with pytest.raises(Exception):
        load_audit_config(workspace, strict=True)


# ---------------------------------------------------------------------------
# Dirty-guard carve-out — N3 absorption
# ---------------------------------------------------------------------------


def test_dirty_guard_carve_out_for_audit_subdir(tmp_path: Path):
    """An untracked `.aiadra/audit/...` file does NOT make the workspace dirty
    per ADR/0026 §9 + Codex1 N3 absorption."""
    workspace = _init_ws(tmp_path)
    # Create an audit file (untracked from git's POV)
    (workspace / ".aiadra" / "audit" / "2026-05-31").mkdir(parents=True, exist_ok=True)
    (workspace / ".aiadra" / "audit" / "2026-05-31" / "tx_0099-failed-abc12345.jsonl").write_text(
        '{"transaction_id":"tx_0099"}\n', encoding="utf-8",
    )
    dirty, reason = git_repo_dirty_for_aiadra_paths(workspace)
    assert not dirty, f"unexpectedly dirty: {reason}"


def test_dirty_guard_still_guards_audit_config_yaml(tmp_path: Path):
    """`.aiadra/audit-config.yaml` at ROOT remains guarded (only the
    `.aiadra/audit/` subdirectory is carved out)."""
    workspace = _init_ws(tmp_path)
    (workspace / ".aiadra" / "audit-config.yaml").write_text(
        '"retention":\n  "max_age_days": 5\n', encoding="utf-8",
    )
    dirty, reason = git_repo_dirty_for_aiadra_paths(workspace)
    assert dirty
    assert "audit-config.yaml" in reason


# ---------------------------------------------------------------------------
# Audit-prune
# ---------------------------------------------------------------------------


def test_audit_prune_dry_run(tmp_path: Path):
    workspace = _init_ws(tmp_path)
    # Create 3 audit records
    for i in range(3):
        d = propose(workspace, kind="create_part", params={"number": f"P-00000{i+1}", "name": "X"})
        rollback(d, reason=f"r{i}")
    assert len(list_audit_files(workspace)) == 3
    # Very tight cap → would prune most
    cfg = AuditConfig(max_entries_per_agent=100, max_age_days=30, max_total_mb=0)
    to_del, to_keep = compute_prune_set(workspace, cfg)
    assert len(to_del) > 0
    # Dry-run did not actually delete
    assert len(list_audit_files(workspace)) == 3


def test_audit_prune_applies(tmp_path: Path):
    workspace = _init_ws(tmp_path)
    for i in range(3):
        d = propose(workspace, kind="create_part", params={"number": f"P-00000{i+1}", "name": "X"})
        rollback(d, reason=f"r{i}")
    cfg = AuditConfig(max_entries_per_agent=100, max_age_days=30, max_total_mb=0)
    count, freed = apply_prune(workspace, cfg)
    assert count > 0
    assert freed > 0


# ---------------------------------------------------------------------------
# CLI delegation
# ---------------------------------------------------------------------------


def test_cli_explain_human_text(tmp_path: Path):
    workspace = _init_ws(tmp_path)
    _create_part(workspace, "P-000001")
    result = _cli("explain", str(workspace), "P-000001")
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert "P-000001" in result.stdout
    assert "[object]" in result.stdout
    assert "[event]" in result.stdout


def test_cli_explain_json(tmp_path: Path):
    workspace = _init_ws(tmp_path)
    _create_part(workspace, "P-000001")
    result = _cli("explain", str(workspace), "P-000001", "--json")
    assert result.returncode == 0, f"stderr={result.stderr}"
    parsed = json.loads(result.stdout)
    assert parsed["root"]["kind"] == "object"
    assert parsed["root"]["details"]["number"] == "P-000001"


def test_cli_explain_unknown_ref_exits_2(tmp_path: Path):
    workspace = _init_ws(tmp_path)
    result = _cli("explain", str(workspace), "P-999999")
    assert result.returncode == 2


def test_cli_audit_list_empty(tmp_path: Path):
    workspace = _init_ws(tmp_path)
    result = _cli("audit", "list", str(workspace))
    assert result.returncode == 0
    assert "no audit records" in result.stdout


def test_cli_audit_list_and_show_round_trip(tmp_path: Path):
    workspace = _init_ws(tmp_path)
    d = propose(workspace, kind="create_part", params={"number": "P-000001", "name": "X"})
    rollback(d, reason="test")
    tx_id = d.transaction_id
    # list
    r1 = _cli("audit", "list", str(workspace))
    assert r1.returncode == 0
    assert tx_id in r1.stdout
    # show
    r2 = _cli("audit", "show", str(workspace), tx_id)
    assert r2.returncode == 0
    parsed = json.loads(r2.stdout.split("\n", 1)[1])  # skip "# <path>" header line
    assert parsed["transaction_id"] == tx_id


def test_cli_audit_prune_dry_run(tmp_path: Path):
    workspace = _init_ws(tmp_path)
    d = propose(workspace, kind="create_part", params={"number": "P-000001", "name": "X"})
    rollback(d, reason="x")
    result = _cli("audit-prune", str(workspace), "--dry-run")
    assert result.returncode == 0
    assert "dry-run" in result.stdout


# ---------------------------------------------------------------------------
# Migrator v0.26.0 → v0.27.0 chain
# ---------------------------------------------------------------------------


def test_bundle_v0_27_0_registered():
    bundle = BundleRegistry().bundle("0.27.0")
    assert bundle.bundle_version == "0.27.0"
    assert bundle.bundle_digest.startswith("sha256:")


def test_migration_step_26_to_27_registered():
    pairs = [(s.from_version, s.to_version) for s in REGISTERED_STEPS]
    assert ("0.26.0", "0.27.0") in pairs


def test_chain_migration_v0_19_0_to_v0_27_0(tmp_path: Path):
    workspace = tmp_path / "ws_mig"
    workspace.mkdir()
    (workspace / ".aiadra").mkdir()
    v019 = BundleRegistry().bundle("0.19.0")
    (workspace / ".aiadra" / "schemas.yaml").write_text(
        f'"bundle_version": "{v019.bundle_version}"\n'
        f'"bundle_digest": "{v019.bundle_digest}"\n',
        encoding="utf-8",
    )
    plan = apply_migration(workspace, "0.27.0")
    assert plan.from_bundle_version == "0.19.0"
    assert plan.to_bundle_version == "0.27.0"
    pin_text = (workspace / ".aiadra" / "schemas.yaml").read_text(encoding="utf-8")
    assert '"bundle_version": "0.27.0"' in pin_text


def test_cli_migrate_includes_v0_27_0_choice(tmp_path: Path):
    result = _cli("migrate", str(tmp_path / "nope"), "--to-bundle", "0.27.0", "--dry-run")
    assert "invalid choice" not in (result.stderr or "")


# ---------------------------------------------------------------------------
# tree_to_dict round-trip
# ---------------------------------------------------------------------------


def test_tree_to_dict_round_trip(tmp_path: Path):
    """tree_to_dict serializes; explain_failure can reconstruct from dict."""
    workspace = _init_ws(tmp_path)
    _create_part(workspace, "P-000001")
    tree = explain(workspace, "P-000001", depth=0)
    d = tree_to_dict(tree)
    rebuilt = explain_failure(d["root"], bundle_version=tree.bundle_version)
    assert rebuilt.root.kind == tree.root.kind
    assert rebuilt.root.ref == tree.root.ref


# ---------------------------------------------------------------------------
# Codex2 B1 regressions — max_entries_per_agent enforcement
# ---------------------------------------------------------------------------


def test_codex2_b1_max_entries_per_agent_same_agent_overflow(tmp_path: Path):
    """3 records same agent_ref + cap=1 → 2 marked for deletion (oldest 2)."""
    workspace = _init_ws(tmp_path)
    for i in range(3):
        d = propose(workspace, kind="create_part", params={"number": f"P-00000{i+1}", "name": "X"})
        rollback(d, reason=f"r{i}", agent_ref="agent-a")
    files = list_audit_files(workspace)
    assert len(files) == 3
    cfg = AuditConfig(max_entries_per_agent=1, max_age_days=30, max_total_mb=50)
    to_del, to_keep = compute_prune_set(workspace, cfg)
    assert len(to_del) == 2, f"expected 2 deletions; got {len(to_del)}"
    assert len(to_keep) == 1


def test_codex2_b1_max_entries_per_agent_cross_agent_independence(tmp_path: Path):
    """Per-agent buckets are INDEPENDENT — overflow in agent A does not
    affect agent B's quota."""
    workspace = _init_ws(tmp_path)
    # 3 records for agent-a + 1 for agent-b
    for i in range(3):
        d = propose(workspace, kind="create_part", params={"number": f"P-00000{i+1}", "name": "X"})
        rollback(d, reason=f"r{i}", agent_ref="agent-a")
    d = propose(workspace, kind="create_part", params={"number": "P-000010", "name": "X"})
    rollback(d, reason="r-b", agent_ref="agent-b")
    cfg = AuditConfig(max_entries_per_agent=1, max_age_days=30, max_total_mb=50)
    to_del, to_keep = compute_prune_set(workspace, cfg)
    # agent-a: 2 over cap; agent-b: 0 over cap
    assert len(to_del) == 2
    assert len(to_keep) == 2
    # Agent-b's file is still in to_keep
    kept_agents = {json.loads(p.read_text())["agent_ref"] for p in to_keep}
    assert "agent-b" in kept_agents
    assert "agent-a" in kept_agents


def test_codex2_b1_unknown_agent_bucket_capped(tmp_path: Path):
    """Files with null/missing agent_ref collapse into the `<unknown>` bucket
    so untagged records don't escape the cap."""
    workspace = _init_ws(tmp_path)
    for i in range(3):
        d = propose(workspace, kind="create_part", params={"number": f"P-00000{i+1}", "name": "X"})
        rollback(d, reason=f"r{i}")  # agent_ref=None
    cfg = AuditConfig(max_entries_per_agent=1, max_age_days=30, max_total_mb=50)
    to_del, _ = compute_prune_set(workspace, cfg)
    assert len(to_del) == 2


# ---------------------------------------------------------------------------
# Codex2 B2 regression — explain incoming-relationship traversal
# ---------------------------------------------------------------------------


def test_codex2_b2_explain_target_finds_source_via_incoming_scan(tmp_path: Path):
    """`P-000001 satisfies REQ-000001` → `explain(REQ-000001, depth=2)` MUST
    include `P-000001` as a related Object (incoming-relationship discovery
    requires scanning all working sidecars per Codex2 B2)."""
    workspace = _init_ws(tmp_path)
    _create_part(workspace, "P-000001")
    propose(workspace, kind="create_requirement", params={
        "number": "REQ-000001", "name": "R",
        "extra_namespaces": {
            "requirement": {
                "statement": {"text": "shall do", "language": "en", "format": "freeform"},
                "category": "functional",
            },
        },
    }).commit()
    propose(workspace, kind="link_satisfies", params={
        "source_number": "P-000001", "target_number": "REQ-000001",
    }).commit()
    tree = explain(workspace, "REQ-000001", depth=2)
    related = [c for c in tree.root.children if c.kind == KIND_OBJECT]
    assert any(c.details["number"] == "P-000001" for c in related), (
        f"expected P-000001 (incoming source) in related children; got {[c.details.get('number') for c in related]}"
    )


def test_codex2_b2_explain_source_still_finds_target(tmp_path: Path):
    """Regression: outgoing traversal still works after B2 refactor."""
    workspace = _init_ws(tmp_path)
    _create_part(workspace, "P-000001")
    propose(workspace, kind="create_requirement", params={
        "number": "REQ-000001", "name": "R",
        "extra_namespaces": {
            "requirement": {
                "statement": {"text": "shall do", "language": "en", "format": "freeform"},
                "category": "functional",
            },
        },
    }).commit()
    propose(workspace, kind="link_satisfies", params={
        "source_number": "P-000001", "target_number": "REQ-000001",
    }).commit()
    tree = explain(workspace, "P-000001", depth=2)
    related = [c for c in tree.root.children if c.kind == KIND_OBJECT]
    assert any(c.details["number"] == "REQ-000001" for c in related)


# ---------------------------------------------------------------------------
# Codex2 B3 regression — simulate skip-dependent-on-schema-fail + safety net
# ---------------------------------------------------------------------------


def test_codex2_b3_simulate_on_malformed_event_does_not_raise(tmp_path: Path):
    """Malformed staged event (missing event_type) must produce a
    ValidationReport with a FAIL outcome — not raise KeyError from fold."""
    workspace = _init_ws(tmp_path)
    draft = propose(workspace, kind="create_part", params={"number": "P-000001", "name": "X"})
    # Clobber the event_type so schema check fails AND fold would KeyError.
    draft.events[0].pop("event_type", None)
    report = simulate(draft)  # MUST NOT raise
    assert isinstance(report, ValidationReport)
    assert report.failures_count >= 1
    # The fold + b6 scan are SKIPPED (Codex2 B3 absorption) with explanatory FAIL
    skipped = [o for o in report.outcomes
               if o.result == "FAIL" and o.check_name in ("proposed_fold_invariant", "proposed_binding_mutation_scan")
               and "SKIPPED" in (o.details or "")]
    assert len(skipped) == 2


def test_codex2_b3_validate_on_malformed_event_still_raises(tmp_path: Path):
    """The commit-path `validate()` still raises on a malformed staged
    event — Phase D B3 only changes simulate's collect-mode behavior."""
    workspace = _init_ws(tmp_path)
    draft = propose(workspace, kind="create_part", params={"number": "P-000001", "name": "X"})
    draft.events[0].pop("event_type", None)
    with pytest.raises(SchemaValidationError):
        draft.validate()


# ---------------------------------------------------------------------------
# Codex2 N1 regression — rollback rejects invalid reason_classification
# ---------------------------------------------------------------------------


def test_codex2_n1_rollback_rejects_invalid_classification(tmp_path: Path):
    """Per Codex2 N1: silent coercion to `other` makes diagnostic data
    untrustworthy; rollback raises ValueError up-front while open."""
    workspace = _init_ws(tmp_path)
    draft = propose(workspace, kind="create_part", params={"number": "P-000001", "name": "X"})
    with pytest.raises(ValueError, match="reason_classification"):
        rollback(draft, reason="x", reason_classification="bogus")
    # Draft remains OPEN (rollback did not run because of the ValueError)
    assert draft._lifecycle_state == "open"


def test_codex2_n1_rollback_accepts_known_classifications(tmp_path: Path):
    """All 6 enum values pass; rollback succeeds + audit record carries them."""
    from aiadra_core.explain import REASON_CLASSIFICATIONS
    for cls in sorted(REASON_CLASSIFICATIONS):
        ws = _init_ws(tmp_path, name=f"ws_{cls}")
        d = propose(ws, kind="create_part", params={"number": "P-000001", "name": "X"})
        rollback(d, reason=f"reason for {cls}", reason_classification=cls)
        files = list_audit_files(ws)
        assert len(files) == 1
        record = json.loads(files[0].read_text(encoding="utf-8"))
        assert record["reason_classification"] == cls
