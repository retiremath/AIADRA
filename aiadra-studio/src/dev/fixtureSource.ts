/**
 * Dev fixture display source (arc 20260610-1, Claude1 P7) — the browser-dev
 * lane that makes display modes testable at a localhost port without Electron
 * or the engine.
 *
 * Gating: loads ONLY in browser dev (`import.meta.env.DEV && !window.aiadra`).
 * In a production build `import.meta.env.DEV` is statically false, the dynamic
 * imports below are unreachable, and the fixture JSON is excluded from the
 * bundle — proven by `scripts/assert-no-fixtures.mjs` after every build
 * (Codex1 N2).
 *
 * The fixtures are engine-generated (`scripts/gen-dev-fixtures.py` runs the
 * REAL `display_representation` / `display_hlr` Tier-1 primitives), clearly
 * badged in the UI, never Product Truth, and version-gated: a contract bump
 * without regeneration fails loudly here — a stale fixture never renders
 * silently.
 *
 * HLR exists only for the pregenerated views (front / iso / tilt — the proven
 * ADR/0036 spike set); their camera placement is derived from each payload's
 * own projector, so there is no duplicated direction table to drift.
 */
import type { HlrViewRequest } from '../aiadra'
import {
  DISPLAY_REPRESENTATION_VERSION,
  type DisplayRepresentation,
  type ViewDependentPayload,
} from '../display/contract'
import type { DisplaySource, SnapView } from '../display/displaySource'

export const FIXTURE_BADGE = 'dev fixture — not Product Truth'

// Iso first → the dev lane opens on the 3D iso view (the nav cube shows three
// faces, the CAD-default first impression). The gallery script snaps explicitly.
const FIXTURE_VIEW_IDS = ['iso', 'front', 'tilt'] as const

export class FixtureVersionError extends Error {
  constructor(found: string) {
    super(
      `dev fixture is contract version ${found}, expected ${DISPLAY_REPRESENTATION_VERSION} — ` +
        'regenerate with scripts/gen-dev-fixtures.py',
    )
    this.name = 'FixtureVersionError'
  }
}

/** Exported for the version-gate unit test (pure check, no imports). */
export function assertFixtureVersion(display: { display_representation_version: string }): void {
  if (display.display_representation_version !== DISPLAY_REPRESENTATION_VERSION) {
    throw new FixtureVersionError(display.display_representation_version)
  }
}

export async function loadFixtureSource(): Promise<DisplaySource | null> {
  if (!import.meta.env.DEV) return null
  if (window.aiadra) return null

  const display = (await import('../../dev-fixtures/display.json')).default as unknown as DisplayRepresentation
  assertFixtureVersion(display)

  const payloads = new Map<string, ViewDependentPayload>()
  const [front, iso, tilt] = await Promise.all([
    import('../../dev-fixtures/hlr-front.json'),
    import('../../dev-fixtures/hlr-iso.json'),
    import('../../dev-fixtures/hlr-tilt.json'),
  ])
  payloads.set('front', front.default as unknown as ViewDependentPayload)
  payloads.set('iso', iso.default as unknown as ViewDependentPayload)
  payloads.set('tilt', tilt.default as unknown as ViewDependentPayload)

  const snapViews: SnapView[] = FIXTURE_VIEW_IDS.map((id) => {
    const view = payloads.get(id)!.views[0]
    return { view_id: id, direction: view.projector.direction, up: view.projector.up }
  })

  return {
    kind: 'fixture',
    badge: FIXTURE_BADGE,
    snapViews,
    async getDisplay() {
      return display
    },
    async getHlr(view: HlrViewRequest) {
      const payload = payloads.get(view.view_id)
      if (!payload) {
        throw new Error(`fixture lane has no HLR for view '${view.view_id}' (only: ${FIXTURE_VIEW_IDS.join(', ')})`)
      }
      return payload
    },
  }
}
