// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useProfileSketch, previewGeometry, nextCandidateKey } from './useProfileSketch'
import type { PreviewResult } from './profilePreviewRequester'
import type { ProfilePayload, SketchPlacementInput } from './profileTypes'
import type { PlaneFrameTS } from './planeFrame'

const FRAME: PlaneFrameTS = {
  origin: [0, 0, 0],
  u: [1, 0, 0],
  v: [0, 1, 0],
  normal: [0, 0, 1],
}
const PLACEMENT: SketchPlacementInput = { support: { kind: 'principal', orientation: 'xy' } }
const TARGET = { workspaceId: 'ws1', partNumber: 'P-000001', generation: 7 }

const previewOf = (n: number): PreviewResult =>
  ({
    preview: {
      owner: { candidate_key: 'draft1' },
      frame: { origin_mm: [0, 0, 0], u_axis: [1, 0, 0], v_axis: [0, 1, 0], normal: [0, 0, 1] },
      points: Array.from({ length: n }, (_, i) => ({ id: `p${i}`, world: [i, 0, 0] })),
      segments: [],
      circles: [],
      annotations: [],
      constraint_glyphs: [],
    },
    refusal: null,
  }) as unknown as PreviewResult

function setup(overrides: Partial<Parameters<typeof useProfileSketch>[0]> = {}) {
  const preview = vi.fn(async () => previewOf(2))
  const onCommit = vi.fn()
  const hook = renderHook(() =>
    useProfileSketch({
      snapAngleToleranceDeg: 3,
      minDragPx: 4,
      preview,
      onCommit,
      ...overrides,
    }),
  )
  return { hook, preview, onCommit }
}

// W-2 chain grammar: a single line is click·click·end (the viewport's
// middle-click / Enter both route to finishTool).
const drawLine = (h: ReturnType<typeof setup>['hook']) => {
  act(() => h.result.current.place({ u: 0, v: 0 }))
  act(() => h.result.current.place({ u: 20, v: 0.4 }))
  act(() => h.result.current.finishTool())
}

describe('the lane is inert until a session opens', () => {
  it('no session means no mode and no preview traffic', async () => {
    const { hook, preview } = setup()
    expect(hook.result.current.active).toBe(false)
    expect(hook.result.current.mode).toBeNull()
    act(() => hook.result.current.place({ u: 1, v: 1 }))
    expect(preview).not.toHaveBeenCalled()
  })

  it('the mode carries the frame the session was OPENED with — no other lifecycle owns it', () => {
    const { hook } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    const mode = hook.result.current.mode
    expect(mode?.kind === 'profile' && mode.frame).toEqual(FRAME)
  })
})

describe('drawing drives the engine preview', () => {
  it('a completed line asks the engine, and the answer becomes the overlay geometry', async () => {
    const { hook, preview } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    drawLine(hook)
    await act(async () => {})

    expect(preview).toHaveBeenCalledOnce()
    const [, objectRef, engineId, profile, owner] = preview.mock.calls[0] as unknown as [
      string, string, string, ProfilePayload, Record<string, unknown>,
    ]
    expect(objectRef).toBe('P-000001')
    // Codex6 B3: the engine owner is carried explicitly, never defaulted below
    expect(engineId).toBe('mechanical')
    expect(profile.segments).toHaveLength(1)
    expect(owner).toMatchObject({ placement: PLACEMENT })

    const mode = hook.result.current.mode
    expect(mode?.kind).toBe('profile')
    expect(mode && 'geometry' in mode && mode.geometry?.points).toHaveLength(2)
  })

  it('MOVING THE CURSOR never triggers a solve — only the drawn graph does', async () => {
    const { hook, preview } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    drawLine(hook)
    await act(async () => {})
    expect(preview).toHaveBeenCalledOnce()

    for (const uv of [{ u: 1, v: 1 }, { u: 2, v: 2 }, { u: 3, v: 3 }]) {
      act(() => hook.result.current.cursor(uv))
    }
    await act(async () => {})
    expect(preview).toHaveBeenCalledOnce()
  })

  it('an in-progress click does not solve a graph that has no segment yet', async () => {
    const { hook, preview } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    act(() => hook.result.current.place({ u: 0, v: 0 }))
    await act(async () => {})
    expect(preview).not.toHaveBeenCalled()
  })

  it('an edit session previews under its FEATURE owner', async () => {
    const { hook, preview } = setup()
    const baseline: ProfilePayload = {
      points: [{ id: 'skp_0006', x: 0, y: 0 }],
      circles: [{ id: 'skp_0007', center: { id: 'skp_0006' }, radius_mm: 5 }],
    }
    act(() => hook.result.current.openEditSession('feat_0001', baseline, FRAME, TARGET))
    drawLine(hook)
    await act(async () => {})
    expect((preview.mock.calls[0] as unknown as unknown[])[4]).toEqual({ sketchFeatureId: 'feat_0001' })
  })
})

