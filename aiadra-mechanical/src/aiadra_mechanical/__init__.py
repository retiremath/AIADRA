"""`aiadra-mechanical` — the first shippable AIADRA Native Engine (ADR/0031).

Registers the mechanical authoring operations (sketch / extrude / revolve /
fillet / chamfer / hole / adjust-parameter / remove) + the read-only display
operations under the `mechanical` engine_id via the `aiadra.native_engines` entry-point
group (ADR/0028 D2). Uses OCCT (via the `cadquery-ocp` binding) as a
geometry-validity kernel; geometry IDENTITY is the canonical feature recipe hash,
not the evaluated BREP (ADR/0031 D6).

**Install precondition (ADR/0031 D11):** `aiadra-core` must already be installed
in the venv (it is not yet published to PyPI, so it cannot be a declared pip
dependency). If it is absent, importing the handlers below fails at engine-load
time and aiadra-core's isolated discovery records a clear load failure for the
`mechanical` engine_id (ADR/0028 D5) — built-in operations and other engines are
unaffected.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

__version__ = "0.0.1"

if TYPE_CHECKING:
    from aiadra_core.native_engine.registrar import NativeEngineRegistrar


def register(registrar: "NativeEngineRegistrar") -> None:
    """Entry point called by aiadra-core during Native Engine discovery."""
    from .handlers import (
        handle_add_chamfer_feature,
        handle_add_extrude_feature,
        handle_add_fillet_feature,
        handle_add_hole_feature,
        handle_add_reference_sketch,
        handle_add_revolve_feature,
        handle_add_sketch_feature,
        handle_adjust_feature_parameter,
        handle_author_profile_sketch,
        handle_redefine_sketch_placement,
        handle_remove_feature,
        handle_replace_sketch_graph,
    )

    registrar.add_operation("mechanical.add_sketch_feature", handle_add_sketch_feature)
    # Gate F2b (ADR/0044 A2, arc 20260717-2): the FIRST v2 (adapter 0.2.0)
    # writer — the slice-1 references sketch (fixed origin + directed axes).
    registrar.add_operation("mechanical.add_reference_sketch", handle_add_reference_sketch)
    # ADR/0044 A3 (arc 20260725-2, pass sketch-place-1; Petre's SP-06 ruling):
    # the 0.2.1 placement redefine — the strict minimal-delta edit.
    registrar.add_operation("mechanical.redefine_sketch_placement", handle_redefine_sketch_placement)
    # ADR/0044 A4 (arc 20260730-1, pass sketch-line-1 increment I1): the
    # 0.2.2 PROFILE lane — ONE fact graph behind every drawing tool. The
    # create/edit pair are write operations; the preview is a READ (below).
    registrar.add_operation("mechanical.author_profile_sketch", handle_author_profile_sketch)
    registrar.add_operation("mechanical.replace_sketch_graph", handle_replace_sketch_graph)
    registrar.add_operation("mechanical.add_extrude_feature", handle_add_extrude_feature)
    # First non-referencing CREATION feature since extrude — ADR/0037 D8 (arc 20260622-4).
    registrar.add_operation("mechanical.add_revolve_feature", handle_add_revolve_feature)
    # First referencing feature (edge) — ADR/0037 D8 step 1; ADR/0038 (arc 20260621-2).
    registrar.add_operation("mechanical.add_fillet_feature", handle_add_fillet_feature)
    # The fillet's edge-reference twin — ADR/0037 D8 (arc 20260622-3).
    registrar.add_operation("mechanical.add_chamfer_feature", handle_add_chamfer_feature)
    # First FACE reference — ADR/0037 D8; ADR/0038 A1-A3 (arc 20260622-2).
    registrar.add_operation("mechanical.add_hole_feature", handle_add_hole_feature)
    registrar.add_operation("mechanical.adjust_feature_parameter", handle_adjust_feature_parameter)
    registrar.add_operation("mechanical.remove_feature", handle_remove_feature)

    # Read-only display generation (arc 20260609-1; ADR/0035). Separate read
    # lane — never sees a staging context, never a Transaction.
    from .display import handle_display_representation

    registrar.add_read_operation(
        "mechanical.display_representation", handle_display_representation
    )

    # Read-only view-dependent HLR (arc 20260609-2; contract v1.1). Same read
    # lane; consumes the SAME topology records as display (Codex1 B1).
    from .hlr import handle_display_hlr

    registrar.add_read_operation("mechanical.display_hlr", handle_display_hlr)

    # ADR/0044 A4: the live drawing preview. Same read lane — no draft, no
    # staging, no audit, no minted id. It shares the ONE compiler with the
    # two write operations above, which is what makes "what you see while
    # drawing" and "what gets committed" the same computation.
    from .handlers import handle_preview_sketch_graph

    registrar.add_read_operation(
        "mechanical.preview_sketch_graph", handle_preview_sketch_graph
    )
