/**
 * The Home state (arc 20260714-1; D-H1/D-H2 — the Creo-paradigm startup).
 *
 * The no-model application state: NO viewport. Where Creo's home is folders,
 * AIADRA's is folders + the AI — the SAME `DesignHero` and `WorkspaceStart` /
 * `CatalogsStub` components the modeling dock hosts, rendered full-width
 * (Codex6 guardrail: one surface family, not a second AI mode).
 */
import { DesignHero } from '../dock/Dock'
import { NavigatorFrame } from '../ui/NavigatorFrame'
import { CatalogsStub, WorkspaceStart, type OpenedWorkspace } from './HomeShared'

export function HomeSurface({
  onOpened,
  onOpenSample,
  onDesignStart,
  onNewPart,
  startGate = null,
}: {
  onOpened: (ws: OpenedWorkspace) => Promise<string | null>
  onOpenSample?: () => void
  onDesignStart: () => void
  onNewPart: () => void
  /** Operation-start gate (Codex3 B1) — disables the hero/new entries. */
  startGate?: string | null
}) {
  return (
    <div className="home-surface">
      {/* Creo's navigator: the SAME resizable/dismissable frame the modeling
          state hosts its tree in (shell-1 S1-08/S1-15 — one navigator). */}
      <NavigatorFrame className="home-left">
        <div className="panel-title">Workspaces</div>
        <WorkspaceStart onOpened={onOpened} onOpenSample={onOpenSample} />
      </NavigatorFrame>
      <main className="home-main">
        <div className="home-hero">
          <DesignHero onStart={onDesignStart} gate={startGate} />
          <div className="home-or">
            <span className="muted small">…or model manually:</span>
            <button
              className="btn"
              type="button"
              disabled={!!startGate}
              title={startGate ?? 'Create a new object (Part, …)'}
              onClick={onNewPart}
            >
              New…
            </button>
          </div>
        </div>
        <div className="home-catalogs">
          <div className="panel-title">Catalogs &amp; KB</div>
          <CatalogsStub />
        </div>
      </main>
    </div>
  )
}
