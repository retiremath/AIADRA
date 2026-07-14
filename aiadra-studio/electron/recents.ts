/**
 * The durable recent-workspaces registry (arc 20260714-1; D-H4 as repinned in
 * arc 20260711-11 Claude10 §2 per Codex6 B3).
 *
 * MAIN-owned, ONE store: entries `{recentId, name, canonicalPath, lastOpened}`
 * persist in a bounded LRU JSON file under `userData` — never in renderer
 * settings, never a session `workspaceId`. The renderer sees only the stripped
 * `{recentId, name, lastOpened}` view (no path ever crosses — ADR/0032 D6 /
 * ADR/0043 D1). Reopening is a RENEWED USER GRANT handled by the caller
 * (main.ts): re-resolve + re-validate the `.aiadra` marker, then mint a FRESH
 * session `workspaceId`; this module only stores/looks up locators.
 *
 * Load-tolerant: recents are convenience, never truth — a corrupt/unknown file
 * yields an empty registry (and is overwritten on the next save).
 *
 * Pure + injectable (the appProtocol pattern) so the LRU/dedupe/bound/strip
 * logic is unit-tested in node without Electron.
 */

export interface RecentEntry {
  recentId: string
  name: string
  canonicalPath: string
  lastOpened: string // ISO8601
}

/** What the renderer is allowed to see — NO canonicalPath. */
export interface RecentView {
  recentId: string
  name: string
  lastOpened: string
}

export const RECENTS_LIMIT = 10
const FILE_VERSION = 1

export interface RecentsIo {
  /** Raw file contents, or null when absent/unreadable. */
  load(): string | null
  save(contents: string): void
  now(): string
  mintId(): string
}

export interface RecentsRegistry {
  /** Renderer-facing views, most recent first. */
  views(): RecentView[]
  /** Full entry lookup (main-side only — carries the path). */
  get(recentId: string): RecentEntry | null
  /** Record a successful open: dedupe by canonicalPath, bump LRU, cap the list. */
  record(canonicalPath: string, name: string): RecentEntry
  remove(recentId: string): void
  clear(): void
}

export function createRecentsRegistry(io: RecentsIo): RecentsRegistry {
  let entries: RecentEntry[] = loadTolerant(io)

  const persist = () => {
    io.save(JSON.stringify({ version: FILE_VERSION, entries }, null, 2))
  }

  return {
    views: () =>
      entries.map(({ recentId, name, lastOpened }) => ({ recentId, name, lastOpened })),
    get: (recentId) => entries.find((e) => e.recentId === recentId) ?? null,
    record: (canonicalPath, name) => {
      const existing = entries.find((e) => e.canonicalPath === canonicalPath)
      const entry: RecentEntry = {
        recentId: existing?.recentId ?? io.mintId(),
        name,
        canonicalPath,
        lastOpened: io.now(),
      }
      entries = [entry, ...entries.filter((e) => e.recentId !== entry.recentId)].slice(
        0,
        RECENTS_LIMIT,
      )
      persist()
      return entry
    },
    remove: (recentId) => {
      entries = entries.filter((e) => e.recentId !== recentId)
      persist()
    },
    clear: () => {
      entries = []
      persist()
    },
  }
}

function loadTolerant(io: RecentsIo): RecentEntry[] {
  const raw = io.load()
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw) as { version?: unknown; entries?: unknown }
    if (parsed.version !== FILE_VERSION || !Array.isArray(parsed.entries)) return []
    return parsed.entries.filter(
      (e): e is RecentEntry =>
        !!e &&
        typeof (e as RecentEntry).recentId === 'string' &&
        typeof (e as RecentEntry).name === 'string' &&
        typeof (e as RecentEntry).canonicalPath === 'string' &&
        typeof (e as RecentEntry).lastOpened === 'string',
    )
  } catch {
    return []
  }
}
