/**
 * The placement dialog (I3, arc 20260905-1): Creo's Placement-tab grammar —
 * the Plane collector, Use Previous disabled with its product reason, Flip,
 * the Reference collector (auto-defaulted per A3.3 under the Z-up names),
 * Orientation — and ONE accept button whose label follows the continuation
 * (Sketch / Create / Redefine). Collector clicks arm the viewport pick; the
 * store's `resolvePlacementPick` fills the armed collector and disarms it.
 */
// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { createAuthoringSessionStore } from './authoringSession'
import { PlacementPanel } from './PlacementPanel'
import { dragOffset } from './placementDrag'
import { USE_PREVIOUS_UNAVAILABLE } from './placementCopy'

afterEach(cleanup)
beforeAll(() => {
  // jsdom ships no PointerEvent constructor; the drag reads the MouseEvent shape
  const w = window as unknown as Record<string, unknown>
  if (typeof w.PointerEvent === 'undefined') w.PointerEvent = MouseEvent
})

const sketchDialog = () => {
  const store = createAuthoringSessionStore()
  store.startPlacementPick(
    7,
    { number: 'P-9', name: 'Walk' },
    { accept: 'sketch', capturedTarget: { workspaceId: 'ws', partNumber: 'P-9', generation: 7 } },
  )
  store.resolvePlanePick('xy') // TOP
  return store
}

