/**
 * Pure floors for the workspace-tree Part actions (pass workspace-tree-1,
 * arc 20260728-4; contract arc 20260728-3 Codex2 SIGNOFF).
 *
 * The two-sided session rule as regressions: `deletePreflight` is Studio's
 * class-4 session refusal (active part / operation gate), and
 * `describeBlocker` is a pure RENDERING of core's structured blocker list —
 * these tests pin that no reinterpretation (filtering, reordering,
 * remediation-inventing) sneaks in.
 */
import { describe, expect, it } from 'vitest'
import type { DeletionBlocker } from '../aiadra'
import {
  DEFAULT_DELETE_REASON,
  deletePreflight,
  describeBlocker,
  shellTitle,
} from './partActions'

describe('shellTitle (WT-05: the active-part title projection)', () => {
  it('Home (no active part) shows the plain product title', () => {
    expect(shellTitle(null)).toBe('AIADRA Studio')
    expect(shellTitle(null, 'stale-name')).toBe('AIADRA Studio')
  })

  it('active part with a name: `name (Active) — number` before the product title', () => {
    expect(shellTitle('P-000001', 'Bracket')).toBe('Bracket (Active) — P-000001 — AIADRA Studio')
  })

  it('number-only fallback when the name is empty or unknown', () => {
    expect(shellTitle('P-000002', '')).toBe('P-000002 (Active) — AIADRA Studio')
    expect(shellTitle('P-000002', null)).toBe('P-000002 (Active) — AIADRA Studio')
    expect(shellTitle('P-000002', '   ')).toBe('P-000002 (Active) — AIADRA Studio')
  })
})

describe('deletePreflight (the class-4 Studio session refusal)', () => {
  it('refuses the ACTIVE part with the close-it-first reason', () => {
    const reason = deletePreflight('P-000001', 'P-000001', null)
    expect(reason).toContain('P-000001')
    expect(reason).toContain('close it first')
  })

  it('an operation gate refuses verbatim (never reworded)', () => {
    expect(deletePreflight('P-000002', 'P-000001', 'A sketch session is active')).toBe(
      'A sketch session is active',
    )
  })

  it('a non-active part with no gate passes to core (null)', () => {
    expect(deletePreflight('P-000002', 'P-000001', null)).toBeNull()
    expect(deletePreflight('P-000002', null, null)).toBeNull()
  })
})

describe('describeBlocker (pure rendering of the core-sorted list)', () => {
  const working: DeletionBlocker = {
    relationship_id: 'rel_satisfies_ab12cd34',
    relationship_type: 'satisfies',
    source_object: { uuid: 'u-1', number: 'P-000001' },
    candidate_role: 'source',
    state: 'working',
  }
  const released: DeletionBlocker = {
    relationship_id: 'rel_executed_on_ef56',
    relationship_type: 'executed_on',
    source_object: { uuid: 'u-2', number: 'TEX-000001' },
    candidate_role: 'endpoint',
    state: 'released',
    revision_id: 'rev-99',
  }

  it('a working source blocker names type, id, owner, role', () => {
    const line = describeBlocker(working)
    expect(line).toContain('satisfies')
    expect(line).toContain('rel_satisfies_ab12cd34')
    expect(line).toContain('P-000001')
    expect(line).toContain('authored by it')
    expect(line).toContain('working')
  })

  it('a released endpoint blocker is marked permanent with its revision', () => {
    const line = describeBlocker(released)
    expect(line).toContain('executed_on')
    expect(line).toContain('TEX-000001')
    expect(line).toContain('references it')
    expect(line).toContain('revision rev-99')
    expect(line).toContain('permanent')
  })

  it('falls back to the source uuid when the number is empty', () => {
    const line = describeBlocker({
      ...working,
      source_object: { uuid: 'u-orphan', number: '' },
    })
    expect(line).toContain('u-orphan')
  })

  it('never invents a remediation path (honest copy — relationship_retired is a named future design)', () => {
    for (const b of [working, released]) {
      const line = describeBlocker(b)
      expect(line).not.toMatch(/unlink|retire now|remove the relationship/i)
    }
  })
})

describe('the default deletion reason', () => {
  it('is non-empty (core requires minLength 1)', () => {
    expect(DEFAULT_DELETE_REASON.trim().length).toBeGreaterThan(0)
  })
})
