/**
 * The sketch-wire overlay (S2; arc 20260714-3 D-S2) — a committed but not yet
 * consumed sketch is VISIBLE in the viewport as its wire (closed polyline) on
 * its plane, exactly like Creo shows an unconsumed sketch curve.
 *
 * This is derived NONCANONICAL display: the rings come from the RECIPE (the
 * decoded inspect view — `inspectDecode.unconsumedSketches`), mapped through
 * the EP2 principal frames. It rides the same overlay lane as the datum
 * scaffold: stable `sketch-wire:<feature_id>` ids in userData only, never
 * canonical topology identity, never a canonical pick target, excluded from
 * fit (it lives outside the canonical part group). NO display-contract
 * amendment — the contract stays geometry-only.
 */
import * as THREE from 'three'
import type { InspectedSketch } from '../authoring/inspectDecode'
import type { PlaneOrientation } from '../authoring/backend'
import type { SketchFrame } from '../display/contract'

export const SKETCH_WIRE_PREFIX = 'sketch-wire:'

/** The EP2 principal frames (u,v,normal) — mirrors engine `recipe.py`, same
 *  table as the mock's procedural extrude. */
const FRAME_AXES: Record<PlaneOrientation, [number[], number[]]> = {
  xy: [
    [1, 0, 0],
    [0, 1, 0],
  ],
  yz: [
    [0, 1, 0],
    [0, 0, 1],
  ],
  zx: [
    [0, 0, 1],
    [1, 0, 0],
  ],
}

function toWorld(ori: PlaneOrientation, u: number, v: number): THREE.Vector3 {
  const [U, V] = FRAME_AXES[ori]
  return new THREE.Vector3(u * U[0] + v * V[0], u * U[1] + v * V[1], u * U[2] + v * V[2])
}

export interface SketchWireOverlay {
  group: THREE.Group
  /** Replace the wire set (idempotent; disposes what it removes). S3: the
   *  ENGINE-resolved frames (Display v1.2 sketch_frames) join by sketch
   *  feature id — a face-bound wire renders through ITS frame; a missing
   *  frame keeps the wire honestly unavailable (never guessed). */
  setSketches(sketches: InspectedSketch[], frames?: ReadonlyMap<string, SketchFrame>): void
  /** P (arc 20260717-2): the sketchSolicit hover affordance — brighten every
   *  wire of ONE sketch id (null clears). Display-only, never identity. */
  setHover(sketchId: string | null): void
  dispose(): void
}

export function createSketchWireOverlay(color = 0xd9a441, hoverColor = 0xffe08a): SketchWireOverlay {
  const group = new THREE.Group()
  group.name = 'sketch-wire-overlay'
  let disposables: { dispose(): void }[] = []
  let hovered: string | null = null

  const clear = () => {
    for (const d of disposables) d.dispose()
    disposables = []
    group.clear()
  }

  return {
    group,
    setSketches(sketches, frames) {
      clear()
      for (const sk of sketches) {
        // S3: resolve the sketch's WORLD mapping — principal via the mirror
        // table; face-bound via the ENGINE frame from the display package.
        const faceFrame = sk.plane.kind === 'face' ? frames?.get(sk.id) ?? null : null
        // SK-C0: per-entity wires — construction guides render DASHED
        // (LineDashedMaterial + computeLineDistances, unit-asserted).
        const wires = sk.wires?.length
          ? sk.wires
          : sk.rings.map((points) => ({ points, construction: false, closed: true }))
        for (const wire of wires) {
          if (wire.points.length < 2) continue
          // Principal renders via the mirror table; face-bound renders via
          // the ENGINE frame — or stays honestly unavailable without one.
          if (sk.plane.kind !== 'principal' && !faceFrame) continue
          const pts = sk.plane.kind === 'principal'
            ? wire.points.map((p) => toWorld((sk.plane as { orientation: PlaneOrientation }).orientation, p.x, p.y))
            : wire.points.map((p) => new THREE.Vector3(
                faceFrame!.origin_mm[0] + p.x * faceFrame!.u_axis[0] + p.y * faceFrame!.v_axis[0],
                faceFrame!.origin_mm[1] + p.x * faceFrame!.u_axis[1] + p.y * faceFrame!.v_axis[1],
                faceFrame!.origin_mm[2] + p.x * faceFrame!.u_axis[2] + p.y * faceFrame!.v_axis[2],
              ))
          if (wire.closed) pts.push(pts[0].clone())
          const geom = new THREE.BufferGeometry().setFromPoints(pts)
          const mat = wire.construction
            ? new THREE.LineDashedMaterial({ color, depthWrite: false, dashSize: 3, gapSize: 2 })
            : new THREE.LineBasicMaterial({ color, depthWrite: false })
          const line = new THREE.Line(geom, mat)
          if (wire.construction) line.computeLineDistances()
          line.renderOrder = 3 // above the part edges, like a Creo sketch curve
          line.name = `${SKETCH_WIRE_PREFIX}${sk.id}`
          line.userData = { kind: 'sketch-wire', sketchFeatureId: sk.id, plane: sk.plane, construction: wire.construction }
          group.add(line)
          disposables.push(geom, mat)
        }
      }
    },
    setHover(sketchId) {
      if (sketchId === hovered) return
      hovered = sketchId
      for (const child of group.children) {
        const ud = child.userData as { sketchFeatureId?: string }
        const mat = (child as THREE.Line).material as THREE.LineBasicMaterial
        mat.color.setHex(ud.sketchFeatureId === sketchId ? hoverColor : color)
      }
    },
    dispose() {
      clear()
    },
  }
}
