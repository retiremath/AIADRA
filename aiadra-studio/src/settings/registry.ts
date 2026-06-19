/**
 * The settings registry (arc 20260619-1 / 6a; ADR/0033 D8). Framework-agnostic
 * single source of truth: resolved value = built-in default ← persisted user
 * override. Validates on `set` (fail-loud, never coerce — Manifesto P5), and
 * notifies subscribers so the viewport re-applies the theme live.
 *
 * Unknown keys (Codex1 N2) are quarantined: known + valid persisted values
 * resolve into live state; unknown keys go into a write-back-only `unknown`
 * bucket — never surfaced through `get`, never reach `theme()`, preserved on
 * save so a downgrade/upgrade does not destroy a newer build's keys.
 */
import {
  DEFAULT_VALUES,
  DESCRIPTOR_BY_KEY,
  isKnownSetting,
  validateSettingValue,
  type SettingValue,
} from './descriptors'
import {
  CURRENT_SETTINGS_VERSION,
  migratePersisted,
  validatePersistedSettingsBlob,
  type JSONValue,
  type PersistedSettings,
} from './persisted'
import { themeFromValues, type Theme } from './theme'

export interface SettingsRegistry {
  get(key: string): SettingValue
  getAll(): Record<string, SettingValue>
  theme(): Theme
  /** Validate + set a known key. Throws on unknown key or invalid value. */
  set(key: string, value: SettingValue): void
  reset(key: string): void
  resetAll(): void
  /** Subscribe to any value change; returns an unsubscribe fn. */
  subscribe(fn: () => void): () => void
  /** The full persisted envelope (known values + the quarantined unknown bucket). */
  toPersisted(): PersistedSettings
  /** Merge a validated persisted blob into live state (load path; no re-persist). */
  hydrate(blob: PersistedSettings): void
}

export interface RegistryOptions {
  /** Called on every set/reset (NOT on hydrate) — the debounced persist hook. */
  onChange?: (blob: PersistedSettings) => void
}

export function createSettingsRegistry(opts: RegistryOptions = {}): SettingsRegistry {
  const values: Record<string, SettingValue> = { ...DEFAULT_VALUES }
  let unknown: Record<string, JSONValue> = {}
  const listeners = new Set<() => void>()

  const toPersisted = (): PersistedSettings => {
    const blob: PersistedSettings = {
      settings_version: CURRENT_SETTINGS_VERSION,
      values: { ...values },
    }
    if (Object.keys(unknown).length > 0) blob.unknown = { ...unknown }
    return blob
  }

  const notify = () => listeners.forEach((l) => l())
  const persist = () => opts.onChange?.(toPersisted())

  const get = (key: string): SettingValue => {
    if (!isKnownSetting(key)) throw new Error(`unknown setting ${key}`)
    return values[key]
  }

  const set = (key: string, value: SettingValue): void => {
    const d = DESCRIPTOR_BY_KEY[key]
    if (!d) throw new Error(`unknown setting ${key}`)
    const check = validateSettingValue(d, value)
    if (!check.ok) throw new Error(check.error)
    if (values[key] === value) return
    values[key] = value
    notify()
    persist()
  }

  const reset = (key: string): void => {
    if (!isKnownSetting(key)) throw new Error(`unknown setting ${key}`)
    if (values[key] === DEFAULT_VALUES[key]) return
    values[key] = DEFAULT_VALUES[key]
    notify()
    persist()
  }

  const resetAll = (): void => {
    for (const k of Object.keys(values)) values[k] = DEFAULT_VALUES[k]
    notify()
    persist()
  }

  const hydrate = (blob: PersistedSettings): void => {
    const check = validatePersistedSettingsBlob(blob)
    if (!check.ok) throw new Error(`cannot hydrate invalid settings blob: ${check.error}`)
    const migrated = migratePersisted(blob) // fail-loud on a newer version
    const nextUnknown: Record<string, JSONValue> = { ...(migrated.unknown ?? {}) }
    for (const [key, value] of Object.entries(migrated.values)) {
      const d = DESCRIPTOR_BY_KEY[key]
      if (!d) {
        nextUnknown[key] = value // quarantine (N2)
        continue
      }
      const vc = validateSettingValue(d, value)
      if (vc.ok) values[key] = value as SettingValue
      // known-but-invalid persisted value → keep the default (skip silently bad data)
    }
    unknown = nextUnknown
    notify() // refresh UI/viewport; NOT persist() — this came FROM disk
  }

  return {
    get,
    getAll: () => ({ ...values }),
    theme: () => themeFromValues(values),
    set,
    reset,
    resetAll,
    subscribe: (fn) => {
      listeners.add(fn)
      return () => listeners.delete(fn)
    },
    toPersisted,
    hydrate,
  }
}
