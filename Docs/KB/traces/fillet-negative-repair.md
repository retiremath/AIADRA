---
source_context:
  no_proprietary_documents: true
  authored_against:
    - aiadra-mechanical/tests/test_fillet_feature.py
    - ADR/0038-persistent-feature-reference-identity.md
  actor: human
  aiadra_core_version: "0.13.0"
  aiadra_mechanical_adapter_schema_version: "0.1.2"
retrieval_tags: [trace, negative, repair, fillet, mechanical, regeneration]
---

# Trace: fillet reference goes stale, then is repaired

The trace an AI authoring agent should learn from: an invalid/unsupported edge
reference fails **loud**, and the correct recovery is to **re-pick** the edge —
not to retry blindly or coerce. Mirrors
`test_stale_reference_fails_loud_on_topology_change` +
`test_missing_role_reference_fails_loud` and the happy-path repair.

## Setup

A box (`feat_0001` sketch + `feat_0002` extrude) with a fillet `feat_0003` on a
vertical wall–wall edge, whose `target_edge.resolved_against_topology_signature`
was recorded against the parent prefix `[sketch, extrude]`.

## Step 1 — a topology edit invalidates the reference (FAIL, loud)

```text
edit: add a circle primitive to feat_0001's sketch  (a TOPOLOGY-skeleton change)
evaluate ->
  TransactionError: mechanical: fillet 'feat_0003' target edge is STALE — the
  parent topology skeleton changed since it was authored
  (resolved_against=topo_AAA…, current=topo_BBB…). A parameter edit preserves
  the reference; a topology edit requires re-picking the edge.
```

The engine refuses to guess which edge the fillet now means. **No commit.** This
is the deterministic-first contract (ADR/0038 D4), not a bug.

### Contrast — what does NOT fail

A *parameter* edit (e.g. `feat_0002.depth_mm` 6 → 10) is fine: the topology
skeleton is unchanged, the recipe-anchored role pair still resolves, the fillet
recomputes automatically. Survival vs. failure is decided entirely by whether the
parent-prefix `topology_signature` changed.

## Step 2 — repair by re-picking the edge (PASS)

```text
1. (read) mechanical.display_representation P-000001   # now a box WITH a hole
       -> inspect the current edge set; pick the intended sharp wall-wall edge id
2. mechanical.remove_feature  feature_ids=[feat_0003]  # drop the stale fillet
3. mechanical.add_fillet_feature  target_edge_id=<freshly picked id>  radius=2 mm
4. validate -> commit   # OK: the new reference resolves to exactly one edge
```

## Lesson for an authoring agent

- A stale-reference error is a **repair prompt**, not a transient failure to
  retry. Read the current display, re-pick against the *new* topology, re-author.
- Never fabricate or mutate `adjacent_face_roles` to force a match — a reference
  that resolves to zero or many edges fails loud by design (ADR/0038 D4). The
  unsupported-operation refusal is a feature of the platform's trustworthiness.
