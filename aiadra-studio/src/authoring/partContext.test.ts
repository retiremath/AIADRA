import { describe, it, expect, vi } from 'vitest'
import {
  authoringFacts,
  captureAuthoringTarget,
  captureSelectorTarget,
  createPartContextStore,
  guardTerminalTarget,
  type InspectFetcher,
} from './partContext'

const io = (fetch: InspectFetcher, installDisplay?: (ok: () => boolean) => Promise<void>) => ({
  fetchInspect: fetch,
  installDisplay,
})

const RAW = (number: string, features: unknown[] = []) => ({
  sidecar: {
    object: { type: 'Part', number, name: `Part ${number}`, uuid: `u-${number}` },
    feature: features,
  },
})

const EXTRUDE_PAIR = [
  {
    id: 'feat_0001',
    feature_type: 'sketch',
    engine: 'mechanical',
    adapter_schema_version: '0.1.8',
    adapter_payload: {
      primitives: [{ type: 'rectangle', id: 'skp_0001', x_mm: 0, y_mm: 0, width_mm: 5, height_mm: 5 }],
    },
  },
  {
    id: 'feat_0002',
    feature_type: 'extrude',
    engine: 'mechanical',
    adapter_schema_version: '0.1.8',
    depends_on_feature_ids: ['feat_0001'],
    adapter_payload: { sketch_feature_id: 'feat_0001', direction: 'normal+' },
  },
]

describe('partContext (S2 Codex1 B2 — ONE generation-owned Part authority)', () => {
  it('setPart: loading → ready; eligibility comes from INSPECTED state (B3 mirror)', async () => {
    const store = createPartContextStore()
    const p = store.setPart('ws-1', 'P-1', io(async () => RAW('P-1')))
    expect(store.getSnapshot().inspection.status).toBe('loading')
    expect(authoringFacts(store.getSnapshot()).canExtrude).toBe(false) // fail closed while loading
    await p
    const s = store.getSnapshot()
    expect(s.inspection.status).toBe('ready')
    expect(authoringFacts(s).canExtrude).toBe(true) // empty Part: extrude eligible

    await store.refresh(io(async () => RAW('P-1', EXTRUDE_PAIR)))
    expect(authoringFacts(store.getSnapshot()).canExtrude).toBe(false) // one-base rule mirror
  })

  it('GENERATION discipline: a stale in-flight load NEVER installs', async () => {
    const store = createPartContextStore()
    let releaseA!: () => void
    const slowA = new Promise<void>((res) => (releaseA = res))
    const first = store.setPart('ws-1', 'P-A', io(async () => {
      await slowA
      return RAW('P-A')
    }))
    // A newer context arrives while A is still fetching.
    await store.setPart('ws-1', 'P-B', io(async () => RAW('P-B')))
    releaseA()
    await first
    const s = store.getSnapshot()
    expect(s.partNumber).toBe('P-B')
    expect(s.inspection.status).toBe('ready')
    expect(s.inspection.status === 'ready' && s.inspection.part.number).toBe('P-B') // A landed in the void
  })

  it('a decode failure is a fail-closed ERROR state (no tree, no eligibility)', async () => {
    const store = createPartContextStore()
    await store.setPart('ws-1', 'P-1', io(async () => ({ sidecar: { object: { type: 'Requirement' } } })))
    const s = store.getSnapshot()
    expect(s.inspection.status).toBe('error')
    expect(s.inspection.status === 'error' && s.inspection.message).toMatch(/not a Part/)
    expect(authoringFacts(s).readyPart).toBeNull()
  })

  it('a view for the WRONG Part is an error, never silently adopted', async () => {
    const store = createPartContextStore()
    await store.setPart('ws-1', 'P-1', io(async () => RAW('P-2')))
    const s = store.getSnapshot()
    expect(s.inspection.status).toBe('error')
    expect(s.inspection.status === 'error' && s.inspection.message).toMatch(/expected P-1/)
  })

  it('clear() invalidates an in-flight load (workspace switch)', async () => {
    const store = createPartContextStore()
    let release!: () => void
    const slow = new Promise<void>((res) => (release = res))
    const p = store.setPart('ws-1', 'P-1', io(async () => {
      await slow
      return RAW('P-1')
    }))
    store.clear()
    release()
    await p
    const s = store.getSnapshot()
    expect(s.partNumber).toBeNull()
    expect(s.inspection.status).toBe('idle') // the late result never installed
  })
})

