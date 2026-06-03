import Viewport from './Viewport'

/**
 * AIADRA Studio — bootstrap shell. Creo-style layout: a 3D viewport beside a
 * docked "Windchill" data panel (Product-Truth browser). Placeholder panel for
 * now; the viewport is live. STEP/STL import + real workspace wiring land next.
 */
export default function App() {
  return (
    <div className="studio">
      <header className="topbar">
        <span className="brand">AIADRA&nbsp;Studio</span>
        <span className="muted small">viewport bootstrap · arc 20260602-5</span>
      </header>
      <div className="workbench">
        <aside className="sidebar">
          <div className="panel-title">Model</div>
          <ul className="tree">
            <li>▾ BracketSpike <span className="muted small">P-000001</span></li>
            <li className="indent">feat_0001 · sketch</li>
            <li className="indent">feat_0002 · extrude · depth 8 mm</li>
            <li className="indent">geom_0001 · authoring_geometry</li>
          </ul>
          <div className="panel-title">Properties</div>
          <div className="muted small pad">
            Windchill-style Product-Truth panel — placeholder. Wires to the AIADRA
            workspace (sidecars + Vault) next.
          </div>
        </aside>
        <main className="viewport">
          <Viewport />
          <div className="hud muted small">drag = orbit · scroll = zoom · right-drag = pan</div>
        </main>
      </div>
    </div>
  )
}
