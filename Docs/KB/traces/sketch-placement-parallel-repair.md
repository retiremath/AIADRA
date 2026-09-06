---
source_context:
  no_proprietary_documents: true
  authored_against:
    - ADR/0044-sketcher-paradigm.md (Amendment A3.2 / A3.5)
    - aiadra-mechanical/src/aiadra_mechanical/sketch_placement.py
    - aiadra-mechanical/tests/test_sketch_placement.py (test_parallel_reference_refuses, test_placement_record_shapes, test_completion_refuses_unknown_members)
    - aiadra-studio/src/authoring/authoringSession.ts (PLACEMENT_FACE_REFUSAL)
  actor: human
  aiadra_core_version: "0.19.1"
  aiadra_mechanical_sketch_series: "0.2.1 / 0.2.2"
retrieval_tags: [trace, negative, repair, sketch, placement, orientation-reference, parallel, closed-record, face, refusal, mechanical, domain-guard]
---

# Trace: placement guards — the ENGINE refuses, the caller repairs

Placement is a closed four-member record. Three guard families fail **loud,
before any solving**, at write time AND on regeneration. In each case the
engine states the reason; the repair is the caller's — never a retry with the
same input. Mirrors `test_sketch_placement.py`'s negatives.

## Failure 1 — a parallel reference (FAIL, engine refusal)

An agent proposes the orientation reference equal to the sketch plane:

```text
mechanical.author_profile_sketch
  placement={support:{principal, xy}, orientation_ref:{principal, xy}, orientation:right, normal_side:positive}
  -> refused: placement orientation_ref must differ from support (both are 'xy') —
     a parallel reference has no castable direction …
```

**What the engine established:** the projection of a parallel plane's normal
into the sketch plane is the zero vector; no `u` can be cast.
**The caller's repair:** pick a non-parallel principal plane as the reference —
the canonical default for `xy` is `yz` (RIGHT); `zx` (FRONT) is the other
choice. Then the same call succeeds (see the golden recipe).

## Failure 2 — an unknown or missing member (FAIL, closed record)

```text
placement={support:{principal, xy}, flip:true}
  -> refused: placement carries unknown members ['flip'] (A3.2 is closed)
placement={orientation_ref:{principal, yz}}
  -> refused: … placement requires support
```

**Repair:** the vocabulary is exactly `support`, `orientation_ref`,
`orientation` (`right|top|left|bottom`), `normal_side` (`positive|negative`).
"Flip" is Studio's label for `normal_side: negative`, not a member. Omitted
nested members take the canonical defaults; `support` is always required.

## Failure 3 — a face offered as a placement reference (Studio refusal, product copy)

In the Studio dialog a click on a flat face while a collector is armed does
not place anything: *"Only the three datum planes can place a sketch here; a
flat face as the sketch plane arrives in a later step (the legacy Sketch keeps
face support)."* Nothing is applied and the datum plane behind the face is
never picked in its place. The engine's `0.2.x` placement record is
principal-only (`kind: principal`), so an agent must not send
`{kind: face, …}` either — it refuses with *placement … kind must be
'principal' …*.

## Distinguishing the voices

- **Engine refusals** name the member and the rule (the texts above) and
  reach every surface unweakened.
- **Studio's envelope** refuses only wire-shape errors in its own voice
  (`author_profile_sketch placement carries unknown members …`).
- **A repair** is the caller's proposal; it is never recorded as the engine's
  reason. After a repair, re-run `preview_sketch_graph` before committing.