describe('the per-segment preview cadence (Codex11 B1)', () => {
  it('click 1 sends nothing; click 2 sends the one-segment graph', async () => {
    const { hook, preview } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    act(() => hook.result.current.place({ u: 0, v: 0 }))
    await act(async () => {})
    expect(preview).not.toHaveBeenCalled()
    act(() => hook.result.current.place({ u: 20, v: 0.4 }))
    await act(async () => {})
    expect(preview).toHaveBeenCalledOnce()
    const profile = (preview.mock.calls[0] as unknown as unknown[])[3] as ProfilePayload
    expect(profile.segments).toHaveLength(1)
  })

  it('click 3 sends the full chain — two segments off the shared vertex', async () => {
    const { hook, preview } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    act(() => hook.result.current.place({ u: 0, v: 0 }))
    act(() => hook.result.current.place({ u: 20, v: 0.2 }))
    await act(async () => {})
    act(() => hook.result.current.place({ u: 25, v: 15 }))
    await act(async () => {})
    expect(preview).toHaveBeenCalledTimes(2)
    const profile = (preview.mock.calls[1] as unknown as unknown[])[3] as ProfilePayload
    expect(profile.segments).toHaveLength(2)
    expect(profile.segments?.[0].end).toEqual(profile.segments?.[1].start)
  })

  it('the end gesture sends NO duplicate — the graph did not change', async () => {
    const { hook, preview } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    act(() => hook.result.current.place({ u: 0, v: 0 }))
    act(() => hook.result.current.place({ u: 20, v: 0.4 }))
    await act(async () => {})
    expect(preview).toHaveBeenCalledOnce()
    act(() => hook.result.current.finishTool()) // the MMB/Enter route
    await act(async () => {})
    expect(preview).toHaveBeenCalledOnce()
  })

  it('Close commits the graph most recently previewed (preview/commit parity)', async () => {
    const { hook, preview, onCommit } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    act(() => hook.result.current.place({ u: 0, v: 0 }))
    act(() => hook.result.current.place({ u: 20, v: 0.4 }))
    await act(async () => {})
    const previewed = (preview.mock.calls.at(-1) as unknown as unknown[])[3] as ProfilePayload
    act(() => hook.result.current.close()) // settles the open run
    expect(onCommit).toHaveBeenCalledOnce()
    const committed = onCommit.mock.calls[0][0].params.profile as ProfilePayload
    expect(JSON.stringify(committed)).toBe(JSON.stringify(previewed))
  })

  it('abandoning the run clears the stale solved preview — nothing left to show', async () => {
    const { hook } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    act(() => hook.result.current.place({ u: 0, v: 0 }))
    act(() => hook.result.current.place({ u: 20, v: 0.4 }))
    await act(async () => {})
    let mode = hook.result.current.mode
    expect(mode && 'geometry' in mode && mode.geometry).not.toBeNull()
    act(() => hook.result.current.abandonRun())
    await act(async () => {})
    mode = hook.result.current.mode
    expect(mode && 'geometry' in mode && mode.geometry).toBeNull()
    expect(hook.result.current.refusal).toBeNull()
    expect(hook.result.current.active).toBe(true) // the session itself survives
  })
})

describe('refusals keep the session alive', () => {
  it('an engine refusal is surfaced without ending the session', async () => {
    const preview = vi.fn(async () => ({
      preview: null,
      refusal: { message: 'segment collapsed' },
    })) as unknown as NonNullable<Parameters<typeof useProfileSketch>[0]['preview']>
    const { hook } = setup({ preview })
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    drawLine(hook)
    await act(async () => {})

    expect(hook.result.current.refusal).toBe('segment collapsed')
    expect(hook.result.current.active).toBe(true)
    const mode = hook.result.current.mode
    expect(mode && 'geometry' in mode && mode.geometry).toBeNull()
  })

  it('a bridge failure becomes a refusal, not a crashed session', async () => {
    const preview = vi.fn(async () => {
      throw new Error('bridge exited')
    }) as unknown as NonNullable<Parameters<typeof useProfileSketch>[0]['preview']>
    const { hook } = setup({ preview })
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    drawLine(hook)
    await act(async () => {})
    expect(hook.result.current.refusal).toBe('bridge exited')
    expect(hook.result.current.active).toBe(true)
  })

  it('with no bridge at all the lane refuses honestly rather than mocking geometry', async () => {
    const { hook } = setup({ preview: undefined })
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    drawLine(hook)
    await act(async () => {})
    expect(hook.result.current.refusal).toMatch(/bridge is unavailable/)
  })
})

