---
source_context:
  no_proprietary_documents: true
  authored_against:
    - ADR/0038-persistent-feature-reference-identity.md
    - aiadra-mechanical/src/aiadra_mechanical/handlers.py
    - aiadra-mechanical/src/aiadra_mechanical/geometry.py
    - aiadra-mechanical/tests/test_chamfer_feature.py
  actor: human
  aiadra_core_version: "0.13.0"
  aiadra_mechanical_adapter_schema_version: "0.1.4"
retrieval_tags: [mechanical, feature, chamfer, bevel, edge-reference, regeneration]
---

# Feature: chamfer

**Operation:** `mechanical.add_chamfer_feature` · The fillet's **edge-reference
twin** (ADR/0037 D8). A chamfer bevels an existing sharp model edge with a flat,
symmetric, single-distance cut. It reuses the ADR/0038 edge-reference machinery
unchanged.

## What it does

Given a Part with an extruded solid, a chamfer replaces one **sharp** edge with a
flat **bevel** face — a plane (unlike a fillet's cylindrical blend). The two
original faces meeting at the edge are trimmed back to the bevel; new **sharp**
edges appear where the bevel meets each face (a flat cut, not a tangent blend).

## Parameters

| Parameter | Where | Type | Notes |
|---|---|---|---|
| `distance_mm` | `feature.parameters[]` | number, `unit: "mm"` | Symmetric chamfer distance (equal on both faces). Positive. A VALUE parameter — excluded from the topology skeleton (ADR/0038 A2). |

## The target-edge reference (ADR/0038)

Identical in shape to the fillet's: `feature.adapter_payload.target_edge` carries
the sorted pair of recipe-anchored `adjacent_face_roles` + `edge_kind` + the
parent-prefix `resolved_against_topology_signature`. The display `edge_id` is an
**input selector** only; the handler resolves it against a fresh extraction and
persists the structured anchor. (The builder `build_edge_reference_payload` is
shared by fillet and chamfer.)

## Truth-Model footprint

- A `feature` record (`feature_type: "chamfer"`), `depends_on_feature_ids:
  [<parent extrude id>]`.
- The `authoring_geometry` `geometry_ref` extends to derive from the chamfer;
  identity stays the recipe hash (`vault_ref`).
- Display: a `feat_N:face:chamfer` face role (a **plane**, claimed by
  construction — ADR/0038 A3) + the bevel's sharp edges.

## Invariants (v1 scope)

- One **sharp** edge, **symmetric single-distance**, one parent solid, one
  reference. OUT: asymmetric / two-distance / angle chamfers, edge-chains,
  tangent-edge targets, heuristic reattachment.
- The target reference resolves to exactly one edge or fails loud — never a guess.

## The paradigm lesson

Same as the fillet: a parameter edit (the `distance_mm`, or a parent dimension)
survives because it preserves the topology skeleton; a topology edit (a new
sketch primitive, a removed parent) fails loud and asks for the edge to be
re-picked (ADR/0038 D4). Resizing the chamfer is a parameter edit, not a topology
change (A2). The chamfer is the first feature to exercise ADR/0038 A3's mandatory
produced-face claim on a **planar** produced face.

## Failure modes

| Cause | Class | Result |
|---|---|---|
| `distance_mm` ≤ 0 / missing | Class-1 domain | `TransactionError` before the kernel |
| `target_edge_id` not on the part | Class-1 domain | `TransactionError` "not found" |
| Target edge is not `sharp` | Class-1 domain | `TransactionError` "v1 bevels a SHARP edge only" |
| Parent topology skeleton changed | Class-1 domain | `TransactionError` "STALE — re-pick the edge" |
| Reference resolves to 0 / >1 edges | Class-1 domain | `TransactionError` "NO edge" / "AMBIGUOUS" |
| Removing the parent solid while the chamfer remains | core fold | `FoldInconsistencyError` (ADR/0029 D12) |
| Plausible reference, distance too large to build | Class-2 kernel | `NativeEngineKernelError` (OCCT rejects) |

## See also

- [features/fillet.md](fillet.md) — the rounding twin (a cylindrical blend).
- [golden-recipes/chamfer-box.md](../golden-recipes/chamfer-box.md) · [traces/chamfer-negative-repair.md](../traces/chamfer-negative-repair.md)
