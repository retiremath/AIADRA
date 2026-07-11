import { describe, it, expect } from 'vitest'
import { hasCandidateFixture } from '../dev/fixtureSource'
import {
  BRACKET_CONFIGURATOR_ID,
  BRACKET_DEFAULT_PARAMS,
  BRACKET_ELICITATION,
  BRACKET_PARAMS,
  createBracketConfigurator,
  proposeBracketCandidates,
} from './brackets'

describe('bracket configurator', () => {
  it('exposes a canonical-unit parameter schema (no prompt-only units)', () => {
    for (const p of BRACKET_PARAMS) {
      expect(p.unit === 'mm' || p.unit === 'count').toBe(true)
      expect(p.min).toBeLessThan(p.max)
      expect(p.default).toBeGreaterThanOrEqual(p.min)
      expect(p.default).toBeLessThanOrEqual(p.max)
    }
    expect(BRACKET_DEFAULT_PARAMS.width_mm).toBe(80)
  })

  it('has a concept-owned elicitation schema (the pattern question)', () => {
    expect(BRACKET_ELICITATION).toHaveLength(1)
    expect(BRACKET_ELICITATION[0].id).toBe('pattern')
    expect(BRACKET_ELICITATION[0].options.map((o) => o.value)).toEqual(['corners', 'grid', 'inline'])
  })

  it('proposes all three real patterns by default (show diverse candidates)', () => {
    const cands = proposeBracketCandidates({}, BRACKET_DEFAULT_PARAMS)
    expect(cands.map((c) => c.id)).toEqual(['bracket-corners', 'bracket-grid', 'bracket-inline'])
    for (const c of cands) {
      expect(c.sourceId).toMatch(/^bracket\//) // stable source key (B2)
      expect(c.validationStatus).toBe('valid')
      expect(c.provenance).toEqual({ sourceConfigurator: BRACKET_CONFIGURATOR_ID, transient: true })
      expect(c.params.width_mm).toBe(80) // merges base params
      expect(typeof c.params.holeCount).toBe('number')
    }
  })

  it('moves the chosen pattern to the front without hiding alternatives', () => {
    const cands = proposeBracketCandidates({ pattern: 'grid' }, BRACKET_DEFAULT_PARAMS)
    expect(cands[0].id).toBe('bracket-grid')
    expect(cands).toHaveLength(3) // navigate, not filter — all stay
    expect(new Set(cands.map((c) => c.id))).toEqual(
      new Set(['bracket-corners', 'bracket-grid', 'bracket-inline']),
    )
  })

  it('merges refined params into every candidate', () => {
    const cands = proposeBracketCandidates({}, { ...BRACKET_DEFAULT_PARAMS, width_mm: 120 })
    expect(cands.every((c) => c.params.width_mm === 120)).toBe(true)
  })

  it('is deterministic — same inputs, same output', () => {
    const a = proposeBracketCandidates({ pattern: 'inline' }, BRACKET_DEFAULT_PARAMS)
    const b = proposeBracketCandidates({ pattern: 'inline' }, BRACKET_DEFAULT_PARAMS)
    expect(a).toEqual(b)
  })

  it('createBracketConfigurator() yields a drivable ActiveConfigurator', () => {
    const cfg = createBracketConfigurator()
    expect(cfg.id).toBe(BRACKET_CONFIGURATOR_ID)
    expect(cfg.defaultParams).toEqual(BRACKET_DEFAULT_PARAMS)
    expect(cfg.propose({}, cfg.defaultParams as Record<string, number>)).toHaveLength(3)
  })

  it('every candidate resolves to a DISTINCT baked fixture (Codex2 B1 identity cross-check)', () => {
    const cands = proposeBracketCandidates({}, BRACKET_DEFAULT_PARAMS)
    const sourceIds = cands.map((c) => c.sourceId)
    expect(new Set(sourceIds).size).toBe(cands.length) // sources are distinct
    for (const c of cands) expect(hasCandidateFixture(c.sourceId)).toBe(true) // and each is baked
  })
})
