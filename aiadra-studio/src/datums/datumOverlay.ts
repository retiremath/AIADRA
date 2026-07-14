/**
 * The datum overlay (arc 20260714-2 EP1) — the Creo-paradigm empty-part
 * scaffold: three labeled translucent principal datum planes + the origin
 * coordinate-system triad, rendered as an OVERLAY lane in the viewport.
 *
 * These carry the stable intrinsic ids Codex1 pinned (`intrinsic-plane:xy|yz|zx`
 * / `intrinsic-csys:origin`) in `userData` — overlay-lane identity only, NEVER
 * leaked into Product Truth (a plane pick commits the engine's principal-plane
 * enum record). The group is NOT a pick target for canonical selection (it
 * lives outside the canonical part group); in-viewport click-to-pick is a
 * later polish — the pick surface today is the plane chooser.
 *
 * Studio labels follow the Creo convention: FRONT=xy · RIGHT=yz · TOP=zx.
 */
import * as THREE from 'three'
import {
  INTRINSIC_CSYS_ID,
  INTRINSIC_PLANE_IDS,
  PLANE_LABELS,
  type PlaneOrientation,
} from '../authoring/backend'

export interface DatumOverlay {
  group: THREE.Group
  setVisible(v: boolean): void
  dispose(): void
}

const PLANE_COLORS: Record<PlaneOrientation, number> = {
  xy: 0x6b9bd1, // FRONT — the accent blue
  yz: 0xc98f6b, // RIGHT — warm
  zx: 0x7bbf7b, // TOP — green
}

/** The plane quad's local basis per orientation: (u, v) → global. */
const PLANE_AXES: Record<PlaneOrientation, [THREE.Vector3, THREE.Vector3]> = {
  xy: [new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 1, 0)],
  yz: [new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, 1)],
  zx: [new THREE.Vector3(0, 0, 1), new THREE.Vector3(1, 0, 0)],
}

export function createDatumOverlay(halfSize = 60): DatumOverlay {
  const group = new THREE.Group()
  group.name = 'datum-overlay'
  const disposables: { dispose(): void }[] = []

  for (const ori of ['xy', 'yz', 'zx'] as PlaneOrientation[]) {
    const [u, v] = PLANE_AXES[ori]
    const color = PLANE_COLORS[ori]

    // The translucent quad (double-sided, never depth-writing so geometry
    // behind it stays visible — the Creo datum look).
    const quadGeom = new THREE.BufferGeometry()
    const corners = [
      u.clone().multiplyScalar(-halfSize).addScaledVector(v, -halfSize),
      u.clone().multiplyScalar(halfSize).addScaledVector(v, -halfSize),
      u.clone().multiplyScalar(halfSize).addScaledVector(v, halfSize),
      u.clone().multiplyScalar(-halfSize).addScaledVector(v, halfSize),
    ]
    quadGeom.setFromPoints([corners[0], corners[1], corners[2], corners[0], corners[2], corners[3]])
    quadGeom.computeVertexNormals()
    const quadMat = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: 0.08,
      side: THREE.DoubleSide,
      depthWrite: false,
    })
    const quad = new THREE.Mesh(quadGeom, quadMat)
    quad.name = INTRINSIC_PLANE_IDS[ori]
    quad.userData = { kind: 'intrinsic-plane', intrinsicId: INTRINSIC_PLANE_IDS[ori], orientation: ori }
    group.add(quad)
    disposables.push(quadGeom, quadMat)

    // The border.
    const borderGeom = new THREE.BufferGeometry().setFromPoints([
      corners[0], corners[1], corners[2], corners[3], corners[0],
    ])
    const borderMat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.5 })
    const border = new THREE.Line(borderGeom, borderMat)
    border.userData = { kind: 'intrinsic-plane-border', intrinsicId: INTRINSIC_PLANE_IDS[ori] }
    group.add(border)
    disposables.push(borderGeom, borderMat)

    // The corner label sprite (canvas-textured, always camera-facing).
    // Browser-only chrome: headless environments (node tests) skip labels.
    const label = makeLabelSprite(PLANE_LABELS[ori], color)
    if (label) {
      label.position.copy(
        u.clone().multiplyScalar(halfSize * 0.86).addScaledVector(v, halfSize * 0.9),
      )
      label.userData = { kind: 'intrinsic-plane-label', intrinsicId: INTRINSIC_PLANE_IDS[ori] }
      group.add(label)
      disposables.push(label.material as THREE.SpriteMaterial)
      disposables.push((label.material as THREE.SpriteMaterial).map as THREE.Texture)
    }
  }

  // The origin coordinate-system triad.
  const triad = new THREE.AxesHelper(halfSize * 0.35)
  triad.name = INTRINSIC_CSYS_ID
  triad.userData = { kind: 'intrinsic-csys', intrinsicId: INTRINSIC_CSYS_ID }
  group.add(triad)
  disposables.push(triad.geometry, triad.material as THREE.Material)
  const originLabel = makeLabelSprite('Origin', 0xf3f4f6)
  if (originLabel) {
    originLabel.position.set(halfSize * 0.04, halfSize * 0.04, halfSize * 0.04)
    originLabel.scale.multiplyScalar(0.8)
    group.add(originLabel)
    disposables.push(originLabel.material as THREE.SpriteMaterial)
    disposables.push((originLabel.material as THREE.SpriteMaterial).map as THREE.Texture)
  }

  return {
    group,
    setVisible: (v) => {
      group.visible = v
    },
    dispose: () => {
      for (const d of disposables) d.dispose()
    },
  }
}

function makeLabelSprite(text: string, color: number): THREE.Sprite | null {
  if (typeof document === 'undefined') return null // headless (node tests)
  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 64
  const ctx = canvas.getContext('2d')
  if (ctx) {
    ctx.font = '600 40px system-ui, sans-serif'
    ctx.fillStyle = `#${color.toString(16).padStart(6, '0')}`
    ctx.textBaseline = 'middle'
    ctx.fillText(text, 8, 32)
  }
  const texture = new THREE.CanvasTexture(canvas)
  texture.anisotropy = 4
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthWrite: false,
    depthTest: false,
  })
  const sprite = new THREE.Sprite(material)
  sprite.scale.set(22, 5.5, 1)
  return sprite
}
