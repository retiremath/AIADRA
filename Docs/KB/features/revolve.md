---
source_context:
  no_proprietary_documents: true
  authored_against:
    - ADR/0037-modeling-paradigm-benchmark-and-knowledge-architecture.md
    - ADR/0035-display-representation-contract-and-topology-identity.md
    - aiadra-mechanical/src/aiadra_mechanical/handlers.py
    - aiadra-mechanical/src/aiadra_mechanical/geometry.py
    - aiadra-mechanical/src/aiadra_mechanical/topology.py
    - aiadra-mechanical/tests/test_revolve_feature.py
  actor: human
  aiadra_core_version: "0.13.0"
  aiadra_mechanical_adapter_schema_version: "0.1.5"
retrieval_tags: [mechanical, feature, revolve, creation, surface-of-revolution, tube, washer, correlation]
---

# Feature: revolve

**Operation:** `mechanical.add_revolve_feature` · The first non-referencing
**creation** feature since extrude (ADR/0037 D8). A revolve sweeps a sketch
profile 360° around an in-plane axis to produce a solid of revolution. Unlike
fillet / chamfer / hole, it does **not** reference prior topology — it creates
base geometry, correlated recipe-first (like the extrude box).

## What it does

Given a sketch with one rectangle profile, a revolve sweeps it a full turn around
the global **X** or **Y** axis:

- profile **offset** from the axis → a **tube / washer** (outer cylinder wall +
  inner cylinder wall + two planar annular caps);
- profile **touching** the axis → a **solid cylinder** (one wall + two caps, no
  inner wall).

All v1 surfaces are **plane + cylinder** — the existing correlation vocabulary
covers it. Richer profiles (an angled or circular edge → cones / tori / spheres)
are a deferred v2.

## Parameters

The v1 revolve carries **no numeric parameter**. The angle is fixed at 360°; the
**axis** (`"x"` / `"y"`) is *structural* — it lives in `adapter_payload`, not in
`parameters[]`, because it is part of the topology skeleton (ADR/0038 A2 spirit:
the axis changes topology, so it is not a value edit). The radii come from the
sketch rectangle's position and size, edited on the sketch.

## Base-feature exclusivity (extrude XOR revolve)

A v1 Part has **exactly one** base creation: a sketch is either extruded **or**
revolved, never both. Enforced symmetrically — `add_revolve_feature` rejects a
Part that already has an extrude, `add_extrude_feature` rejects one that already
has a revolve, and the evaluator fails loud on a stored recipe carrying both
(no silent "last base wins").

## Truth-Model footprint

- A `feature` record (`feature_type: "revolve"`), `depends_on_feature_ids:
  [<sketch id>]`, `adapter_payload: {sketch_feature_id, axis}`.
- The sketch's `authoring_geometry` `geometry_ref` is replaced by one derived
  from **both** features (sketch + revolve); identity stays the recipe hash.
- Display roles, recipe-anchored to the revolve feature: `…:face:outer_wall` /
  `…:face:inner_wall` (cylinders, by absolute radius) + `…:face:cap_lo` /
  `…:face:cap_hi` (planar caps, by axis coordinate). `inner_wall` is absent in
  solid mode.

## Invariants (v1 scope)

- Exactly **one rectangle** profile (no circles / lines / extra rectangles), 360°,
  a global X/Y axis. The profile may not **cross** the axis (a self-intersecting
  revolve). OUT: partial-angle revolves, sketch-line axes, richer profiles
  (cones / tori), thin-revolve / shell, fold features (fillet/chamfer/hole) on a
  revolve.
- The correlation maps every face to a role or fails loud — a face-count
  mismatch, a non-plane/cylinder surface, or a cap whose normal is not the axis
  is a real bug, never a silent fallback.

## The paradigm lesson

The radial **mode** (tube vs solid) is *topology skeleton*, not a value: moving
the rectangle from offset to touching the axis adds or removes the `inner_wall`
role, so it changes the signature. The radii (the rectangle's dimensions) are
*values* — two tubes that differ only in size share a signature. This is the same
skeleton-vs-value line ADR/0038 draws for referencing features, applied to a
creation feature's derived topology.

## Failure modes

| Cause | Class | Result |
|---|---|---|
| `axis` not `"x"`/`"y"` | Class-1 domain | `TransactionError` "axis must be 'x' or 'y'" |
| Profile not exactly one rectangle | Class-1 domain | `TransactionError` "SIMPLE profile" (handler + evaluator) |
| Profile crosses the axis | Class-1 domain | `TransactionError` "crosses the …-axis" (handler + evaluator) |
| Part already has an extrude (or vice-versa) | Class-1 domain | `TransactionError` "one base creation per Part" |
| Stored recipe has BOTH bases | Class-1 domain | `TransactionError` "BOTH an extrude and a revolve" |
| Built solid disagrees with the recipe mode | Class-1 domain | `TransactionError` "face-count mismatch" |

## See also

- [features/fillet.md](fillet.md) · [features/hole.md](hole.md) · [features/chamfer.md](chamfer.md)
- [golden-recipes/revolve-tube.md](../golden-recipes/revolve-tube.md) · [traces/revolve-crossing-axis-repair.md](../traces/revolve-crossing-axis-repair.md)
