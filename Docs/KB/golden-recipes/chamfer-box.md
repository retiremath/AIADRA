---
source_context:
  no_proprietary_documents: true
  authored_against:
    - aiadra-mechanical/tests/test_chamfer_feature.py
    - ADR/0038-persistent-feature-reference-identity.md
  actor: human
  aiadra_core_version: "0.13.0"
  aiadra_mechanical_adapter_schema_version: "0.1.4"
  outcomes: validated
retrieval_tags: [golden-recipe, chamfer, bevel, mechanical, happy-path]
---

# Golden recipe: bevel a box edge

The chamfer happy path — the fillet's edge-reference twin, with a flat bevel.
Every step + expected outcome is exercised by
`aiadra-mechanical/tests/test_chamfer_feature.py`.

## Recipe

```text
1. create_part                       number=P-000001
2. mechanical.add_sketch_feature     rectangle 23 x 11 mm           -> feat_0001
3. mechanical.add_extrude_feature    sketch=feat_0001 depth=6 z+    -> feat_0002
4. (read) mechanical.display_representation P-000001
       pick a sharp vertical wall-wall edge -> its display edge_id
5. mechanical.add_chamfer_feature    target_edge_id=<that id> distance=2 mm  -> feat_0003
6. validate -> commit
```

## Expected outcomes

- **Step 5 persists** a chamfer feature with `depends_on_feature_ids: [feat_0002]`,
  a `distance_mm = 2.0` canonical-unit parameter, and an
  `adapter_payload.target_edge` holding the structured recipe anchor (two sorted
  `adjacent_face_roles` + `edge_kind` + parent-prefix signature) — NOT the display
  `edge_id`, NOT the distance value (ADR/0038 D1/A2).
- **The solid recomputes valid** with a `feat_0003:face:chamfer` **plane** (claimed
  by construction, ADR/0038 A3) + the bevel's sharp edges; the original sharp edge
  is gone; the `vault_ref` changes.
- **Regeneration survives a parameter edit**: `feat_0002.depth_mm` 6 → 10 re-bevels
  unchanged; `distance_mm` 2 → 3 changes the recipe hash but not the topology
  signature.

## Why this matters

Chamfer is the cheap N=3 confirmation that the ADR/0038 edge-reference path reuses
cleanly — and it gives A3's mandatory produced-face claim its first **planar**
produced-face exercise (the bevel is a plane, where the fillet's blend was a
cylinder).
