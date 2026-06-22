---
source_context:
  no_proprietary_documents: true
  authored_against:
    - aiadra-mechanical/tests/test_hole_feature.py
    - ADR/0038-persistent-feature-reference-identity.md
  actor: human
  aiadra_core_version: "0.13.0"
  aiadra_mechanical_adapter_schema_version: "0.1.3"
retrieval_tags: [trace, negative, repair, hole, face-reference, mechanical]
---

# Trace: a hole face reference goes stale, then is repaired

The lesson for an authoring agent: an invalid face reference fails **loud**, and
the recovery is to **re-pick** the face — not to retry or coerce. Mirrors
`test_stale_face_reference_fails_loud_on_topology_change` +
`test_missing_face_role_fails_loud` and the happy-path repair.

## Setup

A box (`feat_0001` sketch + `feat_0002` extrude) with a hole `feat_0003` on the
`cap_top` face, whose `target_face.resolved_against_topology_signature` was
recorded against the parent prefix `[sketch, extrude]`.

## Step 1 — a topology edit invalidates the reference (FAIL, loud)

```text
edit: add a circle primitive to feat_0001's sketch  (a TOPOLOGY-skeleton change)
evaluate ->
  TransactionError: mechanical: hole 'feat_0003' target face is STALE — the
  parent topology skeleton changed since it was authored
  (resolved_against=topo_AAA…, current=topo_BBB…). A parameter edit preserves the
  reference; a topology edit requires re-picking.
```

No commit. The engine refuses to guess which face the hole now means.

### Contrast — what does NOT fail

A *parameter* edit (the extrude `depth_mm`, the sketch width, or the hole's own
`diameter_mm` / centre) is fine: the skeleton is unchanged, `cap_top` still
resolves, the hole recomputes. Resizing/moving the hole within the same cap is a
parameter edit, not a topology change (ADR/0038 A2).

## Step 2 — repair by re-picking the face (PASS)

```text
1. (read) mechanical.display_representation P-000001   # the topology changed
       -> inspect the current faces; pick the intended cap face id
2. mechanical.remove_feature  feature_ids=[feat_0003]  # drop the stale hole
3. mechanical.add_hole_feature  target_face_id=<freshly picked cap>
                                diameter=4 mm  centre=(11.5, 5.5)
4. validate -> commit   # OK: the new reference resolves to exactly one face
```

## A second failure shape — wrong target kind (FAIL, Class-1, before staging)

```text
mechanical.add_hole_feature  target_face_id=<a wall face> ...
  -> TransactionError: v1 places a hole on a cap face only (cap_top / cap_base);
     target '…:face:wall_x_max' is not a cap. Pick a cap face.
```

## Lesson for an authoring agent

- A stale or unsupported reference is a **repair prompt**, not a transient
  failure to retry. Read the current display, re-pick against the *new*
  topology, re-author.
- Never fabricate or mutate `target_face.face_role` to force a match — a
  reference that resolves to zero or many faces fails loud by design (ADR/0038
  D4). The unsupported-operation refusal is what makes the platform trustworthy.
