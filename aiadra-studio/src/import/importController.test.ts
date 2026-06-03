import { afterEach, describe, expect, it, vi } from 'vitest'
import { createImporter, type FileLike, type WorkerLike } from './importController'
import { ImportError } from './normalize'
import type { RawMesh, WorkerRequest, WorkerResponse } from './messages'

/** A fake worker: a `responder` maps each request to a response, or null to
 *  stay silent (simulating a hung parse → timeout). No real Worker/WASM. */
class FakeWorker implements WorkerLike {
  onmessage: ((ev: { data: unknown }) => void) | null = null
  onerror: ((ev: unknown) => void) | null = null
  terminated = false
  posted: WorkerRequest[] = []
  private responder: (req: WorkerRequest) => WorkerResponse | null
  constructor(responder: (req: WorkerRequest) => WorkerResponse | null) {
    this.responder = responder
  }
  postMessage(message: unknown): void {
    const req = message as WorkerRequest
    this.posted.push(req)
    const res = this.responder(req)
    if (res) queueMicrotask(() => this.onmessage?.({ data: res }))
  }
  terminate(): void {
    this.terminated = true
  }
}

function okWith(meshes: RawMesh[]) {
  return (req: WorkerRequest): WorkerResponse => ({ status: 'ok', requestId: req.requestId, meshes })
}

function triMesh(): RawMesh {
  return {
    name: 'm',
    position: new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]),
    normal: new Float32Array([0, 0, 1, 0, 0, 1, 0, 0, 1]),
  }
}

function fakeFile(name: string, opts: { size?: number; buffer?: ArrayBuffer } = {}): FileLike {
  const buffer = opts.buffer ?? new ArrayBuffer(64)
  return { name, size: opts.size ?? buffer.byteLength, arrayBuffer: async () => buffer }
}

/** Install spies on every exposed `window.aiadra` method so a test can assert the
 *  import path calls NONE of them (Codex1 N7 / B-close-condition). */
function installAiadraSpies() {
  const spies = {
    ping: vi.fn(),
    coreVersion: vi.fn(),
    chooseWorkspace: vi.fn(),
    inspect: vi.fn(),
  }
  ;(globalThis as unknown as { window: unknown }).window = { aiadra: spies }
  return spies
}

afterEach(() => {
  delete (globalThis as unknown as { window?: unknown }).window
  vi.restoreAllMocks()
})

describe('createImporter — boundary + B1 safety', () => {
  it('imports a valid STL and makes ZERO window.aiadra calls (Codex1 N7)', async () => {
    const spies = installAiadraSpies()
    let created = 0
    const importer = createImporter({
      workerFactory: () => {
        created++
        return new FakeWorker(okWith([triMesh()]))
      },
    })

    const meshes = await importer.import(fakeFile('part.stl'))

    expect(meshes).toHaveLength(1)
    expect(meshes[0].position.length).toBe(9)
    expect(created).toBe(1)
    for (const spy of Object.values(spies)) expect(spy).not.toHaveBeenCalled()
  })

  it('reuses one worker across imports, then disposes it', async () => {
    let created = 0
    let worker: FakeWorker | null = null
    const importer = createImporter({
      workerFactory: () => {
        created++
        worker = new FakeWorker(okWith([triMesh()]))
        return worker
      },
    })
    await importer.import(fakeFile('a.stl'))
    await importer.import(fakeFile('b.stl'))
    expect(created).toBe(1)
    importer.dispose()
    expect(worker!.terminated).toBe(true)
  })

  it('rejects an oversized file BEFORE creating a worker', async () => {
    let created = 0
    const importer = createImporter({
      maxBytes: 1000,
      workerFactory: () => {
        created++
        return new FakeWorker(okWith([triMesh()]))
      },
    })
    await expect(importer.import(fakeFile('big.stl', { size: 2000 }))).rejects.toThrow(/too large/)
    expect(created).toBe(0)
  })

  it('rejects an unsupported extension', async () => {
    const importer = createImporter({ workerFactory: () => new FakeWorker(okWith([triMesh()])) })
    await expect(importer.import(fakeFile('part.obj'))).rejects.toThrow(ImportError)
  })

  it('surfaces a worker error response as an ImportError', async () => {
    const importer = createImporter({
      workerFactory: () =>
        new FakeWorker((req) => ({ status: 'error', requestId: req.requestId, message: 'bad bytes' })),
    })
    await expect(importer.import(fakeFile('part.stl'))).rejects.toThrow(/bad bytes/)
  })

  it('times out and terminates a hung worker', async () => {
    let worker: FakeWorker | null = null
    const importer = createImporter({
      timeoutMs: 20,
      workerFactory: () => {
        worker = new FakeWorker(() => null) // never responds
        return worker
      },
    })
    await expect(importer.import(fakeFile('hang.stl'))).rejects.toThrow(/timed out/)
    expect(worker!.terminated).toBe(true)
  })

  it('validates worker output through the B1 gate (out-of-range index rejected)', async () => {
    const bad: RawMesh = { position: new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]), index: new Uint32Array([0, 1, 9]) }
    const importer = createImporter({ workerFactory: () => new FakeWorker(okWith([bad])) })
    await expect(importer.import(fakeFile('part.stl'))).rejects.toThrow(/out of range/)
  })
})
