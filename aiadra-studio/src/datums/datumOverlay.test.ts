import { describe, it, expect } from 'vitest'
import * as THREE from 'three'
import { createDatumOverlay } from './datumOverlay'
import { INTRINSIC_CSYS_ID, INTRINSIC_PLANE_IDS } from '../authoring/backend'

describe('the datum overlay (EP1 — the empty-part scaffold)', () => {
  it('carries the three intrinsic planes + the origin csys under STABLE overlay ids', () => {
    const overlay = createDatumOverlay()
    const ids = new Set<string>()
    overlay.group.traverse((o) => {
      const id = (o.userData as { intrinsicId?: string }).intrinsicId
      if (id) ids.add(id)
    })
    for (const ori of ['xy', 'yz', 'zx'] as const) expect(ids).toContain(INTRINSIC_PLANE_IDS[ori])
    expect(ids).toContain(INTRINSIC_CSYS_ID)
    overlay.dispose()
  })

  it('toggles visibility as one group (the scene.datums command target)', () => {
    const overlay = createDatumOverlay()
    expect(overlay.group.visible).toBe(true)
    overlay.setVisible(false)
    expect(overlay.group.visible).toBe(false)
    overlay.setVisible(true)
    expect(overlay.group.visible).toBe(true)
    overlay.dispose()
  })

  it('per-kind filters hide ONLY their sub-lane (the Creo datum-display dropdown)', () => {
    const overlay = createDatumOverlay()
    const lane = (name: string) => overlay.group.children.find((c) => c.name === name)!
    expect(lane('datum-planes').visible).toBe(true)
    expect(lane('datum-fill').visible).toBe(true)
    expect(lane('datum-origin').visible).toBe(true)
    overlay.setKindVisible('fill', false)
    expect(lane('datum-fill').visible).toBe(false)
    expect(lane('datum-planes').visible).toBe(true) // untouched
    expect(lane('datum-origin').visible).toBe(true)
    overlay.setKindVisible('origin', false)
    expect(lane('datum-origin').visible).toBe(false)
    overlay.setKindVisible('fill', true)
    expect(lane('datum-fill').visible).toBe(true)
    // the master gate is INDEPENDENT of the filters
    overlay.setVisible(false)
    expect(overlay.group.visible).toBe(false)
    expect(lane('datum-fill').visible).toBe(true)
    overlay.dispose()
  })

  it('pickTargets() is the plane-pick CONTRACT: three quads, raycastable, grouping-independent', () => {
    // REGRESSION (2026-07-25): the sub-lane restructure moved the quads one
    // level deeper and a non-recursive raycast over `group.children` went
    // silently dead — the sketch plane pick broke with every suite green.
    const overlay = createDatumOverlay()
    const targets = overlay.pickTargets()
    expect(targets).toHaveLength(3)
    const oris = targets.map((t) => (t.userData as { orientation: string }).orientation).sort()
    expect(oris).toEqual(['xy', 'yz', 'zx'])
    for (const t of targets) {
      expect((t.userData as { kind: string }).kind).toBe('intrinsic-plane')
    }
    // and they actually INTERSECT: a ray down the -Z axis must hit the XY quad
    overlay.group.updateMatrixWorld(true)
    const ray = new THREE.Raycaster(new THREE.Vector3(5, 5, 100), new THREE.Vector3(0, 0, -1))
    const hits = ray.intersectObjects(overlay.pickTargets(), false)
    expect(hits.length).toBeGreaterThan(0)
    expect((hits[0].object.userData as { orientation: string }).orientation).toBe('xy')
    overlay.dispose()
  })

  it('is an OVERLAY lane — no child carries canonical display identity', () => {
    const overlay = createDatumOverlay()
    overlay.group.traverse((o) => {
      const u = o.userData as { displayId?: string; faceId?: string; edgeId?: string }
      expect(u.displayId).toBeUndefined() // never a canonical pick target
      expect(u.faceId).toBeUndefined()
      expect(u.edgeId).toBeUndefined()
    })
    overlay.dispose()
  })
  it('the origin csys is THREE ARROWS (shaft + head) — X/Y/Z under the csys id (the Creo csys look)', () => {
    const overlay = createDatumOverlay()
    const arrows: THREE.ArrowHelper[] = []
    overlay.group.traverse((o) => {
      if ((o.userData as { kind?: string }).kind === 'intrinsic-csys-axis') arrows.push(o as THREE.ArrowHelper)
    })
    expect(arrows.map((a) => (a.userData as { axis: string }).axis).sort()).toEqual(['X', 'Y', 'Z'])
    for (const a of arrows) {
      expect(a).toBeInstanceOf(THREE.ArrowHelper)
      expect(a.cone).toBeTruthy() // the head
      expect(a.line).toBeTruthy() // the shaft
      expect((a.userData as { intrinsicId: string }).intrinsicId).toBe(INTRINSIC_CSYS_ID)
    }
    // they live in the origin lane, so the datum-display "origin" filter hides them
    const originLane = overlay.group.children.find((c) => c.name === 'datum-origin')!
    let inLane = 0
    originLane.traverse((o) => {
      if ((o.userData as { kind?: string }).kind === 'intrinsic-csys-axis') inLane++
    })
    expect(inLane).toBe(3)
    overlay.dispose()
  })

})
