/**
 * The view-scale feed seam (Codex17 B1) — a source-level regression in the
 * clipping-ban precedent's style (the ribbon CSS test reads index.css):
 * the Viewport cannot be mounted headlessly, so the seam that MUST hold is
 * pinned at the source: every programmatic camera-scale mutation announces
 * itself through the ONE named exit `cameraScaleChanged()` (settle machine
 * + furniture view-scale feed), and the interactive/resize paths feed too.
 * A refactor that reroutes zoom without the feed fails here, not in Petre's
 * walk.
 */
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const src = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), '..', 'Viewport.tsx'),
  'utf-8',
)

const bodyOf = (decl: string): string => {
  const start = src.indexOf(decl)
  expect(start, `declaration ${decl} exists`).toBeGreaterThan(-1)
  // Codex18 N1: bound the slice at the NEXT sibling declaration (the mount
  // effect's 4-space indent) so an assertion can never match text from a
  // neighbouring function. Nested `const` at deeper indents stay inside.
  const next = src.indexOf('\n    const ', start + decl.length)
  expect(next, `a sibling declaration bounds ${decl}`).toBeGreaterThan(-1)
  return src.slice(start, next)
}

describe('every programmatic camera-scale change feeds the furniture scale', () => {
  it('cameraScaleChanged is the ONE named exit: settle + view-scale feed', () => {
    const body = bodyOf('const cameraScaleChanged = ')
    expect(body).toContain('machine.cameraMoved()')
    expect(body).toContain('feedViewScale()')
  })

  it('zoomBy routes through cameraScaleChanged (the Codex17 B1 gap)', () => {
    expect(bodyOf('const zoomBy = ')).toContain('cameraScaleChanged()')
  })

  it('fit and reset route through cameraScaleChanged', () => {
    expect(bodyOf('const fit = ')).toContain('cameraScaleChanged()')
    expect(bodyOf('const reset = ')).toContain('cameraScaleChanged()')
  })

  it('the interactive path (controls change) and canvas resize feed as well', () => {
    const change = src.indexOf("controls.addEventListener('change'")
    expect(src.slice(change, change + 200)).toContain('feedViewScale()')
    expect(bodyOf('const onResize = ')).toContain('feedViewScale()')
  })

  it('the feed reaches BOTH lanes: the live overlay and every committed overlay', () => {
    const feed = bodyOf('const feedViewScale = ')
    expect(feed).toContain('profileOverlay.setViewScale')
    expect(feed).toContain('committedOverlays.values()')
  })
})
