/**
 * Settings persistence (arc 20260619-1 / 6a). Loads/saves the persisted
 * envelope through the right backend for the runtime, with debounced,
 * coalesced writes (a slider drag is one write, not a hundred):
 *
 *  - **Electron desktop:** `window.aiadra.loadSettings/saveSettings` → main
 *    reads/writes the one fixed `<userData>/settings.json` (main owns path AND
 *    validates the shape — Codex1 B1). Settings never touch the Python engine
 *    bridge and are never Product Truth.
 *  - **Browser dev (`npm run dev:web`):** `localStorage`.
 *  - **Neither (node tests):** in-memory.
 *
 * The backend + scheduler are injectable so the debounce + round-trip are
 * testable headlessly (mirrors `settle.ts`).
 */
import { validatePersistedSettingsBlob, type PersistedSettings } from './persisted'

export interface SettingsBackend {
  load(): Promise<PersistedSettings | null>
  save(blob: PersistedSettings): Promise<void>
}

export interface Persistence {
  load(): Promise<PersistedSettings | null>
  /** Debounced, fire-and-forget save (coalesces a burst into one write). */
  save(blob: PersistedSettings): void
  /** Force any pending debounced write to run now (for shutdown/tests). */
  flush(): Promise<void>
  dispose(): void
}

const LS_KEY = 'aiadra.studio.settings'

/** The Electron backend over the allowlisted bridge (main owns the file). */
function electronBackend(): SettingsBackend | null {
  const api = typeof window !== 'undefined' ? window.aiadra : undefined
  if (!api?.loadSettings || !api.saveSettings) return null
  return {
    async load() {
      const r = await api.loadSettings!()
      if (!r.ok) return null
      const blob = r.result.settings
      if (!blob) return null
      // Defense in depth: validate even what main returned.
      return validatePersistedSettingsBlob(blob).ok ? (blob as PersistedSettings) : null
    },
    async save(blob) {
      await api.saveSettings!(blob)
    },
  }
}

function localStorageBackend(): SettingsBackend | null {
  if (typeof localStorage === 'undefined') return null
  return {
    async load() {
      const raw = localStorage.getItem(LS_KEY)
      if (!raw) return null
      try {
        const blob = JSON.parse(raw)
        return validatePersistedSettingsBlob(blob).ok ? (blob as PersistedSettings) : null
      } catch {
        return null
      }
    },
    async save(blob) {
      localStorage.setItem(LS_KEY, JSON.stringify(blob))
    },
  }
}

function memoryBackend(): SettingsBackend {
  let held: PersistedSettings | null = null
  return {
    async load() {
      return held
    },
    async save(blob) {
      held = blob
    },
  }
}

export function resolveBackend(): SettingsBackend {
  return electronBackend() ?? localStorageBackend() ?? memoryBackend()
}

export interface PersistenceOptions {
  backend?: SettingsBackend
  debounceMs?: number
  /** Injectable timer (test seam). Returns a cancel fn. */
  schedule?: (fn: () => void, ms: number) => () => void
}

export function createPersistence(opts: PersistenceOptions = {}): Persistence {
  const backend = opts.backend ?? resolveBackend()
  const debounceMs = opts.debounceMs ?? 300
  const schedule =
    opts.schedule ??
    ((fn, ms) => {
      const t = setTimeout(fn, ms)
      return () => clearTimeout(t)
    })

  let cancel: (() => void) | null = null
  let pending: PersistedSettings | null = null

  const writeNow = async () => {
    cancel = null
    const blob = pending
    pending = null
    if (blob) await backend.save(blob)
  }

  return {
    load: () => backend.load(),
    save(blob) {
      pending = blob
      if (cancel) cancel()
      cancel = schedule(() => void writeNow(), debounceMs)
    },
    async flush() {
      if (cancel) {
        cancel()
        await writeNow()
      }
    },
    dispose() {
      if (cancel) cancel()
      cancel = null
      pending = null
    },
  }
}
