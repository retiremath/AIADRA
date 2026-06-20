import { type MutableRefObject, useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { ImportedMesh } from './import/normalize'
import type { HlrViewRequest } from './aiadra'
import type { HlrView } from './display/contract'
import {
  applyPartTheme,
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
import { modeFlags, type DisplayMode } from './display/modes'
import type { Theme } from './settings/theme'
import { toCommandContext, useViewState, type ViewStateStore } from './viewstate/store'
import { commandsInGroup } from './commands/registry'
import type { Command, CommandActions } from './commands/types'

/** Imperative viewport API the App drives. Mode + grid are NOT here anymore —
 * they flow through the shared view-state store (arc 20260619-2 / 6b). */
export type ViewportApi = {
  fit: () => void
  reset: () => void
  /** Live re-theming (arc 20260619-1 / 6a). */
  applyTheme: (theme: Theme) => void
  /** Load (or clear) the canonical lane from a display source (arc 20260610-1). */
  setDisplaySource: (source: DisplaySource | null) => Promise<void>
  /** Snap the camera to a pregenerated standard view (fixture lane). */
  snapToView: (viewId: string) => void
  /** Add reference-only imported geometry as one group keyed by `id` (ADR/0032 D5). */
  addImported: (id: string, meshes: ImportedMesh[]) => void
  /** Remove an imported group and dispose all its GPU resources. */
  removeImported: (id: string) => void
}

/**
 * AIADRA Studio viewport (arc 20260610-1 canonical lane live; 20260619-1 / 6a
 * theme-driven; 20260619-2 / 6b store-driven mode+grid).
 *
 * Live display state (mode, grid) lives in the shared `viewStore` (Codex1 N1):
 * the toolbar / context menu / keyboard write it; the viewport SUBSCRIBES and
 * applies it imperatively, and REPORTS scene facts (canonical part present?
 * reference imports present?) back so command enablement stays correct for the
 * imported-only lane (Codex1 B1). All display colors come from `theme` (6a B2).
 */

type Menu = { x: number; y: number } | null

export default function Viewport({
  apiRef: externalApi,
  theme,
  settleMs = 200,
  viewStore,
  commandActions,
}: {
  apiRef?: MutableRefObject<ViewportApi | null>
  theme: Theme
  settleMs?: number
  viewStore: ViewStateStore
  commandActions: CommandActions
}) {
  const mountRef = useRef<HTMLDivElement>(null)
  const localApi = useRef<ViewportApi | null>(null)
  const apiRef = externalApi ?? localApi

  const [menu, setMenu] = useState<Menu>(null)
  const [picked, setPicked] = useState<{ kind: string; displayId: string } | null>(null)
  const [snapIds, setSnapIds] = useState<string[]>([])
  const ctx = toCommandContext(useViewState(viewStore))

  useEffect(() => {
    const mount = mountRef.current!
    const w = () => mount.clientWidth
    const h = () => mount.clientHeight

    let liveTheme = theme

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(liveTheme.viewportBackground)

    // ---- Orthographic, Z-up (engine space). ----
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
    const HOME_DIR = new THREE.Vector3(-1, -1, -1).normalize()
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

    // ---- Grid + axes (Z-up); grid colors themed, rebuilt on theme change. ----
    let gridVisible = viewStore.getSnapshot().gridVisible
    let grid: THREE.GridHelper
    const makeGrid = (): THREE.GridHelper => {
      const g = new THREE.GridHelper(200, 40, liveTheme.gridMajor, liveTheme.gridMinor)
      g.rotation.x = Math.PI / 2
      ;(g.material as THREE.Material).depthWrite = false
      g.visible = gridVisible
      return g
    }
    grid = makeGrid()
    scene.add(grid)
    const axes = new THREE.AxesHelper(12)
    ;(axes.material as THREE.Material).depthWrite = false
    axes.visible = gridVisible
    scene.add(axes)

    const paperMaterial = new THREE.MeshBasicMaterial({
      color: liveTheme.paperBody,
      polygonOffset: true,
      polygonOffsetFactor: 1,
      polygonOffsetUnits: 1,
    })

    // ---- Canonical lane state ----
    let part: CanonicalPart | null = null
    let partGroup: THREE.Group | null = null
    let dimPass: THREE.LineSegments | null = null
    let source: DisplaySource | null = null
    let display: Awaited<ReturnType<DisplaySource['getDisplay']>> | null = null
    let overlayGroup: THREE.Group | null = null
    let heldHlrView: HlrView | null = null
    let currentMode: DisplayMode = viewStore.getSnapshot().mode
    let currentSnapId: string | null = null
    let loadToken = 0

    // ---- Imports (reference lane, ADR/0032 D5) ----
    const importGroups = new Map<string, THREE.Group>()
    const IMPORT_EDGE_ANGLE = 30

    const reportReferenceFacts = () =>
      viewStore.setSceneFacts({ hasReferenceGeometry: importGroups.size > 0 })

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

    // ---- Mode application (the modes.ts matrix made physical). ----
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
        ;(bright.material as THREE.LineBasicMaterial).depthTest = f.brightEdgesDepthTest
      }
      if (dim) {
        dim.visible = f.dimEdgesVisible
        ;(dim.material as THREE.LineBasicMaterial).depthTest = f.dimEdgesDepthTest
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
      overlayGroup = buildHlrOverlay(view, currentMode, liveTheme)
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
      overlayGroup = buildHlrOverlay(view, currentMode, liveTheme)
      heldHlrView = view
      scene.add(overlayGroup)
      applyMode()
    }

    const currentViewRequest = (): HlrViewRequest | null => {
      if (!source) return null
      if (source.snapViews) {
        if (!currentSnapId) return null
        const snap = source.snapViews.find((v) => v.view_id === currentSnapId)
        return snap ? { view_id: snap.view_id, direction: snap.direction, up: snap.up } : null
      }
      const dir = controls.target.clone().sub(camera.position).normalize()
      let up: [number, number, number] = [camera.up.x, camera.up.y, camera.up.z]
      if (Math.abs(dir.x * up[0] + dir.y * up[1] + dir.z * up[2]) > 0.999) {
        up = [0, 1, 0]
      }
      return { view_id: 'live', direction: [dir.x, dir.y, dir.z], up }
    }

    const machine: SettleMachine = createSettleMachine({
      settleMs,
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
            machine.response(seq)
            console.warn('[hlr] request failed:', e instanceof Error ? e.message : e)
          })
      },
    })
    controls.addEventListener('change', () => machine.cameraMoved())
    controls.addEventListener('start', () => {
      currentSnapId = null
    })

    // ---- Canonical part load / clear ----
    const removePart = () => {
      clearOverlay()
      if (partGroup) {
        scene.remove(partGroup)
        if (part) {
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
      viewStore.setSceneFacts({ hasCanonicalPart: false })
    }

    const buildPart = () => {
      if (!display) return
      part = buildCanonicalPart(display, liveTheme)
      partGroup = part.group
      for (const face of part.faces) {
        const mm = face.material as THREE.MeshStandardMaterial
        mm.polygonOffset = true
        mm.polygonOffsetFactor = 1
        mm.polygonOffsetUnits = 1
        face.userData.shadedMaterial = mm
      }
      const merged: number[] = []
      for (const edge of part.edges) {
        const pos = edge.geometry.getAttribute('position')
        for (let i = 0; i < pos.count; i++) merged.push(pos.getX(i), pos.getY(i), pos.getZ(i))
      }
      const dimGeom = new THREE.BufferGeometry()
      dimGeom.setAttribute('position', new THREE.Float32BufferAttribute(merged, 3))
      dimPass = new THREE.LineSegments(
        dimGeom,
        new THREE.LineBasicMaterial({ color: liveTheme.hiddenEdgeDim, depthWrite: false }),
      )
      dimPass.name = 'canonicalEdgesDim'
      dimPass.renderOrder = 1
      dimPass.userData = {}
      partGroup.add(dimPass)
      scene.add(partGroup)
      applyMode()
      viewStore.setSceneFacts({ hasCanonicalPart: true })
    }

    const reloadDisplay = async () => {
      if (!source) return
      const token = ++loadToken
      const fresh = await source.getDisplay()
      if (token !== loadToken) return
      removePart()
      display = fresh
      buildPart()
      machine.cameraMoved()
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
      controls.update()
      fit()
      currentSnapId = viewId
    }

    // ---- Store-driven mode + grid (Codex1 N1). The viewport APPLIES; the
    // toolbar/menu/keyboard WRITE the store. ----
    const applyModeChange = (m: DisplayMode) => {
      currentMode = m
      if (m === 'shading') {
        clearOverlay()
        return
      }
      if (heldHlrView) {
        rebuildOverlayForMode()
        return
      }
      applyMode()
      machine.cameraMoved()
    }

    const applyGridVisible = (v: boolean) => {
      gridVisible = v
      grid.visible = v
      axes.visible = v
    }

    const unsubStore = viewStore.subscribe(() => {
      const s = viewStore.getSnapshot()
      if (s.mode !== currentMode) applyModeChange(s.mode)
      if (s.gridVisible !== gridVisible) applyGridVisible(s.gridVisible)
    })

    // ---- Selection (left click): canonical faces/edges ONLY. ----
    const raycaster = new THREE.Raycaster()
    raycaster.params.Line = { threshold: 0.3 }
    const ndc = new THREE.Vector2()
    let downX = 0
    let downY = 0
    let selectedFace: THREE.Mesh | null = null
    const setEmissive = (m: THREE.Mesh, hex: number) => {
      ;(m.userData.shadedMaterial as THREE.MeshStandardMaterial).emissive.setHex(hex)
    }
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
      const hit = pickDisplayId(raycaster, pickTargets(part))
      if (selectedFace) {
        setEmissive(selectedFace, 0x000000)
        selectedFace = null
      }
      if (hit && hit.kind === 'face') {
        const mesh = part.faces.find((f) => f.userData.displayId === hit.displayId) ?? null
        if (mesh) {
          setEmissive(mesh, liveTheme.selectionHighlight)
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
            color: liveTheme.importedFace,
            metalness: 0.1,
            roughness: 0.8,
            polygonOffset: true,
            polygonOffsetFactor: 1,
            polygonOffsetUnits: 1,
          }),
        )
        im.userData.shadedMaterial = im.material
        const e = makeEdges(g, IMPORT_EDGE_ANGLE, liveTheme.importedEdgeBright, liveTheme.importedEdgeDim)
        im.add(e.b)
        im.add(e.d)
        applyModeToMesh(im, e.b, e.d)
        group.add(im)
      }
      scene.add(group)
      importGroups.set(id, group)
      reportReferenceFacts()
      fit()
    }

    const removeImported = (id: string) => {
      const group = importGroups.get(id)
      if (!group) return
      scene.remove(group)
      disposeGroup(group)
      importGroups.delete(id)
      reportReferenceFacts()
    }

    // ---- Live re-theming (arc 20260619-1 / 6a; Codex1 B2). ----
    const restyleImport = (group: THREE.Group) => {
      group.traverse((o) => {
        const m = o as THREE.Mesh
        if (m.isMesh && m.userData.shadedMaterial) {
          ;(m.userData.shadedMaterial as THREE.MeshStandardMaterial).color.setHex(liveTheme.importedFace)
          const bright = m.getObjectByName('edges') as THREE.LineSegments | undefined
          const dim = m.getObjectByName('edgesDim') as THREE.LineSegments | undefined
          if (bright) (bright.material as THREE.LineBasicMaterial).color.setHex(liveTheme.importedEdgeBright)
          if (dim) (dim.material as THREE.LineBasicMaterial).color.setHex(liveTheme.importedEdgeDim)
        }
      })
    }

    const applyTheme = (next: Theme) => {
      liveTheme = next
      ;(scene.background as THREE.Color).setHex(next.viewportBackground)
      paperMaterial.color.setHex(next.paperBody)
      scene.remove(grid)
      ;(grid.material as THREE.Material).dispose()
      grid.geometry.dispose()
      grid = makeGrid()
      scene.add(grid)
      if (part) applyPartTheme(part, next)
      if (dimPass) (dimPass.material as THREE.LineBasicMaterial).color.setHex(next.hiddenEdgeDim)
      if (heldHlrView) rebuildOverlayForMode()
      for (const g of importGroups.values()) restyleImport(g)
      if (selectedFace) setEmissive(selectedFace, next.selectionHighlight)
      applyMode()
    }

    apiRef.current = {
      fit,
      reset,
      applyTheme,
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
      unsubStore()
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
      ;(grid.material as THREE.Material).dispose()
      grid.geometry.dispose()
      paperMaterial.dispose()
      renderer.dispose()
      apiRef.current = null
      if (canvas.parentNode === mount) mount.removeChild(canvas)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Live theme application (6a) — re-applies whenever the theme prop changes.
  useEffect(() => {
    apiRef.current?.applyTheme(theme)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme])

  // Context menu — rendered from the SAME command taxonomy as the toolbar
  // (Codex1 N2). One source of truth; no second display-state implementation.
  const runFromMenu = (c: Command) => {
    if (c.isEnabled(ctx)) c.run(commandActions, ctx)
    setMenu(null)
  }
  const menuItem = (c: Command) => (
    <li
      key={c.id}
      className={`${c.isActive?.(ctx) ? 'on' : ''} ${c.isEnabled(ctx) ? '' : 'disabled'}`}
      onClick={() => runFromMenu(c)}
    >
      {c.label}
    </li>
  )

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
          {commandsInGroup('view').map(menuItem)}
          <li className="sep" />
          {commandsInGroup('display').map(menuItem)}
          <li className="sep" />
          {commandsInGroup('scene').map(menuItem)}
          <li className="sep" />
          {commandsInGroup('operations').map(menuItem)}
        </ul>
      )}
    </div>
  )
}
