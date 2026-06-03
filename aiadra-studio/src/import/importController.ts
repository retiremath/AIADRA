/**
 * Import controller (Codex1 B1, arc 20260603-1) — the renderer-side orchestrator
 * for the external STEP/STL reference-import lane (ADR/0032 D5 lane 1).
 *
 * Boundary guarantees (Codex1 N7): this module NEVER touches `window.aiadra`, the
 * engine bridge, the Product-Truth write path, or any filesystem. It receives a
 * `File` (bytes from a user-mediated `<input type="file">`), hands the bytes to a
 * Web Worker for parsing, and returns validated render data. No path ever crosses
 * to the privileged main process.
 *
 * Safety envelope (Codex1 B1): a byte cap up front, a worker timeout that
 * terminates a hung parse, discriminated worker messages, and full output
 * validation (`normalizeMeshes`) before any geometry reaches three.js.
 *
 * The worker factory is injectable so the unit tests drive the full controller
 * path with a fake worker — no real WASM, no real `Worker` needed.
 */

import { DEFAULT_CAPS, ImportError, type ImportCaps, type ImportedMesh, normalizeMeshes } from './normalize'
import { STEP_ENABLED } from './importConfig'
import type { ImportFormat, RawMesh, WorkerResponse } from './messages'

/** Reject files larger than this before reading them (1b cap). */
export const MAX_IMPORT_BYTES = 64 * 1024 * 1024
/** Terminate + fail a parse that runs longer than this. */
export const PARSE_TIMEOUT_MS = 30_000

/** The subset of `Worker` the controller uses — lets tests supply a fake. */
export interface WorkerLike {
  postMessage(message: unknown, transfer?: Transferable[]): void
  onmessage: ((ev: { data: unknown }) => void) | null
  onerror: ((ev: unknown) => void) | null
  terminate(): void
}

/** The subset of `File` the controller uses — lets tests supply a fake. */
export interface FileLike {
  name: string
  size: number
  arrayBuffer(): Promise<ArrayBuffer>
}

export interface Importer {
  /** Parse one user-chosen file into validated, reference-only meshes. */
  import(file: FileLike): Promise<ImportedMesh[]>
  /** Tear down the worker and fail any in-flight parse. */
  dispose(): void
}

export function detectFormat(filename: string): ImportFormat {
  const lower = filename.toLowerCase()
  if (lower.endsWith('.stl')) return 'stl'
  if (lower.endsWith('.step') || lower.endsWith('.stp')) {
    // Codex2 N1: enforce the STEP gate structurally at the import boundary, not
    // only in the UI, so the disabled STEP path is unreachable through the controller.
    if (!STEP_ENABLED) throw new ImportError('STEP import is deferred to a follow-up — STL only for now')
    return 'step'
  }
  throw new ImportError(`unsupported file type "${filename}" (expected .stl, .step, or .stp)`)
}

type Pending = {
  resolve: (meshes: RawMesh[]) => void
  reject: (err: Error) => void
  timer: ReturnType<typeof setTimeout>
}

export interface ImporterDeps {
  /**
   * Spawns the parse worker. REQUIRED + injected (not defaulted) so this module
   * carries no static reference to `importWorker.ts` — that keeps the occt/WASM
   * worker graph out of unit tests, which inject a fake worker. The real spawn
   * lives in `defaultWorker.ts` (browser/build only).
   */
  workerFactory: () => WorkerLike
  caps?: ImportCaps
  maxBytes?: number
  timeoutMs?: number
}

export function createImporter(deps: ImporterDeps): Importer {
  const workerFactory = deps.workerFactory
  const caps = deps.caps ?? DEFAULT_CAPS
  const maxBytes = deps.maxBytes ?? MAX_IMPORT_BYTES
  const timeoutMs = deps.timeoutMs ?? PARSE_TIMEOUT_MS

  let worker: WorkerLike | null = null
  let nextId = 1
  const pending = new Map<number, Pending>()

  function failAll(err: Error): void {
    for (const p of pending.values()) {
      clearTimeout(p.timer)
      p.reject(err)
    }
    pending.clear()
  }

  function resetWorker(): void {
    if (worker) {
      try {
        worker.terminate()
      } catch {
        /* terminate is best-effort */
      }
      worker = null
    }
  }

  function ensureWorker(): WorkerLike {
    if (worker) return worker
    const w = workerFactory()
    w.onmessage = (ev) => {
      const res = ev.data as WorkerResponse
      if (!res || typeof (res as { requestId?: unknown }).requestId !== 'number') return
      const p = pending.get(res.requestId)
      if (!p) return
      clearTimeout(p.timer)
      pending.delete(res.requestId)
      if (res.status === 'ok') p.resolve(res.meshes)
      else if (res.status === 'error') p.reject(new ImportError(res.message || 'import failed'))
      else p.reject(new ImportError('malformed worker response'))
    }
    w.onerror = (ev) => {
      const msg =
        (ev && typeof ev === 'object' && 'message' in ev && (ev as { message?: unknown }).message) ||
        'import worker crashed'
      failAll(new ImportError(String(msg)))
      resetWorker()
    }
    worker = w
    return w
  }

  async function importFile(file: FileLike): Promise<ImportedMesh[]> {
    const format = detectFormat(file.name)
    if (file.size > maxBytes) {
      throw new ImportError(`file too large: ${file.size} bytes exceeds the ${maxBytes}-byte import cap`)
    }
    const buffer = await file.arrayBuffer()
    if (buffer.byteLength > maxBytes) {
      throw new ImportError(`file too large: ${buffer.byteLength} bytes exceeds the ${maxBytes}-byte import cap`)
    }

    const w = ensureWorker()
    const requestId = nextId++
    const rawMeshes = await new Promise<RawMesh[]>((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(requestId)
        // The worker may be wedged on a malicious/huge file — kill it; the next
        // import lazily respawns. Any siblings die with it.
        resetWorker()
        failAll(new ImportError('import worker reset after timeout'))
        reject(new ImportError(`import timed out after ${timeoutMs} ms`))
      }, timeoutMs)
      pending.set(requestId, { resolve, reject, timer })
      w.postMessage({ requestId, format, buffer }, [buffer])
    })

    // B1: validate the worker's output before it can reach three.js.
    return normalizeMeshes(rawMeshes, caps)
  }

  return {
    import: importFile,
    dispose() {
      failAll(new ImportError('importer disposed'))
      resetWorker()
    },
  }
}
