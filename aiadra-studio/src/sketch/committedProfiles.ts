/**
 * The COMMITTED profile lane (Codex6 B1; ADR/0044 A4).
 *
 * Joins a Display package's `v2_profiles[]` to its `sketch_frames[]` and
 * yields the same `ProfileGeometry` shape the LIVE preview feeds the overlay —
 * one geometry vocabulary, two producers, one renderer. That identity of shape
 * is what makes "the committed drawing equals the last accepted preview" a
 * checkable claim instead of a hope.
 *
 * The join is FAIL-CLOSED. Core's v1.4 validator already refuses a package
 * whose profile has no frame, so reaching the missing/ambiguous branches here
 * means the package was not validated through the contract — and rendering a
 * profile on a guessed plane would be exactly the silent-drift ADR/0045 D6
 * forbids. We throw; the caller treats it like any other malformed display.
 */
import type { DisplayRepresentation, SketchFrame } from '../display/contract'
import type { ProfileGeometry } from './profileOverlay'

export interface CommittedProfile {
  sketchFeatureId: string
  geometry: ProfileGeometry
  /** The engine-resolved frame normal — the overlay needs it only to keep a
   *  circle's tessellation in the sketch plane. */
  frameNormal: readonly [number, number, number]
}

export class ProfileJoinError extends Error {}

/**
 * Extract every committed profile with its resolved frame. Returns `[]` for
 * pre-1.4 packages and packages with no profiles — absence is normal;
 * a broken join is not.
 */
export function committedProfiles(display: DisplayRepresentation): CommittedProfile[] {
  const profiles = display.v2_profiles ?? []
  if (profiles.length === 0) return []

  const frames = new Map<string, SketchFrame[]>()
  for (const f of display.sketch_frames ?? []) {
    const bucket = frames.get(f.sketch_feature_id)
    if (bucket) bucket.push(f)
    else frames.set(f.sketch_feature_id, [f])
  }

  return profiles.map((p) => {
    const bucket = frames.get(p.sketch_feature_id)
    if (!bucket || bucket.length === 0) {
      throw new ProfileJoinError(
        `committed profile ${p.sketch_feature_id} has no sketch_frames member — ` +
          `the package bypassed the v1.4 contract validator`,
      )
    }
    if (bucket.length > 1) {
      throw new ProfileJoinError(
        `committed profile ${p.sketch_feature_id} joins ${bucket.length} frames — ambiguous`,
      )
    }
    return {
      sketchFeatureId: p.sketch_feature_id,
      geometry: {
        points: p.points,
        segments: p.segments,
        circles: p.circles,
        annotations: p.annotations,
        constraint_glyphs: p.constraint_glyphs,
      },
      frameNormal: bucket[0].normal,
    }
  })
}
