import { describe, expect, it } from 'vitest'
import {
  CURRENT_SETTINGS_VERSION,
  MAX_SETTINGS_BYTES,
  SettingsVersionError,
  migratePersisted,
  validatePersistedSettingsBlob,
  validatePersistedSettingsForSave,
  type PersistedSettings,
} from './persisted'

const valid = (): PersistedSettings => ({ settings_version: 1, values: { a: 1, b: true, c: 'x' } })

describe('persisted envelope validator (Codex1 B1)', () => {
  it('accepts a well-formed envelope', () => {
    expect(validatePersistedSettingsBlob(valid()).ok).toBe(true)
  })

  it('rejects non-objects', () => {
    expect(validatePersistedSettingsBlob(null).ok).toBe(false)
    expect(validatePersistedSettingsBlob([]).ok).toBe(false)
    expect(validatePersistedSettingsBlob(42).ok).toBe(false)
  })

  it('rejects an unexpected top-level key', () => {
    expect(validatePersistedSettingsBlob({ settings_version: 1, values: {}, extra: 1 }).ok).toBe(false)
  })

  it('rejects a bad version shape', () => {
    expect(validatePersistedSettingsBlob({ settings_version: 0, values: {} }).ok).toBe(false)
    expect(validatePersistedSettingsBlob({ settings_version: 1.5, values: {} }).ok).toBe(false)
    expect(validatePersistedSettingsBlob({ values: {} }).ok).toBe(false)
  })

  it('rejects values that is not an object', () => {
    expect(validatePersistedSettingsBlob({ settings_version: 1, values: [] }).ok).toBe(false)
  })

  it('rejects prototype-pollution keys', () => {
    const blob = JSON.parse('{"settings_version":1,"values":{"__proto__":1}}')
    expect(validatePersistedSettingsBlob(blob).ok).toBe(false)
  })

  it('rejects non-finite numbers', () => {
    expect(validatePersistedSettingsBlob({ settings_version: 1, values: { x: Infinity } }).ok).toBe(false)
  })

  it('rejects an oversized blob', () => {
    const big = { settings_version: 1, values: { big: 'x'.repeat(MAX_SETTINGS_BYTES + 10) } }
    expect(validatePersistedSettingsBlob(big).ok).toBe(false)
  })

  it('rejects nesting beyond the depth limit', () => {
    let deep: unknown = 0
    for (let i = 0; i < 8; i++) deep = { n: deep }
    expect(validatePersistedSettingsBlob({ settings_version: 1, values: { deep } }).ok).toBe(false)
  })

  it('rejects non-plain objects (JSON-only)', () => {
    expect(validatePersistedSettingsBlob({ settings_version: 1, values: { d: new Date() } }).ok).toBe(false)
  })
})

describe('save-side validator (Codex2 round 2)', () => {
  it('accepts the current version', () => {
    expect(validatePersistedSettingsForSave({ settings_version: CURRENT_SETTINGS_VERSION, values: {} }).ok).toBe(true)
  })

  it('rejects a forward/newer version BEFORE it can be written (the boot-brick bug)', () => {
    expect(validatePersistedSettingsForSave({ settings_version: 999, values: {} }).ok).toBe(false)
    expect(validatePersistedSettingsForSave({ settings_version: 4, values: {} }).ok).toBe(false)
  })

  it('still applies the shared structural rejections', () => {
    expect(validatePersistedSettingsForSave({ settings_version: 1, values: [] }).ok).toBe(false)
    expect(validatePersistedSettingsForSave(null).ok).toBe(false)
  })
})

describe('migration', () => {
  it('passes the current version through', () => {
    expect(migratePersisted(valid()).settings_version).toBe(CURRENT_SETTINGS_VERSION)
    // v1→v2 (grid closure): the dead grid key is dropped
    const v1 = migratePersisted({ settings_version: 1, values: { gridVisibleDefault: true, settleMs: 350 } })
    expect(v1.values.gridVisibleDefault).toBeUndefined()
    expect(v1.values.settleMs).toBe(350) // untouched neighbors survive
    // v2→v3 (grey background): old-default values yield to the new default…
    const v2 = migratePersisted({ settings_version: 2, values: { viewportBackground: 0xe4efdf, paperBody: 0xe4efdf } })
    expect(v2.values.viewportBackground).toBeUndefined()
    expect(v2.values.paperBody).toBeUndefined()
    // …while a REAL user override is preserved verbatim
    const custom = migratePersisted({ settings_version: 2, values: { viewportBackground: 0x123456 } })
    expect(custom.values.viewportBackground).toBe(0x123456)
  })

  it('fails loud on a newer version', () => {
    expect(() => migratePersisted({ settings_version: 999, values: {} })).toThrow(SettingsVersionError)
  })
})
