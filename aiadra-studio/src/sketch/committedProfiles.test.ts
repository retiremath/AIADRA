import { describe, it, expect } from 'vitest'
import { committedProfiles, ProfileJoinError } from './committedProfiles'
import { previewGeometry } from './useProfileSketch'
import type { DisplayRepresentation, ProfileGraphPreview } from '../display/contract'

const frame = (sid: string) => ({
  sketch_feature_id: sid,
  origin_mm: [0, 0, 0] as [number, number, number],
  u_axis: [1, 0, 0] as [number, number, number],
  v_axis: [0, 1, 0] as [number, number, number],
  normal: [0, 0, 1] as [number, number, number],
})

const profile = (sid: string) => ({
  sketch_feature_id: sid,
  points: [
    { id: 'skp_0006', world: [0, 0, 0] as [number, number, number] },
    { id: 'skp_0007', world: [20, 0, 0] as [number, number, number] },
  ],
  segments: [{ id: 'skp_0008', start: 'skp_0006', end: 'skp_0007' }],
  circles: [],
  annotations: [],
  constraint_glyphs: [],
})

const display = (profiles: unknown[], frames: unknown[]): DisplayRepresentation =>
  ({ v2_profiles: profiles, sketch_frames: frames }) as unknown as DisplayRepresentation

describe('the committed profile→frame join (Codex6 B1)', () => {
  it('a joined profile yields overlay geometry plus its FULL frame (W-4)', () => {
    const [cp] = committedProfiles(display([profile('feat_0001')], [frame('feat_0001')]))
    expect(cp.sketchFeatureId).toBe('feat_0001')
    expect(cp.geometry.segments).toHaveLength(1)
    // the furniture builder needs axes + origin, not just the normal
    expect(cp.frame.normal).toEqual([0, 0, 1])
    expect(cp.frame.u).toEqual([1, 0, 0])
    expect(cp.frame.v).toEqual([0, 1, 0])
    expect(cp.frame.origin).toEqual([0, 0, 0])
  })

  it('absence is normal: no profiles, no entries — including pre-1.4 packages', () => {
    expect(committedProfiles(display([], [frame('feat_0001')]))).toEqual([])
    expect(committedProfiles({} as DisplayRepresentation)).toEqual([])
  })

  it('a profile with NO frame throws — never rendered on a guessed plane', () => {
    expect(() => committedProfiles(display([profile('feat_0001')], []))).toThrow(ProfileJoinError)
  })

  it('an AMBIGUOUS join throws', () => {
    expect(() =>
      committedProfiles(display([profile('feat_0001')], [frame('feat_0001'), frame('feat_0001')])),
    ).toThrow(/ambiguous/)
  })

  it('multiple sketches each join their own frame', () => {
    const out = committedProfiles(
      display([profile('feat_0001'), profile('feat_0002')], [frame('feat_0002'), frame('feat_0001')]),
    )
    expect(out.map((c) => c.sketchFeatureId)).toEqual(['feat_0001', 'feat_0002'])
  })

  it('committed geometry and preview geometry are the SAME shape — one renderer, provably', () => {
    // The engine parity test (test_profile_sketch_ops) proves the VALUES
    // agree after key→id substitution; this pins that the two lanes also
    // feed the overlay the same MEMBERS, so a shape drift cannot hide in
    // the renderer boundary.
    const [cp] = committedProfiles(display([profile('feat_0001')], [frame('feat_0001')]))
    const fromPreview = previewGeometry({
      owner: { candidate_key: 'draft1' },
      frame: frame('feat_0001'),
      ...profile('feat_0001'),
    } as unknown as ProfileGraphPreview)
    expect(Object.keys(cp.geometry).sort()).toEqual(Object.keys(fromPreview ?? {}).sort())
  })
})
