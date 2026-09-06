/**
 * Floors 1 / 6 / 8 CONNECTED (I3; Codex3 B5): the ACTUAL production path from
 * the dialog to the engine request — real context + authoring stores, the
 * real accept (`acceptSketchPlacement`), the real `openCreate`, pointer RAYS
 * converted through the selected frame (`rayPlaneUV`, the viewport's own
 * conversion), the real proposal builder (near-horizontal AND near-vertical
 * input under the flipped, re-oriented frame), the production `commitIntent`,
 * and the exact main validator. The produced requests are pinned as
 * `bridge/fixtures/i3-placement-requests.json`, which
 * `bridge/test_i3_placement_requests.py` carries through the REAL engine
 * (preview + commit + reopen). The fixture is the seam: this test proves it IS
 * the pipeline's output; the Python side proves the engine's answer.
 * Regenerate deliberately: `UPDATE_I3_FIXTURE=1 npx vitest run <this file>`;
 * a MISSING fixture fails (Codex4 N2) — it is never created as a side effect.
 * The comparison is SEMANTIC (parsed JSON), so a checkout that rewrites line
 * endings cannot fail it while any changed request does.
 */
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { validateAuthoringParams } from '../../electron/authoringParamRules'
import { rayPlaneUV, type PlaneFrameTS, type Vec3 } from '../sketch/planeFrame'
import { commitIntent, commitPoint, currentProfile, endTool, openCreate, type ProfileSessionState } from '../sketch/profileSession'
import { createAuthoringSessionStore } from './authoringSession'
import { captureAuthoringTarget, createPartContextStore, type InspectFetcher } from './partContext'
import { acceptSketchPlacement } from './placementAccept'

const FIXTURE = fileURLToPath(new URL('../../bridge/fixtures/i3-placement-requests.json', import.meta.url))
const OPTS = { snapAngleToleranceDeg: 3, minDragPx: 4 } // the registry defaults the lane reads
const PART = 'P-000001'

const io = (fetch: InspectFetcher) => ({ fetchInspect: fetch })
const RAW = (number: string) => ({
  sidecar: { object: { type: 'Part', number, name: `Part ${number}`, uuid: `u-${number}` }, feature: [] },
})

/** A pointer ray from the sketch-view eye (on the +normal side, looking −normal)
 *  aimed at sketch-local (u, v) — what the viewport casts on a click. */
function rayAt(frame: PlaneFrameTS, u: number, v: number): { origin: Vec3; dir: Vec3 } {
  const p = [0, 1, 2].map((i) => frame.origin[i] + u * frame.u[i] + v * frame.v[i] + 100 * frame.normal[i]) as unknown as Vec3
  return { origin: p, dir: [-frame.normal[0], -frame.normal[1], -frame.normal[2]] }
}

async function openThroughTheDialog(): Promise<ProfileSessionState> {
  const context = createPartContextStore()
  await context.setPart('ws-1', PART, io(async () => RAW(PART)))
  const snap = context.getSnapshot()
  const store = createAuthoringSessionStore()
  store.startPlacementPick(snap.generation, { number: PART, name: 'x' }, { accept: 'sketch', capturedTarget: captureAuthoringTarget(snap) })
  store.resolvePlanePick('xy') // TOP
  store.setPlacementMember('orientationRef', 'zx') // FRONT
  store.setPlacementMember('orientation', 'top')
  store.setPlacementMember('normalSide', 'negative') // Flip
  let session: ProfileSessionState | null = null
  const out = acceptSketchPlacement(store, context.getSnapshot(), (placement, frame, target) => {
    session = openCreate(placement, 'draft1', frame, target, OPTS)
  })
  expect(out.kind).toBe('opened')
  return session!
}

function drawThroughRays(session: ProfileSessionState, a: [number, number], b: [number, number]): ProfileSessionState {
  const f = session.frame
  const ra = rayAt(f, a[0], a[1])
  const rb = rayAt(f, b[0], b[1])
  const uvA = rayPlaneUV(f, ra.origin, ra.dir)
  const uvB = rayPlaneUV(f, rb.origin, rb.dir)
  expect(uvA).not.toBeNull()
  expect(uvB).not.toBeNull()
  // the ray lands where it was aimed — the conversion honours the flipped frame
  expect(uvA!.u).toBeCloseTo(a[0], 9)
  expect(uvA!.v).toBeCloseTo(a[1], 9)
  return endTool(commitPoint(commitPoint(session, uvA!), uvB!))
}

describe('the I3 request pipeline (dialog → accept → rays → proposal → intent → main validator → fixture)', () => {
  it('produces the pinned requests for a near-horizontal and a near-vertical line under xy/zx/top/negative', async () => {
    const session = await openThroughTheDialog()
    expect(session.frame.u.map((x) => x + 0)).toEqual([-1, 0, 0])
    expect(session.frame.v.map((x) => x + 0)).toEqual([0, 1, 0])
    expect(session.frame.normal.map((x) => x + 0)).toEqual([0, 0, -1])

    const nearH = drawThroughRays(session, [0, 0], [20, 0.4])
    const nearV = drawThroughRays(session, [0, 0], [0.3, 15])
    // the real proposal builder proposed the axis facts in the SKETCH frame
    expect(currentProfile(nearH)!.facts!.map((f) => f.kind)).toEqual(['horizontal'])
    expect(currentProfile(nearV)!.facts!.map((f) => f.kind)).toEqual(['vertical'])

    const requests = [
      { label: 'near-horizontal', ...commitIntent(nearH, PART)! },
      { label: 'near-vertical', ...commitIntent(nearV, PART)! },
    ]
    for (const r of requests) {
      expect(r.kind).toBe('mechanical.author_profile_sketch')
      expect(r.params.placement).toEqual({
        support: { kind: 'principal', orientation: 'xy' },
        orientation_ref: { kind: 'principal', orientation: 'zx' },
        orientation: 'top',
        normal_side: 'negative',
      })
      expect(validateAuthoringParams(r.kind, r.params)).toBeNull() // the exact main envelope
    }

    const text = JSON.stringify(requests, null, 2) + '\n'
    if (process.env.UPDATE_I3_FIXTURE === '1') writeFileSync(FIXTURE, text)
    if (!existsSync(FIXTURE)) {
      throw new Error(
        `the pinned fixture is missing (${FIXTURE}); regenerate deliberately with UPDATE_I3_FIXTURE=1 npx vitest run src/authoring/i3PlacementRequests.test.ts`,
      )
    }
    // the seam: the fixture the engine-side test consumes IS this pipeline's
    // output — semantic (parsed-JSON) equality
    expect(JSON.parse(readFileSync(FIXTURE, 'utf8'))).toEqual(JSON.parse(text))
  })
})
