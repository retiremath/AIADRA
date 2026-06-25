import { describe, it, expect } from 'vitest'
import {
  navCubeViewportRect,
  pointerInNavCube,
  pointerToNavCubeNdc,
  DEFAULT_NAV_CUBE_LAYOUT,
  type NavCubeLayout,
} from './navCubeRect'

const L: NavCubeLayout = { sizeCss: 100, marginCss: 10, corner: 'top-right' }

describe('navCubeViewportRect', () => {
  it('places a top-right cube at the right, flipped to GL bottom-left origin (CSS px)', () => {
    // 800×600 CSS canvas, cube 100, margin 10. CSS px — three.js applies DPR.
    const r = navCubeViewportRect(L, 800, 600)
    expect(r).toEqual({ x: 690, y: 490, width: 100, height: 100 })
    //   x = 800 - 10 - 100 = 690 ; topCss = 10, bottom-from-top = 110,
    //   y = 600 - 110 = 490 ; size 100.
  })

  it('does NOT bake in device pixel ratio (three.js does that)', () => {
    // The rect is independent of DPR — the round-3 fix for the off-screen cube.
    expect(navCubeViewportRect(L, 800, 600)).toEqual({ x: 690, y: 490, width: 100, height: 100 })
  })

  it('honors a bottom-left corner', () => {
    const r = navCubeViewportRect({ ...L, corner: 'bottom-left' }, 800, 600)
    // left = 10 ; topCss = 600 - 10 - 100 = 490 ; y = 600 - 590 = 10
    expect(r).toEqual({ x: 10, y: 10, width: 100, height: 100 })
  })
})

describe('pointerInNavCube', () => {
  it('detects pointers inside vs outside the top-right rect', () => {
    expect(pointerInNavCube(L, 800, 600, 740, 40)).toBe(true) // inside (690..790, 10..110)
    expect(pointerInNavCube(L, 800, 600, 400, 300)).toBe(false) // center of canvas
    expect(pointerInNavCube(L, 800, 600, 689, 40)).toBe(false) // just left of the rect
  })
})

describe('pointerToNavCubeNdc', () => {
  it('maps the rect center to (0,0) and corners to ±1 with y up', () => {
    const center = pointerToNavCubeNdc(L, 800, 600, 740, 60) // (690+50, 10+50)
    expect(center[0]).toBeCloseTo(0, 6)
    expect(center[1]).toBeCloseTo(0, 6)
    const topLeft = pointerToNavCubeNdc(L, 800, 600, 690, 10)
    expect(topLeft[0]).toBeCloseTo(-1, 6)
    expect(topLeft[1]).toBeCloseTo(1, 6) // top → +1 (y up)
    const bottomRight = pointerToNavCubeNdc(L, 800, 600, 790, 110)
    expect(bottomRight[0]).toBeCloseTo(1, 6)
    expect(bottomRight[1]).toBeCloseTo(-1, 6)
  })
})

describe('defaults', () => {
  it('default layout is a top-right 96px cube', () => {
    expect(DEFAULT_NAV_CUBE_LAYOUT.corner).toBe('top-right')
    expect(DEFAULT_NAV_CUBE_LAYOUT.sizeCss).toBe(96)
  })
})
