# ADR/0043 — The Studio Ring-2 Authoring Bridge (session-capability write surface)

## Frontmatter

- **Status:** **Accepted** — 2026-07-11 (arc 20260711-11; design converged Claude1 + Codex1 / Claude2, then built. Codex1 B1 = session-capability, not raw generic; B2 = dual-lane). Co-landed with slice-1 code.
- **What it is:** the contract for **how AIADRA Studio enters Ring 2 to author geometry** — the *write* sibling of the read bridge ([ADR/0032](0032-aiadra-studio-scope.md) D6). Until now `window.aiadra` was read-only (inspect / list / display); this pins a **capability-gated write surface** so the manual dashboards and the AI panel can drive `propose → simulate → commit` over the real engine, without turning the hardened bridge into an unguarded write hole.
- **Macro direction:** Petre, 2026-07-11 — *"make it possible to create geometry both manually and with AI assistance… we need to have the geometry engine figured out."*
- **Version impact:** Studio bridge gains a write surface (Electron IPC + `bridge.py` methods); **no `aiadra-core` / schema / bundle / Glossary change** — it composes the existing Ring-2 `propose/modify/simulate/commit/rollback` ([ADR/0026](0026-ai-action-protocol-scope.md)).

## §0 — What this ADR does

The engine operations exist ([ADR/0037 D8](0037-modeling-paradigm-benchmark-and-knowledge-architecture.md); the feature arcs) and Ring 2 has the draft lifecycle ([ADR/0026](0026-ai-action-protocol-scope.md)). The missing layer was the Studio *write* path. This ADR pins its **security shape** so it's recorded before it spreads: the renderer never gets raw `propose(workspaceId, kind, params)` into core; it drives an **opaque authoring session** through allowlisted verbs.

## Decisions

### D1. A session-capability write surface, not a raw generic escape hatch (Codex1 B1)
- **Main** keeps the opaque `workspaceId → canonical path` capability (ADR/0032). For authoring it **mints an opaque `operationSessionId`**, tracked main-side as a capability bound to `{workspaceId, feature kind, actor, lifecycle state}`.
- The renderer may call **only allowlisted verbs** over that id: **`begin` (propose) · `add` (modify) · `simulate` · `commit` · `rollback`**.
- **Feature kinds are allowlisted** at the main/bridge boundary — v1: `mechanical.add_sketch_feature`, `add_extrude_feature`, `add_fillet_feature`, `add_chamfer_feature` (+ `create_part`) — and **params are structurally validated per kind** before reaching core.
- **No filesystem paths, Python objects, `TransactionDraft` objects, OCCT handles, or topology handles cross the wire.** The stateful draft lives in the persistent `bridge.py` process, keyed by `operationSessionId`; main brokers every verb.

### D2. Selection ids are input vocabulary only; the durable reference is resolved engine-side (Codex1 B4; ADR/0038)
A picked display `edge_id`/`face_id` crosses as an **input token** for fillet/chamfer targeting. The durable, recipe-anchored `target_edge`/`target_face` is resolved **engine-side** ([ADR/0038](0038-persistent-feature-reference-identity.md)); the ephemeral-identity firewall holds — **committed Truth never stores a raw display id as authority** ([ADR/0035](0035-display-representation-contract-and-topology-identity.md)).

### D3. `commit` returns the refreshed display identity (Codex1 B1)
`commit` returns commit metadata **plus the committed object's refreshed canonical/display identity** (and the display package for the authored object), so the renderer reloads exactly the right display — never guessing which committed object to fetch.

### D4. Explicit session lifecycle (Codex1 B1)
`rollback`/cancel discards the in-memory draft (nothing was written); a terminal-state guard prevents double-commit; stale-session timeout / bridge-exit fails outstanding sessions loudly with clear UI errors. `commit` and `rollback` close the session.

### D5. Dual-lane authoring backend (Codex1 B2)
Studio drives the write surface through an **`AuthoringBackend` interface** with two implementations behind identical TypeScript types: a deterministic **`dev:web` mock** (fast UI iteration — no engine, no Product-Truth writes, only success states the real engine can produce) and the **Electron bridge** (real Ring 2 → engine → display, the acceptance lane). Both are tested — the mock adapter contract and the real-bridge smoke.

## §1 — The verbs (v1)

`begin(workspaceId, kind, params) → { operationSessionId }` · `add(sessionId, kind, params)` · `simulate(sessionId) → { report, valid }` · `commit(sessionId, objectRef) → { commit, objectRef, display }` · `rollback(sessionId)`. Main validates the session capability + kind allowlist + params on every call; `bridge.py` holds the draft and delegates to `aiadra_core.protocol`.

## Consequences

- **Positive:** the manual dashboards and the AI panel share one secure write path; the read-bridge security posture (capability-gated, no paths/handles on the wire) extends to writes; ~0 per-button plumbing (generic verbs); the engine-write path is proven (the slice-1 authoring smoke creates + commits a real extruded box end-to-end).
- **Deferred:** richer sketching (a 2D sketcher), multi-edge/multi-face selection, holes/revolve/patterns, model-tree + full undo history (regen failures surface as operation-session validation state first).
- **Watches:** keep the kind allowlist + per-kind param validation main-side; never expose raw core `propose` to the renderer; session lifetime cleanup on bridge exit.

## Alternatives considered

- **Raw generic `propose(workspaceId, kind, params)` to the renderer** — rejected (D1): a near-direct core write hole; a session capability + allowlist preserves the security posture.
- **Per-button IPC methods** (one per feature) — rejected: per-button plumbing; generic verbs behind a session capability are leaner and equally safe.
- **Commit-then-display-then-rollback as "preview"** — rejected: commit writes Truth; `simulate` is the transient check, and the transient *geometry* preview is a read over draft state (three-state model, [ADR/0039 D3](0039-the-aiad-authoring-model.md)).
- **Bridge-lane-only development** — rejected (D5): too slow; a `dev:web` mock keeps the fast loop.
