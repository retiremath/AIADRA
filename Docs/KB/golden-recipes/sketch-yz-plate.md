---
source_context:
  no_proprietary_documents: true
  authored_against:
    - aiadra-mechanical/tests/test_sketch_plane_matrix.py
    - ADR/0037-modeling-paradigm-benchmark-and-knowledge-architecture.md
  actor: human
  aiadra_core_version: "0.14.0"
  aiadra_mechanical_adapter_schema_version: "0.1.7"
  outcomes: validated
retrieval_tags: [golden-recipe, sketch, plane, yz, extrude, normal, mechanical, happy-path]
---

# Golden recipe: a plate extruded from the yz plane

The sketch-plane happy path — the same rectangle profile, bound to a
non-default principal plane, swept along its normal. Every step + expected
outcome is exercised by `aiadra-mechanical/tests/test_sketch_plane_matrix.py`.

## Recipe

```text
1. create_part                     number=P-000001
2. mechanical.add_sketch_feature   rectangle u=0 v=0 w=40 h=30 mm
       plane={kind: principal, orientation: yz}                 -> feat_0001
3. mechanical.add_extrude_feature  sketch=feat_0001 direction=normal+ depth=10mm
                                                                 -> feat_0002
4. validate -> commit
```

## Expected outcomes

- The sketch's `x_mm`/`y_mm` are sketch-LOCAL (u, v): on `yz`, u=+Y and v=+Z —
  the plate spans **y∈[0,40], z∈[0,30]** and sweeps along **+X to x=10**
  (`normal+`); `normal-` sweeps to x=−10 instead.
- The SAME six roles as an xy plate: `feat_0002:face:cap_base` (on the sketch
  plane, x≈0), `cap_top` (the swept end), four `…:face:wall_*` — role names do
  not encode the plane; the `topology_signature` does (it gains the `yz`
  orientation because it is non-default).
- A width edit (40→55) preserves every role id AND the signature (a value
  edit); re-binding the sketch to another plane changes the signature (a
  skeleton edit) and dependent references invalidate.
- `direction: z+` in step 3 would FAIL loud — legacy `z±` is xy-only; the
  canonical vocabulary is `normal±`.

## Why this matters

This is the step from "the engine models on XY" to "a sketch lives on a chosen
plane" — the substrate for the empty-part scaffold (three live datum planes)
and, later, datum-plane/face bindings (the reserved `datum`/`offset` kinds).
