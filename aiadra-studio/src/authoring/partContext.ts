/**
 * ONE generation-owned Part context (S2; arc 20260714-3 Codex1 B2).
 *
 * The single authority for "which Part is this modeling session about and
 * what does Truth say about it": display, model tree, sketch-wire overlay,
 * authoring target, and Extrude eligibility ALL read here — never their own
 * copy of the Part's state (EP1's featureCount bookkeeping is retired).
 *
 * Lifecycle discipline (Codex2 build bars):
 *  - every context change ADVANCES the generation FIRST; an in-flight refresh
 *    from an older generation lands in the void (never installs);
 *  - inspection is fail-closed: `loading` and `error` states refuse authoring
 *    eligibility — a tree/target is only trustworthy in `ready`;
 *  - the store is the one writer; callers get an immutable snapshot.
 */
import { decodeInspectedPart, stackingRefusal, type InspectedPart } from './inspectDecode'

/** Generation-bound facts about the CURRENT canonical display (arc
 *  20260715-1 D-R8 / Codex1 B1): what the topology-selection features may
 *  capture against. Derived at display INSTALL inside the ONE transition;
 *  they die with the generation — a selector id from an older display can
 *  never qualify. */
export interface SelectorFacts {
  /** display edge_id → its contract `kind` (sharp/tangent/seam/…). */
  edgeKinds: ReadonlyMap<string, string>
  /** The face ids present on THIS display. */
  faceIds: ReadonlySet<string>
}

export type Inspection =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; part: InspectedPart }
  | { status: 'error'; message: string }

export interface PartContextState {
  workspaceId: string | null
  partNumber: string | null
  generation: number
  inspection: Inspection
  /** null until THIS generation's display installed and published its facts. */
  selectorFacts: SelectorFacts | null
}

/** Fetch the raw inspect view for a Part (the lane decides how). */
export type InspectFetcher = (partNumber: string) => Promise<unknown>

/** Everything one canonical Part adoption does (Codex3 B2 — ONE transition,
 *  never display-then-context coordinated by timing). */
export interface PartAdoptionIO {
  fetchInspect: InspectFetcher
  /**
   * Install the canonical display for this Part. Runs INSIDE the transition:
   * implementations must consult `stillCurrent()` before installing (a stale
   * adoption must not publish anything — including a display DEFERRED past
   * viewport mount, Codex4 B1.5). Optional — a refresh that keeps the
   * viewport as-is passes none. The viewport's own load token remains defense
   * in depth, never the authority split.
   */
  installDisplay?: (stillCurrent: () => boolean) => Promise<void>
  /**
   * Runs SYNCHRONOUSLY at the transition-start boundary, before any async
   * work (Codex4 B1.3) — the Workbench clears canonical face/edge selection
   * and the tree's selected sketch here, because feature ids are only
   * list-addressable WITHIN a Part: A's `feat_0001` must never alias B's.
   */
  onTransitionStart?: () => void
}

export interface PartContextStore {
  subscribe(cb: () => void): () => void
  getSnapshot(): PartContextState
  /**
   * THE canonical Part transition: adopt a Part and run its display + inspect
   * work under ONE generation. The generation advances and `loading` publishes
   * SYNCHRONOUSLY (selection/authorability die immediately — fail closed)
   * BEFORE any async work starts; a stale adoption can publish nothing.
   */
  setPart(workspaceId: string | null, partNumber: string, io: PartAdoptionIO): Promise<void>
  /** Re-run the transition for the CURRENT Part (after a commit). */
  refresh(io: PartAdoptionIO): Promise<void>
  /** Publish the INSTALLED display's selector facts under the transition's
   *  generation (a stale publication is dropped silently). */
  publishSelectorFacts(generation: number, facts: SelectorFacts): void
  /** Drop the context (workspace switch / close). Invalidates in-flight loads. */
  clear(): void
}

