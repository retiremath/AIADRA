# Wedge-003 spike

Throwaway Python spike per [ADR/0030](../../Docs/ADR/0030-wedge-003-spike-scope.md).
**First AIADRA spike to exercise the Native Engine API surface end-to-end** —
4 Native Engine handlers (`mechanical_spike.*`) + toy deterministic synthetic
kernel + `part_changed` event emissions + DAG-aware feature dependencies +
B6 binding-scan negative test + provenance discipline negatives +
cascade-rejection negatives.

Primary deliverable: [FRICTION_LOG.md](FRICTION_LOG.md).

## What this spike validates

- ADR/0028 Native Engine API surface (`NativeEngineRegistrar` + `NativeEngineContext` + entry-point discovery + dispatch adapter)
- ADR/0029 Part authoring schema (`part_changed` event + `feature` + `geometry_ref` namespaces + atomic delta rules + STRICT set-equality + DAG acyclicity + cascade integrity + canonical units at fact level)
- ADR/0030 5-step authoring loop in two modes (A: separate Transactions; B: composed via `modify`)
- D16 string-kind dispatch (`mechanical_spike.*` namespace)
- Codex1 B1 R1 absorption (arc 20260601-3): extrude depth as first-class
  `feature.parameters[]` record with canonical unit `mm` — `adjust_feature_parameter`
  updates Product Truth + geometry hash genuinely changes

## What this spike INTENTIONALLY does NOT do

Per [ADR/0030 D14](../../Docs/ADR/0030-wedge-003-spike-scope.md) (15 items) +
ADR/0030 D11 §10 lessons-by-omission:

- Real OCCT geometric kernel (toy deterministic synthetic kernel only)
- Multi-Part assemblies (single Part authoring focus)
- Constraint solving (sketches stay opaque per ADR/0029 D7)
- Mate satisfaction (no `mated_to` in spike)
- Cross-Part geometry derivation (`derived_geometry_from` — multi-Part Native Engine arc)
- CLI for Native Engine operations (engine packages ship own CLI; spike uses Python API)
- UI / viewport (per ADR/0028 D13; future Workspace Browser arc)
- Multi-process / parallel engine instances
- KiCad / electrical engine specifics
- DV / procurement Data Adapter specifics
- Validation hooks (advanced feature; smallest viable doesn't need)
- `aiadra-mechanical` production package (this spike is throwaway)
- Rollback path expanded testing
- `mechanical_spike.recompute_geometry` op (dropped per Codex1 N3 R1 from arc 2)
- Destructive package-uninstall test scenarios

OCCT-class friction NOT surfaced by this spike (documented in FRICTION_LOG §10):
BREP serialization quirks, kernel tolerance behavior, long-running recompute/
cancellation, platform-specific dependency packaging. These ARE the friction
items the first `aiadra-mechanical` production-package arc will surface.

## Quick run

```bash
# From AIADRA repo root:
aiadra-core/.venv/Scripts/pip.exe install -e ./spikes/wedge-003

# Run the Mode A worked invocation:
cd spikes/wedge-003
bash run_demo.sh
```

`run_demo.sh` drives the full Mode A worked invocation; outputs land in
`outputs/ws/` (checked in for review without re-running).

## Layout

```
spikes/wedge-003/
├── pyproject.toml                       # declares aiadra.native_engines entry-point
├── README.md                            # this file
├── FRICTION_LOG.md                      # 10 sections per ADR/0030 D11
├── run_demo.sh                          # Mode A end-to-end invocation
├── aiadra_mechanical_spike/             # the Native Engine package
│   ├── __init__.py                      # def register(registrar) — declares 4 ops
│   ├── handlers.py                      # 4 Native Engine handlers
│   ├── kernel.py                        # toy deterministic synthetic kernel
│   ├── adapter_payload.py               # sketch/extrude adapter_payload helpers
│   └── demo.py                          # Mode A invocation entry point
├── fixtures/
│   └── profile_negative/                # YAML Profile-violation fixtures (Wedge-002 carry-over)
├── outputs/                             # spike-produced; checked in for review
├── test_wedge_003_end_to_end.py         # 13 happy-path tests (Mode A + Mode B)
├── test_wedge_003_negative_discipline.py # 10 negative tests (incl. B6 integration)
└── test_profile_negative.py             # 12 YAML Profile-violation tests (Wedge-001/002 carry-over)
```

## Running tests

```bash
# From AIADRA repo root, after installing the spike per above:
aiadra-core/.venv/Scripts/python.exe -m pytest spikes/wedge-003/ -v
```

Total: **23 Wedge-003-specific tests** (13 happy-path in `test_wedge_003_end_to_end.py`
+ 10 negative-discipline tests in `test_wedge_003_negative_discipline.py` — 8 from
the original ADR/0030 D12 list + 1 B6 binding-scan integration test added per
Codex2 B1 R3 absorption from arc 20260601-3 + 1 adjust depth-domain validation
regression added per Codex2 N1 R3 absorption) + 12 YAML Profile-violation tests
carried forward from Wedge-001/002.

## Throwaway-spike posture

Per [ADR/0023 §4](../../Docs/ADR/0023-wedge-spike-scope-and-runtime.md) +
[ADR/0030 D14 item 12](../../Docs/ADR/0030-wedge-003-spike-scope.md): this
is exploratory code. Production mechanical Native Engine lives in
`aiadra-mechanical` (future arc) — clean slate informed by THIS spike's
friction log.

The spike's engine_id is `mechanical_spike` (NOT `mechanical`) per ADR/0030
D2 + Codex1 B2 R1 absorption from arc 2 — avoids future duplicate-engine_id
collision with production `aiadra-mechanical` package per ADR/0028 D2
invariant #5; spike + production coexist collision-free in the same venv.