describe('the placement dialog', () => {
  it('opens on the A3.3 default under the Z-up names: TOP → RIGHT, Right, Flip off; accept = Sketch', () => {
    const store = sketchDialog()
    render(<PlacementPanel store={store} isReal={false} onAccept={() => {}} />)
    expect(screen.getByTestId('collector-plane').textContent).toBe('TOP (xy)')
    expect(screen.getByTestId('collector-reference').textContent).toBe('RIGHT (yz)')
    expect((screen.getByLabelText('Orientation') as HTMLSelectElement).value).toBe('right')
    expect(screen.getByTestId('flip').getAttribute('aria-pressed')).toBe('false')
    expect(screen.getByTestId('accept').textContent).toBe('Sketch')
    const prev = screen.getByTestId('use-previous') as HTMLButtonElement
    expect(prev.disabled).toBe(true)
    expect(prev.title).toBe(USE_PREVIOUS_UNAVAILABLE)
  })

  it('Flip toggles the normal side; the Reference list and Orientation write the same facts', () => {
    const store = sketchDialog()
    render(<PlacementPanel store={store} isReal={false} onAccept={() => {}} />)
    fireEvent.click(screen.getByTestId('flip'))
    expect(store.getSnapshot()).toMatchObject({ mode: 'placement', normalSide: 'negative' })
    expect(screen.getByTestId('flip').getAttribute('aria-pressed')).toBe('true')
    fireEvent.change(screen.getByLabelText('Orientation reference list'), { target: { value: 'zx' } })
    fireEvent.change(screen.getByLabelText('Orientation'), { target: { value: 'top' } })
    expect(store.getSnapshot()).toMatchObject({ support: 'xy', orientationRef: 'zx', orientation: 'top', normalSide: 'negative' })
    expect(screen.getByTestId('collector-reference').textContent).toBe('FRONT (zx)')
    // the list never offers the support itself as a reference
    const refOptions = Array.from((screen.getByLabelText('Orientation reference list') as HTMLSelectElement).options).map((o) => o.value)
    expect(refOptions).toEqual(['yz', 'zx'])
  })

  it('a collector click ARMS the viewport pick; the pick fills it through the same setter and disarms', () => {
    const store = sketchDialog()
    render(<PlacementPanel store={store} isReal={false} onAccept={() => {}} />)
    fireEvent.click(screen.getByTestId('collector-reference'))
    expect(store.getSnapshot()).toMatchObject({ activeCollector: 'reference' })
    expect(screen.getByTestId('collector-reference').getAttribute('aria-pressed')).toBe('true')
    act(() => store.resolvePlacementPick('zx'))
    expect(store.getSnapshot()).toMatchObject({ orientationRef: 'zx', activeCollector: null })
    expect(screen.getByTestId('collector-reference').getAttribute('aria-pressed')).toBe('false')
    // the Plane collector: a colliding pick repairs the reference to the new default
    fireEvent.click(screen.getByTestId('collector-plane'))
    act(() => store.resolvePlacementPick('zx'))
    expect(store.getSnapshot()).toMatchObject({ support: 'zx', orientationRef: 'xy', activeCollector: null })
    expect(screen.getByTestId('collector-plane').textContent).toBe('FRONT (zx)')
  })

  it('accept calls the App once; Cancel returns the store to idle', () => {
    const store = sketchDialog()
    const onAccept = vi.fn()
    render(<PlacementPanel store={store} isReal={false} onAccept={onAccept} />)
    fireEvent.click(screen.getByTestId('accept'))
    expect(onAccept).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByText('Cancel'))
    expect(store.getSnapshot().mode).toBe('idle')
  })

  it('the References continuation says Create; a redefine says Redefine and refuses a no-op', () => {
    const store = createAuthoringSessionStore()
    store.startPlacementPick(1, { number: 'P-1', name: 'x' })
    store.resolvePlanePick('zx')
    const { unmount } = render(<PlacementPanel store={store} isReal={false} onAccept={() => {}} />)
    expect(screen.getByTestId('accept').textContent).toBe('Create')
    unmount()
    const redefine = createAuthoringSessionStore()
    redefine.startPlacementRedefine(
      'feat_0003',
      { support: 'xy', orientationRef: 'yz', orientation: 'right', normalSide: 'positive' },
      1,
      { number: 'P-1', name: 'x' },
    )
    render(<PlacementPanel store={redefine} isReal={false} onAccept={() => {}} />)
    const accept = screen.getByTestId('accept') as HTMLButtonElement
    expect(accept.textContent).toBe('Redefine')
    expect(accept.disabled).toBe(true) // nothing changed
    fireEvent.click(screen.getByTestId('flip'))
    expect(accept.disabled).toBe(false)
  })
  it('W-5: the dialog drags by its title bar; controls in the bar keep their clicks; release ends the drag', () => {
    const store = sketchDialog()
    render(<PlacementPanel store={store} isReal={false} onAccept={() => {}} />)
    const panel = screen.getByTestId('placement-panel')
    const head = screen.getByTestId('placement-head')
    expect(panel.style.transform).toBe('translate(0px, 0px)')
    fireEvent.pointerDown(head, { button: 0, clientX: 100, clientY: 40 })
    fireEvent.pointerMove(window, { clientX: 160, clientY: 90 })
    expect(panel.style.transform).toBe('translate(60px, 50px)')
    fireEvent.pointerUp(window)
    fireEvent.pointerMove(window, { clientX: 900, clientY: 900 }) // released — no effect
    expect(panel.style.transform).toBe('translate(60px, 50px)')
    // a second drag continues from the kept offset
    fireEvent.pointerDown(head, { button: 0, clientX: 0, clientY: 0 })
    fireEvent.pointerMove(window, { clientX: -10, clientY: 5 })
    fireEvent.pointerUp(window)
    expect(panel.style.transform).toBe('translate(50px, 55px)')
    // the ✕ in the bar is a control, not a handle
    fireEvent.pointerDown(screen.getByTitle('Cancel (Esc)'), { button: 0, clientX: 0, clientY: 0 })
    fireEvent.pointerMove(window, { clientX: 500, clientY: 500 })
    fireEvent.pointerUp(window)
    expect(panel.style.transform).toBe('translate(50px, 55px)')
  })

  it('W-5: the pure offset keeps the panel inside its host (and is unclamped without layout)', () => {
    const panel = { left: 700, top: 52, width: 300, height: 200 } // its natural place at offset 0
    const host = { left: 0, top: 0, right: 1000, bottom: 600, width: 1000 }
    expect(dragOffset({ x: 0, y: 0 }, { x: -100, y: 30 }, panel, host)).toEqual({ x: -100, y: 30 })
    expect(dragOffset({ x: 0, y: 0 }, { x: 500, y: -500 }, panel, host)).toEqual({ x: 0, y: -52 }) // right/top edge
    expect(dragOffset({ x: 0, y: 0 }, { x: -5000, y: 5000 }, panel, host)).toEqual({ x: -700, y: 348 }) // left/bottom edge
    // a drag that starts from a kept offset clamps against the same natural place
    expect(dragOffset({ x: -100, y: 30 }, { x: -5000, y: 0 }, { ...panel, left: 600, top: 82 }, host)).toEqual({ x: -700, y: 30 })
    expect(dragOffset({ x: 0, y: 0 }, { x: 40, y: 40 }, null, null)).toEqual({ x: 40, y: 40 })
    expect(dragOffset({ x: 0, y: 0 }, { x: 40, y: 40 }, { ...panel, width: 0 }, host)).toEqual({ x: 40, y: 40 })
  })
})
