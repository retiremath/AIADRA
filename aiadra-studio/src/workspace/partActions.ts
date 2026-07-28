/**
 * Pure helpers for the workspace tree's Part actions (pass workspace-tree-1,
 * arc 20260728-4; contract arc 20260728-3 Codex2 SIGNOFF).
 *
 * Two-sided session rule: `deletePreflight` is Studio's CLASS-4 preflight —
 * a session convenience refusal, never a Truth rule. Core stays session-blind
 * and enforces the durable rules (v1 gates + the B2 referential-integrity
 * scan); its structured blocker list crosses unweakened and Studio only
 * RENDERS it (`describeBlocker`), never reinterprets it.
 */
import type { DeletionBlocker } from '../aiadra'

/** The titlebar projection (WT-05; class-4 derived, never stored):
 * active Part → `name (Active) — number`; number-only fallback when the
 * name is empty/unknown; Home (no active part) → the plain product title. */
export function shellTitle(activePartNumber: string | null, activePartName?: string | null): string {
  if (!activePartNumber) return 'AIADRA Studio'
  const label = activePartName?.trim()
    ? `${activePartName.trim()} (Active) — ${activePartNumber}`
    : `${activePartNumber} (Active)`
  return `${label} — AIADRA Studio`
}

/** Studio's session preflight for Delete (class 4). Returns the refusal
 * reason, or null when the delete may be sent to core. */
export function deletePreflight(
  targetNumber: string,
  activePartNumber: string | null,
  operationGate: string | null,
): string | null {
  if (operationGate) return operationGate
  if (activePartNumber === targetNumber) {
    return `${targetNumber} is the active model — close it first (Home), then delete`
  }
  return null
}

/** Render ONE structured blocker as a human line. Pure projection of the
 * core-sorted list — no filtering, no reordering, no reinterpretation. */
export function describeBlocker(b: DeletionBlocker): string {
  const owner = b.source_object.number || b.source_object.uuid
  const where =
    b.state === 'released'
      ? `released${b.revision_id ? ` revision ${b.revision_id}` : ''} — permanent`
      : 'working'
  const role = b.candidate_role === 'source' ? 'authored by it' : 'references it'
  return `${b.relationship_type} (${b.relationship_id}) on ${owner} — ${role} (${where})`
}

/** The default deletion reason offered by the confirm dialog; the operator
 * may replace it, but core requires it non-empty. */
export const DEFAULT_DELETE_REASON = 'Deleted from AIADRA Studio workspace tree'
