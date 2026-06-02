"""`NativeEngineContext` per ADR/0028 D3 + Codex1 B2 R1 + B4 R1 absorption arc
20260601-1.

Stable API surface that Native Engine handlers receive via dispatch. Wraps
`TransactionDraft` to hide internals + present a versionable contract.

B4 R1 absorption: NOT a dataclass — uses `__slots__` so `_draft` does not
appear in `dataclasses.fields()`, `repr()` (custom impl), or other dataclass-
discovery surfaces. The boundary ADR/0028 D3 creates is preserved as a
non-trivial barrier, not just convention.

B2 R1 absorption: exposes `make_event(event_type, payload, *, actor=None)` +
`emit_event(...)` envelope helpers using draft-aware event-id allocation so
two Native Engine operations composed in one draft do not collide on event_id.

Codex2 B2 R3 absorption from arc 20260531-12: validation hooks receive
`NativeEngineContext`, NOT raw `TransactionDraft`. Hook arity adapter
accepts 0-arg or 1-arg callables; rejects 2+ arg loudly per Codex3 N1 from
arc 12.
"""
from __future__ import annotations

import inspect
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .exceptions import NativeEngineRegistrationError

if TYPE_CHECKING:
    from ..transaction.boundary import TransactionDraft
    from ..validation.bundle_registry import BundleHandle


