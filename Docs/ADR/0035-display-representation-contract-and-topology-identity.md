# ADR/0035 — Display Representation contract + engine-owned topology identity (v1)

## Frontmatter

- **Status:** Accepted — 2026-06-09 (arc 20260609-1; two-round convergence Claude1 + Codex1 / Claude2 + Codex2). Foundation arc — the first *real* Display build under [ADR/0033](0033-studio-display-ux-vision.md) (D10 step 3); gate cleared by [ADR/0034](0034-licensing-and-third-party-kernel-compliance.md).
- **What it is:** pins the **Display Representation contract** (the versioned, read-only data contract between a geometry producer and the AIADRA Studio viewport), the **engine-owned topology identity** scheme, and the **read-only Native Engine operation category** that delivers it — proven end-to-end on one canonical part (the box-with-hole) with identity tested across an edit.
- **Realizes:** ADR/0033 D2 (BREP-derived true topology), D3 (the contract — the central deliverable), D4 (engine-side OCCT), D5 (engine-owned identity + the across-edit test), D7 (display-mode taxonomy — the edge foundation), D10 step 3. Merges ADR/0032 D8 (topological selection) into the foundation.
- **Version impact:** `aiadra-core` **0.11.2 → 0.12.0** (additive public Tier-1 protocol surface). `aiadra-mechanical` `adapter_schema_version` **0.1.0 → 0.1.1** (engine-internal). **No bundle / schema / Glossary / Manifesto / TruthModelSchema change** — display data is not Product Truth.

## §0 — What this ADR does

[ADR/0033](0033-studio-display-ux-vision.md) pinned the vision and named the crux: Creo-grade display, hidden-line, silhouettes, and topological selection all need the same thing — a **BREP-derived display representation with true edges and explicit, engine-owned topology identity**, not screen-space approximation. This ADR pins the concrete realization of that crux and records the spike that proved it: an engine generates a versioned display package from a part's feature recipe; the package carries true tessellation + true model edges + **stable, feature-anchored topology IDs**; and those IDs **survive an edit/recompute** (the central selection trap, [ADR/0033 D5](0033-studio-display-ux-vision.md)).

## Decisions

### D1. The Display Representation contract is a versioned, read-only, kernel-neutral DTO
The central deliverable ([ADR/0033 D3](0033-studio-display-ux-vision.md)) is `aiadra_core.protocol.display.DisplayRepresentation` (`display_representation_version = "1.0"`), pure data, defined in **kernel-neutral** `aiadra-core` (no geometry kernel import) and mirrored as a TypeScript type in Studio. Sections:
- **identity** — `object_uuid` / `object_number` / `geometry_ref` (the recipe-hash `vault_ref`) / `cache_key` / `topology_signature` (D3 below).
- **render** — `faces` (triangle buffers **grouped by `face_id`**, with true surface normals), `edges` (true-curve polylines by `edge_id` + `kind` + adjacent face ids), `vertices`, `bbox`, tolerance, `buffer_encoding` (`"json_arrays"` v1; binary reserved).
- **selection** — `id_space` (`canonical` for Workspace geometry / `ephemeral` for imports), `pickable_kinds`, human-readable `names`.
- **view_dependent** — a **reserved `null` slot** for HLR/hidden-line (the next arc); the contract rejects a populated value at v1.0 so the HLR arc adds it additively (→ v1.1).
- **invalidation** — `stale_when` + `selection_invalid_when = "topology_signature_changed"`.
- **counters** — face / edge-by-kind / triangle / vertex counts (+ optional latency / bytes) — the acceptance baseline for the HLR / display-mode arcs.

**Boundary:** read-only; never becomes Product Truth; the renderer receives *this DTO*, never a handle to call kernel methods — [Manifesto P11](../Manifesto.md) + [ADR/0032 D6](0032-aiadra-studio-scope.md) hold.

