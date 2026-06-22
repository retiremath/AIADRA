---
source_context:
  no_proprietary_documents: true
  authored_against:
    - aiadra-mechanical/tests/test_fillet_feature.py
    - ADR/0038-persistent-feature-reference-identity.md
  actor: human
  aiadra_core_version: "0.13.0"
  aiadra_mechanical_adapter_schema_version: "0.1.2"
  outcomes: validated   # every step below is asserted in the cited test suite
retrieval_tags: [golden-recipe, fillet, mechanical, happy-path]
---

# Golden recipe: round a box edge

A worked model authored entirely through AIADRA's own protocol — the happy path
for the fillet feature. Every step + expected outcome is exercised by
`aiadra-mechanical/tests/test_fillet_feature.py`.

## Recipe

```text
1. create_part                       number=P-000001
2. mechanical.add_sketch_feature     rectangle 23 x 11 mm           -> feat_0001
3. mechanical.add_extrude_feature    sketch=feat_0001 depth=6 z+    -> feat_0002
4. (read) mechanical.display_representation P-000001
       pick a sharp vertical wall-wall edge -> its display edge_id
5. mechanical.add_fillet_feature     target_edge_id=<that id> radius=2 mm  -> feat_0003
6. validate -> commit
```

## Expected outcomes

- **Step 5 persists** a fillet feature with `depends_on_feature_ids: [feat_0002]`,
  a `radius_mm = 2.0` canonical-unit parameter, and an `adapter_payload.target_edge`
  holding the **structured recipe anchor** (two sorted `adjacent_face_roles`, the
  `edge_kind`, and the parent-prefix `resolved_against_topology_signature`) —
  NOT the display `edge_id` string (ADR/0038 D1).
- **The solid recomputes valid**: faces 6 → 7 (one cylindrical blend added),
  edges 12 → 15 (the sharp target edge replaced by two tangent edges + blend
  edges). The Part's `authoring_geometry` `vault_ref` changes (new recipe hash).
- **Display** shows a `feat_0003:face:blend` face (cylinder, by construction) and
  `tangent` edges; the original sharp edge id is absent from the set.
- **Regeneration survives a parameter edit**: `adjust_feature_parameter` on
  `feat_0002.depth_mm` (6 → 10) recomputes the fillet unchanged — the reference
  is preserved because the topology skeleton did not change.

## Why this is a paradigm proof, not just a feature test

Step 5 is the first time committed Product Truth references derived topology. The
recipe demonstrates the deterministic-first regeneration contract: the fillet is
named by recipe-anchored roles, survives dimensional change, and (see the
companion negative/repair trace) fails loud rather than guessing on a topology
change.
