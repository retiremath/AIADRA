import { resolve } from 'node:path'
import { defineConfig } from 'electron-vite'
import react from '@vitejs/plugin-react'

// electron-vite: main + preload built to out/{main,preload}; renderer is the
// existing Vite app at the project root (keeps the browser-only `npm run dev:web`
// path for fast viewport work — Codex1 N1). The security-sensitive BrowserWindow
// config is written explicitly in electron/main.ts, NOT hidden in tooling.
export default defineConfig({
  // The package is ESM ("type":"module"), which would make plain .js outputs ESM.
  // We force CJS .cjs for BOTH main and preload: a sandboxed preload (B1 requires
  // sandbox:true) is the one case Electron loads inconsistently as ESM, and CJS
  // main is the most battle-tested. The renderer stays ESM (Vite/browser).
  main: {
    build: {
      outDir: 'out/main',
      lib: {
        entry: { index: resolve(__dirname, 'electron/main.ts') },
        formats: ['cjs'],
      },
    },
  },
  preload: {
    build: {
      outDir: 'out/preload',
      lib: {
        entry: { index: resolve(__dirname, 'electron/preload.ts') },
        formats: ['cjs'],
      },
    },
  },
  renderer: {
    root: '.',
    // Relative base so the built renderer + its worker/WASM assets resolve under
    // Electron's file:// origin (Codex1 B2 — the import worker loads occt's .wasm).
    base: './',
    plugins: [react()],
    // The import parse worker (importWorker.ts) is an ES module worker; emit ES so
    // its `import` of three/STLLoader + occt-import-js survives the build.
    worker: { format: 'es' },
    build: {
      outDir: 'out/renderer',
      rollupOptions: { input: { index: resolve(__dirname, 'index.html') } },
    },
    server: { port: 5173 },
  },
})
