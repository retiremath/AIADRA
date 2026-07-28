/**
 * The icon coverage law (pass icons-1; Codex1 N1): the FreeCAD-glyph key set
 * is EXACT — a future override of a deliberately monoline key (or a silent
 * loss of an approved glyph) fails HERE, not in a reviewer's eye. The
 * every-key-resolves floor lives in the ribbon tests; this pins WHICH
 * language each key speaks.
 */
// @vitest-environment jsdom
import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { FREECAD_GLYPH_KEYS, ICONS } from './icons'

/** The Codex1-approved glyph set (B1: the five unfaithful overrides —
 *  swept-blend, pattern, remove, unify, boundary-blend — stay MONOLINE). */
const APPROVED = [
  'boolean-ops', 'chamfer', 'datum-axis', 'datum-csys', 'datum-plane',
  'datum-point', 'draft', 'extrude', 'fill', 'get-data', 'hole',
  'intersect', 'merge', 'mirror', 'new-body', 'offset', 'regenerate',
  'revolve', 'round', 'shell', 'sketch', 'solidify', 'split',
  'split-trim-body', 'sweep', 'thicken',
] as const

describe('the icon coverage law (icons-1)', () => {
  it('the glyph key set is EXACT (no silent expansion or loss)', () => {
    expect([...FREECAD_GLYPH_KEYS]).toEqual([...APPROVED])
  })

  it('approved keys render vendored <img> glyphs; retained keys render inline monoline svg', () => {
    for (const key of APPROVED) {
      const { container, unmount } = render(<>{ICONS[key]}</>)
      expect(container.querySelector('img'), key).toBeTruthy()
      unmount()
    }
    // the five Codex1-B1 reverts + representative small-chrome keys
    for (const key of ['swept-blend', 'pattern', 'remove', 'unify', 'boundary-blend', 'fit', 'zoom-in', 'rib', 'trim', 'project']) {
      const { container, unmount } = render(<>{ICONS[key]}</>)
      expect(container.querySelector('svg'), key).toBeTruthy()
      expect(container.querySelector('img'), key).toBeNull()
      unmount()
    }
  })
})
