# Wedge-001 spike

Throwaway Python spike per [ADR/0023](../../Docs/ADR/0023-wedge-spike-scope-and-runtime.md).
Exercises the basic AIADRA loop end-to-end: one Part + one Requirement + one
`satisfies` relationship + one AI Transaction + one Release.

**Code quality is NOT a deliverable here.** The primary deliverable is
[FRICTION_LOG.md](FRICTION_LOG.md) — what the spec said vs. what the spike
needed.

## Quick run (matches ADR/0023 worked invocation)

```bash
cd spikes/wedge-001
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install "ruamel.yaml>=0.18,<0.19" "jsonschema>=4.0,<5.0"

# Linux/macOS: use python3.11 and .venv/bin/python instead.

bash run_demo.sh
```

The demo script (`run_demo.sh`) drives the full worked invocation; outputs land
in `outputs/` (checked in for review without re-running).

## Layout

```
spikes/wedge-001/
├── README.md
├── pyproject.toml
├── run_demo.sh                    # worked invocation per ADR/0023
├── FRICTION_LOG.md                # PRIMARY DELIVERABLE
├── wedge/                         # Python package
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── sidecar.py                 # YAML I/O + AIADRA YAML Profile lint
│   ├── event_log.py               # JSONL + fold
│   ├── manifest.py                # deterministic JSON release manifest
│   ├── transaction.py             # Transaction lifecycle coordinator
│   ├── validate.py                # schema validation + satisfies check + fold check
│   └── schemas/                   # 7 JSON Schemas + bundle index
├── fixtures/                      # YAML Profile lint test fixtures
│   └── profile_negative/          # files that MUST be rejected by the Profile
├── outputs/                       # spike-produced artifacts (checked in)
│   ├── Reservations/{P,REQ}.yaml
│   ├── events.jsonl
│   ├── revisions/<uuid>/{working,<rev_id>}.yaml
│   └── Releases/<label>/manifest.json
└── .venv/                         # local Python env (git-ignored via .venv/)
```

## Scope (per ADR/0023 §2)

In scope: Part, Requirement, `satisfies`, working + released lifecycle, parameter
change as AI Transaction, sidecar/event invariant fold check, AIADRA YAML
Profile spike-grade lint, deterministic Release Manifest with content hash.

Explicitly NOT in scope: V&V framework (TestProcedure / TestExecution /
EvidenceArtifact / verifies / tested_against / cites / executes / executed_on /
produces); Assembly / Component / SoftwareModule / Drawing; `composed_of` /
`mated_to` / `parameter_expression`; cross-project; Domain Engine; acceleration
cache; schema bundle migrators; Vault Adapter; failed-transaction audit
retention (deferred per [OQ-0003](../../Docs/OpenQuestions.md)).

## Posture

Throwaway per [Glossary "Spike"](../../Docs/Glossary.md). Production-grade
`aiadra-core` runtime / repo layout / posture is a SEPARATE future arc
informed by FRICTION_LOG.md.