class NativeEngineContext:
    """Stable API surface Native Engine handlers use to interact with
    Workspace state + the in-flight Transaction draft per ADR/0028 D3.

    Uses `__slots__` (not a dataclass) so `_draft` does not appear in
    `dataclasses.fields()` or be enumerable through standard dataclass
    discovery — preserves the contract boundary at more than convention level
    (Codex1 B4 R1 absorption arc 20260601-1).

    Versioned via `protocol_version` (class attribute = `"1.0"`). Breaking
    changes bump the version; mechanism for engines to declare compatibility
    deferred per ADR/0028 D15 item 12.
    """

    __slots__ = (
        "_draft",
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
        draft: TransactionDraft,
        workspace: Path,
        bundle: BundleHandle,
        actor: str,
        operation_kind: str,
        engine_id: str,
    ) -> None:
        # Initialize all slots via direct attribute assignment (no __setattr__
        # guard on this class; the draft is internal-state of the wrapper).
        self._draft = draft
        self._workspace = workspace
        self._bundle = bundle
        self._actor = actor
        self._operation_kind = operation_kind
        self._engine_id = engine_id

    def __repr__(self) -> str:
        # Custom repr that does NOT expose _draft (would otherwise show the
        # entire TransactionDraft via default object repr).
        return (
            f"NativeEngineContext(engine_id={self._engine_id!r}, "
            f"operation_kind={self._operation_kind!r}, actor={self._actor!r}, "
            f"transaction_id={self._draft.transaction_id!r}, "
            f"protocol_version={self.protocol_version!r})"
        )

    # ------------------------------------------------------------------
    # Read-only properties (context introspection)
    # ------------------------------------------------------------------

    @property
    def workspace(self) -> Path:
        return self._workspace

    @property
    def bundle(self) -> BundleHandle:
        return self._bundle

    @property
    def actor(self) -> str:
        """Caller actor per ADR/0026 §5 + ADR/0028 D8. Native Engine handlers
        consume this to set provenance correctly: caller-supplied facts use
        `ai_proposal` if actor=agent or `human_input` if actor=human;
        engine-computed derivatives use `computed_result`."""
        return self._actor

    @property
    def operation_kind(self) -> str:
        """Full namespaced operation kind (e.g., `mechanical.adjust_parameter`)."""
        return self._operation_kind

    @property
    def engine_id(self) -> str:
        """Engine discriminator (e.g., `mechanical`). Frozen at dispatch time
        from the entry-point name per ADR/0028 D2."""
        return self._engine_id

    @property
    def transaction_id(self) -> str:
        return self._draft.transaction_id

    # ------------------------------------------------------------------
    # Draft-aware read APIs (delegate to arc 9 Phase C Codex1 B1 helpers)
    # ------------------------------------------------------------------

    def find_reservation_entry_by_number(
        self, number: str
    ) -> tuple[str, dict[str, Any]] | None:
        from ..transaction.operations import _find_reservation_entry_by_number_with_draft

        return _find_reservation_entry_by_number_with_draft(
            self._workspace, self._draft, number
        )

    def load_sidecar(self, obj_uuid: str) -> dict[str, Any]:
        from ..transaction.operations import _load_sidecar_with_draft

        return _load_sidecar_with_draft(self._workspace, self._draft, obj_uuid)

    def load_reservation(self, prefix: str) -> dict[str, Any]:
        from ..transaction.operations import _load_reservation_with_draft

        return _load_reservation_with_draft(self._workspace, self._draft, prefix)

    def event_log_last_event_id(self) -> str | None:
        """Returns the highest event_id known to the workspace (committed +
        staged in this draft), or None if no events exist anywhere. Useful
        for engines implementing the ADR/0028 D6 cache freshness invariant
        keying.

        Read at call time, not memoized at construction (per arc 20260601-4
        Codex2 verification note + arc 20260601-5 Codex1 Q6).

        Corrupt event log entries + missing bundle propagate per arc
        20260531-8 Phase B Codex2 B1 R3 fail-loud discipline (was: silent
        default to "evt_0001"; removed in arc 20260601-5)."""
        from ..truth_model.event_log import next_event_id

        # `next_event_id` returns the NEXT id; subtract 1 to get the highest
        # known committed event_id; then consider staged events in the draft.
        # Empty workspace path returns "evt_0001" cleanly here (no exception);
        # only corrupt event log / missing bundle propagate.
        next_committed = next_event_id(self._workspace, self._bundle.bundle_dir)
        next_n = int(next_committed[len("evt_"):])
        last_committed_n = next_n - 1
        staged_ids = [
            int(e["event_id"][len("evt_"):])
            for e in self._draft.events
            if "event_id" in e and e["event_id"].startswith("evt_")
        ]
        max_n = max([last_committed_n, *staged_ids], default=0)
        if max_n <= 0:
            return None
        return f"evt_{max_n:04d}"

    # ------------------------------------------------------------------
    # Stage APIs (proxy to TransactionDraft.stage_*)
    # ------------------------------------------------------------------

    def stage_sidecar(self, obj_uuid: str, sidecar: dict[str, Any]) -> None:
        self._draft.stage_sidecar(obj_uuid, sidecar)

    def stage_event(self, event: dict[str, Any]) -> None:
        self._draft.stage_event(event)

    def stage_vault_bytes(self, data: bytes) -> tuple[str, str]:
        return self._draft.stage_vault_bytes(data)

    def stage_reservation(self, prefix: str, reservation: dict[str, Any]) -> None:
        self._draft.stage_reservation(prefix, reservation)

    def stage_revision(
        self, obj_uuid: str, rev_id: str, content: dict[str, Any]
    ) -> None:
        self._draft.stage_revision(obj_uuid, rev_id, content)

    # ------------------------------------------------------------------
    # Event envelope helpers (Codex1 B2 R1 absorption arc 20260601-1)
    # ------------------------------------------------------------------

    def make_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        actor: str | None = None,
    ) -> dict[str, Any]:
        """Build a canonical event envelope per `event/_base.schema.json`.

        Codex1 B2 R1 absorption (arc 20260601-1): Native Engines need a
        draft-aware event-id allocation so two engine operations composed
        in one draft do not collide on event_id. This helper uses
        `_next_event_id_in_draft` (the same allocator built-in operations
        use) instead of disk-only `next_event_id`.

        Fields populated:
            - `schema_version`: from `self._bundle.bundle_version`
            - `event_id`: allocated via `_next_event_id_in_draft`
            - `event_type`: the `event_type` argument
            - `timestamp`: current UTC time in ISO 8601 format
            - `transaction_id`: from `self._draft.transaction_id`
            - `actor`: `actor` arg if provided, else `self._actor`
            - `payload`: the `payload` argument (passed through as-is;
              event-type schemas validate at fold time)

        Returns the event dict. Caller must `context.stage_event(event)`
        (or use `context.emit_event(...)` for the combined make+stage).

        **IMPORTANT — emit_event is preferred for multi-event handlers**
        (Codex2 N1 R2 advisory arc 20260601-1): if a handler calls
        `make_event` TWICE without staging the first event in between, both
        events get the SAME event_id (because `_next_event_id_in_draft`
        derives the next id from disk + already-staged events; an unstaged
        event is invisible to the allocator). Native Engine handlers that
        emit multiple events SHOULD use `emit_event()` which makes + stages
        in one call so subsequent allocations see the prior staged event.
        Only use `make_event` directly when the caller needs to inspect /
        mutate / conditionally stage the event before adding it to the draft.
        """
        from ..transaction.operations import _next_event_id_in_draft

        event_id = _next_event_id_in_draft(
            self._workspace, self._draft, self._bundle.bundle_dir
        )
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "schema_version": self._bundle.bundle_version,
            "event_id": event_id,
            "event_type": event_type,
            "timestamp": timestamp,
            "transaction_id": self._draft.transaction_id,
            "actor": actor if actor is not None else self._actor,
            "payload": payload,
        }

    def emit_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        actor: str | None = None,
    ) -> dict[str, Any]:
        """Convenience: `make_event` + `stage_event` in one call. Returns the
        staged event dict (useful for diagnostic logging in the handler)."""
        event = self.make_event(event_type, payload, actor=actor)
        self.stage_event(event)
        return event

    # ------------------------------------------------------------------
    # Validation hook APIs (Codex2 B2 R3 absorption arc 20260531-12)
    # ------------------------------------------------------------------

    def add_pre_validate_hook(self, hook: Callable) -> None:
        """Register a callback to run BEFORE the draft's pre-commit validation.

        Per ADR/0028 D3 + Codex2 B2 R3 from arc 12: hook callback receives the
        SAME `NativeEngineContext` instance — NOT raw `TransactionDraft`.

        Accepted arities (per Codex2 R3 + Codex3 N1 from arc 12):
            - 0-arg `Callable[[], None]` (engine captures context via closure)
            - 1-arg `Callable[[NativeEngineContext], None]`
            - 2+ arg: REJECTED LOUDLY with `NativeEngineRegistrationError`
        """
        self._draft.pre_validate_hooks.append(self._adapt_hook(hook, "pre"))

    def add_post_validate_hook(self, hook: Callable) -> None:
        """Register a callback to run AFTER the draft's pre-commit validation.
        Same arity rules as `add_pre_validate_hook`."""
        self._draft.post_validate_hooks.append(self._adapt_hook(hook, "post"))

    def _adapt_hook(
        self, hook: Callable, which: str
    ) -> Callable[[TransactionDraft], None]:
        """Adapt a Native-Engine-shape hook to the internal
        `Callable[[TransactionDraft], None]` shape `aiadra-core` expects.

        Per Codex3 N1-from-arc-12: reject unsupported arities loudly.
        """
        if not callable(hook):
            raise NativeEngineRegistrationError(
                f"engine {self._engine_id!r} {which}_validate_hook is not callable"
            )
        try:
            sig = inspect.signature(hook)
        except (ValueError, TypeError) as e:
            raise NativeEngineRegistrationError(
                f"engine {self._engine_id!r} {which}_validate_hook signature "
                f"could not be introspected: {e!r}"
            ) from e
        positional_params = [
            p
            for p in sig.parameters.values()
            if p.kind
            in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.POSITIONAL_ONLY,
            )
        ]
        arity = len(positional_params)
        if arity == 0:
            return lambda _draft: hook()
        if arity == 1:
            captured_context = self
            return lambda _draft: hook(captured_context)
        raise NativeEngineRegistrationError(
            f"engine {self._engine_id!r} {which}_validate_hook has unsupported "
            f"arity {arity} (expected 0 or 1); per ADR/0028 D3 + Codex2 B2 R3 "
            f"from arc 20260531-12, hooks receive NativeEngineContext only — "
            f"raw TransactionDraft is never exposed (Codex3 N1 from arc 12 "
            f"reject-loudly discipline)"
        )
