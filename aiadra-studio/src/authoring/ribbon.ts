/**
 * The Model-ribbon taxonomy (arc 20260715-1 D-R1/D-R10) — the Creo 10 Model
 * tab, benchmarked never cloned (ADR/0033 D1): the WHOLE vocabulary renders,
 * and every command carries exactly ONE derived state:
 *
 *  - `working`          — enabled; dispatches an authoring session;
 *  - `state-disabled`   — implemented, but the CURRENT state disallows it;
 *                         greyed with the DERIVED reason as tooltip;
 *  - `roadmap-disabled` — not built; greyed with an honest strand tooltip.
 *
 * The taxonomy is DATA: this one table drives the ribbon (and later menus/
 * keyboard). NOTHING renders `working` unless its full contract path
 * (allowlist → bridge → engine → session UI) exists — commands whose slices
 * land later in this arc stay `roadmap-disabled` until their slice flips
 * them. Lane-aware per Codex1 B4: the dev mock never lies (Codex2 N4 wording).
 */
import type { PartContextState } from './partContext'
import { authoringFacts, authoringStartRefusal } from './partContext'
import { holeBaseRefusal, stackingRefusal, type InspectedPart } from './inspectDecode'

export type RibbonGroup =
  | 'Operations'
  | 'Get Data'
  | 'Body'
  | 'Datum'
  | 'Shapes'
  | 'Engineering'
  | 'Pattern'
  | 'Editing'
  | 'Surfaces'
  | 'Model Intent'

export type CommandState =
  | { state: 'working' }
  | { state: 'state-disabled'; reason: string }
  | { state: 'roadmap-disabled'; reason: string }

export interface RibbonInputs {
  /** true = the desktop real-engine lane; false = browser dev (mock). */
  realLane: boolean
  /** The ONE shared authoring-start gate (S2 Codex5 B1.2), or null. */
  authoringGate: string | null
  /** The generation-owned Part context snapshot. */
  pc: PartContextState
  /** The current canonical selection (transient UI state; capture happens at
   *  session start against selectorFacts — this only drives enablement). */
  selection: { kind: 'edge' | 'face'; id: string } | null
  /** Generation-bound facts for the CURRENT display (D-R8; null pre-R4). */
  edgeKind?: (edgeId: string) => string | null
  /** Does a face id exist on the CURRENT display's facts? (Codex3 B1.2). */
  faceExists?: (faceId: string) => boolean
}

export interface RibbonCommand {
  key: string
  /** The operator-facing label (benchmark vocabulary — Codex1 N2: "Round"). */
  label: string
  group: RibbonGroup
  derive: (i: RibbonInputs) => CommandState
}

const ROADMAP = (reason: string) => (): CommandState => ({ state: 'roadmap-disabled', reason })
const DEV_LANE_TOPO = 'requires the desktop real-engine lane (canonical topology selection)'

function readyPart(i: RibbonInputs): InspectedPart | null {
  return authoringFacts(i.pc).readyPart
}

/** The shared preamble every working command runs: the authoring gate, then
 *  the targeted-non-ready policy (already inside authoringGate via
 *  authoringStartRefusal at the App level — re-derived here so the taxonomy
 *  is self-contained for tests). */
function gateRefusal(i: RibbonInputs): string | null {
  return i.authoringGate ?? authoringStartRefusal(i.pc)
}

const sketchDerive = (i: RibbonInputs): CommandState => {
  const gate = gateRefusal(i)
  if (gate) return { state: 'state-disabled', reason: gate }
  if (i.realLane && readyPart(i) === null) {
    return { state: 'state-disabled', reason: 'Create or open a Part first (New…)' }
  }
  return { state: 'working' }
}

const extrudeDerive = (i: RibbonInputs): CommandState => {
  const gate = gateRefusal(i)
  if (gate) return { state: 'state-disabled', reason: gate }
  const part = readyPart(i)
  // Codex3 B1.3: BOTH lanes need a ready Part — the base-feature panels
  // require one at commit, so a dev no-Part session would be a dead end.
  if (!part) return { state: 'state-disabled', reason: 'Commit a Part first (New…) — Extrude adds to a Part' }
  if (part.hasExtrudeBase || part.hasRevolveBase) {
    return { state: 'state-disabled', reason: 'the Part already has a base creation feature (one per Part in v1)' }
  }
  return { state: 'working' }
}

/** Revolve (D-R9; flips from roadmap when slice R3 lands): base rules like
 *  Extrude, PLUS at least one eligible simple-rectangle xy sketch OR the
 *  chained rectangle path (always offered). */
