/**
 * Shared Home-surface components (arc 20260714-1; ADR/0040 D5 realized).
 *
 * ONE component family rendered in BOTH places (Codex6 guardrail): the full-
 * width Home state at startup AND the dock's Home/Catalogs tabs in modeling —
 * never two disconnected surfaces.
 *
 * `WorkspaceStart` is Creo's "Common Folders / Recent" analog: Open Workspace…
 * (the native-dialog grant), the durable recents (D-H4 as repinned — views
 * only, reopen = a renewed grant re-validated by main + a FRESH workspaceId),
 * and the dev-lane sample part. No path ever reaches this component.
 */
import { useEffect, useState } from 'react'

export interface OpenedWorkspace {
  workspaceId: string
  name: string
}

type RecentView = { recentId: string; name: string; lastOpened: string }

function shortDate(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString()
}

export function WorkspaceStart({
  onOpened,
  onOpenSample,
  gate = null,
  refreshKey = '',
}: {
  /** The central adoption (Codex2 B3) — resolves the refusal reason, or null
   *  when adopted; a refused fresh capability is retired by the switcher. */
  onOpened: (ws: OpenedWorkspace) => Promise<string | null>
  /** Present only in the dev:web lane — opens the badged engine sample part. */
  onOpenSample?: () => void
  /** The central switch-gate reason while an operation is active (Codex1 B1) —
   *  open/reopen are visibly disabled with it; remove/clear stay available. */
  gate?: string | null
  /** Bump to re-fetch recents (e.g. after a workspace opened via ANY surface). */
  refreshKey?: string
}) {
  const bridged = !!window.aiadra
  const [recents, setRecents] = useState<RecentView[]>([])
  const [note, setNote] = useState<string | null>(null)

  useEffect(() => {
    if (!bridged || !window.aiadra?.recentsList) return
    window.aiadra
      .recentsList()
      .then((r) => {
        if (r.ok) setRecents(r.result.recents)
      })
      .catch(() => {})
  }, [bridged, refreshKey])

  const open = async () => {
    if (!window.aiadra || gate) return
    setNote(null)
    const r = await window.aiadra.chooseWorkspace()
    if (!r.ok) {
      if (r.error.message !== 'cancelled') setNote(r.error.message)
      return
    }
    const reason = await onOpened(r.result)
    if (reason !== null) setNote(reason) // refused — the fresh capability was retired
  }

  const reopen = async (recentId: string) => {
    if (!window.aiadra?.reopenWorkspace || gate) return
    setNote(null)
    const r = await window.aiadra.reopenWorkspace(recentId)
    if (!r.ok) {
      // The entry stays — removable in place, never silently dropped (D-H4).
      setNote(r.error.message)
      return
    }
    const reason = await onOpened(r.result)
    if (reason !== null) setNote(reason)
  }

  const remove = async (recentId: string) => {
    if (!window.aiadra?.recentsRemove) return
    const r = await window.aiadra.recentsRemove(recentId)
    if (r.ok) setRecents(r.result.recents)
  }

  const clearAll = async () => {
    if (!window.aiadra?.recentsClear) return
    const r = await window.aiadra.recentsClear()
    if (r.ok) setRecents([])
  }

  return (
    <div className="ws-start">
      <button
        className="btn"
        type="button"
        onClick={open}
        disabled={!bridged || !!gate}
        title={
          !bridged ? 'Available in the desktop app' : (gate ?? 'Open an AIADRA workspace folder')
        }
      >
        Open Workspace…
      </button>
      {note && <div className="small err pad">{note}</div>}

      {bridged && recents.length > 0 && (
        <>
          <div className="panel-title">Recent</div>
          <ul className="tree recents">
            {recents.map((r) => (
              <li key={r.recentId} className="recent-row">
                <button
                  type="button"
                  className="recent-open"
                  disabled={!!gate}
                  title={gate ?? `Reopen ${r.name} (re-validated on open)`}
                  onClick={() => reopen(r.recentId)}
                >
                  {r.name} <span className="muted small">{shortDate(r.lastOpened)}</span>
                </button>
                <button
                  type="button"
                  className="link-btn small"
                  title="Remove from recents"
                  onClick={() => remove(r.recentId)}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
          <button className="link-btn small" type="button" onClick={clearAll}>
            Clear all
          </button>
        </>
      )}
      {bridged && recents.length === 0 && (
        <div className="muted small pad">No recent workspaces yet.</div>
      )}

      {onOpenSample && (
        <>
          <div className="panel-title">Dev lane</div>
          <button className="btn small" type="button" onClick={onOpenSample}>
            Open sample part
          </button>
          <div className="muted small pad">Engine-baked fixture — not Product Truth.</div>
        </>
      )}
    </div>
  )
}

/** Catalogs & KB — local-first browsing (ADR/0040 D5 N3). Stub until the KB
 *  browser slice; the SAME component in the Home state and the dock tab. */
export function CatalogsStub() {
  return (
    <div className="muted small pad">
      Catalogs &amp; KB — browse the project KB, core KB, and local catalogs (local-first; a
      configurator library arrives as the vocabulary grows).
    </div>
  )
}
