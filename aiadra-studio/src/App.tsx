import { type MutableRefObject, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import Viewport, { type SketchInteractionMode, type ViewportApi } from './Viewport'
import { useProfileSketch } from './sketch/useProfileSketch'
import { runProfileClose } from './sketch/profileCloseRunner'
import { invalidationAction, profileActivity, sketchRibbonActive } from './authoring/authoringActivity'
import { deriveFrame as derivePlacementFrame } from './authoring/placementFrame'
import { Toolbar } from './Toolbar'
import { createBridgeSource } from './display/displaySource'
import { createOperationStore, useOperation, type OperationStore } from './operation/store'
import { useCandidatePreview } from './operation/previewController'
import { SessionPill } from './operation/SessionPill'
import { Dock, startBracketSession } from './dock/Dock'
import { HomeSurface } from './home/HomeSurface'
import { HomeRibbon } from './home/HomeRibbon'
import { FileMenu, type FileMenuItem } from './home/FileMenu'
import { QuickAccessBar, type QatCommand } from './ui/QuickAccessBar'
import { NavigatorTabs, type NavTabKey } from './ui/NavigatorTabs'
import { ContextMenu } from './ui/ContextMenu'
import type { MenuItem } from './ui/DropdownMenu'
import type { DeletionBlocker } from './aiadra'
import {
  DEFAULT_DELETE_REASON,
  deletePreflight,
  describeBlocker,
  shellTitle,
} from './workspace/partActions'
import { NewDialog, type NewObjectChoice } from './home/NewDialog'
import { WorkspaceStart, type OpenedWorkspace } from './home/HomeShared'
import {
  createAuthoringSessionStore,
  useAuthoringSession,
  type AuthoringSessionStore,
} from './authoring/authoringSession'
import { ExtrudePanel } from './authoring/ExtrudePanel'
import { EdgeFeaturePanel } from './authoring/EdgeFeaturePanel'
import { HolePanel } from './authoring/HolePanel'
import { EditParameterPanel } from './authoring/EditParameterPanel'
import { ModelRibbon } from './authoring/ModelRibbon'
import { RIBBON_COMMANDS } from './authoring/ribbon'
import { createMockAuthoringBackend } from './authoring/backendMock'
import { createBridgeAuthoringBackend } from './authoring/backendBridge'
import {
  buildCreatePartOps,
  chooseBackendLane,
  createUnavailableBackend,
  INTRINSIC_CSYS_ID,
  INTRINSIC_PLANE_IDS,
  PLANE_LABELS,
  buildRedefinePlacementOps,
  buildReferenceSketchOps,
  sketchAuthoringGate,
  supportFrame,
  type AuthoringBackend,
  type PlacementOpInput,
} from './authoring/backend'
import { PlacementPanel } from './authoring/PlacementPanel'
import { createOneShotRunner } from './authoring/oneShotRun'
import {
  authoringFacts,
  deriveSelectorFacts,
  authoringStartRefusal,
  captureAuthoringTarget,
  captureSelectorTarget,
  createPartContextStore,
  type InspectFetcher,
  type PartContextStore,
} from './authoring/partContext'
import { createPendingDisplayCoordinator } from './authoring/pendingDisplay'
import { buildTreeRows, eligibleExtrudeSketchIds, holeBaseRefusal, revolveSketchRefusal, unconsumedSketches } from './authoring/inspectDecode'
import { runOneShotCommit } from './authoring/oneShotCommit'
import { createWorkspaceSwitcher, isCloseAcked } from './workspace/switcher'
import { routeSketchPlacement } from './sketch/sketchPlacementRouter'
import { SketchRibbon } from './sketch/SketchRibbon'
import { SketchStatusLine } from './sketch/SketchStatusLine'
import { PlanePicker } from './sketch/PlanePicker'
import type { DisplaySource } from './display/displaySource'
import { IMPORT_HOME_REASON, IMPORT_MENU_LABEL, ReferencesList, useReferenceImport } from './import/referenceImport'
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
  onParts,
  onRequestNew,
  onActivePartMissing,
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
  /** WT-05: surface the listed identities so the shell can project the
   *  active-part title (class-4 derived; the list stays owned here). */
  onParts?: (parts: PartRow[]) => void
  /** WT-06: the workspace-header New Part… entry — the EXISTING commit-at-New
   *  flow with this workspace pre-bound (no second creation path). */
  onRequestNew?: () => void
  /** Two-sided session rule (arc 20260728-3): the active Part vanished from
   *  the workspace listing (deleted outside this session) — the shell must
   *  exit the stale context fail-closed. */
  onActivePartMissing?: () => void
}) {
  const [version, setVersion] = useState<string | null>(null)
  const [parts, setParts] = useState<PartRow[]>([])
  const [note, setNote] = useState('')
  // WT-06/07: ONE context menu at a time — either the workspace header or a
  // Part row, at the pointer.
  const [ctx, setCtx] = useState<
    | { kind: 'workspace'; x: number; y: number }
    | { kind: 'part'; part: PartRow; x: number; y: number }
    | null
  >(null)
  // WT-07: the Delete… confirmation (reason editable; core requires non-empty).
  const [confirmDelete, setConfirmDelete] = useState<{ part: PartRow; reason: string } | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  // The last structured refusal — rendered verbatim under the tree.
  const [blocked, setBlocked] = useState<{ number: string; message: string; blockers: DeletionBlocker[] } | null>(null)

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
        onParts?.(list.result.parts)
        // Two-sided session rule (arc 20260728-3): the loaded Part is gone
        // from Truth (deleted outside this session) — fail-closed exit.
        if (
          loadedPart !== null &&
          !list.result.parts.some((p) => p.object_number === loadedPart)
        ) {
          onActivePartMissing?.()
          return
        }
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

  // WT-07: Delete… — Studio's class-4 preflight first (active part / gate),
  // then the confirm dialog; the durable rules stay core's alone.
  const requestDelete = (part: PartRow) => {
    const refusal = deletePreflight(part.object_number, loadedPart, gate)
    if (refusal) {
      setNote(refusal)
      return
    }
    setBlocked(null)
    setConfirmDelete({ part, reason: DEFAULT_DELETE_REASON })
  }

  const runDelete = async () => {
    if (!confirmDelete || !ws || !window.aiadra) return
    const { part, reason } = confirmDelete
    if (!reason.trim()) {
      setNote('a deletion reason is required')
      return
    }
    setDeleteBusy(true)
    try {
      const r = await window.aiadra.deleteObject(ws.workspaceId, part.object_number, reason.trim())
      if (!r.ok) {
        setNote(r.error.message)
        return
      }
      if (!r.result.deleted) {
        // The structured refusal — rendered verbatim (core sorted it).
        setBlocked({
          number: part.object_number,
          message: r.result.refusal?.message ?? 'deletion refused',
          blockers: r.result.refusal?.blockers ?? [],
        })
        return
      }
      setNote(`${part.object_number} deleted — its Number stays permanently reserved`)
      setParts((prev) => {
        const next = prev.filter((p) => p.object_number !== part.object_number)
        onParts?.(next)
        return next
      })
    } finally {
      setDeleteBusy(false)
      setConfirmDelete(null)
    }
  }

  // WT-06: the workspace-header menu. Assembly/Drawing are honest roadmap
  // entries — canonically designed, not yet materialized in the runtime.
  const workspaceMenuItems: MenuItem[] = [
    { key: 'new-part', label: 'New Part…', disabledReason: gate },
    {
      key: 'new-assembly',
      label: 'New Assembly',
      disabledReason:
        'Assembly is canonically designed but not yet materialized in the runtime (ADR/0042)',
      sepBefore: true,
    },
    {
      key: 'new-drawing',
      label: 'New Drawing',
      disabledReason:
        'Drawing is canonically designed but not yet materialized in the runtime',
    },
  ]

  const partMenuItems = (part: PartRow): MenuItem[] => [
    { key: 'open', label: 'Open', disabledReason: gate },
    {
      key: 'delete',
      label: 'Delete…',
      disabledReason: deletePreflight(part.object_number, loadedPart, gate),
      sepBefore: true,
    },
  ]

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
          {ws && (
            /* WT-06: the workspace ROOT row (Creo's tree-root grammar) — RMB
               offers creation with THIS workspace pre-bound. */
            <div
              className="small pad ws-root"
              title="Right-click: New Part / Assembly / Drawing"
              onContextMenu={(e) => {
                e.preventDefault()
                setCtx({ kind: 'workspace', x: e.clientX, y: e.clientY })
              }}
            >
              <b>{ws.name}</b> <span className="muted">workspace</span>
            </div>
          )}
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
                  onContextMenu={(e) => {
                    e.preventDefault()
                    setCtx({ kind: 'part', part: p, x: e.clientX, y: e.clientY })
                  }}
                  style={gate ? { opacity: 0.5, cursor: 'not-allowed' } : undefined}
                >
                  {p.name || p.object_number} <span className="muted small">{p.object_number}</span>
                  {loadedPart === p.object_number && <span className="muted small"> (Active)</span>}
                </li>
              ))}
            </ul>
          )}
          {ws && parts.length === 0 && <div className="small pad muted">no Parts in this workspace</div>}
          {blocked && (
            /* The structured B2 refusal — core's deterministic list, rendered
               verbatim. Honest copy: released refs are permanent; the working
               remediation is a NAMED future design, not a promise. */
            <div className="small pad err delete-blocked">
              <div>
                <b>{blocked.number}</b> cannot be deleted — {blocked.blockers.length} live
                relationship reference{blocked.blockers.length === 1 ? '' : 's'}:
              </div>
              <ul>
                {blocked.blockers.map((b, i) => (
                  <li key={`${b.relationship_id}-${b.state}-${b.revision_id ?? ''}-${i}`}>
                    {describeBlocker(b)}
                  </li>
                ))}
              </ul>
              <button className="btn" type="button" onClick={() => setBlocked(null)}>
                Dismiss
              </button>
            </div>
          )}
          {ctx?.kind === 'workspace' && (
            <ContextMenu
              x={ctx.x}
              y={ctx.y}
              label="Workspace actions"
              items={workspaceMenuItems}
              onClose={() => setCtx(null)}
              onSelect={(key) => {
                if (key === 'new-part') onRequestNew?.()
              }}
            />
          )}
          {ctx?.kind === 'part' && (
            <ContextMenu
              x={ctx.x}
              y={ctx.y}
              label={`${ctx.part.object_number} actions`}
              items={partMenuItems(ctx.part)}
              onClose={() => setCtx(null)}
              onSelect={(key) => {
                if (key === 'open') loadPart(ctx.part)
                if (key === 'delete') requestDelete(ctx.part)
              }}
            />
          )}
          {confirmDelete && (
            <div className="dialog-scrim" role="presentation">
              <div className="dialog" role="dialog" aria-modal="true" aria-label="Delete Part">
                <div className="panel-title">Delete {confirmDelete.part.object_number}</div>
                <div className="small pad">
                  Delete <b>{confirmDelete.part.name || confirmDelete.part.object_number}</b> (
                  {confirmDelete.part.object_number}) from this workspace?
                  <br />
                  Its Number and history stay permanently reserved; vault bytes are preserved.
                </div>
                <label className="small pad" style={{ display: 'block' }}>
                  Reason
                  <input
                    type="text"
                    value={confirmDelete.reason}
                    style={{ width: '100%' }}
                    onChange={(e) =>
                      setConfirmDelete((c) => (c ? { ...c, reason: e.target.value } : c))
                    }
                  />
                </label>
                <div className="pad" style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  <button
                    className="btn"
                    type="button"
                    disabled={deleteBusy}
                    onClick={() => setConfirmDelete(null)}
                  >
                    Cancel
                  </button>
                  <button
                    className="btn danger"
                    type="button"
                    disabled={deleteBusy || !confirmDelete.reason.trim()}
                    onClick={() => void runDelete()}
                  >
                    {deleteBusy ? 'Deleting…' : 'Delete'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
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
  onEditFeature,
  onPlaneRow,
}: {
  session: AuthoringSessionStore
  context: PartContextStore
  /** R6: open the edit-dimension session for a committed feature (null =
   *  the affordance is unavailable, with the reason as tooltip). */
  onEditFeature?: { start: (featureId: string) => void; gate: string | null }
  /** SK-C1.0 S1 (Codex1 B4.5): non-null ONLY in plane-pick mode — the
   *  FRONT/RIGHT/TOP rows become real pick surfaces. */
  onPlaneRow?: ((ori: 'xy' | 'yz' | 'zx') => void) | null
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
        <li
          key={ori}
          className={'feat-row intrinsic' + (onPlaneRow ? ' pickable' : '')}
          data-intrinsic-id={INTRINSIC_PLANE_IDS[ori]}
          role={onPlaneRow ? 'button' : undefined}
          tabIndex={onPlaneRow ? 0 : undefined}
          title={onPlaneRow ? 'Sketch on ' + PLANE_LABELS[ori] : undefined}
          onClick={onPlaneRow ? () => onPlaneRow(ori) : undefined}
          onKeyDown={onPlaneRow ? (e) => { if (e.key === 'Enter') onPlaneRow(ori) } : undefined}
        >
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
              {onEditFeature &&
                row.depth === 0 &&
                (() => {
                  const feat = part.features.find((f) => f.id === row.featureId)
                  const params = feat && feat.kind !== 'sketch' && feat.kind !== 'sketchV2' ? feat.parameters : []
                  if (params.length === 0) return null
                  return (
                    <button
                      type="button"
                      className="link-btn small"
                      disabled={onEditFeature.gate !== null}
                      title={onEditFeature.gate ?? `Edit ${params.map((x) => x.name).join(', ')}`}
                      onClick={(ev) => {
                        ev.stopPropagation()
                        onEditFeature.start(row.featureId)
                      }}
                    >
                      ✎
                    </button>
                  )
                })()}
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
  // ADR/0044 A4 (arc 20260730-1): the v2 PROFILE lane. It owns its own
  // session, preview round trip and interaction mode, so integrating it here
  // is three lines rather than another six pieces of coupled state.
  const [snapAngleToleranceDeg] = useSetting('sketch.snapAngleToleranceDeg')
  const [minDragPx] = useSetting('sketch.minDragPx')
  // Codex6 B2: the profile session OWNS its frame (captured at open), and its
  // terminal is the ONE close runner — a failed commit rolls back and leaves
  // the drawing recoverable; a generation change never installs stale success.
  const profileLaneRef = useRef<ReturnType<typeof useProfileSketch> | null>(null)
  const profileLane = useProfileSketch({
    snapAngleToleranceDeg: Number(snapAngleToleranceDeg),
    minDragPx: Number(minDragPx),
    // Codex7 B2: terminal-start revalidation of the tuple CAPTURED at open.
    validateTarget: (t) => {
      const live = partContext.getSnapshot()
      if ((currentWs?.workspaceId ?? null) !== t.workspaceId) {
        return 'the workspace changed under this sketch — the session is stale (nothing was written); Cancel and reopen the sketch'
      }
      if (live.partNumber !== t.partNumber || live.generation !== t.generation) {
        return 'the Part context changed under this sketch — the session is stale (nothing was written); Cancel and reopen the sketch'
      }
      return null
    },
    onCommit: (intent, target) => {
      const lane = profileLaneRef.current
      if (!lane) return
      void runProfileClose(intent, {
        backend: {
          begin: (ops) => featureBackend.begin(ops as never).then((r) => ({ sessionId: r.sessionId })),
          commit: (sid, ref) => featureBackend.commit(sid, ref),
          rollback: (sid) => featureBackend.rollback(sid),
        },
        lane,
        // the CAPTURED Part, never the current one (Codex7 B2)
        partNumber: target.partNumber,
        generation: () => partContext.getSnapshot().generation,
        adopt: (display) => adoptPart(target.workspaceId, target.partNumber, display),
      })
    },
  })
  profileLaneRef.current = profileLane
  // The temporary Profile Sketch CREATE entry (ADR/0044 A4): plane pick →
  // profile session, with the v1 authoring store IDLE throughout — the two
  // lifecycles are never nested (Codex6 B2).
  const [profilePick, setProfilePick] = useState(false)
  useEffect(() => {
    if (!profilePick) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setProfilePick(false)
        e.preventDefault()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [profilePick])

  // Codex8 B1: profile activity is a RENDER derivation — "active now", the
  // same invariant the legacy store gives the gate. The previous effect
  // projection published one render late, and most gate consumers read
  // render-captured values, so a second operation could start in that frame.
  const profileActive = profileActivity(profilePick, profileLane)
  const authoringBusy = authoringSession.mode !== 'idle' || profileActive
  // The live canonical selection (transient UI state — enablement only; the
  // capture happens at session start, D-R8).
  const selectionSnap = useSyncExternalStore(selectionStore.subscribe, selectionStore.getSnapshot)
  const liveSelection =
    selectionSnap.selected && (selectionSnap.selected.kind === 'edge' || selectionSnap.selected.kind === 'face')
      ? { kind: selectionSnap.selected.kind as 'edge' | 'face', id: selectionSnap.selected.id }
      : null

  // ---- The two application states (arc 20260714-1; D-H1 — the Creo paradigm).
  // `home` at boot: NO viewport, the Home surface (workspace browser + recents
  // + the AI entry). `modeling` once a Part/workspace/sample is opened; File →
  // Close returns Home. One state at a time.
  const [appSession, setAppSession] = useState<'home' | 'modeling'>('home')
  // WT-05: the listed workspace identities (number → name) — the shell's
  // class-4 title projection reads the active Part's display name from here.
  const [wsParts, setWsParts] = useState<PartRow[]>([])
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
  // Codex8 B1: generation invalidation through the ONE pure decision — a
  // pick and an open draft unwind WITHOUT writing; a session whose Close is
  // in flight RETAINS busy ownership until the runner settles (its own
  // generation check refuses stale display adoption; commitFailed reopens
  // the drawing with the refusal surfaced).
  useEffect(() => {
    const action = invalidationAction(
      profilePick,
      profileLane.session === null
        ? null
        : {
            closing: profileLane.closing,
            targetGeneration: profileLane.session.target.generation,
          },
      pc.generation,
    )
    if (action === 'cancel-pick') setProfilePick(false)
    else if (action === 'cancel-session') void profileLane.cancel()
    // 'retain-terminal' | 'none': deliberately nothing
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pc.generation])

  const uiGate =
    switchGate ??
    (wsTransition ? 'A workspace transition is in flight' : null) ??
    (pc.inspection.status === 'loading' ? 'A Part is loading — wait for it to resolve' : null)
  // The AUTHORING-START gate (Codex5 B1.2): everything in uiGate PLUS a
  // targeted-but-not-ready Part context — ONE policy for the ribbon, the AI
  // session, and New/commit starts. Navigation (workspace open/close, Part
  // rows) stays on uiGate so a targeted `error` never blocks recovery.
  // Codex26 B3: the one-shot references commit participates in the GLOBAL
  // authoring gate — while it runs, every authoring start refuses with a
  // named reason (single-flight is enforced in the runner too).
  // The navigator tab (Creo tabbed tree). Starts on Workspace (where a part
  // is picked), auto-switches to Model Tree when a part loads, and is FORCED
  // to Model Tree during a plane pick. Manual choice stands otherwise.
  const [navTabChoice, setNavTabChoice] = useState<NavTabKey>('workspace')
  useEffect(() => {
    if (pc.partNumber !== null) setNavTabChoice('model')
  }, [pc.partNumber])
  const navTab: NavTabKey = authoringSession.mode === 'planePick' ? 'model' : navTabChoice
  const [refsBusy, setRefsBusy] = useState(false)
  const authoringGate =
    (refsBusy ? 'the references commit is still running — wait for it to finish' : null) ??
    uiGate ??
    authoringStartRefusal(pc)
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
  /** ONE generation-guarded install + fact publication for BOTH the
   *  immediate and the deferred (pre-mount) paths (Codex3 N1). */
  const installAndPublishFacts = useCallback(
    async (src: DisplaySource, stillCurrent: () => boolean) => {
      const api = viewportApi.current
      if (!api) throw new Error('viewport unavailable for the display install')
      const display = await api.setDisplaySource(src)
      // D-R8: the INSTALLED display's selector facts publish under THIS
      // transition's generation — edge kinds + face ids die with it.
      if (display && stillCurrent()) {
        const gen = partContext.getSnapshot().generation
        // ONE pure derivation (S2): edge kinds + face ids + v1.2 planar
        // eligibility + face-bound sketch frames, all under THIS generation.
        partContext.publishSelectorFacts(gen, deriveSelectorFacts(display))
      }
    },
    [viewportApi, partContext],
  )
  const installIntoViewport = useCallback(
    (src: DisplaySource) => async (stillCurrent: () => boolean) => {
      if (!stillCurrent()) return
      if (viewportApi.current) await installAndPublishFacts(src, stillCurrent)
      // Pre-mount (commit-at-New from Home): the deferred install stays part
      // of the transition JOIN — this promise settles only when the mounted
      // viewport installs (or fails), so partContext cannot publish `ready`
      // on a merely-queued display (Codex5 B1.1).
      else await pendingDisplay.defer(src, stillCurrent)
    },
    [viewportApi, pendingDisplay, installAndPublishFacts],
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
  // SK-C1.0 S1 (Codex1 B4.1): plane picking is a SESSION substate — the old
  // App-local planePicker state is deleted. Only the list-dialog visibility
  // stays local (presentation, not mode).
  const [planeListOpen, setPlaneListOpen] = useState(false)
  // SK-C1.0 Codex4 B1.3: the hovered canonical id while sketching — the
  // observable SK-E seam (hover-only; no reference is created).
  const [contextHover, setContextHover] = useState<{ kind: 'face' | 'edge'; id: string } | null>(null)
  const planeListOpenRef = useRef(false)
  planeListOpenRef.current = planeListOpen
  /** R6: the tree's edit-dimension entry — captures the authority tuple +
   *  the feature's CATALOGUED parameters at start. S3 lifts the former
   *  real-lane-only gate: the dev mock now models adjust_feature_parameter
   *  on catalogued parameters (mutating its mirror + regenerating the folded
   *  display and sketch_frames), so enabling it here stays honest. */
  const editFeatureEntry = {
    gate: authoringGate,
    start: (featureId: string) => {
      if (authoringGate) return
      const tuple = captureAuthoringTarget(partContext.getSnapshot())
      const part = partFacts.readyPart
      if (!tuple || !part) {
        setShellNote('the Part context is not ready')
        return
      }
      const feat = part.features.find((f) => f.id === featureId)
      // A3.6.2 (Petre's SP-06 ruling): the ✎ on a PLACED v2 sketch opens the
      // placement session seeded from its persisted record; a 0.2.0 legacy
      // sketch refuses honestly (its frame is immortal history per A3.1).
      if (feat && feat.kind === 'sketchV2' && feat.version === '0.2.2') {
        // ADR/0044 A4: the ✎ on a committed PROFILE sketch opens the Edit
        // session — baseline from the inspected record (id-form, byte-exact),
        // frame from the persisted placement via the A3.5 TS mirror (the
        // engine re-derives at commit; the preview echoes its own frame).
        if (!feat.placement || !feat.profile) {
          setShellNote('this profile sketch is missing its placement or profile block — refresh the Part')
          return
        }
        const { u, v, n } = derivePlacementFrame(feat.placement)
        const snap = partContext.getSnapshot()
        if (snap.partNumber === null) return
        profileLane.openEditSession(
          featureId,
          feat.profile,
          { origin: [0, 0, 0], u, v, normal: n },
          {
            workspaceId: currentWs?.workspaceId ?? null,
            partNumber: snap.partNumber,
            generation: snap.generation,
          },
        )
        return
      }
      if (feat && feat.kind === 'sketchV2') {
        if (feat.version !== '0.2.1' || !feat.placement) {
          setShellNote('this is a legacy (0.2.0) references sketch — its frame is fixed history; placement redefine applies to placed (0.2.1) sketches')
          return
        }
        authoringStore.startPlacementRedefine(
          featureId,
          {
            support: feat.placement.support.orientation,
            orientationRef: feat.placement.orientation_ref.orientation,
            orientation: feat.placement.orientation,
            normalSide: feat.placement.normal_side,
          },
          partContext.getSnapshot().generation,
          { number: part.number, name: part.name },
        )
        return
      }
      const parameters = feat && feat.kind !== 'sketch' ? feat.parameters : []
      if (parameters.length === 0) {
        setShellNote('this feature has no catalogued editable dimensions')
        return
      }
      authoringStore.startEditParameter(tuple, featureId, parameters)
    },
  }
  /** Entry B per feature (R3): extrude picks a plane then chains the contour
   *  pad; revolve pins plane=xy + tool=rectangle (the engine's v1 bounds) and
   *  skips the picker entirely. */
  const onNewChainedSketch = (feature: 'extrude' | 'revolve') => {
    if (feature === 'revolve') {
      const target = partFacts.readyPart
      authoringStore.beginChainedSketch(
        'xy',
        target ? { number: target.number, name: target.name } : null,
        'rectangle',
        partContext.getSnapshot().generation,
      )
    } else {
      const target = partFacts.readyPart
      authoringStore.startChainedPlanePick(
        partContext.getSnapshot().generation,
        'contour',
        target ? { number: target.number, name: target.name } : null,
      )
    }
  }
  // V-3 (Codex1 B1): ONE reference-import controller behind File -> Import,
  // the ribbon's Get Data, and the sidebar References list.
  const referenceImport = useReferenceImport(viewportApi)

  const onStartFeature = (kind: string) => {
    // V-3 (Codex1 B1): the TYPED dispatch kind — 'reference-import' commands
    // open the user-mediated picker; they never touch authoring sessions, so
    // the authoring gate does not apply (reference-only display lane).
    if (RIBBON_COMMANDS.find((c) => c.key === kind)?.dispatch === 'reference-import') {
      referenceImport.openPicker()
      return
    }
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
      {
        const target = partFacts.readyPart
        authoringStore.startPlanePick(
          {
            targetPart: target ? { number: target.number, name: target.name } : null,
            targetAuth: target ? captureAuthoringTarget(partContext.getSnapshot()) : null,
          },
          partContext.getSnapshot().generation,
        )
      }
    } else if (kind === 'profile-sketch') {
      // ADR/0044 A4 (Codex6 B2): the temporary CREATE entry. Enters the
      // shared plane-pick surface with the v1 store idle; the pick opens the
      // profile session directly — one lifecycle, never nested.
      const target = partFacts.readyPart
      if (!target) {
        setShellNote('Commit a Part first (New…) — a profile sketch draws on a Part')
        return
      }
      setProfilePick(true)
    } else if (kind === 'references-sketch') {
      // A3.6.1 / Codex1 B4 (pass sketch-place-1): References enters the ONE
      // placement session — support pick → the engine-default confirm panel
      // → explicit accept (which runs the persistent one-shot). The old
      // hard-coded-xy immediate commit is gone.
      const target = partFacts.readyPart
      if (!target) {
        setShellNote('Commit a Part first (New…) — References adds the v2 construction frame to a Part')
        return
      }
      authoringStore.startPlacementPick(
        partContext.getSnapshot().generation,
        { number: target.number, name: target.name },
      )
    } else if (kind === 'extrude' || kind === 'revolve') {
      // S2 B3 (UI eligibility from INSPECTED state): the real lane refuses
      // without a ready context or when the one-base rule already holds.
      if (window.aiadra || partFacts.readyPart) {
        if (!partFacts.readyPart) {
          setShellNote('Open or create a Part first — Extrude needs an inspected Part context')
          return
        }
        if (!partFacts.canExtrude) {
          setShellNote('a sequential extrude consumes a FACE-BOUND sketch — sketch on a face of the body first (or the Part has a revolve base)')
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
      // Entry A per feature: extrude accepts any unconsumed selected sketch;
      // revolve requires the EXACT decoded eligibility (P1 — simple_rectangle
      // + xy + a non-crossing axis); an ineligible selection falls to entry B.
      const selectedSketch =
        sel !== null && part !== null ? unconsumedSketches(part).find((sk) => sk.id === sel) : undefined
      const selectedIsUnconsumed =
        selectedSketch !== undefined &&
        (kind === 'extrude' || revolveSketchRefusal(selectedSketch) === null)
      // Codex3 B2 / Codex4 B1.4: the session CAPTURES the FULL authority
      // tuple {workspaceId, partNumber, generation} at start; the terminal
      // commit revalidates the exact tuple against the live context.
      authoringStore.startExtrude(
        selectedIsUnconsumed ? sel : null,
        captureAuthoringTarget(partContext.getSnapshot()),
        10,
        kind as 'extrude' | 'revolve',
      )
    } else if (kind === 'round' || kind === 'chamfer') {
      // R4 (D-R8): the session CAPTURES {tuple, selector, fact} at start by
      // resolving the LIVE selection against the CURRENT generation's facts —
      // fail closed; a later selection change never retargets.
      const captured = captureSelectorTarget(
        partContext.getSnapshot(),
        selectionStore.getSnapshot().selected,
        'sharp-edge',
      )
      if (typeof captured === 'string') {
        setShellNote(captured)
        return
      }
      authoringStore.startEdgeFeature(kind === 'round' ? 'fillet' : 'chamfer', captured)
    } else if (kind === 'hole') {
      // R5: the P1 base-domain predicate FIRST (a derived refusal, never a
      // doomed dashboard), then the face capture (D-R8).
      const part = partFacts.readyPart
      const baseRefusal = part ? holeBaseRefusal(part) : 'Hole needs an inspected Part context'
      if (baseRefusal) {
        setShellNote(baseRefusal)
        return
      }
      const captured = captureSelectorTarget(
        partContext.getSnapshot(),
        selectionStore.getSnapshot().selected,
        'face',
      )
      if (typeof captured === 'string') {
        setShellNote(captured)
        return
      }
      authoringStore.startHoleFeature(captured)
    }
  }

  /** The ONE adoption path — returns the refusal reason (null = adopted). */
  const switchWorkspace = async (ws: OpenedWorkspace): Promise<string | null> => {
    setShellNote(null)
    const reason = await switcher.adopt(ws)
    if (reason === null) setAppSession('modeling')
    return reason
  }

  const closeToHome = async (): Promise<boolean> => {
    setShellNote(null)
    const reason = await switcher.close()
    if (reason !== null) {
      setShellNote(reason)
      return false
    }
    // Codex2 B2: references are MODELING-SCOPED — clear every import (ready
    // AND in-flight, tombstoned through the session) BEFORE the viewport
    // tears down, so a row can never say ready against geometry no viewport
    // owns, and a late parse completion lands on a tombstone.
    referenceImport.clearAll()
    setAppSession('home')
    return true
  }

  // Two-sided session rule (arc 20260728-3): the active Part vanished from
  // the workspace listing — deleted outside this session (CLI, another
  // client). The stale context exits FAIL-CLOSED; if an operation gate holds
  // the close, its refusal reason surfaces instead and the next refresh
  // retries.
  const failClosedExit = async () => {
    const missing = pc.partNumber
    if (appSession !== 'modeling' || !missing) return
    if (await closeToHome()) {
      setShellNote(`${missing} was deleted outside this session — the model was closed (fail-closed)`)
    }
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
      if (!r.ok) {
        // Petre 2026-07-24: a REAL refusal (e.g. "not an AIADRA workspace")
        // must surface — only a user cancel stays silent. Nothing committed.
        if (r.error.message !== 'cancelled') setShellNote(r.error.message)
        return
      }
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
    // Codex3 N1: the DEFERRED install publishes its selector facts under the
    // SAME generation guard as the immediate path (one helper, both paths).
    void pendingDisplay.drain(installAndPublishFacts)
  }, [appSession, ready, viewportApi, partsRefresh, pendingDisplay, installAndPublishFacts])

  // The sketch-wire overlay (S2 D-S2): committed-but-unconsumed sketches show
  // as wires on their planes — derived from the SAME decoded Truth as the
  // tree, pushed on every partContext change (and on viewport mount).
  useEffect(() => {
    const push = () => {
      const s = partContext.getSnapshot()
      const part = s.inspection.status === 'ready' ? s.inspection.part : null
      viewportApi.current?.setSketchWires(
        part ? unconsumedSketches(part) : [],
        partContext.getSnapshot().selectorFacts?.sketchFrames,
      )
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
  // Codex26 B3: ONE persistent one-shot runner per backend — never a
  // per-click lifecycle (which would orphan a retained failed session and
  // defeat single-flight).
  const referencesRunner = useMemo(() => createOneShotRunner(featureBackend), [featureBackend])

  // sketch-ribbon-1: the ONE Sketch-view reorient (Codex10 B1 — the SUPPORT
  // is the sole frame authority), shared by the Sketch ribbon and the chrome.
  const sketchViewReturn = () => {
    const st = authoringStore.getSnapshot()
    if (st.mode === 'sketch') viewportApi.current?.sketchView(supportFrame(st.support))
  }

  // A3.6 (pass sketch-place-1): the placement session's EXPLICIT accept —
  // builds the create (full placement) or redefine (the DIFF only —
  // omission-keeps is the engine contract) op and runs the persistent
  // one-shot. Terminal hooks keep session + busy truth aligned.
  const acceptPlacement = () => {
    const s = authoringStore.getSnapshot()
    if (s.mode !== 'placement' || s.busy) return
    const target = s.targetPart
    if (!target) {
      authoringStore.failPlacement('no target Part — reopen the session')
      return
    }
    const wireSupport = { kind: 'principal' as const, orientation: s.support }
    const wireRef = { kind: 'principal' as const, orientation: s.orientationRef }
    let ops: ReturnType<typeof buildReferenceSketchOps>
    if (s.redefineOf) {
      const cur = s.redefineOf.current
      const members: Partial<PlacementOpInput> = {}
      if (s.support !== cur.support) members.support = wireSupport
      if (s.orientationRef !== cur.orientationRef) members.orientation_ref = wireRef
      if (s.orientation !== cur.orientation) members.orientation = s.orientation
      if (s.normalSide !== cur.normalSide) members.normal_side = s.normalSide
      if (Object.keys(members).length === 0) {
        authoringStore.failPlacement('nothing changed — adjust a member or cancel')
        return
      }
      ops = buildRedefinePlacementOps(target.number, s.redefineOf.featureId, members)
    } else {
      ops = buildReferenceSketchOps(target.number, {
        support: wireSupport,
        orientation_ref: wireRef,
        orientation: s.orientation,
        normal_side: s.normalSide,
      })
    }
    const startGen = partContext.getSnapshot().generation
    const startWs = switcher.current()?.workspaceId ?? null
    const started = referencesRunner.start(ops, target.number, {
      isStale: () => {
        const live = partContext.getSnapshot()
        const liveWs = switcher.current()?.workspaceId ?? null
        return live.generation !== startGen || liveWs !== startWs
      },
      onError: (m) => {
        setRefsBusy(false)
        authoringStore.failPlacement(m)
      },
      onStaleSuccess: (ref) => {
        setRefsBusy(false)
        authoringStore.setPlacementBusy(false)
        authoringStore.cancelPlacement()
        setShellNote(`placement committed to ${ref}, but the context changed — reopen it to see the frame`)
      },
      onSuccess: (res) => {
        setRefsBusy(false)
        authoringStore.setPlacementBusy(false)
        authoringStore.cancelPlacement()
        refreshPartContext(res.display as Parameters<typeof refreshPartContext>[0])
        setPartsRefresh((n) => n + 1)
        setShellNote(null)
      },
    })
    if (!started) {
      authoringStore.failPlacement('the previous placement commit is still running — wait for it to finish')
      return
    }
    setRefsBusy(true)
    authoringStore.setPlacementBusy(true)
  }
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
  // captured by descriptors. The display mode flows through the store (so toolbar,
  // and keyboard agree); fit/reset are imperative one-shots on the viewport API.
  const actions: CommandActions = useMemo(
    () => ({
      fit: () => viewportApi.current?.fit(),
      reset: () => viewportApi.current?.reset(),
      zoomBy: (f) => viewportApi.current?.zoomBy(f),
      setMode: (m) => viewStore.setMode(m),
      toggleDatums: () => viewStore.setDatumsVisible(!viewStore.getSnapshot().datumsVisible),
      toggleDatumFilter: (k) => viewStore.setDatumFilter(k, !viewStore.getSnapshot().datumFilters[k]),
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
  // SK-C1.0 S1: the viewport's interaction mode is DERIVED from the ONE
  // session (Codex3 bar 2 — the store owns pure state; the viewport owns the
  // imperative consequences). Principal frames are TS-known; face frames
  // arrive from the engine in S2/S3.
  // P (arc 20260717-2): the sketchSolicit ELIGIBLE set — the SAME derivation
  // the ExtrudePanel greys by (one rule, both consumers): unconsumed, with a
  // profile, sequential-eligible for the current Part state.
  const solicitEligibleIds = useMemo<ReadonlySet<string>>(() => {
    const part = partFacts.readyPart
    if (
      authoringSession.mode !== 'extrude'
      || authoringSession.step !== 'select'
      || authoringSession.feature !== 'extrude'
      || !part
    ) {
      return new Set<string>()
    }
    return eligibleExtrudeSketchIds(part)
  }, [authoringSession, partFacts.readyPart])

  const interactionMode = useMemo<SketchInteractionMode | null>(() => {
    // The profile session takes the surface while it is open — it is the one
    // mode that owns both the drawing plane and what is rendered on it.
    if (profileLane.mode !== null) return profileLane.mode
    // The Profile Sketch pick reuses the ONE planePick surface with the v1
    // store idle — the pick resolves into the profile lane, never into a
    // nested v1 session (Codex6 B2).
    if (profilePick) return { kind: 'planePick' }
    if (authoringSession.mode === 'planePick') return { kind: 'planePick' }
    if (
      authoringSession.mode === 'extrude'
      && authoringSession.step === 'select'
      && authoringSession.feature === 'extrude'
    ) {
      // P: the on-screen sketch pick — the list in the panel stays as the
      // keyboard/accessibility fallback feeding the same store transition.
      return { kind: 'sketchSolicit', eligibleIds: solicitEligibleIds }
    }
    if (authoringSession.mode === 'sketch') {
      return {
        kind: 'sketch',
        // S3 (Codex10 B1): the SUPPORT is the frame authority, through the
        // ONE projection — a face session draws on its mirror frame (the
        // engine re-derives at commit)
        frame: supportFrame(authoringSession.support),
        tool: authoringSession.tool,
        construction: authoringSession.construction,
      }
    }
    return null
  }, [authoringSession, solicitEligibleIds, profileLane.mode, profilePick])

  // A generation change INVALIDATES the whole pick→sketch interaction
  // FAIL-CLOSED (Codex4 B2) — a DISTINCT transition from user Escape/cancel:
  // it terminates to idle and never resurrects a captured chained session
  // from the old generation. The viewport unwinds (ghost/datums/overlay)
  // through the normal state transition.
  useEffect(() => {
    if (
      (authoringSession.mode === 'planePick' || authoringSession.mode === 'sketch') &&
      pc.generation !== authoringSession.generation
    ) {
      authoringStore.invalidateForGeneration()
    }
  }, [authoringSession, pc.generation, authoringStore])

  useEffect(() => {
    if (!ready) return
    const onKeyDown = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      const tag = t?.tagName
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA' || t?.isContentEditable) return
      // Escape routes to the active continuation FIRST (SK-C1.0 Codex1
      // B4.6): plane-pick cancels (restoring a chained base session); the
      // list dialog owns its own Escape; sketch mode's chrome owns its
      // cancel — only then does Escape clear the committed selection.
      if (e.key === 'Escape') {
        const mode = authoringStore.getSnapshot().mode
        if (mode === 'planePick') {
          if (!planeListOpenRef.current) {
            authoringStore.cancelPlanePick()
            e.preventDefault()
          }
          return
        }
        if (mode === 'sketch') return // the Sketch ribbon owns sketch Escape (the ONE keyboard owner)
        if (mode === 'placement') {
          // A3.6/B4: Escape cancels the pre-commit placement capture (a BUSY
          // session never cancels — the terminal is uninterruptible)
          authoringStore.cancelPlacement()
          e.preventDefault()
          return
        }
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
  // ONE open-workspace flow shared by the File menu, the Home ribbon, and the
  // Quick Access bar (was three inline copies).
  const openWorkspaceFlow = async () => {
    const r = await window.aiadra!.chooseWorkspace()
    if (!r.ok) {
      if (r.error.message !== 'cancelled') setShellNote(r.error.message)
      return
    }
    const reason = await switchWorkspace(r.result)
    if (reason !== null) setShellNote(reason)
  }
  // The Quick Access bar (Creo QAT benchmark): same gates + handlers as the
  // File menu — one behavior, two surfaces. Placement is a typed setting.
  const [qatBelowRibbon] = useSetting('qatBelowRibbon')
  const [gfxToolbarPos] = useSetting('graphicsToolbarPosition')
  // The navigator sash (Creo drag-resize; same pattern as the dock grip).
  const [navWidth, setNavWidth] = useSetting('navigatorWidth')
  const navDragging = useRef(false)
  const onNavGripDown = (e: React.PointerEvent) => {
    navDragging.current = true
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    const startX = e.clientX
    const startW = navWidth as number
    const move = (ev: PointerEvent) => {
      if (!navDragging.current) return
      setNavWidth(Math.min(640, Math.max(170, startW + (ev.clientX - startX))))
    }
    const up = () => {
      navDragging.current = false
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }
  const qatCommands: QatCommand[] = [
    {
      key: 'new',
      disabledReason: authoringGate,
      title: 'Create a new object (Part, …)',
      onClick: requestNew,
    },
    {
      key: 'open',
      disabledReason: !bridged ? 'Available in the desktop app' : uiGate,
      title: 'Open an AIADRA workspace folder',
      onClick: () => void openWorkspaceFlow(),
    },
    {
      key: 'import',
      disabledReason: appSession === 'modeling' ? null : IMPORT_HOME_REASON,
      title: 'External geometry - reference only, never Product Truth',
      onClick: () => referenceImport.openPicker(),
    },
    {
      key: 'close',
      disabledReason: appSession !== 'modeling' ? 'No model is open' : uiGate,
      title: 'Close the model and return Home',
      onClick: () => void closeToHome(),
    },
  ]
  const qatBar = <QuickAccessBar commands={qatCommands} />

  // WT-05: the active-part title (class-4 DERIVED projection, never stored):
  // `name (Active) — number`, number-only fallback, Home clears.
  const activePartNumber = appSession === 'modeling' ? pc.partNumber : null
  const activePartName = activePartNumber
    ? (wsParts.find((p) => p.object_number === activePartNumber)?.name ?? null)
    : null
  const titlebarText = shellTitle(activePartNumber, activePartName)
  useEffect(() => {
    document.title = titlebarText
  }, [titlebarText])
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
      onClick: () => void openWorkspaceFlow(),
    },
    {
      // V-3 (Codex1 B1): the ONE typed import entry — enabled only in the
      // modeling workspace; format-honest label per STEP_ENABLED.
      label: IMPORT_MENU_LABEL,
      enabled: appSession === 'modeling',
      title: appSession === 'modeling'
        ? 'External geometry - reference only, never Product Truth'
        : IMPORT_HOME_REASON,
      onClick: () => referenceImport.openPicker(),
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
      {/* The title bar (Creo chrome benchmark): the frame area itself — the
          app title in the LEFT corner, Quick Access following it (so a grown
          QAT never collides with the title), the OS overlay window controls
          on the right. Draggable except its controls. */}
      <header className="titlebar">
        <span className="titlebar-title">{titlebarText}</span>
        {qatBelowRibbon !== true && qatBar}
        {appSession === 'modeling' && fixtureBadge && (
          <span className="ref-badge small">{fixtureBadge}</span>
        )}
      </header>
      {/* The tab strip (Creo grammar): the green File button + the active
          ribbon's tab title, ABOVE the ribbon content row. */}
      <div className="ribbon-tabs">
        <FileMenu items={fileItems} />
        {appSession === 'home' ? (
          <span className="rtab active">Home</span>
        ) : sketchRibbonActive(authoringSession.mode, profileLane) ? (
          // pass sketch-ribbon-1: entering a sketch ADDS the dedicated Sketch
          // tab and activates it; Model stays visible but inactive. Codex7
          // B1: the PROFILE session selects the same tab — with the v1 store
          // idle by design, keying on it alone rendered the Model ribbon and
          // stranded the session with no tools and no terminal.
          <>
            <span className="rtab">Model</span>
            <span className="rtab active">Sketch</span>
          </>
        ) : (
          <span className="rtab active">Model</span>
        )}
      </div>
      {appSession === 'home' && (
        <>
          <HomeRibbon
            onNewPart={requestNew}
            onOpenWorkspace={() => void openWorkspaceFlow()}
            canOpenWorkspace={bridged && !uiGate}
          />
          {qatBelowRibbon === true && <div className="qat-row">{qatBar}</div>}
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
      {sketchRibbonActive(authoringSession.mode, profileLane) ? (
        // sketch-ribbon-1: the Sketch tab's ribbon REPLACES the Model ribbon
        // while the session is active (ADR/0040 D4 — one session, projected);
        // increment 2: the ribbon owns the whole surface incl. the Close
        // group's terminal lifecycle; the chrome is retired.
        <SketchRibbon
          store={authoringStore}
          backend={featureBackend}
          context={partContext}
          profile={{
            active: profileLane.active,
            closing: profileLane.closing,
            refusal: profileLane.refusal,
            toolKind: profileLane.session?.tool.kind ?? null,
            close: () => profileLane.close(),
            cancel: () => void profileLane.cancel(),
            setTool: (k) => profileLane.setTool(k),
            finishTool: (o) => profileLane.finishTool(o),
            undo: () => profileLane.undo(),
          }}
          onClose={() => {
            // Codex5 B1.1: sketch Cancel has NO candidate display to
            // discard — the canonical Part display stays installed.
          }}
          onCommitted={(info) => {
            // S2 / Codex3 B2: ONE transition — a fresh dev-lane Part is
            // ADOPTED (display + Truth together); features onto the context
            // Part REFRESH it with the commit's display.
            if (info.createdFresh) adoptPart(currentWs?.workspaceId ?? null, info.number, info.display)
            else refreshPartContext(info.display)
            setPartsRefresh((n) => n + 1)
          }}
          onSketchView={sketchViewReturn}
        />
      ) : (
      <ModelRibbon
        inputs={{
          realLane: !!window.aiadra,
          authoringGate,
          pc,
          selection: liveSelection,
          edgeKind: (id) => pc.selectorFacts?.edgeKinds.get(id) ?? null,
          faceExists: (id) => pc.selectorFacts?.faceIds.has(id) ?? false,
        }}
        onStart={onStartFeature}
      />
      )}
      {qatBelowRibbon === true && <div className="qat-row">{qatBar}</div>}
      {referenceImport.inputElement}
      <div className="workbench">
        {/* the wrap owns width + the sash; the aside scrolls independently */}
        <div className="sidebar-wrap" style={{ width: navWidth as number }}>
        <aside className="sidebar">
          {/* The tabbed navigator (Creo grammar): Model Tree / Workspace.
              A plane pick FORCES the Model Tree tab (its plane rows are an
              active pick surface); otherwise the user's choice stands, with
              part-load auto-switching handled where the part adopts. */}
          <NavigatorTabs active={navTab} onSelect={setNavTabChoice} />
          {fixtureError && <div className="small pad err">{fixtureError}</div>}
          {navTab === 'model' && (
            <>
              <ModelTreePanel
                session={authoringStore}
                context={partContext}
                onEditFeature={editFeatureEntry}
                onPlaneRow={
                  authoringSession.mode === 'planePick'
                    ? (ori) => authoringStore.resolvePlanePick(ori)
                    : null
                }
              />
              <div className="muted small pad">
                Create features from the <b>Model</b> ribbon above.
              </div>
              <ReferencesList imports={referenceImport} />
            </>
          )}
          {navTab === 'workspace' && (
            <>
              <EnginePanel
                ws={currentWs}
                onOpen={switchWorkspace}
                gate={uiGate}
                refresh={partsRefresh}
                loadedPart={pc.partNumber}
                onPartLoaded={(n) => adoptPart(currentWs?.workspaceId ?? null, n)}
                onParts={setWsParts}
                onRequestNew={requestNew}
                onActivePartMissing={() => void failClosedExit()}
              />
              <div className="panel-title">Properties</div>
              <div className="muted small pad">
                Windchill-style Product-Truth panel — placeholder.
              </div>
            </>
          )}
          <AppearancePanel />
        </aside>
        <div className="nav-grip" onPointerDown={onNavGripDown} title="Drag to resize" />
        </div>
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
                interactionMode={interactionMode}
                planarFaceIds={
                  // S3: faces are eligible only for the STANDALONE pick (a
                  // chained base profile cannot lie on a face — the engine
                  // refuses; the picker honestly never offers it)
                  authoringSession.mode === 'planePick' && authoringSession.continuation.type === 'sketch'
                    ? pc.selectorFacts?.planarFaceIds ?? new Set<string>()
                    : new Set<string>()
                }
                onPlanePick={(hit) => {
                  if (profilePick) {
                    // BS-1 principal-only domain: a face pick is not offered
                    // to the profile lane in I1 (same rule as placement).
                    if (hit.kind !== 'datum') return
                    setProfilePick(false)
                    const snap = partContext.getSnapshot()
                    if (snap.partNumber === null) return
                    const placement = {
                      support: { kind: 'principal' as const, orientation: hit.orientation },
                    }
                    profileLane.openCreateSession(
                      placement,
                      supportFrame({ kind: 'principal', orientation: hit.orientation }),
                      // the authority tuple, CAPTURED at open (Codex7 B2)
                      {
                        workspaceId: currentWs?.workspaceId ?? null,
                        partNumber: snap.partNumber,
                        generation: snap.generation,
                      },
                    )
                    return
                  }
                  if (hit.kind === 'datum') authoringStore.resolvePlanePick(hit.orientation)
                  else authoringStore.resolvePlanePick({ faceId: hit.faceId, frame: hit.frame })
                }}
                onSketchSolicit={(sketchId) => {
                  // P (Codex1 B3 -> Codex14 B2): terminal REVALIDATION derives
                  // eligibility from the LIVE inspection state read in THIS
                  // callback — never a render-captured set. A stale overlay
                  // click (consumed sketch, advanced Part) does nothing.
                  const st = authoringStore.getSnapshot()
                  const partSnap = partContext.getSnapshot()
                  if (st.mode !== 'extrude' || st.step !== 'select' || st.feature !== 'extrude') return
                  if (partSnap.inspection.status !== 'ready') return
                  if (!eligibleExtrudeSketchIds(partSnap.inspection.part).has(sketchId)) return
                  authoringStore.chooseCommittedSketch(sketchId)
                }}
                onSketchPlace={(uv) => {
                  // ONE surface, two lanes: the open profile session wins;
                  // otherwise the v1 pad keeps its behaviour verbatim.
                  if (profileLane.active) profileLane.place(uv)
                  else routeSketchPlacement(authoringStore, uv, partContext.getSnapshot().generation)
                }}
                onSketchCursor={(uv) => {
                  if (profileLane.active) profileLane.cursor(uv)
                  else authoringStore.setCursor(uv ? { x: uv.u, y: uv.v } : null)
                }}
                onContextHover={setContextHover}
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
            onNewSketch={onNewChainedSketch}
          />
          <EdgeFeaturePanel
            store={authoringStore}
            backend={featureBackend}
            context={partContext}
            onClose={restoreBase}
            onCommitted={(display) => {
              refreshPartContext(display)
              setPartsRefresh((n) => n + 1)
            }}
          />
          <HolePanel
            store={authoringStore}
            backend={featureBackend}
            context={partContext}
            onClose={restoreBase}
            onCommitted={(display) => {
              refreshPartContext(display)
              setPartsRefresh((n) => n + 1)
            }}
          />
          <EditParameterPanel
            store={authoringStore}
            backend={featureBackend}
            context={partContext}
            onClose={() => {
              // Codex5 B1.1 (same rule as SketchChrome): edit-dimension
              // Cancel has NO candidate display to discard — it previews
              // nothing, so the canonical Part display stays installed.
              // restoreBase (which nulls the dev-lane display) belongs to
              // the AI-candidate preview lane only. Exposed by D-S3.1
              // lifting the panel's real-lane-only gate.
            }}
            onCommitted={(display) => {
              refreshPartContext(display)
              setPartsRefresh((n) => n + 1)
            }}
          />
          {authoringSession.mode === 'planePick' && (
            <div className="pick-prompt">
              <span>
                {authoringSession.continuation.type === 'placement'
                  ? 'Select the SUPPORT plane for the references sketch — a principal datum plane'
                  : 'Select a sketch plane — a datum plane or a flat face of the Part'}
              </span>
              <button type="button" className="btn small" onClick={() => setPlaneListOpen(true)}>
                Choose from list…
              </button>
              <span className="muted small">Esc cancels</span>
            </div>
          )}
          <PlacementPanel store={authoringStore} isReal={featureBackend.isReal} onAccept={acceptPlacement} />
          {/* increment 2 (SR-08): the floating sketch chrome is RETIRED —
              the Sketch ribbon owns the tools + terminal; the statusbar's
              exclusive slot owns identity/prompt (the SketchStatusLine). */}
          {/* the mouse hint yields the bottom edge to a bottom-placed toolbar */}
          <div className={`hud muted small${gfxToolbarPos === 'bottom' ? ' hud-top' : ''}`}>middle = rotate · scroll = zoom · middle+shift = pan · middle+ctrl = zoom · left = select · right = menu</div>
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
        {/* B5 tenancy: the transient slot is EXCLUSIVE — shellNote replaces
            the sketch status line (which itself MERGES the hover readout);
            the slot owns truncation so the pill/chip never leave the screen. */}
        <span className="status-slot">
          {shellNote ? (
            <span className="small err">{shellNote}</span>
          ) : (
            <SketchStatusLine store={authoringStore} isReal={featureBackend.isReal} hover={contextHover} />
          )}
        </span>
        <span className="grow" />
        <span className="chipbar byo" title="AIADRA Core ships no AI — MVP-1 uses a scripted configurator">
          ● BYO-AI: scripted (MVP-1)
        </span>
      </div>
      <NewDialog open={newDialogOpen} onCancel={() => setNewDialogOpen(false)} onCreate={(c) => void createNew(c)} />
      <PlanePicker
        open={planeListOpen && authoringSession.mode === 'planePick'}
        onPick={(pl) => {
          setPlaneListOpen(false)
          authoringStore.resolvePlanePick(pl)
        }}
        onCancel={() => setPlaneListOpen(false)} // closing returns to pick mode
      />
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
    // the persisted startup mode (6a N3) applies on first viewport mount.
    viewStoreRef.current = createViewStateStore({
      mode: registry.get('defaultDisplayMode') as DisplayMode,
      datumsVisible: true, // the empty-part scaffold shows by default (EP1)
      datumFilters: { planes: true, fill: true, origin: true },
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
        // the persisted startup mode applies on the first viewport mount.
        viewStore.setMode(registry.get('defaultDisplayMode') as DisplayMode)
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
