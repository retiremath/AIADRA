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
import { eligibleExtrudeSketchIds, holeBaseRefusal, stackingRefusal, type InspectedPart } from './inspectDecode'

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

// ---- Presentation metadata (arc 20260716-1 V-2, Codex1 B4) ----------------
// PRESENTATION-ONLY: semantics stay in `derive` — none of this changes what a
// command does or when it enables. The dense Creo-benchmarked renderer, the
// addressability invariant test, and the icon map all read THIS data.

/** Every icon key the merged inline icon map must carry (drift is a test). */
export type IconKey =
  | 'regenerate' | 'get-data' | 'boolean-ops' | 'split-trim-body' | 'new-body'
  | 'datum-plane' | 'datum-axis' | 'datum-point' | 'datum-csys' | 'sketch'
  | 'extrude' | 'revolve' | 'sweep' | 'swept-blend'
  | 'hole' | 'round' | 'chamfer' | 'shell' | 'draft' | 'rib'
  | 'pattern' | 'mirror' | 'trim' | 'offset' | 'extend' | 'project'
  | 'thicken' | 'solidify' | 'merge' | 'intersect' | 'split' | 'remove'
  | 'unify' | 'boundary-blend' | 'fill' | 'style' | 'freestyle'
  | 'component-interface' | 'menu-more' | 'overflow'
  | 'fit' | 'reset' | 'display-style' | 'views' | 'sel-filter' | 'datums'
  | 'zoom-in' | 'zoom-out'

export type MenuFamilyId = 'body-ops' | 'editing-more' | 'surfaces-all' | 'model-intent-all'

/** A cell in a group's dense grid: anchors own a whole column (row 0 only);
 *  smalls stack up to three per column (rows 0–2). */
export interface RibbonSlot { column: number; row: number }

/**
 * B4's typed presentation record. One refinement over the contract sketch:
 * `slot` and `menu` are EXCLUSIVE alternatives (a menu member renders inside
 * its family's dropdown, so a grid cell of its own would be dead data) — the
 * addressability test enforces the XOR.
 */
export type RibbonPresentation =
  | { icon: IconKey; size: 'anchor' | 'small'; slot: RibbonSlot; menu?: undefined }
  | { icon: IconKey; size: 'small'; slot?: undefined; menu: { family: MenuFamilyId; order: number } }

/** A declared dropdown family: its trigger is a first-class ribbon cell; its
 *  members are commands whose `presentation.menu.family` names it. The
 *  trigger ALWAYS opens (mixed/disabled children never collapse it). */
export interface RibbonMenuFamily {
  id: MenuFamilyId
  label: string
  group: RibbonGroup
  icon: IconKey
  size: 'small'
  slot: RibbonSlot
}

export const RIBBON_MENU_FAMILIES: RibbonMenuFamily[] = [
  // Codex2 B4 (measured): the 1600 benchmark width must render ALL TEN groups
  // direct — the flat Body/Surfaces/Model Intent columns blew that budget, so
  // their commands live in declared families (the Creo pattern: dropdown
  // clusters), each child keeping its own tri-state + reason.
  { id: 'body-ops', label: 'Body Ops', group: 'Body', icon: 'boolean-ops', size: 'small', slot: { column: 0, row: 0 } },
  { id: 'editing-more', label: 'More', group: 'Editing', icon: 'menu-more', size: 'small', slot: { column: 2, row: 0 } },
  { id: 'surfaces-all', label: 'Surface', group: 'Surfaces', icon: 'boundary-blend', size: 'small', slot: { column: 0, row: 0 } },
  { id: 'model-intent-all', label: 'Intent', group: 'Model Intent', icon: 'component-interface', size: 'small', slot: { column: 0, row: 0 } },
]

const P = (icon: IconKey, size: 'anchor' | 'small', column: number, row = 0): RibbonPresentation =>
  ({ icon, size, slot: { column, row } })
const M = (icon: IconKey, family: MenuFamilyId, order: number): RibbonPresentation =>
  ({ icon, size: 'small', menu: { family, order } })

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
  /** V-2 dense-renderer placement (presentation-only; see RibbonPresentation). */
  presentation: RibbonPresentation
  /** V-3 (Codex1 B1): the TYPED action kind. Absent = 'authoring-session'
   *  (the default); 'reference-import' opens the user-mediated import picker
   *  — the ONE semantic exception, named here, no renderer special-casing. */
  dispatch?: 'reference-import'
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

