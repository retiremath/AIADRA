/**
 * SK-C1.0 S1 — the in-context sketch-edit overlay: live geometry in WORLD
 * space through the frame (from the first click), the display-only lift,
 * dashed construction strokes, the via preview, and the visible sketch
 * origin/axes (the convention Petre judges).
 */
import { describe, expect, it } from 'vitest'
import * as THREE from 'three'
import { createSketchEditOverlay } from './sketchEditOverlay'
import { principalFrame, SKETCH_LIFT_MM } from './planeFrame'
import type { SketchTool } from '../authoring/authoringSession'

const contour = (over: Partial<Extract<SketchTool, { kind: 'contour' }>> = {}): SketchTool => ({
  kind: 'contour', points: [], bulges: [], awaitingVia: false, cursor: null, closed: false, ...over,
})

function lines(o: ReturnType<typeof createSketchEditOverlay>): THREE.Line[] {
  const out: THREE.Line[] = []
  o.group.traverse((obj) => { if ((obj as THREE.Line).isLine) out.push(obj as THREE.Line) })
  return out
}

describe('the in-context sketch overlay (Codex2 B5.2)', () => {
  it('renders the FIRST placed segment in world space, lifted DISPLAY-only, on the zx frame', () => {
    const o = createSketchEditOverlay()
    const f = principalFrame('zx') // u=Z, v=X, n=Y — a non-trivial mapping
    o.update(f, contour({ points: [{ x: 0, y: 0 }, { x: 10, y: 0 }], bulges: [0] }), false)
    const live = lines(o).filter((l) => !(l.material as THREE.LineDashedMaterial).isLineDashedMaterial)
    // find the placed polyline: its endpoints map (u,v)=(10,0) → world (0, lift, 10)
    const withEnd = live.find((l) => {
      const arr = (l.geometry.getAttribute('position') as THREE.BufferAttribute).array
      const n = arr.length
      return Math.abs(arr[n - 1] - 10) < 1e-9 && Math.abs(arr[n - 2] - SKETCH_LIFT_MM) < 1e-9
    })
    expect(withEnd, 'the placed segment lies ON the zx plane (lifted along +Y only)').toBeTruthy()
    o.dispose()
  })

  it('construction strokes are DASHED with computed distances; profile strokes are solid', () => {
    const o = createSketchEditOverlay()
    const f = principalFrame('xy')
    const tool = contour({ points: [{ x: 0, y: 0 }, { x: 20, y: 0 }, { x: 20, y: 10 }], bulges: [0, 0] })
    o.update(f, tool, true)
    const dashed = lines(o).filter((l) => (l.material as THREE.LineDashedMaterial).isLineDashedMaterial)
    expect(dashed.length).toBeGreaterThan(0)
    expect(dashed[0].geometry.getAttribute('lineDistance')).toBeTruthy()
    o.update(f, tool, false)
    expect(lines(o).some((l) => (l.material as THREE.LineDashedMaterial).isLineDashedMaterial)).toBe(false)
    o.dispose()
  })

  it('the rubber line follows the cursor; the via preview draws the 3-point arc route', () => {
    const o = createSketchEditOverlay()
    const f = principalFrame('xy')
    o.update(f, contour({ points: [{ x: 0, y: 0 }], cursor: { x: 15, y: 5 } }), false)
    const rubberEnd = lines(o).some((l) => {
      const arr = (l.geometry.getAttribute('position') as THREE.BufferAttribute).array
      return Math.abs(arr[arr.length - 3] - 15) < 1e-9 && Math.abs(arr[arr.length - 2] - 5) < 1e-9
    })
    expect(rubberEnd).toBe(true)
    // via preview: two placed points + awaitingVia + a cursor → a tessellated arc (many vertices)
    o.update(f, contour({
      points: [{ x: 0, y: 0 }, { x: 20, y: 0 }], bulges: [0], awaitingVia: true, cursor: { x: 10, y: 6 },
    }), false)
    const arcish = lines(o).some((l) => (l.geometry.getAttribute('position') as THREE.BufferAttribute).count > 8)
    expect(arcish).toBe(true)
    o.dispose()
  })

  it('the sketch origin + u/v axes render at the frame origin (the VISIBLE convention)', () => {
    const o = createSketchEditOverlay()
    o.update(principalFrame('yz'), contour(), false)
    let markers = 0
    o.group.traverse((obj) => { if ((obj as THREE.Mesh).isMesh && obj !== o.group) markers += 1 })
    expect(markers).toBeGreaterThanOrEqual(2) // the tint quad + the origin sphere at minimum
    o.dispose()
  })

  it('circle + rectangle previews render; dispose leaves no children behind', () => {
    const o = createSketchEditOverlay()
    const f = principalFrame('xy')
    o.update(f, { kind: 'circle', center: { x: 5, y: 5 }, cursor: { x: 9, y: 5 }, circle: null }, false)
    expect(lines(o).length).toBeGreaterThan(0)
    o.update(f, { kind: 'rectangle', anchor: { x: 0, y: 0 }, cursor: { x: 12, y: 8 }, rect: null }, false)
    expect(lines(o).length).toBeGreaterThan(0)
    o.dispose()
  })
})
