import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

/**
 * AIADRA Studio viewport — bootstrap spike.
 *
 * CAD-style navigation (Creo/SolidWorks convention):
 *   - LEFT   = selection (+ selection box, later) — NOT camera
 *   - RIGHT  = context menu — NOT camera
 *   - MIDDLE = rotate (orbit)
 *   - MIDDLE + SHIFT = pan (true screen-space translation)
 *   - MIDDLE + CTRL  = zoom (dolly)
 *   - SCROLL = zoom
 * Near-zero inertia (damping off). Real pan (screenSpacePanning). Narrow FOV
 * to reduce perspective distortion. Zoom-to-cursor.
 */

type Menu = { x: number; y: number } | null
type DrawStyle = 'shaded' | 'wireframe' | 'shaded-edges'

export default function Viewport() {
  const mountRef = useRef<HTMLDivElement>(null)
  const apiRef = useRef<{
    fit: () => void
    reset: () => void
    setStyle: (s: DrawStyle) => void
  } | null>(null)

  const [menu, setMenu] = useState<Menu>(null)
  const [style, setStyle] = useState<DrawStyle>('shaded-edges')
  const [selected, setSelected] = useState(false)

  useEffect(() => {
    const mount = mountRef.current!
    const w = () => mount.clientWidth
    const h = () => mount.clientHeight

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x1e1f22)

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
    // Free LEFT + RIGHT from the camera (selection + context menu); MIDDLE drives the camera.
    controls.mouseButtons = { MIDDLE: THREE.MOUSE.ROTATE } as typeof controls.mouseButtons

    // Modifier-based middle-button action: plain = rotate, +shift = pan, +ctrl = zoom.
    // Set BEFORE OrbitControls' own pointerdown handler reads it (capture phase).
    const onPointerDownCapture = (e: PointerEvent) => {
      if (e.button === 1) {
        e.preventDefault() // suppress middle-click autoscroll
        // OrbitControls internally flips ROTATE -> PAN whenever a modifier
        // (ctrl/meta/shift) is held (see its onMouseDown). So we lean on that:
        //   plain middle    -> ROTATE (no modifier) -> rotate
        //   shift + middle  -> ROTATE (+shift)       -> OrbitControls flips to PAN
        //   ctrl  + middle  -> DOLLY  (never flipped) -> zoom
        controls.mouseButtons.MIDDLE = e.ctrlKey ? THREE.MOUSE.DOLLY : THREE.MOUSE.ROTATE
      }
      setMenu(null) // any press dismisses the context menu
    }
    canvas.addEventListener('pointerdown', onPointerDownCapture, true)

    // ---- Scene ----
    scene.add(new THREE.AmbientLight(0xffffff, 0.55))
    const keyLight = new THREE.DirectionalLight(0xffffff, 0.95)
    keyLight.position.set(40, 70, 30)
    scene.add(keyLight)
    const fillLight = new THREE.DirectionalLight(0x88aaff, 0.35)
    fillLight.position.set(-50, 20, -30)
    scene.add(fillLight)

    const grid = new THREE.GridHelper(200, 40, 0x3a3d44, 0x2a2c31)
    scene.add(grid)
    scene.add(new THREE.AxesHelper(12))

    // The authored bracket: 20 (x) x 5 (height) x 10 (depth) mm
    const geo = new THREE.BoxGeometry(20, 5, 10)
    const mat = new THREE.MeshStandardMaterial({
      color: 0x6b9bd1,
      metalness: 0.15,
      roughness: 0.55,
    })
    const mesh = new THREE.Mesh(geo, mat)
    mesh.position.y = 2.5
    scene.add(mesh)
    const edges = new THREE.LineSegments(
      new THREE.EdgesGeometry(geo),
      new THREE.LineBasicMaterial({ color: 0x16314e }),
    )
    mesh.add(edges)

    // ---- Left-click selection (placeholder: select the part; topology lands later) ----
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
      if (Math.hypot(e.clientX - downX, e.clientY - downY) > 4) return // was a drag, not a click
      const r = canvas.getBoundingClientRect()
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
      raycaster.setFromCamera(ndc, camera)
      const hit = raycaster.intersectObject(mesh, false).length > 0
      mat.emissive.setHex(hit ? 0x16314e : 0x000000)
      setSelected(hit)
    }
    canvas.addEventListener('pointerdown', onLeftDown)
    canvas.addEventListener('pointerup', onLeftUp)

    // ---- Right-click context menu ----
    const onContextMenu = (e: MouseEvent) => {
      e.preventDefault()
      const r = canvas.getBoundingClientRect()
      setMenu({ x: e.clientX - r.left, y: e.clientY - r.top })
    }
    canvas.addEventListener('contextmenu', onContextMenu)

    // ---- View helpers ----
    const fit = () => {
      const box = new THREE.Box3().setFromObject(mesh)
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
      mat.wireframe = s === 'wireframe'
      edges.visible = s === 'shaded-edges'
    }
    apiRef.current = { fit, reset, setStyle }

    const onResize = () => {
      camera.aspect = w() / h()
      camera.updateProjectionMatrix()
      renderer.setSize(w(), h())
    }
    window.addEventListener('resize', onResize)

    let rafId = 0
    const animate = () => {
      rafId = requestAnimationFrame(animate)
      controls.update()
      renderer.render(scene, camera)
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
          <li className={style === 'shaded' ? 'on' : ''} onClick={() => pick('shaded')}>Shaded</li>
          <li className={style === 'shaded-edges' ? 'on' : ''} onClick={() => pick('shaded-edges')}>Shaded + edges</li>
          <li className={style === 'wireframe' ? 'on' : ''} onClick={() => pick('wireframe')}>Wireframe</li>
          <li className="sep" />
          <li className="disabled">Operations (with selection) — soon</li>
        </ul>
      )}
    </div>
  )
}
