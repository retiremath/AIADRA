import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

/**
 * AIADRA Studio viewport — bootstrap spike (arc 20260602-5).
 * Minimal professional-feeling three.js scene to prove the stack:
 * lit + shaded mesh with edges, grid floor, OrbitControls (orbit/pan/zoom),
 * device-pixel-ratio aware, resize-safe. The sample shape is the 20x10x5 mm
 * "bracket" the mechanical engine authored — STEP/STL import lands next.
 */
export default function Viewport() {
  const mountRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const mount = mountRef.current!
    const w = () => mount.clientWidth
    const h = () => mount.clientHeight

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x1e1f22)

    const camera = new THREE.PerspectiveCamera(50, w() / h(), 0.1, 5000)
    camera.position.set(48, 36, 48)

    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(w(), h())
    mount.appendChild(renderer.domElement)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.target.set(0, 2.5, 0)

    // Lighting
    scene.add(new THREE.AmbientLight(0xffffff, 0.55))
    const key = new THREE.DirectionalLight(0xffffff, 0.95)
    key.position.set(40, 70, 30)
    scene.add(key)
    const fill = new THREE.DirectionalLight(0x88aaff, 0.35)
    fill.position.set(-50, 20, -30)
    scene.add(fill)

    // Grid floor
    const grid = new THREE.GridHelper(200, 40, 0x3a3d44, 0x2a2c31)
    scene.add(grid)
    scene.add(new THREE.AxesHelper(12))

    // The authored bracket: 20 (x) x 5 (z-height) x 10 (y-depth) mm
    const geo = new THREE.BoxGeometry(20, 5, 10)
    const mat = new THREE.MeshStandardMaterial({ color: 0x6b9bd1, metalness: 0.15, roughness: 0.55 })
    const mesh = new THREE.Mesh(geo, mat)
    mesh.position.y = 2.5
    scene.add(mesh)
    const edges = new THREE.LineSegments(
      new THREE.EdgesGeometry(geo),
      new THREE.LineBasicMaterial({ color: 0x16314e })
    )
    mesh.add(edges)

    const onResize = () => {
      camera.aspect = w() / h()
      camera.updateProjectionMatrix()
      renderer.setSize(w(), h())
    }
    window.addEventListener('resize', onResize)

    let raf = 0
    const animate = () => {
      raf = requestAnimationFrame(animate)
      controls.update()
      renderer.render(scene, camera)
    }
    animate()

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onResize)
      controls.dispose()
      renderer.dispose()
      geo.dispose()
      mat.dispose()
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement)
    }
  }, [])

  return <div ref={mountRef} className="viewport-canvas" />
}
