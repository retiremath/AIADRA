"""`NativeEngineRegistrar` per ADR/0028 D2 + Codex1 B1 R1 absorption arc
20260601-1 (engine_id immutability from construction)."""
from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .exceptions import NativeEngineRegistrationError


@dataclass(frozen=True)
class _EngineRegistration:
    """Frozen result of one engine's registration. Internal — not exposed."""

    engine_id: str
    operations: tuple[tuple[str, Callable], ...]  # mutation (kind, handler), sorted by kind
    # arc 20260609-1 Codex1 B1: read-only operations are a SEPARATE lane — they
    # never enter `operations` / `propose_kinds()` / `modify_kinds()` and never
    # see a staging-capable context.
    read_operations: tuple[tuple[str, Callable], ...] = ()  # read (kind, handler), sorted by kind


class NativeEngineRegistrar:
    """Passed by `aiadra-core` to each Native Engine's `register()` function
    during discovery. Enforces ADR/0028 D2 invariants per-call (#2, #3, #6 +
    duplicate-within-engine). Invariants #4 + #5 are merge-time at discovery.

    Codex1 B1 R1 absorption (arc 20260601-1): `engine_id` is IMMUTABLE from
    construction — engine code CANNOT do `registrar.engine_id = "other"`
    between `__init__` and `register()` returning. Enforced via `__setattr__`
    guard + `__slots__` (no dataclass field exposure).

    After `register(registrar)` returns, `aiadra-core` calls `_frozen_view()`
    which returns the immutable `_EngineRegistration` and locks `_frozen` so
    subsequent `add_operation()` calls fail.
    """

    __slots__ = ("_engine_id", "_operations", "_read_operations", "_frozen")

    def __init__(self, *, engine_id: str) -> None:
        # Use object.__setattr__ to bypass our own __setattr__ guard during init.
        object.__setattr__(self, "_engine_id", engine_id)
        object.__setattr__(self, "_operations", {})
        object.__setattr__(self, "_read_operations", {})
        object.__setattr__(self, "_frozen", False)

    @property
    def engine_id(self) -> str:
        """Read-only engine_id (sourced from entry-point name per ADR/0028 D2
        invariant #1)."""
        return self._engine_id

    def __setattr__(self, name: str, value: Any) -> None:
        """Per Codex1 B1 R1 absorption: NativeEngineRegistrar attributes are
        immutable after construction. Engine code attempting to reassign
        engine_id (or any other attribute) fails loudly."""
        raise NativeEngineRegistrationError(
            f"NativeEngineRegistrar attributes are immutable after construction "
            f"(attempted to set {name!r}); engine_id provenance comes from the "
            f"entry-point name per ADR/0028 D2 invariant #1 and engine code "
            f"cannot override it (Codex1 B1 R1 absorption arc 20260601-1)."
        )

    def __repr__(self) -> str:
        return (
            f"NativeEngineRegistrar(engine_id={self._engine_id!r}, "
            f"operations={list(self._operations)}, frozen={self._frozen})"
        )

    def add_operation(self, kind: str, handler: Callable) -> None:
        """Register one Native Engine MUTATION operation. Per ADR/0028 D2
        enforces:
            #2 namespace discipline (kind MUST start with f"{engine_id}.")
            #3 no built-in overwrite (kind MUST NOT collide with built-in
               `_PROPOSE_DISPATCH`)
            duplicate-within-engine (kind MUST NOT already be registered by
               THIS engine, in EITHER the mutation or the read lane)
            #6 handler signature check — ARITY-ONLY per Codex1 N3 absorption
               arc 20260601-1 (accepts any parameter names; checks for exactly
               2 positional-or-keyword parameters)

        Cross-engine collision (#4) + duplicate engine_id (#5) are merge-time
        at discovery, not per-call.
        """
        self._validate_registration("add_operation", kind, handler)
        # All checks passed — mutate dict via object.__setattr__ on the slot.
        # The dict is mutable; we don't reassign the slot, we mutate in place.
        self._operations[kind] = handler

    def add_read_operation(self, kind: str, handler: Callable) -> None:
        """Register one Native Engine READ-ONLY operation (arc 20260609-1
        Codex1 B1). Same ADR/0028 D2 invariants as `add_operation`, but the
        handler lands in a SEPARATE lane (`read_operations`): it is dispatched
        through a read-only adapter that hands it a non-staging
        `NativeEngineReadContext`, never appears in `propose_kinds()` /
        `modify_kinds()`, and never begins a `TransactionDraft`. Use for
        operations that only read committed Workspace state (e.g. generating a
        Display Representation). The same kind cannot be both a mutation and a
        read op for one engine (total-namespace uniqueness)."""
        self._validate_registration("add_read_operation", kind, handler)
        self._read_operations[kind] = handler

    def _validate_registration(self, method: str, kind: str, handler: Callable) -> None:
        """Shared ADR/0028 D2 registration invariants for both lanes."""
        if self._frozen:
            raise NativeEngineRegistrationError(
                f"engine {self._engine_id!r} attempted {method}({kind!r}) "
                f"AFTER register() returned; registrar is frozen"
            )
        if not callable(handler):
            raise NativeEngineRegistrationError(
                f"engine {self._engine_id!r} handler for {kind!r} is not callable"
            )
        # Invariant #2 namespace discipline
        if not kind.startswith(f"{self._engine_id}."):
            raise NativeEngineRegistrationError(
                f"engine {self._engine_id!r} attempted to register kind {kind!r} "
                f"outside its namespace (must start with '{self._engine_id}.') "
                f"per ADR/0028 D2 invariant #2"
            )
        # Invariant #3 no built-in overwrite (lazy import to avoid circular dep)
        from ..protocol import _PROPOSE_DISPATCH

        if kind in _PROPOSE_DISPATCH:
            raise NativeEngineRegistrationError(
                f"engine {self._engine_id!r} attempted to overwrite built-in "
                f"kind {kind!r} per ADR/0028 D2 invariant #3"
            )
        # Duplicate-within-engine — across BOTH lanes (a kind is mutation XOR read)
        if kind in self._operations or kind in self._read_operations:
            raise NativeEngineRegistrationError(
                f"engine {self._engine_id!r} attempted duplicate registration "
                f"of {kind!r} within the same register() call (a kind cannot be "
                f"both a mutation and a read operation)"
            )
        # Invariant #6 handler signature check — arity-only (Codex1 N3 absorption)
        try:
            sig = inspect.signature(handler)
        except (ValueError, TypeError) as e:
            raise NativeEngineRegistrationError(
                f"engine {self._engine_id!r} handler for {kind!r}: "
                f"could not introspect signature: {e!r}"
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
        if len(positional_params) != 2:
            raise NativeEngineRegistrationError(
                f"engine {self._engine_id!r} handler for {kind!r} has wrong "
                f"arity: expected 2 positional parameters (context, params), "
                f"got {len(positional_params)} per ADR/0028 D2 invariant #6 + "
                f"Codex1 N3 absorption arc 20260601-1"
            )

    def _frozen_view(self) -> _EngineRegistration:
        """Called by `aiadra-core` after `register()` returns. Freezes the
        registrar and returns the immutable view. Operations are sorted by
        kind for deterministic iteration order (ADR/0028 D2 invariant #7)."""
        object.__setattr__(self, "_frozen", True)
        return _EngineRegistration(
            engine_id=self._engine_id,
            operations=tuple(sorted(self._operations.items())),
            read_operations=tuple(sorted(self._read_operations.items())),
        )
