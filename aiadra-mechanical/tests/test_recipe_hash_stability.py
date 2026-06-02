"""Recipe-hash identity stability (ADR/0031 D6 + arc 20260602-1 Codex1 N4).

`vault_ref` = sha256 of the canonical feature recipe. It must be stable across
runs/parts for identical recipes and independent of kernel state; irrelevant
record metadata (fact_provenance, version material) must NOT affect it, while
actual feature parameters MUST.
"""
from __future__ import annotations

from pathlib import Path

from aiadra_core.protocol import propose

from aiadra_mechanical import kernel
from conftest import part_sidecar, two_primitives


def _sketch_features(depth: float | None = None) -> list[dict]:
    feats = [{"id": "feat_0001", "feature_type": "sketch",
              "fact_provenance": {"category": "ai_proposal"},
              "adapter_payload": {"primitives": two_primitives()}}]
    if depth is not None:
        feats.append({"id": "feat_0002", "feature_type": "extrude",
                      "fact_provenance": {"category": "ai_proposal"},
                      "adapter_payload": {"direction": "z+", "sketch_feature_id": "feat_0001"},
                      "parameters": [{"id": "featp_0001", "name": "depth_mm", "value": depth,
                                      "datatype": "number", "unit": "mm"}]})
    return feats


def test_identical_recipe_same_hash():
    assert kernel.recipe_hash(_sketch_features()) == kernel.recipe_hash(_sketch_features())


def test_provenance_metadata_does_not_affect_recipe_hash():
    """N4 golden: fact_provenance is NOT part of the geometry recipe."""
    a = _sketch_features(depth=5.0)
    b = _sketch_features(depth=5.0)
    for f in b:
        f["fact_provenance"] = {"category": "human_input", "ai_agent_ref": "noise"}
    assert kernel.recipe_hash(a) == kernel.recipe_hash(b)


def test_parameter_value_changes_recipe_hash():
    """N4 golden: an actual feature parameter DOES affect the hash."""
    assert kernel.recipe_hash(_sketch_features(depth=5.0)) != kernel.recipe_hash(_sketch_features(depth=8.0))


def test_vault_ref_is_recipe_hash_for_two_independent_parts(workspace: Path):
    """Two Parts authored with identical primitives get an identical
    authoring_geometry vault_ref (content-addressed recipe identity)."""
    ws = workspace
    for n in ("P-000001", "P-000002"):
        propose(ws, kind="create_part", params={"number": n, "name": n}).commit()
        propose(ws, kind="mechanical.add_sketch_feature", params={
            "part_number": n, "primitives": two_primitives()}).commit()
    v1 = part_sidecar(ws, "P-000001")["geometry_ref"][0]["vault_ref"]
    v2 = part_sidecar(ws, "P-000002")["geometry_ref"][0]["vault_ref"]
    assert v1 == v2
    assert v1.startswith("sha256:")
