---
source_context:
  no_proprietary_documents: true
  authored_against:
    - aiadra-mechanical/tests/test_face_frame.py
    - aiadra-studio/src/sketch/sketchWireOverlay.ts
    - aiadra-studio/src/authoring/inspectDecode.test.ts
  actor: human
  aiadra_core_version: "0.15.0"
  aiadra_mechanical_adapter_schema_version: "0.1.10"
retrieval_tags: [mechanical, trace, negative, repair, sketch, face-plane]
---

# Trace: face-plane refusals and their repairs

1. **Attempt:** bind a sketch to a cylinder's `outer_wall`.
   **Refusal:** `…is NOT PLANAR — a sketch lies on a flat face…`
   **Repair:** pick a planar face (a cap) or a principal datum plane. Only
   faces the engine classifies exactly `plane` are eligible — cones, spheres,
   tori, and unknown surfaces classify `other` and refuse (never fail open).
2. **Attempt:** regenerate after the parent's topology skeleton changed
   (stored signature ≠ current).
   **Refusal:** `…face binding is STALE — the parent topology skeleton
   changed… Re-pick the sketch plane.`
   **Repair:** re-pick the support on the current shape; the new binding
   captures the fresh prefix signature.
3. **Fact (v1 boundary, not a reachable workflow):** the one-base model
   CANNOT form a valid face-bound base profile — the support face's producer
   must precede the sketch, but the only base IS the producer and must
   consume a sketch that precedes it. Every ordering refuses EARLIER with
   its own typed error (`consumed sketch … not found in the recipe`, or the
   binding's stale/missing refusal); the `base profile cannot lie on a face`
   guard is defence-in-depth retained for the sequential-extrude arc.
   **Current S2 behavior, stated exactly:** a face-bound sketch CAN be
   engine-committed (it validates at its fold position on every
   regeneration), but its viewport WIRE is intentionally unavailable until
   S3's validated `sketch_frames` overlay join lands — the Studio overlay
   skips non-principal sketches rather than render them on a guessed plane
   (`sketchWireOverlay.ts`), and there is no face-pick UI yet. Do not expect
   visible face-sketch geometry in S2.