// R3/R4/R5 flip these to full derivations when their slice lands — until
// then they are HONESTLY roadmap-disabled (nothing enables without its full
// contract path). The dev-lane wording for topology-selection features is
// pinned here so the flips reuse it (Codex2 N4).
export const LANE_TOPO_REASON = DEV_LANE_TOPO
/** Revolve (R3, LIVE): extrude-like base rules — entry B (the chained
 *  rectangle) keeps it working whenever a base creation is still allowed;
 *  per-sketch/axis eligibility lives in the panel (the P1 facts). */
const revolveDerive = (i: RibbonInputs): CommandState => {
  const gate = gateRefusal(i)
  if (gate) return { state: 'state-disabled', reason: gate }
  const part = readyPart(i)
  // Codex3 B1.3: both lanes need a ready Part (see extrudeDerive).
  if (!part) return { state: 'state-disabled', reason: 'Commit a Part first (New…) — Revolve adds to a Part' }
  if (part.hasExtrudeBase || part.hasRevolveBase) {
    return { state: 'state-disabled', reason: 'the Part already has a base creation feature (one per Part in v1)' }
  }
  return { state: 'working' }
}
/** Round/Chamfer (R4, LIVE): real lane only (the mock has no canonical
 *  topology to select — D-R10/N4); need a ready EXTRUDED base and a selected
 *  SHARP edge on the CURRENT display's generation-bound facts. */
const edgeFeatureDerive = (label: string) => (i: RibbonInputs): CommandState => {
  const gate = gateRefusal(i)
  if (gate) return { state: 'state-disabled', reason: gate }
  if (!i.realLane) return { state: 'state-disabled', reason: DEV_LANE_TOPO }
  const part = readyPart(i)
  if (!part) return { state: 'state-disabled', reason: `${label} needs an inspected Part context` }
  if (!part.hasExtrudeBase || part.hasRevolveBase) {
    return { state: 'state-disabled', reason: `${label} needs an EXTRUDED base (v1)` }
  }
  const stacking = stackingRefusal(part)
  if (stacking) return { state: 'state-disabled', reason: stacking }
  if (!i.selection || i.selection.kind !== 'edge') {
    return { state: 'state-disabled', reason: `select an edge, then ${label}` }
  }
  const kind = i.edgeKind?.(i.selection.id) ?? null
  if (kind === null) return { state: 'state-disabled', reason: 'the selected edge is not on the current display' }
  if (kind !== 'sharp') return { state: 'state-disabled', reason: `the selected edge is ${kind} — need a SHARP edge` }
  return { state: 'working' }
}
/** Hole (R5, LIVE): real lane only; the P1 base-domain predicate (extruded
 *  from EXACTLY one rectangle; no prior hole) + a face selected on the
 *  CURRENT display. Wall-vs-cap stays an engine refusal after the panel
 *  opens (P2's named limitation — the display has no cap classification). */
const holeDerive = (i: RibbonInputs): CommandState => {
  const gate = gateRefusal(i)
  if (gate) return { state: 'state-disabled', reason: gate }
  if (!i.realLane) return { state: 'state-disabled', reason: DEV_LANE_TOPO }
  const part = readyPart(i)
  if (!part) return { state: 'state-disabled', reason: 'Hole needs an inspected Part context' }
  const base = holeBaseRefusal(part)
  if (base) return { state: 'state-disabled', reason: base }
  if (!i.selection || i.selection.kind !== 'face') {
    return { state: 'state-disabled', reason: 'select a flat cap face, then Hole' }
  }
  if (!(i.faceExists?.(i.selection.id) ?? false)) {
    return { state: 'state-disabled', reason: 'the selected face is not on the current display' }
  }
  return { state: 'working' }
}

