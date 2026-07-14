---
source_context:
  no_proprietary_documents: true
  authored_against:
    - ADR/0035-display-representation-contract-and-topology-identity.md
    - ADR/0038-persistent-feature-reference-identity.md
    - aiadra-mechanical/src/aiadra_mechanical/recipe.py
    - aiadra-mechanical/src/aiadra_mechanical/adapter_payload.py
    - aiadra-mechanical/tests/test_sketch_plane_matrix.py
  actor: human
  aiadra_core_version: "0.14.0"
  aiadra_mechanical_adapter_schema_version: "0.1.7"
retrieval_tags: [mechanical, sketch, plane, principal, frame, orientation, extrude, direction, normal]
---

# Sketch planes: the principal-plane binding

**Payload:** a sketch feature may carry a discriminated plane record —
`{"plane": {"kind": "principal", "orientation": "xy" | "yz" | "zx"}}`. Absent
≡ principal **xy** (every pre-0.1.7 recipe keeps its meaning byte-for-byte).
`kind: "datum"` / `"offset"` are **reserved** future bindings that fail loud in
v1 — user-created datum planes slot in with no schema migration. Introduced arc
20260714-2 EP2; `adapter_schema_version` 0.1.6 → 0.1.7 (additive).

## The frame

Each orientation is a fixed right-handed (u, v, n) frame through the origin:

| orientation | u | v | n (sweep normal) |
|---|---|---|---|
| `xy` | +X | +Y | +Z |
| `yz` | +Y | +Z | +X |
| `zx` | +Z | +X | +Y |

**Sketch coordinates (`x_mm`/`y_mm`) are the sketch-LOCAL (u, v)** — never
global-axis claims. One shared `effective_plane_frame()` owns validation + the
mapping for the handlers, the evaluator, topology correlation, and display —
there is no per-module frame math.

## The consumed sketch is EXACT

An extrude/revolve resolves **the sketch its `sketch_feature_id` names**
(`resolve_consumed_sketch()`), never "the last sketch": it must exist, precede
its consumer, be a sketch, be unique, and agree with
`depends_on_feature_ids` — any violation fails Class-1 before OCCT. Two
sketches on different planes therefore cannot make the evaluator build the
wrong profile.

## Extrude direction

Canonical vocabulary: **`normal+` / `normal-`** — the sweep sign along the
sketch plane's normal. Legacy `z+`/`z-` is accepted **only** when the consumed
sketch's effective plane is principal xy (where it means the same thing);
stored legacy values are never rewritten; `z±` with a yz/zx sketch fails loud
at write time AND on every regeneration. New writes always store `normal±`.

## The identity rules (skeleton vs value)

- The plane **orientation is skeleton**: changing a sketch's plane reorients
  the whole solid → `topology_signature` changes and dependent references
  correctly invalidate. It enters the signature **only when non-default**, so
  absent-plane and explicit principal-xy recipes keep byte-identical
  signatures.
- The direction **sign is a value** (it flips the sweep, not the role set) —
  it stays out of the signature.
- Roles keep their names across a plane change (`cap_base`/`cap_top` by the
  frame-normal coordinate; walls by in-plane (u, v) midpoints) — the signature
  change carries the invalidation, exactly ADR/0038 D4.

## Invariants (v1 scope)

- One plane per sketch; the three principal planes only (`datum`/`offset`
  reserved). **Revolve remains principal-xy-only** (its axis vocabulary is the
  global x/y in the sketch plane) — enforced at the handler AND the evaluator.
- Fillet/chamfer/hole are topology-reference operations — plane-agnostic by
  construction (the hole's centre is sketch-local (u, v); its cut runs along
  the frame normal).

## Failure modes

| Cause | Class | Result |
|---|---|---|
| Unknown/reserved plane kind, bad orientation, extra keys | Class-1 | `TransactionError` (exact record validation) |
| `z±` with a yz/zx sketch (write or regeneration) | Class-1 | `TransactionError` "only valid on the principal xy plane" |
| Named sketch missing / duplicated / wrong type / after its consumer / dependency disagreement | Class-1 | `TransactionError` naming the exact violation |
| Revolve on a non-xy sketch | Class-1 | `TransactionError` "requires the sketch on the principal xy plane" |

## See also

- [features/contour.md](contour.md) · [golden-recipes/sketch-yz-plate.md](../golden-recipes/sketch-yz-plate.md) · [traces/sketch-plane-negative.md](../traces/sketch-plane-negative.md)
