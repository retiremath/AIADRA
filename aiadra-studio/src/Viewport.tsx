import { type MutableRefObject, useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { ImportedMesh } from './import/normalize'

/** Imperative viewport API the App drives (import lane + view helpers). */
export type ViewportApi = {
  fit: () => void
  reset: () => void
  setStyle: (s: DrawStyle) => void
  /** Show/hide the authored placeholder part (clear the viewport for imports). */
  setAuthoredVisible: (v: boolean) => void
  /** Show/hide the ground grid + axes helper. */
  setGridVisible: (v: boolean) => void
  /** Add reference-only imported geometry as one group keyed by `id` (ADR/0032 D5). */
  addImported: (id: string, meshes: ImportedMesh[]) => void
  /** Remove an imported group and dispose all its GPU resources (Codex1 B1). */
  removeImported: (id: string) => void
}

/**
 * AIADRA Studio viewport.
 *
 * Navigation (Creo/SolidWorks convention): LEFT = select, RIGHT = menu,
 * MIDDLE = rotate, MIDDLE+SHIFT = pan, MIDDLE+CTRL = zoom, SCROLL = zoom.
 *
 * Edges: the model's edges come from `EdgesGeometry` (feature/topological edges,
 * NOT the triangulation). SILHOUETTES (the view-dependent outline of curved
 * surfaces — which are NOT topological edges) come from a depth-discontinuity
 * post-process. Together they give a CAD line look in the +edges / hidden-line
 * modes. (Perfect topological edges incl. smooth tangent edges, and true analytic
 * silhouettes, await the milestone-2 BREP work.)
 */

type Menu = { x: number; y: number } | null
type DrawStyle = 'shaded' | 'shaded-edges' | 'hidden-line' | 'wireframe'

export default function Viewport({ apiRef: externalApi }: { apiRef?: MutableRefObject<ViewportApi | null> } = {}) {
  const mountRef = useRef<HTMLDivElement>(null)
  const localApi = useRef<ViewportApi | null>(null)
  const apiRef = externalApi ?? localApi

  const [menu, setMenu] = useState<Menu>(null)
  const [style, setStyle] = useState<DrawStyle>('shaded-edges')
  const [selected, setSelected] = useState(false)
  const [showAuthored, setShowAuthored] = useState(true)
  const [showGrid, setShowGrid] = useState(true)

  useEffect(() => {
    const mount = mountRef.current!
    const w = () => mount.clientWidth
    const h = () => mount.clientHeight

    const scene = new THREE.Scene()
    // Light, easy-on-the-eyes backdrop. NOTE: background + line colours are coupled
    // (light bg needs dark lines) — a coordinated theme is exactly what the planned
    // Appearance/Options system will own. These values are a stopgap default.
    scene.background = new THREE.Color(0xe6e9ec)

    const camera = new THREE.PerspectiveCamera(35, w() / h(), 0.1, 5000)
    const HOME = new THREE.Vector3(46, 34, 46)
    const TARGET = new THREE.Vector3(0, 2.5, 0)
    camera.position.copy(HOME)

    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(w(), h())
    mount.appendChild(renderer.domElement)
    const canvas = renderer.domElement

    // ---- Controls (CAD scheme) ----
    const controls = new OrbitControls(camera, canvas)
    controls.enableDamping = false // near-zero inertia: view stops when the mouse stops
    controls.screenSpacePanning = true // real pan (translate in screen plane), not orbit
    controls.zoomToCursor = true
    controls.target.copy(TARGET)
    controls.mouseButtons = { MIDDLE: THREE.MOUSE.ROTATE } as typeof controls.mouseButtons

    const onPointerDownCapture = (e: PointerEvent) => {
      if (e.button === 1) {
        e.preventDefault() // suppress middle-click autoscroll
        // OrbitControls flips ROTATE->PAN when a modifier is held: plain = rotate,
        // shift = pan, ctrl = dolly (zoom).
        controls.mouseButtons.MIDDLE = e.ctrlKey ? THREE.MOUSE.DOLLY : THREE.MOUSE.ROTATE
      }
      setMenu(null)
    }
    canvas.addEventListener('pointerdown', onPointerDownCapture, true)

    // ---- Lights ----
    scene.add(new THREE.AmbientLight(0xffffff, 0.55))
    const keyLight = new THREE.DirectionalLight(0xffffff, 0.95)
    keyLight.position.set(40, 70, 30)
    scene.add(keyLight)
    const fillLight = new THREE.DirectionalLight(0x88aaff, 0.35)
    fillLight.position.set(-50, 20, -30)
    scene.add(fillLight)

    // ---- Grid + axes. They stay OUT of the depth buffer (depthWrite:false) so the
    // silhouette post-process only outlines the parts, never the grid lines. ----
    const grid = new THREE.GridHelper(200, 40, 0x3a3d44, 0x2a2c31)
    ;(grid.material as THREE.Material).depthWrite = false
    scene.add(grid)
    const axes = new THREE.AxesHelper(12)
    ;(axes.material as THREE.Material).depthWrite = false
    scene.add(axes)

    // ---- Edges: two passes per part. `bright` = visible edges; `dim` = the
    // occluded edges shown faintly in hidden-line mode. Edges don't write depth
    // (faces do), keeping the silhouette depth clean. ----
    const makeEdges = (g: THREE.BufferGeometry, thresholdDeg: number, bright: number, dim: number) => {
      const eg = new THREE.EdgesGeometry(g, thresholdDeg)
      const b = new THREE.LineSegments(eg, new THREE.LineBasicMaterial({ color: bright, depthWrite: false }))
      const d = new THREE.LineSegments(eg, new THREE.LineBasicMaterial({ color: dim, depthWrite: false }))
      b.name = 'edges'
      b.renderOrder = 2
      d.name = 'edgesDim'
      d.renderOrder = 1
      return { b, d, eg }
    }

    /**
     * Apply a CAD draw style to a part (its mesh + bright/dim edge children).
     * We NEVER use raw `material.wireframe` (that draws the triangulation):
     *   shaded        faces shaded, no edges
     *   shaded-edges  faces shaded + visible (bright) edges
     *   hidden-line   faces invisible but WRITE DEPTH → visible edges bright,
     *                 occluded edges dim
     *   wireframe     faces invisible AND non-occluding → all edges bright, see-through
     * Faces stay `visible` (so the child edge lines render) — hidden via colorWrite.
     */
    const styleMesh = (m: THREE.Mesh, bright: THREE.LineSegments, dim: THREE.LineSegments, s: DrawStyle) => {
      const mm = m.material as THREE.MeshStandardMaterial
      mm.wireframe = false
      mm.colorWrite = s === 'shaded' || s === 'shaded-edges'
      mm.depthWrite = s !== 'wireframe'
      bright.visible = s !== 'shaded'
      ;(bright.material as THREE.LineBasicMaterial).depthTest = s !== 'wireframe'
      dim.visible = s === 'hidden-line'
    }
    const edgesOf = (m: THREE.Mesh) => ({
      bright: m.getObjectByName('edges') as THREE.LineSegments | undefined,
      dim: m.getObjectByName('edgesDim') as THREE.LineSegments | undefined,
    })
    const applyStyleToImport = (group: THREE.Group, s: DrawStyle) => {
      group.traverse((o) => {
        const m = o as THREE.Mesh
        if (m.isMesh) {
          const { bright, dim } = edgesOf(m)
          if (bright && dim) styleMesh(m, bright, dim, s)
        }
      })
    }

    // ---- The authored bracket: 20 x 5 x 10 mm (placeholder until the Workspace lane) ----
    const geo = new THREE.BoxGeometry(20, 5, 10)
    const mat = new THREE.MeshStandardMaterial({
      color: 0x6b9bd1,
      metalness: 0.15,
      roughness: 0.55,
      polygonOffset: true, // let edges sit on faces without z-fight
      polygonOffsetFactor: 1,
      polygonOffsetUnits: 1,
    })
    const mesh = new THREE.Mesh(geo, mat)
    mesh.position.y = 2.5
    scene.add(mesh)
    const authoredEdges = makeEdges(geo, 1, 0x1f3a5c, 0xb4bac2) // dark edges for the light bg; faint dim
    mesh.add(authoredEdges.b)
    mesh.add(authoredEdges.d)

    // ---- Imported (reference-only) geometry: one THREE.Group per import id (Codex1 N3) ----
    const importGroups = new Map<string, THREE.Group>()
    let currentStyle: DrawStyle = 'shaded-edges'
    // Feature-edge threshold for imports: drop tessellation facets on curved faces,
    // keep sharp model edges.
    const IMPORT_EDGE_ANGLE = 30

    // ---- Silhouette post-process: render the scene to a target with a depth
    // texture, then a fullscreen pass draws a line wherever depth jumps (object
    // outline + curved-surface silhouettes + part-over-part contours). ----
    const dbSize = renderer.getDrawingBufferSize(new THREE.Vector2())
    const depthTexture = new THREE.DepthTexture(dbSize.x, dbSize.y)
    const sceneTarget = new THREE.WebGLRenderTarget(dbSize.x, dbSize.y, { depthTexture, depthBuffer: true })
    const edgePass = new THREE.ShaderMaterial({
      depthTest: false,
      depthWrite: false,
      uniforms: {
        tDiffuse: { value: sceneTarget.texture },
        tDepth: { value: depthTexture },
        uTexel: { value: new THREE.Vector2(1 / dbSize.x, 1 / dbSize.y) },
        uNear: { value: camera.near },
        uFar: { value: camera.far },
        uEdgeColor: { value: new THREE.Color(0x12151a) },
        uThreshold: { value: 0.12 },
        uStrength: { value: 1.0 },
        uEnabled: { value: 1.0 },
      },
      vertexShader: /* glsl */ `
        varying vec2 vUv;
        void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }
      `,
      fragmentShader: /* glsl */ `
        precision highp float;
        varying vec2 vUv;
        uniform sampler2D tDiffuse;
        uniform sampler2D tDepth;
        uniform vec2 uTexel;
        uniform float uNear;
        uniform float uFar;
        uniform vec3 uEdgeColor;
        uniform float uThreshold;
        uniform float uStrength;
        uniform float uEnabled;
        float lin(float d) {
          float z = d * 2.0 - 1.0;
          return (2.0 * uNear * uFar) / (uFar + uNear - z * (uFar - uNear));
        }
        void main() {
          vec3 col = texture2D(tDiffuse, vUv).rgb;
          if (uEnabled < 0.5) { gl_FragColor = vec4(col, 1.0); return; }
          float c = lin(texture2D(tDepth, vUv).x);
          float l = lin(texture2D(tDepth, vUv - vec2(uTexel.x, 0.0)).x);
          float r = lin(texture2D(tDepth, vUv + vec2(uTexel.x, 0.0)).x);
          float u = lin(texture2D(tDepth, vUv + vec2(0.0, uTexel.y)).x);
          float dn = lin(texture2D(tDepth, vUv - vec2(0.0, uTexel.y)).x);
          float diff = max(max(abs(c - l), abs(c - r)), max(abs(c - u), abs(c - dn)));
          float t = uThreshold * c;
          float edge = smoothstep(t, t * 2.0 + 0.0001, diff);
          gl_FragColor = vec4(mix(col, uEdgeColor, edge * uStrength), 1.0);
        }
      `,
    })
    const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), edgePass)
    const quadScene = new THREE.Scene()
    quadScene.add(quad)
    const quadCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1)

    styleMesh(mesh, authoredEdges.b, authoredEdges.d, currentStyle) // initial state

    // ---- Left-click selection (placeholder: select the authored part) ----
    const raycaster = new THREE.Raycaster()
    const ndc = new THREE.Vector2()
    let downX = 0
    let downY = 0
    const onLeftDown = (e: PointerEvent) => {
      if (e.button === 0) {
        downX = e.clientX
        downY = e.clientY
      }
    }
    const onLeftUp = (e: PointerEvent) => {
      if (e.button !== 0) return
      if (Math.hypot(e.clientX - downX, e.clientY - downY) > 4) return // was a drag
      const r = canvas.getBoundingClientRect()
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
      raycaster.setFromCamera(ndc, camera)
      const hit = mesh.visible && raycaster.intersectObject(mesh, false).length > 0
      mat.emissive.setHex(hit ? 0x16314e : 0x000000)
      setSelected(hit)
    }
    canvas.addEventListener('pointerdown', onLeftDown)
    canvas.addEventListener('pointerup', onLeftUp)

    const onContextMenu = (e: MouseEvent) => {
      e.preventDefault()
      const r = canvas.getBoundingClientRect()
      setMenu({ x: e.clientX - r.left, y: e.clientY - r.top })
    }
    canvas.addEventListener('contextmenu', onContextMenu)

    // ---- View helpers ----
    const fit = () => {
      const box = new THREE.Box3()
      if (mesh.visible) box.expandByObject(mesh)
      for (const g of importGroups.values()) box.expandByObject(g)
      if (box.isEmpty()) return
      const sphere = box.getBoundingSphere(new THREE.Sphere())
      const dir = camera.position.clone().sub(controls.target).normalize()
      const dist = sphere.radius / Math.sin((camera.fov * Math.PI) / 180 / 2)
      controls.target.copy(sphere.center)
      camera.position.copy(sphere.center).addScaledVector(dir, dist * 1.15)
      camera.near = dist / 100
      camera.far = dist * 100
      camera.updateProjectionMatrix()
      controls.update()
    }
    const reset = () => {
      camera.position.copy(HOME)
      controls.target.copy(TARGET)
      camera.updateProjectionMatrix()
      controls.update()
    }
    const setStyle = (s: DrawStyle) => {
      currentStyle = s
      styleMesh(mesh, authoredEdges.b, authoredEdges.d, s)
      for (const g of importGroups.values()) applyStyleToImport(g, s)
      // Silhouette overlay only in the edge-bearing modes; light line on the dark
      // hidden-line backdrop, dark line over the shaded surface.
      edgePass.uniforms.uEnabled.value = s === 'shaded-edges' || s === 'hidden-line' ? 1 : 0
      edgePass.uniforms.uEdgeColor.value.set(0x1b1f25) // dark silhouette on the light bg
    }
    const setAuthoredVisible = (v: boolean) => {
      mesh.visible = v
    }
    const setGridVisible = (v: boolean) => {
      grid.visible = v
      axes.visible = v
    }

    const disposeGroup = (group: THREE.Group) => {
      group.traverse((o) => {
        const obj = o as THREE.Mesh & THREE.LineSegments
        if (obj.isMesh || obj.isLineSegments) {
          obj.geometry?.dispose()
          const mats = Array.isArray(obj.material) ? obj.material : [obj.material]
          mats.forEach((m) => m?.dispose())
        }
      })
    }

    const addImported = (id: string, meshes: ImportedMesh[]) => {
      const existing = importGroups.get(id)
      if (existing) {
        scene.remove(existing)
        disposeGroup(existing)
      }
      const group = new THREE.Group()
      group.name = `import:${id}`
      for (const m of meshes) {
        const g = new THREE.BufferGeometry()
        g.setAttribute('position', new THREE.BufferAttribute(m.position, 3))
        if (m.normal) g.setAttribute('normal', new THREE.BufferAttribute(m.normal, 3))
        if (m.index) g.setIndex(new THREE.BufferAttribute(m.index, 1))
        if (!m.normal) g.computeVertexNormals()
        const im = new THREE.Mesh(
          g,
          new THREE.MeshStandardMaterial({
            color: 0x9aa0a6, // neutral grey — NOT the authored blue
            metalness: 0.1,
            roughness: 0.8,
            polygonOffset: true,
            polygonOffsetFactor: 1,
            polygonOffsetUnits: 1,
          }),
        )
        const e = makeEdges(g, IMPORT_EDGE_ANGLE, 0x33373d, 0xb4bac2)
        im.add(e.b)
        im.add(e.d)
        styleMesh(im, e.b, e.d, currentStyle)
        group.add(im)
      }
      scene.add(group)
      importGroups.set(id, group)
      fit()
    }

    const removeImported = (id: string) => {
      const group = importGroups.get(id)
      if (!group) return
      scene.remove(group)
      disposeGroup(group)
      importGroups.delete(id)
    }

    apiRef.current = { fit, reset, setStyle, setAuthoredVisible, setGridVisible, addImported, removeImported }

    const onResize = () => {
      camera.aspect = w() / h()
      camera.updateProjectionMatrix()
      renderer.setSize(w(), h())
      const s = renderer.getDrawingBufferSize(new THREE.Vector2())
      sceneTarget.setSize(s.x, s.y)
      edgePass.uniforms.uTexel.value.set(1 / s.x, 1 / s.y)
    }
    window.addEventListener('resize', onResize)

    let rafId = 0
    const animate = () => {
      rafId = requestAnimationFrame(animate)
      controls.update()
      edgePass.uniforms.uNear.value = camera.near
      edgePass.uniforms.uFar.value = camera.far
      // pass 1: scene → target (colour + depth); pass 2: silhouette composite → screen.
      renderer.setRenderTarget(sceneTarget)
      renderer.render(scene, camera)
      renderer.setRenderTarget(null)
      renderer.render(quadScene, quadCam)
    }
    animate()

    return () => {
      cancelAnimationFrame(rafId)
      window.removeEventListener('resize', onResize)
      canvas.removeEventListener('pointerdown', onPointerDownCapture, true)
      canvas.removeEventListener('pointerdown', onLeftDown)
      canvas.removeEventListener('pointerup', onLeftUp)
      canvas.removeEventListener('contextmenu', onContextMenu)
      controls.dispose()
      renderer.dispose()
      geo.dispose()
      mat.dispose()
      authoredEdges.eg.dispose()
      authoredEdges.b.material.dispose()
      authoredEdges.d.material.dispose()
      for (const g of importGroups.values()) disposeGroup(g)
      importGroups.clear()
      sceneTarget.dispose()
      depthTexture.dispose()
      edgePass.dispose()
      quad.geometry.dispose()
      apiRef.current = null
      if (canvas.parentNode === mount) mount.removeChild(canvas)
    }
  }, [])

  const pick = (s: DrawStyle) => {
    setStyle(s)
    apiRef.current?.setStyle(s)
    setMenu(null)
  }

  return (
    <div className="viewport-canvas">
      <div ref={mountRef} style={{ position: 'absolute', inset: 0 }} />
      {selected && <div className="sel-badge small">selected: BracketSpike (P-000001)</div>}
      {menu && (
        <ul
          className="ctx-menu"
          style={{ left: menu.x, top: menu.y }}
          onPointerDown={(e) => e.stopPropagation()}
        >
          <li onClick={() => { apiRef.current?.fit(); setMenu(null) }}>Fit to view</li>
          <li onClick={() => { apiRef.current?.reset(); setMenu(null) }}>Reset view</li>
          <li className="sep" />
          <li
            className={showAuthored ? 'on' : ''}
            onClick={() => { const v = !showAuthored; setShowAuthored(v); apiRef.current?.setAuthoredVisible(v); setMenu(null) }}
          >
            Authored part
          </li>
          <li
            className={showGrid ? 'on' : ''}
            onClick={() => { const v = !showGrid; setShowGrid(v); apiRef.current?.setGridVisible(v); setMenu(null) }}
          >
            Grid
          </li>
          <li className="sep" />
          <li className={style === 'shaded' ? 'on' : ''} onClick={() => pick('shaded')}>Shaded</li>
          <li className={style === 'shaded-edges' ? 'on' : ''} onClick={() => pick('shaded-edges')}>Shaded + edges</li>
          <li className={style === 'hidden-line' ? 'on' : ''} onClick={() => pick('hidden-line')}>Hidden line</li>
          <li className={style === 'wireframe' ? 'on' : ''} onClick={() => pick('wireframe')}>Wireframe</li>
          <li className="sep" />
          <li className="disabled">Operations (with selection) — soon</li>
        </ul>
      )}
    </div>
  )
}
