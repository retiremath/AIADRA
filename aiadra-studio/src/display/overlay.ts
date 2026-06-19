/**
 * Settled HLR overlay builder (arc 20260610-1, Claude1 P5).
 *
 * Lifts the engine's 2D view-plane segments back into 3D on the view plane —
 * `p = origin + u·right + v·up` (the contract-complete frame, ADR/0036
 * Codex1 B2) — so that under the SAME orthographic camera they project
 * pixel-identically onto the part. Drawn depth-test-off above the base scene;
 * visible = bright, hidden = dim, per `overlaySegmentStyle`.
 *
 * EPHEMERAL-IDENTITY FIREWALL (ADR/0036 Codex1 B5; this arc Codex1 N3): no
 * object in the returned group carries a `displayId` in `userData`, and the
 * group must NEVER be added to the viewport's raycast target set. Outlines are
 * per-view ephemeral; even the model-edge segments here are view classification,
 * not the identity source. The group is disposed wholesale on every swap.
 */
import * as THREE from 'three'
import type { HlrView } from './contract'
import { type DisplayMode, overlaySegmentStyle } from './modes'

export const OVERLAY_GROUP_NAME = 'hlr-overlay'

// Stopgap defaults matching the canonical-part edge palette; theming is step 6.
export const OVERLAY_BRIGHT_COLOR = 0x222226
export const OVERLAY_DIM_COLOR = 0xb4bac2

/** Render order above faces (0) and base edge passes (1–2). */
const OVERLAY_RENDER_ORDER = 3

function lift(view: HlrView, polyline2d: number[]): Float32Array {
  const { origin, right, up } = view.projector
  const pointCount = polyline2d.length / 2
  if (pointCount < 2) return new Float32Array(0)
  const segCount = pointCount - 1
  const out = new Float32Array(segCount * 6)
  const at = (i: number, o: number) => {
    const u = polyline2d[i * 2]
    const v = polyline2d[i * 2 + 1]
    out[o] = origin[0] + u * right[0] + v * up[0]
    out[o + 1] = origin[1] + u * right[1] + v * up[1]
    out[o + 2] = origin[2] + u * right[2] + v * up[2]
  }
  for (let s = 0; s < segCount; s++) {
    at(s, s * 6)
    at(s + 1, s * 6 + 3)
  }
  return out
}

export function buildHlrOverlay(view: HlrView, mode: DisplayMode): THREE.Group {
  const group = new THREE.Group()
  group.name = OVERLAY_GROUP_NAME

  const bright: number[] = []
  const dim: number[] = []
  for (const seg of view.segments) {
    const style = overlaySegmentStyle(mode, seg.visibility)
    if (style === 'omit') continue
    const positions = lift(view, seg.polyline_2d)
    ;(style === 'bright' ? bright : dim).push(...positions)
  }

  const addPass = (positions: number[], color: number) => {
    if (positions.length === 0) return
    const geom = new THREE.BufferGeometry()
    geom.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
    const mat = new THREE.LineBasicMaterial({ color, depthTest: false, depthWrite: false })
    const lines = new THREE.LineSegments(geom, mat)
    lines.renderOrder = OVERLAY_RENDER_ORDER
    // Firewall: NO displayId, no pickable identity of any kind.
    lines.userData = {}
    group.add(lines)
  }
  // Dim under bright so visible classification reads on top.
  addPass(dim, OVERLAY_DIM_COLOR)
  addPass(bright, OVERLAY_BRIGHT_COLOR)
  return group
}

export function disposeOverlay(group: THREE.Group): void {
  group.traverse((o) => {
    const lines = o as THREE.LineSegments
    if (lines.isLineSegments) {
      lines.geometry?.dispose()
      const mats = Array.isArray(lines.material) ? lines.material : [lines.material]
      mats.forEach((m) => m?.dispose())
    }
  })
}
