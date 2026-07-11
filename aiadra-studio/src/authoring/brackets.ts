/**
 * The scripted bracket configurator (arc 20260711-10 / MVP-1).
 *
 * A `generate` configurator (ADR/0039 D4) realized as thin metadata over the
 * shipped feature recipes (ADR/0039 D12 — thin-metadata-not-DSL): a parameter
 * schema + a concept-owned elicitation schema + a DETERMINISTIC `propose`
 * mapper (the "scripted AI" — no LLM, ADR/0040 D10 N3). `propose` is pure and
 * total: same answers+params → same ordered candidate set.
 *
 * The deterministic boundary holds (ADR/0039 P-A1/P-A2): this emits only a
 * configurator id + params + a candidate set; each candidate names a stable
 * `sourceId` that resolves to a REAL engine-baked display package
 * (previewController + the bracket dev-fixtures), never a mockup.
 */
import type { ActiveConfigurator, Candidate } from '../operation/store'

export const BRACKET_CONFIGURATOR_ID = 'project:bracket/flat-plate'
const BRACKET_CONFIGURATOR_NAME = 'Flat bracket'

/** Parameter schema — canonical `_mm` / count fields the dock renders as
 *  controls (Codex canonical-units watch: no prompt-only units). */
export interface ParamDescriptor {
  key: string
  label: string
  unit: 'mm' | 'count'
  min: number
  max: number
  step: number
  default: number
}

export const BRACKET_PARAMS: readonly ParamDescriptor[] = [
  { key: 'width_mm', label: 'Width', unit: 'mm', min: 20, max: 200, step: 1, default: 80 },
  { key: 'height_mm', label: 'Height', unit: 'mm', min: 20, max: 200, step: 1, default: 50 },
  { key: 'thickness_mm', label: 'Thickness', unit: 'mm', min: 2, max: 30, step: 0.5, default: 6 },
  { key: 'holeDia_mm', label: 'Hole Ø', unit: 'mm', min: 2, max: 30, step: 0.5, default: 6 },
]

export const BRACKET_DEFAULT_PARAMS: Record<string, number> = Object.fromEntries(
  BRACKET_PARAMS.map((p) => [p.key, p.default]),
)

/** Concept-owned elicitation schema (ADR/0039 D4 / D11 — the questions belong to
 *  the concept, in the artifact; orchestration policy stays client-side). */
export interface ElicitationOption {
  value: string
  label: string
}
export interface ElicitationQuestion {
  id: string
  prompt: string
  options: readonly ElicitationOption[]
}

/** The hole patterns — each is a real candidate (a distinct evaluated recipe). */
const PATTERNS = [
  { value: 'corners', label: 'Corners (4×)', holeCount: 4, sourceId: 'bracket/corners' },
  { value: 'grid', label: '2×2 grid', holeCount: 4, sourceId: 'bracket/grid' },
  { value: 'inline', label: 'Inline (2×)', holeCount: 2, sourceId: 'bracket/inline' },
] as const

export const BRACKET_ELICITATION: readonly ElicitationQuestion[] = [
  {
    id: 'pattern',
    prompt: 'How should the holes be placed?',
    options: PATTERNS.map((p) => ({ value: p.value, label: p.label })),
  },
]

/** The scripted "AI": answers + params → an ordered candidate set (pure/total).
 *  Always proposes all three real patterns (P-A5 — show diverse candidates);
 *  the `pattern` answer, once given, MOVES the chosen pattern to the front
 *  (navigate-not-specify) without hiding the alternatives. */
export function proposeBracketCandidates(
  answers: Record<string, string | number>,
  params: Record<string, number>,
): Candidate[] {
  const chosen = typeof answers.pattern === 'string' ? answers.pattern : null
  const ordered = [...PATTERNS].sort((a, b) => {
    if (a.value === chosen) return -1
    if (b.value === chosen) return 1
    return 0
  })
  return ordered.map((p) => ({
    id: `bracket-${p.value}`,
    label: p.label,
    sourceId: p.sourceId,
    params: { ...params, holeCount: p.holeCount },
    validationStatus: 'valid' as const,
    provenance: { sourceConfigurator: BRACKET_CONFIGURATOR_ID, transient: true as const },
  }))
}

/** Build the ActiveConfigurator the operation store drives. */
export function createBracketConfigurator(): ActiveConfigurator {
  return {
    id: BRACKET_CONFIGURATOR_ID,
    name: BRACKET_CONFIGURATOR_NAME,
    defaultParams: BRACKET_DEFAULT_PARAMS,
    propose: proposeBracketCandidates,
  }
}
