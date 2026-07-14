/**
 * The sketch-plane picker (arc 20260714-2 EP1) — Sketch begins by choosing the
 * flat surface it lives on (Petre's pinned semantics). v1 offers the three
 * principal datum planes (all live via EP2); datum planes / planar part faces
 * arrive with their reference slices. The pick commits ONLY the engine's
 * principal-plane enum — the overlay's intrinsic ids never leak into Truth.
 */
import { useEffect } from 'react'
import {
  INTRINSIC_PLANE_IDS,
  PLANE_LABELS,
  type PlaneOrientation,
} from '../authoring/backend'

const PLANES: PlaneOrientation[] = ['xy', 'yz', 'zx']

export function PlanePicker({
  open,
  onPick,
  onCancel,
}: {
  open: boolean
  onPick: (plane: PlaneOrientation) => void
  onCancel: () => void
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onCancel])

  if (!open) return null

  return (
    <div className="nd-overlay" role="presentation" onPointerDown={(e) => e.target === e.currentTarget && onCancel()}>
      <div className="nd-dialog pp-dialog" role="dialog" aria-modal="true" aria-label="Select a sketch plane">
        <div className="nd-head">
          <span className="nd-title">Select a sketch plane</span>
          <button type="button" className="fd-x" title="Cancel (Esc)" onClick={onCancel}>
            ✕
          </button>
        </div>
        <div className="pp-body">
          {PLANES.map((p) => (
            <button
              key={p}
              type="button"
              className={`pp-plane pp-${p}`}
              data-intrinsic-id={INTRINSIC_PLANE_IDS[p]}
              onClick={() => onPick(p)}
            >
              <span className="pp-name">{PLANE_LABELS[p]}</span>
              <span className="muted small">({p} plane)</span>
            </button>
          ))}
        </div>
        <div className="muted small pad pp-note">
          Datum planes you create — and flat part faces — become pickable in a later slice.
        </div>
      </div>
    </div>
  )
}
