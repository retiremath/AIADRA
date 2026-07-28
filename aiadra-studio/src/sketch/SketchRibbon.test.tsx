/**
 * The Sketch ribbon (pass sketch-ribbon-1): a PROJECTION of the one sketch
 * session — tools dispatch the same store actions the chrome did; roadmap
 * groups (Constrain/Dimension) are honestly disabled with their named
 * strands; the ribbon renders nothing outside sketch mode.
 */
// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SketchRibbon } from './SketchRibbon'
import { createAuthoringSessionStore } from '../authoring/authoringSession'

afterEach(cleanup)

// increment 2: the ribbon owns the terminal — the harness supplies an inert
// backend/context (these tests exercise the projection; the commit lifecycle
// has its own integration floors in sketchCommit.test.ts).
const harness = (store: ReturnType<typeof createAuthoringSessionStore>) => ({
  store,
  backend: {
    isReal: false,
    async begin() { throw new Error('unused') },
    async simulate() { throw new Error('unused') },
    async commit() { throw new Error('unused') },
    async rollback() {},
  } as unknown as import('../authoring/backend').AuthoringBackend,
  context: { getSnapshot: () => ({ generation: 1 }) } as unknown as import('../authoring/partContext').PartContextStore,
  onClose: () => {},
})


const enterSketch = () => {
  const store = createAuthoringSessionStore()
  // the SketchMeta contract: principal support derives from `plane` inside
  // startSketch (Codex1 B1 — no non-contract members in test fixtures)
  store.startSketch({
    tool: 'contour',
    partName: null,
    partNumber: null,
    targetPart: null,
    targetAuth: null,
    plane: 'yz',
    generation: 1,
  })
  return store
}

describe('the Sketch ribbon (the dedicated Sketch-tab grammar)', () => {
  it('renders nothing outside sketch mode', () => {
    const store = createAuthoringSessionStore()
    const { container } = render(<SketchRibbon {...harness(store)} onSketchView={() => {}} />)
    expect(container.firstChild).toBeNull()
  })

  it('groups render; tools dispatch the SAME store actions; the active tool is marked', () => {
    const store = enterSketch()
    render(<SketchRibbon {...harness(store)} onSketchView={() => {}} />)
    expect(screen.getByRole('toolbar', { name: 'Sketch ribbon' })).toBeTruthy()
    // 'Dimension' is both a group title and its roadmap button — count-safe
    for (const g of ['Setup', 'Sketching', 'Editing', 'Constrain', 'Dimension']) {
      expect(screen.getAllByText(g).length).toBeGreaterThan(0)
    }
    const contour = screen.getByRole('button', { name: 'Contour' })
    expect(contour.className).toContain('on') // the entered tool
    fireEvent.click(screen.getByRole('button', { name: 'Rectangle' }))
    const st = store.getSnapshot()
    expect(st.mode === 'sketch' && st.tool.kind).toBe('rectangle')
    expect(screen.getByRole('button', { name: 'Rectangle' }).className).toContain('on')
    // rectangle mode: the Editing group offers Restart, not Undo/Close ring
    expect(screen.getByRole('button', { name: 'Restart' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Close ring' })).toBeNull()
  })

  it('construction toggles through the store and reflects back', () => {
    const store = enterSketch()
    render(<SketchRibbon {...harness(store)} onSketchView={() => {}} />)
    const constr = screen.getByRole('button', { name: 'Constr.' })
    expect(constr.className).not.toContain('on')
    fireEvent.click(constr)
    expect(screen.getByRole('button', { name: 'Constr.' }).className).toContain('on')
  })

  it('Sketch view dispatches the camera callback', () => {
    const store = enterSketch()
    const onView = vi.fn()
    render(<SketchRibbon {...harness(store)} onSketchView={onView} />)
    fireEvent.click(screen.getByRole('button', { name: 'Sketch view' }))
    expect(onView).toHaveBeenCalledTimes(1)
  })

  it('Constrain/Dimension are roadmap-disabled with their NAMED strands', () => {
    const store = enterSketch()
    render(<SketchRibbon {...harness(store)} onSketchView={() => {}} />)
    const vertical = screen.getByRole('button', { name: 'Vertical' }) as HTMLButtonElement
    expect(vertical.disabled).toBe(true)
    expect(vertical.title).toContain('skb-b1')
    const dim = screen.getByRole('button', { name: 'Dimension' }) as HTMLButtonElement
    expect(dim.disabled).toBe(true)
    expect(dim.title).toContain('behavior')
  })

  it('Undo/Close ring drive the contour through the store', () => {
    const store = enterSketch()
    store.addPoint({ x: 0, y: 0 })
    store.addPoint({ x: 20, y: 0 })
    store.addPoint({ x: 20, y: 20 })
    render(<SketchRibbon {...harness(store)} onSketchView={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }))
    let st = store.getSnapshot()
    expect(st.mode === 'sketch' && st.tool.kind === 'contour' && st.tool.points.length).toBe(2)
    act(() => store.addPoint({ x: 20, y: 20 }))
    fireEvent.click(screen.getByRole('button', { name: 'Close ring' }))
    st = store.getSnapshot()
    expect(st.mode === 'sketch' && st.tool.kind === 'contour' && st.tool.closed).toBe(true)
  })

  // Codex1 B2 — the ribbon exposes ONLY the session's defined transitions.
  it('an INVALID contour disables Close ring (the ring is never closed around a problem)', () => {
    const store = enterSketch()
    // three collinear points: zero area — contourProblem is non-null
    store.addPoint({ x: 0, y: 0 })
    store.addPoint({ x: 10, y: 0 })
    store.addPoint({ x: 20, y: 0 })
    render(<SketchRibbon {...harness(store)} onSketchView={() => {}} />)
    const close = screen.getByRole('button', { name: 'Close ring' }) as HTMLButtonElement
    expect(close.disabled).toBe(true)
    expect(close.title.length).toBeGreaterThan(0) // the problem IS the tooltip
    fireEvent.click(close)
    const st = store.getSnapshot()
    expect(st.mode === 'sketch' && st.tool.kind === 'contour' && st.tool.closed).toBe(false)
  })

  it('a CLOSED contour offers Reopen only — Undo/Close are absent (no mutation while closed)', () => {
    const store = enterSketch()
    store.addPoint({ x: 0, y: 0 })
    store.addPoint({ x: 20, y: 0 })
    store.addPoint({ x: 20, y: 20 })
    store.closeRing()
    render(<SketchRibbon {...harness(store)} onSketchView={() => {}} />)
    expect(screen.getByRole('button', { name: 'Reopen' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Undo' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Close ring' })).toBeNull()
  })

  it('Sketch view stays available during a BUSY commit (camera-only; Codex1 N1)', () => {
    const store = enterSketch()
    store.addPoint({ x: 0, y: 0 })
    store.addPoint({ x: 20, y: 0 })
    store.addPoint({ x: 20, y: 20 })
    store.closeRing()
    store.setSketchPhase('busy', 'committing sketch…')
    const onView = vi.fn()
    render(<SketchRibbon {...harness(store)} onSketchView={onView} />)
    const view = screen.getByRole('button', { name: 'Sketch view' }) as HTMLButtonElement
    expect(view.disabled).toBe(false)
    fireEvent.click(view)
    expect(onView).toHaveBeenCalledTimes(1)
    // while every mutating tool IS gated
    expect((screen.getByRole('button', { name: 'Reopen' }) as HTMLButtonElement).disabled).toBe(true)
  })
})
