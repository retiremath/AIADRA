import { describe, it, expect } from 'vitest'
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
})