### D2. Topology identity is engine-minted, feature-anchored, and recipe-derived FIRST
Display IDs use the grammar **`<feature>[/<primitive>]:<kind>:<role>`** (e.g. `feat_0002:face:cap_top`, `feat_0002/skp_0001:face:wall_x_min`, `feat_0002/skp_0002:face:hole_wall`) — modeled on Creo's feature-relative identity (`F12(ROUND_5)`).
- **Roles are enumerated from the recipe BEFORE OCCT traversal**; geometry is the *mapper* (role → subshape), never the identity source. Raw OCCT subshape handles, traversal order, and `occt-import-js` mesh ranges are **never** identity (per [ADR/0033 D5](0033-studio-display-ux-vision.md)).
- **Stable primitive anchors:** the engine mints `skp_NNNN` ids on sketch primitives at authoring time (`adapter_schema_version` 0.1.1; caller-supplied ids rejected). A topology-contributing primitive **must** carry a valid `^skp_[0-9]{4}$` id; a missing/malformed id **fails loud** (`TransactionError`) before any display id is minted — **no placeholder anchors** (arc 20260609-1 Codex2 B1).
- **Symmetric faces are disambiguated by the originating sketch edge** (a wall is matched to the rectangle edge whose midpoint it carries), not by centroid magnitude, area, or traversal order. Correlation gaps fail loud.
- **Imports** get `id_space="ephemeral"` until/unless a future ingest Data Adapter ([ADR/0028 D11](0028-native-engine-implementation-contract.md)) makes them Product Truth.

### D3. Invalidation is keyed on a deterministic `topology_signature`, not a stored counter
A read-only operation writes no Truth, so it cannot persist a monotonic revision counter. `topology_signature` is a deterministic hash over the **topology skeleton** — feature types + sketch primitive `(id, type)` lists — **excluding** all parameter *values* (dimensions, depth, hole position, direction). Therefore a **parameter edit preserves every display ID and the signature** (the across-edit invariant), while **adding/removing a feature or primitive changes the signature** and introduces/retires IDs. The renderer treats `topology_signature_changed` as "held selection IDs may be invalid."

### D4. A read-only Native Engine operation category in `aiadra-core`
Display generation is a **read** (evaluate current recipe → tessellate → return), so it must NOT reuse the mutation (`propose`/`modify`) path that begins a `TransactionDraft` and hands handlers a staging context. This ADR adds a genuine read lane (arc 20260609-1 Codex1 B1):
- **Registry:** `NativeEngineRegistrar.add_read_operation(kind, handler)` → a separate `read_operations` tuple; read ops never enter `propose_kinds()` / `modify_kinds()`; `native_engine_status()` lists them under `read_operations`; new `read_kinds()` introspection. Same ADR/0028 D2 invariants (namespace / no-builtin / arity / a kind is mutation XOR read).
- **Context:** `NativeEngineReadContext` exposes only committed-state reads (`load_sidecar` / `load_reservation` / `find_reservation_entry_by_number` / `event_log_last_event_id` + `workspace` / `bundle` / `actor` / `engine_id` / `operation_kind`). It has **no** `stage_*`, `emit_event`, hooks, `transaction_id`, or `_draft`.
- **Dispatch + primitive:** `_resolve_read_handler` / `_dispatch_read` mirror the four-case engine discipline and the passthrough-vs-`NativeEngineKernelError` failure rule, but create **no draft and no audit**. `display_representation(workspace, object_ref, *, tolerance=…) → DisplayRepresentation` resolves the producing engine from the part's active `authoring_geometry` → `feature[].engine`, failing loud on no authoring geometry / no engine discriminator / multiple engines / engine missing-or-failed-or-lacking-the-read-handler. Core stays the gatekeeper; the Studio bridge stays narrow.

### D5. Engine-side OCCT generation; `aiadra-core` stays kernel-neutral
OCCT (`cadquery-ocp`) lives in `aiadra-mechanical` (the clean Apache-2.0 + LGPL-OCCT lane per [ADR/0034](0034-licensing-and-third-party-kernel-compliance.md)); `aiadra-core` defines only the contract shape + dispatch. The engine's `display.py` reuses the solid the validity gate already builds: `BRepMesh_IncrementalMesh` tessellation read per-face (true UV-derived surface normals, flipped on `REVERSED`), true edges discretized via `GCPnts_TangentialDeflection`, and the recipe-anchored ID correlation. The bridge (`display_representation`) and the renderer's canonical-part path consume the contract; the screen-space stopgap remains a labeled regression baseline only.