describe('the ONE canonical Part transition (Codex3 B2)', () => {
  it('A-slow/B-fast: display, context, and row label ALL end on B — stale A publishes nothing', async () => {
    const store = createPartContextStore()
    const installed: string[] = []
    let releaseA!: () => void
    const slowA = new Promise<void>((res) => (releaseA = res))

    // Part A: BOTH halves are slow (display + inspect resolve after B adopts).
    const first = store.setPart(
      'ws-1',
      'P-A',
      io(
        async () => {
          await slowA
          return RAW('P-A')
        },
        async (stillCurrent) => {
          await slowA
          if (stillCurrent()) installed.push('A') // must never run
        },
      ),
    )
    // The generation advanced SYNCHRONOUSLY — A is already unauthorable.
    expect(store.getSnapshot().inspection.status).toBe('loading')
    expect(authoringFacts(store.getSnapshot()).canExtrude).toBe(false)

    // Part B adopts while A is still in flight.
    await store.setPart(
      'ws-1',
      'P-B',
      io(
        async () => RAW('P-B'),
        async (stillCurrent) => {
          if (stillCurrent()) installed.push('B')
        },
      ),
    )
    releaseA()
    await first

    const s = store.getSnapshot()
    expect(installed).toEqual(['B']) // A's display never installed
    expect(s.partNumber).toBe('P-B') // the loaded-row label (pc.partNumber) is B
    expect(s.inspection.status === 'ready' && s.inspection.part.number).toBe('P-B')
  })

  it('a display failure is the SAME fail-closed error state as an inspect failure', async () => {
    const store = createPartContextStore()
    await store.setPart(
      'ws-1',
      'P-1',
      io(
        async () => RAW('P-1'),
        async () => {
          throw new Error('display fetch failed')
        },
      ),
    )
    const s = store.getSnapshot()
    expect(s.inspection.status).toBe('error')
    expect(authoringFacts(s).canExtrude).toBe(false)
  })

  it('installDisplay runs INSIDE the transition (called with a live stillCurrent)', async () => {
    const store = createPartContextStore()
    const install = vi.fn(async (ok: () => boolean) => {
      expect(ok()).toBe(true)
    })
    await store.setPart('ws-1', 'P-1', io(async () => RAW('P-1'), install))
    expect(install).toHaveBeenCalledTimes(1)
    expect(store.getSnapshot().inspection.status).toBe('ready')
  })
})

