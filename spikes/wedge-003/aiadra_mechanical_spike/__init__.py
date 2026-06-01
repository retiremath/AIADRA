"""Wedge-003 Native Engine spike package per ADR/0030.

Throwaway spike implementing the smallest viable AIADRA-native mechanical
authoring loop. Engine_id `mechanical_spike` per ADR/0030 D2 + Codex1 B2
R1 from arc 20260601-2 (avoids future duplicate-engine_id collision with
production `aiadra-mechanical` package).

Per ADR/0023 §4 + ADR/0030 D14 item 12: throwaway code. Production
mechanical Native Engine lives in `aiadra-mechanical` package (future arc).
"""
from __future__ import annotations

from .handlers import (
    handle_add_sketch_feature,
    handle_add_extrude_feature,
    handle_adjust_feature_parameter,
    handle_remove_feature,
)


__version__ = "0.0.1"
ADAPTER_SCHEMA_VERSION = "0.1.0"
ENGINE_ID = "mechanical_spike"


def register(registrar) -> None:
    """Called by `aiadra-core._discover_native_engines()` during entry-point
    discovery. The registrar is a `NativeEngineRegistrar` per ADR/0028 D2;
    enforces namespace discipline + no-built-in-overwrite + arity-only
    signature check on each add_operation call.

    Per ADR/0030 D5 (Codex1 N3 R1 absorption from arc 20260601-2): 4-op
    catalog. `mechanical_spike.recompute_geometry` was dropped — recompute
    happens automatically inside adjust_feature_parameter per ADR/0030 D4
    step 4 + Q8.
    """
    registrar.add_operation(
        "mechanical_spike.add_sketch_feature", handle_add_sketch_feature
    )
    registrar.add_operation(
        "mechanical_spike.add_extrude_feature", handle_add_extrude_feature
    )
    registrar.add_operation(
        "mechanical_spike.adjust_feature_parameter", handle_adjust_feature_parameter
    )
    registrar.add_operation(
        "mechanical_spike.remove_feature", handle_remove_feature
    )
