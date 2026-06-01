# ADR/0029 — Part authoring Schema Change Note

## Frontmatter

- **Status:** Accepted — 2026-05-31 (arc 20260531-13; four-round convergence Claude1 + Codex1 / Claude2 + Codex2 / Claude3 + Codex3 / Claude4 + Codex4 — R4 doc-only cleanup + N2 polish per Codex3 B1).
- **Operationalizes:** [ADR/0027 D17](0027-aiad-positioning-and-native-engine-posture.md) + [ADR/0028 D14 step 2](0028-native-engine-implementation-contract.md) — Part authoring SCN pre-condition for `aiadra-mechanical` Wedge-003 implementation.
- **Bundle bump:** v0.27.0 → v0.28.0 MINOR additive. Digest `sha256:3ad042ab703a7856ae30fda0b6cc3b06a248ac5da102cf5dcc061432a5e41659` (R4 re-pin after tightening `_shared/geometry_ref_record.schema.json` `fact_provenance.derived_from` description from coverage to STRICT set-equality per Codex3 B1; previous values: R2 `sha256:d65f0cba…`, R3 `sha256:866489ae…`).
- **`aiadra-core` bump:** 0.9.0 → 0.10.0 MINOR additive (fold handler addition + schema bundle additions; matches arc 3 / arc 4 / arc 5 SCN precedent). **This renumbers [ADR/0028 D14 step 3](0028-native-engine-implementation-contract.md) from "0.9.0 → 0.10.0 API additions arc" to "0.10.0 → 0.11.0 API additions arc"** — the work in that arc is unchanged; only the version numbers shift.
- **Sequencing per ADR/0027 D10 + ADR/0028 D14 (renumbered):** (1) ADR/0028 ✓; (2) **this ADR ✓**; (3) `aiadra-core 0.10.0 → 0.11.0` arc — implements ADR/0028 API additions (`NativeEngineRegistrar` + `NativeEngineContext` + `EngineNotAvailableError` + `NativeEngineKernelError` + `NativeEngineRegistrationError` + D16 generalization + entry-point discovery + dispatch lookup + `refresh_native_engines`); (4) Wedge-003 scope ADR; (5) `aiadra-mechanical` ecosystem-package implementation.

## §0 — What this SCN does

Adds the schema surface required for AIADRA-native mechanical Part authoring. Specifically:

1. **Schema-bakes the `feature` + `geometry_ref` namespaces** in the v0.28.0 Part Object schema (which v0.27.0 had only `object` + `parameter` + `relationship` namespaces, despite [ADR/0005 §3](0005-object-type-part.md) pinning 7 namespaces conceptually).
2. **Adds the `part_changed` event** carrying `feature_delta` + `geometry_ref_delta` payload sections with FULL add/update/remove delta semantics.
3. **Adds three shared schemas** in `_shared/`: `feature_record.schema.json` + `geometry_ref_record.schema.json` + `canonical_unit.schema.json`.
4. **Extends fold + proposed-state fold** in `aiadra-core` with `_apply_part_changed` enforcing atomic delta rules + DAG acyclicity + cascade integrity + provenance discipline cross-check.
5. **Adds MigrationStep v0.27.0 → v0.28.0** to the registered chain.

What this SCN does NOT do:
- Add any new `TransactionKind` enum members — Native Engine handlers in `aiadra-mechanical` will emit `part_changed` using namespaced operation kinds (`mechanical.add_feature` / `mechanical.adjust_feature_parameter` / etc.) via [ADR/0028 D16](0028-native-engine-implementation-contract.md) `TransactionDraft.kind: str` generalization (which lands in the next arc).
- Add any Native Engine handler implementations — those land in `aiadra-mechanical` per [ADR/0028 D11](0028-native-engine-implementation-contract.md) ecosystem-package boundary.
- Add `NativeEngineRegistrar` / `NativeEngineContext` / `EngineNotAvailableError` / etc. — separate arc per the (renumbered) [ADR/0028 D14 step 3](0028-native-engine-implementation-contract.md).
- Retrofit existing parameter schemas to use `_shared/canonical_unit.schema.json` — introduce-only this arc per Codex1 N4 + Q4.
- Schema-bake sketch primitives (kept opaque in `adapter_payload`) — premature lock-in per ADR/0029 D7.
- Add quaternion fields at first-class schema level — deferred per ADR/0029 D11; quaternions stay in opaque `adapter_payload` for v0.28.0.

## Decisions

### D1. Bundle v0.27.0 → v0.28.0 MINOR additive

