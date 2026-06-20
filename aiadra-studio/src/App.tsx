import { type MutableRefObject, useEffect, useMemo, useRef, useState } from 'react'
import Viewport, { type ViewportApi } from './Viewport'
import { Toolbar } from './Toolbar'
import { createBridgeSource } from './display/displaySource'
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

function Workbench({
  ready,
  viewportApi,
  viewStore,
}: {
  ready: boolean
  viewportApi: MutableRefObject<ViewportApi | null>
  viewStore: ViewStateStore
}) {
  const registry = useRegistry()
  const theme = useTheme()
  const [fixtureBadge, setFixtureBadge] = useState<string | null>(null)
  const [fixtureError, setFixtureError] = useState<string | null>(null)

  // Command actions (Codex1 N3) — injected into the taxonomy's `run`, never
  // captured by descriptors. Mode/grid flow through the store (so toolbar, menu,
  // and keyboard agree); fit/reset are imperative one-shots on the viewport API.
  const actions: CommandActions = useMemo(
    () => ({
      fit: () => viewportApi.current?.fit(),
      reset: () => viewportApi.current?.reset(),
      setMode: (m) => viewStore.setMode(m),
      toggleGrid: () => viewStore.setGridVisible(!viewStore.getSnapshot().gridVisible),
    }),
    [viewStore, viewportApi],
  )

  // Keyboard shortcuts (Codex1 N4) — guarded: no command fires while typing in
  // an input / select / textarea / contenteditable, or with modifier chords the
  // browser should own.
  useEffect(() => {
    if (!ready) return
    const onKeyDown = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      const tag = t?.tagName
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA' || t?.isContentEditable) return
      const chord = normalizeChord(e)
      const ctx = toCommandContext(viewStore.getSnapshot())
      if (dispatchShortcut(chord, ctx, actions)) e.preventDefault()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [ready, viewStore, actions])

  // Browser-dev fixture lane (arc 20260610-1 P7): loaded ONLY when there is no
  // bridge AND this is a dev build, after settings are ready (so the Viewport
  // is mounted). The dynamic import keeps fixtures out of production bundles
  // (scripts/assert-no-fixtures.mjs — Codex1 N2).
  useEffect(() => {
    if (!ready || !import.meta.env.DEV || window.aiadra) return
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
  }, [ready, viewportApi])

  return (
    <div className="studio">
      <header className="topbar">
        <span className="brand">AIADRA&nbsp;Studio</span>
        <span className="muted small">command toolbar · arc 20260619-2</span>
        {fixtureBadge && <span className="ref-badge small">{fixtureBadge}</span>}
      </header>
      <div className="workbench">
        <aside className="sidebar">
          <EnginePanel api={viewportApi} />
          <ImportPanel api={viewportApi} />
          <AppearancePanel />
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
          {ready ? (
            <>
              <Toolbar store={viewStore} actions={actions} />
              <Viewport
                apiRef={viewportApi}
                theme={theme}
                settleMs={registry.get('settleMs') as number}
                viewStore={viewStore}
                commandActions={actions}
              />
            </>
          ) : (
            <div className="hud muted small">initializing…</div>
          )}
          <div className="hud muted small">middle = rotate · scroll = zoom · middle+shift = pan · middle+ctrl = zoom · left = select · right = menu</div>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  const viewportApi = useRef<ViewportApi | null>(null)
  const registryRef = useRef<SettingsRegistry | null>(null)
  const persistenceRef = useRef<Persistence | null>(null)
  const viewStoreRef = useRef<ViewStateStore | null>(null)
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
      <Workbench ready={ready} viewportApi={viewportApi} viewStore={viewStore} />
    </SettingsProvider>
  )
}
