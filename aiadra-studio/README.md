# AIADRA Studio

The standalone Electron desktop authoring app — the primary Workspace Browser
(Creo-style viewport + Windchill-style Product-Truth panel) over the
AIADRA-native Workspace. Scope: [ADR/0032](../Docs/ADR/0032-aiadra-studio-scope.md).
Display & UX strand: [ADR/0033](../Docs/ADR/0033-studio-display-ux-vision.md)
(realized by [ADR/0035](../Docs/ADR/0035-display-representation-contract-and-topology-identity.md)
+ [ADR/0036](../Docs/ADR/0036-view-dependent-hlr-contract-v1-1.md)).

## Running it

Three lanes. **To just look at the UI, use the browser lane** — it needs nothing else.

| Command | What it is | Needs |
|---|---|---|
| **`npm run dev:web`** | Plain Vite at **http://localhost:5173** — NO Electron, NO Python bridge, NO workspace. In dev with no bridge it **auto-loads the fixture part**, so you get the whole viewport (toolbar, theme, display modes, selection) to click around. | nothing |
| `npm run dev` | The full Electron desktop app. The viewport is empty until you **Open Workspace** (it reaches `aiadra-core` through the Python bridge). Launch from a plain terminal, **not** the VSCode integrated one (it sets `ELECTRON_RUN_AS_NODE`). | a real Workspace |
| `npm run preview` | The production-built Electron app (served from the `app://bundle` origin). | a real Workspace |

The browser lane is for *seeing and clicking* the display UI fast. The Electron
lanes exercise the real bridge/Workspace path (desktop acceptance).

Navigation (Creo/SolidWorks): middle = rotate · scroll = zoom · middle+shift =
pan · middle+ctrl = zoom · left = select · right = menu. The viewport is
orthographic, Z-up. Keyboard: `F` fit · `R` reset · `G` grid · `1`–`5` modes.

## Visual capture (screenshots)

`npm run shoot` boots the browser dev lane on a random free port, screenshots a
standard gallery of the display modes (iso × 5 modes + front Hidden-Line + tilt
No-Hidden), and tears the server down. It doubles as a **smoke** — any page or
console error fails the run. Output goes to `shots/` (git-ignored).

```sh
npx playwright install chromium   # first time only — downloads the browser
npm run shoot                     # → aiadra-studio/shots/*.png
npm run shoot -- ../some/dir      # custom output directory
```

## Checks

```sh
npm run test     # vitest (pure modules — settings, commands, display, import)
npx tsc -b       # type check
npm run build    # electron-vite build + assert-no-fixtures (proves dev fixtures
                 # never reach the production renderer)
```

## Layout

- `src/` — the React renderer (sandboxed; reaches `aiadra-core` only via the
  allowlisted preload bridge). `display/` (canonical render path + HLR overlay +
  display modes), `settings/` (typed registry + coordinated theme, persisted
  under Electron userData), `commands/` + `viewstate/` (command taxonomy +
  shared live view state), `import/` (reference STL/STEP lane, never Product Truth).
- `electron/` — `main.ts` (security envelope, capability-gated IPC, the
  `app://bundle` asset scheme, settings file IO) + `preload.ts`.
- `bridge/` — the Studio-owned Python NDJSON JSON-RPC bridge over Tier-1
  `aiadra_core.protocol` (no core server — [Manifesto P11](../Docs/Manifesto.md)).
- `scripts/` — dev / build / capture / fixture-gen tooling.
