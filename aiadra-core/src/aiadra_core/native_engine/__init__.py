"""Native Engine API surface per ADR/0028 D2 + D3 + D5 + D9 + D16 — implemented
in arc 20260601-1 (`aiadra-core 0.10.0 → 0.11.0`).

This submodule implements the Python API that Native Engine packages
(`aiadra-mechanical`, future `aiadra-electrical`, etc.) consume to integrate
with `aiadra-core`. Per [ADR/0027 D11](../Docs/ADR/0027-aiad-positioning-and-native-engine-posture.md)
ecosystem-package boundary: Native Engine implementations live OUTSIDE
`aiadra-core`; this submodule is the contract.

Public surface:
- `NativeEngineRegistrar` — guarded registration API passed to each Native
  Engine's `register()` function during discovery (ADR/0028 D2).
- `NativeEngineContext` — stable wrapper around `TransactionDraft` that Native
  Engine handlers receive via dispatch (ADR/0028 D3).
- `NativeEngineRegistrationError` — raised on D2 invariant violations.
- `EngineNotAvailableError` — raised by dispatch when a kind's engine is
  missing / failed / duplicate-rejected (ADR/0028 D5 four-case discipline).
- `NativeEngineKernelError` — raised by the dispatch adapter when a Native
  Engine handler's kernel (e.g., OCCT) throws during operation execution
  (ADR/0028 D9).
- `refresh_native_engines()` — escape hatch for tests + embedding (ADR/0028 D5
  + Codex Q6).
- `native_engine_status()` — diagnostic helper (ADR/0028 D15 item 11; landed
  this arc per Codex1 N4 acknowledgement).

Re-exported via `aiadra_core.protocol.*` so callers can
`from aiadra_core.protocol import NativeEngineRegistrar, ...`.
"""
from __future__ import annotations

from .context import NativeEngineContext
from .discovery import (
    ENTRY_POINT_GROUP,
    get_native_engines,
    native_engine_status,
    refresh_native_engines,
)
from .exceptions import (
    EngineNotAvailableError,
    NativeEngineKernelError,
    NativeEngineRegistrationError,
)
from .registrar import NativeEngineRegistrar

__all__ = [
    "ENTRY_POINT_GROUP",
    "EngineNotAvailableError",
    "NativeEngineContext",
    "NativeEngineKernelError",
    "NativeEngineRegistrar",
    "NativeEngineRegistrationError",
    "get_native_engines",
    "native_engine_status",
    "refresh_native_engines",
]
