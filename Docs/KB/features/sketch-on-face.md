---
source_context:
  no_proprietary_documents: true
  authored_against:
    - Docs/ADR/0044-sketcher-paradigm.md
    - Docs/ADR/0038-persistent-feature-reference-identity.md
    - aiadra-mechanical/src/aiadra_mechanical/face_frame.py
    - aiadra-mechanical/src/aiadra_mechanical/recipe.py
    - aiadra-mechanical/tests/test_face_frame.py
  actor: human
  aiadra_core_version: "0.15.0"
  aiadra_mechanical_adapter_schema_version: "0.1.10"
retrieval_tags: [mechanical, sketch, face-plane, binding, frame, regeneration, display-v1.2]
---

# Feature: sketch on a planar face (the face-plane binding)

**Operation:** `mechanical.add_sketch_feature` with
`plane: {kind: 'face', target_face_id: <display face id>}` (SK-C1.0 S2,
arc 20260716-2). A sketch may lie on any **planar** face of the Part's solid,
not only a principal datum plane.

## What it does

The caller names a display face id (input vocabulary only — ADR/0038). The
handler resolves it against a **fresh extraction** of the current recipe
prefix and stores the engine-owned reference:

```json
{"kind": "face",
 "face_role": "feat_0002:face:cap_top",
 "resolved_against_topology_signature": "topo_…"}
```

The producing feature (the role's prefix) is recorded in
`depends_on_feature_ids` — the canonical cascade edge.

## The resolved frame (deterministic, edit-stable)

At every evaluation the fold resolves the binding through
`face_frame.resolve_face_plane` (the OCCT-aware layer): outward normal =
adapted plane normal, flipped when `TopAbs_REVERSED`; `u_axis` = the first
global axis X→Y→Z whose in-plane projection exceeds `1e-6`, normalized;
`v = normal × u`; `origin_mm` = the world origin projected onto the face
plane. A depth edit that moves the face moves the sketch WITH it (plane-local
coordinates are invariant). The topology signature hashes only the binding
SKELETON (kind + role + resolved-against) — never the derived frame.

## Refusals (three distinct recovery paths)

- **not planar** — a cylinder wall etc.: pick a flat face or a datum plane.
- **stale selection** — the role no longer exists: re-pick the plane.
- **parent topology changed** — the stored prefix signature mismatches:
  re-pick against the current shape.

A face-bound sketch cannot be the ONE base feature's profile (its support
would not exist before the base) — sequential features are a later arc.

## Display (contract v1.2)

Faces carry `surface_kind: 'plane'|'other'` (the pick filter's planarity
authority; absent = unknown = fail closed) and the package carries
`sketch_frames[]` — the resolved frames of face-bound sketches, joined by
sketch feature id (derived display data, never Truth).
