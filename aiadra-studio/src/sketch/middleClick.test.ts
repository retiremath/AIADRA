/**
 * The middle-button pair (W-2, Codex11 N3) — pure regressions for the
 * click-vs-orbit distinction and the stale-gesture guards.
 */
import { describe, expect, it } from 'vitest'
import { midPairDown, midPairIsClick } from './middleClick'

const at = (pointerId: number, x: number, y: number) => ({ pointerId, clientX: x, clientY: y })

describe('the MMB pair', () => {
  it('an up paired with its own down within the slop is a click', () => {
    const pair = midPairDown(at(7, 100, 100))
    expect(midPairIsClick(pair, at(7, 103, 102))).toBe(true)
  })

  it('travel beyond the slop is an orbit drag, not a click', () => {
    const pair = midPairDown(at(7, 100, 100))
    expect(midPairIsClick(pair, at(7, 100, 106))).toBe(false)
  })

  it('a mismatched pointer id never pairs — a foreign up cannot borrow coordinates', () => {
    const pair = midPairDown(at(7, 100, 100))
    expect(midPairIsClick(pair, at(8, 100, 100))).toBe(false)
  })

  it('no tracked down (swallowed, cancelled, or cleared) means no click', () => {
    expect(midPairIsClick(null, at(7, 100, 100))).toBe(false)
  })

  it('the slop boundary is inclusive and matches the LMB guard default', () => {
    const pair = midPairDown(at(1, 0, 0))
    expect(midPairIsClick(pair, at(1, 4, 0))).toBe(true)
    expect(midPairIsClick(pair, at(1, 5, 0))).toBe(false)
  })
})
