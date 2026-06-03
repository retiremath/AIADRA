import { type MutableRefObject, useEffect, useRef, useState } from 'react'
import Viewport, { type ViewportApi } from './Viewport'
import { createImporter, type Importer } from './import/importController'
import { createImportSession, type ImportSession } from './import/importSession'
import { spawnImportWorker } from './import/defaultWorker'
import { ACCEPT_EXTENSIONS, ACCEPT_LABEL, STEP_ENABLED } from './import/importConfig'

/**
 * AIADRA Studio — desktop shell (milestone 1b). Creo-style layout: a 3D viewport
 * beside a docked "Windchill" data panel. The Engine panel proves the secure
 * renderer→main→Python bridge round-trip (ADR/0032 D6); the Reference Import
 * panel is the external inspection lane (ADR/0032 D5 lane 1) — drag/pick a STEP/STL
 * file, render it clearly marked "Imported — reference only", never Product Truth.
 * In browser-only dev (`npm run dev:web`) there is no bridge, so it degrades gracefully.
 */
function EnginePanel() {
  const [version, setVersion] = useState<string | null>(null)
  const [ws, setWs] = useState<{ name: string; workspaceId: string } | null>(null)
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

  const open = async () => {
    if (!window.aiadra) return
    const r = await window.aiadra.chooseWorkspace()
    if (r.ok) {
      setWs({ name: r.result.name, workspaceId: r.result.workspaceId })
      setNote('')
    } else if (r.error.message !== 'cancelled') {
      setNote(r.error.message)
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
  return (
    <div className="studio">
      <header className="topbar">
        <span className="brand">AIADRA&nbsp;Studio</span>
        <span className="muted small">milestone 1b · arc 20260603-1</span>
      </header>
      <div className="workbench">
        <aside className="sidebar">
          <EnginePanel />
          <ImportPanel api={viewportApi} />
          <div className="panel-title">Model</div>
          <ul className="tree">
            <li>▾ BracketSpike <span className="muted small">P-000001</span></li>
            <li className="indent">feat_0001 · sketch</li>
            <li className="indent">feat_0002 · extrude · depth 8 mm</li>
            <li className="indent">geom_0001 · authoring_geometry</li>
          </ul>
          <div className="panel-title">Properties</div>
          <div className="muted small pad">
            Windchill-style Product-Truth panel — placeholder. The model tree wires
            to real Workspace sidecars in milestone 2.
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
