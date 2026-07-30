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
      workspaceId: 'ws1',
      partNumber: 'P-000001',
      frame: FRAME,
      snapAngleToleranceDeg: 3,
      minDragPx: 4,
      preview,
      onCommit,
      ...overrides,
    }),
  )
  return { hook, preview, onCommit }
}

const drawLine = (h: ReturnType<typeof setup>['hook']) => {
  act(() => h.result.current.place({ u: 0, v: 0 }))
  act(() => h.result.current.place({ u: 20, v: 0.4 }))
}

describe('the lane is inert until a session opens', () => {
  it('no session means no mode and no preview traffic', async () => {
    const { hook, preview } = setup()
    expect(hook.result.current.active).toBe(false)
    expect(hook.result.current.mode).toBeNull()
    act(() => hook.result.current.place({ u: 1, v: 1 }))
    expect(preview).not.toHaveBeenCalled()
  })

  it('a session with no frame yields no mode — the viewport is never given a plane it lacks', () => {
    const { hook } = setup({ frame: null })
    act(() => hook.result.current.openCreateSession(PLACEMENT))
    expect(hook.result.current.active).toBe(true)
    expect(hook.result.current.mode).toBeNull()
  })
})

describe('drawing drives the engine preview', () => {
  it('a completed line asks the engine, and the answer becomes the overlay geometry', async () => {
    const { hook, preview } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT))
    drawLine(hook)
    await act(async () => {})

    expect(preview).toHaveBeenCalledOnce()
    const [, objectRef, profile, owner] = preview.mock.calls[0] as unknown as [
      string, string, ProfilePayload, Record<string, unknown>,
    ]
    expect(objectRef).toBe('P-000001')
    expect(profile.segments).toHaveLength(1)
    expect(owner).toMatchObject({ placement: PLACEMENT })

    const mode = hook.result.current.mode
    expect(mode?.kind).toBe('profile')
    expect(mode && 'geometry' in mode && mode.geometry?.points).toHaveLength(2)
  })

  it('MOVING THE CURSOR never triggers a solve — only the drawn graph does', async () => {
    const { hook, preview } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT))
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
    act(() => hook.result.current.openCreateSession(PLACEMENT))
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
    act(() => hook.result.current.openEditSession('feat_0001', baseline))
    drawLine(hook)
    await act(async () => {})
    expect((preview.mock.calls[0] as unknown as unknown[])[3]).toEqual({ sketchFeatureId: 'feat_0001' })
  })
})

describe('refusals keep the session alive', () => {
  it('an engine refusal is surfaced without ending the session', async () => {
    const preview = vi.fn(async () => ({
      preview: null,
      refusal: { message: 'segment collapsed' },
    })) as unknown as NonNullable<Parameters<typeof useProfileSketch>[0]['preview']>
    const { hook } = setup({ preview })
    act(() => hook.result.current.openCreateSession(PLACEMENT))
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
    act(() => hook.result.current.openCreateSession(PLACEMENT))
    drawLine(hook)
    await act(async () => {})
    expect(hook.result.current.refusal).toBe('bridge exited')
    expect(hook.result.current.active).toBe(true)
  })

  it('with no bridge at all the lane refuses honestly rather than mocking geometry', async () => {
    const { hook } = setup({ preview: undefined })
    act(() => hook.result.current.openCreateSession(PLACEMENT))
    drawLine(hook)
    await act(async () => {})
    expect(hook.result.current.refusal).toMatch(/bridge is unavailable/)
  })
})

describe('Close and Cancel', () => {
  it('Close hands the shell exactly one commit intent and ends the session', async () => {
    const { hook, onCommit } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT))
    drawLine(hook)
    await act(async () => {})
    act(() => hook.result.current.close())

    expect(onCommit).toHaveBeenCalledOnce()
    expect(onCommit.mock.calls[0][0].kind).toBe('mechanical.author_profile_sketch')
    expect(hook.result.current.active).toBe(false)
  })

  it('Close on an EMPTY create session commits nothing — it coincides with Cancel', () => {
    const { hook, onCommit } = setup()
    act(() => hook.result.current.openCreateSession(PLACEMENT))
    act(() => hook.result.current.close())
    expect(onCommit).not.toHaveBeenCalled()
    expect(hook.result.current.active).toBe(false)
  })

  it('an edited sketch closes as a REPLACE', async () => {
    const { hook, onCommit } = setup()
    act(() =>
      hook.result.current.openEditSession('feat_0001', {
        points: [{ id: 'skp_0006', x: 0, y: 0 }],
        circles: [{ id: 'skp_0007', center: { id: 'skp_0006' }, radius_mm: 5 }],
      }),
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
    act(() => hook.result.current.openEditSession('feat_0001', { points: [] }))
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
    act(() => hook.result.current.openCreateSession(PLACEMENT))
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
    act(() => hook.result.current.openCreateSession(PLACEMENT))
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
