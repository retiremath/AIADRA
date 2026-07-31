/**
 * Dimension VALUE formatting — extracted from `profileOverlay` (W-4) so the
 * furniture builder and the overlay share ONE formatter without a module
 * cycle. The number a label shows is the ENGINE's value through this
 * function verbatim — no renderer rounds, measures, or re-derives.
 */
import type { ProfileAnnotation } from '../display/contract'

/**
 * How a dimension VALUE is written. `length`/`position` are millimetres to
 * three decimals (Creo's default), `angle` is degrees to two — the units come
 * from the engine, never from a guess about the kind.
 */
export function formatAnnotation(a: Pick<ProfileAnnotation, 'value' | 'unit'>): string {
  return a.unit === 'deg' ? `${a.value.toFixed(2)}°` : a.value.toFixed(3)
}
