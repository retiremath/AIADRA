import { describe, expect, it, vi } from 'vitest'
import { createSettingsRegistry } from './registry'
import { DEFAULT_VALUES } from './descriptors'
import type { PersistedSettings } from './persisted'

describe('settings registry', () => {
  it('starts at built-in defaults', () => {
    const r = createSettingsRegistry()
    expect(r.get('viewportBackground')).toBe(DEFAULT_VALUES.viewportBackground)
    expect(r.get('settleMs')).toBe(200)
    expect(r.get('defaultDisplayMode')).toBe('shading-edges')
  })

  it('set validates and stores; invalid throws (fail-loud, never coerce)', () => {
    const r = createSettingsRegistry()
    r.set('settleMs', 500)
    expect(r.get('settleMs')).toBe(500)
    expect(() => r.set('settleMs', -1)).toThrow()
    expect(() => r.set('settleMs', 9999)).toThrow()
    expect(() => r.set('viewportBackground', 0x1000000)).toThrow() // > 0xffffff
    expect(() => r.set('viewportBackground', 1.5)).toThrow() // non-integer color
    expect(() => r.set('nope', 1)).toThrow() // unknown key
    expect(() => r.set('defaultDisplayMode', 'bogus')).toThrow() // bad enum
    expect(() => r.set('paperBodyTracksBackground', 1)).toThrow() // non-boolean
  })

  it('reset / resetAll restore defaults', () => {
    const r = createSettingsRegistry()
    r.set('settleMs', 500)
    r.reset('settleMs')
    expect(r.get('settleMs')).toBe(200)
    r.set('settleMs', 500)
    r.set('paperBodyTracksBackground', false)
    r.resetAll()
    expect(r.get('settleMs')).toBe(200)
    expect(r.get('paperBodyTracksBackground')).toBe(true)
  })

  it('subscribe fires on change; onChange persists on set, NOT on hydrate', () => {
    const onChange = vi.fn()
    const r = createSettingsRegistry({ onChange })
    const sub = vi.fn()
    const unsub = r.subscribe(sub)
    r.set('settleMs', 300)
    expect(sub).toHaveBeenCalled()
    expect(onChange).toHaveBeenCalledTimes(1)

    onChange.mockClear()
    r.hydrate({ settings_version: 1, values: { settleMs: 400 } })
    expect(r.get('settleMs')).toBe(400)
    expect(onChange).not.toHaveBeenCalled() // hydrate came FROM disk — never re-persist

    unsub()
    sub.mockClear()
    r.set('settleMs', 500)
    expect(sub).not.toHaveBeenCalled()
  })

  it('theme() reflects live values', () => {
    const r = createSettingsRegistry()
    r.set('viewportBackground', 0x112233)
    expect(r.theme().viewportBackground).toBe(0x112233)
    expect(r.theme().paperBody).toBe(0x112233) // tracks background by default
  })

  it('hydrate: known-valid applies, known-invalid skipped, unknown quarantined (N2)', () => {
    const r = createSettingsRegistry()
    r.hydrate({
      settings_version: 1,
      values: { settleMs: 350, paperBodyTracksBackground: 'nope' as unknown as boolean, mystery: 7 },
    })
    expect(r.get('settleMs')).toBe(350) // known + valid → applied
    expect(r.get('paperBodyTracksBackground')).toBe(true) // known + invalid → default kept
    const persisted = r.toPersisted()
    expect(persisted.unknown).toEqual({ mystery: 7 }) // unknown → quarantined write-back bucket
    expect(persisted.values.mystery).toBeUndefined() // never surfaced into live values
  })

  it('hydrate fails loud on a newer settings_version', () => {
    const r = createSettingsRegistry()
    expect(() =>
      r.hydrate({ settings_version: 999, values: {} } as PersistedSettings),
    ).toThrow()
  })
})
