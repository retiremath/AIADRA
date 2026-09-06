/**
 * Creo's sketch view-direction arrow (I3, arc 20260905-1; Codex1 Q1): a
 * SEPARATE overlay owned by the placement dialog's lifetime — shown while the
 * dialog is open, updated from the signed frame on every member change (so
 * Flip visibly reverses it), hidden on exit, disposed with the viewport.
 * Outside canonical picking and identity: no intrinsic id, never a pick
 * target, never Truth. Magenta, as the benchmark's.
 */
import * as THREE from 'three'

export type GlyphVec3 = readonly [number, number, number]

export interface PlacementGlyph {
  group: THREE.Group
  /** Point the arrow along `direction` from `origin`, `lengthMm` long. */
  update(origin: GlyphVec3, direction: GlyphVec3, lengthMm: number): void
  dispose(): void
}

export const PLACEMENT_GLYPH_COLOR = 0xc21fc2

export function createPlacementGlyph(): PlacementGlyph {
  const group = new THREE.Group()
  group.name = 'placement-view-direction'
  const arrow = new THREE.ArrowHelper(
    new THREE.Vector3(0, 0, 1),
    new THREE.Vector3(0, 0, 0),
    1,
    PLACEMENT_GLYPH_COLOR,
    0.3,
    0.16,
  )
  arrow.userData = { kind: 'placement-view-direction' }
  // Always readable over the translucent datum planes.
  for (const m of [arrow.line.material, arrow.cone.material] as THREE.Material[]) {
    m.depthTest = false
    m.transparent = true
  }
  arrow.line.renderOrder = 12
  arrow.cone.renderOrder = 12
  group.add(arrow)
  return {
    group,
    update: (origin, direction, lengthMm) => {
      arrow.position.set(origin[0], origin[1], origin[2])
      arrow.setDirection(new THREE.Vector3(direction[0], direction[1], direction[2]).normalize())
      arrow.setLength(lengthMm, lengthMm * 0.3, lengthMm * 0.16)
    },
    dispose: () => arrow.dispose(),
  }
}
