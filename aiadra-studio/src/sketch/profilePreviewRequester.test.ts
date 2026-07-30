import { describe, it, expect, vi } from 'vitest'
import { createPreviewRequester, isLatest, type PreviewResult } from './profilePreviewRequester'

const ok = (tag: string): PreviewResult =>
  ({ preview: { owner: { candidate_key: tag } }, refusal: null }) as unknown as PreviewResult

/** A run() whose completions the test controls, one deferred promise per call. */
function deferredRunner() {
  const calls: string[] = []
  const resolvers: ((r: PreviewResult) => void)[] = []
  const rejecters: ((e: unknown) => void)[] = []
  const run = (req: string): Promise<PreviewResult> => {
    calls.push(req)
    return new Promise<PreviewResult>((res, rej) => {
      resolvers.push(res)
      rejecters.push(rej)
    })
  }
  return { calls, resolvers, rejecters, run }
}

const flush = () => new Promise((r) => setTimeout(r, 0))

describe('only the newest reply may paint', () => {
  it('isLatest is the whole rule', () => {
    expect(isLatest(3, 3)).toBe(true)
    expect(isLatest(2, 3)).toBe(false)
  })

  it('a stale reply is DROPPED even when it lands last', async () => {
    const d = deferredRunner()
    const applied: PreviewResult[] = []
    const r = createPreviewRequester<string>({ run: d.run, apply: (x) => applied.push(x) })

    r.request('a')
    await flush()
    // 'b' coalesces behind the in-flight 'a'
    r.request('b')
    // now 'a' settles, which releases 'b'
    d.resolvers[0](ok('a'))
    await flush()
    d.resolvers[1](ok('b'))
    await flush()

    expect(applied.map((x) => (x.preview as { owner: { candidate_key: string } }).owner.candidate_key))
      .toEqual(['a', 'b'])
  })

  it('an out-of-order reply from a superseded request never applies', async () => {
    const d = deferredRunner()
    const applied: PreviewResult[] = []
    const r = createPreviewRequester<string>({ run: d.run, apply: (x) => applied.push(x) })

    r.request('a')
    await flush()
    d.resolvers[0](ok('a'))
    await flush()
    applied.length = 0

    r.request('b')
    await flush()
    // a LATE duplicate resolution of the first request: already stale
    d.resolvers[0](ok('a-late'))
    await flush()
    expect(applied).toHaveLength(0)
  })
})

describe('requests coalesce instead of queueing', () => {
  it('a burst of pointer moves produces ONE follow-up, carrying the LAST state', async () => {
    const d = deferredRunner()
    const r = createPreviewRequester<string>({ run: d.run, apply: () => {} })

    r.request('m1')
    await flush()
    for (const m of ['m2', 'm3', 'm4', 'm5']) r.request(m)
    expect(d.calls).toEqual(['m1']) // nothing queued behind the wire

    d.resolvers[0](ok('m1'))
    await flush()
    // exactly one follow-up, and it is the FINAL state — not m2
    expect(d.calls).toEqual(['m1', 'm5'])
  })

  it('the final state is never dropped', async () => {
    const d = deferredRunner()
    const applied: string[] = []
    const r = createPreviewRequester<string>({
      run: d.run,
      apply: (x) => applied.push((x.preview as { owner: { candidate_key: string } }).owner.candidate_key),
    })
    r.request('first')
    await flush()
    r.request('final')
    d.resolvers[0](ok('first'))
    await flush()
    d.resolvers[1](ok('final'))
    await flush()
    expect(applied.at(-1)).toBe('final')
  })

  it('busy reports the in-flight state', async () => {
    const d = deferredRunner()
    const r = createPreviewRequester<string>({ run: d.run, apply: () => {} })
    expect(r.isBusy()).toBe(false)
    r.request('a')
    expect(r.isBusy()).toBe(true)
    d.resolvers[0](ok('a'))
    await flush()
    expect(r.isBusy()).toBe(false)
  })
})

describe('refusals are normal; only transport is exceptional', () => {
  it('an engine refusal goes through apply, NOT onError', async () => {
    const d = deferredRunner()
    const applied: PreviewResult[] = []
    const onError = vi.fn()
    const r = createPreviewRequester<string>({ run: d.run, apply: (x) => applied.push(x), onError })

    r.request('a')
    await flush()
    d.resolvers[0]({ preview: null, refusal: { message: 'segment collapsed' } })
    await flush()

    expect(applied[0].refusal?.message).toBe('segment collapsed')
    expect(onError).not.toHaveBeenCalled()
  })

  it('a transport failure reaches onError and never applies', async () => {
    const d = deferredRunner()
    const applied: PreviewResult[] = []
    const onError = vi.fn()
    const r = createPreviewRequester<string>({ run: d.run, apply: (x) => applied.push(x), onError })

    r.request('a')
    await flush()
    d.rejecters[0](new Error('bridge exited'))
    await flush()

    expect(applied).toHaveLength(0)
    expect(onError).toHaveBeenCalledOnce()
  })

  it('a failure still releases the queue', async () => {
    const d = deferredRunner()
    const r = createPreviewRequester<string>({ run: d.run, apply: () => {}, onError: () => {} })
    r.request('a')
    await flush()
    r.request('b')
    d.rejecters[0](new Error('boom'))
    await flush()
    expect(d.calls).toEqual(['a', 'b'])
  })
})

describe('cancel', () => {
  it('nothing outstanding may apply after cancel', async () => {
    const d = deferredRunner()
    const applied: PreviewResult[] = []
    const r = createPreviewRequester<string>({ run: d.run, apply: (x) => applied.push(x) })

    r.request('a')
    await flush()
    r.cancel()
    d.resolvers[0](ok('a'))
    await flush()
    expect(applied).toHaveLength(0)
  })

  it('cancel drops a queued follow-up rather than firing it', async () => {
    const d = deferredRunner()
    const r = createPreviewRequester<string>({ run: d.run, apply: () => {} })
    r.request('a')
    await flush()
    r.request('b')
    r.cancel()
    d.resolvers[0](ok('a'))
    await flush()
    expect(d.calls).toEqual(['a'])
  })

  it('the requester is reusable after cancel — closing and reopening a session works', async () => {
    const d = deferredRunner()
    const applied: PreviewResult[] = []
    const r = createPreviewRequester<string>({ run: d.run, apply: (x) => applied.push(x) })
    r.request('a')
    await flush()
    r.cancel()
    r.request('b')
    await flush()
    d.resolvers[1](ok('b'))
    await flush()
    expect(applied).toHaveLength(1)
  })
})
