import { type MutableRefObject, useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { ImportedMesh } from './import/normalize'
import type { HlrViewRequest } from './aiadra'
import type { HlrView } from './display/contract'
import {
  applyPartTheme,
  buildCanonicalPart,
  canonicalEdgeColor,
  disposeCanonicalPart,
  faceBoundaryEdges,
  pickDisplayId,
  pickTargetsFiltered,
  type CanonicalPart,
} from './display/canonicalPart'
import { checkAttachHlr } from './display/attachHlr'
import { buildHlrOverlay, disposeOverlay } from './display/overlay'
import { createSettleMachine, type SettleMachine } from './display/settle'
import { createDatumOverlay } from './datums/datumOverlay'
import { createSketchEditOverlay } from './sketch/sketchEditOverlay'
import {
  arbitratePlanePick,
  frameFromNormalAndPoint,
  projectedExtent,
  rayPlaneUV,
  sketchViewOrientation,
  type PlaneFrameTS,
} from './sketch/planeFrame'
import type { SketchTool } from './authoring/authoringSession'
import { createSketchWireOverlay } from './sketch/sketchWireOverlay'
import type { InspectedSketch } from './authoring/inspectDecode'
import type { DisplaySource } from './display/displaySource'
import { modeFlags, type DisplayMode } from './display/modes'
import {
  standardViewOrientation,
  rollUp,
  type StandardViewId,
  type ViewOrientation,
} from './display/viewOrientation'
import { createNavCube } from './navcube/navCube'
import {
  navCubeViewportRect,
  pointerInNavCube,
  pointerToNavCubeNdc,
  type NavCubeLayout,
} from './navcube/navCubeRect'
import type { Theme } from './settings/theme'
import { toCommandContext, useViewState, type ViewStateStore } from './viewstate/store'
import {
  useSelectionState,
  type SelectableKind,
  type SelectionStore,
} from './selection/store'
import { commandsInGroup } from './commands/registry'
import type { Command, CommandActions } from './commands/types'

/** Imperative viewport API the App drives. The display mode is NOT here —
 * they flow through the shared view-state store (arc 20260619-2 / 6b). */
export type ViewportApi = {
  fit: () => void
  reset: () => void
  /** Live re-theming (arc 20260619-1 / 6a). */
  applyTheme: (theme: Theme) => void
  /** Load (or clear) the canonical lane from a display source (arc 20260610-1).
   *  R4: resolves with the LOADED payload (null when cleared/superseded) so the
   *  Part transition can derive generation-bound selector facts without a
   *  second display fetch. */
  setDisplaySource: (source: DisplaySource | null) => Promise<import('./display/contract').DisplayRepresentation | null>
  /** Snap the camera to a pregenerated standard view (fixture lane). */
  snapToView: (viewId: string) => void
  /** Orient the main camera to a client-computed standard view (arc 20260625-1 / 6c). */
  standardView: (id: StandardViewId) => void
  /** Roll the camera ±90° about its look axis (the nav-cube roll arrows). */
  rollView: (sign: 1 | -1) => void
  /** Step the camera 90° — yaw (turntable) or pitch (the nav-cube side arrows). */
  orbitView: (kind: 'yaw' | 'pitch', sign: 1 | -1) => void
  /** Add reference-only imported geometry as one group keyed by `id` (ADR/0032 D5). */
  addImported: (id: string, meshes: ImportedMesh[]) => void
  /** Remove an imported group and dispose all its GPU resources. */
  removeImported: (id: string) => void
  /** Replace the UNCONSUMED-sketch wire overlay (S2 D-S2 — derived from the
   *  inspected recipe; overlay lane, never canonical identity). */
  setSketchWires: (
    sketches: InspectedSketch[],
    frames?: ReadonlyMap<string, import('./display/contract').SketchFrame>,
  ) => void
  /** SK-C1.0 S1: the `Sketch view` camera action — reorient normal to the
   *  given frame (look = −normal, up = v; Codex2 B5.4). Camera-only. */
  sketchView: (frame: PlaneFrameTS) => void
}

/** The in-context interaction mode (SK-C1.0 S1) — derived by the Workbench
 *  from the ONE authoring session; the viewport renders/serves it and owns
 *  every imperative three.js consequence (Codex3 bar 2). */
export type SketchInteractionMode =
  | { kind: 'planePick' }
  | { kind: 'sketch'; frame: PlaneFrameTS; tool: SketchTool; construction: boolean }

/** S3: the resolved pick — a datum enum, or an ENGINE-PLANAR face enriched
 *  with the TRANSIENT mirror frame (drawing-only; the engine re-derives). */
export type ResolvedPlanePick =
  | { kind: 'datum'; orientation: 'xy' | 'yz' | 'zx' }
  | { kind: 'face'; faceId: string; frame: PlaneFrameTS }

/**
 * AIADRA Studio viewport (arc 20260610-1 canonical lane live; 20260619-1 / 6a
 * theme-driven; 20260619-2 / 6b store-driven mode).
 *
 * Live display state (the mode) lives in the shared `viewStore` (Codex1 N1):
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
  selectionStore,
  commandActions,
  interactionMode = null,
  planarFaceIds,
  onPlanePick,
  onSketchPlace,
  onSketchCursor,
  onContextHover,
}: {
  apiRef?: MutableRefObject<ViewportApi | null>
  theme: Theme
  settleMs?: number
  viewStore: ViewStateStore
  selectionStore: SelectionStore
  commandActions: CommandActions
  /** SK-C1.0 S1: null = ordinary display shell; the Workbench derives it. */
  interactionMode?: SketchInteractionMode | null
  /** S3: the ENGINE-classified planar faces of the current generation — the
   *  ONLY face-pick eligibility authority (Studio never classifies). */
  planarFaceIds?: ReadonlySet<string>
  onPlanePick?: (hit: ResolvedPlanePick) => void
  onSketchPlace?: (uv: { u: number; v: number }) => void
  onSketchCursor?: (uv: { u: number; v: number } | null) => void
  /** SK-C1.0 Codex4 B1.3: sketch-mode canonical-topology hover — the actual
   *  engine-owned/display-package id, surfaced (hover-only; the SK-E seam). */
  onContextHover?: (hit: { kind: 'face' | 'edge'; id: string } | null) => void
}) {
  const mountRef = useRef<HTMLDivElement>(null)
  const localApi = useRef<ViewportApi | null>(null)
  const apiRef = externalApi ?? localApi

  const [menu, setMenu] = useState<Menu>(null)
  // Callback + mode refs: the mount effect runs ONCE; handlers read these live.
  const sketchCbRef = useRef({ onPlanePick, onSketchPlace, onSketchCursor, onContextHover })
  sketchCbRef.current = { onPlanePick, onSketchPlace, onSketchCursor, onContextHover }
  const planarFaceIdsRef = useRef<ReadonlySet<string>>(new Set())
  planarFaceIdsRef.current = planarFaceIds ?? new Set()
  const interactionModeRef = useRef(interactionMode)
  interactionModeRef.current = interactionMode
  const applyInteractionRef = useRef<((m: SketchInteractionMode | null) => void) | null>(null)
  const [snapIds, setSnapIds] = useState<string[]>([])
  const selState = useSelectionState(selectionStore)
  const ctx = toCommandContext(useViewState(viewStore), {
    filter: selState.filter,
    hasSelection: selState.selected !== null,
  })

  useEffect(() => {
    applyInteractionRef.current?.(interactionMode)
  }, [interactionMode])

  useEffect(() => {
    const mount = mountRef.current!
    const w = () => mount.clientWidth
    const h = () => mount.clientHeight

    let liveTheme = theme

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(liveTheme.viewportBackground)

    // ---- Orthographic, Z-up (engine space). ----
    // Petre round 2: the canvas comes up FRAMING the datum scaffold (+/-60 mm
    // planes) — all three principal planes visible, never zoomed into nothing.
    const DATUM_FRAME_HALF = 80
    let frustumHalf = DATUM_FRAME_HALF
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
    // Codex2 B4: home = the ISO row of the ONE orientation authority
    // (viewOrientation.ts) — direction AND canonical up, shared with the nav
    // cube and the standard views. Reset restores BOTH.
    const HOME_VIEW = standardViewOrientation('iso')
    const HOME_DIR = new THREE.Vector3(HOME_VIEW.direction[0], HOME_VIEW.direction[1], HOME_VIEW.direction[2])
    const HOME_TARGET = new THREE.Vector3(0, 0, 0) // the datum intersection
    camera.up.set(HOME_VIEW.up[0], HOME_VIEW.up[1], HOME_VIEW.up[2])
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

    // ---- Nav cube (arc 20260625-1 / 6c; Codex1 B1) ----
    // A scissor-corner overlay on THIS renderer. Its camera mirrors the main
    // camera each frame; a click on a region orients the MAIN camera. The cube
    // lane CONSUMES pointer gestures inside its rect so OrbitControls / selection
    // / context menu never see them, and it never feeds the settle machine — only
    // a programmatic main-camera change (orientMainCamera) does.
    // The cube uses its OWN fixed, high-contrast palette (a neutral mid-gray body
    // + dark edges) so it reads on any background; only the hover tracks the theme.
    const NAV_CUBE_FACE = 0xaab2bb
    const NAV_CUBE_EDGE = 0x2c3137
    const navCube = createNavCube()
    navCube.applyTheme(NAV_CUBE_FACE, NAV_CUBE_EDGE, theme.hoverHighlight)
    // The cube sits in the centre of a 180px control cluster (the rotate arrows
    // ring it in the JSX); 116px + a 42px corner margin places it there.
    const navLayout: NavCubeLayout = { sizeCss: 116, marginCss: 42, corner: 'top-right' }
    // The corner axis gnomon is REMOVED (Petre round 2): the coordinate
    // system renders AT the origin — the datum overlay's labeled triad at the
    // intersection of the principal planes — not as a floating corner widget.
    const canvasRel = (e: { clientX: number; clientY: number }): [number, number] => {
      const r = canvas.getBoundingClientRect()
      return [e.clientX - r.left, e.clientY - r.top]
    }
    const inNavCube = (e: { clientX: number; clientY: number }): boolean => {
      const [px, py] = canvasRel(e)
      return pointerInNavCube(navLayout, w(), h(), px, py)
    }

    const onPointerDownCapture = (e: PointerEvent) => {
      // The cube rect is an INPUT-OWNED ISLAND (Codex2 B1): it consumes EVERY
      // pointer button so OrbitControls (middle = rotate/zoom) never engages and
      // the context menu never opens over it. Left orients; other buttons are
      // swallowed. Done in capture so the gesture never reaches OrbitControls'
      // bubble listener, the canonical picker, or the menu.
      if (inNavCube(e)) {
        if (e.button === 0) {
          const [px, py] = canvasRel(e)
          const [nx, ny] = pointerToNavCubeNdc(navLayout, w(), h(), px, py)
          const region = navCube.pickRegion(nx, ny)
          if (region) orientMainCamera(region.orientation)
        }
        e.stopImmediatePropagation()
        e.preventDefault()
        setMenu(null)
        return
      }
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

    // (The XY grid AND the standalone axes helper are both gone — arc
    // 20260716-1: the datum overlay's labeled triad IS the coordinate system,
    // at 0,0,0. A future sketch mode mints its own mode-scoped grid.)

    // ---- The datum overlay (arc 20260714-2 EP1): the origin triad + the three
    // labeled translucent principal planes — the Creo-paradigm empty-part
    // scaffold. An OVERLAY lane: intrinsic ids only, never canonical identity,
    // never a pick target (it lives outside the canonical part group).
    const datums = createDatumOverlay()
    datums.setVisible(viewStore.getSnapshot().datumsVisible)
    scene.add(datums.group)

    // ---- The sketch-wire overlay (S2 D-S2): unconsumed committed sketches as
    // closed wires on their planes. Same overlay-lane rules as the datums —
    // derived ids only, outside the canonical group, excluded from fit.
    const sketchWires = createSketchWireOverlay()
    scene.add(sketchWires.group)

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
      // Codex1 B2/Q4: selected ids are canonical for ONE package — every load /
      // reload / recompute path runs through here, so clear unconditionally.
      hovId = null
      selectionStore.clearSelected() // → reconcileSelection (selId=null), no-op repaint (part gone)
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
        return null
      }
      const fresh = await next.getDisplay()
      if (token !== loadToken) return null // superseded (defense in depth)
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
      return fresh
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
      if (box.isEmpty()) {
        // empty part: fit = frame the datum scaffold (all three planes)
        frustumHalf = DATUM_FRAME_HALF
        camera.zoom = 1
        controls.target.copy(HOME_TARGET)
        applyFrustum()
        controls.update()
        return
      }
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

    // Codex2 B4: Reset restores the CANONICAL home orientation — direction
    // AND up, through the same authority path as the standard views — never
    // the prior view's up (Top/Bottom/roll left a stale up before).
    const reset = () => {
      controls.target.copy(HOME_TARGET)
      camera.zoom = 1
      orientMainCamera(HOME_VIEW)
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

    // Client-side orientation (arc 20260625-1 / 6c): nav cube + standard views.
    // A programmatic MAIN-camera move → `fit()` → controls 'change' → the settle
    // machine recomputes HLR exactly like any real camera move (B1).
    const orientMainCamera = (o: ViewOrientation) => {
      const box = sceneBox()
      const center = box.isEmpty()
        ? controls.target.clone()
        : box.getBoundingSphere(new THREE.Sphere()).center
      const dir = new THREE.Vector3(o.direction[0], o.direction[1], o.direction[2]).normalize()
      camera.up.set(o.up[0], o.up[1], o.up[2])
      controls.target.copy(center)
      camera.position.copy(center).addScaledVector(dir, -120)
      currentSnapId = null // not a fixture snap; the live/bridge HLR lane recomputes
      fit()
    }

    const standardView = (id: StandardViewId) => orientMainCamera(standardViewOrientation(id))

    const rollView = (sign: 1 | -1) => {
      const dir = controls.target.clone().sub(camera.position).normalize()
      const up = camera.up.clone().normalize()
      const next = rollUp([dir.x, dir.y, dir.z], [up.x, up.y, up.z], sign)
      camera.up.set(next[0], next[1], next[2])
      controls.update() // 'change' → settle, like any camera move
    }

    // The nav-cube side arrows: step the camera 90° about the world vertical
    // (yaw — left/right turntable) or the screen-horizontal axis (pitch — up/down).
    const orbitView = (kind: 'yaw' | 'pitch', sign: 1 | -1) => {
      const target = controls.target.clone()
      const offset = camera.position.clone().sub(target)
      const dir = offset.clone().negate().normalize() // eye → target
      const up = camera.up.clone().normalize()
      const axis =
        kind === 'yaw'
          ? new THREE.Vector3(0, 0, 1) // world up — a turntable spin
          : new THREE.Vector3().crossVectors(dir, up).normalize() // screen-right
      const q = new THREE.Quaternion().setFromAxisAngle(axis, (sign * Math.PI) / 2)
      offset.applyQuaternion(q)
      camera.up.applyQuaternion(q)
      camera.position.copy(target).add(offset)
      currentSnapId = null
      fit()
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

    let datumsVisible = viewStore.getSnapshot().datumsVisible
    const unsubStore = viewStore.subscribe(() => {
      const s = viewStore.getSnapshot()
      if (s.mode !== currentMode) applyModeChange(s.mode)
      if (s.datumsVisible !== datumsVisible) {
        datumsVisible = s.datumsVisible
        datums.setVisible(datumsVisible)
      }
    })

    // ---- Selection + hover (arc 20260625-1 / 6c; Codex1 B2). Canonical faces /
    // edges ONLY — the ephemeral-identity firewall: `pickTargetsFiltered` returns
    // only the part's faces/edges, never the HLR overlay, dim pass, or imports.
    // Hover is imperative + rAF-coalesced (Codex1 Q5); committed selection is the
    // selectionStore's (the viewport renders it). A selected FACE also lights its
    // boundary edges (via contract adjacency) so it stays visible in wireframe. ----
    type SelId = { kind: SelectableKind; id: string } | null
    const raycaster = new THREE.Raycaster()
    raycaster.params.Line = { threshold: 0.3 }
    const ndc = new THREE.Vector2()
    let downX = 0
    let downY = 0
    let selId: SelId = null
    let hovId: SelId = null
    const sameId = (a: SelId, b: SelId) =>
      (a === null) === (b === null) && (!a || !b || (a.kind === b.kind && a.id === b.id))

    const repaintHighlights = () => {
      if (!part) return
      const selFace = selId?.kind === 'face' ? selId.id : null
      const hovFace = hovId?.kind === 'face' ? hovId.id : null
      for (const f of part.faces) {
        const id = f.userData.displayId as string
        const hex =
          selFace === id ? liveTheme.selectionHighlight : hovFace === id ? liveTheme.hoverHighlight : 0x000000
        ;(f.userData.shadedMaterial as THREE.MeshStandardMaterial).emissive.setHex(hex)
      }
      const selBoundary = selFace ? new Set(faceBoundaryEdges(part, selFace)) : null
      const hovBoundary = hovFace ? new Set(faceBoundaryEdges(part, hovFace)) : null
      for (const e of part.edges) {
        const id = e.userData.displayId as string
        const kind = (e.userData.edgeKind as string) ?? 'sharp'
        const hex =
          (selId?.kind === 'edge' && selId.id === id) || selBoundary?.has(e)
            ? liveTheme.selectionHighlight
            : (hovId?.kind === 'edge' && hovId.id === id) || hovBoundary?.has(e)
              ? liveTheme.hoverHighlight
              : canonicalEdgeColor(liveTheme, kind)
        ;(e.material as THREE.LineBasicMaterial).color.setHex(hex)
      }
    }

    // selectionStore is the source of truth for committed selection; render it.
    const reconcileSelection = () => {
      const s = selectionStore.getSnapshot().selected
      selId = s ? { kind: s.kind, id: s.id } : null
      repaintHighlights()
    }
    const unsubSelection = selectionStore.subscribe(reconcileSelection)

    // ---- SK-C1.0 S1: plane-pick + in-context sketch mode ------------------
    // The session store owns the pure state (Codex3 bar 2); THIS block owns
    // every imperative consequence: the edit overlay, datum-quad hover, the
    // mode-scoped datum exposure, part ghosting, and the entry camera.
    const sketchEdit = createSketchEditOverlay()
    sketchEdit.group.visible = false
    scene.add(sketchEdit.group)
    let modeKind: 'none' | 'planePick' | 'sketch' = 'none'
    let sketchFrame: PlaneFrameTS | null = null
    let hoveredQuad: THREE.Mesh | null = null
    let datumsPriorVisible: boolean | null = null
    let ghosted = false

    const setQuadHover = (quad: THREE.Mesh | null) => {
      if (hoveredQuad === quad) return
      if (hoveredQuad) (hoveredQuad.material as THREE.MeshBasicMaterial).opacity = 0.08
      hoveredQuad = quad
      if (hoveredQuad) (hoveredQuad.material as THREE.MeshBasicMaterial).opacity = 0.22
    }
    const datumQuadAt = (clientX: number, clientY: number): THREE.Mesh | null => {
      const r = canvas.getBoundingClientRect()
      ndc.set(((clientX - r.left) / r.width) * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1)
      raycaster.setFromCamera(ndc, camera)
      const hits = raycaster.intersectObjects(datums.group.children, false)
      const hit = hits.find((h) => (h.object.userData as { kind?: string }).kind === 'intrinsic-plane')
      return (hit?.object as THREE.Mesh) ?? null
    }
    // S3: the ELIGIBLE planar-face hit in pick mode — canonical faces only,
    // filtered by the engine's planarFaceIds; the hit carries the TRANSIENT
    // mirror frame derived from the engine-provided normal attribute + point.
    const planarFaceAt = (
      clientX: number,
      clientY: number,
    ): { faceId: string; frame: PlaneFrameTS } | null => {
      if (!part) return null
      const r = canvas.getBoundingClientRect()
      ndc.set(((clientX - r.left) / r.width) * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1)
      raycaster.setFromCamera(ndc, camera)
      const hits = raycaster.intersectObjects(part.faces, false)
      const hit = hits.find((h) =>
        planarFaceIdsRef.current.has((h.object.userData as { displayId?: string }).displayId ?? ''))
      if (!hit || !hit.face) return null
      const faceId = (hit.object.userData as { displayId: string }).displayId
      // the ENGINE's true normal attribute at the hit triangle (outward)
      const geom = (hit.object as THREE.Mesh).geometry as THREE.BufferGeometry
      const na = geom.getAttribute('normal') as THREE.BufferAttribute
      const i = hit.face.a
      const frame = frameFromNormalAndPoint(
        [na.getX(i), na.getY(i), na.getZ(i)],
        [hit.point.x, hit.point.y, hit.point.z],
      )
      if (!frame) return null
      return { faceId, frame }
    }

    const sketchUvAt = (clientX: number, clientY: number): { u: number; v: number } | null => {
      if (!sketchFrame) return null
      const r = canvas.getBoundingClientRect()
      ndc.set(((clientX - r.left) / r.width) * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1)
      raycaster.setFromCamera(ndc, camera)
      const o = raycaster.ray.origin
      const d = raycaster.ray.direction
      return rayPlaneUV(sketchFrame, [o.x, o.y, o.z], [d.x, d.y, d.z])
    }
    // Ghosting is a reversible PROJECTION of the display authorities (Codex3
    // bar 4): entry dims the shaded materials; exit re-applies the current
    // mode + selection styling rather than restoring cached guesses.
    const ghostPart = (on: boolean) => {
      if (ghosted === on) return
      ghosted = on
      if (!part) return
      for (const f of part.faces) {
        const m = f.userData.shadedMaterial as THREE.MeshStandardMaterial
        m.transparent = on
        m.opacity = on ? 0.3 : 1
        m.needsUpdate = true
      }
      if (!on) {
        applyModeChange(currentMode)
        repaintHighlights()
      }
    }
    // Codex4 B1.1: the ENTRY EXTENT — the canonical Part's bounds projected
    // onto the sketch plane, expanded by a margin, floored at the minimum
    // sheet. Renderer-side, generation-bound presentation state — not Truth.
    const SHEET_MIN_HALF: readonly [number, number] = [130, 85]
    // Codex5 B1.1: bounds from the CANONICAL Part ONLY — reference imports
    // stay visible context but never define the support sheet or entry fit.
    const sketchEntryExtent = (
      f: PlaneFrameTS,
    ): { halfU: number; halfV: number; centerU: number; centerV: number } => {
      const box = new THREE.Box3()
      if (partGroup) box.expandByObject(partGroup)
      if (box.isEmpty()) {
        return { halfU: SHEET_MIN_HALF[0], halfV: SHEET_MIN_HALF[1], centerU: 0, centerV: 0 }
      }
      // ONE pure derivation (planeFrame.projectedExtent) feeds BOTH the sheet
      // and the camera — they cannot disagree (the off-origin test pins it).
      return projectedExtent(
        [box.min.x, box.min.y, box.min.z],
        [box.max.x, box.max.y, box.max.z],
        f,
        1.15,
        SHEET_MIN_HALF,
      )
    }
    const fitSketchExtent = (f: PlaneFrameTS, e: { halfU: number; halfV: number; centerU: number; centerV: number }) => {
      const aspect = w() / h()
      frustumHalf = Math.max(e.halfV, e.halfU / Math.max(aspect, 0.1)) * 1.06
      camera.zoom = 1
      const c = new THREE.Vector3(
        f.origin[0] + e.centerU * f.u[0] + e.centerV * f.v[0],
        f.origin[1] + e.centerU * f.u[1] + e.centerV * f.v[1],
        f.origin[2] + e.centerU * f.u[2] + e.centerV * f.v[2],
      )
      const dir = camera.position.clone().sub(controls.target).normalize()
      controls.target.copy(c)
      camera.position.copy(c).addScaledVector(dir, 120)
      applyFrustum()
      controls.update()
    }

    /** The ONE sketch framing (Codex4 B1.1 extended by Codex10 B1): the
     *  Sketch-view orientation PLUS the sheet extent + entry fit, shared by
     *  the auto entry AND the mid-session `Sketch view` return — a bare
     *  orientMainCamera would end in a scene fit() that discards the sketch
     *  extent (and with it the drawing scale). */
    const applySketchFraming = (frame: PlaneFrameTS) => {
      const o = sketchViewOrientation(frame)
      orientMainCamera({ direction: [o.direction[0], o.direction[1], o.direction[2]], up: [o.up[0], o.up[1], o.up[2]] })
      const extent = sketchEntryExtent(frame)
      sketchEdit.setExtent(extent.halfU, extent.halfV, extent.centerU, extent.centerV)
      fitSketchExtent(frame, extent)
    }

    const applyInteraction = (m: SketchInteractionMode | null) => {
      const kind = m?.kind ?? 'none'
      if (kind !== 'planePick' && modeKind === 'planePick') {
        setQuadHover(null)
        if (datumsPriorVisible !== null) {
          datums.setVisible(datumsPriorVisible)
          datumsPriorVisible = null
        }
      }
      if (kind === 'planePick' && modeKind !== 'planePick') {
        // mode-scoped datum exposure (Codex1 B4.4) — restored on exit above
        datumsPriorVisible = viewStore.getSnapshot().datumsVisible
        datums.setVisible(true)
      }
      if (kind === 'sketch' && modeKind !== 'sketch' && m?.kind === 'sketch') {
        ghostPart(true)
        sketchEdit.group.visible = true
        // AUTO Sketch view on entry (Codex2 B5.4 — the Creo default); the
        // frame and every sketch fact stay camera-independent.
        applySketchFraming(m.frame)
      }
      if (kind !== 'sketch' && modeKind === 'sketch') {
        ghostPart(false)
        sketchEdit.group.visible = false
        sketchFrame = null
        sketchCbRef.current.onContextHover?.(null)
      }
      modeKind = kind
      if (m?.kind === 'sketch') {
        sketchFrame = m.frame
        sketchEdit.update(m.frame, m.tool, m.construction)
      }
    }
    applyInteractionRef.current = applyInteraction

    const onLeftDown = (e: PointerEvent) => {
      if (e.button === 0) {
        downX = e.clientX
        downY = e.clientY
      }
    }
    const onLeftUp = (e: PointerEvent) => {
      if (e.button !== 0) return
      // the slop guard doubles as the orbit-vs-place distinction (Codex3
      // bar 6): a drag gesture never places a point or picks a plane
      if (Math.hypot(e.clientX - downX, e.clientY - downY) > 4) return
      if (modeKind === 'planePick') {
        // ONE arbitration rule (hover = click winner): an ELIGIBLE planar
        // canonical face wins over a datum quad (S3 — planarFaceIds is the
        // engine's authority); otherwise the datum decides.
        const face = planarFaceAt(e.clientX, e.clientY)
        const quad = datumQuadAt(e.clientX, e.clientY)
        const orientation = quad
          ? ((quad.userData as { orientation?: 'xy' | 'yz' | 'zx' }).orientation ?? null)
          : null
        const winner = arbitratePlanePick(face?.faceId ?? null, orientation, planarFaceIdsRef.current)
        if (winner?.kind === 'face' && face) {
          sketchCbRef.current.onPlanePick?.({ kind: 'face', faceId: face.faceId, frame: face.frame })
        } else if (winner?.kind === 'datum') {
          sketchCbRef.current.onPlanePick?.(winner)
        }
        return // never canonical selection from pick mode (Codex1 B4.3)
      }
      if (modeKind === 'sketch') {
        // drawing tools own placement clicks (Codex3 bar 5); canonical
        // topology stays hover-only in this arc
        const uv = sketchUvAt(e.clientX, e.clientY)
        if (uv) sketchCbRef.current.onSketchPlace?.(uv)
        return
      }
      if (!part) return
      const filter = selectionStore.getSnapshot().filter
      const r = canvas.getBoundingClientRect()
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
      raycaster.setFromCamera(ndc, camera)
      const hit = pickDisplayId(raycaster, pickTargetsFiltered(part, filter))
      selectionStore.setSelected(hit ? { kind: hit.kind, id: hit.displayId } : null)
    }

    // Hover: route to the cube over its rect, else pre-highlight the model.
    let hoverRaf = 0
    let lastMove: PointerEvent | null = null
    const doHover = () => {
      hoverRaf = 0
      const e = lastMove
      if (!e) return
      const [px, py] = canvasRel(e)
      if (pointerInNavCube(navLayout, w(), h(), px, py)) {
        const [nx, ny] = pointerToNavCubeNdc(navLayout, w(), h(), px, py)
        navCube.setHover(navCube.pickRegion(nx, ny))
        if (hovId) {
          hovId = null
          if (modeKind === 'sketch') sketchCbRef.current.onContextHover?.(null)
          repaintHighlights()
        }
        return
      }
      navCube.setHover(null)
      if (modeKind === 'planePick') {
        // the SAME winner as click (Codex1 B4.3): an eligible planar face
        // highlights through the canonical hover; else the datum quad
        const face = planarFaceAt(e.clientX, e.clientY)
        if (face) {
          setQuadHover(null)
          const next: SelId = { kind: 'face', id: face.faceId }
          if (!sameId(next, hovId)) {
            hovId = next
            repaintHighlights()
          }
        } else {
          setQuadHover(datumQuadAt(e.clientX, e.clientY))
          if (hovId) {
            hovId = null
            repaintHighlights()
          }
        }
        return
      }
      if (modeKind === 'sketch') {
        // the live cursor rides the TRUE plane (display lift is render-only)…
        sketchCbRef.current.onSketchCursor?.(sketchUvAt(e.clientX, e.clientY))
        // …and canonical topology stays HOVERABLE (Codex2 B5.7 — the SK-E
        // seam: engine-owned ids recoverable while sketching, hover-only).
      }
      if (!part) return
      const filter = selectionStore.getSnapshot().filter
      ndc.set((px / w()) * 2 - 1, -((py / h()) * 2) + 1)
      raycaster.setFromCamera(ndc, camera)
      const hit = pickDisplayId(raycaster, pickTargetsFiltered(part, filter))
      const next: SelId = hit ? { kind: hit.kind, id: hit.displayId } : null
      if (sameId(next, hovId)) return
      hovId = next
      // Codex4 B1.3: while sketching, the hovered canonical id is SURFACED —
      // observable evidence + the operator affordance the SK-E tools build on.
      if (modeKind === 'sketch') sketchCbRef.current.onContextHover?.(next)
      repaintHighlights()
    }
    const onPointerMove = (e: PointerEvent) => {
      lastMove = e
      if (!hoverRaf) hoverRaf = requestAnimationFrame(doHover)
    }
    const onPointerLeave = () => {
      navCube.setHover(null)
      setQuadHover(null)
      if (modeKind === 'sketch') {
        sketchCbRef.current.onSketchCursor?.(null)
        sketchCbRef.current.onContextHover?.(null)
      }
      if (hovId) {
        hovId = null
        repaintHighlights()
      }
    }

    canvas.addEventListener('pointerdown', onLeftDown)
    canvas.addEventListener('pointerup', onLeftUp)
    canvas.addEventListener('pointermove', onPointerMove)
    canvas.addEventListener('pointerleave', onPointerLeave)

    const onContextMenu = (e: MouseEvent) => {
      e.preventDefault()
      // The cube owns its rect (Codex2 B1): a right-click there opens no menu.
      if (inNavCube(e)) return
      const [px, py] = canvasRel(e)
      setMenu({ x: px, y: py })
    }
    canvas.addEventListener('contextmenu', onContextMenu)

    // Complete the island (Codex2 B1): a wheel over the cube must not zoom the
    // main scene through OrbitControls. Capture + stop so its bubble listener
    // never sees it.
    const onWheelCapture = (e: WheelEvent) => {
      if (inNavCube(e)) {
        e.stopImmediatePropagation()
        e.preventDefault()
      }
    }
    canvas.addEventListener('wheel', onWheelCapture, { capture: true, passive: false })

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
      // (the empty-part grid is removed — no themed grid to rebuild here)
      if (part) applyPartTheme(part, next)
      if (dimPass) (dimPass.material as THREE.LineBasicMaterial).color.setHex(next.hiddenEdgeDim)
      if (heldHlrView) rebuildOverlayForMode()
      for (const g of importGroups.values()) restyleImport(g)
      navCube.applyTheme(NAV_CUBE_FACE, NAV_CUBE_EDGE, next.hoverHighlight)
      repaintHighlights()
      applyMode()
    }

    apiRef.current = {
      fit,
      reset,
      applyTheme,
      setDisplaySource,
      snapToView,
      standardView,
      rollView,
      orbitView,
      addImported,
      removeImported,
      setSketchWires: (sketches, frames) => sketchWires.setSketches(sketches, frames),
      sketchView: (frame) => applySketchFraming(frame),
    }
    // apply the mode that CAPTURED before the scene mounted (Codex4 NB1)
    applyInteraction(interactionModeRef.current)

    const onResize = () => {
      applyFrustum()
      renderer.setSize(w(), h())
    }
    window.addEventListener('resize', onResize)

    let rafId = 0
    const navDir = new THREE.Vector3()
    const animate = () => {
      rafId = requestAnimationFrame(animate)
      controls.update()
      renderer.render(scene, camera)
      // Nav cube overlay: mirror the main camera, then draw into the corner rect
      // (state saved/restored inside navCube.render — B1). This does NOT feed the
      // settle machine; only a programmatic main-camera move does.
      navDir.copy(controls.target).sub(camera.position).normalize()
      navCube.syncToMainView(
        [navDir.x, navDir.y, navDir.z],
        [camera.up.x, camera.up.y, camera.up.z],
      )
      // CSS-pixel rect — three.js applies pixelRatio inside setViewport/setScissor.
      navCube.render(renderer, navCubeViewportRect(navLayout, w(), h()))
    }
    animate()

    return () => {
      cancelAnimationFrame(rafId)
      if (hoverRaf) cancelAnimationFrame(hoverRaf)
      unsubStore()
      unsubSelection()
      machine.dispose()
      window.removeEventListener('resize', onResize)
      canvas.removeEventListener('pointerdown', onPointerDownCapture, true)
      canvas.removeEventListener('pointerdown', onLeftDown)
      canvas.removeEventListener('pointerup', onLeftUp)
      canvas.removeEventListener('pointermove', onPointerMove)
      canvas.removeEventListener('pointerleave', onPointerLeave)
      canvas.removeEventListener('contextmenu', onContextMenu)
      canvas.removeEventListener('wheel', onWheelCapture, true)
      navCube.dispose()
      applyInteractionRef.current = null
      sketchEdit.dispose()
      controls.dispose()
      removePart()
      for (const g of importGroups.values()) disposeGroup(g)
      importGroups.clear()
      scene.remove(datums.group)
      datums.dispose()
      scene.remove(sketchWires.group)
      sketchWires.dispose()
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
      {/* Nav-cube control cluster — the GL cube renders in the centre; these HTML
          arrows ring it (4 side = 90° yaw/pitch, 2 corner = roll). */}
      <div className="nav-cube-cluster">
        <button className="nc-arrow nc-up" type="button" title="Rotate up" aria-label="Rotate up" onClick={() => apiRef.current?.orbitView('pitch', 1)}>▲</button>
        <button className="nc-arrow nc-down" type="button" title="Rotate down" aria-label="Rotate down" onClick={() => apiRef.current?.orbitView('pitch', -1)}>▼</button>
        <button className="nc-arrow nc-left" type="button" title="Rotate left" aria-label="Rotate left" onClick={() => apiRef.current?.orbitView('yaw', 1)}>◀</button>
        <button className="nc-arrow nc-right" type="button" title="Rotate right" aria-label="Rotate right" onClick={() => apiRef.current?.orbitView('yaw', -1)}>▶</button>
        <button className="nc-arrow nc-roll-l" type="button" title="Roll left" aria-label="Roll left" onClick={() => apiRef.current?.rollView(-1)}>↺</button>
        <button className="nc-arrow nc-roll-r" type="button" title="Roll right" aria-label="Roll right" onClick={() => apiRef.current?.rollView(1)}>↻</button>
      </div>
      {selState.selected && (
        <div className="sel-badge small">
          selected: {selState.selected.kind} <code>{selState.selected.id}</code>
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
          {commandsInGroup('orientation').map(menuItem)}
          <li className="sep" />
          {commandsInGroup('display').map(menuItem)}
          <li className="sep" />
          {commandsInGroup('selection').map(menuItem)}
          <li className="sep" />
          {commandsInGroup('scene').map(menuItem)}
          <li className="sep" />
          {commandsInGroup('operations').map(menuItem)}
        </ul>
      )}
    </div>
  )
}