describe('Close and Cancel', () => {
  it('Close hands the shell ONE intent and the session SURVIVES until the outcome', async () => {
    const { hook, onCommit } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    drawLine(hook)
    await act(async () => {})
    act(() => hook.result.current.close())

    expect(onCommit).toHaveBeenCalledOnce()
    expect(onCommit.mock.calls[0][0].kind).toBe('mechanical.author_profile_sketch')
    // Codex6 B2: a cleared session cannot be recovered, so Close keeps it
    // open (single-flight) until the shell reports the outcome.
    expect(hook.result.current.active).toBe(true)
    expect(hook.result.current.closing).toBe(true)
    // a second Close mid-flight is refused — one terminal in motion
    act(() => hook.result.current.close())
    expect(onCommit).toHaveBeenCalledOnce()

    act(() => hook.result.current.confirmClosed())
    expect(hook.result.current.active).toBe(false)
    expect(hook.result.current.closing).toBe(false)
  })

  it('a FAILED commit leaves the drawing recoverable with the refusal surfaced', async () => {
    const { hook, onCommit } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    drawLine(hook)
    await act(async () => {})
    act(() => hook.result.current.close())
    expect(onCommit).toHaveBeenCalledOnce()

    act(() => hook.result.current.commitFailed('the engine refused the graph'))
    expect(hook.result.current.active).toBe(true)
    expect(hook.result.current.closing).toBe(false)
    expect(hook.result.current.refusal).toBe('the engine refused the graph')
    // fully recoverable: the user can keep drawing and Close again
    act(() => hook.result.current.place({ u: 40, v: 0 }))
    act(() => hook.result.current.place({ u: 60, v: 0.2 }))
    await act(async () => {})
    act(() => hook.result.current.close())
    expect(onCommit).toHaveBeenCalledTimes(2)
  })

  it('Close on an EMPTY create session commits nothing — it coincides with Cancel', () => {
    const { hook, onCommit } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    act(() => hook.result.current.close())
    expect(onCommit).not.toHaveBeenCalled()
    expect(hook.result.current.active).toBe(false)
  })

  it('Close SETTLES an endable open chain run — OK without the end gesture commits the line (W-2)', async () => {
    const { hook, onCommit } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    act(() => hook.result.current.place({ u: 0, v: 0 }))
    act(() => hook.result.current.place({ u: 20, v: 0.4 }))
    // no finishTool — the user went straight to OK
    act(() => hook.result.current.close())
    expect(onCommit).toHaveBeenCalledOnce()
    const profile = onCommit.mock.calls[0][0].params.profile as ProfilePayload
    expect(profile.segments).toHaveLength(1)
  })

  it('W-3a: two Close dispatches in ONE batch commit ONCE — the flag flips synchronously', async () => {
    // The wild defect: the terminal logic lived inside a setSession updater
    // and the single-flight flag was set there too, so two dispatches queued
    // before a flush (an updater re-run, a double click in one batch) each
    // ran the full chain — tx_0050 committed twice and poisoned the
    // workspace. With the logic in the event handler the second call must
    // see the flag already set, WITHOUT any render flush in between.
    const { hook, onCommit } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    act(() => hook.result.current.place({ u: 0, v: 0 }))
    act(() => hook.result.current.place({ u: 20, v: 0.4 }))
    await act(async () => {})
    act(() => {
      const close = hook.result.current.close
      close()
      close() // same batch: no state flush between the two calls
    })
    expect(onCommit).toHaveBeenCalledOnce()
  })

  it('Close over a lone stray click still coincides with Cancel (the click is an accident)', () => {
    const { hook, onCommit } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    act(() => hook.result.current.place({ u: 5, v: 5 }))
    act(() => hook.result.current.close())
    expect(onCommit).not.toHaveBeenCalled()
    expect(hook.result.current.active).toBe(false)
  })

  it('an edited sketch closes as a REPLACE', async () => {
    const { hook, onCommit } = setup()
    act(() =>
      hook.result.current.openEditSession(
        'feat_0001',
        {
          points: [{ id: 'skp_0006', x: 0, y: 0 }],
          circles: [{ id: 'skp_0007', center: { id: 'skp_0006' }, radius_mm: 5 }],
        },
        FRAME,
        TARGET,
      ),
    )
    drawLine(hook)
    await act(async () => {})
    act(() => hook.result.current.close())
    expect(onCommit.mock.calls[0][0]).toMatchObject({
      kind: 'mechanical.replace_sketch_graph',
      params: { sketch_feature_id: 'feat_0001' },
    })
  })

  it('Cancel writes nothing and reports the preserved feature', async () => {
    const { hook, onCommit } = setup()
    act(() => hook.result.current.openEditSession('feat_0001', { points: [] }, FRAME, TARGET))
    drawLine(hook)
    await act(async () => {})
    const outcomes: { wrote: false; preservedFeatureId: string | null }[] = []
    act(() => {
      outcomes.push(hook.result.current.cancel())
    })
    expect(outcomes[0]).toEqual({ wrote: false, preservedFeatureId: 'feat_0001' })
    expect(onCommit).not.toHaveBeenCalled()
    expect(hook.result.current.active).toBe(false)
  })

  it('a cancelled create session names no feature to preserve', () => {
    const { hook } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    const outcomes: { preservedFeatureId: string | null }[] = []
    act(() => {
      outcomes.push(hook.result.current.cancel())
    })
    expect(outcomes[0].preservedFeatureId).toBeNull()
  })

  it('a reply arriving AFTER cancel cannot resurrect the session', async () => {
    let release: ((r: PreviewResult) => void) | null = null
    const preview = vi.fn(
      () => new Promise<PreviewResult>((res) => { release = res }),
    ) as unknown as NonNullable<Parameters<typeof useProfileSketch>[0]['preview']>
    const { hook } = setup({ preview })
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    drawLine(hook)
    await act(async () => {})
    act(() => void hook.result.current.cancel())
    await act(async () => {
      release?.(previewOf(2))
    })
    expect(hook.result.current.active).toBe(false)
    expect(hook.result.current.mode).toBeNull()
  })
})

