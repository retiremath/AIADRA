/**
 * The New dialog (arc 20260714-1; Petre's steer — Creo 10's New pattern,
 * benchmarked not cloned, ADR/0037 D1): ONE generic "New" command opens a
 * dialog with Type + Sub-type + Number + Name. Types map to AIADRA Truth-Model
 * Object Types (Part today; Assembly et al. greyed until their authoring
 * slices — slice-A honesty: visible, disabled, tooltip'd). Sub-types are
 * pinned now for future use (Solid today; Sheet metal reserved).
 *
 * The NUMBER is explicit and PROVISIONAL (Codex2 B2): a suggested P-NNNNNN the
 * user may edit; core's creation contract validates + reserves it atomically at
 * commit (ADR/0004) and a collision fails loudly. The dialog never claims the
 * number is already canonical.
 */
import { useEffect, useRef, useState } from 'react'
import { PART_NUMBER_RE, suggestPartNumber } from '../authoring/backend'

export interface NewObjectChoice {
  type: 'part'
  subtype: 'solid'
  name: string
  /** PROVISIONAL until core commits it (validated + reserved at commit). */
  number: string
}

const TYPES = [
  { id: 'part', label: 'Part', enabled: true, hint: 'A solid part — sketch + features' },
  {
    id: 'assembly',
    label: 'Assembly',
    enabled: false,
    hint: 'Positioned component occurrences — arrives with the assembly authoring slice (ADR/0042)',
  },
  {
    id: 'drawing',
    label: 'Drawing',
    enabled: false,
    hint: 'A 2D documentation view — a future slice (HLR views exist in the display contract)',
  },
  {
    id: 'workspace',
    label: 'Workspace',
    enabled: false,
    hint: 'Create a new workspace folder — a future slice (open an existing one for now)',
  },
] as const

const PART_SUBTYPES = [
  { id: 'solid', label: 'Solid', enabled: true },
  { id: 'sheetmetal', label: 'Sheet metal', enabled: false, hint: 'Reserved — a future engine capability' },
] as const

export function NewDialog({
  open,
  onCancel,
  onCreate,
}: {
  open: boolean
  onCancel: () => void
  onCreate: (choice: NewObjectChoice) => void
}) {
  const [name, setName] = useState('')
  const [number, setNumber] = useState('')
  const nameRef = useRef<HTMLInputElement>(null)

  // Fresh fields + focus every time the dialog opens; the number starts as a
  // fresh provisional suggestion.
  useEffect(() => {
    if (open) {
      setName('')
      setNumber(suggestPartNumber())
      // after render
      setTimeout(() => nameRef.current?.focus(), 0)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onCancel])

  if (!open) return null

  const numberValid = PART_NUMBER_RE.test(number.trim())
  const ok = () => {
    const trimmed = name.trim()
    if (!trimmed || !numberValid) return
    onCreate({ type: 'part', subtype: 'solid', name: trimmed, number: number.trim() })
  }

  return (
    <div className="nd-overlay" role="presentation" onPointerDown={(e) => e.target === e.currentTarget && onCancel()}>
      <div className="nd-dialog" role="dialog" aria-modal="true" aria-label="New">
        <div className="nd-head">
          <span className="nd-title">New</span>
          <button type="button" className="fd-x" title="Cancel (Esc)" onClick={onCancel}>
            ✕
          </button>
        </div>
        <div className="nd-body">
          <fieldset className="nd-col">
            <legend className="panel-title">Type</legend>
            {TYPES.map((t) => (
              <label key={t.id} className={`nd-opt ${t.enabled ? '' : 'off'}`} title={t.hint}>
                <input type="radio" name="nd-type" checked={t.id === 'part'} disabled={!t.enabled} readOnly />
                {t.label}
              </label>
            ))}
          </fieldset>
          <fieldset className="nd-col">
            <legend className="panel-title">Sub-type</legend>
            {PART_SUBTYPES.map((s) => (
              <label key={s.id} className={`nd-opt ${s.enabled ? '' : 'off'}`} title={'hint' in s ? s.hint : undefined}>
                <input type="radio" name="nd-subtype" checked={s.id === 'solid'} disabled={!s.enabled} readOnly />
                {s.label}
              </label>
            ))}
          </fieldset>
        </div>
        <div className="nd-name">
          <label className="nd-name-row">
            <span>Name</span>
            <input
              ref={nameRef}
              type="text"
              value={name}
              placeholder="e.g. Mounting bracket"
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && ok()}
            />
          </label>
          <label className="nd-name-row">
            <span>Number</span>
            <input
              type="text"
              value={number}
              className={numberValid ? '' : 'invalid'}
              onChange={(e) => setNumber(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && ok()}
            />
          </label>
          <div className="muted small">
            Provisional (P-NNNNNN) — the Truth Model validates and reserves the Number at commit;
            a collision fails loudly (ADR/0004).
          </div>
        </div>
        <div className="nd-actions">
          <button type="button" className="btn" onClick={onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="btn primary"
            disabled={!name.trim() || !numberValid}
            title={numberValid ? undefined : 'The Number must match P-NNNNNN'}
            onClick={ok}
          >
            OK
          </button>
        </div>
      </div>
    </div>
  )
}
