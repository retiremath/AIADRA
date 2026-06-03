/**
 * Built-Electron STEP smoke hook (Codex1 B2, arc 20260603-2). Registered ONLY
 * under `?smoke=1` (main appends it to the app:// URL in smoke mode). It runs a
 * bundled sample STEP through the SAME user pipeline a file pick would — fetch the
 * sample over app:// → wrap in a File → real `createImporter` → worker → occt
 * (which fetches its WASM over app://) → `normalizeMeshes`. No raw fixture bytes
 * are interpolated into the page; the hook fetches the sample itself.
 *
 * The "zero bridge calls" property is asserted on the MAIN side: main snapshots
 * its `aiadra:*` IPC counter before/after this import and requires a delta of 0
 * (a stronger proof at the IPC boundary than monkeypatching the read-only,
 * contextBridge-frozen `window.aiadra`).
 */
import { createImporter } from './import/importController'
import { spawnImportWorker } from './import/defaultWorker'

export type StepSmokeResult = {
  origin: string
  meshCount: number
  triangles: number
}

export function registerStepSmoke(): void {
  ;(window as unknown as { __aiadraStepSmoke?: () => Promise<StepSmokeResult> }).__aiadraStepSmoke = async () => {
    const res = await fetch('samples/sample.step') // → app://bundle/samples/sample.step
    if (!res.ok) throw new Error(`sample STEP fetch failed: ${res.status}`)
    const buf = await res.arrayBuffer()
    const file = new File([buf], 'sample.step')

    const importer = createImporter({ workerFactory: spawnImportWorker })
    try {
      const meshes = await importer.import(file)
      const triangles = meshes.reduce((n, m) => n + (m.index ? m.index.length / 3 : m.position.length / 9), 0)
      return { origin: location.origin, meshCount: meshes.length, triangles }
    } finally {
      importer.dispose()
    }
  }
}
