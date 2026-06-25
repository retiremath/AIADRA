/**
 * The interactive nav cube (arc 20260625-1 / 6c; ADR/0033 D9/D10, Codex1 B1).
 * A small world-axis-aligned **chamfered** cube drawn as a scissor-corner overlay
 * on the main `WebGLRenderer`. Its camera mirrors the MAIN camera's look
 * direction, so the cube turns with the model; clicking a face / edge / corner
 * facet snaps the main camera to the matching orientation (the shared
 * `viewOrientation` table).
 *
 * The 26 ADR-pick regions ARE the cube's facets (6 labeled squares + 12 edge
 * bevels + 8 corner triangles), so the visible geometry and the hit-test are one
 * and the same — the FreeCAD-style cube. Browser-only (three.js + canvas label
 * textures); never imported by the node vitest suite. The pure, testable pieces
 * live in `navCubeRect.ts` and `display/viewOrientation.ts`.
 *
 * B1 isolation contract:
 *  - `render` saves and restores the renderer's viewport / scissor / scissorTest
 *    / autoClear so the main pass + HLR overlay are never order-dependent;
 *  - the cube camera mirror does NOT feed the settle machine — only a programmatic
 *    MAIN-camera change (from a click) does, and that is the viewport's call.
 */
import * as THREE from 'three'
import {
  cubeRegions,
  type CubeRegion,
  type Vec3,
  type ViewOrientation,
} from '../display/viewOrientation'

export interface NavCube {
  scene: THREE.Scene
  camera: THREE.OrthographicCamera
  syncToMainView(direction: Vec3, up: Vec3): void
  pickRegion(ndcX: number, ndcY: number): CubeRegion | null
  setHover(region: CubeRegion | null): void
  applyTheme(faceColor: number, edgeColor: number, hoverColor: number): void
  render(renderer: THREE.WebGLRenderer, glRect: { x: number; y: number; width: number; height: number }): void
  dispose(): void
}

const FACE_LABEL: Record<string, string> = {
  '0,-1,0': 'FRONT', '0,1,0': 'BACK',
  '1,0,0': 'RIGHT', '-1,0,0': 'LEFT',
  '0,0,1': 'TOP', '0,0,-1': 'BOTTOM',
}

const S = 1 // half-size
const C = 0.28 // chamfer — larger bevels give bigger, easier-to-hit edge/corner facets

function darken(hex: number, f: number): number {
  const r = Math.round(((hex >> 16) & 0xff) * f)
  const g = Math.round(((hex >> 8) & 0xff) * f)
  const b = Math.round((hex & 0xff) * f)
  return (r << 16) | (g << 8) | b
}

// A white-background label texture (the facet color comes from material.color,
// which multiplies the map — so hover re-tints without rebuilding the texture).
function labelTexture(text: string): THREE.CanvasTexture {
  const px = 128
  const cv = document.createElement('canvas')
  cv.width = cv.height = px
  const ctx = cv.getContext('2d')!
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, px, px)
  ctx.fillStyle = '#1b2530'
  ctx.font = 'bold 21px system-ui, sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(text, px / 2, px / 2)
  const tex = new THREE.CanvasTexture(cv)
  tex.anisotropy = 4
  tex.flipY = false // map canvas top-left → UV(0,0) so labels read upright
  tex.needsUpdate = true
  return tex
}

type Facet = {
  region: CubeRegion
  mesh: THREE.Mesh
  material: THREE.MeshBasicMaterial
  baseColor: number
}

function v(a: number, b: number, c: number): THREE.Vector3 {
  return new THREE.Vector3(a, b, c)
}

// Build one facet geometry from its corner points (3 = corner triangle, 4 = quad).
function facetGeometry(pts: THREE.Vector3[], withUv: boolean): THREE.BufferGeometry {
  const g = new THREE.BufferGeometry()
  const pos: number[] = []
  for (const p of pts) pos.push(p.x, p.y, p.z)
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3))
  if (pts.length === 4) {
    g.setIndex([0, 1, 2, 0, 2, 3])
    if (withUv) g.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, 1, 0, 1, 1, 0, 1], 2))
  } else {
    g.setIndex([0, 1, 2])
  }
  return g
}

