import { type MutableRefObject, useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { ImportedMesh } from './import/normalize'
import type { HlrViewRequest } from './aiadra'
import type { HlrView } from './display/contract'
import {
  buildCanonicalPart,
  disposeCanonicalPart,
  pickDisplayId,
  pickTargets,
  type CanonicalPart,
} from './display/canonicalPart'
import { checkAttachHlr } from './display/attachHlr'
import { buildHlrOverlay, disposeOverlay } from './display/overlay'
import { createSettleMachine, type SettleMachine } from './display/settle'
import type { DisplaySource } from './display/displaySource'
import { DISPLAY_MODES, MODE_LABELS, modeFlags, type DisplayMode } from './display/modes'

/** Imperative viewport API the App drives. */
export type ViewportApi = {
  fit: () => void
  reset: () => void
  setMode: (m: DisplayMode) => void
  /** Show/hide the ground grid + axes helper. */
  setGridVisible: (v: boolean) => void
  /** Load (or clear) the canonical lane from a display source (arc 20260610-1). */
  setDisplaySource: (source: DisplaySource | null) => Promise<void>
  /** Snap the camera to a pregenerated standard view (fixture lane). */
  snapToView: (viewId: string) => void
  /** Add reference-only imported geometry as one group keyed by `id` (ADR/0032 D5). */
  addImported: (id: string, meshes: ImportedMesh[]) => void
  /** Remove an imported group and dispose all its GPU resources (Codex1 B1). */
  removeImported: (id: string) => void
}

/**
 * AIADRA Studio viewport (arc 20260610-1 — the canonical lane goes live).
 *
 * Navigation (Creo/SolidWorks convention): LEFT = select, RIGHT = menu,
 * MIDDLE = rotate, MIDDLE+SHIFT = pan, MIDDLE+CTRL = zoom, SCROLL = zoom.
 *
 * Camera is ORTHOGRAPHIC, Z-up, rendering engine model coordinates identically
 * (no transform) — the v1.1 HLR projector is orthographic-only, so this is the
 * only projection under which the exact settled overlay registers with the part
 * (Claude1 P3 / Codex1 Q1 concur). Two-phase rendering per ADR/0033 D6:
 * while the camera moves, modes work per-pixel on true model edges + the depth
 * buffer (`modes.ts`); on settle the exact classified HLR overlay swaps in
 * (`settle.ts` + `overlay.ts`, gated by `checkAttachHlr`). The screen-space
 * silhouette post-process and the placeholder box are gone (ADR/0033 D11 —
 * `baf52d2` remains the labeled git-history regression baseline).
 */

type Menu = { x: number; y: number } | null

const SETTLE_MS = 200
const BG_COLOR = 0xe6e9ec // bg+line theme coupling is the step-6 Appearance arc
const DIM_EDGE_COLOR = 0xb4bac2

export default function Viewport({ apiRef: externalApi }: { apiRef?: MutableRefObject<ViewportApi | null> } = {}) {
  const mountRef = useRef<HTMLDivElement>(null)
  const localApi = useRef<ViewportApi | null>(null)
  const apiRef = externalApi ?? localApi

  const [menu, setMenu] = useState<Menu>(null)
  const [mode, setModeState] = useState<DisplayMode>('shading-edges')
  const [picked, setPicked] = useState<{ kind: string; displayId: string } | null>(null)
  const [showGrid, setShowGrid] = useState(true)
  const [snapIds, setSnapIds] = useState<string[]>([])

  useEffect(() => {
    const mount = mountRef.current!
    const w = () => mount.clientWidth
    const h = () => mount.clientHeight

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(BG_COLOR)

    // ---- Orthographic, Z-up (engine space). Frustum half-height is the zoom
    // authority; OrbitControls dolly drives camera.zoom for ortho cameras. ----
    let frustumHalf = 20
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.01, 5000)
    camera.up.set(0, 0, 1)
    const applyFrustum = () => {
      const aspect = w() / h()
      camera.left = -frustumHalf * aspect
      camera.right = frustumHalf * aspect
      camera.top = frustumHalf
      camera.bottom = -frustumHalf
      camera.updateProjectionMatrix()
    }
    const HOME_DIR = new THREE.Vector3(-1, -1, -1).normalize() // iso look direction
    const HOME_TARGET = new THREE.Vector3(10, 5, 2.5)
    camera.position.copy(HOME_TARGET).addScaledVector(HOME_DIR, -120)
    applyFrustum()

    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(w(), h())
    mount.appendChild(renderer.domElement)
    const canvas = renderer.domElement

    // ---- Controls (CAD scheme) ----
    const controls = new OrbitControls(camera, canvas)
    controls.enableDamping = false
    controls.screenSpacePanning = true
    controls.zoomToCursor = true
    controls.target.copy(HOME_TARGET)
    controls.mouseButtons = { MIDDLE: THREE.MOUSE.ROTATE } as typeof controls.mouseButtons

    const onPointerDownCapture = (e: PointerEvent) => {
      if (e.button === 1) {
        e.preventDefault()
        controls.mouseButtons.MIDDLE = e.ctrlKey ? THREE.MOUSE.DOLLY : THREE.MOUSE.ROTATE
      }
      setMenu(null)
    }
    canvas.addEventListener('pointerdown', onPointerDownCapture, true)

    // ---- Lights ----
    scene.add(new THREE.AmbientLight(0xffffff, 0.55))
    const keyLight = new THREE.DirectionalLight(0xffffff, 0.95)
    keyLight.position.set(40, 30, 70)
    scene.add(keyLight)
    const fillLight = new THREE.DirectionalLight(0x88aaff, 0.35)
    fillLight.position.set(-50, -30, 20)
    scene.add(fillLight)

    // ---- Grid + axes (Z-up: grid rotated into the XY plane). LIGHT grid lines
    // on the light bg — model edges must visually dominate the grid (the old
    // dark grid colors were tuned for the retired dark background and rendered
    // grid lines at edge darkness). depthWrite off so the grid never occludes
    // edge passes. ----
    const grid = new THREE.GridHelper(200, 40, 0xb9c0c7, 0xcdd3d9)
    grid.rotation.x = Math.PI / 2
    ;(grid.material as THREE.Material).depthWrite = false
    scene.add(grid)
    const axes = new THREE.AxesHelper(12)
    ;(axes.material as THREE.Material).depthWrite = false
    scene.add(axes)

    // The 'paper' face style (unshaded modes): an opaque background-colored
    // body that occludes the grid — the Creo hidden-line body look. One shared
    // material; meshes swap between their shaded material and this.
    const paperMaterial = new THREE.MeshBasicMaterial({
      color: BG_COLOR,
      polygonOffset: true,
      polygonOffsetFactor: 1,
      polygonOffsetUnits: 1,
    })

    // ---- Canonical lane state ----
    let part: CanonicalPart | null = null
    let partGroup: THREE.Group | null = null
    let dimPass: THREE.LineSegments | null = null // B2: see-through all-edges pass
    let source: DisplaySource | null = null
    let display: Awaited<ReturnType<DisplaySource['getDisplay']>> | null = null
    let overlayGroup: THREE.Group | null = null
    let heldHlrView: HlrView | null = null
    let currentMode: DisplayMode = 'shading-edges'
    let currentSnapId: string | null = null
    let loadToken = 0 // guards a stale setDisplaySource resolution

    // ---- Imports (reference lane, ADR/0032 D5) ----
    const importGroups = new Map<string, THREE.Group>()
    const IMPORT_EDGE_ANGLE = 30

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

    // ---- Mode application (the modes.ts matrix made physical). A settled
    // overlay REPLACES the canonical base edge passes; reference imports keep
    // their live approximation always — they never get exact HLR (P8). ----

    // The mesh's shaded material is stashed in userData so paper mode can swap
    // it out and back without losing it (and without leaking it on dispose).
    const applyFaceStyle = (m: THREE.Mesh) => {
      const f = modeFlags(currentMode)
      const shaded = m.userData.shadedMaterial as THREE.MeshStandardMaterial
      if (f.faceStyle === 'paper') {
        m.material = paperMaterial
        return
      }
      m.material = shaded
      shaded.colorWrite = f.faceStyle === 'shaded'
      shaded.depthWrite = f.facesDepthWrite
    }

    const applyModeToMesh = (m: THREE.Mesh, bright: THREE.LineSegments | null, dim: THREE.LineSegments | null) => {
      const f = modeFlags(currentMode)
      applyFaceStyle(m)
      if (bright) {
        bright.visible = f.brightEdgesVisible
        const bm = bright.material as THREE.LineBasicMaterial
        bm.depthTest = f.brightEdgesDepthTest
      }
      if (dim) {
        dim.visible = f.dimEdgesVisible
        const dm = dim.material as THREE.LineBasicMaterial
        dm.depthTest = f.dimEdgesDepthTest // B2: false while visible
      }
    }

    const applyMode = () => {
      if (part && dimPass) {
        const f = modeFlags(currentMode)
        const hasOverlay = overlayGroup !== null
        for (const face of part.faces) applyFaceStyle(face)
        for (const edge of part.edges) {
          edge.visible = f.brightEdgesVisible && !hasOverlay
          ;(edge.material as THREE.LineBasicMaterial).depthTest = f.brightEdgesDepthTest
          edge.renderOrder = 2
        }
        dimPass.visible = f.dimEdgesVisible && !hasOverlay
        ;(dimPass.material as THREE.LineBasicMaterial).depthTest = f.dimEdgesDepthTest
      }
      for (const g of importGroups.values()) {
        g.traverse((o) => {
          const m = o as THREE.Mesh
          if (m.isMesh && m.userData.shadedMaterial) {
            const bright = m.getObjectByName('edges') as THREE.LineSegments | undefined
            const dim = m.getObjectByName('edgesDim') as THREE.LineSegments | undefined
            applyModeToMesh(m, bright ?? null, dim ?? null)
          }
        })
      }
    }

    // ---- Settled HLR overlay (P4/P5) ----
    const clearOverlay = () => {
      if (overlayGroup) {
        scene.remove(overlayGroup)
        disposeOverlay(overlayGroup)
        overlayGroup = null
      }
      heldHlrView = null
      applyMode()
    }

    const attachOverlay = (view: HlrView) => {
      if (overlayGroup) {
        scene.remove(overlayGroup)
        disposeOverlay(overlayGroup)
      }
      heldHlrView = view
      overlayGroup = buildHlrOverlay(view, currentMode)
      scene.add(overlayGroup)
      applyMode()
    }

    const rebuildOverlayForMode = () => {
      if (!heldHlrView) return
      const view = heldHlrView
      if (overlayGroup) {
        scene.remove(overlayGroup)
        disposeOverlay(overlayGroup)
        overlayGroup = null
      }
      overlayGroup = buildHlrOverlay(view, currentMode)
      heldHlrView = view
      scene.add(overlayGroup)
      applyMode()
    }

    const currentViewRequest = (): HlrViewRequest | null => {
      if (!source) return null
      if (source.snapViews) {
        // Fixture lane: HLR exists only at the pregenerated views.
        if (!currentSnapId) return null
        const snap = source.snapViews.find((v) => v.view_id === currentSnapId)
        return snap ? { view_id: snap.view_id, direction: snap.direction, up: snap.up } : null
      }
      const dir = controls.target.clone().sub(camera.position).normalize()
      let up: [number, number, number] = [camera.up.x, camera.up.y, camera.up.z]
      if (Math.abs(dir.x * up[0] + dir.y * up[1] + dir.z * up[2]) > 0.999) {
        up = [0, 1, 0] // up parallel to look direction — engine would reject
      }
      return { view_id: 'live', direction: [dir.x, dir.y, dir.z], up }
    }

    const machine: SettleMachine = createSettleMachine({
      settleMs: SETTLE_MS,
      schedule: (fn, ms) => {
        const t = window.setTimeout(fn, ms)
        return () => window.clearTimeout(t)
      },
      onClear: clearOverlay,
      onSettle: (seq) => {
        if (!source || !display || currentMode === 'shading') return
        const view = currentViewRequest()
        if (!view) return
        const t0 = performance.now()
        source
          .getHlr(view)
          .then((payload) => {
            if (machine.response(seq) !== 'accept') return
            if (!display) return
            const check = checkAttachHlr(display, payload)
            if (!check.ok) {
              // The held package is stale (recomputed topology / different cache
              // state) — drop, reload the display, and let settle re-fire.
              console.warn('[hlr] attach mismatch:', check.mismatches.join(', '), '— reloading display')
              void reloadDisplay()
              return
            }
            if (payload.views.length > 0) {
              attachOverlay(payload.views[0])
              console.debug(`[hlr] settled overlay attached in ${Math.round(performance.now() - t0)} ms`)
            }
          })
          .catch((e) => {
            machine.response(seq) // consume the sequence
            console.warn('[hlr] request failed:', e instanceof Error ? e.message : e)
          })
      },
    })
    controls.addEventListener('change', () => machine.cameraMoved())
    controls.addEventListener('start', () => {
      currentSnapId = null // user interaction leaves any snapped standard view
    })

    // ---- Canonical part load / clear ----
    const removePart = () => {
      clearOverlay()
      if (partGroup) {
        scene.remove(partGroup)
        if (part) {
          // Restore each face's own material before dispose (paper is shared).
          for (const face of part.faces) face.material = face.userData.shadedMaterial
          disposeCanonicalPart(part)
        }
        if (dimPass) {
          dimPass.geometry.dispose()
          ;(dimPass.material as THREE.Material).dispose()
        }
        part = null
        partGroup = null
        dimPass = null
        display = null
      }
    }

    const buildPart = () => {
      if (!display) return
      part = buildCanonicalPart(display)
      partGroup = part.group
      // Faces get polygon offset so depth-tested edge passes sit cleanly on
      // them; the shaded material is stashed for the paper-mode swap.
      for (const face of part.faces) {
        const mm = face.material as THREE.MeshStandardMaterial
        mm.polygonOffset = true
        mm.polygonOffsetFactor = 1
        mm.polygonOffsetUnits = 1
        face.userData.shadedMaterial = mm
      }
      // B2: one merged see-through dim pass over ALL true model edges.
      const merged: number[] = []
      for (const edge of part.edges) {
        const pos = edge.geometry.getAttribute('position')
        for (let i = 0; i < pos.count; i++) merged.push(pos.getX(i), pos.getY(i), pos.getZ(i))
      }
      const dimGeom = new THREE.BufferGeometry()
      dimGeom.setAttribute('position', new THREE.Float32BufferAttribute(merged, 3))
      dimPass = new THREE.LineSegments(
        dimGeom,
        new THREE.LineBasicMaterial({ color: DIM_EDGE_COLOR, depthWrite: false }),
      )
      dimPass.name = 'canonicalEdgesDim'
      dimPass.renderOrder = 1
      dimPass.userData = {} // render assist — no identity, never pickable
      partGroup.add(dimPass)
      scene.add(partGroup)
      applyMode()
    }

    const reloadDisplay = async () => {
      if (!source) return
      const token = ++loadToken
      const fresh = await source.getDisplay()
      if (token !== loadToken) return
      removePart()
      display = fresh
      buildPart()
      machine.cameraMoved() // schedule a fresh settle for the new package
    }

    const setDisplaySource = async (next: DisplaySource | null) => {
      const token = ++loadToken
      if (!next) {
        source = null
        removePart()
        setSnapIds([])
        return
      }
      const fresh = await next.getDisplay()
      if (token !== loadToken) return
      removePart()
      source = next
      display = fresh
      buildPart()
      setSnapIds(next.snapViews?.map((v) => v.view_id) ?? [])
      fit()
      if (next.snapViews && next.snapViews.length > 0) {
        snapToView(next.snapViews[0].view_id)
      } else {
        machine.cameraMoved()
      }
    }

    // ---- View helpers ----
    const sceneBox = () => {
      const box = new THREE.Box3()
      if (partGroup) box.expandByObject(partGroup)
      for (const g of importGroups.values()) box.expandByObject(g)
      return box
    }

    const fit = () => {
      const box = sceneBox()
      if (box.isEmpty()) return
      const sphere = box.getBoundingSphere(new THREE.Sphere())
      const dir = camera.position.clone().sub(controls.target).normalize()
      frustumHalf = sphere.radius * 1.15
      camera.zoom = 1
      const dist = sphere.radius * 4
      controls.target.copy(sphere.center)
      camera.position.copy(sphere.center).addScaledVector(dir, dist)
      camera.near = 0.01
      camera.far = dist + sphere.radius * 8
      applyFrustum()
      controls.update()
    }

    const reset = () => {
      controls.target.copy(HOME_TARGET)
      camera.position.copy(HOME_TARGET).addScaledVector(HOME_DIR, -120)
      camera.zoom = 1
      camera.updateProjectionMatrix()
      controls.update()
      fit()
    }

    const snapToView = (viewId: string) => {
      const snap = source?.snapViews?.find((v) => v.view_id === viewId)
      if (!snap) return
      const box = sceneBox()
      const center = box.isEmpty() ? HOME_TARGET.clone() : box.getBoundingSphere(new THREE.Sphere()).center
      const dir = new THREE.Vector3(...snap.direction).normalize()
      camera.up.set(...snap.up)
      controls.target.copy(center)
      camera.position.copy(center).addScaledVector(dir, -120)
      camera.zoom = 1
      camera.updateProjectionMatrix()
      controls.update() // fires 'change' → machine.cameraMoved()
      fit()
      currentSnapId = viewId // set AFTER updates: 'start' only fires on user input
    }

    const setMode = (m: DisplayMode) => {
      currentMode = m
      if (m === 'shading') {
        clearOverlay() // re-applies flags; onSettle skips shading anyway
        return
      }
      if (heldHlrView) {
        rebuildOverlayForMode() // restyle the held payload — no re-request
        return
      }
      applyMode()
      machine.cameraMoved() // give the new mode a settled overlay
    }

    const setGridVisible = (v: boolean) => {
      grid.visible = v
      axes.visible = v
    }

    // ---- Selection (left click): canonical faces/edges ONLY — the overlay and
    // the dim pass are never in the raycast target set (Codex1 N3). ----
    const raycaster = new THREE.Raycaster()
    raycaster.params.Line = { threshold: 0.3 }
    const ndc = new THREE.Vector2()
    let downX = 0
    let downY = 0
    let selectedFace: THREE.Mesh | null = null
    const onLeftDown = (e: PointerEvent) => {
      if (e.button === 0) {
        downX = e.clientX
        downY = e.clientY
      }
    }
    const onLeftUp = (e: PointerEvent) => {
      if (e.button !== 0) return
      if (Math.hypot(e.clientX - downX, e.clientY - downY) > 4) return
      if (!part) return
      const r = canvas.getBoundingClientRect()
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
      raycaster.setFromCamera(ndc, camera)
      // N3: the target set comes from pickTargets — overlay + dim pass excluded.
      const hit = pickDisplayId(raycaster, pickTargets(part))
      // Highlight lives on the SHADED material (paper is a shared material and
      // MeshBasicMaterial has no emissive) — visible in the shaded modes.
      if (selectedFace) {
        ;(selectedFace.userData.shadedMaterial as THREE.MeshStandardMaterial).emissive.setHex(0x000000)
        selectedFace = null
      }
      if (hit && hit.kind === 'face') {
        const mesh = part.faces.find((f) => f.userData.displayId === hit.displayId) ?? null
        if (mesh) {
          ;(mesh.userData.shadedMaterial as THREE.MeshStandardMaterial).emissive.setHex(0x16314e)
          selectedFace = mesh
        }
      }
      setPicked(hit)
    }
    canvas.addEventListener('pointerdown', onLeftDown)
    canvas.addEventListener('pointerup', onLeftUp)

    const onContextMenu = (e: MouseEvent) => {
      e.preventDefault()
      const r = canvas.getBoundingClientRect()
      setMenu({ x: e.clientX - r.left, y: e.clientY - r.top })
    }
    canvas.addEventListener('contextmenu', onContextMenu)

    // ---- Imports ----
    const disposeGroup = (group: THREE.Group) => {
      group.traverse((o) => {
        const obj = o as THREE.Mesh & THREE.LineSegments
        if (obj.isMesh || obj.isLineSegments) {
          // Never dispose the SHARED paper material — restore the own one first.
          if (obj.userData.shadedMaterial) obj.material = obj.userData.shadedMaterial as THREE.Material
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
        im.userData.shadedMaterial = im.material
        const e = makeEdges(g, IMPORT_EDGE_ANGLE, 0x33373d, DIM_EDGE_COLOR)
        im.add(e.b)
        im.add(e.d)
        applyModeToMesh(im, e.b, e.d)
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

    apiRef.current = {
      fit,
      reset,
      setMode,
      setGridVisible,
      setDisplaySource,
      snapToView,
      addImported,
      removeImported,
    }

    const onResize = () => {
      applyFrustum()
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
      machine.dispose()
      window.removeEventListener('resize', onResize)
      canvas.removeEventListener('pointerdown', onPointerDownCapture, true)
      canvas.removeEventListener('pointerdown', onLeftDown)
      canvas.removeEventListener('pointerup', onLeftUp)
      canvas.removeEventListener('contextmenu', onContextMenu)
      controls.dispose()
      removePart()
      for (const g of importGroups.values()) disposeGroup(g)
      importGroups.clear()
      paperMaterial.dispose()
      renderer.dispose()
      apiRef.current = null
      if (canvas.parentNode === mount) mount.removeChild(canvas)
    }
  }, [])

  const pickMode = (m: DisplayMode) => {
    setModeState(m)
    apiRef.current?.setMode(m)
    setMenu(null)
  }

  return (
    <div className="viewport-canvas">
      <div ref={mountRef} style={{ position: 'absolute', inset: 0 }} />
      {snapIds.length > 0 && (
        <div className="snap-views">
          {snapIds.map((id) => (
            <button key={id} className="btn small" type="button" onClick={() => apiRef.current?.snapToView(id)}>
              {id}
            </button>
          ))}
        </div>
      )}
      {picked && (
        <div className="sel-badge small">
          selected: {picked.kind} <code>{picked.displayId}</code>
        </div>
      )}
      {menu && (
        <ul
          className="ctx-menu"
          style={{ left: menu.x, top: menu.y }}
          onPointerDown={(e) => e.stopPropagation()}
        >
          <li onClick={() => { apiRef.current?.fit(); setMenu(null) }}>Fit to view</li>
          <li onClick={() => { apiRef.current?.reset(); setMenu(null) }}>Reset view</li>
          <li
            className={showGrid ? 'on' : ''}
            onClick={() => { const v = !showGrid; setShowGrid(v); apiRef.current?.setGridVisible(v); setMenu(null) }}
          >
            Grid
          </li>
          <li className="sep" />
          {DISPLAY_MODES.map((m) => (
            <li key={m} className={mode === m ? 'on' : ''} onClick={() => pickMode(m)}>
              {MODE_LABELS[m]}
            </li>
          ))}
          <li className="sep" />
          <li className="disabled">Operations (with selection) — soon</li>
        </ul>
      )}
    </div>
  )
}
