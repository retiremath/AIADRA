/**
 * The profile status line (W-2) — the statusbar teaches the chain grammar
 * (the gestures are otherwise invisible: middle-click, first-point close,
 * Esc), and the slot no longer goes silent during a profile session.
 */
// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { ProfileStatusLine } from './ProfileStatusLine'
import { profileHint } from './profileHint'
import { commitPoint, openCreate, openEdit, setTool } from './profileSession'
import type { SketchPlacementInput } from './profileTypes'

afterEach(cleanup)

const PLACEMENT: SketchPlacementInput = {
  support: { kind: 'principal', orientation: 'xy' },
}
const OPTS = { snapAngleToleranceDeg: 3, minDragPx: 4 }
const TARGET = { workspaceId: 'ws1', partNumber: 'P-000001', generation: 7 }
const FRAME = {
  origin: [0, 0, 0] as [number, number, number],
  u: [1, 0, 0] as [number, number, number],
  v: [0, 1, 0] as [number, number, number],
  normal: [0, 0, 1] as [number, number, number],
}

const create = () => openCreate(PLACEMENT, 'draft1', FRAME, TARGET, OPTS)

describe('the live hint names the actual gestures', () => {
  it('an armed line chain invites the first click; a run teaches end/close/abandon', () => {
    expect(profileHint(create())).toMatch(/click to start/)
    const hint = profileHint(commitPoint(create(), { u: 0, v: 0 }))
    expect(hint).toMatch(/middle-click ends/)
    expect(hint).toMatch(/first point to close/)
    expect(hint).toMatch(/Esc abandons/)
  })

  it('rectangle and circle keep their two-click prompts', () => {
    expect(profileHint(setTool(create(), 'rectangle'))).toMatch(/first corner/)
    expect(profileHint(setTool(create(), 'circle'))).toMatch(/center/)
    expect(profileHint(commitPoint(setTool(create(), 'circle'), { u: 0, v: 0 }))).toMatch(/rim/)
  })
})

describe('identity + lane badge (the SR-08 tenancy shape)', () => {
  it('a create session names its plane and Part; the lane badge is honest', () => {
    render(<ProfileStatusLine session={create()} isReal={false} />)
    const line = screen.getByTestId('profile-status')
    expect(line.textContent).toContain('Profile Sketch — TOP (xy)')
    expect(line.textContent).toContain('P-000001')
    expect(line.textContent).toContain('dev mock')
  })

  it('an edit session names the feature it owns', () => {
    const s = openEdit('feat_0007', { points: [] }, FRAME, TARGET, OPTS)
    render(<ProfileStatusLine session={s} isReal={true} />)
    const line = screen.getByTestId('profile-status')
    expect(line.textContent).toContain('editing feat_0007')
    expect(line.textContent).toContain('real engine')
  })
})
