---
source_context:
  no_proprietary_documents: true
  authored_against:
    - aiadra-mechanical/tests/test_hole_feature.py
    - ADR/0038-persistent-feature-reference-identity.md
  actor: human
  aiadra_core_version: "0.13.0"
  aiadra_mechanical_adapter_schema_version: "0.1.3"
  outcomes: validated
retrieval_tags: [golden-recipe, hole, face-reference, mechanical, happy-path]
---

# Golden recipe: drill a hole through a cap face

A worked model authored through AIADRA's own protocol — the first **face**
reference. Every step + expected outcome is exercised by
`aiadra-mechanical/tests/test_hole_feature.py`.

## Recipe

```text
1. create_part                       number=P-000001
2. mechanical.add_sketch_feature     rectangle 23 x 11 mm           -> feat_0001
3. mechanical.add_extrude_feature    sketch=feat_0001 depth=6 z+    -> feat_0002
4. (read) mechanical.display_representation P-000001
       pick the top cap face -> its display face_id (feat_0002:face:cap_top)
5. mechanical.add_hole_feature       target_face_id=<cap_top>
                                     diameter=4 mm, centre=(11.5, 5.5)  -> feat_0003
6. validate -> commit
```

## Expected outcomes

- **Step 5 persists** a hole feature with `depends_on_feature_ids: [feat_0002]`,
  three canonical-unit parameters (`diameter_mm`, `center_x_mm`, `center_y_mm`),
  and an `adapter_payload.target_face` holding the **structured recipe anchor**
  (the `face_role` + the parent-prefix `resolved_against_topology_signature`) —
  NOT the display `face_id` string, and NOT the value parameters (ADR/0038
  A1/A2).
- **The solid recomputes valid** with a `feat_0003:face:hole_wall` cylinder
  (claimed by construction, ADR/0038 A3) + the hole's rim edges; the Part's
  `authoring_geometry` `vault_ref` changes.
- **Regeneration survives parameter edits**: changing `feat_0002.depth_mm`
  (6 → 10) re-cuts the hole unchanged; changing the sketch width (23 → 30) keeps
  the hole at the same sketch-XY centre — sketch-coordinate placement is stable
  even though the OCCT face frame would have drifted.
- **Resizing/moving the hole is a parameter edit**: changing `diameter_mm`
  4 → 5 changes the recipe hash but **not** the topology signature.

## Why this is a paradigm proof

It is the first time committed Product Truth references a **face** of derived
topology. It proves ADR/0038 generalizes beyond its first (edge) shape: the same
deterministic-first regeneration contract — recipe-anchored reference, survive
parameter edits, fail loud on a topology change — holds for face references too.