describe('helpers', () => {
  it('previewGeometry strips the envelope down to what the overlay draws', () => {
    const g = previewGeometry(previewOf(3).preview)
    expect(g?.points).toHaveLength(3)
    expect(g && 'owner' in g).toBe(false)
    expect(previewGeometry(null)).toBeNull()
  })

  it('candidate keys are never reused across sessions', () => {
    expect(nextCandidateKey()).not.toBe(nextCandidateKey())
  })
})

describe('the authority tuple (Codex7 B2)', () => {
  it('the preview runs against the CAPTURED tuple — retargeting is unconstructible', async () => {
    // deps no longer carry shell identity at all: the only workspace/Part a
    // preview can reach is the one the session captured at open
    const { hook, preview } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    drawLine(hook)
    await act(async () => {})
    const [workspaceId, objectRef] = preview.mock.calls[0] as unknown as [string, string]
    expect(workspaceId).toBe('ws1')
    expect(objectRef).toBe('P-000001')
  })

  it('terminal-start revalidation: a stale tuple refuses Close WITHOUT committing', async () => {
    const validateTarget = vi.fn(() => 'the Part context changed under this sketch')
    const { hook, onCommit } = setup({ validateTarget })
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    drawLine(hook)
    await act(async () => {})
    act(() => hook.result.current.close())

    expect(validateTarget).toHaveBeenCalledWith(TARGET)
    expect(onCommit).not.toHaveBeenCalled()
    // the refusal is surfaced into the STILL-OPEN session — nothing written
    expect(hook.result.current.active).toBe(true)
    expect(hook.result.current.closing).toBe(false)
    expect(hook.result.current.refusal).toMatch(/context changed/)
  })

  it('a current tuple passes revalidation and commits with the CAPTURED target', async () => {
    const validateTarget = vi.fn(() => null)
    const { hook, onCommit } = setup({ validateTarget })
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    drawLine(hook)
    await act(async () => {})
    act(() => hook.result.current.close())
    expect(onCommit).toHaveBeenCalledOnce()
    expect(onCommit.mock.calls[0][1]).toEqual(TARGET)
    expect(onCommit.mock.calls[0][0].params.part_number).toBe('P-000001')
  })
})

describe('the terminal owns busy until it settles (Codex8 B1)', () => {
  it('Cancel during an in-flight Close is REFUSED — the session and closing survive', async () => {
    const { hook, onCommit } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT, FRAME, TARGET))
    drawLine(hook)
    await act(async () => {})
    act(() => hook.result.current.close())
    expect(hook.result.current.closing).toBe(true)

    // an invalidation (or any caller) trying to cancel mid-terminal
    act(() => void hook.result.current.cancel())
    expect(hook.result.current.active).toBe(true)
    expect(hook.result.current.closing).toBe(true)
    expect(onCommit).toHaveBeenCalledOnce()

    // the terminal settles as a failure → the drawing is recoverable...
    act(() => hook.result.current.commitFailed('validation failed'))
    expect(hook.result.current.active).toBe(true)
    expect(hook.result.current.refusal).toBe('validation failed')
    // ...and Cancel works again now that no terminal is in flight
    act(() => void hook.result.current.cancel())
    expect(hook.result.current.active).toBe(false)
  })
})