export const RIBBON_COMMANDS: RibbonCommand[] = [
  // Operations / Get Data / Body — roadmap strands
  { key: 'regenerate', label: 'Regenerate', group: 'Operations', derive: ROADMAP('arrives with the parametric-edit strand') },
  { key: 'get-data', label: 'Get Data', group: 'Get Data', derive: ROADMAP('arrives with the import/interchange strand') },
  { key: 'boolean-ops', label: 'Boolean Operations', group: 'Body', derive: ROADMAP('arrives with the multi-body strand') },
  { key: 'split-trim-body', label: 'Split/Trim Body', group: 'Body', derive: ROADMAP('arrives with the multi-body strand') },
  { key: 'new-body', label: 'New Body', group: 'Body', derive: ROADMAP('arrives with the multi-body strand') },
  // Datum — EP3 is its own design arc (D-R6); Sketch is live
  { key: 'datum-plane', label: 'Plane', group: 'Datum', derive: ROADMAP('user-created datums arrive with the EP3 datum arc') },
  { key: 'datum-axis', label: 'Axis', group: 'Datum', derive: ROADMAP('user-created datums arrive with the EP3 datum arc') },
  { key: 'datum-point', label: 'Point', group: 'Datum', derive: ROADMAP('user-created datums arrive with the EP3 datum arc') },
  { key: 'datum-csys', label: 'Coordinate System', group: 'Datum', derive: ROADMAP('user-created datums arrive with the EP3 datum arc') },
  { key: 'sketch', label: 'Sketch', group: 'Datum', derive: sketchDerive },
  // Shapes
  { key: 'extrude', label: 'Extrude', group: 'Shapes', derive: extrudeDerive },
  { key: 'revolve', label: 'Revolve', group: 'Shapes', derive: revolveDerive },
  { key: 'sweep', label: 'Sweep', group: 'Shapes', derive: ROADMAP('arrives with the swept-features strand') },
  { key: 'swept-blend', label: 'Swept Blend', group: 'Shapes', derive: ROADMAP('arrives with the swept-features strand') },
  // Engineering
  { key: 'hole', label: 'Hole', group: 'Engineering', derive: holeDerive },
  { key: 'round', label: 'Round', group: 'Engineering', derive: edgeFeatureDerive('Round') },
  { key: 'chamfer', label: 'Chamfer', group: 'Engineering', derive: edgeFeatureDerive('Chamfer') },
  { key: 'shell', label: 'Shell', group: 'Engineering', derive: ROADMAP('arrives with the engineering-features strand') },
  { key: 'draft', label: 'Draft', group: 'Engineering', derive: ROADMAP('arrives with the engineering-features strand') },
  { key: 'rib', label: 'Rib', group: 'Engineering', derive: ROADMAP('arrives with the engineering-features strand') },
  // Pattern / Editing / Surfaces / Model Intent — roadmap strands
  { key: 'pattern', label: 'Pattern', group: 'Pattern', derive: ROADMAP('arrives with the pattern strand') },
  { key: 'mirror', label: 'Mirror', group: 'Editing', derive: ROADMAP('arrives with the editing strand') },
  { key: 'trim', label: 'Trim', group: 'Editing', derive: ROADMAP('arrives with the editing strand') },
  { key: 'offset', label: 'Offset', group: 'Editing', derive: ROADMAP('arrives with the editing strand') },
  { key: 'extend', label: 'Extend', group: 'Editing', derive: ROADMAP('arrives with the editing strand') },
  { key: 'project', label: 'Project', group: 'Editing', derive: ROADMAP('arrives with the editing strand') },
  { key: 'thicken', label: 'Thicken', group: 'Editing', derive: ROADMAP('arrives with the editing strand') },
  { key: 'solidify', label: 'Solidify', group: 'Editing', derive: ROADMAP('arrives with the editing strand') },
  { key: 'merge', label: 'Merge', group: 'Editing', derive: ROADMAP('arrives with the editing strand') },
  { key: 'intersect', label: 'Intersect', group: 'Editing', derive: ROADMAP('arrives with the editing strand') },
  { key: 'split', label: 'Split', group: 'Editing', derive: ROADMAP('arrives with the editing strand') },
  { key: 'remove', label: 'Remove', group: 'Editing', derive: ROADMAP('arrives with the editing strand') },
  { key: 'unify', label: 'Unify', group: 'Editing', derive: ROADMAP('arrives with the surfacing strand') },
  { key: 'boundary-blend', label: 'Boundary Blend', group: 'Surfaces', derive: ROADMAP('arrives with the surfacing strand') },
  { key: 'fill', label: 'Fill', group: 'Surfaces', derive: ROADMAP('arrives with the surfacing strand') },
  { key: 'style', label: 'Style', group: 'Surfaces', derive: ROADMAP('arrives with the surfacing strand') },
  { key: 'freestyle', label: 'Freestyle', group: 'Surfaces', derive: ROADMAP('arrives with the surfacing strand') },
  { key: 'component-interface', label: 'Component Interface', group: 'Model Intent', derive: ROADMAP('arrives with the model-intent strand') },
]

export const RIBBON_GROUP_ORDER: RibbonGroup[] = [
  'Operations', 'Get Data', 'Body', 'Datum', 'Shapes', 'Engineering',
  'Pattern', 'Editing', 'Surfaces', 'Model Intent',
]

export function deriveCommandState(key: string, inputs: RibbonInputs): CommandState {
  const cmd = RIBBON_COMMANDS.find((c) => c.key === key)
  if (!cmd) return { state: 'roadmap-disabled', reason: `unknown command ${key}` }
  return cmd.derive(inputs)
}

/** Every roadmap tooltip must be non-empty and name a strand (Codex1 N3). */
export function roadmapTooltipGaps(): string[] {
  return RIBBON_COMMANDS.filter((c) => {
    const st = c.derive({
      realLane: true,
      authoringGate: null,
      pc: { workspaceId: null, partNumber: null, generation: 0, inspection: { status: 'idle' }, selectorFacts: null },
      selection: null,
    })
    return st.state === 'roadmap-disabled' && !/arrives? (with|later)/.test(st.reason)
  }).map((c) => c.key)
}
