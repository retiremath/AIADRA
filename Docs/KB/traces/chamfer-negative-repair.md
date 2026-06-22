---
source_context:
  no_proprietary_documents: true
  authored_against:
    - aiadra-mechanical/tests/test_chamfer_feature.py
    - ADR/0038-persistent-feature-reference-identity.md
  actor: human
  aiadra_core_version: "0.13.0"
  aiadra_mechanical_adapter_schema_version: "0.1.4"
retrieval_tags: [trace, negative, repair, chamfer, edge-reference, mechanical]
---

# Trace: a chamfer reference goes stale, then is repaired

Same lesson as the fillet, on the chamfer twin: an invalid/unsupported edge
reference fails **loud**; the recovery is to **re-pick**. Mirrors
`test_stale_reference_fails_loud_on_topology_change` + `test_non_sharp_edge_rejected`
and the happy-path repair.

## Step 1 — a topology edit invalidates the reference (FAIL, loud)

```text
setup: box (feat_0001 sketch + feat_0002 extrude) + chamfer feat_0003 on a sharp
       vertical edge, signature recorded against [sketch, extrude].
edit:  add a circle primitive to feat_0001's sketch  (a TOPOLOGY-skeleton change)
evaluate ->
  TransactionError: mechanical: chamfer 'feat_0003' target edge is STALE — the
  parent topology skeleton changed since it was authored (...). A parameter edit
  preserves the reference; a topology edit requires re-picking.
```

No commit. (Contrast: a `distance_mm` or `depth_mm` edit is fine — it preserves
the skeleton.)

## Step 2 — repair by re-picking (PASS)

```text
1. (read) mechanical.display_representation P-000001   # the topology changed
2. mechanical.remove_feature  feature_ids=[feat_0003]  # drop the stale chamfer
3. mechanical.add_chamfer_feature  target_edge_id=<freshly picked sharp edge>  distance=2 mm
4. validate -> commit
```

## A second failure shape — wrong target kind (FAIL, Class-1, before staging)

```text
mechanical.add_chamfer_feature  target_edge_id=<a seam edge of a hole> ...
  -> TransactionError: v1 bevels a SHARP edge only; target '…~seam' is kind
     'seam' (tangent / seam / boundary / free are not supported). Pick a sharp
     model edge.
```

## Lesson for an authoring agent

A stale or unsupported reference is a **repair prompt**, not a transient failure
to retry. Read the current display, re-pick a sharp edge against the new
topology, re-author. Never fabricate `adjacent_face_roles` — a reference that
resolves to zero or many edges fails loud by design (ADR/0038 D4).
