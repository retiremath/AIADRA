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
