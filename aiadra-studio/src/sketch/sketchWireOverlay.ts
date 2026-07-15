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
  /** Replace the wire set (idempotent; disposes what it removes). */
  setSketches(sketches: InspectedSketch[]): void
  dispose(): void
}

export function createSketchWireOverlay(color = 0xd9a441): SketchWireOverlay {
  const group = new THREE.Group()
  group.name = 'sketch-wire-overlay'
  let disposables: { dispose(): void }[] = []

  const clear = () => {
    for (const d of disposables) d.dispose()
    disposables = []
    group.clear()
  }

  return {
    group,
    setSketches(sketches) {
      clear()
      for (const sk of sketches) {
        for (const ring of sk.rings) {
          if (ring.length < 2) continue
          const pts = ring.map((p) => toWorld(sk.plane, p.x, p.y))
          pts.push(pts[0].clone()) // closed
          const geom = new THREE.BufferGeometry().setFromPoints(pts)
          const mat = new THREE.LineBasicMaterial({ color, depthWrite: false })
          const line = new THREE.Line(geom, mat)
          line.renderOrder = 3 // above the part edges, like a Creo sketch curve
          line.name = `${SKETCH_WIRE_PREFIX}${sk.id}`
          line.userData = { kind: 'sketch-wire', sketchFeatureId: sk.id, plane: sk.plane }
          group.add(line)
          disposables.push(geom, mat)
        }
      }
    },
    dispose() {
      clear()
    },
  }
}