export function createPartContextStore(): PartContextStore {
  let state: PartContextState = {
    workspaceId: null,
    partNumber: null,
    generation: 0,
    inspection: { status: 'idle' },
    selectorFacts: null,
  }
  const listeners = new Set<() => void>()
  const set = (next: PartContextState) => {
    state = next
    for (const l of listeners) l()
  }

  /** Run the async half of a transition — display + inspect concurrently.
   *  `ready` is the JOIN POINT (Codex4 B1.1): it publishes ONCE, only after
   *  BOTH halves succeed and the generation still holds. Until then the state
   *  stays `loading` (no tree, no eligibility, no authoring start); either
   *  failure publishes `error` and the other half cannot overwrite it. */
  const run = async (gen: number, partNumber: string, io: PartAdoptionIO) => {
    const stillCurrent = () => state.generation === gen
    let decoded: InspectedPart | null = null
    let failed: { message: string } | null = null
    const remember = (e: unknown) => {
      if (failed === null) failed = { message: e instanceof Error ? e.message : String(e) }
    }
    const displayWork = (async () => {
      if (io.installDisplay) await io.installDisplay(stillCurrent)
    })().catch(remember)
    const inspectWork = (async () => {
      const raw = await io.fetchInspect(partNumber)
      // Decode LOCALLY — nothing publishes until the join below.
      const part = decodeInspectedPart(raw)
      if (part.number !== partNumber) {
        throw new Error(`inspect returned ${part.number}, expected ${partNumber}`)
      }
      decoded = part
    })().catch(remember)
    await Promise.all([displayWork, inspectWork])
    if (!stillCurrent()) return // a newer transition owns the store
    if (failed !== null || decoded === null) {
      // Fail closed: a malformed/newer-versioned/mismatched view OR a display
      // failure is ONE error state — never a silently wrong or half-installed
      // context, and never a briefly-ready one.
      set({
        ...state,
        inspection: { status: 'error', message: (failed ?? { message: 'inspection produced nothing' }).message },
      })
      return
    }
    set({ ...state, inspection: { status: 'ready', part: decoded } })
  }

  return {
    subscribe(cb) {
      listeners.add(cb)
      return () => listeners.delete(cb)
    },
    getSnapshot: () => state,

    async setPart(workspaceId, partNumber, io) {
      // The transition-start boundary is SYNCHRONOUS (Codex3 B2 / Codex4
      // B1.3): selections clear, the generation advances, `loading` publishes
      // — all before any async work can observe the old world.
      io.onTransitionStart?.()
      const gen = state.generation + 1
      set({ workspaceId, partNumber, generation: gen, inspection: { status: 'loading' }, selectorFacts: null })
      await run(gen, partNumber, io)
    },

    async refresh(io) {
      const partNumber = state.partNumber
      if (partNumber === null) return
      io.onTransitionStart?.()
      const gen = state.generation + 1
      set({ ...state, generation: gen, inspection: { status: 'loading' }, selectorFacts: null })
      await run(gen, partNumber, io)
    },

    publishSelectorFacts(generation, facts) {
      if (state.generation !== generation) return // a stale display's facts die
      set({ ...state, selectorFacts: facts })
    },

    clear() {
      set({
        workspaceId: null,
        partNumber: null,
        generation: state.generation + 1,
        inspection: { status: 'idle' },
        selectorFacts: null,
      })
    },
  }
}

/** The SIGNED authority tuple an authoring session captures at start (Codex3
 *  B2 / Codex4 B1.4). A Part number alone is NOT authority: the same Number
 *  can exist in another workspace, and the same Part re-adopts under a newer
 *  generation — the terminal guard requires the EXACT tuple. The fresh-Part
 *  dev flow is the explicit `null` variant, never a partial tuple. */
export interface AuthoringTarget {
  workspaceId: string | null
  partNumber: string
  generation: number
}

/** Capture the current READY context as a session's authority tuple; null if
 *  the context is not ready (callers must refuse to start in that case). */
export function captureAuthoringTarget(s: PartContextState): AuthoringTarget | null {
  if (s.inspection.status !== 'ready' || s.partNumber === null) return null
  return { workspaceId: s.workspaceId, partNumber: s.partNumber, generation: s.generation }
}

/**
 * The terminal-authoring target guard (Codex3 B2 / Codex4 B1.4): the commit
 * boundary revalidates the CAPTURED tuple against the LIVE context — exact
 * workspace, Part number, AND generation, with a ready inspection — so an
 * accidental gate bypass or a future call path fails closed instead of
 * committing against a different (or newer) target. Returns the refusal
 * reason, or null when safe.
 */
