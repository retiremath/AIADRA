---
source_context:
  no_proprietary_documents: true
  authored_against:
    - aiadra-mechanical/tests/test_contour_extrude.py
    - ADR/0037-modeling-paradigm-benchmark-and-knowledge-architecture.md
    - ADR/0035-display-representation-contract-and-topology-identity.md
  actor: human
  aiadra_core_version: "0.13.0"
  aiadra_mechanical_adapter_schema_version: "0.1.6"
  outcomes: validated
retrieval_tags: [golden-recipe, contour, closed-ring, L-shape, extrude, mechanical, happy-path, creation]
---

# Golden recipe: extrude an L-shaped contour into a plate

The contour happy path — a creation feature that bounds a non-rectangular area.
Every step + expected outcome is exercised by
`aiadra-mechanical/tests/test_contour_extrude.py`.

## Recipe

```text
1. create_part                     number=P-000001
2. mechanical.add_sketch_feature   contour, an L (6 line segments, closed):
       (0,0)->(60,0)->(60,20)->(20,20)->(20,50)->(0,50)->(0,0)         -> feat_0001
       (the last segment (0,50)->(0,0) is the EXPLICIT closer — no implicit edge)
3. mechanical.add_extrude_feature  sketch=feat_0001 direction=z+ depth=12mm  -> feat_0002
4. validate -> commit
```

## Expected outcomes

- **Step 2 mints** a stable id per segment (`skp_0001s01 … skp_0001s06`); these
  are the anchors for the wall roles and the signature skeleton.
- **Step 3 recomputes a valid solid** — a 12 mm-thick L-plate with **8 faces**:
  `feat_0002:face:cap_base`, `feat_0002:face:cap_top`, and six
  `feat_0002/skp_0001sNN:face:wall`, one per segment.
- The sketch's `authoring_geometry` `geometry_ref` derives from both features;
  identity stays the recipe hash.

## Signature behaviour (the skeleton-vs-value line)

- **Move a vertex** (e.g. extend the bottom-right corner from x=60 to x=65): the
  segment coordinates change but the ids/kinds do not → the six wall roles and the
  `topology_signature` are **unchanged** (coordinates are values).
- **Change the segment count** (an L's 6 segments vs a triangle's 3): the
  signatures **differ** — a segment insert/delete is skeleton.

## Why this matters

This is the first profile that bounds an arbitrary area — the step from "extrude a
rectangle" to "extrude a drawn shape". It grows the correlation layer the same way
revolve did: a contour extrude is a different (N-side) topology family, so the
recipe carries the outer-profile kind and correlation dispatches to a
segment-anchored wall mapper. Arcs/splines are reserved segment kinds (a future
build), not a gap — the schema already holds them.
