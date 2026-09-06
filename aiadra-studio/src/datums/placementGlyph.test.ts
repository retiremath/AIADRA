/**
 * Creo's sketch view-direction arrow (I3; Codex1 Q1): a separate overlay,
 * one arrow, outside canonical identity; points along the look direction it
 * is given (so Flip reverses it) and can be hidden and disposed.
 */
import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { createPlacementGlyph } from './placementGlyph'

const pointing = (arrow: THREE.ArrowHelper): number[] => {
  // ArrowHelper's native direction is +Y; its quaternion carries the look.
  const d = new THREE.Vector3(0, 1, 0).applyQuaternion(arrow.quaternion)
  return [d.x, d.y, d.z].map((x) => Math.round(x * 1e6) / 1e6 + 0)
}

describe('the placement view-direction glyph', () => {
  it('is ONE arrow with no canonical identity (never a pick target)', () => {
    const g = createPlacementGlyph()
    expect(g.group.children).toHaveLength(1)
    const arrow = g.group.children[0]
    expect(arrow).toBeInstanceOf(THREE.ArrowHelper)
    const u = arrow.userData as { kind?: string; displayId?: string; faceId?: string; intrinsicId?: string }
    expect(u.kind).toBe('placement-view-direction')
    expect(u.displayId).toBeUndefined()
    expect(u.faceId).toBeUndefined()
    expect(u.intrinsicId).toBeUndefined()
    g.dispose()
  })

  it('points along the given look direction and reverses with Flip', () => {
    const g = createPlacementGlyph()
    const arrow = g.group.children[0] as THREE.ArrowHelper
    g.update([0, 0, 0], [0, 0, 1], 24) // TOP, Flip on → look +Z
    expect(pointing(arrow)).toEqual([0, 0, 1])
    g.update([0, 0, 0], [0, 0, -1], 24) // Flip off → look −Z
    expect(pointing(arrow)).toEqual([0, 0, -1])
    g.update([0, 0, 0], [-1, 0, 0], 24) // RIGHT, Flip on
    expect(pointing(arrow)).toEqual([-1, 0, 0])
    g.dispose()
  })

  it('reads over the datum planes and can be hidden without disposal', () => {
    const g = createPlacementGlyph()
    const arrow = g.group.children[0] as THREE.ArrowHelper
    expect((arrow.cone.material as THREE.Material).depthTest).toBe(false)
    expect((arrow.line.material as THREE.Material).depthTest).toBe(false)
    g.group.visible = false
    expect(g.group.visible).toBe(false)
    g.dispose()
  })
})
