import { type MutableRefObject, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Viewport, { type ViewportApi } from './Viewport'
import { Toolbar } from './Toolbar'
import { createBridgeSource } from './display/displaySource'
import { createOperationStore, useOperation, type OperationStore } from './operation/store'
import { useCandidatePreview } from './operation/previewController'
import { SessionPill } from './operation/SessionPill'
import { Dock, startBracketSession } from './dock/Dock'
import { HomeSurface } from './home/HomeSurface'
import { HomeRibbon } from './home/HomeRibbon'
import { FileMenu, type FileMenuItem } from './home/FileMenu'
import { NewDialog, type NewObjectChoice } from './home/NewDialog'
import { WorkspaceStart, type OpenedWorkspace } from './home/HomeShared'
import { createFeatureSessionStore, useFeatureSession, type FeatureSessionStore } from './authoring/featureSession'
import { FeatureDashboard, EXTRUDE_DEFAULTS } from './authoring/FeatureDashboard'
import { ModelRibbon } from './authoring/ModelRibbon'
import { createMockAuthoringBackend } from './authoring/backendMock'
import { createBridgeAuthoringBackend } from './authoring/backendBridge'
import { chooseBackendLane, createUnavailableBackend, type AuthoringBackend } from './authoring/backend'
import { createWorkspaceSwitcher, isCloseAcked } from './workspace/switcher'
import { createSketchStore, useSketch, type SketchStore } from './sketch/sketchStore'
import { SketchPad } from './sketch/SketchPad'
import { createImporter, type Importer } from './import/importController'
import { createImportSession, type ImportSession } from './import/importSession'
import { spawnImportWorker } from './import/defaultWorker'
import { ACCEPT_EXTENSIONS, ACCEPT_LABEL, STEP_ENABLED } from './import/importConfig'
import type { DisplayMode } from './display/modes'
import { SettingsProvider, useRegistry, useSetting, useTheme } from './settings/useSettings'
import { createSettingsRegistry, type SettingsRegistry } from './settings/registry'
import { createPersistence, type Persistence } from './settings/persistence'
import { SETTING_DESCRIPTORS, type SettingDescriptor, type SettingValue } from './settings/descriptors'
import { createViewStateStore, toCommandContext, type ViewStateStore } from './viewstate/store'
import { createSelectionStore, type SelectionStore } from './selection/store'
import { dispatchShortcut, normalizeChord } from './commands/registry'
import type { CommandActions } from './commands/types'

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

function EnginePanel({
  api,
  ws,
  onOpen,
  gate,
}: {
  api: MutableRefObject<ViewportApi | null>
  /** The ONE Workbench-owned current workspace (Codex1 B1) — this panel is a
   *  projection of it, never a second owner. */
  ws: OpenedWorkspace | null
  /** Route an open through the central gated transition (Codex2 B3 — resolves
   *  the refusal reason, or null when adopted). */
  onOpen: (ws: OpenedWorkspace) => Promise<string | null>
  /** Human-readable switch-gate reason while an operation is active, else null. */
  gate: string | null
}) {
  const [version, setVersion] = useState<string | null>(null)
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

  // Projection (Codex1 B1): adopt EVERY current-workspace change — including a
  // mid-modeling A→B switch from any surface — never only the first. The old
  // parts list is cleared before the new listing (the central transition
  // already cleared the display before applying).
  useEffect(() => {
    setParts([])
    setLoadedPart(null)
    setNote('')
    if (!ws || !window.aiadra) return
    let cancelled = false
    window.aiadra
      .listParts(ws.workspaceId)
      .then((list) => {
        if (cancelled) return
        if (!list.ok) {
          setNote(list.error.message)
          return
        }
        setParts(list.result.parts)
        if (list.result.parts.length === 1) {
          // Exactly one Part — load it without a pointless extra click.
          void loadPart(ws.workspaceId, list.result.parts[0])
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ws?.workspaceId])

  const open = async () => {
    if (!window.aiadra) return
    const r = await window.aiadra.chooseWorkspace()
    if (!r.ok) {
      if (r.error.message !== 'cancelled') setNote(r.error.message)
      return
    }
    // ONE central gated transition (Codex1 B1 / Codex2 B3) — surface a refusal.
    const reason = await onOpen(r.result)
    if (reason !== null) setNote(reason)
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
          <button
            className="btn"
            type="button"
            onClick={open}
            disabled={!!gate}
            title={gate ?? 'Open an AIADRA workspace folder'}
          >
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

// ---- Appearance / Behavior panel (arc 20260619-1 / 6a; ADR/0033 D8) ----
// The registry's UI binding (the sidebar panel Codex1 N5 preferred). Each
// descriptor renders by type; changes go through the registry (validate-loud)
// and re-apply live + persist (debounced). The full toolbar/command chrome is
// the next slice (6b).

const toHex = (n: number) => '#' + (n & 0xffffff).toString(16).padStart(6, '0')
const fromHex = (s: string) => parseInt(s.slice(1), 16)
const rowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 8,
  padding: '2px 8px',
}

function SettingRow({ descriptor }: { descriptor: SettingDescriptor }) {
  const [value, setValue] = useSetting(descriptor.key)
  const safeSet = (v: SettingValue) => {
    try {
      setValue(v)
    } catch (e) {
      console.warn('[settings]', e instanceof Error ? e.message : e)
    }
  }
  const label = descriptor.label + (descriptor.unit ? ` (${descriptor.unit})` : '')
  return (
    <label style={rowStyle} className="small" title={descriptor.help}>
      <span className="muted">{label}</span>
      {descriptor.type === 'color' && (
        <input
          type="color"
          value={toHex(value as number)}
          onChange={(e) => safeSet(fromHex(e.target.value))}
        />
      )}
      {descriptor.type === 'number' && (
        <input
          type="number"
          value={value as number}
          min={descriptor.min}
          max={descriptor.max}
          step={descriptor.step}
          style={{ width: 72 }}
          onChange={(e) => {
            const n = Number(e.target.value)
            if (Number.isFinite(n)) safeSet(n)
          }}
        />
      )}
      {descriptor.type === 'boolean' && (
        <input type="checkbox" checked={value as boolean} onChange={(e) => safeSet(e.target.checked)} />
      )}
      {descriptor.type === 'enum' && (
        <select value={value as string} onChange={(e) => safeSet(e.target.value)}>
          {descriptor.options!.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      )}
    </label>
  )
}

function AppearancePanel() {
  const registry = useRegistry()
  const [open, setOpen] = useState(false)
  const groups: { group: SettingDescriptor['group']; title: string }[] = [
    { group: 'Theme', title: 'Appearance' },
    { group: 'Behavior', title: 'Behavior' },
  ]
  return (
    <>
      <div className="panel-title" style={{ cursor: 'pointer' }} onClick={() => setOpen((o) => !o)}>
        Appearance {open ? '▾' : '▸'}
      </div>
      {open && (
        <>
          {groups.map(({ group, title }) => (
            <div key={group}>
              <div className="muted small pad">{title}</div>
              {SETTING_DESCRIPTORS.filter((d) => d.group === group).map((d) => (
                <SettingRow key={d.key} descriptor={d} />
              ))}
            </div>
          ))}
          <div className="pad">
            <button className="btn small" type="button" onClick={() => registry.resetAll()}>
              Reset to defaults
            </button>
          </div>
        </>
      )}
    </>
  )
}

// ---- Model tree (arc 20260711-11 / slice A — the Creo-shaped shell) ----
// For now it reflects the ACTIVE feature op; the persistent per-Part feature
// list arrives with the stepwise Sketch→Extrude flow (slice B).
function ModelTreePanel({ store }: { store: FeatureSessionStore }) {
  const s = useFeatureSession(store)
  const kindLabel = s.featureKind ? s.featureKind[0].toUpperCase() + s.featureKind.slice(1) : null
  return (
    <ul className="tree model-tree">
      {!s.active && (
        <li className="muted small">No features yet — start with Extrude in the Model ribbon.</li>
      )}
      {s.active && (
        <li className={`feat-row ${s.phase}`}>
          <span className="feat-glyph">{s.phase === 'committed' ? '▸' : '◐'}</span>
          <span className="feat-name">{kindLabel}</span>
          <span className="muted small feat-state">
            {s.phase === 'committed' ? (s.objectRef ?? 'committed') : s.phase === 'busy' ? '…' : 'editing'}
          </span>
        </li>
      )}
    </ul>
  )
}

function Workbench({
  ready,
  viewportApi,
  viewStore,
  selectionStore,
  operationStore,
  featureStore,
  sketchStore,
}: {
  ready: boolean
  viewportApi: MutableRefObject<ViewportApi | null>
  viewStore: ViewStateStore
  selectionStore: SelectionStore
  operationStore: OperationStore
  featureStore: FeatureSessionStore
  sketchStore: SketchStore
}) {
  const registry = useRegistry()
  const theme = useTheme()
  // Authoring dispatch (arc 20260711-11): the Model ribbon starts either the
  // sketch pad (draw a contour) or the extrude feature session. One at a time.
  const featureActive = useFeatureSession(featureStore).active
  const sketchActive = useSketch(sketchStore).active
  const authoringBusy = featureActive || sketchActive

  // ---- The two application states (arc 20260714-1; D-H1 — the Creo paradigm).
  // `home` at boot: NO viewport, the Home surface (workspace browser + recents
  // + the AI entry). `modeling` once a Part/workspace/sample is opened; File →
  // Close returns Home. One state at a time.
  const [appSession, setAppSession] = useState<'home' | 'modeling'>('home')
  const opActive = useOperation(operationStore).phase !== 'idle'
  // The dev-lane sample part (D-H5): loaded only on the explicit Home entry —
  // never an ambush at boot. `sampleRef` remembers it for restoreBase.
  const sampleRef = useRef(false)
  const [sampleWanted, setSampleWanted] = useState(false)
  const [fixtureBadge, setFixtureBadge] = useState<string | null>(null)
  const [fixtureError, setFixtureError] = useState<string | null>(null)

  // ---- ONE current-workspace owner + ONE gated atomic transition (Codex1 B1).
  // Every surface (Home browser, recents, File, dock Home tab, EnginePanel
  // Open) routes through `switchWorkspace`; the gate refuses while an authoring
  // op or operation session is active; the old context clears BEFORE the new
  // backend is exposed; the previous main-side capability is retired.
  const [currentWs, setCurrentWs] = useState<OpenedWorkspace | null>(null)
  // Transient shell-level transition feedback (Codex2 B3 — refused adoptions
  // from surfaces without their own note UI surface here, in the statusbar).
  const [shellNote, setShellNote] = useState<string | null>(null)
  // Codex3 B1: the transition state is PUBLISHED and joins every operation-
  // start gate — an op must not start against A while A→B awaits retirement.
  const [wsTransition, setWsTransition] = useState(false)
  const switchGate =
    authoringBusy || opActive ? 'Finish or cancel the active operation first' : null
  const gateRef = useRef<string | null>(null)
  gateRef.current = switchGate
  const switcher = useMemo(
    () =>
      createWorkspaceSwitcher({
        // The OPERATION gate only — the switcher owns the transition state.
        isBlocked: () => gateRef.current,
        clearContext: () => {
          void viewportApi.current?.setDisplaySource(null)
          selectionStore.clearSelected()
          setFixtureBadge(null)
          sampleRef.current = false
        },
        // Codex2 B3 + Codex3 B1: retirement is AWAITED and only counts on the
        // TYPED acknowledgement (ok && result.closed === true).
        releaseWorkspace: async (id) => {
          if (!window.aiadra) return true // no bridge — no main-side capability exists
          if (!window.aiadra.closeWorkspace) return false
          try {
            return isCloseAcked(await window.aiadra.closeWorkspace(id))
          } catch {
            return false
          }
        },
        apply: (ws) => setCurrentWs(ws),
        onTransition: (active) => setWsTransition(active),
      }),
    [selectionStore, viewportApi],
  )
  // The COMBINED gate for every operation start + open/close control (Codex3
  // B1): active work OR an in-flight workspace transition.
  const uiGate = switchGate ?? (wsTransition ? 'A workspace transition is in flight' : null)
  // Authoring dispatch — gated on the COMBINED gate (Codex3 B1): no op may
  // start while a workspace transition owns the shell.
  const onStartFeature = (kind: string) => {
    if (uiGate) return
    if (kind === 'sketch') sketchStore.start()
    else if (kind === 'extrude') featureStore.start('extrude', EXTRUDE_DEFAULTS)
  }
  /** The ONE adoption path — returns the refusal reason (null = adopted). */
  const switchWorkspace = async (ws: OpenedWorkspace): Promise<string | null> => {
    setShellNote(null)
    const reason = await switcher.adopt(ws)
    if (reason === null) setAppSession('modeling')
    return reason
  }
  const closeToHome = async () => {
    setShellNote(null)
    const reason = await switcher.close()
    if (reason !== null) {
      setShellNote(reason)
      return
    }
    setAppSession('home')
  }

  // ONE generic "New" (Petre's steer — Creo's New pattern): a dialog picks the
  // Type/Sub-type/Number/Name; OK runs the REAL Part path (Codex1 B2): the
  // desktop obtains a live workspace capability first (the native-dialog
  // grant), then enters modeling and starts the promised sketch. The metadata
  // is installed on the SKETCH SESSION only after the grant + transition
  // succeed, and dies with that session (Codex2 B1 — never ambient state).
  const [newDialogOpen, setNewDialogOpen] = useState(false)
  const requestNew = () => {
    if (!uiGate) setNewDialogOpen(true)
  }
  const createNew = async (choice: NewObjectChoice) => {
    setNewDialogOpen(false)
    setShellNote(null)
    if (uiGate) return // Codex3 B1: incl. an in-flight workspace transition
    if (window.aiadra && !switcher.current()) {
      const r = await window.aiadra.chooseWorkspace()
      if (!r.ok) return // chooser cancelled/failed — nothing installed anywhere
      const reason = await switcher.adopt(r.result)
      if (reason !== null) {
        setShellNote(reason) // the fresh capability was retired by the switcher
        return
      }
    }
    setAppSession('modeling')
    sketchStore.start({ partName: choice.name, partNumber: choice.number })
  }
  const openSample = () => {
    setSampleWanted(true)
    setAppSession('modeling')
  }
  const startDesign = () => {
    if (uiGate) return // Codex3 B1: the AI-session start is an operation start
    setAppSession('modeling')
    setDockOpen(true)
    startBracketSession(operationStore)
  }
  // Manual authoring lane — the truth-lane rule (Codex1 B2): the bridge with a
  // live workspace; UNAVAILABLE (fails loud) in the desktop without one; the
  // badged mock ONLY in browser dev. The desktop never mocks.
  const featureBackend = useMemo<AuthoringBackend>(() => {
    const lane = chooseBackendLane(!!window.aiadra, currentWs?.workspaceId ?? null)
    if (lane === 'bridge') return createBridgeAuthoringBackend(currentWs!.workspaceId)
    if (lane === 'unavailable') return createUnavailableBackend()
    return createMockAuthoringBackend()
  }, [currentWs])
  // The CAD↔AI dock chrome (ADR/0040 D5). Live open/width are transient; their
  // startup defaults come from the settings registry (aiDockOpenDefault) and the
  // width is a persisted setting written on drag (aiDockWidth).
  const [dockOpen, setDockOpen] = useState<boolean>(() => registry.get('aiDockOpenDefault') as boolean)
  const [dockWidth, setDockWidth] = useSetting('aiDockWidth')

  // Restore the base display when a session ends (Codex B2 — intentional
  // restore, not a stale candidate left on screen). Fast lane only. D-H5: the
  // fixture is restored ONLY if the sample part was explicitly opened this
  // modeling session; a New-Part session restores to an empty viewport.
  const restoreBase = useCallback(() => {
    if (window.aiadra) return
    if (!import.meta.env.DEV || !sampleRef.current) {
      void viewportApi.current?.setDisplaySource(null)
      return
    }
    import('./dev/fixtureSource')
      .then(({ loadFixtureSource }) => loadFixtureSource())
      .then((src) => {
        if (src) {
          void viewportApi.current?.setDisplaySource(src)
          setFixtureBadge(src.badge)
        }
      })
      .catch(() => {})
  }, [viewportApi])

  // Preview controller: drives setDisplaySource off the selected candidate with
  // monotonic race protection (B2). The store stays the source of truth.
  useCandidatePreview({ store: operationStore, viewportApi, ready, restoreBaseDisplay: restoreBase })

  // Command actions (Codex1 N3) — injected into the taxonomy's `run`, never
  // captured by descriptors. Mode/grid flow through the store (so toolbar, menu,
  // and keyboard agree); fit/reset are imperative one-shots on the viewport API.
  const actions: CommandActions = useMemo(
    () => ({
      fit: () => viewportApi.current?.fit(),
      reset: () => viewportApi.current?.reset(),
      setMode: (m) => viewStore.setMode(m),
      toggleGrid: () => viewStore.setGridVisible(!viewStore.getSnapshot().gridVisible),
      standardView: (id) => viewportApi.current?.standardView(id),
      toggleFilterKind: (k) => selectionStore.toggleFilterKind(k),
      clearSelection: () => selectionStore.clearSelected(),
    }),
    [viewStore, selectionStore, viewportApi],
  )

  // The command context combines the view-state and selection snapshots.
  const ctxNow = () =>
    toCommandContext(viewStore.getSnapshot(), {
      filter: selectionStore.getSnapshot().filter,
      hasSelection: selectionStore.getSnapshot().selected !== null,
    })

  // Keyboard shortcuts (Codex1 N4) — guarded: no command fires while typing in
  // an input / select / textarea / contenteditable, or with modifier chords the
  // browser should own.
  useEffect(() => {
    if (!ready) return
    const onKeyDown = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      const tag = t?.tagName
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA' || t?.isContentEditable) return
      // Escape clears the committed selection (Codex1 Q7) — guarded like the rest.
      if (e.key === 'Escape') {
        if (selectionStore.getSnapshot().selected) {
          selectionStore.clearSelected()
          e.preventDefault()
        }
        return
      }
      const chord = normalizeChord(e)
      if (dispatchShortcut(chord, ctxNow(), actions)) e.preventDefault()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, viewStore, selectionStore, actions])

  // The dev-lane SAMPLE part (arc 20260714-1; D-H5): loaded only after the
  // explicit "Open sample part" Home entry — the app never boots into a fixture
  // ambush. Runs once the viewport is mounted (`modeling` + ready). The dynamic
  // import keeps fixtures out of production bundles (assert-no-fixtures).
  useEffect(() => {
    if (!sampleWanted || appSession !== 'modeling' || !ready) return
    setSampleWanted(false)
    if (!import.meta.env.DEV || window.aiadra) return
    let cancelled = false
    import('./dev/fixtureSource')
      .then(async ({ loadFixtureSource }) => {
        const src = await loadFixtureSource()
        if (!src || cancelled) return
        await viewportApi.current?.setDisplaySource(src)
        if (!cancelled) {
          setFixtureBadge(src.badge)
          sampleRef.current = true
        }
      })
      .catch((e) => {
        if (!cancelled) setFixtureError(e instanceof Error ? e.message : String(e))
      })
    return () => {
      cancelled = true
    }
  }, [sampleWanted, appSession, ready, viewportApi])

  // The File menu (D-H3) — present in both states; unbuilt entries are visibly
  // disabled with a tooltip (Codex6: Check-In stays disabled until it performs
  // the real git-backed transition).
  const bridged = !!window.aiadra
  const fileItems: FileMenuItem[] = [
    {
      label: 'New…',
      enabled: !uiGate,
      title: uiGate ?? 'Create a new object (Part, …)',
      onClick: requestNew,
    },
    {
      label: 'Open Workspace…',
      enabled: bridged && !uiGate,
      title: !bridged
        ? 'Available in the desktop app'
        : (uiGate ?? 'Open an AIADRA workspace folder'),
      onClick: async () => {
        const r = await window.aiadra!.chooseWorkspace()
        if (!r.ok) return
        const reason = await switchWorkspace(r.result)
        if (reason !== null) setShellNote(reason)
      },
    },
    {
      label: 'Close',
      enabled: appSession === 'modeling' && !uiGate,
      title:
        appSession !== 'modeling'
          ? 'No model is open'
          : (uiGate ?? 'Close the model and return Home'),
      onClick: () => void closeToHome(),
      sep: true,
    },
    {
      label: 'Check In',
      enabled: false,
      title: 'Performs the git-backed check-in — arrives with the PDM slice (ADR/0040 D7)',
      sep: true,
    },
  ]

  return (
    <div className="studio">
      <header className="topbar">
        <span className="brand">AIADRA&nbsp;Studio</span>
        <FileMenu items={fileItems} />
        <span className="muted small">{appSession === 'home' ? 'Home' : 'Modeling workspace'}</span>
        {appSession === 'modeling' && fixtureBadge && (
          <span className="ref-badge small">{fixtureBadge}</span>
        )}
      </header>
      {appSession === 'home' && (
        <>
          <HomeRibbon
            onNewPart={requestNew}
            onOpenWorkspace={async () => {
              const r = await window.aiadra!.chooseWorkspace()
              if (!r.ok) return
              const reason = await switchWorkspace(r.result)
              if (reason !== null) setShellNote(reason)
            }}
            canOpenWorkspace={bridged && !uiGate}
          />
          <HomeSurface
            onOpened={switchWorkspace}
            onOpenSample={import.meta.env.DEV && !window.aiadra ? openSample : undefined}
            onDesignStart={startDesign}
            startGate={uiGate}
            onNewPart={requestNew}
          />
        </>
      )}
      {appSession === 'modeling' && (
        <>
      <ModelRibbon onStart={onStartFeature} busy={!!uiGate} />
      <div className="workbench">
        <aside className="sidebar">
          <EnginePanel api={viewportApi} ws={currentWs} onOpen={switchWorkspace} gate={uiGate} />
          <ImportPanel api={viewportApi} />
          <AppearancePanel />
          <div className="panel-title">Model tree</div>
          <ModelTreePanel store={featureStore} />
          <div className="muted small pad">
            Create features from the <b>Model</b> ribbon above. The persistent
            per-Part tree arrives with the stepwise Sketch→Extrude flow.
          </div>
          {fixtureError && <div className="small pad err">{fixtureError}</div>}
          <div className="panel-title">Properties</div>
          <div className="muted small pad">
            Windchill-style Product-Truth panel — placeholder.
          </div>
        </aside>
        <main className="viewport">
          {ready ? (
            <>
              <Toolbar store={viewStore} selectionStore={selectionStore} actions={actions} />
              <Viewport
                apiRef={viewportApi}
                theme={theme}
                settleMs={registry.get('settleMs') as number}
                viewStore={viewStore}
                selectionStore={selectionStore}
                commandActions={actions}
              />
            </>
          ) : (
            <div className="hud muted small">initializing…</div>
          )}
          <FeatureDashboard
            store={featureStore}
            backend={featureBackend}
            viewportApi={viewportApi}
            onClose={restoreBase}
          />
          <SketchPad
            store={sketchStore}
            backend={featureBackend}
            viewportApi={viewportApi}
            onClose={restoreBase}
          />
          <div className="hud muted small">middle = rotate · scroll = zoom · middle+shift = pan · middle+ctrl = zoom · left = select · right = menu</div>
        </main>
        {dockOpen && (
          <Dock
            store={operationStore}
            width={dockWidth as number}
            onWidthChange={(w) => setDockWidth(w)}
            onDismiss={() => setDockOpen(false)}
            startGate={uiGate}
            homeTab={
              <WorkspaceStart
                onOpened={switchWorkspace}
                gate={uiGate}
                refreshKey={currentWs?.workspaceId ?? ''}
              />
            }
          />
        )}
      </div>
        </>
      )}
      <div className="statusbar">
        <SessionPill store={operationStore} dockOpen={dockOpen} onShowDock={() => setDockOpen(true)} />
        {shellNote && <span className="small err">{shellNote}</span>}
        <span className="grow" />
        <span className="chipbar byo" title="AIADRA Core ships no AI — MVP-1 uses a scripted configurator">
          ● BYO-AI: scripted (MVP-1)
        </span>
      </div>
      <NewDialog open={newDialogOpen} onCancel={() => setNewDialogOpen(false)} onCreate={(c) => void createNew(c)} />
    </div>
  )
}

export default function App() {
  const viewportApi = useRef<ViewportApi | null>(null)
  const registryRef = useRef<SettingsRegistry | null>(null)
  const persistenceRef = useRef<Persistence | null>(null)
  const viewStoreRef = useRef<ViewStateStore | null>(null)
  const selectionStoreRef = useRef<SelectionStore | null>(null)
  const operationStoreRef = useRef<OperationStore | null>(null)
  const featureStoreRef = useRef<FeatureSessionStore | null>(null)
  const sketchStoreRef = useRef<SketchStore | null>(null)
  const [ready, setReady] = useState(false)

  if (!registryRef.current) {
    const persistence = createPersistence()
    persistenceRef.current = persistence
    // Persist (debounced) on every live change; hydrate does NOT trigger this.
    registryRef.current = createSettingsRegistry({ onChange: (blob) => persistence.save(blob) })
  }
  const registry = registryRef.current

  if (!viewStoreRef.current) {
    // Live view-state store (6b). Seeded from built-in defaults now; re-seeded
    // from the hydrated registry in the boot effect before `ready` flips, so the
    // persisted startup mode/grid (6a N3) apply on first viewport mount.
    viewStoreRef.current = createViewStateStore({
      mode: registry.get('defaultDisplayMode') as DisplayMode,
      gridVisible: registry.get('gridVisibleDefault') as boolean,
      hasCanonicalPart: false,
      hasReferenceGeometry: false,
    })
  }
  const viewStore = viewStoreRef.current

  if (!selectionStoreRef.current) selectionStoreRef.current = createSelectionStore()
  const selectionStore = selectionStoreRef.current

  if (!operationStoreRef.current) operationStoreRef.current = createOperationStore()
  const operationStore = operationStoreRef.current

  if (!featureStoreRef.current) featureStoreRef.current = createFeatureSessionStore()
  const featureStore = featureStoreRef.current

  if (!sketchStoreRef.current) sketchStoreRef.current = createSketchStore()
  const sketchStore = sketchStoreRef.current

  // Boot: load persisted settings → hydrate → render the viewport with the
  // resolved values (so persisted theme/settleMs/defaults apply at startup).
  // A load failure is non-fatal — defaults stand (app prefs never brick boot).
  useEffect(() => {
    let cancelled = false
    persistenceRef.current
      ?.load()
      .then((blob) => {
        if (cancelled) return
        if (blob) {
          try {
            registry.hydrate(blob)
          } catch (e) {
            console.error('[settings] hydrate failed, using defaults:', e instanceof Error ? e.message : e)
          }
        }
        // Re-seed the view-state store from the (now hydrated) registry so the
        // persisted startup mode/grid apply on the first viewport mount.
        viewStore.setMode(registry.get('defaultDisplayMode') as DisplayMode)
        viewStore.setGridVisible(registry.get('gridVisibleDefault') as boolean)
        setReady(true)
      })
      .catch(() => setReady(true))
    return () => {
      cancelled = true
      void persistenceRef.current?.flush()
    }
  }, [registry, viewStore])

  return (
    <SettingsProvider registry={registry}>
      <Workbench
        ready={ready}
        viewportApi={viewportApi}
        viewStore={viewStore}
        selectionStore={selectionStore}
        operationStore={operationStore}
        featureStore={featureStore}
        sketchStore={sketchStore}
      />
    </SettingsProvider>
  )
}
