---
source_context:
  no_proprietary_documents: true
  authored_against:
    - ADR/0037-modeling-paradigm-benchmark-and-knowledge-architecture.md
    - ADR/0035-display-representation-contract-and-topology-identity.md
    - ADR/0038-persistent-feature-reference-identity.md
    - aiadra-mechanical/src/aiadra_mechanical/adapter_payload.py
    - aiadra-mechanical/src/aiadra_mechanical/geometry.py
    - aiadra-mechanical/src/aiadra_mechanical/topology.py
    - aiadra-mechanical/tests/test_contour_extrude.py
  actor: human
  aiadra_core_version: "0.13.0"
  aiadra_mechanical_adapter_schema_version: "0.1.6"
retrieval_tags: [mechanical, sketch, contour, profile, closed-ring, segment, extrude, creation, correlation]
---

# Sketch profile: contour (arbitrary closed ring)

**Primitive:** a `contour` sketch primitive — the second **outer profile** family
(alongside `rectangle`). It lets a sketch bound an arbitrary planar area, so an
extrude is no longer limited to a rectangle. Introduced arc 20260711-11 slice E;
bumps `adapter_schema_version` 0.1.5 → 0.1.6 (additive — the rectangle path is
untouched).

## What it is

An **ordered, closed ring of typed segments**. v1 implements `kind: "line"` only;
`arc` and `spline` are reserved segment kinds that **fail loud** until their curve
build lands — so the schema is future-proof without a migration.

```text
{"type": "contour", "segments": [
   {"kind": "line", "x1_mm": 0,  "y1_mm": 0,  "x2_mm": 60, "y2_mm": 0},
   {"kind": "line", "x1_mm": 60, "y1_mm": 0,  "x2_mm": 60, "y2_mm": 20},
   … ,
   {"kind": "line", "x1_mm": 0,  "y1_mm": 50, "x2_mm": 0,  "y2_mm": 0}   # explicit closer
]}
```

## Explicit closure — no implicit closing edge

A contour is closed by an **authored** final segment (`segment[n-1].end ==
segment[0].start`), never by a hidden auto-closing edge. Every wall-producing
segment — including the closer — carries an engine-minted stable id
(`{contour_id}s{NN}`), because that id is the **anchor** for the wall's display
role and the topology signature. An implicit closing edge would have no anchor,
forcing a placeholder / positional / special-case identity — which ADR/0035 and
ADR/0038 forbid.

## Truth-Model footprint

- Rides in the sketch feature's `adapter_payload.primitives[]` as the single
  outer profile (exactly one of `{rectangle, contour}` per sketch; a `circle`
  hole is **not** supported with a contour in v1 — contour = outer boundary only).
- Extruding a contour of N segments yields a solid with **N side walls + 2 caps**.
- Display roles, recipe-anchored to the extrude feature: `…:face:cap_base`
  (sketch plane, z≈0) / `…:face:cap_top` (swept end), and one
  `{extrude_id}/{segment_id}:face:wall` per segment.

## The paradigm lesson (skeleton vs value)

- Moving a **vertex** edits segment coordinates only → the segment ids/kinds are
  unchanged → **every wall role id and the `topology_signature` are preserved.**
  A downstream fillet/chamfer/hole targeting a wall survives the edit.
- **Inserting/deleting a segment** (or a future `line`→`arc` kind change) changes
  the segment count/ids → the signature changes → dependent references correctly
  invalidate. This is ADR/0038's skeleton-vs-value line, applied to a creation
  feature's derived topology (as revolve did for its radial mode).

## Invariants (v1 scope)

- A closed, **simple** (non-self-intersecting) planar ring of ≥3 line segments,
  non-zero enclosed area, no zero-length segments, and **a real turn at every
  vertex** (no collinear adjacent segments — a redundant vertex or fold-back is
  rejected) so each segment produces exactly one wall. OUT: arcs/splines, inner
  loops (holes) inside a contour, a contour revolve, dimensional constraints (the
  contour stores coordinates directly — no constraint solver in v1).
- The segment↔wall map is a **bijection**: correlation maps every declared
  segment to exactly one wall or **fails loud** — a missing wall (a coplanar
  merge), a duplicated wall, or a non-planar face is a real bug, never a
  positional fallback or a silently-incomplete identity.

## Failure modes

| Cause | Class | Result |
|---|---|---|
| Fewer than 3 segments | Class-1 domain | `TransactionError` "at least 3 segments" |
| Open ring (a gap between segments) | Class-1 domain | `TransactionError` "not a closed ring … a gap" |
| Self-intersecting ring | Class-1 domain | `TransactionError` "self-intersecting" |
| Zero enclosed area (degenerate) | Class-1 domain | `TransactionError` "encloses zero area" |
| Zero-length segment | Class-1 domain | `TransactionError` "zero-length" |
| Collinear adjacent segments (redundant vertex / fold-back) | Class-1 domain | `TransactionError` "collinear adjacent segments … one wall per segment" |
| Unsupported segment kind (`arc`/`spline`) | Class-1 domain | `TransactionError` "not supported in v1" |
| Contour + circle hole | Class-1 domain | `TransactionError` "contour = outer boundary only" |
| Two outer profiles (rectangle + contour) | Class-1 domain | `TransactionError` "exactly one outer profile" |

Every check runs at **write time** (good user errors) **and** in the evaluator
fold (a stored/edited/corrupt recipe), so no breach reaches OCCT on any path.

## See also

- [features/revolve.md](revolve.md) — the other creation feature that grew the correlation layer
- [golden-recipes/contour-l-bracket.md](../golden-recipes/contour-l-bracket.md) · [traces/contour-negative-repair.md](../traces/contour-negative-repair.md)