// The corner points of a region's facet, in winding order.
function facetPoints(region: CubeRegion): { pts: THREE.Vector3[]; uv: boolean } {
  const e = S - C
  const [x, y, z] = region.cell
  if (region.type === 'face') {
    // A square inset by the chamfer, oriented to the standard-view up so the
    // label reads upright. `right` is SCREEN-right when looking at the face
    // (view dir = −normal): screen-right = normal × up. With flipY=false and the
    // verts ordered top-left → top-right → bottom-right → bottom-left, UV
    // (0,0)..(1,1) maps the canvas upright onto the facet.
    const n = new THREE.Vector3(...region.normal)
    const up = new THREE.Vector3(...region.orientation.up)
    // Top/bottom labels: the standard-view up (±Y) reads in the top/bottom view
    // but projects DOWN at the iso default — flip them so they read at iso (the
    // common nav-cube convention; side faces keep +Z up and read either way).
    if (Math.abs(n.z) > 0.5) up.set(0, n.z > 0 ? -1 : 1, 0)
    // Screen-right when looking at the face = camera local +X = up × normal.
    const right = new THREE.Vector3().crossVectors(up, n).normalize()
    const center = n.clone().multiplyScalar(S)
    const p = (sr: number, su: number) =>
      center.clone().addScaledVector(right, sr * e).addScaledVector(up, su * e)
    return { pts: [p(-1, 1), p(1, 1), p(1, -1), p(-1, -1)], uv: true }
  }
  if (region.type === 'edge') {
    // The 45° bevel quad between the two adjacent faces. Axes a,b are nonzero;
    // k is the run axis.
    const ax = [x, y, z]
    const k = ax.findIndex((c) => c === 0)
    const [a, b] = [0, 1, 2].filter((i) => i !== k)
    const mk = (ca: number, cb: number, ck: number): THREE.Vector3 => {
      const out = [0, 0, 0]
      out[a] = ca
      out[b] = cb
      out[k] = ck
      return v(out[0], out[1], out[2])
    }
    const sa = ax[a]
    const sb = ax[b]
    return {
      pts: [
        mk(sa * S, sb * e, -e),
        mk(sa * S, sb * e, e),
        mk(sa * e, sb * S, e),
        mk(sa * e, sb * S, -e),
      ],
      uv: false,
    }
  }
  // corner triangle
  return {
    pts: [v(x * S, y * e, z * e), v(x * e, y * S, z * e), v(x * e, y * e, z * S)],
    uv: false,
  }
}

export function createNavCube(): NavCube {
  const scene = new THREE.Scene()
  const camera = new THREE.OrthographicCamera(-1.45, 1.45, 1.45, -1.45, 0.01, 100)
  camera.up.set(0, 0, 1)

  let faceColor = 0xaab2bb
  let edgeColor = 0x2c3137
  let hoverColor = 0x4a7fb5

  const facets: Facet[] = []
  const borderSegs: number[] = []
  for (const region of cubeRegions()) {
    const { pts, uv } = facetPoints(region)
    const base =
      region.type === 'face' ? faceColor : region.type === 'edge' ? darken(faceColor, 0.9) : darken(faceColor, 0.8)
    const material = new THREE.MeshBasicMaterial({
      color: base,
      side: THREE.DoubleSide,
      map: region.type === 'face' ? labelTexture(FACE_LABEL[region.cell.join(',')]) : null,
    })
    const mesh = new THREE.Mesh(facetGeometry(pts, uv), material)
    mesh.userData = { region }
    scene.add(mesh)
    facets.push({ region, mesh, material, baseColor: base })
    // dark facet outline
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i]
      const b = pts[(i + 1) % pts.length]
      borderSegs.push(a.x, a.y, a.z, b.x, b.y, b.z)
    }
  }

  const borderGeom = new THREE.BufferGeometry()
  borderGeom.setAttribute('position', new THREE.Float32BufferAttribute(borderSegs, 3))
  const borderMat = new THREE.LineBasicMaterial({ color: edgeColor })
  const border = new THREE.LineSegments(borderGeom, borderMat)
  scene.add(border)

  const raycaster = new THREE.Raycaster()
  const ndc = new THREE.Vector2()
  const DIST = 6
  let hovered: Facet | null = null

  const syncToMainView = (direction: Vec3, up: Vec3) => {
    const d = new THREE.Vector3(direction[0], direction[1], direction[2]).normalize()
    camera.up.set(up[0], up[1], up[2])
    camera.position.set(-d.x * DIST, -d.y * DIST, -d.z * DIST)
    camera.lookAt(0, 0, 0)
    camera.updateMatrixWorld()
  }

  const pickRegion = (ndcX: number, ndcY: number): CubeRegion | null => {
    ndc.set(ndcX, ndcY)
    raycaster.setFromCamera(ndc, camera)
    const hits = raycaster.intersectObjects(facets.map((f) => f.mesh), false)
    return hits.length ? (hits[0].object.userData.region as CubeRegion) : null
  }

  const setHover = (region: CubeRegion | null) => {
    const next = region ? facets.find((f) => f.region === region) ?? null : null
    if (next === hovered) return
    if (hovered) hovered.material.color.setHex(hovered.baseColor)
    hovered = next
    if (hovered) hovered.material.color.setHex(hoverColor)
  }

  const applyTheme = (face: number, edge: number, hoverC: number) => {
    faceColor = face
    edgeColor = edge
    hoverColor = hoverC
    for (const f of facets) {
      f.baseColor =
        f.region.type === 'face' ? faceColor : f.region.type === 'edge' ? darken(faceColor, 0.9) : darken(faceColor, 0.8)
      if (f !== hovered) f.material.color.setHex(f.baseColor)
    }
    borderMat.color.setHex(edgeColor)
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
    for (const f of facets) {
      f.mesh.geometry.dispose()
      f.material.map?.dispose()
      f.material.dispose()
    }
    borderGeom.dispose()
    borderMat.dispose()
  }

  return { scene, camera, syncToMainView, pickRegion, setHover, applyTheme, render, dispose }
}

export type { ViewOrientation }
