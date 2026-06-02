# Integration tests

This directory holds integration tests for `aiadra-core` — tests that exercise
end-to-end behavior spanning multiple modules (Transaction draft → commit →
event log → validation fold → Native Engine discovery → protocol dispatch).
Unit-style tests live alongside their source modules or in narrower test
subdirectories; tests here intentionally assume a fully wired-up runtime.

## Rule: no test may assume zero Native Engines installed

The Native Engine discovery layer (`aiadra_core.native_engine.discovery`)
finds engines via Python entry points in the `aiadra.native_engines` group.
The set of installed engines depends on developer-venv state: zero in a fresh
`pip install aiadra-core` venv, but non-zero as soon as
`pip install -e ./spikes/wedge-003` (or any other ecosystem package) lands.
CI runs with whatever the venv has.

**Tests MUST control discovery state explicitly rather than assume "no
engines installed".** Two historical violations from arc 20260601-3 R2
(during the Wedge-003 spike install) made this concrete:

- `test_native_engine_status_empty_when_no_engines` asserted an empty status
  dict; broke when Wedge-003 spike was installed (the `mechanical_spike`
  engine appeared in status).
- `test_phase_c_propose_kinds_catalogue` asserted `len(kinds) == 17`; broke
  when 4 spike `mechanical_spike.*` kinds joined the catalogue (count
  became 21).

Both were fixed in arc 20260601-3 R2 — see
[Wedge-003 FRICTION_LOG §1](../../../spikes/wedge-003/FRICTION_LOG.md)
for the full diagnosis and the recurring-violation cost.

## The monkeypatch pattern (canonical)

`test_native_engine_api.py` already defines the canonical helper
`_patch_entry_points(eps: list[_FakeEntryPoint])` that patches
`aiadra_core.native_engine.discovery.entry_points` (the locally-imported
`importlib.metadata.entry_points` symbol) with a fake callable accepting
`group=` and returning the controlled list. Use that helper for any new
discovery-touching test in this directory rather than rolling your own
patch:

```python
from test_native_engine_api import _FakeEntryPoint, _patch_entry_points

def test_my_engine_thing(tmp_path):
    ep = _FakeEntryPoint(name="myengine", load_fn=lambda registrar: ...)
    with _patch_entry_points([ep]):  # context-manager wrapper
        refresh_native_engines()       # invalidate discovery cache
        # ... test body sees exactly `[myengine]` installed ...
```

For tests in NEW files that should NOT import from
`test_native_engine_api.py`, mirror the same pattern inline (~10 LOC):
patch `aiadra_core.native_engine.discovery.entry_points` with a fake
callable that filters on `group="aiadra.native_engines"`, then call
`refresh_native_engines()` to flush the cache. The autouse fixture
`_reset_discovery_cache` in `test_native_engine_api.py` shows how to keep
cache state clean across tests.

## When a test must distinguish builtin vs engine-contributed surface

When you can't (or shouldn't) monkeypatch — e.g., asserting against the
full registered catalogue including whatever is installed — filter
explicitly. Engine-namespaced kinds carry `.` (e.g.
`mechanical_spike.add_sketch_feature`); builtins do not. Example pattern
from `test_phase_c_propose_modify.py`:

```python
builtin_kinds = [k for k in propose_kinds() if "." not in k]
assert len(builtin_kinds) == EXPECTED_BUILTIN_COUNT
```

This is robust against any number of installed ecosystem packages and was
the second arc-20260601-3-R2 fix.

## Why this README exists

This rule lives in test-folder-local prose (not in a CLAUDE.md or an ADR)
because the cost of violating it is specifically test-author cost — the
violation is silent until an ecosystem package gets installed and someone
reruns the suite. Pre-arc 20260601-3 the implicit rule worked because no
ecosystem packages were ever installed; post-Wedge-003 the rule has to be
explicit. Codified per arc 20260601-4 routing Action B + arc 20260601-5
implementation.
