import { defineConfig } from 'vitest/config'

// Standalone test config (does NOT load electron.vite.config.ts). The import-lane
// unit tests are pure TS — they inject a fake worker and never touch a real
// Worker, WASM, or the DOM, so the node environment is enough.
export default defineConfig({
  test: {
    include: ['src/**/*.test.ts', 'electron/**/*.test.ts'],
    environment: 'node',
  },
})
