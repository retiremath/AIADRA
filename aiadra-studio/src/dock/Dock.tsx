/**
 * The CAD↔AI dock (arc 20260711-10 / MVP-1; ADR/0040 D5).
 *
 * A first-class resizable/dismissable right-docked panel — a PROJECTION of the
 * operation-session store (never its owner; ADR/0040 D4/N2). The drag handle on
 * its inner edge is the "AI-is-a-spectrum" principle made physical. Tabs:
 * Design (session-coupled) + Home/Catalogs (browse stubs). Dismissing hides the
 * panel but NEVER cancels the session (the presence invariant lives in the
 * status-strip pill — ADR/0040 D5 B1). The Design tab is the elicit → propose →
 * refine loop over the scripted bracket configurator.
 */
import { useRef, useState, type ReactNode } from 'react'
import {
  BRACKET_ELICITATION,
  BRACKET_PARAMS,
  createBracketConfigurator,
  type ParamDescriptor,
} from '../authoring/brackets'
import { CatalogsStub } from '../home/HomeShared'
import { selectedCandidate, useOperation, type Candidate, type OperationStore } from '../operation/store'

const DOCK_MIN = 260
const DOCK_MAX = 640

/** Start (or restart) the bracket session — the ONE path the dock button and the
 *  `operations` command both call, so both create the same operation session. */
export function startBracketSession(store: OperationStore): void {
  store.start(createBracketConfigurator())
}

/**
 * The AI design entry — "What do you want to design?" (ADR/0039 elicitation;
 * ADR/0040 D5). ONE component rendered in BOTH places (Codex6 guardrail): the
 * dock's idle Design tab AND the Home state's center surface — never a second
 * disconnected AI mode.
 */
export function DesignHero({ onStart, gate = null }: { onStart: () => void; gate?: string | null }) {
  return (
    <div className="dock-hero">
      <div className="dock-eyebrow">AI-native design</div>
      <h2>What do you want to design?</h2>
      <p className="muted small">
        Describe a part and AIADRA proposes real, buildable candidates — every option is a
        validated recipe, never a mockup.
      </p>
      <button
        className="btn primary"
        type="button"
        disabled={!!gate}
        title={gate ?? undefined}
        onClick={() => !gate && onStart()}
      >
        New flat bracket…
      </button>
      <div className="muted small pad">More configurators arrive as the vocabulary grows.</div>
    </div>
  )
}

function HolePattern({ id }: { id: string }) {
  // A tiny schematic per candidate so the gallery reads at a glance (the real
  // evaluated geometry previews in the viewport on select).
  const holes: Record<string, [number, number][]> = {
    'bracket-corners': [
      [16, 14],
      [48, 14],
      [16, 30],
      [48, 30],
    ],
    'bracket-grid': [
      [24, 15],
      [40, 15],
      [24, 29],
      [40, 29],
    ],
    'bracket-inline': [
      [22, 22],
      [42, 22],
    ],
  }
  return (
    <svg width="64" height="44" viewBox="0 0 64 44" aria-hidden="true">
      <rect x="6" y="8" width="52" height="28" rx="2" className="cand-plate" />
      {(holes[id] ?? []).map(([cx, cy], i) => (
        <circle key={i} cx={cx} cy={cy} r="3.2" className="cand-hole" />
      ))}
    </svg>
  )
}

