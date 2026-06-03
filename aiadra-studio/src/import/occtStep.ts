/**
 * STEP parsing via occt-import-js (single-threaded WASM). Loaded LAZILY by the
 * worker (dynamic import) so an STL-only session never pays for the 7.6 MB WASM.
 *
 * STATUS (arc 20260603-2): LIVE. occt's default `locateFile`→fetch of the `?url`
 * WASM now works because the BUILT renderer is served over a fetchable
 * `app://bundle` origin (route (b) from arc 20260603-1) instead of `file://`
 * (Chromium blocks `fetch(file://)`). The app:// asset handler lives in
 * `electron/main.ts` + `electron/appProtocol.ts`; the built-Electron proof is
 * `scripts/step-electron-smoke.mjs`. No `wasmBinary` plumbing, no sandbox/CSP
 * weakening, single-threaded build (no SharedArrayBuffer → no cross-origin
 * isolation, Codex1 N6). In Vite dev the origin is `http://localhost`, also
 * fetchable. The Node parse proof from arc 20260603-1 stays at `scripts/step-smoke.cjs`.
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
