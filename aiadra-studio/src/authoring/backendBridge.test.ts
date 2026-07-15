import { describe, it, expect, vi, afterEach } from 'vitest'
import { createBridgeAuthoringBackend } from './backendBridge'
import { opRef } from './backend'

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
      opBegin: async () => okEnv({ operationSessionId: 'S1', createdFeatureIds: [] }),
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
    const opAdd = vi.fn(async () => okEnv({ createdFeatureIds: ['feat_0001'] }))
    const opRollback = vi.fn(async () => okEnv({ rolled_back: true }))
    setAiadra({
      opBegin: async () => okEnv({ operationSessionId: 'S1', createdFeatureIds: [] }),
      opAdd,
      opSimulate: async () => okEnv({ report: { valid: true } }),
      opCommit: async () => okEnv({}),
      opRollback,
    })
    const backend = createBridgeAuthoringBackend('WS')
    const begun = await backend.begin([
      { kind: 'create_part', params: {} },
      { kind: 'mechanical.add_sketch_feature', params: {} },
      { kind: 'mechanical.add_extrude_feature', params: {} },
    ])
    expect(begun.sessionId).toBe('S1')
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

describe('the engine-owned id handshake (S2; arc 20260714-3 Codex1 B1)', () => {
  it('returns each op\'s ENGINE-minted ids and resolves $fromOp against them — the wire never sees an alias', async () => {
    const sent: Array<Record<string, unknown>> = []
    let addCalls = 0
    setAiadra({
      opBegin: async () => okEnv({ operationSessionId: 'S1', createdFeatureIds: [] }),
      opAdd: async (_sid: string, _kind: string, params: Record<string, unknown>) => {
        sent.push(params)
        // The ENGINE mints ids the renderer could not have predicted.
        return okEnv({ createdFeatureIds: [['feat_0017', 'feat_0018'][addCalls++]] })
      },
      opSimulate: async () => okEnv({ report: { valid: true } }),
      opCommit: async () => okEnv({}),
      opRollback: async () => okEnv({ rolled_back: true }),
    })
    const backend = createBridgeAuthoringBackend('WS')
    const begun = await backend.begin([
      { kind: 'create_part', params: {} },
      { kind: 'mechanical.add_sketch_feature', params: { part_number: 'P-1' } },
      {
        kind: 'mechanical.add_extrude_feature',
        params: { part_number: 'P-1', sketch_feature_id: opRef(1), depth_mm: 5 },
      },
    ])
    expect(begun.createdFeatureIds).toEqual([[], ['feat_0017'], ['feat_0018']])
    // The extrude op crossed IPC with the REAL engine id, not the alias.
    expect(sent[1].sketch_feature_id).toBe('feat_0017')
  })

  it('B3: a malformed FIRST response (opBegin) rolls the begun session back — never an orphan', async () => {
    const opRollback = vi.fn(async () => okEnv({ rolled_back: true }))
    setAiadra({
      // A session EXISTS but its ids payload is malformed (e.g. a bad double).
      opBegin: async () => okEnv({ operationSessionId: 'S1' }),
      opAdd: async () => okEnv({ createdFeatureIds: [] }),
      opSimulate: async () => okEnv({ report: { valid: true } }),
      opCommit: async () => okEnv({}),
      opRollback,
    })
    const backend = createBridgeAuthoringBackend('WS')
    await expect(backend.begin([{ kind: 'create_part', params: {} }])).rejects.toThrow(
      /createdFeatureIds/,
    )
    expect(opRollback).toHaveBeenCalledWith('S1')
  })

  it('FAILS LOUD (and rolls back) when a response is missing the createdFeatureIds array', async () => {
    const opRollback = vi.fn(async () => okEnv({ rolled_back: true }))
    setAiadra({
      opBegin: async () => okEnv({ operationSessionId: 'S1', createdFeatureIds: [] }),
      opAdd: async () => okEnv({ session_id: 'S1' }), // the pre-S2 response shape
      opSimulate: async () => okEnv({ report: { valid: true } }),
      opCommit: async () => okEnv({}),
      opRollback,
    })
    const backend = createBridgeAuthoringBackend('WS')
    await expect(
      backend.begin([
        { kind: 'create_part', params: {} },
        { kind: 'mechanical.add_sketch_feature', params: {} },
      ]),
    ).rejects.toThrow(/createdFeatureIds/)
    expect(opRollback).toHaveBeenCalledWith('S1')
  })

  it('FAILS LOUD on alias cardinality ≠ 1 (referencing an op that minted nothing)', async () => {
    const opRollback = vi.fn(async () => okEnv({ rolled_back: true }))
    setAiadra({
      opBegin: async () => okEnv({ operationSessionId: 'S1', createdFeatureIds: [] }),
      opAdd: async () => okEnv({ createdFeatureIds: [] }),
      opSimulate: async () => okEnv({ report: { valid: true } }),
      opCommit: async () => okEnv({}),
      opRollback,
    })
    const backend = createBridgeAuthoringBackend('WS')
    await expect(
      backend.begin([
        { kind: 'create_part', params: {} },
        { kind: 'mechanical.add_extrude_feature', params: { sketch_feature_id: opRef(0) } },
      ]),
    ).rejects.toThrow(/created 0 features/)
    expect(opRollback).toHaveBeenCalledWith('S1')
  })

  it('FAILS LOUD on a forward $fromOp reference (never a silent guess)', async () => {
    const opRollback = vi.fn(async () => okEnv({ rolled_back: true }))
    setAiadra({
      opBegin: async () => okEnv({ operationSessionId: 'S1', createdFeatureIds: [] }),
      opAdd: async () => okEnv({ createdFeatureIds: ['feat_0001'] }),
      opSimulate: async () => okEnv({ report: { valid: true } }),
      opCommit: async () => okEnv({}),
      opRollback,
    })
    const backend = createBridgeAuthoringBackend('WS')
    await expect(
      backend.begin([
        { kind: 'create_part', params: {} },
        { kind: 'mechanical.add_extrude_feature', params: { sketch_feature_id: opRef(5) } },
      ]),
    ).rejects.toThrow(/EARLIER op/)
    expect(opRollback).toHaveBeenCalledWith('S1')
  })

  it('an alias in op 0 fails loud BEFORE anything crosses IPC (no session to leak)', async () => {
    const opBegin = vi.fn()
    setAiadra({
      opBegin,
      opAdd: async () => okEnv({ createdFeatureIds: [] }),
      opSimulate: async () => okEnv({ report: { valid: true } }),
      opCommit: async () => okEnv({}),
      opRollback: async () => okEnv({ rolled_back: true }),
    })
    const backend = createBridgeAuthoringBackend('WS')
    await expect(
      backend.begin([{ kind: 'mechanical.add_extrude_feature', params: { sketch_feature_id: opRef(0) } }]),
    ).rejects.toThrow(/EARLIER op/)
    expect(opBegin).not.toHaveBeenCalled()
  })
})