function ParamSlider({
  p,
  value,
  onChange,
}: {
  p: ParamDescriptor
  value: number
  onChange: (v: number) => void
}) {
  return (
    <label className="param-row small">
      <span className="muted">
        {p.label} <span className="param-unit">{p.unit === 'mm' ? 'mm' : ''}</span>
      </span>
      <span className="param-ctl">
        <input
          type="range"
          min={p.min}
          max={p.max}
          step={p.step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
        />
        <span className="param-val">{value}</span>
      </span>
    </label>
  )
}

function DesignTab({ store, startGate = null }: { store: OperationStore; startGate?: string | null }) {
  const op = useOperation(store)
  const sel = selectedCandidate(op)

  if (op.phase === 'idle') {
    // The AI-session start is an operation start — gated during a workspace
    // transition (Codex3 B1).
    return <DesignHero onStart={() => startBracketSession(store)} gate={startGate} />
  }

  return (
    <div className="dock-op">
      <div className="op-eyebrow">
        Operation · <span className="op-name">{op.configuratorName}</span>
      </div>

      {/* Elicitation cards (concept-owned questions) */}
      {BRACKET_ELICITATION.map((q) => (
        <div key={q.id} className="qcard">
          <div className="q small">{q.prompt}</div>
          <div className="qopts">
            {q.options.map((o) => (
              <button
                key={o.value}
                type="button"
                className={`qopt ${op.answers[q.id] === o.value ? 'sel' : ''}`}
                onClick={() => store.answer(q.id, o.value)}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>
      ))}

      {/* Candidate gallery — real evaluated recipes (preview on select) */}
      <div className="cand-title small">Candidates · pick one</div>
      <div className="cands">
        {op.candidates.map((c: Candidate) => (
          <button
            key={c.id}
            type="button"
            className={`cand ${c.id === op.selectedCandidateId ? 'sel' : ''}`}
            onClick={() => store.selectCandidate(c.id)}
          >
            <span className="cand-thumb">
              <HolePattern id={c.id} />
            </span>
            <span className="cand-meta">
              <span className="cand-name">{c.label}</span>
              <span className="cand-dim">Ø{c.params.holeDia_mm}</span>
            </span>
          </button>
        ))}
      </div>

      {/* Provenance strip (ADR/0040 D8) — transient, never Product Truth */}
      {sel && (
        <div className="prov">
          <div className="prov-row">
            <span className="k">source</span>
            <span className="v">{sel.provenance.sourceConfigurator}</span>
          </div>
          <div className="prov-row">
            <span className="k">validated</span>
            <span className="v ok">✓ {sel.validationStatus}</span>
          </div>
          <div className="prov-row">
            <span className="k">state</span>
            <span className="v warn">transient candidate</span>
          </div>
        </div>
      )}

      {/* Parameter controls (canonical mm; refine re-proposes) */}
      <div className="cand-title small">Parameters</div>
      {BRACKET_PARAMS.map((p) => (
        <ParamSlider
          key={p.key}
          p={p}
          value={op.params[p.key] ?? p.default}
          onChange={(v) => store.setParam(p.key, v)}
        />
      ))}

      <div className="op-actions">
        <button className="btn" type="button" onClick={() => store.cancel()}>
          Cancel
        </button>
        <button className="btn primary" type="button" disabled title="Commits a Part — MVP-2">
          Accept → commit (soon)
        </button>
      </div>
    </div>
  )
}

type Tab = 'design' | 'home' | 'catalogs'

export function Dock({
  store,
  width,
  onWidthChange,
  onDismiss,
  homeTab,
  startGate = null,
}: {
  store: OperationStore
  width: number
  onWidthChange: (w: number) => void
  onDismiss: () => void
  /** The SAME WorkspaceStart surface the Home state renders (Codex6 guardrail
   *  — one component family, dock-hosted here). */
  homeTab?: ReactNode
  /** Operation-start gate (active work / workspace transition — Codex3 B1). */
  startGate?: string | null
}) {
  const [tab, setTab] = useState<Tab>('design')
  const dragging = useRef(false)

  // Resize: dragging the inner (left) edge widens/narrows the dock. Pointer
  // capture keeps the drag alive off the handle.
  const onHandleDown = (e: React.PointerEvent) => {
    dragging.current = true
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    const startX = e.clientX
    const startW = width
    const move = (ev: PointerEvent) => {
      if (!dragging.current) return
      const next = Math.min(DOCK_MAX, Math.max(DOCK_MIN, startW + (startX - ev.clientX)))
      onWidthChange(next)
    }
    const up = () => {
      dragging.current = false
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }

  return (
    <aside className="ai-dock" style={{ width }}>
      <div className="dock-grip" onPointerDown={onHandleDown} title="Drag to resize" />
      <div className="dock-tabs">
        <button type="button" className={`dtab ${tab === 'design' ? 'sel' : ''}`} onClick={() => setTab('design')}>
          Design
        </button>
        <button type="button" className={`dtab ${tab === 'home' ? 'sel' : ''}`} onClick={() => setTab('home')}>
          Home
        </button>
        <button type="button" className={`dtab ${tab === 'catalogs' ? 'sel' : ''}`} onClick={() => setTab('catalogs')}>
          Catalogs&nbsp;&amp;&nbsp;KB
        </button>
        <button type="button" className="dock-x" title="Hide the dock (the session stays active)" onClick={onDismiss}>
          ✕
        </button>
      </div>
      <div className="dock-body">
        {tab === 'design' && <DesignTab store={store} startGate={startGate} />}
        {tab === 'home' &&
          (homeTab ?? <div className="muted small pad">Home — recent workspaces &amp; start.</div>)}
        {tab === 'catalogs' && <CatalogsStub />}
      </div>
    </aside>
  )
}
