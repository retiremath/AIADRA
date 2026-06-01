#!/usr/bin/env bash
# Wedge-003 worked invocation per ADR/0030 D4 Mode A (separate Transactions).
# Mode B (composed-via-modify) tested in test_wedge_003_end_to_end.py only.
#
# Precondition (per Codex1 N1 R1 absorption arc 20260601-3): spike package
# must be installed in the AIADRA aiadra-core venv:
#   aiadra-core/.venv/Scripts/pip.exe install -e ./spikes/wedge-003
# (Linux/macOS: aiadra-core/.venv/bin/pip)
#
# The demo verifies entry-point discovery before running; fails fast with
# exit 2 if the spike isn't discovered.

set -euo pipefail

cd "$(dirname "$0")"

if [[ -x "../../aiadra-core/.venv/Scripts/python.exe" ]]; then
    PY="../../aiadra-core/.venv/Scripts/python.exe"
elif [[ -x "../../aiadra-core/.venv/bin/python" ]]; then
    PY="../../aiadra-core/.venv/bin/python"
else
    PY="python3"
fi

# Fresh outputs/
rm -rf outputs && mkdir -p outputs

echo "# Wedge-003 Mode A worked invocation (5-step authoring loop)"
$PY -m aiadra_mechanical_spike.demo --workspace outputs/ws

echo
echo "[OK] Wedge-003 demo complete. Outputs in outputs/ws."
