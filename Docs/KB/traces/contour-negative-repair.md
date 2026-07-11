---
source_context:
  no_proprietary_documents: true
  authored_against:
    - aiadra-mechanical/tests/test_contour_extrude.py
    - ADR/0037-modeling-paradigm-benchmark-and-knowledge-architecture.md
    - ADR/0031-native-engine-geometry-kernel-and-validity.md
  actor: human
  aiadra_core_version: "0.13.0"
  aiadra_mechanical_adapter_schema_version: "0.1.6"
retrieval_tags: [trace, negative, repair, contour, closed-ring, mechanical, domain-guard, creation]
---

# Trace: a contour hits its domain guards, then is repaired

A contour is a creation profile, so its failures are **domain guards on the ring
geometry**, not stale references. Each fails **loud before the kernel** (at write
time AND in the evaluator fold); the repair is to fix the ring. Mirrors
`test_open_ring_fails_class1`, `test_self_intersecting_contour_rejected`,
`test_too_few_segments_fail_class1`, and `test_unsupported_segment_kind_fails_loud`.

## Failure 1 — an open ring (FAIL, Class-1)

```text
mechanical.add_sketch_feature  contour = 5 segments, last end != first start
  -> TransactionError: contour primitive[0] is not a closed ring: segment[4] end
     (0.0, 50.0) does not meet segment[0] start (0.0, 0.0) (a gap; contours must
     close on an authored segment — no implicit closing edge)
```

**Repair:** add the final segment that returns to the start point. Closure is
explicit — the engine will not invent a closing edge, because an unanchored wall
cannot carry stable identity (Codex4 B1).

## Failure 2 — a self-intersecting ring (FAIL, Class-1)

```text
mechanical.add_sketch_feature  contour = a bowtie / crossing ring
  -> TransactionError: contour primitive[0] is self-intersecting; a valid profile
     is a simple (non-crossing) ring
```

**Repair:** reorder the vertices so the ring does not cross itself. A simple
polygon has a well-defined interior; a crossing one does not, and OCCT would build
a degenerate or empty face.

## Failure 3 — too few segments / zero area (FAIL, Class-1)

```text
mechanical.add_sketch_feature  contour = 2 segments
  -> TransactionError: contour primitive[0] needs at least 3 segments to bound an
     area, got 2
```

**Repair:** a closed area needs ≥3 segments; a degenerate ring that encloses zero
area is rejected the same way.

## Failure 4 — an unsupported segment kind (FAIL, Class-1)

```text
mechanical.add_sketch_feature  contour with a {"kind": "arc", …} segment
  -> TransactionError: contour primitive[0] segment[0] kind 'arc' is not supported
     in v1 (supported: ['line']; arc/spline reserved)
```

**Repair:** use `line` segments for now. `arc`/`spline` are reserved kinds — the
schema accepts them structurally so a future build can implement the curve wire
without a schema migration, but v1 fails loud rather than silently dropping them.

## Lesson for an authoring agent

A contour domain rejection is a **fix-the-ring** prompt, not a transient failure to
retry: close the ring on an authored segment, keep it simple (non-crossing), give
it ≥3 segments and non-zero area, and use `line` kinds. The guards fail before the
kernel so the message names the exact violation and the segment index.
