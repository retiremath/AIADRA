import { type MutableRefObject, useEffect, useRef, useState } from 'react'
import Viewport, { type ViewportApi } from './Viewport'
import { createBridgeSource } from './display/displaySource'
import { createImporter, type Importer } from './import/importController'
import { createImportSession, type ImportSession } from './import/importSession'
import { spawnImportWorker } from './import/defaultWorker'
import { ACCEPT_EXTENSIONS, ACCEPT_LABEL, STEP_ENABLED } from './import/importConfig'

/**
 * AIADRA Studio — desktop shell (arc 20260610-1: the canonical display lane is
 * live). Creo-style layout: a 3D viewport beside a docked "Windchill" data
 * panel. The Engine panel opens a Workspace, lists its Parts (Codex1 B1 —
 * `listParts` over the allowlisted bridge), and loads one into the viewport via
 * the Display Representation contract. The Reference Import panel is the
 * external inspection lane (ADR/0032 D5 lane 1) — never Product Truth.
 * In browser-only dev (`npm run dev:web`) there is no bridge: the engine panel
 * degrades gracefully and the viewport loads the engine-generated dev fixture
 * (clearly badged, dev builds only).
 */
type PartRow = { object_number: string; name: string; object_uuid: string }

function EnginePanel({ api }: { api: MutableRefObject<ViewportApi | null> }) {
  const [version, setVersion] = useState<string | null>(null)
  const [ws, setWs] = useState<{ name: string; workspaceId: string } | null>(null)
  const [parts, setParts] = useState<PartRow[]>([])
  const [loadedPart, setLoadedPart] = useState<string | null>(null)
  const [note, setNote] = useState('')

  useEffect(() => {
    if (!window.aiadra) {
      setNote('browser preview — no engine bridge (run as the desktop app)')
      return
    }
    window.aiadra.coreVersion().then((r) => {
      if (r.ok) setVersion(r.result.version)
      else setNote(`bridge error: ${r.error.message}`)
    })
  }, [])

  const loadPart = async (workspaceId: string, part: PartRow) => {
    try {
      await api.current?.setDisplaySource(createBridgeSource(workspaceId, part.object_number))
      setLoadedPart(part.object_number)
      setNote('')
    } catch (e) {
      setNote(e instanceof Error ? e.message : String(e))
    }
  }

  const open = async () => {
    if (!window.aiadra) return
    const r = await window.aiadra.chooseWorkspace()
    if (!r.ok) {
      if (r.error.message !== 'cancelled') setNote(r.error.message)
      return
    }
    setWs({ name: r.result.name, workspaceId: r.result.workspaceId })
    setParts([])
    setLoadedPart(null)
    setNote('')
    const list = await window.aiadra.listParts(r.result.workspaceId)
    if (!list.ok) {
      setNote(list.error.message)
      return
    }
    setParts(list.result.parts)
    if (list.result.parts.length === 1) {
      // Exactly one Part — load it without a pointless extra click.
      void loadPart(r.result.workspaceId, list.result.parts[0])
    }
  }

  return (
    <div className="engine">
      <div className="panel-title">Engine</div>
      <div className="small pad">
        {version ? (
          <span className="ok">● aiadra-core {version} · bridge connected</span>
        ) : (
          <span className="muted">{note || 'connecting…'}</span>
        )}
      </div>
      {window.aiadra && (
        <>
          <button className="btn" type="button" onClick={open}>
            Open Workspace…
          </button>
          {ws && <div className="small pad muted">workspace: {ws.name}</div>}
          {ws && version && note && <div className="small pad err">{note}</div>}
          {parts.length > 0 && (
            <ul className="tree">
              {parts.map((p) => (
                <li
                  key={p.object_uuid}
                  className={`part-row ${loadedPart === p.object_number ? 'on' : ''}`}
                  onClick={() => ws && loadPart(ws.workspaceId, p)}
                >
                  {p.name || p.object_number} <span className="muted small">{p.object_number}</span>
                </li>
              ))}
            </ul>
          )}
          {ws && parts.length === 0 && <div className="small pad muted">no Parts in this workspace</div>}
        </>
      )}
    </div>
  )
}

type ImportStatus = 'loading' | 'ready' | 'error'
type ImportItem = { id: string; name: string; status: ImportStatus; detail?: string }

function triangleCount(meshes: { position: Float32Array; index?: Uint32Array }[]): number {
  return meshes.reduce((n, m) => n + (m.index ? m.index.length / 3 : m.position.length / 9), 0)
}

/**
 * Reference Import panel — the external inspection lane. Bytes come from a
 * user-mediated file input (NO path crosses to main); parsing happens off-thread
 * in a Web Worker; the result is reference-only geometry with NO AIADRA id and
 * NO Product-Truth/engine operations. This panel never calls `window.aiadra`.
 */
