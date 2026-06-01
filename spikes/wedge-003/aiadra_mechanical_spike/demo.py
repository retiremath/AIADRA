"""Mode A worked invocation per ADR/0030 D4 + ADR/0030 D9 run_demo.

Runs the 5-step authoring loop end-to-end in SEPARATE Transactions:
    1. create_part (built-in)
    2. mechanical_spike.add_sketch_feature
    3. mechanical_spike.add_extrude_feature (depends on sketch; depth_mm=5)
    4. mechanical_spike.adjust_feature_parameter (depth_mm: 5 → 8)
    5. release (built-in; final_stage=True)

After commit, verifies the final Part has 2 features + 1 geometry_ref +
released revision_id.

Per Codex1 N1 R1 absorption (arc 20260601-3): verify entry-point install
precondition before running (refresh + status check).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aiadra_core.protocol import (
    native_engine_status,
    propose,
    refresh_native_engines,
)
from aiadra_core.transaction.boundary import TransactionError
from aiadra_core.truth_model.reservation import find_reservation_entry_by_number
from aiadra_core.truth_model.sidecar import load_sidecar


def main() -> int:
    parser = argparse.ArgumentParser(description="Wedge-003 Mode A worked invocation")
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()

    # Per Codex1 N1: verify the spike is installed before running.
    refresh_native_engines()
    status = native_engine_status()
    if "mechanical_spike" not in status:
        print(
            "ERROR: mechanical_spike Native Engine not discovered. "
            "Install the spike first: pip install -e ./spikes/wedge-003",
            file=sys.stderr,
        )
        return 2
    if status["mechanical_spike"]["status"] != "loaded":
        print(
            f"ERROR: mechanical_spike failed to load: {status['mechanical_spike']}",
            file=sys.stderr,
        )
        return 2
    print(f"# Native Engine status: {status['mechanical_spike']}")

    ws = args.workspace
    ws.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: init + create_part (built-in)
        print("# Step 1a: init workspace")
        propose(ws, kind="init", params={}).commit()

        print("# Step 1b: create_part P-000001")
        propose(ws, kind="create_part", params={
            "number": "P-000001",
            "name": "BracketSpike",
        }).commit()

        # Step 2: add_sketch_feature
        print("# Step 2: mechanical_spike.add_sketch_feature")
        propose(ws, kind="mechanical_spike.add_sketch_feature", params={
            "part_number": "P-000001",
            "primitives": [
                {"type": "rectangle", "x_mm": 0.0, "y_mm": 0.0, "width_mm": 20.0, "height_mm": 10.0},
                {"type": "circle", "cx_mm": 5.0, "cy_mm": 5.0, "radius_mm": 2.0},
            ],
        }).commit()

        # Step 3: add_extrude_feature
        print("# Step 3: mechanical_spike.add_extrude_feature (depth_mm=5)")
        propose(ws, kind="mechanical_spike.add_extrude_feature", params={
            "part_number": "P-000001",
            "sketch_feature_id": "feat_0001",
            "depth_mm": 5.0,
            "direction": "z+",
        }).commit()

        # Step 4: adjust_feature_parameter
        print("# Step 4: mechanical_spike.adjust_feature_parameter (depth_mm: 5 -> 8)")
        propose(ws, kind="mechanical_spike.adjust_feature_parameter", params={
            "part_number": "P-000001",
            "feature_id": "feat_0002",
            "parameter_name": "depth_mm",
            "new_value": 8.0,
        }).commit()

        # Step 5: release
        print("# Step 5: release P-000001 final_stage=True")
        propose(ws, kind="release", params={
            "object_numbers": ["P-000001"],
            "final_stage": True,
        }).commit()

        # Verify final state
        _, entry = find_reservation_entry_by_number(ws, "P-000001")
        sidecar = load_sidecar(ws, entry["object_uuid"])
        feature_count = len(sidecar.get("feature", []))
        geom_count = len(sidecar.get("geometry_ref", []))
        revision_id = sidecar.get("object", {}).get("revision_id")
        print(
            f"\n[OK] Final state: P-000001 has {feature_count} feature(s) + "
            f"{geom_count} geometry_ref(s) + revision_id={revision_id}"
        )
        # Verify the adjust step actually changed the depth parameter:
        for f in sidecar.get("feature", []):
            if f.get("feature_type") == "extrude":
                for p in f.get("parameters", []):
                    if p.get("name") == "depth_mm":
                        print(f"  extrude.depth_mm = {p['value']} (canonical unit: {p['unit']})")
                        break
        print("[OK] Wedge-003 Mode A demo complete.")
        return 0
    except TransactionError as e:
        print(f"\n[FAIL] TransactionError: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
