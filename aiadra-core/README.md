# aiadra-core

Production-grade runtime for the AIADRA Product Truth Model.

## Status

Phase 0 skeleton per [ADR/0025 §1](../Docs/ADR/0025-aiadra-core-runtime-scope.md).
Read-only operations (`validate`, `inspect`) implemented. Transaction operations
(state-changing commands) land in Phase 1. See ADR/0025 for the full
implementation roadmap.

## Install

```
pip install -e .
```

## Use

```
aiadra --version
aiadra validate <workspace>
aiadra inspect <workspace> <object-number>
```

## Layout

- `src/aiadra_core/truth_model/` — Layer 1: sidecars, events, Revisions, Reservations, Manifest.
- `src/aiadra_core/validation/` — Layer 2: schema dispatch, Profile lint, sidecar/event fold invariant, bundle digest.
- `src/aiadra_core/transaction/` — Layer 3 (partial): Transaction boundary skeleton; operations stub until Phase 1.
- `src/aiadra_core/vault/` — Vault Adapter interface + local-FS reference implementation.
- `src/aiadra_core/cli/` — Thin CLI wrapper.
- `src/aiadra_core/schemas/v0.19.0/` — Bundled JSON Schemas + index + digest.

## Tests

```
pytest tests/
```

Integration tests validate against carried Wedge-001 + Wedge-002 fixture projects.
