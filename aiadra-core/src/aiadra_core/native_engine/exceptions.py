"""Native Engine exception classes per ADR/0028 D9 + D2 invariants."""
from __future__ import annotations


class NativeEngineRegistrationError(ValueError):
    """Raised when a Native Engine's `register()` function violates a
    `NativeEngineRegistrar` invariant per ADR/0028 D2:
        #1 engine_id immutability (B1 absorption arc 20260601-1)
        #2 namespace discipline (kind MUST start with engine_id.)
        #3 no built-in overwrite
        #4 no cross-engine kind collision (merge-time at discovery)
        #5 no duplicate engine_id across distributions (Codex2 B1 from arc 12)
        #6 handler signature check (arity-only per N3 absorption arc 20260601-1)

    Also raised at hook registration time when a `NativeEngineContext` hook
    callable has unsupported arity (per Codex3 N1-from-arc-12 + ADR/0028 D3).
    """


class EngineNotAvailableError(ValueError):
    """Raised when `propose(kind="<engine>.<op>")` cannot dispatch per
    ADR/0028 D5 four-case discipline:
        - engine_id is not installed (no entry point found)
        - engine failed to load during discovery (broken import,
          register() raised, etc.) — `__cause__` preserves the underlying
          exception
        - engine was rejected for duplicate engine_id across distributions
          (Codex2 B1 R3 absorption arc 20260531-12)
        - engine was rejected for cross-engine kind collision (D2 #4 — though
          this case is largely defense-in-depth per Codex1 N2 arc 20260601-1)
        - engine is loaded but does not register the specific operation_kind
          (fifth case added arc 20260601-1)

    The message distinguishes the case for human + agent diagnostics.
    """


class NativeEngineKernelError(RuntimeError):
    """Raised by the dispatch adapter when a Native Engine handler's kernel
    (e.g., OCCT, KiCad libs) throws an exception during operation execution
    per ADR/0028 D9. Carries `engine_id` + `operation_kind`; preserves the
    underlying kernel exception via `__cause__`.

    Distinct from `EngineNotAvailableError` (availability/discovery failure)
    and `NativeEngineRegistrationError` (D2 invariant violation).
    """

    def __init__(self, message: str, *, engine_id: str, operation_kind: str) -> None:
        super().__init__(message)
        self.engine_id = engine_id
        self.operation_kind = operation_kind
