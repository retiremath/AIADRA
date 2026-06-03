/**
 * Import parse Worker (arc 20260603-1) — runs OFF the UI thread and off the
 * privileged side (Codex1 N6). It receives untrusted external bytes, parses them
 * with three.js `STLLoader` (STL) or `occt-import-js` (STEP, single-threaded
 * WASM — no SharedArrayBuffer, so no cross-origin isolation), and posts back
 * transferable typed arrays. It NEVER touches the bridge, main, or the filesystem.
 *
 * Output is deliberately raw: every invariant is re-checked on the main thread by
 * `normalizeMeshes` (Codex1 B1) before any of it reaches three.js.
 */

import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import type { RawMesh, WorkerRequest, WorkerResponse } from './messages'

// Avoid `/// <reference lib="webworker" />` (it conflicts with the renderer's DOM
// lib). A minimal local alias is enough for postMessage + onmessage.
const ctx = self as unknown as {
  postMessage(message: unknown, transfer?: Transferable[]): void
  onmessage: ((ev: MessageEvent) => void) | null
}

function toFloat32(a: ArrayLike<number> | Float32Array): Float32Array {
  return a instanceof Float32Array ? a : Float32Array.from(a)
}

function parseStl(buffer: ArrayBuffer): RawMesh[] {
  const geo = new STLLoader().parse(buffer)
  const posAttr = geo.getAttribute('position')
  if (!posAttr || posAttr.array.length === 0) throw new Error('STL file contained no geometry')
  const position = toFloat32(posAttr.array as Float32Array)
  const normalAttr = geo.getAttribute('normal')
  const normal = normalAttr ? toFloat32(normalAttr.array as Float32Array) : undefined
  const index = geo.index ? Uint32Array.from(geo.index.array as ArrayLike<number>) : undefined
  return [{ name: 'imported mesh', position, normal, index }]
}

// STEP support (occt-import-js + the 7.6 MB inlined WASM) is dynamically imported
// only when a STEP file actually arrives, so STL-only sessions never load it.
async function parseStep(buffer: ArrayBuffer): Promise<RawMesh[]> {
  const { readStep } = await import('./occtStep')
  return readStep(buffer)
}

function transfersOf(meshes: RawMesh[]): Transferable[] {
  const t: Transferable[] = []
  for (const m of meshes) {
    t.push(m.position.buffer)
    if (m.normal) t.push(m.normal.buffer)
    if (m.index) t.push(m.index.buffer)
  }
  return t
}

ctx.onmessage = async (ev: MessageEvent) => {
  const req = ev.data as WorkerRequest
  const requestId = req?.requestId
  try {
    const meshes = req.format === 'stl' ? parseStl(req.buffer) : await parseStep(req.buffer)
    const res: WorkerResponse = { status: 'ok', requestId, meshes }
    ctx.postMessage(res, transfersOf(meshes))
  } catch (err) {
    const res: WorkerResponse = {
      status: 'error',
      requestId,
      message: err instanceof Error ? err.message : String(err),
    }
    ctx.postMessage(res)
  }
}
