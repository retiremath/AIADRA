import { describe, it, expect } from 'vitest'
import { createRecentsRegistry, RECENTS_LIMIT, type RecentsIo } from './recents'

function fakeIo(initial: string | null = null): RecentsIo & { file: string | null } {
  let n = 0
  let t = 0
  const io = {
    file: initial,
    load: () => io.file,
    save: (c: string) => {
      io.file = c
    },
    now: () => new Date(1700000000000 + ++t * 1000).toISOString(),
    mintId: () => `rec_${++n}`,
  }
  return io
}

describe('recents registry (D-H4 repinned — Codex6 B3)', () => {
  it('records, dedupes by canonical path (stable recentId), and bumps LRU', () => {
    const io = fakeIo()
    const r = createRecentsRegistry(io)
    const a = r.record('C:/ws/alpha', 'alpha')
    r.record('C:/ws/beta', 'beta')
    const a2 = r.record('C:/ws/alpha', 'alpha') // reopen — same entry, bumped
    expect(a2.recentId).toBe(a.recentId)
    expect(r.views().map((v) => v.name)).toEqual(['alpha', 'beta'])
  })

  it('the renderer view NEVER carries the canonical path', () => {
    const r = createRecentsRegistry(fakeIo())
    r.record('C:/secret/place', 'ws')
    const view = r.views()[0] as Record<string, unknown>
    expect(view.canonicalPath).toBeUndefined()
    expect(Object.keys(view).sort()).toEqual(['lastOpened', 'name', 'recentId'])
  })

  it('bounds the list (LRU eviction beyond the cap)', () => {
    const r = createRecentsRegistry(fakeIo())
    for (let i = 0; i < RECENTS_LIMIT + 3; i++) r.record(`C:/ws/${i}`, `ws${i}`)
    const names = r.views().map((v) => v.name)
    expect(names).toHaveLength(RECENTS_LIMIT)
    expect(names[0]).toBe(`ws${RECENTS_LIMIT + 2}`) // newest first
    expect(names).not.toContain('ws0') // oldest evicted
  })

  it('remove and clear persist; get() resolves the main-side path', () => {
    const io = fakeIo()
    const r = createRecentsRegistry(io)
    const a = r.record('C:/ws/alpha', 'alpha')
    r.record('C:/ws/beta', 'beta')
    expect(r.get(a.recentId)?.canonicalPath).toBe('C:/ws/alpha')
    r.remove(a.recentId)
    expect(r.get(a.recentId)).toBeNull()
    r.clear()
    expect(r.views()).toEqual([])
    // persisted: a fresh registry over the same file sees the cleared state
    expect(createRecentsRegistry(io).views()).toEqual([])
  })

  it('is load-tolerant: corrupt or wrong-version files yield an empty registry', () => {
    expect(createRecentsRegistry(fakeIo('not json {{{')).views()).toEqual([])
    expect(
      createRecentsRegistry(fakeIo(JSON.stringify({ version: 99, entries: [{}] }))).views(),
    ).toEqual([])
    expect(
      createRecentsRegistry(
        fakeIo(JSON.stringify({ version: 1, entries: [{ recentId: 'x' }, null] })),
      ).views(),
    ).toEqual([]) // malformed entries filtered
  })

  it('round-trips a valid file', () => {
    const io = fakeIo()
    createRecentsRegistry(io).record('C:/ws/alpha', 'alpha')
    const again = createRecentsRegistry(io)
    expect(again.views().map((v) => v.name)).toEqual(['alpha'])
    expect(again.get(again.views()[0].recentId)?.canonicalPath).toBe('C:/ws/alpha')
  })
})
