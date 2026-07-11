/**
 * Dev fixture display sources (arc 20260610-1, Claude1 P7; extended arc
 * 20260711-10 / MVP-1) — the browser-dev lane that makes display modes + the
 * authoring loop testable at a localhost port without Electron or a live bridge.
 *
 * Gating: loads ONLY in browser dev (`import.meta.env.DEV && !window.aiadra`).
 * In a production build `import.meta.env.DEV` is statically false, the dynamic
 * imports below are unreachable, and the fixture JSON is excluded from the
 * bundle — proven by `scripts/assert-no-fixtures.mjs` after every build.
 *
 * The fixtures are engine-generated (`scripts/gen-dev-fixtures.py` runs the REAL
 * `display_representation` / `display_hlr` Tier-1 primitives), clearly badged,
 * never Product Truth, and version-gated: a contract bump without regeneration
 * fails loudly here. The MVP-1 bracket candidates (`bracket-<pattern>.json`) are
 * baked the same way, so each candidate previews TRUE distinct geometry
 * (ADR/0039 P-A2; Codex2 B1), not a re-badged single fixture.
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
type FixtureViewId = (typeof FIXTURE_VIEW_IDS)[number]

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

/** Build a fixture DisplaySource from a loaded display + per-view HLR payloads.
 *  Shared by the base fixture and every bracket candidate. */
function buildFixtureSource(
  displayJson: unknown,
  hlr: Record<FixtureViewId, unknown>,
  badge: string,
): DisplaySource {
  const display = displayJson as DisplayRepresentation
  assertFixtureVersion(display)

  const payloads = new Map<string, ViewDependentPayload>()
  for (const id of FIXTURE_VIEW_IDS) payloads.set(id, hlr[id] as ViewDependentPayload)

  const snapViews: SnapView[] = FIXTURE_VIEW_IDS.map((id) => {
    const view = payloads.get(id)!.views[0]
    return { view_id: id, direction: view.projector.direction, up: view.projector.up }
  })

  return {
    kind: 'fixture',
    badge,
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

/** The base engine fixture (a box-with-hole part) — boot + restore display. */
export async function loadFixtureSource(): Promise<DisplaySource | null> {
  if (!import.meta.env.DEV) return null
  if (window.aiadra) return null

  const [display, front, iso, tilt] = await Promise.all([
    import('../../dev-fixtures/display.json'),
    import('../../dev-fixtures/hlr-front.json'),
    import('../../dev-fixtures/hlr-iso.json'),
    import('../../dev-fixtures/hlr-tilt.json'),
  ])
  return buildFixtureSource(display.default, { front: front.default, iso: iso.default, tilt: tilt.default }, FIXTURE_BADGE)
}

// One loader per candidate sourceId → its baked bracket fixture family. Literal
// dynamic imports (statically analyzable + tree-shaken out of prod behind the
// DEV gate, so assert-no-fixtures stays green). Keys match the configurator's
// candidate `sourceId`s (authoring/brackets.ts).
const CANDIDATE_LOADERS: Record<string, () => Promise<[unknown, unknown, unknown, unknown]>> = {
  'bracket/corners': () =>
    Promise.all([
      import('../../dev-fixtures/bracket-corners.json'),
      import('../../dev-fixtures/bracket-corners-hlr-front.json'),
      import('../../dev-fixtures/bracket-corners-hlr-iso.json'),
      import('../../dev-fixtures/bracket-corners-hlr-tilt.json'),
    ]).then(([d, f, i, t]) => [d.default, f.default, i.default, t.default]),
  'bracket/grid': () =>
    Promise.all([
      import('../../dev-fixtures/bracket-grid.json'),
      import('../../dev-fixtures/bracket-grid-hlr-front.json'),
      import('../../dev-fixtures/bracket-grid-hlr-iso.json'),
      import('../../dev-fixtures/bracket-grid-hlr-tilt.json'),
    ]).then(([d, f, i, t]) => [d.default, f.default, i.default, t.default]),
  'bracket/inline': () =>
    Promise.all([
      import('../../dev-fixtures/bracket-inline.json'),
      import('../../dev-fixtures/bracket-inline-hlr-front.json'),
      import('../../dev-fixtures/bracket-inline-hlr-iso.json'),
      import('../../dev-fixtures/bracket-inline-hlr-tilt.json'),
    ]).then(([d, f, i, t]) => [d.default, f.default, i.default, t.default]),
}

/** Whether a candidate sourceId has a baked fixture family (for tests + dispatch). */
export function hasCandidateFixture(sourceId: string): boolean {
  return sourceId in CANDIDATE_LOADERS
}

/** Load the baked display source for a candidate sourceId (dev lane only). */
export async function loadCandidateFixtureSource(sourceId: string, badge: string): Promise<DisplaySource | null> {
  if (!import.meta.env.DEV) return null
  if (window.aiadra) return null
  const loader = CANDIDATE_LOADERS[sourceId]
  if (!loader) return null
  const [display, front, iso, tilt] = await loader()
  return buildFixtureSource(display, { front, iso, tilt }, badge)
}

/** The plain extruded box (6-face) — the dev:web mock's honest preview geometry
 *  for the extrude manual dashboard (arc 20260711-11 slice 1b/1c). The real
 *  bridge lane shows the true parametric solid instead. */
export async function loadExtrudeBoxSource(badge: string): Promise<DisplaySource | null> {
  if (!import.meta.env.DEV) return null
  if (window.aiadra) return null
  const [display, front, iso, tilt] = await Promise.all([
    import('../../dev-fixtures/extrude-box.json'),
    import('../../dev-fixtures/extrude-box-hlr-front.json'),
    import('../../dev-fixtures/extrude-box-hlr-iso.json'),
    import('../../dev-fixtures/extrude-box-hlr-tilt.json'),
  ])
  return buildFixtureSource(display.default, { front: front.default, iso: iso.default, tilt: tilt.default }, badge)
}
