/**
 * The placement dialog's product-facing copy (I3, arc 20260905-1; Codex1 N3):
 * no pass ids, no versions, no internals — what the user needs to act. Kept
 * beside, not inside, the component so the component file exports only its
 * component (react-refresh) and tests can pin the exact strings.
 */
import type { PlacementAccept } from './authoringSession'

export const USE_PREVIOUS_UNAVAILABLE = 'Reuse previous placement is not available yet.'
export const COLLECTOR_HINT = 'Click a datum plane in the viewport while this is active, or choose from the list'
export const FLIP_HINT =
  'Sketch view direction — Flip sketches from the other side of the plane (a model fact: a positive-depth feature then grows the other way)'
export const ACCEPT_LABEL: Record<PlacementAccept, string> = {
  sketch: 'Sketch',
  create: 'Create',
  redefine: 'Redefine',
}
