# Wedge-002 spike

Throwaway Python spike per [ADR/0024](../../Docs/ADR/0024-wedge-002-spike-scope.md).
Exercises the full V&V chain end-to-end: 5 Object instances (Part + Requirement
+ TestProcedure + TestExecution + EvidenceArtifact) + 6 V&V relationships
(tested_against / verifies / cites / executes / executed_on / produces) +
Attachment-bearing pattern with minimal local-FS content-addressed Vault Adapter.

Primary deliverable: [FRICTION_LOG.md](FRICTION_LOG.md).

## Quick run

```bash
cd spikes/wedge-002
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install "ruamel.yaml>=0.18,<0.19" "jsonschema>=4.0,<5.0"

# Linux/macOS: python3.11 + .venv/bin/python instead.

bash run_demo.sh
```

`run_demo.sh` drives the full worked invocation; outputs land in `outputs/`
(checked in for review without re-running).

## Layout

```
spikes/wedge-002/
├── README.md
├── pyproject.toml
├── run_demo.sh                    # worked invocation per ADR/0024
├── test_profile_negative.py       # AIADRA YAML Profile lint fixture proof
├── FRICTION_LOG.md                # PRIMARY DELIVERABLE (§4 cross-spike vs Wedge-001)
├── wedge/                         # Python package
│   ├── __init__.py / __main__.py
│   ├── cli.py                     # 6 carried + 4 new create-* + 6 new link-* subcommands
│   ├── sidecar.py                 # carried from Wedge-001 (force-quote dumper + Profile lint)
│   ├── event_log.py               # carried + B1 absorption (generic *_created fold)
│   ├── manifest.py                # carried from Wedge-001 (manifest authority model unchanged)
│   ├── transaction.py             # carried + V&V Object creates + .rev-id-map + materialize verifies Fixed-at-authoring
│   ├── validate.py                # carried + V&V chain integrity (B5) + attachment integrity + execution cardinality
│   ├── vault.py                   # NEW: content-addressed local-FS Vault Adapter
│   └── schemas/                   # 21 schemas: 5 Object + 7 relationship + 5 Reservation + bundle + manifest + event + attachment shared
├── fixtures/
│   ├── profile_negative/          # 12 Profile-violation fixtures (carried from Wedge-001)
│   ├── procedure_TST-000017.txt   # canonical TestProcedure document (semantically inspectable)
│   ├── measurement_EVD-000043.csv # canonical evidence payload
│   └── instron_log_TEX-000007.txt # canonical execution record
└── outputs/                       # spike-produced (checked in)
    ├── Reservations/{P,REQ,TST,TEX,EVD}.yaml
    ├── events.jsonl
    ├── revisions/<uuid>/{working,<rev_id>}.yaml  # 5 directories
    ├── Releases/rev-A/manifest.json
    ├── vault/<sha256-hex>/bytes   # 3 attachments
    ├── .rev-id-map                # spike-local non-canonical (per ADR/0024 §2.5)
    └── .attachments-staging.yaml  # spike-local non-canonical (workspace helper)
```

## Scope (per ADR/0024 §2)

In scope: full V&V chain end-to-end; minimal local-FS content-addressed Vault
Adapter (`outputs/vault/<sha256-hex>/bytes`); execution-instance Fixed-at-
authoring with upfront `--rev-id` predeclaration per ADR/0024 §2.5;
criterion-level addressing (`endpoints[].fact_ref` on `verifies`;
`source_fact_ref` on `cites`); attachment integrity check at release;
V&V chain integrity check including B5 `executed_on` same-Part verification;
status-sensitive `produces` cardinality at release.

Explicitly NOT in scope (per ADR/0024 §10): Assembly + `composed_of` / `mated_to`
/ `parameter_expression` / `depicts`; Component / SoftwareModule / Drawing;
cross-project; Domain Engine; production Vault Adapter (LFS / S3 / etc.);
production-grade `aiadra-core` runtime; Schema Change Notes for Wedge-001
FRICTION items F1/F2/F3 (carried forward unchanged per §7); test-campaign
aggregation; pass/fail outcome semantics on V&V relationships.

## Posture

Throwaway per [Glossary "Spike"](../../Docs/Glossary.md). Production-grade
`aiadra-core` runtime / repo layout / posture is a SEPARATE future arc
informed by combined Wedge-001 + Wedge-002 FRICTION_LOG.md.
