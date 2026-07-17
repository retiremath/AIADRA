/**
 * The in-context sketch-EDIT overlay (arc 20260716-2 SK-C1.0 S1; Codex2 B5.2)
 * — the live drawing rendered in WORLD SPACE through the selected PlaneFrame
 * from the FIRST click: placed contour segments (lines + bulge arcs), the
 * rubber segment to the cursor (with the 3-point-arc via preview), rectangle
 * and circle previews, the support tint quad, and the sketch origin + u/v
 * axis marker. A sibling lane to `sketchWireOverlay` with the same identity
 * rules: overlay-only, never a canonical pick target.
 *
 * Geometry is stored plane-local (u, v) mm in the session store; THIS module
 * maps it to world through `frameToWorld` with the DISPLAY-ONLY
 * `SKETCH_LIFT_MM` (Codex3 bar 3 — the true support plane owns input and
 * facts; the lift only defeats z-fighting).
 */
import * as THREE from 'three'
import type { SketchTool } from '../authoring/authoringSession'
import { pointsToSegments, type Pt } from './contour'
import { bulgeFromThreePoints, tessellateCircle, tessellateSegments, type ContourSegment } from './arcGeometry'
import { frameToWorld, SKETCH_LIFT_MM, type PlaneFrameTS } from './planeFrame'

export interface SketchEditOverlay {
  group: THREE.Group
  /** Re-render from the live tool state (cheap rebuild — interaction-rate). */
  update(frame: PlaneFrameTS, tool: SketchTool, construction: boolean): void
  /** The support tint extent + CENTER in plane-local mm (Codex5 B1.1 — the
   *  sheet centers on the projected Part bounds; the ORIGIN marker stays at
   *  the frame origin). Defaults to the classic pad sheet at the origin. */
  setExtent(halfU: number, halfV: number, centerU?: number, centerV?: number): void
  dispose(): void
}

const COLOR_LIVE = 0x1d4ed8 // committed-in-progress strokes
const COLOR_RUBBER = 0x64748b
const COLOR_TINT = 0x2b5e8f // the support sheet (plane-xy family hue)
const COLOR_U = 0xb03333 // sketch u-axis (matches the X label hue)
const COLOR_V = 0x2e8b2e // sketch v-axis (matches Y)

