---
source_context:
  no_proprietary_documents: true
  authored_against:
    - aiadra-mechanical/tests/test_revolve_feature.py
    - ADR/0037-modeling-paradigm-benchmark-and-knowledge-architecture.md
  actor: human
  aiadra_core_version: "0.13.0"
  aiadra_mechanical_adapter_schema_version: "0.1.5"
retrieval_tags: [trace, negative, repair, revolve, creation, mechanical, domain-guard]
---

# Trace: a revolve hits its domain guards, then is repaired

Revolve is a creation feature, so its failures are **domain guards on the
profile/axis**, not stale references. Each fails **loud** before the kernel;
the repair is to fix the profile or the base-feature choice. Mirrors
`test_crossing_axis_rejected_*`, `test_non_simple_profile_*`, and the symmetric
XOR tests.

## Failure 1 — the profile crosses the axis (FAIL, Class-1)

```text
mechanical.add_revolve_feature  sketch=<rect y=-2..3, straddles the X axis>  axis=x
  -> TransactionError: mechanical: revolve profile crosses the x-axis (a
     self-intersecting v1 revolve); offset the profile to one side of the axis
```

**Repair:** move the rectangle entirely to one side (e.g. `y` ≥ 0). Touching the
axis (`y=0`) is allowed — it makes a solid cylinder; crossing it is not.

## Failure 2 — a non-simple profile (FAIL, Class-1, handler AND evaluator)

```text
sketch has a rectangle + a circle
mechanical.add_revolve_feature  sketch=<that>  axis=x
  -> TransactionError: v1 revolve requires a SIMPLE profile of exactly one
     rectangle (no circles, lines, or extra rectangles); got ['rectangle','circle']
```

The guard is enforced in both the handler (early error) and the evaluator fold
(a stored/corrupt recipe), so a stray primitive is **never** silently dropped —
which would make Product Truth claim a revolve of more than was actually swept.

**Repair:** author a sketch with exactly one rectangle for the revolve profile.

## Failure 3 — two base creations (FAIL, Class-1, symmetric)

```text
Part already has an extrude
mechanical.add_revolve_feature  ...
  -> TransactionError: Part P-000001 already has an extrude base feature; v1
     supports exactly one base creation per Part (extrude XOR revolve)
```

The mirror holds: `add_extrude_feature` on a Part that already revolves fails the
same way, and a stored recipe with both bases fails loud in the evaluator rather
than letting "last base wins" decide the solid.

**Repair:** pick one base creation. To switch, remove the existing base feature
first, then add the other.

## Lesson for an authoring agent

A revolve domain rejection is a **fix-the-input** prompt, not a transient failure
to retry: offset the profile off the axis, keep the profile to one rectangle, and
choose a single base creation per Part. The guards fail before the kernel so the
message names the exact violation.
