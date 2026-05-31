"""Transaction boundary — Draft-then-commit per state-changing CLI command.

Phase 0 lands the SHAPE only (kinds enum + draft/result types). The actual
Draft/Validate/Commit phase implementations land in Phase 1 per ADR/0025
Decision §6.

Per ADR/0025 §1: Phase 0 stubs Transaction operations with NotImplementedError
so Phase 1 has design freedom while the foundation infrastructure lands now.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID


class TransactionKind(str, Enum):
    """The Transaction kinds AIADRA Core surfaces.

    Implemented kinds:
        (none in Phase 0 — all Transaction operations land in Phase 1+)

    Phase 1 implements (per ADR/0025 §1):
        INIT, CHANGE_PARAMETER, CREATE_OBJECT, LINK_RELATIONSHIP,
        ATTACH_FILE, RELEASE, RELEASE_STAGE
    """
    INIT = "init"
    CHANGE_PARAMETER = "change_parameter"
    CREATE_OBJECT = "create_object"
    LINK_RELATIONSHIP = "link_relationship"
    ATTACH_FILE = "attach_file"
    RELEASE = "release"
    RELEASE_STAGE = "release_stage"


@dataclass
class ValidationOutcome:
    check_name: str
    result: str  # "PASS" | "FAIL"
    details: str = ""


@dataclass
class CommitResult:
    commit_hash: str
    transaction_id: str
    event_ids: list[str] = field(default_factory=list)


class TransactionDraft:
    """In-memory draft built during the Draft phase of Decision §6
    Draft-then-commit. Phase 1 implements; Phase 0 raises NotImplementedError.
    """

    def __init__(self, workspace: Path, kind: TransactionKind) -> None:
        self.workspace = workspace
        self.kind = kind

    def stage_sidecar_update(self, obj_uuid: str | UUID, new_sidecar: dict[str, Any]) -> None:
        raise NotImplementedError("lands in Phase 1 runtime-behavior arc; see ADR/0025 §1")

    def stage_event(self, event: dict[str, Any]) -> None:
        raise NotImplementedError("lands in Phase 1 runtime-behavior arc; see ADR/0025 §1")

    def stage_reservation_entry(self, prefix: str, number: str, obj_uuid: str | UUID) -> None:
        raise NotImplementedError("lands in Phase 1 runtime-behavior arc; see ADR/0025 §1")

    def stage_revision(
        self, obj_uuid: str | UUID, rev_id: str | UUID, content: dict[str, Any]
    ) -> None:
        raise NotImplementedError("lands in Phase 1 runtime-behavior arc; see ADR/0025 §1")

    def stage_manifest(self, release_label: str, manifest: dict[str, Any]) -> None:
        raise NotImplementedError("lands in Phase 1 runtime-behavior arc; see ADR/0025 §1")

    def stage_vault_write(self, data: bytes) -> tuple[str, str]:
        raise NotImplementedError("lands in Phase 1 runtime-behavior arc; see ADR/0025 §1")

    def validate(self) -> list[ValidationOutcome]:
        raise NotImplementedError("lands in Phase 1 runtime-behavior arc; see ADR/0025 §1")

    def commit(self) -> CommitResult:
        raise NotImplementedError("lands in Phase 1 runtime-behavior arc; see ADR/0025 §1")

    def rollback(self) -> None:
        """In-memory discard. Phase 0: no-op since nothing is ever staged."""
        return None


def begin(workspace: Path, kind: TransactionKind, **kwargs: Any) -> TransactionDraft:
    """Begin a Transaction. Phase 0 returns a stub draft; Phase 1 wires real
    Draft-then-commit per Decision §6.
    """
    raise NotImplementedError("lands in Phase 1 runtime-behavior arc; see ADR/0025 §1")
