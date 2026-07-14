---
source_context:
  no_proprietary_documents: true
  authored_against:
    - aiadra-mechanical/tests/test_sketch_plane_matrix.py
    - ADR/0037-modeling-paradigm-benchmark-and-knowledge-architecture.md
  actor: human
  aiadra_core_version: "0.14.0"
  aiadra_mechanical_adapter_schema_version: "0.1.7"
retrieval_tags: [trace, negative, repair, sketch, plane, direction, resolution, mechanical, domain-guard]
---

# Trace: sketch-plane and direction guards, then repaired

Plane binding adds three guard families. Each fails **loud before OCCT**, at
write time AND on regeneration; the repair is always to fix the recipe, never
to retry. Mirrors `test_sketch_plane_matrix.py`'s negatives.

## Failure 1 — a reserved/unknown plane kind (FAIL, Class-1)

```text
mechanical.add_sketch_feature  plane={kind: datum, orientation: xy}
  -> TransactionError: plane kind 'datum' is RESERVED — datum-plane and offset
     bindings arrive in a later slice; v1 supports kind 'principal'
```

**Repair:** bind to a principal plane (`xy`/`yz`/`zx`). The reserved kinds are
schema future-proofing, not hidden features — extra keys (e.g. `offset_mm`)
are rejected the same way.

## Failure 2 — legacy `z±` off the xy plane (FAIL, Class-1, write AND regen)

```text
mechanical.add_extrude_feature  sketch=<yz-plane sketch>  direction=z+
  -> TransactionError: legacy direction 'z+' is only valid on the principal xy
     plane; this sketch is on 'yz' — use 'normal+'/'normal-'
```

**Repair:** use the canonical `normal+`/`normal-` (the sweep sign along the
sketch plane's normal). Legacy `z±` survives only where it is unambiguous
(principal xy) and is never rewritten on disk.

## Failure 3 — a bad consumed-sketch reference (FAIL, Class-1)

```text
mechanical.add_extrude_feature  sketch_feature_id=feat_0009  (not in the recipe)
  -> TransactionError: consumed sketch 'feat_0009' not found in the recipe
```

Variants fail with the exact violation named: the id resolves to a non-sketch;
the sketch appears AFTER its consumer; `depends_on_feature_ids` disagrees with
the payload; the id is duplicated. **Repair:** name a real, preceding, unique
sketch and keep the declared dependency in agreement.

## Lesson for an authoring agent

The plane is structural: pick it when the sketch is created; changing it later
is a topology edit that invalidates dependent references (the signature says
so). Directions are plane-relative (`normal±`) — never global-axis claims.
