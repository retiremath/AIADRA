import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Config for the PLAIN-Vite browser lane — `npm run dev:web` (the no-Electron,
// no-bridge fixture lane) and `npm run shoot`. The Electron build is configured
// separately in `electron.vite.config.ts`.
//
// `optimizeDeps.include: ['occt-import-js']` is load-bearing: the STEP parser
// (`occt-import-js`, CommonJS) is reached ONLY through a lazy dynamic import
// inside the parse Web Worker (`src/import/importWorker.ts` → `occtStep.ts`).
// Vite's dev dependency scan never sees it (not in the static main graph), so
// the worker's first import triggered an on-the-fly re-optimization →
// "504 (Outdated Optimize Dep)" → the worker crashed and STEP import failed in
// dev:web. Pre-bundling it up front fixes that. `worker.format: 'es'` matches
// the worker spawned with `{ type: 'module' }`. (The Electron build bundles via
// Rollup — no dev-optimizer step — so STEP already worked there.)
export default defineConfig({
  plugins: [react()],
  worker: { format: 'es' },
  optimizeDeps: { include: ['occt-import-js'] },
})