describe('the transition JOIN + boundary (Codex4 B1)', () => {
  it('inspect-fast/display-DEFERRED: the state stays LOADING (unauthorable) until display succeeds — only then ready', async () => {
    const store = createPartContextStore()
    let releaseDisplay!: () => void
    const slowDisplay = new Promise<void>((res) => (releaseDisplay = res))
    const done = store.setPart(
      'ws-1',
      'P-1',
      io(
        async () => RAW('P-1'), // inspect resolves immediately
        async () => {
          await slowDisplay // display is still fetching
        },
      ),
    )
    // Let the fast inspect half fully settle — readiness must STILL wait.
    await new Promise((res) => setTimeout(res, 0))
    expect(store.getSnapshot().inspection.status).toBe('loading')
    expect(authoringFacts(store.getSnapshot()).canExtrude).toBe(false) // no authoring interval
    releaseDisplay()
    await done
    expect(store.getSnapshot().inspection.status).toBe('ready')
  })

  it('display REJECTS after inspect resolved: loading → error, NEVER briefly ready', async () => {
    const store = createPartContextStore()
    const history: string[] = []
    store.subscribe(() => history.push(store.getSnapshot().inspection.status))
    let rejectDisplay!: (e: Error) => void
    const failing = new Promise<void>((_res, rej) => (rejectDisplay = rej))
    const done = store.setPart(
      'ws-1',
      'P-1',
      io(
        async () => RAW('P-1'),
        async () => failing,
      ),
    )
    await new Promise((res) => setTimeout(res, 0)) // inspect settles first
    rejectDisplay(new Error('display fetch failed'))
    await done
    expect(store.getSnapshot().inspection.status).toBe('error')
    expect(history).not.toContain('ready') // the unsafe interval never existed
  })

  it('onTransitionStart runs SYNCHRONOUSLY at the boundary — Part-local selections cannot alias across Parts with the same feat_0001', async () => {
    const store = createPartContextStore()
    // A stand-in for the Workbench's Part-scoped selections (canonical +
    // selected sketch) — both Parts legitimately contain feat_0001.
    let selectedSketch: string | null = null
    const clears: string[] = []
    const adopt = (num: string) =>
      store.setPart('ws-1', num, {
        onTransitionStart: () => {
          selectedSketch = null
          clears.push(`clear-before-${num}`)
        },
        fetchInspect: async () => RAW(num, EXTRUDE_PAIR.slice(0, 1)), // feat_0001 in BOTH Parts
      })
    await adopt('P-A')
    selectedSketch = 'feat_0001' // the user selects A's sketch
    const second = adopt('P-B')
    // The clear happened SYNCHRONOUSLY at B's transition start — before any
    // async work could observe A's selection against B's identical id.
    expect(selectedSketch).toBeNull()
    expect(clears).toEqual(['clear-before-P-A', 'clear-before-P-B'])
    await second
    expect(store.getSnapshot().inspection.status === 'ready').toBe(true)
  })

  it('B1.5: a transition’s stillCurrent goes FALSE after clear()/re-adoption — a deferred pre-mount display can never install stale', async () => {
    const store = createPartContextStore()
    let captured: (() => boolean) | null = null
    await store.setPart(
      'ws-1',
      'P-1',
      io(async () => RAW('P-1'), async (stillCurrent) => {
        captured = stillCurrent // the pending-display path stores this
      }),
    )
    expect(captured!()).toBe(true) // still the current transition
    store.clear() // workspace switch before the viewport mounted
    expect(captured!()).toBe(false) // the deferred install is now a no-op
  })
})

describe('captureSelectorTarget (R4 D-R8 — generation-bound, fail-closed capture)', () => {
  const FACTS = {
    edgeKinds: new Map([['e:sharp', 'sharp'], ['e:tang', 'tangent']]),
    faceIds: new Set(['f:cap']),
      planarFaceIds: new Set<string>(),
      sketchFrames: new Map(),
  }
  const ready = async () => {
    const store = createPartContextStore()
    await store.setPart('ws-1', 'P-1', { fetchInspect: async () => RAW('P-1', EXTRUDE_PAIR) })
    store.publishSelectorFacts(store.getSnapshot().generation, FACTS)
    return store
  }

  it('captures {tuple, selector, fact} for a SHARP edge on the current display', async () => {
    const store = await ready()
    const cap = captureSelectorTarget(store.getSnapshot(), { kind: 'edge', id: 'e:sharp' }, 'sharp-edge')
    expect(cap).toMatchObject({
      selector: { kind: 'edge', id: 'e:sharp' },
      edgeKind: 'sharp',
      target: { workspaceId: 'ws-1', partNumber: 'P-1' },
    })
  })

  it('Codex3-B1.1 (defense in depth): the capture refuses on a Part with an existing referencing feature', async () => {
    const WITH_FILLET = [...EXTRUDE_PAIR,
      { id: 'feat_0003', feature_type: 'fillet', engine: 'mechanical', adapter_schema_version: '0.1.8',
        adapter_payload: {} }]
    const store = createPartContextStore()
    await store.setPart('ws-1', 'P-1', { fetchInspect: async () => RAW('P-1', WITH_FILLET) })
    store.publishSelectorFacts(store.getSnapshot().generation, FACTS)
    expect(captureSelectorTarget(store.getSnapshot(), { kind: 'edge', id: 'e:sharp' }, 'sharp-edge')).toMatch(
      /stacked referencing features/,
    )
  })

  it('refuses: not ready · revolve base · absent id · non-sharp · facts not yet published', async () => {
    const idle = createPartContextStore()
    expect(captureSelectorTarget(idle.getSnapshot(), { kind: 'edge', id: 'e' }, 'sharp-edge')).toMatch(/not ready/)
    const store = await ready()
    expect(captureSelectorTarget(store.getSnapshot(), { kind: 'edge', id: 'nope' }, 'sharp-edge')).toMatch(/stale selection/)
    expect(captureSelectorTarget(store.getSnapshot(), { kind: 'edge', id: 'e:tang' }, 'sharp-edge')).toMatch(/tangent/)
    expect(captureSelectorTarget(store.getSnapshot(), null, 'sharp-edge')).toMatch(/select an edge/)
    // a NEW transition kills the facts — the capture refuses until re-publish
    const p = store.refresh({ fetchInspect: async () => RAW('P-1', EXTRUDE_PAIR) })
    expect(store.getSnapshot().selectorFacts).toBeNull()
    await p
    expect(captureSelectorTarget(store.getSnapshot(), { kind: 'edge', id: 'e:sharp' }, 'sharp-edge')).toMatch(/display has not installed/)
  })

  it('stale facts publication is DROPPED (generation moved on)', async () => {
    const store = await ready()
    const oldGen = store.getSnapshot().generation
    await store.refresh({ fetchInspect: async () => RAW('P-1', EXTRUDE_PAIR) })
    store.publishSelectorFacts(oldGen, FACTS) // a late publish from the old display
    expect(store.getSnapshot().selectorFacts).toBeNull()
  })
})