Per [ADR/0028 D14 step 2](0028-native-engine-implementation-contract.md) + [ADR/0003](0003-schema-governance.md) schema bundle versioning. MINOR because:
- ADD `event/part_changed.schema.json`.
- ADD `_shared/feature_record.schema.json` + `_shared/geometry_ref_record.schema.json` + `_shared/canonical_unit.schema.json`.
- EXTEND `object/part.schema.json` with OPTIONAL `feature` + `geometry_ref` array namespaces (existing v0.27.0 Parts that don't have these continue to validate against v0.28.0 — confirmed by `test_adr_0029_part_sidecar_works_without_feature_namespace`).
- ADD `lookups.event.part_changed` to `_index.json`.
- ADD `MigrationStep("0.27.0", "0.28.0", ...)` to `REGISTERED_STEPS`.
- ADD `0.28.0` to the CLI `migrate --to-bundle` help text.
- Digest pinned at `sha256:3ad042ab703a7856ae30fda0b6cc3b06a248ac5da102cf5dcc061432a5e41659` per the frontmatter (R4 re-pin after Codex3 B1 absorption tightened the `_shared/geometry_ref_record.schema.json` description for `fact_provenance.derived_from`; R2 was `sha256:d65f0cba…`, R3 was `sha256:866489ae…`).

### D2. Part Object schema gains `feature` + `geometry_ref` namespaces (B2 absorption — keys without colons)

Per [ADR/0005 §3](0005-object-type-part.md), Part has 7 conceptual namespaces; v0.27.0 had only 2 schema-baked. v0.28.0 adds 2 more.

**Codex1 B2 absorption**: serialized JSON keys are `feature` + `geometry_ref` — NOT `feature:` / `geometry_ref:`. The colon form is ADDRESS notation (used in `fact_provenance.derived_from` entries as `feature:<feat_id>`), not the serialized JSON property name. Conflating the two would diverge from every existing namespace (`parameter`, `relationship`, `attachment`, `acceptance_criterion`, etc.). Documented in the schema descriptions explicitly.

Both namespaces are OPTIONAL on a Part sidecar. A Part with only parameters + no features remains valid (matches the v0.27.0 minimum). `design_intent` / `material` / `published_ref` namespaces stay deferred to future per-namespace SCNs.

### D3. `part_changed` event with full add/update/remove delta semantics (B1 + B3 absorption)

**Codex1 B1 absorption — event envelope**: uses `event/_base.schema.json` (`schema_version` / `event_id` / `event_type` / `timestamp` / `transaction_id` / `actor` / `payload`). `event_type` = const `"part_changed"`. `actor` narrowed to enum `["agent", "human"]` at the part_changed level (D8 provenance discipline depends on it). `object_uuid` + `feature_delta` + `geometry_ref_delta` live under `payload` per the existing `parameter_changed` / `requirement_changed` precedent.

**Full add/update/remove (NOT added-only)**: ADR/0027 D17 verbatim scope pinned "feature_delta (add / remove / update feature records) + geometry_ref_delta (add / remove / replace geometry_ref records with their associated `vault_ref` content hashes)". The `requirement_changed` added-only precedent from arc 5 doesn't apply (acceptance criteria are append-mostly in typical R&D; Part features are routinely updated and removed during design). The drawing/test/evidence/test_execution `_apply_attachment_delta` precedent from Phase 1 W2 (arc 20260531-2) is the correct model.

**Codex1 B3 absorption — atomic delta conflict rules** (enforced by `_apply_feature_delta` + `_apply_geometry_ref_delta` per namespace):
1. **No intra-array duplicate ids** — duplicate within a single `added[]` / `updated[]` / `removed[]` raises `FoldInconsistencyError`.
2. **No cross-array overlap** — same id MUST NOT appear in more than one of `added` / `updated` / `removed` for the same namespace.
3. **`added[].id` MUST NOT pre-exist** — collisions with existing sidecar ids raise.
4. **`updated[].id` and `removed[]` entries MUST exist** — missing ids raise.
5. **`updated[].new_record.id` MUST equal `updated[].id`** — wrapper consistency.
6. **Apply the full event atomically** — removes first, then updates, then adds, then post-condition checks (DAG acyclicity per D9; cascade integrity per D12; provenance discipline per D6).

`anyOf [{required: ["feature_delta"]}, {required: ["geometry_ref_delta"]}]` at payload level forbids ghost events with no delta section.

### D4. `_shared/feature_record.schema.json` — canonical feature record shape

```jsonc
{
  "id": "feat_NNNN",                            // list-addressable per S0 commitment 7
  "name": "<string>",
  "feature_type": "<engine-declared string>",   // D8: free string, NOT bounded enum
  "depends_on_feature_ids": ["feat_NNNN", ...], // B6: multi-parent DAG (D9 acyclicity)
  "parameters": [{                              // OPTIONAL; numeric-only per N3
    "id": "featp_NNNN",
    "name": "<string>",
    "value": <number>,
    "datatype": "number",
    "unit": "<canonical_unit enum>"             // D10: canonical-unit-enum-required
  }],
  "adapter_payload": {<engine-opaque>},         // D7: opaque; engine validates
  "engine": "<discriminator>",                  // ADR/0005 §9 + ADR/0027 D18
  "adapter_schema_version": "<x.y.z>",
  "engine_artifact_ref": "sha256:<hex>",        // OPTIONAL
  "stable_engine_object_id": "<string>",        // OPTIONAL
  "status": "active|suppressed",                // OPTIONAL; absence == active (Codex1 N1)
  "fact_provenance": {
    "category": "ai_proposal|human_input"       // D6: actor-derived; computed_result REJECTED
  },
  "fact_uncertainty": "verified|requires_validation|computed|estimated"
}
```

Notes:
- `feat_NNNN` id pattern (4 digits, engine-allocated) matches the attachment/acceptance_criterion pattern; differs from parameter's free-form `param_[a-z0-9_]+$` pattern.
- `depends_on_feature_ids` is the DAG dependency graph per B6 absorption — REPLACES Claude1's `parent_feature_id` (which only supported single-parent tree structure inadequate for mechanical features that often depend on multiple prior features).
- `parameters` are numeric-only per Codex1 N3 — future MINOR SCN can extend `datatype` enum when a load-bearing case surfaces.
- `adapter_payload` is engine-opaque per D7 — sketch primitives and similar kernel-specific data live here; aiadra-core schema-validates only that it IS an object.
- `engine` + `adapter_schema_version` REQUIRED per [ADR/0005 §9](0005-object-type-part.md) + [ADR/0027 D18](0027-aiad-positioning-and-native-engine-posture.md) wire-name preservation.
- `status` per Codex1 N1: absence interpreted as `active` by fold semantics; no JSON Schema `default` annotation (defaults don't write into sidecars).
- `fact_provenance.category` enum closed to `["ai_proposal", "human_input"]` at the schema level (`computed_result` and `measured` schema-rejected on feature records; defense-in-depth for D6 fold-time enforcement).

### D5. `_shared/geometry_ref_record.schema.json` — reconciled with ADR/0005 D7 + D9 (B5 absorption)

**Codex1 B5 absorption**: keep [ADR/0005 D7](0005-object-type-part.md) `role` enum + REQUIRED `vault_ref`; keep `engine_artifact_ref` as OPTIONAL adapter-shell field per [ADR/0005 D9](0005-object-type-part.md) (wrapped under `adapter_ref` object). Claude1 had replaced `vault_ref` with a flat `engine_artifact_ref` — that silently superseded D7's canonical Vault anchor without justification; the fix preserves D7 verbatim per ADR/0027 D18 wire-name preservation.

```jsonc
{
  "id": "geom_NNNN",
  "role": "authoring_geometry|derived_export",  // ADR/0005 D7
  "vault_ref": "sha256:<hex>",                  // REQUIRED canonical Vault anchor per ADR/0005 D7
  "kind": "solid|surface|wireframe|mesh|point_cloud",  // OPTIONAL semantic discriminator
  "derived_from": ["geom_NNNN", ...],           // REQUIRED if role=derived_export (geom-to-geom lineage per ADR/0005 D7)
  "derived_from_feature_ids": ["feat_NNNN", ...],  // REQUIRED if role=authoring_geometry (feature-to-geometry computation lineage)
  "adapter_ref": {                              // OPTIONAL adapter shell per ADR/0005 D9 + ADR/0027 D18
    "engine": "<discriminator>",
    "adapter_schema_version": "<x.y.z>",
    "engine_artifact_ref": "sha256:<hex>",      // OPTIONAL: distinct engine artifact (e.g., FreeCAD .FCStd)
    "stable_engine_object_id": "<string>"
  },
  "bounding_box_mm": {                          // OPTIONAL cached AABB per D10
    "x_min_mm": <number>, "y_min_mm": <number>, "z_min_mm": <number>,
    "x_max_mm": <number>, "y_max_mm": <number>, "z_max_mm": <number>
  },
  "fact_provenance": {
    "category": "computed_result",              // D6: closed enum to computed_result only at geometry_ref
    "derived_from": ["feature:<feat_id>", ...]  // REQUIRED non-empty per ADR/0028 D8
  },
  "fact_uncertainty": "..."
}
```

Conditional schema rules (via `allOf [{if/then}, {if/then}, ...]`):
- `role == "derived_export"` ⇒ `derived_from` REQUIRED (geom-to-geom lineage per ADR/0005 D7).
- `role == "authoring_geometry"` ⇒ `derived_from_feature_ids` REQUIRED (feature-to-geometry lineage for D6 provenance trace).
- `fact_provenance.derived_from` REQUIRED non-empty (ADR/0028 D8 — `computed_result` records MUST trace inputs).

### D6. Provenance discipline enforced at fold + schema (B4 + Codex2 B1 + B2 absorption)

Per [ADR/0028 D8](0028-native-engine-implementation-contract.md) caller-supplied vs engine-computed split. The fold handler enforces:

**Codex2 B1 absorption — `actor` REQUIRED at event root**: `event/part_changed.schema.json` has `required: ["actor"]` at the schema root (in addition to the base envelope's required fields). The fold uses direct `event["actor"]` access — NOT `event.get("actor", "agent")` — so a missing-actor event is schema-rejected, NOT silently interpreted as `"agent"`. Without this rule, a malformed event could manufacture provenance context, bypassing exactly the boundary D6 is meant to protect.

**Feature records (caller-supplied design intent)**:
- `fact_provenance.category == "ai_proposal"` if event's `actor == "agent"`.
- `fact_provenance.category == "human_input"` if event's `actor == "human"`.
- Same self-attestation discipline as built-in `change_parameter` per [arc 20260531-9 Codex1 B4](Discussions/20260531/20260531-9/Codex1.md).
- Schema-level defense-in-depth: `fact_provenance.category` enum at the feature_record level is closed to `["ai_proposal", "human_input"]`.

**Geometry_ref records (engine-computed derivatives)** — per Codex1 B4 + Codex2 B2 absorption:
- `fact_provenance.category == "computed_result"` (schema-enforced).
- `fact_provenance.derived_from` REQUIRED non-empty (schema + conditional `allOf`).
- **Canonical intra-Part address form**: `feature:<feat_id>` (e.g., `feature:feat_0001`) for `authoring_geometry` records; `geometry_ref:<geom_id>` for `derived_export` records.
- **Cross-Object form REJECTED in v0.28.0** (Codex2 B2): `<object_uuid>:feature:<feat_id>` and `<object_uuid>:geometry_ref:<geom_id>` are reserved for a future SCN when cross-Part geometry derivation lands. The fold rejects ANY non-canonical entry (entries not matching `^feature:feat_\d{4}$` or `^geometry_ref:geom_\d{4}$` for the respective role).
- **STRICT set-equality (NOT subset coverage)** between declared inputs and provenance-attested inputs (Codex2 B2):
  - For `authoring_geometry`: the set of feature ids extracted from `fact_provenance.derived_from` (via canonical `feature:<id>` form) MUST EQUAL the set in `derived_from_feature_ids`. Neither under-covering (missing) nor over-attesting (dangling extras) is allowed. The previous Coverage-only rule allowed `fact_provenance.derived_from = ["feature:feat_0001", "feature:feat_9999"]` to pass even though `feat_9999` was a dangling provenance address; the set-equality rule rejects it.
  - For `derived_export`: same agreement pattern applied to `derived_from` (geom-to-geom lineage per ADR/0005 D7) — every intra-Part `geometry_ref:<id>` entry in `fact_provenance.derived_from` MUST equal the `derived_from` set.

This makes the provenance trail self-consistent + tamper-resistant: declared geometric/feature inputs and provenance-attested inputs MUST agree exactly, and only canonical address forms are permitted.

### D7. Sketch primitives + kernel data stay in opaque `adapter_payload`

Sketches are features (one of many `feature_type` values). Sketch primitives (lines, arcs, circles, dimensions, constraints) + other kernel-specific data live INSIDE `feature.adapter_payload` — NOT broken out as first-class schema-baked fields.

Rationale: Sketch primitive shape varies massively between kernels (OCCT vs Solvespace vs SketchUp). Per [ADR/0027 D11](0027-aiad-positioning-and-native-engine-posture.md) + [ADR/0028 D10](0028-native-engine-implementation-contract.md): Native Engine packages do NOT introduce schemas to the canonical bundle on their own. Schema-baking sketch primitives WITHIN this SCN would force every Native Engine that supports sketches to conform to one canonical sketch schema — premature lock-in. `adapter_schema_version` on the feature record pins the format per-engine.

aiadra-core schema-validates only that `adapter_payload` IS a JSON object; the Native Engine validates its structural shape per its own internal schemas.

### D8. `feature_type` is a free string (engine-declared catalog)

Per Codex1 Q2 + ADR/0028 D4 op-kind pattern — engines declare their own catalogs (e.g., `sketch` / `extrude` / `fillet` / `chamfer` / `hole` / `pattern_linear` / `pattern_circular` / `mirror` / `revolve` / `loft` / `sweep` / `shell` / `draft` / `reference_plane` / `reference_axis` / `reference_point` / ...). aiadra-core schema-validates only `string minLength=1`.

Bounded enum was rejected because it would force every Native Engine into one canonical feature-type vocabulary — symmetric to the D7 lock-in concern. Cross-engine readability of `feature_type` is non-critical: a tool inspecting a Part doesn't need to interpret "extrude" semantically; it needs the geometry_ref hash to render the result.

### D9. `depends_on_feature_ids` forms a DAG; fold enforces acyclicity (B6 absorption)

**Codex1 B6 absorption**: Claude1 used `parent_feature_id` (single-parent nullable string) and called the structure a DAG — but a single parent is a TREE, not a DAG. Mechanical features commonly depend on multiple prior features (an extrude depends on a sketch + reference plane; a fillet depends on multiple edges of an extrude). v0.28.0 uses `depends_on_feature_ids: string[]` (multi-parent), with the fold enforcing acyclicity via Kahn's algorithm.

Schema validation: every entry must match `^feat_[0-9]{4}$`. Fold-time validation:
- Every `depends_on_feature_ids[]` entry MUST reference an existing feature on the same Part (no dangling).
- The resulting directed graph MUST be acyclic (Kahn's algorithm; O(V+E) over the Part's feature set).
- Cycles raise `FoldInconsistencyError` naming the cyclic features.

Sidecar `feature` list order is NOT canonical UI order — engines may topologically sort for display, but aiadra-core doesn't enforce list order beyond DAG acyclicity over `depends_on_feature_ids`.

### D10. Canonical units at fact level via `_shared/canonical_unit.schema.json`

Per the SystemState [Coherence Checklist](../SystemState.md#3-coherence-checklist) "Canonical units at fact level" item.

New `_shared/canonical_unit.schema.json` is a closed enum: `["mm", "m", "deg", "rad", "kg", "N", "MPa", "s", "Hz", "K", "dimensionless"]`. Referenced from `feature.parameters[].unit`. Future MINOR SCN can extend the enum.

`geometry_ref.bounding_box_mm` uses field-name-level `_mm` suffix discipline (no unit field needed; schema-enforced canonical via the field name).

NO engine-defined units; NO deferring to "project policy" or "adapter convention" per [ADR/0010 §2](0010-relationship-type-composed-of.md) + [ADR/0011 §2](0011-relationship-type-mated-to.md).

**Retrofit OUT OF SCOPE per Codex1 N4 + Q4**: existing parameter schemas (Object-level `parameter:` namespaces on Part / Requirement / etc.) retain their `unit: string minLength=1` shape. A future retrofit SCN can adopt `canonical_unit.schema.json` across them when a load-bearing case surfaces.

### D11. Quaternion normalization deferred for v0.28.0

Quaternion-bearing transforms (feature placement frames, reference plane orientations) stay inside opaque `adapter_payload` for v0.28.0. When a future SCN exposes explicit transform fields at the first-class schema level, that SCN takes on the [ADR/0010 §2 / ADR/0011 §2](0010-relationship-type-composed-of.md) quaternion-normalization discipline (`|q|² ∈ [1 - 1e-6, 1 + 1e-6]`) via a new `_shared/quaternion.schema.json`.

### D12. Fold + proposed-state fold extensions in `aiadra-core`

`validation/fold.py` gains `_apply_part_changed(state, payload, actor)` + helpers (updated per Codex2 B2 R3 absorption to split the geometry helper by role and apply STRICT set-equality):
- `_apply_feature_delta(sidecar, delta, actor, uuid)` — B3 atomic rules + B4 actor-derived provenance check.
- `_apply_geometry_ref_delta(sidecar, delta, uuid)` — B3 atomic rules; dispatches to role-specific provenance helpers below.
- `_enforce_authoring_geometry_provenance_consistency(rec, uuid)` — Codex2 B2 R3 absorption: STRICT set-equality (NOT subset coverage) between `derived_from_feature_ids` and the intra-Part `feature:<feat_id>` entries in `fact_provenance.derived_from`; rejects cross-Object form `<uuid>:feature:<id>` and any non-canonical form via regex.
- `_enforce_derived_export_provenance_consistency(rec, uuid)` — Codex2 B2 R3 absorption: same STRICT set-equality + canonical-form discipline applied to derived_export records (`derived_from` vs `geometry_ref:<geom_id>` entries in `fact_provenance.derived_from`).
- `_enforce_feature_dependency_acyclicity(sidecar, uuid)` — B6 DAG check via Kahn's algorithm.
- `_enforce_no_dangling_feature_references(sidecar, uuid)` — D12 cascade rule (R3-extended): covers `feature.depends_on_feature_ids`, `authoring_geometry.derived_from_feature_ids`, AND `derived_export.derived_from` against surviving ids.

`transaction/boundary.py::_validate_proposed_fold` adds the mirror `elif et == "part_changed"` branch calling `_apply_part_changed(state, event["payload"], event["actor"])` — direct access per Codex2 B1 R3 absorption (no defaulting to `"agent"` on missing actor; the schema's root-level `required: ["actor"]` ensures actor is always present). Same handler used by read-side fold. This is the dual-fold discipline established by Phase 2 F1 / Phase 4 F2 SCNs ([arc 20260531-3](Discussions/20260531/20260531-3/) + [arc 20260531-5](Discussions/20260531/20260531-5/)).

**Cascade removal** (Codex1 B3 + Codex2 B2 R3 extension): after applying the FULL delta atomically (removes first, updates next, adds last), no surviving record may reference a removed id. Specifically the cascade check enforces:
- `feature.depends_on_feature_ids ⊆ surviving feature ids` (caller batches dependent feature removals).
- `authoring_geometry.derived_from_feature_ids ⊆ surviving feature ids` (caller removes dependent geometry_refs in the same event when removing a feature).
- `derived_export.derived_from ⊆ surviving geometry_ref ids` (caller removes dependent derived_exports in the same event when removing an authoring_geometry).

Engines either batch dependent removals into one event's `removed[]` (accepted) or perform separate Transactions in dependency-correct order. Batched cascade removals work because the rule is "no surviving record may reference a removed id after the entire delta is applied."

### D13. `aiadra-core` version bump 0.9.0 → 0.10.0 (renumbers ADR/0028 D14 step 3)

MINOR additive bump per [arc 3](Discussions/20260531/20260531-3/) F1 / [arc 4](Discussions/20260531/20260531-4/) W3 / [arc 5](Discussions/20260531/20260531-5/) F2 SCN precedent — fold handler additions + schema bundle additions trigger MINOR.

**Sequencing impact on ADR/0028 D14**: step 3 currently named "`aiadra-core 0.9.0 → 0.10.0` arc (small) — implements the API additions ADR/0028 pins" gets renumbered to "**`aiadra-core 0.10.0 → 0.11.0` arc**" once this SCN lands. The scope of that arc is unchanged; only the version numbers shift.

### D14. Explicit out-of-scope (deferred via this SCN)

1. **`TransactionKind` enum additions for Part operations** — Native Engine handlers in `aiadra-mechanical` use namespaced operation kinds like `mechanical.add_feature` / `mechanical.adjust_feature_parameter` via [ADR/0028 D16](0028-native-engine-implementation-contract.md) generalization. aiadra-core adds NO new `TransactionKind` enum members for Part authoring in this SCN.
2. **Native Engine implementation** — `aiadra-mechanical` package ships separately per [ADR/0028 D11](0028-native-engine-implementation-contract.md) ecosystem-package boundary; lives outside this arc + the next arc.
3. **Native Engine API additions in `aiadra-core`** (`NativeEngineRegistrar` / `NativeEngineContext` / etc.) — separate arc per renumbered [ADR/0028 D14 step 3](0028-native-engine-implementation-contract.md).
4. **`design_intent` / `material` / `published_ref` namespaces on Part** — future per-namespace SCNs when authoring need surfaces.
5. **`derived_geometry_from` relationship type** — last unfilled relationship type from [ADR/0009 §3](0009-relationship-type-satisfies.md); awaits Native Engine implementation per [ADR/0027 D11](0027-aiad-positioning-and-native-engine-posture.md). Future SCN venue.
6. **Cross-Part geometry refs** — geometry_ref records here are intra-Part. Cross-Part geometric reference (a Part deriving geometry from another Part's `published_ref`) is the `derived_geometry_from` venue. The cross-Object provenance address form `<object_uuid>:feature:<feat_id>` is RESERVED here for that future SCN; intra-Part `feature:<feat_id>` is the only form used in v0.28.0.
7. **Mate satisfaction interactions** — `mated_to` already requires geometric evaluation at release; this SCN doesn't change that. When geometry_refs become mate endpoints, the existing released_geometric_satisfaction validator extends to use them. Not new logic; future implementation arc.
8. **Sketch primitive schema-baking** — per D7, sketch primitives stay in opaque `adapter_payload`. Future per-engine SCN venue if cross-engine sketch interop becomes load-bearing.
9. **Quaternion fields at first-class schema level** — per D11, deferred to future SCN that exposes explicit transform fields on a specific feature_type.
10. **`bounding_box_mm` computation rules** — schema allows the field; doesn't enforce that engines populate it; doesn't pin recomputation triggers. Future arc per Codex1 N2 (min ≤ max axis check if becomes query-critical).
11. **Datatype extensions on feature parameters** — `datatype: const "number"` per Codex1 N3. Future MINOR SCN can extend the enum when a load-bearing case surfaces.
12. **Canonical unit retrofit across existing parameter schemas** — introduce-only this arc per Codex1 N4 + Q4. Future retrofit SCN can adopt `_shared/canonical_unit.schema.json` across Object-level `parameter:` namespaces.

### D15. Sequencing after this SCN

Per [ADR/0028 D14](0028-native-engine-implementation-contract.md) (renumbered after this SCN's `aiadra-core` bump):
1. **ADR/0028 (landed)** — Native Engine Implementation contract.
2. **This ADR/0029 (landed)** — Part authoring SCN.
3. **`aiadra-core 0.10.0 → 0.11.0` arc** — implements ADR/0028 API additions.
4. **Wedge-003 scope ADR** — smallest viable AIADRA-native mechanical authoring loop per [ADR/0027 D17](0027-aiad-positioning-and-native-engine-posture.md).
5. **`aiadra-mechanical` ecosystem-package implementation** — first concrete Native Engine slice.

Per-engine research arcs (FreeCAD / Solvespace / OpenSCAD / KiCad / Onshape) remain optional parallel work.

### D16. Coherence Checklist walk

| Item | Verdict | Note |
|---|---|---|
| List-addressability | PASS | Every list item (`feature` / `geometry_ref` / `feature.parameters` / `feature.depends_on_feature_ids` / `geometry_ref.derived_from_feature_ids`) carries stable id per S0 commitment 7. |
| Released cross-Object geometry | N/A | This SCN introduces no cross-Object geometric ref shape. `published_ref` deferred per D14 item 4. |
| Engineering-structure cross-project | N/A | No `composed_of` / `mated_to` endpoint policy changes. |
| Binding ownership | N/A | No Float/Fixed binding change. |
| Identity cross-check | N/A | No endpoint `revision_id` cross-check shape change. |
| Released geometric satisfaction | N/A | This SCN doesn't change `mated_to` release validators. Future implementation arc. |
| **Canonical units at fact level** | PASS — LOAD-BEARING | D10 enforces via new `_shared/canonical_unit.schema.json`. Feature parameter units schema-fixed via canonical unit enum. `bounding_box_mm` field-name-level `_mm` suffix. NO engine-deferred units. |
| Quaternion normalization | N/A (deferred per D11) | Quaternions stay in opaque adapter_payload for v0.28.0; future first-class transform SCN takes the discipline. |
| AIADRA Core hosts nothing | PASS | Schema + fold logic only. No service. |
| Execution-record cardinality invariants | N/A | No execution-instance change. |
| **Native engine boundary** | PASS — TIGHTENED | This SCN explicitly KEEPS Native Engine implementation OUT of `aiadra-core`: D7 + D8 keep sketch primitives + feature_type catalog ENGINE-OWNED; D14 items 2 + 3 explicitly defer Native Engine handler + API additions to separate arcs. |

No new Coherence Checklist item proposed.

## Supersession + amendment register

**Partial supersession of [ADR/0005 §3](0005-object-type-part.md)** (Part 7-namespace decision):
- §3 pinned 7 namespaces conceptually; v0.27.0 had only `parameter` + `relationship` schema-baked. v0.28.0 adds `feature` + `geometry_ref` schema-baked per D2. §3's conceptual scope is unchanged; this SCN narrows from "pinned" to "concrete in schema bundle" for 4 of 7. Remaining 3 (`design_intent`, `material`, `published_ref`) stay in pinned-but-not-yet-schema-baked state per D14 item 4.

**Honor without supersession**: [ADR/0005 D7](0005-object-type-part.md) (geometry_ref role enum + REQUIRED vault_ref) + [ADR/0005 D9](0005-object-type-part.md) (adapter shell wire shape) preserved verbatim per [ADR/0027 D18](0027-aiad-positioning-and-native-engine-posture.md) wire-name preservation. Codex1 B5 caught Claude1's accidental supersession of D7 (replacing `vault_ref` with `engine_artifact_ref`) — corrected; both fields exist with their distinct roles (`vault_ref` is the canonical Vault anchor; `engine_artifact_ref` is an OPTIONAL adapter-shell field for a separate engine-side artifact like a `.FCStd` document).

**No multi-document amendments**: Manifesto / ArchitectureOverview / Glossary unchanged. Glossary may gain entries for `feature` + `geometry_ref` records when the `aiadra-core 0.10.0 → 0.11.0` arc lands and Native Engine handlers start emitting them.

## Consequences

- **Bundle v0.27.0 → v0.28.0** with the digest pinned in the frontmatter (re-pinned across R3 + R4 as schema files tightened). Nine bundles (v0.19.0 through v0.28.0) ship side-by-side.
- **`aiadra-core 0.9.0 → 0.10.0`** with fold handler additions. ADR/0028 D14 step 3 renumbers to `0.10.0 → 0.11.0` API additions arc.
- **Native Engine ecosystem unblocked** at the schema layer. The next arc adds the Python API surface (`NativeEngineRegistrar` / `NativeEngineContext` / etc.); after that, Wedge-003 scope ADR; then `aiadra-mechanical` first concrete Native Engine.
- **First multi-Object-Type Schema Change Note** to land in the same arc as both schema additions AND fold logic — matches arc 5 F2 SCN model (which also bundled schema + fold + validator + Transaction op + CLI + tests in one arc).
- **Provenance discipline operationalized in fold** — feature records carry caller-derived provenance; geometry_ref records cross-check `derived_from_feature_ids` against canonical `feature:<id>` form in `fact_provenance.derived_from`. Together with ADR/0028 D8's split at the Native Engine boundary, this closes the laundering risk at multiple layers.
- **DAG-not-tree dependency model** (per Codex1 B6) enables real mechanical authoring patterns (multi-edge fillets, multi-sketch lofts, etc.) without re-opening ADR/0029 once `aiadra-mechanical` exercises them.
- **41 new integration tests** (`tests/integration/test_adr_0029_part_authoring_scn.py`) covering each Codex1 blocker (B1-B6) + N1 absorption + atomic delta rules + DAG acyclicity + cascade integrity + canonical unit validation + Codex2 R3 absorption (B1 missing-actor schema-reject + B2 dangling extras / cross-Object form / non-canonical / derived_export equality + cascade). **299 / 299 tests pass** (was 258 pre-arc; +41 net Phase 5 across R2+R3).
- **Coherence Checklist re-walk PASS** on all 11 items (units-at-fact-level + Native-engine-boundary are load-bearing for this SCN).
- **No new Coherence Checklist item earned** (the DAG acyclicity check is intra-Part not cross-Part — Codex Q9 + ADR/0029 D9 don't justify a new item).

## Alternatives rejected

- **(i) Added-only delta semantics** (matching arc 5 `requirement_changed`). Rejected per ADR/0027 D17 verbatim scope + Wedge-003's need for update + remove from day one. The drawing/test/evidence `_apply_attachment_delta` (full delta) precedent is the correct model.
- **(ii) Bounded enum for `feature_type`**. Rejected per Codex1 Q2 + symmetric to D7 lock-in concern — forces all Native Engines into one vocabulary prematurely.
- **(iii) Schema-baking sketch primitives** at the canonical bundle level. Rejected per D7 + [ADR/0027 D11](0027-aiad-positioning-and-native-engine-posture.md) — varies massively between kernels; engine-owned.
- **(iv) Replacing `vault_ref` with `engine_artifact_ref` on geometry_ref**. Rejected per Codex1 B5 — would silently supersede [ADR/0005 D7](0005-object-type-part.md) canonical Vault anchor. Both fields preserved with distinct roles.
- **(v) `parent_feature_id` single-parent tree** for feature dependencies. Rejected per Codex1 B6 — real mechanical features have multi-parent dependencies. `depends_on_feature_ids: string[]` with DAG acyclicity is the correct model.
- **(vi) Custom event envelope** for `part_changed`. Rejected per Codex1 B1 — must compose with `event/_base.schema.json` like every other `<type>_changed` event.
- **(vii) Colon in serialized namespace keys** (`feature:` / `geometry_ref:` as JSON property names). Rejected per Codex1 B2 — colon is address notation, not key syntax. Every existing namespace (`parameter`, `relationship`, etc.) uses no colon.
- **(viii) Engine-defined units** on feature parameters. Rejected per D10 + Coherence Checklist "Canonical units at fact level" — would violate the load-bearing invariant.
- **(ix) `vault_delta` in the event payload** for staged Vault bytes. Rejected per Codex1 Q6 + Phase 1 W2 precedent — Vault bytes get staged via the existing `stage_vault_bytes()` mechanism; the event references content hashes that result.
- **(x) Cascade-on-remove** automatic deletion of dependent features. Rejected per Codex1 Q7 + D12 — explicit caller responsibility via batched `removed[]` (accepted) or sequential Transactions in dependency-correct order. Avoids silent deletion of records the caller didn't explicitly intend to remove.
- **(xi) New `TransactionKind.PART_CHANGED` enum member**. Rejected per D14 item 1 — Native Engine handlers in `aiadra-mechanical` use namespaced operation kinds (`mechanical.add_feature` / etc.) via [ADR/0028 D16](0028-native-engine-implementation-contract.md) `TransactionDraft.kind: str` generalization. aiadra-core's `TransactionKind` enum is the namespace of BUILT-IN kinds only.
- **(xii) Optional `actor` on `part_changed` events** (defaulted to `"agent"` in fold). Rejected per Codex2 B1: silently manufactures provenance context for malformed events. `event/part_changed.schema.json` has root-level `required: ["actor"]`; fold uses direct access (`event["actor"]`) — missing actor is schema-rejected, NOT defaulted.
- **(xiii) Subset / coverage-only provenance cross-check** (`derived_from_feature_ids ⊆ fact_provenance.derived_from`). Rejected per Codex2 B2: allows over-attesting (dangling extra `feature:feat_9999` refs that don't exist on the Part). STRICT set-equality is the chosen path.
- **(xiv) Cross-Object provenance address form `<object_uuid>:feature:<feat_id>` admitted in v0.28.0**. Rejected per Codex2 B2: this form is RESERVED for a future SCN when cross-Part geometry derivation lands. The v0.28.0 fold rejects any non-canonical entry; only intra-Part `feature:<feat_id>` (and `geometry_ref:<geom_id>` for derived_export) is admitted.

## References

- [ADR/0027 D17](0027-aiad-positioning-and-native-engine-posture.md) — pre-condition framing for this SCN.
- [ADR/0028 D14 step 2](0028-native-engine-implementation-contract.md) — bundle v0.27.0 → v0.28.0 MINOR additive; PRE-CONDITION for `aiadra-mechanical` Wedge-003.
- [ADR/0028 D8](0028-native-engine-implementation-contract.md) — caller-supplied vs engine-computed provenance split; this SCN bakes the split at the delta-operation level.
- [ADR/0028 D16](0028-native-engine-implementation-contract.md) — `TransactionDraft.kind: str` generalization; Native Engine operations use namespaced kinds.
- [ADR/0005 §3](0005-object-type-part.md) — Part 7-namespace decision; this SCN advances 2 more (feature + geometry_ref) from pinned-but-not-baked to schema-baked.
- [ADR/0005 §7](0005-object-type-part.md) — geometry_ref role enum + REQUIRED vault_ref; preserved verbatim per Codex1 B5 absorption.
- [ADR/0005 §9](0005-object-type-part.md) — adapter shell wire shape; preserved verbatim per [ADR/0027 D18](0027-aiad-positioning-and-native-engine-posture.md).
- [ADR/0026 §5](0026-ai-action-protocol-scope.md) — provenance discipline; agent cannot self-attest as human_input.
- [ADR/0025 §5](0025-aiadra-core-runtime-scope.md) — F2 SCN precedent (added-only delta + full schema in shared record).
- [ADR/0025 §4](0025-aiadra-core-runtime-scope.md) — F1 SCN precedent (`new_fact_provenance` extension to event payload).
- [ADR/0025 §9](0025-aiadra-core-runtime-scope.md) — W3 SCN precedent (per-type schemas + bundle lookup namespace).
- [ADR/0003](0003-schema-governance.md) — schema bundle governance (MINOR additive).
- [SystemState.md §3](../SystemState.md) — Coherence Checklist (11 items walked).
- [TruthModelSchema.md S0 commitment 7](../TruthModelSchema.md) — list-addressability rule.
- [Manifesto.md v0.4 P5](../Manifesto.md) — transactional approval; reject loudly.
- Phase 1 W2 arc 20260531-2 `_apply_attachment_delta` — full add/update/remove delta precedent.
- Phase 2 F1 arc 20260531-3 — `new_fact_provenance` + dual-fold discipline precedent.
- Phase 3 W3 arc 20260531-4 — per-relationship-type schemas precedent.
- Phase 4 F2 arc 20260531-5 — `requirement_changed` added-only delta precedent (contrasted in D3).
- Phase C arc 20260531-9 Codex1 B4 — provenance discipline at propose boundary; this SCN bakes the same discipline at the delta-operation level.
