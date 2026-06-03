/**
 * STEP parsing via occt-import-js (single-threaded WASM). Loaded LAZILY by the
 * worker (dynamic import) so an STL-only session never pays for the 7.6 MB WASM.
 *
 * STATUS (arc 20260603-1): STAGED, NOT ACTIVATED. `STEP_ENABLED` is false, so the
 * UI never routes a STEP file here. This module compiles + builds, but the
 * file://-safe WASM-byte delivery is the deferred follow-up's job (Codex1 B2).
 *
 * What is PROVEN: the occt-import-js WASM + ReadStepFile pipeline parses a real
 * STEP file when given `wasmBinary` bytes (no fetch) — see `scripts/step-smoke.cjs`
 * (Node: 18 meshes / 5040 triangles / 160 brep_faces from the sample STEP).
 *
 * What is DEFERRED (the follow-up must solve ALL of): delivering those bytes into
 * the built worker under Electron's file:// origin WITHOUT a fetch (Chromium
 * blocks `fetch(file://)`), and WITHOUT weakening the sandbox/CSP. The `?inline`
 * (base64 → `wasmBinary`) route is blocked by a Vite worker-bundling limitation
 * (`vite:worker-import-meta-url` cannot parse `.wasm?inline` in the worker
 * dynamic-import graph). Candidate fixes for the follow-up: (a) a narrow main-side
 * read of the app's OWN bundled wasm asset handed to the renderer as bytes (a
 * trusted app asset, distinct from the untrusted-geometry lane); (b) a custom
 * `app://` protocol whose handler serves the asset (fetchable, file://-safe);
 * (c) a build step / plugin that inlines the wasm as a JS module the worker can
 * import. The `?url` import below builds cleanly but would `fetch(file://)` at
 * runtime — which is exactly why STEP stays disabled until the follow-up lands.
 */

import occtFactory from 'occt-import-js'
import occtWasmUrl from 'occt-import-js/dist/occt-import-js.wasm?url'
import type { RawMesh } from './messages'

function toFloat32(a: ArrayLike<number> | Float32Array): Float32Array {
  return a instanceof Float32Array ? a : Float32Array.from(a)
}

let occtPromise: Promise<{ ReadStepFile(content: Uint8Array, params: unknown): OcctReadResult }> | null = null
type OcctReadResult = {
  success: boolean
  meshes: {
    name?: string
    attributes: { position?: { array: number[] }; normal?: { array: number[] } }
    index?: { array: number[] }
    brep_faces?: { first: number; last: number }[]
  }[]
}

function getOcct() {
  if (!occtPromise) occtPromise = occtFactory({ locateFile: () => occtWasmUrl })
  return occtPromise
}

export async function readStep(buffer: ArrayBuffer): Promise<RawMesh[]> {
  const occt = await getOcct()
  const result = occt.ReadStepFile(new Uint8Array(buffer), null)
  if (!result || !result.success || !Array.isArray(result.meshes) || result.meshes.length === 0) {
    throw new Error('occt-import-js could not read the STEP file')
  }
  return result.meshes.map((m, i): RawMesh => {
    const pos = m?.attributes?.position?.array
    if (!pos || pos.length === 0) throw new Error(`STEP solid ${i + 1} has no position data`)
    return {
      name: typeof m.name === 'string' && m.name ? m.name : undefined,
      position: toFloat32(pos),
      normal: m?.attributes?.normal?.array ? toFloat32(m.attributes.normal.array) : undefined,
      index: m?.index?.array ? Uint32Array.from(m.index.array) : undefined,
      brepFaceRangesUnused: Array.isArray(m?.brep_faces)
        ? m.brep_faces
            .filter((f) => f && typeof f.first === 'number' && typeof f.last === 'number')
            .map((f) => ({ first: f.first, last: f.last }))
        : undefined,
    }
  })
}
