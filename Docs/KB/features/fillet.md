---
source_context:                       # ADR/0037 D7 provenance attestation
  no_proprietary_documents: true      # ADR/0037 D3 rule 1 — original-content firewall
  authored_against:
    - ADR/0038-persistent-feature-reference-identity.md
    - ADR/0037-modeling-paradigm-benchmark-and-knowledge-architecture.md
    - aiadra-mechanical/src/aiadra_mechanical/handlers.py
    - aiadra-mechanical/src/aiadra_mechanical/geometry.py
    - aiadra-mechanical/src/aiadra_mechanical/topology.py
    - aiadra-mechanical/tests/test_fillet_feature.py
  actor: human                        # Claude (lead); reviewed as original expression
  aiadra_core_version: "0.13.0"
  aiadra_mechanical_adapter_schema_version: "0.1.2"
retrieval_tags: [mechanical, feature, fillet, round, reference-identity, regeneration]
---

# Feature: fillet (round)

**Operation:** `mechanical.add_fillet_feature` · **First referencing feature**
(ADR/0037 D8 step 1). A fillet rounds an existing model edge with a constant
radius. It is the first AIADRA feature that *references topology produced by a
prior feature* and must keep referencing it as the model regenerates.

## What it does

Given a Part that already has an extruded solid, a fillet replaces one sharp
edge with a smooth blend surface (a quarter-cylinder for a straight edge). The
two original faces meeting at the edge are trimmed back to the blend; two new
**tangent** edges appear where the blend meets each face.

## Parameters

| Parameter | Where | Type | Notes |
|---|---|---|---|
| `radius_mm` | `feature.parameters[]` | number, `unit: "mm"` | Constant radius. First-class canonical-unit Product-Truth record (not a kernel option). Must be positive. |

## The target-edge reference (ADR/0038)

The fillet persists, in `feature.adapter_payload.target_edge`, an **engine-owned,
recipe-anchored reference** — never the read-side display `edge_id` string:

```json
"target_edge": {
  "adjacent_face_roles": ["<feature>/<prim>:face:wall_x_max",
                          "<feature>/<prim>:face:wall_y_min"],
  "edge_kind": "sharp",
  "resolved_against_topology_signature": "topo_xxxxxxxxxxxxxxxx"
}
```

- The edge is named by the **sorted pair of recipe-anchored adjacent face roles**
  (the same roles ADR/0035 derives for display) plus its kind. The display
  `edge_id` a UI pick or recipe supplies is only an **input selector**; the
  handler resolves it against a fresh extraction and persists the structured
  anchor read from *that* extraction.
- `resolved_against_topology_signature` records the **parent-prefix** topology
  signature the reference was resolved against (staleness evidence).

## Truth-Model footprint

- A new `feature` record (`feature_type: "fillet"`), with
  `depends_on_feature_ids: [<parent extrude id>]`.
- The Part's `authoring_geometry` `geometry_ref` extends its
  `derived_from_feature_ids` to include the fillet; identity stays the recipe
  hash (`vault_ref`, ADR/0031 D6) — a new hash after the fillet is added/edited.
- Display: a `…:face:blend` face role (by construction, ADR/0038 D6) +
  `tangent` edges through the existing display/HLR lanes.

## Invariants (v1 scope)

- Exactly **one** edge, **constant** radius, **one** parent solid, **one**
  reference. No edge chains, face loops, variable radius, or heuristic
  reattachment.
- The target reference resolves to **exactly one** edge or the operation **fails
  loud** — never a nearest-geometry guess.

## The paradigm lesson — why a parameter edit survives but a topology edit fails

This is the load-bearing idea an AI authoring agent must internalize (ADR/0038
D4):

- **A parameter edit survives.** Changing the parent extrude's `depth_mm` (or the
  rectangle's `width_mm`) changes *dimensions*, not the topology **skeleton**.
  The recipe-anchored role pair (`wall_x_max ~ wall_y_min`) still names the same
  edge, so the fillet re-resolves and recomputes automatically. The
  `topology_signature` is value-independent (ADR/0035 D3), so it is unchanged.
- **A topology edit fails loud.** Adding/removing a feature or primitive (e.g.
  cutting a hole into the parent sketch) changes the skeleton — the parent-prefix
  `topology_signature` no longer matches the stored
  `resolved_against_topology_signature`. AIADRA refuses to guess which edge the
  fillet "should" now mean; it fails before commit and asks for the edge to be
  re-picked. Deterministic-first; reattachment UX is a deliberate future concern.

## Failure modes

| Cause | Class | Result |
|---|---|---|
| `radius_mm` ≤ 0 / missing | Class-1 domain | `TransactionError` before the kernel |
| `target_edge_id` not on the part | Class-1 domain | `TransactionError` "not found" |
| Target edge is not `sharp` (tangent/seam/boundary/free) | Class-1 domain | `TransactionError` "v1 rounds a SHARP edge only" — v1 supports a single sharp edge |
| Parent topology skeleton changed | Class-1 domain | `TransactionError` "STALE — re-pick the edge" |
| Reference resolves to 0 edges (missing role) | Class-1 domain | `TransactionError` "resolves to NO edge" |
| Reference resolves to >1 edge (ambiguous) | Class-1 domain | `TransactionError` "AMBIGUOUS" |
| Removing the parent solid while the fillet remains | core fold | `FoldInconsistencyError` (ADR/0029 D12 cascade) |
| Plausible reference, radius too large to build | Class-2 kernel | `NativeEngineKernelError` (OCCT rejects) |

## See also

- [ADR/0038](../../ADR/0038-persistent-feature-reference-identity.md) — the reference-identity rule.
- [golden-recipes/fillet-box.md](../golden-recipes/fillet-box.md) — a worked recipe.
- [traces/fillet-negative-repair.md](../traces/fillet-negative-repair.md) — a fail-then-repair trace.
