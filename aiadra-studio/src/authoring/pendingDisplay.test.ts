import { describe, it, expect, vi } from 'vitest'
import { createPendingDisplayCoordinator } from './pendingDisplay'
import { authoringStartRefusal, createPartContextStore } from './partContext'
import type { DisplaySource } from '../display/displaySource'

const SRC = { kind: 'probe' } as unknown as DisplaySource
const RAW = (number: string) => ({
  sidecar: { object: { type: 'Part', number, name: number, uuid: `u-${number}` }, feature: [] },
})

/** Wire the coordinator into a partContext transition exactly like the
 *  Workbench does (pre-mount: installDisplay awaits the deferred promise). */
function adoptPreMount(
  store: ReturnType<typeof createPartContextStore>,
  coord: ReturnType<typeof createPendingDisplayCoordinator>,
  partNumber: string,
) {
  return store.setPart('ws-1', partNumber, {
    fetchInspect: async () => RAW(partNumber),
    installDisplay: (stillCurrent) => coord.defer(SRC, stillCurrent),
  })
}

describe('the pre-mount display coordinator (Codex5 B1.1 — the deferral IS the join)', () => {
  it('inspect resolves BEFORE mount: the context stays LOADING; mount + install success → ready', async () => {
    const store = createPartContextStore()
    const coord = createPendingDisplayCoordinator()
    const done = adoptPreMount(store, coord, 'P-1')
    await new Promise((res) => setTimeout(res, 0)) // inspect has fully settled
    expect(store.getSnapshot().inspection.status).toBe('loading') // queued ≠ installed
    // The viewport mounts and drains the queue.
    const install = vi.fn(async () => {})
    await coord.drain(install)
    await done
    expect(install).toHaveBeenCalledWith(SRC, expect.any(Function))
    expect(store.getSnapshot().inspection.status).toBe('ready')
  })

  it('mount + install FAILURE → fail-closed error; ready NEVER appears in the history', async () => {
    const store = createPartContextStore()
    const coord = createPendingDisplayCoordinator()
    const history: string[] = []
    store.subscribe(() => history.push(store.getSnapshot().inspection.status))
    const done = adoptPreMount(store, coord, 'P-1')
    await new Promise((res) => setTimeout(res, 0))
    await coord.drain(async () => {
      throw new Error('WebGL context lost')
    })
    await done
    expect(store.getSnapshot().inspection.status).toBe('error')
    expect(history).not.toContain('ready')
  })

  it('clear() before mount: the stale source NEVER installs and the old transition promise SETTLES', async () => {
    const store = createPartContextStore()
    const coord = createPendingDisplayCoordinator()
    const done = adoptPreMount(store, coord, 'P-1')
    store.clear() // e.g. back to Home before the viewport ever mounted
    coord.cancel() // the Workbench's clearContext does this
    await done // the old transition promise settled — no hang
    expect(store.getSnapshot().inspection.status).toBe('idle')
    const install = vi.fn(async () => {})
    await coord.drain(install)
    expect(install).not.toHaveBeenCalled() // nothing queued anymore
  })

  it('a SUPERSEDING adoption settles the older deferred work; only the newest installs on drain', async () => {
    const store = createPartContextStore()
    const coord = createPendingDisplayCoordinator()
    const first = adoptPreMount(store, coord, 'P-A')
    const second = adoptPreMount(store, coord, 'P-B') // supersedes A pre-mount
    await first // A's promise settled by the supersession — no hang
    const installed: string[] = []
    await coord.drain(async () => {
      installed.push(store.getSnapshot().partNumber ?? '?')
    })
    await second
    expect(installed).toEqual(['P-B']) // only B installed
    const s = store.getSnapshot()
    expect(s.partNumber).toBe('P-B')
    expect(s.inspection.status).toBe('ready')
  })

  it('a drained entry whose transition lost its generation resolves WITHOUT installing', async () => {
    const store = createPartContextStore()
    const coord = createPendingDisplayCoordinator()
    const done = adoptPreMount(store, coord, 'P-1')
    store.clear() // generation moved on, but the queue was not cancelled
    const install = vi.fn(async () => {})
    await coord.drain(install) // stillCurrent() is false → settle, no install
    await done
    expect(install).not.toHaveBeenCalled()
  })
})

describe('authoringStartRefusal (Codex5 B1.2 — ONE targeted-non-ready policy)', () => {
  it('allows idle/no-target (the dev fresh-Part flow) and a READY target', async () => {
    const store = createPartContextStore()
    expect(authoringStartRefusal(store.getSnapshot())).toBeNull() // idle
    await store.setPart('ws-1', 'P-1', { fetchInspect: async () => RAW('P-1') })
    expect(authoringStartRefusal(store.getSnapshot())).toBeNull() // ready
  })

  it('refuses a targeted LOADING and a targeted ERROR context — Sketch/Extrude/AI/New all read this one policy', async () => {
    const store = createPartContextStore()
    const p = store.setPart('ws-1', 'P-1', { fetchInspect: async () => RAW('P-1') })
    expect(authoringStartRefusal(store.getSnapshot())).toMatch(/not ready/) // loading
    await p
    await store.setPart('ws-1', 'P-2', {
      fetchInspect: async () => {
        throw new Error('inspect failed')
      },
    })
    expect(store.getSnapshot().inspection.status).toBe('error')
    expect(authoringStartRefusal(store.getSnapshot())).toMatch(/not ready/) // targeted error
    // Navigation recovery stays possible: the policy is an AUTHORING gate only
    // — a new adoption (the recovery path) is not its concern and proceeds.
    await store.setPart('ws-1', 'P-3', { fetchInspect: async () => RAW('P-3') })
    expect(authoringStartRefusal(store.getSnapshot())).toBeNull()
  })
})
