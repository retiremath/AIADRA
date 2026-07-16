/**
 * THE reference-import controller (arc 20260716-1 V-3, Codex1 B1) — ONE
 * user-mediated import flow consumed by every entry point: File → Import,
 * the ribbon's Get Data (dispatch: 'reference-import'), and the sidebar
 * References list. The sidebar's direct import button is RETIRED — entry
 * moved under the proper menus (Petre's D-V2); the list of imported
 * references stays.
 *
 * Trust boundary preserved VERBATIM from milestone-1b/-2: the picker is
 * user-mediated; bytes stay renderer-side; parsing runs in the worker; no
 * path reaches Electron main; no engine/Truth operation — imported geometry
 * is reference-only display identity; removal is race-safe through the
 * import session (Codex2 B3: a row removed while loading cannot orphan
 * geometry). Format honesty follows STEP_ENABLED (never promising STEP
 * where only STL is on).
 */
import { useEffect, useRef, useState, type MutableRefObject, type ReactElement } from 'react'
import type { ViewportApi } from '../Viewport'
import { ACCEPT_EXTENSIONS, ACCEPT_LABEL, STEP_ENABLED } from './importConfig'
import { createImporter, type Importer } from './importController'
import { createImportSession, type ImportSession } from './importSession'
import { spawnImportWorker } from './defaultWorker'

export type ImportStatus = 'loading' | 'ready' | 'error'
export type ImportItem = { id: string; name: string; status: ImportStatus; detail?: string }

function triangleCount(meshes: { position: Float32Array; index?: Uint32Array }[]): number {
  return meshes.reduce((n, m) => n + (m.index ? m.index.length : m.position.length / 3) / 3, 0)
}

export interface ReferenceImport {
  /** Open the user-mediated file picker (File menu / Get Data). */
  openPicker(): void
  items: ImportItem[]
  remove(id: string): void
  /** Codex2 B2 — the ONE lifecycle policy: references are MODELING-SCOPED.
   *  Called as modeling closes (before viewport teardown): every item —
   *  ready AND in-flight — is removed through the session (tombstoning
   *  in-flight parses so a late completion can never report ready against a
   *  viewport that no longer owns its geometry). */
  clearAll(): void
  /** Render ONCE inside the modeling view (the hidden file input). */
  inputElement: ReactElement
}

export function useReferenceImport(
  api: MutableRefObject<ViewportApi | null>,
  /** TEST SEAM: the importer factory (production = the worker importer). */
  makeImporter: () => Importer = () => createImporter({ workerFactory: spawnImportWorker }),
): ReferenceImport {
  const inputRef = useRef<HTMLInputElement>(null)
  const importerRef = useRef<Importer | null>(null)
  const sessionRef = useRef<ImportSession | null>(null)
  const seq = useRef(0)
  const [items, setItems] = useState<ImportItem[]>([])
  // items mirrored for clearAll (a ref so the File-menu closure never goes stale)
  const itemsRef = useRef<ImportItem[]>([])
  itemsRef.current = items

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
      if (!importerRef.current) importerRef.current = makeImporter()
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

  const clearAll = () => {
    for (const it of itemsRef.current) session().remove(it.id)
    setItems([])
  }

  return {
    openPicker: () => inputRef.current?.click(),
    items,
    remove,
    clearAll,
    inputElement: (
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT_EXTENSIONS}
        style={{ display: 'none' }}
        onChange={onFile}
      />
    ),
  }
}

/** The File-menu item label — format-honest per STEP_ENABLED. */
export const IMPORT_MENU_LABEL = `Import ${ACCEPT_LABEL}… (reference)`

/** The B1 availability reason outside the modeling workspace. */
export const IMPORT_HOME_REASON =
  'open a Part first — imported references display in the modeling workspace'

/** The sidebar References list — imported reference rows only (the import
 *  BUTTON lives under File → Import and the ribbon's Get Data now). */
export function ReferencesList({ imports }: { imports: ReferenceImport }) {
  if (imports.items.length === 0) return null
  return (
    <div className="import-panel">
      <div className="panel-title">References</div>
      <ul className="tree import-list">
        {imports.items.map((it) => (
          <li key={it.id} className="import-row">
            <div className="import-row-head">
              <span className="import-name" title={it.name}>{it.name}</span>
              <button className="link-btn small" type="button" onClick={() => imports.remove(it.id)}>
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
    </div>
  )
}
