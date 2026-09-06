/**
 * The transient placement mirror vs the ENGINE's literal derivation matrix
 * (ADR/0044 A3.5). I3 (Codex1 N1): the TS side loads the SAME 48-row literal
 * file the engine's `TestDerivationMatrix` parametrizes over —
 * `aiadra-mechanical/tests/data/placement_matrix.jsonl` — so the mirror is
 * checked against independently pinned engine literals, never against a
 * second copy of itself. Plus the I3 adapters: the pre-commit session frame
 * and the view-direction glyph.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import {
  defaultPlacement,
  deriveFrame,
  isPlacementRecord,
  placementToPlaneFrame,
  placementToWorld,
  placementViewGlyph,
  type PlacementRecord,
} from './placementFrame'

const P = (support: string, ref: string, orientation: string, side: string): PlacementRecord =>
  ({
    support: { kind: 'principal', orientation: support },
    orientation_ref: { kind: 'principal', orientation: ref },
    orientation,
    normal_side: side,
  }) as PlacementRecord

type Row = [string, string, string, string, number[], number[], number[]]
const MATRIX_PATH = fileURLToPath(
  new URL('../../../aiadra-mechanical/tests/data/placement_matrix.jsonl', import.meta.url),
)
const MATRIX: Row[] = readFileSync(MATRIX_PATH, 'utf8')
  .split('\n')
  .filter((line) => line.trim().length > 0)
  .map((line) => JSON.parse(line) as Row)

const canon = (v: readonly number[]) => v.map((x) => x + 0) // −0 → +0

describe('the placement frame mirror (engine parity — the engine’s own literal matrix)', () => {
  it('the engine matrix is the full admitted domain: 3 supports × 2 refs × 4 orientations × 2 sides = 48', () => {
    expect(MATRIX).toHaveLength(48)
    const keys = new Set(MATRIX.map((r) => r.slice(0, 4).join('/')))
    expect(keys.size).toBe(48)
  })

  it.each(MATRIX)('%s/%s/%s/%s derives the engine axes', (s, r, o, side, u, v, n) => {
    const got = deriveFrame(P(s, r, o, side))
    expect(canon(got.u)).toEqual(canon(u))
    expect(canon(got.v)).toEqual(canon(v))
    expect(canon(got.n)).toEqual(canon(n))
  })

  it('the three defaults reproduce the legacy frames exactly', () => {
    expect(deriveFrame(defaultPlacement('xy'))).toEqual({ u: [1, 0, 0], v: [0, 1, 0], n: [0, 0, 1] })
    expect(deriveFrame(defaultPlacement('yz'))).toEqual({ u: [0, 1, 0], v: [0, 0, 1], n: [1, 0, 0] })
    expect(deriveFrame(defaultPlacement('zx'))).toEqual({ u: [0, 0, 1], v: [1, 0, 0], n: [0, 1, 0] })
  })

  it('placementToWorld maps sketch mm through the derived frame', () => {
    expect(placementToWorld(defaultPlacement('zx'), 20, 0)).toEqual([0, 0, 20])
    const flipped = { ...defaultPlacement('xy'), normal_side: 'negative' as const }
    expect(canon(placementToWorld(flipped, 0, 20))).toEqual([0, -20, 0])
  })

  it('the admission mirror refuses out-of-domain records', () => {
    expect(isPlacementRecord(P('xy', 'yz', 'right', 'positive'))).toBe(true)
    expect(isPlacementRecord(P('xy', 'xy', 'right', 'positive'))).toBe(false) // parallel
    expect(isPlacementRecord(P('xy', 'yz', 'diagonal', 'positive'))).toBe(false)
    expect(isPlacementRecord(P('xy', 'yz', 'right', 'up'))).toBe(false)
  })
})

describe('the I3 adapters over the mirror', () => {
  // The corrected acceptance scenario (Codex1 B2): TOP (xy) → Reference
  // FRONT (zx), Orientation Top, Flip on → u = −X, v = +Y, n = −Z.
  const scenario = P('xy', 'zx', 'top', 'negative')

  it('placementToPlaneFrame is the mirror frame at the world origin (the pre-commit session frame)', () => {
    const f = placementToPlaneFrame(scenario)
    expect(f.origin).toEqual([0, 0, 0])
    expect(canon(f.u)).toEqual([-1, 0, 0])
    expect(canon(f.v)).toEqual([0, 1, 0])
    expect(canon(f.normal)).toEqual([0, 0, -1])
    // and it is one of the engine's literal rows, not a fresh derivation
    const row = MATRIX.find((r) => r.slice(0, 4).join('/') === 'xy/zx/top/negative')
    expect(row).toBeDefined()
    expect(canon(f.u)).toEqual(canon(row![4]))
  })

  it('the view-direction glyph is the sketch view’s LOOK (−n) and reverses with Flip', () => {
    expect(canon(placementViewGlyph(scenario).direction)).toEqual([0, 0, 1])
    expect(canon(placementViewGlyph({ ...scenario, normal_side: 'positive' }).direction)).toEqual([0, 0, -1])
    expect(placementViewGlyph(scenario).origin).toEqual([0, 0, 0])
  })
})
