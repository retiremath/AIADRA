#!/usr/bin/env bash
# Worked invocation per ADR/0023 §"Worked invocation". Re-runnable; clears
# outputs/ first so the demo is deterministic.
#
# Uses spike-local fixture identities per ADR/0023 §6 (reused ADR worked-
# example UUIDs are spike-local demo records; do NOT reserve those Numbers
# against future real project data per ADR/0004's per-project namespace rule).

set -euo pipefail

cd "$(dirname "$0")"

# Pick the Python interpreter
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

# Fixed UUIDs per ADR/0023 §6 (spike-local demo records)
PART_UUID="0193abcd-1234-7890-abcd-111111111111"
REQ_UUID="0193abcd-1234-7890-abcd-222222222222"
PART_REV="0193abcd-1234-7890-abcd-333333333333"
REQ_REV="0193abcd-1234-7890-abcd-444444444444"

echo "# init"
$PY -m wedge --workspace outputs init --project-id "wedge-001-demo"
echo

echo "# create-part P-000058 (drive bracket)"
$PY -m wedge --workspace outputs create-part \
    --number P-000058 \
    --name "Drive bracket" \
    --parameter plate_thickness_mm=6 \
    --uuid "$PART_UUID"
echo

echo "# create-requirement REQ-000058 (minimum thickness)"
$PY -m wedge --workspace outputs create-requirement \
    --number REQ-000058 \
    --name "Drive bracket minimum thickness" \
    --statement "Drive bracket plate thickness shall be at least 5 mm." \
    --category performance \
    --verification-method analysis \
    --acceptance-criterion "ac_min_thickness:plate_thickness_mm>=5" \
    --uuid "$REQ_UUID"
echo

echo "# link-satisfies (P-000058 satisfies REQ-000058)"
$PY -m wedge --workspace outputs link-satisfies \
    --source P-000058 \
    --target REQ-000058
echo

echo "# propose-parameter-change (REJECTED case: thinner than minimum)"
set +e
$PY -m wedge --workspace outputs propose-parameter-change \
    --object P-000058 \
    --parameter plate_thickness_mm \
    --new-value 4 \
    --rationale "AI proposal: thinner for weight target" \
    --auto-approve
REJ_EXIT=$?
set -e
echo "(exit code: $REJ_EXIT — expected 1)"
echo

echo "# propose-parameter-change (APPROVED case: thicker safety margin)"
$PY -m wedge --workspace outputs propose-parameter-change \
    --object P-000058 \
    --parameter plate_thickness_mm \
    --new-value 7 \
    --rationale "AI proposal: stronger for safety margin" \
    --auto-approve
echo

echo "# release rev-A (both Objects)"
$PY -m wedge --workspace outputs release \
    --objects "P-000058,REQ-000058" \
    --label rev-A \
    --rev-id "$PART_UUID=$PART_REV" \
    --rev-id "$REQ_UUID=$REQ_REV"
echo

echo "✓ Demo complete. Outputs in outputs/."