const referencesSketchDerive = (i: RibbonInputs): CommandState => {
  const gate = gateRefusal(i)
  if (gate) return { state: 'state-disabled', reason: gate }
  // The one-shot v2 write commits against a Part on BOTH lanes.
  if (readyPart(i) === null) {
    return { state: 'state-disabled', reason: 'Commit a Part first (New…) — References adds the v2 construction frame to a Part' }
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
  // P (arc 20260717-2): the one-base rule is LIFTED for extrudes — the
  // engine's M thread supports sequential add (boss) and cut (pocket) on a
  // FACE-BOUND sketch. Revolve bodies stay out of the sequential domain.
  if (part.hasRevolveBase) {
    return { state: 'state-disabled', reason: 'the Part has a revolve base — sequential features on a revolve are a later slice' }
  }
  if (part.hasExtrudeBase) {
    if (eligibleExtrudeSketchIds(part).size === 0) {
      return {
        state: 'state-disabled',
        reason: 'a sequential extrude consumes a FACE-BOUND sketch — sketch on a face of the body first',
      }
    }
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
  { key: 'regenerate', label: 'Regenerate', group: 'Operations', derive: ROADMAP('arrives with the parametric-edit strand'), presentation: P('regenerate', 'anchor', 0) },
  // V-3 (Codex1 B1): Get Data FLIPS roadmap-disabled -> working with the
  // typed 'reference-import' dispatch — reference-only display, no session,
  // so no authoring gate. The ribbon exists only in the modeling workspace,
  // which is exactly the B1 availability predicate.
  { key: 'get-data', label: 'Get Data', group: 'Get Data', derive: () => ({ state: 'working' }), dispatch: 'reference-import', presentation: P('get-data', 'anchor', 0) },
  { key: 'boolean-ops', label: 'Boolean Operations', group: 'Body', derive: ROADMAP('arrives with the multi-body strand'), presentation: M('boolean-ops', 'body-ops', 0) },
  { key: 'split-trim-body', label: 'Split/Trim Body', group: 'Body', derive: ROADMAP('arrives with the multi-body strand'), presentation: M('split-trim-body', 'body-ops', 1) },
  { key: 'new-body', label: 'New Body', group: 'Body', derive: ROADMAP('arrives with the multi-body strand'), presentation: M('new-body', 'body-ops', 2) },
  // Datum — EP3 is its own design arc (D-R6); Sketch is live
  { key: 'datum-plane', label: 'Plane', group: 'Datum', derive: ROADMAP('user-created datums arrive with the EP3 datum arc'), presentation: P('datum-plane', 'small', 1, 0) },
  { key: 'datum-axis', label: 'Axis', group: 'Datum', derive: ROADMAP('user-created datums arrive with the EP3 datum arc'), presentation: P('datum-axis', 'small', 1, 1) },
  { key: 'datum-point', label: 'Point', group: 'Datum', derive: ROADMAP('user-created datums arrive with the EP3 datum arc'), presentation: P('datum-point', 'small', 1, 2) },
  { key: 'datum-csys', label: 'Coordinate System', group: 'Datum', derive: ROADMAP('user-created datums arrive with the EP3 datum arc'), presentation: P('datum-csys', 'small', 2, 0) },
  { key: 'sketch', label: 'Sketch', group: 'Datum', derive: sketchDerive, presentation: P('sketch', 'anchor', 0) },
  // Gate F2b (ADR/0044 A2): the slice-1 REFERENCES sketch — the first v2
  // (adapter 0.2.0) writer. One-shot op; needs a READY Part like sketch.
  { key: 'references-sketch', label: 'References', group: 'Datum', derive: referencesSketchDerive, presentation: P('sketch', 'small', 2, 1) },
  // ADR/0044 A4 (arc 20260730-1, Codex6 B2): the TEMPORARY Profile Sketch
  // CREATE entry — plane pick → the v2 profile drawing session, with the v1
  // authoring store idle throughout (the lifecycles never nest). I3 routes
  // ordinary Sketch here and retires this command.
  { key: 'profile-sketch', label: 'Profile Sketch', group: 'Datum', derive: referencesSketchDerive, presentation: P('sketch', 'small', 2, 2) },
  // Shapes
  { key: 'extrude', label: 'Extrude', group: 'Shapes', derive: extrudeDerive, presentation: P('extrude', 'anchor', 0) },
  { key: 'revolve', label: 'Revolve', group: 'Shapes', derive: revolveDerive, presentation: P('revolve', 'anchor', 1) },
  { key: 'sweep', label: 'Sweep', group: 'Shapes', derive: ROADMAP('arrives with the swept-features strand'), presentation: P('sweep', 'small', 2, 0) },
  { key: 'swept-blend', label: 'Swept Blend', group: 'Shapes', derive: ROADMAP('arrives with the swept-features strand'), presentation: P('swept-blend', 'small', 2, 1) },
  // Engineering
  { key: 'hole', label: 'Hole', group: 'Engineering', derive: holeDerive, presentation: P('hole', 'anchor', 0) },
  { key: 'round', label: 'Round', group: 'Engineering', derive: edgeFeatureDerive('Round'), presentation: P('round', 'small', 1, 0) },
  { key: 'chamfer', label: 'Chamfer', group: 'Engineering', derive: edgeFeatureDerive('Chamfer'), presentation: P('chamfer', 'small', 1, 1) },
  { key: 'shell', label: 'Shell', group: 'Engineering', derive: ROADMAP('arrives with the engineering-features strand'), presentation: P('shell', 'small', 1, 2) },
  { key: 'draft', label: 'Draft', group: 'Engineering', derive: ROADMAP('arrives with the engineering-features strand'), presentation: P('draft', 'small', 2, 0) },
  { key: 'rib', label: 'Rib', group: 'Engineering', derive: ROADMAP('arrives with the engineering-features strand'), presentation: P('rib', 'small', 2, 1) },
  // Pattern / Editing / Surfaces / Model Intent — roadmap strands
  { key: 'pattern', label: 'Pattern', group: 'Pattern', derive: ROADMAP('arrives with the pattern strand'), presentation: P('pattern', 'anchor', 0) },
  { key: 'mirror', label: 'Mirror', group: 'Editing', derive: ROADMAP('arrives with the editing strand'), presentation: P('mirror', 'small', 0, 0) },
  { key: 'trim', label: 'Trim', group: 'Editing', derive: ROADMAP('arrives with the editing strand'), presentation: P('trim', 'small', 0, 1) },
  { key: 'offset', label: 'Offset', group: 'Editing', derive: ROADMAP('arrives with the editing strand'), presentation: P('offset', 'small', 0, 2) },
  { key: 'extend', label: 'Extend', group: 'Editing', derive: ROADMAP('arrives with the editing strand'), presentation: P('extend', 'small', 1, 0) },
  { key: 'project', label: 'Project', group: 'Editing', derive: ROADMAP('arrives with the editing strand'), presentation: P('project', 'small', 1, 1) },
  { key: 'thicken', label: 'Thicken', group: 'Editing', derive: ROADMAP('arrives with the editing strand'), presentation: P('thicken', 'small', 1, 2) },
  { key: 'solidify', label: 'Solidify', group: 'Editing', derive: ROADMAP('arrives with the editing strand'), presentation: M('solidify', 'editing-more', 0) },
  { key: 'merge', label: 'Merge', group: 'Editing', derive: ROADMAP('arrives with the editing strand'), presentation: M('merge', 'editing-more', 1) },
  { key: 'intersect', label: 'Intersect', group: 'Editing', derive: ROADMAP('arrives with the editing strand'), presentation: M('intersect', 'editing-more', 2) },
  { key: 'split', label: 'Split', group: 'Editing', derive: ROADMAP('arrives with the editing strand'), presentation: M('split', 'editing-more', 3) },
  { key: 'remove', label: 'Remove', group: 'Editing', derive: ROADMAP('arrives with the editing strand'), presentation: M('remove', 'editing-more', 4) },
  { key: 'unify', label: 'Unify', group: 'Editing', derive: ROADMAP('arrives with the surfacing strand'), presentation: M('unify', 'editing-more', 5) },
  { key: 'boundary-blend', label: 'Boundary Blend', group: 'Surfaces', derive: ROADMAP('arrives with the surfacing strand'), presentation: M('boundary-blend', 'surfaces-all', 0) },
  { key: 'fill', label: 'Fill', group: 'Surfaces', derive: ROADMAP('arrives with the surfacing strand'), presentation: M('fill', 'surfaces-all', 1) },
  { key: 'style', label: 'Style', group: 'Surfaces', derive: ROADMAP('arrives with the surfacing strand'), presentation: M('style', 'surfaces-all', 2) },
  { key: 'freestyle', label: 'Freestyle', group: 'Surfaces', derive: ROADMAP('arrives with the surfacing strand'), presentation: M('freestyle', 'surfaces-all', 3) },
  { key: 'component-interface', label: 'Component Interface', group: 'Model Intent', derive: ROADMAP('arrives with the model-intent strand'), presentation: M('component-interface', 'model-intent-all', 0) },
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

/**
 * The B4 responsive fold (pure; benchmark width 1600 CSS px, supported
 * minimum 1200): how many LEADING groups render directly, given each group's
 * measured width. The rest fold — as a suffix, never a hole — into the `»`
 * overflow menu, whose trigger width must also fit. Clipping is banned; at
 * least one group always stays direct. Unmeasured widths (0 — e.g. jsdom or
 * the first pre-measure render) fold nothing.
 */
export function visibleGroupCount(available: number, widths: number[], overflowWidth: number): number {
  const total = widths.reduce((a, b) => a + b, 0)
  if (total <= available || total === 0) return widths.length
  let used = overflowWidth
  let n = 0
  for (const w of widths) {
    if (used + w > available) break
    used += w
    n += 1
  }
  return Math.max(1, n)
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