describe('guardTerminalTarget (Codex3 B2 / Codex4 B1.4 — the FULL authority tuple)', () => {
  const capture = (s: ReturnType<ReturnType<typeof createPartContextStore>['getSnapshot']>) =>
    captureAuthoringTarget(s)

  it('the EXACT captured tuple passes against the same ready context', async () => {
    const store = createPartContextStore()
    await store.setPart('ws-1', 'P-1', io(async () => RAW('P-1')))
    const tuple = capture(store.getSnapshot())
    expect(tuple).toMatchObject({ workspaceId: 'ws-1', partNumber: 'P-1' })
    expect(guardTerminalTarget(tuple, store.getSnapshot())).toBeNull()
  })

  it('refuses the SAME Part number in a DIFFERENT workspace', async () => {
    const a = createPartContextStore()
    await a.setPart('ws-A', 'P-1', io(async () => RAW('P-1')))
    const captured = capture(a.getSnapshot())!
    const b = createPartContextStore()
    await b.setPart('ws-B', 'P-1', io(async () => RAW('P-1')))
    expect(guardTerminalTarget(captured, b.getSnapshot())).toMatch(/context changed/)
  })

  it('refuses a NEWER generation of the same Part (a re-adoption happened underneath)', async () => {
    const store = createPartContextStore()
    await store.setPart('ws-1', 'P-1', io(async () => RAW('P-1')))
    const captured = capture(store.getSnapshot())!
    await store.refresh(io(async () => RAW('P-1'))) // e.g. another surface committed
    expect(guardTerminalTarget(captured, store.getSnapshot())).toMatch(/context changed/)
  })

  it('refuses while LOADING; captureAuthoringTarget refuses to capture a non-ready context; null = the explicit fresh-Part flow', async () => {
    const store = createPartContextStore()
    const p = store.setPart('ws-1', 'P-1', io(async () => RAW('P-1')))
    expect(capture(store.getSnapshot())).toBeNull() // cannot capture mid-transition
    await p
    const tuple = capture(store.getSnapshot())!
    const p2 = store.refresh(io(async () => RAW('P-1')))
    expect(guardTerminalTarget(tuple, store.getSnapshot())).toMatch(/context changed/) // loading
    await p2
    store.clear()
    expect(guardTerminalTarget(null, store.getSnapshot())).toBeNull() // no capture — dev flow
  })
})
