# AIADRA Studio

The standalone desktop authoring application for [AIADRA](..) — the **primary Workspace Browser**. A professional 3D **viewport** (Creo-style) beside a docked **Product-Truth data panel** (Windchill-style), over the AIADRA-native Workspace.

Scoped by **[ADR/0032](../Docs/ADR/0032-aiadra-studio-scope.md)**. Status: **bootstrap spike → production seed** (Vite/React/three.js shell + first render proven; Electron, WASM-OCCT, and the engine bridge are not yet wired).

## Architecture (per ADR/0032)

- **Shell:** Electron desktop app (over Tauri — Chromium rendering consistency for 3D/WASM).
- **UI:** React + TypeScript + Vite (stable Vite 6 / Rollup) + three.js.
- **Geometry:** BREP-first — tessellated from the true BREP via OCCT (adaptive, true normals, analytic edges, LOD), with **face/edge/vertex topology IDs preserved for selection**. STL is a fallback only.
- **Two geometry lanes:** (1) external STEP/STL import = *reference* (never silently Product Truth); (2) the AIADRA Workspace lane = canonical geometry from the engine.
- **Engine bridge:** a Studio-owned local **stdio JSON-RPC** process over Tier-1 `aiadra_core.protocol` (the Ring 2 ops: `propose`/`modify`/`inspect`/`explain`). Secure by construction (context isolation, no node integration, allowlisted IPC, off-thread untrusted-geometry parsing). No `aiadra-core` server, no network — local-first ([Manifesto P11](../Docs/Manifesto.md)).
- **Native format:** the AIADRA **Workspace** (Git repo: Product-Truth sidecars + Vault) is authoritative; a portable bundled document is a future export.

## Develop

```bash
nvm use 20            # Node 20 LTS (this repo needs 18+)
npm install
npm run dev           # http://localhost:5173
npm run build
```

## Status / roadmap

- ✅ Vite + React + TS + three.js shell; lit/edged viewport; Creo-style layout; first pixels.
- ✅ CAD navigation: middle = rotate · shift+middle = pan · ctrl+middle & scroll = zoom · left = select · right = context menu; near-zero inertia.
- ⏳ Deferred (later): an **orthographic-camera option** for a perfectly flat pan — the perspective camera parallaxes slightly when panning (acceptable for now per Petre).
- ▢ Milestone 1: Electron shell + secure bridge skeleton + STEP/STL import lane + orbit/pan/zoom/fit + shaded+edges + model-tree stub.
- ▢ Milestone 2: topological selection model + AIADRA Workspace lane.
- ▢ Milestone 3: measurement + section planes + Product-Truth data panel wired.
