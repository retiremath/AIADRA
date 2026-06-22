---
source_context:                       # ADR/0037 D7 provenance attestation
  no_proprietary_documents: true      # ADR/0037 D3 rule 1 — original-content firewall
  authored_against:
    - ADR/0038-persistent-feature-reference-identity.md     # incl. the A1–A3 amendment
    - aiadra-mechanical/src/aiadra_mechanical/handlers.py
    - aiadra-mechanical/src/aiadra_mechanical/geometry.py
    - aiadra-mechanical/src/aiadra_mechanical/topology.py
    - aiadra-mechanical/tests/test_hole_feature.py
  actor: human                        # Claude (lead); reviewed as original expression
  aiadra_core_version: "0.13.0"
  aiadra_mechanical_adapter_schema_version: "0.1.3"
retrieval_tags: [mechanical, feature, hole, face-reference, regeneration]
---

# Feature: hole (as a feature)

**Operation:** `mechanical.add_hole_feature` · **First FACE reference**
(ADR/0037 D8; ADR/0038 A1). A hole-as-feature references a planar **cap face** of
the already-built solid and cuts a circular through-hole into it.

## What it is — and what it is NOT

This is **not** a circle in the base sketch (that hole is part of the sketch
profile, cut at extrude time). Hole-as-feature is a distinct, later feature that
*references existing topology* (a cap face) and modifies the solid downstream —
which is exactly why it exercises the face-reference path of ADR/0038.

## Parameters

| Parameter | Where | Type | Notes |
|---|---|---|---|
| `diameter_mm` | `feature.parameters[]` | number, `unit: "mm"` | Hole diameter (positive). |
| `center_x_mm` | `feature.parameters[]` | number, `unit: "mm"` | Hole centre, **sketch-plane X** (absolute, the same frame as the sketch). |
| `center_y_mm` | `feature.parameters[]` | number, `unit: "mm"` | Hole centre, **sketch-plane Y**. |

Placement is in the **sketch coordinate frame**, not the OCCT face frame — so it
is stable under any parent dimension edit (the face's incidental plane origin
moves under a width edit; the sketch frame does not).

## The target-face reference (ADR/0038 A1)

The hole persists, in `feature.adapter_payload.target_face`, an **engine-owned,
recipe-anchored** reference — never the read-side display `face_id`:

```json
"target_face": {
  "face_role": "feat_0002:face:cap_top",
  "resolved_against_topology_signature": "topo_xxxxxxxxxxxxxxxx"
}
```

The display `face_id` a UI pick supplies is only an **input selector**; the
handler resolves it against a fresh extraction and persists the structured anchor
read from *that* extraction.

## Truth-Model footprint

- A `feature` record (`feature_type: "hole"`), `depends_on_feature_ids: [<parent
  extrude id>]`.
- The Part's `authoring_geometry` `geometry_ref` extends `derived_from_feature_ids`
  to include the hole; identity stays the recipe hash (`vault_ref`).
- Display: a `feat_N:face:hole_wall` face role (cylinder, by construction —
  ADR/0038 A3) + the hole's circular rim edges.

## Invariants (v1 scope)

- One selected **cap** face (`cap_top` / `cap_base`); a non-cap/non-planar target
  fails Class-1 (the face analog of the fillet's sharp-edge guard).
- One circular **through**-hole; **simple cap only** — a cap that already carries
  a cutout (a sketch hole or a prior hole feature) is unsupported in v1.
- The footprint must fit entirely inside the cap (Class-1, before the kernel).
- Deferred to v2: counterbore / countersink / tapped / blind holes, non-cap
  planar faces (which need a face-local frame), patterns, heuristic reattachment.

## The paradigm lesson — values vs. skeleton, and faces vs. edges

- **Moving or resizing the hole within the same face is a parameter edit**
  (ADR/0038 A2): `diameter_mm` / `center_x_mm` / `center_y_mm` are *value*
  parameters — excluded from the topology skeleton, exactly like a sketch
  circle's radius or an extrude's depth. The generated `hole_wall` role stays
  stable; a downstream feature referencing it does **not** go stale because the
  diameter changed. **Retargeting** (a different `target_face`) **is** a
  skeleton change. But "parameter edit" still means **within domain**: an edit
  that pushes the footprint outside the cap fails Class-1 ("must fit entirely
  inside") on *every* path — the initial add AND a later parameter edit /
  regeneration — never a side-breaching cut.
- **A parameter edit survives; a topology edit fails loud** — the same rule as
  the fillet, now proven on a *face* reference: the hole re-resolves `cap_top`
  across a depth/width edit, but a skeleton change (a new sketch primitive, a
  removed parent) fails before commit and asks for the face to be re-picked.

## Failure modes

| Cause | Class | Result |
|---|---|---|
| `diameter_mm` ≤ 0 / missing | Class-1 domain | `TransactionError` before the kernel |
| `target_face_id` not on the part | Class-1 domain | `TransactionError` "not found" |
| Target is not a cap (a wall / non-planar) | Class-1 domain | `TransactionError` "cap face only" |
| Cap already has a cutout (sketch hole / prior hole) | Class-1 domain | `TransactionError` "simple cap only" |
| Footprint exceeds the cap boundary (on add OR a later edit) | Class-1 domain | `TransactionError` "must fit entirely inside" — enforced on every regeneration path |
| Parent topology skeleton changed | Class-1 domain | `TransactionError` "STALE — re-pick the face" |
| Face role absent (missing / topology change) | Class-1 domain | `TransactionError` "resolves to NO face" |
| Removing the parent solid while the hole remains | core fold | `FoldInconsistencyError` (ADR/0029 D12 cascade) |

## See also

- [ADR/0038](../../ADR/0038-persistent-feature-reference-identity.md) — A1 `target_face`, A2 values-not-skeleton, A3 mandatory produced-face claim.
- [features/fillet.md](fillet.md) — the first (edge) reference.
- [golden-recipes/hole-box.md](../golden-recipes/hole-box.md) · [traces/hole-negative-repair.md](../traces/hole-negative-repair.md)
