import { describe, expect, it } from 'vitest'
import {
  DISPLAY_MODES,
  MODE_LABELS,
  modeFlags,
  overlayActive,
  overlaySegmentStyle,
} from './modes'

/**
 * The P1 semantics matrix as a table-driven test, with Codex1 B2's three
 * distinguishing cases stated explicitly: the difference between implementing
 * the Creo taxonomy and preserving the stopgap's misnamed mode.
 */
describe('mode flags matrix', () => {
  it('covers exactly the five Creo modes (ADR/0033 D7)', () => {
    expect(DISPLAY_MODES).toEqual(['wireframe', 'hidden-line', 'no-hidden', 'shading', 'shading-edges'])
    for (const m of DISPLAY_MODES) expect(MODE_LABELS[m]).toBeTruthy()
  })

  it('No Hidden: no dim pass — visible base edges over an opaque paper body (B2 case 1)', () => {
    const f = modeFlags('no-hidden')
    expect(f.dimEdgesVisible).toBe(false)
    expect(f.brightEdgesVisible).toBe(true)
    expect(f.brightEdgesDepthTest).toBe(true)
    expect(f.faceStyle).toBe('paper') // occludes the grid — NOT a depth-only body
    expect(f.facesDepthWrite).toBe(true)
  })

  it('Hidden Line: see-through dim all-edges pass under the bright pass (B2 case 2)', () => {
    const f = modeFlags('hidden-line')
    expect(f.dimEdgesVisible).toBe(true)
    expect(f.dimEdgesDepthTest).toBe(false) // THE B2 fix — depth-tested dim collapses into No Hidden
    expect(f.brightEdgesVisible).toBe(true)
    expect(f.brightEdgesDepthTest).toBe(true)
    expect(f.faceStyle).toBe('paper')
    expect(f.facesDepthWrite).toBe(true)
  })

  it('Wireframe: no faces at all, no depth write; all edges see-through (B2 case 3)', () => {
    const f = modeFlags('wireframe')
    expect(f.faceStyle).toBe('none')
    expect(f.facesDepthWrite).toBe(false)
    expect(f.brightEdgesVisible).toBe(true)
    expect(f.brightEdgesDepthTest).toBe(false)
    expect(f.dimEdgesVisible).toBe(false)
  })

  it('shaded modes: faces shaded and occluding; edges only in shading-edges', () => {
    expect(modeFlags('shading')).toMatchObject({
      faceStyle: 'shaded',
      facesDepthWrite: true,
      brightEdgesVisible: false,
      dimEdgesVisible: false,
    })
    expect(modeFlags('shading-edges')).toMatchObject({
      faceStyle: 'shaded',
      facesDepthWrite: true,
      brightEdgesVisible: true,
      brightEdgesDepthTest: true,
      dimEdgesVisible: false,
    })
  })

  it('invariant: the dim pass is never depth-tested while visible (B2)', () => {
    for (const m of DISPLAY_MODES) {
      const f = modeFlags(m)
      if (f.dimEdgesVisible) expect(f.dimEdgesDepthTest).toBe(false)
    }
  })
})

describe('settled overlay segment policy', () => {
  it('Shading renders no overlay at all', () => {
    expect(overlayActive('shading')).toBe(false)
    expect(overlaySegmentStyle('shading', 'visible')).toBe('omit')
    expect(overlaySegmentStyle('shading', 'hidden')).toBe('omit')
  })

  it('Shading With Edges omits hidden segments entirely (Codex1 N4)', () => {
    expect(overlaySegmentStyle('shading-edges', 'visible')).toBe('bright')
    expect(overlaySegmentStyle('shading-edges', 'hidden')).toBe('omit')
  })

  it('No Hidden: hidden removed; Hidden Line: hidden dimmed (the D7 distinction)', () => {
    expect(overlaySegmentStyle('no-hidden', 'visible')).toBe('bright')
    expect(overlaySegmentStyle('no-hidden', 'hidden')).toBe('omit')
    expect(overlaySegmentStyle('hidden-line', 'visible')).toBe('bright')
    expect(overlaySegmentStyle('hidden-line', 'hidden')).toBe('dim')
  })

  it('Wireframe: every segment bright, no hidden distinction', () => {
    expect(overlaySegmentStyle('wireframe', 'visible')).toBe('bright')
    expect(overlaySegmentStyle('wireframe', 'hidden')).toBe('bright')
  })
})
