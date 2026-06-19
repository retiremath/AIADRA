/**
 * Display source abstraction (arc 20260610-1, Claude1 P6/P7).
 *
 * The viewport renders the canonical lane from a `DisplaySource` — either the
 * real engine over the allowlisted bridge (Electron) or the dev fixture lane
 * (browser dev, `src/dev/fixtureSource.ts`). Identical consumption path either
 * way: the same attach gate, the same settle discipline, the same firewall.
 *
 * `snapViews === null` means the source computes HLR for ARBITRARY camera
 * views (the bridge). A non-null list means HLR exists only for those
 * pregenerated views (the fixture lane) — the viewport offers them as
 * standard-view snaps and never requests anything else.
 */
import type { HlrViewRequest } from '../aiadra'
import type { DisplayRepresentation, ViewDependentPayload } from './contract'

export interface SnapView {
  view_id: string
  /** Unit LOOK direction (eye → scene), engine convention. */
  direction: [number, number, number]
  up: [number, number, number]
}

export interface DisplaySource {
  kind: 'bridge' | 'fixture'
  /** Badge text for non-canonical sources (the fixture lane); null for real data. */
  badge: string | null
  getDisplay(): Promise<DisplayRepresentation>
  snapViews: SnapView[] | null
  getHlr(view: HlrViewRequest): Promise<ViewDependentPayload>
}

/** The real lane: an opened Workspace + a Part resolved via listParts (B1). */
export function createBridgeSource(workspaceId: string, objectRef: string): DisplaySource {
  const bridge = window.aiadra
  if (!bridge) throw new Error('bridge source requires window.aiadra')
  return {
    kind: 'bridge',
    badge: null,
    snapViews: null,
    async getDisplay() {
      const r = await bridge.displayRepresentation(workspaceId, objectRef)
      if (!r.ok) throw new Error(r.error.message)
      return r.result.display
    },
    async getHlr(view) {
      const r = await bridge.displayHlr(workspaceId, objectRef, [view], 'exact')
      if (!r.ok) throw new Error(r.error.message)
      return r.result.view_dependent
    },
  }
}