export function createSketchEditOverlay(): SketchEditOverlay {
  const group = new THREE.Group()
  group.name = 'sketch-edit-overlay'
  let extent: [number, number] = [130, 85]
  let extentCenter: [number, number] = [0, 0]
  const disposables: { dispose(): void }[] = []
  const perUpdate: THREE.Object3D[] = []
  let frameApplied: PlaneFrameTS | null = null

  // ---- static per-session pieces (tint quad, border, origin, axes) ----
  const staticGroup = new THREE.Group()
  group.add(staticGroup)

  const clearStatic = () => {
    for (const child of [...staticGroup.children]) staticGroup.remove(child)
  }

  const buildStatic = (f: PlaneFrameTS) => {
    clearStatic()
    const [hu, hv] = extent
    const [cu, cv] = extentCenter
    // sheet corners around the PROJECTED-BOUNDS center; origin/axes stay at
    // the frame origin (the sketch origin is a fact, the sheet is not)
    const corner = (u: number, v: number) => new THREE.Vector3(...frameToWorld(f, u, v))
    const sheet = (u: number, v: number) => corner(cu + u, cv + v)
    // the tint sheet (never depth-writing; the Part stays readable through it)
    const quadGeom = new THREE.BufferGeometry().setFromPoints([
      sheet(-hu, -hv), sheet(hu, -hv), sheet(hu, hv),
      sheet(-hu, -hv), sheet(hu, hv), sheet(-hu, hv),
    ])
    const quadMat = new THREE.MeshBasicMaterial({
      color: COLOR_TINT, transparent: true, opacity: 0.05, side: THREE.DoubleSide, depthWrite: false,
    })
    staticGroup.add(new THREE.Mesh(quadGeom, quadMat))
    disposables.push(quadGeom, quadMat)
    const borderGeom = new THREE.BufferGeometry().setFromPoints([
      sheet(-hu, -hv), sheet(hu, -hv), sheet(hu, hv), sheet(-hu, hv), sheet(-hu, -hv),
    ])
    const borderMat = new THREE.LineBasicMaterial({ color: COLOR_TINT, transparent: true, opacity: 0.45 })
    staticGroup.add(new THREE.Line(borderGeom, borderMat))
    disposables.push(borderGeom, borderMat)
    // the sketch origin + axis stubs (u red-family, v green-family) — the
    // VISIBLE origin convention Petre judges (Codex1 non-blocker 2)
    const axis = (du: number, dv: number, color: number) => {
      const g = new THREE.BufferGeometry().setFromPoints([
        corner(0, 0), corner(du, dv),
      ])
      const m = new THREE.LineBasicMaterial({ color, depthTest: false, transparent: true })
      const line = new THREE.Line(g, m)
      line.renderOrder = 3
      staticGroup.add(line)
      disposables.push(g, m)
    }
    axis(12, 0, COLOR_U)
    axis(0, 12, COLOR_V)
    const originGeom = new THREE.SphereGeometry(0.8, 10, 10)
    const originMat = new THREE.MeshBasicMaterial({ color: 0x24272c, depthTest: false })
    const origin = new THREE.Mesh(originGeom, originMat)
    origin.position.copy(corner(0, 0))
    origin.renderOrder = 3
    staticGroup.add(origin)
    disposables.push(originGeom, originMat)
  }

  const clearPerUpdate = () => {
    for (const obj of perUpdate) {
      group.remove(obj)
      const line = obj as THREE.Line
      line.geometry?.dispose()
      ;(line.material as THREE.Material | undefined)?.dispose?.()
    }
    perUpdate.length = 0
  }

  const worldPoints = (f: PlaneFrameTS, pts: Pt[]): THREE.Vector3[] =>
    pts.map((p) => new THREE.Vector3(...frameToWorld(f, p.x, p.y, SKETCH_LIFT_MM)))

  const addLine = (f: PlaneFrameTS, pts: Pt[], color: number, dashed: boolean) => {
    if (pts.length < 2) return
    const geom = new THREE.BufferGeometry().setFromPoints(worldPoints(f, pts))
    const mat = dashed
      ? new THREE.LineDashedMaterial({ color, dashSize: 2.4, gapSize: 1.6 })
      : new THREE.LineBasicMaterial({ color })
    const line = new THREE.Line(geom, mat)
    if (dashed) line.computeLineDistances()
    line.renderOrder = 2
    group.add(line)
    perUpdate.push(line)
  }

  const addMarker = (f: PlaneFrameTS, p: Pt, color: number) => {
    const geom = new THREE.SphereGeometry(0.7, 8, 8)
    const mat = new THREE.MeshBasicMaterial({ color, depthTest: false })
    const m = new THREE.Mesh(geom, mat)
    m.position.set(...frameToWorld(f, p.x, p.y, SKETCH_LIFT_MM))
    m.renderOrder = 3
    group.add(m)
    perUpdate.push(m)
  }

  const placedSegments = (points: Pt[], bulges: number[]): ContourSegment[] =>
    points.slice(0, -1).map((p, i) => {
      const q = points[i + 1]
      const b = bulges[i] ?? 0
      return b !== 0
        ? { kind: 'arc', x1_mm: p.x, y1_mm: p.y, x2_mm: q.x, y2_mm: q.y, bulge: b }
        : { kind: 'line', x1_mm: p.x, y1_mm: p.y, x2_mm: q.x, y2_mm: q.y }
    })

  return {
    group,
    setExtent(halfU, halfV, centerU = 0, centerV = 0) {
      extent = [halfU, halfV]
      extentCenter = [centerU, centerV]
      if (frameApplied) buildStatic(frameApplied)
    },
    update(frame, tool, construction) {
      if (frameApplied !== frame) {
        frameApplied = frame
        buildStatic(frame)
      }
      clearPerUpdate()
      const stroke = construction ? true : false // construction renders dashed
      if (tool.kind === 'contour') {
        const { points, bulges, cursor, closed, awaitingVia } = tool
        for (const p of points) addMarker(frame, p, COLOR_LIVE)
        if (!closed && points.length >= 2) {
          // open: only the placed segments (the CLOSED loop below replaces
          // this stroke entirely — Codex4 NB2: no duplicate rendering)
          const segs = placedSegments(points, bulges)
          const pts = tessellateSegments(segs)
          pts.push(points[points.length - 1])
          addLine(frame, pts, COLOR_LIVE, stroke)
        }
        if (closed && points.length >= 3) {
          const pts = tessellateSegments(pointsToSegments(points, bulges))
          pts.push(points[0])
          addLine(frame, pts, COLOR_LIVE, stroke)
        }
        if (!closed && cursor && points.length >= 1) {
          const last = points[points.length - 1]
          if (awaitingVia && points.length >= 2) {
            // the via preview: the arc through (prev → cursor → last)'s route
            const prev = points[points.length - 2]
            const b = bulgeFromThreePoints(prev, cursor, last)
            if (b !== null) {
              const pts = tessellateSegments([
                { kind: 'arc', x1_mm: prev.x, y1_mm: prev.y, x2_mm: last.x, y2_mm: last.y, bulge: b },
              ])
              pts.push(last)
              addLine(frame, pts, COLOR_RUBBER, false)
            }
          } else {
            addLine(frame, [last, cursor], COLOR_RUBBER, false)
          }
        }
      } else if (tool.kind === 'rectangle') {
        const rect = tool.rect ?? (tool.anchor && tool.cursor
          ? { x_mm: Math.min(tool.anchor.x, tool.cursor.x), y_mm: Math.min(tool.anchor.y, tool.cursor.y),
              width_mm: Math.abs(tool.cursor.x - tool.anchor.x), height_mm: Math.abs(tool.cursor.y - tool.anchor.y) }
          : null)
        if (tool.anchor) addMarker(frame, tool.anchor, COLOR_LIVE)
        if (rect && rect.width_mm > 0 && rect.height_mm > 0) {
          const { x_mm: x, y_mm: y, width_mm: w, height_mm: h } = rect
          addLine(frame, [
            { x, y }, { x: x + w, y }, { x: x + w, y: y + h }, { x, y: y + h }, { x, y },
          ], tool.rect ? COLOR_LIVE : COLOR_RUBBER, stroke && !!tool.rect)
        }
      } else {
        // circle
        if (tool.center) addMarker(frame, tool.center, COLOR_LIVE)
        const circle = tool.circle ?? (tool.center && tool.cursor
          ? { cx_mm: tool.center.x, cy_mm: tool.center.y,
              radius_mm: Math.hypot(tool.cursor.x - tool.center.x, tool.cursor.y - tool.center.y) }
          : null)
        if (circle && circle.radius_mm > 0) {
          const pts = tessellateCircle(circle.cx_mm, circle.cy_mm, circle.radius_mm)
          pts.push(pts[0])
          addLine(frame, pts, tool.circle ? COLOR_LIVE : COLOR_RUBBER, stroke && !!tool.circle)
        }
      }
    },
    dispose() {
      clearPerUpdate()
      clearStatic()
      for (const d of disposables) d.dispose()
    },
  }
}