function ImportPanel({ api }: { api: MutableRefObject<ViewportApi | null> }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const importerRef = useRef<Importer | null>(null)
  const sessionRef = useRef<ImportSession | null>(null)
  const seq = useRef(0)
  const [items, setItems] = useState<ImportItem[]>([])

  useEffect(() => () => importerRef.current?.dispose(), [])

  // The session governs add/remove so a row removed while still loading cannot
  // orphan geometry (Codex2 B3). `api.current` is read at call time (null-safe).
  const session = (): ImportSession => {
    if (!sessionRef.current) {
      sessionRef.current = createImportSession({
        addImported: (id, m) => api.current?.addImported(id, m),
        removeImported: (id) => api.current?.removeImported(id),
      })
    }
    return sessionRef.current
  }

  const patch = (id: string, next: Partial<ImportItem>) =>
    setItems((xs) => xs.map((it) => (it.id === id ? { ...it, ...next } : it)))

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = '' // allow re-importing the same file
    if (!file) return

    const lower = file.name.toLowerCase()
    if (!STEP_ENABLED && (lower.endsWith('.step') || lower.endsWith('.stp'))) {
      const id = `imp_${++seq.current}`
      setItems((xs) => [...xs, { id, name: file.name, status: 'error', detail: 'STEP import is deferred to a follow-up — STL only for now' }])
      return
    }

    const id = `imp_${++seq.current}`
    session().begin(id)
    setItems((xs) => [...xs, { id, name: file.name, status: 'loading' }])
    try {
      if (!importerRef.current) importerRef.current = createImporter({ workerFactory: spawnImportWorker })
      const meshes = await importerRef.current.import(file)
      if (session().complete(id, meshes)) {
        patch(id, { status: 'ready', detail: `${triangleCount(meshes).toLocaleString()} triangles` })
      }
      // else: removed while loading — the row is already gone, the result dropped.
    } catch (err) {
      session().settleError(id)
      patch(id, { status: 'error', detail: err instanceof Error ? err.message : String(err) })
    }
  }

  const remove = (id: string) => {
    session().remove(id) // tombstones an in-flight parse + drops any added group
    setItems((xs) => xs.filter((it) => it.id !== id))
  }

  return (
    <div className="import-panel">
      <div className="panel-title">Reference import</div>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT_EXTENSIONS}
        style={{ display: 'none' }}
        onChange={onFile}
      />
      <button className="btn" type="button" onClick={() => inputRef.current?.click()}>
        Import {ACCEPT_LABEL}…
      </button>
      <div className="muted small pad">External geometry — reference only, never Product Truth.</div>
      {items.length > 0 && (
        <ul className="tree import-list">
          {items.map((it) => (
            <li key={it.id} className="import-row">
              <div className="import-row-head">
                <span className="import-name" title={it.name}>{it.name}</span>
                <button className="link-btn small" type="button" onClick={() => remove(it.id)}>
                  Remove
                </button>
              </div>
              <span className="ref-badge small">Imported — reference only</span>
              <div className={`small ${it.status === 'error' ? 'err' : 'muted'}`}>
                {it.status === 'loading' ? 'parsing…' : it.detail}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function App() {
  const viewportApi = useRef<ViewportApi | null>(null)
  const [fixtureBadge, setFixtureBadge] = useState<string | null>(null)
  const [fixtureError, setFixtureError] = useState<string | null>(null)

  // Browser-dev fixture lane (arc 20260610-1 P7): engine-generated canned
  // display package, loaded ONLY when there is no bridge AND this is a dev
  // build. The dynamic import keeps the fixture data out of production bundles
  // (proven by scripts/assert-no-fixtures.mjs — Codex1 N2).
  useEffect(() => {
    if (!import.meta.env.DEV || window.aiadra) return
    let cancelled = false
    import('./dev/fixtureSource')
      .then(async ({ loadFixtureSource }) => {
        const src = await loadFixtureSource()
        if (!src || cancelled) return
        await viewportApi.current?.setDisplaySource(src)
        if (!cancelled) setFixtureBadge(src.badge)
      })
      .catch((e) => {
        if (!cancelled) setFixtureError(e instanceof Error ? e.message : String(e))
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="studio">
      <header className="topbar">
        <span className="brand">AIADRA&nbsp;Studio</span>
        <span className="muted small">display modes · arc 20260610-1</span>
        {fixtureBadge && <span className="ref-badge small">{fixtureBadge}</span>}
      </header>
      <div className="workbench">
        <aside className="sidebar">
          <EnginePanel api={viewportApi} />
          <ImportPanel api={viewportApi} />
          <div className="panel-title">Model</div>
          <div className="muted small pad">
            Model tree — placeholder; wires to real Workspace sidecars in the
            data-panel strand. Parts load from the Engine panel above.
          </div>
          {fixtureError && <div className="small pad err">{fixtureError}</div>}
          <div className="panel-title">Properties</div>
          <div className="muted small pad">
            Windchill-style Product-Truth panel — placeholder.
          </div>
        </aside>
        <main className="viewport">
          <Viewport apiRef={viewportApi} />
          <div className="hud muted small">middle = rotate · scroll = zoom · middle+shift = pan · middle+ctrl = zoom · left = select · right = menu</div>
        </main>
      </div>
    </div>
  )
}
