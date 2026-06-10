/**
 * HLR overlay **attach check** (arc 20260609-2 Codex1 B3). A standalone
 * `ViewDependentPayload` from `display_hlr` may be attached to a held
 * `DisplayRepresentation` ONLY when its `identity_echo` matches the package
 * in full — object identity, geometry identity, contract version, cache key,
 * and topology signature. A mismatch means the overlay was computed against
 * different state (stale cache, different object, recomputed topology); the
 * viewport must drop it and re-request, never render it.
 *
 * Pure module — no three.js, no IPC; deterministic and unit-testable.
 */
import type { DisplayRepresentation, ViewDependentPayload } from './contract'

export interface AttachCheck {
  ok: boolean
  /** Echo fields that disagree with the held package (empty when ok). */
  mismatches: string[]
}

export function checkAttachHlr(
  display: DisplayRepresentation,
  payload: ViewDependentPayload,
): AttachCheck {
  const echo = payload.identity_echo
  const id = display.identity
  const mismatches: string[] = []
  if (echo.object_uuid !== id.object_uuid) mismatches.push('object_uuid')
  if (echo.object_number !== id.object_number) mismatches.push('object_number')
  if (echo.geometry_ref !== id.geometry_ref) mismatches.push('geometry_ref')
  if (echo.cache_key !== id.cache_key) mismatches.push('cache_key')
  if (echo.topology_signature !== id.topology_signature)
    mismatches.push('topology_signature')
  if (echo.display_representation_version !== '1.1')
    mismatches.push('display_representation_version')
  return { ok: mismatches.length === 0, mismatches }
}

export function canAttachHlr(
  display: DisplayRepresentation,
  payload: ViewDependentPayload,
): boolean {
  return checkAttachHlr(display, payload).ok
}
