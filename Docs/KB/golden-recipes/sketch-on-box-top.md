---
source_context:
  no_proprietary_documents: true
  authored_against:
    - aiadra-mechanical/tests/test_face_frame.py
  actor: human
  aiadra_core_version: "0.15.0"
  aiadra_mechanical_adapter_schema_version: "0.1.10"
retrieval_tags: [mechanical, golden, sketch, face-plane, box]
---

# Golden: a sketch on the box's top face

The `test_face_frame.py` fixture, verbatim: a 30×20×10 box (rectangle sketch
on principal xy + extrude `feat_0002`), then a face-bound sketch on
`feat_0002:face:cap_top`.

- Stored binding: `{"kind": "face", "face_role": "feat_0002:face:cap_top",
  "resolved_against_topology_signature": <the box-prefix signature>}` with
  `depends_on_feature_ids: ["feat_0002"]`.
- Resolved frame: `normal (0,0,1)`, `u (1,0,0)`, `v (0,1,0)`,
  `origin_mm (0,0,10)`. A depth edit to 20 moves `origin_mm` to `(0,0,20)`
  with identical axes — the sketch rides its cap
  (`test_face_bound_frame_rides_a_depth_edit…`).
- Display v1.2: `surface_kind: "plane"` on both caps and all four walls
  (a box is all-planar); `sketch_frames` carries `feat_0003`'s frame
  (`test_v12_fields_survive_the_real_core_chain`).