export function guardTerminalTarget(
  captured: AuthoringTarget | null,
  s: PartContextState,
): string | null {
  if (captured === null) return null // the EXPLICIT fresh-Part dev flow — no target
  if (
    s.inspection.status === 'ready' &&
    s.workspaceId === captured.workspaceId &&
    s.partNumber === captured.partNumber &&
    s.generation === captured.generation
  ) {
    return null
  }
  return `the Part context changed (now ${s.partNumber ?? 'none'}, generation ${s.generation}) — cancel and reopen the operation`
}

/**
 * The ONE targeted-non-ready authoring-start policy (Codex5 B1.2): with a
 * TARGETED canonical Part whose inspection is not READY, NO authoring may
 * start — manual ribbon features, the AI session, and New/commit alike. The
 * idle/no-target state (dev:web's fresh-Part flow) is the explicit exception.
 * This is an AUTHORING gate only — Part/workspace navigation stays available
 * so a targeted `error` never traps the user away from recovery.
 */
export function authoringStartRefusal(s: PartContextState): string | null {
  if (s.partNumber === null) return null // idle / no target — the dev flow
  if (s.inspection.status === 'ready') return null
  return 'The Part context is not ready — resolve or reopen it before authoring'
}

/** A topology-selection capture (D-R8): everything an edge/face feature
 *  session OWNS from its start — the authority tuple, the selector, and the
 *  matched operation fact. A later selection change never retargets. */
export interface SelectorCapture {
  target: AuthoringTarget
  selector: { kind: 'edge' | 'face'; id: string }
  /** The matched fact at capture time (edge: its contract kind). */
  edgeKind: string | null
}

/**
 * Capture the live selection as an operation target (D-R8, fail closed):
 * refuses unless the context is READY, the base is an EXTRUDE (the engine's
 * fold rejects referencing features on a revolve), the id exists on the
 * CURRENT generation's display facts, and (for edges) the edge is SHARP.
 * Returns the capture or the refusal reason.
 */
export function captureSelectorTarget(
  s: PartContextState,
  selection: { kind: string; id: string } | null,
  need: 'sharp-edge' | 'face',
): SelectorCapture | string {
  const target = captureAuthoringTarget(s)
  if (target === null) return 'the Part context is not ready'
  if (s.inspection.status !== 'ready') return 'the Part context is not ready'
  const part = s.inspection.part
  if (!part.hasExtrudeBase || part.hasRevolveBase) {
    return 'this feature needs an EXTRUDED base (v1 does not reference revolve geometry)'
  }
  // Codex3 B1.1 (defense in depth behind the ribbon): the known-unsupported
  // stacking sequence refuses at command start too.
  const stacking = stackingRefusal(part)
  if (stacking) return stacking
  const facts = s.selectorFacts
  if (facts === null) return 'the canonical display has not installed yet'
  if (selection === null) return need === 'sharp-edge' ? 'select an edge first' : 'select a face first'
  if (need === 'sharp-edge') {
    if (selection.kind !== 'edge') return 'select an EDGE (the current selection is not an edge)'
    const kind = facts.edgeKinds.get(selection.id)
    if (kind === undefined) return 'the selected edge is not on the current display (stale selection)'
    if (kind !== 'sharp') return `the selected edge is ${kind} — Round/Chamfer need a SHARP edge`
    return { target, selector: { kind: 'edge', id: selection.id }, edgeKind: kind }
  }
  if (selection.kind !== 'face') return 'select a FACE (the current selection is not a face)'
  if (!facts.faceIds.has(selection.id)) return 'the selected face is not on the current display (stale selection)'
  return { target, selector: { kind: 'face', id: selection.id }, edgeKind: null }
}

/** The fail-closed authoring facts every surface derives from (B2/B3):
 *  nothing is eligible unless inspection is READY. */
export function authoringFacts(s: PartContextState): {
  readyPart: InspectedPart | null
  canExtrude: boolean
} {
  const readyPart = s.inspection.status === 'ready' ? s.inspection.part : null
  return {
    readyPart,
    // B3's UI mirror of the engine's one-base rule: a Part that already has a
    // base creation feature cannot take another (the engine enforces it too).
    canExtrude: readyPart !== null && !readyPart.hasExtrudeBase && !readyPart.hasRevolveBase,
  }
}
