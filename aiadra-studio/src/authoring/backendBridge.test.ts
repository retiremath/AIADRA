import { describe, it, expect, vi, afterEach } from 'vitest'
import { createBridgeAuthoringBackend } from './backendBridge'

const okEnv = <T>(result: T) => ({ ok: true as const, result })
const errEnv = (message: string) => ({ ok: false as const, error: { message } })

function setAiadra(a: Record<string, unknown>) {
  ;(globalThis as unknown as { window: unknown }).window = { aiadra: a }
}

afterEach(() => {
  delete (globalThis as unknown as { window?: unknown }).window
  vi.restoreAllMocks()
})

describe('backendBridge lifecycle (Codex3 B1)', () => {
  it('rolls back the opened session if a later opAdd fails', async () => {
    const opRollback = vi.fn(async () => okEnv({ rolled_back: true }))
    setAiadra({
      opBegin: async () => okEnv({ operationSessionId: 'S1' }),
      opAdd: async () => errEnv('bad op'), // the second op fails
      opSimulate: async () => okEnv({ report: { valid: true } }),
      opCommit: async () => okEnv({}),
      opRollback,
    })
    const backend = createBridgeAuthoringBackend('WS')
    await expect(
      backend.begin([
        { kind: 'create_part', params: {} },
        { kind: 'mechanical.add_extrude_feature', params: {} },
      ]),
    ).rejects.toThrow('bad op')
    // The opened session must not orphan — begin rolled it back.
    expect(opRollback).toHaveBeenCalledWith('S1')
  })

  it('begins cleanly and does not roll back when every op adds', async () => {
    const opAdd = vi.fn(async () => okEnv({ session_id: 'S1' }))
    const opRollback = vi.fn(async () => okEnv({ rolled_back: true }))
    setAiadra({
      opBegin: async () => okEnv({ operationSessionId: 'S1' }),
      opAdd,
      opSimulate: async () => okEnv({ report: { valid: true } }),
      opCommit: async () => okEnv({}),
      opRollback,
    })
    const backend = createBridgeAuthoringBackend('WS')
    const sid = await backend.begin([
      { kind: 'create_part', params: {} },
      { kind: 'mechanical.add_sketch_feature', params: {} },
      { kind: 'mechanical.add_extrude_feature', params: {} },
    ])
    expect(sid).toBe('S1')
    expect(opAdd).toHaveBeenCalledTimes(2)
    expect(opRollback).not.toHaveBeenCalled()
  })

  it('surfaces the bridge error message on opBegin failure', async () => {
    setAiadra({
      opBegin: async () => errEnv('not an AIADRA workspace'),
      opAdd: async () => okEnv({}),
      opSimulate: async () => okEnv({ report: { valid: true } }),
      opCommit: async () => okEnv({}),
      opRollback: async () => okEnv({}),
    })
    const backend = createBridgeAuthoringBackend('WS')
    await expect(backend.begin([{ kind: 'create_part', params: {} }])).rejects.toThrow(
      'not an AIADRA workspace',
    )
  })
})
