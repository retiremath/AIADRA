/**
 * The axis-triad gnomon (arc 20260625-1 / 6c). A small RGB X/Y/Z indicator drawn
 * as a second scissor-corner overlay (bottom-left), mirroring the main camera —
 * the CAD orientation cue beside the nav cube. Indicator only: no interaction.
 * Browser-only (three.js + canvas letter sprites); never imported by vitest.
 */
import * as THREE from 'three'
import type { Vec3 } from '../display/viewOrientation'

export interface AxisGnomon {
  syncToMainView(direction: Vec3, up: Vec3): void
  render(renderer: THREE.WebGLRenderer, glRect: { x: number; y: number; width: number; height: number }): void
  dispose(): void
}

function letterSprite(text: string, color: number): THREE.Sprite {
  const px = 64
  const cv = document.createElement('canvas')
  cv.width = cv.height = px
  const ctx = cv.getContext('2d')!
  ctx.fillStyle = `#${color.toString(16).padStart(6, '0')}`
  ctx.font = 'bold 44px system-ui, sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(text, px / 2, px / 2)
  const tex = new THREE.CanvasTexture(cv)
  tex.needsUpdate = true
  const mat = new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true })
  const sprite = new THREE.Sprite(mat)
  sprite.scale.set(0.5, 0.5, 0.5)
  return sprite
}

export function createAxisGnomon(): AxisGnomon {
  const scene = new THREE.Scene()
  const camera = new THREE.OrthographicCamera(-1.6, 1.6, 1.6, -1.6, 0.01, 100)
  camera.up.set(0, 0, 1)

  const AXES: { dir: Vec3; color: number; label: string }[] = [
    { dir: [1, 0, 0], color: 0xd6553f, label: 'X' },
    { dir: [0, 1, 0], color: 0x4f9a52, label: 'Y' },
    { dir: [0, 0, 1], color: 0x4a7fb5, label: 'Z' },
  ]
  const disposables: { dispose(): void }[] = []
  const L = 1.0
  for (const a of AXES) {
    const tip = new THREE.Vector3(a.dir[0], a.dir[1], a.dir[2]).multiplyScalar(L)
    const geom = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), tip])
    const mat = new THREE.LineBasicMaterial({ color: a.color, depthTest: false })
    const line = new THREE.Line(geom, mat)
    line.renderOrder = 1
    scene.add(line)
    const label = letterSprite(a.label, a.color)
    label.position.copy(tip).multiplyScalar(1.22)
    label.renderOrder = 2
    scene.add(label)
    disposables.push(geom, mat, label.material, (label.material as THREE.SpriteMaterial).map!)
  }

  const DIST = 6
  const syncToMainView = (direction: Vec3, up: Vec3) => {
    const d = new THREE.Vector3(direction[0], direction[1], direction[2]).normalize()
    camera.up.set(up[0], up[1], up[2])
    camera.position.set(-d.x * DIST, -d.y * DIST, -d.z * DIST)
    camera.lookAt(0, 0, 0)
    camera.updateMatrixWorld()
  }

  const render = (
    renderer: THREE.WebGLRenderer,
    glRect: { x: number; y: number; width: number; height: number },
  ) => {
    const prevViewport = new THREE.Vector4()
    const prevScissor = new THREE.Vector4()
    renderer.getViewport(prevViewport)
    renderer.getScissor(prevScissor)
    const prevScissorTest = renderer.getScissorTest()
    const prevAutoClear = renderer.autoClear

    renderer.setViewport(glRect.x, glRect.y, glRect.width, glRect.height)
    renderer.setScissor(glRect.x, glRect.y, glRect.width, glRect.height)
    renderer.setScissorTest(true)
    renderer.autoClear = false
    renderer.clearDepth()
    renderer.render(scene, camera)

    renderer.setViewport(prevViewport)
    renderer.setScissor(prevScissor)
    renderer.setScissorTest(prevScissorTest)
    renderer.autoClear = prevAutoClear
  }

  const dispose = () => {
    for (const d of disposables) d.dispose()
  }

  return { syncToMainView, render, dispose }
}
