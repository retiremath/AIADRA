import { type MutableRefObject, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
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
import {
  createAuthoringSessionStore,
  useAuthoringSession,
  type AuthoringSessionStore,
} from './authoring/authoringSession'
import { ExtrudePanel } from './authoring/ExtrudePanel'
import { ModelRibbon } from './authoring/ModelRibbon'
import { createMockAuthoringBackend } from './authoring/backendMock'
import { createBridgeAuthoringBackend } from './authoring/backendBridge'
import {
  buildCreatePartOps,
  chooseBackendLane,
  createUnavailableBackend,
  INTRINSIC_CSYS_ID,
  INTRINSIC_PLANE_IDS,
  PLANE_LABELS,
  sketchAuthoringGate,
  type AuthoringBackend,
  type PlaneOrientation,
} from './authoring/backend'
import {
  authoringFacts,
  authoringStartRefusal,
  captureAuthoringTarget,
  createPartContextStore,
  type InspectFetcher,
  type PartContextStore,
} from './authoring/partContext'
import { createPendingDisplayCoordinator } from './authoring/pendingDisplay'
import { buildTreeRows, unconsumedSketches } from './authoring/inspectDecode'
import { runOneShotCommit } from './authoring/oneShotCommit'
import { createWorkspaceSwitcher, isCloseAcked } from './workspace/switcher'
import { SketchPad } from './sketch/SketchPad'
import { PlanePicker } from './sketch/PlanePicker'
import type { DisplaySource } from './display/displaySource'
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
  ws,
  onOpen,
  gate,
  refresh = 0,
  loadedPart,
  onPartLoaded,
}: {
  /** The ONE Workbench-owned current workspace (Codex1 B1) — this panel is a
   *  projection of it, never a second owner. */
  ws: OpenedWorkspace | null
  /** Route an open through the central gated transition (Codex2 B3 — resolves
   *  the refusal reason, or null when adopted). */
  onOpen: (ws: OpenedWorkspace) => Promise<string | null>
  /** Human-readable switch-gate reason while an operation is active, else null. */
  gate: string | null
  /** Bump to re-list parts (EP1: a commit created/changed a Part). */
  refresh?: number
  /** The loaded-row label — the partContext's partNumber (Codex3 B2: bound to
   *  the SAME transition generation as tree/target/display, never local). */
  loadedPart: string | null
  /** Route a Part-row load through the Workbench's ONE canonical transition. */
  onPartLoaded?: (partNumber: string) => void
}) {
  const [version, setVersion] = useState<string | null>(null)
  const [parts, setParts] = useState<PartRow[]>([])
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

  // Codex3 B2: the row load is a pure DISPATCH into the Workbench's one
  // canonical Part transition — this panel installs nothing itself, so
  // display/tree/target/row can never split across two Parts.
  const loadPart = (part: PartRow) => {
    setNote('')
    onPartLoaded?.(part.object_number)
  }

  // Projection (Codex1 B1): adopt EVERY current-workspace change — including a
  // mid-modeling A→B switch from any surface — never only the first. The old
  // parts list is cleared before the new listing (the central transition
  // already cleared the display before applying).
  useEffect(() => {
    setParts([])
    // Keep the lane-identifying note in browser dev — clearing it left a
    // misleading perpetual "connecting…" (it hid which lane was running).
    setNote(window.aiadra ? '' : 'browser preview — no engine bridge (run as the desktop app)')
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
          loadPart(list.result.parts[0])
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ws?.workspaceId, refresh])

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
              {/* Codex3 B2: Part loads join the SAME operation gate as
                  authoring/workspace transitions — a Part cannot change under
                  an active sketch/extrude session. */}
              {parts.map((p) => (
                <li
                  key={p.object_uuid}
                  className={`part-row ${loadedPart === p.object_number ? 'on' : ''}${gate ? ' disabled' : ''}`}
                  title={gate ?? undefined}
                  onClick={() => !gate && loadPart(p)}
                  style={gate ? { opacity: 0.5, cursor: 'not-allowed' } : undefined}
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

// ---- Model tree (S2 — TRUTH-FED, the Creo shape; arc 20260714-3 D-S1) ----
// The Part header + the three intrinsic principal planes + the origin csys
// (stable overlay ids — labeled intrinsic, never Truth features), then the
// COMMITTED features straight from the generation-owned partContext: base
// features as `Extrude N` with their consumed sketch NESTED as `Section N`,
// unconsumed sketches top-level as `Sketch N` — exactly the Creo 10 tree.
// Fail-closed: loading shows a spinner row, a decode error shows the error —
// never a silently stale or wrong tree. The in-flight feature op still shows
// as a transient last row (it is not Truth yet).
const TREE_GLYPHS: Record<string, string> = {
  sketch: '✎',
  extrude: '⬒',
  revolve: '◎',
  section: '✎',
  other: '▪',
}

function ModelTreePanel({
  session,
  context,
}: {
  session: AuthoringSessionStore
  context: PartContextStore
}) {
  const s = useAuthoringSession(session)
  const pc = useSyncExternalStore(context.subscribe, context.getSnapshot)
  const part = pc.inspection.status === 'ready' ? pc.inspection.part : null
  const transient =
    s.mode === 'sketch'
      ? { label: 'Sketch', state: s.phase === 'busy' ? '…' : 'editing' }
      : s.mode === 'extrude'
        ? { label: 'Extrude', state: s.phase === 'busy' ? '…' : 'editing' }
        : null
  return (
    <ul className="tree model-tree">
      {pc.partNumber && (
        <li className="feat-row part-head">
          <span className="feat-glyph">■</span>
          <span className="feat-name">{part?.name ?? pc.partNumber}</span>
          <span className="muted small feat-state">{pc.partNumber}</span>
        </li>
      )}
      {(['xy', 'yz', 'zx'] as const).map((ori) => (
        <li key={ori} className="feat-row intrinsic" data-intrinsic-id={INTRINSIC_PLANE_IDS[ori]}>
          <span className="feat-glyph">▱</span>
          <span className="feat-name">{PLANE_LABELS[ori]}</span>
          <span className="muted small feat-state">intrinsic</span>
        </li>
      ))}
      <li className="feat-row intrinsic" data-intrinsic-id={INTRINSIC_CSYS_ID}>
        <span className="feat-glyph">⌖</span>
        <span className="feat-name">Origin</span>
        <span className="muted small feat-state">intrinsic</span>
      </li>
      {pc.inspection.status === 'loading' && (
        <li className="feat-row busy">
          <span className="feat-glyph">◐</span>
          <span className="feat-name muted">reading Truth…</span>
        </li>
      )}
      {pc.inspection.status === 'error' && (
        <li className="feat-row error">
          <span className="feat-glyph">⚠</span>
          <span className="feat-name">tree unavailable</span>
          <span className="muted small feat-state" title={pc.inspection.message}>
            {pc.inspection.message}
          </span>
        </li>
      )}
      {part &&
        buildTreeRows(part).map((row) => {
          // An UNCONSUMED sketch row is selectable — the Extrude dual entry A
          // (select a sketch → Extrude goes straight to depth).
          const selectable = row.kind === 'sketch'
          const selected = selectable && s.selectedSketchId === row.featureId
          return (
            <li
              key={`${row.featureId}:${row.depth}`}
              className={`feat-row truth${row.depth === 1 ? ' nested' : ''}${selected ? ' selected' : ''}`}
              data-feature-id={row.featureId}
              style={{
                ...(row.depth === 1 ? { paddingLeft: '1.4em' } : null),
                ...(selectable ? { cursor: 'pointer' } : null),
                ...(selected ? { outline: '1px solid var(--accent, #6b9bd1)' } : null),
              }}
              title={selectable ? 'Select this sketch (Extrude will consume it)' : undefined}
              onClick={
                selectable
                  ? () => session.selectSketch(selected ? null : row.featureId)
                  : undefined
              }
            >
              <span className="feat-glyph">{TREE_GLYPHS[row.kind] ?? '▪'}</span>
              <span className="feat-name">{row.label}</span>
              <span className="muted small feat-state">{row.featureId}</span>
            </li>
          )
        })}
      {transient && (
        <li className="feat-row editing">
          <span className="feat-glyph">◐</span>
          <span className="feat-name">{transient.label}</span>
          <span className="muted small feat-state">{transient.state}</span>
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
  authoringStore,
}: {
  ready: boolean
  viewportApi: MutableRefObject<ViewportApi | null>
  viewStore: ViewStateStore
  selectionStore: SelectionStore
  operationStore: OperationStore
  authoringStore: AuthoringSessionStore
}) {
  const registry = useRegistry()
  const theme = useTheme()
  // Authoring dispatch (arc 20260711-11): the Model ribbon starts either the
  // sketch pad (draw a contour) or the extrude feature session. One at a time.
  const authoringSession = useAuthoringSession(authoringStore)
  const authoringBusy = authoringSession.mode !== 'idle'

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
  // Commit-at-New is a REAL operation (Codex5 B1): its busy state joins the
  // SAME gate as every authoring/AI start AND the workspace switcher.
  const [createBusy, setCreateBusy] = useState(false)
  const switchGate =
    authoringBusy || opActive || createBusy
      ? createBusy
        ? 'Part creation is in flight'
        : 'Finish or cancel the active operation first'
      : null
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
          authoringStore.selectSketch(null) // Part-local ids die with the workspace (Codex4 B1.3)
          setFixtureBadge(null)
          sampleRef.current = false
          partContext.clear() // the Part context belongs to the old workspace (S2 B2)
          pendingDisplay.cancel() // settle any queued pre-mount install (Codex5 B1.1)
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
    // eslint-disable-next-line react-hooks/exhaustive-deps -- authoringStore/partContext are creation-stable
    [selectionStore, viewportApi, authoringStore],
  )
  // ---- ONE generation-owned Part context (S2; Codex1 B2). THE authority for
  // "which Part is this session about + what does Truth say": the model tree,
  // the sketch-wire overlay, the authoring target, and Extrude eligibility all
  // read here. EP1's featureCount bookkeeping is retired — the engine owns
  // feature identity (the $fromOp handshake), Truth owns the tree.
  const partContext = useMemo(() => createPartContextStore(), [])
  const pc = useSyncExternalStore(partContext.subscribe, partContext.getSnapshot)
  const partFacts = authoringFacts(pc)
  const [partsRefresh, setPartsRefresh] = useState(0)
  // The COMBINED gate for every operation start + open/close control (Codex3
  // B1 → Codex4 B1.2): active work, an in-flight workspace transition, OR an
  // unresolved canonical Part transition — no manual/AI operation may start
  // while a Part adoption is in flight.
  const uiGate =
    switchGate ??
    (wsTransition ? 'A workspace transition is in flight' : null) ??
    (pc.inspection.status === 'loading' ? 'A Part is loading — wait for it to resolve' : null)
  // The AUTHORING-START gate (Codex5 B1.2): everything in uiGate PLUS a
  // targeted-but-not-ready Part context — ONE policy for the ribbon, the AI
  // session, and New/commit starts. Navigation (workspace open/close, Part
  // rows) stays on uiGate so a targeted `error` never blocks recovery.
  const authoringGate = uiGate ?? authoringStartRefusal(pc)
  // The inspect lane, bound to an EXPLICIT workspaceId (never a render-time
  // closure — commit-at-New adopts a workspace mid-flight): desktop = the
  // capability-checked bridge inspect; browser dev = the mock's honest mirror.
  const makeInspectFetcher = useCallback(
    (wsId: string | null): InspectFetcher =>
      async (partNumber: string) => {
        if (window.aiadra) {
          if (!wsId) throw new Error('no workspace capability for inspect')
          const r = await window.aiadra.inspect(wsId, partNumber)
          if (!r.ok) throw new Error(r.error.message)
          return (r.result as { object: unknown }).object
        }
        const mock = featureBackendRef.current as { inspectRaw?: (n: string) => unknown }
        if (typeof mock?.inspectRaw !== 'function') throw new Error('no inspect lane available')
        return mock.inspectRaw(partNumber)
      },
    [],
  )
  // The pre-mount display coordinator (Codex5 B1.1): keeps a deferred
  // commit-at-New display INSIDE the transition join.
  const pendingDisplay = useMemo(() => createPendingDisplayCoordinator(), [])
  /** Install a display source INSIDE a Part transition (Codex3 B2): stale
   *  adoptions install nothing; the pre-mount case DEFERS through the
   *  coordinator with the transition's `stillCurrent` (Codex4 B1.5 + Codex5
   *  B1.1 — the deferral is a real joined promise, and a cleared or
   *  superseded adoption can never install its deferred source after mount).
   *  The viewport's own load token stays as defense in depth. */
  const installIntoViewport = useCallback(
    (src: DisplaySource) => async (stillCurrent: () => boolean) => {
      if (!stillCurrent()) return
      if (viewportApi.current) await viewportApi.current.setDisplaySource(src)
      // Pre-mount (commit-at-New from Home): the deferred install stays part
      // of the transition JOIN — this promise settles only when the mounted
      // viewport installs (or fails), so partContext cannot publish `ready`
      // on a merely-queued display (Codex5 B1.1).
      else await pendingDisplay.defer(src, stillCurrent)
    },
    [viewportApi, pendingDisplay],
  )
  /** The synchronous transition-start boundary (Codex4 B1.3): canonical
   *  face/edge selection and the tree's selected sketch die BEFORE any async
   *  work — feature ids are Part-local, so A's `feat_0001` must never alias
   *  B's `feat_0001` across an adoption. */
  const clearPartScopedSelections = useCallback(() => {
    selectionStore.clearSelected()
    authoringStore.selectSketch(null)
  }, [selectionStore, authoringStore])
  /** THE canonical Part adoption (Codex3 B2 — ONE transition for row-click
   *  loads, auto-load, commit-at-New, and fresh dev-lane commits): the
   *  generation advances synchronously, then display + inspect run under it.
   *  `display` = a commit result's source; absent → the bridge canonical lane. */
  const adoptPart = useCallback(
    (wsId: string | null, partNumber: string, display?: DisplaySource) => {
      const src =
        display ?? (window.aiadra && wsId ? createBridgeSource(wsId, partNumber) : null)
      void partContext.setPart(wsId, partNumber, {
        onTransitionStart: clearPartScopedSelections,
        fetchInspect: makeInspectFetcher(wsId),
        installDisplay: src ? installIntoViewport(src) : undefined,
      })
    },
    [partContext, makeInspectFetcher, installIntoViewport, clearPartScopedSelections],
  )
  /** Re-run the transition for the CURRENT Part (after a feature commit);
   *  `display` = the commit's returned source (installed under the SAME
   *  generation as the Truth re-read). The commit changed the topology, so
   *  Part-scoped selections clear here too (the same boundary rule). */
  const refreshPartContext = useCallback(
    (display?: DisplaySource) => {
      const s = partContext.getSnapshot()
      if (s.partNumber === null) return
      void partContext.refresh({
        onTransitionStart: clearPartScopedSelections,
        fetchInspect: makeInspectFetcher(s.workspaceId),
        installDisplay: display ? installIntoViewport(display) : undefined,
      })
    },
    [partContext, makeInspectFetcher, installIntoViewport, clearPartScopedSelections],
  )

  // Authoring dispatch — gated on the COMBINED gate (Codex3 B1): no op may
  // start while a workspace transition owns the shell. Sketch begins by
  // PICKING A PLANE (EP1 — Petre's pinned semantics; all three live via EP2).
  // The picker serves BOTH the stepwise sketch and Extrude's chained
  // "New sketch…" (D-S3 entry B) — the purpose decides where the plane goes.
  const [planePicker, setPlanePicker] = useState<null | 'sketch' | 'chained'>(null)
  const onStartFeature = (kind: string) => {
    // Codex4 B1.2 → Codex5 B1.2: the ONE shared authoring-start gate —
    // active work, workspace/Part transitions, AND a targeted-but-not-ready
    // context (dev:web's fresh-Part flow is only legitimate with NO target).
    if (authoringGate) {
      setShellNote(authoringGate)
      return
    }
    if (kind === 'sketch') {
      // Codex5 B2 (fail closed): the REAL lane refuses to sketch without a
      // READY inspected Part context — loading/error states refuse too (S2
      // B2), never the fresh-Part fallback against a hidden/different Part.
      // The badged dev lane keeps the fresh-Part flow.
      const refusal = sketchAuthoringGate(!!window.aiadra && !!currentWs, partFacts.readyPart !== null)
      if (refusal) {
        setShellNote(refusal)
        return
      }
      setPlanePicker('sketch')
    } else if (kind === 'extrude') {
      // S2 B3 (UI eligibility from INSPECTED state): the real lane refuses
      // without a ready context or when the one-base rule already holds.
      if (window.aiadra || partFacts.readyPart) {
        if (!partFacts.readyPart) {
          setShellNote('Open or create a Part first — Extrude needs an inspected Part context')
          return
        }
        if (!partFacts.canExtrude) {
          setShellNote('This Part already has a base creation feature (one per Part in v1)')
          return
        }
      } else {
        // dev:web with no context yet — the chained New sketch… entry still
        // works (a fresh Part is created at commit).
      }
      // Dual entry (D-S3): a tree-selected UNCONSUMED sketch goes straight to
      // depth (entry A); otherwise the select step offers pick-or-create.
      const sel = authoringSession.selectedSketchId
      const part = partFacts.readyPart
      const selectedIsUnconsumed =
        sel !== null && part !== null && unconsumedSketches(part).some((sk) => sk.id === sel)
      // Codex3 B2 / Codex4 B1.4: the session CAPTURES the FULL authority
      // tuple {workspaceId, partNumber, generation} at start; the terminal
      // commit revalidates the exact tuple against the live context.
      authoringStore.startExtrude(
        selectedIsUnconsumed ? sel : null,
        captureAuthoringTarget(partContext.getSnapshot()),
      )
    }
  }
  const onPlanePicked = (plane: PlaneOrientation) => {
    const purpose = planePicker
    setPlanePicker(null)
    if (authoringGate) return
    const target = partFacts.readyPart
    const targetRef = target ? { number: target.number, name: target.name } : null
    if (purpose === 'chained') {
      // The chained sketch keeps the EXTRUDE session's captured tuple — the
      // store copies it at the hand-off (Codex4 B1.4).
      authoringStore.beginChainedSketch(plane, targetRef)
    } else {
      authoringStore.startSketch({
        plane,
        targetPart: targetRef,
        targetAuth: targetRef ? captureAuthoringTarget(partContext.getSnapshot()) : null,
      })
    }
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

  // ONE generic "New" (Creo's New pattern) → COMMIT-AT-NEW (EP1, Petre's pin):
  // OK COMMITS the empty Part through Ring 2 immediately — it exists in Truth
  // with its Number and DISPLAYS as emptiness (the EP0/A4 contract) under the
  // datum scaffold. NO auto sketch pad — Sketch is the user's next move.
  // A Number collision surfaces verbatim (core's ADR/0004 Reservation).
  const [newDialogOpen, setNewDialogOpen] = useState(false)
  const requestNew = () => {
    if (authoringGate) setShellNote(authoringGate)
    else setNewDialogOpen(true)
  }
  const createNew = async (choice: NewObjectChoice) => {
    setNewDialogOpen(false)
    setShellNote(null)
    if (authoringGate) return // Codex3 B1 + Codex5 B1.2: one authoring-start policy
    let wsId = switcher.current()?.workspaceId ?? null
    if (window.aiadra && wsId === null) {
      const r = await window.aiadra.chooseWorkspace()
      if (!r.ok) return // chooser cancelled/failed — nothing committed anywhere
      const reason = await switcher.adopt(r.result)
      if (reason !== null) {
        setShellNote(reason) // the fresh capability was retired by the switcher
        return
      }
      wsId = r.result.workspaceId
    }
    // Commit the empty Part through the SAME lanes as every authoring op
    // (desktop = the real bridge; dev:web = the badged mock; never mixed).
    // The bridge wrapper is rebuilt against the JUST-adopted wsId (the render's
    // featureBackend may predate the adoption); the mock lane reuses the ONE
    // session mock — its honest Truth mirror is what inspect reads (S2).
    const lane = chooseBackendLane(!!window.aiadra, wsId)
    const backend =
      lane === 'bridge'
        ? createBridgeAuthoringBackend(wsId!)
        : lane === 'mock'
          ? featureBackendRef.current
          : createUnavailableBackend()
    // Codex5 B1: a globally GATED, cleanup-owning one-shot — its busy state
    // sits in the same operation gate (createBusy → switchGate/uiGate), every
    // terminal failure AWAITS its rollback, and a stale result (the context
    // changed underneath) installs NOTHING.
    setCreateBusy(true)
    setShellNote(`creating ${choice.number}…`)
    try {
      const startWs = wsId
      const outcome = await runOneShotCommit(
        backend,
        buildCreatePartOps(choice.number, choice.name),
        choice.number,
        () => (switcher.current()?.workspaceId ?? null) !== startWs,
      )
      if (outcome.status === 'failed') {
        setShellNote(outcome.reason) // e.g. a Number collision, verbatim
        return
      }
      if (outcome.status === 'committed-stale') {
        // The Part exists in Truth, but this context is gone — report, do not install.
        setShellNote(`${choice.number} was created, but the workspace changed — open it from the parts list`)
        return
      }
      setShellNote(null)
      // The committed empty Part IS the context — ONE transition installs its
      // display AND reads its Truth (Codex3 B2; the pre-mount case defers to
      // the mount effect inside installIntoViewport).
      adoptPart(wsId, choice.number, outcome.result.display)
      setPartsRefresh((n) => n + 1)
      setAppSession('modeling')
    } finally {
      setCreateBusy(false)
    }
  }
  // Drain a display deferred before the viewport mounted (commit-at-New on
  // the first modeling entry): generation-bound AND join-settling (Codex4
  // B1.5 + Codex5 B1.1) — the coordinator installs iff the deferring
  // transition still holds its generation, and settles that transition's
  // promise either way (success → ready; failure → fail-closed error).
  useEffect(() => {
    if (appSession !== 'modeling' || !ready) return
    void pendingDisplay.drain(async (src) => {
      const api = viewportApi.current
      if (!api) throw new Error('viewport unavailable for the deferred display')
      await api.setDisplaySource(src)
    })
  }, [appSession, ready, viewportApi, partsRefresh, pendingDisplay])

  // The sketch-wire overlay (S2 D-S2): committed-but-unconsumed sketches show
  // as wires on their planes — derived from the SAME decoded Truth as the
  // tree, pushed on every partContext change (and on viewport mount).
  useEffect(() => {
    const push = () => {
      const s = partContext.getSnapshot()
      const part = s.inspection.status === 'ready' ? s.inspection.part : null
      viewportApi.current?.setSketchWires(part ? unconsumedSketches(part) : [])
    }
    push()
    return partContext.subscribe(push)
  }, [partContext, viewportApi, ready, appSession])
  const openSample = () => {
    setSampleWanted(true)
    setAppSession('modeling')
  }
  const startDesign = () => {
    if (authoringGate) return // Codex3 B1 + Codex5 B1.2: the AI start is an authoring start
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
  // The stable handle the inspect fetcher reads (the mock lane's honest
  // `inspectRaw` mirror lives on the instance).
  const featureBackendRef = useRef(featureBackend)
  featureBackendRef.current = featureBackend
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
      toggleDatums: () => viewStore.setDatumsVisible(!viewStore.getSnapshot().datumsVisible),
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
      enabled: !authoringGate,
      title: authoringGate ?? 'Create a new object (Part, …)',
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
            startGate={authoringGate}
            onNewPart={requestNew}
          />
        </>
      )}
      {appSession === 'modeling' && (
        <>
      <ModelRibbon onStart={onStartFeature} busy={!!authoringGate} />
      <div className="workbench">
        <aside className="sidebar">
          <EnginePanel
            ws={currentWs}
            onOpen={switchWorkspace}
            gate={uiGate}
            refresh={partsRefresh}
            loadedPart={pc.partNumber}
            onPartLoaded={(n) => adoptPart(currentWs?.workspaceId ?? null, n)}
          />
          <ImportPanel api={viewportApi} />
          <AppearancePanel />
          <div className="panel-title">Model tree</div>
          <ModelTreePanel session={authoringStore} context={partContext} />
          <div className="muted small pad">
            Create features from the <b>Model</b> ribbon above.
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
          <ExtrudePanel
            store={authoringStore}
            backend={featureBackend}
            context={partContext}
            part={partFacts.readyPart}
            onClose={restoreBase}
            onCommitted={(display) => {
              // S2 / Codex3 B2: the commit's display installs INSIDE the same
              // transition that re-reads Truth — one generation for both.
              refreshPartContext(display)
              setPartsRefresh((n) => n + 1)
            }}
            onNewSketch={() => setPlanePicker('chained')}
          />
          <SketchPad
            store={authoringStore}
            backend={featureBackend}
            context={partContext}
            onClose={restoreBase}
            onCommitted={(info) => {
              // S2 / Codex3 B2: ONE transition — a fresh dev-lane Part is
              // ADOPTED (display + Truth together); features onto the context
              // Part REFRESH it with the commit's display.
              if (info.createdFresh) adoptPart(currentWs?.workspaceId ?? null, info.number, info.display)
              else refreshPartContext(info.display)
              setPartsRefresh((n) => n + 1)
            }}
          />
          <div className="hud muted small">middle = rotate · scroll = zoom · middle+shift = pan · middle+ctrl = zoom · left = select · right = menu</div>
        </main>
        {dockOpen && (
          <Dock
            store={operationStore}
            width={dockWidth as number}
            onWidthChange={(w) => setDockWidth(w)}
            onDismiss={() => setDockOpen(false)}
            startGate={authoringGate}
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
      <PlanePicker open={planePicker !== null} onPick={onPlanePicked} onCancel={() => setPlanePicker(null)} />
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
  const authoringStoreRef = useRef<AuthoringSessionStore | null>(null)
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
      datumsVisible: true, // the empty-part scaffold shows by default (EP1)
      hasCanonicalPart: false,
      hasReferenceGeometry: false,
    })
  }
  const viewStore = viewStoreRef.current

  if (!selectionStoreRef.current) selectionStoreRef.current = createSelectionStore()
  const selectionStore = selectionStoreRef.current

  if (!operationStoreRef.current) operationStoreRef.current = createOperationStore()
  const operationStore = operationStoreRef.current

  if (!authoringStoreRef.current) authoringStoreRef.current = createAuthoringSessionStore()
  const authoringStore = authoringStoreRef.current


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
        authoringStore={authoringStore}
      />
    </SettingsProvider>
  )
}
