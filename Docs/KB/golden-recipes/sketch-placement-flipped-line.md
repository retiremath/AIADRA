---
source_context:
  no_proprietary_documents: true
  authored_against:
    - ADR/0044-sketcher-paradigm.md (Amendment A3 — placement; A4 — the profile writer)
    - aiadra-mechanical/tests/test_profile_sketch_ops.py (TestPlacementThroughTheProfileWriter, TestGoldenRecipePlacement)
    - aiadra-studio/bridge/test_i3_placement_requests.py
    - aiadra-mechanical/src/aiadra_mechanical/sketch_placement.py
  actor: human
  aiadra_core_version: "0.19.1"
  aiadra_mechanical_sketch_series: "0.2.2"
  outcomes: validated
retrieval_tags: [golden-recipe, sketch, placement, flip, normal-side, orientation-reference, profile, line, horizontal, preview, candidate, mechanical, happy-path]
---

# Golden recipe: a line on a flipped, re-oriented sketch plane

The two-reference placement happy path through the PUBLIC protocol — pick a
Part, place a sketch with a complete NON-default placement, draw one
near-horizontal line, **evaluate it as a transient candidate first**, inspect
the result, then commit and reopen. Every step and expected outcome is
exercised by `test_profile_sketch_ops.py::TestGoldenRecipePlacement` and the
connected Studio→engine fixture test `bridge/test_i3_placement_requests.py`.

## Recipe

```text
1. create_part                          number=P-000001 name="Bracket"

2. preview_sketch_graph                 (READ — no draft, no write, no audit)
     object_ref=P-000001 engine_id=mechanical candidate_key=draft1
     placement={support:{kind:principal, orientation:xy},          # TOP
                orientation_ref:{kind:principal, orientation:zx},  # FRONT
                orientation:top, normal_side:negative}             # Flip on
     profile={points:[{key:a, x:0,  y:0},                          # sketch mm
                      {key:b, x:20, y:0.4}],
              segments:[{key:e, start:{key:a}, end:{key:b}}],
              facts:[{key:h, kind:horizontal, target:{key:e}}]}
   -> preview.points[*].world, .annotations, .constraint_glyphs (below)

3. mechanical.author_profile_sketch     (the ONLY writer; same placement + profile)
     part_number=P-000001 placement=… profile=…                    -> feat_0001
4. validate -> commit

5. display_representation P-000001      (the reopen: what any later reader sees)
```

## Expected outcomes

- **The frame** (`sketch_frames[]` row for `feat_0001`): `u = −X, v = +Y,
  n = −Z`. Derivation: Flip selects `n = −Z` first; FRONT's normal `+Y`
  projected into TOP is `p = +Y`; `top ⇒ v = +p, u = v × n = −X`.
- **The record** is `0.2.2` with the complete four-member `placement` nested
  verbatim and `branch_policy: skb-b1`. All four members are Truth; the axes
  are never stored.
- **The solved line** obeys the horizontal fact in the sketch frame: both
  points share `v` → both world points share **Y**; sketch `+u` runs along
  world **−X**, so point b lands at world `x = −20`. `preview` and the
  committed display agree point for point (the candidate IS the commit).
- **Units**: sketch `x`/`y` and `world` are millimetres; the frame axes are
  unit vectors.
- **What an agent reads back**: `points[].world` (evaluated geometry),
  `annotations` (the derived weak dimensions with their values), and
  `constraint_glyphs` (the horizontal fact on segment `e`) — authored facts
  and evaluated geometry are separately identifiable.

## The human-acceptance step

In Studio the SAME placement arrives through the Sketch dialog (Plane TOP,
Reference FRONT, Orientation Top, Flip) and the drawn line through pointer
rays converted in this frame; OK/Close is the acceptance that runs step 3.
The dialog's record and the directly authored record are identical — the
connected fixture test pins the Studio pipeline's exact request and commits it
through the real engine.

## Variations

- `normal_side: positive` keeps `v = +Y` and gives `u = +X, n = +Z` (Flip
  under `top` preserves `v`, reverses `u` and `n`).
- `orientation: right` with the same references gives `u = +Y, v = +X` on the
  negative side (Flip under `right` preserves `u`).
