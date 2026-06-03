/** Wire types between the import controller (main thread) and the parse Worker. */

export type ImportFormat = 'stl' | 'step'

/** Controller → Worker. `buffer` is transferred (not copied). */
export type WorkerRequest = {
  requestId: number
  format: ImportFormat
  buffer: ArrayBuffer
}

/** One mesh as the worker emits it — typed arrays, transferable. UNTRUSTED shape:
 *  the controller's `normalizeMeshes` validates every invariant before use. */
export type RawMesh = {
  name?: string
  position: Float32Array
  normal?: Float32Array
  index?: Uint32Array
  brepFaceRangesUnused?: { first: number; last: number }[]
}

/** Worker → Controller, discriminated by `status` (Codex1 B1 — validate by tag). */
export type WorkerResponse =
  | { status: 'ok'; requestId: number; meshes: RawMesh[] }
  | { status: 'error'; requestId: number; message: string }
