/**
 * Candidate → display source resolution (arc 20260711-10 / MVP-1; Codex B2 + B1).
 *
 * A candidate carries a stable `sourceId`; this resolves it to the DISTINCT
 * engine-baked display source for that candidate (Codex2 B1 — each candidate
 * previews its own real geometry, never a re-badged single fixture). MVP-1 is
 * the fast lane: candidates resolve to their baked bracket fixture family
 * (`bracket-<pattern>.json`, generated through the REAL engine), so the preview
 * shows real evaluated geometry (ADR/0039 P-A2), badged transient (ADR/0040 D8).
 * Production builds never reach here (the `import.meta.env.DEV` gate in
 * loadCandidateFixtureSource + assert-no-fixtures). In the bridge lane (MVP-2)
 * candidates evaluate their recipe live instead.
 */
import type { DisplaySource } from '../display/displaySource'
import { loadCandidateFixtureSource } from '../dev/fixtureSource'
import type { Candidate } from './store'

export async function loadCandidateSource(candidate: Candidate): Promise<DisplaySource | null> {
  const badge = `candidate · ${candidate.label} — transient`
  return loadCandidateFixtureSource(candidate.sourceId, badge)
}
