/**
 * Import lifecycle session (Codex2 B3, arc 20260603-1).
 *
 * An import is async: the user can Remove a row while its parse is still in
 * flight. Without a guard, the later-resolving parse would call `addImported`
 * for a row that no longer exists — orphaned geometry with no tree node and no
 * Remove control. This session makes removal-during-loading deterministic:
 * removing an in-flight import TOMBSTONES its id, and `complete` drops the result
 * for any tombstoned id instead of adding it to the viewport.
 *
 * Pure + framework-agnostic so the race is unit-tested directly (no React/DOM).
 */
import type { ImportedMesh } from './normalize'

export type ViewportSink = {
  addImported: (id: string, meshes: ImportedMesh[]) => void
  removeImported: (id: string) => void
}

export type ImportSession = {
  /** Mark an import id as in-flight (parse started). */
  begin(id: string): void
  /** Parse resolved. Returns true if applied to the viewport, false if it was
   *  removed while loading (dropped — no orphan). */
  complete(id: string, meshes: ImportedMesh[]): boolean
  /** Parse failed/cancelled — clear lifecycle state for the id. */
  settleError(id: string): void
  /** User removed the row. Tombstones an in-flight parse so its late result is
   *  dropped; always tells the viewport to drop any already-added group. */
  remove(id: string): void
}

export function createImportSession(sink: ViewportSink): ImportSession {
  const inFlight = new Set<string>()
  const cancelled = new Set<string>()

  return {
    begin(id) {
      inFlight.add(id)
    },
    complete(id, meshes) {
      inFlight.delete(id)
      if (cancelled.delete(id)) return false // removed while loading → drop, no orphan
      sink.addImported(id, meshes)
      return true
    },
    settleError(id) {
      inFlight.delete(id)
      cancelled.delete(id)
    },
    remove(id) {
      if (inFlight.has(id)) cancelled.add(id) // tombstone the in-flight parse
      sink.removeImported(id) // no-op if no group was added yet
    },
  }
}
