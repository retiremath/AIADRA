import { describe, it, expect } from 'vitest'
import { invalidationAction, profileActivity, sketchRibbonActive } from './authoringActivity'

describe('profile activity is decidable at OPERATION ENTRY (Codex8 B1)', () => {
  it.each([
    ['a pick alone', true, { active: false, closing: false }],
    ['an open session', false, { active: true, closing: false }],
    ['an in-flight terminal', false, { active: true, closing: true }],
  ])('%s refuses a second authoring start immediately', (_l, pick, lane) => {
    // consumed as a render derivation into authoringBusy — no effect frame
    // in which New/navigation/AI/another start could slip through
    expect(profileActivity(pick, lane)).toBe(true)
  })

  it('an idle lane contributes nothing', () => {
    expect(profileActivity(false, { active: false, closing: false })).toBe(false)
  })
})

describe('generation invalidation vs the terminal (Codex8 B1)', () => {
  it('a pick dies with any generation change', () => {
    expect(invalidationAction(true, null, 8)).toBe('cancel-pick')
  })

  it('an open NON-closing draft on a dead generation cancels without writing', () => {
    expect(invalidationAction(false, { closing: false, targetGeneration: 7 }, 8))
      .toBe('cancel-session')
  })

  it('an IN-FLIGHT terminal is retained — busy survives until the backend settles', () => {
    // cancelling here could not cancel the transaction; it would only orphan
    // it and reopen the gate while the engine is still writing. The runner's
    // own generation check refuses stale display adoption when it settles
    // (proven in profileCloseRunner.test: stale-success adopts nothing).
    expect(invalidationAction(false, { closing: true, targetGeneration: 7 }, 8))
      .toBe('retain-terminal')
  })

  it('a current-generation session is untouched', () => {
    expect(invalidationAction(false, { closing: false, targetGeneration: 8 }, 8)).toBe('none')
    expect(invalidationAction(false, null, 8)).toBe('none')
  })
})

describe('ONE ribbon predicate for tab and body (Codex8 N1)', () => {
  it('a profile SESSION selects the Sketch surface', () => {
    expect(sketchRibbonActive('idle', { active: true })).toBe(true)
  })
  it('a profile PICK does not — it runs from the Model ribbon, like legacy planePick', () => {
    expect(sketchRibbonActive('idle', { active: false })).toBe(false)
  })
  it('the legacy sketch session still selects it', () => {
    expect(sketchRibbonActive('sketch', { active: false })).toBe(true)
  })
})
