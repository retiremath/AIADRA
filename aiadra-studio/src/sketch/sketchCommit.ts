/**
 * The sketch commit/cancel invocation module (pass sketch-ribbon-1
 * increment 2; Codex1 B4 / Codex2 authorization). PURE call-time code — the
 * ONE persistent `SessionLifecycle` (owned at the ribbon mount, one per
 * mount × backend identity) is PASSED IN together with the CURRENT
 * snapshot/context/hooks; nothing here captures state at construction, so
 * there is no second owner to drift and no recreation can orphan an
 * in-flight or failed backend session.
 *
 * The semantics moved VERBATIM from the retired sketch chrome: the stepwise
 * commit (or the chained hand-back), `guardTerminalTarget`, the
 * support-sensitive op selection, and the busy/error phases.
 */
import type { DisplaySource } from '../display/displaySource'
import {
  buildCircleSketchOps,
  buildCreateWithCircleOps,
  buildCreateWithRectangleOps,
  buildCreateWithSketchOps,
  buildRectangleSketchOps,
  buildSketchOnlyOps,
  suggestPartNumber,
  type FeatureOp,
} from '../authoring/backend'
import type { AuthoringSessionStore, SketchSubstate } from '../authoring/authoringSession'
import type { SessionLifecycle } from '../authoring/sessionLifecycle'
import { guardTerminalTarget, type PartContextStore } from '../authoring/partContext'
import { contourProblem } from './contour'

export interface SketchCommitHooks {
  onCommitted?: (info: {
    number: string
    name: string
    createdFresh: boolean
    display: DisplaySource
  }) => void
}

/** The live derivations every consumer shares (ribbon, status line). */
export function sketchDerived(s: SketchSubstate) {
  const ct = s.tool.kind === 'contour' ? s.tool : null
  const rt = s.tool.kind === 'rectangle' ? s.tool : null
  const ci = s.tool.kind === 'circle' ? s.tool : null
  const problem = ct ? contourProblem(ct.points, ct.bulges) : null
  const done = ct ? ct.closed : rt ? rt.rect !== null : (ci?.circle ?? null) !== null
  return { ct, rt, ci, problem, done, busy: s.phase === 'busy' }
}

/** The exact status hint (moved verbatim; the status line renders it). */
export function sketchHint(s: SketchSubstate): string {
  const { ct, rt, ci, problem, done } = sketchDerived(s)
  return (
    problem ??
    (done
      ? s.chainToExtrude
        ? 'Ready — OK returns to Extrude.'
        : 'Ready — OK commits the sketch.'
      : ct?.awaitingVia
        ? 'Click a point the arc should pass through (the via).'
        : rt
          ? rt.anchor
            ? 'Click the opposite corner.'
            : 'Click the first corner of the rectangle.'
          : ci
            ? ci.center
              ? 'Click a rim point to set the radius.'
              : 'Click the circle center.'
            : 'Click in the viewport to place points; close the ring at the start point.')
  )
}

/** OK — the stepwise sketch commit (or the chained hand-back), VERBATIM. */
export async function runSketchOk(
  lifecycle: SessionLifecycle,
  store: AuthoringSessionStore,
  context: PartContextStore,
  hooks: SketchCommitHooks,
): Promise<void> {
  const st = store.getSnapshot()
  if (st.mode !== 'sketch') return
  const s = st
  const { problem, done, busy } = sketchDerived(s)
  if (busy || problem || !done) return
  if (s.chainToExtrude) {
    store.finishChainedSketch()
    return
  }
  const target = s.targetPart
  if (target) {
    const refusal = s.targetAuth
      ? guardTerminalTarget(s.targetAuth, context.getSnapshot())
      : 'the session has no captured target authority — cancel and reopen the operation'
    if (refusal) {
      store.setSketchPhase('error', refusal)
      return
    }
  }
  if (s.support.kind === 'face' && !target) {
    store.setSketchPhase('error', 'a face-bound sketch needs its target Part — cancel and reopen')
    return
  }
  const num = target?.number ?? s.partNumber ?? suggestPartNumber()
  const name = target?.name ?? s.partName ?? `Sketch ${num}`
  const ops = selectSketchOps(s, target, num, name)
  await lifecycle.run(ops, num, {
    onBusy: () => store.setSketchPhase('busy', 'committing sketch…'),
    onError: (m) => store.setSketchPhase('error', m),
    onSuccess: (res) => {
      hooks.onCommitted?.({ number: num, name, createdFresh: !target, display: res.display })
      store.cancel()
    },
  })
}

/** The support-sensitive op selection (moved verbatim; exported pure). */
export function selectSketchOps(
  s: SketchSubstate,
  target: { number: string; name: string } | null,
  num: string,
  name: string,
): FeatureOp[] {
  const { ct, rt, ci } = sketchDerived(s)
  const construction = s.construction
  const rect = rt?.rect ?? null
  const circle = ci?.circle ?? null
  return circle
    ? target
      ? buildCircleSketchOps(target.number, circle, s.support, construction)
      : buildCreateWithCircleOps(num, name, circle, s.plane, construction)
    : rect
      ? target
        ? buildRectangleSketchOps(target.number, rect, s.support, construction)
        : buildCreateWithRectangleOps(num, name, rect, s.plane, construction)
      : target
        ? buildSketchOnlyOps(target.number, ct!.points, s.support, { bulges: ct!.bulges, construction })
        : buildCreateWithSketchOps(num, name, ct!.points, s.plane, { bulges: ct!.bulges, construction })
}

/** Cancel — refused by the lifecycle while a terminal run is unresolved. */
export function cancelSketch(
  lifecycle: SessionLifecycle,
  store: AuthoringSessionStore,
  onClose: () => void,
): void {
  if (!lifecycle.cancel()) return
  store.cancel()
  onClose()
}
