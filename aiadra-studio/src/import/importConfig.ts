/**
 * STEP import ships in 1b ONLY if it passes the built-Electron `file://` WASM
 * smoke (Codex1 B2). This is the single toggle: STL is always enabled.
 *
 * DEFERRED (arc 20260603-1): set to `false`. The occt WASM parse pipeline is
 * proven (`scripts/step-smoke.cjs`), but the file://-safe byte delivery into the
 * built worker is not solved — the `?inline` route is blocked by a Vite
 * worker-bundling limitation and the `?url` route would `fetch(file://)` (blocked
 * by Chromium). Resolving that without weakening the sandbox/CSP is the follow-up
 * arc's job (see `occtStep.ts` for the candidate fixes). Flip back to `true` once
 * the follow-up lands a built-Electron STEP smoke.
 */
export const STEP_ENABLED = false

/** `accept` attribute for the file input, derived from the STEP gate. */
export const ACCEPT_EXTENSIONS = STEP_ENABLED ? '.stl,.step,.stp' : '.stl'

/** Human label of what the lane accepts (UI copy). */
export const ACCEPT_LABEL = STEP_ENABLED ? 'STEP / STL' : 'STL'
