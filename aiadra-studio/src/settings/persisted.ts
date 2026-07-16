/**
 * Persisted-settings envelope + the SHARED validator (arc 20260619-1 / 6a;
 * Codex1 B1). PURE module — no DOM, no Node, no three.js, zero imports — so it
 * is imported by BOTH the renderer registry and the Electron main process, and
 * main validates every blob before it touches the filesystem. Main owns the
 * path (a fixed `<userData>/settings.json`) AND the persisted shape: the
 * renderer is the untrusted side of the IPC boundary even when sandboxed.
 *
 * This validates the ENVELOPE only (version shape, allowed top-level keys, byte
 * cap, JSON-only values, depth/array limits, no prototype-pollution keys). It
 * does NOT validate individual setting semantics — that is the registry's
 * descriptor job, applied when values resolve into live state.
 */

export const CURRENT_SETTINGS_VERSION = 3

export type JSONValue =
  | string
  | number
  | boolean
  | null
  | JSONValue[]
  | { [k: string]: JSONValue }

export interface PersistedSettings {
  settings_version: number
  values: Record<string, JSONValue>
  /** Quarantined unknown keys, preserved for write-back only (Codex1 N2). */
  unknown?: Record<string, JSONValue>
}

export const MAX_SETTINGS_BYTES = 64 * 1024 // app prefs, not data
const MAX_DEPTH = 6
const MAX_ARRAY = 256
const UNSAFE_KEYS = new Set(['__proto__', 'prototype', 'constructor'])

export interface BlobCheck {
  ok: boolean
  error?: string
}

/** Thrown when a persisted blob declares a version newer than this build. */
export class SettingsVersionError extends Error {
  readonly found: number
  constructor(found: number) {
    super(
      `settings_version ${found} is newer than this build understands ` +
        `(${CURRENT_SETTINGS_VERSION}) — refusing to load`,
    )
    this.name = 'SettingsVersionError'
    this.found = found
  }
}

function checkJsonSafe(value: unknown, depth: number): string | null {
  if (depth > MAX_DEPTH) return `nesting exceeds ${MAX_DEPTH} levels`
  if (value === null) return null
  const t = typeof value
  if (t === 'string' || t === 'boolean') return null
  if (t === 'number') return Number.isFinite(value as number) ? null : 'non-finite number'
  if (Array.isArray(value)) {
    if (value.length > MAX_ARRAY) return `array exceeds ${MAX_ARRAY} entries`
    for (const v of value) {
      const e = checkJsonSafe(v, depth + 1)
      if (e) return e
    }
    return null
  }
  if (t === 'object') {
    // JSON-only: reject non-plain objects (Date / Map / class instances etc.).
    const proto = Object.getPrototypeOf(value)
    if (proto !== Object.prototype && proto !== null) return 'non-plain object'
    for (const k of Object.keys(value as object)) {
      if (UNSAFE_KEYS.has(k)) return `unsafe key ${k}`
      const e = checkJsonSafe((value as Record<string, unknown>)[k], depth + 1)
      if (e) return e
    }
    return null
  }
  return `unsupported value type ${t}`
}

/** Environment-agnostic UTF-8 byte count (no Buffer / TextEncoder dependency). */
function utf8Bytes(s: string): number {
  let n = 0
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i)
    if (c < 0x80) n += 1
    else if (c < 0x800) n += 2
    else if (c >= 0xd800 && c <= 0xdbff) {
      n += 4
      i++ // a surrogate pair is one code point = 4 UTF-8 bytes
    } else n += 3
  }
  return n
}

/**
 * Validate a persisted-settings blob (the B1 contract). Returns `{ok}` or
 * `{ok:false, error}`. Permissive on the version NUMBER (structure only) —
 * fail-loud-on-newer is migration's job (`migratePersisted`), so an older
 * version is a valid envelope here and gets migrated on load.
 */
