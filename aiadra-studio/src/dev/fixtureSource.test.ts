import { describe, expect, it } from 'vitest'
import { LEGACY_FIXTURE_DISPLAY_VERSION } from '../display/contract'
import { assertFixtureVersion, FixtureVersionError } from './fixtureSource'

/**
 * The fixture version gate (arc 20260610-1 P7): a contract bump without
 * fixture regeneration must fail LOUDLY at load — a stale fixture never
 * renders silently.
 */
describe('fixture version gate', () => {
  it('passes at the current contract version', () => {
    expect(() =>
      assertFixtureVersion({ display_representation_version: LEGACY_FIXTURE_DISPLAY_VERSION }),
    ).not.toThrow()
  })

  it('fails loudly on a stale fixture and says how to fix it', () => {
    expect(() => assertFixtureVersion({ display_representation_version: '1.0' })).toThrow(
      FixtureVersionError,
    )
    try {
      assertFixtureVersion({ display_representation_version: '1.0' })
    } catch (e) {
      const msg = (e as Error).message
      expect(msg).toContain('1.0')
      expect(msg).toContain(LEGACY_FIXTURE_DISPLAY_VERSION)
      expect(msg).toContain('gen-dev-fixtures')
    }
  })
})
