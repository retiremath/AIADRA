/**
 * The A4 profile WIRE shapes (ADR/0044 A4; arc 20260730-1).
 *
 * These mirror what `mechanical.author_profile_sketch`,
 * `mechanical.replace_sketch_graph` and `mechanical.preview_sketch_graph`
 * accept — one fact graph behind every drawing tool. The line chain,
 * rectangle and circle are UI SUGAR that all build THIS payload; there are
 * deliberately no per-tool operations, which is what keeps the G-AI gate
 * true (an agent authors the identical graph with no renderer in the loop).
 *
 * The reference grammar is CLOSED: a new record carries a client `key`, an
 * existing one carries its engine `id`, and a reference is `{key}` or `{id}`
 * — never a bare string, so a ref can never be read two ways.
 *
 * The SURVIVAL LAW belongs to the engine, but the renderer must understand
 * it to build correct payloads:
 *   - a preserved `id` may change only authored NOMINALS; a segment's
 *     endpoints, a circle's centre and a fact's target must stay exact;
 *   - a structural change omits the id and supplies a new `key`;
 *   - a record ABSENT from a `replace` call is REMOVED.
 */

/** A new record mints an id; an existing one preserves its own. */
export type Identity = { key: string } | { id: string }

/** A reference to another record in the SAME call, or to a committed one. */
export type Ref = { key: string } | { id: string }

export type ProfilePoint = Identity & { x: number; y: number }
export type ProfileSegment = Identity & { start: Ref; end: Ref }
export type ProfileCircle = Identity & { center: Ref; radius_mm: number }
export type ProfileFact = Identity & {
  kind: 'horizontal' | 'vertical'
  target: Ref
}

/** The KEYED variants — what a drawing tool builds before anything is
 *  committed. Every record is new, so `key` is always present. */
export type NewPoint = { key: string } & { x: number; y: number }
export type NewSegment = { key: string } & { start: Ref; end: Ref }
export type NewCircle = { key: string } & { center: Ref; radius_mm: number }
export type NewFact = { key: string } & { kind: 'horizontal' | 'vertical'; target: Ref }

export interface ProfilePayload {
  points?: ProfilePoint[]
  segments?: ProfileSegment[]
  circles?: ProfileCircle[]
  facts?: ProfileFact[]
}

/** The A3 placement input. `support` is required; nested omissions take the
 *  engine's canonical defaults — Studio never mints a partial record. */
export interface SketchPlacementInput {
  support: { kind: 'principal'; orientation: 'xy' | 'yz' | 'zx' }
  orientation_ref?: { kind: 'principal'; orientation: 'xy' | 'yz' | 'zx' }
  orientation?: 'right' | 'top' | 'left' | 'bottom'
  normal_side?: 'positive' | 'negative'
}
