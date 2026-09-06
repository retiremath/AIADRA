---
source_context:
  no_proprietary_documents: true
  authored_against:
    - ADR/0044-sketcher-paradigm.md (Amendment A3 — sketch placement as Truth; A4 — the profile writer)
    - aiadra-mechanical/src/aiadra_mechanical/sketch_placement.py
    - aiadra-mechanical/src/aiadra_mechanical/sketch_v2.py
    - aiadra-mechanical/tests/test_sketch_placement.py
    - aiadra-mechanical/tests/data/placement_matrix.jsonl
    - aiadra-studio/src/authoring/placementFrame.ts
  actor: human
  aiadra_core_version: "0.19.1"
  aiadra_mechanical_sketch_series: "0.2.1 / 0.2.2"
retrieval_tags: [mechanical, sketch, placement, sketch-plane, orientation-reference, orientation, flip, normal-side, frame, sketch-view, v2, profile]
---

# Sketch placement: the two-reference frame (v2 sketches)

A v2 sketch (the constrained-model series, `0.2.1` construction sketches and
`0.2.2` drawn profiles) is placed by **four facts**, persisted together as one
closed `placement` record:

```
placement: {
  support:         {kind: "principal", orientation: "xy" | "yz" | "zx"},
  orientation_ref: {kind: "principal", orientation: "xy" | "yz" | "zx"},   # must differ from support
  orientation:     "right" | "top" | "left" | "bottom",
  normal_side:     "positive" | "negative",
}
```

`support` is the sketch plane. `orientation_ref` is a second plane whose
normal, projected into the sketch plane, defines which way the sketch's
**u/v** axes point; `orientation` says where that projected direction goes
(right / top / left / bottom of the sketch view). `normal_side` selects the
side you sketch FROM — the Studio labels it **Flip**, and it is a model fact:
a positive-depth feature built on the sketch grows to the other side when the
side is flipped.

Studio's dialog (arc 20260905-1) names the planes by the view that sees them
face-on: **TOP = xy** (the horizontal plane), **FRONT = zx**, **RIGHT = yz**.
The engine speaks only `xy` / `yz` / `zx`.

## Canonical defaults (engine-owned)

Picking a support fills the rest; the persisted record is always complete.

| support | orientation_ref | orientation | normal_side | frame (u, v, n) |
|---|---|---|---|---|
| `xy` (TOP) | `yz` (RIGHT) | right | positive | +X, +Y, +Z |
| `yz` (RIGHT) | `zx` (FRONT) | right | positive | +Y, +Z, +X |
| `zx` (FRONT) | `xy` (TOP) | right | positive | +Z, +X, +Y |

## The derivation (exact order)

1. `n₀` = the support plane's canonical normal; `n = n₀` for `positive`,
   `n = −n₀` for `negative` — the signed normal is selected FIRST.
2. `p` = the orientation_ref plane's normal projected into the support plane,
   normalized. A parallel pair is refused before any solving.
3. Map: `right: u = +p, v = n × u` · `left: u = −p, v = n × u` ·
   `top: v = +p, u = v × n` · `bottom: v = −p, u = v × n`.
4. The frame is right-handed on BOTH sides (`v = n × u`).

**The Flip law, stated once:** with `right`/`left`, flipping the side keeps
`u` and reverses `v` and `n`; with `top`/`bottom`, it keeps `v` and reverses
`u` and `n`. Flip is never a fixed-axis "reverse" transform.

Horizontal and vertical facts on sketch entities mean the USER's horizontal
and vertical — they are stated in this `u/v` frame, never in world axes.

Example — the acceptance scenario: support `xy`, reference `zx`, orientation
`top`, side `negative` gives `u = −X, v = +Y, n = −Z`; the sketch view looks
along `+Z` with `+Y` up.

## Which operation writes what

| route | operation | persisted version |
|---|---|---|
| a drawn profile (Studio: **Sketch** → placement → draw → Close) | `mechanical.author_profile_sketch` with `placement` + `profile` | `0.2.2` (placement nested; policy `skb-b1`) |
| a construction-only references sketch (Studio: **References**) | `mechanical.add_reference_sketch` with `placement` | `0.2.1` |
| re-placing an existing `0.2.1` references sketch | `mechanical.redefine_sketch_placement` (omitted members keep their value) | stays `0.2.1` |

A `0.2.0` record (the pre-placement series) keeps its frame forever; it is
never rewritten. Placement of a drawn `0.2.2` sketch is fixed once created —
editable placement for drawn sketches is a later capability, not a hidden one.

An AI agent proposing a sketch supplies the same `placement` input as the
dialog; omitted nested members take the canonical defaults above, and the
engine mints the complete record. The full 48-placement derivation matrix is
pinned as literals in `tests/data/placement_matrix.jsonl`, checked by the
engine and by Studio's mirror alike.
