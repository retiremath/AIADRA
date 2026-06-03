/**
 * STEP import is ENABLED (arc 20260603-2). The built renderer is served over a
 * read-only `app://bundle` origin (`electron/main.ts` + `electron/appProtocol.ts`)
 * so occt-import-js can fetch its WASM — Chromium blocks `fetch(file://)`. This is
 * gated on the built-Electron smoke `scripts/step-electron-smoke.mjs`, which proves
 * STEP parses + renders in the built `app://` app (asserts the app:// origin, the
 * handler served the WASM, the real controller/worker path, non-zero geometry, and
 * zero `window.aiadra` bridge calls). STL was always enabled.
 */
export const STEP_ENABLED = true

/** `accept` attribute for the file input, derived from the STEP gate. */
export const ACCEPT_EXTENSIONS = STEP_ENABLED ? '.stl,.step,.stp' : '.stl'

/** Human label of what the lane accepts (UI copy). */
export const ACCEPT_LABEL = STEP_ENABLED ? 'STEP / STL' : 'STL'
