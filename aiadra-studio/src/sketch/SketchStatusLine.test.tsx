/**
 * The sketch status line (SR-08; Codex1 B5): identity + the exact live
 * hint/error + the merged hover readout + the lane badge — present only in
 * sketch mode. (The slot's shellNote EXCLUSIVITY and the fixed tenants live
 * in the statusbar mount's contract; truncation is the slot's CSS law.)
 */
// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { SketchStatusLine } from './SketchStatusLine'
import { createAuthoringSessionStore } from '../authoring/authoringSession'

afterEach(cleanup)

const sketchStore = () => {
  const store = createAuthoringSessionStore()
  store.startSketch({
    tool: 'contour', partName: null, partNumber: null,
    targetPart: { number: 'P-282364', name: 'W' }, targetAuth: null,
    plane: 'yz', generation: 1,
  })
  return store
}

describe('the sketch status line (SR-08)', () => {
  it('renders nothing outside sketch mode', () => {
    const store = createAuthoringSessionStore()
    const { container } = render(<SketchStatusLine store={store} isReal={false} hover={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('identity + the live hint + the lane badge', () => {
    render(<SketchStatusLine store={sketchStore()} isReal={true} hover={null} />)
    const line = screen.getByTestId('sketch-status')
    expect(line.textContent).toContain('Sketch — RIGHT (yz)')
    expect(line.textContent).toContain('P-282364')
    // zero points: the live derivation reports the contour problem AS the
    // hint — exactly the retired chrome's behavior
    expect(line.textContent).toContain('Add at least 3 points')
    expect(line.textContent).toContain('real engine')
  })

  it('the ERROR phase replaces the hint with the message', () => {
    const store = sketchStore()
    store.setSketchPhase('error', 'the engine refused: boom')
    render(<SketchStatusLine store={store} isReal={false} hover={null} />)
    expect(screen.getByTestId('sketch-status').textContent).toContain('the engine refused: boom')
  })

  it('the hover readout MERGES into the line (retained, never dropped)', () => {
    render(
      <SketchStatusLine
        store={sketchStore()}
        isReal={false}
        hover={{ kind: 'face', id: 'feat_0002:face:cap_top' }}
      />,
    )
    const line = screen.getByTestId('sketch-status')
    expect(line.textContent).toContain('context face')
    expect(line.querySelector('[data-context-id="feat_0002:face:cap_top"]')).toBeTruthy()
  })
})
