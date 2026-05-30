#!/usr/bin/env bash
# Worked invocation per ADR/0024 §"Worked invocation". Re-runnable; clears
# outputs/ first so the demo is deterministic.
#
# Per ADR/0024 §2.5: execution-instance relationships (executes / executed_on
# / produces) are authored Fixed-at-authoring; their endpoints[0].revision_id
# is pinned from the upfront --rev-id predeclaration loaded into .rev-id-map.

set -euo pipefail

cd "$(dirname "$0")"

if [[ -x ".venv/Scripts/python.exe" ]]; then
    PY=".venv/Scripts/python.exe"
elif [[ -x ".venv/bin/python" ]]; then
    PY=".venv/bin/python"
else
    PY="python3"
fi

# Fresh outputs/
rm -rf outputs
mkdir -p outputs

# Fixed Object UUIDs per ADR/0024 §5 (spike-local demo records)
PART_UUID="0193abcd-1234-7890-abcd-111111111111"
REQ_UUID="0193abcd-1234-7890-abcd-222222222222"
TST_UUID="0193abcd-1234-7890-abcd-555555555555"
TEX_UUID="0193abcd-1234-7890-abcd-666666666666"
EVD_UUID="0193abcd-1234-7890-abcd-777777777777"

# Predeclared Revision UUIDs (spike-local) — pinned at authoring per ADR/0024 §2.5
PART_REV="0193abcd-1234-7890-abcd-aaaaaaaaaaa1"
REQ_REV="0193abcd-1234-7890-abcd-aaaaaaaaaaa2"
TST_REV="0193abcd-1234-7890-abcd-aaaaaaaaaaa5"
TEX_REV="0193abcd-1234-7890-abcd-aaaaaaaaaaa6"
EVD_REV="0193abcd-1234-7890-abcd-aaaaaaaaaaa7"

echo "# init (with upfront --rev-id predeclaration per ADR/0024 §2.5)"
$PY -m wedge --workspace outputs init --project-id "wedge-002-demo" \
    --rev-id "$PART_UUID=$PART_REV" \
    --rev-id "$REQ_UUID=$REQ_REV" \
    --rev-id "$TST_UUID=$TST_REV" \
    --rev-id "$TEX_UUID=$TEX_REV" \
    --rev-id "$EVD_UUID=$EVD_REV"
echo

echo "# create-part P-000058 (drive bracket; final value already 7 — no propose-parameter-change in Wedge-002 demo)"
$PY -m wedge --workspace outputs create-part \
    --number P-000058 \
    --name "Drive bracket" \
    --parameter plate_thickness_mm=7 \
    --uuid "$PART_UUID"
echo

echo "# create-requirement REQ-000058 (minimum thickness)"
$PY -m wedge --workspace outputs create-requirement \
    --number REQ-000058 \
    --name "Drive bracket minimum thickness" \
    --statement "Drive bracket plate thickness shall be at least 5 mm." \
    --acceptance-criterion "ac_min_thickness:plate_thickness_mm>=5" \
    --uuid "$REQ_UUID"
echo

echo "# attach-file (TestProcedure canonical procedure document)"
$PY -m wedge --workspace outputs attach-file \
    --file fixtures/procedure_TST-000017.txt \
    --role source_authoring \
    --id att_procedure
echo

echo "# create-test-procedure TST-000017"
$PY -m wedge --workspace outputs create-test-procedure \
    --number TST-000017 \
    --name "Drive bracket plate thickness test" \
    --verification-method analysis \
    --attachment att_procedure \
    --uuid "$TST_UUID"
echo

echo "# link-tested-against (Part → TestProcedure; Float; materializes Fixed at release)"
$PY -m wedge --workspace outputs link-tested-against \
    --source P-000058 --target TST-000017
echo

echo "# link-verifies (TestProcedure → Requirement; target-side fact_ref opt-in)"
$PY -m wedge --workspace outputs link-verifies \
    --source TST-000017 --target REQ-000058 --target-criterion ac_min_thickness
echo

echo "# attach-file (EvidenceArtifact canonical measurement log)"
$PY -m wedge --workspace outputs attach-file \
    --file fixtures/measurement_EVD-000043.csv \
    --role source_authoring \
    --id att_measurement_data
echo

echo "# create-evidence-artifact EVD-000043 (parameter lineage to att_measurement_data)"
$PY -m wedge --workspace outputs create-evidence-artifact \
    --number EVD-000043 \
    --summary "Drive bracket plate thickness measurement" \
    --evidence-kind measurement \
    --parameter "reported_thickness_mm=6.98:from=attachment:att_measurement_data" \
    --attachment att_measurement_data \
    --uuid "$EVD_UUID"
echo

echo "# attach-file (TestExecution canonical record of execution event)"
$PY -m wedge --workspace outputs attach-file \
    --file fixtures/instron_log_TEX-000007.txt \
    --role source_authoring \
    --id att_instron_log
echo

echo "# create-test-execution TEX-000007 (parameter lineage to att_instron_log)"
$PY -m wedge --workspace outputs create-test-execution \
    --number TEX-000007 \
    --execution-status completed \
    --executed-on-date 2026-04-15 \
    --operator-identifier "test_engineer:emp_5839" \
    --parameter "measured_thickness_mm=6.98:from=attachment:att_instron_log" \
    --attachment att_instron_log \
    --uuid "$TEX_UUID"
echo

echo "# link-executes (TestExecution → TestProcedure; Fixed-at-authoring)"
$PY -m wedge --workspace outputs link-executes \
    --source TEX-000007 --target TST-000017
echo

echo "# link-executed-on (TestExecution → Part; Fixed-at-authoring; SAME Part as tested_against per B5)"
$PY -m wedge --workspace outputs link-executed-on \
    --source TEX-000007 --target P-000058
echo

echo "# link-produces (TestExecution → EvidenceArtifact; Fixed-at-authoring)"
$PY -m wedge --workspace outputs link-produces \
    --source TEX-000007 --target EVD-000043
echo

echo "# link-cites (Requirement → EvidenceArtifact; source-side source_fact_ref opt-in)"
$PY -m wedge --workspace outputs link-cites \
    --source REQ-000058 --target EVD-000043 --source-criterion ac_min_thickness
echo

echo "# release ALL 5 Objects atomically with V&V chain integrity + attachment integrity + execution cardinality"
$PY -m wedge --workspace outputs release \
    --objects "P-000058,REQ-000058,TST-000017,TEX-000007,EVD-000043" \
    --label rev-A
echo

echo "✓ Wedge-002 demo complete. Outputs in outputs/."
