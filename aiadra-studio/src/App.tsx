import { useEffect, useState } from 'react'
import Viewport from './Viewport'

/**
 * AIADRA Studio — desktop shell (milestone 1). Creo-style layout: a 3D viewport
 * beside a docked "Windchill" data panel. The Engine panel proves the secure
 * renderer→main→Python bridge round-trip (ADR/0032 D6). In browser-only dev
 * (`npm run dev:web`) there is no bridge, so it degrades gracefully.
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

export default function App() {
  return (
    <div className="studio">
      <header className="topbar">
        <span className="brand">AIADRA&nbsp;Studio</span>
        <span className="muted small">milestone 1 · arc 20260602-6</span>
      </header>
      <div className="workbench">
        <aside className="sidebar">
          <EnginePanel />
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
          <Viewport />
          <div className="hud muted small">middle = rotate · scroll = zoom · middle+shift = pan · middle+ctrl = zoom · left = select · right = menu</div>
        </main>
      </div>
    </div>
  )
}