export function validatePersistedSettingsBlob(blob: unknown): BlobCheck {
  if (typeof blob !== 'object' || blob === null || Array.isArray(blob)) {
    return { ok: false, error: 'settings blob must be a JSON object' }
  }
  const obj = blob as Record<string, unknown>
  for (const k of Object.keys(obj)) {
    if (k !== 'settings_version' && k !== 'values' && k !== 'unknown') {
      return { ok: false, error: `unexpected top-level key ${k}` }
    }
  }
  if (
    typeof obj.settings_version !== 'number' ||
    !Number.isInteger(obj.settings_version) ||
    obj.settings_version < 1
  ) {
    return { ok: false, error: 'settings_version must be a positive integer' }
  }
  if (typeof obj.values !== 'object' || obj.values === null || Array.isArray(obj.values)) {
    return { ok: false, error: 'values must be a JSON object' }
  }
  if (
    obj.unknown !== undefined &&
    (typeof obj.unknown !== 'object' || obj.unknown === null || Array.isArray(obj.unknown))
  ) {
    return { ok: false, error: 'unknown must be a JSON object when present' }
  }
  const safe =
    checkJsonSafe(obj.values, 1) ??
    (obj.unknown !== undefined ? checkJsonSafe(obj.unknown, 1) : null)
  if (safe) return { ok: false, error: safe }
  let serialized: string
  try {
    serialized = JSON.stringify(blob)
  } catch {
    return { ok: false, error: 'settings blob is not JSON-serializable' }
  }
  if (utf8Bytes(serialized) > MAX_SETTINGS_BYTES) {
    return { ok: false, error: `settings blob exceeds ${MAX_SETTINGS_BYTES} bytes` }
  }
  return { ok: true }
}

/**
 * SAVE-side validation (arc 20260619-1 Codex2 round 2). Load is deliberately
 * tolerant of an older version (it migrates) — but a SAVE must be strict: the
 * renderer always writes the CURRENT version, so main rejects any other version
 * BEFORE writing. Without this, a forward/corrupt `settings_version` could be
 * persisted and then brick the next boot (load → migrate fails-loud-on-newer →
 * defaults, silently losing the file's settings). Structural checks are shared.
 */
export function validatePersistedSettingsForSave(blob: unknown): BlobCheck {
  const structural = validatePersistedSettingsBlob(blob)
  if (!structural.ok) return structural
  const version = (blob as PersistedSettings).settings_version
  if (version !== CURRENT_SETTINGS_VERSION) {
    return {
      ok: false,
      error: `save requires settings_version ${CURRENT_SETTINGS_VERSION}, got ${version}`,
    }
  }
  return { ok: true }
}

/**
 * Migrate a (validated) blob to the current version. Fail-loud on a newer
 * version (`SettingsVersionError`). Ordered step chain.
 */
export function migratePersisted(blob: PersistedSettings): PersistedSettings {
  if (blob.settings_version > CURRENT_SETTINGS_VERSION) {
    throw new SettingsVersionError(blob.settings_version)
  }
  let out: PersistedSettings = { ...blob, values: { ...blob.values } }
  if (out.settings_version < 2) {
    // v1 -> v2 (arc 20260716-1 V grid closure, Codex1 B3): the empty-part
    // grid is REMOVED — the `gridVisibleDefault` key dies here so a stale
    // persisted `true` can never resurrect it. The future sketch mode mints
    // its OWN setting; it never inherits this key.
    delete out.values.gridVisibleDefault
  }
  if (out.settings_version < 3) {
    // v2 -> v3 (arc 20260716-1, Petre's empty-part round 2): the viewport
    // background default moves light-green -> neutral grey. The B2 rule: a
    // persisted value equal to the OLD built-in default is dropped (the new
    // default takes over); a REAL user override is preserved verbatim.
    const OLD_LIGHT_GREEN = 0xe4efdf
    for (const key of ['viewportBackground', 'paperBody'] as const) {
      if (out.values[key] === OLD_LIGHT_GREEN) delete out.values[key]
    }
  }
  out.settings_version = CURRENT_SETTINGS_VERSION
  return out
}
