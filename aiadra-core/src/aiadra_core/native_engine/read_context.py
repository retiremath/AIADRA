"""`NativeEngineReadContext` — the read-only counterpart to
`NativeEngineContext`, per arc 20260609-1 Codex1 B1.

A read-only Native Engine operation (e.g. generating a Display Representation)
must NOT be handed a staging-capable context. This context exposes ONLY
committed-state reads:

    workspace, bundle, actor, engine_id, operation_kind,
    find_reservation_entry_by_number, load_sidecar, load_reservation,
    event_log_last_event_id

It deliberately has **no** `stage_*`, `emit_event`, `make_event`, validation
hooks, or `transaction_id` — there is no in-flight `TransactionDraft` at all, so
a read handler cannot mutate Workspace state or blur audit/Transaction
semantics. Reads resolve **committed** Workspace authority via the validated
loaders (fail-loud on corrupt artifacts per Manifesto P5).

Versioned via `protocol_version` (mirrors `NativeEngineContext`).
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..validation.bundle_registry import BundleHandle


class NativeEngineReadContext:
    """Stable, read-only API surface a Native Engine READ handler receives via
    the read-dispatch adapter (arc 20260609-1 Codex1 B1).

    Uses `__slots__` (not a dataclass, mirroring `NativeEngineContext`) so the
    surface is a genuine barrier — there is no `_draft` to reach, by
    construction. Every method reads COMMITTED state only.
    """

    __slots__ = (
        "_workspace",
        "_bundle",
        "_actor",
        "_operation_kind",
        "_engine_id",
    )

    protocol_version: str = "1.0"

    def __init__(
        self,
        *,
        workspace: Path,
        bundle: "BundleHandle",
        actor: str,
        operation_kind: str,
        engine_id: str,
    ) -> None:
        self._workspace = workspace
        self._bundle = bundle
        self._actor = actor
        self._operation_kind = operation_kind
        self._engine_id = engine_id

    def __repr__(self) -> str:
        return (
            f"NativeEngineReadContext(engine_id={self._engine_id!r}, "
            f"operation_kind={self._operation_kind!r}, actor={self._actor!r}, "
            f"protocol_version={self.protocol_version!r})"
        )

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------

    @property
    def workspace(self) -> Path:
        return self._workspace

    @property
    def bundle(self) -> "BundleHandle":
        return self._bundle

    @property
    def actor(self) -> str:
        return self._actor

    @property
    def operation_kind(self) -> str:
        return self._operation_kind

    @property
    def engine_id(self) -> str:
        return self._engine_id

    # ------------------------------------------------------------------
    # Committed-state reads (NO draft; fail-loud via validated loaders)
    # ------------------------------------------------------------------

    def find_reservation_entry_by_number(
        self, number: str
    ) -> tuple[str, dict[str, Any]] | None:
        from ..truth_model.reservation import find_reservation_entry_by_number

        return find_reservation_entry_by_number(self._workspace, number)

    def load_sidecar(self, obj_uuid: str) -> dict[str, Any]:
        from ..validation.schema import load_sidecar_validated

        return load_sidecar_validated(
            self._workspace, obj_uuid, self._bundle.bundle_dir
        )

    def load_reservation(self, prefix: str) -> dict[str, Any]:
        from ..validation.schema import load_reservation_validated

        return load_reservation_validated(
            self._workspace, prefix, self._bundle.bundle_dir
        )

    def event_log_last_event_id(self) -> str | None:
        """Highest committed event_id, or None if no events exist. Committed
        state only — there are no staged events in a read context. Corrupt
        event log / missing bundle propagate (fail-loud), mirroring
        `NativeEngineContext.event_log_last_event_id`."""
        from ..truth_model.event_log import next_event_id

        next_committed = next_event_id(self._workspace, self._bundle.bundle_dir)
        last_n = int(next_committed[len("evt_"):]) - 1
        if last_n <= 0:
            return None
        return f"evt_{last_n:04d}"
