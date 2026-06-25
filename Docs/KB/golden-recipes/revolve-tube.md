---
source_context:
  no_proprietary_documents: true
  authored_against:
    - aiadra-mechanical/tests/test_revolve_feature.py
    - ADR/0037-modeling-paradigm-benchmark-and-knowledge-architecture.md
  actor: human
  aiadra_core_version: "0.13.0"
  aiadra_mechanical_adapter_schema_version: "0.1.5"
  outcomes: validated
retrieval_tags: [golden-recipe, revolve, tube, washer, mechanical, happy-path, creation]
---

# Golden recipe: revolve a rectangle into a tube

The revolve happy path — a creation feature (no prior topology referenced). Every
step + expected outcome is exercised by
`aiadra-mechanical/tests/test_revolve_feature.py`.

## Recipe

```text
1. create_part                       number=P-000001
2. mechanical.add_sketch_feature     rectangle x=0 y=2 w=20 h=3 mm   -> feat_0001
       (offset from the X axis so the revolve is a TUBE, not a solid cylinder)
3. mechanical.add_revolve_feature    sketch=feat_0001 axis=x         -> feat_0002
4. validate -> commit
```

## Expected outcomes

- **Step 3 persists** a revolve feature with `depends_on_feature_ids: [feat_0001]`
  and `adapter_payload = {sketch_feature_id: "feat_0001", axis: "x"}` — and **no
  numeric parameter** (the angle is a fixed 360°; the axis is structural).
- The sketch's `authoring_geometry` is **replaced** by one derived from both
  features; the `vault_ref` (recipe hash) changes.
- **The solid recomputes valid** — a tube/washer whose faces correlate
  recipe-first to `feat_0002:face:outer_wall`, `feat_0002:face:inner_wall`,
  `feat_0002:face:cap_lo`, `feat_0002:face:cap_hi` (plane + cylinder only).
- An **on-axis** profile (`y=0`) instead yields a **solid cylinder** — same roles
  minus `inner_wall`.

## Signature behaviour (the skeleton-vs-value line)

- Two tubes that differ only in radii (the rectangle's size/position, same side of
  the axis) **share** a topology signature — radii are values.
- A tube vs a solid cylinder have **different** signatures — the radial mode
  (which adds/removes `inner_wall`) is skeleton.
- Changing `axis` x → y changes the signature — the axis is skeleton.

## Why this matters

Revolve is the first creation feature since extrude to grow the **correlation**
layer: a revolve solid is a different topology family than the box, so the
recipe carries its base kind and the correlation dispatches to a revolve-specific
role mapper. v1 stays within plane + cylinder; cones / tori (richer profiles) are
a deferred v2, not a gap.