### D6. Edge-kind classification: sharp / tangent / seam now; HLR/outline later
Edges are classified from OCCT continuity across adjacent faces: **seam** (same face both sides / closed edge) is detected first, then **sharp** (`C0`) vs **tangent** (`G1+`). Tangent classification is built + unit-tested against a real OCCT fillet fixture even though the v0.0.1 box-with-hole has no fillet (it classifies as 14 sharp + 1 seam + **0 tangent**). **Silhouette/outline + visible/hidden classification (HLR) are view-dependent and deferred** to the next arc ([ADR/0033 D6](0033-studio-display-ux-vision.md)) — the `view_dependent` slot is reserved (D1).

### D7. Scope boundary, performance budgets, and the acceptance baseline
- **In:** the contract v1, the read-op category, the topology identity + across-edit test, face-grouped tessellation + true edges incl. the tangent classifier, the narrow bridge + canonical-part render path + pick-path proof. **Out (slots reserved):** HLR / hidden-line / silhouettes (next arc), the full display-mode taxonomy, selection *interaction* UI (hover/click/tooltips/filters), the appearance/theme system, the nav cube. Reference-import lane untouched.
- **Provisional performance budgets** ([ADR/0033 D10/N2](0033-studio-display-ux-vision.md)): initial package latency < 500 ms; engine generation < 150 ms for the box-with-hole; 60 fps interaction (static package during orbit — no per-frame engine calls). **Measured baseline:** 7 faces / 15 edges (14 sharp, 1 seam) / 120 triangles / 10 vertices; ~22 KB; ~28 ms engine generation. These counters are the baseline the HLR / display-mode arcs build against.

## Consequences
- The engine grows a **read-only display-generation capability** behind a narrow, versioned contract — a Native-Engine concern, not core.
- `aiadra-core` grows a **read-only Native Engine operation category** (the first read lane; previously dispatch was mutation-only) — reusable by future engines and future read primitives.
- **Selection has a foundation:** every face/edge/vertex carries a stable, feature-anchored ID that survives a parameter edit and round-trips through the bridge into the renderer's pick layer.
- The HLR arc, the display-modes arc, and the selection-interaction arc all build on this contract; the `view_dependent` slot absorbs HLR additively.

## Alternatives rejected
- **Reuse the mutation dispatch/context for reads** (discipline-by-convention). Rejected (D4) — a staging-capable context handed to a read handler makes writes *possible* and blurs Transaction/audit semantics; the boundary must be structural.
- **A stored `topology_revision` counter.** Rejected (D3) — a read op cannot persist Truth; a deterministic signature is the correct, side-effect-free invalidation key.
- **Geometry-only identity correlation / placeholder anchors.** Rejected (D2, Codex2 B1) — identity must trace to a real recipe anchor (`skp_` id), never a placeholder, even though `adapter_payload` is opaque to core's schema validation.
- **`occt-import-js` `brep_faces` ranges or raw OCCT handles as identity.** Rejected (per ADR/0033 D5) — mesh-oriented / transient; insufficient as a stable topology contract.
- **Per-frame exact HLR / silhouettes in this arc.** Deferred (D6) — view-dependent; the next arc.

## References
- [ADR/0033](0033-studio-display-ux-vision.md) — Display & UX vision (D2/D3/D4/D5/D6/D7/D10).
- [ADR/0034](0034-licensing-and-third-party-kernel-compliance.md) — licensing (the OCCT lane this depends on; gate cleared).
- [ADR/0028](0028-native-engine-implementation-contract.md) — Native-Engine boundary (D2 registration, D3 context, D5 dispatch discipline) + D11 ingest Data Adapter.
- [ADR/0031](0031-aiadra-mechanical-v0.0.1-scope.md) — `aiadra-mechanical` v0.0.1 (the recipe + validity-gate the display generator reuses).
- [Research/Creo10-Display-Benchmark.md](../Research/Creo10-Display-Benchmark.md) — the acceptance bar (tangent edges; `F12(ROUND_5)` selection identity).
- [Manifesto](../Manifesto.md) P11 — local-first, no hosted service; narrow bridge.
