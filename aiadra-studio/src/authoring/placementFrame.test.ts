/**
 * The transient placement mirror vs the ENGINE's literal derivation matrix
 * (ADR/0044 A3.5; `tests/data/placement_matrix.jsonl` engine-side). Anchor
 * rows are pasted VERBATIM from that matrix — the mirror can never drift
 * from the engine without this file going red.
 */
import { describe, expect, it } from 'vitest'
import {
  defaultPlacement,
  deriveFrame,
  isPlacementRecord,
  placementToWorld,
  type PlacementRecord,
} from './placementFrame'

const P = (support: string, ref: string, orientation: string, side: string): PlacementRecord =>
  ({
    support: { kind: 'principal', orientation: support },
    orientation_ref: { kind: 'principal', orientation: ref },
    orientation,
    normal_side: side,
  }) as PlacementRecord

// verbatim rows from the engine matrix (support, ref, orientation, side, u, v, n)
const ENGINE_ROWS: Array<[string, string, string, string, number[], number[], number[]]> = [
  ['xy', 'yz', 'right', 'positive', [1, 0, 0], [0, 1, 0], [0, 0, 1]],
  ['xy', 'yz', 'right', 'negative', [1, 0, 0], [0, -1, 0], [-0, -0, -1]],
  ['xy', 'yz', 'top', 'positive', [0, -1, 0], [1, 0, 0], [0, 0, 1]],
  ['xy', 'zx', 'right', 'positive', [0, 1, 0], [-1, 0, 0], [0, 0, 1]],
  ['yz', 'zx', 'right', 'positive', [0, 1, 0], [0, 0, 1], [1, 0, 0]],
  ['yz', 'xy', 'bottom', 'negative', [0, 1, 0], [-0, -0, -1], [-1, -0, -0]],
  ['zx', 'xy', 'right', 'positive', [0, 0, 1], [1, 0, 0], [0, 1, 0]],
  ['zx', 'yz', 'left', 'negative', [-1, -0, -0], [0, 0, -1], [-0, -1, -0]],
]

describe('the placement frame mirror (engine parity)', () => {
  it.each(ENGINE_ROWS)('%s/%s/%s/%s derives the engine axes', (s, r, o, side, u, v, n) => {
    const got = deriveFrame(P(s, r, o, side))
    expect(got.u.map((x) => x + 0)).toEqual(u.map((x) => x + 0))
    expect(got.v.map((x) => x + 0)).toEqual(v.map((x) => x + 0))
    expect(got.n.map((x) => x + 0)).toEqual(n.map((x) => x + 0))
  })

  it('the three defaults reproduce the legacy frames exactly', () => {
    expect(deriveFrame(defaultPlacement('xy'))).toEqual({ u: [1, 0, 0], v: [0, 1, 0], n: [0, 0, 1] })
    expect(deriveFrame(defaultPlacement('yz'))).toEqual({ u: [0, 1, 0], v: [0, 0, 1], n: [1, 0, 0] })
    expect(deriveFrame(defaultPlacement('zx'))).toEqual({ u: [0, 0, 1], v: [1, 0, 0], n: [0, 1, 0] })
  })

  it('placementToWorld maps sketch mm through the derived frame', () => {
    expect(placementToWorld(defaultPlacement('zx'), 20, 0)).toEqual([0, 0, 20])
    const flipped = { ...defaultPlacement('xy'), normal_side: 'negative' as const }
    expect(placementToWorld(flipped, 0, 20).map((x) => x + 0)).toEqual([0, -20, 0])
  })

  it('the admission mirror refuses out-of-domain records', () => {
    expect(isPlacementRecord(P('xy', 'yz', 'right', 'positive'))).toBe(true)
    expect(isPlacementRecord(P('xy', 'xy', 'right', 'positive'))).toBe(false) // parallel
    expect(isPlacementRecord(P('xy', 'yz', 'diagonal', 'positive'))).toBe(false)
    expect(isPlacementRecord(P('xy', 'yz', 'right', 'up'))).toBe(false)
    expect(isPlacementRecord({ ...P('xy', 'yz', 'right', 'positive'), extra: 1 })).toBe(false)
    expect(isPlacementRecord(null)).toBe(false)
  })
})
