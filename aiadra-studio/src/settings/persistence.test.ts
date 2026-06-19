import { describe, expect, it } from 'vitest'
import { createPersistence, type SettingsBackend } from './persistence'
import type { PersistedSettings } from './persisted'

function fakeBackend() {
  const saved: PersistedSettings[] = []
  let stored: PersistedSettings | null = null
  const backend: SettingsBackend = {
    async load() {
      return stored
    },
    async save(b) {
      saved.push(b)
      stored = b
    },
  }
  return { backend, saved, prime: (b: PersistedSettings | null) => { stored = b } }
}

/** A scheduler we fire by hand — exposes the debounce without real timers. */
function manualScheduler() {
  let pending: (() => void) | null = null
  return {
    schedule: (fn: () => void) => {
      pending = fn
      return () => {
        pending = null
      }
    },
    fire: () => {
      const p = pending
      pending = null
      p?.()
    },
  }
}

const blob = (a: number): PersistedSettings => ({ settings_version: 1, values: { a } })

describe('settings persistence', () => {
  it('debounces a burst into a single coalesced write (last value wins)', async () => {
    const { backend, saved } = fakeBackend()
    const sch = manualScheduler()
    const p = createPersistence({ backend, schedule: sch.schedule })
    p.save(blob(1))
    p.save(blob(2))
    p.save(blob(3))
    expect(saved).toHaveLength(0) // nothing written yet — debounced
    sch.fire()
    await Promise.resolve()
    expect(saved).toHaveLength(1)
    expect(saved[0].values.a).toBe(3)
  })

  it('flush forces a pending write immediately', async () => {
    const { backend, saved } = fakeBackend()
    const sch = manualScheduler()
    const p = createPersistence({ backend, schedule: sch.schedule })
    p.save(blob(9))
    await p.flush()
    expect(saved).toHaveLength(1)
    expect(saved[0].values.a).toBe(9)
  })

  it('load round-trips from the backend', async () => {
    const f = fakeBackend()
    f.prime(blob(5))
    const p = createPersistence({ backend: f.backend })
    expect((await p.load())?.values.a).toBe(5)
  })
})
